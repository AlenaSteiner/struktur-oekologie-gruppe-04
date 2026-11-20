"use strict";
/* Tabellen, Auswahlanzeige, Warnungen. */

const MODUL_NAME = { "A1-A3": "A1–A3", "C": "C1–C4", "D": "D" };

function matName(id) { return S.katalog.materialien[id].name; }

function renderAuswahl() {
  const box = el("auswahl");
  if (S.auswahl === null || !S.erg) {
    box.innerHTML = '<span class="klein">Stab im 3D-Modell anklicken, um die Werte zu sehen.</span>';
    return;
  }
  const s = S.erg.stab[S.auswahl];
  const mods = gewaehlteModule();
  if (S.projekt === "bauteil6") { box.innerHTML = renderAuswahlBauteil6(s, mods); return; }
  const zeilen = [
    ["Stab (RFEM-Nr.)", s.id], ["Querschnitt", esc(s.profil)], ["Material", esc(matName(s.material))],
    ["Länge", fmt(s.laenge, 3) + " m"], ["Volumen", fmt(s.volumen * 1000, 3) + " dm³"],
    ["Menge", s.menge === null ? "–" : fmt(s.menge, s.einheit === "kg" ? 2 : 4) + " " + s.einheit.replace("m3", "m³")],
  ];
  if (s.bewehrung_kg > 0) zeilen.push(["Bewehrung (Betonstahl)", fmt(s.bewehrung_kg, 1) + " kg"]);
  if (s.co2) {
    for (const m of ["A1-A3", "C", "D"]) {
      zeilen.push(["CO₂e " + MODUL_NAME[m] + (mods.includes(m) ? " ●" : ""), fmt(s.co2[m], 3) + " kg"]);
    }
    zeilen.push(["CO₂e gewählt", fmt(co2Wert(s.co2), 3) + " kg"]);
  } else {
    zeilen.push(["CO₂e", "Datensatz fehlt"]);
  }
  zeilen.push(["Temperatur Mittel", fmt(s.t, 1) + " °C"], ["Temperatur Sonnenseite (Spitze)", fmt(s.t_spitze, 1) + " °C"],
    ["Zeitkonstante", fmt(s.tau, 1) + " min"], ["Biot-Zahl", fmt(s.biot, 3)]);
  box.innerHTML = '<h2>Ausgewählter Stab</h2><div class="kv">' +
    zeilen.map(z => "<div>" + z[0] + "<b>" + z[1] + "</b></div>").join("") + "</div>" +
    (s.biot > 0.1 ? '<p class="klein">Biot-Zahl über 0,1: Das Bauteil ist dick, die Oberfläche wird heißer als das Mittel. ' +
      'Die Spitzentemperatur ist hier aussagekräftiger.</p>' : "") +
    (optAktiv() ? optDetailHtml(S.auswahl) : "") + (reuseAktiv() ? reuseDetailHtml(S.auswahl) : "");
}

/* Bauteil6: IFC-Bauteil mit Geschoss, Schichtaufbau und Hinweisen zu den Annahmen */
function renderAuswahlBauteil6(s, mods) {
  const schichten = s.schichten.map(([m, a]) => esc(matName(m)) + (s.schichten.length > 1 ? " " + fmt(100 * a, 0) + " %" : "")).join(" + ");
  const zeilen = [
    ["Bauteil Nr.", s.id], ["IFC-Typ", esc(s.profil)], ["Art", esc(s.klasse)], ["Geschoss", esc(s.geschoss)],
    ["Material (Quelle: " + esc(s.quelle) + ")", schichten], ["Volumen (Geometrie)", fmt(s.volumen, 3) + " m³"],
    ["Volumen laut IFC", s.ifc === null ? "–" : fmt(s.ifc, 3) + " m³"], ["Masse", fmt(s.menge, 0) + " kg"],
  ];
  if (s.bewehrung_kg > 0) zeilen.push(["Betonstahl (Annahme je Bauteilart)", fmt(s.bewehrung_kg, 0) + " kg"]);
  if (s.co2) {
    for (const m of ["A1-A3", "C", "D"]) zeilen.push(["CO₂e " + MODUL_NAME[m] + (mods.includes(m) ? " ●" : ""), fmt(s.co2[m], 1) + " kg"]);
    zeilen.push(["CO₂e gewählt", fmt(co2Wert(s.co2), 1) + " kg"]);
  } else zeilen.push(["CO₂e", "Datensatz fehlt"]);
  return '<h2>Ausgewähltes Bauteil</h2><div class="kv">' + zeilen.map(z => "<div>" + z[0] + "<b>" + z[1] + "</b></div>").join("") + "</div>" +
    (s.abweichung ? '<p class="klein warn">Geometrie und IFC-Volumen weichen um mehr als 10 % ab. Gerechnet wird mit der Geometrie.</p>' : "") +
    (s.annahme ? '<p class="klein warn">Für dieses Bauteil fehlt eine Materialangabe. Stahlbeton ist angenommen.</p>' : "");
}

