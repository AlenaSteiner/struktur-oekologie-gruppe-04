# -*- coding: utf-8 -*-
"""
3D-Bewehrung der Streifenfundamente, erzeugt aus dem Bewehrungsplan BG_5_BP_FU_XX_001_P-01.

Was aus dem Plan kommt (abgelesen, Plan M 1:25):
  Pos. 1  Buegel ø10 @ 20 cm: 51 je Querstreifen, 23 je Luecke der Laengsstreifen, dazu 12 x "Detail 1"
          (Stabliste: 341 Stueck, 1,98 m)
  Pos. 2  ø12, L = 5,55 m: Querstreifen, 2 Stuecke je Streifen mit 1,00 m Uebergreifung (60 Stk.)
  Pos. 4  ø12, L = 4,10 m: Laengsstreifen, 3 Stuecke je Streifen mit 1,00 m Uebergreifung (60 Stk.)
  Pos. 3  ø12, L = 2,39 m: Endschlaufen (4 je Streifenende, 10 Enden = 40 Stk.)
  Je Stueck von Pos. 2 und 4: 4 oben + 4 unten + 2 seitlich (Plan: "2x 4 ø12 unt.& ob." + "2 ø12 seitl.").

Annahmen (steht NICHT im Plan, ist hier gesetzt):
  * "Detail 1" (12x, je "4 ø10 Bue." zweimal = 96 Buegel): 6 Kreuzungen (3 Querstreifen x 2 Laengsstreifen) und 6 Streifenenden.
    Kreuzung: 4 Buegel quer + 4 Buegel laengs im Abstand 10 cm. Ende: 8 Buegel im Abstand 6 cm. Die genaue Lage
    steht nur im Detail, nicht bemasst; sie ist hier angenommen. Die Summe 153 + 92 + 96 = 341 stimmt mit der Stabliste.
  * Lage der Staebe im Querschnitt (4 oben / 4 unten gleichmaessig, 2 seitlich auf halber Hoehe),
    Versatz der zweiten Uebergreifungshaelfte, Form der Buegel als Rechteck (Haken nicht gezeichnet).
  * Die Plan-Streifen sind laenger als die Betonkoerper im Rhino-Modell (Quer 10,1 m statt 9,0 m).
    Die Stahlmasse ausserhalb des Modell-Betons wird dem jeweils letzten Modellstab zugerechnet.
Die Masse je Stab ergibt sich aus der Stabliste (kg je m je Position), die Summe ist exakt die Plan-Gesamtmasse.
"""
import math

from bewehrungsplan import DECKUNG_CM, STABLISTE, SUMME_KG

KG_JE_M = {z["pos"]: z["masse"] / z["gesamt"] for z in STABLISTE}
LAENGE = {z["pos"]: z["einzel"] for z in STABLISTE}
DURCHMESSER = {z["pos"]: z["durchmesser"] for z in STABLISTE}

C = DECKUNG_CM / 100.0                      # Betondeckung 4 cm
HALB = 0.25                                 # halbe Streifenbreite / -hoehe (50/50)
R_BUEGEL = HALB - C - 0.005                 # Buegelachse (ø10) 0,205
R_STAB = 0.194                              # Achse der ø12-Laengsstaebe
QUER_PLAN = (6.5, 16.6)                     # Querstreifen laut Plan (x), 10,1 m
QUER_STUECKE = ((6.5, 12.05), (11.05, 16.6))
LAENGS_STUECKE = ((-3.95, 0.15), (-7.05, -2.95), (-10.15, -6.05))   # y, 4,10 m, 1,00 m Uebergreifung
LAENGS_LUECKEN = (-0.30, -5.30)             # erster Buegel je Luecke (y), danach 22 x -0,20 m
LAGEN = [(t, R_STAB) for t in (-R_STAB, -0.065, 0.065, R_STAB)] + \
        [(t, -R_STAB) for t in (-R_STAB, -0.065, 0.065, R_STAB)] + [(-R_STAB, 0.0), (R_STAB, 0.0)]
ERWARTET_QUER = (0.0, -5.0, -10.0)
ERWARTET_LAENGS = (10.0, 13.0)


