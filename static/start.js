"use strict";
/* Start: Schalter verdrahten, Daten laden, erste Rechnung. */

function verdrahte() {
  document.querySelectorAll("input[name=modus], input[name=modul]").forEach(i => i.addEventListener("change", zeichneDarstellung));
  el("skala").addEventListener("change", zeichneDarstellung);
  document.querySelectorAll("input[name=modus]").forEach(i => i.addEventListener("change", optSchalte));
  document.querySelectorAll("input[name=modus]").forEach(i => i.addEventListener("change", reuseSchalte));
  ["opt-ansicht", "opt-skala", "opt-nur-hotspots"].forEach(id => el(id).addEventListener("change", zeichneDarstellung));
  el("opt-schwelle").addEventListener("input", () => {
    el("opt-schwelle-anzeige").textContent = el("opt-schwelle").value + " %";
    zeichneDarstellung();
  });
  document.querySelectorAll("input[name=bew]").forEach(i => i.addEventListener("change", () => { planeRechnen(true); setTimeout(zeigePlan, 400); }));
  verdrahtePlan();
  el("vergleich").addEventListener("change", schalteVergleich);
  el("bew3d").addEventListener("change", schalteBewehrung);
  ["datum", "himmel", "t_luft", "wind", "nord"].forEach(id => el(id).addEventListener("change", () => planeRechnen(true)));
  el("zeit").addEventListener("input", () => { el("zeit-anzeige").textContent = zeitText(Number(el("zeit").value)); planeRechnen(false); });
  el("dauer").addEventListener("input", () => {
    const d = Number(el("dauer").value);
    el("dauer-anzeige").textContent = d === 0 ? "Dauerzustand" : d + " min";
    planeRechnen(false);
  });
  el("reset-material").addEventListener("click", () => {
    document.querySelectorAll("select[data-gruppe]").forEach(s => {
      s.value = S.katalog.gruppen.find(x => x.id === s.dataset.gruppe).standard_material;
    });
    planeRechnen(true);
  });
  el("neu-laden").addEventListener("click", async () => {
    const knopf = el("neu-laden");
    knopf.disabled = true; knopf.textContent = "lade von ÖKOBAUDAT …";
    try {
      const gewaehlt = leseConfig().datensatz;
      await api("/api/datensaetze-neu-laden", {});
      S.katalog = await api(mitProjekt("/api/katalog"));
      baueDatensaetze();
      for (const [g, v] of Object.entries(gewaehlt)) {
        const r = document.querySelector("input[name=ds-" + g + "][value=" + v + "]");
        if (r && !r.disabled) r.checked = true;
      }
      planeRechnen(true);
    } catch (e) { zeigeFehler("Neu laden fehlgeschlagen: " + e.message); }
    knopf.disabled = false; knopf.textContent = "Datensätze neu von ÖKOBAUDAT laden";
  });
}

/* Projektwahl: Seite mit dem anderen Projekt neu laden (so bleibt jedes Projekt unveraendert nutzbar). */
function baueProjektwahl() {
  const sel = el("projekt-wahl");
  const liste = S.katalog.projekte || [{ id: "stockerau", name: "Pavillon Stockerau" }];
  sel.innerHTML = liste.map(p => '<option value="' + p.id + '"' + (p.id === S.projekt ? " selected" : "") + ">" + esc(p.name) + "</option>").join("");
  sel.addEventListener("change", () => {
    location.search = sel.value === "bauteil6" ? "?projekt=bauteil6" : "";
  });
}

/* Anzeige je Projekt: bei Bauteil6 ohne Sonne, Bewehrungsplan und Optimierung; dafuer die Regeln. */
function passeProjektAn() {
  const b6 = S.projekt === "bauteil6";
  document.body.classList.toggle("projekt-bauteil6", b6);
  el("b6-info").hidden = !b6;
  el("projekt-titel").textContent = b6 ? "Bauteil6" : "Pavillon Stockerau";
  el("projekt-untertitel").textContent = b6 ? "Embodied Carbon je IFC-Bauteil" : "Embodied Carbon & Sonnenerwärmung";
  document.title = "Embodied Carbon · " + (b6 ? "Bauteil6" : "Pavillon Stockerau");
  if (!b6) return;
  const k = S.katalog.statistik;
  el("b6-statistik").innerHTML = k.bauteile + " Bauteile in " + k.geschosse + " Geschossen · " + k.offen + " Netze offen · " +
    k.abweichung + " Bauteile mit Volumenabweichung über 10 % (IFC ↔ Geometrie)";
  el("b6-regeln").innerHTML = S.katalog.regeln.map(r => "<details><summary>" + esc(r.titel) + "</summary><p class=\"klein\">" +
    esc(r.text) + "</p></details>").join("");
}

async function start() {
  S.auswahl = null;
  try {
    [S.katalog, S.geo] = await Promise.all([api(mitProjekt("/api/katalog")), api(mitProjekt("/api/geometrie"))]);
  } catch (e) {
    zeigeFehler("Server nicht erreichbar oder noch am Laden: " + e.message);
    return;
  }
  berechneZentren();
  baueProjektwahl();
  passeProjektAn();
  baueDatensaetze();
  baueMaterialwahl();
  if (S.projekt !== "bauteil6") baueMaterialwerte();
  baueFussnote();
  verdrahte();
  await rechnen();
}

start();
