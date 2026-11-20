"use strict";
/* Neue Ansicht: Bauteil6 mit denselben Funktionen wie der Pavillon (Optimierung, Reuse, Bewehrungspläne,
   Vergleichsmodus, 3D-Bewehrung, Materialvergleich). Die gemeinsamen Skripte in /static bleiben unverändert;
   hier werden für Bauteil6 nur die Aufrufe (?p=bauteil6) und die Anzeige angepasst.
   Wird nach start.js geladen: start() wartet noch auf den Server, alle Ersetzungen gelten also schon. */

(function () {
  const B6 = S.projekt === "bauteil6";

  /* Materialvergleich: Kopfzeile mit der richtigen Anzahl (beide Projekte) */
  const altVergleich = renderVergleich;
  renderVergleich = function () {
    altVergleich();
    const th = el("tab-vergleich").querySelector("th");
    if (th && S.erg) th.textContent = "Material für alle " + S.erg.stab.length + (B6 ? " Bauteile" : " Stäbe");
  };

  if (!B6) return;

  /* ---------- Server-Aufrufe mit Projekt ---------- */
  const altApi = api;
  api = function (pfad, body) {
    if (/^\/api\/(optimierung|reuse|bewehrung3d|plan)/.test(pfad) && !/[?&]p=/.test(pfad)) {
      pfad += (pfad.includes("?") ? "&" : "?") + "p=bauteil6";
    }
    return altApi(pfad, body);
  };

  /* Materialvergleich gibt es jetzt auch für Bauteil6 (die gemeinsamen Skripte rufen ihn nur für Stockerau auf) */
  const altAlles = zeichneAlles, altDarstellung = zeichneDarstellung;
  zeichneAlles = function () { altAlles(); if (S.erg) renderVergleich(); };
  zeichneDarstellung = function () { altDarstellung(); if (S.erg) renderVergleich(); };

  /* ---------- Reuse: Spender sind die Stahlprofile ---------- */
  REUSE_TEXT[0] = "Beton, Mauerwerk, Holz (kein Spender)";
  REUSE_KURZ[0] = "kein Spender";
  reuseWerte = function () {
    if (S.reuse.daten) return S.reuse.daten.stab.map(s => s.s);
    return S.erg.stab.map(s => (s.material === "stahl" ? 1 : 0));
  };
  const altReuse = renderReuseErgebnis;
  renderReuseErgebnis = function () {
    altReuse();
    el("reuse-zeilen").querySelectorAll("th").forEach(t => { t.textContent = t.textContent.replace("Spenderstäbe (RFEM-Nr.)", "Spender (Bauteil-Nr.)"); });
    el("reuse-kennzahlen").querySelectorAll(".kv > div").forEach(d => {
      if (d.firstChild && d.firstChild.textContent === "Genutzte Spenderstäbe") d.firstChild.textContent = "Genutzte Spender (Stahlprofile)";
    });
    for (let i = 0; i < 4; i++) { const e = el("reuse-n" + i); if (e) e.textContent = e.textContent.replace("Stäbe", "Bauteile"); }
  };

  /* ---------- Optimierung: Detail je Bauteil ---------- */
  const altOptDetail = optDetailHtml;
  optDetailHtml = function (i) {
    const s = S.erg.stab[i];
    const mats = s.material === "stahl" ? "Stahl " + fmt(s.menge, 0) + " kg"
      : "Volumen " + fmt(s.volumen, 2) + " m³" + (s.bewehrung_kg > 0 ? " · Betonstahl " + fmt(s.bewehrung_kg, 0) + " kg" : "");
    return altOptDetail(i).replace(/Materialmengen: <b>.*?<\/b>/, "Materialmengen: <b>" + mats + "</b>")
      .replace(/ Stäben dieser Art/g, " Bauteilen dieser Art").replace(/: (\d+) Stäbe</, ": $1 Bauteile<");
  };

  /* ---------- Auswahl: Plan, Optimierung, Reuse ---------- */
  const altAuswahl = renderAuswahl;
  renderAuswahl = function () {
    altAuswahl();
    if (S.auswahl === null || S.auswahl === undefined || !S.erg) return;
    const s = S.erg.stab[S.auswahl], box = el("auswahl"), plan = S.erg.config.bewehrung === "plan";
    const hatPlan = s.plaene && s.plaene.length;
    if (hatPlan && plan) {
      box.querySelectorAll(".kv > div").forEach(d => {
        if (d.firstChild && String(d.firstChild.textContent).startsWith("Betonstahl")) d.firstChild.textContent = "Betonstahl (laut Plan " + s.plaene.join(", ") + ")";
      });
    }
    box.insertAdjacentHTML("beforeend",
      (hatPlan ? '<p class="klein">Im Bewehrungsplan ' + s.plaene.join(", ") + (plan ? "" : " (nur zur Ansicht, „Richtwerte“ gewählt)") +
        ". Der Plan erscheint unten rechts bzw. im Vergleichsmodus.</p>" : "") +
      (optAktiv() ? optDetailHtml(S.auswahl) : "") + (reuseAktiv() ? reuseDetailHtml(S.auswahl) : ""));
  };

  /* ---------- 3D-Bewehrung (schematisch aus den vier Plänen) ---------- */
  const FARBE = { 1: "#2563eb", 2: "#16a34a", 3: "#dc2626", 4: "#ea580c" };
  bewSpuren = function () {
    if (!bewAn() || !S.bew.daten) return [];
    const d = S.bew.daten;
    const s = S.auswahl !== null && S.auswahl !== undefined ? S.erg.stab[S.auswahl] : null;
    const fokus = s && s.plaene && s.plaene.length ? S.auswahl : null;
    const spuren = [];
    for (const p of Object.keys(d.pos)) {
      const q = d.pos[p];
      spuren.push({ type: "scatter3d", mode: "lines", x: q.x, y: q.y, z: q.z, hoverinfo: "skip", showlegend: false,
                    name: "Plan " + p, opacity: fokus === null ? 1 : 0.15, line: { color: FARBE[p], width: 2 } });
    }
    if (fokus !== null) {
      for (const p of Object.keys(d.pos)) {
        const h = bewFuerStab(p, fokus);
        if (h.x.length) spuren.push({ type: "scatter3d", mode: "lines", x: h.x, y: h.y, z: h.z, hoverinfo: "skip",
                                      showlegend: false, name: "gewähltes Bauteil", line: { color: FARBE[p], width: 5 } });
      }
    }
    return spuren;
  };
  renderBewLegende = function () {
    const d = S.bew.daten, titel = {};
    d.plaene.forEach(p => { titel[p.pos] = p; });
    el("bew-liste").innerHTML = d.pruefung.filter(z => z.pos > 0).map(z =>
      '<li><span class="bew-punkt" style="background:' + FARBE[z.pos] + '"></span>Plan ' + esc(z.plan) + " · " + esc(titel[z.pos].titel) +
      ": " + fmt(z.ist_kg, 0) + " kg (Plan " + fmt(z.soll_kg, 0) + " kg)" + (z.ok ? "" : ' <b class="schlecht">weicht ab</b>') + "</li>").join("");
    const g = d.pruefung.find(z => z.pos === 0);
    el("bew-summe").innerHTML = "Summe: <b>" + fmt(g.ist_kg, 0) + " kg</b> · Pläne: " + fmt(g.soll_kg, 0) + " kg " +
      (g.ok ? '<b class="gut">✓ stimmt (±5 %)</b>' : '<b class="schlecht">✗ weicht ab</b>');
  };

  /* ---------- Bewehrungspläne: Fenster und Vergleichsmodus ---------- */
  const P = { lage: null, aktiv: null };
  async function ladeLage() {
    if (!P.lage) P.lage = await api("/api/plan/lage");
    return P.lage;
  }
  const planInfo = pid => S.katalog.plan.plaene.find(p => p.id === pid);
  const bildUrl = pid => "/api/plan/bild.png?p=bauteil6&plan=" + pid;
  function massenTabelle(p) {
    const zeilen = p.stabliste
      ? p.stabliste.map(z => "<tr><td>Pos. " + z.pos + "</td><td>" + z.stueck + " × ø" + z.durchmesser + "</td><td>" + fmt(z.einzel, 2) +
          " m</td><td>" + fmt(z.masse, 0) + " kg</td></tr>").join("")
      : Object.entries(p.dim).map(([d, kg]) => "<tr><td>ø " + d + " mm</td><td></td><td></td><td>" + fmt(kg, 2) + " kg</td></tr>").join("");
    return '<table class="t">' + zeilen + '<tr class="summe-zeile"><td colspan="3">Gesamtgewicht laut Plan</td><td>' +
      fmt(p.masse_kg, 2) + " kg</td></tr></table>";
  }
  const marke = r => (r ? '<div class="plan-marke" style="left:' + (r[0] * 100) + "%;top:" + (r[1] * 100) + "%;width:" +
    ((r[2] - r[0]) * 100) + "%;height:" + ((r[3] - r[1]) * 100) + '%"></div>' : "");

  zeigePlan = async function () {
    const fenster = el("plan-fenster");
    if (S.vergleich || S.auswahl === null || S.auswahl === undefined || !S.erg) { fenster.hidden = true; return; }
    const s = S.erg.stab[S.auswahl];
    fenster.hidden = false;
    el("plan-titel").textContent = "Bauteil " + s.id + " · " + s.profil;
    const koerper = el("plan-koerper");
    if (!s.plaene || !s.plaene.length) {
      const rw = S.katalog.plan.richtwerte[s.gruppe];
      koerper.innerHTML = '<p class="klein">Für dieses Bauteil gibt es keinen Bewehrungsplan. Die 4 Pläne gelten für den Abschnitt MG5 ' +
        "im E02 (Achsen 1–7 / A–D). Hier gilt der Richtwert" + (rw ? " von " + fmt(rw, 0) + " kg/m³" : "") + ".</p>";
      return;
    }
    const nr = (S.planNr = (S.planNr || 0) + 1);
    try {
      const d = await ladeLage();
      if (nr !== S.planNr) return;
      const lagen = d.lage[String(S.auswahl)] || [];
      koerper.innerHTML = lagen.map(([pid, r]) => {
        const p = planInfo(pid);
        return "<h3>Plan " + esc(pid) + " · " + esc(p.titel) + '</h3><div class="plan-bild"><img src="' + bildUrl(pid) +
          '" alt="Bewehrungsplan ' + esc(pid) + '">' + marke(r) + '</div><p class="klein">' + esc(p.nummer) + " · Beton " + esc(p.beton) +
          ", " + esc(p.betonstahl) + ", Deckung " + esc(p.deckung) + (r ? "" : "<br>Zusatzplan ohne Grundriss: Bauteil nicht markiert.") +
          "</p><details><summary>Massen laut Plan</summary>" + massenTabelle(p) + "</details>";
      }).join("") + '<p class="klein">Dieses Bauteil: <b>' + fmt(s.bewehrung_kg, 0) + " kg Betonstahl</b> (" +
        (S.erg.config.bewehrung === "plan" ? "Plan-Masse nach Volumen auf die Bauteile verteilt" : "Richtwert, die Pläne nur zur Ansicht") + ")</p>";
    } catch (e) {
      koerper.textContent = "Plan nicht verfügbar: " + e.message;
    }
  };

  function zeigeDockPlan(pid) {
    if (P.aktiv === pid && el("dock-bild").getAttribute("src")) return;
    P.aktiv = pid;
    el("dock-bild").src = bildUrl(pid);
    const p = planInfo(pid);
    el("dock-titel").textContent = "Plan " + pid + " · " + p.titel;
    el("dock-stabliste").innerHTML = "<details><summary>Massen laut Plan</summary>" + massenTabelle(p) + "</details>";
  }

  schalteVergleich = function () {
    S.vergleich = el("vergleich").checked;
    document.body.classList.toggle("vergleich", S.vergleich);
    if (S.vergleich) {
      el("plan-fenster").hidden = true;
      zeigeDockPlan(P.aktiv || "2448");
    } else {
      zeigePlan();
    }
    setTimeout(() => { Plotly.Plots.resize(el("szene")); aktualisierePlanDock(); }, 60);
  };

  aktualisierePlanDock = function () {
    if (!S.vergleich || !S.erg || !S.katalog) return;
    if (!P.lage) {
      ladeLage().then(aktualisierePlanDock).catch(e => { el("dock-text").textContent = "Plan nicht verfügbar: " + e.message; });
      return;
    }
    const lagen = n => (n === null || n === undefined ? [] : P.lage.lage[String(n)] || []);
    const aktuell = S.hover !== null && S.hover !== undefined ? S.hover : S.auswahl;
    const la = lagen(aktuell);
    if (la.length && !la.some(x => x[0] === P.aktiv)) zeigeDockPlan(la[0][0]);     // anderes Blatt nötig
    const rect = n => { const e = lagen(n).find(x => x[0] === P.aktiv); return e ? e[1] : null; };
    setzeMarke(el("dock-fest"), rect(S.auswahl));
    setzeMarke(el("dock-marke"), S.hover !== S.auswahl ? rect(S.hover) : null);
    setzeAnsicht(rect(S.hover) || rect(S.auswahl));
    let text;
    if (aktuell === null || aktuell === undefined) {
      text = '<span class="klein">Mit der Maus über ein Bauteil im Planbereich (E02, Achsen 1–7 / A–D) fahren oder eines anklicken. ' +
        "Das Blatt wechselt zum passenden Plan.</span>";
    } else {
      const s = S.erg.stab[aktuell];
      text = "<b>Bauteil " + esc(s.id) + "</b> · " + esc(s.profil) + " · " + esc(matName(s.material)) + "<br>" + (la.length
        ? "Pläne: " + la.map(x => x[0]).join(", ") + " · Betonstahl: <b>" + fmt(s.bewehrung_kg, 0) + " kg</b>" +
          (rect(aktuell) ? "" : ' <span class="klein">(in diesem Blatt nicht markiert)</span>')
        : '<span class="klein">Für dieses Bauteil gibt es keinen Bewehrungsplan.</span>');
    }
    el("dock-text").innerHTML = text;
    el("dock-viewport").classList.toggle("gedimmt", aktuell !== null && aktuell !== undefined && !la.length);
  };

  /* ---------- Texte, sobald der Katalog geladen ist ---------- */
  const altProjekt = passeProjektAn;
  passeProjektAn = function () {
    altProjekt();
    const p = S.katalog.plan;
    if (!p) {                                  // Server läuft noch mit altem Code: Hinweis statt Abbruch
      const b = document.createElement("div");
      b.id = "b6-hinweis";
      b.style.cssText = "max-width:1280px;margin:18px auto 0;padding:12px 18px;border-radius:12px;background:#F6E7E2;" +
        "color:#7A2A18;border:1px solid #E8C5BA;font-size:14px";
      el("banner").before(b);
      b.textContent ="Der Server läuft noch mit dem alten Stand. Bitte im Terminal mit ctrl + C stoppen und mit " +
        "„.venv/bin/python app.py“ neu starten, dann diese Seite neu laden. Bis dahin fehlen bei Bauteil6 Pläne, " +
        "Optimierung und Reuse.";
      return;
    }
    const kachel = (wert, titel, klein) => {
      const l = document.querySelector('input[name=bew][value="' + wert + '"]');
      if (!l) return;
      const lab = l.closest("label");
      lab.querySelector("b").textContent = titel;
      lab.querySelector("small").textContent = klein;
    };
    kachel("plan", "Laut Bewehrungsplänen", "4 Pläne E02, " + fmt(p.summe_kg, 0) + " kg · sonst Richtwerte");
    kachel("pauschal", "Richtwerte je Bauteilart", Object.values(p.richtwerte).reduce((a, b) => Math.min(a, b)) + "–" +
      Object.values(p.richtwerte).reduce((a, b) => Math.max(a, b)) + " kg/m³ (Annahme)");
    const bewSektion = document.querySelector('input[name=bew]').closest("section");
    bewSektion.querySelector("p.klein").textContent = "Gilt für Stahlbeton. Die Pläne decken " + p.bauteile + " Bauteile (" +
      fmt(p.volumen_m3, 0) + " m³) im E02 ab. Klick auf ein Bauteil zeigt seinen Plan.";
    const mw = el("materialwerte").closest("section");
    if (mw) mw.hidden = true;                                    // Wärmewerte gibt es bei Bauteil6 nicht
    const rs = el("reuse-steuerung").querySelector("p.klein");
    if (rs) rs.textContent = "Spender sind die Stahlprofile (HEA, HEB, UPE). Stahlbeton, Beton, Mauerwerk und Holz sind keine Spender. " +
      "Zielentwurf und Annahmen stehen weiter unten.";
    const bl = el("bew-legende").lastElementChild;
    if (bl) bl.innerHTML = "Schematisch: Menge aus den Plänen, Lage und Form angenommen (siehe <code>bauteil6_bewehrung3d.py</code>). " +
      "Bauteil anklicken, um seine Bewehrung hervorzuheben.";
  };
})();
