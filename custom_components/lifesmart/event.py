"""Platform for LifeSmart button events (D9, R25).

Buttons the hub reports as read-only channels:

* LI §6.3.5 Multi-control Accessory `SL_MC_ND1/2/3`: B1-B3, v==1 press,
  v==0 release.
* LI §6.3.6 CUBE Clicker (old) `SL_SC_BB`: B, v==1 press, v==0 release.
* LI §6.3.7 CUBE Clicker (new) `SL_SC_BB_V2`: BN, v==1 press, v==2
  double-press, v==255 press and hold.

Values map to HA's standard button event types. Events come only from
push (NOTIFY): a button state read from `eps` is not a press.

R27 (2026-11-10): the event types are plain strings, not ButtonEventType
members. HA 2026.12 deprecates `MULTI_PRESS_END` and `ATTR_MULTI_PRESS_COUNT`
(removed in 2027.5.0; warning on access) in favour of `SINGLE_PRESS`,
`MULTI_PRESS` and `ATTR_PRESS_COUNT`, which 2026.11 does not have yet. The
string values are the same in both, so they work on 2026.11 and 2026.12
without a warning. Import the constants once the minimum HA is 2026.12.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple, override

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import generate_entity_id
from .availability import HubAvailability
from .coordinator import LifeSmartCoordinator
from .entity import LifeSmartDeviceEntity
from .models import LifeSmartConfigEntry

_LOGGER = logging.getLogger(__name__)

# Read-only platform fed by push and the shared coordinator: nothing to limit
# (HA quality scale `parallel-updates`).
PARALLEL_UPDATES = 0

# ButtonEventType values (HA 2026.12 names in comments).
PRESS_START = "press_start"            # PRESS_START: button went down
PRESS_END = "press_end"                # PRESS_END: released, not a long press
SINGLE_PRESS = "single_press"          # SINGLE_PRESS: device counted one press
MULTI_PRESS = "multi_press"            # MULTI_PRESS: device counted 2 or more
LONG_PRESS_START = "long_press_start"  # LONG_PRESS_START
ATTR_PRESS_COUNT = "press_count"       # ATTR_PRESS_COUNT

# v -> (event type, extra attributes)
_PRESS_RELEASE: Dict[int, Tuple[str, Optional[Dict[str, Any]]]] = {
    1: (PRESS_START, None),
    0: (PRESS_END, None),
}
# The new Clicker reports gestures it has already counted (LI §6.3.7).
_CLICKER_V2: Dict[int, Tuple[str, Optional[Dict[str, Any]]]] = {
    1: (SINGLE_PRESS, None),
    2: (MULTI_PRESS, {ATTR_PRESS_COUNT: 2}),
    255: (LONG_PRESS_START, None),
}

# devtype -> (button channels, value map)
BUTTON_CHANNELS: Dict[str, Tuple[Tuple[str, ...], Dict[int, Tuple[str, Optional[Dict[str, Any]]]]]] = {
    "SL_MC_ND1": (("B1",), _PRESS_RELEASE),
    "SL_MC_ND2": (("B1", "B2"), _PRESS_RELEASE),
    "SL_MC_ND3": (("B1", "B2", "B3"), _PRESS_RELEASE),
    "SL_SC_BB": (("B",), _PRESS_RELEASE),
    "SL_SC_BB_V2": (("BN",), _CLICKER_V2),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LifeSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LifeSmart button events."""
    runtime = config_entry.runtime_data
    api = runtime.api
    hub_device_id = runtime.hub_device_id
    entities: List[EventEntity] = []
    for device in runtime.devices:
        if not isinstance(device, dict) or not isinstance(device.get("me"), str):
            continue
        spec = BUTTON_CHANNELS.get(device.get("devtype"))  # type: ignore[arg-type]
        if spec is None:
            continue
        channels, value_map = spec
        data = device.get("data") or {}
        for idx in channels:
            # Like the battery guard: create only what the firmware reports.
            if idx in data:
                entities.append(
                    LifeSmartButtonEvent(
                        api, device, idx, value_map, hub_device_id,
                        coordinator=runtime.coordinator,
                        availability=runtime.availability,
                    )
                )
    async_add_entities(entities)


class LifeSmartButtonEvent(LifeSmartDeviceEntity, EventEntity):
    """One button channel of a LifeSmart sub-device.

    The coordinator is only the fallback for the device's `stat` (R32): a
    button value read from `eps` is a state, not a press, and fires nothing.
    """

    _attr_device_class = EventDeviceClass.BUTTON

    def __init__(
        self,
        api: Any,
        device: Dict[str, Any],
        idx: str,
        value_map: Dict[int, Tuple[str, Optional[Dict[str, Any]]]],
        hub_device_id: Optional[str] = None,
        coordinator: Optional[LifeSmartCoordinator] = None,
        availability: Optional[HubAvailability] = None,
    ) -> None:
        super().__init__(
            api, device, idx,
            hub_device_id=hub_device_id, coordinator=coordinator,
            availability=availability,
        )
        self._value_map = value_map
        me = device["me"]
        agt = device.get("agt", "")
        label = (device.get("data", {}).get(idx, {}).get("name") or "").replace("{$EPN}", "").strip()
        self._attr_name = label or idx
        self._attr_unique_id = f"event_{agt}_{me}_{idx}"
        self.entity_id = f"event.{generate_entity_id(device.get('devtype'), agt, me, idx)}"
        self._attr_event_types = sorted({event for event, _ in value_map.values()})

    @callback
    @override
    def _handle_state_value(self, val: Any) -> None:
        mapped = self._value_map.get(int(val)) if isinstance(val, (int, float)) else None
        if mapped is None:
            _LOGGER.debug("Ignoring %s %s value %s", self._device["me"], self._idx, val)
            return
        event_type, attributes = mapped
        self._trigger_event(event_type, attributes)
        self._async_write_if_added()
