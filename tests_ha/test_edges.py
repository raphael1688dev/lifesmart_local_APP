"""Odd replies, failed reads, renamed entities, older registry layouts (R40).

What a real hub has not been seen to send is marked as such; these tests
check that the integration keeps working, not that a hub behaves this way.
"""
from datetime import timedelta

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import async_fire_time_changed

from custom_components.lifesmart.api import LifeSmartAPI
from custom_components.lifesmart.const import DOMAIN

from . import hub as sim_hub
from .conftest import make_entry

A = sim_hub.AGT.lower()
STAIRS_L1 = f"switch.sl_sw_nd3_{A}_2711_l1"
STAIRS_BATTERY = f"sensor.sl_sw_nd3_{A}_2711_v"
STAIRS_ONLINE = f"binary_sensor.sl_sw_nd3_{A}_2711_connectivity"
STAIRS_SIGNAL = f"sensor.sl_sw_nd3_{A}_2711_signal"
NATURE_T = f"sensor.sl_nature_{A}_2713_t"
CURTAIN = f"cover.sl_p_{A}_2714_p1"
REMOTE = f"remote.tv_remote_{A}_2715"


async def _setup(hass, entry=None):
    entry = entry or make_entry()
    if entry.entry_id not in {e.entry_id for e in hass.config_entries.async_entries(DOMAIN)}:
        entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def _poll(hass, minutes=16):
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=minutes))
    await hass.async_block_till_done(wait_background_tasks=True)


def _state(hass, entity_id):
    return hass.states.get(entity_id).state


# --- signal strength, once the user enables it ------------------------------------------

@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_signal_strength_when_enabled(hass, sim, loaded):
    assert _state(hass, STAIRS_SIGNAL) == "-61"
    sim.device("2711")["lDbm"] = -75
    await _poll(hass)
    assert _state(hass, STAIRS_SIGNAL) == "-75"
    sim.device("2711")["lDbm"] = "weak"
    await _poll(hass, 32)
    assert _state(hass, STAIRS_SIGNAL) == "-75"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("reply", [{"code": 9}, {"code": 0, "msg": "x"}, {"code": 0, "msg": {}}])
async def test_signal_strength_read_at_start_that_gives_nothing(hass, sim, reply):
    """The value from `eps` stays when the one-off read at start fails."""
    real_answer = sim.answer

    def answer(api, obj, args, pkg_type):
        if obj == "ep" and pkg_type == sim_hub.GET and "idx" not in args:
            return reply
        return real_answer(api, obj, args, pkg_type)
    sim.answer = answer
    await _setup(hass)
    assert _state(hass, STAIRS_SIGNAL) == "-61"


# --- reads at start that fail or come back odd --------------------------------------------

@pytest.mark.parametrize("reply", [
    TimeoutError(),                      # nothing
    {"code": 0, "msg": {"data": {}}},     # the channel missing
    {"code": 0, "msg": "x"},              # not a device
    {"code": 0},                          # no msg
])
async def test_reads_at_start_that_fail_keep_the_values_from_discovery(hass, sim, reply):
    sim.overrides["ep"] = [reply] * 40
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert _state(hass, NATURE_T) == "24.5"
    assert _state(hass, STAIRS_BATTERY) == "90"
    assert _state(hass, STAIRS_L1) == "on"
    # The curtain is the exception: it takes its state only from that read,
    # not from discovery, so it is unknown until the 15-minute poll (D1:
    # which channel carries the state is not verified anyway).
    assert _state(hass, CURTAIN) == "unknown"
    sim.overrides["ep"] = []
    await _poll(hass)
    assert _state(hass, CURTAIN) == "closed"


async def test_a_device_without_a_temperature_value(hass, sim):
    del sim.device("2713")["data"]["T"]["v"]
    sim.overrides["ep"] = [TimeoutError()] * 40
    await _setup(hass)
    assert _state(hass, NATURE_T) == "unknown"


async def test_a_device_without_a_name_gets_no_temperature_sensor(hass, sim):
    """The temperature sensor's setup reads `name` and skips the device
    without it (as before R40); its other entities are created."""
    del sim.device("2713")["name"]
    await _setup(hass)
    assert hass.states.get(NATURE_T) is None
    assert hass.states.get(f"switch.sl_nature_{A}_2713_l1") is not None


