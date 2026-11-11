"""Tests that run inside a real Home Assistant (R33).

Separate from `tests/`, whose conftest replaces `homeassistant.*` with
stubs: the two cannot share one pytest run. Run this suite with

    pip install pytest-homeassistant-custom-component pytest-cov
    python -m pytest tests_ha -o asyncio_mode=auto

The harness pins the Home Assistant version it was built from. On 2026-11-11
the newest harness (0.13.375) targets Home Assistant 2026.10.4, one release
below this integration's minimum (2026.11.0), and it does not import under
2026.11. So only what works on 2026.10.4 is tested here: the config flow.
Entry setup uses 2026.11 APIs and stays in `tests/` until the harness
catches up.
"""
