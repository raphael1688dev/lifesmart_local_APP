"""DataUpdateCoordinator for LifeSmart Local.

Replaces per-entity `async_track_time_interval` polling with a single
shared coordinator that fetches the full device list (`eps`, LI §3.3.2)
once per cycle and broadcasts the result to all subscribed entities.

This satisfies the HA 2026.5 規範 (DataUpdateCoordinator requirement, see
CLAUDE.md). For a hub with N devices the request count drops from N to 1
per poll cycle.

Push (NOTIFY) updates are ORTHOGONAL to this coordinator: state listeners
registered via `api.register_state_listener(me, idx, cb)` continue to fire
immediately on incoming events. The coordinator's role is to keep a
warm cache and act as a fallback when push drops a message.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, Optional, TYPE_CHECKING, override

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import REJECTED_TOKEN, LifeSmartAPI, rejection

if TYPE_CHECKING:
    # models.py imports this module for the dataclass fields.
    from .models import LifeSmartConfigEntry

_LOGGER = logging.getLogger(__name__)

# 15 min matches the previous per-entity interval. For a stat-driven
# CONNECTIVITY sensor we may want shorter, but push handles that case.
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=15)


class LifeSmartCoordinator(DataUpdateCoordinator[Dict[str, Dict[str, Any]]]):
    """Per-hub coordinator. Data shape: {me: device_dict} after each refresh."""

    def __init__(
        self, hass: HomeAssistant, entry: LifeSmartConfigEntry, api: LifeSmartAPI, host: str
    ) -> None:
        # R30: the config entry is passed explicitly. Without it the
        # coordinator falls back to a ContextVar, which HA reports as an
        # error for core integrations and only tolerates for custom ones.
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"lifesmart_{host}",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self._api = api

    @override
    async def _async_update_data(self) -> Dict[str, Dict[str, Any]]:
        """Fetch fresh `eps` snapshot."""
        try:
            response = await self._api.discover_devices()
        except (asyncio.TimeoutError, OSError) as err:
            raise UpdateFailed(f"Hub unreachable: {err}") from err

        if not isinstance(response, dict):
            raise UpdateFailed(f"Unexpected discovery response shape: {type(response).__name__}")

        if rejection(response) == REJECTED_TOKEN:
            # R34: Home Assistant opens the reauth form for this.
            raise ConfigEntryAuthFailed("The hub rejected the token (code 101)")
        if response.get("code") != 0:
            raise UpdateFailed(f"Hub returned non-zero code: {response.get('code')}")

        msg = response.get("msg")
        if isinstance(msg, list):
            iterable = msg
        elif isinstance(msg, dict):
            iterable = [d for d in msg.values() if isinstance(d, dict)]
        else:
            raise UpdateFailed(f"Unexpected msg shape in discovery: {type(msg).__name__}")

        out: Dict[str, Dict[str, Any]] = {}
        for d in iterable:
            if not isinstance(d, dict):
                continue
            me = d.get("me")
            if isinstance(me, str):
                out[me] = d
        return out


# D4 (R25): the hub's own identity (cfg:getver) and time zone (cfg:timezone)
# were read once at setup, so a firmware upgrade only showed after a reload.
# Neither changes often; once a day is plenty.
HUB_INFO_UPDATE_INTERVAL = timedelta(hours=24)


def parse_hub_version(response: Any) -> Optional[Dict[str, Any]]:
    """`ver` / `osver` / `mgatype` from a cfg:getver reply (LI §3.3.10), or
    None when the hub answered with an error or an unexpected shape."""
    if (
        isinstance(response, dict)
        and response.get("code") == 0
        and isinstance(response.get("msg"), dict)
    ):
        msg = response["msg"]
        return {"ver": msg.get("ver"), "osver": msg.get("osver"), "mgatype": msg.get("mgatype")}
    return None


def parse_timezone(response: Any) -> Optional[Dict[str, Any]]:
    """`timezone` ([-12, 12]) and `summer` (DST) from a cfg:timezone reply
    (LI §3.3.10, OD §2.3.1), or None. `summer` is None when not a bool."""
    if not (
        isinstance(response, dict)
        and response.get("code") == 0
        and isinstance(response.get("msg"), dict)
    ):
        return None
    tz = response["msg"].get("timezone")
    summer = response["msg"].get("summer")
    if isinstance(tz, bool) or not isinstance(tz, int) or not -12 <= tz <= 12:
        return None
    return {"timezone": tz, "summer": summer if isinstance(summer, bool) else None}


class LifeSmartHubCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Per-hub cfg:getver + cfg:timezone, refreshed daily.

    Data: `ver`, `osver`, `mgatype`, `timezone`, `summer` and `version_ok`
    (False when the last cfg:getver failed; a warning is logged below. R36:
    no repair issue any more, the user could not act on it). A failed read keeps the
    previous values instead of raising UpdateFailed: the hub sensors would
    rather show the last known firmware than go blank.
    """

    def __init__(
        self, hass: HomeAssistant, entry: LifeSmartConfigEntry, api: LifeSmartAPI, host: str
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,  # R30: explicit, see LifeSmartCoordinator
            name=f"lifesmart_hub_{host}",
            update_interval=HUB_INFO_UPDATE_INTERVAL,
        )
        self._api = api

    async def async_fetch(self, include_timezone: bool = True) -> Dict[str, Any]:
        """Read cfg:getver (and cfg:timezone); merge into the previous data.

        Setup passes include_timezone=False and reads the time zone through
        async_load_timezone afterwards (R28).
        """
        info: Dict[str, Any] = dict(self.data or {})
        version: Optional[Dict[str, Any]] = None
        try:
            reply = await self._api.get_hub_version()
            version = parse_hub_version(reply)
            if version is None:
                _LOGGER.warning("cfg:getver returned non-zero or unexpected shape: %s", reply)
        except (asyncio.TimeoutError, OSError, KeyError, ValueError) as err:
            _LOGGER.warning("Failed to query hub version (cfg:getver): %s", err)
        if version is not None:
            info.update(version)
        info["version_ok"] = version is not None
        if include_timezone:
            info.update(await self._async_read_timezone())
        return info

    async def _async_read_timezone(self) -> Dict[str, Any]:
        """`timezone` / `summer` from the hub, or {} when it cannot be read."""
        try:
            timezone = parse_timezone(await self._api.get_hub_timezone())
        except (asyncio.TimeoutError, OSError, KeyError, ValueError) as err:
            _LOGGER.debug("Failed to query hub time zone (cfg:timezone): %s", err)
            return {}
        return timezone or {}

    async def async_load_timezone(self) -> None:
        """Read the time zone once, outside setup, and tell the listeners."""
        timezone = await self._async_read_timezone()
        if timezone:
            self.async_set_updated_data({**(self.data or {}), **timezone})

    @override
    async def _async_update_data(self) -> Dict[str, Any]:
        return await self.async_fetch()
