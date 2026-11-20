"use strict";
/* Optimierung: Daten vom Server (/api/optimierung), Heatmap-Werte und Hotspots.
   Alles sind rechnerische Szenarien, keine statisch nachgewiesenen Aenderungen. */

const OPT_MODUL_INDEX = { "A1-A3": 0, "C": 1, "D": 2 };
const HEAT = { gruen: "#1a9850", gelb: "#ffe34d", rot: "#d7191c", grau: "#dfe3e8" };

S.opt = { daten: null, massnahmen: {}, laeuft: false, wieder: false, dirty: true, timer: null };

function optAktiv() { return modus() === "opt"; }

function optModulSumme(z) {
  return gewaehlteModule().reduce((a, m) => a + z[OPT_MODUL_INDEX[m]], 0);
}

/* "−965,0 kg" bei Einsparung, "+12,0 kg" bei Mehremission (x = Einsparung, positiv = weniger CO2e) */
function einsparText(x, d) {
  const n = d === undefined ? 1 : d;
  return (x >= 0 ? "−" : "+") + fmt(Math.abs(x), n) + " kg";
}

/* CO2e je Stab fuer die Heatmap: Ist (normale Rechnung) oder Szenario (aus /api/optimierung). */
function optWerte() {
  const szen = el("opt-ansicht").value === "szenario" && S.opt.daten;
  return S.erg.stab.map((s, i) => (szen ? optModulSumme(S.opt.daten.szenario[i]) : (co2Wert(s.co2) || 0)));
}

/* Obere x % der Staebe (nach CO2e) sind Hotspots. */
function optHotspots(werte) {
  const n = werte.length, prozent = Number(el("opt-schwelle").value);
  const k = Math.max(1, Math.round(n * prozent / 100));
  const sortiert = werte.map((v, i) => [v, i]).sort((a, b) => b[0] - a[0]);
  const hot = new Set(), rang = new Array(n);
  sortiert.forEach(([v, i], r) => { rang[i] = r + 1; if (r < k && v > 0) hot.add(i); });
  return { hot, rang, sortiert: sortiert.map(x => x[1]), k, relativ: false };
}

/* Je Gruppe: Hotspots, Anteil an der Summe, "gleich" = alle Staebe fast gleich gross. */
function optGruppenInfo(werte, hot) {
  const summe = werte.reduce((a, v) => a + Math.max(v, 0), 0) || 1;
  return S.katalog.gruppen.map(g => {
    const idx = [];
    S.erg.stab.forEach((s, i) => { if (s.gruppe === g.id) idx.push(i); });
    const w = idx.map(i => werte[i]), max = Math.max(...w), min = Math.min(...w);
    return { id: g.id, name: g.name, n: idx.length, hot: idx.filter(i => hot.has(i)).length,
             anteil: idx.reduce((a, i) => a + Math.max(werte[i], 0), 0) / summe,
             gleich: max - min <= 0.05 * Math.max(max, 1e-9) };
  });
}

/* Werte, Hotspots und Farben fuer die aktuelle Ansicht berechnen (wird von aktualisiereSzene aufgerufen). */
function optBerechne() {
  S.opt.werte = optWerte();
  S.opt.hs = optHotspots(S.opt.werte);
  S.opt.heat = optHeat(S.opt.werte, S.opt.hs.hot);
  const szen = el("opt-ansicht").value === "szenario" && S.opt.daten && S.opt.daten.massnahmen.some(m => m.aktiv);
  el("szenario-badge").hidden = !(szen);
}

/* Heatmap-Farben: gruen -> gelb -> rot. Nicht-Hotspots optional in einem grauen Band unterhalb der Skala. */
function optHeat(werte, hot) {
  const log = el("skala").value === "log", relativ = el("opt-skala").value === "gruppe";
  const nurHot = el("opt-nur-hotspots").checked;
  const pos = werte.map(v => Math.max(v || 0, 0));
  let norm, max, tickvals, ticktext;
  if (relativ) {
    const mm = {};
    S.erg.stab.forEach((s, i) => {
      const m = mm[s.gruppe] || (mm[s.gruppe] = [Infinity, -Infinity]);
      m[0] = Math.min(m[0], pos[i]); m[1] = Math.max(m[1], pos[i]);
    });
    norm = pos.map((v, i) => {                       // Gruppen mit fast gleichen Werten: einheitlich gelb
      const [a, b] = mm[S.erg.stab[i].gruppe];
      return b - a > 0.05 * b ? (v - a) / (b - a) : 0.5;
    });
    max = 1; tickvals = [0, 0.5, 1]; ticktext = ["niedrig", "mittel", "hoch"];
  } else {
    const t = log ? (v => Math.log10(1 + v)) : (v => v);
    norm = pos.map(t);
    max = Math.max(...norm) || 1;
    if (log) {
      const T = [0, 1, 10, 100].filter(x => x <= Math.max(...pos) * 1.5);
      tickvals = T.map(t); ticktext = T.map(x => fmt(x, 0));
    } else {
      const dez = max < 10 ? 1 : 0;
      tickvals = [0, 0.25, 0.5, 0.75, 1].map(f => f * max); ticktext = tickvals.map(v => fmt(v, dez));
    }
  }
  const luecke = nurHot ? 0.16 * max : 0, f0 = luecke / (max + luecke);
  const draw = norm.map((v, i) => (nurHot && !hot.has(i) ? -luecke / 2 : v));
  const stops = nurHot
    ? [[0, HEAT.grau], [f0, HEAT.grau], [f0, HEAT.gruen], [f0 + (1 - f0) / 2, HEAT.gelb], [1, HEAT.rot]]
    : [[0, HEAT.gruen], [0.5, HEAT.gelb], [1, HEAT.rot]];
  if (nurHot) { tickvals = tickvals.concat([-luecke / 2]); ticktext = ticktext.concat(["kein Hotspot"]); }
  return { draw, relativ, p: { min: -luecke, max, farbskala: stops, umkehren: false, mitte: undefined,
                               transform: v => v, tickvals, ticktext } };
}
