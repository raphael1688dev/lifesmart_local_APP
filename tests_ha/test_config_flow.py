"""The config flow, driven through Home Assistant's own flow manager.

HA quality scale `config-flow-test-coverage`: every line of config_flow.py,
and for every error the proof that the user can correct the input and still
finish. CI fails if coverage of config_flow.py drops below 100 %.

Runs on the Home Assistant version the harness pins (see tests_ha/__init__.py).
"""
import asyncio

import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lifesmart.config_flow import (
    FLOW_TIMEOUT,
    _has_devices,
    validate_host,
    validate_token,
)
from custom_components.lifesmart.const import DEFAULT_MODEL, DOMAIN

from .conftest import BOUND_PORT, DEVICES, HOST, MODEL, TOKEN

GOOD = {"host": HOST, "model": MODEL, "token": TOKEN}
ENTRY_DATA = {**GOOD, "local_port": BOUND_PORT}


async def _start(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    return result


async def _submit(hass, result, **changes):
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {**GOOD, **changes}
    )


def _shown(result):
    """What the form is redrawn with: the values Home Assistant pre-fills."""
    return {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }


def _assert_created(result):
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "LifeSmart Hub"
    assert result["data"] == ENTRY_DATA
    assert result["result"].unique_id == HOST
    assert result["result"].version == 2


def _existing_entry(hass, **data):
    entry = MockConfigEntry(
        domain=DOMAIN, title="LifeSmart Hub", version=2, unique_id=HOST,
        data={**ENTRY_DATA, **data},
    )
    entry.add_to_hass(hass)
    return entry


# --- user step: the happy path ----------------------------------------------------

async def test_user_flow_creates_the_entry(hass, hub, setup_entry):
    result = await _submit(hass, await _start(hass))
    _assert_created(result)
    (api,) = hub.apis
    assert (api.host, api.model, api.token) == (HOST, MODEL, TOKEN)
    assert api.timeout == FLOW_TIMEOUT
    assert api.sent == ["eps"]
    assert api.started and api.stopped
    await hass.async_block_till_done()
    setup_entry.assert_awaited_once()


async def test_the_form_offers_the_default_model(hass, hub):
    result = await _start(hass)
    filled = result["data_schema"]({"host": HOST, "token": TOKEN})
    assert filled["model"] == DEFAULT_MODEL


async def test_host_and_token_are_stored_without_surrounding_spaces(hass, hub, setup_entry):
    result = await _submit(hass, await _start(hass), host=f"  {HOST} ", token=f" {TOKEN}  ")
    _assert_created(result)


async def test_a_hostname_is_accepted(hass, hub, setup_entry):
    result = await _submit(hass, await _start(hass), host="lifesmart-hub.lan")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "lifesmart-hub.lan"


async def test_devices_as_a_dict_are_accepted(hass, hub, setup_entry):
    """Some firmware answers `eps` with {id: device} instead of a list."""
    hub.devices = {device["me"]: device for device in DEVICES}
    _assert_created(await _submit(hass, await _start(hass)))


async def test_any_model_is_accepted(hass, hub, setup_entry):
    """The hubs measured do not check the model (R34): a made-up one with
    the right token goes through, as it did on the real hubs."""
    result = await _submit(hass, await _start(hass), model="CLAUDE_CODE_W_RIGHT_TOKEN")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["model"] == "CLAUDE_CODE_W_RIGHT_TOKEN"


async def test_a_hub_clock_that_is_off_is_corrected(hass, hub, setup_entry):
    """LI §3.2: more than five minutes apart is code 101, with the hub's
    time in the reply. The API takes that time and asks again."""
    hub.clock_ahead = 3600
    result = await _submit(hass, await _start(hass))
    _assert_created(result)
    (api,) = hub.apis
    assert api.sent == ["eps", "eps"]
    assert 3590 <= api.ts_offset <= 3610


# --- user step: every error, and getting past it -----------------------------------

