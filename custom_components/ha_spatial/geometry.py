"""Runtime geometry validation (decision 8A).

Pure module — no Home Assistant imports — so it can be unit-tested without the
HA test harness. Rejects degenerate or self-intersecting room polygons rather
than silently storing garbage geometry (the failure mode that would poison the
accuracy harness). Coordinates are real-world meters.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

Point2D = Mapping[str, float]

_EPS = 1e-9
_CASCADE_GAP = 1.0  # meters between auto-offset rooms


class GeometryError(ValueError):
    """A geometry validation failure, carrying a stable error code.

    The code maps to the typed WS error contract (decision 8A): invalid_polygon,
    self_intersecting, invalid_height.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def polygon_area(points: Sequence[Point2D]) -> float:
    """Shoelace area (m^2). 0 for degenerate input."""
    n = len(points)
    if n < 3:
        return 0.0
    acc = 0.0
    for i in range(n):
        j = (i + 1) % n
        acc += points[i]["x"] * points[j]["y"]
        acc -= points[j]["x"] * points[i]["y"]
    return abs(acc) / 2.0


def wall_lengths(points: Sequence[Point2D]) -> list[float]:
    """Length (m) of each edge, treating the ring as closed."""
    n = len(points)
    return [
        math.hypot(points[(i + 1) % n]["x"] - points[i]["x"], points[(i + 1) % n]["y"] - points[i]["y"])
        for i in range(n)
    ]


def normalize_polygon(points: Sequence[Point2D]) -> list[dict[str, float]]:
    """Closed-ring normalization (decision 8A).

    Drops an explicit closing vertex (last == first) and collapses consecutive
    duplicate vertices, so callers may send either open or explicitly-closed
    rings.
    """
    pts = [dict(p) for p in points]
    if len(pts) >= 2 and abs(pts[0]["x"] - pts[-1]["x"]) < _EPS and abs(pts[0]["y"] - pts[-1]["y"]) < _EPS:
        pts = pts[:-1]
    out: list[dict[str, float]] = []
    for p in pts:
        if not out or abs(out[-1]["x"] - p["x"]) >= _EPS or abs(out[-1]["y"] - p["y"]) >= _EPS:
            out.append(p)
    return out


def _orientation(a: Point2D, b: Point2D, c: Point2D) -> int:
    """0 = collinear, 1 = clockwise, 2 = counter-clockwise."""
    val = (b["y"] - a["y"]) * (c["x"] - b["x"]) - (b["x"] - a["x"]) * (c["y"] - b["y"])
    if abs(val) < _EPS:
        return 0
    return 1 if val > 0 else 2


def _on_segment(a: Point2D, b: Point2D, c: Point2D) -> bool:
    """Is c (collinear with a-b) on segment ab?"""
    return (
        min(a["x"], b["x"]) - _EPS <= c["x"] <= max(a["x"], b["x"]) + _EPS
        and min(a["y"], b["y"]) - _EPS <= c["y"] <= max(a["y"], b["y"]) + _EPS
    )


def _segments_intersect(p1: Point2D, p2: Point2D, p3: Point2D, p4: Point2D) -> bool:
    d1, d2 = _orientation(p3, p4, p1), _orientation(p3, p4, p2)
    d3, d4 = _orientation(p1, p2, p3), _orientation(p1, p2, p4)
    if ((d1 == 1 and d2 == 2) or (d1 == 2 and d2 == 1)) and ((d3 == 1 and d4 == 2) or (d3 == 2 and d4 == 1)):
        return True
    if d1 == 0 and _on_segment(p3, p4, p1):
        return True
    if d2 == 0 and _on_segment(p3, p4, p2):
        return True
    if d3 == 0 and _on_segment(p1, p2, p3):
        return True
    if d4 == 0 and _on_segment(p1, p2, p4):
        return True
    return False


def has_self_intersection(points: Sequence[Point2D]) -> bool:
    """True if any pair of non-adjacent edges of the closed ring cross."""
    n = len(points)
    if n < 4:
        return False
    edges = [(points[i], points[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1:
                continue  # adjacent edges share a vertex
            if i == 0 and j == n - 1:
                continue  # wrap-around adjacency
            a, b = edges[i]
            c, d = edges[j]
            if _segments_intersect(a, b, c, d):
                return True
    return False


def validate_room_polygon(points: Sequence[Point2D]) -> list[dict[str, float]]:
    """Validate + normalize a room polygon. Raises GeometryError on failure."""
    pts = normalize_polygon(points)
    if len(pts) < 3:
        raise GeometryError("invalid_polygon", "polygon needs at least 3 distinct points")
    for p in pts:
        if not (math.isfinite(p["x"]) and math.isfinite(p["y"])):
            raise GeometryError("invalid_polygon", "polygon has a non-finite coordinate")
    if has_self_intersection(pts):
        raise GeometryError("self_intersecting", "polygon edges self-intersect")
    return pts


def resolve_polygon(
    polygon: Sequence[Point2D],
    origin: Point2D | None = None,
    rotation: float = 0.0,
) -> list[dict[str, float]]:
    """Return the world-space polygon from a room-local polygon + transform.

    World = translate(rotate(local, rotation), origin). Absent origin or zero
    rotation = identity, so legacy rooms without transforms render unchanged.
    """
    angle_rad = math.radians(rotation)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    ox = origin["x"] if origin else 0.0
    oy = origin["y"] if origin else 0.0
    return [
        {
            "x": p["x"] * cos_a - p["y"] * sin_a + ox,
            "y": p["x"] * sin_a + p["y"] * cos_a + oy,
        }
        for p in polygon
    ]


def polygon_bounds(
    polygon: Sequence[Point2D],
    origin: Point2D | None = None,
    rotation: float = 0.0,
) -> dict[str, float]:
    """Axis-aligned bounds of a transformed polygon."""
    world = resolve_polygon(polygon, origin, rotation)
    xs = [p["x"] for p in world]
    ys = [p["y"] for p in world]
    return {"min_x": min(xs), "max_x": max(xs), "min_y": min(ys), "max_y": max(ys)}


def cascade_offset(
    new_polygon: Sequence[Point2D],
    existing_rooms: Sequence[Mapping[str, Any]],
    gap: float = _CASCADE_GAP,
) -> dict[str, float]:
    """Compute an origin that places a new room to the right of existing rooms.

    Uses the axis-aligned bounds of the existing same-floor rooms and adds a
    horizontal gap. Floor scoping is the caller's responsibility; this helper
    sees only the rooms passed to it.
    """
    if not existing_rooms:
        return {"x": 0.0, "y": 0.0}
    max_x = max(
        polygon_bounds(
            r["polygon"], r.get("origin"), r.get("rotation", 0.0)
        )["max_x"]
        for r in existing_rooms
    )
    new_local = polygon_bounds(new_polygon)
    return {"x": max_x + gap - new_local["min_x"], "y": 0.0}


def validate_layout_geometry(layout: Mapping) -> None:
    """Semantic geometry checks across a whole layout. Raises GeometryError."""
    for room in layout.get("rooms", []):
        if room["height"] <= 0:
            raise GeometryError("invalid_height", f"room {room['id']} height must be > 0")
        validate_room_polygon(room["polygon"])
