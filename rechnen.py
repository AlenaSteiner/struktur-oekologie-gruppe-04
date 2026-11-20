# -*- coding: utf-8 -*-
"""
Rechenkern der Web-App (Embodied Carbon + Sonnenerwaermung je Stab).

Alles im Speicher: Staebe und Geometrie aus dem Rhino-Modell, Datensaetze live aus der
OEKOBAUDAT (beim Start geladen, per Knopf neu ladbar).

Module in der App (Vorgabe): A1-A3, C (= C1+C2+C3+C4), D. A4, A5, B1 gehoeren nicht dazu.
Fehlt ein Wert im Datensatz, zaehlt er als 0 (steht in den Hinweisen der Datensaetze).
"""
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import bewehrungsplan
import waerme
from berechnung import BEWEHRUNG_KG_PRO_M3
from materialien import MATERIALIEN, UI_GRUPPEN, gruppen_warnung, standard_material, ui_gruppe
from modell import lese_geometrie, lese_staebe
from oekobaudat import DATENSAETZE, lade_datensatz

MODUL_GRUPPEN = {"A1-A3": ["A1-A3"], "C": ["C1", "C2", "C3", "C4"], "D": ["D"]}
RD_DURCHMESSER_M = 0.012

STANDARD_UMGEBUNG = {"datum": "2026-07-21", "zeit": "14:00", "himmel": "klar",
                     "t_luft": 30.0, "wind": 1.0, "nord": 0.0, "dauer": 0.0}


def _zahl(wert, minimum, maximum, standard):
    try:
        x = float(wert)
    except (TypeError, ValueError):
        return standard
    return min(max(x, minimum), maximum)


