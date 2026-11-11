"""Checks tied to Home Assistant's integration quality scale (R32, 2026-11-11).

HA validates these rules only for core integrations. PROGRESS.md R31 has the
rule-by-rule comparison; each test here pins one rule so it stays met.
"""
import ast
import asyncio
import importlib
import inspect
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from lifesmart import diagnostics
from lifesmart.const import DOMAIN, PLATFORMS
from lifesmart.entity import LifeSmartEntity
from lifesmart.models import LifeSmartConfigEntry, LifeSmartData

from .fakes import AGT, HOST, HUB_REGISTRY_ID, make_env, runtime, setup, unload

PKG = Path(__file__).resolve().parent.parent / "custom_components" / "lifesmart"
README = (PKG.parent.parent / "README.md").read_text(encoding="utf-8")
LANGS = ["en.json", "zh-Hant.json", "zh-Hans.json"]


@pytest.mark.parametrize("platform", PLATFORMS)
def test_parallel_updates_is_set_explicitly(platform):
    """parallel-updates: every entity platform states its limit."""
    module = importlib.import_module(f"lifesmart.{platform}")
    assert module.PARALLEL_UPDATES == 0


def test_every_entity_class_uses_has_entity_name():
    """has-entity-name: no entity class left without it."""
    missing = []
    for platform in PLATFORMS:
        module = importlib.import_module(f"lifesmart.{platform}")
        for name, obj in vars(module).items():
            if (
                isinstance(obj, type)
                and obj.__module__ == module.__name__
                and name.startswith("LifeSmart")
                and getattr(obj, "_attr_has_entity_name", False) is not True
            ):
                missing.append(f"{platform}.{name}")
    assert missing == []


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("step", ["user", "reconfigure", "reauth_confirm"])
def test_every_config_field_is_described(lang, step):
    """config-flow: `data_description` gives context for each input field."""
    form = json.loads((PKG / "translations" / lang).read_text(encoding="utf-8"))["config"]["step"][step]
    assert set(form["data_description"]) == set(form["data"])
    assert all(form["data_description"].values())


@pytest.mark.parametrize("heading", [
    "Removing the integration",   # docs-removal-instructions
    "How data is updated",        # docs-data-update
    "Use cases",                  # docs-use-cases
    "Examples",                   # docs-examples
    "Hub actions",                # docs-actions
    "Supported devices",          # docs-supported-devices
    "Known limitations",          # docs-known-limitations
    "Troubleshooting",            # docs-troubleshooting
])
def test_readme_has_the_section(heading):
    assert re.search(rf"^## {re.escape(heading)}$", README, flags=re.M)


def test_readme_links_to_the_brand():
    """docs-high-level-description: a link to the product's website."""
    assert "https://ilifesmart.com" in README


def test_readme_states_the_polling_intervals():
    """docs-data-update: say how often, not only "a slow poll"."""
    section = README.split("## How data is updated", 1)[1].split("\n## ", 1)[0]
    assert "15 minutes" in section and "90 seconds" in section and "once a day" in section
    # ...and the numbers in the README are the ones in the code.
    from datetime import timedelta
    from lifesmart.coordinator import DEFAULT_UPDATE_INTERVAL, HUB_INFO_UPDATE_INTERVAL
    assert DEFAULT_UPDATE_INTERVAL == timedelta(minutes=15)
    assert HUB_INFO_UPDATE_INTERVAL == timedelta(days=1)
    assert "timedelta(seconds=90)" in (PKG / "__init__.py").read_text(encoding="utf-8")


# --- runtime-data (R32 step 2) --------------------------------------------------

@pytest.fixture
def env(monkeypatch):
    return make_env(monkeypatch)


def test_nothing_is_kept_in_hass_data():
    """runtime-data: no `hass.data` / `self.hass.data` anywhere in the code."""
    hits = []
    for path in sorted(PKG.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Attribute) and node.attr == "data"):
                continue
            owner = node.value
            name = owner.id if isinstance(owner, ast.Name) else getattr(owner, "attr", None)
            if name == "hass":
                hits.append(f"{path.name}:{node.lineno}")
    assert hits == []


def test_setup_puts_typed_runtime_data_on_the_entry(env):
    setup(env)
    data = runtime(env)
    assert isinstance(data, LifeSmartData)
    assert data.api is env.apis[0]
    assert (data.host, data.hub_key, data.hub_device_id) == (HOST, AGT, HUB_REGISTRY_ID)
    assert env.hass.data == {}


