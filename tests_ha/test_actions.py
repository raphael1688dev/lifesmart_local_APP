"""The integration's actions, called through Home Assistant (R40).

Each one is checked for what reaches the hub, what the user sees when the
hub refuses or does not answer, and that a wrong target is refused before
anything is sent (quality scale action-exceptions)."""
import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from custom_components.lifesmart.const import DOMAIN

from . import hub as sim_hub
from .conftest import make_entry


async def _act(hass, service, **data):
    await hass.services.async_call(DOMAIN, service, data, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)


def _device_id(hass, entry, identifier):
    return dr.async_get(hass).async_get_device_by_identifier((DOMAIN, identifier), entry.entry_id).id


# --- set_hub_timezone -------------------------------------------------------------------

async def test_set_hub_timezone(hass, sim, loaded):
    await _act(hass, "set_hub_timezone", config_entry_id=loaded.entry_id, timezone=-5, daylight_saving=True)
    assert sim.sent("config", cfg="timezone", timezone=-5) == [
        {"cfg": "timezone", "timezone": -5, "summer": True},
    ]
    # Read back at once, so the sensor shows it.
    assert hass.states.get("sensor.lifesmart_hub_timezone").state == "UTC-5"
    assert hass.states.get("sensor.lifesmart_hub_timezone").attributes["daylight_saving"] is True


async def test_set_hub_timezone_refused(hass, sim, loaded):
    sim.overrides["config:timezone"] = [{"code": 7}]
    with pytest.raises(HomeAssistantError, match="cfg:timezone"):
        await _act(hass, "set_hub_timezone", config_entry_id=loaded.entry_id, timezone=1)


# --- rename_device ----------------------------------------------------------------------

async def test_rename_a_sub_device(hass, sim, loaded):
    stairs = _device_id(hass, loaded, "2711")
    apis = len(sim.apis)
    await _act(hass, "rename_device", config_entry_id=loaded.entry_id, name="Hall", device_id=stairs)
    assert sim.sent("config", cfg="devname") == [{"cfg": "devname", "name": "Hall", "me": "2711"}]
    # Device names come from `eps` at setup, so the entry reloads.
    assert len(sim.apis) == apis + 1
    assert dr.async_get(hass).async_get(stairs).name == "Hall"


async def test_rename_the_hub(hass, sim, loaded):
    for device_id in (None, _device_id(hass, loaded, f"hub_{sim_hub.AGT}")):
        data = {"device_id": device_id} if device_id else {}
        await _act(hass, "rename_device", config_entry_id=loaded.entry_id, name="Upstairs", **data)
    assert sim.sent("config", cfg="devname") == [{"cfg": "devname", "name": "Upstairs"}] * 2


async def test_rename_refuses_a_device_of_another_hub_or_integration(hass, sim, loaded):
    registry = dr.async_get(hass)
    other_entry = make_entry(host="192.168.1.99")
    other_entry.add_to_hass(hass)
    foreign = registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={(DOMAIN, "2711")},
    )
    not_ours = registry.async_get_or_create(
        config_entry_id=loaded.entry_id, identifiers={("other", "x")},
    )
    for device_id in (foreign.id, not_ours.id, "no-such-device"):
        with pytest.raises(ServiceValidationError):
            await _act(hass, "rename_device", config_entry_id=loaded.entry_id, name="x", device_id=device_id)
    assert not sim.sent("config", cfg="devname")


async def test_rename_refused_by_the_hub(hass, sim, loaded):
    sim.overrides["config:devname"] = [{"code": 7}]
    apis = len(sim.apis)
    with pytest.raises(HomeAssistantError):
        await _act(hass, "rename_device", config_entry_id=loaded.entry_id, name="x")
    assert len(sim.apis) == apis  # no reload


# --- upgrade_hub_firmware / factory_reset_hub ------------------------------------------------

async def test_upgrade(hass, sim, loaded):
    await _act(hass, "upgrade_hub_firmware", config_entry_id=loaded.entry_id)
    await _act(hass, "upgrade_hub_firmware", config_entry_id=loaded.entry_id, reboot=True)
    assert sim.sent("config", cfg="upgrade") == [
        {"cfg": "upgrade"}, {"cfg": "upgrade", "reboot": True},
    ]
    sim.overrides["config:upgrade"] = [{"code": 7}]
    with pytest.raises(HomeAssistantError):
        await _act(hass, "upgrade_hub_firmware", config_entry_id=loaded.entry_id)


async def test_factory_reset_needs_confirm(hass, sim, loaded):
    with pytest.raises(ServiceValidationError):
        await _act(hass, "factory_reset_hub", config_entry_id=loaded.entry_id, confirm=False)
    assert not sim.sent("config", cfg="reset")
    await _act(hass, "factory_reset_hub", config_entry_id=loaded.entry_id, confirm=True)
    assert sim.sent("config", cfg="reset") == [{"cfg": "reset"}]


@pytest.mark.parametrize(("reply", "raises"), [(TimeoutError(), False), ({"code": 7}, True)])
async def test_factory_reset_without_an_answer_or_refused(hass, sim, loaded, reply, raises):
    """No answer: like a reboot, the hub may restart before it replies."""
    sim.overrides["config:reset"] = [reply]
    if raises:
        with pytest.raises(HomeAssistantError):
            await _act(hass, "factory_reset_hub", config_entry_id=loaded.entry_id, confirm=True)
    else:
        await _act(hass, "factory_reset_hub", config_entry_id=loaded.entry_id, confirm=True)


# --- send_keys (R30) -----------------------------------------------------------------------

async def test_send_keys(hass, sim, loaded):
    await _act(hass, "send_keys", remote_id="AI_IR_2715_1", keys=["power", "vol_up"])
    await _act(hass, "send_keys", remote_id="AI_IR_2715_1", keys="power", config_entry_id=loaded.entry_id)
    assert [a["key"] for a in sim.sent("spotremote", cmd="sendkey")] == ["power", "vol_up", "power"]


async def test_send_keys_to_a_remote_no_hub_lists_tries_them_all(hass, sim, loaded):
    await _act(hass, "send_keys", remote_id="AI_IR_9999_1", keys="power")
    assert sim.sent("spotremote", cmd="sendkey", id="AI_IR_9999_1")


@pytest.mark.parametrize("reply", [{"code": 10004}, TimeoutError()])
async def test_send_keys_fails_when_no_hub_accepts(hass, sim, loaded, reply):
    sim.overrides["spotremote:sendkey"] = [reply]
    with pytest.raises(HomeAssistantError):
        await _act(hass, "send_keys", remote_id="AI_IR_2715_1", keys="power")


# --- the target must be a loaded LifeSmart hub (R28 / R32) ---------------------------------

@pytest.mark.parametrize(("service", "data"), [
    ("set_hub_timezone", {"timezone": 1}),
    ("rename_device", {"name": "x"}),
    ("upgrade_hub_firmware", {}),
    ("factory_reset_hub", {"confirm": True}),
    ("send_keys", {"remote_id": "AI_IR_2715_1", "keys": "power"}),
])
async def test_an_unloaded_or_unknown_hub_is_refused(hass, sim, loaded, service, data):
    with pytest.raises(ServiceValidationError):
        await _act(hass, service, config_entry_id="no-such-entry", **data)
    await hass.config_entries.async_unload(loaded.entry_id)
    with pytest.raises(ServiceValidationError):
        await _act(hass, service, config_entry_id=loaded.entry_id, **data)
    sent_before = len(sim.received)
    if service == "send_keys":
        with pytest.raises(ServiceValidationError):
            await _act(hass, service, **data)
    assert len(sim.received) == sent_before
