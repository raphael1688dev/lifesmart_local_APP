"""Platform for LifeSmart switch integration."""
import asyncio
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, CMD_GET, CMD_SET, MANUFACTURER
from . import generate_entity_id

_LOGGER = logging.getLogger(__name__)

VAL_TYPE_ON = 0x81
VAL_TYPE_OFF = 0x80

# 已合併新舊版本的所有支援型號
SUPPORTED_SWITCH_TYPES = [
    "SL_SW_NS1",
    "SL_SW_NS2",
    "SL_SW_NS3",
    "SL_NATURE",
    "SL_SW_ND1",
    "SL_SW_ND2",
    "SL_SW_ND3",
    "SL_SW_IF1",
    "SL_SW_IF2",
    "SL_SW_IF3",
    "SL_SW_RC"
]

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LifeSmart switches."""
    entry_data = hass.data[DOMAIN]["entries"][config_entry.entry_id]
    api = entry_data["api"]
    devices = entry_data.get("devices") or []
    if not devices:
        devices_data = await api.discover_devices()
        if isinstance(devices_data, dict) and isinstance(devices_data.get("msg"), list):
            devices = devices_data["msg"]
            entry_data["devices"] = devices
    
    switches = []
    if isinstance(devices, list):
        for device in devices:
            if device.get("devtype") in SUPPORTED_SWITCH_TYPES:
                data = device.get("data", {})
                for channel in ["L1", "L2", "L3"]:
                    if channel in data:
                        channel_data = data[channel]
                        channel_name = channel_data.get('name', channel).replace('{$EPN}', '').strip() or channel
                        switches.append(
                            LifeSmartSwitch(
                                api=api,
                                device=device,
                                idx=channel,
                                name=channel_name
                            )
                        )

    async_add_entities(switches)

class LifeSmartSwitch(SwitchEntity):
    _attr_should_poll = False
    def __init__(self, api, device, idx, name):
        """Initialize the switch."""
        self._api = api
        self._device = device
        self._idx = idx
        self._attr_name = name
        self._available = True
        self._unsub_report = None
        self._expected_state = None
        self._confirm_event = None
        self._failures = 0
        self._send_lock = asyncio.Lock()
        self._send_task: asyncio.Task | None = None
        self._pending_value: int | None = None
        self._pending_waiters: list[asyncio.Future] = []
        
        device_type = device.get('devtype')
        hub_id = device.get('agt', '')
        device_id = device['me']
        self._attr_unique_id = f"switch_{device_id}_{idx}"
        self.entity_id = f"switch.{generate_entity_id(device_type, hub_id, device_id, idx)}"
        
        initial_state = device.get("data", {}).get(idx, {}).get("v", 0)
        self._state = bool(initial_state)

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._unsub_report = self._api.register_state_listener(self._device["me"], self._idx, self._handle_state_value)
        await self._async_update_state()

    async def async_will_remove_from_hass(self):
        """When entity is removed from hass."""
        if self._unsub_report:
            self._unsub_report()
            self._unsub_report = None
        if self._send_task:
            self._send_task.cancel()
            self._send_task = None

    async def _async_update_state(self, *_):
        """Fetch state from device."""
        try:
            args = {
                "me": self._device["me"],
                "idx": self._idx
            }
            response = await self._api.send_command("ep", args, CMD_GET)
            if response.get("code") == 0 and "msg" in response:
                new_state = response["msg"]["data"][self._idx]["v"]
                self._state = bool(new_state)
                self._available = True
                _LOGGER.debug(
                    "Switch %s state updated: %s (value=%s)", 
                    self.entity_id, 
                    "on" if self._state else "off",
                    new_state
                )
            self.async_write_ha_state()
        except Exception as ex:
            self._failures += 1
            if self._failures >= 3:
                self._available = False
            self.async_write_ha_state()

    def _handle_state_value(self, val) -> None:
        if not isinstance(val, (int, float)):
            return
        self._state = bool(int(val))
        self._available = True
        self._failures = 0
        if self._confirm_event and self._expected_state is not None and self._state == self._expected_state:
            self._confirm_event.set()
        if self.hass:
            self.hass.async_create_task(self._async_write_state())

    async def _async_write_state(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device['me'])},
            name=self._device.get('name', 'LifeSmart Switch'),
            manufacturer=MANUFACTURER,
            model=self._device.get('devtype'),
            sw_version=self._device.get('epver'),
        )

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._enqueue_command(1)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._enqueue_command(0)

    async def _enqueue_command(self, value: int) -> None:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending_value = value
        self._pending_waiters.append(fut)
        if self._send_task is None or self._send_task.done():
            self._send_task = self.hass.async_create_task(self._drain_pending_commands())
        await fut

    async def _drain_pending_commands(self) -> None:
        async with self._send_lock:
            while self._pending_value is not None:
                value = self._pending_value
                waiters = self._pending_waiters
                self._pending_value = None
                self._pending_waiters = []
                try:
                    await self._send_command(value)
                finally:
                    for w in waiters:
                        if not w.done():
                            w.set_result(None)

    async def _send_command(self, value: int) -> None:
        args = {
            "tag": "m",
            "me": self._device["me"],
            "idx": self._idx,
            "type": VAL_TYPE_ON if value == 1 else VAL_TYPE_OFF,
            "val": value
        }
        try:
            self._expected_state = bool(value)
            self._confirm_event = asyncio.Event()
            try:
                response = await self._api.send_command("ep", args, CMD_SET, 0.7)
            except asyncio.TimeoutError:
                response = {"code": 0}

            if response.get("code") == 0:
                self._available = True
                self._failures = 0
                try:
                    await asyncio.wait_for(self._confirm_event.wait(), timeout=1.5)
                except asyncio.TimeoutError:
                    await self._async_update_state()
            else:
                await self._async_update_state()
        except Exception as ex:
            _LOGGER.error("Error sending command: %s", type(ex).__name__)
            self._failures += 1
            if self._failures >= 3:
                self._available = False
            self.async_write_ha_state()
        finally:
            self._expected_state = None
            self._confirm_event = None