def _streifen(staebe, gruppe):
    """{(art, Konstante): [Segmente nach Lage sortiert]} aus den Fundamentstaeben des Modells."""
    res = {}
    for i, (s, g) in enumerate(zip(staebe, gruppe)):
        if g != "fundament":
            continue
        a, b = s.start, s.ende
        if abs(a[1] - b[1]) < 1e-6:
            art, c, s0, s1, z0, z1 = "quer", round(a[1], 3), a[0], b[0], a[2], b[2]
        elif abs(a[0] - b[0]) < 1e-6:
            art, c, s0, s1, z0, z1 = "laengs", round(a[0], 3), a[1], b[1], a[2], b[2]
        else:
            raise ValueError("Fundamentstab liegt nicht in x- oder y-Richtung: %s" % s.beam_id)
        if s0 > s1:
            s0, s1, z0, z1 = s1, s0, z1, z0
        res.setdefault((art, c), []).append({"i": i, "s0": s0, "s1": s1, "z0": z0, "z1": z1})
    for liste in res.values():
        liste.sort(key=lambda e: e["s0"])
    quer = sorted(c for (a, c) in res if a == "quer")
    laengs = sorted(c for (a, c) in res if a == "laengs")
    if quer != sorted(ERWARTET_QUER) or laengs != sorted(ERWARTET_LAENGS):
        raise ValueError("Streifen im Modell passen nicht zum Plan: quer %s, laengs %s" % (quer, laengs))
    return res


def _z(liste, s):
    """Hoehe der Streifenachse bei s (linear je Segment, ausserhalb mit der Steigung des Endsegments)."""
    if s <= liste[0]["s0"]:
        e = liste[0]
    elif s >= liste[-1]["s1"]:
        e = liste[-1]
    else:
        e = next(x for x in liste if x["s0"] <= s <= x["s1"])
    return e["z0"] + (e["z1"] - e["z0"]) * (s - e["s0"]) / (e["s1"] - e["s0"])


def _segment(liste, s):
    if s <= liste[0]["s0"]:
        return liste[0]["i"]
    for e in liste:
        if s <= e["s1"] + 1e-9:
            return e["i"]
    return liste[-1]["i"]


def _verteile(liste, lo, hi):
    """Laenge von [lo, hi] je Modellstab; was ueber die Enden hinausragt, geht an den Endstab."""
    out = {}
    s0, s1 = liste[0]["s0"], liste[-1]["s1"]
    for k, e in enumerate(liste):
        laenge = max(0.0, min(hi, e["s1"]) - max(lo, e["s0"]))
        if k == 0:
            laenge += max(0.0, min(hi, s0) - lo)
        if k == len(liste) - 1:
            laenge += max(0.0, hi - max(lo, s1))
        if laenge > 1e-9:
            out[e["i"]] = out.get(e["i"], 0.0) + laenge
    return out


def _punkt(art, c, liste, s, t, v):
    z = _z(liste, s) + v
    return [round(c + t, 4), round(s, 4), round(z, 4)] if art == "laengs" else [round(s, 4), round(c + t, 4), round(z, 4)]


def _grenzen(liste, a, b):
    """Stuetzstellen entlang [a, b]: Anfang, Knoten der Modellstaebe dazwischen, Ende."""
    inner = sorted({v for e in liste for v in (e["s0"], e["s1"]) if a + 1e-6 < v < b - 1e-6})
    return [a] + inner + [b]


def _stange(art, c, liste, a, b, t, v):
    return [_punkt(art, c, liste, s, t, v) for s in _grenzen(liste, a, b)]


def _buegel(art, c, liste, s, r=R_BUEGEL):
    z = _z(liste, s)
    ecken = [(-r, -r), (r, -r), (r, r), (-r, r), (-r, -r)]
    if art == "quer":
        return [[round(s, 4), round(c + t, 4), round(z + v, 4)] for t, v in ecken]
    return [[round(c + t, 4), round(s, 4), round(z + v, 4)] for t, v in ecken]