function renderGruppenBauteil6() {
  const mods = gewaehlteModule();
  const summe = S.erg.gruppen.reduce((a, g) => a + mods.reduce((b, m) => b + g.co2[m], 0), 0);
  let sumN = 0, sumV = 0;
  const zeilen = S.erg.gruppen.map(g => {
    const wert = mods.reduce((a, m) => a + g.co2[m], 0);
    sumN += g.n; sumV += g.volumen;
    return "<tr><td>" + esc(g.name) + "</td><td>" + esc(matName(g.material)) + "</td><td>" + g.n + "</td><td>" + fmt(g.volumen, 1) + "</td>" +
      mods.map(m => "<td>" + fmt(g.co2[m], 0) + "</td>").join("") + "<td><b>" + fmt(wert, 0) + "</b></td><td>" +
      (summe !== 0 ? fmt(100 * wert / summe, 0) + " %" : "–") + "</td></tr>";
  }).join("");
  el("tab-gruppen").innerHTML = '<div class="wrap"><table class="t"><tr><th>Bauteilart</th><th>Hauptmaterial</th><th>Anz.</th><th>Volumen m³</th>' +
    mods.map(m => "<th>" + MODUL_NAME[m] + " kg CO₂e</th>").join("") + "<th>gewählt kg</th><th>Anteil</th></tr>" + zeilen +
    '<tr class="summe-zeile"><td>Summe</td><td></td><td>' + sumN + "</td><td>" + fmt(sumV, 1) + "</td>" +
    mods.map(m => "<td>" + fmt(S.erg.gesamt[m], 0) + "</td>").join("") + "<td>" + fmt(summe, 0) + "</td><td>100 %</td></tr></table></div>";
}

function renderGruppen() {
  if (S.projekt === "bauteil6") return renderGruppenBauteil6();
  const mods = gewaehlteModule();
  const kopf = '<tr><th>Gruppe</th><th>Material</th><th>Anz.</th><th>Länge m</th><th>Volumen m³</th>' +
    mods.map(m => "<th>" + MODUL_NAME[m] + " kg CO₂e</th>").join("") +
    "<th>gewählt kg</th><th>Anteil</th><th>T Mittel °C</th><th>T Spitze °C</th><th>τ min</th></tr>";
  const summe = S.erg.gruppen.reduce((a, g) => a + mods.reduce((b, m) => b + g.co2[m], 0), 0);
  let sumN = 0, sumL = 0, sumV = 0;
  const zeilen = S.erg.gruppen.map(g => {
    const wert = mods.reduce((a, m) => a + g.co2[m], 0);
    sumN += g.n; sumL += g.laenge; sumV += g.volumen;
    return "<tr><td>" + esc(g.name) + "</td><td>" + esc(matName(g.material)) + "</td><td>" + g.n + "</td><td>" + fmt(g.laenge, 1) +
      "</td><td>" + fmt(g.volumen, 4) + "</td>" + mods.map(m => "<td>" + fmt(g.co2[m], 1) + "</td>").join("") +
      "<td><b>" + fmt(wert, 1) + "</b></td><td>" + (summe !== 0 ? fmt(100 * wert / summe, 0) + " %" : "–") +
      "</td><td>" + fmt(g.t_mittel, 1) + "</td><td>" + fmt(g.t_spitze_max, 1) + "</td><td>" + fmt(g.tau_mittel, 0) + "</td></tr>";
  }).join("");
  const fuss = '<tr class="summe-zeile"><td>Summe</td><td></td><td>' + sumN + "</td><td>" + fmt(sumL, 1) + "</td><td>" +
    fmt(sumV, 4) + "</td>" + mods.map(m => "<td>" + fmt(S.erg.gesamt[m], 1) + "</td>").join("") +
    "<td>" + fmt(summe, 1) + "</td><td>100 %</td><td></td><td></td><td></td></tr>";
  el("tab-gruppen").innerHTML = '<div class="wrap"><table class="t">' + kopf + zeilen + fuss + "</table></div>";
}

function renderVergleich() {
  const mods = gewaehlteModule();
  const wert = v => (v.co2 ? mods.reduce((a, m) => a + v.co2[m], 0) : null);
  const kopf = "<tr><th>Material für alle 736 Stäbe</th><th>α Sonne</th><th>ε</th><th>kg CO₂e (gewählte Module)</th>" +
    "<th>T Mittel °C</th><th>T Spitze max °C</th><th>τ Median min</th></tr>";
  const zeilen = S.erg.vergleich.map(v => "<tr><td>" + esc(v.name) + "</td><td>" + fmt(v.alpha, 2) + "</td><td>" + fmt(v.eps, 2) +
    "</td><td>" + fmt(wert(v), 0) + "</td><td>" + fmt(v.t_mittel, 1) + "</td><td>" + fmt(v.t_spitze_max, 1) + "</td><td>" +
    fmt(v.tau_median, 0) + "</td></tr>").join("");
  el("tab-vergleich").innerHTML = '<div class="wrap"><table class="t">' + kopf + zeilen + "</table></div>" +
    '<p class="klein">Gleicher Querschnitt, nur das Material getauscht. Das ist eine Rechenübung, keine Tragwerksplanung: ' +
    "Holz oder Aluminium mit den Stahlquerschnitten tragen die Lasten nicht.</p>";
}

function renderWarnungen() {
  S.erg.gruppen.forEach(g => {
    const w = document.querySelector('[data-warn="' + g.id + '"]');
    if (w) w.textContent = g.warnung ? "⚠ " + g.warnung : "";
  });
}

function renderSonnenInfo() {
  const u = S.erg.umgebung;
  el("sonnen-info").textContent = u.hoehe <= 0
    ? "Die Sonne ist unter dem Horizont. Es gibt nur Abstrahlung zum Himmel."
    : "Sonnenhöhe " + fmt(u.hoehe, 1) + "°, Azimut " + fmt(u.azimut, 0) + "° · Direkt " + u.dni + " W/m² · Diffus " + u.dhi +
      " W/m² · Himmel " + fmt(u.t_himmel, 0) + " °C";
}
