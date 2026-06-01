"""The LifeSmart Local integration."""
import logging
import re
import socket
import asyncio
from datetime import timedelta
from typing import Optional
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval
from .const import DOMAIN, PLATFORMS, API_TIMEOUT
from .api import LifeSmartAPI
from .coordinator import LifeSmartCoordinator

_LOGGER = logging.getLogger(__name__)

def _get_local_ip_for_target(target_ip: str) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((target_ip, 1))
        return sock.getsockname()[0]
    finally:
        sock.close()

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LifeSmart Local from a config entry."""
    api = LifeSmartAPI(
        host=entry.data["host"],
        model=entry.data.get("model", "OD_ALI_TECH"),
        token=entry.data["token"],
        timeout=API_TIMEOUT,
        local_port=entry.data.get("local_port", 0),
    )
    
    try:
        await api.async_start()
        discovery = await api.discover_devices()
        
        if isinstance(discovery, dict) and discovery.get("code") == 101:
            _LOGGER.warning(
                "LifeSmart hub returned code 101 (timestamp rejected). "
                "Adjusting ts_offset from hub response and retrying."
            )
            api.apply_ts_from_response(discovery)
            discovery = await api.discover_devices()

        _LOGGER.debug("Raw discovery response: %s", discovery)
    except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError) as err:
        _LOGGER.error("Failed to connect or discover devices: %s", err)
        await api.async_stop()
        raise ConfigEntryNotReady from err

    domain_data = hass.data.setdefault(DOMAIN, {"entries": {}, "_services_registered": False})
    
    devices = []
    if isinstance(discovery, dict):
        if discovery.get("code") == 0 and "msg" in discovery:
            msg_data = discovery["msg"]
            if isinstance(msg_data, list):
                devices = msg_data
            elif isinstance(msg_data, dict):
                devices = [dev for dev in msg_data.values() if isinstance(dev, dict)]
            
    if not devices:
        _LOGGER.warning("No devices found after discovery. Raw data: %s", discovery)
    else:
        _LOGGER.info("Successfully loaded %s devices from LifeSmart Hub.", len(devices))

    # Phase 1 / R9: fetch hub identity (cfg:getver) once at setup so all
    # hub-level entities can read from a single cached dict without each one
    # racing for its own request. Failures are non-fatal — hub entities will
    # show "Unknown" but the rest of the integration still works.
    # D17 (2026-05-24): On failure, surface a HA Issue so the user gets
    # actionable feedback instead of having to dig through logs.
    hub_info: dict = {}
    issue_id_version = f"hub_version_unknown_{entry.entry_id}"
    try:
        ver_resp = await api.get_hub_version()
        if isinstance(ver_resp, dict) and ver_resp.get("code") == 0 and isinstance(ver_resp.get("msg"), dict):
            msg = ver_resp["msg"]
            hub_info = {
                "ver": msg.get("ver"),
                "osver": msg.get("osver"),
                "mgatype": msg.get("mgatype"),
            }
            _LOGGER.debug("Hub version info: %s", hub_info)
            # Clear any previously-raised issue for this entry.
            ir.async_delete_issue(hass, DOMAIN, issue_id_version)
        else:
            _LOGGER.warning("cfg:getver returned non-zero or unexpected shape: %s", ver_resp)
            ir.async_create_issue(
                hass, DOMAIN, issue_id_version,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="hub_version_unknown",
            )
    except (asyncio.TimeoutError, OSError, KeyError, ValueError) as err:
        _LOGGER.warning("Failed to query hub version (cfg:getver): %s", err)
        ir.async_create_issue(
            hass, DOMAIN, issue_id_version,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="hub_version_unknown",
        )

    # D15 (2026-05-24): single coordinator per hub replaces the per-entity
    # `async_track_time_interval` polling pattern (HA 2026.5 規範要求).
    # Sensor entities migrated this iteration; binary_sensor / cover still
    # poll individually — tracked in PROGRESS.md as remaining D15 follow-up.
    coordinator = LifeSmartCoordinator(hass, api, entry.data["host"])
    # Seed coordinator with discovery data we already have so the first
    # refresh doesn't block setup.
    coordinator.async_set_updated_data({
        d["me"]: d for d in devices if isinstance(d, dict) and isinstance(d.get("me"), str)
    })

    domain_data["entries"][entry.entry_id] = {
        "api": api,
        "devices": devices,
        "hub_info": hub_info,
        "host": entry.data["host"],
        "coordinator": coordinator,
    }

    # D14 (2026-05-24): R10's unique_id migration is now handled by
    # async_migrate_entry below — fires when ConfigEntry.version < 2. We
    # still call it here as a defensive idempotent re-run to catch entries
    # whose migration may have failed on first boot (e.g. discovery was
    # empty so we had no devices to look up agt against).
    _migrate_unique_ids(hass, entry, devices)

    _async_register_services(hass)

    local_ip = await hass.async_add_executor_job(_get_local_ip_for_target, entry.data["host"])
    try:
        await api.configure_event_service(local_ip, api.local_port)
    except (asyncio.TimeoutError, OSError, KeyError, ValueError) as err:
        _LOGGER.warning("Failed to configure OpenDev event service: %s", err)

    async def _refresh_notify(_now) -> None:
        try:
            await api.configure_event_service(local_ip, api.local_port)
        except (asyncio.TimeoutError, OSError, KeyError, ValueError) as err:
            _LOGGER.debug("Failed to refresh OpenDev event service: %s", err)

    unsub_notify = async_track_time_interval(hass, _refresh_notify, timedelta(seconds=90))
    domain_data["entries"][entry.entry_id]["unsub_notify"] = unsub_notify

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry across version bumps.

    Version history:
    - 1 → 2 (R10/D14, 2026-05-24): unique_id format change to include `agt`.
      Migration walks the entity registry and rewrites legacy
      `<feature>_<me>` ids to `<feature>_<agt>_<me>`. We need device data
      (the `me` → `agt` map) so we momentarily start the API to fetch eps.
    """
    _LOGGER.info("Migrating config entry from version %s", entry.version)

    if entry.version == 1:
        # We need agt info to migrate. Spin up a transient API just for eps.
        api = LifeSmartAPI(
            host=entry.data["host"],
            model=entry.data.get("model", "OD_ALI_TECH"),
            token=entry.data["token"],
            timeout=API_TIMEOUT,
            local_port=entry.data.get("local_port", 0),
        )
        devices: list = []
        try:
            await api.async_start()
            discovery = await api.discover_devices()
            if isinstance(discovery, dict) and discovery.get("code") == 101:
                api.apply_ts_from_response(discovery)
                discovery = await api.discover_devices()
            if isinstance(discovery, dict) and discovery.get("code") == 0:
                msg = discovery.get("msg")
                if isinstance(msg, list):
                    devices = msg
                elif isinstance(msg, dict):
                    devices = [d for d in msg.values() if isinstance(d, dict)]
        except (asyncio.TimeoutError, OSError) as err:
            _LOGGER.warning(
                "Migration discovery failed (%s) — async_setup_entry will retry "
                "the migration idempotently on next boot.", err,
            )
        finally:
            try:
                await api.async_stop()
            except (asyncio.TimeoutError, OSError):
                pass

        if devices:
            _migrate_unique_ids(hass, entry, devices)

        hass.config_entries.async_update_entry(entry, version=2)
        _LOGGER.info("Migration to version 2 complete (entry=%s)", entry.entry_id)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        domain_data = hass.data[DOMAIN]
        entry_data = domain_data["entries"].pop(entry.entry_id, None)
        if entry_data and entry_data.get("unsub_notify"):
            entry_data["unsub_notify"]()
        api: Optional[LifeSmartAPI] = entry_data["api"] if entry_data else None
        if api is not None:
            await api.async_stop()
        if not domain_data["entries"]:
            hass.data.pop(DOMAIN)
    return unload_ok

