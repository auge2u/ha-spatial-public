import { K as St, b as It, I as At, X as C, J as ve, a1 as Le, P as s, z as Ct, Y as Pt, v as e, B as $, A as Lt, D as Ht, w as H, a as d, G as Dt, g as i, i as qe, r as M, W as a, Z as y, U as f, o as P, p as ie, u as v, q as Ge, k as Et, a0 as oe, Q as Ye, f as Ke, n as Vt, j as jt, C as Qe, T as Xe, R as Mt, m as Ot, l as Wt, x as Nt, H as Ut, d as Ze, y as Ft, O as Tt, c as $e } from "./ha-spatial-panel-7R_qzjSW.js";
import { p as Bt, R as Jt } from "./ha-spatial-panel-roomplan-import-D6eAwOIk.js";
import qt from "./ha-spatial-panel-Floorplan2D-B7qaVtui.js";
function Gt(w) {
  const p = (/* @__PURE__ */ new Date()).toISOString(), j = w.sessionId || `vision-${Date.now()}`, r = w.photoFiles.map((u, W) => {
    const N = w.imageDimensions[W] || { width: 0, height: 0 }, le = N.width && N.height ? N.width / N.height : 1;
    return {
      name: u.name,
      type: u.type,
      size: u.size,
      width: N.width,
      height: N.height,
      aspect: le
    };
  }), x = r.length, ee = r.reduce((u, W) => u + W.size, 0), O = x > 0 ? Math.round(r.reduce((u, W) => u + W.width, 0) / x) : 0, T = x > 0 ? Math.round(r.reduce((u, W) => u + W.height, 0) / x) : 0, fe = O && T ? O / T : 1, I = x >= 5 && O >= 2e3 && T >= 1500, B = {
    photosLeftDevice: !1,
    // CRITICAL — must flip to true only when we actually upload
    processingLocation: "local-only",
    captureTimestamp: p,
    retention: "discard-immediately",
    explanation: "Photos are analyzed in your browser for this prototype. No imagery leaves your device."
  };
  return {
    sessionId: j,
    roomHint: w.roomHint,
    photos: r,
    localSignals: {
      photoCount: x,
      avgWidth: O,
      avgHeight: T,
      avgAspect: fe,
      totalBytes: ee,
      isHighQualitySet: I
    },
    privacy: B,
    preparedAt: p
  };
}
async function Yt(w) {
  const { simulatedVision: p } = await import("./ha-spatial-panel-simulated-vision-D_G8pPNt.js");
  return p(w);
}
async function Kt(w) {
  try {
    const j = (await w.sendMessagePromise({ type: "ha_spatial/info" }))?.vision?.egress_class;
    return j === "none" || j === "local" || j === "cloud" ? j : null;
  } catch {
    return null;
  }
}
function Qt(w) {
  switch (w) {
    case "local":
      return "Analyzed by your Home Assistant AI setup — you choose the provider and where it runs.";
    case "cloud":
      return "Analyzed once by the configured cloud vision service with your consent.";
    default:
      return "Analyzed on this device — your photos never left it.";
  }
}
class tt extends Error {
  constructor() {
    super("cloud vision requires explicit consent"), this.name = "VisionConsentRequired";
  }
}
async function He(w, p) {
  try {
    return await w.sendMessagePromise({
      type: "ha_spatial/vision/analyze",
      photos: p.photos ?? [],
      room_hint: p.roomHint,
      signals: p.signals,
      consent: p.consent ?? !1
    });
  } catch (j) {
    throw j?.code === "consent_required" ? new tt() : j;
  }
}
class De extends Error {
  constructor(p) {
    super(p), this.name = "DownscaleError";
  }
}
function Xt(w, p, j) {
  const r = Math.max(w, p);
  if (r <= j || r === 0) return { width: w, height: p };
  const x = j / r;
  return { width: Math.round(w * x), height: Math.round(p * x) };
}
async function et(w, p = 1568, j = 0.8) {
  const r = await createImageBitmap(w), { width: x, height: ee } = Xt(r.width, r.height, p), O = document.createElement("canvas");
  O.width = x, O.height = ee;
  const T = O.getContext("2d");
  if (!T)
    throw r.close?.(), new De("Could not get 2D canvas context");
  return T.drawImage(r, 0, 0, x, ee), r.close?.(), O.toDataURL("image/jpeg", j);
}
var Zt = v('<p class="hint svelte-2684sp">Looking at your Home Assistant setup…</p>'), $t = v('<div><input type="checkbox" class="suggestion-toggle svelte-2684sp"/> <button class="suggestion-body svelte-2684sp"><div class="suggestion-main svelte-2684sp"><span class="suggestion-name svelte-2684sp"> </span> <span class="suggestion-count svelte-2684sp"> </span></div> <div class="suggestion-meta svelte-2684sp"><span class="suggestion-source svelte-2684sp"> </span> <span> </span></div></button></div>'), es = v('<div class="preview-map svelte-2684sp"><!></div>'), ts = v('<details class="inferred-rooms svelte-2684sp"><summary class="svelte-2684sp"> </summary> <p class="hint svelte-2684sp">Guessed from entity names — review before adding.</p> <div class="suggestion-list svelte-2684sp"></div></details>'), ss = v('<h2 class="svelte-2684sp">We found rooms in your Home Assistant setup</h2> <p class="hint svelte-2684sp">Toggle the rooms you want, preview the layout, then create it.</p> <!> <button class="primary strong create-all svelte-2684sp"> </button> <div class="suggestion-list svelte-2684sp"></div> <!> <div class="discovery-actions svelte-2684sp"><button class="button-secondary manual-add svelte-2684sp">+ Add room manually</button> <button class="button-secondary svelte-2684sp">Import RoomPlan scan</button></div>', 1), os = v('<p class="hint svelte-2684sp">No existing rooms found. Add your first room.</p> <div class="discovery-actions svelte-2684sp"><button class="primary svelte-2684sp">Add room manually</button> <button class="button-secondary svelte-2684sp">Import RoomPlan scan</button></div>', 1), as = v('<img alt="room" class="svelte-2684sp"/>'), ns = v("<option> </option>"), rs = v('<label class="area-label svelte-2684sp"><span>Area</span> <select class="area-select svelte-2684sp"><option> </option><!></select></label>'), is = v('<div class="thumbs svelte-2684sp"></div> <input class="name svelte-2684sp" type="text" placeholder="Room name (e.g. Living Room)"/> <!> <button class="primary svelte-2684sp"> </button>', 1), ls = v('<p class="err svelte-2684sp"> </p>'), cs = v('<h2 class="svelte-2684sp">Map a room</h2> <p class="hint svelte-2684sp">Take a few photos of one room from different corners.</p> <label class="drop-zone svelte-2684sp" for="room-photos"><input id="room-photos" class="sr-only" type="file" accept="image/*" multiple=""/> <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="drop-icon svelte-2684sp" aria-hidden="true"><path fill-rule="evenodd" d="M1.5 6a2.25 2.25 0 012.25-2.25h16.5A2.25 2.25 0 0122.5 6v12a2.25 2.25 0 01-2.25 2.25H3.75A2.25 2.25 0 011.5 18V6zM3 16.06V18c0 .414.336.75.75.75h16.5A.75.75 0 0021 18v-1.94l-2.69-2.689a1.5 1.5 0 00-2.12 0l-.88.879.97.97a.75.75 0 11-1.06 1.06l-5.47-5.47a1.5 1.5 0 00-2.12 0L3 16.06zm5.25-7.78a2.25 2.25 0 114.5 0 2.25 2.25 0 01-4.5 0z" clip-rule="evenodd"></path></svg> <span class="drop-title svelte-2684sp"> </span> <span class="drop-meta svelte-2684sp"> </span></label> <!> <!>', 1), ps = v('<p class="hint svelte-2684sp"> </p>'), ds = v('<h2 class="svelte-2684sp">Send to your Home Assistant AI?</h2> <p class="hint svelte-2684sp"> </p> <div class="actions svelte-2684sp"><button class="primary strong svelte-2684sp">Send to my AI setup</button> <button class="ghost svelte-2684sp">Keep on-device</button></div>', 1), vs = v('<h2 class="svelte-2684sp">Use cloud vision?</h2> <p class="hint svelte-2684sp"> </p> <div class="actions svelte-2684sp"><button class="primary strong svelte-2684sp">Send to vision service</button> <button class="ghost svelte-2684sp">Keep on-device</button></div>', 1), us = v('<span class="chip svelte-2684sp"> </span>'), gs = v('<div class="suggestion svelte-2684sp"><strong> </strong> <span class="svelte-2684sp"> </span></div>'), ms = v('<p class="warn svelte-2684sp"> </p>'), hs = v('<p class="hint privacy-note svelte-2684sp"> </p>'), fs = v('<p class="hint estimate-note svelte-2684sp">The room outline is an estimate from the photos and name — you can edit it later.</p>'), _s = v('<p class="err svelte-2684sp"> </p>'), xs = v('<h2 class="svelte-2684sp"> </h2> <div class="success-layer svelte-2684sp"><p class="understanding svelte-2684sp"> </p> <div class="chips svelte-2684sp"></div> <!></div> <!> <!> <!> <button class="primary strong svelte-2684sp">Map my room</button> <!>', 1), bs = v('<p class="hint svelte-2684sp">Saving…</p>'), ys = v('<p class="understanding svelte-2684sp"> </p>'), ws = v('<label class="svelte-2684sp"><input type="checkbox"/> </label>'), ks = v('<div class="picker-section svelte-2684sp">In this area</div> <!>', 1), zs = v('<label class="svelte-2684sp"><input type="checkbox"/> </label>'), Rs = v('<div class="picker-section svelte-2684sp">Other lights</div> <!>', 1), Ss = v('<p class="hint svelte-2684sp">Save the current lights in this room as a one-tap scene:</p> <div class="picker svelte-2684sp"><!> <!></div> <div class="actions svelte-2684sp"><button class="primary svelte-2684sp">Create the scene</button> <button class="ghost svelte-2684sp">Skip</button></div>', 1), Is = v('<p class="hint svelte-2684sp">No lights here yet — add some devices and you can save a scene next time.</p> <button class="primary svelte-2684sp">Done</button>', 1), As = v('<p class="err svelte-2684sp"> </p>'), Cs = v('<h2 class="svelte-2684sp">Mapped ✓</h2> <!> <!> <!>', 1), Ps = v('<div class="success-layer svelte-2684sp"><p class="understanding svelte-2684sp"> </p> <p class="hint svelte-2684sp"> </p></div> <input class="name svelte-2684sp" type="text" placeholder="Room name"/> <button class="primary strong svelte-2684sp">Import this room</button>', 1), Ls = v('<p class="err svelte-2684sp"> </p>'), Hs = v(
  `<h2 class="svelte-2684sp">Import a RoomPlan scan</h2> <p class="hint svelte-2684sp">Upload a <code>forge_roomplan_import</code> JSON file from the Forge exporter. The raw
      photo data is not in this file — only the room outline and ceiling height.</p> <input type="file" accept=".json,application/json"/> <!> <!> <button class="ghost svelte-2684sp">Back</button>`,
  1
), Ds = v('<p class="hint done svelte-2684sp">Mapped ✓ Your home just got a little smarter.</p>'), Es = v('<div class="capture svelte-2684sp"><!></div>');
const Vs = {
  hash: "svelte-2684sp",
  code: `.capture.svelte-2684sp {padding:24px;max-width:520px;margin:0 auto;font-family:'Instrument Sans', system-ui, sans-serif;color:#111827;}h2.svelte-2684sp {font-size:22px;font-weight:600;margin:0 0 4px;}.hint.svelte-2684sp {color:#6b7280;font-size:15px;}.hint.done.svelte-2684sp {color:#047857;font-weight:600;}.thumbs.svelte-2684sp {display:flex;gap:8px;flex-wrap:wrap;margin:12px 0;}.thumbs.svelte-2684sp img:where(.svelte-2684sp) {width:72px;height:72px;-o-object-fit:cover;object-fit:cover;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.12);}.name.svelte-2684sp {display:block;width:100%;margin:8px 0 12px;padding:10px 12px;font-size:16px;border:1px solid #e5e7eb;border-radius:12px;}.drop-zone.svelte-2684sp {display:flex;flex-direction:column;align-items:center;gap:6px;padding:28px 20px;margin:12px 0 16px;border:2px dashed #d1d5db;border-radius:16px;background:#f9fafb;color:#374151;cursor:pointer;transition:border-color 180ms ease-out, background 180ms ease-out;}.drop-zone.svelte-2684sp:hover {border-color:#10b981;background:#f0fdf4;}.drop-icon.svelte-2684sp {width:32px;height:32px;color:#10b981;}.drop-title.svelte-2684sp {font-size:15px;font-weight:600;}.drop-meta.svelte-2684sp {font-size:13px;color:#6b7280;}.area-label.svelte-2684sp {display:flex;align-items:center;gap:10px;margin:-4px 0 14px;font-size:14px;color:#6b7280;}.area-select.svelte-2684sp {flex:1;padding:8px 10px;font-size:14px;border:1px solid #e5e7eb;border-radius:10px;background:#fff;color:#374151;}.primary.svelte-2684sp {background:#10b981;color:#ffffff;border:1px solid #10b981;border-radius:9999px;padding:11px 22px;font-size:15px;font-weight:600;cursor:pointer;min-height:44px;transition:background 180ms ease-out, box-shadow 200ms ease-out;}.primary.svelte-2684sp:hover {background:#059669;}.primary.svelte-2684sp:disabled {opacity:0.6;cursor:default;}.button-secondary.svelte-2684sp {background:#fff;color:#374151;border:1px solid #e5e7eb;border-radius:9999px;padding:11px 22px;font-size:15px;font-weight:600;cursor:pointer;min-height:44px;transition:background 180ms ease-out;}.button-secondary.svelte-2684sp:hover {background:#f9fafb;}.manual-add.svelte-2684sp {margin-top:12px;}.discovery-actions.svelte-2684sp {display:flex;flex-wrap:wrap;gap:10px;margin-top:12px;}.create-all.svelte-2684sp {width:100%;margin:4px 0 12px;}.estimate-note.svelte-2684sp {font-size:13px;color:#6b7280;margin:-8px 0 12px;}
  /* Strongest emerald ring at the moment of choice (DESIGN.md ring-emerald-500). */.primary.strong.svelte-2684sp {box-shadow:0 0 0 2px #10b981;}
  /* Layer 0 success container: emerald-50 base + emerald-200 border, revealing
     in 180-250ms ease-out. Holds the understanding (layer 2 text) + the nested
     suggestion (layer 1) so the emerald system reads as layered, not flat. */.success-layer.svelte-2684sp {background:#ecfdf5;border:1px solid #a7f3d0;border-radius:16px;padding:16px;margin:8px 0 16px; animation: svelte-2684sp-success-reveal 220ms ease-out;}
  @keyframes svelte-2684sp-success-reveal { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }.understanding.svelte-2684sp {color:#065f46;font-size:16px;line-height:1.4;margin:0 0 10px;}.chips.svelte-2684sp {display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px;}.chip.svelte-2684sp {font-size:12px;background:#d1fae5;color:#047857;border-radius:9999px;padding:3px 10px;}.suggestion.svelte-2684sp {display:flex;flex-direction:column;gap:2px;background:#ffffff;border:1px solid #bbf7d0;border-radius:12px;padding:12px;margin-bottom:0;}.suggestion.svelte-2684sp span:where(.svelte-2684sp) {color:#6b7280;font-size:13px;}.err.svelte-2684sp {color:#be123c;font-size:13px;}.warn.svelte-2684sp {color:#b45309;font-size:13px;background:#fffbeb;padding:8px 10px;border-radius:8px;border:1px solid #fde68a;}.picker.svelte-2684sp {display:flex;flex-direction:column;gap:6px;margin:8px 0 16px;max-height:220px;overflow:auto;}.picker-section.svelte-2684sp {font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#9ca3af;padding:6px 0 2px;}.picker.svelte-2684sp label:where(.svelte-2684sp) {display:flex;align-items:center;gap:8px;font-size:14px;color:#374151;}.preview-map.svelte-2684sp {width:100%;height:200px;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;margin:8px 0 16px;background:#f9fafb;}.suggestion-list.svelte-2684sp {display:flex;flex-direction:column;gap:10px;margin:16px 0;max-height:360px;overflow:auto;padding-right:4px;}.suggestion-card.svelte-2684sp {display:flex;align-items:center;gap:12px;text-align:left;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:12px 14px;transition:border-color 180ms ease-out, box-shadow 180ms ease-out;}.suggestion-card.svelte-2684sp:has(.suggestion-toggle:where(.svelte-2684sp):checked) {border-color:#a7f3d0;background:#f6fdf9;}.suggestion-card.guess.svelte-2684sp {border-style:dashed;}.inferred-rooms.svelte-2684sp {margin-top:4px;}.inferred-rooms.svelte-2684sp > summary:where(.svelte-2684sp) {cursor:pointer;font-size:13px;font-weight:600;color:#374151;padding:8px 0;list-style:none;}.inferred-rooms.svelte-2684sp > summary:where(.svelte-2684sp)::before {content:'▸';display:inline-block;margin-right:8px;transition:transform 180ms ease-out;}.inferred-rooms[open].svelte-2684sp > summary:where(.svelte-2684sp)::before {transform:rotate(90deg);}.inferred-rooms.svelte-2684sp .hint:where(.svelte-2684sp) {margin-top:0;margin-bottom:8px;}.suggestion-toggle.svelte-2684sp {flex:0 0 auto;width:18px;height:18px;accent-color:#10b981;cursor:pointer;}.suggestion-body.svelte-2684sp {flex:1 1 auto;display:flex;flex-direction:column;gap:6px;background:none;border:none;padding:0;margin:0;text-align:left;cursor:pointer;}.suggestion-body.svelte-2684sp:hover .suggestion-name:where(.svelte-2684sp) {color:#047857;}.suggestion-main.svelte-2684sp {display:flex;align-items:baseline;justify-content:space-between;gap:8px;}.suggestion-name.svelte-2684sp {font-size:16px;font-weight:600;color:#111827;transition:color 120ms ease-out;}.suggestion-count.svelte-2684sp {font-size:13px;color:#6b7280;}.suggestion-meta.svelte-2684sp {display:flex;align-items:center;justify-content:space-between;gap:8px;}.suggestion-source.svelte-2684sp {font-size:12px;color:#6b7280;}.suggestion-confidence.svelte-2684sp {font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;padding:2px 8px;border-radius:9999px;}.confidence-high.svelte-2684sp {background:#d1fae5;color:#047857;}.confidence-medium.svelte-2684sp {background:#fef3c7;color:#b45309;}.confidence-low.svelte-2684sp {background:#fee2e2;color:#be123c;}.actions.svelte-2684sp {display:flex;gap:10px;align-items:center;}.ghost.svelte-2684sp {background:none;border:none;color:#6b7280;font-size:14px;cursor:pointer;}`
};
function Ws(w, p) {
  St(p, !0), It(w, Vs);
  let j = At(p, "states", 19, () => ({})), r = C("discover"), x = C(ve([])), ee = C(
    !1
    // dims computed → safe to analyze (no zeroed-dim race)
  ), O = [], T = [], fe = 0, I = C(""), B = C(null), u = C(null), W = C(null), N = C(ve({})), le = null, Y = C(null), ke = C(null), ze = C(2.5), ue = C(null), ge = C(ve([])), X = C(null), Re = C(!1), me = C(ve([])), Z = C(ve([])), ae = C(ve({})), _e = C(320), xe = C(200), Ee = C(!0), Se = C(null);
  const be = oe(() => e(Z).length ? Ut(e(Z).filter((t) => e(ae)[t.name] !== !1).map((t) => ({ name: t.name, area_id: t.area_id, floor_id: t.floor_id }))) : null), Ve = oe(() => e(be) && e(_e) > 0 && e(xe) > 0 ? jt(e(be), e(_e), e(xe), 16) : null);
  function je(t) {
    return t.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  }
  Le(() => {
    Kt(p.connection).then((t) => {
      s(Se, t, !0);
    }), Promise.all([
      Ct(p.connection).then((t) => {
        s(ge, t.areas, !0);
      }),
      Pt(p.connection).then((t) => {
        s(Z, t.suggestions, !0), s(ae, Object.fromEntries(e(Z).map((o) => [o.name, !0])), !0);
      }).catch(() => {
        s(Z, [], !0), s(ae, {}, !0);
      })
    ]).catch(() => {
    }).finally(() => {
      s(Ee, !1), e(Z).length > 0 ? $(p.connection, "rooms_suggested") : e(r) === "discover" && s(r, "capture");
    });
  }), Le(() => {
    if (e(Re) || !e(I).trim() || e(ge).length === 0) return;
    const t = je(e(I)), o = e(ge).find((c) => je(c.name) === t);
    s(X, o?.areaId ?? null, !0);
  }), Le(() => {
    if (!e(X)) {
      s(me, [], !0);
      return;
    }
    Lt(p.connection, e(X)).then((t) => {
      s(me, t.entity_ids.filter((o) => o.startsWith("light.")), !0);
    }).catch(() => {
      s(me, [], !0);
    });
  });
  const ce = oe(() => Object.keys(j()).filter((t) => t.startsWith("light.")).sort()), ne = oe(() => e(me).filter((t) => e(ce).includes(t))), Me = oe(() => e(ce).filter((t) => !e(ne).includes(t)));
  function Oe() {
    for (const t of e(x)) URL.revokeObjectURL(t);
  }
  Ht(Oe);
  function st(t) {
    return new Promise((o) => {
      const c = new Image(), b = URL.createObjectURL(t), k = (L) => {
        URL.revokeObjectURL(b), o(L);
      };
      c.onload = () => k({ width: c.naturalWidth, height: c.naturalHeight }), c.onerror = () => k({ width: 0, height: 0 }), c.src = b;
    });
  }
  async function ot(t) {
    const o = Array.from(t.target.files ?? []);
    if (!o.length) return;
    Oe(), s(ee, !1), O = o, s(x, o.map((k) => URL.createObjectURL(k)), !0);
    const c = ++fe;
    $(p.connection, "capture_started");
    const b = await Promise.all(o.map(st));
    c === fe && (T = b, s(ee, !0));
  }
  function ye() {
    const t = T.length, o = t ? T.reduce((b, k) => b + k.width, 0) / t : 0, c = t ? T.reduce((b, k) => b + k.height, 0) / t : 0;
    return {
      photo_count: t,
      avg_aspect: o && c ? o / c : 1,
      is_high_quality_set: t >= 5 && o >= 2e3 && c >= 1500
    };
  }
  async function Ie() {
    return Yt(Gt({
      photoFiles: O,
      imageDimensions: T,
      roomHint: e(I) || void 0
    }));
  }
  function pe(t) {
    s(B, t, !0), !e(I) && t.suggestedRoomName && s(I, t.suggestedRoomName, !0);
    const o = ye(), c = Ge(e(I).trim() || t.suggestedRoomName || "Room", o.avg_aspect);
    s(ke, c.polygon, !0), s(ze, c.height, !0), s(ue, "estimate"), s(r, "result");
  }
  function at(t) {
    s(I, t.name, !0), s(X, t.area_id ?? null, !0), s(Re, !0), s(me, t.entity_ids.filter((o) => o.startsWith("light.")), !0), $(p.connection, "room_suggestion_selected"), s(r, "capture");
  }
  function We() {
    $(p.connection, "capture_started"), s(r, "capture");
  }
  const nt = oe(() => e(Z).filter((t) => t.source !== "entity_pattern")), Ae = oe(() => e(Z).filter((t) => t.source === "entity_pattern")), Ce = oe(() => e(Z).filter((t) => t.source === "entity_pattern" ? e(ae)[t.name] === !0 : e(ae)[t.name] !== !1)), rt = oe(() => e(be)?.rooms.reduce(
    (t, o) => {
      const c = o.name;
      return o.origin && (t[c] = { origin: o.origin, rotation: o.rotation ?? 0 }), t;
    },
    {}
  ) ?? {});
  async function it() {
    if (e(Ce).length) {
      s(r, "saving"), s(u, null);
      try {
        await Ot(p.connection, e(Ce).map((t) => ({ name: t.name, areaId: t.area_id, floorId: t.floor_id })), e(rt)), $(p.connection, "room_mapped"), he();
      } catch (t) {
        s(u, t?.message ?? t?.code ?? "Could not create the layout.", !0), s(r, "discover");
      }
    }
  }
  function Ne() {
    le = null, s(Y, null), s(I, ""), s(u, null), s(r, "roomplan");
  }
  async function lt(t) {
    const o = t.target.files?.[0] ?? null;
    if (le = o ?? null, s(Y, null), s(u, null), !!o) {
      $(p.connection, "roomplan_import_started");
      try {
        const c = await o.text(), b = JSON.parse(c);
        s(Y, Bt(b), !0), s(I, e(Y).name ?? "", !0), s(ke, e(Y).polygon, !0), s(ze, e(Y).height, !0), s(ue, "roomplan");
      } catch (c) {
        c instanceof Jt ? s(u, c.message, !0) : c instanceof SyntaxError ? s(u, "This file is not valid JSON.") : s(u, "Could not read this scan file.");
      }
    }
  }
  async function ct() {
    if (!(!le || !e(Y))) {
      s(r, "saving"), s(u, null);
      try {
        const t = await le.text(), o = JSON.parse(t);
        await Nt(p.connection, o), $(p.connection, "roomplan_import_succeeded"), s(
          N,
          Object.fromEntries(e(ce).map((c) => [
            c,
            e(ne).length ? e(ne).includes(c) : !0
          ])),
          !0
        ), s(r, "suggest");
      } catch (t) {
        $(p.connection, "roomplan_import_failed"), s(u, t?.message ?? t?.error ?? "Could not import the RoomPlan scan.", !0), s(r, "roomplan");
      }
    }
  }
  async function pt() {
    s(r, "analyzing"), s(u, null), s(W, null);
    try {
      if (e(Se) === "local") {
        const t = await Promise.all(O.map((o) => et(o)));
        pe(await He(p.connection, {
          signals: ye(),
          roomHint: e(I) || void 0,
          photos: t
        }));
        return;
      }
      pe(await He(p.connection, {
        signals: ye(),
        roomHint: e(I) || void 0
      }));
    } catch (t) {
      if (t instanceof tt) {
        s(r, "consent");
        return;
      }
      if (t instanceof De) {
        s(u, `Could not prepare photo: ${t.message}`), s(r, "capture");
        return;
      }
      s(W, "Could not reach the vision service. Showing an on-device estimate instead."), pe(await Ie());
    }
  }
  async function Ue() {
    s(r, "analyzing"), s(u, null), s(W, null);
    try {
      const t = await Promise.all(O.map((o) => et(o)));
      pe(await He(p.connection, {
        signals: ye(),
        roomHint: e(I) || void 0,
        photos: t,
        consent: !0
      }));
    } catch (t) {
      if (t instanceof De) {
        s(u, `Could not prepare photo: ${t.message}`), s(r, "capture");
        return;
      }
      s(W, "Cloud vision failed. Showing an on-device estimate instead."), pe(await Ie());
    }
  }
  async function Fe() {
    s(r, "analyzing"), pe(await Ie());
  }
  async function dt() {
    s(r, "saving"), s(u, null);
    try {
      const t = e(ke) ?? Ge(e(I).trim() || "My Room").polygon;
      await Et(p.connection, {
        name: e(I).trim() || "My Room",
        polygon: t,
        height: e(ze),
        areaId: e(X),
        metadata: e(ue) ? { source: e(ue) } : void 0
      }), $(p.connection, "room_mapped"), s(
        N,
        Object.fromEntries(e(ce).map((o) => [
          o,
          e(ne).length ? e(ne).includes(o) : !0
        ])),
        !0
      ), s(r, "suggest");
    } catch (t) {
      s(u, t?.message ?? t?.code ?? "Could not save the room.", !0), s(r, "result");
    }
  }
  async function vt() {
    const t = e(ce).filter((o) => e(N)[o]);
    if (!t.length) {
      he();
      return;
    }
    s(r, "saving"), s(u, null);
    try {
      await Wt(p.connection, { name: `${e(I).trim() || "Room"} scene`, entityIds: t }), $(p.connection, "suggestion_accepted"), he();
    } catch (o) {
      s(u, o?.message ?? o?.code ?? "Could not create the scene.", !0), s(r, "suggest");
    }
  }
  function he() {
    s(r, "done"), p.onmapped();
  }
  var Te = Es(), ut = i(Te);
  {
    var gt = (t) => {
      var o = qe(), c = M(o);
      {
        var b = (z) => {
          var A = Zt();
          d(z, A);
        }, k = (z) => {
          const A = (l, n = Qe, _ = Qe) => {
            var m = $t();
            let D;
            var E = i(m), q = a(E, 2), se = i(q), G = i(se), re = i(G), de = a(G, 2), Pe = i(de), we = a(se, 2), Be = i(we), kt = i(Be), Je = a(Be, 2), zt = i(Je);
            y(() => {
              D = Xe(m, 1, "suggestion-card svelte-2684sp", null, D, { guess: !_() }), Mt(E, _() ? e(ae)[n().name] !== !1 : e(ae)[n().name] === !0), Ye(E, "aria-label", `Include ${n().name}`), f(re, n().name), f(Pe, `${n().entity_ids.length ?? ""} entities`), f(kt, n().reason), Xe(Je, 1, `suggestion-confidence confidence-${n().confidence ?? ""}`, "svelte-2684sp"), f(zt, n().confidence);
            }), P("change", E, (Rt) => {
              e(ae)[n().name] = Rt.currentTarget.checked;
            }), P("click", q, () => at(n())), d(l, m);
          };
          var R = ss(), g = a(M(R), 4);
          {
            var h = (l) => {
              var n = es(), _ = i(n);
              qt(_, {
                get layout() {
                  return e(be);
                },
                get baseViewport() {
                  return e(Ve);
                },
                get width() {
                  return e(_e);
                },
                get height() {
                  return e(xe);
                },
                activeFloorLevel: 0,
                disabled: !0,
                showControls: !1,
                showScaleBar: !1,
                showStatusBar: !1
              }), Ze(n, "clientWidth", (m) => s(_e, m)), Ze(n, "clientHeight", (m) => s(xe, m)), d(l, n);
            };
            H(g, (l) => {
              e(Ve) && l(h);
            });
          }
          var S = a(g, 2), V = i(S), U = a(S, 2);
          ie(U, 21, () => e(nt), (l) => l.name, (l, n) => {
            A(l, () => e(n), () => !0);
          });
          var F = a(U, 2);
          {
            var K = (l) => {
              var n = ts(), _ = i(n), m = i(_), D = a(_, 4);
              ie(D, 21, () => e(Ae), (E) => E.name, (E, q) => {
                A(E, () => e(q), () => !1);
              }), y(() => f(m, `Inferred rooms (${e(Ae).length ?? ""})`)), d(l, n);
            };
            H(F, (l) => {
              e(Ae).length && l(K);
            });
          }
          var Q = a(F, 2), J = i(Q), te = a(J, 2);
          y(() => f(V, `Create layout from selected rooms (${e(Ce).length ?? ""})`)), P("click", S, it), P("click", J, We), P("click", te, Ne), d(z, R);
        }, L = (z) => {
          var A = os(), R = a(M(A), 2), g = i(R), h = a(g, 2);
          P("click", g, We), P("click", h, Ne), d(z, A);
        };
        H(c, (z) => {
          e(Ee) ? z(b) : e(Z).length ? z(k, 1) : z(L, -1);
        });
      }
      d(t, o);
    }, mt = (t) => {
      var o = cs(), c = a(M(o), 4), b = i(c), k = a(b, 4), L = i(k), z = a(k, 2), A = i(z), R = a(c, 2);
      {
        var g = (V) => {
          var U = is(), F = M(U);
          ie(F, 20, () => e(x), (n) => n, (n, _) => {
            var m = as();
            y(() => Ye(m, "src", _)), d(n, m);
          });
          var K = a(F, 2), Q = a(K, 2);
          {
            var J = (n) => {
              var _ = rs(), m = a(i(_), 2), D = i(m), E = i(D);
              D.value = D.__value = "";
              var q = a(D);
              ie(q, 17, () => e(ge), (G) => G.areaId, (G, re) => {
                var de = ns(), Pe = i(de), we = {};
                y(() => {
                  f(Pe, e(re).name), we !== (we = e(re).areaId) && (de.value = (de.__value = e(re).areaId) ?? "");
                }), d(G, de);
              });
              var se;
              Ft(m), y(() => {
                f(E, e(X) ? "Unmatched — no area" : "Auto-match by name"), se !== (se = e(X) ?? "") && (m.value = (m.__value = e(X) ?? "") ?? "", Tt(m, e(X) ?? ""));
              }), P("change", m, (G) => {
                const re = G.currentTarget.value;
                s(X, re || null, !0), s(Re, !0);
              }), d(n, _);
            };
            H(Q, (n) => {
              e(ge).length && n(J);
            });
          }
          var te = a(Q, 2), l = i(te);
          y(() => {
            te.disabled = !e(ee), f(l, e(ee) ? "Understand my room" : "Reading photos…");
          }), Ke(K, () => e(I), (n) => s(I, n)), P("click", te, pt), d(V, U);
        };
        H(R, (V) => {
          e(x).length && V(g);
        });
      }
      var h = a(R, 2);
      {
        var S = (V) => {
          var U = ls(), F = i(U);
          y(() => f(F, e(u))), d(V, U);
        };
        H(h, (V) => {
          e(u) && V(S);
        });
      }
      y(() => {
        f(L, e(x).length ? "Add more photos" : "Choose photos"), f(A, e(x).length ? `${e(x).length} selected` : "JPG or PNG, up to 6 photos");
      }), P("change", b, ot), d(t, o);
    }, ht = (t) => {
      var o = ps(), c = i(o);
      y(() => f(c, `Studying your ${e(x).length ?? ""} photo${e(x).length === 1 ? "" : "s"}…`)), d(t, o);
    }, ft = (t) => {
      var o = qe(), c = M(o);
      {
        var b = (L) => {
          var z = ds(), A = a(M(z), 2), R = i(A), g = a(A, 2), h = i(g), S = a(h, 2);
          y(() => f(R, `To really understand this room, your ${e(x).length ?? ""} photo${e(x).length === 1 ? "" : "s"}
        would be sent once to the AI task provider configured in your Home Assistant — which may be
        a cloud provider. Or keep everything on this device.`)), P("click", h, Ue), P("click", S, Fe), d(L, z);
        }, k = (L) => {
          var z = vs(), A = a(M(z), 2), R = i(A), g = a(A, 2), h = i(g), S = a(h, 2);
          y(() => f(R, `To really understand this room, your ${e(x).length ?? ""} photo${e(x).length === 1 ? "" : "s"}
        would be sent once to the configured vision service for this analysis. Or keep everything on this device.`)), P("click", h, Ue), P("click", S, Fe), d(L, z);
        };
        H(c, (L) => {
          e(Se) === "local" ? L(b) : L(k, -1);
        });
      }
      d(t, o);
    }, _t = (t) => {
      var o = xs(), c = M(o), b = i(c), k = a(c, 2), L = i(k), z = i(L), A = a(L, 2);
      ie(A, 20, () => e(B).noticed, (l) => l, (l, n) => {
        var _ = us(), m = i(_);
        y(() => f(m, n)), d(l, _);
      });
      var R = a(A, 2);
      {
        var g = (l) => {
          var n = gs(), _ = i(n), m = i(_), D = a(_, 2), E = i(D);
          y(() => {
            f(m, e(B).recommendations[0].title), f(E, e(B).recommendations[0].rationale);
          }), d(l, n);
        };
        H(R, (l) => {
          e(B).recommendations.length && l(g);
        });
      }
      var h = a(k, 2);
      {
        var S = (l) => {
          var n = ms(), _ = i(n);
          y(() => f(_, e(W))), d(l, n);
        };
        H(h, (l) => {
          e(W) && l(S);
        });
      }
      var V = a(h, 2);
      {
        var U = (l) => {
          var n = hs(), _ = i(n);
          y((m) => f(_, m), [() => Qt(e(B).egressClass)]), d(l, n);
        };
        H(V, (l) => {
          e(B).egressClass && l(U);
        });
      }
      var F = a(V, 2);
      {
        var K = (l) => {
          var n = fs();
          d(l, n);
        };
        H(F, (l) => {
          e(ue) === "estimate" && l(K);
        });
      }
      var Q = a(F, 2), J = a(Q, 2);
      {
        var te = (l) => {
          var n = _s(), _ = i(n);
          y(() => f(_, e(u))), d(l, n);
        };
        H(J, (l) => {
          e(u) && l(te);
        });
      }
      y(() => {
        f(b, e(I) || "Your room"), f(z, e(B).understanding);
      }), P("click", Q, dt), d(t, o);
    }, xt = (t) => {
      var o = bs();
      d(t, o);
    }, bt = (t) => {
      var o = Cs(), c = a(M(o), 2);
      {
        var b = (g) => {
          var h = ys(), S = i(h);
          y(() => f(S, e(B).recommendations[0].title)), d(g, h);
        };
        H(c, (g) => {
          e(B)?.recommendations.length && g(b);
        });
      }
      var k = a(c, 2);
      {
        var L = (g) => {
          var h = Ss(), S = a(M(h), 2), V = i(S);
          {
            var U = (l) => {
              var n = ks(), _ = a(M(n), 2);
              ie(_, 16, () => e(ne), (m) => m, (m, D) => {
                var E = ws(), q = i(E), se = a(q);
                y(() => f(se, ` ${D ?? ""}`)), $e(q, () => e(N)[D], (G) => e(N)[D] = G), d(m, E);
              }), d(l, n);
            };
            H(V, (l) => {
              e(ne).length && l(U);
            });
          }
          var F = a(V, 2);
          {
            var K = (l) => {
              var n = Rs(), _ = a(M(n), 2);
              ie(_, 16, () => e(Me), (m) => m, (m, D) => {
                var E = zs(), q = i(E), se = a(q);
                y(() => f(se, ` ${D ?? ""}`)), $e(q, () => e(N)[D], (G) => e(N)[D] = G), d(m, E);
              }), d(l, n);
            };
            H(F, (l) => {
              e(Me).length && l(K);
            });
          }
          var Q = a(S, 2), J = i(Q), te = a(J, 2);
          P("click", J, vt), P("click", te, he), d(g, h);
        }, z = (g) => {
          var h = Is(), S = a(M(h), 2);
          P("click", S, he), d(g, h);
        };
        H(k, (g) => {
          e(ce).length ? g(L) : g(z, -1);
        });
      }
      var A = a(k, 2);
      {
        var R = (g) => {
          var h = As(), S = i(h);
          y(() => f(S, e(u))), d(g, h);
        };
        H(A, (g) => {
          e(u) && g(R);
        });
      }
      d(t, o);
    }, yt = (t) => {
      var o = Hs(), c = a(M(o), 4), b = a(c, 2);
      {
        var k = (R) => {
          var g = Ps(), h = M(g), S = i(h), V = i(S), U = a(S, 2), F = i(U), K = a(h, 2), Q = a(K, 2);
          y(
            (J) => {
              f(V, e(Y).name || "Scanned room"), f(F, `${e(Y).polygon.length ?? ""} corners · ceiling ${J ?? ""} m`);
            },
            [() => e(Y).height.toFixed(2)]
          ), Ke(K, () => e(I), (J) => s(I, J)), P("click", Q, ct), d(R, g);
        };
        H(b, (R) => {
          e(Y) && R(k);
        });
      }
      var L = a(b, 2);
      {
        var z = (R) => {
          var g = Ls(), h = i(g);
          y(() => f(h, e(u))), d(R, g);
        };
        H(L, (R) => {
          e(u) && R(z);
        });
      }
      var A = a(L, 2);
      P("change", c, lt), P("click", A, () => {
        s(r, "discover");
      }), d(t, o);
    }, wt = (t) => {
      var o = Ds();
      d(t, o);
    };
    H(ut, (t) => {
      e(r) === "discover" ? t(gt) : e(r) === "capture" ? t(mt, 1) : e(r) === "analyzing" ? t(ht, 2) : e(r) === "consent" ? t(ft, 3) : e(r) === "result" && e(B) ? t(_t, 4) : e(r) === "saving" ? t(xt, 5) : e(r) === "suggest" ? t(bt, 6) : e(r) === "roomplan" ? t(yt, 7) : e(r) === "done" && t(wt, 8);
    });
  }
  d(w, Te), Dt();
}
Vt(["change", "click"]);
export {
  Ws as default
};
