"""Platform for LifeSmart sensor integration."""
import logging
from datetime import timedelta
from typing import Any, Callable, Dict, Optional, List
import asyncio
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from .const import DOMAIN, CMD_GET, MANUFACTURER
from . import generate_entity_id
_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL_SECONDS = 900

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    _LOGGER.debug("Setting up LifeSmart sensors")

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

    sensors: List[SensorEntity] = []
    if isinstance(devices, list):
        for device in devices:
            try:
                if device.get("devtype") == "SL_NATURE":
                    if "data" in device and "T" in device["data"]:
                        _LOGGER.debug("Found temperature sensor in %s", device['name'])
                        sensors.append(
                            LifeSmartTemperatureSensor(
                                api=api,
                                device=device,
                                idx="T"
                            )
                        )
                elif device.get("devtype") == "SL_P" and "data" in device and "P8" in device["data"]:
                    _LOGGER.debug("Found battery sensor in %s", device['name'])
                    sensors.append(
                        LifeSmartBatterySensor(
                            api=api,
                            device=device,
                            idx="P8"
                        )
                    )
            except KeyError as e:
                _LOGGER.error("Missing required device data: %s", e)
                continue
            except ValueError as e:
                _LOGGER.error("Invalid device data format: %s", e)
                continue

    _LOGGER.debug("Adding %s sensors", len(sensors))
    async_add_entities(sensors)

class LifeSmartBaseSensor(SensorEntity):
    _attr_should_poll = False
    _api: Any
    _device: Dict[str, Any]
    _idx: Optional[str]
    _remove_tracker: Optional[Callable[[], None]]
    _attr_device_info: DeviceInfo
    _unsub_report: Optional[Callable[[], None]]

    def __init__(self, api: Any, device: Dict[str, Any], idx: Optional[str] = None) -> None:
        self._api = api
        self._device = device
        self._idx = idx
        self._remove_tracker = None
        self._unsub_report = None


        try:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device['me'])},
                name=device.get('name', 'LifeSmart Sensor'),
                manufacturer=MANUFACTURER,
                model=device.get('devtype', 'Unknown'),
                sw_version=device.get('epver', 'Unknown')
            )
        except KeyError as e:
            _LOGGER.error("Missing required device info field: %s", e)
            raise

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        if self._idx is not None:
            self._unsub_report = self._api.register_state_listener(self._device["me"], self._idx, self._handle_state_value)
        await self._async_update()

        self._remove_tracker = async_track_time_interval(
            self.hass,
            self._async_update,
            timedelta(seconds=UPDATE_INTERVAL_SECONDS)
        )

    async def async_will_remove_from_hass(self) -> None:
        """When entity is removed from hass."""
        if self._remove_tracker:
            self._remove_tracker()
        if self._unsub_report:
            self._unsub_report()
            self._unsub_report = None

    async def _async_update(self, *_: Any) -> None:
        """Abstract method to be implemented by child classes."""
        raise NotImplementedError

    def _handle_state_value(self, val: Any) -> None:
        if not isinstance(val, (int, float)):
            return
        self._attr_native_value = val
        if self.hass:
            self.hass.async_create_task(self._async_write_state())

    async def _async_write_state(self) -> None:
        self.async_write_ha_state()

class LifeSmartTemperatureSensor(LifeSmartBaseSensor):
    _attr_name: str
    _attr_unique_id: str
    _attr_native_value: Optional[float]
    _attr_native_unit_of_measurement: str

    def __init__(self, api: Any, device: Dict[str, Any], idx: str) -> None:
        super().__init__(api, device, idx)
        try:
            self._attr_name = device.get('name', 'Temperature Sensor')
            self._attr_unique_id = f"temp_{device['me']}"

            raw_v = device.get("data", {}).get(idx, {}).get("v")
            if raw_v is not None:
                self._attr_native_value = float(raw_v) / 10.0
            else:
                self._attr_native_value = None

            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            device_type = device.get('devtype')
            hub_id = device.get('agt', '')
            device_id = device['me']
            self._idx = idx
            self.entity_id = f"sensor.{generate_entity_id(device_type, hub_id, device_id, idx)}"

        except KeyError as e:
            _LOGGER.error("Missing required temperature sensor field: %s", e)
            raise

    def _handle_state_value(self, val: Any) -> None:
        if not isinstance(val, (int, float)):
            return
        self._attr_native_value = float(val) / 10.0
        if self.hass:
            self.hass.async_create_task(self._async_write_state())

    async def _async_update(self, *_: Any) -> None:
        """Fetch temperature from device."""
        args: Dict[str, Any] = {
            "me": self._device["me"],
            "idx": self._idx
        }
        try:
            response: Dict[str, Any] = await self._api.send_command("ep", args, CMD_GET)
            if response.get("code") == 0 and "msg" in response:
                temp_value = response["msg"]["data"][self._idx]["v"]
                self._attr_native_value = float(temp_value) / 10.0
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Unexpected error updating temperature sensor: %s", e)


class LifeSmartBatterySensor(LifeSmartBaseSensor):
    _attr_name: str
    _attr_unique_id: str
    _attr_native_value: Optional[int]
    _attr_native_unit_of_measurement: str

    def __init__(self, api: Any, device: Dict[str, Any] , idx: str) -> None:
        super().__init__(api, device, idx)
        try:
            self._attr_name = f"{device.get('name', 'MINS Curtain')} Battery"
            self._attr_unique_id = f"battery_{device['me']}"
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_native_value = device.get("data", {}).get("P8", {}).get("v")
            device_type = device.get('devtype')
            hub_id = device.get('agt', '')
            device_id = device['me']
            self._idx = idx
            self.entity_id = f"sensor.{generate_entity_id(device_type, hub_id, device_id, idx)}"
        except KeyError as e:
            _LOGGER.error("Missing required battery sensor field: %s", e)
            raise

    async def _async_update(self, *_: Any) -> None:
        """Fetch battery level."""
        args: Dict[str, Any] = {
            "me": self._device["me"],
            "idx": self._idx
        }
        try:
            response: Dict[str, Any] = await self._api.send_command("ep", args, CMD_GET)
            if response.get("code") == 0 and "msg" in response:
                battery_level = response["msg"]["data"][self._idx]["v"]
                self._attr_native_value = int(battery_level)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Unexpected error updating battery sensor: %s", e)

    def _handle_state_value(self, val: Any) -> None:
        if not isinstance(val, (int, float)):
            return
        self._attr_native_value = int(val)
        if self.hass:
            self.hass.async_create_task(self._async_write_state())
