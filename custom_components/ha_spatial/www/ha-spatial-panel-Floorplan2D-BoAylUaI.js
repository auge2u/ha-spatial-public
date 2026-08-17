import { S as bt, _ as It, K as rt, b as yt, W as S, w as K, Z as Q, Q as at, V as At, U as q, v as t, o as P, a as Z, G as nt, a0 as T, g as R, u as V, n as Lt, t as ht, I as L, X as D, J as Zt, a1 as F, P as g, $ as J, N as tt, L as xt, a3 as Vt, D as Bt, e as Gt, a2 as Dt, h as et, E as Kt, M as Ot, s as jt } from "./ha-spatial-panel-D1fnh84z.js";
function ot(m, e = {}, x, s) {
  for (var h in x) {
    var p = x[h];
    e[h] !== p && (x[h] == null ? m.style.removeProperty(h) : m.style.setProperty(h, p, s));
  }
}
function gt(m, e, x, s) {
  var h = (
    /** @type {any} */
    m[bt]
  );
  if (h !== e) {
    var p = It(e, s);
    p == null ? m.removeAttribute("style") : m.style.cssText = p, m[bt] = e;
  } else s && (Array.isArray(s) ? (ot(m, x?.[0], s[0]), ot(m, x?.[1], s[1], "important")) : ot(m, x, s));
  return s;
}
var Nt = V('<button type="button" class="px-2.5 py-1.5 text-xs font-semibold text-[color:var(--p-text,#374151)] hover:text-[color:var(--p-emerald-hover-text,#047857)] hover:bg-[color:var(--p-emerald-hover,#f0fdf4)] rounded-lg transition-colors" aria-label="Fit selected room to view" title="Fit selected">Fit selected</button>'), Ut = V('<div class="flex items-center gap-1 bg-[color-mix(in_srgb,var(--p-surface,#ffffff)_92%,transparent)] backdrop-blur-sm border border-[color:var(--p-border,#e5e7eb)] rounded-xl shadow-sm shadow-black/5 p-1" role="toolbar" aria-label="Floorplan view controls" tabindex="0"><button type="button" class="flex items-center justify-center w-8 h-8 rounded-lg text-[color:var(--p-text-secondary,#6b7280)] hover:text-[color:var(--p-emerald-hover-text,#047857)] hover:bg-[color:var(--p-emerald-hover,#f0fdf4)] transition-colors" aria-label="Zoom out" title="Zoom out"><svg class="w-5 h-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M6.75 9.25a.75.75 0 000 1.5h6.5a.75.75 0 000-1.5h-6.5z"></path><path fill-rule="evenodd" d="M9.965 2a7.465 7.465 0 104.936 13.13l2.641 2.642a.75.75 0 101.06-1.061l-2.64-2.641A7.465 7.465 0 009.965 2zM3.5 9.465a6.465 6.465 0 1112.93 0 6.465 6.465 0 01-12.93 0z" clip-rule="evenodd"></path></svg></button> <div class="flex items-center gap-2 px-1"><input type="range" class="zoom-slider w-24 h-1 bg-[color:var(--p-border)] rounded-lg appearance-none cursor-pointer accent-emerald-600 svelte-1k9fsin" step="0.05" aria-label="Zoom"/> <span class="text-[11px] font-semibold text-[color:var(--p-text-secondary,#6b7280)] w-10 text-right tabular-nums"> </span></div> <button type="button" class="flex items-center justify-center w-8 h-8 rounded-lg text-[color:var(--p-text-secondary,#6b7280)] hover:text-[color:var(--p-emerald-hover-text,#047857)] hover:bg-[color:var(--p-emerald-hover,#f0fdf4)] transition-colors" aria-label="Zoom in" title="Zoom in"><svg class="w-5 h-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M10.75 6.75a.75.75 0 00-1.5 0v2.5h-2.5a.75.75 0 000 1.5h2.5v2.5a.75.75 0 001.5 0v-2.5h2.5a.75.75 0 000-1.5h-2.5v-2.5z"></path><path fill-rule="evenodd" d="M9.965 2a7.465 7.465 0 104.936 13.13l2.641 2.642a.75.75 0 101.06-1.061l-2.64-2.641A7.465 7.465 0 009.965 2zM3.5 9.465a6.465 6.465 0 1112.93 0 6.465 6.465 0 01-12.93 0z" clip-rule="evenodd"></path></svg></button> <div class="w-px h-5 bg-[color:var(--p-border)] mx-1" aria-hidden="true"></div> <button type="button" class="px-2.5 py-1.5 text-xs font-semibold text-[color:var(--p-text,#374151)] hover:text-[color:var(--p-emerald-hover-text,#047857)] hover:bg-[color:var(--p-emerald-hover,#f0fdf4)] rounded-lg transition-colors" aria-label="Fit floor to view" title="Fit floor">Fit floor</button> <!> <button type="button" class="px-2.5 py-1.5 text-xs font-semibold text-[color:var(--p-text,#374151)] hover:text-[color:var(--p-emerald-hover-text,#047857)] hover:bg-[color:var(--p-emerald-hover,#f0fdf4)] rounded-lg transition-colors" aria-label="Reset pan and zoom" title="Reset">Reset</button></div>');
const Xt = {
  hash: "svelte-1k9fsin",
  code: ".zoom-slider.svelte-1k9fsin::-webkit-slider-thumb {width:14px;height:14px;background-color:#059669;border-radius:9999px;border:2px solid #ffffff;box-shadow:0 1px 2px rgba(0, 0, 0, 0.1);-webkit-appearance:none;appearance:none;}.zoom-slider.svelte-1k9fsin::-moz-range-thumb {width:14px;height:14px;background-color:#059669;border-radius:9999px;border:2px solid #ffffff;box-shadow:0 1px 2px rgba(0, 0, 0, 0.1);}"
};
function Ht(m, e) {
  rt(e, !0), yt(m, Xt);
  const x = T(() => Math.round(e.zoom * 100));
  var s = Ut(), h = R(s), p = S(h, 2), z = R(p), O = S(z, 2), B = R(O), y = S(p, 2), r = S(y, 4), b = S(r, 2);
  {
    var C = (u) => {
      var H = Nt();
      P("click", H, function(...w) {
        e.onFitSelected?.apply(this, w);
      }), Z(u, H);
    };
    K(b, (u) => {
      e.canFitSelected && u(C);
    });
  }
  var M = S(b, 2);
  Q(() => {
    at(z, "min", e.minZoom), at(z, "max", e.maxZoom), At(z, e.zoom), q(B, `${t(x) ?? ""}%`);
  }), P("click", s, (u) => u.stopPropagation()), P("keydown", s, (u) => u.stopPropagation()), P("click", h, function(...u) {
    e.onZoomOut?.apply(this, u);
  }), P("input", z, (u) => e.onZoom(parseFloat(u.currentTarget.value))), P("click", y, function(...u) {
    e.onZoomIn?.apply(this, u);
  }), P("click", r, function(...u) {
    e.onFitAll?.apply(this, u);
  }), P("click", M, function(...u) {
    e.onReset?.apply(this, u);
  }), Z(m, s), nt();
}
Lt(["click", "keydown", "input"]);
var Yt = V('<div class="scale-bar inline-flex flex-col items-center gap-1 bg-[color-mix(in_srgb,var(--p-surface,#ffffff)_92%,transparent)] backdrop-blur-sm border border-[color:var(--p-border,#e5e7eb)] rounded-lg shadow-sm shadow-black/5 px-2 py-1.5 pointer-events-none select-none" role="img"><div class="relative"><div class="absolute inset-x-0 top-1/2 -translate-y-1/2 h-0.5 bg-[color:var(--p-text-faint,#9ca3af)] rounded-full"></div> <div class="absolute left-0 top-0 bottom-0 w-0.5 bg-[color:var(--p-text-faint,#9ca3af)] rounded-full"></div> <div class="absolute right-0 top-0 bottom-0 w-0.5 bg-[color:var(--p-text-faint,#9ca3af)] rounded-full"></div></div> <span class="text-[11px] font-semibold text-[color:var(--p-text-secondary,#6b7280)] tabular-nums"> </span></div>');
function Wt(m, e) {
  rt(e, !0);
  const x = T(() => {
    const y = 96 / e.scale, r = Math.floor(Math.log10(y)), b = y / Math.pow(10, r);
    let C = 1;
    b >= 5 ? C = 10 : b >= 2 ? C = 5 : b >= 1 ? C = 2 : C = 1;
    const M = C * Math.pow(10, r);
    return { meters: M, px: M * e.scale };
  });
  var s = Yt(), h = R(s);
  let p;
  var z = S(h, 2), O = R(z);
  Q(
    (B, y) => {
      at(s, "aria-label", B), p = gt(h, "", p, { width: `${t(x).px ?? ""}px`, height: "10px" }), q(O, y);
    },
    [
      () => `Scale: ${ht(t(x).meters)}`,
      () => ht(t(x).meters)
    ]
  ), Z(m, s), nt();
}
var Jt = V(`<div class="empty svelte-h0bz5n">The floorplan editor failed to load — this tab is running outdated code.
      Hard-refresh (Ctrl/Cmd+Shift+R) to reload.</div>`), Qt = V('<div class="empty svelte-h0bz5n">No rooms on this floor.</div>'), qt = V('<div class="status svelte-h0bz5n">Rooms: <strong> </strong> </div>'), $t = V('<div class="floorplan svelte-h0bz5n"><!> <!> <!> <!> <!></div>');
