# -*- coding: utf-8 -*-
"""
Optimierungspotenziale: Szenarien fuer weniger Materialeinsatz und weniger CO2e.

WICHTIG: Das sind rechnerische Szenarien (Was waere, wenn), KEINE statisch nachgewiesenen
Aenderungen. Tragfaehigkeit, Gebrauchstauglichkeit, Herstellbarkeit und Verfuegbarkeit sind nicht
geprueft. Die CO2-Werte kommen aus den bereits geladenen OEKOBAUDAT-Datensaetzen der App.

Ablauf:
    Basis     = aktuelle Einstellungen der App (Datensaetze, Material je Gruppe, Bewehrung).
    Ansatz    = aendert genau eine Stellschraube (z. B. anderer Betondatensatz, weniger Volumen).
    Szenario  = alle aktiv gewaehlten Ansaetze zusammen, exakt neu gerechnet (nicht addiert).
    Einsparung = Basis - Szenario (positiv = weniger CO2e).
Module: A1-A3, C (= C1+C2+C3+C4), D, wie in der restlichen App.
"""
import copy
import re

from materialien import MATERIALIEN, UI_GRUPPEN, gruppen_warnung
from rechnen import MODUL_GRUPPEN

MODULE = list(MODUL_GRUPPEN)          # ["A1-A3", "C", "D"]

HINWEIS = ("Mögliche Szenarien, keine statisch nachgewiesenen Änderungen. Tragfähigkeit, "
           "Gebrauchstauglichkeit, Herstellbarkeit und Verfügbarkeit sind nicht geprüft. Die Werte sind "
           "rechnerisch aus den ÖKOBAUDAT-Datensätzen abgeleitet.")

# art: schalter (an/aus), prozent (Regler), auswahl (feste Werte)
MASSNAHMEN = [
    {"id": "beton_ecopact", "art": "schalter", "gruppen": "Fundamente",
     "name": "Beton mit weniger CO₂: EcoPact C25/30 statt Standard-Beton",
     "hinweis": "Anderer Datensatz (Hersteller-EPD, Werk Büttelborn). Gleiche Festigkeitsklasse, Eignung und "
                "Verfügbarkeit am Standort sind zu klären. A1–A3 sinkt, C und D steigen leicht."},
    {"id": "fundament_volumen", "art": "prozent", "gruppen": "Fundamente", "min": 0, "max": 40, "schritt": 5,
     "standard": 20, "einheit": "%", "name": "Fundamentquerschnitt verkleinern",
     "hinweis": "Betonvolumen und damit auch die Bewehrung sinken im gleichen Verhältnis. Ob der Boden und die "
                "Lasten das zulassen, ist nicht geprüft."},
    {"id": "bewehrung", "art": "prozent", "gruppen": "Fundamente", "min": 0, "max": 30, "schritt": 5,
     "standard": 10, "einheit": "%", "name": "Bewehrungsmenge verringern",
     "hinweis": "Weniger Betonstahl je m³ Beton, z. B. durch genauere Bemessung. Annahme, nicht berechnet."},
    {"id": "rohr_wand", "art": "auswahl", "gruppen": "Rohre (RO 139.7)", "optionen": [6.3, 5.0], "standard": 6.3,
     "einheit": "mm", "name": "Rohrwandstärke verringern (statt 8,0 mm)",
     "hinweis": "Außendurchmesser bleibt, die Wandstärke sinkt. Knicken und Beulen sind nicht geprüft; "
                "gängige Wandstärken, Verfügbarkeit prüfen."},
    {"id": "flachstahl_menge", "art": "prozent", "gruppen": "Flachstähle", "min": 0, "max": 30, "schritt": 5,
     "standard": 10, "einheit": "%", "name": "Stahlmenge bei Flachstählen verringern",
     "hinweis": "Pauschale Annahme (z. B. dünnere Bleche bei wenig ausgelasteten Stäben). Die Auslastung der "
                "Stäbe ist hier nicht bekannt, die Statik ist nicht geprüft."},
    {"id": "baustahl_datensatz", "art": "schalter", "gruppen": "Flachstähle, Rohre, Zugstäbe",
     "name": "Baustahl-Datensatz wechseln (Profile/Stabstahl ↔ Grobblech)",
     "hinweis": "Reiner Datensatzvergleich bei gleicher Menge. Kann auch schlechter ausfallen (Mehremission). "
                "Welcher Datensatz passt, hängt vom tatsächlichen Produkt ab."},
]

_RO = re.compile(r"RO\s+(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)")


def _rohr_faktor(profil, t_neu):
    """Verhaeltnis der Querschnittsflaeche (neue Wandstaerke / alte) eines Rohres."""
    m = _RO.match(profil)
    if not m:
        return 1.0
    d, t = float(m.group(1)), float(m.group(2))
    if t_neu >= t:
        return 1.0

    def flaeche(w):
        return d * d - (d - 2.0 * w) ** 2
    return flaeche(t_neu) / flaeche(t)


