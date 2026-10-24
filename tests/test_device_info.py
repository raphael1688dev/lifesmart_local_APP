"""Tests for lifesmart.device_info (R19, 2026-10-24).

Background: HA 2026.11 turns DeviceInfo into a dataclass. Item assignment
(`info["x"] = ...`) survives through a compatibility layer that HA has said
it will deprecate and remove; attribute assignment is not available on the
dict-based DeviceInfo of HA <= 2026.10. The helpers therefore build every
field as a constructor kwarg and never mutate the result — which also makes
the field logic a pure function we can test here without HA.
"""
import pytest

import lifesmart.device_info as di
from lifesmart.const import DOMAIN, HUB_MODEL_NAMES, MANUFACTURER
from lifesmart.device_info import (
    DEFAULT_HUB_MODEL,
    DEFAULT_HUB_NAME,
    hub_device_info,
    hub_device_info_kwargs,
    sub_device_info,
    sub_device_info_kwargs,
)

DEVICE = {
    "me": "2711",
    "agt": "A3EAAABtAEwQRzM0NzA2NQ",
    "name": "Kitchen",
    "devtype": "SL_SW_ND1",
    "epver": "0.0.2",
    "stat": 1,
    "lDbm": -61,
    "data": {"L1": {"type": 129, "v": 1}},
}
HUB_INFO = {"ver": "1.0.5p3", "osver": "4.9.253", "mgatype": "LSJZX1K"}


# --- sub-device ----------------------------------------------------------------

def test_sub_device_all_fields():
    assert sub_device_info_kwargs(DEVICE, "hub-registry-id") == {
        "identifiers": {(DOMAIN, "2711")},
        "name": "Kitchen",
        "manufacturer": MANUFACTURER,
        "model": "SL_SW_ND1",
        "sw_version": "0.0.2",
        "via_device_id": "hub-registry-id",
    }


@pytest.mark.parametrize("hub_device_id", [None, ""])
def test_sub_device_without_hub_has_no_via_device_id(hub_device_id):
    """D22: only link when we actually have the hub's registry id. A None
    via_device_id would *remove* an existing link on the dataclass DeviceInfo."""
    assert "via_device_id" not in sub_device_info_kwargs(DEVICE, hub_device_id)


def test_sub_device_missing_epver_omits_sw_version():
    """Omitted, not None (would wipe) and not "Unknown" (pre-R19 behaviour)."""
    device = {k: v for k, v in DEVICE.items() if k != "epver"}
    assert "sw_version" not in sub_device_info_kwargs(device)


def test_sub_device_epver_is_coerced_to_str():
    """HA `_validate_str` rejects non-str sw_version from 2026.12.0 (R18)."""
    assert sub_device_info_kwargs({**DEVICE, "epver": 2})["sw_version"] == "2"


def test_sub_device_explicit_name_wins():
    assert sub_device_info_kwargs(DEVICE, name="Living room curtain")["name"] == "Living room curtain"


def test_sub_device_defaults_when_firmware_fields_missing():
    bare = {"me": "2711"}
    kwargs = sub_device_info_kwargs(bare, default_name="LifeSmart Switch", default_model="SL_P")
    assert kwargs["name"] == "LifeSmart Switch"
    assert kwargs["model"] == "SL_P"
    assert sub_device_info_kwargs(bare)["name"] == "LifeSmart Device"
    assert sub_device_info_kwargs(bare)["model"] == "Unknown"


def test_sub_device_empty_name_falls_back():
    assert sub_device_info_kwargs({**DEVICE, "name": ""})["name"] == "LifeSmart Device"


def test_sub_device_requires_me():
    """Callers (sensor.py) catch KeyError, log and skip — keep that contract."""
    with pytest.raises(KeyError):
        sub_device_info_kwargs({"name": "no id"})


# --- hub -------------------------------------------------------------------------

def test_hub_all_fields():
    assert hub_device_info_kwargs("192.168.1.50", "My hub", HUB_INFO) == {
        "identifiers": {(DOMAIN, "hub_192.168.1.50")},
        "name": "My hub",
        "manufacturer": MANUFACTURER,
        "model": HUB_MODEL_NAMES["LSJZX1K"],
        "sw_version": "1.0.5p3",
    }


@pytest.mark.parametrize("title", [None, ""])
def test_hub_title_fallback(title):
    assert hub_device_info_kwargs("h", title, HUB_INFO)["name"] == DEFAULT_HUB_NAME


def test_hub_unknown_mgatype_passes_raw_value():
    assert hub_device_info_kwargs("h", "t", {**HUB_INFO, "mgatype": "LSXYZ9"})["model"] == "LSXYZ9"


def test_hub_missing_mgatype_uses_default_model():
    """cfg:getver failed (D17 raises a repair issue) — still a valid device."""
    assert hub_device_info_kwargs("h", "t", {})["model"] == DEFAULT_HUB_MODEL


def test_hub_missing_ver_omits_sw_version():
    """R17: None would wipe the version stored on a previous boot."""
    assert "sw_version" not in hub_device_info_kwargs("h", "t", {"mgatype": "LSJZX1K"})


def test_hub_ver_is_coerced_to_str():
    """R18: LI §3.3.10 gives no type for `ver`; HA rejects non-str from 2026.12.0."""
    assert hub_device_info_kwargs("h", "t", {"ver": 105})["sw_version"] == "105"


def test_hub_kwargs_carry_no_registry_only_keys():
    """config_entry_id is added by __init__.py's registry call only — on the
    dataclass DeviceInfo an unknown key raises KeyError/TypeError."""
    assert "config_entry_id" not in hub_device_info_kwargs("h", "t", HUB_INFO)


# --- the R19 contract: constructor kwargs only, never item assignment -------------

class _StrictDeviceInfo:
    """What DeviceInfo looks like once HA removes the dict compatibility layer:
    keyword-only construction, attribute reads, no `[]`."""

    def __init__(self, **fields):
        self.__dict__.update(fields)

    def __setitem__(self, key, value):  # pragma: no cover - must never run
        raise TypeError("DeviceInfo does not support item assignment")

    def __getitem__(self, key):  # pragma: no cover - must never run
        raise TypeError("DeviceInfo does not support item access")


def test_builders_never_mutate_device_info(monkeypatch):
    monkeypatch.setattr(di, "DeviceInfo", _StrictDeviceInfo)

    info = sub_device_info(DEVICE, "hub-registry-id")
    assert info.identifiers == {(DOMAIN, "2711")}
    assert info.via_device_id == "hub-registry-id"
    assert info.sw_version == "0.0.2"

    hub = hub_device_info("192.168.1.50", None, {"ver": 1, "mgatype": "LSNAMIV3"})
    assert hub.name == DEFAULT_HUB_NAME
    assert hub.model == HUB_MODEL_NAMES["LSNAMIV3"]
    assert hub.sw_version == "1"


def test_builders_equal_kwargs_form():
    """The three hub callers (registry / sensor / button) must agree."""
    assert hub_device_info("h", "t", HUB_INFO) == di.DeviceInfo(**hub_device_info_kwargs("h", "t", HUB_INFO))
    assert sub_device_info(DEVICE, "x") == di.DeviceInfo(**sub_device_info_kwargs(DEVICE, "x"))
