"""The messages the forms show, as Home Assistant's own loader serves them.

The test harness does not check a custom integration's translations (R33), and
tests/test_translations_contract.py only reads the JSON files. This asks
Home Assistant for the strings the frontend would get.
"""
import pytest
from homeassistant.helpers.translation import async_get_translations

from custom_components.lifesmart import config_flow
from custom_components.lifesmart.const import DOMAIN

ERROR_KEYS = sorted(
    value for name, value in vars(config_flow).items() if name.startswith("ERR_")
)


@pytest.mark.parametrize("language", ["en", "zh-Hant", "zh-Hans"])
async def test_every_form_message_is_served(hass, language):
    strings = await async_get_translations(hass, language, "config", [DOMAIN])
    prefix = f"component.{DOMAIN}.config"
    for key in ERROR_KEYS:
        message = strings.get(f"{prefix}.error.{key}")
        assert message and message != key, f"{language}: no message for {key}"
    for step in ("user", "reconfigure", "reauth_confirm"):
        assert strings.get(f"{prefix}.step.{step}.title"), f"{language}: {step} has no title"
        assert strings.get(f"{prefix}.step.{step}.data.token")
        assert strings.get(f"{prefix}.step.{step}.data_description.token")
    assert "{host}" in strings[f"{prefix}.step.reauth_confirm.description"]


async def test_the_rejected_token_message_in_english(hass):
    strings = await async_get_translations(hass, "en", "config", [DOMAIN])
    message = strings[f"component.{DOMAIN}.config.error.invalid_auth"]
    assert message.startswith("The hub rejected this token")
    description = strings[f"component.{DOMAIN}.config.step.user.data_description.model"]
    assert "do not check it" in description
