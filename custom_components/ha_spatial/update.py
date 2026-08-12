"""Update entity: surfaces new releases of the public distribution repo.

Polls the GitHub releases API (api.github.com, unauthenticated, every 12 h)
from the HA server. This is a deliberate, documented network egress — it
exists so the user can see "a newer HA Spatial is released" natively in
Settings → Updates, independent of HACS's cached release scan (which has
served day-old "latest" versions). Installation itself stays with HACS;
this entity only tells the truth about installed vs released.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN, _manifest_version

_LOGGER = logging.getLogger(__name__)

RELEASES_LATEST_URL = "https://api.github.com/repos/auge2u/ha-spatial-public/releases/latest"
UPDATE_INTERVAL = timedelta(hours=12)


class ReleaseCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch the latest published release tag from the public repo."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} release check",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)
        async with asyncio.timeout(30):
            resp = await session.get(
                RELEASES_LATEST_URL,
                headers={"Accept": "application/vnd.github+json"},
            )
            resp.raise_for_status()
            data = await resp.json()
        return {
            "latest": str(data.get("tag_name", "")).lstrip("v") or None,
            "url": data.get("html_url"),
        }


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the update entity (never blocks setup on network failure)."""
    coordinator = ReleaseCoordinator(hass)
    # Tolerate an offline first refresh: the entity simply reports unavailable
    # until a later poll succeeds. An air-gapped HA must still set up cleanly.
    await coordinator.async_refresh()
    hass.data[DOMAIN][entry.entry_id]["release_coordinator"] = coordinator
    async_add_entities([HaSpatialUpdateEntity(coordinator, entry)])


class HaSpatialUpdateEntity(CoordinatorEntity[ReleaseCoordinator], UpdateEntity):
    """Installed vs latest-released HA Spatial version."""

    _attr_has_entity_name = True
    _attr_name = "Update"
    _attr_release_summary = (
        "Update via HACS: HA Spatial → Redownload → pick the newest version, "
        "then restart Home Assistant and hard-refresh the browser."
    )

    def __init__(self, coordinator: ReleaseCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_update"
        self._attr_installed_version = _manifest_version()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="HA Spatial",
            manufacturer="Forge",
        )

    @property
    def latest_version(self) -> str | None:
        return (self.coordinator.data or {}).get("latest")

    @property
    def release_url(self) -> str | None:
        return (self.coordinator.data or {}).get("url")
