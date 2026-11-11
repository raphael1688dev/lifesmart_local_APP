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

import pytest

import lifesmart
from lifesmart.const import DOMAIN, PLATFORMS
from lifesmart.device_info import hub_device_info_kwargs

from .fakes import (
    AGT,
    GOOD_TIMEZONE,
    GOOD_VERSION,
    HOST,
    HUB_REGISTRY_ID,
    FakeAPI,
    device_info as _device_info,
    runtime as _runtime,
    make_env,
    setup as _setup,
)

# R25 (D21): the hub device is keyed on the hub ID the sub-devices report.
HUB_IDENTIFIER = (DOMAIN, f"hub_{AGT}")


@pytest.fixture
def env(monkeypatch):
    return make_env(monkeypatch)


# --- hub device (R17 #4) -------------------------------------------------------

def test_setup_registers_hub_device_before_forwarding_platforms(env):
    _setup(env)
    assert env.log == ["hub_device", "forward"]
    assert env.hass.config_entries.forwarded == PLATFORMS
    (call,) = env.dev_reg.calls
    assert call == {
        "config_entry_id": "entry1",
        **hub_device_info_kwargs(
            AGT, "Living room hub", {**GOOD_VERSION["msg"], **GOOD_TIMEZONE["msg"]}
        ),
    }
    assert call["identifiers"] == {HUB_IDENTIFIER}
    assert "via_device_id" not in call  # the hub is a top-level device
    assert _runtime(env).hub_device_id == HUB_REGISTRY_ID


@pytest.mark.parametrize("platform", ["switch", "sensor", "binary_sensor", "cover", "remote", "event"])
def test_sub_devices_hang_off_the_hub(env, platform, monkeypatch):
    # R25: a button device so the event platform has something to create.
    monkeypatch.setattr(FakeAPI, "devices", FakeAPI.devices + [
        {"me": "2721", "agt": AGT, "name": "Cube", "devtype": "SL_SC_BB",
         "data": {"B": {"v": 0}, "V": {"v": 60}}},
    ])
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


def test_failed_unload_propagates_and_keeps_the_entry(env):
    _setup(env)
    api = env.apis[0]
    env.hass.config_entries.unload_error = RuntimeError("platform failed to unload")
    with pytest.raises(RuntimeError):
        asyncio.run(lifesmart.async_unload_entry(env.hass, env.entry))
    assert _runtime(env).api is api  # still usable: the entry stays loaded
    assert not api.stopped
    assert env.issues.unsub_calls == 0


# --- R23: repair issues are linked to the entry ---------------------------------

def test_an_unreadable_hub_version_raises_no_repair_issue(env, monkeypatch):
    """R36 (quality scale `repair-issues`): the user cannot act on it, so no
    issue. Up to 20261111r6 this raised `hub_version_unknown`; an issue left
    by such a version is deleted at setup."""
    monkeypatch.setattr(FakeAPI, "get_hub_version",
                        lambda self: asyncio.sleep(0, {"code": 1}))
    _setup(env)
    assert env.issues.created == []
    assert "hub_version_unknown_entry1" in env.issues.deleted
    assert _runtime(env).hub_info["version_ok"] is False   # the sensors show "unknown"


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
