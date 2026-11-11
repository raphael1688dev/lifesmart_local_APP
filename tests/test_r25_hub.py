"""R25 (2026-11-06) hub-level changes: D21 hub key, D4 daily hub info,
D5 reload after reboot, D8 hub configuration actions."""
import asyncio
from types import SimpleNamespace

import pytest

import lifesmart
import lifesmart.button as button_mod
from lifesmart import _resolve_hub_key
from lifesmart.const import DOMAIN
from lifesmart.coordinator import parse_hub_version, parse_timezone
from lifesmart.sensor import LifeSmartHubInfoSensor

from .fakes import AGT, HOST, HUB_REGISTRY_ID, FakeAPI, FakeTimers, runtime, make_env, setup

ServiceValidationError = lifesmart.ServiceValidationError
HomeAssistantError = lifesmart.HomeAssistantError


@pytest.fixture
def env(monkeypatch):
    return make_env(monkeypatch)


# --- D21: hub key -------------------------------------------------------------

def test_hub_key_prefers_the_agt_sub_devices_report():
    assert _resolve_hub_key({"agtid": "other"}, [{"agt": AGT}], "old", HOST) == AGT


def test_hub_key_falls_back_to_agtid():
    assert _resolve_hub_key({"agtid": "HUBID"}, [], None, HOST) == "HUBID"


def test_hub_key_keeps_the_existing_one_when_discovery_is_empty():
    """An empty `eps` must not split the hub device back onto the IP."""
    assert _resolve_hub_key({}, [], AGT, HOST) == AGT


def test_hub_key_falls_back_to_host():
    assert _resolve_hub_key(None, [{"agt": ""}], None, HOST) == HOST


def test_host_keyed_hub_device_moves_to_the_hub_id(env):
    """Pre-R25 install: the device and hub entities keep their ids and
    entity_ids; only the identifier and the unique_id suffix change."""
    env.dev_reg.add("existing-hub", {(DOMAIN, f"hub_{HOST}")}, "entry1")
    env.ent_reg.add("sensor.lifesmart_hub_firmware", "hub_firmware_192_168_1_50", "entry1")
    env.ent_reg.add("button.lifesmart_hub_reboot", "hub_reboot_192_168_1_50", "entry1")
    env.ent_reg.add("sensor.other", "hub_firmware_192_168_1_50", "other-entry")
    setup(env)
    assert env.dev_reg.devices["existing-hub"].identifiers == {(DOMAIN, f"hub_{AGT}")}
    assert runtime(env).hub_device_id == "existing-hub"
    assert runtime(env).hub_key == AGT
    uids = {e.entity_id: e.unique_id for e in env.ent_reg.entities.values()}
    assert uids == {
        "sensor.lifesmart_hub_firmware": f"hub_firmware_{AGT}",
        "button.lifesmart_hub_reboot": f"hub_reboot_{AGT}",
        "sensor.other": "hub_firmware_192_168_1_50",  # another entry: untouched
    }


def test_hub_key_migration_is_idempotent(env):
    env.dev_reg.add("existing-hub", {(DOMAIN, f"hub_{AGT}")}, "entry1")
    setup(env)
    assert not [u for u in env.dev_reg.updates if "new_identifiers" in u[1]]


# --- D4: hub info, daily -------------------------------------------------------

def test_parse_hub_version():
    assert parse_hub_version({"code": 0, "msg": {"ver": "1", "osver": "2", "mgatype": "X"}}) == {
        "ver": "1", "osver": "2", "mgatype": "X",
    }
    assert parse_hub_version({"code": 1}) is None
    assert parse_hub_version("junk") is None


@pytest.mark.parametrize("msg, expected", [
    ({"timezone": 8, "summer": False}, {"timezone": 8, "summer": False}),
    ({"timezone": -12}, {"timezone": -12, "summer": None}),
    ({"timezone": 13}, None),
    ({"timezone": True}, None),   # bool is an int in Python
    ({"timezone": "8"}, None),
])
def test_parse_timezone(msg, expected):
    assert parse_timezone({"code": 0, "msg": msg}) == expected


def test_daily_refresh_updates_device_and_issue(env):
    setup(env)
    data = runtime(env)
    coordinator = data.hub_coordinator
    api = env.apis[0]
    api.version_reply = {"code": 0, "msg": {"ver": "1.0.6", "osver": "4.9", "mgatype": "LSNAMIV3"}}
    coordinator.async_set_updated_data(asyncio.run(coordinator.async_fetch()))
    for listener in coordinator.listeners:
        listener()
    assert env.dev_reg.updates[-1] == (
        HUB_REGISTRY_ID, {"model": "NatureMini Pro", "sw_version": "1.0.6"},
    )
    assert data.hub_info["ver"] == "1.0.6"
    assert "hub_version_unknown_entry1" in env.issues.deleted


def test_failed_refresh_keeps_last_values_and_raises_issue(env):
    setup(env)
    coordinator = runtime(env).hub_coordinator
    env.apis[0].version_reply = {"code": 1}
    info = asyncio.run(coordinator.async_fetch())
    assert info["ver"] == "1.0.5p3" and info["version_ok"] is False
    coordinator.async_set_updated_data(info)
    for listener in coordinator.listeners:
        listener()
    assert env.issues.created[-1][0] == "hub_version_unknown_entry1"
    assert "sw_version" in env.dev_reg.updates[-1][1]  # last known, not wiped


