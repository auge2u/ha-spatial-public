"""Durable store of HA Spatial scene definitions (T3 / decision D3).

Scenes created from the First Room loop are persisted here — separate from the
layout store — and materialized as real, activatable HA scene entities by
scene.py. Persisting the definition (not HA's in-memory scene.create) is what
makes the "my home got smarter" payoff survive a restart.

The integration OWNS every scene in this store. That ownership is what makes
undo safe (Codex #8): scene/remove only ever deletes scenes we created, never a
same-named scene the user authored elsewhere.

A scene definition is: {id, name, entities: [{entity_id, state, attributes}]}.
Writes are immediate (durable across restart/crash).
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import SCENES_STORAGE_KEY, SCENES_STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class SceneStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, SCENES_STORAGE_VERSION, SCENES_STORAGE_KEY)
        self._scenes: dict[str, dict[str, Any]] = {}

    async def async_load(self) -> list[dict[str, Any]]:
        data = await self._store.async_load()
        if data and "scenes" in data:
            self._scenes = {s["id"]: s for s in data["scenes"]}
        return list(self._scenes.values())

    @callback
    def async_all(self) -> list[dict[str, Any]]:
        return list(self._scenes.values())

    @callback
    def async_get(self, scene_id: str) -> dict[str, Any] | None:
        return self._scenes.get(scene_id)

    async def async_add(self, scene_def: dict[str, Any]) -> None:
        self._scenes[scene_def["id"]] = scene_def
        await self._async_save()

    async def async_remove(self, scene_id: str) -> bool:
        """Remove a scene we own. Returns False if we never created it (provenance)."""
        if scene_id not in self._scenes:
            return False
        del self._scenes[scene_id]
        await self._async_save()
        return True

    async def _async_save(self) -> None:
        await self._store.async_save({"scenes": list(self._scenes.values())})
