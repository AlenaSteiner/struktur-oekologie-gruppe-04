# -*- coding: utf-8 -*-
"""
Zweites Projekt der App: Bauteil6 (mehrgeschossiges Gebaeude, IFC-Export als Rhino-Datei).

Unterschied zu Stockerau: keine Stabachsen mit Querschnitt, sondern geschlossene Netze je IFC-Bauteil
(Waende, Decken, Traeger, Stuetzen, Treppen) mit Material, Geschoss und Mengen im User-Text.
Die Datensaetze (OEKOBAUDAT) und die Modulgruppen (A1-A3, C, D) sind dieselben wie bei Stockerau.

Regeln, die hier gelten (siehe REGELN, wird in der Oberflaeche angezeigt):
  * Bauteilart kommt aus der IFC-Klasse, das Material aus dem Modell (Schichtaufbau vor Strukturmaterial).
  * Mehrschichtige Bauteile: das Volumen wird nach Schichtdicke auf die Materialien verteilt.
  * Volumen = IFC-Menge, nur ohne IFC-Menge das Volumen des Netzes. Grosse Abweichungen werden gezaehlt.
  * Betonstahl: fuer die Bauteile, die in den 4 Bewehrungsplaenen (E02, MG5) liegen, die Plan-Masse (nach
    Volumen verteilt, siehe bauteil6_plaene.py). Fuer alle anderen Richtwerte je Bauteilart in kg je m3
    Stahlbeton (ANNAHMEN). Umschaltbar: "plan" (Standard) oder "pauschal" (nur Richtwerte).
  * Die Sonnenerwaermung gibt es hier nicht (die Netze sind nicht konvex, das Modell dafuer schon).
  * Optimierung, Reuse und 3D-Bewehrung: bauteil6_optimierung.py, bauteil6_reuse.py, bauteil6_bewehrung3d.py.
"""
import json
import math
from pathlib import Path

import rhino3dm

import bauteil6_plaene
from rechnen import MODUL_GRUPPEN

PFAD = Path(__file__).resolve().parent / "rhino" / "Bauteil6.3dm"

ARTEN = [("wand", "Wände"), ("decke", "Decken"), ("traeger", "Träger"), ("stuetze", "Stützen"),
         ("treppe", "Treppen"), ("sonst", "Sonstiges")]
KLASSE_ART = {"IfcWallStandardCase": "wand", "IfcWall": "wand", "IfcSlab": "decke", "IfcBeam": "traeger",
              "IfcColumn": "stuetze", "IfcStair": "treppe", "IfcCovering": "sonst", "IfcBuildingElementProxy": "sonst"}

# Materialname im IFC-Modell -> Material der App
MAT_ABBILDUNG = {
    "AT_100_Stahlbeton": "stahlbeton", "DE_100_Stahlbeton": "stahlbeton", "Fertigteil": "stahlbeton",
    "AT_110_Fertigteil": "stahlbeton", "AT_120_Beton-Unbewehrt": "beton_unbewehrt", "AT_300_Mauerwerk": "mauerwerk",
    "AT_450_Vollholz": "holz", "Metall - Stahl - 345 MPa": "stahl", "Metall - Baustahl S235": "stahl",
}

MATERIALIEN = {
    "stahlbeton": {"name": "Stahlbeton C25/30", "kurz": "Stahlbeton", "gruppe": "beton", "dichte": 2400.0, "bewehrung": True,
                   "hinweis": "Beton plus Betonstahl nach Bauteilart (Annahme, siehe Regeln)."},
    "beton_unbewehrt": {"name": "Beton unbewehrt C25/30", "kurz": "unbewehrter Beton", "gruppe": "beton", "dichte": 2300.0,
                        "bewehrung": False, "hinweis": "Gleicher Betondatensatz, aber ohne Betonstahl."},
    "mauerwerk": {"name": "Mauerwerk (Kalksandstein-Datensatz als Näherung)", "kurz": "Mauerwerk", "gruppe": "mauerwerk",
                  "dichte": 2000.0, "bewehrung": False,
                  "hinweis": "Näherung: Die Ziegel-Datensätze der ÖKOBAUDAT liefern keinen auswertbaren GWP-total. "
                             "Der Kalksandstein-Datensatz (2022) steht stellvertretend für das Mauerwerk."},
    "stahl": {"name": "Stahl (Baustahl)", "kurz": "Stahl", "gruppe": "baustahl", "dichte": 7850.0, "bewehrung": False,
              "hinweis": "Profile aus dem Modell; Menge = Volumen mal Rohdichte."},
    "holz": {"name": "Brettschichtholz", "kurz": "Holz", "gruppe": "holz", "dichte": 470.0, "bewehrung": False,
             "hinweis": "A1-A3 ist negativ (biogener Kohlenstoff), dafür ist C3 positiv."},
}

