"use strict";
/* Kern: Zustand, Server-Aufrufe, Eingaben lesen, Werte je Stab. */

const S = { katalog: null, geo: null, erg: null, laufend: false, wieder: false, timer: null,
            projekt: new URLSearchParams(location.search).get("projekt") === "bauteil6" ? "bauteil6" : "stockerau" };

/* Pfad mit Projekt-Parameter (nur bei Bauteil6; Stockerau bleibt wie es war) */
function mitProjekt(pfad) {
  return S.projekt === "bauteil6" ? pfad + (pfad.includes("?") ? "&" : "?") + "p=bauteil6" : pfad;
}

function el(id) { return document.getElementById(id); }

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function fmt(x, d) {
  if (x === null || x === undefined || Number.isNaN(x)) return "–";
  const n = d === undefined ? 1 : d;
  return x.toLocaleString("de-AT", { minimumFractionDigits: n, maximumFractionDigits: n });
}

function zeitText(min) {
  const h = Math.floor(min / 60), m = min % 60;
  return String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0");
}

async function api(pfad, body) {
  const optionen = body === undefined ? {} :
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(pfad, optionen);
  if (!r.ok) {
    let text = r.statusText;
    try {
      const j = await r.json();
      text = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch (_) { /* keine JSON-Antwort */ }
    throw new Error(text);
  }
  return r.json();
}

/* ---------- Eingaben ---------- */

function gewaehlteModule() {
  const m = Array.from(document.querySelectorAll("input[name=modul]:checked")).map(x => x.value);
  return m.length ? m : ["A1-A3"];
}

function modus() {
  return document.querySelector("input[name=modus]:checked").value;
}

function leseConfig() {
  const cfg = { datensatz: {}, material: {}, umgebung: {} };
  for (const g of ["baustahl", "beton"]) {
    const r = document.querySelector("input[name=ds-" + g + "]:checked");
    if (r) cfg.datensatz[g] = r.value;
  }
  document.querySelectorAll("select[data-gruppe]").forEach(s => { cfg.material[s.dataset.gruppe] = s.value; });
  const bew = document.querySelector("input[name=bew]:checked");
  cfg.bewehrung = bew ? bew.value : "plan";
  cfg.module = gewaehlteModule();
  cfg.umgebung = {
    datum: el("datum").value, zeit: zeitText(Number(el("zeit").value)), himmel: el("himmel").value,
    t_luft: Number(el("t_luft").value), wind: Number(el("wind").value), nord: Number(el("nord").value),
    dauer: Number(el("dauer").value),
  };
  return cfg;
}

/* ---------- Werte je Stab ---------- */

function co2Wert(c) {
  if (!c) return null;
  return gewaehlteModule().reduce((a, m) => a + c[m], 0);
}

function stabWert(st, m) {
  const art = m || modus();
  if (art === "co2" || art === "opt") return co2Wert(st.co2);
  if (art === "t") return st.t;
  return st.t_spitze;
}

/* ---------- Rechnen (letzte Eingabe gewinnt) ---------- */

function planeRechnen(sofort) {
  clearTimeout(S.timer);
  S.timer = setTimeout(rechnen, sofort ? 0 : 250);
}

function zeigeFehler(text) {
  const b = el("banner");
  b.textContent = text;
  b.hidden = !text;
}

async function rechnen() {
  if (S.laufend) { S.wieder = true; return; }
  S.laufend = true;
  el("laden").hidden = false;
  try {
    S.erg = await api(mitProjekt("/api/rechnen"), leseConfig());
    const fehlt = S.erg.fehlende_datensaetze;
    zeigeFehler(fehlt.length ? "Datensatz nicht geladen: " + fehlt.join(", ") +
      ". Die CO₂-Werte dieser Stäbe fehlen (als 0 gezeichnet). Mit „Datensätze neu laden“ erneut versuchen." : "");
    zeichneAlles();
  } catch (e) {
    zeigeFehler("Rechnung fehlgeschlagen: " + e.message);
  } finally {
    S.laufend = false;
    el("laden").hidden = true;
    if (S.wieder) { S.wieder = false; rechnen(); }
  }
}

/* Aenderung, die nur die Darstellung betrifft (Modus, Module, Skala): kein Server-Aufruf noetig. */
function zeichneAlles() {
  if (!S.erg) return;
  zeichneSumme();
  aktualisiereSzene();
  renderGruppen();
  renderWarnungen();
  if (S.projekt !== "bauteil6") {            // Sonne, Materialvergleich und Tagesverlauf gibt es nur bei Stockerau
    renderVergleich();
    renderSonnenInfo();
    ladeTagesverlauf();
  }
  if (optAktiv()) planeOptimierung(true);        // Einstellungen geaendert: Optimierungsdaten neu holen
  if (reuseAktiv()) planeReuse(true);
}

function zeichneDarstellung() {
  if (!S.erg) return;
  zeichneSumme();
  aktualisiereSzene();
  renderGruppen();
  if (S.projekt !== "bauteil6") renderVergleich();
  if (optAktiv() && S.opt.daten) renderOptKarte();   // gewaehlte Module aendern die Summen
  if (reuseAktiv() && S.reuse.daten) renderReuseErgebnis();
}

function zeichneSumme() {
  const g = S.erg.gesamt, mods = gewaehlteModule();
  const summe = mods.reduce((a, m) => a + g[m], 0);
  const namen = { "A1-A3": "A1–A3", "C": "C1–C4", "D": "D" };
  el("summe").innerHTML =
    '<span class="gross">' + fmt(summe, 0) + ' kg CO₂e</span>' +
    '<span class="teil">gewählte Module: ' + mods.map(m => namen[m]).join(" + ") + '</span>' +
    Object.keys(namen).map(m => '<span class="teil">' + namen[m] + ': ' + fmt(g[m], 0) + ' kg</span>').join("");
}
