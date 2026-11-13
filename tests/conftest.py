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

    # R19: enum-like stub. `SensorDeviceClass.BATTERY`, `UnitOfTemperature.CELSIUS`,
    # `CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE` all appear in class
    # bodies, so attribute access must succeed at import time and the values
    # must support `|` — every member is the int 1.
    class _EnumMeta(type):
        def __getattr__(cls, name):
            if name.startswith("__"):
                raise AttributeError(name)
            return 1

    class _AnyEnum(metaclass=_EnumMeta):
        pass

    def _module_getattr(default):
        """PEP 562 module __getattr__ returning `default` for any public name."""
        def _getattr(name):
            if name.startswith("__"):
                raise AttributeError(name)
            return default
        return _getattr

    # homeassistant.const
    const = types.ModuleType("homeassistant.const")
    const.CONF_HOST = "host"
    const.CONF_TOKEN = "token"
    # R19: PERCENTAGE / UnitOfTemperature / EntityCategory / ... resolve to
    # the enum-like stub so platform modules import. Dunders must raise so
    # the import machinery doesn't mistake the module for a package.
    const.__getattr__ = _module_getattr(_AnyEnum)  # type: ignore[attr-defined]
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

    class _HomeAssistantError(Exception):
        pass

    class _ServiceValidationError(_HomeAssistantError):
        pass

    exc.ConfigEntryNotReady = _ConfigEntryNotReady

    # R34: raised by setup and by the coordinator when the hub rejects the
    # token. A HomeAssistantError in HA too, and not a ConfigEntryNotReady.
    class _ConfigEntryAuthFailed(_HomeAssistantError):
        pass

    exc.ConfigEntryAuthFailed = _ConfigEntryAuthFailed
    exc.HomeAssistantError = _HomeAssistantError
    exc.ServiceValidationError = _ServiceValidationError
    sys.modules["homeassistant.exceptions"] = exc

    # homeassistant.helpers / entity_registry / event / issue_registry /
    # update_coordinator. Mark as a package by giving it __path__ so
    # `from homeassistant.helpers import X` and `from homeassistant.helpers.X
    # import Y` both resolve.
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers"] = helpers

    # R28: __init__.py defines CONFIG_SCHEMA next to async_setup.
    cv_mod = types.ModuleType("homeassistant.helpers.config_validation")
    cv_mod.config_entry_only_config_schema = lambda domain: (lambda config: config)
    sys.modules["homeassistant.helpers.config_validation"] = cv_mod
    helpers.config_validation = cv_mod  # type: ignore[attr-defined]

    ent_reg = types.ModuleType("homeassistant.helpers.entity_registry")
    ent_reg.async_get = lambda hass: None
    sys.modules["homeassistant.helpers.entity_registry"] = ent_reg

    # device_registry: __init__.py registers the hub device (D22) so
    # sub-devices can reference it with via_device_id.
    dev_reg = types.ModuleType("homeassistant.helpers.device_registry")
    dev_reg.async_get = lambda hass: None
    dev_reg.DeviceEntry = _Stub
    # R25 (D21): __init__.py looks up this entry's hub device.
    dev_reg.async_entries_for_config_entry = lambda registry, entry_id: (
        registry.entries_for(entry_id) if registry is not None else []
    )
    sys.modules["homeassistant.helpers.device_registry"] = dev_reg

    event = types.ModuleType("homeassistant.helpers.event")
    event.async_track_time_interval = lambda *a, **kw: (lambda: None)
    event.async_call_later = lambda *a, **kw: (lambda: None)
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
            self.listeners: list = []  # R25: tests fire these by hand
            # R30: a coordinator that does not pass `config_entry` gets None
            # here; test_r28_review.py checks both coordinators pass the entry.
            self.config_entry = kw.get("config_entry")

        def async_add_listener(self, cb, *a, **kw):
            self.listeners.append(cb)
            return lambda: self.listeners.remove(cb) if cb in self.listeners else None

        async def async_request_refresh(self) -> None:
            pass

        def async_set_updated_data(self, data) -> None:
            # R28: like the real one, tell the listeners.
            self.data = data
            for listener in list(self.listeners):
                listener()

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

    # R18: enough surface to import config_flow.py so its pure validators
    # can be tested. `class X(ConfigFlow, domain=DOMAIN)` passes a class
    # keyword, which a plain class would reject — swallow it here.
    class _ConfigFlow:
        def __init_subclass__(cls, domain=None, **kwargs) -> None:
            super().__init_subclass__(**kwargs)

    cfg.ConfigFlow = _ConfigFlow
    cfg.ConfigFlowResult = dict  # R42: config_flow.py annotates its steps
    cfg.OptionsFlow = _Stub
    sys.modules["homeassistant.config_entries"] = cfg

    # R16: enough surface to import remote.py so its pure _slugify can be
    # tested. helpers.entity / entity_platform / components.remote.
    ent = types.ModuleType("homeassistant.helpers.entity")

    class _DeviceInfo(dict):
        def __init__(self, **kw) -> None:
            super().__init__(**kw)

    ent.DeviceInfo = _DeviceInfo
    # R42: device_info.py imports it from where HA defines it.
    sys.modules["homeassistant.helpers.device_registry"].DeviceInfo = _DeviceInfo

    # R32: entity.py derives every entity from this. Like HA's: `hass` is
    # None until the entity is added, and the lifecycle methods exist so
    # subclasses can chain to them. State writes are counted for the tests.
    class _Entity:
        hass = None

        async def async_added_to_hass(self) -> None:
            pass

        async def async_will_remove_from_hass(self) -> None:
            pass

        def async_entity_id_changed(self, old_entity_id: str) -> None:
            pass

        def async_write_ha_state(self) -> None:
            self.state_writes = getattr(self, "state_writes", 0) + 1

    ent.Entity = _Entity
    ent.EntityCategory = _AnyEnum  # R19: sensor.py imports it from here
    sys.modules["homeassistant.helpers.entity"] = ent

    ent_plat = types.ModuleType("homeassistant.helpers.entity_platform")
    ent_plat.AddEntitiesCallback = _Stub
    sys.modules["homeassistant.helpers.entity_platform"] = ent_plat

    components = types.ModuleType("homeassistant.components")
    components.__path__ = []  # type: ignore[attr-defined]
    sys.modules["homeassistant.components"] = components

    remote_mod = types.ModuleType("homeassistant.components.remote")

    class _RemoteEntity:
        pass

    remote_mod.RemoteEntity = _RemoteEntity
    # PEP 562: any other attribute remote.py might reference resolves to a
    # harmless stub instead of failing at import.
    remote_mod.__getattr__ = lambda name: _Stub  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.remote"] = remote_mod
    components.remote = remote_mod  # type: ignore[attr-defined]

    # R19: enough surface to import sensor.py / binary_sensor.py / cover.py /
    # switch.py so tests can inspect the entity classes (lifecycle hooks).
    # The entity base class is a plain class; every other name (device
    # classes, state classes, feature flags) is the enum-like stub.
    def _platform_module(name: str, entity_cls_name: str) -> None:
        mod = types.ModuleType(f"homeassistant.components.{name}")
        setattr(mod, entity_cls_name, type(entity_cls_name, (), {}))
        mod.__getattr__ = _module_getattr(_AnyEnum)  # type: ignore[attr-defined]
        sys.modules[mod.__name__] = mod
        setattr(components, name, mod)

    # R32: diagnostics.py. The redaction mirrors HA's: the named keys are
    # replaced wherever they appear, at any depth.
    diag_mod = types.ModuleType("homeassistant.components.diagnostics")

    def _redact(data, to_redact):
        if isinstance(data, dict):
            return {
                k: "**REDACTED**" if k in to_redact else _redact(v, to_redact)
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [_redact(v, to_redact) for v in data]
        return data

    diag_mod.async_redact_data = _redact
    sys.modules[diag_mod.__name__] = diag_mod
    components.diagnostics = diag_mod  # type: ignore[attr-defined]

    _platform_module("sensor", "SensorEntity")
    _platform_module("binary_sensor", "BinarySensorEntity")
    _platform_module("cover", "CoverEntity")
    _platform_module("switch", "SwitchEntity")
    # R25: button (D5 reload), scene, light (D9 group scenes).
    _platform_module("button", "ButtonEntity")
    _platform_module("scene", "Scene")
    _platform_module("light", "LightEntity")

    # R25 (D9): event platform. `_trigger_event` records what was fired so
    # tests can read it; the real one validates the type the same way.
    event_mod = types.ModuleType("homeassistant.components.event")

    class _EventEntity:
        _attr_event_types: list

        def _trigger_event(self, event_type, event_attributes=None) -> None:
            if event_type not in self._attr_event_types:
                raise ValueError(f"Invalid event type {event_type}")
            self.last_event = (event_type, event_attributes)

    class _ButtonEventType:
        PRESS_START = "press_start"
        PRESS_END = "press_end"
        LONG_PRESS_START = "long_press_start"
        LONG_PRESS_END = "long_press_end"
        MULTI_PRESS_ONGOING = "multi_press_ongoing"
        MULTI_PRESS_END = "multi_press_end"

    event_mod.EventEntity = _EventEntity
    event_mod.ButtonEventType = _ButtonEventType
    event_mod.EventDeviceClass = _AnyEnum
    event_mod.ATTR_MULTI_PRESS_COUNT = "multi_press_count"
    sys.modules[event_mod.__name__] = event_mod
    components.event = event_mod  # type: ignore[attr-defined]


def _install_voluptuous_stub() -> None:
    """Minimal voluptuous stub — only `Schema`, `Required`, `Any`, `Invalid`
    are used by lifesmart/__init__.py (services) and config_flow.py
    (validators). We don't need real validation for the pure-function tests.

    R18: if the real library is importable (local venv with voluptuous or
    probatio installed) use it — the config_flow tests then exercise the
    genuine `Invalid` hierarchy. CI installs only pytest and gets the stub,
    whose `Invalid` mirrors the real one (subclass of Exception, NOT of
    ValueError — that distinction is exactly what R18 fixed).
    """
    if "voluptuous" in sys.modules:
        return
    try:
        import voluptuous  # noqa: F401  (real package present — prefer it)
    except ImportError:
        pass
    else:
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
    vol.Optional = _Required  # R25: service schemas
    vol.Any = _Any
    vol.All = _Any
    vol.Coerce = _Any
    vol.Range = _Any
    vol.Length = _Any
    vol.Invalid = type("Invalid", (Exception,), {})
    sys.modules["voluptuous"] = vol


_ensure_path()
_install_ha_stubs()
_install_voluptuous_stub()
