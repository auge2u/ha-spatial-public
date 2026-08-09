"""Constants for the HA Spatial integration."""
from __future__ import annotations

import json
import os

DOMAIN = "ha_spatial"

# HA Store (decision 4A: versioned with a migration function from v1).
STORAGE_KEY = f"{DOMAIN}.layout"
STORAGE_VERSION = 1
STORAGE_MINOR_VERSION = 1
SAVE_DELAY = 2.0  # seconds; debounced disk writes (decision 12A)

# Sidebar panel (decision 1A: real panel registration, replacing add_extra_js_url).
PANEL_URL_PATH = "ha-spatial"
PANEL_WEBCOMPONENT = "ha-spatial-panel"
PANEL_STATIC_URL = "/ha_spatial_static"


def _manifest_version() -> str:
    manifest = os.path.join(os.path.dirname(__file__), "manifest.json")
    try:
        with open(manifest, encoding="utf-8") as f:
            return json.load(f).get("version", "dev")
    except Exception:
        return "dev"


PANEL_TITLE = "HA Spatial"
PANEL_ICON = "mdi:floor-plan"
PANEL_REQUIRE_ADMIN = True  # decision 6A: panel is admin-only in v0

# Allowed device mount types (mirrors layout.schema.json mount_type enum).
MOUNT_TYPES = ("floor", "wall", "ceiling")

# Funnel instrumentation (First Room PMF loop). Events live in a SEPARATE store
# (the layout schema is closed), are written immediately, and are capped.
EVENTS_STORAGE_KEY = f"{DOMAIN}.events"
EVENTS_STORAGE_VERSION = 1
EVENT_LOG_CAP = 500
FUNNEL_EVENTS = (
    "capture_started",
    "room_mapped",
    "roomplan_import_started",
    "roomplan_import_succeeded",
    "roomplan_import_failed",
    "suggestion_accepted",
    "second_room_started",
    "rooms_suggested",
    "room_suggestion_selected",
)

# Durable scenes (T3/D3): defs persisted in our own store and materialized as
# real HA scene entities by scene.py. We own every scene here — that is what
# makes scene/remove undo safe (Codex #8).
SCENES_STORAGE_KEY = f"{DOMAIN}.scenes"
SCENES_STORAGE_VERSION = 1

# Vision provider (D4/D9/Codex#7) — OFF the PMF critical path. Pluggable: the
# key stays server-side (D4); the provider is chosen via the options flow.
CONF_VISION_PROVIDER = "vision_provider"
CONF_VISION_API_KEY = "vision_api_key"
CONF_VISION_MODEL = "vision_model"
CONF_VISION_TIMEOUT = "vision_timeout"
VISION_PROVIDERS = ("simulated", "grok")
DEFAULT_VISION_PROVIDER = "simulated"
DEFAULT_VISION_MODEL = "grok-2-vision-latest"
DEFAULT_VISION_TIMEOUT = 30
