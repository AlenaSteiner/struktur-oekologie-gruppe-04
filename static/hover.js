"use strict";
/* Hover im 3D: alle anderen Staebe werden blasser, der Stab unter der Maus bleibt farbig und bekommt Kanten. */

let hoverTimer = null;

function stabAusPunkt(pt) {
  if (!pt) return null;
  if (pt.curveNumber === 0) return S.geo.stab_je_punkt[pt.pointNumber];
  if (pt.curveNumber === 1) return S.geo.linien.stab[pt.pointNumber];
  return null;
}

function baueStabDreiecke() {
  const g = S.geo;
  S.stabTris = Array.from({ length: g.anzahl_staebe }, () => []);
  for (let t = 0; t < g.i.length; t++) S.stabTris[g.stab_je_punkt[g.i[t]]].push(t);
}

function normale(g, a, b, c) {
  const ux = g.x[b] - g.x[a], uy = g.y[b] - g.y[a], uz = g.z[b] - g.z[a];
  const vx = g.x[c] - g.x[a], vy = g.y[c] - g.y[a], vz = g.z[c] - g.z[a];
  const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
  const l = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
  return [nx / l, ny / l, nz / l];
}

/* Kanten = Dreieckskanten, an denen die Flaechenrichtung knickt (oder die nur zu einem Dreieck gehoeren). */
function kantenVon(n) {
  const g = S.geo, kanten = new Map();
  const key = i => g.x[i].toFixed(3) + "," + g.y[i].toFixed(3) + "," + g.z[i].toFixed(3);
  for (const t of S.stabTris[n]) {
    const a = g.i[t], b = g.j[t], c = g.k[t], nr = normale(g, a, b, c);
    for (const [p, q] of [[a, b], [b, c], [c, a]]) {
      const kp = key(p), kq = key(q), k = kp < kq ? kp + "|" + kq : kq + "|" + kp;
      const e = kanten.get(k);
      if (e) e.n.push(nr); else kanten.set(k, { p, q, n: [nr] });
    }
  }
  const x = [], y = [], z = [];
  for (const e of kanten.values()) {
    let scharf = e.n.length === 1;
    if (!scharf) {
      const d = Math.abs(e.n[0][0] * e.n[1][0] + e.n[0][1] * e.n[1][1] + e.n[0][2] * e.n[1][2]);
      scharf = d < 0.9;
    }
    if (!scharf) continue;
    x.push(g.x[e.p], g.x[e.q], null); y.push(g.y[e.p], g.y[e.q], null); z.push(g.z[e.p], g.z[e.q], null);
  }
  return { x, y, z };
}

/* Kopie des Stabes, minimal vergroessert (sonst flackert es gegen das blasse Original). */
function hervorhebung(n) {
  const g = S.geo, tris = S.stabTris[n];
  if (!tris.length) {                           // RD 12: nur eine Linie
    const l = g.linien, x = [], y = [], z = [];
    for (let i = 0; i < l.x.length; i++) if (l.stab[i] === n) { x.push(l.x[i]); y.push(l.y[i]); z.push(l.z[i]); }
    return { mesh: null, kanten: { x, y, z } };
  }
  const c = S.zentren[n], f = 1.01, map = new Map();
  const X = [], Y = [], Z = [], I = [], J = [], K = [];
  const idx = v => {
    let r = map.get(v);
    if (r === undefined) {
      r = X.length; map.set(v, r);
      X.push(c[0] + (g.x[v] - c[0]) * f); Y.push(c[1] + (g.y[v] - c[1]) * f); Z.push(c[2] + (g.z[v] - c[2]) * f);
    }
    return r;
  };
  for (const t of tris) { I.push(idx(g.i[t])); J.push(idx(g.j[t])); K.push(idx(g.k[t])); }
  const w = S.wertDraw[n];
  return { mesh: { x: X, y: Y, z: Z, i: I, j: J, k: K, intensity: X.map(() => w) }, kanten: kantenVon(n) };
}

function wendeHoverAn(n) {
  if (S.hover === n || !S.erg || !S.wertDraw) return;
  S.hover = n;
  if (S.vergleich) aktualisierePlanDock();       // Vergleichsmodus: Markierung im Bewehrungsplan folgt der Maus
  if (n === null) {
    const o = bewAn() ? BEW_BETON_OPAZ : 1;
    Plotly.restyle("szene", { opacity: [o, o] }, [0, 1]);
    Plotly.restyle("szene", { visible: [false, false] }, [2, 3]);
    return;
  }
  if (!S.stabTris) baueStabDreiecke();
  const h = hervorhebung(n);
  Plotly.restyle("szene", { opacity: [0.15, 0.15] }, [0, 1]);
  if (h.mesh) {
    Plotly.restyle("szene", { visible: [true], x: [h.mesh.x], y: [h.mesh.y], z: [h.mesh.z],
                              i: [h.mesh.i], j: [h.mesh.j], k: [h.mesh.k], intensity: [h.mesh.intensity] }, [2]);
  } else {
    Plotly.restyle("szene", { visible: [false] }, [2]);
  }
  Plotly.restyle("szene", { visible: [true], x: [h.kanten.x], y: [h.kanten.y], z: [h.kanten.z] }, [3]);
}

function planeHover(n) {
  clearTimeout(hoverTimer);
  hoverTimer = setTimeout(() => wendeHoverAn(n), n === null ? 120 : 30);
}

function registriereHover(d) {
  d.on("plotly_hover", ev => planeHover(stabAusPunkt(ev.points && ev.points[0])));
  d.on("plotly_unhover", () => planeHover(null));
}

/* Platzhalter-Spuren (unsichtbar, bis ein Stab ueberfahren wird). */
function leereHervorhebung() {
  return { type: "mesh3d", visible: false, x: [0], y: [0], z: [0], i: [0], j: [0], k: [0], intensity: [0],
           intensitymode: "vertex", coloraxis: "coloraxis", flatshading: true, hoverinfo: "skip", showlegend: false,
           lighting: { ambient: 0.7, diffuse: 0.8, specular: 0.2, roughness: 0.5 } };
}

function leereKanten() {
  return { type: "scatter3d", mode: "lines", visible: false, x: [0], y: [0], z: [0], hoverinfo: "skip",
           showlegend: false, line: { color: "#111", width: 6 } };
}
