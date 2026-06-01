"""Platform for LifeSmart scenes.

Discovers scenes via LI §3.3.5 (obj=scene GET) and exposes each as an HA Scene
entity. Triggering hits LI §3.3.6 (obj=doscene SET).

Scope: only `cls in ("scene", "groupirc")` is exposed — both are
parameter-free triggers (§5.2). Group switch / light scenes (`groupsw`,
`grouphw`, `grouprgbw`) carry on/off + color state, so they belong on the
`light` / `switch` platform rather than `scene`. Out of Phase 1 scope.
"""
import asyncio
import logging
import re
from typing import Any, Dict, List

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# cls values from LI §5.2 that map cleanly to HA Scene (pure triggers).
TRIGGER_ONLY_CLASSES = {"scene", "groupirc"}


def _slugify(value: str) -> str:
    """Reduce a scene name to ASCII slug for entity_id construction."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value or "").strip("_").lower()
    return slug or "scene"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Discover scenes on the hub and register them with HA."""
    entry_data = hass.data[DOMAIN]["entries"][config_entry.entry_id]
    api = entry_data["api"]

    try:
        response = await api.get_scene_list()
    except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError) as err:
        _LOGGER.warning("Failed to fetch scene list: %s", err)
        return

    if not isinstance(response, dict) or response.get("code") != 0:
        _LOGGER.debug("Scene list call returned non-zero code: %s", response)
        return

    raw_list = response.get("msg")
    if not isinstance(raw_list, list):
        _LOGGER.debug("Scene list msg is not a list: %s", raw_list)
        return

    scenes: List[Scene] = []
    skipped: List[str] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        scene_id = item.get("id")
        cls = item.get("cls")
        if not isinstance(scene_id, str) or not isinstance(cls, str):
            continue
        if cls not in TRIGGER_ONLY_CLASSES:
            skipped.append(f"{scene_id}(cls={cls})")
            continue
        scenes.append(LifeSmartScene(api=api, scene=item))

    if skipped:
        _LOGGER.info(
            "Skipped %d scenes with parameterised cls (out of Phase 1 scope): %s",
            len(skipped), skipped,
        )
    _LOGGER.debug("Adding %d LifeSmart scenes", len(scenes))
    async_add_entities(scenes)


class LifeSmartScene(Scene):
    """A single LifeSmart hub scene, identified by an AI... id.

    Scenes are NOT mounted on the hub DeviceInfo — HA's Scene platform
    convention is to not attach to a device (LI scenes don't really belong
    to a device anyway; they're hub-level orchestration).
    """

    def __init__(self, api: Any, scene: Dict[str, Any]) -> None:
        self._api = api
        self._scene_id: str = scene["id"]

        name = scene.get("name") or self._scene_id
        self._attr_name = name

        # unique_id uses the AI... id directly — globally unique within the hub.
        self._attr_unique_id = f"scene_{self._scene_id}"

        # entity_id: scene.lifesmart_<name_slug>_<id_tail>
        # The id_tail keeps entities distinct if two scenes share a name.
        id_tail = self._scene_id[-8:] if len(self._scene_id) > 8 else self._scene_id
        self.entity_id = f"scene.lifesmart_{_slugify(name)}_{id_tail.lower()}"

    async def async_activate(self, **kwargs: Any) -> None:
        """Fire the scene via cfg:doscene."""
        _LOGGER.debug("Activating LifeSmart scene %s (%s)", self._scene_id, self._attr_name)
        try:
            response = await self._api.trigger_scene(self._scene_id)
            if isinstance(response, dict) and response.get("code") != 0:
                _LOGGER.warning(
                    "Scene %s returned non-zero code: %s",
                    self._scene_id, response,
                )
        except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError) as err:
            _LOGGER.error("Failed to trigger scene %s: %s", self._scene_id, err)
