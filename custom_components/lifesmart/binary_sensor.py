"""Platform for LifeSmart binary_sensor integration.

Currently exposes one CONNECTIVITY binary_sensor per sub-device, based on the
device-level `stat` common attribute (Local Interfaces §6.1 — `stat`: 1=online,
0=offline; §4 — NOTIFY events include `stat` for online/offline changes).
"""
import asyncio
import logging
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import generate_entity_id
from .const import CMD_GET, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

# stat doesn't change as often as data channels; 15 min fallback poll is
# adequate since the primary signal is the NOTIFY push event.
UPDATE_INTERVAL_SECONDS = 900


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LifeSmart binary sensors."""
    _LOGGER.debug("Setting up LifeSmart binary_sensors")

    entry_data = hass.data[DOMAIN]["entries"][config_entry.entry_id]
    api = entry_data["api"]
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
        except Exception as e:
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
                        LifeSmartConnectivitySensor(api=api, device=device)
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
    2. Fallback periodic `ep` GET every 15 min — defensive in case push is lost.
    """

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    _api: Any
    _device: Dict[str, Any]
    _unsub_report: Optional[Callable[[], None]]
    _remove_tracker: Optional[Callable[[], None]]

    def __init__(self, api: Any, device: Dict[str, Any]) -> None:
        self._api = api
        self._device = device
        self._unsub_report = None
        self._remove_tracker = None

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

            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, me)},
                name=device.get('name', 'LifeSmart Device'),
                manufacturer=MANUFACTURER,
                model=devtype or 'Unknown',
                sw_version=device.get('epver', 'Unknown'),
            )

            stat = device.get("stat")
            self._attr_is_on = (stat == 1) if isinstance(stat, (int, float)) else None
        except KeyError as e:
            _LOGGER.error("Missing required connectivity sensor field: %s", e)
            raise

    async def async_added_to_hass(self) -> None:
        """Register push listener and fallback poll."""
        # Push: api dispatches stat changes via virtual idx "stat".
        self._unsub_report = self._api.register_state_listener(
            self._device["me"], "stat", self._handle_stat_value
        )
        await self._async_update()
        self._remove_tracker = async_track_time_interval(
            self.hass,
            self._async_update,
            timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_tracker:
            self._remove_tracker()
            self._remove_tracker = None
        if self._unsub_report:
            self._unsub_report()
            self._unsub_report = None

    def _handle_stat_value(self, val: Any) -> None:
        if not isinstance(val, (int, float)):
            return
        self._attr_is_on = (val == 1)
        if self.hass:
            self.hass.async_create_task(self._async_write_state())

    async def _async_write_state(self) -> None:
        self.async_write_ha_state()

    async def _async_update(self, *_: Any) -> None:
        """Fallback poll via ep GET — refreshes stat at device level."""
        args: Dict[str, Any] = {"me": self._device["me"]}
        try:
            response: Dict[str, Any] = await self._api.send_command("ep", args, CMD_GET)
            if response.get("code") == 0 and isinstance(response.get("msg"), dict):
                stat = response["msg"].get("stat")
                if isinstance(stat, (int, float)):
                    self._attr_is_on = (stat == 1)
                    self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Unexpected error updating connectivity sensor: %s", e)
