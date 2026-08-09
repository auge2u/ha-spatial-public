"""Sidebar panel registration (decision 1A).

Replaces the previous add_extra_js_url (which injected a script into every HA
page without registering a panel) with a real custom panel registered via
panel_custom, admin-only in v0 (decision 6A). The served bundle is the
placeholder today; the real editor lands with the panel build pipeline (M4).
"""
from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from homeassistant.components import panel_custom
from homeassistant.components.frontend import async_remove_panel
from homeassistant.components.http import StaticPathConfig

from .const import (
    DOMAIN,
    PANEL_ICON,
    PANEL_REQUIRE_ADMIN,
    PANEL_STATIC_URL,
    PANEL_TITLE,
    PANEL_URL_PATH,
    PANEL_WEBCOMPONENT,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_STATIC_REGISTERED = "static_registered"
_BUNDLE_MANIFEST = "bundle-manifest.json"
_FALLBACK_PANEL_JS = "ha-spatial-panel.js"


def _panel_js_url(static_dir: str) -> str:
    """Return the panel JS URL from the content-hashed bundle manifest.

    Falls back to the legacy un-hashed filename if the manifest is missing.
    """
    manifest_path = os.path.join(static_dir, _BUNDLE_MANIFEST)
    filename = _FALLBACK_PANEL_JS
    try:
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
        filename = data.get("panel", filename)
    except (OSError, json.JSONDecodeError):
        pass
    return f"{PANEL_STATIC_URL}/{filename}"


async def async_register_panel(hass: "HomeAssistant") -> None:
    """Register the static asset path and the sidebar panel (idempotent)."""
    domain_data = hass.data.setdefault(DOMAIN, {})

    if not domain_data.get(_STATIC_REGISTERED):
        static_dir = os.path.join(os.path.dirname(__file__), "www")
        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_STATIC_URL, static_dir, False)]
        )
        domain_data[_STATIC_REGISTERED] = True

    if PANEL_URL_PATH in hass.data.get("frontend_panels", {}):
        return

    static_dir = os.path.join(os.path.dirname(__file__), "www")
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_WEBCOMPONENT,
        module_url=_panel_js_url(static_dir),
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=PANEL_REQUIRE_ADMIN,
        config={},
    )


async def async_unregister_panel(hass: "HomeAssistant") -> None:
    """Remove the sidebar panel on unload (async_remove_panel is a callback)."""
    if PANEL_URL_PATH in hass.data.get("frontend_panels", {}):
        async_remove_panel(hass, PANEL_URL_PATH)
