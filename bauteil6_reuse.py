# -*- coding: utf-8 -*-
"""
Reuse-Planung fuer Bauteil6: genau wie reuse.py (Stockerau), nur sind die Spender die Stahlprofile von Bauteil6.

WICHTIG: rechnerisches Szenario, KEIN statischer Nachweis und KEINE Zulassung zur Wiederverwendung.
Stahlguete, Zustand, Anschluesse und Pruefung sind nicht beruecksichtigt. Schnitt, Transport und Zeiten sind
Annahmen (dieselben Vorgaben wie bei Stockerau, reuse.STANDARD_PARAMETER).

Spender: alle Bauteile, deren Material Stahl ist (Traeger und Stuetzen HEA, HEB, UPE). Stahlbeton, Beton,
Mauerwerk und Holz sind keine Spender (wie die Fundamente bei Stockerau).
Profil: aus dem IFC-Typ (z. B. "HE-A-Traeger:HEA 220" -> HEA 220). Laenge: Ausdehnung entlang der Hauptachse
des Netzes. Querschnitt: Volumen / Laenge. Zielteile brauchen dasselbe Profil (laengs wird nicht geschnitten).
Zuschnitt: Best-Fit-Decreasing wie bei Stockerau (Heuristik, nicht garantiert optimal).
Vergleich: "Neu" (alles neu aus dem Stahlwerk) gegen "Reuse" (Spender, Fehlmenge neu). C und D der Zielteile
sind in beiden Faellen gleich.
"""
import math
import re

from reuse import GRENZEN, MODULE, STANDARD_PARAMETER, _parameter, _teile, _zahl

EPS = 1e-9
DICHTE = 7850.0
PROFIL = re.compile(r"\b(HEA|HEB|HEM|IPE|UPE|UPN)\s*-?\s*(\d{2,4})", re.I)

HINWEIS = ("Rechnerisches Szenario, kein statischer Nachweis und keine Zulassung zur Wiederverwendung. "
           "Stahlgüte, Zustand, Anschlüsse und Prüfung sind nicht berücksichtigt. Schnitt, Transport und "
           "Zeiten sind Annahmen. C und D der Zielteile gelten in beiden Fällen gleich.")


def profil_von(typ):
    m = PROFIL.search(typ or "")
    return "%s %s" % (m.group(1).upper(), m.group(2)) if m else None


def _spender_liste(b6, cfg):
    """[(Index, Profil, Laenge m, Volumen m3)] aller Stahlbauteile mit erkanntem Profil."""
    liste = []
    for i, t in enumerate(b6.teile):
        haupt = max(b6.material_teile(t, cfg["material"]), key=lambda x: x[1])[0]
        p = profil_von(t["typ"])
        if haupt == "stahl" and p and t["laenge"] > 0.05:
            liste.append((i, p, t["laenge"], t["volumen"]))
    return liste


def _querschnitte(spender):
    """Mittlere Querschnittsflaeche je Profil in m2."""
    s = {}
    for _i, p, laenge, vol in spender:
        a = s.setdefault(p, [0.0, 0.0])
        a[0] += vol
        a[1] += laenge
    return {p: v / l for p, (v, l) in s.items() if l > 0}


