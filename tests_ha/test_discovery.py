"""Finding hubs on the LAN and identifying entries by hub id (R43).

The replies below are the bytes the user's two hubs sent on 2026-11-13
(Smart Station `LSJZX1K` and DEFED `LSDEFED`, firmware 1.0.94p10).
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from custom_components.lifesmart import diagnostics, discovery
from custom_components.lifesmart.const import DOMAIN
from custom_components.lifesmart.discovery import DiscoveredHub, parse_reply
# Bound now: the autouse `lan_search` fixture replaces the module attribute.
from custom_components.lifesmart.discovery import async_discover_hubs as real_discover_hubs

from . import hub as sim_hub
from .conftest import HOST, HUB_ID, MODEL, TOKEN, make_entry

REPLY_1F = b"LSID=A3YAAABDAGcTRzAzMDM3OQ\nMGAMOD=LSJZX1K\nWLAN=WPA\nNAME=SS-1F\nMGAFWVER=1312\nVER=1.0.94p10"
REPLY_2F = b"LSID=AzQAAPwwaAEAAA8-GQz__w\nMGAMOD=LSDEFED\nWLAN=NA\nNAME=DEFED-2F\nVER=1.0.94p10\nMGAFWVER=3366"


# --- reading a reply (LI §2) -----------------------------------------------------------

def test_the_replies_of_the_users_hubs():
    assert parse_reply(REPLY_1F, "192.168.88.53") == DiscoveredHub(
        host="192.168.88.53", hub_id="A3YAAABDAGcTRzAzMDM3OQ",
        model="LSJZX1K", name="SS-1F", version="1.0.94p10",
    )
    assert parse_reply(REPLY_2F, "192.168.88.13") == DiscoveredHub(
        host="192.168.88.13", hub_id="AzQAAPwwaAEAAA8-GQz__w",
        model="LSDEFED", name="DEFED-2F", version="1.0.94p10",
    )


@pytest.mark.parametrize("data", [
    b"Z-SEARCH * \r\n",                 # our own search, heard back
    b"MGAMOD=LSJZX1K\nNAME=x",           # no LSID
    b"LSID=\nNAME=x",                    # empty LSID
    b"\xff\xfe",                         # not UTF-8
    b"",
])
def test_anything_else_is_not_a_hub(data):
    assert parse_reply(data, "192.168.88.1") is None


def test_the_spec_s_line_ends_too():
    """LI §2 shows `\\n`; a `\\r\\n` would be read the same."""
    assert parse_reply(b"LSID=X\r\nNAME=Y\r\n", "h").name == "Y"


# --- the search itself ------------------------------------------------------------------

class _FakeEndpoint:
    """Stands in for the UDP socket: answers each search like the user's
    hubs did, twice per hub, to the port the search came from."""

    def __init__(self, protocol, replies, send_error=None):
        self.protocol = protocol
        self.replies = replies
        self.send_error = send_error
        self.sent: list = []
        self.closed = False

    def sendto(self, data, addr):
        if self.send_error is not None:
            raise self.send_error
        self.sent.append((data, addr))
        for host, reply in self.replies:
            self.protocol.datagram_received(reply, (host, 12345))
            self.protocol.datagram_received(reply, (host, 12345))
        self.protocol.datagram_received(data, ("192.168.88.251", 44001))

    def close(self):
        self.closed = True


async def _search(hass, *, replies=(), endpoint_error=None, send_error=None,
                  addresses=("192.168.88.255", "255.255.255.255")):
    from ipaddress import IPv4Address

    endpoints = []

    async def create(factory, **kwargs):
        if endpoint_error is not None:
            raise endpoint_error
        assert kwargs == {"local_addr": ("0.0.0.0", 0), "allow_broadcast": True}
        endpoint = _FakeEndpoint(factory(), list(replies), send_error)
        endpoints.append(endpoint)
        return endpoint, endpoint.protocol

    async def broadcast_addresses(_hass):
        return {IPv4Address(a) for a in addresses}

    with (
        patch.object(hass.loop, "create_datagram_endpoint", create),
        patch.object(discovery.network, "async_get_ipv4_broadcast_addresses", broadcast_addresses),
    ):
        hubs = await real_discover_hubs(hass, timeout=0)
    return hubs, endpoints


async def test_a_search_finds_each_hub_once(hass):
    hubs, (endpoint,) = await _search(hass, replies=[
        ("192.168.88.53", REPLY_1F), ("192.168.88.13", REPLY_2F),
    ])
    assert sorted(h.name for h in hubs) == ["DEFED-2F", "SS-1F"]
    assert endpoint.sent == [
        (b"Z-SEARCH * \r\n", ("192.168.88.255", 12345)),
        (b"Z-SEARCH * \r\n", ("255.255.255.255", 12345)),
    ]
    assert endpoint.closed


async def test_a_search_that_cannot_start_or_send(hass):
    hubs, endpoints = await _search(hass, endpoint_error=OSError("no network"))
    assert hubs == [] and endpoints == []
    hubs, (endpoint,) = await _search(hass, send_error=OSError("unreachable"))
    assert hubs == [] and endpoint.closed


async def test_searching_at_start_and_every_15_minutes(hass, sim, loaded, lan_search):
    await hass.async_block_till_done(wait_background_tasks=True)
    assert lan_search.call_count == 1
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=15, seconds=1))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert lan_search.call_count == 2


# --- what a found hub leads to ------------------------------------------------------------

async def _found(hass, *hubs):
    discovery.async_trigger_discovery(hass, list(hubs))
    await hass.async_block_till_done(wait_background_tasks=True)
    return hass.config_entries.flow.async_progress_by_handler(DOMAIN)


NEW_HUB = DiscoveredHub(host=HOST, hub_id=HUB_ID, model="LSJZX1K", name="SS-1F", version="1.0.94p10")


async def test_a_new_hub_is_offered_and_set_up_with_its_token(hass, hub, setup_entry):
    (flow,) = await _found(hass, NEW_HUB)
    assert flow["context"]["source"] == SOURCE_INTEGRATION_DISCOVERY
    assert flow["context"]["title_placeholders"] == {"name": "SS-1F"}
    assert flow["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {"token": "short"})
    assert result["errors"] == {"token": "invalid_token"}
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"model": MODEL, "token": "WRONGTOKEN0000000000"},
    )
    assert result["errors"] == {"base": "invalid_auth"}
    assert result["description_placeholders"] == {"host": HOST, "name": "SS-1F", "model": "LSJZX1K"}

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"model": MODEL, "token": TOKEN},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == HUB_ID
    assert entry.data["host"] == HOST and entry.data["token"] == TOKEN


async def test_the_same_hub_found_twice_is_offered_once(hass, hub):
    flows = await _found(hass, NEW_HUB, NEW_HUB)
    assert len(flows) == 1


async def test_a_configured_hub_at_its_address_is_left_alone(hass, sim):
    entry = make_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, unique_id=sim_hub.AGT)
    found = DiscoveredHub(host=sim_hub.HOST, hub_id=sim_hub.AGT, name="SS-1F")
    assert await _found(hass, found) == []
    assert entry.data["host"] == sim_hub.HOST


async def test_a_configured_hub_at_a_new_address_is_followed(hass, sim, loaded):
    """discovery-update-info: the entry takes the new address and reloads."""
    await hass.async_block_till_done(wait_background_tasks=True)
    assert loaded.unique_id == sim_hub.AGT        # adopted at setup
    apis = len(sim.apis)
    moved = DiscoveredHub(host="192.168.1.77", hub_id=sim_hub.AGT, name="SS-1F")
    assert await _found(hass, moved) == []
    assert loaded.data["host"] == "192.168.1.77"
    assert len(sim.apis) == apis + 1               # reloaded
    assert loaded.state is ConfigEntryState.LOADED


async def test_an_entry_from_before_r43_takes_the_id_when_found(hass, sim):
    """Still identified by its address (e.g. a hub with nothing paired):
    found at that address, it takes the hub id and nothing is offered."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert entry.unique_id == sim_hub.HOST
    found = DiscoveredHub(host=sim_hub.HOST, hub_id=sim_hub.AGT, name="SS-1F")
    assert await _found(hass, found) == []
    assert entry.unique_id == sim_hub.AGT