# --- values pushed or polled that are not numbers ------------------------------------------

async def test_values_that_are_not_numbers_are_ignored(hass, sim, loaded):
    sim.push(body={"chg": [
        {"me": "2711", "L1": {"v": "on"}, "V": {"v": None}, "stat": "1"},
        {"me": "2713", "T": {"v": "warm"}},
        {"me": "2714", "P1": {"v": "half"}, "P8": {"v": []}},
    ]})
    sim.push(body={"msg": {"me": "2711", "idx": "L1", "data": {"v": "on"}, "val": "on"}})
    await hass.async_block_till_done(wait_background_tasks=True)
    sim.device("2711")["stat"] = True
    sim.device("2711")["data"]["V"]["v"] = "full"
    sim.device("2713")["data"]["T"]["v"] = None
    sim.device("2714")["data"]["P1"] = "x"
    await _poll(hass)
    assert _state(hass, STAIRS_L1) == "on"
    assert _state(hass, STAIRS_BATTERY) == "90"
    assert _state(hass, STAIRS_ONLINE) == "on"
    assert _state(hass, NATURE_T) == "24.5"
    assert _state(hass, CURTAIN) == "closed"


async def test_a_device_missing_from_a_poll_keeps_its_state(hass, sim, loaded):
    sim.devices = [d for d in sim.devices if d["me"] != "2711"]
    await _poll(hass)
    assert _state(hass, STAIRS_L1) == "on"
    assert _state(hass, STAIRS_ONLINE) == "on"


@pytest.mark.parametrize("devices", [
    {"2711": None},                           # dict form, nothing usable
    [{"me": 2711}, "not a device"],           # list form, nothing usable
])
async def test_a_poll_with_nothing_usable(hass, sim, loaded, devices):
    sim.overrides["eps"] = [{"code": 0, "msg": devices}]
    await _poll(hass)
    assert _state(hass, STAIRS_L1) == "on"


# --- the hub's own replies, odd ------------------------------------------------------------

@pytest.mark.parametrize("timezone", [
    {"code": 0, "msg": {"timezone": 15, "summer": False}},     # out of range
    {"code": 0, "msg": {"timezone": True, "summer": False}},   # not a number
    {"code": 0, "msg": {"timezone": 8, "summer": "no"}},       # summer unknown
    TimeoutError(),
])
async def test_an_odd_time_zone_reply(hass, sim, timezone):
    sim.overrides["config:timezone"] = [timezone, timezone]
    entry = await _setup(hass)
    state = hass.states.get("sensor.lifesmart_hub_timezone")
    if timezone is not None and isinstance(timezone, dict) and timezone["msg"]["timezone"] == 8:
        assert state.state == "UTC+8" and "daylight_saving" not in state.attributes
    else:
        assert state.state == "unknown"
    assert entry.state is ConfigEntryState.LOADED


async def test_version_read_with_no_answer(hass, sim):
    sim.overrides["config:getver"] = [TimeoutError(), TimeoutError()]
    await _setup(hass)
    assert _state(hass, "sensor.lifesmart_hub_firmware") == "unknown"


async def test_subscribing_to_events_fails_at_start(hass, sim):
    """The hub does not answer cfg:notify at start: set up anyway; the
    90 s renewal subscribes later."""
    sim.overrides["config:notify"] = [TimeoutError(), TimeoutError()]
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=91))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(sim.sent("config", cfg="notify")) >= 3


@pytest.mark.parametrize("scenes", [TimeoutError(), {"code": 0, "msg": {"not": "a list"}}])
async def test_scene_list_unreadable(hass, sim, scenes):
    sim.overrides["scene"] = [scenes, scenes]
    entry = await _setup(hass)
    assert entry.runtime_data.scenes == []


async def test_devices_sent_as_a_dict(hass, sim):
    """Some firmware answers `eps` with {id: device} instead of a list."""
    as_dict = {d["me"]: d for d in sim.devices}
    sim.overrides["eps"] = [{"code": 0, "msg": {**as_dict, "note": "x"}}]
    entry = await _setup(hass)
    assert len(entry.runtime_data.devices) == 8


