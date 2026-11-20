"use strict";
/* Kleines Fenster mit dem 2D-Bewehrungsplan. Erscheint beim Klick auf einen Stab; bei Fundamenten ist der
   angeklickte Streifenabschnitt im Plan markiert. */

async function ladePlanLage() {
  if (S.planLage) return S.planLage;
  S.planLage = await api("/api/plan/lage");
  return S.planLage;
}

function stablisteHtml() {
  const p = S.katalog.plan;
  const zeilen = p.stabliste.map(z => "<tr><td>" + z.pos + "</td><td>" + z.stueck + "</td><td>Ø" + z.durchmesser + "</td><td>" +
    fmt(z.einzel, 2) + "</td><td>" + fmt(z.gesamt, 2) + "</td><td>" + fmt(z.masse, 2) + "</td></tr>").join("");
  return '<table class="t"><tr><th>Pos.</th><th>Stk.</th><th>ø mm</th><th>Länge m</th><th>Gesamt m</th><th>kg</th></tr>' +
    zeilen + '<tr class="summe-zeile"><td colspan="5">Gesamtmasse</td><td>' + fmt(p.summe_kg, 2) + "</td></tr></table>";
}

async function zeigePlan() {
  const fenster = el("plan-fenster");
  if (S.projekt === "bauteil6") { fenster.hidden = true; return; }     // Bauteil6: kein Bewehrungsplan-Fenster
  if (S.vergleich) { fenster.hidden = true; return; }     // im Vergleichsmodus ist der Plan fest neben dem 3D-Modell
  if (S.auswahl === null || !S.erg) { fenster.hidden = true; return; }
  const s = S.erg.stab[S.auswahl];
  fenster.hidden = false;
  el("plan-titel").textContent = "Stab " + s.id + " · " + s.profil;
  const koerper = el("plan-koerper");
  if (s.gruppe !== "fundament") {
    koerper.innerHTML = '<p class="klein">Für diesen Querschnitt gibt es keinen Bewehrungsplan. Der Plan <b>' + esc(S.katalog.plan.nummer) +
      "</b> gilt nur für die Streifenfundamente (Rectangle 500/500).</p>";
    return;
  }
  const nr = (S.planNr = (S.planNr || 0) + 1);
  try {
    const d = await ladePlanLage();
    if (nr !== S.planNr) return;
    const l = d.lage[String(S.auswahl)];
    const p = S.katalog.plan;
    const bew = S.erg.config.bewehrung === "plan"
      ? "Bewehrung laut Plan: " + fmt(p.kg_pro_m3, 1) + " kg/m³ (Mittel über alle Fundamente)"
      : "Bewehrung pauschal: " + fmt(S.katalog.bewehrung, 0) + " kg/m³ (Plan nur zur Ansicht)";
    koerper.innerHTML =
      '<div class="plan-bild"><img src="/api/plan/bild.png" alt="Bewehrungsplan Streifenfundamente">' +
      '<div class="plan-marke" style="left:' + (l[0] * 100) + "%;top:" + (l[1] * 100) + "%;width:" + ((l[2] - l[0]) * 100) +
      "%;height:" + ((l[3] - l[1]) * 100) + '%"></div></div>' +
      '<p class="klein">' + esc(p.nummer) + " · " + esc(p.beton) + ", " + esc(p.betonstahl) + ", Deckung " + fmt(p.deckung_cm, 1) +
      " cm<br>" + esc(bew) + "<br>Dieser Stab: " + fmt(s.bewehrung_kg, 1) + " kg Betonstahl</p>" +
      "<details><summary>Stabliste (Biegeformen)</summary>" + stablisteHtml() + "</details>";
  } catch (e) {
    koerper.textContent = "Plan nicht verfügbar: " + e.message;
  }
}

function verdrahtePlan() {
  el("plan-zu").addEventListener("click", () => { el("plan-fenster").hidden = true; });
  el("plan-gross").addEventListener("click", () => el("plan-fenster").classList.toggle("gross"));
  el("dock-zoom").addEventListener("change", aktualisierePlanDock);
  el("dock-bild").addEventListener("load", aktualisierePlanDock);
  window.addEventListener("resize", aktualisierePlanDock);
}

/* ---------- Vergleichsmodus: 3D-Modell und Bewehrungsplan nebeneinander ---------- */

const PLAN_ZOOM = 3;          // Vergroesserung beim Zoom auf den markierten Abschnitt

