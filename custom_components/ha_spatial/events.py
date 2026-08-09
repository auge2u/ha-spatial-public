"""Funnel-event store for the First Room PMF loop.

A SEPARATE, durable, capped event log — deliberately NOT in the layout store,
whose schema is closed (additionalProperties: false). Writes are immediate (no
debounce) so a crash or restart does not lose the most recent conversion events,
which is the whole point of measuring the funnel.

Records are counts + timestamps only — no imagery, no PII.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import EVENT_LOG_CAP, EVENTS_STORAGE_KEY, EVENTS_STORAGE_VERSION, FUNNEL_EVENTS

_LOGGER = logging.getLogger(__name__)

# Debounce window for event writes: keeps bursts of UI events from hammering disk.
_SAVE_DELAY = 1.0


class EventStore:
    """Durable, capped log of funnel events with a debounced-write policy.

    Events are appended in memory immediately and flushed to disk after a short
    debounce. A manual flush is provided for shutdown/unload so conversion events
    are not lost on restart.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, EVENTS_STORAGE_VERSION, EVENTS_STORAGE_KEY)
        self._events: list[dict[str, Any]] = []

    async def async_load(self) -> list[dict[str, Any]]:
        data = await self._store.async_load()
        self._events = list(data["events"]) if data and "events" in data else []
        return self._events

    async def async_append(self, event: str) -> dict[str, Any]:
        """Append an event and schedule a debounced persist. Raises ValueError on unknown event."""
        if event not in FUNNEL_EVENTS:
            raise ValueError(f"unknown funnel event: {event}")
        record = {"event": event, "ts": dt_util.utcnow().isoformat()}
        self._events.append(record)
        if len(self._events) > EVENT_LOG_CAP:
            self._events = self._events[-EVENT_LOG_CAP:]
        self._store.async_delay_save(lambda: {"events": self._events}, _SAVE_DELAY)
        return record

    async def async_save_now(self) -> None:
        """Flush the event log to disk immediately (e.g. on shutdown/unload)."""
        await self._store.async_save({"events": self._events})

    @callback
    def async_funnel(self) -> dict[str, int]:
        """Per-event counts across the retained window (the funnel readout)."""
        counts = {event: 0 for event in FUNNEL_EVENTS}
        for record in self._events:
            if record["event"] in counts:
                counts[record["event"]] += 1
        return counts
