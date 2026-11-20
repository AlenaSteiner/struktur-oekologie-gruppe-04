# -*- coding: utf-8 -*-
"""
Embodied Carbon je Stab (GWP-total, kg CO2e je Lebenszyklus-Modul), live aus der OEKOBAUDAT.

Zuordnung (Vorgabe der Aufgabe):
    Flat Bar, RO (Rohr), RD (Zugstab)  -> Baustahl   (Menge = Volumen * Rohdichte aus dem Datensatz, kg)
    Rectangle 500/500 (Fundamente)     -> Beton C25/30 (Menge = Volumen, m3)
                                          + Betonstahl: pauschal 85 kg je m3 Beton
Das Material im Rhino-Modell (User-Text) wird NICHT verwendet: dort steht nur bei zwei
Layern etwas, und bei "Flat Bar 162.5/20" ist "Concrete C25/30" offensichtlich falsch.

Aufruf (im Repo-Ordner):
    python berechnung.py                          Standard-Datensaetze
    python berechnung.py --stahl alternative      Baustahl: Grobblech
    python berechnung.py --beton alternative      Beton: EcoPact (Hersteller)
    python berechnung.py --stab 679               Rechenweg fuer einen Stab (RFEM-Nummer)
"""
import argparse
from collections import OrderedDict
from dataclasses import dataclass

from modell import Stab, lese_staebe
from oekobaudat import DATENSAETZE, MODUL_REIHENFOLGE, lade_datensatz

BEWEHRUNG_KG_PRO_M3 = 85.0   # Betonstahl je m3 Beton (Vorgabe, pauschal)


def materialgruppe(profil):
    if profil.startswith("Rectangle"):
        return "beton"
    if profil.startswith(("Flat Bar", "RO", "RD")):
        return "baustahl"
    raise ValueError("Keine Materialgruppe fuer Querschnitt: " + profil)


@dataclass
class StabErgebnis:
    stab: Stab
    gruppe: str            # baustahl / beton
    menge: float           # kg (Baustahl) bzw. m3 (Beton)
    einheit: str
    bewehrung_kg: float    # nur bei Beton, sonst 0
    gwp: dict              # Modul -> kg CO2e des Stabes (ohne Bewehrung)
    gwp_bewehrung: dict    # Modul -> kg CO2e der Bewehrung

    def gesamt(self, modul):
        return self.gwp.get(modul, 0.0) + self.gwp_bewehrung.get(modul, 0.0)


def lade_datensaetze(stahl="standard", beton="standard"):
    """Gruppe -> Datensatz. Der Betonstahl hat nur den Standard-Datensatz."""
    wahl = {"baustahl": stahl, "beton": beton, "betonstahl": "standard"}
    return {g: lade_datensatz(DATENSAETZE[g][v]) for g, v in wahl.items()}


def _je_modul(datensatz, menge):
    return {m: w * menge for m, w in datensatz.gwp.items()}


def berechne_stab(stab, ds):
    gruppe = materialgruppe(stab.profil)
    if gruppe == "baustahl":
        d = ds["baustahl"]
        menge, einheit = stab.volumen_m3 * d.dichte_kg_m3, "kg"
        return StabErgebnis(stab, gruppe, menge, einheit, 0.0, _je_modul(d, menge), {})
    bewehrung = stab.volumen_m3 * BEWEHRUNG_KG_PRO_M3
    return StabErgebnis(stab, gruppe, stab.volumen_m3, "m3", bewehrung,
                        _je_modul(ds["beton"], stab.volumen_m3),
                        _je_modul(ds["betonstahl"], bewehrung))


def berechne(staebe, ds):
    return [berechne_stab(s, ds) for s in staebe]


def module_von(ds):
    alle = set()
    for d in ds.values():
        alle.update(d.gwp)
    return [m for m in MODUL_REIHENFOLGE if m in alle]


def summen_je_profil(ergebnisse, module):
    """Profil -> {anzahl, laenge, volumen, menge, einheit, gwp{modul}} (inkl. Bewehrung)."""
    summen = OrderedDict()
    for e in ergebnisse:
        s = summen.setdefault(e.stab.profil, {"anzahl": 0, "laenge": 0.0, "volumen": 0.0,
                                              "menge": 0.0, "einheit": e.einheit,
                                              "gwp": {m: 0.0 for m in module}})
        s["anzahl"] += 1
        s["laenge"] += e.stab.laenge_m
        s["volumen"] += e.stab.volumen_m3
        s["menge"] += e.menge
        for m in module:
            s["gwp"][m] += e.gesamt(m)
    return summen


def f(zahl, stellen=1):
    return ("{:,.%df}" % stellen).format(zahl).replace(",", " ")