# ANNAHME: Betonstahl in kg je m3 Stahlbeton nach Bauteilart (typische Richtwerte der Tragwerksplanung).
# Nicht aus den Bewehrungsplaenen des Projekts gerechnet. Zum Aendern hier die Zahlen anpassen.
BEWEHRUNG_KG_M3 = {"decke": 100.0, "wand": 80.0, "traeger": 150.0, "stuetze": 200.0, "treppe": 100.0, "sonst": 100.0}


def _zahl(us, *schluessel):
    for k in schluessel:
        if k in us:
            try:
                return float(us[k])
            except (TypeError, ValueError):
                pass
    return None


def _netz(geom, faktor):
    """Netz eines IFC-Bauteils in Metern: (Punkte, Dreiecke, Volumen in m3 aus dem Netz, geschlossen)."""
    punkte = [(v.X * faktor, v.Y * faktor, v.Z * faktor) for v in geom.Vertices]
    tris = []
    for i in range(len(geom.Faces)):
        f = geom.Faces[i]
        tris.append((f[0], f[1], f[2]))
        if f[2] != f[3]:
            tris.append((f[0], f[2], f[3]))
    vol = 0.0
    for a, b, c in tris:
        p, q, r = punkte[a], punkte[b], punkte[c]
        vol += (p[0] * (q[1] * r[2] - q[2] * r[1]) - p[1] * (q[0] * r[2] - q[2] * r[0]) + p[2] * (q[0] * r[1] - q[1] * r[0])) / 6.0
    return punkte, tris, abs(vol), bool(geom.IsClosed)


def _schichten(us, typ):
    """Materialien des Bauteils [(Material, Anteil am Volumen)], Quelle, Anzahl Annahmen."""
    roh = us.get("MaterialLayers")
    if roh:
        try:
            lagen = json.loads(roh)
        except ValueError:
            lagen = []
        teile, annahme = {}, 0
        for name, dicke in lagen:
            m = MAT_ABBILDUNG.get(str(name).strip())
            if m is None:
                m, annahme = "stahlbeton", annahme + 1
            teile[m] = teile.get(m, 0.0) + float(dicke)
        summe = sum(teile.values())
        if summe > 0:
            return sorted(((m, d / summe) for m, d in teile.items()), key=lambda x: -x[1]), "Schichtaufbau", annahme
    for key, quelle in (("Materials and Finishes.Structural Material", "Strukturmaterial"), ("Material", "Material"),
                        ("Materials and Finishes(Type).Material", "Typ-Material")):
        m = MAT_ABBILDUNG.get(str(us.get(key, "")).strip())
        if m:
            return [(m, 1.0)], quelle, 0
    if "STB" in typ:
        return [("stahlbeton", 1.0)], "Typname (STB)", 0
    return [("stahlbeton", 1.0)], "Annahme (kein Material im Modell)", 1


