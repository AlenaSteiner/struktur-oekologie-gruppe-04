# -*- coding: utf-8 -*-
"""
Modell lesen: Staebe aus dem Rhino-Export von RFEM (Pavillon Stockerau).

Liest mit rhino3dm die Layer "...::MemberAxes::<Querschnitt>". Jede Achse ist
eine gerade Linie = ein Stab. Der Querschnitt steht im Layernamen, bei
veraenderlichem Querschnitt der Endquerschnitt im User-Text
(BG_RFEM_Exchange_CrosSec_E). Das Modell ist in Metern, Querschnittsnamen in mm.

Verwendung:
    from modell import lese_staebe
    staebe = lese_staebe()
"""
import math
import re
from dataclasses import dataclass
from pathlib import Path

import rhino3dm

STANDARD_PFAD = Path(__file__).resolve().parent / "rhino" / "Stockerau Rhino Export from RFEM.3dm"

KEY_ID = "BG_RFEM_Exchange_BeamId_bg0246"
KEY_TYP = "BG_RFEM_Exchange_Type_bg0247"
KEY_QS_START = "BG_RFEM_Exchange_CrosSec_S_bg0252"
KEY_QS_ENDE = "BG_RFEM_Exchange_CrosSec_E_bg0251"
KEY_MATERIAL = "BG_Dlubal-Name (Material)_bg0211"

ZAHL = r"(\d+(?:\.\d+)?)"


@dataclass
class Stab:
    beam_id: str          # RFEM-Stabnummer
    profil: str           # Layername = Querschnitt am Anfang, z. B. "Flat Bar 275/12"
    profil_ende: str      # Querschnitt am Ende ("-" = konstant)
    typ: str              # Beam / Tension
    laenge_m: float
    flaeche_start_m2: float
    flaeche_ende_m2: float
    volumen_m3: float
    modell_material: str  # Material aus dem User-Text ("" = nicht gesetzt)
    rhino_id: str
    start: tuple = (0.0, 0.0, 0.0)   # Achse Anfang (x, y, z) in m
    ende: tuple = (0.0, 0.0, 0.0)    # Achse Ende (x, y, z) in m


def flaeche_m2(querschnitt):
    """Querschnittsflaeche in m2 aus dem Querschnittsnamen (Masse in mm)."""
    if querschnitt.startswith(("Flat Bar", "Rectangle")):
        a, b = re.findall(ZAHL + "/" + ZAHL, querschnitt)[0]
        return float(a) * float(b) * 1e-6
    if querschnitt.startswith("RD"):
        d = float(querschnitt.split()[1])
        return math.pi / 4 * d * d * 1e-6
    if querschnitt.startswith("RO"):
        d, t = (float(x) for x in re.findall(ZAHL + "x" + ZAHL, querschnitt)[0])
        return math.pi / 4 * (d * d - (d - 2 * t) ** 2) * 1e-6
    raise ValueError("Unbekannter Querschnitt: " + querschnitt)


def umfang_m(querschnitt):
    """Aeusserer Umfang des Querschnitts in m (Masse in mm). Fuer die Mantelflaeche."""
    if querschnitt.startswith(("Flat Bar", "Rectangle")):
        a, b = re.findall(ZAHL + "/" + ZAHL, querschnitt)[0]
        return 2.0 * (float(a) + float(b)) * 1e-3
    if querschnitt.startswith("RD"):
        return math.pi * float(querschnitt.split()[1]) * 1e-3
    if querschnitt.startswith("RO"):
        d = float(re.findall(ZAHL + "x" + ZAHL, querschnitt)[0][0])
        return math.pi * d * 1e-3
    raise ValueError("Unbekannter Querschnitt: " + querschnitt)


