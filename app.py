# -*- coding: utf-8 -*-
"""
Lokale Web-App: Embodied Carbon und Sonnenerwaermung des Pavillons Stockerau.

Start (im Repo-Ordner):
    .venv/bin/python app.py          dann im Browser http://127.0.0.1:8000
    .venv/bin/python app.py --lan    zusaetzlich von anderen Geraeten im selben Netz erreichbar
oder
    .venv/bin/python -m uvicorn app:app --port 8000

Beim Start werden die OEKOBAUDAT-Datensaetze live geholt (ca. 30-60 s). Die App laeuft
komplett lokal, die einzige Verbindung nach aussen ist der Abruf der OEKOBAUDAT.
"""
import os
import socket
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import plotly
import uvicorn
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import bauteil6_bewehrung3d
import bauteil6_optimierung
import bauteil6_plaene
import bauteil6_reuse
import bewehrung3d
import bewehrungsplan
import optimierung
import reuse
from bauteil6 import Bauteil6
from rechnen import Projekt

HIER = Path(__file__).resolve().parent
STATIC = HIER / "static"
PLOTLY_JS = Path(plotly.__file__).resolve().parent / "package_data" / "plotly.min.js"

projekt = None          # Stockerau (Standard, unveraendert)
bauteil = None          # Bauteil6 (zweites Projekt, Auswahl ueber ?projekt=bauteil6 bzw. Parameter p)


@asynccontextmanager
async def lifespan(_app):
    global projekt, bauteil
    print("Lese Rhino-Modell und lade OEKOBAUDAT-Datensaetze live ...", flush=True)
    projekt = Projekt()
    ok, schlecht = len(projekt.daten), len(projekt.fehler)
    print("Datensaetze geladen: %d, fehlgeschlagen: %d" % (ok, schlecht), flush=True)
    for (gruppe, variante), text in projekt.fehler.items():
        print("  FEHLER %s/%s: %s" % (gruppe, variante, text), flush=True)
    try:
        bauteil = Bauteil6(projekt)
        print("Bauteil6 gelesen: %d Bauteile" % len(bauteil.teile), flush=True)
    except Exception as fehler:          # Stockerau soll auch ohne Bauteil6 laufen
        print("  Bauteil6 nicht geladen: %s" % fehler, flush=True)
    yield


def waehle(p):
    """Projekt je nach Parameter p: leer = Stockerau, bauteil6 = Bauteil6."""
    if p == "bauteil6":
        if bauteil is None:
            raise HTTPException(status_code=404, detail="Bauteil6 ist nicht geladen (siehe Serverprotokoll)")
        return bauteil
    return projekt


