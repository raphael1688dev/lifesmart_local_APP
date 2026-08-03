"""Regression tests for generate_entity_id (R6 命名規則 / R10 unique_id).

The function is the single source of truth for entity_id construction across
switch/sensor/cover/binary_sensor. Bugs here ripple to every entity in HA
so we lock down its behavior with explicit cases.
"""
from __future__ import annotations

from lifesmart import generate_entity_id


def test_basic_with_idx() -> None:
    """Standard pattern: <devtype>_<agt>_<me>_<idx>, all lowercase."""
    assert generate_entity_id("SL_SW_ND3", "A3yAaB", "7D01", "L1") == "sl_sw_nd3_a3yaab_7d01_l1"


def test_without_idx() -> None:
    """No idx → just <devtype>_<agt>_<me>."""
    assert generate_entity_id("SL_NATURE", "AGT123", "2711") == "sl_nature_agt123_2711"


def test_collapses_consecutive_underscores() -> None:
    """Repeated underscores must collapse — guards against agt containing trailing _."""
    assert generate_entity_id("A__B", "C", "D", "E") == "a_b_c_d_e"


def test_strips_outer_underscores() -> None:
    """Leading/trailing underscores get stripped."""
    assert generate_entity_id("_A_", "_B_", "_C_", "_D_") == "a_b_c_d"


def test_does_not_leak_lls_prefix() -> None:
    """R6 revert: function must NOT re-introduce an lls_ prefix."""
    result = generate_entity_id("X", "Y", "Z")
    assert not result.startswith("lls_"), "lls_ prefix re-introduced; R6 revert violated"


def test_includes_agt_for_cross_hub_safety() -> None:
    """R10: agt MUST appear in entity_id slug so two hubs don't collide on
    devices that share `me` (e.g. V_SI / me=0020 system devices).
    """
    a = generate_entity_id("V_SI", "agt_one", "0020", "connectivity")
    b = generate_entity_id("V_SI", "agt_two", "0020", "connectivity")
    assert a != b, "agt absent from entity_id → R10 cross-hub collision risk"


def test_idx_none_explicit_vs_missing() -> None:
    """Calling with idx=None must equal omitting idx."""
    assert (
        generate_entity_id("X", "Y", "Z", None)
        == generate_entity_id("X", "Y", "Z")
    )


def test_sanitizes_hyphen_in_agt() -> None:
    """agt tokens with '-' must produce HA-valid entity_ids (2027.2 will reject '-')."""
    result = generate_entity_id("SL_SW_ND2", "AzQAAPWwAAEAAA8-Gqz", "w_A21D", "L2")
    assert "-" not in result
    assert result == "sl_sw_nd2_azqaapwwaaeaaa8_gqz_w_a21d_l2"


def test_sanitizes_other_invalid_chars() -> None:
    """Any char outside [a-z0-9_] gets replaced and collapsed."""
    # spaces, +, /, . all become _ then collapse
    assert generate_entity_id("A B", "C+D", "E/F", "G.H") == "a_b_c_d_e_f_g_h"