@pytest.mark.parametrize(
    ("changes", "errors"),
    [
        ({"host": "   "}, {"host": "invalid_host"}),
        ({"host": "a" * 64 + ".lan"}, {"host": "invalid_host"}),
        ({"token": "tooshort"}, {"token": "invalid_token"}),
        ({"token": "0123456789abcdef-!"}, {"token": "invalid_token"}),
        ({"host": "", "token": "x"}, {"host": "invalid_host", "token": "invalid_token"}),
    ],
)
async def test_malformed_input_is_reported_per_field_without_calling_the_hub(
    hass, hub, setup_entry, changes, errors
):
    result = await _submit(hass, await _start(hass), **changes)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == errors
    assert hub.apis == []  # nothing was sent anywhere
    # R34: the form comes back with what was typed (normalised), not empty.
    typed = {**GOOD, **changes}
    assert _shown(result)["model"] == typed["model"]
    assert set(_shown(result)) == {"host", "model", "token"}

    _assert_created(await _submit(hass, result))


@pytest.mark.parametrize(
    "replies",
    [
        # A read that times out is sent once more before giving up (D18).
        [asyncio.TimeoutError(), asyncio.TimeoutError()],
        # A socket error is not retried.
        [OSError("network unreachable")],
    ],
)
async def test_a_hub_that_does_not_answer(hass, hub, setup_entry, replies):
    hub.replies = list(replies)
    result = await _submit(hass, await _start(hass))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert hub.apis[0].stopped
    assert _shown(result) == GOOD  # nothing to retype

    _assert_created(await _submit(hass, result))


async def test_one_lost_packet_is_resent(hass, hub, setup_entry):
    hub.replies = [asyncio.TimeoutError()]
    _assert_created(await _submit(hass, await _start(hass)))
    assert hub.apis[0].sent == ["eps", "eps"]


async def test_a_socket_that_cannot_be_opened(hass, hub, setup_entry):
    hub.start_error = OSError("address in use")
    result = await _submit(hass, await _start(hass))
    assert result["errors"] == {"base": "cannot_connect"}
    assert hub.apis[0].stopped  # cleaned up even though start failed

    hub.start_error = None
    _assert_created(await _submit(hass, result))


@pytest.mark.parametrize(
    "reply",
    [
        {"code": 0, "msg": []},
        {"code": 0, "msg": {}},
        {"code": 0, "msg": {"note": "not a device"}},
        {"code": 0, "msg": "nothing"},
        {"code": 0},
    ],
)
async def test_a_hub_with_no_devices(hass, hub, setup_entry, reply):
    hub.replies = [reply]
    result = await _submit(hass, await _start(hass))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}
    assert hub.apis[0].stopped

    _assert_created(await _submit(hass, result))


@pytest.mark.parametrize("reply", [{"code": 10004, "msg": "error"}, "not even a dict", None])
async def test_an_answer_that_is_not_a_device_list(hass, hub, setup_entry, reply):
    """R34: its own message. It used to be shown as "no devices found"."""
    hub.replies = [reply]
    result = await _submit(hass, await _start(hass))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unexpected_reply"}
    assert hub.apis[0].stopped

    _assert_created(await _submit(hass, result))


async def test_a_wrong_token_is_reported_as_the_token(hass, hub, setup_entry):
    """R34. The hub answers a wrong token with code 101, the code for a
    clock that is off. After taking the hub's time and asking again it is
    still 101, so it is the token — not "sync your clock with NTP", which is
    what this showed before."""
    result = await _submit(hass, await _start(hass), token="WRONGTOKEN0000000000")
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert hub.apis[0].sent == ["eps", "eps"]
    assert hub.apis[0].stopped
    assert _shown(result) == {**GOOD, "token": "WRONGTOKEN0000000000"}

    _assert_created(await _submit(hass, result))


async def test_code_101_without_the_hubs_time(hass, hub, setup_entry):
    """Not seen on a real hub. Nothing can be corrected, so the message
    names both possible causes."""
    hub.replies = [{"code": 101}]
    result = await _submit(hass, await _start(hass))
    assert result["errors"] == {"base": "clock_skew"}
    assert hub.apis[0].sent == ["eps"]

    _assert_created(await _submit(hass, result))