def lese_staebe(pfad=STANDARD_PFAD):
    """Alle Staebe (Layer ...::MemberAxes::...) als Liste von Stab."""
    modell = rhino3dm.File3dm.Read(str(pfad))
    if modell is None:
        raise FileNotFoundError("Rhino-Datei nicht lesbar: " + str(pfad))
    if modell.Settings.ModelUnitSystem != rhino3dm.UnitSystem.Meters:
        raise ValueError("Modell ist nicht in Metern: " + str(modell.Settings.ModelUnitSystem))

    staebe = []
    for obj in modell.Objects:
        layer = modell.Layers[obj.Attributes.LayerIndex].FullPath
        if "::MemberAxes::" not in layer:
            continue
        kurve = obj.Geometry
        if not isinstance(kurve, rhino3dm.LineCurve):
            raise ValueError("Stab ist keine gerade Linie: " + layer)
        us = dict(obj.Attributes.GetUserStrings())
        profil = layer.split("::")[-1]
        profil_ende = us[KEY_QS_ENDE]
        a_start = flaeche_m2(profil)
        a_ende = flaeche_m2(profil_ende) if profil_ende != "-" else a_start
        p0, p1 = kurve.PointAtStart, kurve.PointAtEnd
        laenge = math.sqrt((p1.X - p0.X) ** 2 + (p1.Y - p0.Y) ** 2 + (p1.Z - p0.Z) ** 2)
        staebe.append(Stab(
            beam_id=us[KEY_ID],
            profil=profil,
            profil_ende=profil_ende,
            typ=us[KEY_TYP],
            laenge_m=laenge,
            flaeche_start_m2=a_start,
            flaeche_ende_m2=a_ende,
            # Fuer Flachstaebe ist die Flaeche linear ueber die Laenge, das Mittel ist exakt.
            volumen_m3=laenge * (a_start + a_ende) / 2.0,
            modell_material=us[KEY_MATERIAL].strip(),
            rhino_id=str(obj.Attributes.Id),
            start=(p0.X, p0.Y, p0.Z),
            ende=(p1.X, p1.Y, p1.Z),
        ))
    return staebe


def kleinste_abmessung_mm(querschnitt):
    """Kleinste Querschnittsabmessung in mm (fuer Plausibilitaetspruefung der Materialwahl)."""
    if querschnitt.startswith(("Flat Bar", "Rectangle")):
        a, b = re.findall(ZAHL + "/" + ZAHL, querschnitt)[0]
        return min(float(a), float(b))
    if querschnitt.startswith("RD"):
        return float(querschnitt.split()[1])
    if querschnitt.startswith("RO"):                 # Hohlprofil: massgebend ist die Wandstaerke
        return float(re.findall(ZAHL + "x" + ZAHL, querschnitt)[0][1])
    raise ValueError("Unbekannter Querschnitt: " + querschnitt)


def lese_geometrie(pfad=STANDARD_PFAD):
    """Volumenkoerper der Layer ...::Members::... als Dreiecksnetz.

    Rueckgabe: {beam_id: (vertices[(x, y, z)], dreiecke[(i, j, k)])}.
    Stab ohne Koerper (RD 12) kommt nicht vor.
    """
    modell = rhino3dm.File3dm.Read(str(pfad))
    if modell is None:
        raise FileNotFoundError("Rhino-Datei nicht lesbar: " + str(pfad))
    ergebnis = {}
    for obj in modell.Objects:
        layer = modell.Layers[obj.Attributes.LayerIndex].FullPath
        if "::Members::" not in layer:
            continue
        beam_id = dict(obj.Attributes.GetUserStrings())[KEY_ID]
        brep = obj.Geometry
        verts, tris = [], []
        for fi in range(len(brep.Faces)):
            netz = brep.Faces[fi].GetMesh(rhino3dm.MeshType.Any)
            if netz is None:
                continue
            offset = len(verts)
            verts.extend((v.X, v.Y, v.Z) for v in netz.Vertices)
            for i in range(len(netz.Faces)):
                f = netz.Faces[i]
                tris.append((offset + f[0], offset + f[1], offset + f[2]))
                if f[2] != f[3]:
                    tris.append((offset + f[0], offset + f[2], offset + f[3]))
        ergebnis[beam_id] = (verts, tris)
    return ergebnis


if __name__ == "__main__":
    liste = lese_staebe()
    print("Staebe:", len(liste))
    print("Laenge gesamt: %.2f m" % sum(s.laenge_m for s in liste))
    print("Volumen gesamt: %.4f m3" % sum(s.volumen_m3 for s in liste))
