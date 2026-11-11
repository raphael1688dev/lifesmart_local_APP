"""R32 step 3: entities go unavailable (quality scale `entity-unavailable`,
`log-when-unavailable`).

Two causes, both in entity.py:
* the hub stops answering the 90 s cfg:notify refresh (availability.py);
* a sub-device reports `stat` 0 (LI §6.1) — except for its connectivity
  sensor, which exists to show that.
"""
import asyncio
import importlib
import logging

import pytest

from lifesmart.availability import FAILURES_BEFORE_UNAVAILABLE, HubAvailability
from lifesmart.binary_sensor import LifeSmartConnectivitySensor
from lifesmart.const import PLATFORMS
from lifesmart.entity import LifeSmartDeviceEntity, LifeSmartEntity, LifeSmartHubEntity
from lifesmart.sensor import LifeSmartBatterySensor
from lifesmart.switch import LifeSmartSwitch

from .fakes import DEVICES, HOST, FakeAPI, make_env, runtime, setup

KITCHEN = DEVICES[0]  # me 2711, SL_SW_ND1, stat 1


@pytest.fixture
def env(monkeypatch):
    return make_env(monkeypatch)


def _all_entities(env):
    """Run every platform's setup; return the entities by platform."""
    setup(env)
    found = {}
    for platform in PLATFORMS:
        module = importlib.import_module(f"lifesmart.{platform}")
        added = []
        asyncio.run(module.async_setup_entry(env.hass, env.entry, added.extend))
        found[platform] = added
    return found


# --- availability.py ------------------------------------------------------------

def test_one_missed_refresh_is_not_enough():
    hub = HubAvailability(HOST)
    assert FAILURES_BEFORE_UNAVAILABLE == 2
    hub.record_failure("TimeoutError")
    assert hub.available
    hub.record_failure("TimeoutError")
    assert not hub.available
    hub.record_success()
    assert hub.available


def test_a_success_in_between_starts_the_count_again():
    hub = HubAvailability(HOST)
    hub.record_failure()
    hub.record_success()
    hub.record_failure()
    assert hub.available


def test_listeners_hear_changes_only():
    hub = HubAvailability(HOST)
    calls = []
    unsub = hub.async_add_listener(lambda: calls.append(hub.available))
    hub.record_success()           # still available: no call
    hub.record_failure()           # 1 of 2: no call
    hub.record_failure()           # unavailable
    hub.record_failure()           # still unavailable: no call
    hub.record_success()           # back
    hub.record_success()
    assert calls == [False, True]
    unsub()
    hub.record_failure()
    hub.record_failure()
    assert calls == [False, True]
    unsub()  # a second call is harmless


def test_logs_once_when_it_stops_answering_and_once_when_back(caplog):
    """log-when-unavailable: info level, no repeats."""
    hub = HubAvailability(HOST)
    with caplog.at_level(logging.DEBUG, logger="lifesmart.availability"):
        for _ in range(5):
            hub.record_failure("TimeoutError")
        for _ in range(3):
            hub.record_success()
    lines = [(r.levelno, r.getMessage()) for r in caplog.records]
    assert [level for level, _ in lines] == [logging.INFO, logging.INFO]
    assert "not answering" in lines[0][1] and HOST in lines[0][1]
    assert "answering again" in lines[1][1] and HOST in lines[1][1]


def test_no_recovery_line_without_an_outage(caplog):
    hub = HubAvailability(HOST)
    with caplog.at_level(logging.DEBUG, logger="lifesmart.availability"):
        hub.record_failure()
        hub.record_success()
    assert caplog.records == []


# --- the heartbeat feeds it -----------------------------------------------------

def test_two_missed_heartbeats_mark_the_hub_unavailable(env):
    setup(env)
    hub = runtime(env).availability
    api = env.apis[0]
    assert hub.available
    api.notify_error = TimeoutError()
    asyncio.run(env.issues.timer(None))
    assert hub.available
    asyncio.run(env.issues.timer(None))
    assert not hub.available
    api.notify_error = None
    asyncio.run(env.issues.timer(None))
    assert hub.available


