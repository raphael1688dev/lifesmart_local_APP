"""R30 (2026-11-11): lifesmart.send_keys with several hubs.

Before R30 the action sent every key to every loaded hub, ignored the hubs'
answers, and did nothing — without an error — when no hub was loaded. It had
no test at all.
"""
import asyncio
from types import SimpleNamespace

import pytest

import lifesmart
from lifesmart.remote import async_setup_entry as remote_setup

from .fakes import FakeAPI, loaded_hub, make_env, runtime, setup, unload

ServiceValidationError = lifesmart.ServiceValidationError
HomeAssistantError = lifesmart.HomeAssistantError


@pytest.fixture
def env(monkeypatch):
    return make_env(monkeypatch)


def _hub(env, entry_id, reply, remote_ids=()):
    """One more loaded hub; returns its API to inspect."""
    api = FakeAPI()
    api.reply = reply
    loaded_hub(env, entry_id, api, remote_ids)
    return api


def _send(env, **data):
    asyncio.run(lifesmart.async_setup(env.hass, {}))
    call = SimpleNamespace(data={"remote_id": "R1", "keys": "power", **data})
    return asyncio.run(env.hass.services.handlers["send_keys"](call))


def _sent(api):
    return [c for c in api.calls if c[0] == "send_remote_key"]


def test_no_hub_loaded_is_an_error(env):
    with pytest.raises(ServiceValidationError):
        _send(env)


def test_key_goes_only_to_the_hub_that_has_the_remote(env):
    other, owner = _hub(env, "a", {"code": 0}, {"R9"}), _hub(env, "b", {"code": 0}, {"R1"})
    _send(env, keys=["power", "vol_up"])
    assert _sent(owner) == [("send_remote_key", "R1", "power"), ("send_remote_key", "R1", "vol_up")]
    assert _sent(other) == []


def test_unknown_remote_is_tried_on_every_hub(env):
    """A remote added in the app after setup is in no hub's list yet."""
    rejects, accepts = _hub(env, "a", {"code": 10004}), _hub(env, "b", {"code": 0})
    _send(env)
    assert len(_sent(rejects)) == 1 and len(_sent(accepts)) == 1


def test_error_when_no_hub_accepts_the_key(env):
    _hub(env, "a", {"code": 10004}, {"R1"})
    with pytest.raises(HomeAssistantError):
        _send(env)


def test_silent_hub_is_an_error_not_a_success(env):
    _hub(env, "a", asyncio.TimeoutError(), {"R1"})
    with pytest.raises(HomeAssistantError):
        _send(env)


def test_one_silent_hub_does_not_fail_a_key_another_hub_sent(env):
    _hub(env, "a", asyncio.TimeoutError())
    _hub(env, "b", {"code": 0})
    _send(env)  # no error


def test_config_entry_id_picks_the_hub(env):
    setup(env)
    other = _hub(env, "other", {"code": 0}, {"R1"})
    _send(env, config_entry_id="entry1")
    assert [c for c in env.apis[0].calls if c[0] == "send_remote_key"] == [("send_remote_key", "R1", "power")]
    assert _sent(other) == []


def test_config_entry_id_of_an_unknown_hub_is_refused(env):
    _hub(env, "a", {"code": 0}, {"R1"})
    with pytest.raises(ServiceValidationError):
        _send(env, config_entry_id="nope")


def test_an_unloaded_hub_is_not_sent_to(env):
    """R32: "loaded" is the entry's state, as Home Assistant tracks it. The
    entry in make_env exists but was never set up; a hub that was unloaded
    is the same."""
    with pytest.raises(ServiceValidationError):
        _send(env, config_entry_id="entry1")
    setup(env)
    unload(env)
    with pytest.raises(ServiceValidationError):
        _send(env, config_entry_id="entry1")
    with pytest.raises(ServiceValidationError):
        _send(env)
    assert _sent(env.apis[0]) == []


def test_another_integrations_entry_is_refused(env):
    api = FakeAPI()
    loaded_hub(env, "foreign", api, {"R1"}).domain = "mqtt"
    with pytest.raises(ServiceValidationError):
        _send(env, config_entry_id="foreign")
    with pytest.raises(ServiceValidationError):
        _send(env)
    assert _sent(api) == []


def test_remote_setup_records_which_remotes_the_hub_has(env, monkeypatch):
    async def remote_list(self):
        return [{"remote": {"id": "AI_IR_2713_1"}, "keys": {}}, {"remote": {"id": "AI_IR_2713_2"}, "keys": {}}]
    monkeypatch.setattr(FakeAPI, "get_remote_list", remote_list)
    setup(env)
    asyncio.run(remote_setup(env.hass, env.entry, lambda entities: None))
    assert runtime(env).remote_ids == {"AI_IR_2713_1", "AI_IR_2713_2"}
