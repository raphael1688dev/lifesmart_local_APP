"""Config flow for LifeSmart Local integration."""
import asyncio
import voluptuous as vol
import logging
import ipaddress
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

def validate_host(host):
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        if len(host) > 253 or not all(len(part) <= 63 for part in host.split(".")):
            raise vol.Invalid("Invalid hostname")
        return host

def validate_token(token):
    if not isinstance(token, str):
        raise vol.Invalid("Invalid token")
    token = token.strip()
    if not 16 <= len(token) <= 64:
        raise vol.Invalid("Invalid token length")
    if not token.isalnum():
        raise vol.Invalid("Invalid token characters")
    return token

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
        errors = {}
        if user_input is not None:
            try:
                user_input[CONF_HOST] = validate_host(user_input[CONF_HOST])
                user_input[CONF_TOKEN] = validate_token(user_input[CONF_TOKEN])

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
        errors = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            try:
                user_input[CONF_HOST] = validate_host(user_input[CONF_HOST])
                user_input[CONF_TOKEN] = validate_token(user_input[CONF_TOKEN])

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