def drucke_quellen(ds):
    print("Datensaetze (live aus der OEKOBAUDAT, GWP-total):")
    for gruppe, d in ds.items():
        print("  %-10s %s" % (gruppe, d.name))
        print("             %s  | je %g %s | Rohdichte %s" % (
            d.url, d.bezugsmenge, d.einheit, ("%g kg/m3" % d.dichte_kg_m3) if d.dichte_kg_m3 else "-"))
        for h in d.hinweise:
            print("             Hinweis: " + h)
        if d.luecken:
            print("             ohne Wert (als 0 gezaehlt): " + ", ".join(d.luecken))
        fehlt = [m for m in module_von(ds) if m not in d.gwp and m not in d.luecken]
        if fehlt:
            print("             nicht deklariert (0 in der Tabelle): " + ", ".join(fehlt))


def drucke_je_profil(ergebnisse, module):
    summen = summen_je_profil(ergebnisse, module)
    kopf = "%-32s %5s %9s %10s %11s" % ("Querschnitt", "Anz.", "Laenge m", "Volumen m3", "Menge")
    kopf += "".join(" %9s" % m for m in module) + " %10s" % "alle Mod."
    print()
    print("kg CO2e je Querschnitt (Beton inkl. Bewehrung):")
    print(kopf)
    print("-" * len(kopf))
    gesamt = {m: 0.0 for m in module}
    for profil, s in summen.items():
        menge = "%s %s" % (f(s["menge"], 0 if s["einheit"] == "kg" else 2), s["einheit"])
        zeile = "%-32s %5d %9s %10s %11s" % (profil[:32], s["anzahl"], f(s["laenge"], 1),
                                            f(s["volumen"], 4), menge)
        zeile += "".join(" %9s" % f(s["gwp"][m], 1) for m in module)
        zeile += " %10s" % f(sum(s["gwp"].values()), 1)
        print(zeile)
        for m in module:
            gesamt[m] += s["gwp"][m]
    print("-" * len(kopf))
    print("%-32s %5d %9s %10s %11s" % ("SUMME", len(ergebnisse),
          f(sum(e.stab.laenge_m for e in ergebnisse), 1),
          f(sum(e.stab.volumen_m3 for e in ergebnisse), 4), "")
          + "".join(" %9s" % f(gesamt[m], 1) for m in module) + " %10s" % f(sum(gesamt.values()), 1))
    return gesamt


def drucke_rechenweg(ergebnis, ds, module):
    s = ergebnis.stab
    d = ds[ergebnis.gruppe]
    print()
    print("Rechenweg Stab %s (%s, Typ %s):" % (s.beam_id, s.profil, s.typ))
    print("  Laenge            %.4f m" % s.laenge_m)
    print("  Querschnitt       %.3f cm2 (Anfang) / %.3f cm2 (Ende)" % (
        s.flaeche_start_m2 * 1e4, s.flaeche_ende_m2 * 1e4))
    print("  Volumen           %.6f m3 = Laenge * (A_start + A_ende) / 2" % s.volumen_m3)
    if ergebnis.gruppe == "baustahl":
        print("  Masse             %.3f kg = Volumen * %g kg/m3" % (ergebnis.menge, d.dichte_kg_m3))
    else:
        print("  Beton             %.6f m3" % ergebnis.menge)
        print("  Bewehrung         %.3f kg = %.6f m3 * %g kg/m3" % (
            ergebnis.bewehrung_kg, s.volumen_m3, BEWEHRUNG_KG_PRO_M3))
    for m in module:
        faktor = d.gwp.get(m, 0.0)
        zeile = "  %-6s %12.6f kg CO2e = %.6f kg CO2e/%s * %.6f %s" % (
            m, ergebnis.gwp.get(m, 0.0), faktor, d.einheit, ergebnis.menge, ergebnis.einheit)
        if ergebnis.gruppe == "beton":
            zeile += "  + Bewehrung %.6f = %.6f" % (ergebnis.gwp_bewehrung.get(m, 0.0), ergebnis.gesamt(m))
        print(zeile)


def main():
    parser = argparse.ArgumentParser(description="Embodied Carbon je Stab aus der OEKOBAUDAT")
    parser.add_argument("--stahl", choices=["standard", "alternative"], default="standard")
    parser.add_argument("--beton", choices=["standard", "alternative"], default="standard")
    parser.add_argument("--stab", help="RFEM-Stabnummer (BeamId) fuer den Rechenweg")
    args = parser.parse_args()

    staebe = lese_staebe()
    ds = lade_datensaetze(args.stahl, args.beton)
    module = module_von(ds)
    ergebnisse = berechne(staebe, ds)

    print("Pavillon Stockerau: %d Staebe, Variante Stahl=%s, Beton=%s, Bewehrung %g kg/m3 Beton\n" % (
        len(staebe), args.stahl, args.beton, BEWEHRUNG_KG_PRO_M3))
    drucke_quellen(ds)
    drucke_je_profil(ergebnisse, module)
    if args.stab:
        treffer = [e for e in ergebnisse if e.stab.beam_id == args.stab]
        if not treffer:
            raise SystemExit("Stab %s nicht gefunden" % args.stab)
        drucke_rechenweg(treffer[0], ds, module)


if __name__ == "__main__":
    main()

