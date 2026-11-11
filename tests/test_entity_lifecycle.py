"""R19 (2026-10-24): opt in to HA 2026.11 in-place entity_id changes.

From HA 2026.11 an entity whose entity_id is renamed in the registry is
updated in place instead of being removed and re-added. For custom
integrations HA keeps the old remove + re-add path (until 2027.11) when a
class outside core defines async_prepare_to_add_to_hass / async_added_to_hass /
async_will_remove_from_hass but neither it nor a subclass defines
async_entity_id_changed. R32: one class, entity.py's LifeSmartEntity, defines
the add/remove hooks and the opt-in hook for every entity.

`_requires_readd` below is the logic of HA dev's
`homeassistant.helpers.entity._entity_class_requires_readd` (read 2026-10-24),
reproduced so the check runs without HA installed.
"""
from unittest.mock import Mock

import pytest

from lifesmart.binary_sensor import LifeSmartConnectivitySensor
from lifesmart.button import LifeSmartHubRebootButton
from lifesmart.cover import LifeSmartCover
from lifesmart.entity import LifeSmartDeviceEntity, LifeSmartEntity, LifeSmartHubEntity
from lifesmart.event import LifeSmartButtonEvent
from lifesmart.light import LifeSmartGroupLight
from lifesmart.remote import LifeSmartRemote
from lifesmart.scene import LifeSmartScene
from lifesmart.sensor import (
    LifeSmartBaseSensor,
    LifeSmartBatterySensor,
    LifeSmartHubInfoSensor,
    LifeSmartSignalSensor,
    LifeSmartTemperatureSensor,
)
from lifesmart.switch import LifeSmartGroupSwitch, LifeSmartSwitch

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


# R32: the add / remove hooks and the rename hook live on one class,
# entity.py's LifeSmartEntity. Platform classes must not define the add /
# remove hooks themselves: HA would not credit the base class's rename hook
# for them (it has to be on the same class or a subclass).
HOOK_OWNERS = [LifeSmartEntity]
ALL_ENTITY_CLASSES = [
    LifeSmartEntity,
    LifeSmartDeviceEntity,
    LifeSmartHubEntity,
    LifeSmartBaseSensor,
    LifeSmartTemperatureSensor,
    LifeSmartBatterySensor,
    LifeSmartSignalSensor,
    LifeSmartHubInfoSensor,
    LifeSmartConnectivitySensor,
    LifeSmartCover,
    LifeSmartSwitch,
    LifeSmartGroupSwitch,
    LifeSmartGroupLight,
    LifeSmartHubRebootButton,
    LifeSmartButtonEvent,
    LifeSmartRemote,
    LifeSmartScene,
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


@pytest.mark.parametrize(
    "cls", [c for c in ALL_ENTITY_CLASSES if c is not LifeSmartEntity], ids=lambda c: c.__name__,
)
def test_only_the_base_class_defines_lifecycle_and_availability(cls):
    """R32: platform classes use `_subscribe` / `_async_initial_refresh` /
    `_cleanup`. `available` is decided in entity.py for all of them."""
    own = [c for c in cls.__mro__ if c.__module__.startswith("lifesmart.") and c is not LifeSmartEntity]
    for owner in own:
        defined = set(owner.__dict__)
        assert not defined & set(_ADD_REMOVE_METHODS), owner.__name__
        assert "async_entity_id_changed" not in defined, owner.__name__
        if owner is not LifeSmartDeviceEntity:
            assert "available" not in defined, owner.__name__


@pytest.mark.parametrize("cls", ALL_ENTITY_CLASSES, ids=lambda c: c.__name__)
def test_hook_chains_to_super(cls, monkeypatch):
    """The hook must call super() so HA's base class can move its own
    bookkeeping. Give the (stubbed) HA base the method and check it is reached."""
    ha_base = LifeSmartEntity.__mro__[1]
    base_hook = Mock()
    monkeypatch.setattr(ha_base, "async_entity_id_changed", base_hook)
    entity = object.__new__(cls)  # no __init__: hooks must not depend on it
    entity.async_entity_id_changed("sensor.old_id")
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
