"""Finding hubs on the LAN (LI §2, quality scale `discovery`, R43).

LI §2: a broadcast `Z-SEARCH * \\r\\n` to UDP port 12345 is answered by every
hub with `LSID=…\\nMGAMOD=…\\nWLAN=…\\nNAME=…\\n`, `LSID` being the hub's
unique id.

Measured on the user's two hubs (Smart Station `LSJZX1K` and DEFED
`LSDEFED`, firmware 1.0.94p10), 2026-11-13, twice:
* both answer, from port 12345, to the port the search came from, so any
  local port will do;
* each answers a search twice, so replies are de-duplicated by `LSID`;
* `LSID` equals the `agt` the hub's sub-devices report, the id this
  integration already keys the hub device on (R25);
* the replies also carry `VER` and `MGAFWVER`, which the spec does not list.

Found hubs are handed to Home Assistant as integration discovery flows: a
new one shows as "Discovered", a configured one whose address changed is
updated (config_flow.async_step_integration_discovery).
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import timedelta
import logging
from typing import Any, override

from homeassistant.components import network
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DISCOVERY_PORT = 12345
SEARCH = b"Z-SEARCH * \r\n"
# Both hubs answered within a fraction of a second when measured.
SCAN_SECONDS = 3.0
DISCOVERY_INTERVAL = timedelta(minutes=15)


@dataclass(frozen=True)
class DiscoveredHub:
    """One hub that answered a search."""

    host: str
    hub_id: str          # LSID
    model: str = ""      # MGAMOD, e.g. LSJZX1K
    name: str = ""       # NAME, as set in the LifeSmart app
    version: str = ""    # VER (not in the spec)

    def as_flow_data(self) -> dict[str, str]:
        return asdict(self)


def parse_reply(data: bytes, host: str) -> DiscoveredHub | None:
    """A hub from its answer to `Z-SEARCH`, or None for anything else
    (including the search itself, which comes back to us too)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    fields: dict[str, str] = {}
    for line in text.replace("\r", "").split("\n"):
        key, sep, value = line.partition("=")
        if sep:
            fields[key.strip()] = value.strip()
    hub_id = fields.get("LSID")
    if not hub_id:
        return None
    return DiscoveredHub(
        host=host,
        hub_id=hub_id,
        model=fields.get("MGAMOD", ""),
        name=fields.get("NAME", ""),
        version=fields.get("VER", ""),
    )


class _SearchProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.hubs: dict[str, DiscoveredHub] = {}

    @override
    def datagram_received(self, data: bytes, addr: tuple[str | Any, int]) -> None:
        hub = parse_reply(data, str(addr[0]))
        if hub is not None:
            self.hubs.setdefault(hub.hub_id, hub)

    @override
    def error_received(self, exc: Exception) -> None:
        _LOGGER.debug("Hub search: %s", exc)


async def async_discover_hubs(
    hass: HomeAssistant, timeout: float = SCAN_SECONDS
) -> list[DiscoveredHub]:
    """Broadcast a search on every network Home Assistant uses; collect the
    answers for `timeout` seconds."""
    targets = sorted(str(a) for a in await network.async_get_ipv4_broadcast_addresses(hass))
    protocol = _SearchProtocol()
    try:
        transport, _ = await hass.loop.create_datagram_endpoint(
            lambda: protocol, local_addr=("0.0.0.0", 0), allow_broadcast=True,
        )
    except OSError as err:
        _LOGGER.debug("Could not open a socket to search for hubs: %s", err)
        return []
    try:
        for target in targets:
            try:
                transport.sendto(SEARCH, (target, DISCOVERY_PORT))
            except OSError as err:
                _LOGGER.debug("Could not search %s for hubs: %s", target, err)
        await asyncio.sleep(timeout)
    finally:
        transport.close()
    return list(protocol.hubs.values())


@callback
def async_trigger_discovery(hass: HomeAssistant, hubs: list[DiscoveredHub]) -> None:
    for hub in hubs:
        discovery_flow.async_create_flow(
            hass, DOMAIN,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data=hub.as_flow_data(),
        )


@callback
def async_start_discovery(hass: HomeAssistant) -> None:
    """Search now, and every 15 minutes while Home Assistant runs (the
    pattern of Home Assistant's own Flux LED integration)."""

    async def _search() -> None:
        async_trigger_discovery(hass, await async_discover_hubs(hass))

    @callback
    def _start(*_: Any) -> None:
        hass.async_create_background_task(_search(), f"{DOMAIN} hub search", eager_start=True)

    _start()
    async_track_time_interval(hass, _start, DISCOVERY_INTERVAL, cancel_on_shutdown=True)