const te = {
  hash: "svelte-h0bz5n",
  code: `
  /* Dark-mode bridge: prefer HA theme variables (real HA dark mode), fall back
     to the light palette, and darken the fallbacks under prefers-color-scheme
     (dev harness / browsers). The Konva palette in the script reads the
     computed .floorplan background so canvas paint matches. */.floorplan.svelte-h0bz5n {position:relative;background:var(--card-background-color, #f8f9fa);overflow:hidden;cursor:grab;--fp-text: #6b7280;--fp-status-bg: rgba(255, 255, 255, 0.8);}
  @media (prefers-color-scheme: dark) {.floorplan.svelte-h0bz5n {background:var(--card-background-color, #1f2937);--fp-text: #9ca3af;--fp-status-bg: rgba(31, 41, 55, 0.85);}
  }.floorplan.svelte-h0bz5n:active {cursor:grabbing;}.empty.svelte-h0bz5n {position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--fp-text);font:14px system-ui, sans-serif;}.status.svelte-h0bz5n {position:absolute;left:8px;bottom:8px;font:12px system-ui, sans-serif;color:var(--fp-text);background:var(--fp-status-bg);padding:2px 8px;border-radius:9999px;}`
};
function oe(m, e) {
  rt(e, !0), yt(m, te);
  let x = L(e, "activeFloorLevel", 3, 0), s = L(e, "selectedRoomId", 3, null), h = L(e, "disabled", 3, !1), p = L(e, "placeEntityMode", 3, !1), z = L(e, "showControls", 3, !0), O = L(e, "showScaleBar", 3, !0), B = L(e, "showStatusBar", 3, !0), y, r = D(Zt({ scale: 1, x: 0, y: 0 }));
  F(() => {
    e.baseViewport.scale, e.baseViewport.offset.x, e.baseViewport.offset.y, g(
      r,
      {
        scale: e.baseViewport.scale,
        x: e.baseViewport.offset.x,
        y: e.baseViewport.offset.y
      },
      !0
    );
  });
  const b = T(() => e.layout.rooms.filter((o) => o.floorLevel === x())), C = T(() => new Set(t(b).map((o) => o.id))), M = T(() => e.layout.entities.filter((o) => !o.roomId || t(C).has(o.roomId))), u = T(() => t(b).map((o) => o.id).join("|") + "#" + t(M).map((o) => o.entityId).join("|")), H = 13;
  let w = D(null), I = D(null), k = D(null), A = {}, j = [], N = D(null);
  const pt = 2, wt = 7, kt = 2, lt = {
    roomFill: "rgba(16,185,129,0.12)",
    roomStroke: "#10b981",
    roomStrokeSelected: "#059669",
    labelFill: "#065f46",
    entityFill: "#10b981"
  }, St = {
    roomFill: "rgba(52,211,153,0.16)",
    roomStroke: "#34d399",
    roomStrokeSelected: "#6ee7b7",
    labelFill: "#a7f3d0",
    entityFill: "#34d399"
  };
  let E = lt;
  function _t(o) {
    return Kt(getComputedStyle(o).backgroundColor, lt, St);
  }
  const c = {
    placeEntityMode: !1,
    disabled: !1,
    layout: {
      id: "",
      name: "",
      version: 1,
      rooms: [],
      entities: [],
      createdAt: "",
      updatedAt: ""
    },
    onSelectRoom: void 0,
    onCommitGeometry: void 0,
    onCommitEntity: void 0,
    onPlaceEntity: void 0
  };
  F(() => {
    c.placeEntityMode = p(), c.disabled = h(), c.layout = e.layout, c.onSelectRoom = e.onSelectRoom, c.onCommitGeometry = e.onCommitGeometry, c.onCommitEntity = e.onCommitEntity, c.onPlaceEntity = e.onPlaceEntity;
  });
  async function Et() {
    const o = document.createElement("canvas");
    if (typeof o.getContext != "function" || !o.getContext("2d")) return null;
    try {
      return (await import("./ha-spatial-panel-konva-BolVosKQ.js")).default;
    } catch (l) {
      return g(it, !0), e.onLoadError?.(l), null;
    }
  }
  let it = D(!1);
  Et().then((o) => {
    g(N, o, !0);
  }).catch(() => {
  }), F(() => {
    if (!y || !t(N)) return;
    const o = t(N), l = J(() => e.width), a = J(() => e.height), n = J(() => t(r));
    E = _t(y);
    const i = new o.Stage({
      container: y,
      width: l,
      height: a,
      draggable: !0,
      // pan; a room's own drag wins over the stage's
      x: n.x,
      y: n.y
    }), d = new o.Layer();
    i.add(d);
    const f = new o.Transformer({
      rotateEnabled: !0,
      borderStroke: E.roomStroke,
      anchorStroke: E.roomStroke,
      anchorFill: "#ffffff",
      anchorSize: 9,
      rotationSnaps: [0, 45, 90, 135, 180, 225, 270, 315],
      rotationSnapTolerance: 4,
      // Resize from any edge/corner; default skips some anchors on thin shapes.
      enabledAnchors: [
        "top-left",
        "top-right",
        "bottom-left",
        "bottom-right",
        "middle-left",
        "middle-right",
        "top-center",
        "bottom-center"
      ]
    });
    return d.add(f), i.on("dragmove", (_) => {
      _.target === i && g(r, { ...t(r), x: i.x(), y: i.y() }, !0);
    }), i.on("wheel", (_) => {
      _.evt.preventDefault();
      const v = i.getPointerPosition();
      if (!v) return;
      const U = t(r).scale, W = (v.x - t(r).x) / U, X = (v.y - t(r).y) / U, G = Dt(_.evt.deltaY), $ = et(t(r).scale, t(r).scale * G);
      g(r, { scale: $, x: v.x - W * $, y: v.y - X * $ }, !0);
    }), i.on("click tap", (_) => {
      if (_.target === i) {
        if (c.placeEntityMode && c.onPlaceEntity) {
          const v = i.getPointerPosition();
          v && c.onPlaceEntity({
            x: (v.x - t(r).x) / t(r).scale,
            y: (v.y - t(r).y) / t(r).scale,
            z: 1.2
          });
          return;
        }
        c.onSelectRoom?.(null);
      }
    }), g(w, i, !0), g(I, d, !0), g(k, f, !0), () => {
      i.destroy(), g(w, null), g(I, null), g(k, null);
    };
  }), F(() => {
    t(w) && t(w).size({ width: e.width, height: e.height });
  }), F(() => {
    t(w) && t(w).position({ x: t(r).x, y: t(r).y });
  }), F(() => {
    if (!t(I) || !t(N)) return;
    t(u);
    const o = t(N), l = J(() => t(
      r
      // bake at current scale; re-bake effect tracks zoom
    ).scale);
    for (const { group: a } of Object.values(A)) a.destroy();
    for (const { node: a } of j) a.destroy();
    A = {}, j = [];
    for (const a of t(b)) {
      const n = new o.Group({
        id: a.id,
        x: (a.origin?.x ?? 0) * l,
        y: (a.origin?.y ?? 0) * l,
        rotation: a.rotation ?? 0,
        draggable: !c.disabled && !!c.onCommitGeometry
      }), i = new o.Line({
        points: tt(a.polygon, l),
        closed: !0,
        fill: E.roomFill,
        stroke: E.roomStroke,
        strokeWidth: pt
      });
      n.add(i);
      const d = new o.Text({
        text: a.name,
        fontSize: H,
        fontFamily: "Instrument Sans, system-ui, sans-serif",
        fill: E.labelFill,
        x: 6,
        y: 6,
        listening: !1
      });
      n.add(d), t(I).add(n), A[a.id] = { group: n, line: i, label: d }, n.on("click tap", (f) => {
        c.disabled || (f.cancelBubble = !0, c.onSelectRoom?.(a.id));
      }), n.on("transform", () => {
        t(k)?.forceUpdate(), t(k)?.getLayer()?.batchDraw();
      }), n.on("dragmove", () => {
        t(k)?.forceUpdate();
      }), n.on("dragend", () => {
        if (!c.onCommitGeometry) return;
        const f = t(
          r
          // px -> meters
        ).scale;
        c.onCommitGeometry(a.id, {
          origin: { x: n.x() / f, y: n.y() / f },
          rotation: n.rotation()
        }), t(k)?.forceUpdate();
      }), n.on("transformend", () => {
        if (!c.onCommitGeometry) return;
        const f = t(r).scale, v = c.layout.rooms.find((G) => G.id === a.id)?.polygon ?? a.polygon, U = n.scaleX(), W = n.scaleY();
        let X = v;
        (Math.abs(U - 1) > 1e-4 || Math.abs(W - 1) > 1e-4) && (X = v.map((G) => ({ x: G.x * U, y: G.y * W })), n.scale({ x: 1, y: 1 }), i.points(tt(X, f))), c.onCommitGeometry(a.id, {
          origin: { x: n.x() / f, y: n.y() / f },
          rotation: n.rotation(),
          polygon: X
        });
      });
    }
    for (const a of t(M)) {
      const n = a.roomId ? e.layout.rooms.find((f) => f.id === a.roomId) ?? null : null, i = n ? xt(a, n) : { x: a.position.x, y: a.position.y };
      if (!i) continue;
      const d = new o.Circle({
        x: i.x * l,
        y: i.y * l,
        radius: wt,
        fill: E.entityFill,
        stroke: "#ffffff",
        strokeWidth: kt,
        draggable: !c.disabled && !!c.onCommitEntity
      });
      d.on("dragstart", (f) => {
        f.cancelBubble = !0;
      }), d.on("dragend", () => {
        if (!c.onCommitEntity) return;
        const f = t(r).scale, _ = { x: d.x() / f, y: d.y() / f, z: a.position.z }, v = n ? { position: Vt(_, n) } : { position: _ };
        c.onCommitEntity(a.entityId, v);
      }), t(I).add(d), j.push({ node: d, entity: a });
    }
    t(k)?.moveToTop();
  }), F(() => {
    const o = t(r).scale;
    if (t(u), !!t(I)) {
      for (const l of t(b)) {
        const a = A[l.id];
        a && (a.group.position({ x: (l.origin?.x ?? 0) * o, y: (l.origin?.y ?? 0) * o }), a.group.rotation(l.rotation ?? 0), a.group.scale({ x: 1, y: 1 }), a.line.points(tt(l.polygon, o)));
      }
      for (const { node: l, entity: a } of j) {
        const n = e.layout.entities.find((f) => f.entityId === a.entityId) ?? a, i = n.roomId ? e.layout.rooms.find((f) => f.id === n.roomId) ?? null : null, d = i ? xt(n, i) : { x: n.position.x, y: n.position.y };
        d && l.position({ x: d.x * o, y: d.y * o });
      }
      t(k)?.forceUpdate(), t(I).batchDraw();
    }
  }), F(() => {
    t(u);
    const o = s(), l = h();
    if (t(k)) {
      for (const [a, { line: n, group: i }] of Object.entries(A))
        n.stroke(l ? E.roomStroke : o === a ? E.roomStrokeSelected : E.roomStroke), i.draggable(!l && !!e.onCommitGeometry);
      for (const { node: a } of j)
        a.draggable(!l && !!e.onCommitEntity);
      t(k).nodes(l ? [] : o && A[o] ? [A[o].group] : []), t(k).moveToTop(), t(k).forceUpdate(), t(k).getLayer()?.batchDraw();
    }
  }), F(() => {
    y && t(w) && (y.__konvaStage = t(w));
  }), Bt(() => {
    t(w)?.destroy();
  });
  function st(o) {
    if (!t(w)) return;
    const l = e.width / 2, a = e.height / 2, n = (l - t(r).x) / t(r).scale, i = (a - t(r).y) / t(r).scale, d = et(t(r).scale, t(r).scale * o);
    g(r, { scale: d, x: l - n * d, y: a - i * d }, !0);
  }
  function ct() {
    g(
      r,
      {
        scale: e.baseViewport.scale,
        x: e.baseViewport.offset.x,
        y: e.baseViewport.offset.y
      },
      !0
    );
  }
  function zt() {
    if (!s()) return;
    const o = t(b).find((n) => n.id === s());
    if (!o) return;
    const l = Ot(o);
    if (!l) return;
    const a = jt(l, e.width, e.height, 16);
    g(r, { scale: a.scale, x: a.offset.x, y: a.offset.y }, !0);
  }
  var Y = $t();
  let dt;
  var ft = R(Y);
  {
    var Ct = (o) => {
      var l = Jt();
      Z(o, l);
    };
    K(ft, (o) => {
      t(it) && o(Ct);
    });
  }
  var ut = S(ft, 2);
  {
    var Ft = (o) => {
      const l = T(() => e.baseViewport.scale > 0 ? t(r).scale / e.baseViewport.scale : 1);
      {
        let a = T(() => !!s());
        Ht(o, {
          get zoom() {
            return t(l);
          },
          minZoom: 0.1,
          maxZoom: 20,
          get canFitSelected() {
            return t(a);
          },
          onZoom: (n) => {
            const i = e.width / 2, d = e.height / 2, f = (i - t(r).x) / t(r).scale, _ = (d - t(r).y) / t(r).scale, v = et(e.baseViewport.scale, e.baseViewport.scale * n);
            g(r, { scale: v, x: i - f * v, y: d - _ * v }, !0);
          },
          onZoomIn: () => st(1.2),
          onZoomOut: () => st(0.8333333333333334),
          onFitAll: ct,
          onFitSelected: zt,
          onReset: ct
        });
      }
    };
    K(ut, (o) => {
      z() && t(b).length > 0 && o(Ft);
    });
  }
  var mt = S(ut, 2);
  {
    var Pt = (o) => {
      Wt(o, {
        get scale() {
          return t(r).scale;
        }
      });
    };
    K(mt, (o) => {
      O() && t(b).length > 0 && t(w) && o(Pt);
    });
  }
  var vt = S(mt, 2);
  {
    var Tt = (o) => {
      var l = Qt();
      Z(o, l);
    };
    K(vt, (o) => {
      t(b).length === 0 && o(Tt);
    });
  }
  var Rt = S(vt, 2);
  {
    var Mt = (o) => {
      var l = qt(), a = S(R(l)), n = R(a), i = S(a);
      Q(() => {
        q(n, t(b).length), q(i, ` · Selected: ${s() ? "1" : "None"}`);
      }), Z(o, l);
    };
    K(Rt, (o) => {
      B() && t(b).length > 0 && o(Mt);
    });
  }
  Gt(Y, (o) => y = o, () => y), Q(() => dt = gt(Y, "", dt, {
    width: `${e.width ?? ""}px`,
    height: `${e.height ?? ""}px`
  })), Z(m, Y), nt();
}
export {
  oe as default
};
