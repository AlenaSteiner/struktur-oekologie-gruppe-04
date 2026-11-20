# -*- coding: utf-8 -*-
"""
Reuse-Planung: Zielentwurf (Bedarf an Stahlteilen) aus den Staeben des Pavillons zuschneiden.

WICHTIG: Das ist ein rechnerisches Szenario, KEIN statischer Nachweis und KEINE Zulassung zur
Wiederverwendung. Stahlguete, Zustand, Anschluesse (Schweissnaehte, Bohrungen) und Pruefung sind
nicht beruecksichtigt. Die Faktoren fuer Schnitt, Transport und Zeit sind Annahmen (STANDARD_PARAMETER),
sie stammen nicht aus der OEKOBAUDAT. Die CO2-Werte des Stahls kommen aus den geladenen
OEKOBAUDAT-Datensaetzen der App.

Spender: Flachstaehle, Rohre, Zugstaebe. Fundamente (Beton) sind keine Spender.
Zuschnitt: Best-Fit-Decreasing (Heuristik, nicht garantiert optimal).
    - Jeder Spender ist eine Strecke. Teile werden nacheinander vom breiten Ende abgeschnitten,
      zwischen zwei Teilen geht der Schnittverlust (Schnittfuge) verloren.
    - Verjuengte Flachstaehle: Die Breite aendert sich linear. Ein Teil mit Breite b darf nur dort
      liegen, wo der Stab ueberall mindestens b breit ist, und nicht dort, wo er mehr als
      b + Breitenueberschuss breit ist (sonst geht zu viel Stahl verloren). Die Dicke muss gleich sein.
    - Laengs wird nicht geschnitten. Rohr und Rundstahl: gleicher Querschnitt wie das Zielteil.
    - Zielteile laenger als das Transportmass werden in gleich lange Stuecke geteilt (je Teilung
      ein Stoss, der konstruktiv zu loesen ist).
Vergleich: "Neu" (alles neu aus dem Stahlwerk) gegen "Reuse" (Spender, Fehlmenge neu).
C und D der Zielteile sind in beiden Faellen gleich. Rest und Verschnitt werden als Masse
ausgewiesen, aber nicht bilanziert.
Module wie in der App: A1-A3, C (= C1+C2+C3+C4), D.
"""
import math
import re

from materialien import MATERIALIEN
from modell import flaeche_m2
from rechnen import MODUL_GRUPPEN

MODULE = list(MODUL_GRUPPEN)          # ["A1-A3", "C", "D"]
DICHTE = MATERIALIEN["stahl"]["dichte"]
EPS = 1e-9
ZAHL = r"(\d+(?:\.\d+)?)"

HINWEIS = ("Rechnerisches Szenario, kein statischer Nachweis und keine Zulassung zur Wiederverwendung. "
           "Stahlgüte, Zustand, Anschlüsse und Prüfung sind nicht berücksichtigt. Schnitt, Transport und "
           "Zeiten sind Annahmen. C und D der Zielteile gelten in beiden Fällen gleich.")

# Annahmen (in der Oberflaeche aenderbar). Keine Werte aus der OEKOBAUDAT.
STANDARD_PARAMETER = {
    "transport_max": 3.0,         # m, laengstes transportierbares Stueck
    "schnittverlust_mm": 3.0,     # mm Schnittfuge je Schnitt
    "min_rest": 0.30,             # m, kuerzere Reste zaehlen als Verschnitt
    "ueberbreite_mm": 40.0,       # mm, max. Breite des Spenders ueber dem Zielteil (Flachstahl)
    "schnitt_co2": 0.5,           # kg CO2e je Schnitt (Annahme)
    "transport_co2": 0.1,         # kg CO2e je t und km (Annahme LKW)
    "km_reuse": 50.0,             # km Spender -> Baustelle
    "km_neu": 150.0,              # km Stahlhandel -> Baustelle
    "min_schnitt": 5.0,           # min je Schnitt
    "min_ausbau": 20.0,           # min Ausbau je genutztem Spenderstab
    "min_pruefung": 10.0,         # min Pruefung/Reinigung je genutztem Spenderstab
    "tage_neu": 10.0,             # Arbeitstage bis zur Lieferung neuer Ware
    "tage_reuse": 2.0,            # Arbeitstage bis die Spender verfuegbar sind
}

