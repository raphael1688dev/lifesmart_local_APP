"""Platform for LifeSmart hub-level button entities.

Currently exposes a single Reboot button per integration entry, mapped to
`cfg:reboot` (LI §3.3.10). Hub-level, mounted on the synthetic hub device so
it groups under the same UI card as the firmware/OS/model sensors.
"""
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN
from .device_info import hub_device_info, hub_key_slug

_LOGGER = logging.getLogger(__name__)

# No limit on parallel action calls (HA quality scale `parallel-updates`): each
# request is one UDP datagram matched to its reply by id, and the hub answers
# in about 10 ms. A limit of 1 would make "turn off 19 switches" wait for each
# switch's confirmation in turn.
PARALLEL_UPDATES = 0

# D5 (R25): after a reboot the hub may have new firmware or devices, so the
# entry is reloaded. Two minutes covers a normal restart; if the hub is still
# down, setup raises ConfigEntryNotReady and HA retries on its own.
REBOOT_RELOAD_DELAY_SECONDS = 120


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LifeSmart hub-level buttons."""
    entry_data = hass.data[DOMAIN]["entries"][config_entry.entry_id]
    api = entry_data["api"]
    hub_key = entry_data.get("hub_key") or entry_data.get("host", "")
    hub_info = entry_data.get("hub_info") or {}
    title = config_entry.title or "LifeSmart Hub"

    buttons: List[ButtonEntity] = [
        LifeSmartHubRebootButton(
            api=api, hub_key=hub_key, hub_info=hub_info, title=title,
            entry_id=config_entry.entry_id,
        ),
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
    _attr_has_entity_name = True  # R18: "Reboot" + hub device name

    def __init__(
        self,
        api: Any,
        hub_key: str,
        hub_info: Dict[str, Any],
        title: str,
        entry_id: str,
    ) -> None:
        self._api = api
        self._entry_id = entry_id
        self._cancel_reload: Optional[Callable[[], None]] = None

        self._attr_name = "Reboot"
        # D21 (R25): hub ID, or the host for older entries (same slug as before).
        self._attr_unique_id = f"hub_reboot_{hub_key_slug(hub_key)}"
        # Hand-written entity_id per CLAUDE.md "Hub-level entity 組織慣例".
        self.entity_id = "button.lifesmart_hub_reboot"

        # R19: same kwargs as __init__.py's registry call and sensor.py, built
        # by device_info.py (R17 omit-unknown sw_version and R18 str() live
        # there) — no item assignment, DeviceInfo is a dataclass from 2026.11.
        self._attr_device_info = hub_device_info(hub_key, title, hub_info)

    async def async_will_remove_from_hass(self) -> None:
        # An unload before the timer fires must not reload the entry again.
        if self._cancel_reload is not None:
            self._cancel_reload()
            self._cancel_reload = None

    @callback
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Opt in to in-place entity_id renames (HA 2026.11+, R19).

        The reload timer is not keyed on the entity_id; nothing to re-key.
        """
        super().async_entity_id_changed(old_entity_id)

    async def async_press(self) -> None:
        """Send cfg:reboot. Hub will ack then restart immediately."""
        _LOGGER.info("Sending cfg:reboot to LifeSmart hub")
        try:
            response = await self._api.reboot_hub()
            if isinstance(response, dict) and response.get("code") == 0:
                _LOGGER.info("Hub acknowledged reboot — connection will drop shortly")
            else:
                _LOGGER.warning("Unexpected response from cfg:reboot: %s", response)
                return
        except (asyncio.TimeoutError, OSError, KeyError, ValueError) as err:
            # Hub may stop responding mid-flight; treat that as success-ish.
            _LOGGER.info("cfg:reboot did not return cleanly (likely already restarting): %s", err)
        self._schedule_reload()

    @callback
    def _schedule_reload(self) -> None:
        if self._cancel_reload is not None:
            self._cancel_reload()
        self._cancel_reload = async_call_later(
            self.hass, REBOOT_RELOAD_DELAY_SECONDS, self._reload
        )

    @callback
    def _reload(self, _now: Any) -> None:
        self._cancel_reload = None
        _LOGGER.info("Reloading LifeSmart after the hub reboot")
        self.hass.config_entries.async_schedule_reload(self._entry_id)
