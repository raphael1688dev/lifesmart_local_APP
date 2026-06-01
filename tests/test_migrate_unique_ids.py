"""Regression tests for _migrate_unique_ids (R10 cross-hub fix).

The migration rewrites legacy <feature>_<me>[_<idx>] unique_ids to the
post-R10 <feature>_<agt>_<me>[_<idx>] form so two hubs sharing a `me`
value (e.g. V_SI / me=0020 system devices) don't collide.

Critical properties under test:
1. Legacy ids get rewritten
2. Already-migrated ids are left alone (idempotent)
3. Unknown features are skipped (no false positives)
4. Stale entries (me no longer present in current devices) are skipped
5. Cross-entry isolation: only entries belonging to the supplied
   config_entry are rewritten
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

# Patch homeassistant.helpers.entity_registry before importing target module.
from homeassistant.helpers import entity_registry as er  # type: ignore

from lifesmart import _migrate_unique_ids


@dataclass
class FakeEntityEntry:
    entity_id: str
    unique_id: str
    config_entry_id: str


class FakeEntityRegistry:
    def __init__(self) -> None:
        self._entries: List[FakeEntityEntry] = []
        self.updates: list[tuple[str, str]] = []  # (entity_id, new_unique_id)

    @property
    def entities(self) -> dict[str, FakeEntityEntry]:
        return {e.entity_id: e for e in self._entries}

    def async_update_entity(self, entity_id: str, *, new_unique_id: str) -> None:
        self.updates.append((entity_id, new_unique_id))
        for e in self._entries:
            if e.entity_id == entity_id:
                e.unique_id = new_unique_id


class FakeConfigEntry:
    def __init__(self, entry_id: str) -> None:
        self.entry_id = entry_id


def _run(registry: FakeEntityRegistry, entry_id: str, devices: list) -> list[tuple[str, str]]:
    """Helper: install fake registry into the er stub and run the migration."""
    er.async_get = lambda hass: registry  # type: ignore[assignment]
    _migrate_unique_ids(hass=None, entry=FakeConfigEntry(entry_id), devices=devices)
    return registry.updates


def test_rewrites_legacy_connectivity_unique_id() -> None:
    """R10 core case: connectivity_<me> → connectivity_<agt>_<me>."""
    reg = FakeEntityRegistry()
    reg._entries.append(FakeEntityEntry(
        entity_id="binary_sensor.v_si_agt1_0020_connectivity",
        unique_id="connectivity_0020",
        config_entry_id="entry_A",
    ))
    devices = [{"me": "0020", "agt": "agt1"}]
    updates = _run(reg, "entry_A", devices)
    assert updates == [(
        "binary_sensor.v_si_agt1_0020_connectivity",
        "connectivity_agt1_0020",
    )]


def test_rewrites_switch_with_idx() -> None:
    """switch_<me>_<idx> → switch_<agt>_<me>_<idx>."""
    reg = FakeEntityRegistry()
    reg._entries.append(FakeEntityEntry(
        entity_id="switch.x",
        unique_id="switch_2711_L1",
        config_entry_id="entry_A",
    ))
    devices = [{"me": "2711", "agt": "agtX"}]
    updates = _run(reg, "entry_A", devices)
    assert updates == [("switch.x", "switch_agtX_2711_L1")]


def test_idempotent_skips_already_migrated() -> None:
    """If unique_id already in new format, leave it alone."""
    reg = FakeEntityRegistry()
    reg._entries.append(FakeEntityEntry(
        entity_id="binary_sensor.x",
        unique_id="connectivity_agt1_0020",  # already has agt
        config_entry_id="entry_A",
    ))
    devices = [{"me": "0020", "agt": "agt1"}]
    updates = _run(reg, "entry_A", devices)
    # First token of suffix is "agt1" which is NOT a known me → skip.
    assert updates == []


def test_skips_unknown_features() -> None:
    """Features not in the legacy whitelist must not be touched."""
    reg = FakeEntityRegistry()
    reg._entries.append(FakeEntityEntry(
        entity_id="sensor.something",
        unique_id="hub_firmware_192_168_1_50",  # 'hub_*' not in whitelist
        config_entry_id="entry_A",
    ))
    devices = [{"me": "firmware", "agt": "fake"}]  # tempting collision
    updates = _run(reg, "entry_A", devices)
    assert updates == []


def test_skips_stale_entries_for_unknown_me() -> None:
    """Entity whose me no longer exists in discovery → don't rewrite."""
    reg = FakeEntityRegistry()
    reg._entries.append(FakeEntityEntry(
        entity_id="sensor.x",
        unique_id="temp_9999",
        config_entry_id="entry_A",
    ))
    devices = [{"me": "2711", "agt": "agt1"}]  # 9999 not here
    updates = _run(reg, "entry_A", devices)
    assert updates == []


def test_cross_entry_isolation() -> None:
    """Only rewrites entries for the supplied config_entry_id."""
    reg = FakeEntityRegistry()
    reg._entries.append(FakeEntityEntry(
        entity_id="sensor.a",
        unique_id="temp_2711",
        config_entry_id="entry_A",
    ))
    reg._entries.append(FakeEntityEntry(
        entity_id="sensor.b",
        unique_id="temp_2711",
        config_entry_id="entry_B",  # belongs to the OTHER hub
    ))
    devices = [{"me": "2711", "agt": "agt1"}]
    updates = _run(reg, "entry_A", devices)
    assert ("sensor.a", "temp_agt1_2711") in updates
    assert all(e[0] != "sensor.b" for e in updates)


def test_empty_devices_is_no_op() -> None:
    """If discovery returned nothing, the migration is a no-op."""
    reg = FakeEntityRegistry()
    reg._entries.append(FakeEntityEntry(
        entity_id="sensor.a",
        unique_id="temp_2711",
        config_entry_id="entry_A",
    ))
    updates = _run(reg, "entry_A", devices=[])
    assert updates == []
