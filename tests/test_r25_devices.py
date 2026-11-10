"""R25 (2026-11-06) device-level changes: D6 reload on paired / removed
devices, D9 new device types and group scenes, D15 coordinator fallback,
D18 resending reads."""
import asyncio
from types import SimpleNamespace

import pytest

import lifesmart
from lifesmart import MEMBERSHIP_RELOAD_DELAY_SECONDS
from lifesmart.api import (
    SCENE_TYPE_OFF,
    SCENE_TYPE_ON,
    LifeSmartAPI,
    _extract_membership_changes,
)
from lifesmart.binary_sensor import LifeSmartConnectivitySensor
from lifesmart.const import CMD_GET, CMD_SET, DOMAIN
from lifesmart.cover import LifeSmartCover
from lifesmart.event import LifeSmartButtonEvent, async_setup_entry as event_setup
from lifesmart.light import async_setup_entry as light_setup
from lifesmart.sensor import async_setup_entry as sensor_setup
from lifesmart.switch import SUPPORTED_SWITCH_TYPES, async_setup_entry as switch_setup

from .fakes import AGT, HUB_REGISTRY_ID, DEVICES, FakeAPI, device_info, entry_data, make_env, setup

MC_ND2 = {"me": "2720", "agt": AGT, "name": "Remote", "devtype": "SL_MC_ND2", "stat": 1,
          "data": {"L1": {"v": 0}, "L2": {"v": 1}, "B1": {"v": 0}, "B2": {"v": 0}, "V": {"v": 77}}}
CLICKER = {"me": "2721", "agt": AGT, "name": "Cube", "devtype": "SL_SC_BB", "stat": 1,
           "data": {"B": {"v": 0}, "V": {"v": 60}}}
CLICKER_V2 = {"me": "2722", "agt": AGT, "name": "Cube 2", "devtype": "SL_SC_BB_V2", "stat": 1,
              "data": {"BN": {"v": 0}, "V": {"v": 55}}}
SCENES = [
    {"id": "AI0000000001", "name": "Evening", "cls": "scene"},
    {"id": "AI0000000002", "name": "All lights", "cls": "groupsw"},
    {"id": "AI0000000003", "name": "Fast bulbs", "cls": "grouphw"},
    {"id": "AI0000000004", "name": "Strip group", "cls": "grouprgbw"},
]


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(FakeAPI, "devices", DEVICES + [MC_ND2, CLICKER, CLICKER_V2])
    monkeypatch.setattr(FakeAPI, "scenes", SCENES)
    return make_env(monkeypatch)


def _platform(env, setup_fn):
    added: list = []
    asyncio.run(setup_fn(env.hass, env.entry, added.extend))
    return added


# --- D6: reload when the hub reports a paired / removed device ------------------

@pytest.mark.parametrize("message, expected", [
    ({"add": [{"devtype": "SL_SW_ND1", "me": "27aa"}]}, ({"27aa"}, set())),
    ({"del": {"devtype": "SL_SW_ND1", "me": "2711"}}, (set(), {"2711"})),
    ({"msg": {"add": [{"me": "27aa"}], "del": [{"me": "2711"}]}}, ({"27aa"}, {"2711"})),
    ({"chg": [{"me": "2711", "L1": {"v": 1}}]}, (set(), set())),
    ({"add": "junk", "del": [{"me": 5}]}, (set(), set())),
])
def test_extract_membership_changes(message, expected):
    assert _extract_membership_changes(message) == expected


def _notify(env, message):
    for listener in list(env.apis[0].report_listeners):
        listener(message)


def test_new_device_reloads_once_after_the_events_settle(env):
    setup(env)
    _notify(env, {"add": [{"me": "27aa"}]})
    _notify(env, {"add": [{"me": "27ab"}]})
    (handle,) = env.timers.active()  # the second event restarted the wait
    assert handle[0] == MEMBERSHIP_RELOAD_DELAY_SECONDS
    env.timers.fire_all()
    assert env.hass.config_entries.reloads == ["entry1"]


def test_removed_known_device_reloads(env):
    setup(env)
    _notify(env, {"del": [{"me": "2711"}]})
    env.timers.fire_all()
    assert env.hass.config_entries.reloads == ["entry1"]


@pytest.mark.parametrize("message", [
    {"add": [{"me": "2711"}]},   # already known
    {"del": [{"me": "9999"}]},   # never had it
    {"chg": [{"me": "2711", "stat": 0}]},
])
def test_no_reload_without_a_real_change(env, message):
    setup(env)
    _notify(env, message)
    assert not env.timers.active()


