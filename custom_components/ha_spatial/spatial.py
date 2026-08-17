"""Canonical spatial layout store (decision 4A).

Wraps Home Assistant's Store helper: versioned with a migration function from
v1, debounced writes (decision 12A), and validation on every save (structural
via voluptuous + semantic geometry, decision 8A). Built to pass the M1 accuracy
harness: a ground-truth layout round-trips through the store unchanged.

Trust core (eng lock 1A/19A/OV2/OV3): every accepted save first pushes the
PREVIOUS in-memory layout to the revision ring (revisions.py), and async_load
VALIDATES what it reads — a missing/corrupt primary with a non-empty ring
surfaces a restore_available signal instead of silently starting empty.
"""
from __future__ import annotations

import copy
import logging
import os
from collections.abc import Callable
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import SAVE_DELAY, STORAGE_KEY, STORAGE_MINOR_VERSION, STORAGE_VERSION
from .geometry import GeometryError, validate_layout_geometry
from .revisions import RevisionRing
from .schema import check_writable_version, validate_layout_structure

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
        self._revisions = RevisionRing(hass)
        self._layout: dict[str, Any] = empty_layout()
        self._restore_available = False
        # True while the in-memory layout is the untouched recovery placeholder:
        # the primary failed to load and the real model lives only in the ring.
        # The placeholder must NEVER be flushed as a valid primary (codex P2).
        self._recovery_placeholder = False
        # The ONE pending debounced flush. SpatialStore owns a single timer so
        # the ring and primary never race on independent delay_save timers.
        self._flush_unsub: Callable[[], None] | None = None

    @property
    def revisions(self) -> RevisionRing:
        """The revision ring (history/restore read path)."""
        return self._revisions

    @property
    def restore_available(self) -> bool:
        """True when the primary layout failed to load but revisions exist."""
        return self._restore_available

    async def async_load(self) -> dict[str, Any]:
        """Load from disk, VALIDATING what comes back (eng lock: never silent).

        - Primary missing/corrupt + non-empty ring → keep an empty in-memory
          layout and expose restore_available (surfaced via layout/get + info).
        - Ring empty + primary missing (no store file, no load error) → fresh
          install, no signal — the ONLY non-recovery empty case.
        - ANY other primary load failure (unreadable store, validation failure)
          → recovery placeholder: never flush it over the primary, even when
          the ring is also unreadable/empty (a downgrade can break BOTH stores;
          an unconditional flush would then erase the newer primary).
        """
        await self._revisions.async_load()
        self._restore_available = False
        primary_failed = False
        try:
            data = await self._store.async_load()
        except Exception as err:  # e.g. UnsupportedStorageVersionError
            _LOGGER.error("Layout store unreadable (%s); checking revisions", err)
            data = None
            primary_failed = True
        if data is None:
            self._layout = empty_layout()
            fresh_install = (
                not primary_failed
                and not self._revisions
                and not os.path.exists(self._store.path)
            )
            if fresh_install:
                return self._layout
            # Not a fresh install: the placeholder must never be flushed as a
            # valid primary. Ring emptiness only changes the wording/signal.
            self._recovery_placeholder = True
            if len(self._revisions):
                self._restore_available = True
                _LOGGER.warning(
                    "No usable layout in primary store but %d revision(s) exist; "
                    "restore is available via ha_spatial/layout/history + layout/restore",
                    len(self._revisions),
                )
            else:
                _LOGGER.error(
                    "Layout store is unreadable and the revision ring is empty — "
                    "starting with an empty placeholder layout that will NOT be "
                    "flushed over the primary store"
                )
            return self._layout
        try:
            self._layout = validate_layout(data)
        except (vol.Invalid, GeometryError, TypeError) as err:
            # TypeError: belt-and-braces for validator leaks (corrupt JSON with
            # null numerics) — a corrupt store enters recovery, never aborts.
            _LOGGER.error("Stored layout failed validation: %s", err)
            self._layout = empty_layout()
            self._recovery_placeholder = True
            if len(self._revisions):
                self._restore_available = True
            else:
                _LOGGER.error(
                    "Stored layout is invalid and the revision ring is empty — "
                    "starting with an empty placeholder layout that will NOT be "
                    "flushed over the primary store"
                )
        return self._layout

    @callback
    def async_get(self) -> dict[str, Any]:
        """Return the current in-memory layout."""
        return self._layout

    async def async_save(self, layout: Any) -> dict[str, Any]:
        """Validate and persist a layout (debounced disk write, decision 12A).

        BEFORE accepting the new layout, the PREVIOUS in-memory layout is pushed
        to the revision ring (in-memory), so the debounce window can never be
        the only place a good layout lives. The disk flush is a single ordered
        callback: ring first, then primary (see _async_ordered_flush).

        Conservative writing (eng lock 2A/OV4): if the CURRENT in-memory layout
        is newer than KNOWN_LAYOUT_VERSION this build is READ-ONLY — every save
        is rejected with typed error ``unsupported_version`` before anything is
        captured or persisted; the same guard rejects a newer INCOMING payload.
        """
        check_writable_version(self._layout)  # downgraded build: read-only, period
        check_writable_version(layout)
        validated = validate_layout(layout)
        if self._recovery_placeholder:
            # Accepted save while in recovery: the user is rebuilding on top of
            # the placeholder — the placeholder itself is not worth a revision,
            # and recovery mode ends here.
            self._recovery_placeholder = False
            self._restore_available = False
        else:
            await self._revisions.async_push(self._layout, validated)
        validated["updated_at"] = dt_util.utcnow().isoformat()
        self._layout = validated
        self._schedule_flush()
        return validated

    async def async_restore(self, index: int) -> dict[str, Any] | None:
        """Restore revision ``index`` as the current layout.

        Writes a pre-restore revision of the CURRENT layout first (forced, so a
        restore is itself undoable) — EXCEPT in recovery, where the current
        layout is the empty placeholder and capturing it would only evict a
        real backup. Returns None for an out-of-range index.
        """
        check_writable_version(self._layout)  # downgraded build: read-only, period
        revision = self._revisions.async_get_revision(index)
        if revision is None:
            return None
        check_writable_version(revision["layout"])  # a newer build's revision stays read-only
        # Deepcopy: voluptuous shares nested mutables (ALLOW_EXTRA, metadata),
        # so without this the live layout would alias the ring entry.
        body = validate_layout(copy.deepcopy(revision["layout"]))
        if not self._recovery_placeholder and not self._revisions.async_contains_layout(
            self._layout
        ):
            # Normal restore: capture the CURRENT layout first so the restore is
            # itself undoable — unless it is already preserved in the ring (a
            # re-restore / ping-pong would only flood the cap and evict genuine
            # backups). In recovery the current layout is the empty placeholder
            # — nothing worth preserving at all.
            await self._revisions.async_push(self._layout, body, force=True)
        body["updated_at"] = dt_util.utcnow().isoformat()
        self._layout = body
        self._schedule_flush()
        self._restore_available = False
        self._recovery_placeholder = False
        return self._layout

    @callback
    def _schedule_flush(self) -> None:
        """Schedule the single debounced flush (2s, decision 12A).

        Re-saves within the window reuse the pending timer; the flush writes
        whatever is current when it fires — same coalescing as HA's delay_save.
        """
        if self._flush_unsub is None:
            self._flush_unsub = async_call_later(
                self._hass, SAVE_DELAY, self._async_ordered_flush
            )

    async def _async_flush_ring(self) -> None:
        """Flush the ring until it is clean.

        A push landing DURING an in-flight ring write re-marks the ring dirty
        (clear-before-await in async_flush), so a single flush call is not
        enough — loop until the ring on disk covers every in-memory revision.
        """
        while self._revisions.dirty:
            await self._revisions.async_flush()

    async def _async_ordered_flush(self, _now: Any = None) -> None:
        """The ONE disk-write path for edits: ring BEFORE primary, always.

        Ordering invariant: a crash mid-flush may lose the newest primary edit,
        but can never durably commit a new primary whose pre-edit revision was
        not yet on disk. The recovery placeholder is never written as primary.

        The layout to write is SNAPSHOTED (deep-copied) before the ring flush:
        registry reconciliation mutates the live layout dict IN PLACE before
        calling async_save, so holding the reference across the ring-flush
        await could pick up reconciled state and commit it before that later
        save's own pre-edit revision is on disk.
        """
        self._flush_unsub = None
        snapshot = copy.deepcopy(self._layout)
        await self._async_flush_ring()
        if self._recovery_placeholder:
            return
        await self._store.async_save(snapshot)

    async def async_save_now(self) -> None:
        """Flush revision ring THEN layout to disk immediately (e.g. on shutdown).

        Same ordering invariant as _async_ordered_flush; cancels any pending
        debounced flush so shutdown never double-writes.

        Recovery guard (codex P2): while the in-memory layout is the untouched
        recovery placeholder, flush the ring only — writing the placeholder as
        a valid primary would erase the restore_available signal and orphan the
        real model that lives only in the ring.
        """
        if self._flush_unsub is not None:
            self._flush_unsub()
            self._flush_unsub = None
        snapshot = copy.deepcopy(self._layout)  # same in-place-mutation hazard
        while self._revisions.dirty:
            await self._revisions.async_save_now()
        if self._recovery_placeholder:
            return
        await self._store.async_save(snapshot)