async def test_an_entry_at_that_address_with_another_id_is_not_changed(hass, sim):
    """Another hub now answers at the address an entry has (the old hub
    moved away): nothing is offered for the address, nothing is changed."""
    entry = make_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, unique_id="ANOTHER_HUB_ID")
    found = DiscoveredHub(host=sim_hub.HOST, hub_id=sim_hub.AGT, name="SS-1F")
    assert await _found(hass, found) == []
    assert entry.unique_id == "ANOTHER_HUB_ID"


async def test_an_ignored_hub_stays_ignored(hass, hub):
    MockConfigEntry(
        domain=DOMAIN, unique_id=HUB_ID, source="ignore", data={},
    ).add_to_hass(hass)
    assert await _found(hass, NEW_HUB) == []


# --- identifying entries by hub id at setup --------------------------------------------------

async def test_setup_gives_an_entry_its_hub_id(hass, sim, loaded):
    assert loaded.unique_id == sim_hub.AGT
    result = await diagnostics.async_get_config_entry_diagnostics(hass, loaded)
    assert result["entry"]["unique_id"] == sim_hub.AGT


async def test_a_hub_with_nothing_paired_keeps_its_address_as_id(hass, sim):
    sim.devices = []
    entry = make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == sim_hub.HOST


async def test_the_same_hub_set_up_twice_raises_a_repair_issue(hass, sim):
    first = make_entry()
    first.add_to_hass(hass)
    hass.config_entries.async_update_entry(first, unique_id=sim_hub.AGT)
    second = MockConfigEntry(
        domain=DOMAIN, title="LifeSmart Hub (again)", version=2, unique_id="lifesmart-hub.lan",
        data={**first.data, "host": "lifesmart-hub.lan"},
    )
    second.add_to_hass(hass)
    await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert second.unique_id == "lifesmart-hub.lan"          # not taken over
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"duplicate_hub_{second.entry_id}")
    assert issue is not None and issue.config_entry_id == second.entry_id
    assert issue.translation_placeholders == {
        "title": "LifeSmart Hub (again)", "host": "lifesmart-hub.lan",
        "other_title": "LifeSmart Hub", "other_host": sim_hub.HOST,
    }

    # The user deletes the first one; the second takes the id on its next start.
    await hass.config_entries.async_remove(first.entry_id)
    await hass.config_entries.async_reload(second.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert second.unique_id == sim_hub.AGT
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"duplicate_hub_{second.entry_id}") is None


