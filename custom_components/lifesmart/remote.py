"""LifeSmart Remote Platform"""
import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional

from homeassistant.components import remote
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .availability import HubAvailability
from .coordinator import LifeSmartCoordinator
from .entity import LifeSmartDeviceEntity
from .models import LifeSmartConfigEntry

_LOGGER = logging.getLogger(__name__)

# No limit on parallel action calls (HA quality scale `parallel-updates`): each
# request is one UDP datagram matched to its reply by id, and the hub answers
# in about 10 ms. A limit of 1 would make "turn off 19 switches" wait for each
# switch's confirmation in turn.
PARALLEL_UPDATES = 0

SUPPORTED_REMOTE_TYPES = ["SL_P_IR"]

def _normalize_devtype(devtype: Any) -> str:
    if not isinstance(devtype, str):
        return ""
    return re.sub(r"\s+", "", devtype).upper()

def _parse_remotes(
    remote_list: Any, device_id: str,
) -> "tuple[Dict[str, Dict[str, Any]], Dict[str, str]]":
    """The remotes of one IR device, and key -> remote id, from what
    `get_remote_list` returns.

    R41: setup and the re-read use this one parser. Setup used to take every
    entry as it came, so a key list that was not a dict of keys was kept
    until the first re-read dropped it.
    """
    details: Dict[str, Dict[str, Any]] = {}
    all_keys: Dict[str, str] = {}
    if not isinstance(remote_list, list):
        return details, all_keys
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
        for key in keys:
            if isinstance(key, str):
                all_keys[key] = remote_id
    return details, all_keys


