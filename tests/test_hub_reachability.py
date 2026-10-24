"""R19 (2026-10-24): the `hub_unreachable` repair issue.

The issue had translations in all three languages since 2026-05 but nothing
ever created it. It is now driven by the 90 s notify refresh: `_HubReachability`
decides when silence has lasted long enough. The clock is passed in, so the
logic is tested here without HA.
"""
import pytest

from lifesmart import HUB_UNREACHABLE_AFTER_SECONDS, _HubReachability, _hub_unreachable_issue_id


def test_threshold_is_five_minutes():
    assert HUB_UNREACHABLE_AFTER_SECONDS == 300


def test_no_issue_before_threshold():
    r = _HubReachability()
    assert r.record_failure(1000.0) is None
    assert r.record_failure(1090.0) is None
    assert r.record_failure(1299.9) is None


def test_issue_at_threshold_reports_whole_minutes():
    r = _HubReachability()
    r.record_failure(0.0)
    assert r.record_failure(300.0) == 5
    assert r.record_failure(390.0) == 6   # placeholder keeps counting
    assert r.record_failure(1859.0) == 30


def test_elapsed_counts_from_first_failure_not_last():
    r = _HubReachability()
    for t in (0.0, 90.0, 180.0, 270.0):
        assert r.record_failure(t) is None
    assert r.record_failure(360.0) == 6


def test_success_resets_and_reports_previous_failure():
    r = _HubReachability()
    assert r.record_success() is False      # never failed -> nothing to clear
    r.record_failure(0.0)
    assert r.record_success() is True       # was failing -> caller deletes issue
    assert r.record_success() is False
    # a fresh outage starts its own clock
    assert r.record_failure(1000.0) is None
    assert r.record_failure(1299.0) is None
    assert r.record_failure(1300.0) == 5


def test_custom_threshold():
    r = _HubReachability(threshold_seconds=60)
    r.record_failure(0.0)
    assert r.record_failure(59.0) is None
    assert r.record_failure(60.0) == 1


def test_issue_id_is_per_entry():
    """Two hubs = two entries = two independent notices."""
    assert _hub_unreachable_issue_id("a") != _hub_unreachable_issue_id("b")
    assert _hub_unreachable_issue_id("abc").startswith("hub_unreachable_")
