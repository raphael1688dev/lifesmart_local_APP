"""R28 (2026-11-10) self-review fixes.

1. Request signature: booleans and nested objects (LI §3.2.1).
2. A NOTIFY must never be taken for the reply to a pending request (LI §4.1).
3. No deprecated device-registry API (the fakes no longer offer it).
4. A silent hub: the form, setup and the switch command path wait no longer
   than before R25's resends.
5. Actions are registered in async_setup.
"""
import asyncio
import hashlib
import json
import struct
from types import SimpleNamespace

import pytest

import lifesmart
import lifesmart.config_flow as config_flow
from lifesmart.api import DEFAULT_GET_RETRIES, LifeSmartAPI
from lifesmart.const import CMD_GET, CMD_GET_REPLY, CMD_NOTIFY, CMD_SET, DOMAIN
from lifesmart.switch import LifeSmartSwitch

from .fakes import AGT, DEVICES, HOST, FakeAPI, FakeDeviceRegistry, runtime, make_env, setup

ServiceValidationError = lifesmart.ServiceValidationError


@pytest.fixture
def env(monkeypatch):
    return make_env(monkeypatch)


# --- 1. signature ---------------------------------------------------------------

def _base_string(monkeypatch, obj, args):
    seen: dict = {}
    real = hashlib.md5

    def spy(data):
        seen["base"] = data.decode()
        return real(data)
    monkeypatch.setattr(hashlib, "md5", spy)
    LifeSmartAPI("h", "OD_XXX_XXX", "token1")._create_signature(obj, args, 1571976095)
    return seen["base"]


def test_signature_matches_the_spec_example(monkeypatch):
    """LI §3.2.1 "Original signature string"."""
    base = _base_string(monkeypatch, "ep", {"tag": "m", "me": "80fa", "idx": "L1", "type": 128, "val": 0})
    assert base == "obj:ep,idx:L1,me:80fa,tag:m,type:128,val:0,ts:1571976095,model:OD_XXX_XXX,token:token1"


def test_signature_writes_booleans_as_json(monkeypatch):
    """cfg:timezone always carries `summer`; str(False) is 'False'."""
    base = _base_string(monkeypatch, "config", {"cfg": "timezone", "timezone": 8, "summer": False})
    assert base.startswith("obj:config,cfg:timezone,summer:false,timezone:8,ts:")
    base = _base_string(monkeypatch, "config", {"cfg": "upgrade", "reboot": True})
    assert ",reboot:true," in base
    assert "True" not in base and "False" not in base


def test_signature_leaves_out_nested_objects_and_lists(monkeypatch):
    """doscene's `args` object used to be signed as Python's `{'type': 128}`."""
    base = _base_string(monkeypatch, "doscene", {"id": "AI1", "args": {"type": 128}, "keys": ["a"]})
    assert base == "obj:doscene,id:AI1,ts:1571976095,model:OD_XXX_XXX,token:token1"


# --- 2. NOTIFY vs pending requests ---------------------------------------------

def _datagram(pkg_type, body):
    raw = json.dumps(body).encode()
    return struct.pack(">2sHHI", b"JL", 0, pkg_type, len(raw)) + raw


def _api_with_pending(msg_id):
    api = LifeSmartAPI("h", "m", "t")
    future = asyncio.get_running_loop().create_future()
    api._pending[msg_id] = future
    return api, future


def test_notify_with_a_pending_id_is_an_event_not_a_reply():
    async def run():
        api, future = _api_with_pending(7)
        got: list = []
        api.register_state_listener("2711", "L1", got.append)
        api._handle_datagram(_datagram(CMD_NOTIFY, {"id": 7, "chg": [{"me": "2711", "L1": {"v": 1}}]}))
        return future.done(), got
    assert asyncio.run(run()) == (False, [1])


@pytest.mark.parametrize("pkg_type", [CMD_GET_REPLY, 4])  # GET-REPLY, SET-REPLY (LI §3.1)
def test_replies_still_resolve_their_request(pkg_type):
    async def run():
        api, future = _api_with_pending(7)
        api._handle_datagram(_datagram(pkg_type, {"id": 7, "code": 0, "msg": {}}))
        return future.result()
    assert asyncio.run(run()) == {"id": 7, "code": 0, "msg": {}}


# --- 3. device registry API ------------------------------------------------------

