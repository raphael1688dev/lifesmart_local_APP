"""Setting up, failing to set up, unloading and migrating, inside Home Assistant (R40).

The integration runs unchanged against tests_ha/hub.py, a hub simulated at the
datagram level.
"""
import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir

from custom_components.lifesmart import diagnostics
from custom_components.lifesmart.const import DOMAIN
from custom_components.lifesmart.models import LifeSmartData

from . import hub as sim_hub
from .conftest import make_entry

HUB_ID = (DOMAIN, f"hub_{sim_hub.AGT}")


def _entities(hass, entry):
    return er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)


async def _setup(hass, entry):
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


# --- a normal start -----------------------------------------------------------------

async def test_every_platform_gets_its_entities(hass, sim, loaded):
    assert loaded.state is ConfigEntryState.LOADED
    counts: dict[str, int] = {}
    for entity in _entities(hass, loaded):
        counts[entity.domain] = counts.get(entity.domain, 0) + 1
    assert counts == {
        "switch": 7,          # 6 channels + the groupsw scene
        "sensor": 14,         # 4 hub, 4 battery, 1 temperature, 5 signal
        "binary_sensor": 8,   # one connectivity sensor per sub-device
        "button": 1, "scene": 1, "cover": 1, "event": 2, "remote": 1, "light": 1,
    }


async def test_states_after_start(hass, sim, loaded):
    def state(entity_id):
        return hass.states.get(entity_id)

    stairs = f"sl_sw_nd3_{sim_hub.AGT.lower()}_2711"
    assert state(f"switch.{stairs}_l1").state == "on"
    assert state(f"switch.{stairs}_l1").attributes["friendly_name"] == "Stairs Stairs main"
    # `{$EPN}` is the hub's placeholder for the device name: left out.
    assert state(f"switch.{stairs}_l2").attributes["friendly_name"] == "Stairs Side"
    assert state(f"switch.{stairs}_l3").attributes["friendly_name"] == "Stairs L3"
    assert state(f"sensor.{stairs}_v").state == "90"
    assert state(f"sensor.sl_nature_{sim_hub.AGT.lower()}_2713_t").state == "24.5"
    assert state(f"cover.sl_p_{sim_hub.AGT.lower()}_2714_p1").state == "closed"
    assert state("sensor.lifesmart_hub_firmware").state == "1.0.94p10"
    assert state("sensor.lifesmart_hub_model").state == "Smart Station / Smart Station Pro"
    assert state("sensor.lifesmart_hub_timezone").state == "UTC+8"
    assert state("sensor.lifesmart_hub_timezone").attributes["daylight_saving"] is False
    # Undocumented channels (I1 on SL_SW_RC) are left alone.
    assert state(f"switch.sl_sw_rc_{sim_hub.AGT.lower()}_2712_i1") is None


async def test_signal_strength_is_disabled_by_default(hass, sim, loaded):
    signal = [e for e in _entities(hass, loaded) if e.unique_id.startswith("signal_")]
    assert len(signal) == 5
    assert all(e.disabled_by is er.RegistryEntryDisabler.INTEGRATION for e in signal)
    assert all(hass.states.get(e.entity_id) is None for e in signal)


async def test_hub_device_and_sub_devices(hass, sim, loaded):
    registry = dr.async_get(hass)
    hub = registry.async_get_device_by_identifier(HUB_ID, loaded.entry_id)
    assert hub.model == "Smart Station / Smart Station Pro"
    assert hub.sw_version == "1.0.94p10"
    assert hub.via_device_id is None
    subs = [d for d in dr.async_entries_for_config_entry(registry, loaded.entry_id) if d.id != hub.id]
    assert len(subs) == 8
    assert all(d.via_device_id == hub.id for d in subs)
    stairs = registry.async_get_device_by_identifier((DOMAIN, "2711"), loaded.entry_id)
    assert (stairs.name, stairs.model, stairs.sw_version) == ("Stairs", "SL_SW_ND3", "1.2.3")


async def test_runtime_data(hass, sim, loaded):
    data = loaded.runtime_data
    assert isinstance(data, LifeSmartData)
    assert (data.host, data.hub_key) == (sim_hub.HOST, sim_hub.AGT)
    assert len(data.devices) == 8 and len(data.scenes) == 4
    assert data.remote_ids == {"AI_IR_2715_1"}
    # Subscribed to the hub's events (LI §4) at the address it can reach.
    (notify,) = sim.sent("config", cfg="notify")
    assert notify == {"cfg": "notify", "host": sim_hub.LOCAL_IP, "port": sim_hub.BOUND_PORT}


