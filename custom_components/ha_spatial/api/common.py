"""Shared helpers for the HA Spatial WebSocket commands (decisions 6A / 8A).

Everything the domain modules need that is not the command logic itself:
single-instance store lookups, per-connection rate limiting, the stale-version
check (decision 8A), area/floor existence checks, and the shared mutation
preamble used by layout commands.
"""
from __future__ import annotations

import copy
import logging
import time
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    entity_registry as er,
    floor_registry as fr,
)

from ..const import DOMAIN

if TYPE_CHECKING:
    from ..events import EventStore
    from ..spatial import SpatialStore

_LOGGER = logging.getLogger(__name__)
_API_REGISTERED = "api_registered"
_RATE_LIMITS = "rate_limits"

# Per-command rate limits: (tokens, refill_per_second)
_RATE_LIMITS_CONFIG: dict[str, tuple[float, float]] = {
    "ha_spatial/vision/analyze": (10, 10 / 60),        # 10 per minute
    "ha_spatial/event/log": (60, 60 / 60),              # 60 per minute
    "ha_spatial/mutation": (30, 30 / 60),               # shared bucket for geometry/scene writes
}


class _TokenBucket:
    """Simple token bucket for per-connection rate limiting."""

    def __init__(self, capacity: float, refill_per_second: float) -> None:
        self.capacity = capacity
        self.tokens = capacity
        self.refill_per_second = refill_per_second
        self.last_update = time.monotonic()

    def consume(self, tokens: float = 1.0) -> tuple[bool, float]:
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.last_update = now
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, 0.0
        retry_after = (tokens - self.tokens) / self.refill_per_second if self.refill_per_second > 0 else 60.0
        return False, retry_after


class _RateLimiter:
    """Per-connection rate limiter keyed by command type."""

    def __init__(self) -> None:
        self._buckets: dict[str, _TokenBucket] = {}

    def check(self, command: str) -> tuple[bool, float]:
        # Map all geometry/scene/layout mutations to the shared mutation bucket.
        bucket_key = command if command in _RATE_LIMITS_CONFIG else "ha_spatial/mutation"
        if command not in _RATE_LIMITS_CONFIG and not command.startswith("ha_spatial/"):
            return True, 0.0
        capacity, refill = _RATE_LIMITS_CONFIG.get(bucket_key, _RATE_LIMITS_CONFIG["ha_spatial/mutation"])
        if bucket_key not in self._buckets:
            self._buckets[bucket_key] = _TokenBucket(capacity, refill)
        return self._buckets[bucket_key].consume()


def _get_rate_limiter(hass: HomeAssistant, connection: websocket_api.ActiveConnection) -> _RateLimiter:
    """Return (and create if needed) the rate limiter for this WS connection."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    limiters = domain_data.setdefault(_RATE_LIMITS, {})
    key = id(connection)
    if key not in limiters:
        limiters[key] = _RateLimiter()
    return limiters[key]


@callback
def _get_store(hass: HomeAssistant) -> "SpatialStore | None":
    """Return the single spatial store (single-instance integration)."""
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if isinstance(entry_data, dict) and "store" in entry_data:
            return entry_data["store"]
    return None


@callback
def _get_event_store(hass: HomeAssistant) -> "EventStore | None":
    """Return the single funnel-event store."""
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if isinstance(entry_data, dict) and "event_store" in entry_data:
            return entry_data["event_store"]
    return None


@callback
def _get_entry_data(hass: HomeAssistant) -> dict | None:
    """Return the single entry's data dict (store/scene_store/scene_manager)."""
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if isinstance(entry_data, dict) and "store" in entry_data:
            return entry_data
    return None


def _entity_exists(hass: HomeAssistant, entity_id: str) -> bool:
    registry = er.async_get(hass)
    return registry.async_get(entity_id) is not None or hass.states.get(entity_id) is not None


def _check_rate_limit(hass: HomeAssistant, connection: websocket_api.ActiveConnection, command: str) -> tuple[bool, float]:
    """Consume a token for command; return (allowed, retry_after_seconds)."""
    limiter = _get_rate_limiter(hass, connection)
    return limiter.check(command)


def _rate_limit_or_error(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> bool:
    """If command is rate limited, send an error and return False."""
    allowed, retry = _check_rate_limit(hass, connection, msg["type"])
    if not allowed:
        connection.send_error(msg["id"], "rate_limited", f"rate limited; retry after {int(retry)}s")
        return False
    return True


def _validate_area_floor(hass: HomeAssistant, area_id: str | None, floor_id: str | None) -> tuple[bool, str | None]:
    """Return (ok, error_code) after verifying area_id/floor_id exist in HA registries."""
    if area_id is not None:
        area_reg = ar.async_get(hass)
        if area_reg.async_get_area(area_id) is None:
            return False, "unknown_area"
    if floor_id is not None:
        floor_reg = fr.async_get(hass)
        if floor_reg.async_get_floor(floor_id) is None:
            return False, "unknown_floor"
    return True, None


def _check_stale(msg: dict[str, Any], layout: dict[str, Any]) -> bool:
    """True if the caller's base revision no longer matches (decision 8A)."""
    expected = msg.get("expected_updated_at")
    return expected is not None and expected != layout.get("updated_at")


@callback
def prepare_layout_mutation(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> "tuple[SpatialStore, dict[str, Any]] | None":
    """Shared mutation preamble for layout commands (async_mutate_layout-style).

    Handles the skeleton every layout mutation repeats: store lookup
    (not_loaded), rate limit, deepcopy of the current layout, and the
    stale-version check. Returns (store, working copy) for the command to
    mutate + save, or None after sending the appropriate error.
    """
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return None
    if not _rate_limit_or_error(hass, connection, msg):
        return None
    layout = copy.deepcopy(store.async_get())
    if _check_stale(msg, layout):
        connection.send_error(msg["id"], "stale_version", "layout changed since last read")
        return None
    return store, layout


async def save_layout_or_error(
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    store: "SpatialStore",
    layout: dict[str, Any],
) -> dict[str, Any] | None:
    """Persist a mutated layout, converting store rejections to typed WS errors.

    Centralizes the save-time error contract (codex P2): a newer-version layout
    loaded read-tolerantly fails as ``unsupported_version`` instead of escaping
    as an internal WebSocket failure; structural/geometry rejections carry
    their typed codes. UNEXPECTED errors are logged and re-raised — never
    silently mislabeled ``invalid_structure``. Returns the saved layout, or
    None after sending the error.
    """
    # Deferred import: geometry has no HA deps, schema is pure voluptuous.
    from ..geometry import GeometryError
    from ..schema import UnsupportedLayoutVersionError

    try:
        return await store.async_save(layout)
    except UnsupportedLayoutVersionError as err:
        connection.send_error(msg["id"], "unsupported_version", str(err))
        return None
    except GeometryError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return None
    except vol.Invalid as err:
        connection.send_error(msg["id"], getattr(err, "code", "invalid_structure"), str(err))
        return None
    except Exception:
        _LOGGER.exception("Unexpected error saving layout")
        raise