def _async_register_services(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {"entries": {}, "_services_registered": False})
    if domain_data["_services_registered"]:
        return

    async def _handle_send_keys(call: ServiceCall) -> None:
        remote_id = call.data["remote_id"]
        keys = call.data["keys"]
        keys_to_send = [keys] if isinstance(keys, str) else list(keys)

        for entry_data in hass.data.get(DOMAIN, {}).get("entries", {}).values():
            api = entry_data.get("api")
            if isinstance(api, LifeSmartAPI):
                for key in keys_to_send:
                    await api.send_remote_key(remote_id, key)

    hass.services.async_register(
        DOMAIN,
        "send_keys",
        _handle_send_keys,
        schema=vol.Schema({
            vol.Required("remote_id"): str,
            vol.Required("keys"): vol.Any(str, [str]),
        }),
    )
    domain_data["_services_registered"] = True

def generate_entity_id(device_type, hub_id, device_id, idx=None):
    if idx is not None:
        raw_id = f"{device_type}_{hub_id}_{device_id}_{idx}".lower()
    else:
        raw_id = f"{device_type}_{hub_id}_{device_id}".lower()
    return re.sub(r"_+", "_", raw_id).strip("_")


# Features whose unique_id followed the legacy <feature>_<me>[_<idx>] pattern
# before R10. After R10 they all carry <feature>_<agt>_<me>[_<idx>] so two hubs
# can coexist when they share device IDs (e.g. the V_SI / me=0020 system device
# auto-created by every Smart Station).
_LEGACY_FEATURES = ("connectivity", "signal", "temp", "battery", "cover", "remote", "switch")


