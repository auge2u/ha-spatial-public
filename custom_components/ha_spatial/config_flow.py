"""Config flow for HA Spatial (decision 1A).

Minimal single-instance, zero-field flow. Its only job is to make the
integration installable from the UI so async_setup_entry actually runs.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback

from .const import (
    CONF_VISION_API_KEY,
    CONF_VISION_MODEL,
    CONF_VISION_PROVIDER,
    CONF_VISION_TIMEOUT,
    DEFAULT_VISION_MODEL,
    DEFAULT_VISION_PROVIDER,
    DEFAULT_VISION_TIMEOUT,
    DOMAIN,
    PANEL_TITLE,
    VISION_PROVIDERS,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry, ConfigFlowResult


class HaSpatialConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Spatial."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> "ConfigFlowResult":
        """Single-instance setup: confirm, then create the entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title=PANEL_TITLE, data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: "ConfigEntry") -> "HaSpatialOptionsFlow":
        return HaSpatialOptionsFlow()


class HaSpatialOptionsFlow(OptionsFlow):
    """Vision provider configuration (D9/Codex#7). The API key stays server-side."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> "ConfigFlowResult":
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_VISION_PROVIDER,
                    default=opts.get(CONF_VISION_PROVIDER, DEFAULT_VISION_PROVIDER),
                ): vol.In(VISION_PROVIDERS),
                vol.Optional(CONF_VISION_API_KEY, default=opts.get(CONF_VISION_API_KEY, "")): str,
                vol.Optional(
                    CONF_VISION_MODEL, default=opts.get(CONF_VISION_MODEL, DEFAULT_VISION_MODEL)
                ): str,
                vol.Optional(
                    CONF_VISION_TIMEOUT,
                    default=opts.get(CONF_VISION_TIMEOUT, DEFAULT_VISION_TIMEOUT),
                ): vol.All(int, vol.Range(min=5, max=120)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
