"""Setup / unload wiring (R23, 2026-11-05).

Closes R17 #4: the hub device registration and the `via_device_id` wiring
(D22, R15) had no test — conftest's `dr.async_get` returns None and
`async_setup_entry` was never called. These tests drive `async_setup_entry`
/ `async_unload_entry` with small fakes for the API, the registries and
hass, then run each sub-device platform's setup on the entry data that
setup produced.

Also covers the R23 move to minimum HA 2026.11: the entry functions return
None, unload goes through `async_unload_platforms_or_raise`, and every
repair issue is linked to its config entry.
"""
import asyncio
import importlib
from types import SimpleNamespace

import pytest

import lifesmart
from lifesmart.const import DOMAIN, PLATFORMS
from lifesmart.device_info import hub_device_info_kwargs

HOST = "192.168.1.50"
AGT = "A3EAAABtAEwQRzM0NzA2NQ"
HUB_REGISTRY_ID = "hub-registry-id"
HUB_IDENTIFIER = (DOMAIN, f"hub_{HOST}")

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


class FakeAPI:
    def __init__(self, **kwargs) -> None:
        self.local_port = 12348
        self.version_reply = GOOD_VERSION
        self.notify_error = None
        self.stopped = False

    async def async_start(self) -> None:
        pass

    async def async_stop(self) -> None:
        self.stopped = True

    async def discover_devices(self):
        return {"code": 0, "msg": DEVICES}

    async def get_hub_version(self):
        return self.version_reply

    async def configure_event_service(self, ip, port):
        if self.notify_error is not None:
            raise self.notify_error
        return {"code": 0}

    async def get_remote_list(self):
        return []

    async def get_scene_list(self):
        return {"code": 0, "msg": []}


class FakeDeviceRegistry:
    def __init__(self, log: list) -> None:
        self.calls: list = []
        self._log = log

    def async_get_or_create(self, **kwargs):
        self._log.append("hub_device")
        self.calls.append(kwargs)
        return SimpleNamespace(id=HUB_REGISTRY_ID)


class FakeEntityRegistry:
    entities: dict = {}

    def async_get_entity_id(self, *args):
        return None

    def async_get(self, entity_id):
        return None


class FakeConfigEntries:
    def __init__(self, log: list) -> None:
        self.forwarded = None
        self.unloaded = None
        self.unload_error = None
        self._log = log

    async def async_forward_entry_setups(self, entry, platforms) -> None:
        self._log.append("forward")
        self.forwarded = list(platforms)

    async def async_unload_platforms_or_raise(self, entry, platforms) -> None:
        self.unloaded = list(platforms)
        if self.unload_error is not None:
            raise self.unload_error


class FakeHass:
    def __init__(self, log: list) -> None:
        self.data: dict = {}
        self.config_entries = FakeConfigEntries(log)
        self.services = SimpleNamespace(async_register=lambda *a, **kw: None)

    async def async_add_executor_job(self, func, *args):
        return func(*args)


@pytest.fixture
def env(monkeypatch):
    """Patch the integration's collaborators; return the handles tests inspect."""
    log: list = []
    issues = SimpleNamespace(created=[], deleted=[], timer=None, unsub_calls=0, clock=[0.0])
    apis: list = []
    dev_reg = FakeDeviceRegistry(log)

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
    monkeypatch.setattr(lifesmart, "time", SimpleNamespace(monotonic=lambda: issues.clock[0]))
    monkeypatch.setattr(lifesmart.dr, "async_get", lambda hass: dev_reg)
    monkeypatch.setattr(lifesmart.er, "async_get", lambda hass: FakeEntityRegistry())
    monkeypatch.setattr(
        lifesmart.ir, "async_create_issue",
        lambda hass, domain, issue_id, **kw: issues.created.append((issue_id, kw)),
    )
    monkeypatch.setattr(
        lifesmart.ir, "async_delete_issue",
        lambda hass, domain, issue_id, **kw: issues.deleted.append(issue_id),
    )
    hass = FakeHass(log)
    entry = SimpleNamespace(
        entry_id="entry1", title="Living room hub", version=2,
        data={"host": HOST, "token": "0123456789abcdef", "model": "OD_ALI_TECH"},
    )
    return SimpleNamespace(hass=hass, entry=entry, log=log, issues=issues,
                           apis=apis, dev_reg=dev_reg)


