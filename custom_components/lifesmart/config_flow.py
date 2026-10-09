"""Config flow for LifeSmart Local integration."""
import asyncio
import voluptuous as vol
import logging
import ipaddress
from typing import Any, Dict
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import callback
from .const import DOMAIN, DEFAULT_MODEL
from .api import LifeSmartAPI

_LOGGER = logging.getLogger(__name__)

def _has_devices(msg) -> bool:
    if isinstance(msg, list):
        return bool(msg)
    if isinstance(msg, dict):
        return any(isinstance(v, dict) for v in msg.values())
    return False

def validate_host(host: Any) -> str:
    """Return a normalised host (IP literal or hostname) or raise vol.Invalid."""
    if not isinstance(host, str):
        raise vol.Invalid("Invalid host")
    host = host.strip()
    if not host:
        # R18: `vol.Required(CONF_HOST): str` accepts "", and "" passed the
        # hostname checks below, so an empty host used to reach discovery.
        raise vol.Invalid("Empty host")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        if len(host) > 253 or not all(len(part) <= 63 for part in host.split(".")):
            raise vol.Invalid("Invalid hostname")
        return host

def validate_token(token: Any) -> str:
    """Return a stripped token or raise vol.Invalid."""
    if not isinstance(token, str):
        raise vol.Invalid("Invalid token")
    token = token.strip()
    if not 16 <= len(token) <= 64:
        raise vol.Invalid("Invalid token length")
    if not token.isalnum():
        raise vol.Invalid("Invalid token characters")
    return token


def _validate_input(user_input: Dict[str, Any]) -> Dict[str, str]:
    """Normalise host/token in place and return field-level errors.

    R18 (2026-10-09): `validate_*` raise `vol.Invalid`, which is NOT a
    ValueError — true for voluptuous 0.16 and for probatio 0.13 (what HA
    aliases `voluptuous` to since 2026.9). The flow steps used to call the
    validators inside a `try` that only caught ValueError & friends, so a bad
    token escaped the step entirely and the UI showed "Unknown error
    occurred" instead of the `invalid_token` / `invalid_host` messages that
    had been sitting unused in translations since 2026-05.

    Returns {} when both fields are valid. Keys are the schema field names so
    HA renders each message next to the offending field.
    """
    errors: Dict[str, str] = {}
    try:
        user_input[CONF_HOST] = validate_host(user_input.get(CONF_HOST))
    except vol.Invalid:
        errors[CONF_HOST] = "invalid_host"
    try:
        user_input[CONF_TOKEN] = validate_token(user_input.get(CONF_TOKEN))
    except vol.Invalid:
        errors[CONF_TOKEN] = "invalid_token"
    return errors

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required("model", default=DEFAULT_MODEL): str,
        vol.Required(CONF_TOKEN): str,
    }
)


class LifeSmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    # VERSION bump (1→2) on 2026-05-24 with R10 unique_id format change.
    # async_migrate_entry in __init__.py picks up entries created under v1
    # and rewrites legacy <feature>_<me> unique_ids to <feature>_<agt>_<me>.
    VERSION = 2

    def __init__(self):
        self._errors = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "LifeSmartOptionsFlowHandler":
        return LifeSmartOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        errors: Dict[str, str] = {}
        if user_input is not None:
            # R18: field validation first; only touch the network when the
            # input is well-formed. See _validate_input for why this is not
            # inside the try below.
            errors = _validate_input(user_input)
        if user_input is not None and not errors:
            try:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()

                api = LifeSmartAPI(
                    host=user_input[CONF_HOST],
                    model=user_input["model"],
                    token=user_input[CONF_TOKEN],
                    timeout=10,
                    local_port=0
                )

                try:
                    await api.async_start()
                    discovery = await api.discover_devices()
                    if isinstance(discovery, dict) and discovery.get("code") == 101:
                        api.apply_ts_from_response(discovery)
                        discovery = await api.discover_devices()
                finally:
                    await api.async_stop()

                if (
                    isinstance(discovery, dict)
                    and discovery.get("code") == 0
                    and _has_devices(discovery.get("msg"))
                ):
                    user_input["local_port"] = api.local_port
                    return self.async_create_entry(title="LifeSmart Hub", data=user_input)
                _LOGGER.warning("Discovery response: %s", discovery)
                if isinstance(discovery, dict) and discovery.get("code") == 101:
                    errors["base"] = "clock_skew"
                else:
                    errors["base"] = "no_devices"
            except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError) as err:
                _LOGGER.debug("Config flow connection failed: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        errors: Dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            errors = _validate_input(user_input)  # R18, same as async_step_user
        if user_input is not None and not errors:
            try:
                api = LifeSmartAPI(
                    host=user_input[CONF_HOST],
                    model=user_input.get("model", DEFAULT_MODEL),
                    token=user_input[CONF_TOKEN],
                    timeout=10,
                    local_port=0
                )

                try:
                    await api.async_start()
                    discovery = await api.discover_devices()
                    if isinstance(discovery, dict) and discovery.get("code") == 101:
                        api.apply_ts_from_response(discovery)
                        discovery = await api.discover_devices()
                finally:
                    await api.async_stop()

                if (
                    isinstance(discovery, dict)
                    and discovery.get("code") == 0
                    and _has_devices(discovery.get("msg"))
                ):
                    user_input["local_port"] = api.local_port
                    return self.async_update_reload_and_abort(
                        entry, data={**entry.data, **user_input}
                    )
                _LOGGER.warning("Discovery response: %s", discovery)
                if isinstance(discovery, dict) and discovery.get("code") == 101:
                    errors["base"] = "clock_skew"
                else:
                    errors["base"] = "no_devices"
            except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError) as err:
                _LOGGER.debug("Config flow reconfigure failed: %s", err)
                errors["base"] = "cannot_connect"

        schema = vol.Schema({
            vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST)): str,
            vol.Required("model", default=entry.data.get("model", DEFAULT_MODEL)): str,
            vol.Required(CONF_TOKEN, default=entry.data.get(CONF_TOKEN)): str,
        })
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)


class LifeSmartOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        schema = vol.Schema({
            vol.Required("model", default=self._config_entry.data.get("model", DEFAULT_MODEL)): str,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
