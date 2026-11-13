"""Base entities (HA quality scale `common-modules`).

Every entity of this integration derives from `LifeSmartEntity`. It owns what
used to be repeated in each platform:

* the add / remove lifecycle: listeners go into `self._unsubs` and are
  released on removal;
* the HA 2026.11 in-place entity_id rename hook (R19);
* availability (quality scale `entity-unavailable`).

Availability has two parts:

1. The hub. When it stops answering (availability.py) every entity of that
   hub is unavailable.
2. The sub-device. LI §6.1 `stat`: 1 online, 0 offline. A sub-device entity is
   unavailable while its device reports 0. Only an explicit 0 counts: a
   missing or odd value leaves the entity available. The connectivity sensor
   is the exception, it exists to show that state.

Platform classes must not define `async_added_to_hass` /
`async_will_remove_from_hass` themselves: HA credits the rename hook only when
it sits on the same class as those methods (or a subclass), so an override
would need its own copy of the hook. Use `_subscribe`, `_async_initial_refresh`
and `_cleanup` instead.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, override

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .availability import HubAvailability
from .coordinator import LifeSmartCoordinator
from .device_info import hub_device_info, sub_device_info

# Virtual idx api.py dispatches the device-level `stat` under (R8-b).
STAT_IDX = "stat"


class LifeSmartEntity(Entity):
    """Lifecycle, rename hook and hub availability."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, availability: Optional[HubAvailability] = None) -> None:
        self._availability = availability
        self._unsubs: List[Callable[[], None]] = []

    @property
    @override
    def available(self) -> bool:
        """False while the hub is not answering."""
        return self._availability is None or self._availability.available

    @override
    async def async_added_to_hass(self) -> None:
        if self._availability is not None:
            self._unsubs.append(
                self._availability.async_add_listener(self._async_write_if_added)
            )
        await super().async_added_to_hass()
        self._subscribe()
        await self._async_initial_refresh()

    @override
    async def async_will_remove_from_hass(self) -> None:
        self._cleanup()
        while self._unsubs:
            self._unsubs.pop()()
        await super().async_will_remove_from_hass()

    @callback
    @override
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Opt in to in-place entity_id renames (HA 2026.11+, R19).

        Nothing is keyed on the entity_id: push listeners key on (me, idx),
        coordinator and availability listeners on the bound method. Without
        this method HA keeps removing and re-adding the entity on a rename
        (compatibility path, removed in 2027.11).
        """
        super().async_entity_id_changed(old_entity_id)

    def _subscribe(self) -> None:
        """Register listeners; append each unsubscribe to `self._unsubs`."""

    async def _async_initial_refresh(self) -> None:
        """Read the first value once the entity is added, if it needs one."""

    def _cleanup(self) -> None:
        """Cancel timers or tasks the entity started itself."""

    @callback
    def _async_write_if_added(self) -> None:
        """Write the state, unless the entity is not added to hass (yet)."""
        if self.hass is not None:
            self.async_write_ha_state()


class LifeSmartDeviceEntity(LifeSmartEntity):
    """An entity of one sub-device.

    `idx` is the channel whose pushed values go to `_handle_state_value`
    (None: no channel, e.g. signal strength). With a coordinator, each `eps`
    snapshot goes to `_update_from_device`.
    """

    # False: stay available while the device is offline (connectivity sensor).
    _follows_device_stat = True

    def __init__(
        self,
        api: Any,
        device: Dict[str, Any],
        idx: Optional[str] = None,
        *,
        hub_device_id: Optional[str] = None,
        coordinator: Optional[LifeSmartCoordinator] = None,
        availability: Optional[HubAvailability] = None,
        device_name: Optional[str] = None,
        default_name: str = "LifeSmart Device",
        default_model: str = "Unknown",
    ) -> None:
        super().__init__(availability)
        self._api = api
        self._device = device
        self._idx = idx
        self._coordinator = coordinator
        self._device_online = True
        self._set_online(device.get(STAT_IDX))
        # R19: built in one go by device_info.py — DeviceInfo is a dataclass
        # from HA 2026.11, so no item assignment. via_device_id (D22) and the
        # sw_version handling live there.
        self._attr_device_info = sub_device_info(
            device, hub_device_id,
            name=device_name, default_name=default_name, default_model=default_model,
        )

    @property
    @override
    def available(self) -> bool:
        if not super().available:
            return False
        return self._device_online or not self._follows_device_stat

    @override
    def _subscribe(self) -> None:
        me = self._device["me"]
        if self._idx is not None:
            self._unsubs.append(
                self._api.register_state_listener(me, self._idx, self._handle_state_value)
            )
        self._unsubs.append(
            self._api.register_state_listener(me, STAT_IDX, self._handle_stat_value)
        )
        if self._coordinator is not None:
            self._unsubs.append(
                self._coordinator.async_add_listener(self._handle_coordinator_update)
            )

    def _set_online(self, stat: Any) -> bool:
        """Take a `stat` value. Return True if online / offline changed."""
        if isinstance(stat, bool) or not isinstance(stat, (int, float)):
            return False
        online = stat != 0
        if online == self._device_online:
            return False
        self._device_online = online
        return True

    @callback
    def _handle_stat_value(self, val: Any) -> None:
        """Pushed `stat` (LI §4 NOTIFY)."""
        if self._set_online(val):
            self._async_write_if_added()

    def _device_from_coordinator(self) -> Optional[Dict[str, Any]]:
        """This device in the coordinator's latest `eps` snapshot, if any."""
        if self._coordinator is None or self._coordinator.data is None:
            return None
        device = self._coordinator.data.get(self._device["me"])
        return device if isinstance(device, dict) else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """A new `eps` snapshot: the fallback for a lost push."""
        device = self._device_from_coordinator()
        if device is None:
            return
        changed = self._set_online(device.get(STAT_IDX))
        if self._update_from_device(device) or changed:
            self._async_write_if_added()

    def _update_from_device(self, device: Dict[str, Any]) -> bool:
        """Take this entity's value from a snapshot. Return True if it did."""
        return False

    @callback
    def _handle_state_value(self, val: Any) -> None:
        """A pushed value for `idx`."""


class LifeSmartHubEntity(LifeSmartEntity):
    """An entity of the hub itself, on the hub device."""

    def __init__(
        self,
        hub_key: str,
        title: str,
        hub_info: Dict[str, Any],
        availability: Optional[HubAvailability] = None,
    ) -> None:
        super().__init__(availability)
        # Same kwargs as __init__.py's registry call (device_info.py): the
        # registry sees one consistent hub device.
        self._attr_device_info = hub_device_info(hub_key, title, hub_info)
