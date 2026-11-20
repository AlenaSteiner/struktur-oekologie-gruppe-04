# -*- coding: utf-8 -*-
"""
Optimierungspotenziale fuer Bauteil6 (Geschossbau): gleiche Logik und gleiches Antwortformat wie
optimierung.py (Stockerau), aber mit Ansaetzen, die zu Waenden, Decken und Stahlbeton passen.

WICHTIG: rechnerische Szenarien (Was waere, wenn), KEINE statisch nachgewiesenen Aenderungen.
Tragfaehigkeit, Brandschutz, Schallschutz, Herstellbarkeit und Verfuegbarkeit sind nicht geprueft.

Ablauf wie bei Stockerau:
    Basis      = aktuelle Einstellungen der App (Datensaetze, Material je Bauteilart, Bewehrung Plan/pauschal).
    Ansatz     = aendert genau eine Stellschraube.
    Szenario   = alle aktiv gewaehlten Ansaetze zusammen, exakt neu gerechnet (nicht addiert).
    Einsparung = Basis - Szenario (positiv = weniger CO2e).
"""
import copy

from optimierung import HINWEIS, MODULE, _summe, _wert

MASSNAHMEN = [
    {"id": "beton_ecopact", "art": "schalter", "gruppen": "alle Stahlbeton- und Betonbauteile",
     "name": "Beton mit weniger CO₂: EcoPact C25/30 statt Standard-Beton",
     "hinweis": "Anderer Datensatz (Hersteller-EPD). Festigkeitsklasse, Expositionsklasse und Verfügbarkeit sind zu "
                "prüfen; die Pläne verlangen teils C30/37 und C40/50. A1–A3 sinkt, C und D ändern sich leicht."},
    {"id": "decke_dicke", "art": "prozent", "gruppen": "Decken (Stahlbeton)", "min": 0, "max": 30, "schritt": 5,
     "standard": 10, "einheit": "%", "name": "Deckenstärke verringern",
     "hinweis": "Betonvolumen der Stahlbetondecken sinkt, die Bewehrung im gleichen Verhältnis. Durchbiegung, "
                "Schwingung, Schall- und Brandschutz sind nicht geprüft."},
    {"id": "wand_dicke", "art": "prozent", "gruppen": "Wände (Stahlbeton)", "min": 0, "max": 30, "schritt": 5,
     "standard": 10, "einheit": "%", "name": "Wandstärke verringern",
     "hinweis": "Betonvolumen der Stahlbetonwände sinkt, die Bewehrung im gleichen Verhältnis. Tragfähigkeit, "
                "Aussteifung und Brandschutz sind nicht geprüft."},
    {"id": "bewehrung", "art": "prozent", "gruppen": "alle Stahlbetonbauteile", "min": 0, "max": 30, "schritt": 5,
     "standard": 10, "einheit": "%", "name": "Bewehrungsmenge verringern",
     "hinweis": "Weniger Betonstahl je m³, z. B. durch genauere Bemessung. Gilt für Plan- und Richtwerte. "
                "Annahme, nicht berechnet."},
    {"id": "hbv_decke", "art": "prozent", "gruppen": "Decken (Stahlbeton)", "min": 0, "max": 80, "schritt": 10,
     "standard": 50, "einheit": "%", "name": "Holz-Beton-Verbunddecke: Betonanteil durch Brettschichtholz ersetzen",
     "hinweis": "Der gewählte Anteil des Deckenbetons wird als Brettschichtholz gleichen Volumens gerechnet, die "
                "Bewehrung dieses Anteils entfällt. Starke Vereinfachung: Aufbau, Verbundmittel und Spannweiten sind "
                "nicht bemessen. Holz: A1–A3 negativ, C3 positiv."},
    {"id": "baustahl_datensatz", "art": "schalter", "gruppen": "Stahlträger und -stützen (HEA, HEB, UPE)",
     "name": "Baustahl-Datensatz wechseln (Profile/Stabstahl ↔ Grobblech)",
     "hinweis": "Reiner Datensatzvergleich bei gleicher Menge. Kann auch schlechter ausfallen (Mehremission)."},
]


