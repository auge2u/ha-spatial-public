"""HA Spatial - Spatially accurate, HA-aware home layout mapping.

HA imports are deferred into the entry lifecycle functions so the pure modules
(geometry, schema) stay importable without Home Assistant installed.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .const import DOMAIN, _manifest_version

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

__version__ = _manifest_version()


async def async_setup(hass: "HomeAssistant", config: dict) -> bool:
    """Set up the HA Spatial component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    """Set up HA Spatial: load the store, start registry sync, register API + panel."""
    from homeassistant.const import Platform

    from .api import async_register_api
    from .events import EventStore
    from .panel import async_register_panel
    from .registry_sync import RegistrySync
    from .scene_store import SceneStore
    from .spatial import SpatialStore

    store = SpatialStore(hass)
    await store.async_load()

    event_store = EventStore(hass)
    await event_store.async_load()

    scene_store = SceneStore(hass)
    await scene_store.async_load()

    sync = RegistrySync(hass, store)
    await sync.async_setup()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "entry": entry,  # for live options (vision provider config, D9)
        "store": store,
        "sync": sync,
        "event_store": event_store,
        "scene_store": scene_store,
    }

    # Forward to our scene platform AFTER stashing scene_store (scene.py reads it).
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SCENE])

    async_register_api(hass)
    await async_register_panel(hass)
    return True


async def async_unload_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    """Unload a config entry: scene platform, sync, flush the store, panel."""
    from homeassistant.const import Platform

    from .panel import async_unregister_panel

    await hass.config_entries.async_unload_platforms(entry, [Platform.SCENE])
    entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if entry_data:
        if (sync := entry_data.get("sync")) is not None:
            await sync.async_unload()
        # Flush any debounced layout write so unload never drops the last edit (Codex #5).
        if (store := entry_data.get("store")) is not None:
            await store.async_save_now()
        # Same for funnel events.
        if (event_store := entry_data.get("event_store")) is not None:
            await event_store.async_save_now()
    await async_unregister_panel(hass)
    return True