async def test_a_hub_with_nothing_paired_still_loads(hass, sim):
    sim.devices = []
    sim.scenes = []
    entry = make_entry()
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    # The hub's own entities: four sensors and the reboot button.
    assert sorted(e.domain for e in _entities(hass, entry)) == ["button"] + ["sensor"] * 4
    # Without sub-devices the hub key falls back to the address.
    assert entry.runtime_data.hub_key == sim_hub.HOST


async def test_a_hub_with_nothing_paired_reads_the_list_once(hass, sim, caplog):
    """R41: the platforms used to read the list again when it was empty.
    When that read failed, the hub sensors were not created and the switch,
    cover and remote platforms failed to set up (the groupsw switch with
    them); when it worked it only cost five more requests."""
    sim.devices = []
    sim.scenes = [{"id": "AI_GROUP_000002", "name": "All lamps", "cls": "groupsw"}]
    sim.overrides["eps"] = [{"code": 0, "msg": []}] + [TimeoutError()] * 20
    entry = make_entry()
    await _setup(hass, entry)
    assert len(sim.sent("eps")) == 1
    assert hass.states.get("sensor.lifesmart_hub_firmware").state == "1.0.94p10"
    assert hass.states.get("switch.lifesmart_all_lamps_p_000002") is not None
    assert "Failed to set up" not in caplog.text
    assert "Timeout while discovering devices" not in caplog.text


async def test_hub_id_from_the_reply_when_no_device_has_one(hass, sim):
    for device in sim.devices:
        device.pop("agt")
    sim.overrides["eps"] = [{"code": 0, "msg": sim.devices, "agtid": "AGTID_FROM_REPLY"}]
    entry = make_entry()
    await _setup(hass, entry)
    assert entry.runtime_data.hub_key == "AGTID_FROM_REPLY"


async def test_an_unreadable_version_leaves_the_hub_sensors_unknown(hass, sim):
    sim.overrides["config:getver"] = [{"code": 1}, {"code": 1}]
    entry = make_entry()
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.lifesmart_hub_firmware").state == "unknown"
    assert entry.runtime_data.hub_info["version_ok"] is False
    # Not a repair issue: nothing the user can do (quality scale R36).
    assert not ir.async_get(hass).issues


async def test_an_unreadable_scene_list_loads_without_scenes(hass, sim):
    sim.overrides["scene"] = [{"code": 5}, {"code": 5}]
    entry = make_entry()
    await _setup(hass, entry)
    assert entry.runtime_data.scenes == []
    assert hass.states.get("scene.lifesmart_movie_night_e_000001") is None


# --- unloading and reloading ----------------------------------------------------------

async def test_unload_releases_everything(hass, sim, loaded):
    api = loaded.runtime_data.api
    assert await hass.config_entries.async_unload(loaded.entry_id)
    await hass.async_block_till_done()
    assert loaded.state is ConfigEntryState.NOT_LOADED
    assert not hasattr(loaded, "runtime_data")
    assert api._transport is None
    assert api._state_listeners == {} and api._report_listeners == set()
    assert all(hass.states.get(e.entity_id).state == "unavailable"
               for e in _entities(hass, loaded) if hass.states.get(e.entity_id))


async def test_reload(hass, sim, loaded):
    assert await hass.config_entries.async_reload(loaded.entry_id)
    await hass.async_block_till_done()
    assert loaded.state is ConfigEntryState.LOADED
    assert hass.states.get(f"switch.sl_sw_nd3_{sim_hub.AGT.lower()}_2711_l1").state == "on"
    # Each start makes its own API; the old one is closed.
    assert [api._transport is None for api in sim.apis] == [True, False]


# --- what setup reports (quality scale test-before-setup, R34) --------------------------

async def test_a_rejected_token_asks_for_reauthentication(hass, sim):
    sim.token = "THEHUBHASANOTHERTOKEN"
    entry = make_entry()
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]
    assert sim.apis[0]._transport is None


@pytest.mark.parametrize(
    ("silent", "reply"),
    [
        (True, None),                       # no answer
        (False, {"code": 10004, "msg": "x"}),  # another error
        (False, {"code": 101}),             # 101 without the hub's time
    ],
)
async def test_other_failures_are_retried(hass, sim, silent, reply):
    sim.silent = silent
    if reply is not None:
        sim.overrides["eps"] = [reply, reply]
    entry = make_entry()
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN) == []
    assert sim.apis[0]._transport is None


