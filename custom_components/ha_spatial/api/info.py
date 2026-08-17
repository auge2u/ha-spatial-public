"""ha_spatial/info — installed version + latest published release."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from ..const import DOMAIN, _manifest_version
from .common import _get_store


@websocket_api.websocket_command({vol.Required("type"): "ha_spatial/info"})
@callback
def ws_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Installed version + latest published release (any authenticated user).

    The panel compares its own baked bundle version against `version` to
    detect a stale browser tab, and shows `update_available` so users learn
    about new releases without relying on HACS's cached release scan.
    """
    version = _manifest_version()
    latest: str | None = None
    release_url: str | None = None
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if isinstance(entry_data, dict) and (
            coordinator := entry_data.get("release_coordinator")
        ):
            data = coordinator.data or {}
            latest = data.get("latest")
            release_url = data.get("url")
            break
    update_available = False
    if latest:
        try:
            from awesomeversion import AwesomeVersion

            update_available = AwesomeVersion(latest) > AwesomeVersion(version)
        except Exception:  # noqa: BLE001 — a weird tag must never break info
            update_available = False
    store = _get_store(hass)
    connection.send_result(
        msg["id"],
        {
            "version": version,
            "latest_version": latest,
            "release_url": release_url,
            "update_available": update_available,
            "restore_available": store.restore_available if store is not None else False,
        },
    )
