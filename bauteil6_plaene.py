# -*- coding: utf-8 -*-
"""
Bewehrungsplaene fuer Bauteil6 (MG5, Geschoss E02), Mayr | Ludescher | Partner (MCM), Stand 2023.

Vier Plaene liegen vor (Ordner plaene/bauteil6):
  2438  Aussenwaende, Innenwaende und Stuetzen E02 ............ 3 599,50 kg
  2448  Decke ueber E02, untere Bewehrung (Grundnetz) ......... 3 293,63 kg
  2458  Decke ueber E02, Randnadeln, Stecker, Unter-/Ueberzuege  2 786,16 kg
  2648  Wandscheiben E02 Hoffassade Achse D (Zusatzplan) ......   377,00 kg
Die Massen sind die "Gesamtgewicht"-Angaben der Biegelisten (je Plan nur als Summe, nicht je Bauteil).

Zuordnung Plan -> Bauteile im Modell (nach Lage, siehe zuordnen()):
  Der Planbereich (Achsen 1-7 / A-D) liegt im Modell bei x = 26..46 m, y = -102..-87,5 m.
  2448        die Decke ueber E02 (OK +12,27, 25 cm)
  2458        dieselbe Decke + die Unter-/Ueberzuege UEZ 01 (20/101), UZ 01 (20/131), UEZ 02 (20/98), UZ 02 (20/91).
              Die Querschnitte stehen so im Plan und im Modell.
  2438        Stahlbeton-Waende und -Stuetzen im E02 (UK +7,63 bis +12,27) im Planbereich
  2648        die vier schmalen Bauteile an Achse D im E02 unterhalb UZ (UK +10,71): Stuetzen 26/20 und 44/20
              sowie die Bruestungen 20/105. ANNAHME: Im Modell heissen sie nicht "Wand 105-108".
Die Masse eines Plans wird nach dem Stahlbetonvolumen auf seine Bauteile verteilt (wie bei Stockerau
"gleichmaessig je m3"). Das ist eine Annahme: Der Plan nennt keine Masse je Bauteil.

Lage im Planbild (zum Markieren): aus den Achsbeschriftungen im PDF abgelesen (pdftotext -bbox).
  Achse 2 = Modell x 29,89 (Stuetzenachse), Achse 4 = x 35,69, Achse 6 = x 41,49 (passt auf 2 cm),
  Achse A = Modell y -101,78, Achse D = y -87,77. Massstab 1:50 (2448, 2458), Uebersicht 1:200 (2438).
  2648 ist ein A4-Zusatzplan ohne Grundriss-Massstab: das Bauteil wird dort nicht markiert.
"""
from pathlib import Path

ORDNER = Path(__file__).resolve().parent / "plaene" / "bauteil6"
PT_PRO_M_50 = 1000.0 / 50.0 / 25.4 * 72.0       # 1 m im Massstab 1:50 in PDF-Punkten (56,69)
PT_PRO_M_200 = 1000.0 / 200.0 / 25.4 * 72.0     # 1 m im Massstab 1:200 (14,17)
ACHSE_2_X = 29.89                               # Modell-x der Achse 2
ACHSE_A_Y = -101.776                            # Modell-y der Achse A

PLAENE = [
    {"id": "2438", "nummer": "6-MCM_AF_GPTP_BW_GR_E02_2438_-_02_FF",
     "titel": "Außenwände, Innenwände und Stützen E02", "masse_kg": 3599.50,
     "beton": "C25/30 (Innenwand 101 und Stützen C40/50)", "betonstahl": "B 550 B", "deckung": "2,5–3,0 cm",
     "dim": {"6–10": 729.77, "12–16": 2710.38, "20–30": 159.32}, "seite": 0,
     "breite_pt": 2693.0, "hoehe_pt": 2384.0,
     # Uebersicht M 1:200 unten links: Achse 2 bei x = 646,3 pt, Achse A bei y = 2283,2 pt
     "achse": {"x2": 646.3, "ya": 2283.2, "pt_m": PT_PRO_M_200}},
    {"id": "2448", "nummer": "6-MCM_AF_GPTP_BW_GR_E02_2448_-_02_FF",
     "titel": "Decke über E02 · untere Bewehrung (Grundnetz und untere Zulagen)", "masse_kg": 3293.63,
     "beton": "C30/37", "betonstahl": "B 550 B", "deckung": "2,5 cm",
     "dim": {"6–10": 346.60, "12–16": 2947.04}, "seite": 0,
     "breite_pt": 2409.0, "hoehe_pt": 1684.0,
     "achse": {"x2": 862.3, "ya": 1472.2, "pt_m": PT_PRO_M_50}},
    {"id": "2458", "nummer": "6-MCM_AF_GPTP_BW_GR_E02_2458_-_02_FF",
     "titel": "Decke über E02 · Randnadeln, Stecker, Unter- und Überzüge", "masse_kg": 2786.16,
     "beton": "C30/37", "betonstahl": "B 550 B", "deckung": "2,5 cm",
     "dim": {"6–10": 610.94, "12–16": 1939.60, "20–30": 235.64}, "seite": 0,
     "breite_pt": 2551.0, "hoehe_pt": 2526.0,
     "achse": {"x2": 958.3, "ya": 2374.2, "pt_m": PT_PRO_M_50}},
    {"id": "2648", "nummer": "6-MCM_AF_GPTP_BW_GR_E02_2648_-_01_FF",
     "titel": "Wandscheiben E02 Hoffassade Achse D (Zusatzplan zu 2438)", "masse_kg": 377.0,
     "beton": "–", "betonstahl": "B 550 B", "deckung": "–",
     "dim": {"6–10": 180.0, "12–16": 196.0}, "seite": 0,
     "breite_pt": 595.28, "hoehe_pt": 841.89, "achse": None,
     "stabliste": [{"pos": 100, "stueck": 56, "durchmesser": 12, "einzel": 3.95, "gesamt": 221.2, "masse": 196.0},
                   {"pos": 101, "stueck": 170, "durchmesser": 10, "einzel": 1.72, "gesamt": 292.4, "masse": 180.0}]},
]
PLAN = {p["id"]: p for p in PLAENE}
SUMME_KG = round(sum(p["masse_kg"] for p in PLAENE), 2)