GRENZEN = {
    "transport_max": (0.5, 12.0), "schnittverlust_mm": (0.0, 20.0), "min_rest": (0.0, 2.0),
    "ueberbreite_mm": (0.0, 300.0), "schnitt_co2": (0.0, 50.0), "transport_co2": (0.0, 1.0),
    "km_reuse": (0.0, 1000.0), "km_neu": (0.0, 3000.0), "min_schnitt": (0.0, 120.0),
    "min_ausbau": (0.0, 600.0), "min_pruefung": (0.0, 600.0), "tage_neu": (0.0, 200.0),
    "tage_reuse": (0.0, 200.0),
}

# Beispiel-Zielentwurf (ausgedacht, passt zu den vorhandenen Spendern). In der Oberflaeche aenderbar.
ZIEL_STANDARD = [
    {"typ": "flach", "breite": 120.0, "dicke": 12.0, "laenge": 0.50, "anzahl": 20},
    {"typ": "flach", "breite": 200.0, "dicke": 20.0, "laenge": 0.35, "anzahl": 10},
    {"typ": "flach", "breite": 150.0, "dicke": 12.0, "laenge": 0.35, "anzahl": 15},
    {"typ": "rohr", "breite": 0.0, "dicke": 0.0, "laenge": 1.50, "anzahl": 16},
    {"typ": "rohr", "breite": 0.0, "dicke": 0.0, "laenge": 4.50, "anzahl": 2},
    {"typ": "rund", "breite": 0.0, "dicke": 0.0, "laenge": 1.20, "anzahl": 100},
    {"typ": "rund", "breite": 0.0, "dicke": 0.0, "laenge": 3.00, "anzahl": 5},
]

TYP_NAME = {"flach": "Flachstahl", "rohr": "Rohr RO 139.7x8.0", "rund": "Rundstahl RD 12"}
GRUPPE_ZU_TYP = {"flachstahl": "flach", "rohr": "rohr", "zugstab": "rund"}


def standard():
    """Vorgabewerte fuer die Oberflaeche."""
    return {"hinweis": HINWEIS, "parameter": dict(STANDARD_PARAMETER), "grenzen": GRENZEN,
            "ziel": [dict(z) for z in ZIEL_STANDARD], "typen": TYP_NAME}


def _zahl(wert, lo, hi, std):
    try:
        x = float(wert)
    except (TypeError, ValueError):
        return std
    return min(max(x, lo), hi) if math.isfinite(x) else std


def _parameter(roh):
    roh = roh if isinstance(roh, dict) else {}
    return {k: _zahl(roh.get(k), GRENZEN[k][0], GRENZEN[k][1], v) for k, v in STANDARD_PARAMETER.items()}


def _ziel(roh):
    """Zielentwurf pruefen. Rueckgabe: Liste sauberer Zeilen."""
    if not isinstance(roh, list):
        raise ValueError("Der Zielentwurf muss eine Liste sein")
    zeilen = []
    for n, z in enumerate(roh[:200]):
        if not isinstance(z, dict) or z.get("typ") not in TYP_NAME:
            raise ValueError("Zielentwurf Zeile %d ist ungültig" % (n + 1))
        zeile = {"typ": z["typ"], "laenge": _zahl(z.get("laenge"), 0.05, 12.0, 1.0),
                 "anzahl": int(_zahl(z.get("anzahl"), 0, 1000, 1)), "breite": 0.0, "dicke": 0.0}
        if z["typ"] == "flach":
            zeile["breite"] = _zahl(z.get("breite"), 10.0, 500.0, 100.0)
            zeile["dicke"] = _zahl(z.get("dicke"), 3.0, 60.0, 12.0)
        zeilen.append(zeile)
    return zeilen


