"""R19 (2026-10-24): opt in to HA 2026.11 in-place entity_id changes.

From HA 2026.11 an entity whose entity_id is renamed in the registry is
updated in place instead of being removed and re-added. For custom
integrations HA keeps the old remove + re-add path (until 2027.11) when a
class outside core defines async_prepare_to_add_to_hass / async_added_to_hass /
async_will_remove_from_hass but neither it nor a subclass defines
async_entity_id_changed. Our four entity bases define the add/remove hooks, so
each must define the opt-in hook too.

`_requires_readd` below is the logic of HA dev's
`homeassistant.helpers.entity._entity_class_requires_readd` (read 2026-10-24),
reproduced so the check runs without HA installed.
"""
from unittest.mock import Mock

import pytest

from lifesmart.binary_sensor import LifeSmartConnectivitySensor
from lifesmart.cover import LifeSmartCover
from lifesmart.sensor import (
    LifeSmartBaseSensor,
    LifeSmartBatterySensor,
    LifeSmartHubInfoSensor,
    LifeSmartSignalSensor,
    LifeSmartTemperatureSensor,
)
from lifesmart.switch import LifeSmartSwitch

_ADD_REMOVE_METHODS = (
    "async_prepare_to_add_to_hass",
    "async_added_to_hass",
    "async_will_remove_from_hass",
)


def _requires_readd(entity_class: type) -> bool:
    """HA dev `_entity_class_requires_readd`, verbatim logic."""
    mro = [cls for cls in entity_class.__mro__ if not cls.__module__.startswith("homeassistant.")]
    hook_owners = [cls for cls in mro if "async_entity_id_changed" in cls.__dict__]
    return any(
        any(method in cls.__dict__ for method in _ADD_REMOVE_METHODS)
        and not any(issubclass(owner, cls) for owner in hook_owners)
        for cls in mro
    )


HOOK_OWNERS = [LifeSmartBaseSensor, LifeSmartConnectivitySensor, LifeSmartCover, LifeSmartSwitch]
ALL_ENTITY_CLASSES = HOOK_OWNERS + [
    LifeSmartTemperatureSensor,
    LifeSmartBatterySensor,
    LifeSmartSignalSensor,
    LifeSmartHubInfoSensor,  # no add/remove hooks at all — in place regardless
]


@pytest.mark.parametrize("cls", ALL_ENTITY_CLASSES, ids=lambda c: c.__name__)
def test_entity_id_changes_in_place(cls):
    assert not _requires_readd(cls)


@pytest.mark.parametrize("cls", HOOK_OWNERS, ids=lambda c: c.__name__)
def test_hook_defined_next_to_the_add_remove_hooks(cls):
    """HA only credits the hook when it is on the same class (or a subclass)
    as the add/remove methods — a sibling base earlier in the MRO doesn't count."""
    assert any(m in cls.__dict__ for m in _ADD_REMOVE_METHODS)
    assert "async_entity_id_changed" in cls.__dict__


@pytest.mark.parametrize("cls", HOOK_OWNERS, ids=lambda c: c.__name__)
def test_hook_chains_to_super(cls, monkeypatch):
    """The hook must call super() so HA's base class can move its own
    bookkeeping. Give the (stubbed) base the method and check it is reached."""
    base = cls.__mro__[1]
    base_hook = Mock()
    monkeypatch.setattr(base, "async_entity_id_changed", base_hook, raising=False)
    entity = object.__new__(cls)  # no __init__: hooks must not depend on it
    cls.async_entity_id_changed(entity, "sensor.old_id")
    base_hook.assert_called_once_with("sensor.old_id")


def test_detector_catches_a_class_without_the_hook():
    """Sanity check of the reproduced HA logic itself."""

    class Forgot:
        async def async_added_to_hass(self): ...

    class Fixed(Forgot):
        def async_entity_id_changed(self, old_entity_id): ...

    class SiblingOnly:
        def async_entity_id_changed(self, old_entity_id): ...

    class NotCovered(SiblingOnly, Forgot):  # hook on a sibling, not a subclass
        pass

    assert _requires_readd(Forgot)
    assert not _requires_readd(Fixed)
    assert _requires_readd(NotCovered)
