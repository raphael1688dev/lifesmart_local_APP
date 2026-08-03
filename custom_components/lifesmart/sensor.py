"""Platform for LifeSmart sensor integration."""
import logging
from datetime import timedelta
from typing import Any, Callable, Dict, Optional, List
import asyncio
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
)
from .const import CMD_GET, DOMAIN, HUB_MODEL_NAMES, MANUFACTURER
from .coordinator import LifeSmartCoordinator
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
                                idx="T",
                                coordinator=coordinator,
                                hub_device_id=hub_device_id,
                            )
                        )
                elif device.get("devtype") == "SL_P" and "data" in device and "P8" in device["data"]:
                    _LOGGER.debug("Found battery sensor in %s", device['name'])
                    sensors.append(
                        LifeSmartBatterySensor(
                            api=api,
                            device=device,
                            idx="P8",
                            coordinator=coordinator,
                            hub_device_id=hub_device_id,
                        )
                    )
                elif (
                    isinstance(device.get("devtype"), str)
                    and device["devtype"].startswith(("SL_SW_ND", "SL_MC_ND"))
                    and "data" in device
                    and "V" in device["data"]
                ):
                    # §6.3.2 Stellar/Starry/Polar Switch (SL_SW_ND*)
                    # §6.3.5 Stellar/Starry/Polar Multi-control Accessory (SL_MC_ND*)
                    # V idx = battery level, range 0-100 %, read-only
                    _LOGGER.debug("Found switch battery sensor in %s", device.get('name'))
                    sensors.append(
                        LifeSmartBatterySensor(
                            api=api,
                            device=device,
                            idx="V",
                            coordinator=coordinator,
                            hub_device_id=hub_device_id,
                        )
                    )

                # Universal: signal strength (LI §6.1 common attribute `lDbm`).
                # Independent `if` — coexists with the elif chain above so a
                # device can have e.g. both a Temperature sensor and a Signal sensor.
                if "lDbm" in device:
                    _LOGGER.debug("Found signal sensor in %s", device.get('name'))
                    sensors.append(
                        LifeSmartSignalSensor(
                            api=api,
                            device=device,
                            coordinator=coordinator,
                            hub_device_id=hub_device_id,
                        )
                    )
            except KeyError as e:
                _LOGGER.error("Missing required device data: %s", e)
                continue
            except ValueError as e:
                _LOGGER.error("Invalid device data format: %s", e)
                continue

    # Phase 1 / R9: hub-level diagnostic sensors driven by cfg:getver
    # (cached at integration setup, see __init__.py).
    hub_info = entry_data.get("hub_info") or {}
    host = entry_data.get("host", "")
    for field in ("ver", "osver", "mgatype"):
        sensors.append(LifeSmartHubInfoSensor(
            hub_info=hub_info, host=host, field=field,
            config_entry_title=config_entry.title or "LifeSmart Hub",
        ))

    _LOGGER.debug("Adding %s sensors", len(sensors))
    async_add_entities(sensors)

