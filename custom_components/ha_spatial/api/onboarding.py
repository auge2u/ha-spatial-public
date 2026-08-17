"""Onboarding + registry read commands: areas, entities, room suggestions."""
from __future__ import annotations

import copy
import uuid
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from ..geometry import GeometryError
from ..reconcile import resolve_effective_areas
from ..schema import _ORIGIN, _finite_float
from ..suggest import suggest_rooms as suggest_rooms_from_registry
from .common import (
    _check_stale,
    _get_store,
    _rate_limit_or_error,
    _validate_area_floor,
    save_layout_or_error,
)


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


_SUGGESTION_GRID_GAP = 1.0  # meters
_SUGGESTION_ROW_WIDTH = 18.0  # meters before wrapping to next row
_DEFAULT_ROOM_HEIGHT = 2.5


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

    saved = await save_layout_or_error(connection, msg, store, layout)
    if saved is None:
        return
    connection.send_result(msg["id"], {"room_ids": created_ids, "layout": saved})