def test_unload_runs_every_unsub_and_stops_the_api(env):
    """Unload no longer pops a dict: it must still release everything."""
    setup(env)
    data = runtime(env)
    called = []
    data.unsubs.append(lambda: called.append("extra"))
    unload(env)
    assert called == ["extra"]
    assert env.issues.unsub_calls == 1   # the 90 s notify timer
    assert env.apis[0].report_listeners == []
    assert env.apis[0].stopped


@pytest.mark.parametrize("platform", PLATFORMS)
def test_platform_setup_takes_the_typed_entry(platform):
    """runtime-data: the typed `LifeSmartConfigEntry` is used throughout."""
    module = importlib.import_module(f"lifesmart.{platform}")
    hints = inspect.get_annotations(module.async_setup_entry, eval_str=True)
    assert hints["config_entry"] is LifeSmartConfigEntry


def test_diagnostics_of_a_loaded_entry(env):
    setup(env)
    result = asyncio.run(diagnostics.async_get_config_entry_diagnostics(env.hass, env.entry))
    assert result["host"] == HOST
    assert result["device_count"] == 4
    assert result["hub_info"]["mgatype"] == "LSJZX1K"
    assert result["entry"]["data"]["token"] == "**REDACTED**"


def test_diagnostics_of_an_entry_that_is_not_loaded(env):
    """Downloadable for an entry whose setup failed: no runtime_data then."""
    result = asyncio.run(diagnostics.async_get_config_entry_diagnostics(env.hass, env.entry))
    assert (result["host"], result["device_count"], result["hub_info"]) == ("", 0, {})
    assert result["entry"]["data"]["token"] == "**REDACTED**"
    hub = SimpleNamespace(identifiers={(DOMAIN, f"hub_{AGT}")})
    result = asyncio.run(diagnostics.async_get_device_diagnostics(env.hass, env.entry, hub))
    assert result == {"device_type": "hub", "host": "", "hub_info": {}, "device_count": 0}


def test_device_diagnostics(env):
    setup(env)
    hub = SimpleNamespace(identifiers={(DOMAIN, f"hub_{AGT}")})
    result = asyncio.run(diagnostics.async_get_device_diagnostics(env.hass, env.entry, hub))
    assert result["device_type"] == "hub" and result["host"] == HOST and result["device_count"] == 4
    sub = SimpleNamespace(identifiers={(DOMAIN, "2711")})
    result = asyncio.run(diagnostics.async_get_device_diagnostics(env.hass, env.entry, sub))
    assert result["device_type"] == "sub_device" and result["payload"]["name"] == "Kitchen"
    gone = SimpleNamespace(identifiers={(DOMAIN, "9999")})
    result = asyncio.run(diagnostics.async_get_device_diagnostics(env.hass, env.entry, gone))
    assert result["device_identifier"] == "9999"


# --- common-modules / entity-unavailable (R32 step 3) -----------------------------

def test_every_entity_class_derives_from_the_base_entity():
    """common-modules: one base entity, in entity.py. It also carries
    `available`, so no platform can forget entity-unavailable."""
    assert (PKG / "entity.py").exists() and (PKG / "coordinator.py").exists()
    strays = []
    for platform in PLATFORMS:
        module = importlib.import_module(f"lifesmart.{platform}")
        for name, obj in vars(module).items():
            if (
                isinstance(obj, type)
                and obj.__module__ == module.__name__
                and name.startswith("LifeSmart")
                and not issubclass(obj, LifeSmartEntity)
            ):
                strays.append(f"{platform}.{name}")
    assert strays == []


def test_readme_says_when_entities_are_unavailable():
    """docs-data-update / docs-troubleshooting: the behaviour is documented."""
    update = README.split("## How data is updated", 1)[1].split("\n## ", 1)[0]
    assert "Unavailable" in update and "two renewals in a row" in update
    trouble = README.split("## Troubleshooting", 1)[1].split("\n## ", 1)[0]
    assert 'Every entity of a hub shows "Unavailable"' in trouble
    limits = README.split("## Known limitations", 1)[1].split("\n## ", 1)[0]
    assert "not verified on hardware" in limits and "`stat`" in limits
