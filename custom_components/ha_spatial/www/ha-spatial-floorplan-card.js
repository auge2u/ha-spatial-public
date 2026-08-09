var P = Object.defineProperty;
var T = (t, n, o) => n in t ? P(t, n, { enumerable: !0, configurable: !0, writable: !0, value: o }) : t[n] = o;
var y = (t, n, o) => T(t, typeof n != "symbol" ? n + "" : n, o);
function S(t) {
  const n = t.origin ?? { x: 0, y: 0 }, o = (t.rotation ?? 0) * (Math.PI / 180), e = Math.cos(o), a = Math.sin(o);
  return t.polygon.map((s) => ({
    x: s.x * e - s.y * a + n.x,
    y: s.x * a + s.y * e + n.y
  }));
}
function k(t, n) {
  const o = n.origin ?? { x: 0, y: 0 }, e = (n.rotation ?? 0) * (Math.PI / 180), a = Math.cos(e), s = Math.sin(e), { x: r, y: c, z: i } = t.position;
  return {
    x: r * a - c * s + o.x,
    y: r * s + c * a + o.y,
    z: i
  };
}
const g = 1e-9;
function A(t) {
  if (t.rooms.length === 0) return 0;
  const n = /* @__PURE__ */ new Map();
  for (const a of t.rooms)
    n.set(a.floorLevel, (n.get(a.floorLevel) ?? 0) + 1);
  let o = 0, e = -1;
  for (const [a, s] of n)
    (s > e || s === e && a < o) && (e = s, o = a);
  return o;
}
function H(t, n) {
  const o = n ?? A(t);
  let e = 1 / 0, a = 1 / 0, s = -1 / 0, r = -1 / 0;
  for (const c of t.rooms)
    if (c.floorLevel === o)
      for (const i of S(c))
        i.x < e && (e = i.x), i.y < a && (a = i.y), i.x > s && (s = i.x), i.y > r && (r = i.y);
  return Number.isFinite(e) ? { minX: e, minY: a, maxX: s, maxY: r } : null;
}
const x = 5, N = 400, W = 40, v = 120, _ = 24;
function M(t) {
  if (t.length === 0) return null;
  let n = 1 / 0, o = 1 / 0, e = -1 / 0, a = -1 / 0;
  for (const s of t)
    s.x < n && (n = s.x), s.y < o && (o = s.y), s.x > e && (e = s.x), s.y > a && (a = s.y);
  return { minX: n, minY: o, maxX: e, maxY: a };
}
function B(t, n, o) {
  const e = [
    { x: t.minX, y: t.minY },
    { x: t.maxX, y: t.minY },
    { x: t.maxX, y: t.maxY },
    { x: t.minX, y: t.maxY }
  ];
  return Math.abs(n) < g ? M(e) : M(e.map((a) => E(a, n, o)));
}
function z(t, n, o, e, a = 0, s = { x: 0, y: 0 }) {
  const r = e + _, c = Math.max(n - 2 * r, 1), i = Math.max(o - 2 * r, 1), l = B(t, a, s), f = Math.max(l.maxX - l.minX, 1e-6), d = Math.max(l.maxY - l.minY, 1e-6), m = Math.min(c / f, i / d), $ = f > 0 ? v / f : x, F = d > 0 ? v / d : x, u = Math.max(x, Math.min(N, Math.max(m, $, F))), X = f * u, C = d * u, h = {
    scale: u,
    offset: {
      x: (n - X) / 2 - l.minX * u,
      y: (o - C) / 2 - l.minY * u
    }
  };
  return Math.abs(a) > g && (h.rotation = a, h.pivot = s), h;
}
function O(t, n, o, e = 24, a) {
  const s = H(t, a);
  return s === null || n <= 0 || o <= 0 ? { scale: W, offset: { x: e + _, y: e + _ } } : z(s, n, o, e, 0, { x: 0, y: 0 });
}
function E(t, n, o = { x: 0, y: 0 }) {
  const e = n * Math.PI / 180, a = Math.cos(e), s = Math.sin(e), r = t.x - o.x, c = t.y - o.y;
  return {
    x: a * r - s * c + o.x,
    y: s * r + a * c + o.y
  };
}
function Y(t, n) {
  const o = n.rotation ?? 0;
  if (Math.abs(o) < g)
    return {
      x: t.x * n.scale + n.offset.x,
      y: t.y * n.scale + n.offset.y
    };
  const e = n.pivot ?? { x: 0, y: 0 }, a = E(t, o, e);
  return {
    x: a.x * n.scale + n.offset.x,
    y: a.y * n.scale + n.offset.y
  };
}
function q(t, n) {
  return S(t).map((o) => {
    const e = Y(o, n);
    return `${e.x.toFixed(2)},${e.y.toFixed(2)}`;
  }).join(" ");
}
function w(t) {
  const n = {
    id: t.id,
    name: t.name,
    areaId: t.area_id,
    floorId: t.floor_id,
    floorLevel: t.floor_level,
    polygon: t.polygon.map((o) => ({ x: o.x, y: o.y })),
    height: t.height,
    orphaned: t.orphaned,
    metadata: t.metadata ? {
      ...t.metadata,
      wallThickness: t.metadata.wall_thickness ?? void 0,
      hasSlopedCeiling: t.metadata.has_sloped_ceiling ?? void 0
    } : void 0
  };
  return t.origin !== void 0 && (n.origin = { x: t.origin.x, y: t.origin.y }), t.rotation !== void 0 && (n.rotation = t.rotation), n;
}
function R(t) {
  return {
    entityId: t.entity_id,
    roomId: t.room_id,
    position: { x: t.position.x, y: t.position.y, z: t.position.z },
    rotation: t.rotation,
    mountType: t.mount_type,
    notes: t.notes
  };
}
function V(t) {
  return {
    id: t.id,
    name: t.name,
    version: t.version,
    calibration: t.calibration ? {
      referenceEntity: t.calibration.reference_entity,
      realWorldDistance: t.calibration.real_world_distance,
      measuredDistance: t.calibration.measured_distance
    } : void 0,
    rooms: t.rooms.map(w),
    entities: t.placements.map(R),
    createdAt: t.created_at,
    updatedAt: t.updated_at
  };
}
const I = 480, L = 360, b = `
  .wrap { padding: 8px 12px 12px; }
  svg { width: 100%; height: auto; display: block; background: #f8f9fa; border-radius: 12px; }
  .room { fill: rgba(16,185,129,0.10); stroke: #059669; stroke-width: 1.5; }
  .room.orphaned { fill: rgba(148,163,184,0.12); stroke: #94a3b8; stroke-dasharray: 4 3; }
  .dot { stroke: #ffffff; stroke-width: 1.5; }
  .dot.on { fill: #059669; }
  .dot.off { fill: #9ca3af; }
  .empty { padding: 24px; color: #6b7280; font-size: 14px; }
`;
function j(t) {
  return t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
class D extends HTMLElement {
  constructor() {
    super();
    y(this, "_config");
    y(this, "_hass");
    y(this, "_layout", null);
    y(this, "_requested", !1);
    y(this, "_root");
    this._root = this.attachShadow({ mode: "open" });
  }
  setConfig(o) {
    this._config = o, this._render();
  }
  set hass(o) {
    this._hass = o, !this._requested && o?.connection ? (this._requested = !0, this._loadLayout()) : this._render();
  }
  getCardSize() {
    return 6;
  }
  async _loadLayout() {
    try {
      const o = await this._hass.connection.sendMessagePromise({ type: "ha_spatial/layout/get" });
      this._layout = V(o);
    } catch {
      this._layout = null;
    }
    this._render();
  }
  _isActive(o) {
    const e = this._hass?.states?.[o]?.state;
    return e !== void 0 && e !== "off" && e !== "unavailable" && e !== "unknown";
  }
  _render() {
    const o = j(this._config?.title ?? "Floorplan");
    if (this._layout === null || this._layout.rooms.length === 0) {
      this._root.innerHTML = `<style>${b}</style><ha-card header="${o}"><div class="empty">No spatial layout yet.</div></ha-card>`;
      return;
    }
    const e = A(this._layout), a = O(this._layout, I, L, 16, e), s = this._layout.rooms.filter((i) => i.floorLevel === e).map((i) => `<polygon points="${q(i, a)}" class="room${i.orphaned ? " orphaned" : ""}"/>`).join(""), r = new Map(this._layout.rooms.map((i) => [i.id, i])), c = this._layout.entities.filter((i) => i.roomId ? r.get(i.roomId)?.floorLevel === e : !0).map((i) => {
      const l = i.roomId ? r.get(i.roomId) : void 0, f = l ? k(i, l) : i.position, d = Y({ x: f.x, y: f.y }, a), m = this._isActive(i.entityId) ? "on" : "off";
      return `<circle cx="${d.x.toFixed(1)}" cy="${d.y.toFixed(1)}" r="5" class="dot ${m}"/>`;
    }).join("");
    this._root.innerHTML = `<style>${b}</style><ha-card header="${o}"><div class="wrap"><svg viewBox="0 0 ${I} ${L}" preserveAspectRatio="xMidYMid meet">${s}${c}</svg></div></ha-card>`;
  }
}
customElements.get("ha-spatial-floorplan-card") || customElements.define("ha-spatial-floorplan-card", D);
const p = window;
p.customCards = p.customCards ?? [];
p.customCards.push({
  type: "ha-spatial-floorplan-card",
  name: "HA Spatial Floorplan",
  description: "Spatially accurate floorplan with live entity positions."
});
