"""Pure heuristics for suggesting rooms from existing Home Assistant data."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .reconcile import resolve_effective_areas


# Minimum token length for a pattern-suggestion name. Two-letter tokens like
# 'sm' produce noisy, ambiguous suggestions (e.g. Sim / Sm / Smart), so we
# require at least three characters.
_MIN_TOKEN_LENGTH = 3

# Tokens that are clearly not room names.
_IGNORED_TOKENS = {
    "sensor", "switch", "light", "climate", "fan", "cover", "lock", "binary",
    "device", "tracker", "automation", "script", "scene", "input", "helper",
    "group", "zone", "weather", "sun", "moon", "update", "persistent",
    "notification", "homeassistant", "default", "config", "ui", "lovelace",
    "esphome", "mqtt", "zigbee", "zwave", "hue", "tuya", "shelly", "sonoff",
    "template", "integration", "min", "max", "avg", "total", "count", "status",
    "power", "energy", "voltage", "current", "temperature", "humidity",
    "motion", "occupancy", "contact", "door", "window", "smoke", "leak",
    "battery", "wifi", "signal", "rssi", "linkquality", "lqi",
    # Structural / positional descriptors (not room names).
    "ceiling", "wall", "floor", "level", "main", "master", "upper", "lower",
    "front", "back", "left", "right", "north", "south", "east", "west",
    # Storey names. These identify a floor, not a room, and belong with
    # upper/lower above (vacuum.demo_vacuum_0_ground_floor -> "Ground").
    "ground", "first", "second", "third", "fourth", "fifth", "storey", "story",
    # HA state/attribute words that leak into entity names.
    "color", "brightness", "speed", "mode", "state", "value", "reading",
    "alarm", "tamper", "water", "gas", "heat", "cold", "index", "number",
    "channel", "volume", "source", "media", "player", "receiver", "remote",
    "usb", "bluetooth", "thread", "mesh", "node", "bridge", "hub", "dongle",
    # Whole-house, never a single room. Earns its place because `home` DOES
    # ride on placed entities and so survives the structural filter below:
    # light.home_office_desk would otherwise suggest both "Home" and "Office".
    "home",
    # Bare "room" is not a room name. `<word>_room` is merged into one token by
    # _entity_tokens, so this only ever rejects a dangling one.
    "room",
    # HA domain names. A token equal to a domain is a device category by
    # construction — vacuum.demo_vacuum_0_ground_floor offered "Vacuum" as a
    # room. Domains already covered above (light, switch, sensor, ...) are not
    # repeated. Plurals are handled by _singularize, so these stay singular.
    "vacuum", "camera", "valve", "siren", "humidifier", "heater", "button",
    "event", "calendar", "image", "select", "date", "datetime", "counter",
    "todo", "conversation", "person", "assist", "notify", "backup", "tts",
    "stt", "mower", "text", "time",
    # Platform / demo scaffolding that ships with test and showcase setups.
    "demo", "example", "mock", "test", "sample", "dummy",
    # Energy and solar plumbing. Not places.
    "solar", "grid", "inverter", "meter", "consumption", "production",
    "tariff", "compensation", "percentage", "limited", "preset", "only",
    # Sun / almanac state words (binary_sensor.sun_solar_rising offered
    # "Rising"). Same family as the state words above.
    "rising", "falling", "setting", "dawn", "dusk", "noon", "midnight",
    "above", "below", "horizon", "azimuth", "elevation",
}

# Domains whose entities are physically installed somewhere in the home. A
# pattern token only names a room if it appears on at least one of these
# (_has_placed_entity).
#
# This is the structural half of the filter, and it does the work a token
# blocklist cannot: a stock HA ships sensor.backup_last_*_automatic_backup,
# event.backup_automatic_backup, conversation.home_assistant, zone.home,
# person.*, tts.* and update.ha_spatial_update, which between them offered
# "Backup", "Automatic", "Last", "Home" and "Spatial" as rooms on a first-run
# install. None of them is placed anywhere, so none survives this test.
#
# `sensor` and `binary_sensor` are deliberately absent: both carry real room
# telemetry AND a flood of device-attached bookkeeping, so neither can
# discriminate. binary_sensor is the sharper trap of the two — the HA companion
# app creates binary_sensor.<device>_focus and friends, so including it let
# "Iphone" through as a room on any install with an iPhone paired, defeating the
# device_tracker exclusion below. Fixtures worth naming a room after (lights,
# switches, covers, climate, media players, ...) are never binary_sensors.
#
# The cost is that a room evidenced ONLY by sensors is not suggested. It is
# still reachable by assigning an HA area, which outranks every pattern guess
# anyway.
#
# Excluding `device_tracker` settles the 'iphone' problem noted in
# _pattern_confidence: phones and wearables move with their owner, so they
# never evidence a room.
_PLACED_DOMAINS = frozenset({
    "light", "switch", "climate", "cover", "fan",
    "media_player", "vacuum", "lock", "camera", "humidifier", "water_heater",
    "valve", "siren", "lawn_mower",
})


def _has_placed_entity(entity_ids: set[str]) -> bool:
    """True if any entity id belongs to a physically-placed domain."""
    return any(e.split(".", 1)[0] in _PLACED_DOMAINS for e in entity_ids)

# Area names that are typically NOT rooms. An area with one of these names
# (case-insensitive substring) is excluded from room suggestions. Conservative:
# "garage" and "office" are rooms, so they are NOT here.
_NON_ROOM_AREA_NAMES = {
    "outdoor", "outside", "exterior", "garden", "yard", "lawn", "patio",
    "deck", "balcony" , "terrace", "rooftop", "roof", "driveway", "parking",
    "carport", "pool", "pond", "fountain", "shed", "greenhouse",
    "network", "server", "rack", " closet", "equipment", "utility",
    "technical", "electrical", "mechanical",
}

# The same vocabulary as exact tokens, for _is_room_token. _NON_ROOM_AREA_NAMES
# is matched as a substring against area names (hence the leading space on
# " closet"), so it is stripped here for exact token comparison.
_NON_ROOM_TOKENS = frozenset(name.strip() for name in _NON_ROOM_AREA_NAMES)


def _normalize_name(raw: str) -> str:
    """Turn a token into a displayable room name."""
    return raw.replace("_", " ").replace("-", " ").strip().title()


def _area_confidence(entity_count: int) -> tuple[str, str]:
    """Confidence + human reason for an area-based suggestion."""
    if entity_count >= 5:
        return ("high", f"{entity_count} devices already assigned to this area")
    if entity_count >= 2:
        return ("medium", f"{entity_count} devices already assigned to this area")
    return ("low", "Only one device assigned to this area")


def _pattern_confidence(token: str, entity_count: int) -> tuple[str, str]:
    """Confidence + human reason for an entity-pattern suggestion.

    Pattern guesses never exceed 'medium': they are inferred from entity-name
    tokens, not real HA areas, so a high-frequency token like 'iphone' must not
    be presented as a high-confidence room. Area suggestions (which can be
    'high') always sort above patterns at the same tier — see suggest_rooms.
    """
    if entity_count >= 2:
        return ("medium", f"{entity_count} entity names mention '{token}'")
    return ("low", f"Only {entity_count} entity names mention '{token}'")


def _entity_tokens(entity_id: str) -> list[str]:
    """Extract candidate room-name tokens from an entity id.

    light.kitchen_ceiling -> ['kitchen', 'ceiling']
    light.living_room_lamp -> ['living_room', 'lamp']

    A token immediately followed by "room" merges with it, so the single most
    common shape of English room name survives tokenization. Splitting them
    yielded two bogus rooms, "Living" and "Room" (observed with the demo
    integration on 0.8.12) — never the one the user actually has.
    """
    parts = entity_id.split(".")
    if len(parts) < 2:
        return []
    raw = [t.lower() for t in re.split(r"[_.-]", parts[1]) if len(t) > 1]
    tokens: list[str] = []
    i = 0
    while i < len(raw):
        if i + 1 < len(raw) and raw[i + 1] == "room" and raw[i] != "room":
            tokens.append(f"{raw[i]}_room")
            i += 2
            continue
        tokens.append(raw[i])
        i += 1
    return tokens


def _singularize(token: str) -> str:
    """Best-effort English singular, so a plural inherits its singular's verdict.

    The blocklist held "light" but not "lights", and light.kitchen_lights /
    light.ceiling_lights are ubiquitous — enough to offer "Lights" as a room.
    Checking both forms keeps the list singular-only instead of doubling it.
    """
    if token.endswith("ies") and len(token) > 4:
        return f"{token[:-3]}y"
    if token.endswith(("ses", "xes", "ches", "shes")):
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _blocked(word: str) -> bool:
    """True if a word is rejected by either vocabulary, in singular or plural."""
    return any(
        candidate in _IGNORED_TOKENS or candidate in _NON_ROOM_TOKENS
        for candidate in (word, _singularize(word))
    )


def _is_room_token(token: str) -> bool:
    """A token is a plausible room name if it is not a generic device/sensor word.

    Also rejects the non-room vocabulary used for area names: if "garden" is not
    a room when HA calls an area that, it is not a room when it appears in an
    entity id either (valve.back_garden / valve.front_garden offered "Garden").

    A merged "<head>_room" token is only as good as its head. The trailing
    "room" is structural — checking the merged token as a whole matched neither
    vocabulary, so merging smuggled "Demo Room", "Server Room" and "Backup Room"
    past both blocklists even though demo/server/backup are in them.
    """
    if len(token) < _MIN_TOKEN_LENGTH:
        return False
    if _blocked(token):
        return False
    head, sep, tail = token.rpartition("_")
    if sep and tail == "room" and _blocked(head):
        return False
    return True


# Cap pattern guesses so the onboarding UI doesn't drown in low-quality
# entity-token heuristics. Real HA area suggestions are not capped.
_MAX_PATTERN_SUGGESTIONS = 6


def suggest_rooms(
    area_entries: list[dict[str, Any]],
    entity_entries: list[dict[str, Any]],
    device_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return room suggestions inferred from HA registry data.

    :param area_entries: list of {id, name, floor_id}
    :param entity_entries: list of {entity_id, area_id, device_id}
    :param device_entries: list of {id, area_id}
    :return: sorted suggestions list
    """
    # Effective area for every entity.
    device_areas = {d["id"]: d.get("area_id") for d in device_entries}
    entities = [(e["entity_id"], e.get("area_id"), e.get("device_id")) for e in entity_entries]
    effective = resolve_effective_areas(entities, device_areas)

    area_by_id = {a["id"]: a for a in area_entries}

    # 1. Area-based suggestions (skip areas whose names are clearly not rooms).
    area_suggestions: dict[str, dict[str, Any]] = {}
    for area_id, area in area_by_id.items():
        area_name_lower = area["name"].lower()
        if any(bad in area_name_lower for bad in _NON_ROOM_AREA_NAMES):
            continue
        area_entities = sorted(eid for eid, eff_area in effective.items() if eff_area == area_id)
        if not area_entities:
            continue
        confidence, reason = _area_confidence(len(area_entities))
        area_suggestions[area_id] = {
            "name": area["name"],
            "area_id": area_id,
            "floor_id": area.get("floor_id"),
            "entity_ids": area_entities,
            "confidence": confidence,
            "reason": reason,
            "source": "area",
        }

    # Track entity ids already covered by an area suggestion.
    covered = {eid for s in area_suggestions.values() for eid in s["entity_ids"]}

    # 2. Entity-pattern suggestions for uncovered entities.
    token_entities: dict[str, set[str]] = defaultdict(set)
    for entity_id, eff_area in effective.items():
        if entity_id in covered:
            continue
        for token in _entity_tokens(entity_id):
            if _is_room_token(token):
                token_entities[token].add(entity_id)

    # Drop tokens that are substrings of a larger token covering the same set of
    # entities, e.g. 'sm' when 'smart' covers the same entities.
    kept_tokens: dict[str, set[str]] = {}
    sorted_tokens = sorted(token_entities.items(), key=lambda kv: (-len(kv[0]), kv[0]))
    for token, entity_ids in sorted_tokens:
        if len(entity_ids) < 2:
            continue
        # A token only evidences a room if something physically installed
        # carries it. Bookkeeping entities (backup sensors, the conversation
        # agent, persons, this integration's own update entity) never do.
        if not _has_placed_entity(entity_ids):
            continue
        if any(token != kept and token in kept and entity_ids <= kept_entities
               for kept, kept_entities in kept_tokens.items()):
            continue
        kept_tokens[token] = entity_ids

    # Avoid suggesting a name identical to an existing area suggestion.
    area_names_lower = {s["name"].lower() for s in area_suggestions.values()}

    pattern_suggestions: list[dict[str, Any]] = []
    for token, entity_ids in sorted(
        kept_tokens.items(),
        key=lambda kv: (-len(kv[1]), kv[0].lower()),
    ):
        display = _normalize_name(token)
        if display.lower() in area_names_lower:
            continue
        confidence, reason = _pattern_confidence(token, len(entity_ids))
        pattern_suggestions.append({
            "name": display,
            "area_id": None,
            "floor_id": None,
            "entity_ids": sorted(entity_ids),
            "confidence": confidence,
            "reason": reason,
            "source": "entity_pattern",
        })
        if len(pattern_suggestions) >= _MAX_PATTERN_SUGGESTIONS:
            break

    # Combine and sort. Pattern guesses are capped above, but real HA area
    # suggestions are always preserved — a home with many populated areas should
    # still see all of them in onboarding. Sort prefers higher confidence, then
    # real areas over inferred patterns (a 45-entity area beats a 64-entity
    # 'iphone' token), then entity count, then name.
    all_suggestions = list(area_suggestions.values()) + pattern_suggestions
    confidence_order = {"high": 0, "medium": 1, "low": 2}
    source_order = {"area": 0, "entity_pattern": 1}
    all_suggestions.sort(
        key=lambda s: (
            confidence_order.get(s["confidence"], 99),
            source_order.get(s["source"], 99),
            -len(s["entity_ids"]),
            s["name"].lower(),
        )
    )
    return all_suggestions
