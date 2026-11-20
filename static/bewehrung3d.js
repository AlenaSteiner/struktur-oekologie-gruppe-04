"use strict";
/* 3D-Bewehrung der Streifenfundamente: aus dem Bewehrungsplan erzeugte Staebe, ueber dem (transparenten) Beton.
   Positionen wie im Plan: 1 Buegel ø10, 2 und 4 Laengsstaebe ø12, 3 Endschlaufen ø12. */

const BEW_FARBE = { 1: "#2563eb", 2: "#dc2626", 3: "#16a34a", 4: "#ea580c" };
const BEW_NAME = { 1: "Pos. 1 Bügel ø10", 2: "Pos. 2 Querstreifen ø12", 3: "Pos. 3 Schlaufen ø12", 4: "Pos. 4 Längsstreifen ø12" };
const BEW_BREITE = { 1: 2, 2: 4, 3: 4, 4: 4 };

const BEW_BETON_OPAZ = 0.3;     // Deckkraft des Modells, solange die Bewehrung gezeigt wird

S.bew = { an: false, daten: null, laedt: false };

function bewAn() { return S.bew.an; }

/* Fundamentstab n (Index im Modell) -> Auswahl aller beruehrenden Bewehrungsstaebe je Position */
function bewFuerStab(pos, n) {
  const d = S.bew.daten.pos[pos], x = [], y = [], z = [];
  for (const [a, b, stabs] of d.balken) {
    if (n === null || !stabs.includes(n)) continue;
    for (let i = a; i < b; i++) { x.push(d.x[i]); y.push(d.y[i]); z.push(d.z[i]); }
  }
  return { x, y, z };
}

/* Spuren fuer Plotly: alle Staebe je Position (gedimmt, wenn ein Stab gewaehlt ist) + hervorgehobene Staebe */
function bewSpuren() {
  if (!bewAn() || !S.bew.daten) return [];
  const fokus = S.auswahl !== null && S.auswahl !== undefined && S.erg.stab[S.auswahl].gruppe === "fundament" ? S.auswahl : null;
  const spuren = [];
  for (const p of [1, 2, 3, 4]) {
    const d = S.bew.daten.pos[p];
    spuren.push({ type: "scatter3d", mode: "lines", x: d.x, y: d.y, z: d.z, hoverinfo: "skip", showlegend: false,
                  name: BEW_NAME[p], opacity: fokus === null ? 1 : 0.18, line: { color: BEW_FARBE[p], width: BEW_BREITE[p] } });
  }
  if (fokus !== null) {
    for (const p of [1, 2, 3, 4]) {
      const h = bewFuerStab(p, fokus);
      spuren.push({ type: "scatter3d", mode: "lines", x: h.x, y: h.y, z: h.z, hoverinfo: "skip", showlegend: false,
                    name: BEW_NAME[p] + " (gewählter Stab)", line: { color: BEW_FARBE[p], width: BEW_BREITE[p] + 4 } });
    }
  }
  return spuren;
}

async function schalteBewehrung() {
  S.bew.an = el("bew3d").checked;
  el("bew-legende").hidden = !S.bew.an;
  if (S.bew.an && !S.bew.daten && !S.bew.laedt) {
    S.bew.laedt = true;
    try {
      S.bew.daten = await api("/api/bewehrung3d");
      renderBewLegende();
    } catch (e) {
      zeigeFehler("Bewehrung konnte nicht erzeugt werden: " + e.message);
      el("bew3d").checked = S.bew.an = false;
      el("bew-legende").hidden = true;
    }
    S.bew.laedt = false;
  }
  aktualisiereSzene();
}

function renderBewLegende() {
  const d = S.bew.daten;
  const zeilen = d.pruefung.filter(z => z.pos > 0).map(z =>
    '<li><span class="bew-punkt" style="background:' + BEW_FARBE[z.pos] + '"></span>' + esc(BEW_NAME[z.pos]) + ": " + z.ist_stueck +
    " Stk., " + fmt(z.ist_kg, 1) + " kg" + (z.ok ? "" : ' <b class="schlecht">≠ Plan ' + z.soll_stueck + "</b>") + "</li>").join("");
  const g = d.pruefung.find(z => z.pos === 0);
  el("bew-liste").innerHTML = zeilen;
  el("bew-summe").innerHTML = "Summe: <b>" + g.ist_stueck + " Stk., " + fmt(g.ist_kg, 2) + " kg</b> · Plan: " + g.soll_stueck + " Stk., " +
    fmt(g.soll_kg, 2) + " kg " + (g.ok ? '<b class="gut">✓ stimmt</b>' : '<b class="schlecht">✗ weicht ab</b>');
}
