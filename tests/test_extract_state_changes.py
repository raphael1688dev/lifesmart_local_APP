"""Regression tests for api._extract_state_changes (R8-b stat dispatch).

This function parses NOTIFY / REPORT payloads from the hub and emits
(me, idx, value) tuples consumed by state listeners. The R8-b feature
(connectivity binary_sensor) depends on scalar `stat` being emitted as
virtual idx "stat" — this test pins that behavior.
"""
from __future__ import annotations

from lifesmart.api import _extract_state_changes


def test_msg_form_extracts_idx_value() -> None:
    """Single-device msg form: msg has me/idx/data.v."""
    message = {
        "msg": {
            "me": "2711",
            "idx": "L1",
            "data": {"v": 1},
        },
    }
    assert _extract_state_changes(message) == [("2711", "L1", 1)]


def test_msg_form_with_val_fallback() -> None:
    """If `data.v` missing but `val` present at msg top, use val."""
    message = {
        "msg": {
            "me": "2711",
            "idx": "L1",
            "val": 42,
        },
    }
    assert _extract_state_changes(message) == [("2711", "L1", 42)]


def test_chg_form_dict_channels() -> None:
    """chg list form: each entry has channel dicts with .v values."""
    message = {
        "chg": [
            {
                "me": "2711",
                "devtype": "SL_SW_NS3",
                "L1": {"v": 1},
                "L2": {"v": 0},
            },
        ],
    }
    out = _extract_state_changes(message)
    assert ("2711", "L1", 1) in out
    assert ("2711", "L2", 0) in out


def test_chg_form_emits_scalar_stat_as_virtual_idx() -> None:
    """R8-b regression: scalar `stat` is emitted as (me, 'stat', value).

    Without this, the connectivity binary_sensor never receives push updates
    and only refreshes via the 15-min fallback poll.
    """
    message = {
        "chg": [
            {
                "me": "2711",
                "devtype": "SL_SW_NS3",
                "stat": 0,  # device went offline
            },
        ],
    }
    out = _extract_state_changes(message)
    assert ("2711", "stat", 0) in out


def test_chg_skips_reserved_keys() -> None:
    """me/agt/agtid/devtype/fulltype must NOT appear as virtual idx events."""
    message = {
        "chg": [
            {
                "me": "2711",
                "agt": "agt_string",
                "agtid": "mga",
                "devtype": "SL_SW_NS3",
                "fulltype": "X",
                "L1": {"v": 1},
            },
        ],
    }
    out = _extract_state_changes(message)
    # Only L1 should be emitted; reserved keys must be skipped.
    assert out == [("2711", "L1", 1)]


def test_chg_skips_non_numeric_stat() -> None:
    """If stat is a string (shouldn't happen per spec but defensive), skip."""
    message = {
        "chg": [
            {"me": "2711", "devtype": "X", "stat": "online"},
        ],
    }
    out = _extract_state_changes(message)
    assert out == []


def test_empty_or_missing_payload_returns_empty_list() -> None:
    """Robustness: garbage in → empty list out, never raises."""
    assert _extract_state_changes({}) == []
    assert _extract_state_changes({"msg": None}) == []
    assert _extract_state_changes({"chg": "not a list"}) == []
    assert _extract_state_changes({"chg": [None, "junk"]}) == []
