"""Translations must match what the code actually uses (R19, 2026-10-24).

Two gaps this would have caught: `issues.hub_unreachable` was translated in
2026-05 but never raised, and `options.step.init` stayed translated for an
options flow whose value nothing read. Source is scanned as text so the test
needs no HA runtime.
"""
import json
import re
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent / "custom_components" / "lifesmart"
LANGS = ["en.json", "zh-Hant.json", "zh-Hans.json"]
SOURCE = "\n".join(p.read_text() for p in PKG.glob("*.py"))


def _load(name):
    return json.loads((PKG / "translations" / name).read_text())


def _issue_keys_in_code():
    return set(re.findall(r'translation_key="([a-z_]+)"', SOURCE))


@pytest.mark.parametrize("lang", LANGS)
def test_every_raised_issue_is_translated(lang):
    assert _issue_keys_in_code() <= set(_load(lang).get("issues", {}))


@pytest.mark.parametrize("lang", LANGS)
def test_every_translated_issue_is_raised(lang):
    assert set(_load(lang).get("issues", {})) <= _issue_keys_in_code()


@pytest.mark.parametrize("lang", LANGS)
def test_issue_placeholders_match_english(lang):
    en, other = _load("en.json")["issues"], _load(lang)["issues"]
    ph = lambda s: set(re.findall(r"\{(\w+)\}", s))
    for key, val in en.items():
        assert ph(other[key]["description"]) == ph(val["description"]), key


def test_hub_unreachable_placeholders_are_passed():
    assert ph_in_code("hub_unreachable") == {"host", "minutes"}


def ph_in_code(key):
    block = SOURCE[SOURCE.index(f'translation_key="{key}"'):]
    block = block[: block.index(")")]
    return set(re.findall(r'"(\w+)":', block))


@pytest.mark.parametrize("lang", LANGS)
def test_no_options_flow_translations(lang):
    assert "options" not in _load(lang)


@pytest.mark.parametrize("lang", LANGS)
def test_same_keys_in_every_language(lang):
    def flat(d, prefix=""):
        out = set()
        for k, v in d.items():
            out |= flat(v, f"{prefix}{k}.") if isinstance(v, dict) else {prefix + k}
        return out
    assert flat(_load(lang)) == flat(_load("en.json"))


def test_config_flow_has_no_options_flow():
    from lifesmart.config_flow import LifeSmartConfigFlow
    import lifesmart.config_flow as cf
    # Real HA's ConfigFlow base defines async_get_options_flow and offers the
    # Configure button only when a subclass overrides it — check our class's
    # own namespace, not hasattr (which would see the base method).
    assert "async_get_options_flow" not in LifeSmartConfigFlow.__dict__
    assert not hasattr(cf, "LifeSmartOptionsFlowHandler")