app = FastAPI(title="Embodied Carbon Pavillon Stockerau", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def startseite():
    # Startseite: neue Ansicht (static/neu). Die bisherige Ansicht bleibt unter /klassisch erreichbar.
    return FileResponse(STATIC / "neu" / "index.html")


@app.get("/klassisch")
def klassische_ansicht():
    return FileResponse(STATIC / "index.html")


@app.get("/plotly.min.js")
def plotly_js():
    # lokal aus dem plotly-Paket, kein CDN noetig
    return FileResponse(PLOTLY_JS, media_type="application/javascript")


@app.get("/api/katalog")
def katalog(p: str = ""):
    k = waehle(p).katalog()
    k.setdefault("projekt", "stockerau")
    k["projekte"] = [{"id": "stockerau", "name": "Pavillon Stockerau"}] + \
                    ([{"id": "bauteil6", "name": "Bauteil6 (Geschossbau)"}] if bauteil is not None else [])
    return k


@app.get("/api/geometrie")
def geometrie(p: str = ""):
    return waehle(p).geometrie()


@app.post("/api/rechnen")
def rechnen(konfig: dict = Body(default={}), p: str = ""):
    try:
        return waehle(p).rechne(konfig)
    except ValueError as fehler:
        raise HTTPException(status_code=422, detail=str(fehler))


@app.post("/api/optimierung")
def optimierung_rechnen(konfig: dict = Body(default={}), p: str = ""):
    """Optimierungsszenarien (rechnerisch, kein statischer Nachweis), siehe optimierung.py / bauteil6_optimierung.py."""
    try:
        if p == "bauteil6":
            return bauteil6_optimierung.rechne(waehle(p), konfig)
        return optimierung.rechne(projekt, konfig)
    except ValueError as fehler:
        raise HTTPException(status_code=422, detail=str(fehler))


@app.get("/api/reuse/standard")
def reuse_standard(p: str = ""):
    """Vorgabewerte der Reuse-Planung (Beispiel-Zielentwurf, Annahmen), siehe reuse.py / bauteil6_reuse.py."""
    if p == "bauteil6":
        return bauteil6_reuse.standard(waehle(p))
    return reuse.standard()


@app.post("/api/reuse")
def reuse_rechnen(konfig: dict = Body(default={}), p: str = ""):
    """Reuse-Planung (rechnerisches Szenario, kein statischer Nachweis), siehe reuse.py / bauteil6_reuse.py."""
    try:
        if p == "bauteil6":
            return bauteil6_reuse.rechne(waehle(p), konfig)
        return reuse.rechne(projekt, konfig)
    except ValueError as fehler:
        raise HTTPException(status_code=422, detail=str(fehler))


_bewehrung3d = None
_bewehrung3d_b6 = None


@app.get("/api/bewehrung3d")
def bewehrung3d_daten(p: str = ""):
    """Bewehrungsstaebe in 3D aus den Bewehrungsplaenen (einmal gerechnet). Bauteil6: schematisch je Bauteil."""
    global _bewehrung3d, _bewehrung3d_b6
    if p == "bauteil6":
        b6 = waehle(p)
        if _bewehrung3d_b6 is None:
            _bewehrung3d_b6 = bauteil6_bewehrung3d.fuer_oberflaeche(bauteil6_bewehrung3d.erzeuge(b6.teile, b6.plan_je_plan))
        return _bewehrung3d_b6
    if _bewehrung3d is None:
        try:
            erg = bewehrung3d.erzeuge(projekt.staebe, projekt.gruppe)
        except ValueError as fehler:
            raise HTTPException(status_code=422, detail=str(fehler))
        _bewehrung3d = bewehrung3d.fuer_oberflaeche(erg)
    return _bewehrung3d


@app.get("/api/plan/bild.png")
def plan_bild(p: str = "", plan: str = ""):
    if p == "bauteil6":
        try:
            return Response(bauteil6_plaene.bild_png(plan), media_type="image/png")
        except KeyError:
            raise HTTPException(status_code=404, detail="Unbekannter Plan: %s" % plan)
    return Response(bewehrungsplan.bild_png(), media_type="image/png")


@app.get("/api/plan/lage")
def plan_lage(p: str = ""):
    if p == "bauteil6":
        return waehle(p).plan_lage()
    b, h = bewehrungsplan.bildgroesse()
    return {"breite": b, "hoehe": h, "lage": projekt.plan_lage()}


@app.post("/api/tagesverlauf/{gruppe}")
def tagesverlauf(gruppe: str, konfig: dict = Body(default={})):
    try:
        return projekt.tagesverlauf(konfig, gruppe)
    except ValueError as fehler:
        raise HTTPException(status_code=422, detail=str(fehler))


@app.post("/api/datensaetze-neu-laden")
def neu_laden():
    ok, schlecht = projekt.lade_datensaetze()
    return JSONResponse({"geladen": ok, "fehlgeschlagen": schlecht, "datensaetze": projekt.datensatz_info()})


def lan_adresse():
    """IP dieses Rechners im lokalen Netz (UDP-Socket, es wird nichts gesendet)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    lan = "--lan" in sys.argv
    if lan:
        ip = lan_adresse()
        print("LAN-Modus: erreichbar im selben WLAN/Netz unter http://%s:%d" % (ip or "<IP-dieses-Rechners>", port))
        print("Achtung: die App hat keinen Login. Nur in vertrauenswuerdigen Netzen verwenden.", flush=True)
    uvicorn.run(app, host="0.0.0.0" if lan else "127.0.0.1", port=port)
