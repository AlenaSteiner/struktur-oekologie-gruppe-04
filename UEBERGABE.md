## Übergabe: App „Embodied Carbon Pavillon Stockerau“ (Stand 19.11.2026)

**Ordner:** `/Users/lukasweinberger/Documents/GitHub/struktur-oekologie-gruppe-04`
**Starten:** `.venv/bin/python app.py`, dann `http://127.0.0.1:8000`. Der Start dauert 30 bis 45 s, weil die ÖKOBAUDAT-Datensätze live geladen werden. Bauteil6 erreichst du über `?projekt=bauteil6` oder das Auswahlfeld „Projekt“ in der Kopfzeile.
**Stack:** Python mit FastAPI und rhino3dm, im Browser Plotly. Node ist nicht installiert.

### Was fertig ist
| Funktion | Dateien |
|---|---|
| Embodied Carbon je Stab aus der ÖKOBAUDAT (A1–A3, C, D), Materialwahl je Gruppe, Datensatzwahl | `rechnen.py`, `berechnung.py`, `oekobaudat.py`, `materialien.py`, `modell.py` |
| Sonnenerwärmung, Tagesverlauf | `waerme.py`, `static/tag.js` |
| Bewehrungsplan (PDF) mit Stabliste, Markierung im Plan (Hover rot, Klick blau), Vergleichsmodus | `bewehrungsplan.py`, `static/plan.js` |
| **3D-Bewehrung** aus dem Plan: 501 Stäbe, 1.015,63 kg, stimmt exakt mit der Stabliste | `bewehrung3d.py`, `static/bewehrung3d.js` |
| **Optimierungsmodus:** Heatmap, Hotspots, 6 Ansätze, Szenario-Rechner (alles als Szenario gekennzeichnet) | `optimierung.py`, `static/optimierung*.js` |
| **Bauteil6** als zweites Projekt: 883 IFC-Bauteile, 17 Geschosse, CO₂e je Bauteilart, 6 Regeln in der Seitenleiste | `bauteil6.py`, `rhino/Bauteil6.3dm` |

Stockerau läuft unverändert weiter: 736 Stäbe, A1–A3 = 6.538 kg. Bauteil6 liegt bei 906.253 kg (A1–A3).

### Offene Punkte (Aufgabe verlangt mindestens eine Zusatzoption)
1. **Reuse-Planung (Option 1): erledigt (20.11.2026).** Neuer Modus „Reuse-Planung“ (nur Stockerau). Dateien: `reuse.py`, `static/reuse.js`, `static/reuse_ui.js`, `static/reuse_ergebnis.js`, Endpunkte `/api/reuse` und `/api/reuse/standard`. Zielentwurf als Tabelle (Beispiel, änderbar), Zuschnitt per Best-Fit-Decreasing mit Transportmaß, Schnittverlust, Mindestrest und verjüngten Flachstählen, Vergleich Neu ↔ Reuse nach CO₂e und Zeit, Einfärbung im 3D-Modell. Spender sind Flachstähle (502), Rohre (12) und Zugstäbe (175), Fundamente nicht. **Offen:** Der Beispiel-Zielentwurf ist ausgedacht. Schnitt-, Transport- und Zeitfaktoren sind Annahmen (`STANDARD_PARAMETER` in `reuse.py`). Rest und Verschnitt werden nur als Masse ausgewiesen, nicht in C/D bilanziert. Kein statischer Nachweis, Stahlgüte und Zustand sind ungeprüft. Getestet mit einem Python-Test (Massenbilanz, Randfälle) und Playwright im Headless-Browser (ohne echte Mausklicks im 3D-Modell).
2. **Reuse-Regeln für Bauteil6 fehlen** (Stützen, Träger, Decken, Wände) samt Recherche. Das gehört zu Option 2 „Import und Bauteil6“. Der Import selbst (Rhino-Datei mit IFC-Attributen) ist für Bauteil6 gelöst, aber noch nicht als Hochladefunktion.
3. **Die vier Bewehrungspläne von Bauteil6** (Dateien in `~/Downloads/Archive-16/Bauteil6/*.pdf`) sind nicht eingebunden. Der Betonstahl ist angenommen (Decke 100, Wand 80, Träger 150, Stütze 200 kg/m³).
4. **Die CO₂-Rechnung von Stockerau** verteilt die Bewehrung gleichmäßig (21,6 kg je Fundamentstab). Die 3D-Bewehrung kennt die echte Verteilung (15 bis 42 kg), sie ist aber nicht angebunden.
5. **Kleinigkeiten:** Bei Bauteil6 heißt die Anzeige noch „CO₂e je Stab“. Der Holz-Datensatz hat negatives A1–A3 (biogener Kohlenstoff), die Farbskala wechselt dadurch auf Blau–Rot. Die Ziegel-Datensätze der ÖKOBAUDAT sind nicht auswertbar, Kalksandstein steht stellvertretend für Mauerwerk.
6. **Unbeantwortete Frage:** Soll die App bei einem Bauteil sagen, was die CO₂-Einsparung bei einem anderen Material (Holz, Alu, anderer Beton oder Stahl) wäre?

### Git und Zusammenarbeit
- Fast alle Dateien sind noch **nicht in Git** (`app.py`, `static/`, `rhino/`, `plaene/`, alle `.py` außer `check_setup.py`).
- Die `.gitignore` hat eine kaputte letzte Zeile (`__pycache_python`), `__pycache__/` wird dadurch nicht ignoriert.
- Das Remote zeigt auf `AlinaSchuster/struktur-oekologie-gruppe-XX`. Prüft, ob das euer Gruppen-Repo ist.
- Im Repo liegt ein unbekannter Ordner „Ohne Titel“ mit eigenem `.git` und Vorlagedateien. Nicht anfassen, bevor ihr wisst, was das ist.
- **Zweites Gerät:** Repo klonen, `.venv` anlegen, `pip install -r requirements.txt`, `.env` aus `.env.example` kopieren, `python app.py`. Im selben WLAN geht `python app.py --lan`, die App hat aber keinen Login.

### Tests und Hinweise
- Getestet wurde mit Playwright im Headless-Browser (`/tmp/pw-test`, Browser in `~/Library/Caches/ms-playwright`). `/tmp` kann aufgeräumt sein. Dann das venv neu anlegen und `pip install playwright` ausführen.
- Echte Maus-Hover und Klicks auf das 3D-Modell wurden nie getestet, die Auswahl lief über App-Funktionen.
- Annahmen stehen im Code und in der App: Lage der Bügel in „Detail 1“ und im Querschnitt (`bewehrung3d.py`), Prozentwerte der Optimierungsansätze (`optimierung.py`), Betonstahl je Bauteilart (`bauteil6.py`).

### Credits
Rest auf dem OpenRouter-Konto: **5,06 $**. Der Key ist gültig. Ein langer Verlauf macht jeden Schritt teurer, deshalb lieber neu beginnen.

### Vorschlag für die erste Nachricht in der neuen Unterhaltung
> Lies zuerst `UEBERGABE.md` bzw. diese Notiz. Baue die Reuse-Planung für Stockerau (Punkt 1) in einem Rutsch: eigener Modus, Zielentwurf als Tabelle, Zuschnitt mit Transportmaß, Vergleich CO₂e und Zeit, Markierung im 3D-Modell. Teste einmal am Ende im Headless-Browser und fasse dich kurz.
