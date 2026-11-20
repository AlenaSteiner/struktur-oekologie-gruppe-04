"use strict";
/* Optimierung: Oberflaeche (Ansaetze, Szenario-Ergebnis, Diagramme). Rechnerische Szenarien, kein statischer Nachweis. */

function optSchalte() {
  const an = optAktiv();
  el("opt-steuerung").hidden = !an;
  el("opt-karte").hidden = !an;
  if (an) planeOptimierung(true);
  else el("szenario-badge").hidden = true;
}

function planeOptimierung(sofort) {
  clearTimeout(S.opt.timer);
  S.opt.timer = setTimeout(ladeOptimierung, sofort ? 0 : 250);
}

async function ladeOptimierung() {
  if (!optAktiv() || !S.katalog) return;
  if (S.opt.laeuft) { S.opt.wieder = true; return; }
  S.opt.laeuft = true;
  try {
    const cfg = leseConfig();
    cfg.massnahmen = S.opt.massnahmen;
    const d = await api("/api/optimierung", cfg);
    S.opt.daten = d;
    for (const m of d.massnahmen) {
      if (!S.opt.massnahmen[m.id]) S.opt.massnahmen[m.id] = { aktiv: false, wert: m.wert };
    }
    renderOptKarte();
    aktualisiereSzene();
  } catch (e) {
    zeigeFehler("Optimierung fehlgeschlagen: " + e.message);
  } finally {
    S.opt.laeuft = false;
    if (S.opt.wieder) { S.opt.wieder = false; ladeOptimierung(); }
  }
}

/* ---------- Karte: Ansaetze + Ergebnis ---------- */

function omRegler(m) {
  if (m.art === "prozent") {
    return '<input type="range" data-om="' + m.id + '" min="' + m.min + '" max="' + m.max + '" step="' + m.schritt +
      '" value="' + m.wert + '"><span class="om-wert" id="omw-' + m.id + '">' + m.wert + " " + m.einheit + "</span>";
  }
  if (m.art === "auswahl") {
    return '<select data-om="' + m.id + '">' + m.optionen.map(o =>
      '<option value="' + o + '"' + (o === m.wert ? " selected" : "") + ">" + fmt(o, 1) + " " + m.einheit + "</option>").join("") + "</select>";
  }
  return "";
}

function baueMassnahmen(d) {
  el("opt-massnahmen").innerHTML = "<h3>Optimierungsansätze · mögliche Szenarien</h3>" +
    '<p class="klein">Ansätze anhaken, um sie zu einem Szenario zu kombinieren. Die Einsparung je Ansatz gilt für ihn allein; ' +
    "das Szenario wird mit allen gewählten Ansätzen zusammen neu gerechnet (Wechselwirkungen eingerechnet).</p>" +
    d.massnahmen.map(m => '<div class="om"><label class="om-kopf"><input type="checkbox" data-oma="' + m.id + '"> <b>' + esc(m.name) +
      '</b></label><div class="om-zeile">' + omRegler(m) + '<span class="om-gilt klein">gilt für: ' + esc(m.gruppen) + "</span></div>" +
      '<div class="om-ersparnis" id="ome-' + m.id + '"></div><div class="klein">' + esc(m.hinweis) + "</div></div>").join("") +
    '<button type="button" id="opt-aus">Alle Ansätze ausschalten</button>';
  el("opt-diagramm").innerHTML = '<div id="opt-d1" class="opt-chart"></div><div id="opt-d2" class="opt-chart"></div>';
  S.opt.gebaut = true;
  verdrahteMassnahmen();
}

function verdrahteMassnahmen() {
  document.querySelectorAll("[data-oma]").forEach(cb => cb.addEventListener("change", () => {
    S.opt.massnahmen[cb.dataset.oma].aktiv = cb.checked;
    if (cb.checked) el("opt-ansicht").value = "szenario";
    planeOptimierung(true);
  }));
  document.querySelectorAll("[data-om]").forEach(r => r.addEventListener(r.tagName === "SELECT" ? "change" : "input", () => {
    S.opt.massnahmen[r.dataset.om].wert = Number(r.value);
    const w = el("omw-" + r.dataset.om);
    if (w) w.textContent = r.value + " %";
    planeOptimierung(false);
  }));
  el("opt-aus").addEventListener("click", () => {
    Object.values(S.opt.massnahmen).forEach(m => { m.aktiv = false; });
    el("opt-ansicht").value = "ist";
    planeOptimierung(true);
  });
}

function renderOptKarte() {
  const d = S.opt.daten;
  if (!d) return;
  el("opt-hinweis").innerHTML = "<b>Mögliche Szenarien, keine statisch nachgewiesenen Änderungen.</b> " +
    "Tragfähigkeit, Gebrauchstauglichkeit, Herstellbarkeit und Verfügbarkeit sind nicht geprüft. " +
    "Die Werte sind rechnerisch aus den ÖKOBAUDAT-Datensätzen abgeleitet." +
    (d.warnungen.length ? '<br><span class="warn">⚠ ' + d.warnungen.map(esc).join("<br>⚠ ") + "</span>" : "");
  if (!S.opt.gebaut) baueMassnahmen(d);
  const basis = optModulSumme(d.gesamt.basis) || 1;
  for (const m of d.massnahmen) {
    const ein = optModulSumme(m.einzeln.gesamt);
    const box = el("ome-" + m.id);
    box.className = "om-ersparnis " + (ein >= 0 ? "gut" : "schlecht");
    box.textContent = "allein: " + einsparText(ein, 0) + " CO₂e (" + (ein >= 0 ? "−" : "+") + fmt(Math.abs(100 * ein / basis), 1) +
      " % der Gebäudebilanz) · " + m.betroffen + " Stäbe betroffen";
    const cb = document.querySelector('[data-oma="' + m.id + '"]');
    if (cb) cb.checked = !!S.opt.massnahmen[m.id].aktiv;
  }
  renderOptErgebnis(d);
  zeichneOptDiagramme(d);
}
