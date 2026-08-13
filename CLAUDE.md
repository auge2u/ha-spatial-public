# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

The **public distribution repo** for the HA Spatial Home Assistant custom integration
(HACS). Development happens in a private repo (`auge2u/ha-forge-vista`); this repo receives
mirrored release snapshots. Consequences that shape every task here:

- **There is no test suite, linter, or type-checker here** — and no source for the frontend.
  Don't invent `pytest`/`npm test` invocations; nothing backs them. The private repo has the
  harness (~170 tests) and the Vite build.
- **`custom_components/ha_spatial/www/*.js` are build artifacts.** Never hand-edit them.
- **`.github/workflows/release.yml` is itself mirrored** — its own header says to edit it in
  the private repo, because the next mirrored release overwrites it here.
- Practically: a fix made *only* in this repo gets clobbered by the next release mirror.
  Real changes belong upstream, then flow down. If you're asked to fix something here,
  say so and offer to port it.

### Release mechanics

Pushing a `v*` tag triggers `release.yml`, which:

1. **asserts `manifest.json`'s `version` equals the tag** (minus the `v`) — a mismatch fails
   the job, so the two move together or not at all;
2. packages two zips — `ha-spatial.zip` with the integration files at the **archive root**
   (HACS extracts it into `custom_components/ha_spatial/` itself, per `hacs.json`'s
   `zip_release`), and `ha-spatial-v<version>.zip` **nested under `custom_components/`** for
   manual extraction into an HA config dir;
3. creates the GitHub release with both attached.

`manifest.json` is the single source of truth for the version. `const.py` reads it **once at
import** into `MANIFEST_VERSION`; `_manifest_version()` returns that cached string.

## Verification without Home Assistant

Some modules are **deliberately HA-free** so they can be exercised without the HA test
harness — `geometry.py`, `reconcile.py`, `suggest.py` import with zero third-party deps;
`schema.py` and `roomplan_import.py` need only `voluptuous` (bundled with HA):

```bash
python3 -c "from custom_components.ha_spatial import geometry, reconcile, suggest"
python3 -m compileall -q custom_components/ha_spatial   # syntax check everything
```

Preserve that property. `__init__.py` defers **all** HA imports into the entry-lifecycle
functions specifically to keep those modules importable — don't hoist them to module scope.
Anything HA-dependent (`api.py`, `spatial.py`, `scene.py`, `update.py`, `panel.py`,
`registry_sync.py`, `events.py`, `scene_store.py`) can only really be verified in a live HA
instance, or by the upstream test suite.

## Architecture

### Layered by HA-dependence

```
api.py  panel.py  registry_sync.py  scene.py  update.py  events.py  scene_store.py  spatial.py   ← HA-bound
        ↓ delegate all logic to ↓
geometry.py  schema.py  reconcile.py  suggest.py  roomplan_import.py                             ← pure
```

The HA-bound layer snapshots live registries into plain dicts/maps and calls the pure layer.
New logic goes in the pure layer; keep the adapter thin.

### No blocking I/O on the event loop

HA's blocking-call detector will flag a bare `open()` during setup, and both known file reads
are already worked around — treat this as a rule, not trivia:

- `const.MANIFEST_VERSION` is read at **module import** (HA imports custom integrations in an
  executor thread, so the read is off-loop) and cached for every later caller — the update
  entity, `ha_spatial/info`, panel registration.
- `panel.py` reads `www/bundle-manifest.json` via `hass.async_add_executor_job(...)`.

Any new disk/network access in a setup path needs the same treatment.

### The layout is the whole domain model

One document — id, name, `rooms[]`, `placements[]`, `calibration?`, timestamps — persisted in
a versioned HA `Store`. Conventions that hold throughout:

- **All coordinates are real-world meters.** No pixels anywhere. `calibration` is a
  distance-pair (`real_world_distance` / `measured_distance`), never a pixel scale.
- **snake_case keys** in the persisted/wire layout (matches `area_id`/`entity_id`). Exception:
  the `VisionResult` from `vision_provider.py` is camelCase, matching an existing frontend
  contract.
