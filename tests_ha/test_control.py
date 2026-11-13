"""Commands from Home Assistant reach the hub, and the hub's answers and
events reach the entities (R40). Against tests_ha/hub.py."""
from datetime import timedelta

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import async_fire_time_changed

from . import hub as sim_hub

A = sim_hub.AGT.lower()
STAIRS_L1 = f"switch.sl_sw_nd3_{A}_2711_l1"
STAIRS_L2 = f"switch.sl_sw_nd3_{A}_2711_l2"
CURTAIN = f"cover.sl_p_{A}_2714_p1"
REMOTE = f"remote.tv_remote_{A}_2715"
CLICKER = f"event.sl_sc_bb_v2_{A}_2716_bn"
ACCESSORY_BUTTON = f"event.sl_mc_nd1_{A}_2717_b1"
SCENE = "scene.lifesmart_movie_night_e_000001"
GROUP_SWITCH = "switch.lifesmart_all_lamps_p_000002"
GROUP_LIGHT = "light.lifesmart_bulbs_p_000003"


async def _call(hass, domain, service, entity_id, **data):
    await hass.services.async_call(domain, service, {"entity_id": entity_id, **data}, blocking=True)
    await hass.async_block_till_done()


def _state(hass, entity_id):
    return hass.states.get(entity_id).state


# --- switches ------------------------------------------------------------------------

def _reads(sim, me, idx):
    return [a for o, a, kind in sim.received
            if o == "ep" and kind == sim_hub.GET and a.get("me") == me and a.get("idx") == idx]


async def test_turning_a_channel_on_and_off(hass, sim, loaded):
    reads_at_start = len(_reads(sim, "2711", "L2"))
    await _call(hass, "switch", "turn_on", STAIRS_L2)
    assert _state(hass, STAIRS_L2) == "on"
    await _call(hass, "switch", "turn_off", STAIRS_L2)
    assert _state(hass, STAIRS_L2) == "off"
    # LI §3.3.3: tag m, type 0x81 on / 0x80 off. (The read at start-up is
    # the same `ep` without `tag`.)
    assert sim.sent("ep", me="2711", idx="L2", tag="m") == [
        {"tag": "m", "me": "2711", "idx": "L2", "type": 0x81, "val": 1},
        {"tag": "m", "me": "2711", "idx": "L2", "type": 0x80, "val": 0},
    ]
    # The hub's NOTIFY confirmed both; nothing was read back.
    assert len(_reads(sim, "2711", "L2")) == reads_at_start


async def test_a_switch_without_a_confirming_event_reads_the_channel(hass, sim, loaded):
    """No NOTIFY within 1.5 s: the state is read back with `ep`."""
    sim.push_after_set = False
    reads_before = len(sim.sent("ep", me="2711", idx="L2"))
    await _call(hass, "switch", "turn_on", STAIRS_L2)
    assert _state(hass, STAIRS_L2) == "on"
    gets = [a for o, a, t in sim.received if o == "ep" and t == sim_hub.GET and a.get("idx") == "L2"]
    assert len(gets) >= 1
    assert len(sim.sent("ep", me="2711", idx="L2")) > reads_before


async def test_a_refused_command_reads_the_real_state(hass, sim, loaded):
    sim.overrides["ep"] = [{"code": 10004, "msg": "refused"}]
    await _call(hass, "switch", "turn_on", STAIRS_L2)
    assert _state(hass, STAIRS_L2) == "off"


async def test_a_command_the_hub_does_not_answer(hass, sim, loaded):
    """No reply to the SET within 0.7 s is taken as sent; the read-back
    that follows gets no answer either; the state is left as it was."""
    sim.overrides["ep"] = [TimeoutError(), TimeoutError()]
    await _call(hass, "switch", "turn_on", STAIRS_L2)
    assert _state(hass, STAIRS_L2) == "off"


async def test_a_switched_channel_reported_by_the_hub(hass, sim, loaded):
    """Someone pressed the wall switch: the hub sends a NOTIFY (LI §4)."""
    sim.push(body={"chg": [{"me": "2711", "L1": {"v": 0}}]})
    await hass.async_block_till_done()
    assert _state(hass, STAIRS_L1) == "off"
    # The other form a NOTIFY may take, one channel under `msg`.
    sim.push(body={"msg": {"me": "2711", "idx": "L1", "data": {"v": 1}}})
    await hass.async_block_till_done()
    assert _state(hass, STAIRS_L1) == "on"
    sim.push(body={"msg": {"me": "2711", "idx": "L1", "val": 0}})
    await hass.async_block_till_done()
    assert _state(hass, STAIRS_L1) == "off"


