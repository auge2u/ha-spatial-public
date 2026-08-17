import { K as M, b as U, w as _, v as e, a as m, G as W, X as k, g as u, W as v, r as I, o as S, Z as w, U as R, f as Y, P as o, u as f, a0 as B, F as G, k as K, B as V, n as X } from "./ha-spatial-panel-D1fnh84z.js";
import { R as j, p as Z } from "./ha-spatial-panel-roomplan-import-Dv5pN-IS.js";
var D = f('<p class="err svelte-6qyrke"> </p>'), H = f(
  `<h2 class="svelte-6qyrke">Import a room scan</h2> <p class="hint svelte-6qyrke">Upload a <code class="svelte-6qyrke">forge_roomplan_import</code> <code class="svelte-6qyrke">.json</code> file. The geometry is
      read on this device; nothing is uploaded anywhere.</p> <p class="hint honest svelte-6qyrke">Exporting straight from Apple's RoomPlan app isn't wired up yet, so a raw RoomPlan
      file won't import. For now this reads a <code class="svelte-6qyrke">forge_roomplan_import</code> file
      (see <code class="svelte-6qyrke">docs/roomplan-import-format.md</code>). Real-scan export is coming.</p> <input type="file" accept="application/json,.json"/> <!>`,
  1
), Q = f('<p class="err svelte-6qyrke"> </p>'), $ = f('<h2 class="svelte-6qyrke">Looks like a room</h2> <div class="success-layer svelte-6qyrke"><p class="understanding svelte-6qyrke"> </p> <input class="name svelte-6qyrke" type="text" placeholder="Room name (e.g. Living Room)"/></div> <button class="primary strong svelte-6qyrke">Add this room</button> <p class="hint small svelte-6qyrke">One room per import for now — position it relative to others in a later step.</p> <!>', 1), ee = f('<p class="hint svelte-6qyrke">Saving…</p>'), re = f('<div class="import svelte-6qyrke"><!></div>');
const oe = {
  hash: "svelte-6qyrke",
  code: `.import.svelte-6qyrke {padding:24px;max-width:520px;margin:0 auto;font-family:'Instrument Sans', system-ui, sans-serif;color:#111827;}h2.svelte-6qyrke {font-size:22px;font-weight:600;margin:0 0 4px;}.hint.svelte-6qyrke {color:#6b7280;font-size:15px;}.hint.small.svelte-6qyrke {font-size:13px;margin-top:10px;}.hint.honest.svelte-6qyrke {font-size:13px;color:#6b7280;background:#f9fafb;border-left:3px solid #e5e7eb;border-radius:0 8px 8px 0;padding:10px 12px;margin:12px 0;}code.svelte-6qyrke {background:#f3f4f6;border-radius:4px;padding:1px 5px;font-size:13px;}.success-layer.svelte-6qyrke {background:#ecfdf5;border:1px solid #a7f3d0;border-radius:16px;padding:16px;margin:12px 0 16px; animation: svelte-6qyrke-success-reveal 220ms ease-out;}
  @keyframes svelte-6qyrke-success-reveal { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }.understanding.svelte-6qyrke {color:#065f46;font-size:16px;line-height:1.4;margin:0 0 10px;}.name.svelte-6qyrke {display:block;width:100%;padding:10px 12px;font-size:16px;border:1px solid #e5e7eb;border-radius:12px;}.primary.svelte-6qyrke {background:#10b981;color:#ffffff;border:1px solid #10b981;border-radius:9999px;padding:11px 22px;font-size:15px;font-weight:600;cursor:pointer;min-height:44px;transition:background 180ms ease-out, box-shadow 200ms ease-out;}.primary.svelte-6qyrke:hover {background:#059669;}.primary.strong.svelte-6qyrke {box-shadow:0 0 0 2px #10b981;}.err.svelte-6qyrke {color:#be123c;font-size:13px;}`
};
function ae(z, y) {
  M(y, !0), U(z, oe);
  let c = k("pick"), t = k(null), h = k(""), n = k(null), b = 0;
  const A = B(() => e(t) ? Math.abs(G(e(t).polygon)) : 0);
  async function P(r) {
    const s = r.target.files?.[0];
    if (!s) return;
    o(n, null);
    const i = ++b;
    try {
      const a = await s.text();
      if (i !== b) return;
      let d;
      try {
        d = JSON.parse(a);
      } catch {
        throw new j("malformed", "That file isn't valid JSON.");
      }
      const l = Z(d);
      o(t, l, !0), o(h, l.name ?? "", !0), o(c, "confirm");
    } catch (a) {
      if (i !== b) return;
      o(n, a instanceof j ? a.message : "Could not read this scan.", !0), o(t, null);
    }
  }
  async function E() {
    if (e(t)) {
      o(c, "saving"), o(n, null);
      try {
        await K(y.connection, {
          name: e(h).trim() || "Imported Room",
          polygon: e(t).polygon,
          height: e(t).height
        }), V(y.connection, "room_mapped"), y.onmapped();
      } catch (r) {
        o(
          n,
          r?.code === "self_intersecting" ? "This room outline crosses itself." : r?.message ?? r?.code ?? "Could not save the room.",
          !0
        ), o(c, "confirm");
      }
    }
  }
  var F = re(), N = u(F);
  {
    var O = (r) => {
      var s = H(), i = v(I(s), 6), a = v(i, 2);
      {
        var d = (l) => {
          var g = D(), q = u(g);
          w(() => R(q, e(n))), m(l, g);
        };
        _(a, (l) => {
          e(n) && l(d);
        });
      }
      S("change", i, P), m(r, s);
    }, T = (r) => {
      var s = $(), i = v(I(s), 2), a = u(i), d = u(a), l = v(a, 2), g = v(i, 2), q = v(g, 4);
      {
        var J = (p) => {
          var x = Q(), L = u(x);
          w(() => R(L, e(n))), m(p, x);
        };
        _(q, (p) => {
          e(n) && p(J);
        });
      }
      w((p, x) => R(d, `A ${e(t).polygon.length ?? ""}-corner outline, ${p ?? ""} m², ${x ?? ""} m ceiling.`), [
        () => e(A).toFixed(1),
        () => e(t).height.toFixed(2)
      ]), Y(l, () => e(h), (p) => o(h, p)), S("click", g, E), m(r, s);
    }, C = (r) => {
      var s = ee();
      m(r, s);
    };
    _(N, (r) => {
      e(c) === "pick" ? r(O) : e(c) === "confirm" && e(t) ? r(T, 1) : e(c) === "saving" && r(C, 2);
    });
  }
  m(z, F), W();
}
X(["change", "click"]);
export {
  ae as default
};
