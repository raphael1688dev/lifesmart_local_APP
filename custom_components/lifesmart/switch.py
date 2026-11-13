"""Platform for LifeSmart switch integration."""
import asyncio
import logging
from typing import Optional
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import CMD_GET, CMD_SET
from .availability import HubAvailability
from .coordinator import LifeSmartCoordinator
from .entity import LifeSmartDeviceEntity
from .group_scene import SWITCH_GROUP_CLASSES, LifeSmartGroupScene, group_scenes
from . import generate_entity_id
from .models import LifeSmartConfigEntry

_LOGGER = logging.getLogger(__name__)

# No limit on parallel action calls (HA quality scale `parallel-updates`): each
# request is one UDP datagram matched to its reply by id, and the hub answers
# in about 10 ms. A limit of 1 would make "turn off 19 switches" wait for each
# switch's confirmation in turn.
PARALLEL_UPDATES = 0

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
    "SL_SW_RC",
    # LI §6.3.5 Multi-control Accessory: L1-L3 take the same type/val
    # commands as the switches above (D9, R25). Its B1-B3 buttons are events.
    "SL_MC_ND1",
    "SL_MC_ND2",
    "SL_MC_ND3",
]

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LifeSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LifeSmart switches."""
    runtime = config_entry.runtime_data
    api = runtime.api
    # D22: hub device registry ID — sub-devices hang off it via via_device_id.
    hub_device_id = runtime.hub_device_id
    # R41: the device list is the one setup read. Platforms used to read it
    # again when it was empty (a hub with nothing paired); a failed read then
    # cost the hub sensors, or failed the whole switch / cover / remote
    # platform, and a successful one only sent five more requests.
    devices = runtime.devices
    
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
                                name=channel_name,
                                hub_device_id=hub_device_id,
                                coordinator=runtime.coordinator,
                                availability=runtime.availability,
                            )
                        )

    # D9 (R25): LI §5.2 `groupsw` scenes turn a group on / off.
    hub_key = runtime.hub_key
    for scene in group_scenes(runtime.scenes, SWITCH_GROUP_CLASSES):
        switches.append(
            LifeSmartGroupSwitch(
                api=api,
                scene=scene,
                platform="switch",
                hub_key=hub_key,
                hub_info=runtime.hub_info,
                title=config_entry.title or "LifeSmart Hub",
                availability=runtime.availability,
            )
        )

    async_add_entities(switches)


class LifeSmartGroupSwitch(LifeSmartGroupScene, SwitchEntity):
    """A `groupsw` scene: a group of switches / bulbs, on or off."""

    _attr_device_class = SwitchDeviceClass.SWITCH


class LifeSmartSwitch(LifeSmartDeviceEntity, SwitchEntity):
    """One channel (L1 / L2 / L3) of a switch.

    R32: lifecycle and availability are in entity.py. The coordinator is
    only the fallback for the device's `stat`; the on / off state comes from
    push and from the reads below.
    """

    _attr_device_class = SwitchDeviceClass.SWITCH  # R32: quality scale `entity-device-class`
    # R18: HA 2026.5 naming — `_attr_name` is the channel label only ("L1" or
    # the firmware-provided channel name); the frontend prepends the device name.

    def __init__(
        self,
        api,
        device,
        idx,
        name,
        hub_device_id: Optional[str] = None,
        coordinator: Optional[LifeSmartCoordinator] = None,
        availability: Optional[HubAvailability] = None,
    ):
        """Initialize the switch."""
        super().__init__(
            api, device, idx,
            hub_device_id=hub_device_id, coordinator=coordinator,
            availability=availability, default_name="LifeSmart Switch",
        )
        self._attr_name = name
        self._expected_state = None
        self._confirm_event = None
        self._send_lock = asyncio.Lock()
        self._send_task: asyncio.Task | None = None
        self._pending_value: int | None = None
        self._pending_waiters: list[asyncio.Future] = []

        device_type = device.get('devtype')
        hub_id = device.get('agt', '')
        device_id = device['me']
        # Include agt (R10) — `me` collides across hubs on system devices.
        self._attr_unique_id = f"switch_{hub_id}_{device_id}_{idx}"
        self.entity_id = f"switch.{generate_entity_id(device_type, hub_id, device_id, idx)}"

        initial_state = device.get("data", {}).get(idx, {}).get("v", 0)
        self._state = bool(initial_state)

    async def _async_initial_refresh(self) -> None:
        await self._async_update_state()

    def _cleanup(self) -> None:
        if self._send_task:
            self._send_task.cancel()
            self._send_task = None

    async def _async_update_state(self, *_, retries: Optional[int] = None):
        """Fetch state from device.

        `retries` goes to api.send_command (None = its default for a GET).
        The command path passes 0: it holds the send lock, and a silent hub
        should not keep the next command waiting for two timeouts (R28).
        """
        try:
            args = {
                "me": self._device["me"],
                "idx": self._idx
            }
            response = await self._api.send_command("ep", args, CMD_GET, retries=retries)
            if response.get("code") == 0 and "msg" in response:
                new_state = response["msg"]["data"][self._idx]["v"]
                self._state = bool(new_state)
                _LOGGER.debug(
                    "Switch %s state updated: %s (value=%s)", 
                    self.entity_id, 
                    "on" if self._state else "off",
                    new_state
                )
            self.async_write_ha_state()
        except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError) as ex:
            # R32: one failed read no longer counts towards "unavailable".
            # That is decided for the whole hub (availability.py) and by the
            # device's `stat`, not per entity.
            _LOGGER.debug("Switch %s state read failed: %s", self.entity_id, type(ex).__name__)

    @callback
    def _handle_state_value(self, val) -> None:
        if not isinstance(val, (int, float)):
            return
        self._state = bool(int(val))
        if self._confirm_event and self._expected_state is not None and self._state == self._expected_state:
            self._confirm_event.set()
        self._async_write_if_added()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

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
                try:
                    await asyncio.wait_for(self._confirm_event.wait(), timeout=1.5)
                except asyncio.TimeoutError:
                    await self._async_update_state(retries=0)
            else:
                await self._async_update_state(retries=0)
        except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError) as ex:
            _LOGGER.error("Error sending command: %s", type(ex).__name__)
        finally:
            self._expected_state = None
            self._confirm_event = None
