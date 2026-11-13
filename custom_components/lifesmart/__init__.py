"""The LifeSmart Local integration."""
import logging
import re
import socket
import time
import asyncio
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from .const import DOMAIN, PLATFORMS, API_TIMEOUT
from .api import (
    REJECTED_TOKEN,
    LifeSmartAPI,
    _extract_membership_changes,
    rejection,
)
from .availability import HubAvailability
from .coordinator import LifeSmartCoordinator, LifeSmartHubCoordinator
from .discovery import async_start_discovery
from .device_info import hub_device_info_kwargs, hub_key_slug
from .models import LifeSmartConfigEntry, LifeSmartData

# R28: async_setup below only registers the actions; the integration is set
# up from config entries (hassfest wants a CONFIG_SCHEMA next to async_setup).
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

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
        address: str = sock.getsockname()[0]
        return address
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


def _duplicate_hub_issue_id(entry_id: str) -> str:
    return f"duplicate_hub_{entry_id}"


@callback
def _async_adopt_hub_id(hass: HomeAssistant, entry: LifeSmartConfigEntry, hub_key: str) -> None:
    """Make the hub's own id the entry's unique id (R43).

    Entries used to be identified by the address the user typed (R35 kept
    that; R43 reverses it): the same hub could then be added twice under two
    addresses, and a hub that moved to another address was not recognised.
    The hub id is `agt` / `LSID` (LI §6.1 / §2), the same id the hub device
    has been keyed on since R25, so nothing else changes: entity ids and
    unique ids are built from the devices, not from the entry's unique id.

    Only an id the hub reported is taken. When `hub_key` fell back to the
    address (a hub with nothing paired), the entry keeps its unique id until
    the hub reports one, or discovery finds it at that address.

    Home Assistant does not refuse a unique id another entry already has (it
    logs and accepts it), so that is checked here. If the same hub is set up
    twice, this entry keeps its old unique id and a repair issue asks the
    user to delete one of the two.
    """
    issue_id = _duplicate_hub_issue_id(entry.entry_id)
    if hub_key != entry.data["host"] and entry.unique_id != hub_key:
        other = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, hub_key)
        if other is not None and other.entry_id != entry.entry_id:
            _LOGGER.warning(
                "%s and %s are the same LifeSmart hub (%s); delete one of them",
                entry.title, other.title, hub_key,
            )
            ir.async_create_issue(
                hass, DOMAIN, issue_id,
                config_entry_id=entry.entry_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="duplicate_hub",
                translation_placeholders={
                    "title": entry.title, "host": entry.data["host"],
                    "other_title": other.title, "other_host": other.data.get("host", ""),
                },
            )
            return
        _LOGGER.info("%s is now identified by its hub id instead of its address", entry.title)
        hass.config_entries.async_update_entry(entry, unique_id=hub_key)
    ir.async_delete_issue(hass, DOMAIN, issue_id)


def _existing_hub_key(dev_reg: Any, entry: LifeSmartConfigEntry) -> Optional[str]:
    """The key of this entry's hub device, if one is registered."""
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and identifier.startswith("hub_"):
                return identifier[len("hub_"):]
    return None


