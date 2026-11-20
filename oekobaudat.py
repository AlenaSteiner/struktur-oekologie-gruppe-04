# -*- coding: utf-8 -*-
"""
OEKOBAUDAT: Datensaetze live abrufen und GWP-total je Lebenszyklus-Modul lesen.

Schnittstelle (offen, ohne Konto):
    https://oekobaudat.de/OEKOBAU.DAT/resource/processes/<UUID>?format=json&view=extended

Besonderheiten der Datensaetze (alle in der Antwort geprueft):
    * Bezugseinheit ist je Datensatz verschieden: Baustahl-EPD gilt je 1000 kg,
      Betonstahl je 1 kg, Beton je 1 m3. Der Wert wird deshalb durch die
      Bezugsmenge geteilt -> kg CO2e je kg bzw. je m3.
    * Module mit mehreren Szenarien (Baustahl C3, C4, D: S1/S2/S3): es gilt das
      Szenario, das der Datensatz selbst als "default" markiert (Baustahl: S3,
      Europaeischer Durchschnitt).
    * Betonstahl hat kein A1-A3, sondern A1, A2, A3 einzeln -> werden addiert.
    * Fehlt ein Wert (z. B. Beton C25/30, C4), steht das Modul in `luecken`
      und wird bei der Rechnung als 0 gezaehlt.

Verwendung:
    from oekobaudat import lade_datensatz
    ds = lade_datensatz("20c29cbd-f9a2-4518-a1ce-c681246c29c8")
    ds.gwp["A1-A3"]    # kg CO2e je kg
"""
from dataclasses import dataclass, field

import httpx

BASE_URL = "https://oekobaudat.de/OEKOBAU.DAT/resource/processes/{uuid}"
PARAMETER = {"format": "json", "view": "extended"}

# Indikator "GWP-total" (Global Warming Potential total)
GWP_TOTAL_UUID = "6a37f984-a4b3-458a-a20a-64418c145fa2"

MODUL_REIHENFOLGE = ["A1-A3", "A4", "A5", "B1", "B2", "B3", "B4", "B5", "B6", "B7",
                     "C1", "C2", "C3", "C4", "D"]

# Datensaetze der Aufgabe: Materialgruppe -> {Variante: UUID}
DATENSAETZE = {
    "baustahl": {   # Flachstaehle, Rohre, Zugstaebe
        "standard": "20c29cbd-f9a2-4518-a1ce-c681246c29c8",     # Baustahl: Profile und Stabstahl
        "alternative": "04d1311a-ae38-4bfb-8e11-8992f1ddb14f",  # Baustahl: Grobblech
    },
    "beton": {      # Fundamente
        "standard": "8347f9a7-f4ec-4a36-a266-a0281f5fd16d",     # Beton C25/30
        "alternative": "69dc12cf-ce4d-4251-8ea3-330ed72f2f79",  # Beton C25/30 EcoPact (Hersteller)
    },
    "betonstahl": {  # Bewehrung der Fundamente
        "standard": "a8ebf8f2-2fcc-4431-b730-93bf5efd8111",     # Betonstahl in Staeben
    },
    # Zusaetzlich fuer den Materialwechsel in der Web-App (NICHT Teil der Vorgabe, eigene
    # Auswahl, beide live abgerufen und auf GWP-total geprueft):
    "aluminium": {
        "standard": "c5982fc9-a486-4f00-82a2-59985d8ab196",     # Aluminium profiles (RER, 2024-2029)
    },
    "holz": {
        "standard": "efa55966-4f29-4f15-bfec-8c08b3945923",     # Brettschichtholz (Update) (RER, 2023-2028)
    },
    # Nur fuer Bauteil6 (Mauerwerk). Die Ziegel-Datensaetze der OEKOBAUDAT hatten keinen auswertbaren GWP-total
    # (Szenarien ohne default bzw. Indikator fehlt), deshalb steht Kalksandstein stellvertretend fuer Mauerwerk.
    "mauerwerk": {
        "standard": "722467a6-68cb-4676-bf9f-c6ea1d36594f",     # Kalksandstein (DE, 2022, Sphera, generic)
    },
}


class OekobaudatFehler(RuntimeError):
    """Abruf oder Auswertung eines Datensatzes ist fehlgeschlagen."""


@dataclass
class Datensatz:
    uuid: str
    name: str
    einheit: str                 # Bezugseinheit: "kg" oder "m3"
    bezugsmenge: float           # Menge, auf die sich die Rohwerte beziehen (z. B. 1000 kg)
    dichte_kg_m3: float          # Rohdichte aus dem Datensatz (None, falls nicht angegeben)
    gwp: dict                    # Modul -> kg CO2e je 1 kg bzw. je 1 m3
    szenarien: dict              # Modul -> verwendetes Szenario (None = ohne Szenario)
    luecken: list = field(default_factory=list)    # Module ohne Wert im Datensatz
    hinweise: list = field(default_factory=list)
    url: str = ""


def hole_json(uuid, timeout=60.0):
    """Datensatz live von der OEKOBAUDAT holen."""
    url = BASE_URL.format(uuid=uuid)
    try:
        antwort = httpx.get(url, params=PARAMETER, timeout=timeout, follow_redirects=True)
        antwort.raise_for_status()
        return antwort.json()
    except (httpx.HTTPError, ValueError) as fehler:
        raise OekobaudatFehler("Abruf von %s fehlgeschlagen: %s" % (url, fehler)) from fehler