def _wert(m, roh):
    """Parameter eines Ansatzes pruefen, sonst Standardwert."""
    if m["art"] == "schalter":
        return 1
    try:
        x = float(roh)
    except (TypeError, ValueError):
        return m["standard"]
    if m["art"] == "prozent":
        return min(max(x, m["min"]), m["max"])
    return x if x in m["optionen"] else m["standard"]


def _szenario(p, cfg, werte):
    """CO2e je Stab (Liste [A1-A3, C, D]) und Mengen fuer die Ansaetze in `werte` {id: Parameter}."""
    cfg2 = copy.deepcopy(cfg)
    if werte.get("beton_ecopact"):
        cfg2["datensatz"]["beton"] = "alternative"
    if werte.get("baustahl_datensatz"):
        cfg2["datensatz"]["baustahl"] = "alternative" if cfg["datensatz"]["baustahl"] == "standard" else "standard"
    je_stab = []
    mengen = {"beton_m3": 0.0, "betonstahl_kg": 0.0, "baustahl_kg": 0.0}
    fehlt = False
    for i, s in enumerate(p.staebe):
        g = p.gruppe[i]
        mat_id = cfg2["material"][g]
        mat = MATERIALIEN[mat_id]
        vol = s.volumen_m3
        bew = p._bew_faktor(i, cfg2)
        if g == "fundament":
            vol *= 1.0 - werte.get("fundament_volumen", 0.0) / 100.0
            bew *= 1.0 - werte.get("bewehrung", 0.0) / 100.0
        elif g == "flachstahl":
            vol *= 1.0 - werte.get("flachstahl_menge", 0.0) / 100.0
        elif g == "rohr" and "rohr_wand" in werte:
            vol *= _rohr_faktor(s.profil, werte["rohr_wand"])
        _menge, _einheit, je = p._co2(vol, mat_id, cfg2, bew)
        if je is None:
            fehlt = True
            je_stab.append([0.0] * len(MODULE))
        else:
            je_stab.append([je[m] for m in MODULE])
        if mat["gruppe"] == "beton":
            mengen["beton_m3"] += vol
            if mat.get("bewehrung"):
                mengen["betonstahl_kg"] += vol * bew
        elif mat_id == "stahl":
            mengen["baustahl_kg"] += vol * mat["dichte"]
    return je_stab, mengen, fehlt


def _summe(werte, indizes):
    return [round(sum(werte[i][k] for i in indizes), 2) for k in range(len(MODULE))]



def rechne(p, roh):
    """Analyse und Szenario-Rechnung. roh = Konfiguration der App + {"massnahmen": {id: {aktiv, wert}}}."""
    roh = roh or {}
    cfg = p.config(roh)
    eingabe = roh.get("massnahmen") or {}
    n = len(p.staebe)

    basis, mengen_basis, fehlt = _szenario(p, cfg, {})
    aktiv_werte, katalog = {}, []
    for m in MASSNAHMEN:
        e = eingabe.get(m["id"]) or {}
        wert = _wert(m, e.get("wert"))
        aktiv = bool(e.get("aktiv"))
        if aktiv:
            aktiv_werte[m["id"]] = wert
        sz, _mg, _f = _szenario(p, cfg, {m["id"]: wert})
        stab, gesamt = {}, [0.0] * len(MODULE)
        for i in range(n):
            d = [basis[i][k] - sz[i][k] for k in range(len(MODULE))]
            if any(abs(x) > 1e-9 for x in d):
                stab[str(i)] = [round(x, 3) for x in d]
            for k in range(len(MODULE)):
                gesamt[k] += d[k]
        eintrag = dict(m)
        eintrag.update({"aktiv": aktiv, "wert": wert, "betroffen": len(stab),
                        "einzeln": {"gesamt": [round(x, 2) for x in gesamt], "stab": stab}})
        katalog.append(eintrag)

    szenario, mengen_szenario, fehlt_s = _szenario(p, cfg, aktiv_werte)

    gruppen = []
    for gid, name, _test in UI_GRUPPEN:
        idx = [i for i, g in enumerate(p.gruppe) if g == gid]
        gruppen.append({"id": gid, "name": name, "n": len(idx),
                        "basis": _summe(basis, idx), "szenario": _summe(szenario, idx)})
    alle = list(range(n))
    warnungen = [w for w in (gruppen_warnung(p.profile_je_gruppe[g], cfg["material"][g])
                             for g in p.profile_je_gruppe) if w]
    if fehlt or fehlt_s:
        warnungen.append("Für ein gewähltes Material fehlt ein Datensatz. Die betroffenen Stäbe zählen als 0.")
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