function schalteVergleich() {
  S.vergleich = el("vergleich").checked;
  document.body.classList.toggle("vergleich", S.vergleich);
  if (S.vergleich) {
    el("plan-fenster").hidden = true;
    const bild = el("dock-bild");
    if (!bild.getAttribute("src")) bild.src = "/api/plan/bild.png";
    el("dock-titel").textContent = "Bewehrungsplan · " + S.katalog.plan.nummer;
    el("dock-stabliste").innerHTML = "<details><summary>Stabliste (Biegeformen)</summary>" + stablisteHtml() + "</details>";
  }
  // das 3D-Modell bekommt eine andere Breite
  setTimeout(() => { Plotly.Plots.resize(el("szene")); aktualisierePlanDock(); }, 60);
}

function setzeMarke(knoten, l) {
  if (!l) { knoten.hidden = true; return; }
  knoten.hidden = false;
  knoten.style.left = (l[0] * 100) + "%";
  knoten.style.top = (l[1] * 100) + "%";
  knoten.style.width = ((l[2] - l[0]) * 100) + "%";
  knoten.style.height = ((l[3] - l[1]) * 100) + "%";
}

/* Ausschnitt: ohne Lage der ganze Plan (eingepasst), sonst um die Markierung herangezoomt. */
function setzeAnsicht(l) {
  const vp = el("dock-viewport"), bild = el("dock-bild");
  const Vw = vp.clientWidth, Vh = vp.clientHeight;
  if (!Vw || !bild.naturalWidth) return;
  const H = Vw * bild.naturalHeight / bild.naturalWidth;
  const klemme = (v, a, b) => Math.min(Math.max(v, Math.min(a, b)), Math.max(a, b));
  let z, tx, ty;
  if (l && el("dock-zoom").checked) {
    z = PLAN_ZOOM;
    tx = klemme(Vw / 2 - ((l[0] + l[2]) / 2) * Vw * z, Vw - Vw * z, 0);
    ty = klemme(Vh / 2 - ((l[1] + l[3]) / 2) * H * z, Vh - H * z, 0);
  } else {
    z = Math.min(1, Vh / H);
    tx = (Vw - Vw * z) / 2;
    ty = (Vh - H * z) / 2;
  }
  el("dock-inhalt").style.transform = "translate(" + tx + "px," + ty + "px) scale(" + z + ")";
}

function dockText(n, hatLage) {
  const p = S.katalog.plan;
  if (n === null) return '<span class="klein">Mit der Maus über ein Fundament fahren oder eines anklicken. Der zugehörige Abschnitt ist im Plan markiert.</span>';
  const s = S.erg.stab[n];
  const kopf = "<b>Stab " + s.id + "</b> · " + esc(s.profil) + " · " + esc(matName(s.material)) + "<br>";
  if (!hatLage) {
    return kopf + '<span class="klein">Für diesen Querschnitt gibt es keinen Bewehrungsplan. Der Plan gilt nur für die Streifenfundamente (Rectangle 500/500).</span>';
  }
  const bew = S.erg.config.bewehrung === "plan"
    ? "Bewehrung laut Plan: " + fmt(p.kg_pro_m3, 1) + " kg/m³ (Mittel über alle Fundamente)"
    : "Bewehrung pauschal: " + fmt(S.katalog.bewehrung, 0) + " kg/m³ (Plan nur zur Ansicht)";
  return kopf + "Länge " + fmt(s.laenge, 2) + " m · Betonstahl in diesem Stab: <b>" + fmt(s.bewehrung_kg, 1) + " kg</b>" +
    '<br><span class="klein">' + esc(bew) + "</span>";
}

function aktualisierePlanDock() {
  if (!S.vergleich || !S.erg || !S.katalog) return;
  if (!S.planLage) {
    ladePlanLage().then(aktualisierePlanDock).catch(e => { el("dock-text").textContent = "Plan nicht verfügbar: " + e.message; });
    return;
  }
  const lage = n => (n === null || n === undefined ? null : S.planLage.lage[String(n)] || null);
  const lHover = lage(S.hover), lFest = lage(S.auswahl);
  setzeMarke(el("dock-fest"), lFest);
  setzeMarke(el("dock-marke"), S.hover !== S.auswahl ? lHover : null);   // Hover auf dem gewaehlten Stab: nur blau
  const fokus = lHover || lFest;                       // Hover hat Vorrang, sonst der angeklickte Stab
  setzeAnsicht(fokus);
  const aktuell = S.hover !== null && S.hover !== undefined ? S.hover : S.auswahl;   // Text: Hover, sonst der angeklickte Stab
  el("dock-text").innerHTML = dockText(aktuell, aktuell !== null && !!lage(aktuell));
  el("dock-viewport").classList.toggle("gedimmt", aktuell !== null && !lage(aktuell));   // Bauteil ohne Plan: Plan abgedunkelt
}