async def test_a_remote_list_the_hub_cannot_give(hass, sim):
    sim.overrides["spotremote:getlist"] = [{"code": 5}, {"code": 5}]
    await _setup(hass)
    assert hass.states.get(REMOTE).attributes["all_commands"] == []


# --- datagrams that are not what they should be (LI §3.1) ----------------------------------

async def test_garbage_datagrams_are_dropped(hass, sim, loaded):
    api = loaded.runtime_data.api
    for packet in (
        b"short",
        b"XX" + sim_hub.datagram(9, {"chg": []})[2:],     # wrong marker
        sim_hub.datagram(9, {})[:10] + b"{not json",
        b"JL\x00\x00\x00\x09\x00\x00\x00\x02\xff\xfe",      # not UTF-8
    ):
        api._protocol.datagram_received(packet, (sim_hub.HOST, 12348))
    sim.push(body={"chg": [{"me": "2711", "L1": {"v": 0}}]})
    await hass.async_block_till_done()
    assert _state(hass, STAIRS_L1) == "off"


async def test_a_failing_listener_does_not_stop_the_others(hass, sim, loaded):
    api = loaded.runtime_data.api

    def broken(_value):
        raise RuntimeError("listener bug")
    unsub_state = api.register_state_listener("2711", "L1", broken)
    unsub_report = api.register_report_listener(broken)
    sim.push(body={"chg": [{"me": "2711", "L1": {"v": 0}}]})
    await hass.async_block_till_done()
    assert _state(hass, STAIRS_L1) == "off"
    unsub_state()
    unsub_state()        # twice is harmless
    unsub_report()


async def test_an_api_that_was_never_started():
    api = LifeSmartAPI(sim_hub.HOST, sim_hub.MODEL, sim_hub.TOKEN)
    await api.async_stop()   # nothing to stop
    api.register_state_listener("2711", "L1", lambda v: None)()


# --- renaming an entity in Home Assistant (R19) --------------------------------------------

async def test_an_entity_renamed_by_the_user_keeps_working(hass, sim, loaded):
    """HA 2026.11+ renames in place when the entity class has the hook
    (R19). The pushed value still reaches it under its new id."""
    registry = er.async_get(hass)
    registry.async_update_entity(STAIRS_L1, new_entity_id="switch.hall_light")
    await hass.async_block_till_done()
    assert hass.states.get(STAIRS_L1) is None
    sim.push(body={"chg": [{"me": "2711", "L1": {"v": 0}}]})
    await hass.async_block_till_done()
    assert _state(hass, "switch.hall_light") == "off"
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.hall_light"}, blocking=True)
    assert _state(hass, "switch.hall_light") == "on"


# --- older registry layouts --------------------------------------------------------------

async def test_hub_entities_keyed_on_the_address_move_with_the_hub_device(hass, sim):
    """D21 (R25): hub entities' unique ids end in the hub key."""
    entry = make_entry()
    entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, f"hub_{sim_hub.HOST}")},
    )
    host_slug = sim_hub.HOST.replace(".", "_")
    firmware = entities.async_get_or_create(
        "sensor", DOMAIN, f"hub_firmware_{host_slug}", config_entry=entry,
    )
    entities.async_get_or_create(
        "sensor", DOMAIN, "not_a_hub_entity", config_entry=entry,
    )
    await _setup(hass, entry)
    assert entities.async_get(firmware.entity_id).unique_id == f"hub_firmware_{sim_hub.AGT}"


async def test_two_hub_devices_are_left_alone(hass, sim):
    """Both the address-keyed and the id-keyed hub device exist (an earlier
    migration half done): nothing is merged."""
    entry = make_entry()
    entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    old = devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, f"hub_{sim_hub.HOST}")},
    )
    devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, f"hub_{sim_hub.AGT}")},
    )
    await _setup(hass, entry)
    assert devices.async_get(old.id).identifiers == {(DOMAIN, f"hub_{sim_hub.HOST}")}


async def test_a_remote_with_its_entity_id_from_before_r10(hass, sim):
    """R10-b: remote entity ids gained the hub id; the old one is renamed."""
    entry = make_entry()
    entry.add_to_hass(hass)
    entities = er.async_get(hass)
    old = entities.async_get_or_create(
        "remote", DOMAIN, f"remote_{sim_hub.AGT}_2715", config_entry=entry,
        suggested_object_id="tv_remote_2715",
    )
    assert old.entity_id == "remote.tv_remote_2715"
    await _setup(hass, entry)
    assert entities.async_get_entity_id("remote", DOMAIN, f"remote_{sim_hub.AGT}_2715") == REMOTE


