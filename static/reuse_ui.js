"use strict";
/* Reuse-Planung: Oberflaeche (Zielentwurf, Annahmen). Rechnerisches Szenario. Ergebnis: reuse_ergebnis.js */

const REUSE_PARAMETER = [
  ["transport_max", "Max. Transportmaß", "m", 0.5], ["schnittverlust_mm", "Schnittverlust", "mm", 1],
  ["min_rest", "Mindestlänge Reststück", "m", 0.1], ["ueberbreite_mm", "Max. Überbreite Flachstahl", "mm", 5],
  ["schnitt_co2", "CO₂e je Schnitt (Annahme)", "kg", 0.1], ["transport_co2", "CO₂e Transport (Annahme)", "kg/t·km", 0.01],
  ["km_reuse", "Entfernung Spender", "km", 10], ["km_neu", "Entfernung Neuware", "km", 10],
  ["min_schnitt", "Zeit je Schnitt", "min", 1], ["min_ausbau", "Ausbau je Spenderstab", "min", 5],
  ["min_pruefung", "Prüfung je Spenderstab", "min", 5], ["tage_neu", "Lieferzeit Neuware", "Tage", 1],
  ["tage_reuse", "Bereitstellung Spender", "Tage", 1],
];

function reuseZielZeile(z, n) {
  const typen = S.reuse.std.typen, flach = z.typ === "flach";
  const feld = (f, schritt) => '<td><input type="number" data-f="' + f + '" value="' + z[f] + '" step="' + schritt + '" min="0"' +
    (!flach && (f === "breite" || f === "dicke") ? " disabled" : "") + "></td>";
  return '<tr data-z="' + n + '"><td><select data-f="typ">' + Object.keys(typen).map(t =>
      '<option value="' + t + '"' + (t === z.typ ? " selected" : "") + ">" + esc(typen[t]) + "</option>").join("") + "</select></td>" +
    feld("breite", 1) + feld("dicke", 1) + feld("laenge", 0.05) + feld("anzahl", 1) +
    '<td><button type="button" data-del="' + n + '" title="Zeile löschen">✕</button></td></tr>';
}

function baueZielTabelle() {
  el("reuse-ziel").innerHTML = '<table class="t"><tr><th>Typ</th><th>Breite mm</th><th>Dicke mm</th><th>Länge m</th><th>Anzahl</th><th></th></tr>' +
    S.reuse.ziel.map(reuseZielZeile).join("") + "</table>";
  el("reuse-ziel").querySelectorAll("tr[data-z]").forEach(tr => {
    const z = S.reuse.ziel[Number(tr.dataset.z)];
    tr.querySelectorAll("[data-f]").forEach(inp => inp.addEventListener("change", () => {
      z[inp.dataset.f] = inp.dataset.f === "typ" ? inp.value : Number(inp.value);
      if (inp.dataset.f === "typ") baueZielTabelle();
      planeReuse(false);
    }));
  });
  el("reuse-ziel").querySelectorAll("[data-del]").forEach(b => b.addEventListener("click", () => {
    S.reuse.ziel.splice(Number(b.dataset.del), 1);
    baueZielTabelle();
    planeReuse(true);
  }));
}

function baueParameter() {
  el("reuse-parameter").innerHTML = '<div class="kv">' + REUSE_PARAMETER.map(([k, name, einheit, schritt]) =>
    '<label class="zeile">' + esc(name) + ' <span><input type="number" data-p="' + k + '" value="' + S.reuse.parameter[k] +
    '" step="' + schritt + '" min="0" style="width:80px"> ' + esc(einheit) + "</span></label>").join("") + "</div>";
  el("reuse-parameter").querySelectorAll("[data-p]").forEach(inp => inp.addEventListener("change", () => {
    S.reuse.parameter[inp.dataset.p] = Number(inp.value);
    planeReuse(false);
  }));
}

function baueReuse() {
  baueParameter();
  baueZielTabelle();
  el("reuse-neu-zeile").addEventListener("click", () => {
    S.reuse.ziel.push({ typ: "rund", breite: 0, dicke: 0, laenge: 1, anzahl: 1 });
    baueZielTabelle();
    planeReuse(true);
  });
  el("reuse-zurueck").addEventListener("click", () => {
    S.reuse.ziel = S.reuse.std.ziel.map(z => Object.assign({}, z));
    S.reuse.parameter = Object.assign({}, S.reuse.std.parameter);
    baueParameter();
    baueZielTabelle();
    planeReuse(true);
  });
  el("reuse-legende").innerHTML = REUSE_FARBEN.map((c, i) => '<li><span class="bew-punkt" style="background:' + c + '"></span>' +
    esc(REUSE_TEXT[i]) + ' <span id="reuse-n' + i + '"></span></li>').join("");
  S.reuse.gebaut = true;
}