def test_unload_cancels_a_pending_reload(env):
    setup(env)
    _notify(env, {"add": [{"me": "27aa"}]})
    asyncio.run(lifesmart.async_unload_entry(env.hass, env.entry))
    env.timers.fire_all()
    assert env.hass.config_entries.reloads == []
    assert env.apis[0].report_listeners == []


# --- D9: multi-control accessory, CUBE clickers ---------------------------------

def test_multi_control_accessory_channels_are_switches(env):
    assert {"SL_MC_ND1", "SL_MC_ND2", "SL_MC_ND3"} <= set(SUPPORTED_SWITCH_TYPES)
    setup(env)
    switches = [e for e in _platform(env, switch_setup) if getattr(e, "_device", {}).get("me") == "2720"]
    assert sorted(e._idx for e in switches) == ["L1", "L2"]


def test_clicker_batteries(env):
    setup(env)
    batteries = {
        e._device["me"] for e in _platform(env, sensor_setup)
        if type(e).__name__ == "LifeSmartBatterySensor"
    }
    assert {"2720", "2721", "2722"} <= batteries


def test_button_events_are_created_per_reported_channel(env):
    setup(env)
    events = _platform(env, event_setup)
    assert sorted((e._device["me"], e._idx) for e in events) == [
        ("2720", "B1"), ("2720", "B2"), ("2721", "B"), ("2722", "BN"),
    ]
    for e in events:
        assert device_info(e)["via_device_id"] == HUB_REGISTRY_ID
        assert e._attr_unique_id == f"event_{AGT}_{e._device['me']}_{e._idx}"


def _event(device, idx):
    from lifesmart.event import BUTTON_CHANNELS
    entity = LifeSmartButtonEvent(FakeAPI(), device, idx, BUTTON_CHANNELS[device["devtype"]][1])
    entity.hass = None
    return entity


@pytest.mark.parametrize("val, expected", [
    (1, ("press_start", None)),
    (0, ("press_end", None)),
])
def test_press_release_buttons(val, expected):
    entity = _event(MC_ND2, "B1")
    entity._handle_value(val)
    assert entity.last_event == expected


@pytest.mark.parametrize("val, expected", [
    (1, ("single_press", None)),
    (2, ("multi_press", {"press_count": 2})),
    (255, ("long_press_start", None)),
])
def test_clicker_v2_gestures(val, expected):
    entity = _event(CLICKER_V2, "BN")
    entity._handle_value(val)
    assert entity.last_event == expected


def test_unknown_button_value_fires_nothing():
    entity = _event(CLICKER_V2, "BN")
    entity._handle_value(0)   # v2 sends no release
    entity._handle_value("x")
    assert not hasattr(entity, "last_event")


# --- D9: group scenes ---------------------------------------------------------------

def test_group_scenes_land_on_switch_and_light(env):
    setup(env)
    group_switches = [e for e in _platform(env, switch_setup) if hasattr(e, "_scene_id")]
    lights = _platform(env, light_setup)
    assert [e._scene_id for e in group_switches] == ["AI0000000002"]
    assert sorted(e._scene_id for e in lights) == ["AI0000000003", "AI0000000004"]
    for e in group_switches + lights:
        assert e._attr_assumed_state is True
        assert device_info(e)["identifiers"] == {(DOMAIN, f"hub_{AGT}")}
    assert group_switches[0].entity_id == "switch.lifesmart_all_lights_00000002"


def test_scene_list_is_read_once(env):
    from lifesmart.scene import async_setup_entry as scene_setup
    setup(env)
    scenes = _platform(env, scene_setup)
    assert [s._scene_id for s in scenes] == ["AI0000000001"]


def test_group_scene_on_off(env):
    setup(env)
    (group,) = [e for e in _platform(env, switch_setup) if hasattr(e, "_scene_id")]
    writes: list = []
    group.async_write_ha_state = lambda: writes.append(group._attr_is_on)
    asyncio.run(group.async_turn_on())
    asyncio.run(group.async_turn_off())
    assert env.apis[0].calls == [
        ("trigger_scene", "AI0000000002", SCENE_TYPE_ON),
        ("trigger_scene", "AI0000000002", SCENE_TYPE_OFF),
    ]
    assert writes == [True, False]


