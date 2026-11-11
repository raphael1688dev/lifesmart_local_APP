"""A scripted hub and the fixtures the Home Assistant tests share."""
from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

# Imported before the harness mounts its own `custom_components` package:
# whichever is imported first is the one Home Assistant's loader scans.
# This import is all it takes; custom_components/ needs no __init__.py
# (one was added in 00a685e on that assumption and removed again: the suite
# passes without it).
from custom_components.lifesmart.api import LifeSmartAPI

HOST = "192.168.1.50"
MODEL = "OD_TEST_MODEL"
TOKEN = "0123456789abcdefABCD"
BOUND_PORT = 50001
DEVICES = [
    {"me": "2711", "agt": "A3EAAABtAEwQRzM0NzA2NQ", "name": "Kitchen", "devtype": "SL_SW_ND1",
     "stat": 1, "data": {"L1": {"type": 129, "v": 1}}},
]


class Hub:
    """What the hub at HOST would answer.

    It knows its model / token pair and its clock, like the real one: a
    request signed with the wrong pair, or stamped more than five minutes
    off, gets `{"code": 101, "msg": {"ts": <hub time>}}` (LI §3.2; the
    wrong-signature case was observed on a Smart Station, PROGRESS R31).
    `replies` overrides that for the next requests: each item is returned,
    or raised if it is an exception.
    """

    def __init__(self) -> None:
        self.model = MODEL
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
        signed_ok = (api.model, api.token) == (self.model, self.token)
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
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load integrations from custom_components/."""
    yield


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

    Returns True: Home Assistant 2026.10.4, which the harness runs, expects a
    bool here. The integration's own function returns None (2026.11+).
    """
    with patch(
        "custom_components.lifesmart.async_setup_entry", AsyncMock(return_value=True)
    ) as mock:
        yield mock