async def test_version_1_entry_with_devices_as_a_dict_and_odd_unique_ids(hass, sim):
    entry = make_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, version=1)
    as_dict = {d["me"]: d for d in sim.devices}
    sim.overrides["eps"] = [{"code": 0, "msg": as_dict}]
    entities = er.async_get(hass)
    odd = entities.async_get_or_create("switch", DOMAIN, "nounderscore", config_entry=entry)
    await _setup(hass, entry)
    assert entry.version == 2
    assert entities.async_get(odd.entity_id).unique_id == "nounderscore"


# --- more odd values -----------------------------------------------------------------------

async def test_a_temperature_that_is_not_a_number_at_start(hass, sim):
    sim.device("2713")["data"]["T"]["v"] = "warm"
    await _setup(hass)
    assert hass.states.get(NATURE_T) is None   # skipped, as before R40
    assert hass.states.get(f"switch.sl_nature_{A}_2713_l1") is not None


async def test_odd_values_in_a_poll(hass, sim, loaded):
    sim.device("2711")["stat"] = "online"
    sim.device("2714")["data"]["P1"] = {"v": "half"}
    await _poll(hass)
    assert _state(hass, STAIRS_ONLINE) == "on"
    assert _state(hass, CURTAIN) == "closed"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_reads_at_start_the_socket_cannot_send(hass, sim):
    """Every `ep` read at start fails at the socket (OSError, not a
    timeout): the entry still loads and the values from discovery stay."""
    sim.send_errors["ep"] = OSError("network down")
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert _state(hass, STAIRS_SIGNAL) == "-61"
    assert _state(hass, STAIRS_L1) == "on"


# --- the socket refuses to send ------------------------------------------------------------

async def test_a_switch_command_the_socket_cannot_send(hass, sim, loaded):
    sim.send_errors["ep"] = OSError("network down")
    await hass.services.async_call("switch", "turn_off", {"entity_id": STAIRS_L1}, blocking=True)
    assert _state(hass, STAIRS_L1) == "on"


async def test_remote_keys_the_socket_cannot_send(hass, sim, loaded):
    sim.send_errors["spotremote:sendkey"] = OSError("network down")
    await hass.services.async_call(
        "remote", "send_command",
        {"entity_id": REMOTE, "command": ["power", "AI_IR_2715_1::power"]}, blocking=True,
    )
    # One attempt each: an error that is not a timeout is not retried.
    assert len(sim.sent("spotremote", cmd="sendkey")) == 2


# --- the remote's list of remotes, odd ------------------------------------------------------

async def test_remotes_of_other_devices_and_odd_key_lists(hass, sim):
    sim.remotes.append({"id": "AI_IR_9999_1", "name": "Other device's"})
    sim.remote_keys["AI_IR_9999_1"] = {"x": "k"}
    sim.remotes.append({"id": "AI_IR_2715_7", "name": "Odd"})
    sim.remote_keys["AI_IR_2715_7"] = ["not", "a", "dict"]
    await _setup(hass)
    # A key the remote does not have makes it read the list again.
    await hass.services.async_call(
        "remote", "send_command", {"entity_id": REMOTE, "command": ["nope"]}, blocking=True,
    )
    # Re-reading drops the remote whose key list is not a list of keys
    # (the list read at setup kept it), so its "keys" are not sent.
    await hass.services.async_call(
        "remote", "send_command", {"entity_id": REMOTE, "command": ["AI_IR_2715_7::not"]},
        blocking=True,
    )
    assert not sim.sent("spotremote", cmd="sendkey")


async def test_a_remote_with_nothing_learned_and_a_hub_that_stops_answering(hass, sim):
    sim.remotes = []
    await _setup(hass)
    assert hass.states.get(REMOTE).attributes["all_commands"] == []
    sim.send_errors["spotremote:getlist"] = OSError("network down")
    await hass.services.async_call(
        "remote", "send_command", {"entity_id": REMOTE, "command": ["power"]}, blocking=True,
    )
    assert not sim.sent("spotremote", cmd="sendkey")
