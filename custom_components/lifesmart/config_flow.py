"""Config flow for LifeSmart Local integration."""
import asyncio
import voluptuous as vol
import logging
import ipaddress
from typing import Any, Dict, Mapping, Optional, Tuple
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_TOKEN
from .const import DOMAIN, DEFAULT_MODEL
from .api import LifeSmartAPI, REJECTED_CLOCK, REJECTED_TOKEN, rejection

_LOGGER = logging.getLogger(__name__)

# R28: per-attempt timeout while the form is open. Discovery is a GET, which
# is sent twice (api.py D18), so the form answers within 10 s as it did
# before R25 — instead of 20 s — and survives one lost packet.
FLOW_TIMEOUT = 5

# Every message a form can show. tests/test_translations_contract.py checks
# that these are exactly the keys translated under `config.error`, and that
# each one is used.
ERR_INVALID_HOST = "invalid_host"
ERR_INVALID_TOKEN = "invalid_token"
ERR_CANNOT_CONNECT = "cannot_connect"
ERR_INVALID_AUTH = "invalid_auth"
ERR_CLOCK_SKEW = "clock_skew"
ERR_NO_DEVICES = "no_devices"
ERR_UNEXPECTED_REPLY = "unexpected_reply"

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
        errors[CONF_HOST] = ERR_INVALID_HOST
    try:
        user_input[CONF_TOKEN] = validate_token(user_input.get(CONF_TOKEN))
    except vol.Invalid:
        errors[CONF_TOKEN] = ERR_INVALID_TOKEN
    return errors

async def _async_try_hub(
    host: str, model: str, token: str, *, need_devices: bool
) -> Tuple[Optional[str], int]:
    """Ask the hub for its device list (LI §3.3.2), as setup will.

    Returns (error key, 0), or (None, the local UDP port that was bound).

    R34: what the reply means. `send_command` has already corrected the
    clock and asked again on code 101, so a 101 that comes back here is not
    the clock (see api.rejection):
    * no reply                          -> cannot_connect
    * code 101 with the hub's time      -> invalid_auth (the token)
    * code 101 without it               -> clock_skew (could not be corrected)
    * code 0 with devices               -> success
    * code 0 without devices            -> no_devices, where devices are needed
    * anything else                     -> unexpected_reply

    Before R34 every 101 was shown as "clock difference too large" and every
    other odd reply as "no devices found".
    """
    api = LifeSmartAPI(
        host=host, model=model, token=token, timeout=FLOW_TIMEOUT, local_port=0,
    )
    try:
        try:
            await api.async_start()
            discovery = await api.discover_devices()
        finally:
            await api.async_stop()
    except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError) as err:
        _LOGGER.debug("Config flow could not reach the hub: %s", err)
        return ERR_CANNOT_CONNECT, 0

    why = rejection(discovery)
    if why == REJECTED_TOKEN:
        return ERR_INVALID_AUTH, 0
    if why == REJECTED_CLOCK:
        return ERR_CLOCK_SKEW, 0
    if isinstance(discovery, dict) and discovery.get("code") == 0:
        if need_devices and not _has_devices(discovery.get("msg")):
            return ERR_NO_DEVICES, 0
        return None, api.local_port
    _LOGGER.warning("Unexpected reply from the hub at %s: %s", host, discovery)
    return ERR_UNEXPECTED_REPLY, 0


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required("model", default=DEFAULT_MODEL): str,
        vol.Required(CONF_TOKEN): str,
    }
)

# R34: the hub does not check the model (api.rejection), so a rejected
# signature can only be put right with another token.
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): str})


def _form_values(source: Mapping[str, Any]) -> Dict[str, Any]:
    """The three form fields out of an entry's data or a submission."""
    return {
        CONF_HOST: source.get(CONF_HOST),
        "model": source.get("model", DEFAULT_MODEL),
        CONF_TOKEN: source.get(CONF_TOKEN),
    }


class LifeSmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    # VERSION bump (1→2) on 2026-05-24 with R10 unique_id format change.
    # async_migrate_entry in __init__.py picks up entries created under v1
    # and rewrites legacy <feature>_<me> unique_ids to <feature>_<agt>_<me>.
    VERSION = 2

    # No options flow (R19, 2026-10-24). The old one saved `model` to
    # entry.options, which nothing ever read — the "Configure" button looked
    # like it worked and did nothing. Every setting lives in entry.data and is
    # changed through async_step_reconfigure, so there is one source of truth.

    # R34: every form is redrawn with what the user typed
    # (add_suggested_values_to_schema). Before, an error cleared the user
    # form, and reset the reconfigure form to the stored values.

    async def async_step_user(self, user_input=None):
        errors: Dict[str, str] = {}
        if user_input is not None:
            # R18: field validation first; only touch the network when the
            # input is well-formed. See _validate_input.
            errors = _validate_input(user_input)
        if user_input is not None and not errors:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()
            error, local_port = await _async_try_hub(
                user_input[CONF_HOST], user_input["model"], user_input[CONF_TOKEN],
                need_devices=True,
            )
            if error is None:
                user_input["local_port"] = local_port
                return self.async_create_entry(title="LifeSmart Hub", data=user_input)
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        errors: Dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            errors = _validate_input(user_input)  # R18, same as async_step_user
        if user_input is not None and not errors:
            error, local_port = await _async_try_hub(
                user_input[CONF_HOST], user_input["model"], user_input[CONF_TOKEN],
                need_devices=True,
            )
            if error is None:
                user_input["local_port"] = local_port
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, **user_input}
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, _form_values(user_input if user_input is not None else entry.data)
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        """Home Assistant starts this when setup or a poll raises
        ConfigEntryAuthFailed: the hub rejected the token (R34)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Ask for the token again; host and model stay as they are."""
        errors: Dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                token = validate_token(user_input.get(CONF_TOKEN))
            except vol.Invalid:
                errors[CONF_TOKEN] = ERR_INVALID_TOKEN
            else:
                # A hub that accepts the token but has no devices paired is
                # still a working login.
                error, _port = await _async_try_hub(
                    entry.data[CONF_HOST], entry.data.get("model", DEFAULT_MODEL), token,
                    need_devices=False,
                )
                if error is None:
                    return self.async_update_reload_and_abort(
                        entry, data_updates={CONF_TOKEN: token}
                    )
                errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(REAUTH_SCHEMA, user_input),
            errors=errors,
            description_placeholders={"name": entry.title, "host": entry.data[CONF_HOST]},
        )