def _migrate_unique_ids(
    hass: HomeAssistant, entry: ConfigEntry, devices: list,
) -> None:
    """Rewrite legacy <feature>_<me> unique_ids to <feature>_<agt>_<me>.

    Idempotent: the only entries we rewrite are those whose second token is
    found as a `me` value in the current device list — already-migrated
    entries have an `agt` (long base64-ish string) in that slot and will not
    match any `me`, so we leave them alone.

    Returns silently if devices is empty (e.g. discovery returned nothing) —
    no entities should exist for an entry with no devices anyway.
    """
    if not devices:
        return

    me_to_agt: dict[str, str] = {}
    for d in devices:
        if not isinstance(d, dict):
            continue
        me = d.get("me")
        agt = d.get("agt")
        if isinstance(me, str) and isinstance(agt, str):
            me_to_agt[me] = agt

    if not me_to_agt:
        return

    ent_reg = er.async_get(hass)
    rewrites = 0
    for entity_entry in list(ent_reg.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id:
            continue
        old_uid = entity_entry.unique_id
        if not isinstance(old_uid, str) or "_" not in old_uid:
            continue
        feature, _, suffix = old_uid.partition("_")
        if feature not in _LEGACY_FEATURES or not suffix:
            continue
        # Pre-R10 patterns:
        #   <feature>_<me>          (connectivity / signal / temp / battery / cover / remote)
        #   switch_<me>_<idx>       (switch only)
        # so the FIRST suffix token must be a known `me`.
        first_token, _, rest = suffix.partition("_")
        if first_token not in me_to_agt:
            # Either already migrated (second token is agt) or stale entry
            # for a device no longer paired — leave untouched.
            continue
        agt = me_to_agt[first_token]
        new_uid = f"{feature}_{agt}_{suffix}"  # suffix already starts with me
        try:
            ent_reg.async_update_entity(
                entity_entry.entity_id, new_unique_id=new_uid,
            )
            rewrites += 1
        except (ValueError, KeyError) as err:
            _LOGGER.debug(
                "Skipped migration for %s (%s → %s): %s",
                entity_entry.entity_id, old_uid, new_uid, err,
            )

    if rewrites:
        _LOGGER.info("Migrated %d unique_id(s) to include agt prefix", rewrites)
