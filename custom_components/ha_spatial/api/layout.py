"""Layout commands: reads (get/validate) plus the trust-core commands —
history, restore, export, import (eng lock 1A/OV2)."""
from __future__ import annotations

import json
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from ..geometry import GeometryError
from ..spatial import validate_layout
from .common import _get_event_store, _get_store, prepare_layout_mutation

_MAX_IMPORT_PAYLOAD_BYTES = 5 * 1024 * 1024  # 5 MB JSON


def _validate_import_payload(payload: Any) -> Any:
    """Reject oversized import payloads before validating them."""
    if not isinstance(payload, dict):
        raise vol.Invalid("layout must be an object")
    try:
        size = len(json.dumps(payload).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise vol.Invalid(f"layout is not serializable: {exc}") from exc
    if size > _MAX_IMPORT_PAYLOAD_BYTES:
        raise vol.Invalid(f"layout exceeds {_MAX_IMPORT_PAYLOAD_BYTES / (1024 * 1024)} MB")
    return payload


@websocket_api.websocket_command({vol.Required("type"): "ha_spatial/layout/get"})
@callback
def ws_get_layout(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return the current layout (any authenticated user).

    The response is an ENVELOPE: ``layout`` is the pure persisted layout and
    ``restore_available`` (true when the primary failed to load but the
    revision ring has snapshots) rides as a sibling — injecting it into the
    layout root would let forward-tolerance extras round-trip it back into the
    stored layout and pollute the structural signature.
    """
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    connection.send_result(
        msg["id"],
        {"layout": store.async_get(), "restore_available": store.restore_available},
    )


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


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "ha_spatial/layout/history"})
@callback
def ws_layout_history(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """List revision metadata — index, timestamp, counts; NO bodies (admin)."""
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    connection.send_result(
        msg["id"],
        {
            "revisions": store.revisions.async_history(),
            "restore_available": store.restore_available,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_spatial/layout/restore",
        vol.Required("revision"): vol.All(int, vol.Range(min=0)),
        # Pin the revision by timestamp: indices shift when eviction drops the
        # oldest entry, so an index from a stale history view could otherwise
        # restore the WRONG revision silently.
        vol.Required("ts"): str,
        # Restore overwrites the WHOLE layout — the version token is mandatory
        # here (unlike granular mutations where it stays optional).
        vol.Required("expected_updated_at"): str,
    }
)
@websocket_api.async_response
async def ws_layout_restore(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Restore a revision as the current layout (admin, version-token guarded).

    The store writes a pre-restore revision of the CURRENT layout first, so a
    restore is itself undoable (eng lock 1A).
    """
    prepared = prepare_layout_mutation(hass, connection, msg)
    if prepared is None:
        return
    store, _layout = prepared
    revision = store.revisions.async_get_revision(msg["revision"])
    if revision is None:
        connection.send_error(msg["id"], "unknown_revision", f"no revision {msg['revision']}")
        return
    if revision.get("ts") != msg["ts"]:
        connection.send_error(
            msg["id"],
            "revision_moved",
            f"revision {msg['revision']} changed since the history view; reload history",
        )
        return
    try:
        restored = await store.async_restore(msg["revision"])
    except (vol.Invalid, GeometryError) as err:
        connection.send_error(msg["id"], getattr(err, "code", "invalid_structure"), str(err))
        return
    if restored is None:
        connection.send_error(msg["id"], "unknown_revision", f"no revision {msg['revision']}")
        return
    event_store = _get_event_store(hass)
    if event_store is not None:
        await event_store.async_append("layout_restored")
    connection.send_result(
        msg["id"], {"layout": restored, "restored_revision": msg["revision"]}
    )


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "ha_spatial/layout/export"})
@callback
def ws_layout_export(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return the full layout JSON for an off-HA backup (admin, OV2)."""
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    connection.send_result(msg["id"], {"layout": store.async_get()})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_spatial/layout/import",
        vol.Required("layout"): _validate_import_payload,
        # Import overwrites the WHOLE layout — version token mandatory.
        vol.Required("expected_updated_at"): str,
    }
)
@websocket_api.async_response
async def ws_layout_import(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Validate + save an uploaded layout (admin, version-token guarded, OV2).

    Goes through the normal save path, so the previous layout lands in the
    revision ring first and the import is undoable via layout/restore.
    """
    prepared = prepare_layout_mutation(hass, connection, msg)
    if prepared is None:
        return
    store, _layout = prepared
    try:
        saved = await store.async_save(msg["layout"])
    except (vol.Invalid, GeometryError) as err:
        connection.send_error(msg["id"], getattr(err, "code", "invalid_structure"), str(err))
        return
    connection.send_result(msg["id"], {"layout": saved})