class _Spender:
    """Ein Stab des Pavillons als Strecke. x = Abstand vom breiteren Ende in m."""

    def __init__(self, i, stab, typ):
        self.i, self.typ, self.laenge, self.volumen = i, typ, stab.laenge_m, stab.volumen_m3
        self.pos, self.stuecke, self.sprunge, self.ende_letztes, self.genutzt_vol = 0.0, 0, 0, 0.0, 0.0
        if typ == "flach":
            b0, d = (float(v) for v in re.findall(ZAHL + "/" + ZAHL, stab.profil)[0])
            b1 = float(re.findall(ZAHL + "/", stab.profil_ende)[0]) if stab.profil_ende != "-" else b0
            self.wb, self.wn, self.dicke = max(b0, b1), min(b0, b1), d
            self.klasse = ("flach", round(d, 2))
            self.flaeche = 0.0
        else:
            self.wb = self.wn = self.dicke = 0.0
            self.flaeche = flaeche_m2(stab.profil)
            self.klasse = (typ,)

    def _quer(self, x):
        """Querschnittsflaeche in m2 an der Stelle x."""
        if self.typ != "flach":
            return self.flaeche
        return (self.wb - (self.wb - self.wn) * x / self.laenge) * self.dicke * 1e-6

    def vol(self, x0, x1):
        return (self._quer(x0) + self._quer(x1)) / 2.0 * max(x1 - x0, 0.0)

    def _teil_vol(self, b, laenge):
        return (b * self.dicke * 1e-6 if self.typ == "flach" else self.flaeche) * laenge

    def fenster(self, b, ueber_mm):
        """(xmin, xmax): Bereich, in dem ein Teil der Breite b liegen darf, sonst None (nur Flachstahl)."""
        if self.typ != "flach":
            return 0.0, self.laenge
        if self.wb < b - EPS:
            return None
        xmax = self.laenge if self.wn >= b else self.laenge * (self.wb - b) / (self.wb - self.wn)
        if self.wb <= b + ueber_mm:
            xmin = 0.0
        elif self.wb - self.wn < EPS:
            return None                       # gleichbreit, aber zu breit fuer das Teil
        else:
            xmin = self.laenge * (self.wb - b - ueber_mm) / (self.wb - self.wn)
        return (xmin, xmax) if xmin <= xmax + EPS else None

    def passt(self, b, laenge, ueber_mm):
        """(Startposition, Verlustvolumen) wenn das Teil noch passt, sonst None."""
        f = self.fenster(b, ueber_mm)
        if f is None:
            return None
        s = max(self.pos, f[0])
        if s + laenge > min(f[1], self.laenge) + EPS:
            return None
        return s, self.vol(self.pos, s + laenge) - self._teil_vol(b, laenge)

    def lege(self, b, laenge, s, fuge):
        if s > self.pos + 1e-6:
            self.sprunge += 1
        self.genutzt_vol += self._teil_vol(b, laenge)
        self.ende_letztes = s + laenge
        self.pos = min(s + laenge + fuge, self.laenge)
        self.stuecke += 1

    def schnitte(self):
        """Ein Schnitt am Ende jedes Teils (entfaellt am Stabende) und einer am Anfang nach einer Luecke."""
        if self.stuecke == 0:
            return 0
        return self.stuecke + self.sprunge - (1 if self.laenge - self.ende_letztes < 1e-3 else 0)


def _teile(ziel, transport_max):
    """Zielzeilen in einzelne Stuecke zerlegen. Teile ueber dem Transportmass werden gleichmaessig geteilt."""
    teile, stoesse = [], 0
    for r, z in enumerate(ziel):
        n = max(1, math.ceil(z["laenge"] / transport_max - 1e-9))
        for _ in range(z["anzahl"]):
            for _k in range(n):
                teile.append((r, z["typ"], z["breite"], z["dicke"], z["laenge"] / n))
            stoesse += n - 1
    if len(teile) > 5000:
        raise ValueError("Der Zielentwurf hat über 5000 Einzelteile. Bitte verkleinern.")
    return teile, stoesse



