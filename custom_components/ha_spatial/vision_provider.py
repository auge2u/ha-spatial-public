"""Pluggable, backend-mediated vision providers (D4 / D9).

The vision call runs server-side so the API key never reaches the browser (D4),
behind a small provider interface so alternatives are genuinely built in and a
swap is config, not a rewrite (D9). Two channels ship: `simulated` (the default —
no network, no egress, mirrors the frontend simulated layer) and `grok` (x.ai
multimodal). Selected via the options flow (Codex #7).

Returns the camelCase VisionResult shape the frontend already consumes.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_VISION_API_KEY,
    CONF_VISION_MODEL,
    CONF_VISION_TIMEOUT,
    DEFAULT_VISION_MODEL,
    DEFAULT_VISION_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)
GROK_URL = "https://api.x.ai/v1/chat/completions"

_DEFAULT_RECOMMENDATION = {
    "id": "evening-lighting-scene",
    "title": "Set up an evening lighting scene",
    "rationale": "Group this room's lights into a one-tap evening scene.",
    "priority": 1,
    "entityType": "light",
}


class VisionProviderError(Exception):
    """Carries a stable error code for the WS layer."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def build_simulated_result(signals: dict[str, Any], room_hint: str | None) -> dict[str, Any]:
    """Derive a plausible VisionResult from local signals — no network (mirrors the
    frontend simulated layer so the simulated/real swap is seamless)."""
    photo_count = int(signals.get("photo_count", 0))
    avg_aspect = float(signals.get("avg_aspect", 1) or 1)
    high_quality = bool(signals.get("is_high_quality_set", False))
    wide = avg_aspect > 1.85
    plural = "" if photo_count == 1 else "s"

    if wide:
        understanding = f"A wide room read from {photo_count} photo{plural} — likely an open space with more than one zone."
    elif high_quality:
        understanding = f"A clearly defined room from a detailed set of {photo_count} photos."
    else:
        understanding = f"A room captured from {photo_count} photo{plural}."

    noticed: list[str] = []
    if high_quality:
        noticed.append("High-resolution set")
    if wide:
        noticed.append(f"Wide layout ({avg_aspect:.2f}:1)")
    noticed.append(f"{photo_count} photo{plural}")

    return {
        "understanding": understanding,
        "confidence": 0.87 if high_quality else 0.7,
        "noticed": noticed,
        "recommendations": [dict(_DEFAULT_RECOMMENDATION)],
        "suggestedRoomName": room_hint,
        "modelUsed": "simulated",
    }


async def _analyze_simulated(
    hass: HomeAssistant, request: dict[str, Any], options: dict[str, Any]
) -> dict[str, Any]:
    return build_simulated_result(request.get("signals", {}), request.get("room_hint"))


def _prompt(room_hint: str | None) -> str:
    hint = f" The user calls it: {room_hint}." if room_hint else ""
    return (
        "You are helping map a home room from photos." + hint + " Reply ONLY with JSON: "
        '{"understanding": "<one plain sentence>", "noticed": ["<short signal>", ...], '
        '"recommendations": [{"id":"<slug>","title":"<short>","rationale":"<why>","priority":1,"entityType":"light"}]}'
    )


def _parse_grok(text: str, room_hint: str | None) -> dict[str, Any]:
    """Parse the model's reply into a VisionResult; degrade gracefully to plain text."""
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        parsed = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return {
            "understanding": text.strip()[:400] or "Analyzed your room.",
            "confidence": 0.6,
            "noticed": [],
            "recommendations": [dict(_DEFAULT_RECOMMENDATION)],
            "suggestedRoomName": room_hint,
            "modelUsed": "grok",
        }
    recs = parsed.get("recommendations") or [dict(_DEFAULT_RECOMMENDATION)]
    return {
        "understanding": parsed.get("understanding", "Analyzed your room."),
        "confidence": float(parsed.get("confidence", 0.85)),
        "noticed": list(parsed.get("noticed", [])),
        "recommendations": recs,
        "suggestedRoomName": parsed.get("suggestedRoomName", room_hint),
        "modelUsed": "grok",
    }


async def _analyze_grok(
    hass: HomeAssistant, request: dict[str, Any], options: dict[str, Any]
) -> dict[str, Any]:
    key = options.get(CONF_VISION_API_KEY)
    if not key:
        raise VisionProviderError("no_provider_configured", "Grok API key is not set")
    photos = request.get("photos", [])
    if not photos:
        raise VisionProviderError("no_photos", "no photos to analyze")

    content: list[dict[str, Any]] = [{"type": "text", "text": _prompt(request.get("room_hint"))}]
    for data_url in photos:
        content.append({"type": "image_url", "image_url": {"url": data_url}})

    payload = {
        "model": options.get(CONF_VISION_MODEL, DEFAULT_VISION_MODEL),
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 700,
        "temperature": 0.2,
    }
    timeout = aiohttp.ClientTimeout(total=options.get(CONF_VISION_TIMEOUT, DEFAULT_VISION_TIMEOUT))
    session = async_get_clientsession(hass)
    try:
        resp = await session.post(
            GROK_URL, json=payload, headers={"Authorization": f"Bearer {key}"}, timeout=timeout
        )
        if resp.status != 200:
            raise VisionProviderError("provider_error", f"vision provider returned HTTP {resp.status}")
        data = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as err:
        raise VisionProviderError("provider_error", f"vision request failed: {err}") from err

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as err:
        raise VisionProviderError("provider_error", "unexpected vision response shape") from err
    return _parse_grok(text, request.get("room_hint"))


ProviderFn = Callable[[HomeAssistant, dict, dict], Awaitable[dict]]
PROVIDERS: dict[str, ProviderFn] = {"simulated": _analyze_simulated, "grok": _analyze_grok}


def get_provider(name: str) -> ProviderFn | None:
    return PROVIDERS.get(name)
