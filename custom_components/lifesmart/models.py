"""What a loaded config entry keeps while it runs.

HA quality scale `runtime-data`: this lives on `entry.runtime_data`, typed,
instead of in a dict under `hass.data[DOMAIN]`. Home Assistant drops it when
the entry unloads, so nothing here has to be removed by hand.

Every field is set in `async_setup_entry` before the platforms are forwarded,
except `remote_ids`, which remote.py fills in during its own setup.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Set

from homeassistant.config_entries import ConfigEntry

from .api import LifeSmartAPI
from .coordinator import LifeSmartCoordinator, LifeSmartHubCoordinator


@dataclass
class LifeSmartData:
    """One hub's runtime state."""

    api: LifeSmartAPI
    # Sub-devices from `eps` at setup (LI §3.3.2), as the hub sent them.
    devices: List[Dict[str, Any]]
    # cfg:getver / cfg:timezone, refreshed daily by `hub_coordinator`.
    hub_info: Dict[str, Any]
    host: str
    # Hub ID the hub device and hub-level unique ids are keyed on (R25).
    hub_key: str
    coordinator: LifeSmartCoordinator
    hub_coordinator: LifeSmartHubCoordinator
    # Device registry id of the hub device: sub-devices' `via_device_id`.
    hub_device_id: str
    # LI §3.3.5 scene list, read once at setup.
    scenes: List[Dict[str, Any]]
    # Called on unload, in order.
    unsubs: List[Callable[[], None]] = field(default_factory=list)
    # IR remotes this hub has; `send_keys` uses it to pick the hub (R30).
    remote_ids: Set[str] = field(default_factory=set)


type LifeSmartConfigEntry = ConfigEntry[LifeSmartData]
