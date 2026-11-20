# -*- coding: utf-8 -*-
"""
Stabliste Pavillon Stockerau  (Etappe 1-3: Modell lesen, Querschnitt, Material)

Fuer eine GhPython-Komponente (Rhino 7) bzw. "Python 3 Script"-Komponente
(Rhino 8) in Grasshopper. Liest die Staebe direkt aus dem aktiven Rhino-Dokument
(dort stehen Layer, Name und User-Text mit dem Material).

EINGAENGE (Rechtsklick auf Eingang -> Name aendern, Type Hint setzen)
    run             bool   Toggle/Button. True = einlesen.
    layer_filter    str    optional. Nur Layer, deren Name diesen Text enthaelt
                           (ohne Gross/Klein). Leer = alle Layer.
    include_hidden  bool   optional. Versteckte Objekte mitzaehlen (Standard False).

AUSGAENGE
    count       int    Anzahl Staebe
    ids         list   Rhino-Objekt-IDs (str)
    names       list   Objektname (leer = "")
    layers      list   Layername
    types       list   Curve / Extrusion / Brep
    lengths     list   Stablaenge in m
    volumes     list   Volumen in m3 (None bei Kurven / offenen Koerpern)
    areas       list   mittlere Querschnittsflaeche in cm2 (= Volumen / Laenge)
    materials   list   Material
    mat_source  list   Woher das Material kommt: usertext / material / layer / fehlt
    geo         list   Geometrie (zum Anzeigen/Weiterrechnen in GH)
    report      list   Textzeilen, an ein Panel haengen

HINWEISE
    * Laenge bei Kurve: Kurvenlaenge. Bei Extrusion: Pfadlaenge.
      Bei Brep: laengste Kante (Naeherung, bitte stichprobenartig pruefen!).
    * Die mittlere Flaeche ist bei Staeben mit veraenderlichem Querschnitt nur ein
      Mittelwert. Fuer Etappe 2 den Stab in Abschnitte teilen und einzeln rechnen.
    * Es werden nur Kurven, Extrusionen und Breps gezaehlt. Texte, Bemassungen,
      Punkte, Meshes usw. werden ignoriert.
"""

import Rhino
import Rhino.Geometry as rg
import Rhino.DocObjects as rdo

# Keys im User-Text, in denen das Material stehen kann (Gross/Klein egal)
MATERIAL_KEYS = ["material", "werkstoff", "baustoff", "materialname", "mat"]


def _inp(name, default):
    """Eingabe lesen. Fehlt der Eingang oder ist er leer, gilt der Standardwert."""
    value = globals().get(name, None)
    if value is None:
        return default
    return value


def _unit_scale_to_m(doc):
    return Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Meters)


def _user_strings(attr):
    """User-Text als dict {key_lower: value}."""
    result = {}
    coll = attr.GetUserStrings()
    if coll is None:
        return result
    for key in coll.AllKeys:
        result[str(key).lower()] = coll[key]
    return result


def _material(rh_obj, layer_name):
    """Gibt (material, quelle) zurueck."""
    # 1. User-Text
    ustr = _user_strings(rh_obj.Attributes)
    for key in MATERIAL_KEYS:
        if key in ustr and str(ustr[key]).strip() != "":
            return str(ustr[key]).strip(), "usertext"

    # 2. Rhino-Material (Objekt oder Layer)
    try:
        rmat = rh_obj.GetMaterial(True)
        if rmat is not None and rmat.Name:
            return str(rmat.Name), "material"
    except Exception:
        pass

    # 3. Layername als Hinweis
    if layer_name:
        return layer_name, "layer"

    return "", "fehlt"
