"""Platform for LifeSmart cover integration."""
import logging
from typing import Optional, Any
from homeassistant.components.cover import CoverEntity, CoverDeviceClass, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, CMD_SET, CMD_GET, MANUFACTURER
from . import generate_entity_id

_LOGGER = logging.getLogger(__name__)

PORT_1 = "P2" # 負責打開
PORT_2 = "P3" # 負責關閉
PORT_3 = "P4" # 負責停止
PORT_STATE = "P1" # 負責回報狀態 (通常 SL_P 的 P1 代表行程/開關狀態)
TYPE_ON = 0x81

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    _LOGGER.debug("Setting up LifeSmart cover platform")
    entry_data = hass.data[DOMAIN]["entries"][config_entry.entry_id]
    api = entry_data["api"]
    devices = entry_data.get("devices") or []
    if not devices:
        devices_data = await api.discover_devices()
        if isinstance(devices_data, dict) and isinstance(devices_data.get("msg"), list):
            devices = devices_data["msg"]
            entry_data["devices"] = devices
    
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
                        idx=device.get('idx', PORT_STATE)
                    )
                )
    
    _LOGGER.debug("Adding %s cover entities", len(covers))
    async_add_entities(covers)


class LifeSmartCover(CoverEntity):
    """Representation of a LifeSmart cover."""
    _attr_should_poll = False
    
    def __init__(self, api, device, idx: Optional[str] = None):
        self._api = api
        self._device = device
        self._attr_name = device.get('name', 'MINS Curtain')
        self._attr_unique_id = f"lls_cover_{device['me']}"
        self._attr_device_class = CoverDeviceClass.CURTAIN
        
        # 支援開、關、停功能
        self._attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        
        self._attr_is_closed = None
        self._idx = idx or PORT_STATE
        self._unsub_report = None
        
        device_type = device.get("devtype")
        hub_id = device.get("agt", "")
        device_id = device["me"]
        self.entity_id = f"cover.{generate_entity_id(device_type, hub_id, device_id, self._idx)}"

        _LOGGER.debug("Initializing cover: %s (ID: %s)", self._attr_name, self._attr_unique_id)
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device['me'])},
            name=self._attr_name,
            manufacturer=MANUFACTURER,
            model=device.get('devtype', 'SL_P'),
            sw_version=device.get('epver', 'Unknown')
        )

    async def async_added_to_hass(self):
        """實體加入 HA 時，註冊 UDP 推播監聽並獲取初始狀態"""
        # 註冊對 P1 (狀態通道) 的監聽
        self._unsub_report = self._api.register_state_listener(self._device["me"], self._idx, self._handle_state_value)
        await self._async_update_state()

    async def async_will_remove_from_hass(self):
        """實體移除時清理資源"""
        if self._unsub_report:
            self._unsub_report()
            self._unsub_report = None

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
        except Exception as ex:
            _LOGGER.error("Error updating cover state: %s", type(ex).__name__)

    def _handle_state_value(self, val: Any) -> None:
        """處理網關主動推播的 UDP 狀態"""
        self._update_internal_state(val)

    def _update_internal_state(self, val: Any) -> None:
        """更新 HA 內部狀態"""
        if not isinstance(val, (int, float)):
            return
        # 假設 val 為 0 代表全關，大於 0 代表有開啟 (依照一般 SL_P 行為，若不同可自行調整)
        self._attr_is_closed = (val == 0)
        
        if self.hass:
            self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        _LOGGER.debug("Opening cover: %s", self._attr_name)
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
        _LOGGER.debug("Closing cover: %s", self._attr_name)
        await self._api.send_command("ep", {
            "tag": "m",
            "me": self._device["me"],
            "idx": PORT_2,
            "type": TYPE_ON,
            "val": 0 # 若原代碼 val:0 可運作則保留，若無效請改為 1
        }, CMD_SET)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        _LOGGER.debug("Stopping cover: %s", self._attr_name)
        await self._api.send_command("ep", {
            "tag": "m",
            "me": self._device["me"],
            "idx": PORT_3,
            "type": TYPE_ON,
            "val": 0 # 若原代碼 val:0 可運作則保留，若無效請改為 1
        }, CMD_SET)
