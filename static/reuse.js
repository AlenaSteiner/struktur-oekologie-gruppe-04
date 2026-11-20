"use strict";
/* Reuse-Planung: Zielentwurf aus Staeben des Pavillons zuschneiden (/api/reuse).
   Rechnerisches Szenario, kein statischer Nachweis, keine Zulassung zur Wiederverwendung. */

const REUSE_FARBEN = ["#c0504d", "#cfd4da", "#f59e0b", "#1a9850"];
const REUSE_TEXT = ["Fundament (kein Spender)", "Spender, nicht genutzt", "Spender, teilweise genutzt (unter 80 %)",
                    "Spender, weitgehend genutzt (ab 80 %)"];
const REUSE_KURZ = ["Fundament", "nicht genutzt", "teilweise", "weitgehend"];

S.reuse = { daten: null, std: null, ziel: [], parameter: {}, laeuft: false, wieder: false, timer: null, gebaut: false };

function reuseAktiv() { return modus() === "reuse"; }

/* Status je Stab: 0 Fundament, 1 nicht genutzt, 2 teilweise, 3 weitgehend. Ohne Ergebnis: nur nach Gruppe. */
function reuseWerte() {
  if (S.reuse.daten) return S.reuse.daten.stab.map(s => s.s);
  return S.erg.stab.map(s => (s.gruppe === "fundament" ? 0 : 1));
}

function reuseBerechne() {
  S.reuse.werte = reuseWerte();
  const f = REUSE_FARBEN, stops = [];
  f.forEach((c, i) => { stops.push([i / 4, c], [(i + 1) / 4, c]); });
  S.reuse.p = { min: -0.5, max: 3.5, farbskala: stops, umkehren: false, mitte: undefined, transform: v => v,
                tickvals: [0, 1, 2, 3], ticktext: REUSE_KURZ };
  el("szenario-badge").hidden = false;
}

function reuseLabel(i) {
  const s = S.reuse.werte[i], d = S.reuse.daten && S.reuse.daten.stab[i];
  if (s <= 1 || !d) return REUSE_TEXT[s];
  return REUSE_TEXT[s] + "<br>" + d.n + " Teile · " + fmt(100 * d.auslastung, 0) + " % genutzt · Rest " + fmt(d.rest_m, 2) + " m";
}

function reuseDetailHtml(i) {
  const s = S.reuse.werte[i], d = S.reuse.daten && S.reuse.daten.stab[i];
  if (!d) return "";
  return '<div class="opt-detail"><b>Reuse-Planung:</b> ' + esc(REUSE_TEXT[s]) +
    (s >= 2 ? '<div>' + d.n + " Zielteile zugeschnitten, " + fmt(100 * d.auslastung, 0) + " % des Stahlvolumens verwendet, Reststück " +
      fmt(d.rest_m, 2) + " m</div>" : "") + "</div>";
}

function planeReuse(sofort) {
  clearTimeout(S.reuse.timer);
  S.reuse.timer = setTimeout(ladeReuse, sofort ? 0 : 300);
}

async function ladeReuse() {
  if (!reuseAktiv() || !S.katalog) return;
  if (S.reuse.laeuft) { S.reuse.wieder = true; return; }
  S.reuse.laeuft = true;
  try {
    if (!S.reuse.std) {
      S.reuse.std = await api("/api/reuse/standard");
      S.reuse.ziel = S.reuse.std.ziel.map(z => Object.assign({}, z));
      S.reuse.parameter = Object.assign({}, S.reuse.std.parameter);
    }
    if (!S.reuse.gebaut) baueReuse();
    const cfg = leseConfig();
    cfg.ziel = S.reuse.ziel;
    cfg.parameter = S.reuse.parameter;
    S.reuse.daten = await api("/api/reuse", cfg);
    zeigeFehler("");
    renderReuseErgebnis();
    aktualisiereSzene();
  } catch (e) {
    zeigeFehler("Reuse-Planung fehlgeschlagen: " + e.message);
  } finally {
    S.reuse.laeuft = false;
    if (S.reuse.wieder) { S.reuse.wieder = false; ladeReuse(); }
  }
}

function reuseSchalte() {
  const an = reuseAktiv();
  el("reuse-steuerung").hidden = !an;
  el("reuse-karte").hidden = !an;
  if (an) planeReuse(true);
  else if (!optAktiv()) el("szenario-badge").hidden = true;
}
