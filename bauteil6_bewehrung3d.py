# -*- coding: utf-8 -*-
"""
3D-Bewehrung fuer Bauteil6 aus den vier Bewehrungsplaenen (siehe bauteil6_plaene.py).

WICHTIG, anders als bei Stockerau: Die Plaene fuer Bauteil6 sind gross (Biegelisten mit ueber 100 Positionen).
Die Staebe werden hier NICHT einzeln nach Plan verlegt, sondern SCHEMATISCH je Bauteil erzeugt:
  * Menge aus dem Plan: Die Masse, die einem Bauteil zugeteilt ist (Plan-Masse nach Volumen verteilt),
    bestimmt die Anzahl der Staebe. Die erzeugte Masse liegt deshalb nahe an der Plan-Masse (Pruefung je Plan).
  * Lage und Form sind Annahmen: Decke (2448) = unteres Netz in beide Richtungen, Decke (2458) = Randnadeln
    oben am Rand, Waende = Netz auf beiden Seiten, Stuetzen und Unter-/Ueberzuege = Laengsstaebe + Buegel.
  * Durchmesser: Netze und Laengsstaebe ø12, Buegel ø10 (die haeufigsten Durchmesser der Biegelisten).
  * Achsen: Bauteile als achsparallele Quader (Bounding Box). Schraege Waende sind dadurch leicht versetzt.
Die Darstellung zeigt also, wo und wie viel Bewehrung laut Plan steckt, nicht jeden einzelnen Stab.
"""
import math

from bauteil6_plaene import PLAENE

KG_JE_M = {10: 0.617, 12: 0.888, 16: 1.578}
C = 0.035                       # Achsabstand der Staebe zur Betonoberflaeche (Deckung + halber Stab)
MAX_STAEBE = 400                # je Richtung und Bauteil (Darstellung)


def _anzahl(kg, laenge, d, maximum=MAX_STAEBE):
    if laenge <= 0.05 or kg <= 0:
        return 0
    return max(1, min(maximum, int(round(kg / (laenge * KG_JE_M[d])))))


def _verteilt(lo, hi, n):
    if n <= 0:
        return []
    if n == 1:
        return [(lo + hi) / 2.0]
    return [lo + (hi - lo) * k / (n - 1) for k in range(n)]


class _Sammler:
    def __init__(self):
        self.stangen = []           # {"pts", "d", "laenge"}

    def stab(self, pts, d):
        laenge = sum(math.dist(pts[k], pts[k + 1]) for k in range(len(pts) - 1))
        self.stangen.append({"pts": [tuple(round(c, 3) for c in p) for p in pts], "d": d, "laenge": laenge})


def _netz(s, b, kg, z, d=12):
    """Zwei Lagen in x- und y-Richtung auf Hoehe z (Decke)."""
    x0, y0, x1, y1 = b[0] + C, b[1] + C, b[3] - C, b[4] - C
    lx, ly = x1 - x0, y1 - y0
    for y in _verteilt(y0, y1, _anzahl(kg / 2, lx, d)):
        s.stab([(x0, y, z), (x1, y, z)], d)
    for x in _verteilt(x0, x1, _anzahl(kg / 2, ly, d)):
        s.stab([(x, y0, z + 0.012), (x, y1, z + 0.012)], d)


def _randnadeln(s, b, kg, z, d=12, laenge=2.5):
    """Nadeln quer zum Rand, oben, rundum (Decke, Plan 2458)."""
    x0, y0, x1, y1 = b[0] + C, b[1] + C, b[3] - C, b[4] - C
    umfang = 2 * ((x1 - x0) + (y1 - y0))
    n = _anzahl(kg, laenge, d, maximum=1500)
    if n == 0 or umfang <= 0:
        return
    for k in range(n):
        t = (k + 0.5) / n * umfang
        if t < x1 - x0:
            x = x0 + t
            s.stab([(x, y0, z), (x, y0 + laenge, z)], d)
        elif t < (x1 - x0) + (y1 - y0):
            y = y0 + t - (x1 - x0)
            s.stab([(x1, y, z), (x1 - laenge, y, z)], d)
        elif t < 2 * (x1 - x0) + (y1 - y0):
            x = x1 - (t - (x1 - x0) - (y1 - y0))
            s.stab([(x, y1, z), (x, y1 - laenge, z)], d)
        else:
            y = y1 - (t - 2 * (x1 - x0) - (y1 - y0))
            s.stab([(x0, y, z), (x0 + laenge, y, z)], d)


def _wand(s, b, kg, d=12):
    """Netz auf beiden Wandseiten: senkrechte und waagrechte Staebe."""
    dx, dy = b[3] - b[0], b[4] - b[1]
    z0, z1 = b[2] + C, b[5] - C
    laengs_x = dx >= dy
    a0, a1 = (b[0] + C, b[3] - C) if laengs_x else (b[1] + C, b[4] - C)
    q0, q1 = (b[1] + C, b[4] - C) if laengs_x else (b[0] + C, b[3] - C)
    if q1 < q0:
        q0 = q1 = (q0 + q1) / 2
    lang, hoch = a1 - a0, z1 - z0

    def p(a, q, z):
        return (a, q, z) if laengs_x else (q, a, z)
    for q in (q0, q1):
        for a in _verteilt(a0, a1, _anzahl(kg / 4, hoch, d)):
            s.stab([p(a, q, z0), p(a, q, z1)], d)
        for z in _verteilt(z0, z1, _anzahl(kg / 4, lang, d)):
            s.stab([p(a0, q, z), p(a1, q, z)], d)


