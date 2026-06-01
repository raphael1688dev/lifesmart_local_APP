"""Platform for LifeSmart hub-level button entities.

Currently exposes a single Reboot button per integration entry, mapped to
`cfg:reboot` (LI §3.3.10). Hub-level, mounted on the synthetic hub device so
it groups under the same UI card as the firmware/OS/model sensors.
"""
import asyncio
import logging
from typing import Any, Dict, List

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HUB_MODEL_NAMES, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LifeSmart hub-level buttons."""
    entry_data = hass.data[DOMAIN]["entries"][config_entry.entry_id]
    api = entry_data["api"]
    host = entry_data.get("host", "")
    hub_info = entry_data.get("hub_info") or {}
    title = config_entry.title or "LifeSmart Hub"

    buttons: List[ButtonEntity] = [
        LifeSmartHubRebootButton(api=api, host=host, hub_info=hub_info, title=title),
    ]
    async_add_entities(buttons)


class LifeSmartHubRebootButton(ButtonEntity):
    """Restart the hub via LI §3.3.10 cfg:reboot.

    The hub ACKs the command and then restarts immediately — no spec-level
    confirmation. HA's default RESTART device_class shows a confirmation
    prompt in the UI, which is the only safeguard.
    """

    _attr_should_poll = False
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        api: Any,
        host: str,
        hub_info: Dict[str, Any],
        title: str,
    ) -> None:
        self._api = api

        host_slug = host.replace(".", "_")
        self._attr_name = "Reboot"
        self._attr_unique_id = f"hub_reboot_{host_slug}"
        # Hand-written entity_id per CLAUDE.md "Hub-level entity 組織慣例".
        self.entity_id = "button.lifesmart_hub_reboot"

        hub_identifier = f"hub_{host}"
        mgatype = hub_info.get("mgatype")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub_identifier)},
            name=title,
            manufacturer=MANUFACTURER,
            model=HUB_MODEL_NAMES.get(mgatype, mgatype) if isinstance(mgatype, str) else "LifeSmart Hub",
            sw_version=hub_info.get("ver"),
        )

    async def async_press(self) -> None:
        """Send cfg:reboot. Hub will ack then restart immediately."""
        _LOGGER.info("Sending cfg:reboot to LifeSmart hub")
        try:
            response = await self._api.reboot_hub()
            if isinstance(response, dict) and response.get("code") == 0:
                _LOGGER.info("Hub acknowledged reboot — connection will drop shortly")
            else:
                _LOGGER.warning("Unexpected response from cfg:reboot: %s", response)
        except (asyncio.TimeoutError, OSError, KeyError, ValueError) as err:
            # Hub may stop responding mid-flight; treat that as success-ish.
            _LOGGER.info("cfg:reboot did not return cleanly (likely already restarting): %s", err)
