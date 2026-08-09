"""Pure HA->spatial reconciliation (decisions 2A / 3A / T2).

No Home Assistant imports, so the ownership rules are unit-testable without the
HA harness. The registry adapter (registry_sync.py) snapshots the live
registries into plain maps and calls these functions.

Ownership model (2A): HA owns identity (room name, area/floor membership);
spatial owns geometry (polygon, placement positions, calibration). So this only
ever writes identity fields — never geometry.
"""
from __future__ import annotations

from typing import Iterable, Mapping


def resolve_effective_areas(
    entities: Iterable[tuple[str, str | None, str | None]],
    device_areas: Mapping[str, str | None],
) -> dict[str, str | None]:
    """Map entity_id -> effective HA area.

    Precedence (decision T2): the entity's own area_id wins; otherwise it
    inherits its device's area. This is the device-vs-entity precedence that an
    unspecified "bidirectional sync" would get wrong.
    """
    result: dict[str, str | None] = {}
    for entity_id, area_id, device_id in entities:
        if area_id is not None:
            result[entity_id] = area_id
        elif device_id is not None:
            result[entity_id] = device_areas.get(device_id)
        else:
            result[entity_id] = None
    return result


def reconcile_layout(
    layout: dict,
    *,
    area_ids: set[str],
    area_names: Mapping[str, str],
    area_floors: Mapping[str, str | None],
    floor_ids: set[str],
    entity_areas: Mapping[str, str | None],
) -> bool:
    """Apply HA identity state to the layout in place. Returns True if changed.

    - Linked room (area_id present and still exists): name + floor follow HA;
      an orphaned room is restored.
    - Linked room whose area was deleted: tombstoned (orphaned=True), geometry
      kept (decision 2A).
    - Room pointing at a deleted floor: floor_id cleared to null.
    - Placement: room_id follows the room linked to the entity's effective area
      (HA owns membership).
    """
    changed = False
    area_to_room: dict[str, str] = {}

    for room in layout.get("rooms", []):
        area_id = room.get("area_id")
        if area_id is None:
            continue
        if area_id in area_ids:
            if room.get("orphaned"):
                room["orphaned"] = False
                changed = True
            new_name = area_names.get(area_id)
            if new_name is not None and room.get("name") != new_name:
                room["name"] = new_name
                changed = True
            new_floor = area_floors.get(area_id)
            if room.get("floor_id") != new_floor:
                room["floor_id"] = new_floor
                changed = True
            area_to_room[area_id] = room["id"]
        else:
            if not room.get("orphaned"):
                room["orphaned"] = True
                changed = True

    for room in layout.get("rooms", []):
        floor_id = room.get("floor_id")
        if floor_id is not None and floor_id not in floor_ids:
            room["floor_id"] = None
            changed = True

    for placement in layout.get("placements", []):
        effective_area = entity_areas.get(placement["entity_id"])
        if effective_area is not None and effective_area in area_to_room:
            target_room = area_to_room[effective_area]
            if placement.get("room_id") != target_room:
                placement["room_id"] = target_room
                changed = True

    return changed
