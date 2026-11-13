"""Tests that run inside a real Home Assistant (R33, harness replaced in R39).

Separate from `tests/`, whose conftest replaces `homeassistant.*` with
stubs: the two cannot share one pytest run, and the harness is a pytest
plugin that loads automatically wherever it is installed. Run this suite with

    pip install "pytest-homeassistant==2026.11.1" pytest-cov
    python -m pytest tests_ha -o asyncio_mode=auto -p no:respx \
        --cov=custom_components/lifesmart --cov-config=tests_ha/coverage.ini

Give coverage the path, not the module name; tests_ha/coverage.ini says why
and lists the two coverage gates CI applies.

What runs here (R40): the config flow (test_config_flow.py), and the whole
integration set up for real against tests_ha/hub.py, a hub simulated at the
datagram level, so the integration's own API builds, signs, sends and parses
every packet (test_setup / test_control / test_running / test_actions /
test_edges). `tests/` keeps its stubbed tests for pure functions.

`pytest-homeassistant` is Home Assistant's own test package, published from
home-assistant/core (`packages/pytest-homeassistant`) with the same version
number as Home Assistant. Install the release that matches the Home Assistant
being targeted, and upgrade the two together.

Until 2026-11-12 this used `pytest-homeassistant-custom-component`, whose last
release (0.13.375) ran Home Assistant 2026.10.4. Its author marked it broken
on 2026-11-03 and pointed to this package.
"""
