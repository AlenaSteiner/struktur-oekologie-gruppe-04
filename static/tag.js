"use strict";
/* Tagesverlauf der Temperatur je Bauteilgruppe in allen Materialien. */

const FARBE_MATERIAL = { stahl: "#52616b", beton: "#9a8f80", aluminium: "#4a90c2", holz: "#b5782f" };

async function ladeTagesverlauf() {
  const gruppe = el("tag-gruppe").value;
  if (!gruppe) return;
  const nr = (S.tagNr = (S.tagNr || 0) + 1);
  try {
    const d = await api("/api/tagesverlauf/" + gruppe, leseConfig());
    if (nr !== S.tagNr) return;                       // veraltete Antwort
    const traces = d.kurven.map(k => ({
      type: "scatter", mode: "lines", x: k.stunde, y: k.t, name: k.name, line: { color: FARBE_MATERIAL[k.material], width: 3 },
      hovertemplate: "%{x:.1f} h · %{y:.1f} °C",
    }));
    traces.push({ type: "scatter", mode: "lines", x: [0, 24], y: [d.t_luft, d.t_luft], name: "Luft",
                  line: { color: "#999", dash: "dot", width: 1 }, hoverinfo: "skip" });
    const jetzt = Number(el("zeit").value) / 60;
    Plotly.react("tag", traces, {
      margin: { l: 50, r: 10, t: 10, b: 40 }, xaxis: { title: "Uhrzeit", range: [0, 24], dtick: 3 },
      yaxis: { title: "°C" }, legend: { orientation: "h", y: -0.25 },
      shapes: [{ type: "line", x0: jetzt, x1: jetzt, yref: "paper", y0: 0, y1: 1, line: { color: "#0b6bcb", dash: "dash", width: 1 } }],
    }, { responsive: true, displaylogo: false });
  } catch (e) {
    el("tag").textContent = "Tagesverlauf nicht verfügbar: " + e.message;
  }
}
