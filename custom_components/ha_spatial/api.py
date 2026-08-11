"""WebSocket API for the HA Spatial panel (decisions 6A / 8A / 12A).

Five commands. Reads (layout/get, validate) are allowed for any authenticated
user; mutations (update_geometry, place, calibrate) are admin-only (decision
6A). Mutations validate at the boundary and return typed error codes
(invalid_polygon, self_intersecting, unknown_room, unknown_entity,
stale_version), never silently coercing (decision 8A). Persistence is debounced
in the store (decision 12A).
"""
from __future__ import annotations

import base64
import copy
import json
import logging
import math
import re
import time
import uuid
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
)

from .const import CONF_VISION_PROVIDER, DEFAULT_VISION_PROVIDER, DOMAIN, FUNNEL_EVENTS, MOUNT_TYPES
from .geometry import GeometryError, cascade_offset, validate_room_polygon
from .reconcile import resolve_effective_areas
from .roomplan_import import RoomPlanImportError, parse_roomplan_import
from .schema import _POINT2D, _POINT3D, _ORIGIN, _finite_float
from .spatial import validate_layout
from .suggest import suggest_rooms as suggest_rooms_from_registry
from .vision_provider import VisionProviderError, get_provider

if TYPE_CHECKING:
    from .events import EventStore
    from .spatial import SpatialStore

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


# Coordinate validators are imported from schema.py so command inputs reject
# NaN/Infinity before they ever reach the layout store.


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
def async_register_api(hass: HomeAssistant) -> None:
    """Register the WS commands once per hass."""
    if hass.data.setdefault(DOMAIN, {}).get(_API_REGISTERED):
        return
    websocket_api.async_register_command(hass, ws_get_layout)
    websocket_api.async_register_command(hass, ws_validate)
    websocket_api.async_register_command(hass, ws_create_room)
    websocket_api.async_register_command(hass, ws_update_geometry)
    websocket_api.async_register_command(hass, ws_delete_room)
    websocket_api.async_register_command(hass, ws_place_entity)
    websocket_api.async_register_command(hass, ws_calibrate)
    websocket_api.async_register_command(hass, ws_log_event)
    websocket_api.async_register_command(hass, ws_funnel)
    websocket_api.async_register_command(hass, ws_create_scene)
    websocket_api.async_register_command(hass, ws_remove_scene)
    websocket_api.async_register_command(hass, ws_analyze_vision)
    websocket_api.async_register_command(hass, ws_areas_list)
    websocket_api.async_register_command(hass, ws_entities_by_area)
    websocket_api.async_register_command(hass, ws_suggest_rooms)
    websocket_api.async_register_command(hass, ws_create_suggested_rooms)
    websocket_api.async_register_command(hass, ws_roomplan_import)
    hass.data[DOMAIN][_API_REGISTERED] = True


