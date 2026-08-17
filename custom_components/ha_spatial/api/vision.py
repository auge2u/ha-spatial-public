"""Vision command: ha_spatial/vision/analyze (backend-mediated, consent-gated)."""
from __future__ import annotations

import base64
import re

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from ..const import CONF_VISION_PROVIDER, DEFAULT_VISION_PROVIDER
from ..schema import _finite_float
from ..vision_provider import VisionProviderError, get_provider
from .common import _get_entry_data, _rate_limit_or_error

_MAX_VISION_PHOTOS = 6
_MAX_VISION_PHOTO_BYTES = 2 * 1024 * 1024  # 2 MB decoded
_ALLOWED_VISION_IMAGE_TYPES = ("image/jpeg", "image/png")


_DATA_URL_RE = re.compile(r"^data:([^;]+);base64,(.+)$", re.IGNORECASE)


def _validate_data_url(url: str) -> str:
    """Validate a vision photo data URL: image type and decoded size limits."""
    if not isinstance(url, str):
        raise vol.Invalid("photo must be a data URL string")
    match = _DATA_URL_RE.match(url)
    if not match:
        raise vol.Invalid("photo must be a base64 data URL")
    mime, b64 = match.groups()
    mime = mime.lower()
    if mime not in _ALLOWED_VISION_IMAGE_TYPES:
        raise vol.Invalid(f"unsupported image type {mime}")
    try:
        decoded = base64.b64decode(b64, validate=True)
    except Exception as exc:
        raise vol.Invalid(f"invalid base64 photo data: {exc}") from exc
    if len(decoded) > _MAX_VISION_PHOTO_BYTES:
        raise vol.Invalid(f"photo exceeds {_MAX_VISION_PHOTO_BYTES // (1024 * 1024)} MB decoded")
    return url


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
    """Backend-mediated vision analysis (D4/D9). Key stays server-side; cloud
    providers require explicit consent before any photo egress."""
    data = _get_entry_data(hass)
    if data is None or "entry" not in data:
        connection.send_error(msg["id"], "not_loaded", "HA Spatial is not set up")
        return
    if not _rate_limit_or_error(hass, connection, msg):
        return
    options = data["entry"].options
    provider_name = options.get(CONF_VISION_PROVIDER, DEFAULT_VISION_PROVIDER)
    provider = get_provider(provider_name)
    if provider is None:
        connection.send_error(msg["id"], "no_provider", f"unknown vision provider {provider_name}")
        return
    # Privacy contract: a cloud provider must not receive photos without explicit
    # consent for this analysis (the simulated provider never leaves the device).
    if provider_name != "simulated" and not msg["consent"]:
        connection.send_error(msg["id"], "consent_required", "cloud vision requires explicit consent")
        return
    request = {
        "photos": msg["photos"],
        "room_hint": msg.get("room_hint"),
        "signals": msg["signals"],
    }
    try:
        result = await provider(hass, request, options)
    except VisionProviderError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    connection.send_result(msg["id"], result)
