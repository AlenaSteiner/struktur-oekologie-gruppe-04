"use strict";
/* Bedienelemente aus dem Katalog aufbauen. */

const GRUPPEN_NAMEN = { baustahl: "Baustahl", beton: "Beton" };

function baueDatensaetze() {
  const box = el("datensaetze");
  box.innerHTML = "";
  for (const gruppe of ["baustahl", "beton"]) {      // Bauteil6 nutzt dieselben Beton- und Stahl-Datensaetze
    const varianten = S.katalog.datensaetze[gruppe];
    const div = document.createElement("div");
    div.innerHTML = "<h3>" + GRUPPEN_NAMEN[gruppe] + "</h3>";
    for (const v of ["standard", "alternative"]) {
      const d = varianten[v];
      const titel = d.name ? esc(d.name) : "(nicht geladen)";
      const gwp = d.gwp ? "A1–A3: " + fmt(d.gwp["A1-A3"], 3) + " kg CO₂e je " + d.einheit.replace("m3", "m³") : "";
      const label = document.createElement("label");
      label.className = "opt";
      label.innerHTML = '<input type="radio" name="ds-' + gruppe + '" value="' + v + '"' + (v === "standard" ? " checked" : "") +
        (d.fehler ? " disabled" : "") + "> <b>" + (v === "standard" ? "Standard" : "Alternative") + "</b>: " + titel;
      div.appendChild(label);
      const info = document.createElement("div");
      info.className = "ds-info";
      const hinweise = (d.hinweise || []).concat(d.luecken && d.luecken.length ? ["ohne Wert (als 0): " + d.luecken.join(", ")] : []);
      info.innerHTML = (d.fehler ? '<span class="warn">Fehler: ' + esc(d.fehler) + "</span><br>" : "") + esc(gwp) +
        (hinweise.length ? "<br>" + hinweise.map(esc).join("<br>") : "") +
        '<br><a href="' + esc(d.url) + '" target="_blank" rel="noopener">Datensatz in der ÖKOBAUDAT (JSON)</a>';
      div.appendChild(info);
    }
    box.appendChild(div);
  }
  box.querySelectorAll("input").forEach(i => i.addEventListener("change", () => planeRechnen(true)));
}

function baueMaterialwahl() {
  const box = el("material-wahl");
  box.innerHTML = "";
  for (const g of S.katalog.gruppen) {
    const div = document.createElement("div");
    div.className = "wahl";
    const optionen = Object.entries(S.katalog.materialien).map(([id, m]) =>
      '<option value="' + id + '"' + (id === g.standard_material ? " selected" : "") + ">" + esc(m.name) +
      (id === g.standard_material ? " (Vorgabe)" : "") + "</option>").join("");
    const typen = S.projekt === "bauteil6" ? g.profile.length + " IFC-Typen" : g.profile.join(", ");
    div.innerHTML = "<label>" + esc(g.name) + ' <span class="klein">· ' + esc(typen) + "</span></label>" +
      '<select data-gruppe="' + g.id + '">' + optionen + '</select><div class="warn" data-warn="' + g.id + '"></div>';
    box.appendChild(div);
  }
  box.querySelectorAll("select").forEach(s => s.addEventListener("change", () => planeRechnen(true)));
  const sel = el("tag-gruppe");
  sel.innerHTML = S.katalog.gruppen.map(g => '<option value="' + g.id + '">' + esc(g.name) + "</option>").join("");
  if (S.projekt !== "bauteil6") sel.addEventListener("change", ladeTagesverlauf);
}

function baueMaterialwerte() {
  el("materialwerte").innerHTML = Object.values(S.katalog.materialien).map(m =>
    "<details><summary>" + esc(m.name) + "</summary><table class=\"t\">" +
    "<tr><td>Absorption Sonne α</td><td>" + fmt(m.alpha, 2) + "</td></tr>" +
    "<tr><td>Emission ε</td><td>" + fmt(m.eps, 2) + "</td></tr>" +
    "<tr><td>Dichte</td><td>" + fmt(m.dichte, 0) + " kg/m³</td></tr>" +
    "<tr><td>Wärmekapazität</td><td>" + fmt(m.cp, 0) + " J/(kg·K)</td></tr>" +
    "<tr><td>Wärmeleitfähigkeit</td><td>" + fmt(m.k, 2) + " W/(m·K)</td></tr></table>" +
    '<span class="klein">' + esc(m.hinweis) + "</span></details>").join("") +
    '<p class="klein">Typische Literaturwerte als Annahme, nicht aus dem Modell. ' +
    "Absorption und Emission hängen stark von Farbe und Oberfläche ab (in <code>materialien.py</code> änderbar).</p>";
}

function baueFussnote() {
  if (S.projekt === "bauteil6") {
    el("fussnote").innerHTML = "<b>Grundlagen Bauteil6.</b> CO₂e = GWP-total je Lebenszyklus-Modul aus der ÖKOBAUDAT (live abgerufen). " +
      "Volumen aus der Geometrie des IFC-Modells, Masse = Volumen × Rohdichte. Betonstahl nach Bauteilart ist eine Annahme (Richtwerte), " +
      "Mauerwerk steht stellvertretend für Kalksandstein. Regeln: Seitenleiste. Module: C = C1+C2+C3+C4. Fehlende Werte zählen als 0.";
    return;
  }
  el("fussnote").innerHTML = "<b>Grundlagen.</b> CO₂e = GWP-total je Lebenszyklus-Modul aus der ÖKOBAUDAT (live abgerufen). " +
    "Volumen = Achslänge × Querschnittsfläche (bei verjüngten Flachstählen Mittel aus Anfangs- und Endfläche), " +
    "Masse = Volumen × Rohdichte des Materials. Beton enthält Betonstahl: laut Bewehrungsplan " + S.katalog.plan.nummer + " (" + fmt(S.katalog.plan.summe_kg, 2) +
    " kg für alle Fundamente, gleichmäßig auf die 47 Stäbe verteilt) oder pauschal " + S.katalog.bewehrung + " kg/m³ (umschaltbar). " +
    "Module: C = C1+C2+C3+C4. Fehlende Werte im Datensatz zählen als 0. " +
    "Für Aluminium und Holz gelten eigene Datensätze (nicht Teil der Aufgabe). " +
    "Die Sonnenerwärmung ist ein stark vereinfachtes Modell: kein Schattenwurf zwischen den Stäben, " +
    "Annahmen für Absorption und Emission, Lufttemperatur und Wind konstant. Sie zeigt Unterschiede zwischen den Materialien, " +
    "keine genauen Messwerte.";
}