def _schneide(p, teile, par):
    """Best-Fit-Decreasing. Rueckgabe: Spender je Klasse, Ergebnis je Zielzeile, Volumen gedeckt/fehlend (m3)."""
    fuge = par["schnittverlust_mm"] / 1000.0
    spender = {}
    for i, (s, g) in enumerate(zip(p.staebe, p.gruppe)):
        if g in GRUPPE_ZU_TYP:
            d = _Spender(i, s, GRUPPE_ZU_TYP[g])
            spender.setdefault(d.klasse, []).append(d)
    quer = {"rohr": flaeche_m2(p.profile_je_gruppe["rohr"][0]), "rund": flaeche_m2(p.profile_je_gruppe["zugstab"][0])}
    zeilen = {}
    vol_gedeckt = vol_fehlt = 0.0
    for r, typ, b, d, laenge in sorted(teile, key=lambda t: (t[1], -t[2], -t[4])):
        klasse = ("flach", round(d, 2)) if typ == "flach" else (typ,)
        vol = (b * d * 1e-6 if typ == "flach" else quer[typ]) * laenge
        beste = None
        for sp in spender.get(klasse, []):
            erg = sp.passt(b, laenge, par["ueberbreite_mm"])
            if erg is None:
                continue
            schluessel = (round(erg[1], 9), sp.laenge - (erg[0] + laenge + fuge))
            if beste is None or schluessel < beste[0]:
                beste = (schluessel, sp, erg[0])
        z = zeilen.setdefault(r, {"gedeckt": 0, "fehlend": 0, "stab": set()})
        if beste is None:
            z["fehlend"] += 1
            vol_fehlt += vol
        else:
            beste[1].lege(b, laenge, beste[2], fuge)
            z["gedeckt"] += 1
            z["stab"].add(p.staebe[beste[1].i].beam_id)
            vol_gedeckt += vol
    return spender, zeilen, vol_gedeckt, vol_fehlt


def _bilanz(p, spender, par):
    """Status je Stab (0 kein Spender, 1 unbenutzt, 2 teilweise, 3 weitgehend genutzt) und Massen."""
    stab = [{"s": 0, "n": 0, "auslastung": 0.0, "rest_m": 0.0} for _ in p.staebe]
    verschnitt = rest_lager = 0.0
    schnitte = genutzt = 0
    info = {}
    for klasse, liste in spender.items():
        e = info.setdefault(klasse[0], {"typ": klasse[0], "name": TYP_NAME[klasse[0]], "n": 0, "genutzt": 0,
                                        "laenge": 0.0, "masse": 0.0})
        for sp in liste:
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
            rest_vol = sp.vol(sp.pos, sp.laenge)
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
    return stab, verschnitt * DICHTE, rest_lager * DICHTE, schnitte, genutzt, info



def rechne(p, roh):
    """Zuschnitt und Vergleich. roh = App-Konfiguration + {ziel, parameter}."""
    roh = roh or {}
    cfg = p.config(roh)
    par = _parameter(roh.get("parameter"))
    ziel = _ziel(roh["ziel"] if "ziel" in roh else ZIEL_STANDARD)
    _menge, _einheit, je_m3 = p._co2(1.0, "stahl", cfg)          # kg CO2e je m3 Baustahl
    if je_m3 is None:
        raise ValueError("Der Datensatz für Baustahl ist nicht geladen. Bitte „Datensätze neu laden“.")

    teile, stoesse = _teile(ziel, par["transport_max"])
    spender, zeilen, vol_gedeckt, vol_fehlt = _schneide(p, teile, par)
    stab, verschnitt_kg, rest_kg, schnitte, genutzt, info = _bilanz(p, spender, par)

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
            name = TYP_NAME[z["typ"]] + (" %g/%g" % (z["breite"], z["dicke"]) if z["typ"] == "flach" else "")
            warnungen.append("%s, %s m: %d Teile finden keinen passenden Spender und werden neu beschafft."
                             % (name, ("%g" % z["laenge"]).replace(".", ","), zeilen[n]["fehlend"]))
    return {
        "module": MODULE, "hinweis": HINWEIS, "warnungen": warnungen, "parameter": par,
        "ziel": [dict(z, gedeckt=zeilen.get(n, {}).get("gedeckt", 0), fehlend=zeilen.get(n, {}).get("fehlend", 0),
                      staebe=sorted(zeilen.get(n, {}).get("stab", ()), key=lambda x: (len(x), x)))
                 for n, z in enumerate(ziel)],
        "stab": stab,
        "spender": [info[k] for k in ("flach", "rohr", "rund") if k in info],
        "summen": {
            "teile": anz, "stoesse": stoesse, "schnitte": schnitte, "spender_genutzt": genutzt,
            "masse_ziel_kg": round(m_ziel, 2), "masse_gedeckt_kg": round(m_gedeckt, 2),
            "masse_fehlt_kg": round(m_fehlt, 2),
            "deckung_prozent": round(100.0 * m_gedeckt / m_ziel, 1) if m_ziel else 0.0,
            "verschnitt_kg": round(verschnitt_kg, 2), "rest_lager_kg": round(rest_kg, 2),
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