async def test_quick_successive_commands_end_in_the_last_one(hass, sim, loaded):
    import asyncio

    await asyncio.gather(
        _call(hass, "switch", "turn_on", STAIRS_L2),
        _call(hass, "switch", "turn_off", STAIRS_L2),
        _call(hass, "switch", "turn_on", STAIRS_L2),
    )
    assert _state(hass, STAIRS_L2) == "on"
    sets = [a["val"] for o, a, t in sim.received if o == "ep" and t == sim_hub.SET]
    assert sets[-1] == 1 and len(sets) <= 3


# --- group scenes as switch / light (LI §5.2) ------------------------------------------

@pytest.mark.parametrize(("domain", "entity_id", "scene_id"), [
    ("switch", GROUP_SWITCH, "AI_GROUP_000002"),
    ("light", GROUP_LIGHT, "AI_GROUP_000003"),
])
async def test_group_scenes(hass, sim, loaded, domain, entity_id, scene_id):
    assert _state(hass, entity_id) == "unknown"
    await _call(hass, domain, "turn_on", entity_id)
    assert _state(hass, entity_id) == "on"
    await _call(hass, domain, "turn_off", entity_id)
    assert _state(hass, entity_id) == "off"
    assert sim.sent("doscene", id=scene_id) == [
        {"id": scene_id, "args": {"type": 0x81}},
        {"id": scene_id, "args": {"type": 0x80}},
    ]
    sim.overrides["doscene"] = [{"code": 3}]
    with pytest.raises(HomeAssistantError):
        await _call(hass, domain, "turn_on", entity_id)
    assert _state(hass, entity_id) == "off"
    sim.overrides["doscene"] = [TimeoutError()]
    with pytest.raises(HomeAssistantError):
        await _call(hass, domain, "turn_on", entity_id)


# --- scenes --------------------------------------------------------------------------

async def test_a_scene(hass, sim, loaded):
    await _call(hass, "scene", "turn_on", SCENE)
    assert sim.sent("doscene", id="AI_SCENE_000001") == [
        {"id": "AI_SCENE_000001", "args": {"type": 128}},
    ]
    # A refusal or no answer is logged, not raised (as before R40).
    sim.overrides["doscene"] = [{"code": 3}, TimeoutError()]
    await _call(hass, "scene", "turn_on", SCENE)
    await _call(hass, "scene", "turn_on", SCENE)


# --- curtain (D1: the state channel is not verified on hardware) ------------------------

async def test_the_curtain(hass, sim, loaded):
    await _call(hass, "cover", "open_cover", CURTAIN)
    await _call(hass, "cover", "close_cover", CURTAIN)
    await _call(hass, "cover", "stop_cover", CURTAIN)
    assert [(a["idx"], a["type"]) for a in sim.sent("ep", me="2714") if "tag" in a] == [
        ("P2", 0x81), ("P3", 0x81), ("P4", 0x81),
    ]
    sim.push(body={"chg": [{"me": "2714", "P1": {"v": 50}}]})
    await hass.async_block_till_done()
    assert _state(hass, CURTAIN) == "open"
    sim.push(body={"chg": [{"me": "2714", "P1": {"v": 0}}]})
    await hass.async_block_till_done()
    assert _state(hass, CURTAIN) == "closed"


# --- buttons (events) -----------------------------------------------------------------

@pytest.mark.parametrize(("entity_id", "me", "idx", "value", "event_type"), [
    (CLICKER, "2716", "BN", 1, "single_press"),
    (CLICKER, "2716", "BN", 2, "multi_press"),
    (CLICKER, "2716", "BN", 255, "long_press_start"),
    (ACCESSORY_BUTTON, "2717", "B1", 1, "press_start"),
    (ACCESSORY_BUTTON, "2717", "B1", 0, "press_end"),
])
async def test_button_events(hass, sim, loaded, entity_id, me, idx, value, event_type):
    sim.push(body={"chg": [{"me": me, idx: {"v": value}}]})
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == event_type
    if event_type == "multi_press":
        assert state.attributes["press_count"] == 2


