"""Fakes for driving async_setup_entry / platform setups without HA (R23, R25).

`make_env(monkeypatch)` patches the integration's collaborators — the API,
the registries, the issue registry, timers — and returns the handles the
tests inspect. Shared by test_setup_entry.py and the R25 feature tests.
"""
import asyncio
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

import lifesmart
from lifesmart.const import DOMAIN

HOST = "192.168.1.50"
AGT = "A3EAAABtAEwQRzM0NzA2NQ"
HUB_REGISTRY_ID = "hub-registry-id"

DEVICES = [
    {"me": "2711", "agt": AGT, "name": "Kitchen", "devtype": "SL_SW_ND1", "stat": 1,
     "lDbm": -61, "data": {"L1": {"type": 129, "v": 1}, "V": {"v": 90}}},
    {"me": "2712", "agt": AGT, "name": "Curtain", "devtype": "SL_P", "stat": 1,
     "data": {"P1": {"type": 128, "v": 0}, "P8": {"v": 80}}},
    {"me": "2713", "agt": AGT, "name": "TV", "devtype": "SL_P_IR", "stat": 1, "data": {}},
    {"me": "2714", "agt": AGT, "name": "Nature", "devtype": "SL_NATURE", "stat": 1,
     "data": {"L1": {"type": 129, "v": 0}, "T": {"v": 245}}},
]
GOOD_VERSION = {"code": 0, "msg": {"ver": "1.0.5p3", "osver": "4.9.253", "mgatype": "LSJZX1K"}}
GOOD_TIMEZONE = {"code": 0, "msg": {"timezone": 8, "summer": False}}


class FakeAPI:
    devices: List[Dict[str, Any]] = DEVICES
    scenes: List[Dict[str, Any]] = []
    discovery_extra: Dict[str, Any] = {}

    def __init__(self, **kwargs: Any) -> None:
        self.local_port = 12348
        self.version_reply: Any = GOOD_VERSION
        self.timezone_reply: Any = GOOD_TIMEZONE
        self.notify_error: Optional[BaseException] = None
        self.stopped = False
        self.report_listeners: List[Callable[[Dict[str, Any]], None]] = []
        self.state_listeners: Dict[tuple, Callable[[Any], None]] = {}
        self.calls: List[tuple] = []
        self.reply: Any = {"code": 0, "msg": {}}

    async def async_start(self) -> None:
        pass

    async def async_stop(self) -> None:
        self.stopped = True

    async def discover_devices(self):
        return {"code": 0, "msg": self.devices, **self.discovery_extra}

    async def get_hub_version(self):
        return self.version_reply

    async def get_hub_timezone(self):
        return self.timezone_reply

    async def configure_event_service(self, ip, port):
        if self.notify_error is not None:
            raise self.notify_error
        return {"code": 0}

    async def get_remote_list(self):
        return []

    async def get_scene_list(self):
        return {"code": 0, "msg": self.scenes}

    def register_report_listener(self, listener):
        self.report_listeners.append(listener)
        return lambda: self.report_listeners.remove(listener)

    def register_state_listener(self, me, idx, listener):
        self.state_listeners[(me, idx)] = listener
        return lambda: self.state_listeners.pop((me, idx), None)

    async def _record(self, *call):
        self.calls.append(call)
        if isinstance(self.reply, BaseException):
            raise self.reply
        return self.reply

    def trigger_scene(self, scene_id, scene_type=128):
        return self._record("trigger_scene", scene_id, scene_type)

    def set_hub_timezone(self, timezone, summer):
        return self._record("set_hub_timezone", timezone, summer)

    def set_device_name(self, name, me=None):
        return self._record("set_device_name", name, me)

    def upgrade_hub(self, reboot):
        return self._record("upgrade_hub", reboot)

    def factory_reset_hub(self):
        return self._record("factory_reset_hub")

    def reboot_hub(self):
        return self._record("reboot_hub")

    def send_remote_key(self, remote_id, key):
        return self._record("send_remote_key", remote_id, key)


