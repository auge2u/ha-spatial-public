"""WebSocket API for the HA Spatial panel (decisions 6A / 8A / 12A).

Reads (layout/get, validate, areas/list, entities/by_area, event/funnel, info,
onboarding/suggest_rooms) are allowed for any authenticated user; mutations are
admin-only (decision 6A). Mutations validate at the boundary and return typed
error codes (invalid_polygon, self_intersecting, unknown_room, unknown_entity,
stale_version), never silently coercing (decision 8A). Persistence is debounced
in the store (decision 12A).

The commands live in per-domain modules; this package __init__ keeps the public
registration surface (`async_register_api`) in one place.
"""
from __future__ import annotations

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from ..const import DOMAIN
from .common import _API_REGISTERED
from .events import ws_funnel, ws_log_event
from .info import ws_info
from .layout import (
    ws_get_layout,
    ws_layout_export,
    ws_layout_history,
    ws_layout_import,
    ws_layout_restore,
    ws_validate,
)
from .onboarding import (
    ws_areas_list,
    ws_create_suggested_rooms,
    ws_entities_by_area,
    ws_suggest_rooms,
)
from .rooms import (
    ws_calibrate,
    ws_create_room,
    ws_delete_room,
    ws_place_entity,
    ws_roomplan_import,
    ws_update_geometry,
)
from .scenes import ws_create_scene, ws_remove_scene
from .vision import ws_analyze_vision


@callback
def async_register_api(hass: HomeAssistant) -> None:
    """Register the WS commands once per hass."""
    if hass.data.setdefault(DOMAIN, {}).get(_API_REGISTERED):
        return
    websocket_api.async_register_command(hass, ws_info)
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
    websocket_api.async_register_command(hass, ws_layout_history)
    websocket_api.async_register_command(hass, ws_layout_restore)
    websocket_api.async_register_command(hass, ws_layout_export)
    websocket_api.async_register_command(hass, ws_layout_import)
    hass.data[DOMAIN][_API_REGISTERED] = True
