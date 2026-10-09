"""Tests for the pure validators in lifesmart.config_flow (R18, 2026-10-09).

Background: `validate_host` / `validate_token` raise `vol.Invalid`. That
exception is NOT a ValueError (voluptuous 0.16 and probatio 0.13 both derive
it from a plain `Error(Exception)`), so the flow steps' `except (…ValueError…)`
never caught it and a malformed token crashed the flow with "Unknown error".
`_validate_input` is the explicit catch that maps each failure to the
translation key that had existed, unused, since 2026-05.
"""
import pytest
import voluptuous as vol

from lifesmart.config_flow import _validate_input, validate_host, validate_token


# --- the premise -----------------------------------------------------------

def test_vol_invalid_is_not_a_value_error():
    """Documents WHY _validate_input exists. Holds for the real library and
    for the conftest stub alike; if a future library makes Invalid a
    ValueError this test still passes only if we keep the explicit catch."""
    assert issubclass(vol.Invalid, Exception)
    assert not issubclass(vol.Invalid, ValueError)


# --- validate_host -----------------------------------------------------------

@pytest.mark.parametrize("host", ["192.168.1.50", "10.0.0.1", "::1", "fe80::1"])
def test_ip_literals_pass_through(host):
    assert validate_host(host) == host


def test_hostname_passes_through():
    assert validate_host("lifesmart-hub.lan") == "lifesmart-hub.lan"


def test_host_is_stripped():
    assert validate_host("  192.168.1.50 ") == "192.168.1.50"


@pytest.mark.parametrize("host", ["", "   ", None, 42])
def test_empty_or_non_string_host_rejected(host):
    with pytest.raises(vol.Invalid):
        validate_host(host)


def test_label_longer_than_63_rejected():
    with pytest.raises(vol.Invalid):
        validate_host("a" * 64 + ".lan")


def test_hostname_longer_than_253_rejected():
    with pytest.raises(vol.Invalid):
        validate_host(".".join(["abcdefghij"] * 25))  # 10*25 + 24 dots = 274


# --- validate_token ----------------------------------------------------------

def test_token_is_stripped_and_returned():
    assert validate_token("  ABCDEFGHIJKLMNOP1234  ") == "ABCDEFGHIJKLMNOP1234"


@pytest.mark.parametrize("token", ["a" * 16, "Z" * 64, "aB3" * 10])
def test_token_length_boundaries_accepted(token):
    assert validate_token(token) == token


@pytest.mark.parametrize(
    "token",
    [
        "a" * 15,            # too short
        "a" * 65,            # too long
        "abcdefghijklmnop-",  # non-alphanumeric
        "abcdefgh ijklmnop",  # inner whitespace
        None,
        1234567890123456,     # not a str
    ],
)
def test_bad_tokens_rejected(token):
    with pytest.raises(vol.Invalid):
        validate_token(token)


# --- _validate_input (the R18 fix) --------------------------------------------

def test_valid_input_returns_no_errors_and_normalises_in_place():
    user_input = {"host": " 192.168.1.50 ", "token": " ABCDEFGHIJKLMNOP1234 ", "model": "OD_ALI_TECH"}
    assert _validate_input(user_input) == {}
    assert user_input["host"] == "192.168.1.50"
    assert user_input["token"] == "ABCDEFGHIJKLMNOP1234"
    assert user_input["model"] == "OD_ALI_TECH"  # untouched


def test_bad_token_maps_to_field_error_not_exception():
    user_input = {"host": "192.168.1.50", "token": "short"}
    assert _validate_input(user_input) == {"token": "invalid_token"}
    assert user_input["host"] == "192.168.1.50"  # valid field still normalised


def test_bad_host_maps_to_field_error():
    user_input = {"host": "", "token": "ABCDEFGHIJKLMNOP1234"}
    assert _validate_input(user_input) == {"host": "invalid_host"}


def test_both_bad_reports_both_fields():
    user_input = {"host": "a" * 64 + ".x", "token": "nope"}
    assert _validate_input(user_input) == {"host": "invalid_host", "token": "invalid_token"}


def test_missing_keys_are_errors_not_key_errors():
    """A malformed submission must not raise either — map to field errors."""
    assert _validate_input({}) == {"host": "invalid_host", "token": "invalid_token"}
