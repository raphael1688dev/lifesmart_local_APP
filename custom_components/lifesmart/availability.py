"""Whether a hub is answering, shared by all of that hub's entities.

HA quality scale `entity-unavailable` and `log-when-unavailable`. The source
is the 90 s cfg:notify re-subscription in __init__.py, which every loaded hub
already sends: it is the most frequent request there is, so it notices a
silent hub long before the 15 min `eps` poll would.

One missed refresh is already two unanswered datagrams (the request is
re-sent once, D18). Two missed refreshes in a row mark the hub unavailable;
the first answer after that marks it available again.
"""
from __future__ import annotations

import logging
from typing import Callable, List

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

# Missed 90 s refreshes in a row before the entities go unavailable: about
# three minutes at the latest. One alone is not enough, UDP loses packets.
FAILURES_BEFORE_UNAVAILABLE = 2


class HubAvailability:
    """Tracks one hub. Tells its listeners when the answer changes.

    Logs once, at info, when the hub stops answering and once when it is back
    (quality scale `log-when-unavailable`).
    """

    def __init__(self, host: str, failures_before_unavailable: int = FAILURES_BEFORE_UNAVAILABLE) -> None:
        self._host = host
        self._threshold = failures_before_unavailable
        self._failures = 0
        self._available = True
        self._listeners: List[Callable[[], None]] = []

    @property
    def available(self) -> bool:
        return self._available

    @callback
    def record_success(self) -> None:
        """The hub answered."""
        self._failures = 0
        if self._available:
            return
        self._available = True
        _LOGGER.info("LifeSmart hub %s is available again", self._host)
        self._notify()

    @callback
    def record_failure(self, reason: object = None) -> None:
        """The hub did not answer, or answers but refuses us (R34: token).

        `reason` completes "LifeSmart hub <host> is unavailable: ...".
        """
        self._failures += 1
        if not self._available or self._failures < self._threshold:
            return
        self._available = False
        _LOGGER.info(
            "LifeSmart hub %s is unavailable: %s. Its entities are unavailable until that clears",
            self._host, reason if reason else "it is not answering",
        )
        self._notify()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call `listener` whenever `available` changes. Returns the unsubscribe."""
        self._listeners.append(listener)

        def _unsub() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)
        return _unsub

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()
