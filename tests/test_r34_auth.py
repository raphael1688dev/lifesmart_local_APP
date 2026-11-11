"""R34 (quality scale step 5): what code 101 means, and what follows from it.

Measured on a Smart Station and a DEFED hub (firmware 1.0.94p10): a wrong
token is answered with `{"code": 101, "msg": {"ts": <hub time>}}`, the same
code the spec gives for a timestamp more than five minutes off (LI §3.2).
A wrong model with the right token is accepted.

So: on 101, take the hub's time and ask again. Still 101 = the token.
"""
import asyncio

import pytest

import lifesmart
from lifesmart.api import (
    CMD_GET,
    CMD_SET,
    REJECTED_CLOCK,
    REJECTED_TOKEN,
    LifeSmartAPI,
    rejection,
)
from lifesmart.coordinator import LifeSmartCoordinator

from .fakes import FakeAPI, make_env, runtime, setup

ConfigEntryAuthFailed = lifesmart.ConfigEntryAuthFailed
ConfigEntryNotReady = lifesmart.ConfigEntryNotReady

HUB_TIME = 1_794_361_729
REJECTED = {"code": 101, "msg": {"ts": HUB_TIME}}
OK = {"code": 0, "msg": []}


@pytest.fixture
def env(monkeypatch):
    return make_env(monkeypatch)


def _api(replies):
    """A real LifeSmartAPI whose datagrams are answered from `replies`."""
    api = LifeSmartAPI("h", "m", "t")
    sent = []

    async def once(obj, args, pkg_type, timeout):
        sent.append((obj, api.ts_offset))
        reply = replies[len(sent) - 1]
        if isinstance(reply, BaseException):
            raise reply
        return reply
    api._send_once = once
    return api, sent


# --- rejection(): reading a reply ------------------------------------------------

@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (REJECTED, REJECTED_TOKEN),
        ({"code": 101, "msg": {}}, REJECTED_CLOCK),
        ({"code": 101}, REJECTED_CLOCK),
        ({"code": 101, "msg": "x"}, REJECTED_CLOCK),
        ({"code": 101, "msg": {"ts": "1794361729"}}, REJECTED_CLOCK),
        ({"code": 101, "msg": {"ts": True}}, REJECTED_CLOCK),
        (OK, None),
        ({"code": 10004}, None),
        (None, None),
        ("code 101", None),
    ],
)
def test_rejection(reply, expected):
    assert rejection(reply) == expected


# --- send_command: correct the clock once, for every command ---------------------

def test_a_clock_that_is_off_is_corrected_and_the_request_resent(monkeypatch):
    monkeypatch.setattr(lifesmart.api.time, "time", lambda: HUB_TIME - 1000.0)
    api, sent = _api([REJECTED, OK])
    assert asyncio.run(api.send_command("eps", {}, CMD_GET)) == OK
    assert sent == [("eps", 0), ("eps", 1000)]


def test_a_wrong_token_is_asked_twice_and_no_more():
    api, sent = _api([REJECTED, REJECTED, OK])
    reply = asyncio.run(api.send_command("eps", {}, CMD_GET))
    assert rejection(reply) == REJECTED_TOKEN
    assert len(sent) == 2


def test_101_without_the_hubs_time_is_not_resent():
    api, sent = _api([{"code": 101}, OK])
    reply = asyncio.run(api.send_command("eps", {}, CMD_GET))
    assert rejection(reply) == REJECTED_CLOCK
    assert len(sent) == 1
    assert api.ts_offset == 0


def test_a_command_that_must_not_be_repeated_is_still_resent_after_101():
    """The hub did not carry out what it answered with 101, so asking again
    cannot run it twice. Timeouts are different: a SET is not resent then."""
    api, sent = _api([REJECTED, OK])
    assert asyncio.run(api.send_command("doscene", {"id": "AI1"}, CMD_SET)) == OK
    assert len(sent) == 2

    api, sent = _api([asyncio.TimeoutError(), OK])
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(api.send_command("doscene", {"id": "AI1"}, CMD_SET))
    assert len(sent) == 1


def test_the_resend_after_101_keeps_the_timeout_rule():
    """After the clock correction a read may still lose one packet."""
    api, sent = _api([REJECTED, asyncio.TimeoutError(), OK])
    assert asyncio.run(api.send_command("eps", {}, CMD_GET)) == OK
    assert len(sent) == 3


def test_other_replies_are_returned_untouched():
    for reply in (OK, {"code": 10004, "msg": "x"}):
        api, sent = _api([reply])
        assert asyncio.run(api.send_command("eps", {}, CMD_GET)) is reply
        assert len(sent) == 1


# --- setup: say what is wrong (test-before-setup) ---------------------------------