def erzeuge(staebe, gruppe):
    """Alle Bewehrungsstaebe in 3D. Rueckgabe: {"stangen": [...], "masse": {stab_index: kg}, "pruefung": [...]}."""
    strei = _streifen(staebe, gruppe)
    stangen, masse = [], {}

    def neu(pos, pts, anteile):
        """anteile: {stab_index: Anteil 0..1 der Stangenmasse}."""
        kg = LAENGE[pos] * KG_JE_M[pos]
        for i, f in anteile.items():
            masse[i] = masse.get(i, 0.0) + kg * f
        stangen.append({"pos": pos, "pts": pts, "stabs": sorted(anteile)})

    for c in ERWARTET_QUER:                                   # Querstreifen (x-Richtung)
        li = strei[("quer", c)]
        for k in range(51):                                   # Pos. 1: 51 Buegel @ 20 cm
            s = 6.55 + 0.2 * k
            neu(1, _buegel("quer", c, li, s), {_segment(li, s): 1.0})
        offs = (-0.15, -0.05, 0.05, 0.15)
        for xz in ERWARTET_LAENGS:                            # Detail 1 an der Kreuzung: 4 + 4 Zusatzbuegel
            ll = strei[("laengs", xz)]
            for o in offs:
                s = xz + o                                    # 4 Buegel des Querstreifens in der Kreuzung
                neu(1, _buegel("quer", c, li, s), {_segment(li, s): 1.0})
            for o in offs:
                s = c + o                                     # 4 Buegel des Laengsstreifens in der Kreuzung
                neu(1, _buegel("laengs", xz, ll, s), {_segment(ll, s): 1.0})
        for ende, vorz in ((QUER_PLAN[0], 1.0), (QUER_PLAN[1], -1.0)):   # Detail 1 am Streifenende: 8 Buegel
            for k in range(8):
                s = ende + vorz * (0.05 + 0.06 * k)
                neu(1, _buegel("quer", c, li, s), {_segment(li, s): 1.0})
        for a, b in QUER_STUECKE:                             # Pos. 2: ø12, 5,55 m
            teil = _verteile(li, a, b)
            for t, v in LAGEN:
                neu(2, _stange("quer", c, li, a, b, t, v), {i: d / (b - a) for i, d in teil.items()})
        for ende, vorz in ((QUER_PLAN[0], 1.0), (QUER_PLAN[1], -1.0)):    # Pos. 3: Schlaufen an den Enden
            for v in (-R_STAB, -0.065, 0.065, R_STAB):
                s0, s1 = ende, ende + vorz * 1.0
                pts = [_punkt("quer", c, li, s1, -R_STAB, v), _punkt("quer", c, li, s0, -R_STAB, v),
                       _punkt("quer", c, li, s0, R_STAB, v), _punkt("quer", c, li, s1, R_STAB, v)]
                neu(3, pts, {_segment(li, s0): 1.0})
    for c in ERWARTET_LAENGS:                                 # Laengsstreifen (y-Richtung)
        li = strei[("laengs", c)]
        for start in LAENGS_LUECKEN:                          # Pos. 1: 23 Buegel je Luecke
            for k in range(23):
                s = start - 0.2 * k
                neu(1, _buegel("laengs", c, li, s), {_segment(li, s): 1.0})
        for a, b in LAENGS_STUECKE:                           # Pos. 4: ø12, 4,10 m
            teil = _verteile(li, a, b)
            for t, v in LAGEN:
                neu(4, _stange("laengs", c, li, a, b, t, v), {i: d / (b - a) for i, d in teil.items()})
        for ende, vorz in ((LAENGS_STUECKE[0][1], -1.0), (LAENGS_STUECKE[-1][0], 1.0)):
            for v in (-R_STAB, -0.065, 0.065, R_STAB):
                s0, s1 = ende, ende + vorz * 1.0
                pts = [_punkt("laengs", c, li, s1, -R_STAB, v), _punkt("laengs", c, li, s0, -R_STAB, v),
                       _punkt("laengs", c, li, s0, R_STAB, v), _punkt("laengs", c, li, s1, R_STAB, v)]
                neu(3, pts, {_segment(li, s0): 1.0})
    return {"stangen": stangen, "masse": masse, "pruefung": _pruefung(stangen, masse)}


def _pruefung(stangen, masse):
    """Vergleich mit der Stabliste: Stueckzahl, Gesamtlaenge und Masse je Position."""
    zeilen = []
    for z in STABLISTE:
        mine = [s for s in stangen if s["pos"] == z["pos"]]
        kg = len(mine) * LAENGE[z["pos"]] * KG_JE_M[z["pos"]]
        zeilen.append({"pos": z["pos"], "durchmesser": z["durchmesser"], "soll_stueck": z["stueck"], "ist_stueck": len(mine),
                       "soll_kg": z["masse"], "ist_kg": round(kg, 2), "ok": len(mine) == z["stueck"]})
    zeilen.append({"pos": 0, "durchmesser": 0, "soll_stueck": sum(z["stueck"] for z in STABLISTE),
                   "ist_stueck": len(stangen), "soll_kg": SUMME_KG, "ist_kg": round(sum(masse.values()), 2),
                   "ok": abs(sum(masse.values()) - SUMME_KG) < 0.05})
    return zeilen


def fuer_oberflaeche(erg):
    """Kompakte Form fuer die Web-Oberflaeche.

    Je Position ein Linienzug mit None-Trennern (x, y, z). `balken` = [Start, Ende (ohne), [Modellstaebe, die der
    Bewehrungsstab beruehrt]] -> damit laesst sich die Bewehrung eines angeklickten Fundamentstabes herausfiltern."""
    pos = {p: {"x": [], "y": [], "z": [], "balken": []} for p in (1, 2, 3, 4)}
    for s in erg["stangen"]:
        d = pos[s["pos"]]
        a = len(d["x"])
        for p in s["pts"]:
            d["x"].append(p[0]); d["y"].append(p[1]); d["z"].append(p[2])
        d["x"].append(None); d["y"].append(None); d["z"].append(None)
        d["balken"].append([a, len(d["x"]), s["stabs"]])
    return {"pos": pos, "pruefung": erg["pruefung"], "durchmesser": DURCHMESSER,
            "masse_je_stab": {str(i): round(v, 3) for i, v in erg["masse"].items()}}

