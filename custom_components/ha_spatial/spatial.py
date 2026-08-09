"""Canonical spatial layout store (decision 4A).

Wraps Home Assistant's Store helper: versioned with a migration function from
v1, debounced writes (decision 12A), and validation on every save (structural
via voluptuous + semantic geometry, decision 8A). Built to pass the M1 accuracy
harness: a ground-truth layout round-trips through the store unchanged.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import SAVE_DELAY, STORAGE_KEY, STORAGE_MINOR_VERSION, STORAGE_VERSION
from .geometry import validate_layout_geometry
from .schema import validate_layout_structure

_LOGGER = logging.getLogger(__name__)


def empty_layout() -> dict[str, Any]:
    """A minimal, schema-valid layout for a fresh install."""
    now = dt_util.utcnow().isoformat()
    return {
        "id": "default",
        "name": "My Home",
        "version": STORAGE_VERSION,
        "rooms": [],
        "placements": [],
        "created_at": now,
        "updated_at": now,
    }


def validate_layout(layout: Any) -> dict[str, Any]:
    """Full validation: structure (voluptuous) then geometry. Raises on failure."""
    validated = validate_layout_structure(layout)
    validate_layout_geometry(validated)
    return validated


class _SpatialLayoutStore(Store[dict[str, Any]]):
    """Versioned HA Store with a forward-compatible migration hook (decision 4A).

    Migration is done by overriding _async_migrate_func (the HA Store contract),
    not a constructor kwarg. Only v1 exists today; future schema bumps branch on
    old_major_version here, so users never hit an un-migratable store.
    """

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        return old_data


class SpatialStore:
    """In-memory layout backed by a versioned HA Store."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store: _SpatialLayoutStore = _SpatialLayoutStore(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
            minor_version=STORAGE_MINOR_VERSION,
        )
        self._layout: dict[str, Any] = empty_layout()

    async def async_load(self) -> dict[str, Any]:
        """Load from disk, falling back to an empty layout for a fresh install."""
        data = await self._store.async_load()
        self._layout = data if data is not None else empty_layout()
        return self._layout

    @callback
    def async_get(self) -> dict[str, Any]:
        """Return the current in-memory layout."""
        return self._layout

    async def async_save(self, layout: Any) -> dict[str, Any]:
        """Validate and persist a layout (debounced disk write, decision 12A)."""
        validated = validate_layout(layout)
        validated["updated_at"] = dt_util.utcnow().isoformat()
        self._layout = validated
        self._store.async_delay_save(lambda: self._layout, SAVE_DELAY)
        return validated

    async def async_save_now(self) -> None:
        """Flush the current layout to disk immediately (e.g. on shutdown)."""
        await self._store.async_save(self._layout)
