"""Vision command: ha_spatial/vision/analyze (backend-mediated, consent-gated)."""
from __future__ import annotations

import logging
import re
import time

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from ..const import (
    CONF_VISION_AI_TASK_ACK,
    CONF_VISION_PROVIDER,
    DEFAULT_VISION_PROVIDER,
)
from ..schema import _finite_float
from ..vision_provider import (
    EGRESS_CLOUD,
    EGRESS_LOCAL,
    VisionProviderError,
    decode_data_url,
    get_provider_spec,
    resolve_ai_task_entity,
)
from .common import _get_entry_data, _rate_limit_or_error

_LOGGER = logging.getLogger(__name__)

_MAX_VISION_PHOTOS = 6
_MAX_VISION_PHOTO_BYTES = 2 * 1024 * 1024  # 2 MB decoded
# Encoded-length upper bound (~4/3 of decoded + padding): lets the schema reject
# oversized photos WITHOUT decoding them on the event loop (eng lock 12A fold).
_MAX_VISION_PHOTO_B64_LEN = (_MAX_VISION_PHOTO_BYTES // 3 + 1) * 4
_ALLOWED_VISION_IMAGE_TYPES = ("image/jpeg", "image/png")

# Structural image checks per allowed MIME (codex verification #2): a JPEG
# must open with SOI (FF D8 FF) AND close with EOI (FF D9); a PNG must carry
# the 8-byte signature AND the IEND chunk trailer. This rejects truncated and
# polyglot-lite payloads without new dependencies — full decode validation
# (e.g. Pillow) is deliberately out of scope.
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_IEND = b"\x00\x00\x00\x00IEND\xae\x42\x60\x82"


def _valid_image_bytes(mime: str, data: bytes) -> bool:
    if mime == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9")
    if mime == "image/png":
        return data.startswith(_PNG_SIGNATURE) and data.endswith(_PNG_IEND)
    return False


_DATA_URL_RE = re.compile(r"^data:([^;]+);base64,(.+)$", re.IGNORECASE)
_B64_ALPHABET_RE = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")


def _validate_data_url(url: str) -> str:
    """Cheap, decode-free schema check: shape, image type, base64 alphabet, and
    an encoded-size upper bound. The actual decode + magic-byte check happens
    off the event loop in the handler (eng lock 12A fold)."""
    if not isinstance(url, str):
        raise vol.Invalid("photo must be a data URL string")
    match = _DATA_URL_RE.match(url)
    if not match:
        raise vol.Invalid("photo must be a base64 data URL")
    mime = match.group(1).lower()
    if mime not in _ALLOWED_VISION_IMAGE_TYPES:
        raise vol.Invalid(f"unsupported image type {mime}")
    b64 = match.group(2)
    if len(b64) > _MAX_VISION_PHOTO_B64_LEN:
        raise vol.Invalid(f"photo exceeds {_MAX_VISION_PHOTO_BYTES // (1024 * 1024)} MB decoded")
    if len(b64) % 4 or not _B64_ALPHABET_RE.match(b64):
        raise vol.Invalid("invalid base64 photo data")
    return url


def _decode_photos(urls: list[str]) -> list[tuple[str, bytes]]:
    """Decode + validate photo data URLs: decoded size and magic bytes.
    Blocking — run in the executor. Raises ValueError with the same messages
    the schema used to produce, so the WS error contract (``invalid_format``)
    is unchanged."""
    decoded: list[tuple[str, bytes]] = []
    for url in urls:
        try:
            mime, data = decode_data_url(url)
        except ValueError as err:
            raise ValueError(str(err)) from err
        if len(data) > _MAX_VISION_PHOTO_BYTES:
            raise ValueError(f"photo exceeds {_MAX_VISION_PHOTO_BYTES // (1024 * 1024)} MB decoded")
        if not _valid_image_bytes(mime, data):
            raise ValueError("photo bytes are not a structurally valid JPEG/PNG image")
        decoded.append((mime, data))
    return decoded


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_spatial/vision/analyze",
        vol.Optional("photos", default=list): vol.All(
            [_validate_data_url],
            vol.Length(max=_MAX_VISION_PHOTOS),
        ),
        vol.Optional("room_hint"): str,
        vol.Optional("signals", default=dict): {
            vol.Optional("photo_count", default=0): vol.All(int, vol.Range(min=0)),
            vol.Optional("avg_aspect", default=1.0): vol.All(_finite_float, vol.Range(min=0)),
            vol.Optional("is_high_quality_set", default=False): bool,
        },
        vol.Optional("consent", default=False): bool,
    }
)
@websocket_api.async_response
async def ws_analyze_vision(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Backend-mediated vision analysis (D4/D9). Key stays server-side; egress
    is consent-gated by provider class."""
    data = _get_entry_data(hass)
    if data is None or "entry" not in data:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    if not _rate_limit_or_error(hass, connection, msg):
        return
    options = data["entry"].options
    provider_name = options.get(CONF_VISION_PROVIDER, DEFAULT_VISION_PROVIDER)
    spec = get_provider_spec(provider_name)
    if spec is None:
        connection.send_error(msg["id"], "no_provider", f"unknown vision provider {provider_name}")
        return
    # Privacy contract (eng lock 12A + codex adversarial #1 + verification #1):
    # the gate keys on the provider's EGRESS CLASS, not its name. `none` never
    # leaves the device (no gate). `cloud` requires explicit per-analysis
    # consent. `local` means "managed by the user's HA AI configuration" — HA
    # owns ai_task routing and the configured provider CAN be cloud-backed, so
    # it requires either per-analysis consent or the stored acknowledgment.
    # The acknowledgment is BOUND TO THE ENTITY it was given for: if HA's
    # preferred AI task entity has changed since, the ack is stale and the
    # gate fires again (the options flow re-acks against the new entity).
    if spec.egress_class == EGRESS_CLOUD and not msg["consent"]:
        connection.send_error(msg["id"], "consent_required", "cloud vision requires explicit consent")
        return
    if spec.egress_class == EGRESS_LOCAL and not msg["consent"]:
        ack = options.get(CONF_VISION_AI_TASK_ACK)
        entity = resolve_ai_task_entity(hass)
        if not isinstance(ack, str) or not ack or entity is None or ack != entity:
            connection.send_error(
                msg["id"],
                "consent_required",
                "ai_task vision requires an acknowledgment for the current AI task entity or per-analysis consent",
            )
            return
    # Decode off the event loop — and only when the provider actually consumes
    # or egresses photo bytes (codex adversarial #7): the simulated provider
    # never looks at them, so decoding would be pure waste.
    decoded: list[tuple[str, bytes]] = []
    if spec.decode_photos:
        try:
            decoded = await hass.async_add_executor_job(_decode_photos, msg["photos"])
        except ValueError as err:
            connection.send_error(msg["id"], "invalid_format", str(err))
            return
    request = {
        "photos": msg["photos"],
        "photos_decoded": decoded,
        "room_hint": msg.get("room_hint"),
        "signals": msg["signals"],
    }
    started = time.monotonic()
    try:
        result = await spec.fn(hass, request, options)
    except VisionProviderError as err:
        elapsed = time.monotonic() - started
        # Redacted on purpose (eng lock 18A fold): the error message can embed
        # request URLs, file paths, or prompt fragments — none of those belong
        # in the log. Class + code + status + timing is the actionable signal.
        _LOGGER.warning(
            "Vision analysis failed: provider=%s egress_class=%s code=%s status=%s elapsed=%.2fs",
            provider_name,
            spec.egress_class,
            err.code,
            err.status,
            elapsed,
        )
        connection.send_error(msg["id"], err.code, str(err))
        return
    # The panel keys its per-class privacy microcopy off this (eng lock 12A).
    result["egressClass"] = spec.egress_class
    connection.send_result(msg["id"], result)