def _stab_bauteil(s, b, kg, rund, senkrecht):
    """Stuetze (senkrecht) oder Unter-/Ueberzug: 60 % Laengsstaebe ø12 an den Ecken, 40 % Buegel ø10."""
    if senkrecht:
        achse, q = 2, (0, 1)
    else:
        achse = 0 if (b[3] - b[0]) >= (b[4] - b[1]) else 1
        q = (1, 2) if achse == 0 else (0, 2)
    lo, hi = b[achse] + C, b[achse + 3] - C
    u0, u1, v0, v1 = b[q[0]] + C, b[q[0] + 3] - C, b[q[1]] + C, b[q[1] + 3] - C
    um, vm = (u0 + u1) / 2, (v0 + v1) / 2

    def p(a, u, v):
        x = [0.0, 0.0, 0.0]
        x[achse], x[q[0]], x[q[1]] = a, u, v
        return tuple(x)
    n_l = max(4, _anzahl(kg * 0.6, hi - lo, 12))
    for k in range(n_l):                       # rundum gleichmaessig (Kreis bzw. Rechteckumfang)
        w = 2 * math.pi * (k + 0.5) / n_l
        if rund:
            u, v = um + (u1 - u0) / 2 * math.cos(w), vm + (v1 - v0) / 2 * math.sin(w)
        else:
            c, sn = math.cos(w), math.sin(w)
            f = 1.0 / max(abs(c), abs(sn))
            u, v = um + (u1 - u0) / 2 * c * f, vm + (v1 - v0) / 2 * sn * f
        s.stab([p(lo, u, v), p(hi, u, v)], 12)
    if rund:
        ring = [(um + (u1 - u0) / 2 * math.cos(2 * math.pi * k / 16), vm + (v1 - v0) / 2 * math.sin(2 * math.pi * k / 16))
                for k in range(17)]
    else:
        ring = [(u0, v0), (u1, v0), (u1, v1), (u0, v1), (u0, v0)]
    umfang = sum(math.dist(ring[k], ring[k + 1]) for k in range(len(ring) - 1))
    for a in _verteilt(lo, hi, _anzahl(kg * 0.4, umfang, 10)):
        s.stab([p(a, u, v) for u, v in ring], 10)


def erzeuge(teile, je_plan):
    """Staebe je Plan. je_plan = {plan_id: {Bauteil-Index: kg}} (aus bauteil6_plaene.verteile)."""
    plaene = {}
    for nr, plan in enumerate(PLAENE, start=1):
        stangen = []
        for i, kg in sorted(je_plan.get(plan["id"], {}).items()):
            t, s = teile[i], _Sammler()
            b = t["bbox"]
            if t["art"] == "decke":
                if plan["id"] == "2448":
                    _netz(s, b, kg, b[2] + C)
                else:
                    _randnadeln(s, b, kg, b[5] - C)
            elif t["art"] == "wand":
                _wand(s, b, kg)
            else:
                _stab_bauteil(s, b, kg, rund="ø" in t["typ"], senkrecht=t["art"] == "stuetze")
            for st in s.stangen:
                st["teil"] = i
                st["soll_kg"] = kg
            stangen.extend(s.stangen)
        plaene[plan["id"]] = {"nr": nr, "stangen": stangen}
    return plaene


def fuer_oberflaeche(plaene):
    """Gleiches Format wie bewehrung3d.fuer_oberflaeche (Stockerau): je Position (= Plan) ein Linienzug."""
    pos, pruefung, masse = {}, [], {}
    gesamt_ist = gesamt_soll = 0.0
    n_gesamt = 0
    for plan in PLAENE:
        e = plaene[plan["id"]]
        d = {"x": [], "y": [], "z": [], "balken": []}
        ist = 0.0
        for st in e["stangen"]:
            a = len(d["x"])
            for p in st["pts"]:
                d["x"].append(p[0]); d["y"].append(p[1]); d["z"].append(p[2])
            d["x"].append(None); d["y"].append(None); d["z"].append(None)
            d["balken"].append([a, len(d["x"]), [st["teil"]]])
            kg = st["laenge"] * KG_JE_M[st["d"]]
            ist += kg
            masse[st["teil"]] = masse.get(st["teil"], 0.0) + kg
        pos[e["nr"]] = d
        soll = plan["masse_kg"]
        pruefung.append({"pos": e["nr"], "plan": plan["id"], "durchmesser": 12, "soll_stueck": len(e["stangen"]),
                         "ist_stueck": len(e["stangen"]), "soll_kg": soll, "ist_kg": round(ist, 2),
                         "ok": abs(ist - soll) <= 0.05 * soll})
        gesamt_ist += ist
        gesamt_soll += soll
        n_gesamt += len(e["stangen"])
    pruefung.append({"pos": 0, "plan": "", "durchmesser": 0, "soll_stueck": n_gesamt, "ist_stueck": n_gesamt,
                     "soll_kg": round(gesamt_soll, 2), "ist_kg": round(gesamt_ist, 2),
                     "ok": abs(gesamt_ist - gesamt_soll) <= 0.05 * gesamt_soll})
    return {"pos": pos, "pruefung": pruefung, "schematisch": True,
            "plaene": [{"pos": n + 1, "id": p["id"], "titel": p["titel"]} for n, p in enumerate(PLAENE)],
            "masse_je_stab": {str(i): round(v, 3) for i, v in masse.items()}}
