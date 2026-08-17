"""Sidebar panel registration (decision 1A).

Replaces the previous add_extra_js_url (which injected a script into every HA
page without registering a panel) with a real custom panel registered via
panel_custom, admin-only in v0 (decision 6A). The served bundles are the
content-hashed panel entry + lazy chunks built from prototype/spatial-config
(T9 code-splitting); the module URL comes from bundle-manifest.json.
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
    PANEL_HASHED_STATIC_URL,
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

    Points at the cache-enabled static path (PANEL_HASHED_STATIC_URL): the
    manifest maps to a content-hashed filename, so immutable caching is safe.
    Lazy chunks import each other relatively, so they ride the same path.
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
    return f"{PANEL_HASHED_STATIC_URL}/{filename}"


async def async_register_panel(hass: "HomeAssistant") -> None:
    """Register the static asset paths and the sidebar panel (idempotent)."""
    domain_data = hass.data.setdefault(DOMAIN, {})

    if not domain_data.get(_STATIC_REGISTERED):
        static_dir = os.path.join(os.path.dirname(__file__), "www")
        # Two paths over the same dir (T9): PANEL_HASHED_STATIC_URL serves the
        # content-hashed panel entry + chunks with cache headers ON (new build
        # = new filenames via bundle-manifest.json, so a year-long immutable
        # cache is safe); PANEL_STATIC_URL serves the un-hashed card bundle and
        # fonts with cache headers OFF, since those URLs are stable across
        # releases. The browser never fetches the manifest itself (panel.py
        # reads it server-side).
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(PANEL_STATIC_URL, static_dir, False),
                StaticPathConfig(PANEL_HASHED_STATIC_URL, static_dir, True),
            ]
        )
        domain_data[_STATIC_REGISTERED] = True

    if PANEL_URL_PATH in hass.data.get("frontend_panels", {}):
        return

    static_dir = os.path.join(os.path.dirname(__file__), "www")
    # The bundle manifest is read from disk, so it goes to the executor — a
    # plain open() here trips HA's blocking-call detector during setup.
    module_url = await hass.async_add_executor_job(_panel_js_url, static_dir)
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_WEBCOMPONENT,
        module_url=module_url,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=PANEL_REQUIRE_ADMIN,
        config={},
    )


async def async_unregister_panel(hass: "HomeAssistant") -> None:
    """Remove the sidebar panel on unload (async_remove_panel is a callback)."""
    if PANEL_URL_PATH in hass.data.get("frontend_panels", {}):
        async_remove_panel(hass, PANEL_URL_PATH)
