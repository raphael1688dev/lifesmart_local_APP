"""Platform for LifeSmart binary_sensor integration.

Currently exposes one CONNECTIVITY binary_sensor per sub-device, based on the
device-level `stat` common attribute (Local Interfaces §6.1 — `stat`: 1=online,
0=offline; §4 — NOTIFY events include `stat` for online/offline changes).
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import generate_entity_id
from .coordinator import LifeSmartCoordinator
from .availability import HubAvailability
from .entity import LifeSmartDeviceEntity
from .models import LifeSmartConfigEntry

_LOGGER = logging.getLogger(__name__)

# Read-only platform fed by push and the shared coordinator: nothing to limit
# (HA quality scale `parallel-updates`).
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LifeSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LifeSmart binary sensors."""
    _LOGGER.debug("Setting up LifeSmart binary_sensors")

    runtime = config_entry.runtime_data
    api = runtime.api
    coordinator = runtime.coordinator
    # D22: hub device registry ID — sub-devices hang off it via via_device_id.
    hub_device_id = runtime.hub_device_id
    availability = runtime.availability
    devices = runtime.devices
    if not devices:
        try:
            devices_data: Dict[str, Any] = await api.discover_devices()
            if isinstance(devices_data, dict) and isinstance(devices_data.get("msg"), list):
                devices = devices_data["msg"]
                runtime.devices = devices
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
                            coordinator=coordinator, availability=availability,
                        )
                    )
            except KeyError as e:
                _LOGGER.error("Missing required device field: %s", e)
                continue

    _LOGGER.debug("Adding %s binary_sensors", len(binary_sensors))
    async_add_entities(binary_sensors)


class LifeSmartConnectivitySensor(LifeSmartDeviceEntity, BinarySensorEntity):
    """Online/offline status of a LifeSmart sub-device.

    State sources:
    1. Push via api.register_state_listener(me, "stat", ...) — driven by
       LI §4 NOTIFY events; api.py extracts scalar `stat` from `chg` items
       and dispatches as virtual idx "stat".
    2. Fallback: the shared LifeSmartCoordinator's 15 min `eps` snapshot,
       in case a push is lost. D15 (R25): it replaced a per-entity `ep` GET
       timer, so N connectivity sensors no longer cost N requests a cycle.

    R32: the base class listens to `stat` for every sub-device entity and
    turns the others unavailable while the device is offline. This one stays
    available and shows "Disconnected": that is what it is for. It still goes
    unavailable when the hub itself stops answering.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _follows_device_stat = False

    def __init__(
        self,
        api: Any,
        device: Dict[str, Any],
        hub_device_id: Optional[str] = None,
        coordinator: Optional[LifeSmartCoordinator] = None,
        availability: Optional[HubAvailability] = None,
    ) -> None:
        try:
            super().__init__(
                api, device, None,
                hub_device_id=hub_device_id, coordinator=coordinator,
                availability=availability,
            )
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

            stat = device.get("stat")
            self._attr_is_on = (stat == 1) if isinstance(stat, (int, float)) else None
        except KeyError as e:
            _LOGGER.error("Missing required connectivity sensor field: %s", e)
            raise

    @callback
    def _handle_stat_value(self, val: Any) -> None:
        """Pushed `stat` (LI §4 NOTIFY, dispatched as virtual idx "stat")."""
        if not isinstance(val, (int, float)):
            return
        self._attr_is_on = (val == 1)
        self._async_write_if_added()

    def _update_from_device(self, device: Dict[str, Any]) -> bool:
        """D15: `stat` from the coordinator's `eps` snapshot."""
        stat = device.get("stat")
        if not isinstance(stat, (int, float)):
            return False
        self._attr_is_on = (stat == 1)
        return True