- Room geometry is **room-local**; world space = `translate(rotate(polygon, rotation), origin)`
  (`geometry.resolve_polygon`). Placement positions are room-local too, resolved through the
  linked room's transform.
- `placements[]` is a **single global array**, each entry optionally linked via `room_id`.
  There is no room↔entity mapping table; `room.area_id` *is* the room↔area mapping.
- `floor_level` (integer storey index, for geometry/render offset) is distinct from `floor_id`
  (HA floor registry link). Both exist; don't conflate them.

### Contracts written twice — change both or neither

Three places encode a contract redundantly with something outside this file:

1. **`layout.schema.json`** (JSON Schema 2020-12, `additionalProperties: false`, also consumed
   by the TypeScript panel) and **`schema.py`** (voluptuous, the runtime validator) must accept
   and reject identically. voluptuous adds no dependency — it ships with HA.
2. **`geometry.cascade_offset`'s `_CASCADE_WRAP_W` (24.0 m)** must match `_CASCADE_WRAP_W` in
   the frontend's `floorplan-render.ts`. Rooms fill a shelf rightward, then wrap below —
   an unbounded row turned a many-room home into a ~100 m strip that shrank every room into
   unreadability at viewport fit.
3. **`const.MOUNT_TYPES`** mirrors the `mount_type` enum in `layout.schema.json`.

`schema.py` covers structure only. **Semantic** geometry checks live in `geometry.py`
(≥3 distinct points, finite coordinates, no self-intersection, height > 0) and run after
structural validation. `spatial.validate_layout()` composes both and is called on **every**
save — an invalid layout is never persisted.

The layout schema is frozen at v1. Bumping `version` requires a matching branch in
`_SpatialLayoutStore._async_migrate_func`.

### Ownership model (the rule that decides most sync questions)

**HA owns identity; HA Spatial owns geometry.** `reconcile.reconcile_layout()` writes identity
fields only (room name, `area_id`, `floor_id`, placement `room_id`) and never touches a
polygon, origin, rotation, position, or calibration value.

Corollaries encoded in `reconcile.py`:
- Deleted HA area → the room is **tombstoned** (`orphaned: True`), geometry retained,
  restorable if the area returns. Never deleted.
- Deleted floor → `floor_id` cleared to null.
- An entity's **effective area** = its own `area_id`, else its device's `area_id`
  (`resolve_effective_areas`). Used identically by reconciliation, `entities/by_area`, and
  `suggest.py` — keep it in one place.

The same layering holds the other way: `room/delete` removes the spatial room and its
placements but leaves the HA area alone — the spatial layer sits *over* the registry, it
doesn't own it.

### Three stores, three write policies

| Store | Key | Write policy | Why |
|---|---|---|---|
| Layout | `ha_spatial.layout` | debounced 2s (`SAVE_DELAY`) | high-frequency drag/edit traffic |
| Funnel events | `ha_spatial.events` | debounced 1s, capped at 500 | closed layout schema can't hold them; counts+timestamps only, no PII |
| Scenes | `ha_spatial.scenes` | immediate | must survive a crash to keep the "my home got smarter" payoff |

`async_unload_entry` explicitly flushes the layout and event stores (`async_save_now`) so a
reload never drops the last debounced edit.

### WebSocket API conventions (`api.py`)

All commands are `ha_spatial/...`, registered once per `hass` (guarded by an `api_registered`
flag, since registration is global rather than per-entry).

- **Reads** (`info`, `layout/get`, `validate`, `areas/list`, `entities/by_area`,
  `onboarding/suggest_rooms`, `event/funnel`) — any authenticated user. **Mutations** —
  `@websocket_api.require_admin`. The panel itself is admin-only (`PANEL_REQUIRE_ADMIN`).
