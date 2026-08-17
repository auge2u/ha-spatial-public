function d(i) {
  const { photoCount: e, avgAspect: s, isHighQualitySet: t } = i.localSignals, a = s > 1.85, n = e === 1 ? "" : "s", r = a ? `A wide room read from ${e} photo${n} — likely an open living space with more than one zone.` : t ? `A clearly defined room from a detailed set of ${e} photos.` : `A room captured from ${e} photo${n}.`, o = [];
  return t && o.push("High-resolution set"), a && o.push(`Wide layout (${s.toFixed(2)}:1)`), o.push(`${e} photo${n}`), {
    understanding: r,
    confidence: t ? 0.87 : 0.7,
    noticed: o,
    recommendations: [
      {
        id: "evening-lighting-scene",
        title: "Set up an evening lighting scene",
        rationale: "Group this room's lights into a one-tap evening scene.",
        priority: 1,
        entityType: "light"
      }
    ],
    suggestedRoomName: i.roomHint,
    modelUsed: "simulated",
    analysisDurationMs: 0
  };
}
export {
  d as simulatedVision
};
