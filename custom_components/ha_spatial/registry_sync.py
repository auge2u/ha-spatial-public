"""HA->spatial registry sync adapter (decisions 2A / 3A / T2 / 12A).

Listens to area/floor/entity/device registry events and runs a debounced full
reconciliation (decision 12A: coalesce startup + edit bursts before saving
once). The reconciliation logic itself is pure (reconcile.py); this module only
snapshots the live registries into plain maps.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from homeassistant.core import callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
)
from homeassistant.helpers.event import async_call_later

from .reconcile import reconcile_layout, resolve_effective_areas

if TYPE_CHECKING:
    from homeassistant.core import Event, HomeAssistant

    from .spatial import SpatialStore

_LOGGER = logging.getLogger(__name__)
RECONCILE_COOLDOWN = 0.5  # seconds; debounce window over event bursts (12A)


class RegistrySync:
    """Keeps the spatial layout's identity fields in step with HA registries."""

    def __init__(self, hass: "HomeAssistant", store: "SpatialStore") -> None:
        self._hass = hass
        self._store = store
        self._unsubs: list[Callable[[], None]] = []
        self._cancel_timer: Callable[[], None] | None = None

    async def async_setup(self) -> None:
        """Initial reconciliation pass, then subscribe to registry events."""
        await self.async_reconcile()
        bus = self._hass.bus
        self._unsubs = [
            bus.async_listen(ar.EVENT_AREA_REGISTRY_UPDATED, self._handle_event),
            bus.async_listen(fr.EVENT_FLOOR_REGISTRY_UPDATED, self._handle_event),
            bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self._handle_event),
            bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, self._handle_event),
        ]

    @callback
    def _handle_event(self, event: "Event") -> None:
        """Debounce: reset the timer so a burst collapses into one reconcile."""
        if self._cancel_timer is not None:
            self._cancel_timer()
        self._cancel_timer = async_call_later(self._hass, RECONCILE_COOLDOWN, self._async_scheduled)

    async def _async_scheduled(self, _now) -> None:
        self._cancel_timer = None
        await self.async_reconcile()

    async def async_reconcile(self) -> bool:
        """Snapshot the registries and apply HA identity state to the layout."""
        area_reg = ar.async_get(self._hass)
        floor_reg = fr.async_get(self._hass)
        entity_reg = er.async_get(self._hass)
        device_reg = dr.async_get(self._hass)

        area_ids = set(area_reg.areas)
        area_names = {aid: area.name for aid, area in area_reg.areas.items()}
        area_floors = {aid: area.floor_id for aid, area in area_reg.areas.items()}
        floor_ids = set(floor_reg.floors)
        device_areas = {did: device.area_id for did, device in device_reg.devices.items()}
        entities = [(e.entity_id, e.area_id, e.device_id) for e in entity_reg.entities.values()]
        entity_areas = resolve_effective_areas(entities, device_areas)

        layout = self._store.async_get()
        changed = reconcile_layout(
            layout,
            area_ids=area_ids,
            area_names=area_names,
            area_floors=area_floors,
            floor_ids=floor_ids,
            entity_areas=entity_areas,
        )
        if changed:
            await self._store.async_save(layout)
        return changed

    async def async_unload(self) -> None:
        """Cancel listeners and any pending debounced reconcile."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None
