"""Platform for LifeSmart light groups (D9, R25).

Exposes the hub's `grouphw` / `grouprgbw` scenes (LI §5.2) as on / off
lights. See group_scene.py for what is left out and why.
"""
from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .group_scene import LIGHT_GROUP_CLASSES, LifeSmartGroupScene, group_scenes


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LifeSmart light groups."""
    entry_data = hass.data[DOMAIN]["entries"][config_entry.entry_id]
    hub_key = entry_data.get("hub_key") or entry_data.get("host", "")
    async_add_entities(
        LifeSmartGroupLight(
            api=entry_data["api"],
            scene=scene,
            platform="light",
            hub_key=hub_key,
            hub_info=entry_data.get("hub_info") or {},
            title=config_entry.title or "LifeSmart Hub",
        )
        for scene in group_scenes(entry_data, LIGHT_GROUP_CLASSES)
    )


class LifeSmartGroupLight(LifeSmartGroupScene, LightEntity):
    """A `grouphw` / `grouprgbw` scene: a group of bulbs, on or off."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
