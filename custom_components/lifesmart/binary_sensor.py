"""Platform for LifeSmart binary_sensor integration.

Currently exposes one CONNECTIVITY binary_sensor per sub-device, based on the
device-level `stat` common attribute (Local Interfaces §6.1 — `stat`: 1=online,
0=offline; §4 — NOTIFY events include `stat` for online/offline changes).
"""
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import generate_entity_id
from .const import DOMAIN
from .coordinator import LifeSmartCoordinator
from .device_info import sub_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LifeSmart binary sensors."""
    _LOGGER.debug("Setting up LifeSmart binary_sensors")

    entry_data = hass.data[DOMAIN]["entries"][config_entry.entry_id]
    api = entry_data["api"]
    coordinator: Optional[LifeSmartCoordinator] = entry_data.get("coordinator")
    # D22: hub device registry ID — sub-devices hang off it via via_device_id.
    hub_device_id: Optional[str] = entry_data.get("hub_device_id")
    devices = entry_data.get("devices") or []
    if not devices:
        try:
            devices_data: Dict[str, Any] = await api.discover_devices()
            if isinstance(devices_data, dict) and isinstance(devices_data.get("msg"), list):
                devices = devices_data["msg"]
                entry_data["devices"] = devices
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout while discovering devices")
            return
        except (OSError, KeyError, ValueError, TypeError) as e:
            _LOGGER.error("Unexpected error during device discovery: %s", e)
            return

    binary_sensors: List[BinarySensorEntity] = []
    if isinstance(devices, list):
        for device in devices:
            try:
                # LI §6.1 — `stat` is a common attribute on every sub-device.
                # Guard anyway: firmware may omit it on some device types.
                if "stat" in device:
                    _LOGGER.debug("Found connectivity sensor in %s", device.get('name'))
                    binary_sensors.append(
                        LifeSmartConnectivitySensor(
                            api=api, device=device, hub_device_id=hub_device_id,
                            coordinator=coordinator,
                        )
                    )
            except KeyError as e:
                _LOGGER.error("Missing required device field: %s", e)
                continue

    _LOGGER.debug("Adding %s binary_sensors", len(binary_sensors))
    async_add_entities(binary_sensors)


class LifeSmartConnectivitySensor(BinarySensorEntity):
    """Online/offline status of a LifeSmart sub-device.

    State sources:
    1. Push via api.register_state_listener(me, "stat", ...) — driven by
       LI §4 NOTIFY events; api.py extracts scalar `stat` from `chg` items
       and dispatches as virtual idx "stat".
    2. Fallback: the shared LifeSmartCoordinator's 15 min `eps` snapshot,
       in case a push is lost. D15 (R25): it replaced a per-entity `ep` GET
       timer, so N connectivity sensors no longer cost N requests a cycle.
    """

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True  # R18: "Connectivity" + device name

    _api: Any
    _device: Dict[str, Any]
    _unsub_report: Optional[Callable[[], None]]
    _unsub_coordinator: Optional[Callable[[], None]]

    def __init__(
        self,
        api: Any,
        device: Dict[str, Any],
        hub_device_id: Optional[str] = None,
        coordinator: Optional[LifeSmartCoordinator] = None,
    ) -> None:
        self._api = api
        self._device = device
        self._coordinator = coordinator
        self._unsub_report = None
        self._unsub_coordinator = None

        try:
            me = device['me']
            devtype = device.get('devtype')
            hub_id = device.get('agt', '')

            # HA 2026.5 naming: function only; device name from DeviceInfo.
            self._attr_name = "Connectivity"
            # Include agt — `me` is only unique within a hub (system devices
            # like V_SI / 0020 exist on every hub). See R10 migration.
            self._attr_unique_id = f"connectivity_{hub_id}_{me}"
            # Virtual idx "connectivity" only feeds entity_id slug.
            self.entity_id = (
                f"binary_sensor.{generate_entity_id(devtype, hub_id, me, 'connectivity')}"
            )

            # R19: built in one go by device_info.py — DeviceInfo is a
            # dataclass from HA 2026.11, so no item assignment. via_device_id
            # (D22) handled there.
            self._attr_device_info = sub_device_info(device, hub_device_id)

            stat = device.get("stat")
            self._attr_is_on = (stat == 1) if isinstance(stat, (int, float)) else None
        except KeyError as e:
            _LOGGER.error("Missing required connectivity sensor field: %s", e)
            raise

    async def async_added_to_hass(self) -> None:
        """Register the push listener and the coordinator fallback."""
        # Push: api dispatches stat changes via virtual idx "stat".
        self._unsub_report = self._api.register_state_listener(
            self._device["me"], "stat", self._handle_stat_value
        )
        if self._coordinator is not None:
            self._unsub_coordinator = self._coordinator.async_add_listener(
                self._handle_coordinator_update
            )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_coordinator:
            self._unsub_coordinator()
            self._unsub_coordinator = None
        if self._unsub_report:
            self._unsub_report()
            self._unsub_report = None

    @callback
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Opt in to in-place entity_id renames (HA 2026.11+, R19).

        Nothing here is keyed on entity_id — the push listener keys on
        (me, "stat") and the coordinator listener on the method — so there is
        nothing to re-key. Without this method HA keeps removing and re-adding the
        entity on rename (compat path, removed in 2027.11) because this class
        defines async_added_to_hass / async_will_remove_from_hass.
        """
        super().async_entity_id_changed(old_entity_id)

    def _handle_stat_value(self, val: Any) -> None:
        if not isinstance(val, (int, float)):
            return
        self._attr_is_on = (val == 1)
        if self.hass:
            self.hass.async_create_task(self._async_write_state())

    async def _async_write_state(self) -> None:
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """D15: take `stat` from the coordinator's `eps` snapshot."""
        if self._coordinator is None or self._coordinator.data is None:
            return
        device = self._coordinator.data.get(self._device["me"])
        stat = device.get("stat") if isinstance(device, dict) else None
        if not isinstance(stat, (int, float)):
            return
        self._attr_is_on = (stat == 1)
        self.async_write_ha_state()