def _szenario(b6, cfg, werte):
    """CO2e je Bauteil (Liste [A1-A3, C, D]) und Mengen fuer die Ansaetze in `werte` {id: Parameter}."""
    from bauteil6 import MATERIALIEN
    cfg2 = copy.deepcopy(cfg)
    if werte.get("beton_ecopact"):
        cfg2["datensatz"]["beton"] = "alternative"
    if werte.get("baustahl_datensatz"):
        cfg2["datensatz"]["baustahl"] = "alternative" if cfg["datensatz"]["baustahl"] == "standard" else "standard"
    wahl = cfg2["material"]
    je_teil, fehlt = [], False
    mengen = {"beton_m3": 0.0, "betonstahl_kg": 0.0, "baustahl_kg": 0.0, "holz_m3": 0.0}
    bew_faktor = 1.0 - werte.get("bewehrung", 0.0) / 100.0
    for n, t in enumerate(b6.teile):
        art = t["art"]
        bew_m3 = b6.bew_kg_m3(n, cfg2) * bew_faktor
        summe = [0.0] * len(MODULE)
        for m, anteil in b6.material_teile(t, wahl):
            vol = t["volumen"] * anteil
            stueck = [(m, vol)]
            if m == "stahlbeton":
                if art == "decke":
                    vol *= 1.0 - werte.get("decke_dicke", 0.0) / 100.0
                    h = werte.get("hbv_decke", 0.0) / 100.0
                    stueck = [(m, vol * (1.0 - h))] + ([("holz", vol * h)] if h > 0 else [])
                elif art == "wand":
                    stueck = [(m, vol * (1.0 - werte.get("wand_dicke", 0.0) / 100.0))]
            for mat_id, v in stueck:
                _menge, _einheit, je = b6._co2(v, mat_id, art, cfg2, bew_m3)
                if je is None:
                    fehlt = True
                    continue
                for k, mod in enumerate(MODULE):
                    summe[k] += je[mod]
                mat = MATERIALIEN[mat_id]
                if mat["gruppe"] == "beton":
                    mengen["beton_m3"] += v
                    if mat["bewehrung"]:
                        mengen["betonstahl_kg"] += v * bew_m3
                elif mat_id == "stahl":
                    mengen["baustahl_kg"] += v * mat["dichte"]
                elif mat_id == "holz":
                    mengen["holz_m3"] += v
        je_teil.append(summe)
    return je_teil, mengen, fehlt


def rechne(b6, roh):
    """Analyse und Szenario-Rechnung fuer Bauteil6. Antwort wie optimierung.rechne (Stockerau)."""
    from bauteil6 import ARTEN
    roh = roh or {}
    cfg = b6.config(roh)
    eingabe = roh.get("massnahmen") or {}
    n = len(b6.teile)

    basis, mengen_basis, fehlt = _szenario(b6, cfg, {})
    aktiv_werte, katalog = {}, []
    for m in MASSNAHMEN:
        e = eingabe.get(m["id"]) or {}
        wert = _wert(m, e.get("wert"))
        aktiv = bool(e.get("aktiv"))
        if aktiv:
            aktiv_werte[m["id"]] = wert
        sz, _mg, _f = _szenario(b6, cfg, {m["id"]: wert})
        teil, gesamt = {}, [0.0] * len(MODULE)
        for i in range(n):
            d = [basis[i][k] - sz[i][k] for k in range(len(MODULE))]
            if any(abs(x) > 1e-9 for x in d):
                teil[str(i)] = [round(x, 3) for x in d]
            for k in range(len(MODULE)):
                gesamt[k] += d[k]
        eintrag = dict(m)
        eintrag.update({"aktiv": aktiv, "wert": wert, "betroffen": len(teil),
                        "einzeln": {"gesamt": [round(x, 2) for x in gesamt], "stab": teil}})
        katalog.append(eintrag)

    szenario, mengen_szenario, fehlt_s = _szenario(b6, cfg, aktiv_werte)
    gruppen = []
    for art, name in ARTEN:
        idx = [i for i, t in enumerate(b6.teile) if t["art"] == art]
        if idx:
            gruppen.append({"id": art, "name": name, "n": len(idx),
                            "basis": _summe(basis, idx), "szenario": _summe(szenario, idx)})
    alle = list(range(n))
    warnungen = []
    if fehlt or fehlt_s:
        warnungen.append("Für ein gewähltes Material fehlt ein Datensatz. Die betroffenen Bauteile zählen als 0.")
    return {
        "module": MODULE, "hinweis": HINWEIS, "warnungen": warnungen,
        "basis": [[round(x, 3) for x in z] for z in basis],
        "szenario": [[round(x, 3) for x in z] for z in szenario],
        "gruppen": gruppen,
        "gesamt": {"basis": _summe(basis, alle), "szenario": _summe(szenario, alle)},
        "mengen": {"basis": {k: round(v, 3) for k, v in mengen_basis.items()},
                   "szenario": {k: round(v, 3) for k, v in mengen_szenario.items()}},
        "massnahmen": katalog,
    }