def test_timezone_sensor():
    sensor = LifeSmartHubInfoSensor({"timezone": -5, "summer": True}, AGT, "timezone", "Hub")
    assert sensor._attr_native_value == "UTC-5"
    assert sensor._attr_extra_state_attributes == {"daylight_saving": True}
    assert sensor._attr_unique_id == f"hub_timezone_{AGT}"
    assert LifeSmartHubInfoSensor({}, AGT, "timezone", "Hub")._attr_native_value is None


def test_hub_sensor_unique_id_keeps_the_host_form():
    """Hubs still keyed on the IP keep their pre-R25 unique_ids."""
    sensor = LifeSmartHubInfoSensor({}, HOST, "ver", "Hub")
    assert sensor._attr_unique_id == "hub_firmware_192_168_1_50"


# --- D5: reload after reboot ---------------------------------------------------

def _button(monkeypatch, reply):
    timers = FakeTimers()
    monkeypatch.setattr(button_mod, "async_call_later", timers.call_later)
    api = FakeAPI()
    api.reply = reply
    btn = button_mod.LifeSmartHubRebootButton(api, AGT, {}, "Hub", "entry1")
    reloads: list = []
    btn.hass = SimpleNamespace(config_entries=SimpleNamespace(async_schedule_reload=reloads.append))
    return btn, timers, reloads


@pytest.mark.parametrize("reply", [{"code": 0}, asyncio.TimeoutError()])
def test_reboot_schedules_a_reload(monkeypatch, reply):
    btn, timers, reloads = _button(monkeypatch, reply)
    asyncio.run(btn.async_press())
    (handle,) = timers.active()
    assert handle[0] == button_mod.REBOOT_RELOAD_DELAY_SECONDS
    timers.fire_all()
    assert reloads == ["entry1"]


def test_rejected_reboot_does_not_reload(monkeypatch):
    btn, timers, _ = _button(monkeypatch, {"code": 5})
    asyncio.run(btn.async_press())
    assert not timers.active()


def test_removing_the_button_cancels_the_reload(monkeypatch):
    btn, timers, reloads = _button(monkeypatch, {"code": 0})
    asyncio.run(btn.async_press())
    asyncio.run(btn.async_will_remove_from_hass())
    timers.fire_all()
    assert reloads == []


# --- D8: actions ------------------------------------------------------------------

def _call(env, service, **data):
    handler = env.hass.services.handlers[service]
    return asyncio.run(handler(SimpleNamespace(data={"config_entry_id": "entry1", **data})))


def test_set_hub_timezone_sends_and_refreshes(env):
    setup(env)
    refreshed: list = []
    coordinator = runtime(env).hub_coordinator
    coordinator.async_request_refresh = lambda: asyncio.sleep(0, refreshed.append(True))
    _call(env, "set_hub_timezone", timezone=-3, daylight_saving=True)
    assert env.apis[0].calls == [("set_hub_timezone", -3, True)]
    assert refreshed == [True]


def test_action_for_an_unknown_entry_is_refused(env):
    setup(env)
    handler = env.hass.services.handlers["upgrade_hub_firmware"]
    with pytest.raises(ServiceValidationError):
        asyncio.run(handler(SimpleNamespace(data={"config_entry_id": "nope", "reboot": False})))


def test_rejected_command_raises(env):
    setup(env)
    env.apis[0].reply = {"code": 7}
    with pytest.raises(HomeAssistantError):
        _call(env, "upgrade_hub_firmware", reboot=True)
    assert env.apis[0].calls == [("upgrade_hub", True)]


def test_rename_sub_device_maps_to_me_and_reloads(env):
    setup(env)
    env.dev_reg.add("kitchen", {(DOMAIN, "2711")}, "entry1")
    _call(env, "rename_device", name="Hall", device_id="kitchen")
    assert env.apis[0].calls == [("set_device_name", "Hall", "2711")]
    assert env.hass.config_entries.reloads == ["entry1"]


@pytest.mark.parametrize("device_id", [None, HUB_REGISTRY_ID])
def test_rename_hub(env, device_id):
    setup(env)
    data = {"name": "Hub"} if device_id is None else {"name": "Hub", "device_id": device_id}
    _call(env, "rename_device", **data)
    assert env.apis[0].calls == [("set_device_name", "Hub", None)]


def test_rename_device_of_another_entry_is_refused(env):
    setup(env)
    env.dev_reg.add("foreign", {(DOMAIN, "2711")}, "other-entry")
    with pytest.raises(ServiceValidationError):
        _call(env, "rename_device", name="X", device_id="foreign")
    assert env.apis[0].calls == []


def test_factory_reset_needs_confirm(env):
    setup(env)
    with pytest.raises(ServiceValidationError):
        _call(env, "factory_reset_hub", confirm=False)
    assert env.apis[0].calls == []
    _call(env, "factory_reset_hub", confirm=True)
    assert env.apis[0].calls == [("factory_reset_hub",)]


def test_factory_reset_without_reply_is_not_an_error(env):
    setup(env)
    env.apis[0].reply = asyncio.TimeoutError()
    _call(env, "factory_reset_hub", confirm=True)
