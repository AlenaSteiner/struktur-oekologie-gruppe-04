"use strict";
/* 3D-Ansicht (Plotly): Mesh3d fuer die Koerper, Scatter3d-Linien fuer RD 12, Auswahl per Klick. */

const MODUS_TEXT = {
  co2: { titel: "kg CO₂e", einheit: " kg" },
  opt: { titel: "kg CO₂e (Heatmap)", einheit: " kg" },
  reuse: { titel: "Reuse-Planung", einheit: "" },
  t: { titel: "°C (Mittel)", einheit: " °C" },
  spitze: { titel: "°C (Sonnenseite)", einheit: " °C" },
};

/* Hover-Text im 3D: klein, ohne Box (transparenter Hintergrund, kein Rahmen). */
const HOVER_LABEL = {
  bgcolor: "rgba(0,0,0,0)", bordercolor: "rgba(0,0,0,0)",
  font: { size: 10, color: "#111", family: "-apple-system, 'Segoe UI', Roboto, sans-serif" },
  align: "left",
};

function berechneZentren() {
  const g = S.geo, n = g.anzahl_staebe;
  const sum = Array.from({ length: n }, () => [0, 0, 0, 0]);
  for (let i = 0; i < g.x.length; i++) {
    const s = sum[g.stab_je_punkt[i]];
    s[0] += g.x[i]; s[1] += g.y[i]; s[2] += g.z[i]; s[3] += 1;
  }
  const l = g.linien;
  for (let i = 0; i < l.x.length; i++) {
    if (l.x[i] === null) continue;
    const s = sum[l.stab[i]];
    s[0] += l.x[i]; s[1] += l.y[i]; s[2] += l.z[i]; s[3] += 1;
  }
  S.zentren = sum.map(s => s[3] ? [s[0] / s[3], s[1] / s[3], s[2] / s[3]] : [0, 0, 0]);
}

function farbParameter(werte, art, skala) {
  const gueltig = werte.filter(v => v !== null && Number.isFinite(v));
  let min = Math.min(...gueltig), max = Math.max(...gueltig);
  if (min === max) { min -= 1; max += 1; }
  const p = { min, max, farbskala: art === "co2" ? "YlOrRd" : "Inferno", umkehren: false, mitte: undefined,
              transform: v => v, tickvals: undefined, ticktext: undefined };
  if (art === "co2") {
    if (min < 0) {                       // negative Werte: blau = Gutschrift/Speicher, rot = Last
      const m = Math.max(Math.abs(min), Math.abs(max));
      p.farbskala = "RdBu"; p.umkehren = true; p.mitte = 0;
      if (skala === "log") {
        p.transform = v => Math.sign(v) * Math.log10(1 + Math.abs(v));
        p.min = -Math.log10(1 + m); p.max = Math.log10(1 + m);
        const T = [-1000, -100, -10, -1, 0, 1, 10, 100, 1000].filter(t => Math.abs(t) <= m * 1.5);
        p.tickvals = T.map(p.transform); p.ticktext = T.map(t => fmt(t, 0));
      } else { p.min = -m; p.max = m; }
    } else if (skala === "log") {
      p.transform = v => Math.log10(1 + Math.max(v, 0));
      p.min = 0; p.max = Math.log10(1 + max);
      const T = [0, 0.1, 1, 10, 100, 1000].filter(t => t <= max * 1.5);
      p.tickvals = T.map(p.transform); p.ticktext = T.map(t => fmt(t, t < 1 ? 1 : 0));
    } else { p.min = 0; }
  }
  return p;
}

