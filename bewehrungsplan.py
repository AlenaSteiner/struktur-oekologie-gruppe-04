# -*- coding: utf-8 -*-
"""
Bewehrungsplan der Streifenfundamente (Bollinger+Grohmann, Plan BG_5_BP_FU_XX_001_P-01, Stand 05.2026).

Enthaelt:
  * die Stabliste (Biegeformen) des Plans, abgeschrieben aus dem PDF und gegengerechnet,
  * die Zuordnung Rhino-Modell -> Planausschnitt (damit der angeklickte Fundamentstab im Plan
    markiert werden kann) und
  * das Planbild als PNG (aus dem PDF gerendert).

Die Zuordnung stammt aus den Achsbeschriftungen im PDF (Plan M 1:25, 1 m = 113,386 pt):
  Achse D = Modell x = 10 m  (Achse F = x = 13 m)
  Achse 7 = Modell y = 0 m   (Achse 5 = y = -5 m, Achse 3 = y = -10 m)
Die Masse steht im Plan nur gesamt, nicht je Streifen.
"""
from pathlib import Path

import pymupdf

PLAN_NUMMER = "BG_5_BP_FU_XX_001_P-01"
PLAN_PDF = Path(__file__).resolve().parent / "plaene" / (PLAN_NUMMER + ".pdf")

BETON = "C25/30"
BETONSTAHL = "B550B"
DECKUNG_CM = 4.0

# Pos., Stueck, Durchmesser mm, Einzellaenge m, Gesamtlaenge m, Masse kg (Stabliste im Plan)
STABLISTE = [
    {"pos": 1, "stueck": 341, "durchmesser": 10, "einzel": 1.98, "gesamt": 675.18, "masse": 416.59},
    {"pos": 2, "stueck": 60, "durchmesser": 12, "einzel": 5.55, "gesamt": 333.00, "masse": 295.70},
    {"pos": 3, "stueck": 40, "durchmesser": 12, "einzel": 2.39, "gesamt": 95.60, "masse": 84.89},
    {"pos": 4, "stueck": 60, "durchmesser": 12, "einzel": 4.10, "gesamt": 246.00, "masse": 218.45},
]
SUMME_KG = 1015.63            # "Gesamtmasse" laut Plan

# Zuordnung Modell -> PDF (Punkte, Ursprung oben links)
ACHSE_D_X = 742.7             # Achse D (Modell x = 10)
ACHSE_7_Y = 461.7             # Achse 7 (Modell y = 0)
MODELL_X_D = 10.0
PT_PRO_M = 1000.0 / 25.0 / 25.4 * 72.0     # 1 m im Massstab 1:25 in PDF-Punkten
HALBE_BREITE_M = 0.25                      # Streifen 50 cm breit

CROP = (150.0, 60.0, 1700.0, 1800.0)       # Planausschnitt (x0, y0, x1, y1) in pt
ZOOM = 1.0


def _pruefe():
    for z in STABLISTE:
        assert abs(z["stueck"] * z["einzel"] - z["gesamt"]) < 0.02, "Stabliste Pos. %d: Laenge" % z["pos"]
    assert abs(sum(z["masse"] for z in STABLISTE) - SUMME_KG) < 0.01, "Stabliste: Summe der Massen"


_pruefe()


def lage(start, ende):
    """Rechteck des Fundamentstabes im Planausschnitt als Anteile [x0, y0, x1, y1] (0..1)."""
    xs = [ACHSE_D_X + (p[0] - MODELL_X_D) * PT_PRO_M for p in (start, ende)]
    ys = [ACHSE_7_Y - p[1] * PT_PRO_M for p in (start, ende)]
    h = HALBE_BREITE_M * PT_PRO_M
    x0, x1 = min(xs) - h, max(xs) + h
    y0, y1 = min(ys) - h, max(ys) + h
    # Staebe sind 1 m lang in Achsrichtung: quer dazu +-h, in Achsrichtung nur die Achslaenge
    if abs(xs[1] - xs[0]) >= abs(ys[1] - ys[0]):
        x0, x1 = min(xs), max(xs)
    else:
        y0, y1 = min(ys), max(ys)
    b, h_ = CROP[2] - CROP[0], CROP[3] - CROP[1]
    return [round((x0 - CROP[0]) / b, 5), round((y0 - CROP[1]) / h_, 5),
            round((x1 - CROP[0]) / b, 5), round((y1 - CROP[1]) / h_, 5)]


def bildgroesse():
    return int((CROP[2] - CROP[0]) * ZOOM), int((CROP[3] - CROP[1]) * ZOOM)


_bild = None


def bild_png():
    """Planausschnitt als PNG (einmal gerendert, dann im Speicher)."""
    global _bild
    if _bild is None:
        seite = pymupdf.open(str(PLAN_PDF))[0]
        pix = seite.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), clip=pymupdf.Rect(*CROP), alpha=False)
        _bild = pix.tobytes("png")
    return _bild
