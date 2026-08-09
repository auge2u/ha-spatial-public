"""HA Spatial scene platform (T3 / decision D3).

Materializes the stored scene definitions (scene_store.py) as real, activatable
Home Assistant scene entities. Using the documented scene-platform API — rather
than poking the core scene integration's storage internals — keeps this durable
AND robust: scenes survive restarts (reloaded from our store on setup) and show
up as scene.* entities the user can trigger from the UI or automations.

A SceneManager (stashed per entry) lets the WS commands add/remove scenes
dynamically after setup.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.state import async_reproduce_state

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: "ConfigEntry", async_add_entities: "AddEntitiesCallback"
) -> None:
    """Recreate scene entities from stored defs and wire the dynamic manager."""
    data = hass.data[DOMAIN][entry.entry_id]
    store = data["scene_store"]
    manager = SceneManager(hass, async_add_entities)
    data["scene_manager"] = manager

    existing = [SpatialScene(scene_def) for scene_def in store.async_all()]
    manager.track(existing)
    if existing:
        async_add_entities(existing)


class SceneManager:
    """Adds/removes SpatialScene entities at runtime (after platform setup)."""

    def __init__(self, hass: HomeAssistant, async_add_entities: "AddEntitiesCallback") -> None:
        self._hass = hass
        self._add = async_add_entities
        self._entities: dict[str, SpatialScene] = {}

    def track(self, entities: list["SpatialScene"]) -> None:
        for entity in entities:
            self._entities[entity.scene_id] = entity

    def async_add_scene(self, scene_def: dict[str, Any]) -> None:
        entity = SpatialScene(scene_def)
        self._entities[entity.scene_id] = entity
        self._add([entity])

    async def async_remove_scene(self, scene_id: str) -> bool:
        entity = self._entities.pop(scene_id, None)
        if entity is None:
            return False
        # Remove via the entity registry (how HA's own UI deletes entities): this
        # clears the state AND the registry entry. entity.async_remove() alone
        # leaves a registry-backed entity's state in place.
        registry = er.async_get(self._hass)
        if entity.entity_id and registry.async_get(entity.entity_id):
            registry.async_remove(entity.entity_id)
        else:
            await entity.async_remove(force_remove=True)
        return True


class SpatialScene(Scene):
    """A scene built from a stored HA Spatial definition."""

    _attr_should_poll = False

    def __init__(self, scene_def: dict[str, Any]) -> None:
        self._def = scene_def
        self._attr_unique_id = scene_def["id"]
        self._attr_name = scene_def["name"]

    @property
    def scene_id(self) -> str:
        return self._def["id"]

    async def async_activate(self, **kwargs: Any) -> None:
        """Reproduce the snapshotted states this scene captured."""
        states = [
            State(e["entity_id"], e["state"], e.get("attributes") or {})
            for e in self._def["entities"]
        ]
        await async_reproduce_state(self.hass, states)