class Projekt:
    def __init__(self, datensaetze_laden=True):
        self.staebe = lese_staebe()
        self.geo = lese_geometrie()
        self.gruppe = [ui_gruppe(s.profil) for s in self.staebe]
        self.profile_je_gruppe = {gid: [] for gid, _n, _t in UI_GRUPPEN}
        for s, g in zip(self.staebe, self.gruppe):
            if s.profil not in self.profile_je_gruppe[g]:
                self.profile_je_gruppe[g].append(s.profil)
        self.standard_material = {g: standard_material(p[0]) for g, p in self.profile_je_gruppe.items()}
        self.flaechen = []
        for s in self.staebe:
            if s.beam_id in self.geo:
                verts, tris = self.geo[s.beam_id]
                self.flaechen.append(waerme.flaechengruppen_aus_netz(verts, tris))
            else:
                self.flaechen.append(waerme.flaechengruppen_zylinder(s.start, s.ende, RD_DURCHMESSER_M))
        # Bewehrung laut Plan: Gesamtmasse gleichmaessig je m3 Fundament verteilt (Plan gibt nur die Summe)
        vol_fundament = sum(s.volumen_m3 for s, g in zip(self.staebe, self.gruppe) if g == "fundament")
        self.plan_faktor = bewehrungsplan.SUMME_KG / vol_fundament
        self.daten = {}      # (gruppe, variante) -> Datensatz
        self.fehler = {}     # (gruppe, variante) -> Text
        self._ein_cache = {}
        if datensaetze_laden:
            self.lade_datensaetze()

    # ------------------------------------------------------------ Datensaetze (live)
    def lade_datensaetze(self, versuche=3):
        auftraege = [(g, v, u) for g, varianten in DATENSAETZE.items() for v, u in varianten.items()]

        def holen(auftrag):
            letzter = ""
            for versuch in range(versuche):
                try:
                    return lade_datensatz(auftrag[2]), ""
                except Exception as fehler:     # Netz, JSON, unerwartete Struktur
                    letzter = str(fehler)
                    time.sleep(1.5 * (versuch + 1))
            return None, letzter

        neu, fehler = {}, {}
        with ThreadPoolExecutor(max_workers=len(auftraege)) as pool:
            for (gruppe, variante, _uuid), (ds, text) in zip(auftraege, pool.map(holen, auftraege)):
                if ds is None:
                    fehler[(gruppe, variante)] = text
                else:
                    neu[(gruppe, variante)] = ds
        self.daten, self.fehler = neu, fehler
        return len(neu), len(fehler)

    def datensatz_info(self):
        info = {}
        for gruppe, varianten in DATENSAETZE.items():
            info[gruppe] = {}
            for variante, uuid in varianten.items():
                ds = self.daten.get((gruppe, variante))
                eintrag = {"uuid": uuid, "url": "https://oekobaudat.de/OEKOBAU.DAT/resource/processes/"
                                                + uuid + "?format=json&view=extended"}
                if ds is None:
                    eintrag["fehler"] = self.fehler.get((gruppe, variante), "nicht geladen")
                else:
                    eintrag.update({"name": ds.name, "einheit": ds.einheit, "bezug": ds.bezugsmenge,
                                    "luecken": ds.luecken, "hinweise": ds.hinweise,
                                    "gwp": {m: round(v, 5) for m, v in ds.gwp.items()}})
                info[gruppe][variante] = eintrag
        return info

    # ------------------------------------------------------------ Konfiguration
    def config(self, roh):
        """Eingabe der Oberflaeche pruefen und mit Standardwerten ergaenzen."""
        roh = roh or {}
        cfg = {"datensatz": {"baustahl": "standard", "beton": "standard"},
               "material": dict(self.standard_material)}
        for g, v in (roh.get("datensatz") or {}).items():
            if g in cfg["datensatz"] and v in DATENSAETZE[g]:
                cfg["datensatz"][g] = v
        for g, v in (roh.get("material") or {}).items():
            if g in cfg["material"] and v in MATERIALIEN:
                cfg["material"][g] = v
        cfg["module"] = [m for m in (roh.get("module") or []) if m in MODUL_GRUPPEN] or ["A1-A3"]
        cfg["bewehrung"] = roh.get("bewehrung") if roh.get("bewehrung") in ("plan", "pauschal") else "plan"
        u, s = roh.get("umgebung") or {}, STANDARD_UMGEBUNG
        datum, zeit = str(u.get("datum", s["datum"])), str(u.get("zeit", s["zeit"]))
        try:
            datetime.strptime(datum + " " + zeit, "%Y-%m-%d %H:%M")
        except ValueError:
            raise ValueError("Datum oder Uhrzeit ungültig: %s %s" % (datum, zeit))
        himmel = u.get("himmel", s["himmel"])
        cfg["umgebung"] = {
            "datum": datum, "zeit": zeit,
            "himmel": himmel if himmel in waerme.HIMMEL else s["himmel"],
            "t_luft": _zahl(u.get("t_luft"), -30.0, 50.0, s["t_luft"]),
            "wind": _zahl(u.get("wind"), 0.0, 25.0, s["wind"]),
            "nord": _zahl(u.get("nord"), 0.0, 360.0, s["nord"]) % 360.0,
            "dauer": _zahl(u.get("dauer"), 0.0, 1440.0, s["dauer"]),
        }
        return cfg

    # ------------------------------------------------------------ Embodied Carbon
    def _variante(self, gruppe, cfg):
        return cfg["datensatz"].get(gruppe, "standard")

    def _bew_faktor(self, i, cfg):
        """Betonstahl in kg je m3 Beton fuer Stab i: laut Bewehrungsplan (nur Fundamente) oder pauschal."""
        if cfg["bewehrung"] == "plan" and self.gruppe[i] == "fundament":
            return self.plan_faktor
        return BEWEHRUNG_KG_PRO_M3

    def _co2(self, volumen, mat_id, cfg, bew_kg_m3=BEWEHRUNG_KG_PRO_M3):
        """(Menge, Einheit, {modulgruppe: kg CO2e} oder None bei fehlendem Datensatz).

        Datensaetze mit Bezug kg: Menge = Volumen * Dichte aus materialien.py (die Dichte im
        Alu-Datensatz ist mit 2,7 kg/m3 falsch angegeben, Einheitenverwechslung).
        Beton: zusaetzlich Bewehrung bew_kg_m3 kg Betonstahl je m3 Beton (Standard 85 pauschal)."""
        mat = MATERIALIEN[mat_id]
        ds = self.daten.get((mat["gruppe"], self._variante(mat["gruppe"], cfg)))
        if ds is None:
            return None, "", None
        menge = volumen * mat["dichte"] if ds.einheit == "kg" else volumen
        je = {g: sum(ds.gwp.get(m, 0.0) for m in mods) * menge for g, mods in MODUL_GRUPPEN.items()}
        if mat.get("bewehrung"):
            bs = self.daten.get(("betonstahl", "standard"))
            if bs is None:
                return None, "", None
            kg = volumen * bew_kg_m3
            for g, mods in MODUL_GRUPPEN.items():
                je[g] += sum(bs.gwp.get(m, 0.0) for m in mods) * kg
        return menge, ds.einheit, je

    # ------------------------------------------------------------ Sonne
    def _einstrahlung(self, u):
        schluessel = (u["datum"], u["zeit"], u["himmel"], u["t_luft"], u["wind"], u["nord"])
        if schluessel not in self._ein_cache:
            env = waerme.umgebung(u["datum"], u["zeit"], u["himmel"], u["t_luft"], u["wind"], u["nord"])
            if len(self._ein_cache) > 24:
                self._ein_cache.clear()
            self._ein_cache[schluessel] = (env, [waerme.einstrahlung(f, env) for f in self.flaechen])
        return self._ein_cache[schluessel]

    @staticmethod
    def _temperatur(t_gl, t_luft_c, tau_min, dauer_min):
        """Temperatur nach dauer_min Sonne (Start = Lufttemperatur). dauer 0 = Gleichgewicht."""
        if dauer_min <= 0.0:
            return t_gl
        return t_luft_c + (t_gl - t_luft_c) * (1.0 - math.exp(-dauer_min / tau_min))

    # ------------------------------------------------------------ Gesamtrechnung
    def _erwaermung_stab(self, i, mat_id, env, ein, dauer):
        mat = MATERIALIEN[mat_id]
        t_gl, t_spitze, tau, biot = waerme.erwaermung(ein[i], mat, self.staebe[i].volumen_m3, env)
        t_luft_c = env.t_luft_k - 273.15
        return t_gl, t_spitze, tau, biot, self._temperatur(t_gl, t_luft_c, tau, dauer)

    def _fehlende(self, cfg):
        """Namen der gewaehlten Datensaetze, die nicht geladen werden konnten."""
        fehlt = set()
        for mat_id in cfg["material"].values():
            mat = MATERIALIEN[mat_id]
            var = self._variante(mat["gruppe"], cfg)
            if self.daten.get((mat["gruppe"], var)) is None:
                fehlt.add("%s (%s)" % (mat["name"], var))
            if mat.get("bewehrung") and self.daten.get(("betonstahl", "standard")) is None:
                fehlt.add("Betonstahl (standard)")
        return sorted(fehlt)

    def rechne(self, roh):
        cfg = self.config(roh)
        u = cfg["umgebung"]
        env, ein = self._einstrahlung(u)

        stab = []
        summen = {g: {"laenge": 0.0, "volumen": 0.0, "flaeche": 0.0, "t_x_a": 0.0, "t_max": -1e9,
                      "t_spitze_max": -1e9, "tau_x_a": 0.0, "n": 0, "co2": {m: 0.0 for m in MODUL_GRUPPEN}}
                  for g in self.profile_je_gruppe}
        for i, s in enumerate(self.staebe):
            g = self.gruppe[i]
            mat_id = cfg["material"][g]
            bew = self._bew_faktor(i, cfg)
            menge, einheit, je = self._co2(s.volumen_m3, mat_id, cfg, bew)
            t_gl, t_sp, tau, biot, t_dauer = self._erwaermung_stab(i, mat_id, env, ein, u["dauer"])
            flaeche = ein[i][0]
            stab.append({
                "id": s.beam_id, "profil": s.profil, "gruppe": g, "material": mat_id,
                "laenge": round(s.laenge_m, 4), "volumen": round(s.volumen_m3, 6),
                "menge": None if menge is None else round(menge, 4), "einheit": einheit,
                "bewehrung_kg": round(s.volumen_m3 * bew, 3) if MATERIALIEN[mat_id].get("bewehrung") else 0.0,
                "co2": None if je is None else {m: round(v, 4) for m, v in je.items()},
                "t": round(t_dauer, 2), "t_gl": round(t_gl, 2), "t_spitze": round(t_sp, 2),
                "tau": round(tau, 2), "biot": round(biot, 4), "flaeche": round(flaeche, 5),
            })
            z = summen[g]
            z["n"] += 1
            z["laenge"] += s.laenge_m
            z["volumen"] += s.volumen_m3
            z["flaeche"] += flaeche
            z["t_x_a"] += t_dauer * flaeche
            z["tau_x_a"] += tau * flaeche
            z["t_max"] = max(z["t_max"], t_dauer)
            z["t_spitze_max"] = max(z["t_spitze_max"], t_sp)
            if je is not None:
                for m, v in je.items():
                    z["co2"][m] += v

        gruppen = []
        for gid, name, _test in UI_GRUPPEN:
            z = summen[gid]
            mat_id = cfg["material"][gid]
            gruppen.append({
                "id": gid, "name": name, "material": mat_id, "n": z["n"],
                "profile": self.profile_je_gruppe[gid],
                "laenge": round(z["laenge"], 2), "volumen": round(z["volumen"], 4),
                "co2": {m: round(v, 2) for m, v in z["co2"].items()},
                "t_mittel": round(z["t_x_a"] / z["flaeche"], 1),
                "t_max": round(z["t_max"], 1), "t_spitze_max": round(z["t_spitze_max"], 1),
                "tau_mittel": round(z["tau_x_a"] / z["flaeche"], 1),
                "warnung": gruppen_warnung(self.profile_je_gruppe[gid], mat_id),
            })
        gesamt = {m: round(sum(z["co2"][m] for z in summen.values()), 2) for m in MODUL_GRUPPEN}
        return {
            "config": cfg,
            "umgebung": {"hoehe": round(env.elevation, 1), "azimut": round(env.azimut, 1),
                         "dni": round(env.dni), "dhi": round(env.dhi), "ghi": round(env.ghi),
                         "t_himmel": round(env.t_himmel_k - 273.15, 1),
                         "sonne": [round(c, 4) for c in env.sonne]},
            "stab": stab, "gruppen": gruppen, "gesamt": gesamt,
            "vergleich": self.vergleich(cfg, env, ein),
            "fehlende_datensaetze": self._fehlende(cfg),
        }


    def vergleich(self, cfg, env, ein):
        """Was waere, wenn ALLE Staebe aus demselben Material waeren (gewaehlte Datensaetze, Sonne)."""
        u = cfg["umgebung"]
        ergebnis = []
        for mat_id, mat in MATERIALIEN.items():
            co2 = {m: 0.0 for m in MODUL_GRUPPEN}
            ok = True
            t_x_a = a_sum = 0.0
            t_sp = -1e9
            taus = []
            for i, s in enumerate(self.staebe):
                _menge, _einheit, je = self._co2(s.volumen_m3, mat_id, cfg, self._bew_faktor(i, cfg))
                if je is None:
                    ok = False
                else:
                    for m, v in je.items():
                        co2[m] += v
                _t_gl, t_s, tau, _biot, t_d = self._erwaermung_stab(i, mat_id, env, ein, u["dauer"])
                t_x_a += t_d * ein[i][0]
                a_sum += ein[i][0]
                t_sp = max(t_sp, t_s)
                taus.append(tau)
            taus.sort()
            ergebnis.append({
                "id": mat_id, "name": mat["name"], "alpha": mat["alpha"], "eps": mat["eps"],
                "co2": {m: round(v, 1) for m, v in co2.items()} if ok else None,
                "t_mittel": round(t_x_a / a_sum, 1), "t_spitze_max": round(t_sp, 1),
                "tau_median": round(taus[len(taus) // 2], 1),
            })
        return ergebnis

    def tagesverlauf(self, roh, gruppe_id):
        """Temperatur ueber den Tag fuer eine Bauteilgruppe, in allen vier Materialien."""
        cfg = self.config(roh)
        u = cfg["umgebung"]
        ids = [n for n, g in enumerate(self.gruppe) if g == gruppe_id]
        if not ids:
            raise ValueError("Unbekannte Gruppe: %s" % gruppe_id)
        flaechen = waerme.flaechen_zusammenfassen([self.flaechen[n] for n in ids])
        volumen = sum(self.staebe[n].volumen_m3 for n in ids)
        kurven = []
        for mat_id, mat in MATERIALIEN.items():
            verlauf = waerme.tagesverlauf(flaechen, volumen, mat, u["datum"], u["himmel"], u["t_luft"],
                                          u["wind"], u["nord"])
            kurven.append({"material": mat_id, "name": mat["name"],
                           "stunde": [round(v[0], 3) for v in verlauf],
                           "t": [round(v[1], 2) for v in verlauf]})
        sonne = [round(v[2], 1) for v in waerme.tagesverlauf(
            flaechen, volumen, MATERIALIEN["stahl"], u["datum"], u["himmel"], u["t_luft"], u["wind"], u["nord"])]
        return {"gruppe": gruppe_id, "datum": u["datum"], "t_luft": u["t_luft"], "kurven": kurven,
                "sonnenhoehe": sonne}

    # ------------------------------------------------------------ Geometrie fuer die 3D-Ansicht
    def geometrie(self):
        """Ein Dreiecksnetz aller Koerper (mit Stab-Nummer je Punkt) und Linien fuer RD 12."""
        x, y, z, i, j, k, ordnung = [], [], [], [], [], [], []
        linien = {"x": [], "y": [], "z": [], "stab": []}
        for n, s in enumerate(self.staebe):
            netz = self.geo.get(s.beam_id)
            if netz is None:
                for punkt in (s.start, s.ende, (None, None, None)):
                    linien["x"].append(punkt[0])
                    linien["y"].append(punkt[1])
                    linien["z"].append(punkt[2])
                    linien["stab"].append(n)
                continue
            verts, tris = netz
            offset = len(x)
            for v in verts:
                x.append(round(v[0], 4))
                y.append(round(v[1], 4))
                z.append(round(v[2], 4))
                ordnung.append(n)
            for a, b, c in tris:
                i.append(offset + a)
                j.append(offset + b)
                k.append(offset + c)
        return {"x": x, "y": y, "z": z, "i": i, "j": j, "k": k, "stab_je_punkt": ordnung,
                "linien": linien, "anzahl_staebe": len(self.staebe)}

    def katalog(self):
        """Statische Angaben fuer die Oberflaeche."""
        return {
            "materialien": {m: {"name": d["name"], "alpha": d["alpha"], "eps": d["eps"], "dichte": d["dichte"],
                                "cp": d["cp"], "k": d["k"], "hinweis": d["hinweis"], "gruppe": d["gruppe"]}
                            for m, d in MATERIALIEN.items()},
            "gruppen": [{"id": gid, "name": name, "profile": self.profile_je_gruppe[gid],
                         "standard_material": self.standard_material[gid]} for gid, name, _t in UI_GRUPPEN],
            "datensaetze": self.datensatz_info(),
            "bewehrung": BEWEHRUNG_KG_PRO_M3,
            "plan": {"nummer": bewehrungsplan.PLAN_NUMMER, "stabliste": bewehrungsplan.STABLISTE,
                     "summe_kg": bewehrungsplan.SUMME_KG, "beton": bewehrungsplan.BETON,
                     "betonstahl": bewehrungsplan.BETONSTAHL, "deckung_cm": bewehrungsplan.DECKUNG_CM,
                     "kg_pro_m3": round(self.plan_faktor, 2)},
        }

    def plan_lage(self):
        """Lage jedes Fundamentstabes im Planbild (Anteile 0..1), Schluessel = Stab-Index."""
        return {str(i): bewehrungsplan.lage(s.start, s.ende)
                for i, (s, g) in enumerate(zip(self.staebe, self.gruppe)) if g == "fundament"}