def _setup_with(env, monkeypatch, reply):
    async def discover(self):
        return reply
    monkeypatch.setattr(FakeAPI, "discover_devices", discover)
    setup(env)


def test_setup_with_a_rejected_token_asks_for_reauthentication(env, monkeypatch):
    with pytest.raises(ConfigEntryAuthFailed):
        _setup_with(env, monkeypatch, REJECTED)
    assert env.apis[0].stopped                      # the socket is released
    assert not hasattr(env.entry, "runtime_data")   # nothing half set up
    assert env.hass.config_entries.forwarded is None


@pytest.mark.parametrize(
    ("reply", "fragment"),
    [
        ({"code": 101}, "without its time"),
        ({"code": 10004, "msg": "x"}, "10004"),
        ("garbage", "str"),
        (None, "NoneType"),
    ],
)
def test_setup_retries_on_any_other_hub_error(env, monkeypatch, reply, fragment):
    """Before R34 all of these loaded the entry with no devices and no error."""
    with pytest.raises(ConfigEntryNotReady) as err:
        _setup_with(env, monkeypatch, reply)
    assert fragment in str(err.value)
    assert not isinstance(err.value, ConfigEntryAuthFailed)
    assert env.apis[0].stopped
    assert not hasattr(env.entry, "runtime_data")


@pytest.mark.parametrize("msg", [[], {}])
def test_a_hub_without_sub_devices_still_loads(env, monkeypatch, msg):
    """Code 0 and nothing paired is not an error: the hub's own entities work."""
    _setup_with(env, monkeypatch, {"code": 0, "msg": msg})
    assert runtime(env).devices == []
    assert env.hass.config_entries.forwarded is not None


def test_devices_as_a_dict_are_loaded(env, monkeypatch):
    _setup_with(env, monkeypatch, {"code": 0, "msg": {"2711": {"me": "2711"}, "note": "x"}})
    assert runtime(env).devices == [{"me": "2711"}]


# --- while running: the token is changed on the hub -------------------------------

def test_the_poll_raises_auth_failed_for_a_rejected_token():
    api = FakeAPI()
    coordinator = LifeSmartCoordinator(None, None, api, "h")

    async def discover():
        return REJECTED
    api.discover_devices = discover
    with pytest.raises(ConfigEntryAuthFailed):
        asyncio.run(coordinator._async_update_data())


def test_the_poll_reports_other_errors_as_a_failed_update():
    from lifesmart.coordinator import UpdateFailed
    api = FakeAPI()
    coordinator = LifeSmartCoordinator(None, None, api, "h")
    for reply in ({"code": 101}, {"code": 10004}):
        async def discover(reply=reply):
            return reply
        api.discover_devices = discover
        with pytest.raises(UpdateFailed):
            asyncio.run(coordinator._async_update_data())


def test_the_heartbeat_notices_a_rejected_token(env):
    setup(env)
    hub = runtime(env).availability
    api = env.apis[0]

    async def rejected(ip, port):
        return REJECTED
    accepted = api.configure_event_service
    api.configure_event_service = rejected

    asyncio.run(env.issues.timer(None))
    assert env.entry.reauth_requests == 1    # asked for at once
    assert hub.available                     # one refusal is not enough yet
    asyncio.run(env.issues.timer(None))
    assert not hub.available                 # entities go unavailable
    assert env.entry.reauth_requests == 2    # HA keeps one flow; asking again is harmless

    # The hub is answering: this is not the "unreachable" repair issue.
    env.issues.clock[0] = 10_000.0
    asyncio.run(env.issues.timer(None))
    assert env.issues.created == []

    api.configure_event_service = accepted
    asyncio.run(env.issues.timer(None))
    assert hub.available


def test_a_healthy_heartbeat_never_asks_for_reauthentication(env):
    setup(env)
    for _ in range(3):
        asyncio.run(env.issues.timer(None))
    assert not hasattr(env.entry, "reauth_requests")


def test_an_unreachable_issue_is_cleared_when_the_hub_answers_with_a_rejection(env):
    """Silent for five minutes, then back but refusing the token: the hub is
    reachable again, so the "unreachable" notice goes."""
    setup(env)
    api = env.apis[0]
    api.notify_error = TimeoutError()
    for now in (0.0, 300.0):
        env.issues.clock[0] = now
        asyncio.run(env.issues.timer(None))
    assert [issue_id for issue_id, _ in env.issues.created] == ["hub_unreachable_entry1"]

    api.notify_error = None

    async def rejected(ip, port):
        return REJECTED
    api.configure_event_service = rejected
    deleted_before = len(env.issues.deleted)
    asyncio.run(env.issues.timer(None))
    assert env.issues.deleted[deleted_before:] == ["hub_unreachable_entry1"]
    assert not runtime(env).availability.available   # still unavailable: token
