"""Runtime structural validation with voluptuous (decision 8A).

HA-native validation that mirrors the cross-language contract in
layout.schema.json (decision 4A). voluptuous is bundled with Home Assistant, so
this adds no runtime dependency. A contract-agreement test asserts this schema
and the JSON Schema accept/reject the same cases.

Pure module — no HA imports — so it is unit-testable without the HA harness.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import voluptuous as vol

from .const import KNOWN_LAYOUT_VERSION, MOUNT_TYPES


def _finite_float(value: Any) -> float:
    """Coerce to float and reject NaN / Infinity.

    Non-numeric input (None, objects, non-numeric strings) raises the TYPED
    vol.Invalid — a raw TypeError here would bypass the corrupt-store recovery
    path in SpatialStore.async_load.
    """
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise vol.Invalid("value must be a finite number") from exc
    if not math.isfinite(v):
        raise vol.Invalid("value must be a finite number")
    return v


def _datetime(value: Any) -> str:
    """Validate an ISO 8601 / RFC 3339 timestamp string."""
    if not isinstance(value, str):
        raise vol.Invalid("timestamp must be a string")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise vol.Invalid(f"invalid timestamp: {exc}") from exc
    return value


_POINT2D = vol.Schema(
    {vol.Required("x"): _finite_float, vol.Required("y"): _finite_float}
)
_POINT3D = vol.Schema(
    {
        vol.Required("x"): _finite_float,
        vol.Required("y"): _finite_float,
        vol.Required("z"): _finite_float,
    }
)

_CALIBRATION = vol.Schema(
    {
        vol.Optional("reference_entity"): str,
        vol.Required("real_world_distance"): vol.All(_finite_float, vol.Range(min=0, min_included=False)),
        vol.Required("measured_distance"): vol.All(_finite_float, vol.Range(min=0, min_included=False)),
    }
)

_ORIGIN = vol.Schema(
    {
        vol.Required("x"): _finite_float,
        vol.Required("y"): _finite_float,
    }
)

_ROOM = vol.Schema(
    {
        vol.Required("id"): vol.All(str, vol.Length(min=1)),
        vol.Required("name"): str,
        vol.Required("area_id"): vol.Any(None, str),
        vol.Required("floor_id"): vol.Any(None, str),
        vol.Required("floor_level"): int,
        vol.Required("polygon"): vol.All([_POINT2D], vol.Length(min=3)),
        vol.Required("height"): vol.All(_finite_float, vol.Range(min=0, min_included=False)),
        vol.Optional("origin"): _ORIGIN,
        vol.Optional("rotation"): _finite_float,
        vol.Optional("orphaned"): bool,
        vol.Optional("metadata"): dict,
    },
    # Forward tolerance (eng lock 2A/OV4): unknown room keys are preserved on a
    # validate->save round-trip so a newer build's fields survive a downgrade.
    extra=vol.ALLOW_EXTRA,
)

_PLACEMENT = vol.Schema(
    {
        vol.Required("entity_id"): vol.All(str, vol.Length(min=1)),
        vol.Required("room_id"): vol.Any(None, str),
        vol.Required("position"): _POINT3D,
        vol.Required("rotation"): _finite_float,
        vol.Required("mount_type"): vol.In(MOUNT_TYPES),
        vol.Optional("notes"): str,
    },
    extra=vol.ALLOW_EXTRA,  # forward tolerance, as above
)

LAYOUT_SCHEMA = vol.Schema(
    {
        vol.Required("id"): vol.All(str, vol.Length(min=1)),
        vol.Required("name"): str,
        # Forward tolerance (2A/OV4): accept any version >= 1. A newer build's
        # layout must load on this build; migrations still branch on the HA
        # Store major/minor version in spatial.py.
        vol.Required("version"): vol.All(int, vol.Range(min=1)),
        vol.Optional("calibration"): _CALIBRATION,
        vol.Required("rooms"): [_ROOM],
        vol.Required("placements"): [_PLACEMENT],
        vol.Required("created_at"): _datetime,
        vol.Required("updated_at"): _datetime,
    },
    extra=vol.ALLOW_EXTRA,  # forward tolerance, as above
)


def validate_layout_structure(layout: Any) -> dict:
    """Validate + coerce a layout's structure. Raises voluptuous.Invalid."""
    return LAYOUT_SCHEMA(layout)


class UnsupportedLayoutVersionError(vol.Invalid):
    """Raised when asked to WRITE a layout newer than this build understands.

    Forward-tolerant READING (schema accepts version >= 1), conservative
    WRITING (eng lock 2A/OV4): a downgraded build must not persist over a newer
    layout. Carries the typed error code ``unsupported_version`` so the WS
    boundary can return it verbatim.
    """

    def __init__(self, version: Any) -> None:
        super().__init__(
            f"this build is read-only because the stored layout is newer "
            f"(layout schema v{version} > known v{KNOWN_LAYOUT_VERSION}); "
            f"upgrade HA Spatial to edit it — do not hand-edit the store file"
        )
        self.code = "unsupported_version"
        self.version = version


def check_writable_version(layout: Any) -> None:
    """Raise UnsupportedLayoutVersionError if the layout is newer than KNOWN_LAYOUT_VERSION."""
    if not isinstance(layout, dict):
        return  # structural validation downstream reports the real problem
    version = layout.get("version")
    if isinstance(version, int) and not isinstance(version, bool) and version > KNOWN_LAYOUT_VERSION:
        raise UnsupportedLayoutVersionError(version)
