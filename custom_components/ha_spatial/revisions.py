"""Layout revision ring (eng lock 1A/19A/OV2/OV3) — the model-backup guarantee.

A SEPARATE HA Store (``ha_spatial.layout_revisions``, own version) holding the
most recent pre-edit layouts, capped by count and by a byte budget. SpatialStore
pushes the PREVIOUS in-memory layout synchronously BEFORE accepting a new save,
coalesced to one revision per 60s editing burst UNLESS the change is structural
— and ANY persisted-field change (polygon, origin, name, placement position,
calibration, unknown extras; only ``updated_at`` is volatile) counts as
structural. When in doubt, capture.

Cross-store semantics: the ring write happens first (in-memory + delay_save),
then the layout debounce proceeds. Restore tolerates skew — it picks a revision
and never requires the two stores to agree.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    REVISION_COALESCE_SECONDS,
    REVISION_RING_CAP,
    REVISION_RING_MAX_BYTES,
    REVISIONS_STORAGE_KEY,
    REVISIONS_STORAGE_MINOR_VERSION,
    REVISIONS_STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

# Module-level indirection so tests can pin the clock for coalescing tests.
_monotonic = time.monotonic


def _structural_signature(layout: dict[str, Any]) -> str | None:
    """A canonical hash of everything PERSISTED in the layout, minus volatiles.

    Any persisted-field change counts as structural: room ids/names/origins/
    rotations/heights/area bindings, placement positions/room links, calibration,
    and unknown forward-tolerance extras. Only ``updated_at`` (rewritten on every
    save) is excluded. Returns None when the layout cannot be serialized —
    callers must treat None as "unknown", i.e. never equal to anything, so a
    doubtful change is captured.
    """
    try:
        pruned = {k: v for k, v in layout.items() if k != "updated_at"}
        return hashlib.sha256(
            json.dumps(pruned, sort_keys=True, default=str).encode()
        ).hexdigest()
    except (TypeError, ValueError):
        return None


class RevisionRing:
    """Capped, durable ring of pre-edit layout snapshots."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass,
            REVISIONS_STORAGE_VERSION,
            REVISIONS_STORAGE_KEY,
            minor_version=REVISIONS_STORAGE_MINOR_VERSION,
        )
        self._revisions: list[dict[str, Any]] = []
        self._last_capture_mono: float | None = None
        self._dirty = False

    async def async_load(self) -> list[dict[str, Any]]:
        """Load the ring, quarantining malformed entries.

        The ring is the safety net — its own load must NEVER break startup. An
        unreadable store falls back to an empty ring (logged); entries missing
        a dict ``layout`` or a string ``ts`` are dropped with a warning, so
        history/restore can never KeyError on a malformed entry.
        """
        try:
            data = await self._store.async_load()
        except Exception as err:  # noqa: BLE001 — the backup must not be a SPOF
            _LOGGER.error("Revision ring unreadable (%s); starting with an empty ring", err)
            self._revisions = []
            self._dirty = False
            return self._revisions
        if not isinstance(data, dict) or not isinstance(data.get("revisions"), list):
            if data is not None:
                _LOGGER.warning("Revision ring has an unexpected shape; starting empty")
            self._revisions = []
            self._dirty = False
            return self._revisions
        valid: list[dict[str, Any]] = []
        for i, entry in enumerate(data["revisions"]):
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("layout"), dict)
                and isinstance(entry.get("ts"), str)
            ):
                valid.append(entry)
            else:
                _LOGGER.warning("Dropping malformed revision entry at index %d", i)
        self._revisions = valid
        self._dirty = False
        return self._revisions

    def __len__(self) -> int:
        return len(self._revisions)

    async def async_push(
        self,
        previous: dict[str, Any],
        incoming: dict[str, Any] | None = None,
        *,
        force: bool = False,
    ) -> bool:
        """Capture ``previous`` as a revision. Returns True when captured.

        Coalescing: a non-structural change within REVISION_COALESCE_SECONDS of
        the last capture is skipped (one revision per editing burst).
        ``incoming`` is the layout about to replace ``previous``; the structural
        comparison is between the two. ``force`` bypasses coalescing (used for
        the pre-restore revision).

        This updates memory ONLY and marks the ring dirty — the disk flush is
        owned by SpatialStore's single ordered flush (ring before primary), so
        the ring never races the primary on an independent timer.
        """
        if not previous:
            return False
        now = _monotonic()
        if not force and self._last_capture_mono is not None:
            sig_previous = _structural_signature(previous)
            sig_incoming = _structural_signature(incoming) if incoming is not None else None
            # None means "cannot hash" — in doubt, capture.
            structural = (
                incoming is None
                or sig_previous is None
                or sig_incoming is None
                or sig_previous != sig_incoming
            )
            if not structural and now - self._last_capture_mono < REVISION_COALESCE_SECONDS:
                return False
        self._revisions.append(
            {"ts": dt_util.utcnow().isoformat(), "layout": copy.deepcopy(previous)}
        )
        self._last_capture_mono = now
        self._evict()
        self._dirty = True
        return True

    @property
    def dirty(self) -> bool:
        """True when in-memory revisions have not been flushed to disk."""
        return self._dirty

    async def async_flush(self) -> None:
        """Persist pending revisions if dirty (called by the ordered flush).

        The dirty flag is cleared BEFORE the await: an async_push landing while
        the write is in flight re-marks the ring dirty, and the caller's flush
        loop persists it in a second pass — the flag is never cleared for data
        the write did not cover.
        """
        if not self._dirty:
            return
        self._dirty = False
        try:
            await self._store.async_save({"revisions": self._revisions})
        except Exception:
            self._dirty = True  # write failed — the data still needs a flush
            raise

    @callback
    def async_history(self) -> list[dict[str, Any]]:
        """Revision index without bodies: index, timestamp, entity counts."""
        history: list[dict[str, Any]] = []
        for i, rev in enumerate(self._revisions):
            layout = rev.get("layout") if isinstance(rev, dict) else None
            layout = layout if isinstance(layout, dict) else {}
            history.append(
                {
                    "index": i,
                    "ts": rev.get("ts") if isinstance(rev, dict) else None,
                    "rooms": len(layout.get("rooms") or []),
                    "placements": len(layout.get("placements") or []),
                }
            )
        return history

    @callback
    def async_get_revision(self, index: int) -> dict[str, Any] | None:
        """Materialize a revision body by index (lazy bodies: only on restore)."""
        if 0 <= index < len(self._revisions):
            return self._revisions[index]
        return None

    @callback
    def async_contains_layout(self, layout: dict[str, Any]) -> bool:
        """True when a revision with the same structural signature is retained.

        Used to skip redundant pre-restore captures: if the current layout is
        already preserved in the ring, capturing it again would only push the
        ring toward the cap and evict genuine backups (ping-pong restores).
        """
        sig = _structural_signature(layout)
        if sig is None:
            return False  # cannot hash — in doubt, capture
        return any(
            isinstance(rev, dict) and _structural_signature(rev.get("layout") or {}) == sig
            for rev in self._revisions
        )

    def _evict(self) -> None:
        while len(self._revisions) > REVISION_RING_CAP:
            self._revisions.pop(0)
        while len(self._revisions) > 1 and self._size_bytes() > REVISION_RING_MAX_BYTES:
            self._revisions.pop(0)

    def _size_bytes(self) -> int:
        try:
            return len(json.dumps({"revisions": self._revisions}, default=str).encode())
        except (TypeError, ValueError):
            return 0

    async def async_save_now(self) -> None:
        """Flush the ring to disk immediately (e.g. on shutdown/unload).

        Same clear-before-await shape as async_flush, so a push interleaved
        with this write leaves the ring dirty instead of losing the flag.
        """
        self._dirty = False
        try:
            await self._store.async_save({"revisions": self._revisions})
        except Exception:
            self._dirty = True
            raise