async def test_a_hub_clock_far_off_is_corrected(hass, sim):
    sim.clock_ahead = 3600
    entry = make_entry()
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert 3590 <= entry.runtime_data.api.ts_offset <= 3610


# --- migrations -----------------------------------------------------------------------

async def test_hub_device_keyed_on_the_address_moves_to_the_hub_id(hass, sim):
    """Entries from before R25 keyed the hub device on the IP (D21)."""
    entry = make_entry()
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    old = registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, f"hub_{sim_hub.HOST}")},
        name="LifeSmart Hub",
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    moved = registry.async_get(old.id)
    assert moved.identifiers == {HUB_ID}
    assert registry.async_get_device_by_identifier((DOMAIN, f"hub_{sim_hub.HOST}"), entry.entry_id) is None


async def test_an_old_hub_key_is_kept_when_discovery_comes_back_empty(hass, sim):
    sim.devices = []
    entry = make_entry()
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={HUB_ID}, name="LifeSmart Hub",
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.hub_key == sim_hub.AGT


async def test_version_1_entries_get_agt_in_their_unique_ids(hass, sim):
    """R10: unique ids from before 2026-05-24 had no hub id in them."""
    entry = make_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, version=1)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "switch", DOMAIN, "switch_2711_L1", config_entry=entry,
        suggested_object_id="old_stairs",
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.version == 2
    assert registry.async_get(old.entity_id).unique_id == f"switch_{sim_hub.AGT}_2711_L1"


async def test_migration_waits_for_an_unreachable_hub(hass, sim):
    sim.silent = True
    entry = make_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, version=1)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.version == 1
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_entity_ids_with_characters_home_assistant_rejects_are_renamed(hass, sim):
    """R14: an `agt` with '-' gave entity ids HA 2027.2 will reject. HA
    2026.11 no longer registers such an id, so the old one is written with
    its check switched off, as an older version would have left it."""
    from unittest.mock import patch

    for device in sim.devices:
        device["agt"] = "A3EA-AAB"
    entry = make_entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "switch", DOMAIN, "switch_A3EA-AAB_2711_L1", config_entry=entry,
    )
    with patch("homeassistant.helpers.entity_registry.valid_entity_id", return_value=True):
        registry.async_update_entity(entity.entity_id, new_entity_id="switch.sl_sw_nd3_A3EA-AAB_2711_l1")
    other = registry.async_get_or_create("switch", "other_integration", "x")
    with patch("homeassistant.helpers.entity_registry.valid_entity_id", return_value=True):
        registry.async_update_entity(other.entity_id, new_entity_id="switch.not-ours")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get_entity_id("switch", DOMAIN, "switch_A3EA-AAB_2711_L1") == (
        "switch.sl_sw_nd3_a3ea_aab_2711_l1"
    )
    assert hass.states.get("switch.sl_sw_nd3_a3ea_aab_2711_l1").state == "on"
    assert registry.async_get("switch.not-ours") is not None  # not ours, not touched


# --- diagnostics ----------------------------------------------------------------------

async def test_entry_diagnostics(hass, sim, loaded):
    result = await diagnostics.async_get_config_entry_diagnostics(hass, loaded)
    assert result["entry"]["data"]["token"] == "**REDACTED**"
    assert result["device_count"] == 8
    assert result["devtype_counts"]["SL_SW_ND3"] == 1
    assert result["hub_info"]["mgatype"] == "LSJZX1K"


async def test_device_diagnostics(hass, sim, loaded):
    registry = dr.async_get(hass)
    hub = registry.async_get_device_by_identifier(HUB_ID, loaded.entry_id)
    result = await diagnostics.async_get_device_diagnostics(hass, loaded, hub)
    assert result["device_type"] == "hub" and result["device_count"] == 8
    stairs = registry.async_get_device_by_identifier((DOMAIN, "2711"), loaded.entry_id)
    result = await diagnostics.async_get_device_diagnostics(hass, loaded, stairs)
    assert result["payload"]["name"] == "Stairs"
    sim.devices.pop(0)
    loaded.runtime_data.devices = [d for d in loaded.runtime_data.devices if d["me"] != "2711"]
    result = await diagnostics.async_get_device_diagnostics(hass, loaded, stairs)
    assert result["device_identifier"] == "2711"
    other = registry.async_get_or_create(
        config_entry_id=loaded.entry_id, identifiers={("other", "x")}, name="x",
    )
    result = await diagnostics.async_get_device_diagnostics(hass, loaded, other)
    assert "error" in result