def test_rejected_group_scene_keeps_state(env):
    setup(env)
    (group,) = [e for e in _platform(env, switch_setup) if hasattr(e, "_scene_id")]
    env.apis[0].reply = {"code": 3}
    with pytest.raises(lifesmart.HomeAssistantError):
        asyncio.run(group.async_turn_on())
    assert group._attr_is_on is None


# --- D15: coordinator fallback ---------------------------------------------------

class _Coordinator:
    def __init__(self, data):
        self.data = data


def test_connectivity_follows_the_coordinator():
    sensor = LifeSmartConnectivitySensor(FakeAPI(), DEVICES[0], coordinator=_Coordinator(
        {"2711": {**DEVICES[0], "stat": 0}}
    ))
    sensor.async_write_ha_state = lambda: None
    assert sensor._attr_is_on is True
    sensor._handle_coordinator_update()
    assert sensor._attr_is_on is False


def test_cover_follows_the_coordinator():
    curtain = DEVICES[1]
    cover = LifeSmartCover(FakeAPI(), curtain, coordinator=_Coordinator(
        {"2712": {**curtain, "data": {"P1": {"v": 50}}}}
    ))
    cover.hass = None
    cover._handle_coordinator_update()
    assert cover._attr_is_closed is False


def test_binary_sensor_no_longer_polls_on_its_own():
    import lifesmart.binary_sensor as bs
    assert not hasattr(bs, "async_track_time_interval")


# --- D18: resend reads --------------------------------------------------------------

def _api_with_attempts(outcomes):
    api = LifeSmartAPI("h", "m", "t")
    seen: list = []

    async def once(obj, args, pkg_type, timeout):
        seen.append(obj)
        result = outcomes[len(seen) - 1]
        if isinstance(result, BaseException):
            raise result
        return result
    api._send_once = once
    return api, seen


def test_get_is_resent_once_after_a_timeout():
    api, seen = _api_with_attempts([asyncio.TimeoutError(), {"code": 0}])
    assert asyncio.run(api.send_command("eps", {}, CMD_GET)) == {"code": 0}
    assert seen == ["eps", "eps"]


def test_get_gives_up_after_the_retry():
    api, seen = _api_with_attempts([asyncio.TimeoutError(), asyncio.TimeoutError()])
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(api.send_command("eps", {}, CMD_GET))
    assert len(seen) == 2


def test_set_is_not_resent_by_default():
    api, seen = _api_with_attempts([asyncio.TimeoutError(), {"code": 0}])
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(api.send_command("doscene", {}, CMD_SET))
    assert seen == ["doscene"]


@pytest.mark.parametrize("method, args", [
    ("send_remote_key", ("id", "vol_up")),
    ("trigger_scene", ("AI1",)),
    ("reboot_hub", ()),
    ("factory_reset_hub", ()),
    ("upgrade_hub", (False,)),
])
def test_commands_that_act_on_every_delivery_are_never_resent(method, args):
    api, seen = _api_with_attempts([asyncio.TimeoutError(), {"code": 0}])
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(getattr(api, method)(*args))
    assert len(seen) == 1


def test_each_attempt_uses_a_new_message_id():
    api = LifeSmartAPI("h", "m", "t")
    ids: list = []

    async def fake_start():
        api._transport = SimpleNamespace(sendto=lambda message, addr: ids.append(api.sequence - 1))
    api.async_start = fake_start
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(api.send_command("eps", {}, CMD_GET, timeout=0.01))
    assert len(ids) == 2 and ids[0] != ids[1]


# --- R27: HA 2026.12 button event types ---------------------------------------

def test_event_types_avoid_deprecated_members():
    """2026.12 deprecates multi_press_end / multi_press_count (gone in
    2027.5.0) and the event module must not touch them, not even at import."""
    import ast
    import inspect
    import lifesmart.event as ev
    tree = ast.parse(inspect.getsource(ev))
    deprecated = {"MULTI_PRESS_END", "MULTI_PRESS_ONGOING", "ATTR_MULTI_PRESS_COUNT", "ButtonEventType"}
    used = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    used |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not used & deprecated
    types = {t for _, value_map in ev.BUTTON_CHANNELS.values() for t, _ in value_map.values()}
    assert types <= {"press_start", "press_end", "single_press", "multi_press",
                     "long_press_start", "long_press_end"}


def test_multi_press_is_listed_with_single_press():
    """HA: only list multi_press when single_press is listed too."""
    from lifesmart.event import BUTTON_CHANNELS
    for _, value_map in BUTTON_CHANNELS.values():
        types = {t for t, _ in value_map.values()}
        assert "multi_press" not in types or "single_press" in types
