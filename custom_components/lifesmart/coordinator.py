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
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LifeSmartAPI

_LOGGER = logging.getLogger(__name__)

# 15 min matches the previous per-entity interval. For a stat-driven
# CONNECTIVITY sensor we may want shorter, but push handles that case.
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=15)


class LifeSmartCoordinator(DataUpdateCoordinator[Dict[str, Dict[str, Any]]]):
    """Per-hub coordinator. Data shape: {me: device_dict} after each refresh."""

    def __init__(self, hass: HomeAssistant, api: LifeSmartAPI, host: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"lifesmart_{host}",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self._api = api

    async def _async_update_data(self) -> Dict[str, Dict[str, Any]]:
        """Fetch fresh `eps` snapshot."""
        try:
            response = await self._api.discover_devices()
        except (asyncio.TimeoutError, OSError) as err:
            raise UpdateFailed(f"Hub unreachable: {err}") from err

        if not isinstance(response, dict):
            raise UpdateFailed(f"Unexpected discovery response shape: {type(response).__name__}")

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
