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


# --- R31: rules hassfest enforces for core integrations only -----------------------

def _service_names():
    text = (PKG / "services.yaml").read_text()
    return set(re.findall(r"^([a-z_]+):\s*$", text, flags=re.M))


def test_every_action_has_an_icon():
    """hassfest: "Service X has no icon in icons.json" (core only)."""
    icons = json.loads((PKG / "icons.json").read_text())["services"]
    assert set(icons) == _service_names()
    assert all(v["service"].startswith("mdi:") for v in icons.values())


@pytest.mark.parametrize("lang", LANGS)
def test_every_action_is_translated(lang):
    """hassfest: every action and field needs a name and description (core only)."""
    services = _load(lang)["services"]
    assert set(services) == _service_names()
    for name, service in services.items():
        assert service["name"] and service["description"], name
        for field, texts in service["fields"].items():
            assert texts["name"], (name, field)


def test_manifest_declares_integration_type():
    """hassfest: a config-flow integration must declare one (core only)."""
    manifest = json.loads((PKG / "manifest.json").read_text())
    assert manifest["integration_type"] == "hub"



# --- config flow messages (R33) -------------------------------------------------

def _flow_error_keys_in_code():
    """Every error key config_flow.py can put on a form: its ERR_* constants,
    each of which must also be used somewhere in the file."""
    import ast
    tree = ast.parse((PKG / "config_flow.py").read_text())
    defined = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id.startswith("ERR_")
        ):
            defined[node.targets[0].id] = node.value.value
    used = {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    assert set(defined) <= used, f"defined but never shown: {set(defined) - used}"
    # No error key is written as a bare string next to the constants.
    literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    values = list(defined.values())
    assert all(sum(v == lit for lit in literals) <= 1 for v in values)
    return set(values)


@pytest.mark.parametrize("lang", LANGS)
def test_config_flow_errors_match_the_translations(lang):
    """Both ways: a message for every error the flow shows, and no message
    the flow cannot show. `invalid_model` and `invalid_config` sat here
    unused since 2026-05; Home Assistant's test harness does not check
    custom integrations' translations, so this does."""
    used = _flow_error_keys_in_code()
    assert used == {
        "invalid_host", "invalid_token", "cannot_connect",
        "invalid_auth", "clock_skew", "no_devices", "unexpected_reply",  # R34
        "wrong_hub",  # R43: reconfigure pointed at another hub
    }
    assert set(_load(lang)["config"]["error"]) == used


@pytest.mark.parametrize("lang", LANGS)
def test_discovery_form_is_translated(lang):
    """R43: the card shows the hub's name; the form asks model and token."""
    config = _load(lang)["config"]
    assert config["flow_title"] == "{name}"
    step = config["step"]["discovery_confirm"]
    assert set(step["data"]) == {"model", "token"} == set(step["data_description"])
    assert all(p in step["description"] for p in ("{name}", "{model}", "{host}"))


@pytest.mark.parametrize("lang", LANGS)
def test_reauth_form_is_translated(lang):
    """R34: the reauth form asks for the token only and names the hub."""
    step = _load(lang)["config"]["step"]["reauth_confirm"]
    assert set(step["data"]) == {"token"} == set(step["data_description"])
    assert "{host}" in step["description"]


@pytest.mark.parametrize("lang", LANGS)
def test_config_flow_abort_reasons(lang):
    """`already_configured` comes from Home Assistant's duplicate check and
    is not among the reasons it translates itself (2026.10+), so it stays
    here. `reconfigure_successful` and `reauth_successful` are translated by
    Home Assistant (checked in 2026.11.1 strings.json, R34)."""
    assert set(_load(lang)["config"]["abort"]) == {"already_configured"}
