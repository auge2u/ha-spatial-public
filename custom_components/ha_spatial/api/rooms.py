"""Room + placement + calibration mutation commands (admin only)."""
from __future__ import annotations

import copy
import json
import math
import uuid
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import MOUNT_TYPES
from ..geometry import GeometryError, cascade_offset, validate_room_polygon
from ..roomplan_import import RoomPlanImportError, parse_roomplan_import
from ..schema import _POINT2D, _POINT3D, _ORIGIN, _finite_float
from ..spatial import validate_layout
from .common import (
    _check_stale,
    _entity_exists,
    _get_store,
    _rate_limit_or_error,
    _validate_area_floor,
    save_layout_or_error,
)

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
    saved = await save_layout_or_error(connection, msg, store, layout)
    if saved is None:
        return
    connection.send_result(msg["id"], {"room": room, "layout": layout})


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
    saved = await save_layout_or_error(connection, msg, store, layout)
    if saved is None:
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
    saved = await save_layout_or_error(connection, msg, store, layout)
    if saved is None:
        return
    connection.send_result(msg["id"], saved)


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
    saved = await save_layout_or_error(connection, msg, store, layout)
    if saved is None:
        return
    connection.send_result(msg["id"], saved)


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
    saved = await save_layout_or_error(connection, msg, store, layout)
    if saved is None:
        return
    connection.send_result(msg["id"], saved)


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
    saved = await save_layout_or_error(connection, msg, store, layout)
    if saved is None:
        return
    connection.send_result(msg["id"], saved)
