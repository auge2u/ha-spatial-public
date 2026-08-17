var x = Object.defineProperty;
var _ = (e, t, n) => t in e ? x(e, t, { enumerable: !0, configurable: !0, writable: !0, value: n }) : e[t] = n;
var y = (e, t, n) => _(e, typeof t != "symbol" ? t + "" : t, n);
import { F as g } from "./ha-spatial-panel-D1fnh84z.js";
class f extends Error {
  constructor(n, r) {
    super(r);
    y(this, "code");
    this.name = "RoomPlanImportError", this.code = n;
  }
}
const A = 1, M = 1e3, w = 0.01;
function d(e) {
  return typeof e == "object" && e !== null && !Array.isArray(e);
}
function b(e) {
  const t = [];
  for (const s of e) {
    const o = t[t.length - 1];
    o && Math.hypot(s.x - o.x, s.y - o.y) <= w || t.push(s);
  }
  const n = t[0], r = t[t.length - 1];
  return t.length > 1 && n && r && Math.hypot(n.x - r.x, n.y - r.y) <= w && t.pop(), t;
}
function u(e, t, n) {
  return (t.x - e.x) * (n.y - e.y) - (t.y - e.y) * (n.x - e.x);
}
function l(e, t, n) {
  return Math.min(e.x, t.x) <= n.x && n.x <= Math.max(e.x, t.x) && Math.min(e.y, t.y) <= n.y && n.y <= Math.max(e.y, t.y);
}
function E(e, t, n, r) {
  const s = u(n, r, e), o = u(n, r, t), c = u(e, t, n), i = u(e, t, r);
  return !!((s > 0 && o < 0 || s < 0 && o > 0) && (c > 0 && i < 0 || c < 0 && i > 0) || s === 0 && l(n, r, e) || o === 0 && l(n, r, t) || c === 0 && l(e, t, n) || i === 0 && l(e, t, r));
}
function T(e) {
  const t = e.length;
  if (t < 4) return !1;
  for (let n = 0; n < t; n++) {
    const r = e[n], s = e[(n + 1) % t];
    for (let o = n + 1; o < t; o++) {
      if (o === n || (n + 1) % t === o || (o + 1) % t === n) continue;
      const c = e[o], i = e[(o + 1) % t];
      if (E(r, s, c, i)) return !0;
    }
  }
  return !1;
}
function F(e) {
  const t = g(e) >= 0 ? e.slice() : e.slice().reverse();
  let n = 0;
  for (let r = 1; r < t.length; r++)
    (t[r].y < t[n].y || t[r].y === t[n].y && t[r].x < t[n].x) && (n = r);
  return [...t.slice(n), ...t.slice(0, n)];
}
function p(e) {
  const t = () => new f("malformed", "Couldn't read this scan file.");
  if (!d(e)) throw t();
  const n = e.forge_roomplan_import;
  if (n !== void 0 && n !== 1)
    throw new f(
      "unsupported_version",
      "This scan file is a newer or older format than this app supports."
    );
  if (n !== 1 || e.source !== "roomplan" || !d(e.room)) throw t();
  const r = e.room, s = r.polygon_m, o = r.ceiling_height_m;
  if (!Array.isArray(s) || s.length < 3) throw t();
  if (typeof o != "number" || o <= 0)
    throw typeof o == "number" && !Number.isFinite(o) ? new f("non_finite", "This scan has invalid measurements.") : t();
  const c = [];
  for (const a of s) {
    if (!Array.isArray(a) || a.length !== 2 || typeof a[0] != "number" || typeof a[1] != "number")
      throw t();
    if (!Number.isFinite(a[0]) || !Number.isFinite(a[1]))
      throw new f("non_finite", "This scan has invalid measurements.");
    c.push({ x: a[0], y: a[1] });
  }
  if (!Number.isFinite(o))
    throw new f("non_finite", "This scan has invalid measurements.");
  const i = b(c);
  if (i.length < 3)
    throw new f("too_few_points", "Couldn't form a room outline from this scan.");
  const m = Math.abs(g(i));
  if (m < A || m > M)
    throw new f("implausible_scale", "This scan's measurements look wrong (check units).");
  if (T(i))
    throw new f("self_intersecting", "This room outline crosses itself.");
  const h = { polygon: F(i), height: o };
  return typeof r.name == "string" && r.name.trim() && (h.name = r.name.trim()), h;
}
export {
  f as R,
  p
};