async def test_a_button_value_with_no_meaning_fires_nothing(hass, sim, loaded):
    sim.push(body={"chg": [{"me": "2716", "BN": {"v": 0}}]})  # V2 sends no release
    await hass.async_block_till_done()
    assert _state(hass, CLICKER) == "unknown"


async def test_a_button_state_from_the_poll_is_not_a_press(hass, sim, loaded):
    sim.device("2716")["data"]["BN"]["v"] = 1
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=16))
    await hass.async_block_till_done()
    assert _state(hass, CLICKER) == "unknown"


# --- IR remote (SL_P_IR) ----------------------------------------------------------------

async def test_the_remote(hass, sim, loaded):
    state = hass.states.get(REMOTE)
    assert state.attributes["all_commands"] == ["power", "vol_up"]
    await _call(hass, "remote", "send_command", REMOTE, command=["power", "AI_IR_2715_1::vol_up"])
    assert sim.sent("spotremote", cmd="sendkey") == [
        {"id": "AI_IR_2715_1", "cmd": "sendkey", "key": "power"},
        {"id": "AI_IR_2715_1", "cmd": "sendkey", "key": "vol_up"},
    ]


async def test_a_key_learned_since_setup_is_found(hass, sim, loaded):
    sim.remote_keys["AI_IR_2715_1"]["mute"] = "k3"
    await _call(hass, "remote", "send_command", REMOTE, command=["mute"])
    assert sim.sent("spotremote", cmd="sendkey", key="mute")
    sim.remotes.append({"id": "AI_IR_2715_2", "name": "Fan"})
    sim.remote_keys["AI_IR_2715_2"] = {"speed": "k9"}
    await _call(hass, "remote", "send_command", REMOTE, command=["AI_IR_2715_2::speed"])
    assert sim.sent("spotremote", cmd="sendkey", id="AI_IR_2715_2")


async def test_unknown_keys_and_lost_packets(hass, sim, loaded):
    await _call(hass, "remote", "send_command", REMOTE, command=["no_such_key", "AI_IR_2715_1::nope"])
    assert not sim.sent("spotremote", cmd="sendkey")
    # A key whose request is lost is tried three times in all.
    sim.overrides["spotremote:sendkey"] = [TimeoutError(), TimeoutError(), TimeoutError()]
    await _call(hass, "remote", "send_command", REMOTE, command=["power"])
    assert len(sim.sent("spotremote", cmd="sendkey", key="power")) == 3
    sim.overrides["spotremote:sendkey"] = [TimeoutError(), TimeoutError(), TimeoutError()]
    await _call(hass, "remote", "send_command", REMOTE, command=["AI_IR_2715_1::power"])
    assert len(sim.sent("spotremote", cmd="sendkey", key="power")) == 6


# --- reboot button (D5: reload two minutes later) ------------------------------------------

async def test_reboot_reloads_two_minutes_later(hass, sim, loaded):
    await _call(hass, "button", "press", "button.lifesmart_hub_reboot")
    assert sim.sent("config", cfg="reboot")
    apis_before = len(sim.apis)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=121))
    await hass.async_block_till_done()
    assert len(sim.apis) == apis_before + 1
    assert loaded.state is ConfigEntryState.LOADED


@pytest.mark.parametrize("reply", [TimeoutError(), {"code": 7}])
async def test_reboot_with_no_answer_or_a_refusal(hass, sim, loaded, reply):
    sim.overrides["config:reboot"] = [reply]
    await _call(hass, "button", "press", "button.lifesmart_hub_reboot")
    apis_before = len(sim.apis)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=121))
    await hass.async_block_till_done()
    # No answer: probably restarting, so reload. A refusal: nothing happened.
    assert len(sim.apis) == apis_before + (1 if isinstance(reply, TimeoutError) else 0)


async def test_pressing_twice_reloads_once(hass, sim, loaded):
    await _call(hass, "button", "press", "button.lifesmart_hub_reboot")
    await _call(hass, "button", "press", "button.lifesmart_hub_reboot")
    apis_before = len(sim.apis)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=121))
    await hass.async_block_till_done()
    assert len(sim.apis) == apis_before + 1


async def test_unloading_cancels_the_pending_reload(hass, sim, loaded):
    await _call(hass, "button", "press", "button.lifesmart_hub_reboot")
    assert await hass.config_entries.async_unload(loaded.entry_id)
    apis_before = len(sim.apis)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=121))
    await hass.async_block_till_done()
    assert len(sim.apis) == apis_before
    assert loaded.state is ConfigEntryState.NOT_LOADED