def _setup(env) -> None:
    assert asyncio.run(lifesmart.async_setup_entry(env.hass, env.entry)) is None


def _entry_data(env) -> dict:
    return env.hass.data[DOMAIN]["entries"][env.entry.entry_id]


# --- hub device (R17 #4) -------------------------------------------------------

def test_setup_registers_hub_device_before_forwarding_platforms(env):
    _setup(env)
    assert env.log == ["hub_device", "forward"]
    assert env.hass.config_entries.forwarded == PLATFORMS
    (call,) = env.dev_reg.calls
    assert call == {
        "config_entry_id": "entry1",
        **hub_device_info_kwargs(HOST, "Living room hub", GOOD_VERSION["msg"]),
    }
    assert call["identifiers"] == {HUB_IDENTIFIER}
    assert "via_device_id" not in call  # the hub is a top-level device
    assert _entry_data(env)["hub_device_id"] == HUB_REGISTRY_ID


def _device_info(entity):
    info = getattr(entity, "_attr_device_info", None)
    return info if info is not None else entity.device_info


@pytest.mark.parametrize("platform", ["switch", "sensor", "binary_sensor", "cover", "remote"])
def test_sub_devices_hang_off_the_hub(env, platform):
    _setup(env)
    module = importlib.import_module(f"lifesmart.{platform}")
    added: list = []
    asyncio.run(module.async_setup_entry(env.hass, env.entry, added.extend))
    assert added, f"{platform} created no entities for the test devices"
    sub_devices = 0
    for entity in added:
        info = _device_info(entity)
        if info["identifiers"] == {HUB_IDENTIFIER}:
            assert "via_device_id" not in info  # hub-level sensors
        else:
            assert info["via_device_id"] == HUB_REGISTRY_ID
            sub_devices += 1
    assert sub_devices


# --- R23: entry functions return None -------------------------------------------

def test_migrate_entry_returns_none(env):
    assert asyncio.run(lifesmart.async_migrate_entry(env.hass, env.entry)) is None


def test_unload_uses_the_raising_helper_and_cleans_up(env):
    _setup(env)
    api = env.apis[0]
    assert asyncio.run(lifesmart.async_unload_entry(env.hass, env.entry)) is None
    assert env.hass.config_entries.unloaded == PLATFORMS
    assert env.issues.unsub_calls == 1
    assert api.stopped
    assert DOMAIN not in env.hass.data


def test_failed_unload_propagates_and_keeps_the_entry(env):
    _setup(env)
    api = env.apis[0]
    env.hass.config_entries.unload_error = RuntimeError("platform failed to unload")
    with pytest.raises(RuntimeError):
        asyncio.run(lifesmart.async_unload_entry(env.hass, env.entry))
    assert env.entry.entry_id in env.hass.data[DOMAIN]["entries"]
    assert not api.stopped
    assert env.issues.unsub_calls == 0


# --- R23: repair issues are linked to the entry ---------------------------------

def test_hub_version_issue_is_linked_to_the_entry(env, monkeypatch):
    monkeypatch.setattr(FakeAPI, "get_hub_version",
                        lambda self: asyncio.sleep(0, {"code": 1}))
    _setup(env)
    (issue_id, kw), = env.issues.created
    assert issue_id == "hub_version_unknown_entry1"
    assert kw["config_entry_id"] == "entry1"
    assert kw["translation_key"] == "hub_version_unknown"


def test_hub_unreachable_issue_is_linked_and_survives_unload(env):
    _setup(env)
    api = env.apis[0]
    api.notify_error = TimeoutError()
    for now in (0.0, 300.0):
        env.issues.clock[0] = now
        asyncio.run(env.issues.timer(None))
    (issue_id, kw), = env.issues.created
    assert issue_id == "hub_unreachable_entry1"
    assert kw["config_entry_id"] == "entry1"
    assert kw["translation_placeholders"] == {"host": HOST, "minutes": "5"}

    deleted_before_unload = list(env.issues.deleted)
    asyncio.run(lifesmart.async_unload_entry(env.hass, env.entry))
    # Deleting on unload would revive an ignored issue after a reload.
    assert env.issues.deleted == deleted_before_unload
