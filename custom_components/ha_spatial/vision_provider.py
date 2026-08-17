"""Pluggable, backend-mediated vision providers (D4 / D9 / eng lock 3A/12A/18A).

The vision call runs server-side so the API key never reaches the browser (D4),
behind a small provider interface so alternatives are genuinely built in and a
swap is config, not a rewrite (D9). Three tiers ship:

- ``simulated`` (the default) — no network, no egress, mirrors the frontend
  simulated layer. Egress class ``none``.
- ``ai_task`` — the local-first tier (eng lock 3A): a structured vision task
  through Home Assistant's own ``ai_task`` integration. HA owns provider,
  model, and locality selection; we attach the photos and pass the
  room-analysis output structure. Egress class ``local``.
- ``grok`` — x.ai multimodal. Egress class ``cloud``.

Every provider is classified by egress class (``none`` | ``local`` | ``cloud``)
in the registry below; the WS consent gate keys on the CLASS, not the provider
name (eng lock 12A): ``none`` needs no consent step, ``local`` gets
informational microcopy only, ``cloud`` keeps the existing explicit consent
gate at full strength.

Returns the camelCase VisionResult shape the frontend already consumes.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_VISION_API_KEY,
    CONF_VISION_MODEL,
    CONF_VISION_TIMEOUT,
    DEFAULT_VISION_MODEL,
    DEFAULT_VISION_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
GROK_URL = "https://api.x.ai/v1/chat/completions"

# Timeout bounds mirror the options-flow schema (5–120 s). Stored options are
# trusted only after this coercion (codex verification #3): garbage/None falls
# back to the default, out-of-range numbers clamp.
_VISION_TIMEOUT_MIN = 5
_VISION_TIMEOUT_MAX = 120


def vision_timeout(options: dict[str, Any]) -> int:
    """The effective provider timeout (seconds), coerced into 5–120."""
    raw = options.get(CONF_VISION_TIMEOUT, DEFAULT_VISION_TIMEOUT)
    if isinstance(raw, bool):
        return DEFAULT_VISION_TIMEOUT
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_VISION_TIMEOUT
    return min(_VISION_TIMEOUT_MAX, max(_VISION_TIMEOUT_MIN, value))

# Egress classes (eng lock 12A). The consent gate keys on these, never on the
# provider name, so a new provider inherits the right privacy posture the
# moment it is classified here.
EGRESS_NONE = "none"
EGRESS_LOCAL = "local"
EGRESS_CLOUD = "cloud"
EGRESS_CLASSES = (EGRESS_NONE, EGRESS_LOCAL, EGRESS_CLOUD)

# Where photos are staged so ai_task can attach them: ai_task attachments are
# media-source references (there is no inline-bytes channel), so decoded photos
# are written under the local media dir for the duration of the call and
# deleted immediately after.
_MEDIA_STAGING_SUBDIR = DOMAIN

_DEFAULT_RECOMMENDATION = {
    "id": "evening-lighting-scene",
    "title": "Set up an evening lighting scene",
    "rationale": "Group this room's lights into a one-tap evening scene.",
    "priority": 1,
    "entityType": "light",
}


class VisionProviderError(Exception):
    """Carries a stable error code for the WS layer.

    ``status`` is the provider's HTTP status when one exists; it feeds the
    structured (redacted) error log in the WS layer. The message may embed
    request details — it is shown to the admin client but MUST NOT be logged
    (eng lock 18A fold: no endpoint hosts, file paths, or prompts in logs).
    """

    def __init__(self, code: str, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


_DATA_URL_RE = re.compile(r"^data:([^;]+);base64,(.+)$", re.IGNORECASE)


def decode_data_url(url: str) -> tuple[str, bytes]:
    """Decode a validated photo data URL into (mime, bytes).

    Pure and blocking — callers on the event loop must run this in the
    executor. Assumes the URL already passed the WS schema's format checks;
    raises ValueError on undecodable payloads.
    """
    match = _DATA_URL_RE.match(url)
    if not match:
        raise ValueError("photo must be a base64 data URL")
    mime = match.group(1).lower()
    try:
        return mime, base64.b64decode(match.group(2), validate=True)
    except Exception as exc:
        raise ValueError(f"invalid base64 photo data: {exc}") from exc


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


# Output bounds (codex adversarial #5): a provider's structured output is
# untrusted — cap counts and string lengths and coerce wrong-typed fields,
# same philosophy as the grok degrade path. Bounded here so every provider
# that flows through _parse_structured inherits the limits.
_MAX_UNDERSTANDING_LEN = 400
_MAX_NOTICED = 10
_MAX_NOTICED_LEN = 80
_MAX_RECOMMENDATIONS = 5
_MAX_REC_ID_LEN = 60
_MAX_REC_TITLE_LEN = 80
_MAX_REC_RATIONALE_LEN = 240
_MAX_REC_ENTITY_TYPE_LEN = 40
_MAX_ROOM_NAME_LEN = 100


def _bounded_str(value: Any, max_len: int) -> str:
    """str-or-empty, truncated to max_len. Numbers are coerced (str(7) → "7");
    bools, None, and containers are dropped."""
    if isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        value = str(value)
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_len]


def _normalize_recommendations(raw: Any) -> list[dict[str, Any]]:
    """Whitelist-normalize recommendation objects: mappings only, contract keys
    only, bounded strings, integer priority. Empty result → the default rec."""
    if not isinstance(raw, list):
        return [dict(_DEFAULT_RECOMMENDATION)]
    recs: list[dict[str, Any]] = []
    for item in raw:
        if len(recs) >= _MAX_RECOMMENDATIONS:
            break
        if not isinstance(item, Mapping):
            continue
        try:
            priority = int(item.get("priority", 1))
        except (TypeError, ValueError):
            priority = 1
        recs.append(
            {
                "id": _bounded_str(item.get("id"), _MAX_REC_ID_LEN) or "scene",
                "title": _bounded_str(item.get("title"), _MAX_REC_TITLE_LEN) or "Scene suggestion",
                "rationale": _bounded_str(item.get("rationale"), _MAX_REC_RATIONALE_LEN),
                "priority": max(1, priority),
                "entityType": _bounded_str(item.get("entityType"), _MAX_REC_ENTITY_TYPE_LEN) or "light",
            }
        )
    return recs or [dict(_DEFAULT_RECOMMENDATION)]


def _parse_structured(
    parsed: Mapping[str, Any], room_hint: str | None, model_used: str
) -> dict[str, Any]:
    """Fill a VisionResult from a parsed mapping — defaulted AND bounded."""
    noticed_raw = parsed.get("noticed", [])
    if isinstance(noticed_raw, str):
        noticed_raw = [noticed_raw]
    if not isinstance(noticed_raw, list):
        noticed_raw = []
    # Break at the cap BEFORE building (codex verification #4): a hostile
    # 10k-item list must not be fully normalized first.
    noticed: list[str] = []
    for item in noticed_raw:
        if len(noticed) >= _MAX_NOTICED:
            break
        chip = _bounded_str(item, _MAX_NOTICED_LEN)
        if chip:
            noticed.append(chip)
    try:
        confidence = float(parsed.get("confidence", 0.85))
    except (TypeError, ValueError):
        confidence = 0.85
    confidence = min(1.0, max(0.0, confidence))
    understanding = _bounded_str(parsed.get("understanding"), _MAX_UNDERSTANDING_LEN)
    if not understanding:
        understanding = "Analyzed your room."
    suggested = _bounded_str(parsed.get("suggestedRoomName"), _MAX_ROOM_NAME_LEN) or room_hint
    return {
        "understanding": understanding,
        "confidence": confidence,
        "noticed": noticed,
        "recommendations": _normalize_recommendations(parsed.get("recommendations")),
        "suggestedRoomName": suggested,
        "modelUsed": model_used,
    }


def _parse_grok(text: str, room_hint: str | None, model_used: str = "grok") -> dict[str, Any]:
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
            "modelUsed": model_used,
        }
    if not isinstance(parsed, Mapping):
        parsed = {}
    return _parse_structured(parsed, room_hint, model_used)


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
    timeout = aiohttp.ClientTimeout(total=vision_timeout(options))
    session = async_get_clientsession(hass)
    try:
        resp = await session.post(
            GROK_URL, json=payload, headers={"Authorization": f"Bearer {key}"}, timeout=timeout
        )
        if resp.status != 200:
            raise VisionProviderError(
                "provider_error", f"vision provider returned HTTP {resp.status}", status=resp.status
            )
        data = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as err:
        raise VisionProviderError("provider_error", f"vision request failed: {err}") from err

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as err:
        raise VisionProviderError("provider_error", "unexpected vision response shape") from err
    return _parse_grok(text, request.get("room_hint"))


# --- ai_task tier (eng lock 3A) -------------------------------------------------

AI_TASK_SERVICE_DOMAIN = "ai_task"
AI_TASK_SERVICE_GENERATE_DATA = "generate_data"

# Selector-based output structure for ai_task.generate_data. Providers that
# honor it return exactly these keys in response["data"]; providers that ignore
# it (plain text, partial dicts, foreign shapes) are caught by _parse_ai_task —
# same degrade contract as grok: fill defaults, and raise a typed error when
# the output is unusable (never silent garbage, eng lock 18A).
AI_TASK_STRUCTURE: dict[str, Any] = {
    "understanding": {
        "selector": {"text": {}},
        "description": "One plain sentence describing the room",
        "required": True,
    },
    "confidence": {
        "selector": {"number": {"min": 0, "max": 1, "step": 0.05}},
        "description": "Confidence in the read, 0 to 1",
    },
    "noticed": {
        "selector": {"text": {"multiple": True}},
        "description": "Short observed signals about the room",
    },
    "recommendations": {
        "selector": {"object": {}},
        "description": "List of {id, title, rationale, priority, entityType} recommendations",
    },
    "suggestedRoomName": {
        "selector": {"text": {}},
        "description": "A short name for the room",
    },
}


def _ai_task_instructions(room_hint: str | None) -> str:
    hint = f" The user calls it: {room_hint}." if room_hint else ""
    return (
        "You are helping map a home room from the attached photos."
        + hint
        + " Describe the room — what kind of space it is, its rough layout, and "
        "notable features — then recommend one useful lighting scene for it."
    )


def detect_ai_task_capabilities(hass: HomeAssistant) -> dict[str, Any]:
    """Probe whether HA's ai_task integration can run a structured vision task.

    Used by the options flow (preflight) and ha_spatial/info (surfacing). Never
    raises — an unconfigured ai_task is a normal state, not an error.
    ``preferred`` is the user's configured generate_data preference;
    ``resolved`` is the entity WE will actually use: the preferred one only if
    it supports BOTH generate-data and attachments, else the first entity that
    does, else None (verification pass #1 — a text-only preferred entity must
    not be acked/named and then fail or misroute at runtime).
    """
    available = hass.services.has_service(AI_TASK_SERVICE_DOMAIN, AI_TASK_SERVICE_GENERATE_DATA)
    entities: list[str] = []
    attachment_entities: list[str] = []
    preferred: str | None = None
    if available:
        # Deferred import (repo convention) — and deliberately defensive: pip
        # installs of homeassistant do NOT include component manifest
        # requirements, and the ai_task package __init__ pulls in
        # homeassistant.components.conversation, which imports hassil at
        # module level. Real HA installs fetch hassil when conversation/ai_task
        # set up, but stripped TEST environments (pytest-ha-cc) don't have it,
        # so the import can fail even though the mocked service is registered.
        # The fallbacks are equivalent: HassKey is a str subclass (plain-string
        # lookup hits the same hass.data entry) and the feature bits are part
        # of HA's state-attribute API contract.
        try:
            from homeassistant.components.ai_task.const import (
                DATA_PREFERENCES,
                AITaskEntityFeature,
            )

            generate_data_feature: int = AITaskEntityFeature.GENERATE_DATA
            attachments_feature: int = AITaskEntityFeature.SUPPORT_ATTACHMENTS
        except ImportError:  # pragma: no cover — depends on the test env's deps
            DATA_PREFERENCES = "ai_task_preferences"
            generate_data_feature = 1
            attachments_feature = 2

        prefs = hass.data.get(DATA_PREFERENCES)
        if prefs is not None:
            preferred = prefs.gen_data_entity_id
        for state in hass.states.async_all(AI_TASK_SERVICE_DOMAIN):
            features = int(state.attributes.get("supported_features", 0) or 0)
            if features & generate_data_feature:
                entities.append(state.entity_id)
                if features & attachments_feature:
                    attachment_entities.append(state.entity_id)
    if preferred in attachment_entities:
        resolved: str | None = preferred
    else:
        resolved = attachment_entities[0] if attachment_entities else None
    return {
        "available": available,
        "entities": entities,
        "attachment_entities": attachment_entities,
        "preferred": preferred,
        "resolved": resolved,
        "generate_data": bool(entities),
        "attachments": bool(attachment_entities),
    }


def resolve_ai_task_entity(hass: HomeAssistant) -> str | None:
    """The ai_task entity generate_data will be called with: the user's
    configured preference IF it supports both generate-data and attachments,
    else the first entity that does, else None. Single source for the WS
    consent gate (ack binding, codex verification #1) and the provider call,
    so routing is deterministic and auditable."""
    return detect_ai_task_capabilities(hass)["resolved"]


def _write_media_photos(media_dir: str, decoded: list[tuple[str, bytes]]) -> list[tuple[str, str]]:
    """Stage decoded photos under the local media dir. Returns (mime, filename)
    pairs. Blocking — run in the executor. On any write failure, every file
    written so far is deleted before the error propagates (no partial staging
    leak, codex adversarial #3)."""
    folder = Path(media_dir) / _MEDIA_STAGING_SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    batch = uuid.uuid4().hex
    written: list[tuple[str, str]] = []
    try:
        for index, (mime, data) in enumerate(decoded):
            ext = ".jpg" if mime == "image/jpeg" else ".png"
            name = f"{batch}-{index}{ext}"
            (folder / name).write_bytes(data)
            written.append((mime, name))
    except OSError:
        _cleanup_media_photos(media_dir, written)
        raise
    return written


def _cleanup_media_photos(media_dir: str, written: list[tuple[str, str]]) -> None:
    """Delete staged photos (best effort). Blocking — run in the executor."""
    folder = Path(media_dir) / _MEDIA_STAGING_SUBDIR
    for _mime, name in written:
        try:
            (folder / name).unlink(missing_ok=True)
        except OSError:
            pass


def _parse_ai_task(data: Any, room_hint: str | None) -> dict[str, Any]:
    """Map an ai_task generate_data response payload to a VisionResult.

    A provider that honors AI_TASK_STRUCTURE returns a mapping — missing keys
    fall back to the same defaults as the grok parse. A provider that ignores
    the structure usually returns plain text — degrade exactly like the grok
    text path. Anything else is unusable: typed error, never silent garbage.
    """
    if isinstance(data, Mapping):
        return _parse_structured(data, room_hint, "ai_task")
    if isinstance(data, str) and data.strip():
        return _parse_grok(data, room_hint, model_used="ai_task")
    raise VisionProviderError("provider_error", "unexpected ai_task response shape")


async def _analyze_ai_task(
    hass: HomeAssistant, request: dict[str, Any], options: dict[str, Any]
) -> dict[str, Any]:
    """Structured vision task through HA's own ai_task integration (eng lock 3A).

    HA owns provider/model/locality selection. Photos reach ai_task the only
    way it accepts attachments — as local media-source references — so decoded
    photos are staged under the media dir for the duration of the call and
    deleted right after; nothing is sent anywhere by THIS integration.
    """
    decoded = request.get("photos_decoded")
    if decoded is None:
        # Eval-runner path: the WS layer decodes off the event loop and passes
        # photos_decoded; direct callers get the same treatment here.
        urls = request.get("photos", [])
        decoded = await hass.async_add_executor_job(
            lambda: [decode_data_url(u) for u in urls]
        )
    if not decoded:
        raise VisionProviderError("no_photos", "no photos to analyze")
    if not hass.services.has_service(AI_TASK_SERVICE_DOMAIN, AI_TASK_SERVICE_GENERATE_DATA):
        raise VisionProviderError(
            "no_provider_configured",
            "Home Assistant's ai_task integration is not set up — configure an AI task entity first",
        )
    # Resolve BEFORE staging (verification pass #1): the entity must support
    # both generate-data AND attachments — a text-only preferred entity is
    # never called with photos, and a mixed-capability setup falls back to the
    # first attachment-capable entity. None capable → clear typed error.
    entity_id = resolve_ai_task_entity(hass)
    if entity_id is None:
        raise VisionProviderError(
            "provider_error",
            "no attachment-capable ai_task entity is configured",
        )

    media_dir = hass.config.media_dirs.get("local") or hass.config.path("media")
    try:
        written = await hass.async_add_executor_job(_write_media_photos, media_dir, decoded)
    except OSError as err:
        raise VisionProviderError("provider_error", "could not stage photos for ai_task") from err

    attachments = [
        {
            "media_content_id": f"media-source://media_source/local/{_MEDIA_STAGING_SUBDIR}/{name}",
            "media_content_type": mime,
        }
        for mime, name in written
    ]
    # Pass entity_id explicitly (codex verification #1): routing is
    # deterministic — the same resolution the acknowledgment gate checked —
    # never a silent preference lookup at call time.
    service_data: dict[str, Any] = {
        "task_name": "HA Spatial room analysis",
        "instructions": _ai_task_instructions(request.get("room_hint")),
        "structure": AI_TASK_STRUCTURE,
        "attachments": attachments,
        "entity_id": entity_id,
    }
    try:
        # Bounded wait (codex adversarial #2): a hung provider must not hold
        # staged photos (or the WS handler) forever. The configured vision
        # timeout doubles as the cap; the finally below still cleans up.
        response = await asyncio.wait_for(
            hass.services.async_call(
                AI_TASK_SERVICE_DOMAIN,
                AI_TASK_SERVICE_GENERATE_DATA,
                service_data,
                blocking=True,
                return_response=True,
            ),
            timeout=vision_timeout(options),
        )
    except TimeoutError as err:
        raise VisionProviderError("provider_timeout", "ai_task generate_data timed out") from err
    except HomeAssistantError as err:
        raise VisionProviderError("provider_error", "ai_task generate_data failed") from err
    finally:
        await hass.async_add_executor_job(_cleanup_media_photos, media_dir, written)

    data = (response or {}).get("data")
    return _parse_ai_task(data, request.get("room_hint"))


ProviderFn = Callable[[HomeAssistant, dict, dict], Awaitable[dict]]


@dataclass(frozen=True)
class ProviderSpec:
    """A registered provider: its analyze function + egress class (eng lock 12A).

    ``decode_photos`` tells the WS layer whether to decode base64 photos off
    the event loop: required when the provider consumes bytes (ai_task staging)
    and kept for cloud providers so payloads are validated before egress;
    skipped for zero-egress providers that never look at photo bytes (codex
    adversarial #7).
    """

    name: str
    egress_class: str
    fn: ProviderFn
    decode_photos: bool


PROVIDERS: dict[str, ProviderSpec] = {
    "simulated": ProviderSpec("simulated", EGRESS_NONE, _analyze_simulated, decode_photos=False),
    "ai_task": ProviderSpec("ai_task", EGRESS_LOCAL, _analyze_ai_task, decode_photos=True),
    "grok": ProviderSpec("grok", EGRESS_CLOUD, _analyze_grok, decode_photos=True),
}


def get_provider(name: str) -> ProviderFn | None:
    spec = PROVIDERS.get(name)
    return spec.fn if spec is not None else None


def get_provider_spec(name: str) -> ProviderSpec | None:
    return PROVIDERS.get(name)
