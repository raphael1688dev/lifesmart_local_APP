"""Pytest configuration for LifeSmart Local tests.

Tests target the *pure functions* inside the integration (no Home Assistant
runtime required). We stub `homeassistant.*` imports so test modules don't
need HA installed — that lets contributors run tests quickly with just
`pytest` and the standard library.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent
_PKG_PARENT = _REPO_ROOT / "custom_components"


def _ensure_path() -> None:
    """Insert custom_components/ at the head of sys.path."""
    p = str(_PKG_PARENT)
    if p not in sys.path:
        sys.path.insert(0, p)


def _install_ha_stubs() -> None:
    """Minimal stub modules for HA imports referenced by lifesmart code under test.

    Only stubs the symbols the *pure* tests need to import. If a test imports
    something we haven't stubbed yet, add it here rather than installing the
    real homeassistant package — keep tests light.
    """
    if "homeassistant" in sys.modules:
        return

    ha = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    # homeassistant.const
    const = types.ModuleType("homeassistant.const")
    const.CONF_HOST = "host"
    const.CONF_TOKEN = "token"
    sys.modules["homeassistant.const"] = const

    # homeassistant.core
    core = types.ModuleType("homeassistant.core")

    class _Stub:
        pass

    core.HomeAssistant = _Stub
    core.ServiceCall = _Stub
    core.callback = lambda f: f
    sys.modules["homeassistant.core"] = core

    # homeassistant.exceptions
    exc = types.ModuleType("homeassistant.exceptions")

    class _ConfigEntryNotReady(Exception):
        pass

    exc.ConfigEntryNotReady = _ConfigEntryNotReady
    sys.modules["homeassistant.exceptions"] = exc

    # homeassistant.helpers / entity_registry / event / issue_registry /
    # update_coordinator. Mark as a package by giving it __path__ so
    # `from homeassistant.helpers import X` and `from homeassistant.helpers.X
    # import Y` both resolve.
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers"] = helpers

    ent_reg = types.ModuleType("homeassistant.helpers.entity_registry")
    ent_reg.async_get = lambda hass: None
    sys.modules["homeassistant.helpers.entity_registry"] = ent_reg

    event = types.ModuleType("homeassistant.helpers.event")
    event.async_track_time_interval = lambda *a, **kw: (lambda: None)
    sys.modules["homeassistant.helpers.event"] = event

    issue_reg = types.ModuleType("homeassistant.helpers.issue_registry")
    issue_reg.async_create_issue = lambda *a, **kw: None
    issue_reg.async_delete_issue = lambda *a, **kw: None

    class _IssueSeverity:
        WARNING = "warning"
        ERROR = "error"

    issue_reg.IssueSeverity = _IssueSeverity
    sys.modules["homeassistant.helpers.issue_registry"] = issue_reg

    upd = types.ModuleType("homeassistant.helpers.update_coordinator")

    class _DataUpdateCoordinator:
        """Stub: enough surface for sensor.py to import and reference."""

        def __init__(self, *a, **kw) -> None:
            self.data = None

        def async_add_listener(self, _cb, *a, **kw):
            return lambda: None

        def async_set_updated_data(self, data) -> None:
            self.data = data

    class _UpdateFailed(Exception):
        pass

    # DataUpdateCoordinator[T] (generic subscripting); accept any subscript.
    def _generic_class_getitem(cls, _item):
        return cls

    _DataUpdateCoordinator.__class_getitem__ = classmethod(_generic_class_getitem)  # type: ignore[attr-defined]
    upd.DataUpdateCoordinator = _DataUpdateCoordinator
    upd.UpdateFailed = _UpdateFailed
    sys.modules["homeassistant.helpers.update_coordinator"] = upd

    # homeassistant.config_entries
    cfg = types.ModuleType("homeassistant.config_entries")
    cfg.ConfigEntry = _Stub
    sys.modules["homeassistant.config_entries"] = cfg


def _install_voluptuous_stub() -> None:
    """Minimal voluptuous stub — only `Schema`, `Required`, `Any` are used in
    lifesmart/__init__.py services registration. We don't need real validation
    for the pure-function tests.
    """
    if "voluptuous" in sys.modules:
        return

    vol = types.ModuleType("voluptuous")

    class _Schema:
        def __init__(self, *a, **kw) -> None: ...

    def _Required(*a, **kw):
        return a[0] if a else None

    def _Any(*a, **kw):
        return None

    vol.Schema = _Schema
    vol.Required = _Required
    vol.Any = _Any
    vol.Invalid = type("Invalid", (Exception,), {})
    sys.modules["voluptuous"] = vol


_ensure_path()
_install_ha_stubs()
_install_voluptuous_stub()
