"""Group scenes as switches and lights (D9, R25).

LI §5.2 gives three scene classes that turn a group on or off rather than run
once: `groupsw` (a group of switches / bulbs), `grouphw` (a group of bulbs
driven by broadcast, faster) and `grouprgbw` (a light group). Each takes
`args.type` 0x81 (on) or 0x80 (off) on `doscene` (LI §3.3.6). switch.py
exposes `groupsw`, light.py the other two.

What is left out on purpose:
* State. The hub reports no on/off for a scene, so these entities are
  `assumed_state` and show the last command sent from Home Assistant.
* Colour. 0xff / 0xfe set an RGBW colour too, but §5.2 does not say which
  argument carries the 4-byte WRGB value — unverified, so on / off only.

They hang off the hub device: a group scene belongs to the hub, not to a
sub-device.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo

from .api import SCENE_TYPE_OFF, SCENE_TYPE_ON
from .device_info import hub_device_info
from .scene import _slugify

_LOGGER = logging.getLogger(__name__)

SWITCH_GROUP_CLASSES = {"groupsw"}
LIGHT_GROUP_CLASSES = {"grouphw", "grouprgbw"}


def group_scenes(entry_data: Dict[str, Any], classes: set[str]) -> List[Dict[str, Any]]:
    """The hub scenes (read once in __init__.py) whose `cls` is in `classes`."""
    return [s for s in entry_data.get("scenes") or [] if s.get("cls") in classes]


class LifeSmartGroupScene:
    """On / off through `doscene`; mixed in before SwitchEntity / LightEntity."""

    _attr_assumed_state = True
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_is_on: Optional[bool]
    _attr_device_info: DeviceInfo

    def __init__(
        self,
        api: Any,
        scene: Dict[str, Any],
        platform: str,
        hub_key: str,
        hub_info: Dict[str, Any],
        title: str,
    ) -> None:
        self._api = api
        self._scene_id: str = scene["id"]
        name = scene.get("name") or self._scene_id
        self._attr_name = name
        self._attr_is_on = None
        # Scene ids are unique within the hub; `scene_<id>` is the scene
        # platform's, so these get their own prefix.
        self._attr_unique_id = f"scene_group_{self._scene_id}"
        id_tail = self._scene_id[-8:] if len(self._scene_id) > 8 else self._scene_id
        self.entity_id = f"{platform}.lifesmart_{_slugify(name)}_{id_tail.lower()}"
        self._attr_device_info = hub_device_info(hub_key, title, hub_info)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_send(SCENE_TYPE_ON, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_send(SCENE_TYPE_OFF, False)

    async def _async_send(self, scene_type: int, is_on: bool) -> None:
        try:
            reply = await self._api.trigger_scene(self._scene_id, scene_type)
        except (asyncio.TimeoutError, OSError) as err:
            raise HomeAssistantError(f"No reply from the hub for scene {self._scene_id}") from err
        if not isinstance(reply, dict) or reply.get("code") != 0:
            raise HomeAssistantError(f"The hub rejected scene {self._scene_id}: {reply}")
        self._attr_is_on = is_on
        self.async_write_ha_state()  # type: ignore[attr-defined]
