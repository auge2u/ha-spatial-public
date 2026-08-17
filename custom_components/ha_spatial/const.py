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

# Forward tolerance (eng lock 2A/OV4): the schema READS any integer version >= 1,
# but this build WRITES only what it understands. Saving a layout whose version
# exceeds KNOWN_LAYOUT_VERSION fails with typed error `unsupported_version`.
KNOWN_LAYOUT_VERSION = 1

# Layout revision ring (eng lock 1A/OV2/OV3): a SEPARATE store holding pre-edit
# layout snapshots so a bug cannot wipe out the model. Ring writes happen
# synchronously before the layout debounce proceeds.
REVISIONS_STORAGE_KEY = f"{DOMAIN}.layout_revisions"
REVISIONS_STORAGE_VERSION = 1
REVISIONS_STORAGE_MINOR_VERSION = 1
REVISION_RING_CAP = 20
REVISION_RING_MAX_BYTES = 2 * 1024 * 1024  # 2 MB serialized budget
REVISION_COALESCE_SECONDS = 60.0  # one revision per editing burst

# Sidebar panel (decision 1A: real panel registration, replacing add_extra_js_url).
PANEL_URL_PATH = "ha-spatial"
PANEL_WEBCOMPONENT = "ha-spatial-panel"
PANEL_STATIC_URL = "/ha_spatial_static"


def _read_manifest_version() -> str:
    manifest = os.path.join(os.path.dirname(__file__), "manifest.json")
    try:
        with open(manifest, encoding="utf-8") as f:
            return json.load(f).get("version", "dev")
    except Exception:
        return "dev"


# Read ONCE at module import. HA imports custom integrations in an executor
# thread, so this file read happens off the event loop; every later caller
# (update entity, ha_spatial/info, panel registration) gets the cached string
# with no I/O. Reading it lazily instead trips HA's blocking-call detector.
MANIFEST_VERSION = _read_manifest_version()


def _manifest_version() -> str:
    """The integration version from manifest.json (cached at import)."""
    return MANIFEST_VERSION


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
    "layout_restored",
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