REGELN = [
    {"titel": "Bauteilart aus der IFC-Klasse",
     "text": "Wand, Decke, Träger, Stütze, Treppe und Sonstiges (Voute, Belag) werden getrennt geführt. Jede Art hat andere "
             "Bewehrung und später andere Wiederverwendungsregeln (Wände und Decken lassen sich nur schwer, Stützen und "
             "Stahlträger gut ausbauen)."},
    {"titel": "Material aus dem Modell, mehrschichtig nach Dicke",
     "text": "Reihenfolge: Schichtaufbau, Strukturmaterial, Material, Typname. Bauteile mit mehreren Schichten (z. B. "
             "Stahlbeton plus Holz) teilen ihr Volumen im Verhältnis der Schichtdicken auf. Fehlt jede Angabe, gilt "
             "Stahlbeton und das Bauteil ist als Annahme gezählt."},
    {"titel": "Volumen aus der Geometrie",
     "text": "Das geschlossene Netz bestimmt das Volumen. Der IFC-Wert gilt nur bei offenem Netz. Beide weichen bei einzelnen "
             "Bauteilen stark ab (z. B. doppelt gezählte Decken), die Geometrie ist das, was man im Modell sieht."},
    {"titel": "Betonstahl: Pläne im E02, sonst Richtwerte",
     "text": "Die 4 Bewehrungspläne (Wände und Stützen E02, Decke über E02 unten und Randnadeln/Unterzüge, Wandscheiben "
             "Achse D) gelten für den Abschnitt MG5 im E02 (Achsen 1–7 / A–D). Ihre Massen (zusammen %s kg) werden nach "
             "Volumen auf die Bauteile verteilt, die im Modell dort liegen. Für alle anderen Bauteile gelten Richtwerte in kg je m³ "
             "Stahlbeton: " % ("{:,.0f}".format(bauteil6_plaene.SUMME_KG).replace(",", ".")) +
             ", ".join("%s %g" % (n.lower(), BEWEHRUNG_KG_M3[k]) for k, n in ARTEN if k in BEWEHRUNG_KG_M3) +
             ". Mit „pauschal“ gelten die Richtwerte überall. Die Richtwerte sind Annahmen."},
    {"titel": "Mauerwerk: Näherung",
     "text": "Die Ziegel-Datensätze der ÖKOBAUDAT lassen sich nicht auswerten (kein GWP-total bzw. Szenarien ohne Vorgabe). "
             "Der Kalksandstein-Datensatz steht stellvertretend für alle gemauerten Bauteile."},
    {"titel": "Nicht in diesem Projekt",
     "text": "Die Sonnenerwärmung gibt es nur für Stockerau. Optimierung, Reuse-Planung, 3D-Bewehrung und Planvergleich "
             "gibt es für Bauteil6 in der neuen Ansicht (Startseite). In der klassischen Ansicht (/klassisch) sind sie ausgeblendet."},
]



def _bbox(punkte):
    xs, ys, zs = zip(*punkte)
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def _hauptlaenge(punkte):
    """Ausdehnung des Netzes entlang seiner Hauptachse (Hauptkomponente), z. B. Laenge eines Traegers in m."""
    n = len(punkte)
    m = [sum(p[k] for p in punkte) / n for k in range(3)]
    c = [[0.0] * 3 for _ in range(3)]
    for p in punkte:
        d = [p[k] - m[k] for k in range(3)]
        for a in range(3):
            for b in range(3):
                c[a][b] += d[a] * d[b]
    v = [1.0, 0.7, 0.3]
    for _ in range(60):
        w = [sum(c[a][b] * v[b] for b in range(3)) for a in range(3)]
        laenge = math.sqrt(sum(x * x for x in w)) or 1.0
        v = [x / laenge for x in w]
    t = [sum((p[k] - m[k]) * v[k] for k in range(3)) for p in punkte]
    return max(t) - min(t)


