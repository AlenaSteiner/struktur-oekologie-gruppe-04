"use strict";
/* Optimierung: Ergebnis-Tabellen und Diagramme. Alles nur rechnerische Szenarien, kein statischer Nachweis. */

const OPT_MOD_NAME = { "A1-A3": "A1–A3", "C": "C1–C4", "D": "D" };

function optSumme(z) { return optModulSumme(z); }

function renderOptErgebnis(d) {
  const mods = gewaehlteModule();
  const b = optSumme(d.gesamt.basis), s = optSumme(d.gesamt.szenario), e = b - s;
  const nAktiv = d.massnahmen.filter(m => m.aktiv).length;
  const kl = x => (x >= 0 ? "gut" : "schlecht");
  const prozent = (x, b0) => (b0 ? (x >= 0 ? "−" : "+") + fmt(Math.abs(100 * x / b0), 1) + " %" : "–");
  const gruppenZeile = g => {
    const gb = optSumme(g.basis), gs = optSumme(g.szenario), x = gb - gs;
    return "<tr><td>" + esc(g.name) + "</td><td>" + fmt(gb, 0) + "</td><td>" + fmt(gs, 0) + '</td><td class="' + kl(x) + '">' +
      einsparText(x, 0) + "</td><td>" + prozent(x, gb) + "</td></tr>";
  };
  const modZeilen = d.module.map((m, k) => {
    const x = d.gesamt.basis[k] - d.gesamt.szenario[k];
    return "<tr><td>" + OPT_MOD_NAME[m] + (mods.includes(m) ? " ●" : "") + "</td><td>" + fmt(d.gesamt.basis[k], 0) + "</td><td>" +
      fmt(d.gesamt.szenario[k], 0) + '</td><td class="' + kl(x) + '">' + einsparText(x, 0) + "</td></tr>";
  }).join("");
  const mg = (name, k, dez) => {
    const x = d.mengen.basis[k] - d.mengen.szenario[k];
    return "<tr><td>" + name + "</td><td>" + fmt(d.mengen.basis[k], dez) + "</td><td>" + fmt(d.mengen.szenario[k], dez) + "</td><td>" +
      (x >= 0 ? "−" : "+") + fmt(Math.abs(x), dez) + "</td></tr>";
  };
  el("opt-ergebnis").innerHTML =
    '<div class="opt-gross"><span>Gesamtbilanz Gebäude (' + mods.map(m => OPT_MOD_NAME[m]).join(" + ") + ")</span><b>" + fmt(b, 0) + " kg → " +
    fmt(s, 0) + ' kg CO₂e</b><span class="' + kl(e) + '">' + einsparText(e, 0) + " (" + prozent(e, b) + ") · " +
    (nAktiv ? nAktiv + " Ansatz/Ansätze als Szenario gewählt" : "noch kein Ansatz gewählt") + "</span></div>" +
    '<div class="opt-tabellen"><div class="wrap"><table class="t"><tr><th>Bauteilgruppe</th><th>Ist kg</th><th>Szenario kg</th><th>Einsparung</th><th>%</th></tr>' +
    d.gruppen.map(gruppenZeile).join("") + '<tr class="summe-zeile"><td>Gebäude gesamt</td><td>' + fmt(b, 0) + "</td><td>" + fmt(s, 0) +
    '</td><td class="' + kl(e) + '">' + einsparText(e, 0) + "</td><td>" + prozent(e, b) + "</td></tr></table></div>" +
    '<div class="wrap"><table class="t"><tr><th>Modul</th><th>Ist kg</th><th>Szenario kg</th><th>Einsparung</th></tr>' + modZeilen + "</table></div>" +
    '<div class="wrap"><table class="t"><tr><th>Materialmenge</th><th>Ist</th><th>Szenario</th><th>Differenz</th></tr>' +
    mg("Beton m³", "beton_m3", 2) + mg("Betonstahl kg", "betonstahl_kg", 0) + mg("Baustahl kg", "baustahl_kg", 0) + "</table></div></div>" +
    '<p class="klein">● = in der Seitenleiste gewähltes Modul. Negative Einsparung bei C und D entsteht z. B. beim Wechsel auf EcoPact: A1–A3 sinkt, ' +
    "dafür steigen C und D leicht. Mögliches Szenario, kein statischer Nachweis.</p>";
}

function zeichneOptDiagramme(d) {
  if (!el("opt-d1")) return;
  const namen = d.gruppen.map(g => g.name.replace(/ \(.*\)/, ""));
  const konf = { responsive: true, displaylogo: false, displayModeBar: false };
  Plotly.react("opt-d1", [
    { type: "bar", name: "Ist", x: namen, y: d.gruppen.map(g => optSumme(g.basis)), marker: { color: "#9aa5b1" } },
    { type: "bar", name: "Szenario (mögliche Änderung)", x: namen, y: d.gruppen.map(g => optSumme(g.szenario)), marker: { color: "#1a9850" } },
  ], { barmode: "group", height: 260, margin: { l: 55, r: 10, t: 34, b: 40 }, legend: { orientation: "h", y: 1.2 },
       title: { text: "CO₂e je Bauteilgruppe: Ist und Szenario (kg)", font: { size: 12 } }, font: { size: 11 }, yaxis: { title: "kg CO₂e" } }, konf);
  const ms = d.massnahmen.slice().sort((a, b) => optSumme(a.einzeln.gesamt) - optSumme(b.einzeln.gesamt));
  Plotly.react("opt-d2", [{
    type: "bar", orientation: "h", y: ms.map(m => m.name.replace(/ \(.*\)/, "")), x: ms.map(m => optSumme(m.einzeln.gesamt)),
    marker: { color: ms.map(m => (optSumme(m.einzeln.gesamt) >= 0 ? "#1a9850" : "#d7191c")) },
    text: ms.map(m => einsparText(optSumme(m.einzeln.gesamt), 0)), textposition: "auto", hoverinfo: "skip",
  }], { height: 280, margin: { l: 10, r: 20, t: 34, b: 40 }, font: { size: 10 },
        title: { text: "Einsparpotenzial je Ansatz allein (kg CO₂e, rechts = Einsparung, links = Mehremission)", font: { size: 12 } },
        yaxis: { automargin: true }, xaxis: { title: "kg CO₂e Einsparung", zeroline: true } }, konf);
}
