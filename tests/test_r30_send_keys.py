"""R30 (2026-11-11): lifesmart.send_keys with several hubs.

Before R30 the action sent every key to every loaded hub, ignored the hubs'
answers, and did nothing — without an error — when no hub was loaded. It had
no test at all.
"""
import asyncio
from types import SimpleNamespace

import pytest

import lifesmart
from lifesmart.const import DOMAIN
from lifesmart.remote import async_setup_entry as remote_setup

from .fakes import FakeAPI, entry_data, make_env, setup

ServiceValidationError = lifesmart.ServiceValidationError
HomeAssistantError = lifesmart.HomeAssistantError


@pytest.fixture
def env(monkeypatch):
    return make_env(monkeypatch)


def _hub(reply, remote_ids=()):
    api = FakeAPI()
    api.reply = reply
    return {"api": api, "remote_ids": set(remote_ids)}


def _send(env, **data):
    asyncio.run(lifesmart.async_setup(env.hass, {}))
    call = SimpleNamespace(data={"remote_id": "R1", "keys": "power", **data})
    return asyncio.run(env.hass.services.handlers["send_keys"](call))


def _sent(hub):
    return [c for c in hub["api"].calls if c[0] == "send_remote_key"]


def test_no_hub_loaded_is_an_error(env):
    with pytest.raises(ServiceValidationError):
        _send(env)


def test_key_goes_only_to_the_hub_that_has_the_remote(env):
    owner, other = _hub({"code": 0}, {"R1"}), _hub({"code": 0}, {"R9"})
    env.hass.data[DOMAIN] = {"entries": {"a": other, "b": owner}}
    _send(env, keys=["power", "vol_up"])
    assert _sent(owner) == [("send_remote_key", "R1", "power"), ("send_remote_key", "R1", "vol_up")]
    assert _sent(other) == []


def test_unknown_remote_is_tried_on_every_hub(env):
    """A remote added in the app after setup is in no hub's list yet."""
    rejects, accepts = _hub({"code": 10004}), _hub({"code": 0})
    env.hass.data[DOMAIN] = {"entries": {"a": rejects, "b": accepts}}
    _send(env)
    assert len(_sent(rejects)) == 1 and len(_sent(accepts)) == 1


def test_error_when_no_hub_accepts_the_key(env):
    env.hass.data[DOMAIN] = {"entries": {"a": _hub({"code": 10004}, {"R1"})}}
    with pytest.raises(HomeAssistantError):
        _send(env)


def test_silent_hub_is_an_error_not_a_success(env):
    env.hass.data[DOMAIN] = {"entries": {"a": _hub(asyncio.TimeoutError(), {"R1"})}}
    with pytest.raises(HomeAssistantError):
        _send(env)


def test_one_silent_hub_does_not_fail_a_key_another_hub_sent(env):
    silent, accepts = _hub(asyncio.TimeoutError()), _hub({"code": 0})
    env.hass.data[DOMAIN] = {"entries": {"a": silent, "b": accepts}}
    _send(env)  # no error


def test_config_entry_id_picks_the_hub(env):
    setup(env)
    other = _hub({"code": 0}, {"R1"})
    env.hass.data[DOMAIN]["entries"]["other"] = other
    _send(env, config_entry_id="entry1")
    assert [c for c in env.apis[0].calls if c[0] == "send_remote_key"] == [("send_remote_key", "R1", "power")]
    assert _sent(other) == []


def test_config_entry_id_of_an_unloaded_hub_is_refused(env):
    env.hass.data[DOMAIN] = {"entries": {"a": _hub({"code": 0}, {"R1"})}}
    with pytest.raises(ServiceValidationError):
        _send(env, config_entry_id="nope")


def test_remote_setup_records_which_remotes_the_hub_has(env, monkeypatch):
    async def remote_list(self):
        return [{"remote": {"id": "AI_IR_2713_1"}, "keys": {}}, {"remote": {"id": "AI_IR_2713_2"}, "keys": {}}]
    monkeypatch.setattr(FakeAPI, "get_remote_list", remote_list)
    setup(env)
    asyncio.run(remote_setup(env.hass, env.entry, lambda entities: None))
    assert entry_data(env)["remote_ids"] == {"AI_IR_2713_1", "AI_IR_2713_2"}