@websocket_api.websocket_command({vol.Required("type"): "ha_spatial/layout/get"})
@callback
def ws_get_layout(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return the current layout (any authenticated user)."""
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    connection.send_result(msg["id"], store.async_get())


@websocket_api.websocket_command(
    {vol.Required("type"): "ha_spatial/validate", vol.Optional("layout"): dict}
)
@callback
def ws_validate(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Validate the current (or a supplied) layout (any authenticated user)."""
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    layout = msg.get("layout", store.async_get())
    try:
        validate_layout(layout)
    except vol.Invalid as err:
        connection.send_result(msg["id"], {"valid": False, "error": "invalid_structure", "detail": str(err)})
        return
    except GeometryError as err:
        connection.send_result(msg["id"], {"valid": False, "error": err.code, "detail": str(err)})
        return
    connection.send_result(msg["id"], {"valid": True})


@websocket_api.websocket_command({vol.Required("type"): "ha_spatial/areas/list"})
@callback
def ws_areas_list(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """List HA areas (any authenticated user)."""
    area_reg = ar.async_get(hass)
    areas = [
        {"area_id": area.id, "name": area.name, "floor_id": area.floor_id}
        for area in area_reg.areas.values()
    ]
    connection.send_result(msg["id"], {"areas": areas})


@websocket_api.websocket_command(
    {vol.Required("type"): "ha_spatial/entities/by_area", vol.Required("area_id"): str}
)
@callback
def ws_entities_by_area(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return real entity IDs whose effective area matches area_id.

    Effective area uses the same precedence as registry reconciliation: the
    entity's own area wins, otherwise its device's area.
    """
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)
    device_areas = {did: device.area_id for did, device in device_reg.devices.items()}
    entities = [(e.entity_id, e.area_id, e.device_id) for e in entity_reg.entities.values()]
    effective = resolve_effective_areas(entities, device_areas)
    target = msg["area_id"]
    entity_ids = [entity_id for entity_id, area_id in effective.items() if area_id == target]
    connection.send_result(msg["id"], {"entity_ids": sorted(entity_ids)})


@websocket_api.websocket_command({vol.Required("type"): "ha_spatial/onboarding/suggest_rooms"})
@callback
def ws_suggest_rooms(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Suggest rooms from existing HA areas, entities, and device registry."""
    area_reg = ar.async_get(hass)
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    area_entries = [
        {"id": a.id, "name": a.name, "floor_id": a.floor_id}
        for a in area_reg.areas.values()
    ]
    entity_entries = [
        {
            "entity_id": e.entity_id,
            "area_id": e.area_id,
            "device_id": e.device_id,
        }
        for e in entity_reg.entities.values()
    ]
    device_entries = [
        {"id": d.id, "area_id": d.area_id}
        for d in device_reg.devices.values()
    ]

    suggestions = suggest_rooms_from_registry(area_entries, entity_entries, device_entries)
    connection.send_result(msg["id"], {"suggestions": suggestions})


_MAX_ROOMPLAN_PAYLOAD_BYTES = 5 * 1024 * 1024  # 5 MB JSON


def _validate_roomplan_payload(payload: Any) -> Any:
    """Reject oversized RoomPlan payloads before parsing."""
    if not isinstance(payload, dict):
        raise vol.Invalid("RoomPlan payload must be an object")
    try:
        size = len(json.dumps(payload).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise vol.Invalid(f"payload is not serializable: {exc}") from exc
    if size > _MAX_ROOMPLAN_PAYLOAD_BYTES:
        raise vol.Invalid(f"RoomPlan payload exceeds {_MAX_ROOMPLAN_PAYLOAD_BYTES / (1024 * 1024)} MB")
    return payload


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_spatial/roomplan/import",
        vol.Required("payload"): vol.All(dict, _validate_roomplan_payload),
    }
)
@websocket_api.async_response
async def ws_roomplan_import(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Import a RoomPlan scan and create a room with real metric geometry."""
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    if not _rate_limit_or_error(hass, connection, msg):
        return
    try:
        parsed = parse_roomplan_import(msg["payload"])
    except RoomPlanImportError as exc:
        connection.send_error(msg["id"], exc.code, exc.message)
        return

    layout = copy.deepcopy(store.async_get())
    rooms = layout.get("rooms", [])

    origin = cascade_offset(parsed["polygon"], rooms)
    room_id = str(uuid.uuid4())
    now = dt_util.utcnow().isoformat()
    room: dict[str, Any] = {
        "id": room_id,
        "name": parsed["name"],
        "polygon": parsed["polygon"],
        "height": parsed["height"],
        "origin": origin,
        "rotation": 0,
        "area_id": None,
        "floor_id": None,
        "floor_level": 0,
        "orphaned": False,
        "metadata": {"source": "roomplan"},
    }
    rooms.append(room)
    layout["rooms"] = rooms
    layout["updated_at"] = now
    validate_layout(layout)
    await store.async_save(layout)
    connection.send_result(msg["id"], {"room": room, "layout": layout})


_DEFAULT_ROOM_HEIGHT = 2.5
_SUGGESTION_GRID_GAP = 1.0  # meters
_SUGGESTION_ROW_WIDTH = 18.0  # meters before wrapping to next row
_MAX_VISION_PHOTOS = 6
_MAX_VISION_PHOTO_BYTES = 2 * 1024 * 1024  # 2 MB decoded
_ALLOWED_VISION_IMAGE_TYPES = ("image/jpeg", "image/png")


_DATA_URL_RE = re.compile(r"^data:([^;]+);base64,(.+)$", re.IGNORECASE)


def _validate_data_url(url: str) -> str:
    """Validate a vision photo data URL: image type and decoded size limits."""
    if not isinstance(url, str):
        raise vol.Invalid("photo must be a data URL string")
    match = _DATA_URL_RE.match(url)
    if not match:
        raise vol.Invalid("photo must be a base64 data URL")
    mime, b64 = match.groups()
    mime = mime.lower()
    if mime not in _ALLOWED_VISION_IMAGE_TYPES:
        raise vol.Invalid(f"unsupported image type {mime}")
    try:
        decoded = base64.b64decode(b64, validate=True)
    except Exception as exc:
        raise vol.Invalid(f"invalid base64 photo data: {exc}") from exc
    if len(decoded) > _MAX_VISION_PHOTO_BYTES:
        raise vol.Invalid(f"photo exceeds {_MAX_VISION_PHOTO_BYTES // (1024 * 1024)} MB decoded")
    return url


def _suggested_room_size(name: str) -> tuple[float, float]:
    """Return a reasonable (width, height) in meters for a room from its name."""
    lowered = name.lower()
    if any(tok in lowered for tok in ("bath", "wc", "toilet")):
        return (2.5, 2.0)
    if any(tok in lowered for tok in ("bed", "bedroom")):
        return (3.5, 4.0)
    if any(tok in lowered for tok in ("kitchen", "cuisine")):
        return (3.5, 3.0)
    if any(tok in lowered for tok in ("living", "lounge", "salon")):
        return (5.5, 4.5)
    if any(tok in lowered for tok in ("dining", "salle à manger")):
        return (4.0, 4.0)
    if any(tok in lowered for tok in ("hall", "entry", "entrance", "corridor")):
        return (2.0, 4.0)
    if any(tok in lowered for tok in ("balcon", "balcony", "terrace")):
        return (2.5, 5.0)
    if any(tok in lowered for tok in ("office", "studio", "study")):
        return (3.0, 3.5)
    return (4.0, 4.0)


def _rectangle_polygon(width: float, height: float) -> list[dict[str, float]]:
    """A centered rectangle polygon in meters."""
    hw = width / 2.0
    hh = height / 2.0
    return [
        {"x": -hw, "y": -hh},
        {"x": hw, "y": -hh},
        {"x": hw, "y": hh},
        {"x": -hw, "y": hh},
    ]


_SUGGESTION_ARRANGEMENT_ORIGIN = vol.Schema(
    {
        vol.Optional("origin", default={"x": 0.0, "y": 0.0}): _ORIGIN,
        vol.Optional("rotation", default=0.0): _finite_float,
    }
)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_spatial/onboarding/create_suggested_rooms",
        vol.Required("suggestions"): [
            {
                vol.Required("name"): str,
                vol.Optional("area_id"): vol.Any(None, str),
                vol.Optional("floor_id"): vol.Any(None, str),
                vol.Optional("floor_level", default=0): int,
            }
        ],
        vol.Optional("arrangement", default={}): dict,
        vol.Optional("expected_updated_at"): str,
    }
)
@websocket_api.async_response
async def ws_create_suggested_rooms(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Batch-create rectangular rooms from HA area/device priors (auto-layout grid).

    Each suggestion becomes a room with a name-based default footprint, arranged
    in a simple grid so the user sees a coherent floorplan instead of a list.
    If an ``arrangement`` keyed by suggestion name is provided, those origins/
    rotations are used instead of the auto-grid. The resulting batch is centered
    around the world origin.
    """
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    if not _rate_limit_or_error(hass, connection, msg):
        return
    layout = copy.deepcopy(store.async_get())
    if _check_stale(msg, layout):
        connection.send_error(msg["id"], "stale_version", "layout changed since last read")
        return

    suggestions = msg["suggestions"]
    if not suggestions:
        connection.send_error(msg["id"], "invalid_structure", "suggestions list is empty")
        return

    for s in suggestions:
        ok, err_code = _validate_area_floor(hass, s.get("area_id"), s.get("floor_id"))
        if not ok:
            connection.send_error(msg["id"], err_code, f"suggestion {s.get('name')}: no {err_code.replace('_', ' ')} provided")
            return

    arrangement = msg.get("arrangement", {})

    # Group by floor level and lay out each floor independently.
    by_floor: dict[int, list[dict[str, Any]]] = {}
    for s in suggestions:
        by_floor.setdefault(s.get("floor_level", 0), []).append(s)

    created_rooms: list[dict[str, Any]] = []
    created_ids: list[str] = []
    for floor_level, floor_suggestions in by_floor.items():
        cursor_x = 0.0
        cursor_y = 0.0
        row_height = 0.0
        for s in floor_suggestions:
            name = s["name"]
            width, height = _suggested_room_size(name)
            polygon = _rectangle_polygon(width, height)
            room_id = uuid.uuid4().hex[:12]
            if name in arrangement:
                try:
                    cfg = _SUGGESTION_ARRANGEMENT_ORIGIN(arrangement[name])
                    origin: dict[str, float] = {"x": cfg["origin"]["x"], "y": cfg["origin"]["y"]}
                    rotation = float(cfg["rotation"])
                except vol.Invalid:
                    origin = {"x": cursor_x + width / 2.0, "y": cursor_y + height / 2.0}
                    rotation = 0.0
            else:
                if cursor_x + width > _SUGGESTION_ROW_WIDTH and cursor_x > 0:
                    cursor_x = 0.0
                    cursor_y += row_height + _SUGGESTION_GRID_GAP
                    row_height = 0.0
                origin = {"x": cursor_x + width / 2.0, "y": cursor_y + height / 2.0}
                rotation = 0.0
                cursor_x += width + _SUGGESTION_GRID_GAP
                row_height = max(row_height, height)
            room: dict[str, Any] = {
                "id": room_id,
                "name": name,
                "area_id": s.get("area_id"),
                "floor_id": s.get("floor_id"),
                "floor_level": floor_level,
                "polygon": polygon,
                "height": _DEFAULT_ROOM_HEIGHT,
                "origin": origin,
                "rotation": rotation,
                "metadata": {"source": "suggested_area"},
            }
            created_rooms.append(room)
            created_ids.append(room_id)

    # Center the newly created batch around the origin for a balanced initial view.
    if created_rooms:
        min_x = min(
            r["origin"]["x"] + min(p["x"] for p in r["polygon"]) for r in created_rooms
        )
        max_x = max(
            r["origin"]["x"] + max(p["x"] for p in r["polygon"]) for r in created_rooms
        )
        min_y = min(
            r["origin"]["y"] + min(p["y"] for p in r["polygon"]) for r in created_rooms
        )
        max_y = max(
            r["origin"]["y"] + max(p["y"] for p in r["polygon"]) for r in created_rooms
        )
        dx = -(min_x + max_x) / 2.0
        dy = -(min_y + max_y) / 2.0
        for r in created_rooms:
            r["origin"]["x"] += dx
            r["origin"]["y"] += dy

    layout["rooms"].extend(created_rooms)

    try:
        saved = await store.async_save(layout)
    except (vol.Invalid, GeometryError) as err:
        connection.send_error(msg["id"], getattr(err, "code", "invalid_structure"), str(err))
        return
    connection.send_result(msg["id"], {"room_ids": created_ids, "layout": saved})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_spatial/room/create",
        vol.Required("name"): str,
        vol.Optional("area_id"): vol.Any(None, str),
        vol.Optional("floor_id"): vol.Any(None, str),
        vol.Optional("floor_level", default=0): int,
        vol.Required("polygon"): [_POINT2D],
        vol.Required("height"): vol.All(_finite_float, vol.Range(min=0, min_included=False)),
        vol.Optional("metadata"): dict,
        vol.Optional("placements", default=list): [
            {
                vol.Required("entity_id"): str,
                vol.Required("position"): _POINT3D,
                vol.Optional("rotation", default=0): _finite_float,
                vol.Required("mount_type"): vol.In(MOUNT_TYPES),
            }
        ],
        vol.Optional("expected_updated_at"): str,
    }
)
@websocket_api.async_response
async def ws_create_room(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Atomically create a room + its placements in one validated save (D11/D12).

    Placements must reference real HA entities (D11); the whole room + placements
    persist in a single save, so there is no two-step race (D12).
    """
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    if not _rate_limit_or_error(hass, connection, msg):
        return
        return
    layout = copy.deepcopy(store.async_get())
    if _check_stale(msg, layout):
        connection.send_error(msg["id"], "stale_version", "layout changed since last read")
        return
    ok, err_code = _validate_area_floor(hass, msg.get("area_id"), msg.get("floor_id"))
    if not ok:
        connection.send_error(msg["id"], err_code, f"no {err_code.replace('_', ' ')} provided")
        return
    try:
        polygon = validate_room_polygon(msg["polygon"])
    except GeometryError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    # D11: every placement must reference a real HA entity — one HA currently
    # knows about, via the entity registry OR the live state machine. The
    # registry alone is NOT the set of real entities (YAML/template entities are
    # real, persist across restarts, and often have no registry entry), so
    # registry-OR-state is the correct "does the user have this entity" check.
    for placement in msg["placements"]:
        if not _entity_exists(hass, placement["entity_id"]):
            connection.send_error(msg["id"], "unknown_entity", f"no entity {placement['entity_id']}")
            return

    room_id = uuid.uuid4().hex[:12]
    same_floor = [r for r in layout["rooms"] if r.get("floor_level", 0) == msg["floor_level"]]
    origin = cascade_offset(polygon, same_floor)
    room: dict[str, Any] = {
        "id": room_id,
        "name": msg["name"],
        "area_id": msg.get("area_id"),
        "floor_id": msg.get("floor_id"),
        "floor_level": msg["floor_level"],
        "polygon": polygon,
        "height": msg["height"],
        "origin": origin,
        "rotation": 0.0,
    }
    if msg.get("metadata"):
        room["metadata"] = msg["metadata"]
    layout["rooms"].append(room)
    for placement in msg["placements"]:
        layout["placements"] = [p for p in layout["placements"] if p["entity_id"] != placement["entity_id"]]
        layout["placements"].append(
            {
                "entity_id": placement["entity_id"],
                "room_id": room_id,
                "position": {k: placement["position"][k] for k in ("x", "y", "z")},
                "rotation": placement["rotation"],
                "mount_type": placement["mount_type"],
            }
        )
    try:
        saved = await store.async_save(layout)
    except (vol.Invalid, GeometryError) as err:
        connection.send_error(msg["id"], getattr(err, "code", "invalid_structure"), str(err))
        return
    connection.send_result(msg["id"], {"room_id": room_id, "layout": saved})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_spatial/room/update_geometry",
        vol.Required("room_id"): str,
        vol.Required("polygon"): [_POINT2D],
        vol.Optional("height"): vol.All(_finite_float, vol.Range(min=0, min_included=False)),
        vol.Optional("origin"): _ORIGIN,
        vol.Optional("rotation"): _finite_float,
        vol.Optional("expected_updated_at"): str,
    }
)
@websocket_api.async_response
async def ws_update_geometry(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Update a room's polygon/height/origin/rotation (admin only)."""
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    if not _rate_limit_or_error(hass, connection, msg):
        return
    layout = copy.deepcopy(store.async_get())
    if _check_stale(msg, layout):
        connection.send_error(msg["id"], "stale_version", "layout changed since last read")
        return
    room = next((r for r in layout["rooms"] if r["id"] == msg["room_id"]), None)
    if room is None:
        connection.send_error(msg["id"], "unknown_room", f"no room {msg['room_id']}")
        return
    if "polygon" in msg:
        try:
            room["polygon"] = validate_room_polygon(msg["polygon"])
        except GeometryError as err:
            connection.send_error(msg["id"], err.code, str(err))
            return
    if "height" in msg:
        room["height"] = msg["height"]
    if "origin" in msg:
        origin = msg["origin"]
        if not (math.isfinite(origin["x"]) and math.isfinite(origin["y"])):
            connection.send_error(msg["id"], "invalid_origin", "origin has a non-finite coordinate")
            return
        room["origin"] = {"x": origin["x"], "y": origin["y"]}
    if "rotation" in msg:
        if not math.isfinite(msg["rotation"]):
            connection.send_error(msg["id"], "invalid_rotation", "rotation must be finite")
            return
        room["rotation"] = msg["rotation"]
    connection.send_result(msg["id"], await store.async_save(layout))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_spatial/room/delete",
        vol.Required("room_id"): str,
        vol.Optional("expected_updated_at"): str,
    }
)
@websocket_api.async_response
async def ws_delete_room(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Delete a room and its entity placements (admin only).

    The linked HA area is untouched — the spatial room is a layer over the
    registry, not its owner. Placements require a room_id (schema v1), so the
    room takes its placements with it rather than leaving invalid orphans.
    """
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    if not _rate_limit_or_error(hass, connection, msg):
        return
    layout = copy.deepcopy(store.async_get())
    if _check_stale(msg, layout):
        connection.send_error(msg["id"], "stale_version", "layout changed since last read")
        return
    if not any(r["id"] == msg["room_id"] for r in layout["rooms"]):
        connection.send_error(msg["id"], "unknown_room", f"no room {msg['room_id']}")
        return
    layout["rooms"] = [r for r in layout["rooms"] if r["id"] != msg["room_id"]]
    layout["placements"] = [
        p for p in layout.get("placements", []) if p.get("room_id") != msg["room_id"]
    ]
    connection.send_result(msg["id"], await store.async_save(layout))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_spatial/entity/place",
        vol.Required("entity_id"): str,
        vol.Optional("room_id"): vol.Any(None, str),
        vol.Required("position"): _POINT3D,
        vol.Required("rotation"): _finite_float,
        vol.Required("mount_type"): vol.In(MOUNT_TYPES),
        vol.Optional("expected_updated_at"): str,
    }
)
@websocket_api.async_response
async def ws_place_entity(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Place (or move) an entity (admin only)."""
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    if not _rate_limit_or_error(hass, connection, msg):
        return
    if not _entity_exists(hass, msg["entity_id"]):
        connection.send_error(msg["id"], "unknown_entity", f"no entity {msg['entity_id']}")
        return
    layout = copy.deepcopy(store.async_get())
    if _check_stale(msg, layout):
        connection.send_error(msg["id"], "stale_version", "layout changed since last read")
        return
    room_id = msg.get("room_id")
    if room_id is not None and not any(r["id"] == room_id for r in layout.get("rooms", [])):
        connection.send_error(msg["id"], "unknown_room", f"no room {room_id}")
        return
    placement = {
        "entity_id": msg["entity_id"],
        "room_id": room_id,
        "position": {k: msg["position"][k] for k in ("x", "y", "z")},
        "rotation": msg["rotation"],
        "mount_type": msg["mount_type"],
    }
    layout["placements"] = [p for p in layout["placements"] if p["entity_id"] != msg["entity_id"]]
    layout["placements"].append(placement)
    connection.send_result(msg["id"], await store.async_save(layout))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_spatial/calibrate",
        vol.Optional("reference_entity"): str,
        vol.Required("real_world_distance"): vol.All(_finite_float, vol.Range(min=0, min_included=False)),
        vol.Required("measured_distance"): vol.All(_finite_float, vol.Range(min=0, min_included=False)),
        vol.Optional("expected_updated_at"): str,
    }
)
@websocket_api.async_response
async def ws_calibrate(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Set the calibration reference (admin only)."""
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    if not _rate_limit_or_error(hass, connection, msg):
        return
    layout = copy.deepcopy(store.async_get())
    if _check_stale(msg, layout):
        connection.send_error(msg["id"], "stale_version", "layout changed since last read")
        return
    calibration: dict[str, Any] = {
        "real_world_distance": msg["real_world_distance"],
        "measured_distance": msg["measured_distance"],
    }
    if "reference_entity" in msg:
        calibration["reference_entity"] = msg["reference_entity"]
    layout["calibration"] = calibration
    connection.send_result(msg["id"], await store.async_save(layout))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_spatial/event/log",
        vol.Required("event"): vol.In(FUNNEL_EVENTS),
    }
)
@websocket_api.async_response
async def ws_log_event(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Append a funnel event (immediate, durable write). Admin only."""
    event_store = _get_event_store(hass)
    if event_store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    if not _rate_limit_or_error(hass, connection, msg):
        return
    connection.send_result(msg["id"], await event_store.async_append(msg["event"]))


@websocket_api.websocket_command({vol.Required("type"): "ha_spatial/event/funnel"})
@callback
def ws_funnel(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return per-event funnel counts (any authenticated user)."""
    event_store = _get_event_store(hass)
    if event_store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    connection.send_result(msg["id"], event_store.async_funnel())


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_spatial/scene/create",
        vol.Required("name"): vol.All(str, vol.Length(min=1)),
        vol.Required("entity_ids"): vol.All([str], vol.Length(min=1)),
    }
)
@websocket_api.async_response
async def ws_create_scene(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Create a durable HA scene from the current states of real entities (T3/D3).

    Snapshots the live state of each entity into a stored scene definition, then
    materializes it as a real scene entity (survives restart, activatable).
    """
    data = _get_entry_data(hass)
    if data is None or "scene_manager" not in data:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    if not _rate_limit_or_error(hass, connection, msg):
        return

    snapshot: list[dict[str, Any]] = []
    for entity_id in msg["entity_ids"]:
        state = hass.states.get(entity_id)
        if state is None:
            connection.send_error(msg["id"], "unknown_entity", f"no entity {entity_id}")
            return
        snapshot.append(
            {"entity_id": entity_id, "state": state.state, "attributes": dict(state.attributes)}
        )

    scene_def = {"id": uuid.uuid4().hex[:12], "name": msg["name"], "entities": snapshot}
    await data["scene_store"].async_add(scene_def)
    data["scene_manager"].async_add_scene(scene_def)
    connection.send_result(msg["id"], {"scene_id": scene_def["id"], "name": scene_def["name"]})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "ha_spatial/scene/remove", vol.Required("scene_id"): str}
)
@websocket_api.async_response
async def ws_remove_scene(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Remove a scene the integration created (safe undo, Codex #8)."""
    data = _get_entry_data(hass)
    if data is None or "scene_manager" not in data:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    if not _rate_limit_or_error(hass, connection, msg):
        return
    # Provenance: only remove scenes we own. A non-owned id is rejected, so undo
    # can never delete a same-named scene the user authored elsewhere.
    removed = await data["scene_store"].async_remove(msg["scene_id"])
    if not removed:
        connection.send_error(msg["id"], "unknown_scene", "not an HA Spatial scene")
        return
    await data["scene_manager"].async_remove_scene(msg["scene_id"])
    connection.send_result(msg["id"], {"removed": msg["scene_id"]})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_spatial/vision/analyze",
        vol.Optional("photos", default=list): vol.All(
            [_validate_data_url],
            vol.Length(max=_MAX_VISION_PHOTOS),
        ),
        vol.Optional("room_hint"): str,
        vol.Optional("signals", default=dict): {
            vol.Optional("photo_count", default=0): vol.All(int, vol.Range(min=0)),
            vol.Optional("avg_aspect", default=1.0): vol.All(_finite_float, vol.Range(min=0)),
            vol.Optional("is_high_quality_set", default=False): bool,
        },
        vol.Optional("consent", default=False): bool,
    }
)
@websocket_api.async_response
async def ws_analyze_vision(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Backend-mediated vision analysis (D4/D9). Key stays server-side; cloud
    providers require explicit consent before any photo egress."""
    data = _get_entry_data(hass)
    if data is None or "entry" not in data:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    if not _rate_limit_or_error(hass, connection, msg):
        return
    options = data["entry"].options
    provider_name = options.get(CONF_VISION_PROVIDER, DEFAULT_VISION_PROVIDER)
    provider = get_provider(provider_name)
    if provider is None:
        connection.send_error(msg["id"], "no_provider", f"unknown vision provider {provider_name}")
        return
    # Privacy contract: a cloud provider must not receive photos without explicit
    # consent for this analysis (the simulated provider never leaves the device).
    if provider_name != "simulated" and not msg["consent"]:
        connection.send_error(msg["id"], "consent_required", "cloud vision requires explicit consent")
        return
    request = {
        "photos": msg["photos"],
        "room_hint": msg.get("room_hint"),
        "signals": msg["signals"],
    }
    try:
        result = await provider(hass, request, options)
    except VisionProviderError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    connection.send_result(msg["id"], result)
