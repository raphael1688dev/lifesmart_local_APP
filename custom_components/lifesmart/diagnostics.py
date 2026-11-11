"""Diagnostics support for LifeSmart Local.

Exposes both config-entry-level and device-level diagnostics so users can
"Download diagnostics" from the UI and paste the result into bug reports
without us asking them to grep their HA log.

Sensitive fields (token, sign, possibly `agt` since it identifies the hub)
are redacted via Home Assistant's async_redact_data helper.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .models import LifeSmartConfigEntry, LifeSmartData

# Keys whose values get replaced with "**REDACTED**" before returning.
# `agt` and `lsid` are arguably PII (uniquely identify the hub),
# but they appear EVERYWHERE in device dicts — redaction would obliterate
# most of the diagnostic value. Compromise: redact only the token-like
# fields at the entry level, keep `agt` visible in device payloads.
TO_REDACT = {"token", "sign", "password", "C_WPAPSK", "C_password"}


def _runtime(entry: LifeSmartConfigEntry) -> LifeSmartData | None:
    """The entry's runtime data, or None while it is not loaded.

    Diagnostics can be downloaded for an entry that failed to set up; it has
    no `runtime_data` then, and the download should still work.
    """
    return getattr(entry, "runtime_data", None)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LifeSmartConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = _runtime(entry)

    devices = runtime.devices if runtime else []
    hub_info = runtime.hub_info if runtime else {}
    host = runtime.host if runtime else ""

    # Count devices by devtype so reviewers can spot weird/undocumented types
    # (like the V_SI case from 2026-05-23) without scanning every entry.
    devtype_counts: dict[str, int] = {}
    for dev in devices:
        if isinstance(dev, dict):
            dt = dev.get("devtype", "unknown")
            devtype_counts[dt] = devtype_counts.get(dt, 0) + 1

    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "host": host,
        "hub_info": hub_info,
        "devtype_counts": devtype_counts,
        "device_count": len(devices),
        "devices": async_redact_data(devices, TO_REDACT),
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: LifeSmartConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a single device.

    Identifiers come from DeviceInfo — for sub-devices `(DOMAIN, me)`, for
    the synthetic hub device `(DOMAIN, f"hub_{hub_key}")` (hub ID, or the host
    for entries older than R25). We try both shapes.
    """
    runtime = _runtime(entry)
    devices = runtime.devices if runtime else []

    # Try to find a matching sub-device by `me`.
    target_me: str | None = None
    for ident in device.identifiers:
        if isinstance(ident, tuple) and len(ident) == 2 and ident[0] == DOMAIN:
            value = ident[1]
            if isinstance(value, str):
                if value.startswith("hub_"):
                    # Hub-level device — return hub_info.
                    return {
                        "device_type": "hub",
                        "host": runtime.host if runtime else "",
                        "hub_info": runtime.hub_info if runtime else {},
                        "device_count": len(devices),
                    }
                target_me = value
                break

    if target_me is None:
        return {"error": "Could not parse device identifier"}

    matched = None
    for dev in devices:
        if isinstance(dev, dict) and dev.get("me") == target_me:
            matched = dev
            break

    if matched is None:
        return {
            "error": f"No device with me={target_me} in current discovery",
            "device_identifier": target_me,
        }

    return {
        "device_type": "sub_device",
        "payload": async_redact_data(matched, TO_REDACT),
    }