# --- the forms (R43) ---------------------------------------------------------------------------

async def test_adding_a_configured_hub_under_another_address_updates_it(hass, hub, setup_entry):
    entry = MockConfigEntry(
        domain=DOMAIN, title="LifeSmart Hub", version=2, unique_id=HUB_ID,
        data={"host": "192.168.1.99", "model": MODEL, "token": TOKEN, "local_port": 1},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "model": MODEL, "token": TOKEN},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["host"] == HOST


async def test_reconfiguring_to_another_hub_is_refused(hass, hub, setup_entry):
    entry = MockConfigEntry(
        domain=DOMAIN, title="LifeSmart Hub", version=2, unique_id="SOME_OTHER_HUB",
        data={"host": "192.168.1.99", "model": MODEL, "token": TOKEN, "local_port": 1},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "model": MODEL, "token": TOKEN},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_hub"}
    assert entry.data["host"] == "192.168.1.99"


async def test_reconfiguring_an_old_entry_onto_a_hub_another_entry_has(hass, hub, setup_entry):
    MockConfigEntry(
        domain=DOMAIN, title="Has it", version=2, unique_id=HUB_ID,
        data={"host": "192.168.1.98", "model": MODEL, "token": TOKEN},
    ).add_to_hass(hass)
    old = MockConfigEntry(
        domain=DOMAIN, title="Old", version=2, unique_id="192.168.1.99",
        data={"host": "192.168.1.99", "model": MODEL, "token": TOKEN},
    )
    old.add_to_hass(hass)
    result = await old.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "model": MODEL, "token": TOKEN},
    )
    assert result["errors"] == {"base": "wrong_hub"}


async def test_reconfiguring_an_entry_identified_by_its_hub_id(hass, hub, setup_entry):
    """The usual case after R43: the entry already has the hub id and the
    address still leads to that hub."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="LifeSmart Hub", version=2, unique_id=HUB_ID,
        data={"host": HOST, "model": MODEL, "token": TOKEN, "local_port": 1},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "model": "OD_OTHER", "token": TOKEN},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == HUB_ID and entry.data["model"] == "OD_OTHER"


def test_a_socket_error_during_the_search_is_only_logged(caplog):
    import logging

    protocol = discovery._SearchProtocol()
    with caplog.at_level(logging.DEBUG, logger="custom_components.lifesmart.discovery"):
        protocol.error_received(OSError("host unreachable"))
    assert "host unreachable" in caplog.text
    assert protocol.hubs == {}