class Bauteil6:
    """Bauteile aus dem IFC-Rhino-Export im selben Datenformat wie der Rechenkern von Stockerau, damit die Oberflaeche
    beide Projekte darstellen kann. Die OEKOBAUDAT-Datensaetze kommen vom Hauptprojekt (haupt)."""

    def __init__(self, haupt, pfad=PFAD):
        self.haupt = haupt
        modell = rhino3dm.File3dm.Read(str(pfad))
        if modell is None:
            raise FileNotFoundError("Rhino-Datei nicht lesbar: " + str(pfad))
        faktor = {rhino3dm.UnitSystem.Millimeters: 0.001, rhino3dm.UnitSystem.Centimeters: 0.01,
                  rhino3dm.UnitSystem.Meters: 1.0}.get(modell.Settings.ModelUnitSystem)
        if faktor is None:
            raise ValueError("Einheit des Modells nicht unterstuetzt: %s" % modell.Settings.ModelUnitSystem)
        self.teile = []
        self.uebersprungen = 0
        for o in modell.Objects:
            geom = o.Geometry
            if not isinstance(geom, rhino3dm.Mesh):
                self.uebersprungen += 1
                continue
            us = dict(o.Attributes.GetUserStrings())
            klasse = us.get("IfcClass", "?")
            typ = us.get("IfcType") or us.get("Other.Type") or klasse
            punkte, tris, vol_netz, zu = _netz(geom, faktor)
            ifc = _zahl(us, "BaseQuantities.GrossVolume", "Dimensions.Volume")
            vol = vol_netz if (zu and vol_netz > 0) else (ifc if ifc is not None else vol_netz)
            abw = bool(ifc and ifc > 0.01 and abs(vol_netz - ifc) / ifc > 0.10)
            schichten, quelle, annahme = _schichten(us, typ)
            self.teile.append({
                "id": str(len(self.teile) + 1), "klasse": klasse, "art": KLASSE_ART.get(klasse, "sonst"), "typ": typ,
                "geschoss": us.get("IfcStorey", ""), "schichten": schichten, "quelle": quelle, "annahme": annahme,
                "volumen": vol, "ifc": ifc, "abweichung": abw, "offen": not zu, "punkte": punkte, "tris": tris})
        self.arten = [a for a, _n in ARTEN if any(t["art"] == a for t in self.teile)]
        self._nachbereiten()

    def _nachbereiten(self):
        """Lage (Bounding Box), Laenge (Hauptachse) je Bauteil und die Zuordnung zu den Bewehrungsplaenen."""
        for t in self.teile:
            t["bbox"] = _bbox(t["punkte"])
            t["laenge"] = _hauptlaenge(t["punkte"])
        self.plan_bauteile = bauteil6_plaene.zuordnen(self.teile)
        self.plan_kg, self.plan_je_teil, self.plan_je_plan = bauteil6_plaene.verteile(self.teile, self.plan_bauteile)

    def _dominant(self, teile):
        summe = {}
        for t in teile:
            for m, anteil in t["schichten"]:
                summe[m] = summe.get(m, 0.0) + t["volumen"] * anteil
        return max(summe, key=summe.get) if summe else "stahlbeton"

    def katalog(self):
        gruppen = []
        for a, name in ARTEN:
            if a not in self.arten:
                continue
            ts = [t for t in self.teile if t["art"] == a]
            gruppen.append({"id": a, "name": name, "profile": sorted({t["typ"] for t in ts}),
                            "standard_material": self._dominant(ts)})
        return {
            "projekt": "bauteil6",
            "materialien": {m: {"name": d["name"], "alpha": None, "eps": None, "dichte": d["dichte"], "cp": None, "k": None,
                                "hinweis": d["hinweis"], "gruppe": d["gruppe"]} for m, d in MATERIALIEN.items()},
            "gruppen": gruppen, "datensaetze": self.haupt.datensatz_info(), "bewehrung": None,
            "plan": {"plaene": bauteil6_plaene.info(), "summe_kg": bauteil6_plaene.SUMME_KG,
                     "bauteile": len(self.plan_kg),
                     "volumen_m3": round(sum(self.teile[i]["volumen"] for i in self.plan_kg), 2),
                     "richtwerte": BEWEHRUNG_KG_M3},
            "regeln": REGELN,
            "statistik": {"bauteile": len(self.teile), "offen": sum(1 for t in self.teile if t["offen"]),
                          "abweichung": sum(1 for t in self.teile if t["abweichung"]),
                          "annahme": sum(1 for t in self.teile if t["annahme"]), "uebersprungen": self.uebersprungen,
                          "geschosse": len({t["geschoss"] for t in self.teile})},
        }

    def geometrie(self):
        x, y, z, i, j, k, ordnung = [], [], [], [], [], [], []
        for n, t in enumerate(self.teile):
            offset = len(x)
            for p in t["punkte"]:
                x.append(round(p[0], 3))
                y.append(round(p[1], 3))
                z.append(round(p[2], 3))
                ordnung.append(n)
            for a, b, c in t["tris"]:
                i.append(offset + a)
                j.append(offset + b)
                k.append(offset + c)
        return {"x": x, "y": y, "z": z, "i": i, "j": j, "k": k, "stab_je_punkt": ordnung,
                "linien": {"x": [], "y": [], "z": [], "stab": []}, "anzahl_staebe": len(self.teile)}


    # ------------------------------------------------------------ Rechnung
    def config(self, roh):
        roh = roh or {}
        cfg = {"datensatz": {"baustahl": "standard", "beton": "standard"},
               "material": {g["id"]: g["standard_material"] for g in self.katalog()["gruppen"]}}
        for g, v in (roh.get("datensatz") or {}).items():
            if g in cfg["datensatz"] and v in ("standard", "alternative"):
                cfg["datensatz"][g] = v
        for g, v in (roh.get("material") or {}).items():
            if g in cfg["material"] and v in MATERIALIEN:
                cfg["material"][g] = v
        cfg["module"] = [m for m in (roh.get("module") or []) if m in MODUL_GRUPPEN] or ["A1-A3"]
        cfg["bewehrung"] = roh.get("bewehrung") if roh.get("bewehrung") in ("plan", "pauschal") else "plan"
        return cfg

    def bew_kg_m3(self, i, cfg):
        """Betonstahl in kg je m3 Stahlbeton fuer Bauteil i: laut Plan (falls im Planbereich) oder Richtwert."""
        t = self.teile[i]
        if cfg.get("bewehrung") == "plan" and i in self.plan_kg:
            vol = t["volumen"] * sum(a for m, a in t["schichten"] if m == "stahlbeton")
            if vol > 0:
                return self.plan_kg[i] / vol
        return BEWEHRUNG_KG_M3.get(t["art"], 100.0)

    def material_teile(self, t, wahl):
        """[(Material, Anteil)] eines Bauteils mit der Materialwahl je Bauteilart."""
        if wahl[t["art"]] != self._dominant_art(t["art"]):
            return [(wahl[t["art"]], 1.0)]          # eigene Materialwahl fuer die ganze Bauteilart
        return t["schichten"]

    def _dominant_art(self, art):
        cache = self.__dict__.setdefault("_dom_cache", {})
        if art not in cache:
            cache[art] = self._dominant([x for x in self.teile if x["art"] == art])
        return cache[art]

    def _co2(self, vol, mat_id, art, cfg, bew_kg_m3=None):
        """(Menge, Einheit, {modulgruppe: kg CO2e} oder None) fuer ein Volumen in m3 des Materials.
        bew_kg_m3: Betonstahl je m3 (Standard: Richtwert der Bauteilart)."""
        mat = MATERIALIEN[mat_id]
        gruppe = mat["gruppe"]
        ds = self.haupt.daten.get((gruppe, cfg["datensatz"].get(gruppe, "standard")))
        if ds is None:
            return None, "", None
        menge = vol * mat["dichte"] if ds.einheit == "kg" else vol
        je = {g: sum(ds.gwp.get(m, 0.0) for m in mods) * menge for g, mods in MODUL_GRUPPEN.items()}
        if mat["bewehrung"]:
            bs = self.haupt.daten.get(("betonstahl", "standard"))
            if bs is None:
                return None, "", None
            kg = vol * (BEWEHRUNG_KG_M3.get(art, 100.0) if bew_kg_m3 is None else bew_kg_m3)
            for g, mods in MODUL_GRUPPEN.items():
                je[g] += sum(bs.gwp.get(m, 0.0) for m in mods) * kg
        return menge, ds.einheit, je

    def rechne(self, roh):
        cfg = self.config(roh)
        wahl = cfg["material"]
        stab = []
        summen = {a: {"n": 0, "volumen": 0.0, "co2": {m: 0.0 for m in MODUL_GRUPPEN}} for a in self.arten}
        fehlt = set()
        for n, t in enumerate(self.teile):
            art = t["art"]
            einzel = {m: 0.0 for m in MODUL_GRUPPEN}
            ok, bew, menge = True, 0.0, 0.0
            teile = self.material_teile(t, wahl)
            bew_m3 = self.bew_kg_m3(n, cfg)
            for m, anteil in teile:
                _menge, _einheit, je = self._co2(t["volumen"] * anteil, m, art, cfg, bew_m3)
                if je is None:
                    ok = False
                    fehlt.add(MATERIALIEN[m]["name"])
                    continue
                menge += _menge if _einheit == "kg" else _menge * MATERIALIEN[m]["dichte"]
                for g in MODUL_GRUPPEN:
                    einzel[g] += je[g]
                if MATERIALIEN[m]["bewehrung"]:
                    bew += t["volumen"] * anteil * bew_m3
            s = summen[art]
            s["n"] += 1
            s["volumen"] += t["volumen"]
            if ok:
                for g in MODUL_GRUPPEN:
                    s["co2"][g] += einzel[g]
            haupt = max(teile, key=lambda x: x[1])[0]
            stab.append({"id": t["id"], "profil": t["typ"], "gruppe": art, "material": haupt,
                         "volumen": round(t["volumen"], 5), "menge": round(menge, 2), "einheit": "kg",
                         "bewehrung_kg": round(bew, 2), "geschoss": t["geschoss"], "klasse": t["klasse"],
                         "quelle": t["quelle"], "annahme": t["annahme"], "abweichung": t["abweichung"],
                         "ifc": None if t["ifc"] is None else round(t["ifc"], 4), "klasse_art": art,
                         "schichten": [[m, round(a, 3)] for m, a in teile],
                         "plaene": self.plan_je_teil.get(n, []), "laenge": round(t["laenge"], 3),
                         "co2": None if not ok else {g: round(v, 4) for g, v in einzel.items()},
                         "t": 0.0, "t_gl": 0.0, "t_spitze": 0.0, "tau": 0.0, "biot": 0.0, "flaeche": 0.0})
        gruppen = []
        for a, name in ARTEN:
            if a not in summen:
                continue
            z = summen[a]
            gruppen.append({"id": a, "name": name, "material": wahl[a], "n": z["n"], "profile": [],
                            "laenge": 0.0, "volumen": round(z["volumen"], 3),
                            "co2": {m: round(v, 2) for m, v in z["co2"].items()},
                            "t_mittel": 0.0, "t_max": 0.0, "t_spitze_max": 0.0, "tau_mittel": 0.0, "warnung": ""})
        gesamt = {m: round(sum(z["co2"][m] for z in summen.values()), 2) for m in MODUL_GRUPPEN}
        return {"config": cfg, "umgebung": {}, "stab": stab, "gruppen": gruppen, "gesamt": gesamt,
                "vergleich": self.vergleich(cfg), "fehlende_datensaetze": sorted(fehlt)}

    def vergleich(self, cfg):
        """Was waere, wenn ALLE Bauteile aus demselben Material waeren (gleiches Volumen, gewaehlte Datensaetze)."""
        ergebnis = []
        for mat_id, mat in MATERIALIEN.items():
            co2 = {m: 0.0 for m in MODUL_GRUPPEN}
            ok = True
            for n, t in enumerate(self.teile):
                _menge, _einheit, je = self._co2(t["volumen"], mat_id, t["art"], cfg, self.bew_kg_m3(n, cfg))
                if je is None:
                    ok = False
                    continue
                for m, v in je.items():
                    co2[m] += v
            ergebnis.append({"id": mat_id, "name": mat["name"], "alpha": None, "eps": None,
                             "co2": {m: round(v, 1) for m, v in co2.items()} if ok else None,
                             "t_mittel": None, "t_spitze_max": None, "tau_median": None})
        return ergebnis

    def plan_lage(self):
        """Je Bauteil im Planbereich: [[plan_id, Rechteck im Planbild oder None], ...]. Schluessel = Bauteil-Index."""
        lage = {}
        for i, plaene in self.plan_je_teil.items():
            lage[str(i)] = [[pid, bauteil6_plaene.lage(pid, self.teile[i]["bbox"])] for pid in plaene]
        return {"plaene": {p["id"]: {"breite": p["breite_pt"], "hoehe": p["hoehe_pt"]} for p in bauteil6_plaene.PLAENE},
                "lage": lage}


