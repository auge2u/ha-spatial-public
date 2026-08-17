"""Funnel-event commands: ha_spatial/event/log + ha_spatial/event/funnel."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from ..const import FUNNEL_EVENTS
from .common import _get_event_store, _rate_limit_or_error


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