def test_a_hub_that_answers_oddly_is_still_available(env):
    """An error code or a strange payload is an answer."""
    setup(env)
    env.apis[0].notify_error = ValueError("bad payload")
    for _ in range(3):
        asyncio.run(env.issues.timer(None))
    assert runtime(env).availability.available


# --- every entity follows the hub -----------------------------------------------

def test_every_entity_goes_unavailable_with_the_hub(env, monkeypatch):
    monkeypatch.setattr(FakeAPI, "scenes", [
        {"id": "AI_SCENE_0001", "name": "Movie", "cls": "scene"},
        {"id": "AI_GROUP_0002", "name": "Lamps", "cls": "groupsw"},
        {"id": "AI_GROUP_0003", "name": "Bulbs", "cls": "grouphw"},
    ])
    monkeypatch.setattr(FakeAPI, "devices", DEVICES + [
        {"me": "2715", "agt": DEVICES[0]["agt"], "name": "Clicker", "devtype": "SL_SC_BB_V2",
         "stat": 1, "data": {"BN": {"v": 0}, "V": {"v": 77}}},
    ])

    async def remote_list(self):
        return [{"remote": {"id": "AI_IR_2713_1"}, "keys": {"power": "x"}}]
    monkeypatch.setattr(FakeAPI, "get_remote_list", remote_list)

    by_platform = _all_entities(env)
    assert all(by_platform[p] for p in PLATFORMS), {p: len(v) for p, v in by_platform.items()}
    entities = [e for group in by_platform.values() for e in group]
    hub = runtime(env).availability

    assert all(isinstance(e, LifeSmartEntity) for e in entities)
    assert all(e.available for e in entities)
    for _ in range(2):
        hub.record_failure("TimeoutError")
    assert not any(e.available for e in entities)
    hub.record_success()
    assert all(e.available for e in entities)


def test_added_entities_write_their_state_when_the_hub_changes(env):
    by_platform = _all_entities(env)
    entities = [e for group in by_platform.values() for e in group]
    hub = runtime(env).availability
    for entity in entities:
        entity.hass = env.hass
        asyncio.run(entity.async_added_to_hass())
        entity.state_writes = 0
    for _ in range(2):
        hub.record_failure()
    assert [e.state_writes for e in entities] == [1] * len(entities)
    hub.record_success()
    assert [e.state_writes for e in entities] == [2] * len(entities)

    # Removed entities stop listening, to the hub and to the API.
    for entity in entities:
        asyncio.run(entity.async_will_remove_from_hass())
        entity.state_writes = 0
    for _ in range(2):
        hub.record_failure()
    assert [e.state_writes for e in entities] == [0] * len(entities)
    assert env.apis[0].state_listeners == {}
    assert runtime(env).coordinator.listeners == []


def test_an_entity_not_added_yet_does_not_write(env):
    by_platform = _all_entities(env)
    switch = by_platform["switch"][0]
    assert switch.hass is None
    switch._handle_stat_value(0)
    assert not switch.available
    assert not hasattr(switch, "state_writes")


# --- sub-device `stat` ----------------------------------------------------------

def _added(env, entity):
    entity.hass = env.hass
    asyncio.run(entity.async_added_to_hass())
    entity.state_writes = 0
    return entity