def standard(b6):
    """Vorgabewerte fuer die Oberflaeche. Beispiel-Zielentwurf aus den vorhandenen Spendern abgeleitet."""
    spender = _spender_liste(b6, b6.config({}))
    je = {}
    for _i, p, laenge, _v in spender:
        je.setdefault(p, []).append(laenge)
    haeufig = sorted(je, key=lambda p: -len(je[p]))[:4]
    ziel = []
    for p in haeufig:
        ls = sorted(je[p])
        median = ls[len(ls) // 2]
        ziel.append({"typ": p, "breite": 0.0, "dicke": 0.0, "laenge": round(max(0.3, 0.45 * median), 2), "anzahl": len(ls)})
        ziel.append({"typ": p, "breite": 0.0, "dicke": 0.0, "laenge": round(max(0.2, 0.30 * median), 2),
                     "anzahl": max(1, len(ls) // 2)})
    return {"hinweis": HINWEIS, "parameter": dict(STANDARD_PARAMETER), "grenzen": GRENZEN, "ziel": ziel,
            "typen": {p: p for p in sorted(je)}}


def _ziel(roh, typen):
    if not typen:
        raise ValueError("Im Modell gibt es keine Stahlprofile als Spender.")
    if not isinstance(roh, list):
        raise ValueError("Der Zielentwurf muss eine Liste sein")
    zeilen = []
    for n, z in enumerate(roh[:200]):
        if not isinstance(z, dict):
            raise ValueError("Zielentwurf Zeile %d ist ungültig" % (n + 1))
        typ = z.get("typ") if z.get("typ") in typen else sorted(typen)[0]     # neue Zeile: erstes Profil der Liste
        zeilen.append({"typ": typ, "laenge": _zahl(z.get("laenge"), 0.05, 12.0, 1.0),
                       "anzahl": int(_zahl(z.get("anzahl"), 0, 1000, 1)), "breite": 0.0, "dicke": 0.0})
    return zeilen


class _Spender:
    """Ein Stahlprofil als Strecke mit gleichem Querschnitt."""

    def __init__(self, i, profil, laenge, volumen):
        self.i, self.profil, self.laenge, self.volumen = i, profil, laenge, volumen
        self.flaeche = volumen / laenge
        self.pos, self.stuecke, self.ende_letztes, self.genutzt_vol = 0.0, 0, 0.0, 0.0

    def passt(self, laenge):
        return self.pos + laenge <= self.laenge + EPS

    def lege(self, laenge, fuge):
        self.genutzt_vol += self.flaeche * laenge
        self.ende_letztes = self.pos + laenge
        self.pos = min(self.pos + laenge + fuge, self.laenge)
        self.stuecke += 1

    def schnitte(self):
        if self.stuecke == 0:
            return 0
        return self.stuecke - (1 if self.laenge - self.ende_letztes < 1e-3 else 0)


def rechne(b6, roh):
    """Zuschnitt und Vergleich. Antwort im selben Format wie reuse.rechne (Stockerau)."""
    roh = roh or {}
    cfg = b6.config(roh)
    par = _parameter(roh.get("parameter"))
    liste = _spender_liste(b6, cfg)
    quer = _querschnitte(liste)
    std = standard(b6)
    ziel = _ziel(roh["ziel"] if "ziel" in roh else std["ziel"], quer)
    _menge, _einheit, je_m3 = b6._co2(1.0, "stahl", "traeger", cfg)
    if je_m3 is None:
        raise ValueError("Der Datensatz für Baustahl ist nicht geladen. Bitte „Datensätze neu laden“.")

    teile, stoesse = _teile(ziel, par["transport_max"])
    fuge = par["schnittverlust_mm"] / 1000.0
    spender = {}
    for i, p, laenge, vol in liste:
        spender.setdefault(p, []).append(_Spender(i, p, laenge, vol))
    zeilen, vol_gedeckt, vol_fehlt = {}, 0.0, 0.0
    for r, typ, _b, _d, laenge in sorted(teile, key=lambda t: (t[1], -t[4])):
        vol = quer[typ] * laenge
        beste = None
        for sp in spender.get(typ, []):
            if sp.passt(laenge):
                rest = sp.laenge - (sp.pos + laenge + fuge)
                if beste is None or rest < beste[0]:
                    beste = (rest, sp)
        z = zeilen.setdefault(r, {"gedeckt": 0, "fehlend": 0, "stab": set()})
        if beste is None:
            z["fehlend"] += 1
            vol_fehlt += vol
        else:
            beste[1].lege(laenge, fuge)
            z["gedeckt"] += 1
            z["stab"].add(b6.teile[beste[1].i]["id"])
            vol_gedeckt += vol

    stab = [{"s": 0, "n": 0, "auslastung": 0.0, "rest_m": 0.0} for _ in b6.teile]
    verschnitt = rest_lager = 0.0
    schnitte = genutzt = 0
    info = {}
    for p, sps in spender.items():
        e = info.setdefault(p, {"typ": p, "name": p, "n": 0, "genutzt": 0, "laenge": 0.0, "masse": 0.0})
        for sp in sps:
            e["n"] += 1
            e["laenge"] += sp.laenge
            e["masse"] += sp.volumen * DICHTE
            if sp.stuecke == 0:
                stab[sp.i] = {"s": 1, "n": 0, "auslastung": 0.0, "rest_m": round(sp.laenge, 3)}
                continue
            e["genutzt"] += 1
            genutzt += 1
            schnitte += sp.schnitte()
            rest_laenge = sp.laenge - sp.pos
            rest_vol = sp.flaeche * rest_laenge
            verschnitt += max(sp.volumen - sp.genutzt_vol - rest_vol, 0.0)
            if rest_laenge >= par["min_rest"] - EPS:
                rest_lager += rest_vol
            else:
                verschnitt += rest_vol
            ausl = sp.genutzt_vol / sp.volumen if sp.volumen > 0 else 0.0
            stab[sp.i] = {"s": 3 if ausl >= 0.8 else 2, "n": sp.stuecke, "auslastung": round(ausl, 3),
                          "rest_m": round(rest_laenge, 3)}
    for e in info.values():
        e["laenge"], e["masse"] = round(e["laenge"], 2), round(e["masse"], 2)

    anz = len(teile)
    fehl_teile = sum(z["fehlend"] for z in zeilen.values())
    vol_ziel = vol_gedeckt + vol_fehlt
    m_ziel, m_gedeckt, m_fehlt = vol_ziel * DICHTE, vol_gedeckt * DICHTE, vol_fehlt * DICHTE

    def co2(v_a13):
        return [round(je_m3["A1-A3"] * v_a13, 2), round(je_m3["C"] * vol_ziel, 2), round(je_m3["D"] * vol_ziel, 2)]

    def zusatz(n_schnitte, tkm):
        return round(n_schnitte * par["schnitt_co2"] + tkm * par["transport_co2"], 2)

    neu_h = anz * par["min_schnitt"] / 60.0
    reuse_h = (genutzt * (par["min_ausbau"] + par["min_pruefung"]) + (schnitte + fehl_teile) * par["min_schnitt"]) / 60.0
    warnungen = []
    if anz == 0:
        warnungen.append("Der Zielentwurf ist leer.")
    for n, z in enumerate(ziel):
        if zeilen.get(n, {}).get("fehlend"):
            warnungen.append("%s, %s m: %d Teile finden keinen passenden Spender und werden neu beschafft."
                             % (z["typ"], ("%g" % z["laenge"]).replace(".", ","), zeilen[n]["fehlend"]))
    return {
        "module": MODULE, "hinweis": HINWEIS, "warnungen": warnungen, "parameter": par,
        "ziel": [dict(z, gedeckt=zeilen.get(n, {}).get("gedeckt", 0), fehlend=zeilen.get(n, {}).get("fehlend", 0),
                      staebe=sorted(zeilen.get(n, {}).get("stab", ()), key=lambda x: (len(x), x)))
                 for n, z in enumerate(ziel)],
        "stab": stab,
        "spender": [info[k] for k in sorted(info)],
        "summen": {
            "teile": anz, "stoesse": stoesse, "schnitte": schnitte, "spender_genutzt": genutzt,
            "masse_ziel_kg": round(m_ziel, 2), "masse_gedeckt_kg": round(m_gedeckt, 2),
            "masse_fehlt_kg": round(m_fehlt, 2),
            "deckung_prozent": round(100.0 * m_gedeckt / m_ziel, 1) if m_ziel else 0.0,
            "verschnitt_kg": round(verschnitt * DICHTE, 2), "rest_lager_kg": round(rest_lager * DICHTE, 2),
            "spender_masse_kg": round(sum(e["masse"] for e in info.values()), 2),
        },
        "vergleich": {
            "neu": {"co2": co2(vol_ziel), "zusatz": zusatz(anz, m_ziel / 1000.0 * par["km_neu"]),
                    "aufwand_h": round(neu_h, 1), "tage": par["tage_neu"]},
            "reuse": {"co2": co2(vol_fehlt),
                      "zusatz": zusatz(schnitte + fehl_teile,
                                       m_gedeckt / 1000.0 * par["km_reuse"] + m_fehlt / 1000.0 * par["km_neu"]),
                      "aufwand_h": round(reuse_h, 1), "tage": par["tage_neu"] if vol_fehlt > 0 else par["tage_reuse"]},
        },
    }
