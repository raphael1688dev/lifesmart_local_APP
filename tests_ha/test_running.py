"""While the integration runs: the 90 s heartbeat, the 15 min poll, devices
going offline, being paired or removed, the token being changed (R40)."""
from datetime import timedelta

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import async_fire_time_changed

from custom_components.lifesmart import async_remove_config_entry_device
from custom_components.lifesmart.const import DOMAIN

from . import hub as sim_hub

A = sim_hub.AGT.lower()
STAIRS_L1 = f"switch.sl_sw_nd3_{A}_2711_l1"
STAIRS_BATTERY = f"sensor.sl_sw_nd3_{A}_2711_v"
STAIRS_ONLINE = f"binary_sensor.sl_sw_nd3_{A}_2711_connectivity"
NATURE_T = f"sensor.sl_nature_{A}_2713_t"
FIRMWARE = "sensor.lifesmart_hub_firmware"


def _state(hass, entity_id):
    return hass.states.get(entity_id).state


async def _beats(hass, count, start=None):
    """Let `count` 90-second heartbeats go by."""
    now = start or dt_util.utcnow()
    for n in range(1, count + 1):
        async_fire_time_changed(hass, now + timedelta(seconds=91 * n))
        await hass.async_block_till_done(wait_background_tasks=True)
    return now + timedelta(seconds=91 * count)


def _ours(hass, entry):
    return [
        e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if hass.states.get(e.entity_id) is not None
    ]


# --- the hub stops answering (R32) ------------------------------------------------------

async def test_entities_go_unavailable_after_two_missed_heartbeats(hass, sim, loaded, caplog):
    sim.silent = True
    now = await _beats(hass, 1)
    assert _state(hass, STAIRS_L1) == "on"
    now = await _beats(hass, 1, now)
    assert all(_state(hass, e) == "unavailable" for e in _ours(hass, loaded))
    assert "is unavailable" in caplog.text

    sim.silent = False
    await _beats(hass, 1, now)
    assert _state(hass, STAIRS_L1) == "on"
    assert "is available again" in caplog.text


async def test_five_silent_minutes_raise_a_repair_issue(hass, sim, loaded):
    """The five minutes are measured on `time.monotonic`. Moving the whole
    clock (freezegun) would also stop the event loop's own timers, so only
    the clock the integration reads is replaced."""
    from types import SimpleNamespace
    from unittest.mock import patch

    issues = ir.async_get(hass)
    issue_id = f"hub_unreachable_{loaded.entry_id}"
    clock = [1000.0]
    sim.silent = True
    with patch("custom_components.lifesmart.time", SimpleNamespace(monotonic=lambda: clock[0])):
        now = dt_util.utcnow()
        for n in range(1, 5):                    # silent since 0 s; up to 273 s: not yet
            clock[0] = 1000.0 + 91 * (n - 1)
            async_fire_time_changed(hass, now + timedelta(seconds=91 * n))
            await hass.async_block_till_done(wait_background_tasks=True)
        assert issues.async_get_issue(DOMAIN, issue_id) is None
        clock[0] = 1000.0 + 364
        async_fire_time_changed(hass, now + timedelta(seconds=91 * 5))
        await hass.async_block_till_done(wait_background_tasks=True)
        issue = issues.async_get_issue(DOMAIN, issue_id)
        assert issue is not None
        assert issue.translation_placeholders == {"host": sim_hub.HOST, "minutes": "6"}
        assert issue.config_entry_id == loaded.entry_id

        sim.silent = False
        async_fire_time_changed(hass, now + timedelta(seconds=91 * 6))
        await hass.async_block_till_done(wait_background_tasks=True)
    assert issues.async_get_issue(DOMAIN, issue_id) is None


async def test_an_odd_heartbeat_reply_still_counts_as_an_answer(hass, sim, loaded):
    sim.overrides["config:notify"] = [{"code": 0, "msg": "odd"}] * 3
    await _beats(hass, 3)
    assert _state(hass, STAIRS_L1) == "on"


# --- the token is changed while running (R34) -------------------------------------------

async def test_a_token_changed_on_the_hub_asks_for_reauthentication(hass, sim, loaded):
    sim.token = "THEHUBHASANEWTOKEN00"
    await _beats(hass, 2)
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]
    assert _state(hass, STAIRS_L1) == "unavailable"
    # Not "unreachable": the hub answers.
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"hub_unreachable_{loaded.entry_id}") is None


async def test_the_poll_also_notices_a_rejected_token(hass, sim, loaded):
    sim.token = "THEHUBHASANEWTOKEN00"
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=15, seconds=5))
    await hass.async_block_till_done(wait_background_tasks=True)
    sources = [f["context"]["source"] for f in hass.config_entries.flow.async_progress_by_handler(DOMAIN)]
    assert sources == [SOURCE_REAUTH]


# --- a device goes offline (LI §6.1 `stat`, R32) ---------------------------------------

async def test_a_device_reported_offline(hass, sim, loaded):
    sim.push(body={"chg": [{"me": "2711", "stat": 0}]})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _state(hass, STAIRS_L1) == "unavailable"
    assert _state(hass, STAIRS_BATTERY) == "unavailable"
    assert _state(hass, STAIRS_ONLINE) == "off"          # still shown, as disconnected
    assert _state(hass, NATURE_T) == "24.5"               # other devices unaffected
    sim.push(body={"chg": [{"me": "2711", "stat": 1}]})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _state(hass, STAIRS_L1) == "on"
    assert _state(hass, STAIRS_ONLINE) == "on"