class FakeDevice(SimpleNamespace):
    """A device registry entry as of HA 2026.11: one `config_entry_id`.

    R28: deliberately no `config_entries` — that property is deprecated
    (removed in HA 2027.10.0), and R25 used it because the old fake had it.
    """


class FakeDeviceRegistry:
    """R28: offers only the lookups HA 2026.11 does not deprecate. There is
    no `async_get_device(identifiers=…)` (removed in HA 2027.8.0), so code
    that calls it fails here instead of logging a warning for the user."""

    def __init__(self, log: list) -> None:
        self.calls: list = []
        self.updates: list = []
        self.devices: Dict[str, FakeDevice] = {}
        self._log = log

    def async_get_or_create(self, **kwargs):
        self._log.append("hub_device")
        self.calls.append(kwargs)
        for identifier in kwargs["identifiers"]:
            existing = self.async_get_device_by_identifier(identifier, kwargs["config_entry_id"])
            if existing is not None:
                return existing
        device = FakeDevice(
            id=HUB_REGISTRY_ID if not self.devices else f"device-{len(self.devices)}",
            identifiers=set(kwargs["identifiers"]),
            config_entry_id=kwargs["config_entry_id"],
        )
        self.devices[device.id] = device
        return device

    def add(self, device_id: str, identifiers: set, entry_id: str) -> FakeDevice:
        device = FakeDevice(id=device_id, identifiers=identifiers, config_entry_id=entry_id)
        self.devices[device_id] = device
        return device

    def entries_for(self, entry_id: str) -> list:
        return [d for d in self.devices.values() if d.config_entry_id == entry_id]

    def async_get(self, device_id: str):
        return self.devices.get(device_id)

    def async_get_device_by_identifier(self, identifier, config_entry_id):
        for device in self.devices.values():
            if device.config_entry_id == config_entry_id and identifier in device.identifiers:
                return device
        return None

    def async_update_device(self, device_id: str, **kwargs):
        self.updates.append((device_id, kwargs))
        if "new_identifiers" in kwargs:
            self.devices[device_id].identifiers = set(kwargs["new_identifiers"])


class FakeEntityRegistry:
    def __init__(self) -> None:
        self.entities: Dict[str, SimpleNamespace] = {}

    def add(self, entity_id: str, unique_id: str, entry_id: str) -> None:
        self.entities[entity_id] = SimpleNamespace(
            entity_id=entity_id, unique_id=unique_id, config_entry_id=entry_id,
        )

    def async_get_entity_id(self, *args):
        return None

    def async_get(self, entity_id):
        return self.entities.get(entity_id)

    def async_update_entity(self, entity_id, **kwargs):
        if "new_unique_id" in kwargs:
            self.entities[entity_id].unique_id = kwargs["new_unique_id"]


class FakeConfigEntries:
    def __init__(self, log: list) -> None:
        self.forwarded = None
        self.unloaded = None
        self.unload_error = None
        self.reloads: List[str] = []
        self.entries: Dict[str, Any] = {}
        self._log = log

    async def async_forward_entry_setups(self, entry, platforms) -> None:
        self._log.append("forward")
        self.forwarded = list(platforms)

    async def async_unload_platforms_or_raise(self, entry, platforms) -> None:
        self.unloaded = list(platforms)
        if self.unload_error is not None:
            raise self.unload_error

    def async_schedule_reload(self, entry_id: str) -> None:
        self.reloads.append(entry_id)

    def async_get_entry(self, entry_id: str):
        return self.entries.get(entry_id)


class FakeServices:
    def __init__(self) -> None:
        self.handlers: Dict[str, Callable] = {}

    def async_register(self, domain, name, handler, schema=None) -> None:
        self.handlers[name] = handler


