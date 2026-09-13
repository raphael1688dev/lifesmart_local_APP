"""Regression tests for remote.py entity_id construction (R16, 2026-09-13).

R14 sanitized generate_entity_id() but wrongly cleared remote.py on the
grounds that it "has _slugify" — it did, but only applied it to the device
NAME; `agt` was interpolated raw. A hub whose agt carries '-' therefore
produced remote entity_ids HA 2026.8 warns about and 2027.2 rejects, and
remote.py's own in-place rename fought _migrate_entity_ids every boot.

Fix: slugify the whole object id. These tests lock that down and prove the
change is a no-op for already-clean ids (nobody's entity_id moves).
"""
from __future__ import annotations

from lifesmart.remote import _slugify


def test_slugify_strips_hyphen_in_agt() -> None:
    """The exact shape the constructor now builds: <name>_<agt>_<me>."""
    assert (
        _slugify("living_room_AzQAAPWwAAEAAA8-Gqz_2711")
        == "living_room_azqaapwwaaeaaa8_gqz_2711"
    )


def test_slugify_is_noop_for_clean_id() -> None:
    """Clean agt → identical output, so existing users' entity_ids don't move."""
    assert _slugify("tv_a3yaab_7d01") == "tv_a3yaab_7d01"


def test_slugify_lowercases_agt() -> None:
    """Constructor previously never lowercased agt at all."""
    assert _slugify("tv_A3yAaB_7D01") == "tv_a3yaab_7d01"


def test_slugify_collapses_and_strips() -> None:
    assert _slugify("--a__b--c--") == "a_b_c"


def test_slugify_empty_falls_back() -> None:
    assert _slugify("") == "remote"
    assert _slugify(None) == "remote"