async def test_offline_from_the_poll_when_the_event_was_lost(hass, sim, loaded):
    sim.device("2711")["stat"] = 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=15, seconds=5))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _state(hass, STAIRS_L1) == "unavailable"
    assert _state(hass, STAIRS_ONLINE) == "off"


# --- the 15-minute poll (D15) ------------------------------------------------------------

async def test_the_poll_updates_values_a_lost_event_would_have_brought(hass, sim, loaded):
    sim.device("2711")["data"]["V"]["v"] = 40
    sim.device("2713")["data"]["T"]["v"] = 231
    sim.device("2714")["data"]["P1"]["v"] = 70
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=15, seconds=5))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _state(hass, STAIRS_BATTERY) == "40"
    assert _state(hass, NATURE_T) == "23.1"
    assert _state(hass, f"cover.sl_p_{A}_2714_p1") == "open"


async def test_values_pushed_by_the_hub(hass, sim, loaded):
    sim.push(body={"chg": [
        {"me": "2711", "V": {"v": 33}},
        {"me": "2713", "T": {"v": 199}},
        {"me": "2714", "P8": {"v": 12}},
        {"me": "2711", "V": {"v": "not a number"}},
        "not a change", {"no_me": 1},
    ]})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _state(hass, STAIRS_BATTERY) == "33"
    assert _state(hass, NATURE_T) == "19.9"
    assert _state(hass, f"sensor.sl_p_{A}_2714_p8") == "12"


async def test_a_failed_poll_keeps_the_values(hass, sim, loaded):
    for reply in ({"code": 9}, {"code": 0, "msg": "nothing"}, "not a dict"):
        sim.overrides["eps"] = [reply]
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=16))
        await hass.async_block_till_done(wait_background_tasks=True)
    sim.silent = True
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=45))
    await hass.async_block_till_done(wait_background_tasks=True)
    sim.silent = False
    assert _state(hass, NATURE_T) == "24.5"


async def test_the_daily_hub_read_updates_the_hub_device(hass, sim, loaded):
    sim.version = {"ver": "1.0.95", "osver": "4.4.95", "mgatype": "LSDEFED"}
    sim.timezone = {"timezone": 9, "summer": True}
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1, minutes=1))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _state(hass, FIRMWARE) == "1.0.95"
    assert _state(hass, "sensor.lifesmart_hub_model") == "DEFED Smart Station"
    assert _state(hass, "sensor.lifesmart_hub_timezone") == "UTC+9"
    hub = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, f"hub_{sim_hub.AGT}"), loaded.entry_id,
    )
    assert (hub.model, hub.sw_version) == ("DEFED Smart Station", "1.0.95")


async def test_a_failed_daily_read_keeps_the_last_values(hass, sim, loaded):
    sim.overrides["config:getver"] = [{"code": 1}, {"code": 1}]
    sim.overrides["config:timezone"] = [{"code": 1}, {"code": 1}]
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1, minutes=1))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _state(hass, FIRMWARE) == "1.0.94p10"
    assert _state(hass, "sensor.lifesmart_hub_timezone") == "UTC+8"


# --- devices paired or removed (D6: the event's shape is not verified) -------------------

async def test_a_paired_device_reloads_the_entry(hass, sim, loaded):
    sim.devices.append(sim_hub._device("2799", "SL_SW_ND1", "New", {"L1": {"v": 0}}))
    sim.push(body={"add": {"me": "2799", "devtype": "SL_SW_ND1"}})
    sim.push(body={"msg": {"add": [{"me": "2799"}]}})  # a second event while waiting
    await hass.async_block_till_done(wait_background_tasks=True)
    apis_before = len(sim.apis)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(sim.apis) == apis_before + 1          # reloaded once
    assert hass.states.get(f"switch.sl_sw_nd1_{A}_2799_l1") is not None


async def test_an_event_about_a_known_device_does_not_reload(hass, sim, loaded):
    sim.push(body={"add": [{"me": "2711"}], "del": [{"me": "9999"}]})
    await hass.async_block_till_done(wait_background_tasks=True)
    apis_before = len(sim.apis)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(sim.apis) == apis_before


async def test_a_removed_device_can_then_be_deleted(hass, sim, loaded):
    """stale-devices (R36): not removed automatically; deletable once the
    hub no longer lists it."""
    registry = dr.async_get(hass)
    stairs = registry.async_get_device_by_identifier((DOMAIN, "2711"), loaded.entry_id)
    hub = registry.async_get_device_by_identifier((DOMAIN, f"hub_{sim_hub.AGT}"), loaded.entry_id)
    assert await async_remove_config_entry_device(hass, loaded, stairs) is False
    assert await async_remove_config_entry_device(hass, loaded, hub) is False

    sim.devices = [d for d in sim.devices if d["me"] != "2711"]
    sim.push(body={"del": {"me": "2711"}})
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert loaded.state is ConfigEntryState.LOADED
    assert registry.async_get(stairs.id) is not None          # still there
    assert hass.states.get(STAIRS_L1).state == "unavailable"  # nothing behind it
    assert await async_remove_config_entry_device(hass, loaded, stairs) is True

    other = registry.async_get_or_create(
        config_entry_id=loaded.entry_id, identifiers={("other", "x")},
    )
    assert await async_remove_config_entry_device(hass, loaded, other) is False


async def test_nothing_is_deletable_while_not_loaded(hass, sim, loaded):
    registry = dr.async_get(hass)
    stairs = registry.async_get_device_by_identifier((DOMAIN, "2711"), loaded.entry_id)
    await hass.config_entries.async_unload(loaded.entry_id)
    assert await async_remove_config_entry_device(hass, loaded, stairs) is False
