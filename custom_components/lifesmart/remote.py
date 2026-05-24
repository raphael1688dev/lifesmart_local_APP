"""LifeSmart Remote Platform"""
import asyncio
import logging
import re
import time
from typing import Any, Dict, List

from homeassistant.components import remote
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

SUPPORTED_REMOTE_TYPES = ["SL_P_IR"]

def _normalize_devtype(devtype: Any) -> str:
    if not isinstance(devtype, str):
        return ""
    return re.sub(r"\s+", "", devtype).upper()

def _slugify(text: Any) -> str:
    base = (text or "").strip().lower()
    base = re.sub(r"[^a-z0-9]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    return base or "remote"

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LifeSmart Remote devices."""
    _LOGGER.info("Setting up LifeSmart remotes")
    entry_data = hass.data[DOMAIN]["entries"][config_entry.entry_id]
    api = entry_data["api"]
    devices = entry_data.get("devices") or []
    if not devices:
        devices_data = await api.discover_devices()
        if isinstance(devices_data, dict) and isinstance(devices_data.get("msg"), list):
            devices = devices_data["msg"]
            entry_data["devices"] = devices
    
    remotes: List[LifeSmartRemote] = []
    
    if isinstance(devices, list):
        # 優化點：先檢查設備清單中，是否真的存在支援的 IR 設備
        has_ir_device = any(_normalize_devtype(d.get("devtype")) in SUPPORTED_REMOTE_TYPES for d in devices)
        
        remote_list = []
        if has_ir_device:
            # 只有真的有 IR 設備，才去呼叫 API
            remote_list = await api.get_remote_list()
            if not isinstance(remote_list, list):
                _LOGGER.warning("Failed to load remote list from hub")
                remote_list = []
        
        device_remotes = {}
        
        for device in devices:
            devtype = _normalize_devtype(device.get("devtype"))
            if devtype in SUPPORTED_REMOTE_TYPES:
                device_id = device["me"]
                if device_id not in device_remotes:
                    device_remotes[device_id] = {
                        "device": device,
                        "remotes": []
                    }
                
                for remote_data in remote_list:
                    if device_id in remote_data["remote"]["id"]:
                        device_remotes[device_id]["remotes"].append(remote_data)
        
        registry = er.async_get(hass)

        for device_id, data in device_remotes.items():
            desired_object_id = f"{_slugify(data['device'].get('name') or 'remote')}_{device_id}".lower()
            desired_entity_id = f"remote.{desired_object_id}"
            agt = data['device'].get('agt', '')
            unique_id = f"remote_{agt}_{device_id}"
            existing_entity_id = registry.async_get_entity_id("remote", DOMAIN, unique_id)
            if existing_entity_id and existing_entity_id != desired_entity_id and registry.async_get(desired_entity_id) is None:
                registry.async_update_entity(existing_entity_id, new_entity_id=desired_entity_id)

            remotes.append(
                LifeSmartRemote(
                    api=api,
                    device=data["device"],
                    remote_data_list=data["remotes"],
                    name=data["device"].get("name", "Remote")
                )
            )
    
    async_add_entities(remotes)

class LifeSmartRemote(remote.RemoteEntity):
    """LifeSmart Remote Entity."""
    _attr_should_poll = False

    def __init__(self, api, device: Dict[str, Any], remote_data_list: List[Dict[str, Any]], name: str):
        """Initialize the remote."""
        self._api = api
        self._device = device

        self._remote_data_list = remote_data_list
        self._attr_name = name
        device_id = device["me"]
        agt = device.get("agt", "")
        # Include agt (R10) — `me` collides across hubs on system devices.
        self._attr_unique_id = f"remote_{agt}_{device_id}"
        base = _slugify(device.get("name") or name or "remote")
        self.entity_id = f"remote.{base}_{device_id}"
        self._available = True


        self._all_keys = {}
        self._remote_details = {}
        self._refresh_lock = asyncio.Lock()
        self._last_refresh = 0.0
        self._failures = 0

        for remote_data in remote_data_list:
            remote_id = remote_data["remote"]["id"]
            self._remote_details[remote_id] = {
                "name": remote_data["remote"].get("name", ""),
                "category": remote_data["remote"].get("category", ""),
                "brand": remote_data["remote"].get("brand", ""),
                "keys": remote_data["keys"]
            }
            self._all_keys.update({key: remote_id for key in remote_data["keys"]})
        
      
        _LOGGER.debug("Initializing LifeSmart remote: %s", self._attr_name)

    async def _async_refresh_data(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and self._remote_details and (now - self._last_refresh) < 60:
            return
        async with self._refresh_lock:
            now = time.monotonic()
            if not force and self._remote_details and (now - self._last_refresh) < 60:
                return
            remote_list = await self._api.get_remote_list()
            if not isinstance(remote_list, list):
                return

            device_id = self._device["me"]
            details = {}
            all_keys = {}
            for remote_data in remote_list:
                remote_info = remote_data.get("remote") if isinstance(remote_data, dict) else None
                keys = remote_data.get("keys") if isinstance(remote_data, dict) else None
                if not isinstance(remote_info, dict) or not isinstance(keys, dict):
                    continue
                remote_id = remote_info.get("id")
                if not isinstance(remote_id, str) or device_id not in remote_id:
                    continue
                details[remote_id] = {
                    "name": remote_info.get("name", ""),
                    "category": remote_info.get("category", ""),
                    "brand": remote_info.get("brand", ""),
                    "keys": keys,
                }
                for k in keys:
                    if isinstance(k, str):
                        all_keys[k] = remote_id

            if details:
                self._remote_details = details
                self._all_keys = all_keys
                self._last_refresh = time.monotonic()

    @property
    def name(self) -> str:
        """Return the name of the remote."""
        return self._attr_name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return remote.RemoteEntityFeature.ACTIVITY

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device["me"])},
            name=self._device.get("name", "LifeSmart Remote"),
            manufacturer=MANUFACTURER,
            model=self._device.get("devtype"),
            sw_version=self._device.get("epver"),
        )

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attributes = {
            "agt": self._device.get("agt"),
            "me": self._device.get("me"),
            "devtype": self._device.get("devtype"),
            "remotes": self._remote_details,
            "all_commands": list(self._all_keys.keys())
        }

        return attributes

    async def async_send_command(self, command: List[str], **kwargs: Any) -> None:
        """Send commands remote_id to a device."""      
        if not self._remote_details:
            try:
                await self._async_refresh_data(force=True)
            except Exception:
                return

        for cmd in command:
            if "::" in cmd:
                remote_id, key = cmd.split("::", 1)
                if remote_id not in self._remote_details:
                    await self._async_refresh_data(force=True)
                if remote_id in self._remote_details and key in self._remote_details[remote_id]["keys"]:
                    for attempt in range(3):
                        try:
                            await self._api.send_remote_key(remote_id, key)
                            self._available = True
                            self._failures = 0
                            break
                        except asyncio.TimeoutError:
                            self._failures += 1
                            if self._failures >= 3:
                                self._available = False
                            if attempt == 2:
                                break
                        except Exception as ex:
                            _LOGGER.error("Unexpected error sending command %s to remote %s: %s", key, remote_id, type(ex).__name__)
                            break
            else:
                if cmd not in self._all_keys:
                    await self._async_refresh_data(force=True)
                remote_id = self._all_keys.get(cmd)
                if remote_id:
                    for attempt in range(3):
                        try:
                            await self._api.send_remote_key(remote_id, cmd)
                            self._available = True
                            self._failures = 0
                            break
                        except asyncio.TimeoutError:
                            self._failures += 1
                            if self._failures >= 3:
                                self._available = False
                            if attempt == 2:
                                break
                        except Exception as ex:
                            _LOGGER.error("Error sending command %s to remote %s: %s", cmd, remote_id, type(ex).__name__)
                            break
