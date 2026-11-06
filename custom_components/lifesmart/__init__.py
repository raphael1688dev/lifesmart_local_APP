"""The LifeSmart Local integration."""
import logging
import re
import socket
import time
import asyncio
from datetime import timedelta
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from .const import DOMAIN, PLATFORMS, API_TIMEOUT
from .api import LifeSmartAPI, _extract_membership_changes
from .coordinator import LifeSmartCoordinator, LifeSmartHubCoordinator
from .device_info import hub_device_info_kwargs, hub_key_slug

# R19 (2026-10-24): raise the `hub_unreachable` repair issue once the hub has
# not answered the 90 s notify refresh for this long. The translation existed
# since 2026-05 but nothing created the issue. 5 min = 3-4 missed refreshes,
# long enough to ride out a hub reboot from the button.
HUB_UNREACHABLE_AFTER_SECONDS = 300

# D6 (R25): a NOTIFY `add` / `del` (LI §4.1) reloads the entry so the new
# device's entities appear (or the removed one's go). Pairing several devices
# in a row sends several events; wait for them to settle and reload once.
MEMBERSHIP_RELOAD_DELAY_SECONDS = 10


class _HubReachability:
    """How long the hub has been silent. Pure: the caller passes the clock.

    Only "no answer" counts (timeout / socket error). A hub that answers with
    an error code is reachable and does not feed this tracker.
    """

    def __init__(self, threshold_seconds: float = HUB_UNREACHABLE_AFTER_SECONDS) -> None:
        self._threshold = threshold_seconds
        self._first_failure: Optional[float] = None

    def record_failure(self, now: float) -> Optional[int]:
        """Return whole minutes of silence once past the threshold, else None."""
        if self._first_failure is None:
            self._first_failure = now
        elapsed = now - self._first_failure
        if elapsed < self._threshold:
            return None
        return int(elapsed // 60)

    def record_success(self) -> bool:
        """Reset. Return True if the hub had been failing (issue may exist)."""
        was_failing = self._first_failure is not None
        self._first_failure = None
        return was_failing


def _hub_unreachable_issue_id(entry_id: str) -> str:
    return f"hub_unreachable_{entry_id}"

_LOGGER = logging.getLogger(__name__)

def _get_local_ip_for_target(target_ip: str) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((target_ip, 1))
        return sock.getsockname()[0]
    finally:
        sock.close()


def _resolve_hub_key(
    discovery: Any, devices: List[Dict[str, Any]], existing_key: Optional[str], host: str,
) -> str:
    """Pick the key for the hub device's identifier (D21, R25).

    1. The hub's own ID: the `agt` its sub-devices report (LI §6.1 "Device ID
       of the Smart Station"), else the reply's `agtid` (LI §4.1 "Unique ID
       of the Smart Station"). The spec examples show the two equal.
    2. The key the hub device already has — so a boot where discovery came
       back empty does not fall back to the IP and split the device.
    3. The host IP, as before R25.
    """
    for device in devices:
        agt = device.get("agt") if isinstance(device, dict) else None
        if isinstance(agt, str) and agt:
            return agt
    if isinstance(discovery, dict):
        agtid = discovery.get("agtid")
        if isinstance(agtid, str) and agtid:
            return agtid
    if existing_key:
        return existing_key
    return host


def _existing_hub_key(dev_reg: Any, entry: ConfigEntry) -> Optional[str]:
    """The key of this entry's hub device, if one is registered."""
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and identifier.startswith("hub_"):
                return identifier[len("hub_"):]
    return None


def _migrate_hub_key(
    hass: HomeAssistant, entry: ConfigEntry, dev_reg: Any, old_key: Optional[str], new_key: str,
) -> None:
    """Move the hub device and its entities from `old_key` to `new_key`.

    Rewrites the device's identifier in place (so its id, area, name and the
    sub-devices' via_device_id links survive) and the hub-level unique_ids
    `hub_<feature>_<old slug>` → `hub_<feature>_<new slug>` (entity_ids,
    and so automations, are unchanged). Idempotent.
    """
    if not old_key or old_key == new_key:
        return
    old_device = dev_reg.async_get_device(identifiers={(DOMAIN, f"hub_{old_key}")})
    if old_device is None:
        return
    if dev_reg.async_get_device(identifiers={(DOMAIN, f"hub_{new_key}")}) is not None:
        _LOGGER.warning(
            "Hub device for %s already exists; leaving the one for %s in place",
            new_key, old_key,
        )
        return
    dev_reg.async_update_device(old_device.id, new_identifiers={(DOMAIN, f"hub_{new_key}")})

    old_suffix, new_suffix = f"_{hub_key_slug(old_key)}", f"_{hub_key_slug(new_key)}"
    ent_reg = er.async_get(hass)
    for entity_entry in list(ent_reg.entities.values()):
        uid = entity_entry.unique_id
        if (
            entity_entry.config_entry_id != entry.entry_id
            or not isinstance(uid, str)
            or not uid.startswith("hub_")
            or not uid.endswith(old_suffix)
        ):
            continue
        new_uid = uid[: -len(old_suffix)] + new_suffix
        try:
            ent_reg.async_update_entity(entity_entry.entity_id, new_unique_id=new_uid)
        except (ValueError, KeyError) as err:
            _LOGGER.debug("Skipped hub unique_id migration %s → %s: %s", uid, new_uid, err)
    _LOGGER.info("Hub device now keyed on its hub ID instead of %s", old_key)


@callback
def _async_update_version_issue(hass: HomeAssistant, entry: ConfigEntry, info: Mapping[str, Any]) -> None:
    """D17: surface a failed cfg:getver as a repair issue; clear it on success."""
    issue_id = f"hub_version_unknown_{entry.entry_id}"
    if info.get("version_ok"):
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return
    ir.async_create_issue(
        hass, DOMAIN, issue_id,
        config_entry_id=entry.entry_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="hub_version_unknown",
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up LifeSmart Local from a config entry.

    R23 (2026-11-05, minimum HA 2026.11): the config entry functions return
    None and fail by raising (dev blog 2026-10-23). Repair issues carry
    `config_entry_id`, so HA deletes them when the entry is removed and hides
    them while it is disabled (dev blog 2026-10-28).
    """
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

    # Phase 1 / R9: hub identity (cfg:getver) feeds every hub-level entity
    # from one cached dict. D4 (R25): a coordinator re-reads it, and the hub
    # time zone, once a day. Failures are non-fatal — the hub entities show
    # the last known values and D17 raises a repair issue.
    hub_coordinator = LifeSmartHubCoordinator(hass, api, entry.data["host"])
    hub_info = await hub_coordinator.async_fetch()
    hub_coordinator.async_set_updated_data(hub_info)
    _async_update_version_issue(hass, entry, hub_info)

    # D15 (2026-05-24): single coordinator per hub replaces the per-entity
    # `async_track_time_interval` polling pattern (HA 2026.5 規範要求).
    coordinator = LifeSmartCoordinator(hass, api, entry.data["host"])
    # Seed coordinator with discovery data we already have so the first
    # refresh doesn't block setup.
    coordinator.async_set_updated_data({
        d["me"]: d for d in devices if isinstance(d, dict) and isinstance(d.get("me"), str)
    })

    # D22 (R15, 2026-08-03): register the hub as a real device up-front so
    # every sub-device can point at it via `via_device_id`, giving the HA UI
    # a hub → sub-device hierarchy.
    #
    # We must use `via_device_id` (the registry ID string), NOT the older
    # `via_device=(DOMAIN, identifier)` tuple: as of HA 2026.8 identifiers are
    # only unique *per config entry*, so an identifier pair no longer names a
    # single device unambiguously and `via_device` is deprecated.
    # Creating the device here (rather than relying on the hub-level entities
    # in sensor.py / button.py) also removes a setup-order race — platforms
    # are forwarded concurrently, so a sub-device could otherwise be created
    # before the hub device exists.
    # R19: the hub's DeviceInfo fields are built once in device_info.py and
    # shared with the hub-level entities so the registry sees one consistent
    # device. The registry call additionally needs config_entry_id.
    # D21 (R25): keyed on the hub ID rather than the IP; older hub devices
    # are moved over in place.
    dev_reg = dr.async_get(hass)
    existing_key = _existing_hub_key(dev_reg, entry)
    hub_key = _resolve_hub_key(discovery, devices, existing_key, entry.data["host"])
    _migrate_hub_key(hass, entry, dev_reg, existing_key, hub_key)
    hub_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        **hub_device_info_kwargs(hub_key, entry.title, hub_info),
    )

    scenes = await _async_fetch_scenes(api)

    entry_data: Dict[str, Any] = {
        "api": api,
        "devices": devices,
        "hub_info": hub_info,
        "host": entry.data["host"],
        "hub_key": hub_key,
        "coordinator": coordinator,
        "hub_coordinator": hub_coordinator,
        "hub_device_id": hub_device.id,
        "scenes": scenes,
        "unsubs": [],
    }
    domain_data["entries"][entry.entry_id] = entry_data
    unsubs: List[Callable[[], None]] = entry_data["unsubs"]

    @callback
    def _on_hub_info() -> None:
        # D4: daily cfg:getver — keep the device page and the issue current.
        info = hub_coordinator.data or {}
        entry_data["hub_info"] = info
        _async_update_version_issue(hass, entry, info)
        kwargs = hub_device_info_kwargs(hub_key, entry.title, info)
        update: Dict[str, Any] = {"model": kwargs["model"]}
        if "sw_version" in kwargs:
            update["sw_version"] = kwargs["sw_version"]
        dev_reg.async_update_device(hub_device.id, **update)

    unsubs.append(hub_coordinator.async_add_listener(_on_hub_info))

    # D14 (2026-05-24): R10's unique_id migration is now handled by
    # async_migrate_entry below — fires when ConfigEntry.version < 2. We
    # still call it here as a defensive idempotent re-run to catch entries
    # whose migration ran against an empty device list (hub reachable but
    # `eps` returned nothing). R18: unreachable-hub failures no longer reach
    # this point — the migration raises ConfigEntryNotReady instead.
    _migrate_unique_ids(hass, entry, devices)
    _migrate_entity_ids(hass, entry)

    _async_register_services(hass)

    local_ip = await hass.async_add_executor_job(_get_local_ip_for_target, entry.data["host"])
    try:
        await api.configure_event_service(local_ip, api.local_port)
    except (asyncio.TimeoutError, OSError, KeyError, ValueError) as err:
        _LOGGER.warning("Failed to configure OpenDev event service: %s", err)

    # Setup reached this point, so the hub answered: drop any issue left from
    # before a restart / reload.
    issue_id_unreachable = _hub_unreachable_issue_id(entry.entry_id)
    ir.async_delete_issue(hass, DOMAIN, issue_id_unreachable)
    reachability = _HubReachability()

    async def _refresh_notify(_now) -> None:
        # The 90 s re-subscription (LI §4: expires after 300 s) doubles as the
        # hub heartbeat for the `hub_unreachable` repair issue (R19).
        try:
            await api.configure_event_service(local_ip, api.local_port)
        except (asyncio.TimeoutError, OSError) as err:
            _LOGGER.debug("Failed to refresh OpenDev event service: %s", err)
            minutes = reachability.record_failure(time.monotonic())
            if minutes is not None:
                ir.async_create_issue(
                    hass, DOMAIN, issue_id_unreachable,
                    config_entry_id=entry.entry_id,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="hub_unreachable",
                    translation_placeholders={
                        "host": entry.data["host"],
                        "minutes": str(minutes),
                    },
                )
            return
        except (KeyError, ValueError) as err:
            # The hub answered; the payload was odd. Reachable.
            _LOGGER.debug("Unexpected OpenDev event service reply: %s", err)
        if reachability.record_success():
            _LOGGER.info("LifeSmart hub %s is answering again", entry.data["host"])
            ir.async_delete_issue(hass, DOMAIN, issue_id_unreachable)

    unsub_notify = async_track_time_interval(hass, _refresh_notify, timedelta(seconds=90))
    entry_data["unsub_notify"] = unsub_notify

    # D6 (R25): reload when the hub reports a paired or removed sub-device.
    known = {d["me"] for d in devices if isinstance(d, dict) and isinstance(d.get("me"), str)}
    pending_reload: List[Optional[Callable[[], None]]] = [None]

    @callback
    def _reload_for_membership(_now: Any) -> None:
        pending_reload[0] = None
        _LOGGER.info("LifeSmart hub reported paired or removed devices; reloading")
        hass.config_entries.async_schedule_reload(entry.entry_id)

    @callback
    def _on_report(message: Dict[str, Any]) -> None:
        added, removed = _extract_membership_changes(message)
        if not (added - known or removed & known):
            return
        if pending_reload[0] is not None:
            pending_reload[0]()
        pending_reload[0] = async_call_later(
            hass, MEMBERSHIP_RELOAD_DELAY_SECONDS, _reload_for_membership
        )

    @callback
    def _cancel_pending_reload() -> None:
        if pending_reload[0] is not None:
            pending_reload[0]()
            pending_reload[0] = None

    unsubs.append(api.register_report_listener(_on_report))
    unsubs.append(_cancel_pending_reload)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def _async_fetch_scenes(api: LifeSmartAPI) -> List[Dict[str, Any]]:
    """LI §3.3.5 scene list, read once for scene.py, switch.py and light.py.

    Scene ids are `AI...` strings (LI §5.1). An error leaves the list empty:
    the hub's devices still work without its scenes.
    """
    try:
        response = await api.get_scene_list()
    except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError) as err:
        _LOGGER.warning("Failed to fetch scene list: %s", err)
        return []
    if not isinstance(response, dict) or response.get("code") != 0:
        _LOGGER.debug("Scene list call returned non-zero code: %s", response)
        return []
    raw = response.get("msg")
    if not isinstance(raw, list):
        _LOGGER.debug("Scene list msg is not a list: %s", raw)
        return []
    return [
        item for item in raw
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("cls"), str)
    ]

async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate config entry across version bumps.

    Version history:
    - 1 → 2 (R10/D14, 2026-05-24): unique_id format change to include `agt`.
      Migration walks the entity registry and rewrites legacy
      `<feature>_<me>` ids to `<feature>_<agt>_<me>`. We need device data
      (the `me` → `agt` map) so we momentarily start the API to fetch eps.

    Error handling (R18, 2026-10-09): if the hub cannot be reached we raise
    ConfigEntryNotReady so HA puts the entry in SETUP_RETRY and re-runs the
    migration later (supported since HA 2026.10 — see dev blog 2026-09-17).
    Before R18 we bumped the version anyway and relied on async_setup_entry's
    idempotent re-run; functionally equivalent, but the entry version then
    claimed a migration that had not actually happened yet.
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
                "Migration discovery failed (%s) — entry goes to SETUP_RETRY "
                "and the migration is re-attempted later.", err,
            )
            raise ConfigEntryNotReady(f"Hub unreachable during migration: {err}") from err
        finally:
            try:
                await api.async_stop()
            except (asyncio.TimeoutError, OSError):
                pass

        if devices:
            _migrate_unique_ids(hass, entry, devices)

        hass.config_entries.async_update_entry(entry, version=2)
        _LOGGER.info("Migration to version 2 complete (entry=%s)", entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry.

    R23: raises (translated by HA) when a platform fails to unload. The
    `hub_unreachable` issue is no longer deleted here: deleting on unload
    revives an issue the user ignored as soon as a reload re-creates it
    (dev blog 2026-10-28). It is linked to the entry instead, and setup
    deletes it once the hub answers.
    """
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    domain_data = hass.data[DOMAIN]
    entry_data = domain_data["entries"].pop(entry.entry_id, None)
    if entry_data and entry_data.get("unsub_notify"):
        entry_data["unsub_notify"]()
    for unsub in (entry_data or {}).get("unsubs", []):
        unsub()
    api: Optional[LifeSmartAPI] = entry_data["api"] if entry_data else None
    if api is not None:
        await api.async_stop()
    if not domain_data["entries"]:
        hass.data.pop(DOMAIN)


# D8 (R25): hub configuration commands (LI §3.3.10) as actions. Each takes
# the config entry of the hub it acts on, so several hubs stay apart.
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
SERVICE_SET_HUB_TIMEZONE = "set_hub_timezone"
SERVICE_RENAME_DEVICE = "rename_device"
SERVICE_UPGRADE_HUB_FIRMWARE = "upgrade_hub_firmware"
SERVICE_FACTORY_RESET_HUB = "factory_reset_hub"


def _entry_for_call(hass: HomeAssistant, call: ServiceCall) -> Tuple[ConfigEntry, Dict[str, Any]]:
    """The loaded config entry an action names, or ServiceValidationError."""
    entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
    entry = hass.config_entries.async_get_entry(entry_id)
    entry_data = hass.data.get(DOMAIN, {}).get("entries", {}).get(entry_id)
    if entry is None or entry.domain != DOMAIN or entry_data is None:
        raise ServiceValidationError(f"{entry_id} is not a loaded LifeSmart hub")
    return entry, entry_data


def _raise_unless_ok(reply: Any, command: str) -> None:
    if not isinstance(reply, dict) or reply.get("code") != 0:
        raise HomeAssistantError(f"The hub rejected {command}: {reply}")


def _sub_device_me(
    hass: HomeAssistant, entry: ConfigEntry, device_id: Optional[str],
) -> Optional[str]:
    """Map an HA device id to the LifeSmart `me` for cfg:devname.

    None means the hub itself: no device given, or the hub device chosen.
    """
    if not device_id:
        return None
    device = dr.async_get(hass).async_get(device_id)
    if device is None or entry.entry_id not in device.config_entries:
        raise ServiceValidationError(f"Device {device_id} does not belong to {entry.title}")
    for domain, identifier in device.identifiers:
        if domain != DOMAIN:
            continue
        return None if identifier.startswith("hub_") else identifier
    raise ServiceValidationError(f"Device {device_id} is not a LifeSmart device")


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

    async def _handle_set_hub_timezone(call: ServiceCall) -> None:
        _entry, entry_data = _entry_for_call(hass, call)
        reply = await entry_data["api"].set_hub_timezone(
            call.data["timezone"], call.data["daylight_saving"]
        )
        _raise_unless_ok(reply, "cfg:timezone")
        await entry_data["hub_coordinator"].async_request_refresh()

    async def _handle_rename_device(call: ServiceCall) -> None:
        entry, entry_data = _entry_for_call(hass, call)
        me = _sub_device_me(hass, entry, call.data.get("device_id"))
        reply = await entry_data["api"].set_device_name(call.data["name"], me)
        _raise_unless_ok(reply, "cfg:devname")
        # Device names come from `eps` at setup; reload to show the new one.
        hass.config_entries.async_schedule_reload(entry.entry_id)

    async def _handle_upgrade_hub_firmware(call: ServiceCall) -> None:
        _entry, entry_data = _entry_for_call(hass, call)
        reply = await entry_data["api"].upgrade_hub(call.data["reboot"])
        _raise_unless_ok(reply, "cfg:upgrade")

    async def _handle_factory_reset_hub(call: ServiceCall) -> None:
        entry, entry_data = _entry_for_call(hass, call)
        if call.data["confirm"] is not True:
            raise ServiceValidationError("Set confirm to true to factory-reset the hub")
        _LOGGER.warning("Sending cfg:reset — %s returns to factory settings", entry.title)
        try:
            reply = await entry_data["api"].factory_reset_hub()
        except asyncio.TimeoutError:
            # Like cfg:reboot, the hub may restart before it answers.
            _LOGGER.info("cfg:reset got no reply; the hub is probably restarting")
            return
        _raise_unless_ok(reply, "cfg:reset")

    entry_field = {vol.Required(ATTR_CONFIG_ENTRY_ID): str}

    hass.services.async_register(
        DOMAIN,
        "send_keys",
        _handle_send_keys,
        schema=vol.Schema({
            vol.Required("remote_id"): str,
            vol.Required("keys"): vol.Any(str, [str]),
        }),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HUB_TIMEZONE,
        _handle_set_hub_timezone,
        schema=vol.Schema({
            **entry_field,
            # LI §3.3.10 / OD §2.3.1: [-12, 12], east positive.
            vol.Required("timezone"): vol.All(vol.Coerce(int), vol.Range(min=-12, max=12)),
            vol.Optional("daylight_saving", default=False): bool,
        }),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RENAME_DEVICE,
        _handle_rename_device,
        schema=vol.Schema({
            **entry_field,
            vol.Required("name"): vol.All(str, vol.Length(min=1)),
            vol.Optional("device_id"): str,
        }),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPGRADE_HUB_FIRMWARE,
        _handle_upgrade_hub_firmware,
        schema=vol.Schema({
            **entry_field,
            vol.Optional("reboot", default=False): bool,
        }),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FACTORY_RESET_HUB,
        _handle_factory_reset_hub,
        schema=vol.Schema({
            **entry_field,
            vol.Required("confirm"): bool,
        }),
    )
    domain_data["_services_registered"] = True

def generate_entity_id(device_type, hub_id, device_id, idx=None):
    if idx is not None:
        raw_id = f"{device_type}_{hub_id}_{device_id}_{idx}".lower()
    else:
        raw_id = f"{device_type}_{hub_id}_{device_id}".lower()
    # HA entity_id object part must match [a-z0-9_]+; some `agt` tokens carry
    # '-' (base64-ish) which HA 2027.2 will reject outright. Sanitize any
    # non-conforming char to '_' before collapsing.
    raw_id = re.sub(r"[^a-z0-9_]", "_", raw_id)
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


def _migrate_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rename entity_ids whose object part contains chars HA 2027.2 will reject.

    HA requires entity_id's object part to match ``[a-z0-9_]+``. Some hubs
    ship an ``agt`` (hub ID) containing ``-`` (base64-ish tokens), so early
    boots produced entity_ids like ``switch.foo_a-b_c``. HA currently accepts
    them with a warning; 2027.2 will reject them entirely.

    Idempotent: skips entity_ids that are already clean, and skips ids not
    owned by this config entry. HA does NOT rewrite automation, script or
    dashboard references to the renamed entity_id (R19, checked against
    2026.10.3 and dev) — release notes must tell users to update them.
    """
    ent_reg = er.async_get(hass)
    renames = 0
    for entity_entry in list(ent_reg.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id:
            continue
        old_id = entity_entry.entity_id
        if not isinstance(old_id, str) or "." not in old_id:
            continue
        domain, _, obj = old_id.partition(".")
        if not obj or not re.search(r"[^a-z0-9_]", obj):
            continue
        # R17: lower() FIRST, same order as generate_entity_id / remote._slugify.
        # Without it every uppercase letter matched [^a-z0-9_] and became '_',
        # mangling mixed-case ids (e.g. remote.tv_AzQ..8-Gqz_7D01 -> tv_z_w_8_qz_7_01).
        fixed_obj = re.sub(r"[^a-z0-9_]", "_", obj.lower())
        fixed_obj = re.sub(r"_+", "_", fixed_obj).strip("_")
        if not fixed_obj or fixed_obj == obj:
            continue
        new_id = f"{domain}.{fixed_obj}"
        try:
            ent_reg.async_update_entity(old_id, new_entity_id=new_id)
            renames += 1
        except (ValueError, KeyError) as err:
            _LOGGER.debug(
                "Skipped entity_id migration for %s → %s: %s",
                old_id, new_id, err,
            )

    if renames:
        _LOGGER.info(
            "Migrated %d entity_id(s) to strip characters HA 2027.2 will reject",
            renames,
        )