async def test_the_same_host_cannot_be_added_twice(hass, hub, setup_entry):
    _existing_entry(hass)
    result = await _submit(hass, await _start(hass))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hub.apis == []


# --- reconfigure --------------------------------------------------------------------

NEW_TOKEN = "NEWTOKEN0000000000000"


async def _start_reconfigure(hass, entry):
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}
    return result


async def test_reconfigure_form_is_prefilled_from_the_entry(hass, hub, setup_entry):
    entry = _existing_entry(hass)
    result = await _start_reconfigure(hass, entry)
    assert _shown(result) == GOOD


async def test_reconfigure_updates_the_entry_and_reloads(hass, hub, setup_entry):
    entry = _existing_entry(hass, extra="kept")
    hub.token = NEW_TOKEN
    result = await _submit(hass, await _start_reconfigure(hass, entry), token=NEW_TOKEN)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {**ENTRY_DATA, "token": NEW_TOKEN, "extra": "kept"}
    assert entry.unique_id == HOST
    assert hub.apis[0].stopped
    await hass.async_block_till_done()
    setup_entry.assert_awaited_once()  # the reload set it up with the new data


async def test_reconfigure_defaults_to_the_stock_model_for_an_old_entry(hass, hub, setup_entry):
    """Entries from before the model field existed have no `model`."""
    entry = MockConfigEntry(
        domain=DOMAIN, version=2, unique_id=HOST, data={"host": HOST, "token": TOKEN},
    )
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry)
    assert _shown(result) == {"host": HOST, "model": DEFAULT_MODEL, "token": TOKEN}


@pytest.mark.parametrize(
    ("changes", "errors"),
    [
        ({"host": ""}, {"host": "invalid_host"}),
        ({"token": "short"}, {"token": "invalid_token"}),
    ],
)
async def test_reconfigure_reports_malformed_input_per_field(
    hass, hub, setup_entry, changes, errors
):
    entry = _existing_entry(hass)
    result = await _submit(hass, await _start_reconfigure(hass, entry), **changes)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == errors
    assert hub.apis == []
    assert entry.data == ENTRY_DATA  # untouched
    # R34: redrawn with what was typed, not reset to the stored values.
    assert _shown(result)["model"] == MODEL
    assert _shown(result) != GOOD

    result = await _submit(hass, result)
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    ("replies", "error"),
    [
        ([asyncio.TimeoutError(), asyncio.TimeoutError()], "cannot_connect"),
        ([OSError("down")], "cannot_connect"),
        ([{"code": 0, "msg": []}], "no_devices"),
        ([{"code": 10004}], "unexpected_reply"),
        ([{"code": 101}], "clock_skew"),
    ],
)
async def test_reconfigure_errors_keep_the_entry_and_can_be_corrected(
    hass, hub, setup_entry, replies, error
):
    entry = _existing_entry(hass)
    hub.replies = list(replies)
    result = await _submit(hass, await _start_reconfigure(hass, entry))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert entry.data == ENTRY_DATA
    assert hub.apis[0].stopped
    setup_entry.assert_not_awaited()

    result = await _submit(hass, result)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_with_a_wrong_token(hass, hub, setup_entry):
    entry = _existing_entry(hass)
    result = await _submit(hass, await _start_reconfigure(hass, entry), token="WRONGTOKEN0000000000")
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data == ENTRY_DATA
    assert _shown(result)["token"] == "WRONGTOKEN0000000000"

    result = await _submit(hass, result)
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_corrects_a_hub_clock_that_is_off(hass, hub, setup_entry):
    entry = _existing_entry(hass)
    hub.clock_ahead = -7200
    result = await _submit(hass, await _start_reconfigure(hass, entry))
    assert result["reason"] == "reconfigure_successful"
    assert hub.apis[0].sent == ["eps", "eps"]


# --- reauth (R34): the hub rejected the stored token ----------------------------------