def test_fakes_offer_no_deprecated_registry_api(env):
    """The guard itself: R25 shipped async_get_device(identifiers=…) and
    DeviceEntry.config_entries because the old fakes had them."""
    assert not hasattr(FakeDeviceRegistry, "async_get_device")
    device = env.dev_reg.add("d", {(DOMAIN, "2711")}, "entry1")
    assert not hasattr(device, "config_entries")


def test_migration_only_looks_at_this_entry(env):
    """Another entry's hub device with the same old identifier is not touched."""
    env.dev_reg.add("foreign-hub", {(DOMAIN, f"hub_{HOST}")}, "other-entry")
    env.dev_reg.add("my-hub", {(DOMAIN, f"hub_{HOST}")}, "entry1")
    setup(env)
    assert env.dev_reg.devices["foreign-hub"].identifiers == {(DOMAIN, f"hub_{HOST}")}
    assert env.dev_reg.devices["my-hub"].identifiers == {(DOMAIN, f"hub_{AGT}")}


# --- 4. waits on a silent hub ------------------------------------------------------

def test_form_waits_ten_seconds_at_most():
    assert config_flow.FLOW_TIMEOUT * (DEFAULT_GET_RETRIES + 1) <= 10


def test_setup_does_not_wait_for_the_time_zone(env, monkeypatch):
    asked: list = []

    async def slow_timezone(self):
        asked.append(True)
        return {"code": 0, "msg": {"timezone": 8, "summer": False}}
    monkeypatch.setattr(FakeAPI, "get_hub_timezone", slow_timezone)
    setup(env, run_background=False)
    assert asked == []                                   # setup finished without it
    assert "timezone" not in runtime(env).hub_info
    (task,) = env.entry.background                       # read afterwards, in the background
    asyncio.run(task)
    assert asked == [True]
    assert runtime(env).hub_info["timezone"] == 8  # listeners were told


def test_unreadable_time_zone_changes_nothing(env, monkeypatch):
    monkeypatch.setattr(FakeAPI, "get_hub_timezone", lambda self: asyncio.sleep(0, {"code": 1}))
    setup(env)
    assert "timezone" not in runtime(env).hub_info
    assert runtime(env).hub_info["ver"] == "1.0.5p3"


def test_switch_read_back_in_the_command_path_is_not_resent():
    calls: list = []

    class Api:
        async def send_command(self, obj, args, pkg_type, timeout=None, retries=None):
            calls.append((pkg_type, retries))
            return {"code": 5} if pkg_type == CMD_SET else {"code": 0, "msg": {"data": {"L1": {"v": 1}}}}

    switch = LifeSmartSwitch(Api(), DEVICES[0], "L1", "L1")
    switch.entity_id = "switch.x"
    switch.async_write_ha_state = lambda: None
    asyncio.run(switch._send_command(1))
    assert calls == [(CMD_SET, None), (CMD_GET, 0)]
    calls.clear()
    asyncio.run(switch._async_update_state())            # at add time: default resend
    assert calls == [(CMD_GET, None)]


# --- 5. actions in async_setup -------------------------------------------------------

def test_actions_are_registered_by_async_setup(env):
    assert asyncio.run(lifesmart.async_setup(env.hass, {})) is True
    assert set(env.hass.services.handlers) == {
        "send_keys", "set_hub_timezone", "rename_device",
        "upgrade_hub_firmware", "factory_reset_hub",
    }


def test_setup_entry_registers_no_actions(env):
    asyncio.run(lifesmart.async_setup_entry(env.hass, env.entry))
    for coro in env.entry.background:
        coro.close()  # the background time zone read; not this test's subject
    assert env.hass.services.handlers == {}


def test_action_says_so_when_the_hub_entry_is_not_loaded(env):
    """The point of the move: the action exists and explains itself."""
    asyncio.run(lifesmart.async_setup(env.hass, {}))
    handler = env.hass.services.handlers["set_hub_timezone"]
    call = SimpleNamespace(data={"config_entry_id": "entry1", "timezone": 8, "daylight_saving": False})
    with pytest.raises(ServiceValidationError):
        asyncio.run(handler(call))


# --- R30: coordinators get their config entry explicitly ----------------------------

def test_coordinators_are_given_the_config_entry(env):
    """Not relying on HA's ContextVar fallback (reported as an error for core
    integrations, tolerated for custom ones)."""
    setup(env)
    data = runtime(env)
    assert data.coordinator.config_entry is env.entry
    assert data.hub_coordinator.config_entry is env.entry

