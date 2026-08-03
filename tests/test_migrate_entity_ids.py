"""Regression tests for _migrate_entity_ids.

HA 2027.2 will reject entity_ids whose object part contains characters outside
``[a-z0-9_]``. Some hubs deliver an ``agt`` (hub ID) containing ``-``, which
early boots baked into the entity registry. This migration cleans them up.

Critical properties under test:
1. Ids with '-' get renamed with '_'
2. Clean ids are untouched (idempotent)
3. Cross-entry isolation
4. Collisions raised by the registry are swallowed (don't crash setup)
5. Object-part collapse handles adjacent invalid chars
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from homeassistant.helpers import entity_registry as er  # type: ignore

from lifesmart import _migrate_entity_ids


@dataclass
class FakeEntityEntry:
    entity_id: str
    config_entry_id: str


class FakeEntityRegistry:
    def __init__(self) -> None:
        self._entries: List[FakeEntityEntry] = []
        self.renames: list[tuple[str, str]] = []
        self.collide_on: set[str] = set()

    @property
    def entities(self) -> dict[str, FakeEntityEntry]:
        return {e.entity_id: e for e in self._entries}

    def async_update_entity(self, entity_id: str, *, new_entity_id: str) -> None:
        if new_entity_id in self.collide_on:
            raise ValueError(f"entity_id {new_entity_id} already registered")
        self.renames.append((entity_id, new_entity_id))
        for e in self._entries:
            if e.entity_id == entity_id:
                e.entity_id = new_entity_id


class FakeConfigEntry:
    def __init__(self, entry_id: str) -> None:
        self.entry_id = entry_id


def _run(registry: FakeEntityRegistry, entry_id: str) -> list[tuple[str, str]]:
    er.async_get = lambda hass: registry  # type: ignore[assignment]
    _migrate_entity_ids(hass=None, entry=FakeConfigEntry(entry_id))
    return registry.renames


def test_renames_hyphen_to_underscore() -> None:
    """Core case: switch.foo_a-b_c → switch.foo_a_b_c."""
    reg = FakeEntityRegistry()
    reg._entries.append(FakeEntityEntry(
        entity_id="switch.sl_sw_nd2_azqaapwwaaeaaa8-gqz_w_a21d_l2",
        config_entry_id="entry_A",
    ))
    renames = _run(reg, "entry_A")
    assert renames == [(
        "switch.sl_sw_nd2_azqaapwwaaeaaa8-gqz_w_a21d_l2",
        "switch.sl_sw_nd2_azqaapwwaaeaaa8_gqz_w_a21d_l2",
    )]


def test_leaves_clean_ids_alone() -> None:
    """Idempotent: clean entity_ids are not touched."""
    reg = FakeEntityRegistry()
    reg._entries.append(FakeEntityEntry(
        entity_id="sensor.sl_nature_agt1_2711_temperature",
        config_entry_id="entry_A",
    ))
    assert _run(reg, "entry_A") == []


def test_cross_entry_isolation() -> None:
    """Only entities of the supplied config_entry are considered."""
    reg = FakeEntityRegistry()
    reg._entries.append(FakeEntityEntry(
        entity_id="switch.a-b",  # our entry
        config_entry_id="entry_A",
    ))
    reg._entries.append(FakeEntityEntry(
        entity_id="switch.c-d",  # other hub, unrelated
        config_entry_id="entry_B",
    ))
    renames = _run(reg, "entry_A")
    assert ("switch.a-b", "switch.a_b") in renames
    assert all(old != "switch.c-d" for old, _ in renames)


def test_collision_is_swallowed() -> None:
    """If HA raises on new_entity_id collision, we log & continue — no crash."""
    reg = FakeEntityRegistry()
    reg._entries.append(FakeEntityEntry(
        entity_id="switch.foo-bar",
        config_entry_id="entry_A",
    ))
    reg._entries.append(FakeEntityEntry(
        entity_id="switch.baz-qux",
        config_entry_id="entry_A",
    ))
    reg.collide_on.add("switch.foo_bar")  # simulate existing taker
    renames = _run(reg, "entry_A")
    # Only the non-colliding rename lands
    assert ("switch.baz-qux", "switch.baz_qux") in renames
    assert ("switch.foo-bar", "switch.foo_bar") not in renames


def test_collapses_and_strips_underscores() -> None:
    """Adjacent invalid chars collapse; leading/trailing underscores strip."""
    reg = FakeEntityRegistry()
    reg._entries.append(FakeEntityEntry(
        entity_id="sensor.-abc--def-",
        config_entry_id="entry_A",
    ))
    renames = _run(reg, "entry_A")
    assert renames == [("sensor.-abc--def-", "sensor.abc_def")]


def test_no_object_part_is_skipped() -> None:
    """Malformed ids without '.' are ignored (defensive)."""
    reg = FakeEntityRegistry()
    reg._entries.append(FakeEntityEntry(
        entity_id="not_an_entity_id",
        config_entry_id="entry_A",
    ))
    assert _run(reg, "entry_A") == []