async def _start_reauth(hass, entry):
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}
    assert result["description_placeholders"]["host"] == HOST
    return result


async def _submit_token(hass, result, token):
    return await hass.config_entries.flow.async_configure(result["flow_id"], {"token": token})


async def test_reauth_asks_for_the_token_only(hass, hub, setup_entry):
    entry = _existing_entry(hass, token="OLDTOKEN000000000000")
    result = await _start_reauth(hass, entry)
    assert [str(key) for key in result["data_schema"].schema] == ["token"]


async def test_reauth_stores_the_new_token_and_reloads(hass, hub, setup_entry):
    entry = _existing_entry(hass, token="OLDTOKEN000000000000", extra="kept")
    result = await _submit_token(hass, await _start_reauth(hass, entry), f" {TOKEN} ")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {**ENTRY_DATA, "extra": "kept"}   # host, model, port untouched
    (api,) = hub.apis
    assert (api.host, api.model, api.token) == (HOST, MODEL, TOKEN)
    assert api.stopped
    await hass.async_block_till_done()
    setup_entry.assert_awaited_once()


async def test_reauth_uses_the_stock_model_for_an_old_entry(hass, hub, setup_entry):
    entry = MockConfigEntry(
        domain=DOMAIN, version=2, unique_id=HOST, data={"host": HOST, "token": "OLDTOKEN000000000000"},
    )
    entry.add_to_hass(hass)
    result = await _submit_token(hass, await _start_reauth(hass, entry), TOKEN)
    assert result["reason"] == "reauth_successful"
    assert hub.apis[0].model == DEFAULT_MODEL
    assert "model" not in entry.data


async def test_reauth_accepts_a_hub_with_no_devices(hass, hub, setup_entry):
    """The token is what is being checked; a hub with nothing paired that
    accepts it is a working login."""
    entry = _existing_entry(hass, token="OLDTOKEN000000000000")
    hub.devices = []
    result = await _submit_token(hass, await _start_reauth(hass, entry), TOKEN)
    assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("token", "replies", "errors"),
    [
        ("short", [], {"token": "invalid_token"}),
        ("STILLWRONG0000000000", [], {"base": "invalid_auth"}),
        (TOKEN, [asyncio.TimeoutError(), asyncio.TimeoutError()], {"base": "cannot_connect"}),
        (TOKEN, [{"code": 10004}], {"base": "unexpected_reply"}),
        (TOKEN, [{"code": 101}], {"base": "clock_skew"}),
    ],
)
async def test_reauth_errors_keep_the_entry_and_can_be_corrected(
    hass, hub, setup_entry, token, replies, errors
):
    old = "OLDTOKEN000000000000"
    entry = _existing_entry(hass, token=old)
    hub.replies = list(replies)
    result = await _submit_token(hass, await _start_reauth(hass, entry), token)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == errors
    assert entry.data["token"] == old
    assert _shown(result) == {"token": token}
    setup_entry.assert_not_awaited()

    result = await _submit_token(hass, result, TOKEN)
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"] == TOKEN


# --- the validators' branches a form cannot reach -------------------------------------
# The form's schema only lets strings through, so these are called directly.

@pytest.mark.parametrize("host", [None, 42, ".".join(["abcdefghij"] * 25)])
def test_validate_host_rejects(host):
    with pytest.raises(vol.Invalid):
        validate_host(host)


@pytest.mark.parametrize("host", ["10.0.0.1", "fe80::1", "hub.lan"])
def test_validate_host_accepts(host):
    assert validate_host(host) == host


@pytest.mark.parametrize("token", [None, 1234567890123456, "a" * 65])
def test_validate_token_rejects(token):
    with pytest.raises(vol.Invalid):
        validate_token(token)


@pytest.mark.parametrize(
    ("msg", "expected"),
    [([{"me": "1"}], True), ([], False), ({"1": {"me": "1"}}, True), ({"1": "x"}, False), (None, False), ("x", False)],
)
def test_has_devices(msg, expected):
    assert _has_devices(msg) is expected