function aktualisiereSzene() {
  if (!S.geo || !S.erg) return;
  const art = modus(), skala = el("skala").value;
  const stab = S.erg.stab;
  const opt = art === "opt";                // Optimierung: Heatmap gruen -> gelb -> rot, Hotspots
  const reu = art === "reuse";              // Reuse-Planung: Spender nach Nutzung eingefaerbt
  if (opt) optBerechne();
  if (reu) reuseBerechne();
  const werte = opt ? S.opt.werte : reu ? S.reuse.werte : stab.map(s => stabWert(s));
  const p = opt ? S.opt.heat.p : reu ? S.reuse.p : farbParameter(werte, art, skala);
  const wertDraw = opt ? S.opt.heat.draw : werte.map(v => (v === null ? 0 : p.transform(v)));
  S.wertDraw = wertDraw;
  S.hover = null;
  const einheit = MODUS_TEXT[art].einheit;
  const label = stab.map((s, i) => "<b>Stab " + s.id + "</b> · " + esc(s.profil) + "<br>" +
    (reu ? reuseLabel(i) : esc(S.katalog.materialien[s.material].name) + "<br>" + fmt(werte[i], art === "co2" || opt ? 2 : 1) + einheit) +
    (opt && S.opt.hs.hot.has(i) ? " · Hotspot" : ""));

  const g = S.geo;
  const mesh = {
    type: "mesh3d", x: g.x, y: g.y, z: g.z, i: g.i, j: g.j, k: g.k,
    intensity: g.stab_je_punkt.map(n => wertDraw[n]), intensitymode: "vertex",
    coloraxis: "coloraxis", flatshading: true, name: "Stäbe", opacity: bewAn() ? BEW_BETON_OPAZ : 1,
    lighting: { ambient: 0.65, diffuse: 0.8, specular: 0.15, roughness: 0.6 },
    hoverinfo: "text", text: g.stab_je_punkt.map(n => label[n]), hoverlabel: HOVER_LABEL,
  };
  const l = g.linien;
  const linie = {
    type: "scatter3d", mode: "lines", x: l.x, y: l.y, z: l.z, name: "Zugstäbe (RD 12)",
    line: { width: 3, color: l.stab.map(n => wertDraw[n]), coloraxis: "coloraxis" }, opacity: bewAn() ? BEW_BETON_OPAZ : 1,
    hoverinfo: "text", text: l.stab.map(n => label[n]), hoverlabel: HOVER_LABEL,
  };
  const traces = [mesh, linie, leereHervorhebung(), leereKanten()];   // 2 und 3: Hover-Hervorhebung
  if (S.auswahl !== null && S.zentren) {
    const c = S.zentren[S.auswahl];
    traces.push({ type: "scatter3d", mode: "markers", x: [c[0]], y: [c[1]], z: [c[2] + 0.35], hoverinfo: "skip",
                  marker: { size: 8, symbol: "diamond", color: "#0b6bcb", line: { color: "#fff", width: 2 } },
                  name: "Auswahl", showlegend: false });
  }
  traces.push(...bewSpuren());                 // 3D-Bewehrung (nur wenn eingeschaltet)
  const achse = { showbackground: false, gridcolor: "#dde1e6", zerolinecolor: "#dde1e6", title: "" };
  const layout = {
    uirevision: "konstant", margin: { l: 0, r: 0, t: 0, b: 0 }, showlegend: false, hoverlabel: HOVER_LABEL,
    coloraxis: {
      colorscale: p.farbskala, reversescale: p.umkehren, cmin: p.min, cmax: p.max, cmid: p.mitte,
      colorbar: { title: { text: MODUS_TEXT[art].titel }, thickness: 14, len: 0.8, tickvals: p.tickvals, ticktext: p.ticktext },
    },
    scene: {
      aspectmode: "data", xaxis: Object.assign({ title: "x [m]" }, achse), yaxis: Object.assign({ title: "y [m]" }, achse),
      zaxis: Object.assign({ title: "z [m]" }, achse),
      camera: S.kamera || { eye: { x: 1.5, y: -1.7, z: 0.9 }, up: { x: 0, y: 0, z: 1 } },
    },
  };
  Plotly.react("szene", traces, layout, { responsive: true, displaylogo: false });
  if (!S.szeneBereit) {
    S.szeneBereit = true;
    const d = el("szene");
    registriereHover(d);
    d.on("plotly_relayout", e => { if (e["scene.camera"]) S.kamera = e["scene.camera"]; });
    d.on("plotly_click", ev => {
      const pt = ev.points && ev.points[0];
      if (!pt) return;
      const nr = pt.curveNumber === 0 ? S.geo.stab_je_punkt[pt.pointNumber]
               : pt.curveNumber === 1 ? S.geo.linien.stab[pt.pointNumber] : null;
      if (nr === null || nr === undefined) return;
      S.auswahl = nr;
      renderAuswahl();
      aktualisiereSzene();
      zeigePlan();
    });
  }
  renderAuswahl();
  if (opt) renderHotspots();
  if (S.vergleich) aktualisierePlanDock();
}
