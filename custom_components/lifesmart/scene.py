"""Platform for LifeSmart scenes.

Discovers scenes via LI §3.3.5 (obj=scene GET) and exposes each as an HA Scene
entity. Triggering hits LI §3.3.6 (obj=doscene SET).

Scope: only `cls in ("scene", "groupirc")` is exposed — both are
parameter-free triggers (§5.2). Group switch / light scenes (`groupsw`,
`grouphw`, `grouprgbw`) turn a group on or off, so R25 puts them on the
`switch` / `light` platforms (group_scene.py).

R25: the scene list is read once in __init__.py and shared by the three
platforms.
"""
import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .availability import HubAvailability
from .entity import LifeSmartEntity
from .models import LifeSmartConfigEntry

_LOGGER = logging.getLogger(__name__)

# No limit on parallel action calls (HA quality scale `parallel-updates`): each
# request is one UDP datagram matched to its reply by id, and the hub answers
# in about 10 ms. A limit of 1 would make "turn off 19 switches" wait for each
# switch's confirmation in turn.
PARALLEL_UPDATES = 0

# cls values from LI §5.2 that map cleanly to HA Scene (pure triggers).
TRIGGER_ONLY_CLASSES = {"scene", "groupirc"}


def _slugify(value: str) -> str:
    """Reduce a scene name to ASCII slug for entity_id construction."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value or "").strip("_").lower()
    return slug or "scene"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LifeSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Discover scenes on the hub and register them with HA."""
    runtime = config_entry.runtime_data
    api = runtime.api

    scenes: List[Scene] = [
        LifeSmartScene(api=api, scene=item, availability=runtime.availability)
        for item in runtime.scenes
        if item.get("cls") in TRIGGER_ONLY_CLASSES
    ]
    _LOGGER.debug("Adding %d LifeSmart scenes", len(scenes))
    async_add_entities(scenes)


class LifeSmartScene(LifeSmartEntity, Scene):
    """A single LifeSmart hub scene, identified by an AI... id.

    Scenes are NOT mounted on the hub DeviceInfo — HA's Scene platform
    convention is to not attach to a device (LI scenes don't really belong
    to a device anyway; they're hub-level orchestration).
    """

    # R32: `has_entity_name` comes from the base class (quality scale
    # `has-entity-name`). A scene has no device, so HA uses the name as it
    # is. The base also makes it unavailable while the hub is not answering.

    def __init__(
        self, api: Any, scene: Dict[str, Any],
        availability: Optional[HubAvailability] = None,
    ) -> None:
        super().__init__(availability)
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
