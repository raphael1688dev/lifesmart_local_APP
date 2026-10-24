"""Shared DeviceInfo builders (R19, 2026-10-24).

HA 2026.11 turns `DeviceInfo` from a TypedDict into a dataclass
(contributors.home-assistant.io blog 2026-10-13 "DeviceInfo is now a
dataclass"). Item assignment (`info["sw_version"] = ...`) keeps working
through a compatibility layer that HA says it will deprecate and remove;
attribute assignment (`info.sw_version = ...`) is the replacement, but it
raises AttributeError on the dict-based DeviceInfo of HA <= 2026.10, which
this integration still supports. The one form both accept is passing every
field as a keyword argument at construction — so every platform builds its
kwargs here and never mutates the result.

Two device shapes exist in this integration:

* sub-device — one per LifeSmart `me`, identifiers `(DOMAIN, me)`, linked
  under the hub with `via_device_id` (D22 / R15). NOT the deprecated
  `via_device` tuple, and NOT a child device: HA's 2026-10-22 "Introducing
  child devices" post keeps `via_device_id` for "a hub and the devices it
  talks to", which is exactly what a LifeSmart station and its paired
  switches / curtains / remotes are.
* hub — the synthetic top-level device, identifiers `(DOMAIN, f"hub_{host}")`,
  fed by cfg:getver (LI §3.3.10). Built in three places (registry call in
  __init__.py, hub sensors, reboot button); they must agree, so they share
  `hub_device_info_kwargs`.
"""
from typing import Any, Dict, Mapping, Optional

from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, HUB_MODEL_NAMES, MANUFACTURER

DEFAULT_HUB_NAME = "LifeSmart Hub"
DEFAULT_HUB_MODEL = "LifeSmart Hub"


def sub_device_info_kwargs(
    device: Mapping[str, Any],
    hub_device_id: Optional[str] = None,
    *,
    name: Optional[str] = None,
    default_name: str = "LifeSmart Device",
    default_model: str = "Unknown",
) -> Dict[str, Any]:
    """Return the DeviceInfo fields for one LifeSmart sub-device.

    `device` is one entry of the `eps` response (LI §3.3.2 / §6.1); the
    fields used are `me`, `name`, `devtype`, `epver`. `me` is required and a
    missing one raises KeyError so the caller can log and skip the device.

    * `name`: explicit override (cover / remote compute their own), else the
      firmware name, else `default_name`.
    * `model`: `devtype`, else `default_model`.
    * `sw_version`: `str(epver)` when present. Omitted — not None, not
      "Unknown" — when missing, for the same reasons as the hub (R17 / R18):
      None would wipe a version stored on a previous boot, and HA rejects
      non-str values from 2026.12.0.
    * `via_device_id`: only when `hub_device_id` is truthy.
    """
    kwargs: Dict[str, Any] = {
        "identifiers": {(DOMAIN, device["me"])},
        "name": name if name is not None else (device.get("name") or default_name),
        "manufacturer": MANUFACTURER,
        "model": device.get("devtype") or default_model,
    }
    epver = device.get("epver")
    if epver is not None:
        kwargs["sw_version"] = str(epver)
    if hub_device_id:
        kwargs["via_device_id"] = hub_device_id
    return kwargs


def sub_device_info(
    device: Mapping[str, Any],
    hub_device_id: Optional[str] = None,
    *,
    name: Optional[str] = None,
    default_name: str = "LifeSmart Device",
    default_model: str = "Unknown",
) -> DeviceInfo:
    """Build the DeviceInfo for one sub-device. See sub_device_info_kwargs."""
    return DeviceInfo(
        **sub_device_info_kwargs(
            device,
            hub_device_id,
            name=name,
            default_name=default_name,
            default_model=default_model,
        )
    )


def hub_device_info_kwargs(
    host: str,
    title: Optional[str],
    hub_info: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return the DeviceInfo fields for the synthetic hub device.

    * identifiers use the host IP — stable across remove / re-add of the
      config entry, which `entry_id` is not (see CLAUDE.md hub template).
    * `name`: the config entry title, else DEFAULT_HUB_NAME.
    * `model`: friendly name from HUB_MODEL_NAMES (LI §3.3.10 L1561-1576),
      the raw mgatype if unknown, DEFAULT_HUB_MODEL if cfg:getver failed.
    * `sw_version`: only when `ver` is known (R17 — None would wipe the
      stored value every time cfg:getver fails), coerced to str (R18 — LI
      §3.3.10 L1557 gives no type for `ver`; HA rejects non-str from
      2026.12.0 via `_validate_str`).

    The device-registry call in __init__.py adds `config_entry_id` on top.
    """
    mgatype = hub_info.get("mgatype")
    kwargs: Dict[str, Any] = {
        "identifiers": {(DOMAIN, f"hub_{host}")},
        "name": title or DEFAULT_HUB_NAME,
        "manufacturer": MANUFACTURER,
        "model": (
            HUB_MODEL_NAMES.get(mgatype, mgatype)
            if isinstance(mgatype, str)
            else DEFAULT_HUB_MODEL
        ),
    }
    ver = hub_info.get("ver")
    if ver is not None:
        kwargs["sw_version"] = str(ver)
    return kwargs


def hub_device_info(
    host: str,
    title: Optional[str],
    hub_info: Mapping[str, Any],
) -> DeviceInfo:
    """Build the DeviceInfo for the hub device. See hub_device_info_kwargs."""
    return DeviceInfo(**hub_device_info_kwargs(host, title, hub_info))
