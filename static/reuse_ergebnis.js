"use strict";
/* Reuse-Planung: Ergebnisanzeige (Kennzahlen, Zielteile, Vergleich Neu <-> Reuse, Diagramm). Rechnerisches Szenario. */

function reuseZeilenName(z) {
  const n = S.reuse.std.typen[z.typ];
  return z.typ === "flach" ? n + " " + fmt(z.breite, 0) + "/" + fmt(z.dicke, 0) : n;
}

function renderReuseErgebnis() {
  const d = S.reuse.daten;
  if (!d) return;
  const s = d.summen, mods = gewaehlteModule(), v = d.vergleich;
  const zaehl = [0, 0, 0, 0];
  d.stab.forEach(x => { zaehl[x.s] += 1; });
  zaehl.forEach((n, i) => { const e = el("reuse-n" + i); if (e) e.textContent = "· " + n + " Stäbe"; });
  const summe = z => optModulSumme(z.co2) + z.zusatz;
  const ersparnis = summe(v.neu) - summe(v.reuse);
  el("reuse-hinweis").innerHTML = "<b>" + esc(d.hinweis) + "</b>" +
    (d.warnungen.length ? '<br><span class="warn">⚠ ' + d.warnungen.map(esc).join("<br>⚠ ") + "</span>" : "");
  const kv = [["Zielentwurf", fmt(s.masse_ziel_kg, 0) + " kg"],
    ["Aus Spendern gedeckt", fmt(s.deckung_prozent, 1) + " % (" + fmt(s.masse_gedeckt_kg, 0) + " kg)"],
    ["Neu zu beschaffen", fmt(s.masse_fehlt_kg, 0) + " kg"], ["Verschnitt (inkl. kurze Reste)", fmt(s.verschnitt_kg, 0) + " kg"],
    ["Reststücke ab Mindestlänge", fmt(s.rest_lager_kg, 0) + " kg"], ["Schnitte", fmt(s.schnitte, 0)],
    ["Stöße (Transportmaß)", fmt(s.stoesse, 0)], ["Genutzte Spenderstäbe", fmt(s.spender_genutzt, 0)]];
  el("reuse-kennzahlen").innerHTML = '<div class="kv">' + kv.map(k => "<div>" + k[0] + "<b>" + k[1] + "</b></div>").join("") + "</div>";
  el("reuse-zeilen").innerHTML = '<div class="wrap"><table class="t"><tr><th>Zielteil</th><th>Länge m</th><th>Anzahl</th>' +
    "<th>aus Spendern</th><th>neu</th><th>Spenderstäbe (RFEM-Nr.)</th></tr>" +
    d.ziel.map(z => "<tr><td>" + esc(reuseZeilenName(z)) + "</td><td>" + fmt(z.laenge, 2) + "</td><td>" + z.anzahl + "</td><td>" + z.gedeckt +
      "</td><td" + (z.fehlend ? ' class="schlecht"' : "") + ">" + z.fehlend + '</td><td style="white-space:normal;text-align:left">' +
      esc(z.staebe.slice(0, 8).join(", ") + (z.staebe.length > 8 ? " … (+" + (z.staebe.length - 8) + ")" : "")) + "</td></tr>").join("") +
    "</table></div>";
  const reihe = (name, a, b, dez) => "<tr><td>" + name + "</td><td>" + fmt(a, dez) + "</td><td>" + fmt(b, dez) + "</td><td>" + fmt(a - b, dez) + "</td></tr>";
  el("reuse-vergleich").innerHTML = '<div class="wrap"><table class="t"><tr><th>kg CO₂e bzw. Zeit</th><th>Neu</th><th>Reuse</th><th>Differenz</th></tr>' +
    d.module.map((m, i) => reihe(MODUL_NAME[m] + (mods.includes(m) ? " ●" : ""), v.neu.co2[i], v.reuse.co2[i], 1)).join("") +
    reihe("Schnitt + Transport (Annahme)", v.neu.zusatz, v.reuse.zusatz, 1) +
    '<tr class="summe-zeile"><td>Summe gewählte Module + Schnitt/Transport</td><td>' + fmt(summe(v.neu), 1) + "</td><td>" + fmt(summe(v.reuse), 1) +
    "</td><td>" + fmt(ersparnis, 1) + "</td></tr>" + reihe("Arbeitszeit (Annahme), h", v.neu.aufwand_h, v.reuse.aufwand_h, 1) +
    reihe("Zeit bis Material da (Annahme), Tage", v.neu.tage, v.reuse.tage, 0) + "</table></div>" +
    '<p class="opt-gross"><b class="' + (ersparnis >= 0 ? "gut" : "schlecht") + '">' + einsparText(ersparnis, 0) + " CO₂e</b> " +
    "<span>durch Reuse im Szenario (gewählte Module, inkl. Schnitt und Transport)</span></p>";
  zeichneReuseDiagramm(v);
}

function zeichneReuseDiagramm(v) {
  const mods = gewaehlteModule(), x = ["Neu", "Reuse"], farben = ["#52606d", "#9aa5b1", "#cbd2d9"];
  const spuren = ["A1-A3", "C", "D"].map((m, i) => ({ type: "bar", name: MODUL_NAME[m], x, marker: { color: farben[i] },
    y: [mods.includes(m) ? v.neu.co2[i] : 0, mods.includes(m) ? v.reuse.co2[i] : 0] }));
  spuren.push({ type: "bar", name: "Schnitt + Transport", x, y: [v.neu.zusatz, v.reuse.zusatz], marker: { color: "#b45309" } });
  Plotly.react("reuse-d1", spuren, { barmode: "stack", height: 280, margin: { l: 50, r: 10, t: 10, b: 30 },
    yaxis: { title: "kg CO₂e" }, legend: { orientation: "h" } }, { responsive: true, displaylogo: false });
}