class LifeSmartBaseSensor(SensorEntity):
    """Base for periodically-polled sub-device sensors.

    D15 (2026-05-24): periodic refresh now flows through the shared
    LifeSmartCoordinator (one `eps` request per cycle instead of N).
    The push state_listener mechanism stays — it's orthogonal and gives
    near-real-time updates between coordinator cycles.
    """

    _attr_should_poll = False
    _api: Any
    _device: Dict[str, Any]
    _idx: Optional[str]
    _coordinator: Optional[LifeSmartCoordinator]
    _attr_device_info: DeviceInfo
    _unsub_report: Optional[Callable[[], None]]
    _unsub_coordinator: Optional[Callable[[], None]]

    def __init__(
        self,
        api: Any,
        device: Dict[str, Any],
        idx: Optional[str] = None,
        coordinator: Optional[LifeSmartCoordinator] = None,
        hub_device_id: Optional[str] = None,
    ) -> None:
        self._api = api
        self._device = device
        self._idx = idx
        self._coordinator = coordinator
        self._unsub_report = None
        self._unsub_coordinator = None

        try:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device['me'])},
                name=device.get('name', 'LifeSmart Sensor'),
                manufacturer=MANUFACTURER,
                model=device.get('devtype', 'Unknown'),
                sw_version=device.get('epver', 'Unknown')
            )
            # D22: link under the hub device. `via_device_id` (not the
            # deprecated `via_device` tuple) — see __init__.py rationale.
            if hub_device_id:
                self._attr_device_info["via_device_id"] = hub_device_id
        except KeyError as e:
            _LOGGER.error("Missing required device info field: %s", e)
            raise

    async def async_added_to_hass(self) -> None:
        """Subscribe to push + coordinator."""
        if self._idx is not None:
            self._unsub_report = self._api.register_state_listener(
                self._device["me"], self._idx, self._handle_state_value,
            )
        # One-shot initial fetch (don't wait for coordinator tick).
        await self._async_update()

        # D15: replace per-entity timer with coordinator subscription.
        if self._coordinator is not None:
            self._unsub_coordinator = self._coordinator.async_add_listener(
                self._handle_coordinator_update
            )

    async def async_will_remove_from_hass(self) -> None:
        """When entity is removed from hass."""
        if self._unsub_coordinator:
            self._unsub_coordinator()
            self._unsub_coordinator = None
        if self._unsub_report:
            self._unsub_report()
            self._unsub_report = None

    async def _async_update(self, *_: Any) -> None:
        """Abstract method to be implemented by child classes."""
        raise NotImplementedError

    def _handle_coordinator_update(self) -> None:
        """Called when coordinator finishes a polling cycle.

        Subclasses override to pull their value out of the fresh device
        dict in `self._coordinator.data[me]` and write_ha_state. Default
        falls back to the legacy one-shot poll path.
        """
        if self.hass:
            self.hass.async_create_task(self._async_update())

    def _device_from_coordinator(self) -> Optional[Dict[str, Any]]:
        """Read the freshest device dict from coordinator cache, if any."""
        if self._coordinator is None or self._coordinator.data is None:
            return None
        return self._coordinator.data.get(self._device["me"])

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

    def __init__(
        self,
        api: Any,
        device: Dict[str, Any],
        idx: str,
        coordinator: Optional[LifeSmartCoordinator] = None,
        hub_device_id: Optional[str] = None,
    ) -> None:
        super().__init__(api, device, idx, coordinator=coordinator, hub_device_id=hub_device_id)
        try:
            # HA 2026.5 naming: _attr_name = function only;
            # device name is provided by DeviceInfo (base class).
            self._attr_name = "Temperature"
            # Include agt (R10) — `me` collides across hubs on system devices.
            self._attr_unique_id = f"temp_{device.get('agt', '')}_{device['me']}"
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_state_class = SensorStateClass.MEASUREMENT

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

    def _handle_coordinator_update(self) -> None:
        """D15: pull fresh value from coordinator's eps snapshot."""
        device = self._device_from_coordinator()
        if device is None:
            return
        raw = device.get("data", {}).get(self._idx, {}).get("v")
        if isinstance(raw, (int, float)):
            self._attr_native_value = float(raw) / 10.0
            if self.hass:
                self.hass.async_create_task(self._async_write_state())

    async def _async_update(self, *_: Any) -> None:
        """One-shot init fetch. Periodic refresh now handled by coordinator."""
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
        except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError) as e:
            _LOGGER.error("Unexpected error updating temperature sensor: %s", e)


class LifeSmartBatterySensor(LifeSmartBaseSensor):
    _attr_name: str
    _attr_unique_id: str
    _attr_native_value: Optional[int]
    _attr_native_unit_of_measurement: str

    def __init__(
        self,
        api: Any,
        device: Dict[str, Any],
        idx: str,
        coordinator: Optional[LifeSmartCoordinator] = None,
        hub_device_id: Optional[str] = None,
    ) -> None:
        super().__init__(api, device, idx, coordinator=coordinator, hub_device_id=hub_device_id)
        try:
            # HA 2026.5 naming: _attr_name = function only;
            # device name is provided by DeviceInfo (base class).
            self._attr_name = "Battery"
            # Include agt (R10) — `me` collides across hubs on system devices.
            self._attr_unique_id = f"battery_{device.get('agt', '')}_{device['me']}"
            self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_native_value = device.get("data", {}).get(idx, {}).get("v")
            device_type = device.get('devtype')
            hub_id = device.get('agt', '')
            device_id = device['me']
            self._idx = idx
            self.entity_id = f"sensor.{generate_entity_id(device_type, hub_id, device_id, idx)}"
        except KeyError as e:
            _LOGGER.error("Missing required battery sensor field: %s", e)
            raise

    def _handle_coordinator_update(self) -> None:
        """D15: pull fresh value from coordinator's eps snapshot."""
        device = self._device_from_coordinator()
        if device is None:
            return
        raw = device.get("data", {}).get(self._idx, {}).get("v")
        if isinstance(raw, (int, float)):
            self._attr_native_value = int(raw)
            if self.hass:
                self.hass.async_create_task(self._async_write_state())

    async def _async_update(self, *_: Any) -> None:
        """One-shot init fetch. Periodic refresh now handled by coordinator."""
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
        except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError) as e:
            _LOGGER.error("Unexpected error updating battery sensor: %s", e)

    def _handle_state_value(self, val: Any) -> None:
        if not isinstance(val, (int, float)):
            return
        self._attr_native_value = int(val)
        if self.hass:
            self.hass.async_create_task(self._async_write_state())