def test_device_entities_follow_a_pushed_stat(env):
    by_platform = _all_entities(env)
    api = env.apis[0]
    mine = [
        _added(env, e)
        for group in by_platform.values() for e in group
        if isinstance(e, LifeSmartDeviceEntity) and e._device["me"] == "2711"
    ]
    others = [
        e for group in by_platform.values() for e in group
        if not (isinstance(e, LifeSmartDeviceEntity) and e._device["me"] == "2711")
    ]
    connectivity = [e for e in mine if isinstance(e, LifeSmartConnectivitySensor)]
    rest = [e for e in mine if not isinstance(e, LifeSmartConnectivitySensor)]
    # Kitchen has a switch channel, a battery sensor, a signal sensor and
    # its connectivity sensor.
    assert len(connectivity) == 1 and len(rest) == 3

    api.push("2711", "stat", 0)
    assert not any(e.available for e in rest)
    assert connectivity[0].available and connectivity[0]._attr_is_on is False
    assert all(e.available for e in others)          # other devices, hub entities
    assert all(e.state_writes == 1 for e in mine)

    api.push("2711", "stat", 0)                      # no change: nothing to write
    assert all(e.state_writes == 1 for e in rest)

    api.push("2711", "stat", 1)
    assert all(e.available for e in mine)
    assert connectivity[0]._attr_is_on is True


def test_device_entities_follow_stat_from_the_coordinator(env):
    """A lost push must not leave the entity unavailable (or available) for good."""
    by_platform = _all_entities(env)
    coordinator = runtime(env).coordinator
    switch = _added(env, next(e for e in by_platform["switch"] if e._device["me"] == "2711"))
    battery = _added(env, next(
        e for e in by_platform["sensor"]
        if isinstance(e, LifeSmartBatterySensor) and e._device["me"] == "2711"
    ))

    coordinator.async_set_updated_data({"2711": {**KITCHEN, "stat": 0}})
    assert not switch.available and not battery.available
    coordinator.async_set_updated_data({"2711": {**KITCHEN, "stat": 1, "data": {"V": {"v": 55}}}})
    assert switch.available and battery.available
    assert battery._attr_native_value == 55


def test_a_device_offline_at_setup_starts_unavailable():
    offline = {**KITCHEN, "stat": 0}
    assert not LifeSmartSwitch(FakeAPI(), offline, "L1", "L1").available
    sensor = LifeSmartConnectivitySensor(FakeAPI(), offline)
    assert sensor.available and sensor._attr_is_on is False


@pytest.mark.parametrize("stat", [None, "0", True, False, 2, 1])
def test_only_an_explicit_zero_means_offline(stat):
    """Unverified on real hardware, so stay conservative: a missing or odd
    `stat` leaves the entity usable."""
    device = {**KITCHEN, "stat": stat}
    if stat is None:
        device.pop("stat")
    switch = LifeSmartSwitch(FakeAPI(), device, "L1", "L1")
    assert switch.available
    for odd in (None, "0", True, False):
        switch._handle_stat_value(odd)
        assert switch.available


def test_hub_and_device_must_both_be_up(env):
    hub = HubAvailability(HOST)
    switch = LifeSmartSwitch(FakeAPI(), KITCHEN, "L1", "L1", availability=hub)
    connectivity = LifeSmartConnectivitySensor(FakeAPI(), KITCHEN, availability=hub)
    switch._handle_stat_value(0)
    connectivity._handle_stat_value(0)
    assert not switch.available and connectivity.available
    for _ in range(2):
        hub.record_failure()
    switch._handle_stat_value(1)
    assert not switch.available          # device is back, the hub is not
    assert not connectivity.available    # the hub's silence does apply to it
    hub.record_success()
    assert switch.available and connectivity.available


# --- what replaced the per-entity failure counters ---------------------------------

def test_failed_switch_reads_do_not_make_it_unavailable():
    """Before R32 three failed reads marked the switch unavailable until the
    next push. Availability is the hub's and the device's now."""
    api = FakeAPI()
    api.reply = asyncio.TimeoutError()
    switch = LifeSmartSwitch(api, KITCHEN, "L1", "L1")
    for _ in range(5):
        asyncio.run(switch._async_update_state())
    assert switch.available


def test_without_a_tracker_an_entity_is_available():
    """Entities built outside setup (tests, future callers) default to available."""

    class Plain(LifeSmartEntity):
        pass

    class OnHub(LifeSmartHubEntity):
        pass

    assert Plain().available
    assert OnHub("key", "Hub", {}).available
