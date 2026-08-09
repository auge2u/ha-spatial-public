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

from .const import MOUNT_TYPES


def _finite_float(value: Any) -> float:
    """Coerce to float and reject NaN / Infinity."""
    v = float(value)
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
    }
)

_PLACEMENT = vol.Schema(
    {
        vol.Required("entity_id"): vol.All(str, vol.Length(min=1)),
        vol.Required("room_id"): vol.Any(None, str),
        vol.Required("position"): _POINT3D,
        vol.Required("rotation"): _finite_float,
        vol.Required("mount_type"): vol.In(MOUNT_TYPES),
        vol.Optional("notes"): str,
    }
)

LAYOUT_SCHEMA = vol.Schema(
    {
        vol.Required("id"): vol.All(str, vol.Length(min=1)),
        vol.Required("name"): str,
        vol.Required("version"): 1,
        vol.Optional("calibration"): _CALIBRATION,
        vol.Required("rooms"): [_ROOM],
        vol.Required("placements"): [_PLACEMENT],
        vol.Required("created_at"): _datetime,
        vol.Required("updated_at"): _datetime,
    }
)


def validate_layout_structure(layout: Any) -> dict:
    """Validate + coerce a layout's structure. Raises voluptuous.Invalid."""
    return LAYOUT_SCHEMA(layout)
