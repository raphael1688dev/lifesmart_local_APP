"""A scripted hub and the fixtures the Home Assistant tests share."""
from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

# Imported before Home Assistant's loader looks for custom integrations, so
# `custom_components` resolves to this repository's folder. It needs no
# __init__.py (R33).
from custom_components.lifesmart.api import LifeSmartAPI

HOST = "192.168.1.50"
HUB_ID = "A3EAAABtAEwQRzM0NzA2NQ"  # the `agt` of DEVICES: the hub's id (R43)
MODEL = "OD_TEST_MODEL"
TOKEN = "0123456789abcdefABCD"
BOUND_PORT = 50001
DEVICES = [
    {"me": "2711", "agt": "A3EAAABtAEwQRzM0NzA2NQ", "name": "Kitchen", "devtype": "SL_SW_ND1",
     "stat": 1, "data": {"L1": {"type": 129, "v": 1}}},
]


class Hub:
    """What the hub at HOST would answer.

    It knows its token and its clock, like the real ones: a request signed
    with another token, or stamped more than five minutes off, gets
    `{"code": 101, "msg": {"ts": <hub time>}}` (LI §3.2 for the clock; the
    wrong-token case was measured on a Smart Station and a DEFED hub,
    PROGRESS R31 / R34). Like them it does not look at the model: a request
    with any model and the right token is accepted.
    `replies` overrides that for the next requests: each item is returned,
    or raised if it is an exception.
    """

    def __init__(self) -> None:
        self.token = TOKEN
        self.devices: Any = list(DEVICES)
        self.clock_ahead = 0
        self.replies: list[Any] = []
        self.start_error: BaseException | None = None
        self.apis: list[ScriptedAPI] = []

    def answer(self, api: "ScriptedAPI", obj: str) -> Any:
        if self.replies:
            reply = self.replies.pop(0)
            if isinstance(reply, BaseException):
                raise reply
            return reply
        hub_time = int(time.time()) + self.clock_ahead
        signed_ok = api.token == self.token
        in_time = abs(int(time.time()) + api.ts_offset - hub_time) <= 300
        if not (signed_ok and in_time):
            return {"code": 101, "msg": {"ts": hub_time}}
        if obj == "eps":
            return {"code": 0, "msg": self.devices}
        return {"code": 0, "msg": {}}


class ScriptedAPI(LifeSmartAPI):
    """The real API class with the UDP socket replaced by the script.

    `send_command`, its resend rule, `discover_devices` and
    `apply_ts_from_response` are the real ones.
    """

    hub: Hub

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.started = False
        self.stopped = False
        self.sent: list[str] = []
        self.hub.apis.append(self)

    async def async_start(self) -> None:
        if self.hub.start_error is not None:
            raise self.hub.start_error
        self.started = True
        if self.local_port == 0:
            self.local_port = BOUND_PORT

    async def async_stop(self) -> None:
        self.stopped = True

    async def _send_once(self, obj, args, pkg_type, timeout):
        self.sent.append(obj)
        await asyncio.sleep(0)
        return self.hub.answer(self, obj)


@pytest.fixture(autouse=True)
def lan_search():
    """The LAN search (discovery.py, R43) finds nothing unless a test says
    otherwise: tests may not open sockets. Yields the mock; set its
    `return_value` to a list of DiscoveredHub."""
    with patch(
        "custom_components.lifesmart.discovery.async_discover_hubs",
        AsyncMock(return_value=[]),
    ) as mock:
        yield mock


@pytest.fixture
def hub():
    """A hub the config flow talks to instead of opening a socket."""
    the_hub = Hub()
    api_class = type("ScriptedAPIForTest", (ScriptedAPI,), {"hub": the_hub})
    with patch("custom_components.lifesmart.config_flow.LifeSmartAPI", api_class):
        yield the_hub


@pytest.fixture
def setup_entry():
    """Stop Home Assistant from setting the entry up for real.

    Returns None, as the integration's own function does (Home Assistant
    2026.11+). It returned True while the harness ran 2026.10.4 (R33).
    """
    # The real unload needs the runtime data the real setup would have
    # created; with setup replaced, unload is replaced too (R43: flows that
    # update an entry now reload it).
    with (
        patch(
            "custom_components.lifesmart.async_setup_entry", AsyncMock(return_value=None)
        ) as mock,
        patch(
            "custom_components.lifesmart.async_unload_entry", AsyncMock(return_value=None)
        ),
    ):
        yield mock


# --- the whole integration, against a hub simulated at the datagram level ---------
# (R40, quality scale step 9). tests_ha/hub.py says what the hub does.

from pytest_homeassistant.common import MockConfigEntry  # noqa: E402

from custom_components.lifesmart.const import DOMAIN  # noqa: E402

from . import hub as sim_hub  # noqa: E402


@pytest.fixture
def sim():
    """A simulated hub; every LifeSmartAPI the integration creates talks to it."""
    the_hub = sim_hub.Hub()
    with (
        patch("custom_components.lifesmart.LifeSmartAPI", sim_hub.api_class_for(the_hub)),
        patch(
            "custom_components.lifesmart._get_local_ip_for_target",
            return_value=sim_hub.LOCAL_IP,
        ),
        # The simulated hub answers at once; this only shortens the wait for
        # an answer that never comes (10 s per attempt in the integration).
        patch("custom_components.lifesmart.API_TIMEOUT", sim_hub.TIMEOUT),
    ):
        yield the_hub


def make_entry(**data) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN, title="LifeSmart Hub", version=2, unique_id=sim_hub.HOST,
        data={
            "host": sim_hub.HOST, "model": sim_hub.MODEL, "token": sim_hub.TOKEN,
            "local_port": sim_hub.BOUND_PORT, **data,
        },
    )


@pytest.fixture
async def loaded(hass, sim):
    """The integration set up for real, on the simulated hub."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
