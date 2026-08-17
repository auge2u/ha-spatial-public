"""Scene commands: ha_spatial/scene/create + ha_spatial/scene/remove."""
from __future__ import annotations

import uuid

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .common import _get_entry_data, _rate_limit_or_error


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

    snapshot: list[dict] = []
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
