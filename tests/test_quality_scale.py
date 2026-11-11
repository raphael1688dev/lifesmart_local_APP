"""Checks tied to Home Assistant's integration quality scale (R32, 2026-11-11).

HA validates these rules only for core integrations. PROGRESS.md R31 has the
rule-by-rule comparison; each test here pins one rule so it stays met.
"""
import importlib
import json
import re
from pathlib import Path

import pytest

from lifesmart.const import PLATFORMS

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
@pytest.mark.parametrize("step", ["user", "reconfigure"])
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
