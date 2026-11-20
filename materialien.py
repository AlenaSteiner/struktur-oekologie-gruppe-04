# -*- coding: utf-8 -*-
"""
Materialkatalog fuer die Web-App: Zuordnung zu OEKOBAUDAT-Datensaetzen und
Waermeeigenschaften fuer die Sonnen-Simulation.

WICHTIG: Die Waermewerte (Absorption, Emission, Dichte, Waermekapazitaet,
Waermeleitfaehigkeit) sind typische Literaturwerte, die ich als Annahme gesetzt habe.
Sie stammen NICHT aus dem Modell oder der OEKOBAUDAT. Absorption und Emission haengen
stark von Farbe und Oberflaeche ab. Zum Aendern einfach hier die Zahlen anpassen.
"""
from modell import kleinste_abmessung_mm

# id -> Eigenschaften
MATERIALIEN = {
    "stahl": {
        "name": "Stahl (Baustahl)",
        "gruppe": "baustahl",          # Schluessel in oekobaudat.DATENSAETZE
        "dichte": 7850.0,              # kg/m3
        "cp": 470.0,                   # J/(kg K)
        "k": 50.0,                     # W/(m K)
        "alpha": 0.70,                 # Absorptionsgrad Solarstrahlung (Walzhaut, leicht korrodiert)
        "eps": 0.80,                   # Emissionsgrad langwellig
        "hinweis": "Absorption/Emission fuer unbehandelte, leicht korrodierte Oberflaeche. "
                   "Verzinkt oder hell lackiert waere die Absorption deutlich niedriger.",
    },
    "beton": {
        "name": "Stahlbeton C25/30",
        "gruppe": "beton",
        "dichte": 2400.0,
        "cp": 880.0,
        "k": 2.0,
        "alpha": 0.65,                 # graue, bewitterte Betonoberflaeche
        "eps": 0.90,
        "bewehrung": True,             # + 85 kg Betonstahl je m3 (Vorgabe)
        "hinweis": "Beton inklusive pauschaler Bewehrung (85 kg/m3).",
    },
    "aluminium": {
        "name": "Aluminium",
        "gruppe": "aluminium",
        "dichte": 2700.0,
        "cp": 900.0,
        "k": 200.0,
        "alpha": 0.25,                 # walzblank / leicht oxidiert
        "eps": 0.15,
        "hinweis": "Eigene Auswahl (nicht Teil der Aufgabe). Walzblank: wenig Absorption, aber "
                   "auch kaum Abstrahlung.",
    },
    "holz": {
        "name": "Brettschichtholz",
        "gruppe": "holz",
        "dichte": 470.0,
        "cp": 1600.0,
        "k": 0.13,                     # quer zur Faser
        "alpha": 0.60,                 # naturbelassen, leicht vergraut
        "eps": 0.90,
        "hinweis": "Eigene Auswahl (nicht Teil der Aufgabe). A1-A3 ist negativ (biogener "
                   "Kohlenstoff), dafuer ist C3 positiv.",
    },
}

# Welche Datensatz-Varianten je Gruppe zur Auswahl stehen
VARIANTEN = {"baustahl": ["standard", "alternative"], "beton": ["standard", "alternative"]}

# Gruppen fuer die Bedienung (Querschnitte gleicher Art zusammen umschalten)
UI_GRUPPEN = [
    ("flachstahl", "Flachstähle (Flat Bar)", lambda p: p.startswith("Flat Bar")),
    ("zugstab", "Zugstäbe (RD 12)", lambda p: p.startswith("RD")),
    ("rohr", "Rohre (RO 139.7x8.0)", lambda p: p.startswith("RO")),
    ("fundament", "Fundamente (Rectangle 500/500)", lambda p: p.startswith("Rectangle")),
]


def ui_gruppe(profil):
    for gid, _name, test in UI_GRUPPEN:
        if test(profil):
            return gid
    raise ValueError("Keine Gruppe fuer " + profil)


def standard_material(profil):
    """Zuordnung der Aufgabe: Rectangle = Beton (Fundamente), alles andere Baustahl."""
    return "beton" if profil.startswith("Rectangle") else "stahl"


def gruppen_warnung(profile, material_id):
    """Warntext, wenn die Materialwahl fuer die Querschnitte einer Gruppe unrealistisch ist, sonst ''.

    Es ist KEINE statische Pruefung. Der Querschnitt bleibt beim Wechsel unveraendert, die
    Tragfaehigkeit aendert sich dabei aber stark. Bewertet wird die kleinste Abmessung der Gruppe.
    """
    d = min(kleinste_abmessung_mm(p) for p in profile)
    if material_id == "beton" and d < 100.0:
        return ("Beton mit nur %g mm kleinster Abmessung ist nicht herstellbar (Mindestmass ca. 100 mm). "
                "Der CO2-Wert gilt nur rechnerisch." % d)
    if material_id == "holz" and d < 40.0:
        return ("Brettschichtholz mit nur %g mm kleinster Abmessung ist nicht sinnvoll "
                "(unter ca. 40 mm). Der CO2-Wert gilt nur rechnerisch." % d)
    if material_id != "stahl" and any(p.startswith("RD") for p in profile):
        return ("RD 12 ist als Zugstab ausgelegt. Ein anderes Material mit gleichem Querschnitt "
                "kann das nicht tragen. Der CO2-Wert gilt nur rechnerisch.")
    return ""