def _text(liste, sprache="de"):
    if isinstance(liste, str):
        return liste
    for eintrag in liste or []:
        if eintrag.get("lang") == sprache:
            return eintrag.get("value", "")
    return liste[0].get("value", "") if liste else ""


def _bezug(d):
    """(Einheit, Bezugsmenge, Rohdichte) aus dem Referenzfluss."""
    for ex in d["exchanges"]["exchange"]:
        if not ex.get("referenceFlow"):
            continue
        dichte = None
        for mp in ex.get("materialProperties", []):
            if mp.get("name") == "gross density":
                dichte = float(mp["value"])
        for fp in ex.get("flowProperties", []):
            if fp.get("referenceFlowProperty"):
                einheit = fp["referenceUnit"]
                if einheit not in ("kg", "m3"):
                    raise OekobaudatFehler("Unerwartete Bezugseinheit: " + str(einheit))
                return einheit, float(fp["meanValue"]) * float(ex.get("meanAmount", 1.0)), dichte
    raise OekobaudatFehler("Kein Referenzfluss im Datensatz")


def _standard_szenario(d):
    """Name des Szenarios, das der Datensatz als default markiert (oder None)."""
    other = d["processInformation"]["dataSetInformation"].get("other") or {}
    for eintrag in other.get("anies", []):
        szenarien = eintrag.get("scenario")
        if isinstance(szenarien, list):
            for sz in szenarien:
                if sz.get("default"):
                    return sz.get("name")
    return None


def _gwp_total_eintraege(d):
    """Liste (Modul, Szenario, Wert) des Indikators GWP-total."""
    for ergebnis in d["LCIAResults"]["LCIAResult"]:
        if ergebnis["referenceToLCIAMethodDataSet"].get("refObjectId") != GWP_TOTAL_UUID:
            continue
        eintraege = []
        einheit = ""
        for a in ergebnis["other"]["anies"]:
            if a.get("name") == "referenceToUnitGroupDataSet":
                einheit = _text(a["value"]["shortDescription"], "en")
            elif "module" in a:
                wert = a.get("value")
                eintraege.append((a["module"], a.get("scenario"), None if wert is None else float(wert)))
        if "CO" not in einheit:
            raise OekobaudatFehler("GWP-total hat keine CO2-Einheit: " + einheit)
        return eintraege
    raise OekobaudatFehler("Indikator GWP-total nicht im Datensatz")


def parse_datensatz(uuid, d):
    """JSON eines Datensatzes -> Datensatz (GWP-total je Modul, je Bezugseinheit)."""
    einheit, bezugsmenge, dichte = _bezug(d)
    standard = _standard_szenario(d)
    name = _text(d["processInformation"]["dataSetInformation"]["name"].get("baseName"), "de")

    je_modul = {}
    for modul, szenario, wert in _gwp_total_eintraege(d):
        je_modul.setdefault(modul, []).append((szenario, wert))

    gwp, szenarien, luecken, hinweise = {}, {}, [], []
    for modul, eintraege in je_modul.items():
        if len(eintraege) == 1:
            szenario, wert = eintraege[0]
        else:
            treffer = [e for e in eintraege if e[0] == standard]
            if not treffer:
                raise OekobaudatFehler("Modul %s hat mehrere Szenarien, aber kein default" % modul)
            szenario, wert = treffer[0]
            hinweise.append("%s: Szenario %s (default) von %s" % (
                modul, szenario, ", ".join(str(e[0]) for e in eintraege)))
        if wert is None:
            luecken.append(modul)
            continue
        gwp[modul] = wert / bezugsmenge
        szenarien[modul] = szenario

    # Betonstahl: A1, A2, A3 einzeln -> A1-A3
    if "A1-A3" not in gwp and all(m in gwp for m in ("A1", "A2", "A3")):
        gwp["A1-A3"] = gwp.pop("A1") + gwp.pop("A2") + gwp.pop("A3")
        szenarien["A1-A3"] = szenarien.pop("A1")
        szenarien.pop("A2")
        szenarien.pop("A3")
        hinweise.append("A1-A3 = A1 + A2 + A3 (im Datensatz einzeln angegeben)")
    if "A1-A3" not in gwp:
        raise OekobaudatFehler("Datensatz %s hat kein A1-A3" % uuid)

    ordnung = {m: i for i, m in enumerate(MODUL_REIHENFOLGE)}
    gwp = dict(sorted(gwp.items(), key=lambda kv: ordnung.get(kv[0], 99)))
    return Datensatz(uuid=uuid, name=name, einheit=einheit, bezugsmenge=bezugsmenge,
                     dichte_kg_m3=dichte, gwp=gwp, szenarien=szenarien, luecken=luecken,
                     hinweise=hinweise, url=BASE_URL.format(uuid=uuid))


def lade_datensatz(uuid):
    """Datensatz live abrufen und auswerten."""
    return parse_datensatz(uuid, hole_json(uuid))


if __name__ == "__main__":
    for gruppe, varianten in DATENSAETZE.items():
        for variante, uuid in varianten.items():
            ds = lade_datensatz(uuid)
            print("%s / %s: %s (je %g %s)" % (gruppe, variante, ds.name, ds.bezugsmenge, ds.einheit))
            print("   kg CO2e je %s:" % ds.einheit, {m: round(v, 5) for m, v in ds.gwp.items()})
            if ds.luecken:
                print("   ohne Wert:", ds.luecken)