def _migrate_hub_key(
    hass: HomeAssistant, entry: LifeSmartConfigEntry, dev_reg: Any, old_key: Optional[str], new_key: str,
) -> None:
    """Move the hub device and its entities from `old_key` to `new_key`.

    Rewrites the device's identifier in place (so its id, area, name and the
    sub-devices' via_device_id links survive) and the hub-level unique_ids
    `hub_<feature>_<old slug>` → `hub_<feature>_<new slug>` (entity_ids,
    and so automations, are unchanged). Idempotent.
    """
    if not old_key or old_key == new_key:
        return
    # R28: async_get_device(identifiers=…) is deprecated (identifiers are only
    # unique per config entry; removed in HA 2027.8.0) — look up by entry.
    old_device = dev_reg.async_get_device_by_identifier(
        (DOMAIN, f"hub_{old_key}"), entry.entry_id
    )
    if old_device is None:
        return
    if dev_reg.async_get_device_by_identifier(
        (DOMAIN, f"hub_{new_key}"), entry.entry_id
    ) is not None:
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
def _async_drop_version_issue(hass: HomeAssistant, entry: LifeSmartConfigEntry) -> None:
    """Delete the `hub_version_unknown` repair issue older versions raised.

    R36 (quality scale `repair-issues`): a repair issue is for something the
    user can act on. "cfg:getver did not answer as expected" is not: there is
    nothing to do but wait for the daily retry. The hub sensors show
    "unknown" and coordinator.py logs a warning; that is all that is needed.
    This only removes an issue left by a version before 20261111r7 and can
    go once those are no longer in use.
    """
    ir.async_delete_issue(hass, DOMAIN, f"hub_version_unknown_{entry.entry_id}")


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Register the integration's actions (R28).

    HA's `action-setup` rule: actions belong in async_setup, not in
    async_setup_entry, so they exist even while a hub's entry is not loaded
    and can then say so, instead of being an unknown action.

    R43: also starts the search for hubs on the LAN (discovery.py), which
    offers new hubs and follows configured ones to a new address.
    """
    _async_register_services(hass)
    async_start_discovery(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: LifeSmartConfigEntry) -> None:
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
        # On code 101 send_command takes the hub's clock and asks again, so
        # what comes back here is final (R34).
        discovery = await api.discover_devices()
        _LOGGER.debug("Raw discovery response: %s", discovery)
    except (asyncio.TimeoutError, OSError, KeyError, ValueError, TypeError) as err:
        _LOGGER.error("Failed to connect or discover devices: %s", err)
        await api.async_stop()
        raise ConfigEntryNotReady from err

    # R34 (quality scale `test-before-setup`): say what is wrong instead of
    # loading with no devices, which is what every hub error did before.
    failure = _setup_failure(discovery)
    if failure is not None:
        await api.async_stop()
        raise failure

    devices = []
    msg_data = discovery.get("msg")
    if isinstance(msg_data, list):
        devices = msg_data
    elif isinstance(msg_data, dict):
        devices = [dev for dev in msg_data.values() if isinstance(dev, dict)]

    if not devices:
        # Code 0 and nothing paired: the hub's own entities still work.
        _LOGGER.info("The LifeSmart hub at %s reports no sub-devices", entry.data["host"])
    else:
        _LOGGER.info("Successfully loaded %s devices from LifeSmart Hub.", len(devices))

    # Phase 1 / R9: hub identity (cfg:getver) feeds every hub-level entity
    # from one cached dict. D4 (R25): a coordinator re-reads it, and the hub
    # time zone, once a day. Failures are non-fatal — the hub entities show
    # the last known values and D17 raises a repair issue.
    # R28: only cfg:getver is read here. cfg:timezone is read in the
    # background once setup is done — a hub that does not answer it would
    # otherwise hold up every start for two timeouts.
    hub_coordinator = LifeSmartHubCoordinator(hass, entry, api, entry.data["host"])
    hub_info = await hub_coordinator.async_fetch(include_timezone=False)
    hub_coordinator.async_set_updated_data(hub_info)
    _async_drop_version_issue(hass, entry)

    # D15 (2026-05-24): single coordinator per hub replaces the per-entity
    # `async_track_time_interval` polling pattern (HA 2026.5 規範要求).
    coordinator = LifeSmartCoordinator(hass, entry, api, entry.data["host"])
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
    _async_adopt_hub_id(hass, entry, hub_key)
    hub_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        **hub_device_info_kwargs(hub_key, entry.title, hub_info),
    )

    scenes = await _async_fetch_scenes(api)

    # HA quality scale `runtime-data`: on the entry, not in hass.data. Home
    # Assistant removes it once the entry has unloaded.
    runtime = LifeSmartData(
        api=api,
        devices=devices,
        hub_info=hub_info,
        host=entry.data["host"],
        hub_key=hub_key,
        coordinator=coordinator,
        hub_coordinator=hub_coordinator,
        hub_device_id=hub_device.id,
        scenes=scenes,
        # Setup got this far, so the hub is answering.
        availability=HubAvailability(entry.data["host"]),
    )
    entry.runtime_data = runtime
    unsubs = runtime.unsubs

    @callback
    def _on_hub_info() -> None:
        # D4: daily cfg:getver — keep the device page current.
        info = hub_coordinator.data or {}
        runtime.hub_info = info
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

    async def _refresh_notify(_now: Any) -> None:
        # The 90 s re-subscription (LI §4: expires after 300 s) doubles as the
        # hub heartbeat for the `hub_unreachable` repair issue (R19).
        reply: Any = None
        try:
            reply = await api.configure_event_service(local_ip, api.local_port)
        except (asyncio.TimeoutError, OSError) as err:
            _LOGGER.debug("Failed to refresh OpenDev event service: %s", err)
            # R32: two of these in a row make the hub's entities unavailable
            # (availability.py logs it once); five minutes raise the issue.
            runtime.availability.record_failure(f"it is not answering ({type(err).__name__})")
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
        # The hub answered: it is reachable, whatever it said.
        if reachability.record_success():
            ir.async_delete_issue(hass, DOMAIN, issue_id_unreachable)
        if rejection(reply) == REJECTED_TOKEN:
            # R34: the token was changed on the hub while we were running.
            # Nothing we send is carried out, so the entities are as good as
            # unavailable; ask the user for the new token. Home Assistant
            # keeps a single reauth flow per entry, however often this runs.
            runtime.availability.record_failure("it rejects the token (code 101)")
            entry.async_start_reauth(hass)
            return
        # availability.py logs "available again" once, and only after it
        # logged the outage.
        runtime.availability.record_success()

    unsubs.append(async_track_time_interval(hass, _refresh_notify, timedelta(seconds=90)))

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

    entry.async_create_background_task(
        hass, hub_coordinator.async_load_timezone(), f"{DOMAIN} hub time zone"
    )


def _setup_failure(discovery: Any) -> Optional[Exception]:
    """What to raise for the hub's answer to the first `eps`, or None.

    * the token is rejected -> ConfigEntryAuthFailed: Home Assistant shows
      "reauthentication required" and opens the reauth form;
    * anything else that is not code 0 -> ConfigEntryNotReady: Home Assistant
      retries on its own and shows the message meanwhile. Such an answer has
      not been seen on a real hub, so it is not assumed to be permanent.
    """
    why = rejection(discovery)
    if why == REJECTED_TOKEN:
        return ConfigEntryAuthFailed(
            "The hub rejected the token (code 101 although the timestamp was correct)"
        )
    if why is not None:
        return ConfigEntryNotReady(
            "The hub answered code 101 without its time, so the clock could not be corrected"
        )
    if isinstance(discovery, dict) and discovery.get("code") == 0:
        return None
    code = discovery.get("code") if isinstance(discovery, dict) else type(discovery).__name__
    return ConfigEntryNotReady(f"The hub answered the device list request with {code!r}")


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

async def async_migrate_entry(hass: HomeAssistant, entry: LifeSmartConfigEntry) -> None:
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
            discovery = await api.discover_devices()  # corrects code 101 itself (R34)
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


async def async_unload_entry(hass: HomeAssistant, entry: LifeSmartConfigEntry) -> None:
    """Unload a config entry.

    R23: raises (translated by HA) when a platform fails to unload. The
    `hub_unreachable` issue is no longer deleted here: deleting on unload
    revives an issue the user ignored as soon as a reload re-creates it
    (dev blog 2026-10-28). It is linked to the entry instead, and setup
    deletes it once the hub answers.
    """
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    runtime = entry.runtime_data
    for unsub in runtime.unsubs:
        unsub()
    await runtime.api.async_stop()


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: LifeSmartConfigEntry, device_entry: dr.DeviceEntry,
) -> bool:
    """May the user delete this device from the device page? (R36)

    HA quality scale `stale-devices`. When a sub-device is removed from the
    hub, its device and entity registry entries stay behind in Home
    Assistant, and without this function the device page offers no way to
    delete them short of removing the whole hub.

    Yes only for a sub-device the hub no longer lists. Never for the hub
    device, a device that is still listed, or while the entry is not loaded
    (then there is no list to check against).

    Stale devices are not removed automatically. The rule asks for that only
    when the integration is sure, and we are not: how the hub's device list
    behaves when it misbehaves has not been observed, and a wrong removal
    would take the user's names and areas with it.
    """
    runtime = getattr(entry, "runtime_data", None)
    if runtime is None:
        return False
    # The latest `eps` snapshot (seeded from discovery at setup, refreshed
    # every 15 minutes and after a reload).
    listed = runtime.coordinator.data
    if listed is None:
        return False
    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        if identifier.startswith("hub_"):
            return False
        return identifier not in listed
    return False


# D8 (R25): hub configuration commands (LI §3.3.10) as actions. Each takes
# the config entry of the hub it acts on, so several hubs stay apart.
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
SERVICE_SET_HUB_TIMEZONE = "set_hub_timezone"
SERVICE_RENAME_DEVICE = "rename_device"
SERVICE_UPGRADE_HUB_FIRMWARE = "upgrade_hub_firmware"
SERVICE_FACTORY_RESET_HUB = "factory_reset_hub"


def _loaded_entries(hass: HomeAssistant) -> List[LifeSmartConfigEntry]:
    """This integration's entries that finished setup.

    Only a loaded entry has `runtime_data`: it is set during setup and
    removed by Home Assistant after unload.
    """
    return hass.config_entries.async_loaded_entries(DOMAIN)


def _entry_for_call(hass: HomeAssistant, call: ServiceCall) -> LifeSmartConfigEntry:
    """The loaded config entry an action names, or ServiceValidationError."""
    entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
    for entry in _loaded_entries(hass):
        if entry.entry_id == entry_id:
            return entry
    raise ServiceValidationError(f"{entry_id} is not a loaded LifeSmart hub")


def _raise_unless_ok(reply: Any, command: str) -> None:
    if not isinstance(reply, dict) or reply.get("code") != 0:
        raise HomeAssistantError(f"The hub rejected {command}: {reply}")


def _sub_device_me(
    hass: HomeAssistant, entry: LifeSmartConfigEntry, device_id: Optional[str],
) -> Optional[str]:
    """Map an HA device id to the LifeSmart `me` for cfg:devname.

    None means the hub itself: no device given, or the hub device chosen.
    """
    if not device_id:
        return None
    device = dr.async_get(hass).async_get(device_id)
    # R28: DeviceEntry.config_entries is deprecated (a device belongs to one
    # config entry; removed in HA 2027.10.0).
    if device is None or device.config_entry_id != entry.entry_id:
        raise ServiceValidationError(f"Device {device_id} does not belong to {entry.title}")
    for domain, identifier in device.identifiers:
        if domain != DOMAIN:
            continue
        return None if identifier.startswith("hub_") else identifier
    raise ServiceValidationError(f"Device {device_id} is not a LifeSmart device")


def _async_register_services(hass: HomeAssistant) -> None:
    """Called once from async_setup."""

    async def _handle_send_keys(call: ServiceCall) -> None:
        """Send IR keys through the hub that has the remote.

        R30: this used to send every key to every loaded hub, ignore what
        the hubs answered, and do nothing at all when no hub was loaded.
        """
        remote_id = call.data["remote_id"]
        keys = call.data["keys"]
        keys_to_send = [keys] if isinstance(keys, str) else list(keys)

        if call.data.get(ATTR_CONFIG_ENTRY_ID) is not None:
            targets = [_entry_for_call(hass, call).runtime_data]
        else:
            loaded = [entry.runtime_data for entry in _loaded_entries(hass)]
            if not loaded:
                raise ServiceValidationError("No LifeSmart hub is loaded")
            # remote.py records which remotes each hub has; a remote_id no
            # hub lists (e.g. added in the app since setup) goes to them all.
            owners = [hub for hub in loaded if remote_id in hub.remote_ids]
            targets = owners or loaded

        for key in keys_to_send:
            accepted = False
            last: Any = None
            for hub in targets:
                try:
                    reply = await hub.api.send_remote_key(remote_id, key)
                except (asyncio.TimeoutError, OSError) as err:
                    last = err
                    continue
                if isinstance(reply, dict) and reply.get("code") == 0:
                    accepted = True
                else:
                    last = reply
            if not accepted:
                raise HomeAssistantError(
                    f"No hub accepted key {key!r} for remote {remote_id}: {last!r}"
                )

    async def _handle_set_hub_timezone(call: ServiceCall) -> None:
        runtime = _entry_for_call(hass, call).runtime_data
        reply = await runtime.api.set_hub_timezone(
            call.data["timezone"], call.data["daylight_saving"]
        )
        _raise_unless_ok(reply, "cfg:timezone")
        await runtime.hub_coordinator.async_request_refresh()

    async def _handle_rename_device(call: ServiceCall) -> None:
        entry = _entry_for_call(hass, call)
        me = _sub_device_me(hass, entry, call.data.get("device_id"))
        reply = await entry.runtime_data.api.set_device_name(call.data["name"], me)
        _raise_unless_ok(reply, "cfg:devname")
        # Device names come from `eps` at setup; reload to show the new one.
        hass.config_entries.async_schedule_reload(entry.entry_id)

    async def _handle_upgrade_hub_firmware(call: ServiceCall) -> None:
        entry = _entry_for_call(hass, call)
        reply = await entry.runtime_data.api.upgrade_hub(call.data["reboot"])
        _raise_unless_ok(reply, "cfg:upgrade")

    async def _handle_factory_reset_hub(call: ServiceCall) -> None:
        entry = _entry_for_call(hass, call)
        if call.data["confirm"] is not True:
            raise ServiceValidationError("Set confirm to true to factory-reset the hub")
        _LOGGER.warning("Sending cfg:reset — %s returns to factory settings", entry.title)
        try:
            reply = await entry.runtime_data.api.factory_reset_hub()
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
            vol.Optional(ATTR_CONFIG_ENTRY_ID): str,
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

def generate_entity_id(
    device_type: Any, hub_id: Any, device_id: Any, idx: Optional[str] = None,
) -> str:
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
    hass: HomeAssistant, entry: LifeSmartConfigEntry, devices: list,
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


def _migrate_entity_ids(hass: HomeAssistant, entry: LifeSmartConfigEntry) -> None:
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
