"""Platform for LifeSmart cover integration."""
import asyncio
import logging
from typing import Optional, Any
from homeassistant.components.cover import CoverEntity, CoverDeviceClass, CoverEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import CMD_SET, CMD_GET
from .coordinator import LifeSmartCoordinator
from .availability import HubAvailability
from .entity import LifeSmartDeviceEntity
from . import generate_entity_id
from .models import LifeSmartConfigEntry

_LOGGER = logging.getLogger(__name__)

# No limit on parallel action calls (HA quality scale `parallel-updates`): each
# request is one UDP datagram matched to its reply by id, and the hub answers
# in about 10 ms. A limit of 1 would make "turn off 19 switches" wait for each
# switch's confirmation in turn.
PARALLEL_UPDATES = 0

PORT_1 = "P2" # 負責打開
PORT_2 = "P3" # 負責關閉
PORT_3 = "P4" # 負責停止
PORT_STATE = "P1" # 負責回報狀態 (通常 SL_P 的 P1 代表行程/開關狀態)
TYPE_ON = 0x81

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LifeSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    _LOGGER.debug("Setting up LifeSmart cover platform")
    runtime = config_entry.runtime_data
    api = runtime.api
    # D22: hub device registry ID — sub-devices hang off it via via_device_id.
    hub_device_id = runtime.hub_device_id
    coordinator = runtime.coordinator
    # R41: the device list is the one setup read. Platforms used to read it
    # again when it was empty (a hub with nothing paired); a failed read then
    # cost the hub sensors, or failed the whole switch / cover / remote
    # platform, and a successful one only sent five more requests.
    devices = runtime.devices
    
    covers = []
    if isinstance(devices, list):
        _LOGGER.debug("Found %s devices in response", len(devices))
        for device in devices:
            if device.get("devtype") == "SL_P":
                _LOGGER.debug("Adding cover device: %s", device.get('name', 'MINS Curtain'))
                covers.append(
                    LifeSmartCover(
                        api=api,
                        device=device,
                        idx=device.get('idx', PORT_STATE),
                        hub_device_id=hub_device_id,
                        coordinator=coordinator,
                        availability=runtime.availability,
                    )
                )
    
    _LOGGER.debug("Adding %s cover entities", len(covers))
    async_add_entities(covers)


class LifeSmartCover(LifeSmartDeviceEntity, CoverEntity):
    """Representation of a LifeSmart cover.

    State comes from push on the state channel, one read when added, and the
    coordinator's 15 min `eps` snapshot as the fallback (D15, R25). Lifecycle
    and availability are in entity.py (R32).
    """

    # R18: HA 2026.5 naming. The cover IS the device, so the entity carries
    # no name of its own (`_attr_name = None`) and HA shows the device name.
    _attr_name = None

    def __init__(
        self,
        api,
        device,
        idx: Optional[str] = None,
        hub_device_id: Optional[str] = None,
        coordinator: Optional[LifeSmartCoordinator] = None,
        availability: Optional[HubAvailability] = None,
    ):
        device_name = device.get('name', 'MINS Curtain')
        super().__init__(
            api, device, idx or PORT_STATE,
            hub_device_id=hub_device_id, coordinator=coordinator,
            availability=availability, device_name=device_name, default_model="SL_P",
        )
        # Include agt (R10) — `me` collides across hubs on system devices.
        self._attr_unique_id = f"cover_{device.get('agt', '')}_{device['me']}"
        self._attr_device_class = CoverDeviceClass.CURTAIN
        # 支援開、關、停功能
        self._attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        self._attr_is_closed = None
        # R41: start from the state in the device list, as the other entities
        # do. It used to stay unknown until the read below answered, or until
        # the 15-minute poll when that read failed.
        channel = device.get("data", {}).get(self._idx)
        if isinstance(channel, dict):
            self._set_closed(channel.get("v"))

        device_type = device.get("devtype")
        hub_id = device.get("agt", "")
        device_id = device["me"]
        self.entity_id = f"cover.{generate_entity_id(device_type, hub_id, device_id, self._idx)}"

        _LOGGER.debug("Initializing cover: %s (ID: %s)", device_name, self._attr_unique_id)

    async def _async_initial_refresh(self) -> None:
        """實體加入 HA 時獲取初始狀態（推播監聽由 entity.py 註冊）"""
        await self._async_update_state()

    async def _async_update_state(self, *_):
        """獲取窗簾初始狀態"""
        try:
            # 官方規範：精簡 GET 參數
            args = {
                "me": self._device["me"],
                "idx": self._idx
            }
            response = await self._api.send_command("ep", args, CMD_GET)
            if response.get("code") == 0 and "msg" in response:
                val = response["msg"]["data"].get(self._idx, {}).get("v")
                if val is not None:
                    self._update_internal_state(val)
        except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError) as ex:
            # R41: debug; the state from the device list stays (see __init__).
            _LOGGER.debug("Could not read %s at start (%s)", self.entity_id, type(ex).__name__)

    @callback
    def _handle_state_value(self, val: Any) -> None:
        """處理網關主動推播的 UDP 狀態"""
        self._update_internal_state(val)

    def _update_from_device(self, device: dict) -> bool:
        """D15: same channel as push (PORT_STATE, D1 unverified), from `eps`."""
        channel = device.get("data", {}).get(self._idx)
        return isinstance(channel, dict) and self._set_closed(channel.get("v"))

    def _set_closed(self, val: Any) -> bool:
        """Take a state-channel value. Return True if it was usable."""
        if not isinstance(val, (int, float)):
            return False
        # 假設 val 為 0 代表全關，大於 0 代表有開啟 (依照一般 SL_P 行為，若不同可自行調整)
        self._attr_is_closed = (val == 0)
        return True

    def _update_internal_state(self, val: Any) -> None:
        """更新 HA 內部狀態"""
        if self._set_closed(val):
            self._async_write_if_added()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        _LOGGER.debug("Opening cover: %s", self.entity_id)
        # 官方規範：加入 tag: "m"
        await self._api.send_command("ep", {
            "tag": "m",
            "me": self._device["me"],
            "idx": PORT_1,
            "type": TYPE_ON,
            "val": 1
        }, CMD_SET)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        _LOGGER.debug("Closing cover: %s", self.entity_id)
        await self._api.send_command("ep", {
            "tag": "m",
            "me": self._device["me"],
            "idx": PORT_2,
            "type": TYPE_ON,
            "val": 0 # 若原代碼 val:0 可運作則保留，若無效請改為 1
        }, CMD_SET)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        _LOGGER.debug("Stopping cover: %s", self.entity_id)
        await self._api.send_command("ep", {
            "tag": "m",
            "me": self._device["me"],
            "idx": PORT_3,
            "type": TYPE_ON,
            "val": 0 # 若原代碼 val:0 可運作則保留，若無效請改為 1
        }, CMD_SET)
