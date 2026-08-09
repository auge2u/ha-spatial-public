"""Pure RoomPlan import validation (Python side of forge_roomplan_import v1).

Mirrors the contract in docs/roomplan-import-format.md and the TypeScript
importer at prototype/spatial-config/src/lib/capture/roomplan-import.ts.
This module has no Home Assistant imports so the lean test harness can exercise it.
"""
from __future__ import annotations

import math
from typing import Any

import voluptuous as vol

from .geometry import GeometryError, polygon_area, validate_room_polygon


class RoomPlanImportError(Exception):
    """A RoomPlan import failure with a stable, UI-mappable error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# Owned format version. Bump only on breaking changes.
_FORGE_ROOMPLAN_IMPORT_VERSION = 1

_MIN_AREA_M2 = 1.0
_MAX_AREA_M2 = 1000.0

def _point(value: Any) -> list[float]:
    """Validate a [x, y] point with exactly two floats."""
    if not isinstance(value, list) or len(value) != 2:
        raise vol.Invalid("expected [x, y]")
    return [float(value[0]), float(value[1])]


_ROOM_SCHEMA = vol.Schema(
    {
        vol.Optional("name", default=""): vol.All(str, vol.Length(max=120)),
        vol.Required("polygon_m"): vol.All(
            list,
            vol.Length(min=3),
            [_point],
        ),
        vol.Required("ceiling_height_m"): vol.All(
            vol.Coerce(float), vol.Range(min=0.01, max=50.0)
        ),
        vol.Optional("confidence"): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
    },
    extra=vol.ALLOW_EXTRA,
)

_PAYLOAD_SCHEMA = vol.Schema(
    {
        vol.Required("forge_roomplan_import"): _FORGE_ROOMPLAN_IMPORT_VERSION,
        vol.Required("source"): "roomplan",
        vol.Optional("captured_at"): str,
        vol.Optional("exporter_version"): str,
        vol.Required("room"): _ROOM_SCHEMA,
    },
    extra=vol.ALLOW_EXTRA,
)


def _polygon_to_points(polygon_m: list[list[float]]) -> list[dict[str, float]]:
    return [{"x": p[0], "y": p[1]} for p in polygon_m]


def parse_roomplan_import(payload: Any) -> dict[str, Any]:
    """Validate a forge_roomplan_import v1 payload and return a normalized room dict.

    The returned dict has:
      - name: str
      - polygon: list[{"x": float, "y": float}] (normalized, meters)
      - height: float (meters)
      - source: "roomplan"
      - captured_at: str | None
      - exporter_version: str | None
      - confidence: float | None

    Raises RoomPlanImportError with one of these codes:
      - malformed
      - unsupported_version
      - non_finite
      - too_few_points
      - implausible_scale
      - self_intersecting
    """
    # 1. Structural schema validation.
    try:
        data = _PAYLOAD_SCHEMA(payload)
    except vol.Invalid as exc:
        path = " -> ".join(str(p) for p in exc.path) if exc.path else "payload"
        # Distinguish a version mismatch from general malformed data.
        if "forge_roomplan_import" in str(exc.path):
            try:
                version = payload.get("forge_roomplan_import") if isinstance(payload, dict) else None
            except Exception:
                version = None
            if version is not None and version != _FORGE_ROOMPLAN_IMPORT_VERSION:
                raise RoomPlanImportError(
                    "unsupported_version",
                    f"Scan file uses version {version}; this app supports version {_FORGE_ROOMPLAN_IMPORT_VERSION}.",
                )
        raise RoomPlanImportError("malformed", f"Couldn't read this scan file ({path}).")

    room_data = data["room"]
    points = _polygon_to_points(room_data["polygon_m"])

    # 2. Finite coordinate check.
    for p in points:
        if not (math.isfinite(p["x"]) and math.isfinite(p["y"])):
            raise RoomPlanImportError("non_finite", "This scan has invalid measurements.")

    # 3. Authoritative polygon validation (distinct points, self-intersection).
    try:
        normalized = validate_room_polygon(points)
    except GeometryError as exc:
        if exc.code == "self_intersecting":
            raise RoomPlanImportError("self_intersecting", "This room outline crosses itself.")
        # All other geometry errors at this point mean too few usable points.
        raise RoomPlanImportError("too_few_points", "Couldn't form a room outline from this scan.")

    # 4. Area plausibility check.
    area = polygon_area(normalized)
    if not (_MIN_AREA_M2 <= area <= _MAX_AREA_M2):
        raise RoomPlanImportError(
            "implausible_scale",
            "This scan's measurements look wrong (check units).",
        )

    return {
        "name": room_data["name"].strip() or "Scanned room",
        "polygon": normalized,
        "height": room_data["ceiling_height_m"],
        "source": "roomplan",
        "captured_at": data.get("captured_at"),
        "exporter_version": data.get("exporter_version"),
        "confidence": room_data.get("confidence"),
    }
