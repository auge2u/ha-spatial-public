var k = Object.defineProperty;
var N = (t, n, o) => n in t ? k(t, n, { enumerable: !0, configurable: !0, writable: !0, value: o }) : t[n] = o;
var u = (t, n, o) => N(t, typeof n != "symbol" ? n + "" : n, o);
function I(t) {
  const n = t.origin ?? { x: 0, y: 0 }, o = (t.rotation ?? 0) * (Math.PI / 180), e = Math.cos(o), s = Math.sin(o);
  return t.polygon.map((a) => ({
    x: a.x * e - a.y * s + n.x,
    y: a.x * s + a.y * e + n.y
  }));
}
function H(t, n) {
  const o = n.origin ?? { x: 0, y: 0 }, e = (n.rotation ?? 0) * (Math.PI / 180), s = Math.cos(e), a = Math.sin(e), { x: c, y: l, z: i } = t.position;
  return {
    x: c * s - l * a + o.x,
    y: c * a + l * s + o.y,
    z: i
  };
}
const L = 1e-9;
function S(t) {
  if (t.rooms.length === 0) return 0;
  const n = /* @__PURE__ */ new Map();
  for (const s of t.rooms)
    n.set(s.floorLevel, (n.get(s.floorLevel) ?? 0) + 1);
  let o = 0, e = -1;
  for (const [s, a] of n)
    (a > e || a === e && s < o) && (e = a, o = s);
  return o;
}
function _(t, n) {
  const o = n ?? S(t);
  let e = 1 / 0, s = 1 / 0, a = -1 / 0, c = -1 / 0;
  for (const l of t.rooms)
    if (l.floorLevel === o)
      for (const i of I(l))
        i.x < e && (e = i.x), i.y < s && (s = i.y), i.x > a && (a = i.x), i.y > c && (c = i.y);
  return Number.isFinite(e) ? { minX: e, minY: s, maxX: a, maxY: c } : null;
}
const p = 5, R = 400, W = 40, b = 120, M = 24;
function h(t) {
  if (t.length === 0) return null;
  let n = 1 / 0, o = 1 / 0, e = -1 / 0, s = -1 / 0;
  for (const a of t)
    a.x < n && (n = a.x), a.y < o && (o = a.y), a.x > e && (e = a.x), a.y > s && (s = a.y);
  return { minX: n, minY: o, maxX: e, maxY: s };
}
function B(t, n, o) {
  const e = [
    { x: t.minX, y: t.minY },
    { x: t.maxX, y: t.minY },
    { x: t.maxX, y: t.maxY },
    { x: t.minX, y: t.maxY }
  ];
  return Math.abs(n) < L ? h(e) : h(e.map((s) => X(s, n, o)));
}
function O(t, n, o, e, s = 0, a = { x: 0, y: 0 }) {
  const c = e + M, l = Math.max(n - 2 * c, 1), i = Math.max(o - 2 * c, 1), f = B(t, s, a), d = Math.max(f.maxX - f.minX, 1e-6), r = Math.max(f.maxY - f.minY, 1e-6), m = Math.min(l / d, i / r), T = d > 0 ? b / d : p, F = r > 0 ? b / r : p, y = Math.max(p, Math.min(R, Math.max(m, T, F))), $ = d * y, P = r * y, x = {
    scale: y,
    offset: {
      x: (n - $) / 2 - f.minX * y,
      y: (o - P) / 2 - f.minY * y
    }
  };
  return Math.abs(s) > L && (x.rotation = s, x.pivot = a), x;
}
const z = 12, D = 3;
function g(t) {
  const n = [...t].sort((e, s) => e - s), o = n.length >> 1;
  return n.length % 2 ? n[o] : (n[o - 1] + n[o]) / 2;
}
function q(t, n) {
  const o = n ?? S(t), e = t.rooms.filter((r) => r.floorLevel === o);
  if (e.length <= 3) return _(t, o);
  const s = e.map((r) => I(r)), a = s.map((r) => {
    const m = h(r);
    return { x: (m.minX + m.maxX) / 2, y: (m.minY + m.maxY) / 2 };
  }), c = g(a.map((r) => r.x)), l = g(a.map((r) => r.y)), i = a.map((r) => Math.max(Math.abs(r.x - c), Math.abs(r.y - l))), f = Math.max(z, D * g(i)), d = s.filter((r, m) => i[m] <= f);
  return d.length === s.length || d.length < Math.ceil(e.length / 2) ? _(t, o) : h(d.flat());
}
function w(t, n, o, e = 24, s) {
  const a = q(t, s);
  return a === null || n <= 0 || o <= 0 ? { scale: W, offset: { x: e + M, y: e + M } } : O(a, n, o, e, 0, { x: 0, y: 0 });
}
function X(t, n, o = { x: 0, y: 0 }) {
  const e = n * Math.PI / 180, s = Math.cos(e), a = Math.sin(e), c = t.x - o.x, l = t.y - o.y;
  return {
    x: s * c - a * l + o.x,
    y: a * c + s * l + o.y
  };
}
function C(t, n) {
  const o = n.rotation ?? 0;
  if (Math.abs(o) < L)
    return {
      x: t.x * n.scale + n.offset.x,
      y: t.y * n.scale + n.offset.y
    };
  const e = n.pivot ?? { x: 0, y: 0 }, s = X(t, o, e);
  return {
    x: s.x * n.scale + n.offset.x,
    y: s.y * n.scale + n.offset.y
  };
}
function U(t, n) {
  return I(t).map((o) => {
    const e = C(o, n);
    return `${e.x.toFixed(2)},${e.y.toFixed(2)}`;
  }).join(" ");
}
function V(t) {
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
function j(t) {
  return {
    entityId: t.entity_id,
    roomId: t.room_id,
    position: { x: t.position.x, y: t.position.y, z: t.position.z },
    rotation: t.rotation,
    mountType: t.mount_type,
    notes: t.notes
  };
}
function G(t) {
  return {
    id: t.id,
    name: t.name,
    version: t.version,
    calibration: t.calibration ? {
      referenceEntity: t.calibration.reference_entity,
      realWorldDistance: t.calibration.real_world_distance,
      measuredDistance: t.calibration.measured_distance
    } : void 0,
    rooms: t.rooms.map(V),
    entities: t.placements.map(j),
    createdAt: t.created_at,
    updatedAt: t.updated_at
  };
}
const A = 480, E = 360, Y = `
  .wrap { padding: 8px 12px 12px; }
  svg { width: 100%; height: auto; display: block; background: #f8f9fa; border-radius: 12px; }
  .room { fill: rgba(16,185,129,0.10); stroke: #059669; stroke-width: 1.5; }
  .room.orphaned { fill: rgba(148,163,184,0.12); stroke: #94a3b8; stroke-dasharray: 4 3; }
  .dot { stroke: #ffffff; stroke-width: 1.5; }
  .dot.on { fill: #059669; }
  .dot.off { fill: #9ca3af; }
  .empty { padding: 24px; color: #6b7280; font-size: 14px; }
`;
function Z(t) {
  return t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
class J extends HTMLElement {
  constructor() {
    super();
    u(this, "_config");
    u(this, "_hass");
    u(this, "_layout", null);
    u(this, "_requested", !1);
    u(this, "_root");
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
      this._layout = G(o);
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
    const o = Z(this._config?.title ?? "Floorplan");
    if (this._layout === null || this._layout.rooms.length === 0) {
      this._root.innerHTML = `<style>${Y}</style><ha-card header="${o}"><div class="empty">No spatial layout yet.</div></ha-card>`;
      return;
    }
    const e = S(this._layout), s = w(this._layout, A, E, 16, e), a = this._layout.rooms.filter((i) => i.floorLevel === e).map((i) => `<polygon points="${U(i, s)}" class="room${i.orphaned ? " orphaned" : ""}"/>`).join(""), c = new Map(this._layout.rooms.map((i) => [i.id, i])), l = this._layout.entities.filter((i) => i.roomId ? c.get(i.roomId)?.floorLevel === e : !0).map((i) => {
      const f = i.roomId ? c.get(i.roomId) : void 0, d = f ? H(i, f) : i.position, r = C({ x: d.x, y: d.y }, s), m = this._isActive(i.entityId) ? "on" : "off";
      return `<circle cx="${r.x.toFixed(1)}" cy="${r.y.toFixed(1)}" r="5" class="dot ${m}"/>`;
    }).join("");
    this._root.innerHTML = `<style>${Y}</style><ha-card header="${o}"><div class="wrap"><svg viewBox="0 0 ${A} ${E}" preserveAspectRatio="xMidYMid meet">${a}${l}</svg></div></ha-card>`;
  }
}
customElements.get("ha-spatial-floorplan-card") || customElements.define("ha-spatial-floorplan-card", J);
const v = window;
v.customCards = v.customCards ?? [];
v.customCards.push({
  type: "ha-spatial-floorplan-card",
  name: "HA Spatial Floorplan",
  description: "Spatially accurate floorplan with live entity positions."
});
