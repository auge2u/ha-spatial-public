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
    CONF_VISION_AI_TASK_ACK,
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
from .vision_provider import detect_ai_task_capabilities, resolve_ai_task_entity

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
            # Bind the acknowledgment to the entity it names (codex verification
            # #1): the checkbox stores the RESOLVED ai_task entity_id, not a
            # bare boolean, so a later preference change invalidates the ack.
            # Nothing to ack against (no capable entity) → store False.
            if user_input.get(CONF_VISION_AI_TASK_ACK):
                user_input[CONF_VISION_AI_TASK_ACK] = resolve_ai_task_entity(self.hass) or False
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
                vol.Optional(
                    CONF_VISION_AI_TASK_ACK,
                    # Stored value is the acknowledged entity_id (truthy) or
                    # False; the checkbox default only needs truthiness.
                    default=bool(opts.get(CONF_VISION_AI_TASK_ACK, False)),
                ): bool,
            }
        )
        # ai_task preflight (eng lock 3A): tell the user whether the local-first
        # tier is actually usable BEFORE they pick it. Detection is best-effort
        # and never blocks the form. The acknowledgment copy NAMES the entity
        # photos would go to (codex adversarial #1): HA owns ai_task routing,
        # so "local" can still be a cloud-backed provider.
        caps = detect_ai_task_capabilities(self.hass)
        if caps["attachments"]:
            ai_task_status = (
                "ai_task is ready: a configured AI task entity supports photo attachments."
            )
        elif caps["available"]:
            ai_task_status = (
                "ai_task is set up, but no configured AI task entity supports photo "
                "attachments — the local tier cannot analyze photos yet."
            )
        else:
            ai_task_status = (
                "ai_task is not set up — add an AI task integration (for example a "
                "local model) to use the local tier."
            )
        ai_task_entity = caps["resolved"]
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "ai_task_status": ai_task_status,
                "ai_task_entity": ai_task_entity or "no attachment-capable AI task entity",
            },
        )