class FakeHass:
    def __init__(self, log: list) -> None:
        self.data: dict = {}
        self.config_entries = FakeConfigEntries(log)
        self.services = FakeServices()

    async def async_add_executor_job(self, func, *args):
        return func(*args)


class FakeTimers:
    """async_call_later stand-in: records callbacks, fires them on demand."""

    def __init__(self) -> None:
        self.pending: List[list] = []

    def call_later(self, hass, delay, action):
        handle = [delay, action, True]
        self.pending.append(handle)

        def cancel() -> None:
            handle[2] = False
        return cancel

    def active(self) -> List[list]:
        return [h for h in self.pending if h[2]]

    def fire_all(self) -> None:
        for handle in self.active():
            handle[2] = False
            handle[1](None)


class FakeEntry(SimpleNamespace):
    """Config entry stand-in. Background tasks are collected, not started:
    `setup()` awaits them after async_setup_entry, as HA's loop would."""

    def async_create_background_task(self, hass, coro, name):
        self.background.append(coro)


def make_env(monkeypatch) -> SimpleNamespace:
    """Patch the integration's collaborators; return the handles tests inspect."""
    log: list = []
    issues = SimpleNamespace(created=[], deleted=[], timer=None, unsub_calls=0, clock=[0.0])
    apis: list = []
    dev_reg = FakeDeviceRegistry(log)
    ent_reg = FakeEntityRegistry()
    timers = FakeTimers()

    def make_api(**kwargs):
        api = FakeAPI(**kwargs)
        apis.append(api)
        return api

    def track(hass, cb, interval):
        issues.timer = cb

        def unsub() -> None:
            issues.unsub_calls += 1
        return unsub

    monkeypatch.setattr(lifesmart, "LifeSmartAPI", make_api)
    monkeypatch.setattr(lifesmart, "_get_local_ip_for_target", lambda ip: "192.168.1.10")
    monkeypatch.setattr(lifesmart, "async_track_time_interval", track)
    monkeypatch.setattr(lifesmart, "async_call_later", timers.call_later)
    monkeypatch.setattr(lifesmart, "time", SimpleNamespace(monotonic=lambda: issues.clock[0]))
    monkeypatch.setattr(lifesmart.dr, "async_get", lambda hass: dev_reg)
    monkeypatch.setattr(lifesmart.er, "async_get", lambda hass: ent_reg)
    monkeypatch.setattr(
        lifesmart.ir, "async_create_issue",
        lambda hass, domain, issue_id, **kw: issues.created.append((issue_id, kw)),
    )
    monkeypatch.setattr(
        lifesmart.ir, "async_delete_issue",
        lambda hass, domain, issue_id, **kw: issues.deleted.append(issue_id),
    )
    hass = FakeHass(log)
    entry = FakeEntry(
        entry_id="entry1", title="Living room hub", version=2, domain=DOMAIN,
        data={"host": HOST, "token": "0123456789abcdef", "model": "OD_ALI_TECH"},
        background=[],
    )
    hass.config_entries.entries[entry.entry_id] = entry
    return SimpleNamespace(hass=hass, entry=entry, log=log, issues=issues, apis=apis,
                           dev_reg=dev_reg, ent_reg=ent_reg, timers=timers)


def setup(env, run_background: bool = True) -> None:
    """async_setup (actions) + async_setup_entry, then the background tasks.

    With run_background=False the collected coroutines stay in
    `env.entry.background` for the test to run or close.
    """
    async def run() -> None:
        assert await lifesmart.async_setup(env.hass, {}) is True
        assert await lifesmart.async_setup_entry(env.hass, env.entry) is None
        if run_background:
            while env.entry.background:
                await env.entry.background.pop(0)
    asyncio.run(run())


def entry_data(env) -> dict:
    return env.hass.data[DOMAIN]["entries"][env.entry.entry_id]


def device_info(entity) -> Any:
    info = getattr(entity, "_attr_device_info", None)
    return info if info is not None else entity.device_info
