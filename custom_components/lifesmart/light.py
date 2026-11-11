"""Platform for LifeSmart light groups (D9, R25).

Exposes the hub's `grouphw` / `grouprgbw` scenes (LI §5.2) as on / off
lights. See group_scene.py for what is left out and why.
"""
from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .group_scene import LIGHT_GROUP_CLASSES, LifeSmartGroupScene, group_scenes
from .models import LifeSmartConfigEntry

# No limit on parallel action calls (HA quality scale `parallel-updates`): each
# request is one UDP datagram matched to its reply by id, and the hub answers
# in about 10 ms. A limit of 1 would make "turn off 19 switches" wait for each
# switch's confirmation in turn.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LifeSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LifeSmart light groups."""
    runtime = config_entry.runtime_data
    hub_key = runtime.hub_key
    async_add_entities(
        LifeSmartGroupLight(
            api=runtime.api,
            scene=scene,
            platform="light",
            hub_key=hub_key,
            hub_info=runtime.hub_info,
            title=config_entry.title or "LifeSmart Hub",
            availability=runtime.availability,
        )
        for scene in group_scenes(runtime.scenes, LIGHT_GROUP_CLASSES)
    )


class LifeSmartGroupLight(LifeSmartGroupScene, LightEntity):
    """A `grouphw` / `grouprgbw` scene: a group of bulbs, on or off."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