class LifeSmartSignalSensor(LifeSmartBaseSensor):
    """RF signal strength of the sub-device (LI §6.1 common attribute `lDbm`).

    lDbm is reported at the device level (not under `data[idx]`), already in dBm,
    available for both battery-powered and mains-powered devices. No state listener
    is registered (idx=None) — polling-only via periodic `ep` GET.
    """

    _attr_name: str
    _attr_unique_id: str
    _attr_native_value: Optional[int]
    _attr_native_unit_of_measurement: str

    def __init__(
        self,
        api: Any,
        device: Dict[str, Any],
        coordinator: Optional[LifeSmartCoordinator] = None,
        hub_device_id: Optional[str] = None,
    ) -> None:
        super().__init__(api, device, idx=None, coordinator=coordinator, hub_device_id=hub_device_id)
        try:
            # HA 2026.5 naming: function only; device name from DeviceInfo.
            self._attr_name = "Signal strength"
            # Include agt (R10) — `me` collides across hubs on system devices.
            self._attr_unique_id = f"signal_{device.get('agt', '')}_{device['me']}"
            self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            raw = device.get("lDbm")
            self._attr_native_value = int(raw) if isinstance(raw, (int, float)) else None
            device_type = device.get('devtype')
            hub_id = device.get('agt', '')
            device_id = device['me']
            # Virtual idx "signal" only feeds entity_id slug, not state listener.
            self.entity_id = (
                f"sensor.{generate_entity_id(device_type, hub_id, device_id, 'signal')}"
            )
        except KeyError as e:
            _LOGGER.error("Missing required signal sensor field: %s", e)
            raise

    def _handle_coordinator_update(self) -> None:
        """D15: pull fresh lDbm from coordinator's eps snapshot."""
        device = self._device_from_coordinator()
        if device is None:
            return
        raw = device.get("lDbm")
        if isinstance(raw, (int, float)):
            self._attr_native_value = int(raw)
            if self.hass:
                self.hass.async_create_task(self._async_write_state())

    async def _async_update(self, *_: Any) -> None:
        """One-shot init fetch. Periodic refresh now handled by coordinator."""
        args: Dict[str, Any] = {"me": self._device["me"]}
        try:
            response: Dict[str, Any] = await self._api.send_command("ep", args, CMD_GET)
            if response.get("code") == 0 and isinstance(response.get("msg"), dict):
                raw = response["msg"].get("lDbm")
                if isinstance(raw, (int, float)):
                    self._attr_native_value = int(raw)
                    self.async_write_ha_state()
        except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError) as e:
            _LOGGER.error("Unexpected error updating signal sensor: %s", e)


class LifeSmartHubInfoSensor(SensorEntity):
    """Hub-level identity sensor driven by cfg:getver (LI §3.3.10).

    Three instances per integration entry — ver / osver / mgatype. Mounted on
    the synthetic hub device (identifiers `(DOMAIN, f"hub_{host}")`) so they
    group with the future reboot button. Pure cache reader — no API calls.
    Refresh is owned by __init__.py (currently single-shot at setup; bump to
    24h timer if hubs upgrade in place).
    """

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    # Field-specific labels and unique_id slugs.
    _FIELD_META = {
        "ver":     ("Firmware version", "firmware"),
        "osver":   ("OS version",       "os"),
        "mgatype": ("Model",            "model"),
    }

    def __init__(
        self,
        hub_info: Dict[str, Any],
        host: str,
        field: str,
        config_entry_title: str,
    ) -> None:
        self._field = field
        label, slug = self._FIELD_META[field]
        host_slug = host.replace(".", "_")  # 192.168.1.50 -> 192_168_1_50

        self._attr_name = label
        self._attr_unique_id = f"hub_{slug}_{host_slug}"
        # Hub-level entity_id is hand-written per CLAUDE.md convention.
        self.entity_id = f"sensor.lifesmart_hub_{slug}"

        # Pre-format the mgatype value if a friendly name exists.
        raw = hub_info.get(field)
        if field == "mgatype" and isinstance(raw, str):
            self._attr_native_value = HUB_MODEL_NAMES.get(raw, raw)
        else:
            self._attr_native_value = raw

        hub_identifier = f"hub_{host}"
        mgatype = hub_info.get("mgatype")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub_identifier)},
            name=config_entry_title,
            manufacturer=MANUFACTURER,
            model=HUB_MODEL_NAMES.get(mgatype, mgatype) if isinstance(mgatype, str) else "LifeSmart Hub",
            sw_version=hub_info.get("ver"),
        )
