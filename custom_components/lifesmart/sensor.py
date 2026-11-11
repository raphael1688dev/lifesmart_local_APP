"""Platform for LifeSmart sensor integration."""
import logging
from typing import Any, Callable, Dict, Optional, List
import asyncio
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
)
from .const import CMD_GET, HUB_MODEL_NAMES
from .coordinator import LifeSmartCoordinator, LifeSmartHubCoordinator
from .device_info import hub_device_info, hub_key_slug, sub_device_info
from . import generate_entity_id
from .models import LifeSmartConfigEntry
_LOGGER = logging.getLogger(__name__)

# Read-only platform fed by push and the shared coordinator: nothing to limit
# (HA quality scale `parallel-updates`).
PARALLEL_UPDATES = 0

UPDATE_INTERVAL_SECONDS = 900

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LifeSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    _LOGGER.debug("Setting up LifeSmart sensors")

    runtime = config_entry.runtime_data
    api = runtime.api
    coordinator = runtime.coordinator
    # D22: hub device registry ID — sub-devices hang off it via via_device_id.
    hub_device_id = runtime.hub_device_id
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
                    and device["devtype"].startswith(("SL_SW_ND", "SL_MC_ND", "SL_SC_BB"))
                    and "data" in device
                    and "V" in device["data"]
                ):
                    # §6.3.2 Stellar/Starry/Polar Switch (SL_SW_ND*)
                    # §6.3.5 Stellar/Starry/Polar Multi-control Accessory (SL_MC_ND*)
                    # §6.3.6 / §6.3.7 CUBE Clicker (SL_SC_BB / SL_SC_BB_V2, R25)
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

    # Phase 1 / R9: hub-level diagnostic sensors driven by cfg:getver; D4
    # (R25) the hub coordinator re-reads it daily, plus cfg:timezone.
    hub_coordinator = runtime.hub_coordinator
    hub_info = runtime.hub_info
    hub_key = runtime.hub_key
    for field in ("ver", "osver", "mgatype", "timezone"):
        sensors.append(LifeSmartHubInfoSensor(
            hub_info=hub_info, hub_key=hub_key, field=field,
            config_entry_title=config_entry.title or "LifeSmart Hub",
            hub_coordinator=hub_coordinator,
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
    # R18: HA 2026.5 naming — entity name describes only the function
    # ("Battery"); the frontend prepends the device name. Explicit entity_ids
    # are unaffected (platform uses our entity_id as suggested object id).
    _attr_has_entity_name = True
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
            # R19: built in one go by device_info.py — DeviceInfo is a
            # dataclass from HA 2026.11, so no item assignment. via_device_id
            # (D22) and sw_version handling live there.
            self._attr_device_info = sub_device_info(
                device, hub_device_id, default_name="LifeSmart Sensor"
            )
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

    @callback
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Opt in to in-place entity_id renames (HA 2026.11+, R19).

        Nothing here is keyed on entity_id — push listeners key on (me, idx)
        and the coordinator listener on the object — so there is nothing to
        re-key. Without this method HA keeps removing and re-adding the
        entity on rename (compat path, removed in 2027.11) because this class
        defines async_added_to_hass / async_will_remove_from_hass.
        """
        super().async_entity_id_changed(old_entity_id)

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
    """Hub-level sensor driven by cfg:getver / cfg:timezone (LI §3.3.10).

    Four instances per integration entry — ver / osver / mgatype / timezone.
    Mounted on the synthetic hub device so they group with the reboot
    button. No API calls of their own: D4 (R25) the hub coordinator re-reads
    the values daily and these follow it.
    """

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True  # R18: "Firmware version" + hub device name

    # Field-specific labels and unique_id slugs.
    _FIELD_META = {
        "ver":      ("Firmware version", "firmware"),
        "osver":    ("OS version",       "os"),
        "mgatype":  ("Model",            "model"),
        "timezone": ("Time zone",        "timezone"),
    }

    def __init__(
        self,
        hub_info: Dict[str, Any],
        hub_key: str,
        field: str,
        config_entry_title: str,
        hub_coordinator: Optional[LifeSmartHubCoordinator] = None,
    ) -> None:
        self._field = field
        self._hub_coordinator = hub_coordinator
        self._unsub_coordinator: Optional[Callable[[], None]] = None
        label, slug = self._FIELD_META[field]

        self._attr_name = label
        # D21 (R25): hub_key is the hub ID; for older entries still the host,
        # whose slug gives the pre-R25 `hub_firmware_192_168_1_50`.
        self._attr_unique_id = f"hub_{slug}_{hub_key_slug(hub_key)}"
        # Hub-level entity_id is hand-written per CLAUDE.md convention.
        self.entity_id = f"sensor.lifesmart_hub_{slug}"
        self._apply(hub_info)

        # R19: same kwargs as __init__.py's registry call and button.py, built
        # by device_info.py (R17 omit-unknown sw_version and R18 str() live
        # there) — no item assignment, DeviceInfo is a dataclass from 2026.11.
        self._attr_device_info = hub_device_info(hub_key, config_entry_title, hub_info)

    def _apply(self, hub_info: Dict[str, Any]) -> None:
        raw = hub_info.get(self._field)
        if self._field == "mgatype" and isinstance(raw, str):
            self._attr_native_value = HUB_MODEL_NAMES.get(raw, raw)
        elif self._field == "timezone":
            # LI §3.3.10: [-12, 12], east positive; `summer` = DST.
            self._attr_native_value = f"UTC{raw:+d}" if isinstance(raw, int) else None
            summer = hub_info.get("summer")
            self._attr_extra_state_attributes = (
                {"daylight_saving": summer} if isinstance(summer, bool) else {}
            )
        else:
            self._attr_native_value = raw

    async def async_added_to_hass(self) -> None:
        if self._hub_coordinator is not None:
            self._unsub_coordinator = self._hub_coordinator.async_add_listener(
                self._handle_coordinator_update
            )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_coordinator:
            self._unsub_coordinator()
            self._unsub_coordinator = None

    @callback
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Opt in to in-place entity_id renames (HA 2026.11+, R19).

        The coordinator listener is keyed on the bound method, not the
        entity_id, so there is nothing to re-key.
        """
        super().async_entity_id_changed(old_entity_id)

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._hub_coordinator is None or self._hub_coordinator.data is None:
            return
        self._apply(self._hub_coordinator.data)
        self.async_write_ha_state()
