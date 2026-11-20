"use strict";
/* Neue Ansicht ohne Temperatur und Sonnenseite.
   Die gemeinsamen Skripte in /static bleiben unverändert; hier wird nur ausgeblendet, was die Temperatur betrifft. */

(function () {
  const SPALTEN_GRUPPEN = ["T Mittel °C", "T Spitze °C", "τ min"];
  const SPALTEN_VERGLEICH = ["α Sonne", "ε", "T Mittel °C", "T Spitze max °C", "τ Median min"];
  const ZEILEN_AUSWAHL = ["Temperatur Mittel", "Temperatur Sonnenseite", "Zeitkonstante", "Biot-Zahl"];

  /* Spalten einer Tabelle anhand der Überschrift entfernen */
  function entferneSpalten(boxId, namen) {
    el(boxId).querySelectorAll("table.t").forEach(tab => {
      const kopf = tab.rows[0];
      if (!kopf) return;
      const weg = [];
      Array.from(kopf.cells).forEach((c, i) => { if (namen.includes(c.textContent.trim())) weg.push(i); });
      weg.reverse();
      Array.from(tab.rows).forEach(r => weg.forEach(i => { if (r.cells[i]) r.deleteCell(i); }));
    });
  }

  const altGruppen = renderGruppen;
  renderGruppen = function () { altGruppen(); entferneSpalten("tab-gruppen", SPALTEN_GRUPPEN); };

  const altVergleich = renderVergleich;
  renderVergleich = function () { altVergleich(); entferneSpalten("tab-vergleich", SPALTEN_VERGLEICH); };

  const altAuswahl = renderAuswahl;
  renderAuswahl = function () {
    altAuswahl();
    const box = el("auswahl");
    box.querySelectorAll(".kv > div").forEach(d => {
      if (ZEILEN_AUSWAHL.some(z => d.firstChild && String(d.firstChild.textContent).startsWith(z))) d.remove();
    });
    box.querySelectorAll("p.klein").forEach(p => { if (p.textContent.includes("Biot")) p.remove(); });
  };

  /* Tagesverlauf wird nicht mehr angezeigt, also auch nicht abgefragt */
  ladeTagesverlauf = function () {};

  const altFussnote = baueFussnote;
  baueFussnote = function () {
    altFussnote();
    const f = el("fussnote");
    const i = f.innerHTML.indexOf("Die Sonnenerwärmung");
    if (i > 0) f.innerHTML = f.innerHTML.slice(0, i).trim();
  };

  const altProjekt = passeProjektAn;
  passeProjektAn = function () {
    altProjekt();
    if (S.projekt !== "bauteil6") el("projekt-untertitel").textContent = "Embodied Carbon";
  };
})();