- **Typed error codes, never silent coercion**: `invalid_polygon`, `self_intersecting`,
  `invalid_height`, `unknown_room`, `unknown_entity`, `unknown_area`, `unknown_floor`,
  `unknown_scene`, `stale_version`, `rate_limited`, `consent_required`, `not_loaded`.
  `GeometryError`, `RoomPlanImportError`, and `VisionProviderError` each carry a `.code`
  mapping onto this contract. New failure modes get a new code, not a best-effort fixup.
- **Optimistic concurrency**: mutations accept `expected_updated_at`; `_check_stale` rejects
  with `stale_version` if the layout moved on. Mutations `copy.deepcopy` the layout, edit the
  copy, then save — so a validation failure leaves live state untouched.
- **Rate limiting** is a per-WS-connection token bucket keyed by command, with one shared
  bucket for all mutations (`_RATE_LIMITS_CONFIG`).
- "Does this entity exist" is **registry OR state machine** (`_entity_exists`). YAML and
  template entities are real but have no registry entry, so a registry-only check is wrong.
- `room/create` writes the room *and* its placements in one validated save — deliberately
  atomic, no two-step race.
- `ha_spatial/info` is the version-truth surface: installed version, latest release, and
  `update_available`. The panel also compares its own baked bundle version against `version`
  to detect a **stale browser tab** after an upgrade.

### Platforms: SCENE and UPDATE

`async_setup_entry` forwards both, and ordering matters — entry data must be in `hass.data`
*before* the forward, because `scene.py` reads `scene_store` and `update.py` stashes its
`release_coordinator` back into the same dict.

**Scenes.** `scene_store.py` holds definitions
(`{id, name, entities: [{entity_id, state, attributes}]}`); `scene.py` materializes them as
real `scene.*` entities through the documented scene-platform API (never by poking core
`scene` internals) so they survive restarts and work in automations. `SceneManager` adds and
removes entities after platform setup. Removal is **provenance-gated**: `scene/remove` only
deletes ids present in our store, so undo can never destroy a same-named scene the user
authored elsewhere — and it goes through the entity registry, because `entity.async_remove()`
alone leaves a registry-backed entity's state behind.

**Update entity.** `update.py` polls `api.github.com` for this repo's latest release every
12 h — a deliberate, documented egress that exists because HACS's cached release scan has
served day-old "latest" versions. It only *reports*; installation stays with HACS. It must
tolerate an offline first refresh (reporting unavailable) so an air-gapped HA still sets up.

### Privacy and vision providers

`vision_provider.py` runs vision calls **server-side** so the API key never reaches the
browser; the provider is chosen through the options flow (`simulated` — no network at all,
the default — or `grok` via x.ai). Adding a provider is one async function plus a `PROVIDERS`
entry.

The privacy contract in `ws_analyze_vision` is load-bearing: any non-`simulated` provider
requires explicit per-call `consent`, else `consent_required`. Photos are validated as base64
data URLs, JPEG/PNG only, ≤6 photos, ≤2 MB decoded each; RoomPlan payloads cap at 5 MB. Don't
relax these silently.

### Frontend surfaces

- **Panel**: registered via `panel_custom` at `/ha-spatial`, assets under `/ha_spatial_static`.
  The bundle filename is **content-hashed** and resolved at runtime from
  `www/bundle-manifest.json` (`{"panel": "..."}`), falling back to `ha-spatial-panel.js`.
  A new bundle means a new manifest entry.
- **Lovelace card**: `www/ha-spatial-floorplan-card.js` is served statically but *not*
  registered by any Python code — users add it as a dashboard resource manually.

## Style notes observed in this codebase

- Docstrings reference the design decisions they implement (`decision 8A`, `T2`, `D9`,
  `Codex #5`). Keep those references intact when editing — they're the trail back to the
  private repo's design record (`docs/`, which is not mirrored here).
- Comments tend to record *why*, often naming the failure that motivated the code (the
  blocking-read detector, the ~100 m strip, the day-old HACS "latest"). Match that when
  adding code.
- `from __future__ import annotations` everywhere; HA types imported under `TYPE_CHECKING`
  and quoted in signatures.