# Planbereich im Modell (Achsen 1-7 / A-D, etwas Luft fuer Bauteile auf den Raendern)
BEREICH_X = (25.9, 46.2)
BEREICH_Y = (-102.0, -87.5)


def _im_bereich(b):
    return b[0] >= BEREICH_X[0] and b[3] <= BEREICH_X[1] and b[1] >= BEREICH_Y[0] and b[4] <= BEREICH_Y[1]


def _stb_anteil(t):
    return sum(a for m, a in t["schichten"] if m == "stahlbeton")


def zuordnen(teile):
    """{plan_id: [Index der Bauteile]} nach Lage, Bauteilart und Hoehe (siehe Kopf der Datei)."""
    plaene = {p["id"]: [] for p in PLAENE}
    for i, t in enumerate(teile):
        b = t["bbox"]
        if _stb_anteil(t) <= 0 or not _im_bereich(b):
            continue
        art, z0, z1 = t["art"], b[2], b[5]
        if art == "decke" and z0 >= 11.9 and z1 <= 12.4:
            plaene["2448"].append(i)
            plaene["2458"].append(i)
        elif art == "traeger" and z0 >= 10.6 and z1 <= 13.4:
            plaene["2458"].append(i)
        if art in ("wand", "stuetze") and z0 >= 7.5 and z1 <= 12.4:
            plaene["2438"].append(i)
        if art in ("wand", "stuetze", "traeger") and z0 >= 7.5 and z1 <= 10.8 and b[4] >= -87.75:
            plaene["2648"].append(i)
    return plaene


def verteile(teile, plaene):
    """Plan-Masse nach Stahlbetonvolumen auf die Bauteile. Rueckgabe: {Index: kg}, {Index: [plan_id]}, {plan_id: {Index: kg}}."""
    kg, je_bauteil, je_plan = {}, {}, {}
    for pid, idx in plaene.items():
        vol = {i: teile[i]["volumen"] * _stb_anteil(teile[i]) for i in idx}
        summe = sum(vol.values())
        je_plan[pid] = {}
        if summe <= 0:
            continue
        for i, v in vol.items():
            anteil = PLAN[pid]["masse_kg"] * v / summe
            je_plan[pid][i] = anteil
            kg[i] = kg.get(i, 0.0) + anteil
            je_bauteil.setdefault(i, []).append(pid)
    return kg, je_bauteil, je_plan


def lage(pid, bbox):
    """Rechteck des Bauteils im Planbild als Anteile [x0, y0, x1, y1] (0..1) oder None (kein Grundriss)."""
    p = PLAN[pid]
    a = p["achse"]
    if a is None:
        return None
    xs = [a["x2"] + (x - ACHSE_2_X) * a["pt_m"] for x in (bbox[0], bbox[3])]
    ys = [a["ya"] - (y - ACHSE_A_Y) * a["pt_m"] for y in (bbox[1], bbox[4])]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    mitte_x, mitte_y = (x0 + x1) / 2, (y0 + y1) / 2         # sehr schmale Bauteile sichtbar machen
    x0, x1 = min(x0, mitte_x - 3), max(x1, mitte_x + 3)
    y0, y1 = min(y0, mitte_y - 3), max(y1, mitte_y + 3)
    b, h = p["breite_pt"], p["hoehe_pt"]
    return [round(x0 / b, 5), round(y0 / h, 5), round(x1 / b, 5), round(y1 / h, 5)]


BILD_BREITE_PX = 2000
_bilder = {}


def bild_png(pid):
    """Ganzes Planblatt als PNG (einmal gerendert, dann im Speicher)."""
    if pid not in PLAN:
        raise KeyError(pid)
    if pid not in _bilder:
        import pymupdf                         # nur hier gebraucht
        p = PLAN[pid]
        seite = pymupdf.open(str(ORDNER / (p["nummer"] + ".pdf")))[p["seite"]]
        zoom = BILD_BREITE_PX / seite.rect.width
        _bilder[pid] = seite.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes("png")
    return _bilder[pid]


def info():
    """Angaben fuer die Oberflaeche (ohne Geometrie)."""
    return [dict({k: p[k] for k in ("id", "nummer", "titel", "masse_kg", "beton", "betonstahl", "deckung", "dim")},
                 markierbar=p["achse"] is not None, stabliste=p.get("stabliste")) for p in PLAENE]