def _slugify(text: Any) -> str:
    base = (text or "").strip().lower()
    base = re.sub(r"[^a-z0-9]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    return base or "remote"

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LifeSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LifeSmart Remote devices."""
    _LOGGER.info("Setting up LifeSmart remotes")
    runtime = config_entry.runtime_data
    api = runtime.api
    # D22: hub device registry ID — sub-devices hang off it via via_device_id.
    hub_device_id = runtime.hub_device_id
    # R41: the device list is the one setup read. Platforms used to read it
    # again when it was empty (a hub with nothing paired); a failed read then
    # cost the hub sensors, or failed the whole switch / cover / remote
    # platform, and a successful one only sent five more requests.
    devices = runtime.devices
    
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
        # R30: lets lifesmart.send_keys route a remote_id to the hub that has it.
        runtime.remote_ids = {
            item["remote"]["id"]
            for item in remote_list
            if isinstance(item, dict) and isinstance(item.get("remote"), dict) and "id" in item["remote"]
        }
        
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
            agt = data['device'].get('agt', '')
            # R10-b (2026-05-24): include agt in entity_id so two hubs with
            # identically-named remotes (and identical me on system devices)
            # don't collide. The block below auto-renames legacy entity_ids
            # in the registry to the new agt-bearing form.
            base_slug = _slugify(data['device'].get('name') or 'remote')
            # R16: run the WHOLE object id through _slugify, not just the
            # name — `agt` can carry '-' (base64-ish) which HA rejects in
            # entity_ids from 2027.2. Without this the rename below would
            # fight _migrate_entity_ids every boot (it restores the bad id).
            desired_object_id = _slugify(f"{base_slug}_{agt}_{device_id}")
            desired_entity_id = f"remote.{desired_object_id}"
            unique_id = f"remote_{agt}_{device_id}"
            existing_entity_id = registry.async_get_entity_id("remote", DOMAIN, unique_id)
            if existing_entity_id and existing_entity_id != desired_entity_id and registry.async_get(desired_entity_id) is None:
                registry.async_update_entity(existing_entity_id, new_entity_id=desired_entity_id)

            remotes.append(
                LifeSmartRemote(
                    api=api,
                    device=data["device"],
                    remote_data_list=data["remotes"],
                    name=data["device"].get("name", "Remote"),
                    hub_device_id=hub_device_id,
                    coordinator=runtime.coordinator,
                    availability=runtime.availability,
                )
            )
    
    async_add_entities(remotes)

class LifeSmartRemote(LifeSmartDeviceEntity, remote.RemoteEntity):
    """LifeSmart Remote Entity."""
    # R18: HA 2026.5 naming. The remote IS the device, so the entity has no
    # name of its own and HA shows the device name. Before R18 `_attr_name`
    # (and a `name` property override) duplicated the device name.
    _attr_name = None

    def __init__(
        self,
        api,
        device: Dict[str, Any],
        remote_data_list: List[Dict[str, Any]],
        name: str,
        hub_device_id: Optional[str] = None,
        coordinator: Optional[LifeSmartCoordinator] = None,
        availability: Optional[HubAvailability] = None,
    ):
        """Initialize the remote.

        R32: lifecycle and availability are in entity.py. The coordinator is
        only the fallback for the device's `stat`.
        """
        # `name` is kept as the slug / log fallback only (R18) — see class note.
        self._device_name = device.get("name") or name or "Remote"
        super().__init__(
            api, device, None,
            hub_device_id=hub_device_id, coordinator=coordinator,
            availability=availability, device_name=self._device_name,
        )

        self._remote_data_list = remote_data_list
        device_id = device["me"]
        agt = device.get("agt", "")
        # Include agt (R10) — `me` collides across hubs on system devices.
        self._attr_unique_id = f"remote_{agt}_{device_id}"
        base = _slugify(device.get("name") or name or "remote")
        # R10-b: entity_id also needs agt for the same reason as unique_id.
        # R16: slugify the whole object id so a '-' in agt can't leak in.
        self.entity_id = f"remote.{_slugify(f'{base}_{agt}_{device_id}')}"

        self._refresh_lock = asyncio.Lock()
        self._last_refresh = 0.0
        self._remote_details, self._all_keys = _parse_remotes(remote_data_list, device_id)
        
      
        _LOGGER.debug("Initializing LifeSmart remote: %s", self._device_name)

    async def _async_refresh_data(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and self._remote_details and (now - self._last_refresh) < 60:
            return
        async with self._refresh_lock:
            now = time.monotonic()
            if not force and self._remote_details and (now - self._last_refresh) < 60:
                return
            remote_list = await self._api.get_remote_list()
            details, all_keys = _parse_remotes(remote_list, self._device["me"])
            if details:
                self._remote_details = details
                self._all_keys = all_keys
                self._last_refresh = time.monotonic()
                # R41: the attributes show the list; they used to keep the
                # one read at setup.
                self._async_write_if_added()

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return remote.RemoteEntityFeature.ACTIVITY

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
            except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError):
                return

        for cmd in command:
            if "::" in cmd:
                remote_id, key = cmd.split("::", 1)
                if remote_id not in self._remote_details:
                    await self._async_refresh_data(force=True)
                if remote_id in self._remote_details and key in self._remote_details[remote_id]["keys"]:
                    for _attempt in range(3):
                        try:
                            await self._api.send_remote_key(remote_id, key)
                            break
                        except asyncio.TimeoutError:
                            # Tried up to three times. R32: a failed send no longer
                            # makes the remote unavailable; that follows the hub
                            # (availability.py) and the device's `stat`.
                            continue
                        except (OSError, KeyError, ValueError, TypeError) as ex:
                            _LOGGER.error("Unexpected error sending command %s to remote %s: %s", key, remote_id, type(ex).__name__)
                            break
            else:
                if cmd not in self._all_keys:
                    await self._async_refresh_data(force=True)
                remote_id = self._all_keys.get(cmd)
                if remote_id:
                    for _attempt in range(3):
                        try:
                            await self._api.send_remote_key(remote_id, cmd)
                            break
                        except asyncio.TimeoutError:
                            # Tried up to three times. R32: a failed send no longer
                            # makes the remote unavailable; that follows the hub
                            # (availability.py) and the device's `stat`.
                            continue
                        except (OSError, KeyError, ValueError, TypeError) as ex:
                            _LOGGER.error("Error sending command %s to remote %s: %s", cmd, remote_id, type(ex).__name__)
                            break
