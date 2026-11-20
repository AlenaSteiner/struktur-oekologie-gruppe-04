"use strict";
/* Optimierung: Hotspot-Liste (Seitenleiste) und Detail beim Anklicken. Nur rechnerische Szenarien. */

function renderHotspots() {
  const box = el("opt-hotspots");
  if (!S.erg || !S.opt.hs) { box.innerHTML = ""; return; }
  const { hot, sortiert, k } = S.opt.hs, w = S.opt.werte;
  const summe = w.reduce((a, v) => a + Math.max(v, 0), 0) || 1;
  const anteil = sortiert.slice(0, k).reduce((a, i) => a + Math.max(w[i], 0), 0) / summe;
  const gr = optGruppenInfo(w, hot).filter(g => g.hot > 0 || g.gleich);
  const gruppenText = gr.map(g => "<li><b>" + esc(g.name.replace(/ \(.*\)/, "")) + "</b>: " + (g.gleich && g.n > 1
    ? "alle " + g.n + " Stäbe ähnlich hoch (" + fmt(100 * g.anteil, 0) + " % der Bilanz), gemeinsam ein Hotspot"
    : g.hot + " von " + g.n + " im Hotspot") + "</li>").join("");
  const top = sortiert.slice(0, 8).map((i, r) => {
    const s = S.erg.stab[i];
    return '<li><a href="#" data-hs="' + i + '">' + (r + 1) + ". Stab " + esc(s.id) + "</a> · " + esc(s.profil.replace(/ \|.*/, "")) +
      " · <b>" + fmt(w[i], 1) + " kg</b></li>";
  }).join("");
  box.innerHTML = '<p class="klein"><b>' + k + " Hotspot-Stäbe</b> verursachen " + fmt(100 * anteil, 0) + " % der CO₂e (" +
    (el("opt-ansicht").value === "szenario" ? "Szenario" : "Ist") + ').</p><ul class="hs-liste klein">' + gruppenText + "</ul>" +
    '<p class="klein"><b>Höchste Einzelwerte</b> (Klick = auswählen)</p><ol class="hs-liste klein">' + top + "</ol>";
  box.querySelectorAll("[data-hs]").forEach(a => a.addEventListener("click", ev => {
    ev.preventDefault();
    S.auswahl = Number(a.dataset.hs);
    renderAuswahl(); aktualisiereSzene(); zeigePlan();
  }));
}

/* Detail im Auswahlfeld: Mengen, CO2e, Rang, Ansaetze fuer genau diesen Stab. */
function optDetailHtml(i) {
  const d = S.opt.daten, s = S.erg.stab[i];
  if (!d || !S.opt.hs) return "";
  const ist = optSumme(d.basis[i]), sz = optSumme(d.szenario[i]);
  const rang = S.opt.hs.rang[i], n = S.erg.stab.length;
  const gesamtB = optSumme(d.gesamt.basis) || 1;
  const gruppe = S.erg.gruppen.find(g => g.id === s.gruppe);
  const gleiche = d.massnahmen.map(m => ({ m, e: m.einzeln.stab[String(i)] })).filter(x => x.e);
  const mats = s.gruppe === "fundament"
    ? "Beton " + fmt(s.menge, 3) + " m³ · Betonstahl " + fmt(s.bewehrung_kg, 1) + " kg"
    : "Stahl " + fmt(s.menge, 2) + " kg";
  const ansaetze = gleiche.length ? gleiche.map(x => {
    const e = optSumme(x.e), ges = optSumme(x.m.einzeln.gesamt);
    return "<li><b>" + esc(x.m.name) + "</b>: " + einsparText(e, 1) + " an diesem Stab · " + einsparText(ges, 0) + " an allen " + x.m.betroffen +
      " Stäben dieser Art" + (x.m.aktiv ? " <i>(im Szenario)</i>" : "") + "</li>";
  }).join("") : '<li class="klein">Für diese Bauteilart gibt es keinen Ansatz im Katalog.</li>';
  return '<div class="opt-detail"><h2>Optimierung · mögliche Szenarien</h2><p class="klein">Mögliche Szenarien, kein statischer Nachweis.</p>' +
    "<div>Materialmengen: <b>" + mats + "</b></div>" +
    "<div>CO₂e (gewählte Module): <b>" + fmt(ist, 2) + " kg</b>" + (Math.abs(ist - sz) > 1e-6 ? " → Szenario <b>" + fmt(sz, 2) + " kg</b>" : "") +
    " · " + fmt(100 * ist / gesamtB, 2) + " % der Gebäudebilanz · Rang " + rang + " von " + n +
    (S.opt.hs.hot.has(i) ? ' · <b class="schlecht">Hotspot</b>' : "") + "</div>" +
    (gruppe ? '<div class="klein">Gruppe „' + esc(gruppe.name) + "“: " + gruppe.n + " Stäbe</div>" : "") +
    '<h3>Mögliche Ansätze für diesen Stab</h3><ul class="hs-liste">' + ansaetze + "</ul></div>";
}
