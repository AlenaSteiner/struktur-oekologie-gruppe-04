# -*- coding: utf-8 -*-
"""
Sonnenstand, Strahlung und Erwaermung der Staebe (stark vereinfachtes Modell).

Was gerechnet wird, je Stab und Material:
  * t_mittel  mittlere Stabtemperatur im Gleichgewicht (Sonne + Diffusstrahlung + Bodenreflexion
              gegen Konvektion + Abstrahlung). Stab wird ueber den Querschnitt als gleichmaessig
              warm angenommen, die Ausrichtung des Querschnitts wird gemittelt.
  * t_spitze  Obergrenze fuer die Oberflaeche einer Flaeche, die senkrecht zur Sonne steht
              (nur eine Seite gibt Waerme ab).
  * tau_min   Zeitkonstante der Erwaermung (Minuten): nach tau sind 63 % des Weges zum
              Gleichgewicht erreicht.
Nach t Minuten: T(t) = T_luft + (T_gleichgewicht - T_luft) * (1 - exp(-t / tau)).

Grenzen (bitte beachten):
  * Kein Schatten durch andere Staebe, kein Bodenschatten, keine Waermeleitung zwischen Staeben.
  * Klarer Himmel nach Meinel-Modell, bewoelkt/bedeckt ueber feste Faktoren (Annahme).
  * Beim Beton ist die Biot-Zahl nicht klein (dicker Querschnitt): die Oberflaeche wird in
    Wirklichkeit schneller und heisser als das Mittel. Dort ist t_spitze aussagekraeftiger.
  * Absorption/Emission siehe materialien.py: Annahmen, haengen stark von der Oberflaeche ab.
"""
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from modell import flaeche_m2, umfang_m

BREITE_GRAD = 48.38     # Stockerau
LAENGE_GRAD = 16.21
ZEITZONE = ZoneInfo("Europe/Vienna")

SIGMA = 5.670374e-8     # W/(m2 K4)
ALBEDO = 0.20           # Bodenreflexion
SOLARKONSTANTE = 1353.0

# Himmelszustand: (Faktor Direktstrahlung, Faktor Diffusstrahlung) -- Annahme
HIMMEL = {
    "klar": (1.0, 1.0),
    "wolkig": (0.4, 1.6),
    "bedeckt": (0.0, 2.4),
}


@dataclass
class Umgebung:
    elevation: float      # Sonnenhoehe in Grad
    azimut: float         # Grad von Nord im Uhrzeigersinn
    dni: float            # Direktstrahlung senkrecht zur Sonne, W/m2
    dhi: float            # Diffusstrahlung horizontal, W/m2
    t_luft_k: float
    wind: float           # m/s
    sonne: tuple          # Einheitsvektor Richtung Sonne im Modell (x, y, z)

    @property
    def ghi(self):
        return self.dni * math.sin(math.radians(max(self.elevation, 0.0))) + self.dhi

    @property
    def t_himmel_k(self):
        """Effektive Himmelstemperatur nach Swinbank (klarer Himmel)."""
        return 0.0552 * self.t_luft_k ** 1.5

    @property
    def h_konv(self):
        """Konvektiver Waermeuebergang nach Juerges, W/(m2 K)."""
        return 5.7 + 3.8 * self.wind


def sonnenstand(datum, zeit, breite=BREITE_GRAD, laenge=LAENGE_GRAD):
    """(Hoehe, Azimut) in Grad fuer lokales Datum (YYYY-MM-DD) und Uhrzeit (HH:MM), NOAA-Naeherung."""
    lokal = datetime.strptime(datum + " " + zeit, "%Y-%m-%d %H:%M").replace(tzinfo=ZEITZONE)
    utc = lokal.astimezone(timezone.utc)
    tag = utc.timetuple().tm_yday
    stunden = utc.hour + utc.minute / 60.0
    g = 2.0 * math.pi / 365.0 * (tag - 1 + (stunden - 12.0) / 24.0)
    zeitgl = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    delta = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
             + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    wahre_sonnenzeit = stunden * 60.0 + zeitgl + 4.0 * laenge       # Minuten
    stundenwinkel = math.radians(wahre_sonnenzeit / 4.0 - 180.0)
    phi = math.radians(breite)
    cos_zenit = (math.sin(phi) * math.sin(delta)
                 + math.cos(phi) * math.cos(delta) * math.cos(stundenwinkel))
    hoehe = 90.0 - math.degrees(math.acos(max(-1.0, min(1.0, cos_zenit))))
    azimut = math.degrees(math.atan2(
        math.sin(stundenwinkel),
        math.cos(stundenwinkel) * math.sin(phi) - math.tan(delta) * math.cos(phi))) + 180.0
    return hoehe, azimut % 360.0


def strahlung_klar(hoehe):
    """(DNI, DHI) in W/m2 bei klarem Himmel (Meinel, Kasten-Young fuer die Luftmasse)."""
    if hoehe <= 0.0:
        return 0.0, 0.0
    luftmasse = 1.0 / (math.sin(math.radians(hoehe)) + 0.50572 * (hoehe + 6.07995) ** -1.6364)
    dni = SOLARKONSTANTE * 0.7 ** (luftmasse ** 0.678)
    dhi = 0.12 * dni * math.sin(math.radians(hoehe))
    return dni, dhi


def sonnenvektor(hoehe, azimut, nord_grad):
    """Einheitsvektor zur Sonne im Modell. nord_grad = Kompasswinkel der Modell-Y-Achse."""
    rel = math.radians(azimut - nord_grad)
    h = math.radians(hoehe)
    return (math.sin(rel) * math.cos(h), math.cos(rel) * math.cos(h), math.sin(h))


def umgebung(datum, zeit, himmel, t_luft_c, wind, nord_grad):
    hoehe, azimut = sonnenstand(datum, zeit)
    dni, dhi = strahlung_klar(hoehe)
    f_dni, f_dhi = HIMMEL[himmel]
    return Umgebung(hoehe, azimut, dni * f_dni, dhi * f_dhi, t_luft_c + 273.15, wind,
                    sonnenvektor(hoehe, azimut, nord_grad))


# ---------------------------------------------------------------- Flaechen eines Stabes

def flaechengruppen_aus_netz(verts, tris):
    """Oberflaeche eines (konvexen) Stabes als Liste (Flaeche m2, Normale), gleiche Normalen
    zusammengefasst. Die Normalen werden nach aussen gedreht (Brep-Netze haben keine
    einheitliche Orientierung): aussen = vom Schwerpunkt weg. Gilt fuer konvexe Koerper
    (Flachstaehle, Rohr, Quader)."""
    n = float(len(verts))
    cx = sum(v[0] for v in verts) / n
    cy = sum(v[1] for v in verts) / n
    cz = sum(v[2] for v in verts) / n
    gruppen = {}
    for a, b, c in tris:
        p, q, r = verts[a], verts[b], verts[c]
        ux, uy, uz = q[0] - p[0], q[1] - p[1], q[2] - p[2]
        vx, vy, vz = r[0] - p[0], r[1] - p[1], r[2] - p[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        laenge = math.sqrt(nx * nx + ny * ny + nz * nz)
        if laenge < 1e-12:
            continue
        flaeche = laenge / 2.0
        nx, ny, nz = nx / laenge, ny / laenge, nz / laenge
        tx = (p[0] + q[0] + r[0]) / 3.0 - cx
        ty = (p[1] + q[1] + r[1]) / 3.0 - cy
        tz = (p[2] + q[2] + r[2]) / 3.0 - cz
        if nx * tx + ny * ty + nz * tz < 0:
            nx, ny, nz = -nx, -ny, -nz
        g = gruppen.setdefault((round(nx, 2), round(ny, 2), round(nz, 2)), [0.0, 0.0, 0.0, 0.0])
        g[0] += flaeche
        g[1] += nx * flaeche
        g[2] += ny * flaeche
        g[3] += nz * flaeche
    ergebnis = []
    for flaeche, sx, sy, sz in gruppen.values():
        l = math.sqrt(sx * sx + sy * sy + sz * sz) or 1.0
        ergebnis.append((flaeche, (sx / l, sy / l, sz / l)))
    return ergebnis


def flaechengruppen_zylinder(start, ende, durchmesser_m, segmente=12):
    """Mantel eines duennen Rundstabes (ohne Netz, z. B. RD 12) als gleich grosse Flaechen
    rund um die Achse (Stirnflaechen vernachlaessigt)."""
    dx, dy, dz = ende[0] - start[0], ende[1] - start[1], ende[2] - start[2]
    laenge = math.sqrt(dx * dx + dy * dy + dz * dz)
    d = (dx / laenge, dy / laenge, dz / laenge)
    hilf = (1.0, 0.0, 0.0) if abs(d[0]) < 0.9 else (0.0, 1.0, 0.0)
    e1 = (d[1] * hilf[2] - d[2] * hilf[1], d[2] * hilf[0] - d[0] * hilf[2], d[0] * hilf[1] - d[1] * hilf[0])
    l1 = math.sqrt(sum(c * c for c in e1))
    e1 = tuple(c / l1 for c in e1)
    e2 = (d[1] * e1[2] - d[2] * e1[1], d[2] * e1[0] - d[0] * e1[2], d[0] * e1[1] - d[1] * e1[0])
    mantel = math.pi * durchmesser_m * laenge
    ergebnis = []
    for k in range(segmente):
        w = 2.0 * math.pi * k / segmente
        ergebnis.append((mantel / segmente, tuple(math.cos(w) * e1[i] + math.sin(w) * e2[i] for i in range(3))))
    return ergebnis


# ---------------------------------------------------------------- Einstrahlung und Gleichgewicht

def einstrahlung(gruppen, env):
    """Je Stab (unabhaengig vom Material):
    (Oberflaeche m2, mittlere Einstrahlung W/m2, Himmelsanteil, hoechste Einstrahlung W/m2,
     Himmelsanteil dieser Flaeche)."""
    s = env.sonne
    ghi = env.ghi
    sonne_da = env.elevation > 0.0
    gesamt = absorbiert = himmel = 0.0
    q_max, f_max = 0.0, 0.5
    for flaeche, (nx, ny, nz) in gruppen:
        cos = max(0.0, nx * s[0] + ny * s[1] + nz * s[2]) if sonne_da else 0.0
        f_himmel = (1.0 + nz) / 2.0
        e = env.dni * cos + env.dhi * f_himmel + ghi * ALBEDO * (1.0 - f_himmel)
        gesamt += flaeche
        absorbiert += flaeche * e
        himmel += flaeche * f_himmel
        if e > q_max:
            q_max, f_max = e, f_himmel
    return gesamt, absorbiert / gesamt, himmel / gesamt, q_max, f_max


def _loese(alpha, eps, g, f_himmel, env):
    """Oberflaechentemperatur in K, bei der Aufnahme (alpha*g) = Konvektion + Abstrahlung."""
    t_rad4 = f_himmel * env.t_himmel_k ** 4 + (1.0 - f_himmel) * env.t_luft_k ** 4
    h = env.h_konv
    unten, oben = env.t_luft_k - 80.0, env.t_luft_k + 150.0
    for _ in range(45):
        t = (unten + oben) / 2.0
        bilanz = alpha * g - h * (t - env.t_luft_k) - eps * SIGMA * (t ** 4 - t_rad4)
        if bilanz > 0:
            unten = t
        else:
            oben = t
    return (unten + oben) / 2.0


def erwaermung(ein, material, volumen_m3, env):
    """(T Gleichgewicht degC, T Spitze degC, Zeitkonstante min, Biot-Zahl) fuer einen Stab.

    ein: Ergebnis von einstrahlung(). volumen_m3: Materialvolumen (Rohr: Wandvolumen)."""
    flaeche, g_mittel, f_himmel, q_max, f_max = ein
    t_gl = _loese(material["alpha"], material["eps"], g_mittel, f_himmel, env)
    t_spitze = _loese(material["alpha"], material["eps"], q_max, f_max, env)
    h_rad = 4.0 * material["eps"] * SIGMA * t_gl ** 3
    h_ges = env.h_konv + h_rad
    tau_s = material["dichte"] * material["cp"] * volumen_m3 / (flaeche * h_ges)
    biot = h_ges * (volumen_m3 / flaeche) / material["k"]
    return t_gl - 273.15, t_spitze - 273.15, tau_s / 60.0, biot


# ---------------------------------------------------------------- Tagesverlauf

def flaechen_zusammenfassen(listen, genauigkeit=0.1):
    """Mehrere Flaechenlisten zu einer: gleiche Normalen (auf `genauigkeit` gerundet) werden addiert."""
    gruppen = {}
    for liste in listen:
        for flaeche, n in liste:
            key = tuple(round(c / genauigkeit) for c in n)
            g = gruppen.setdefault(key, [0.0, 0.0, 0.0, 0.0])
            g[0] += flaeche
            g[1] += n[0] * flaeche
            g[2] += n[1] * flaeche
            g[3] += n[2] * flaeche
    ergebnis = []
    for flaeche, sx, sy, sz in gruppen.values():
        l = math.sqrt(sx * sx + sy * sy + sz * sz) or 1.0
        ergebnis.append((flaeche, (sx / l, sy / l, sz / l)))
    return ergebnis


def tagesverlauf(flaechen, volumen_m3, material, datum, himmel, t_luft_c, wind, nord_grad,
                 schritt_min=10, tage=2):
    """Temperaturverlauf eines Bauteils ueber den Tag (konzentrierte Waermekapazitaet).

    Start bei Lufttemperatur um 0:00; es werden `tage` Tage nacheinander gerechnet und der letzte
    zurueckgegeben (eingeschwungen). Die Lufttemperatur ist den ganzen Tag konstant angenommen.
    Rueckgabe: [(Stunde, Temperatur degC, Sonnenhoehe Grad)] fuer den letzten Tag."""
    flaeche_summe = sum(f for f, _n in flaechen)
    va = volumen_m3 / flaeche_summe
    t = t_luft_c + 273.15
    dt = schritt_min * 60.0
    ergebnis = []
    for tag in range(tage):
        for k in range(int(24 * 60 / schritt_min) + 1):
            minuten = k * schritt_min
            m = min(minuten, 1439)
            env = umgebung(datum, "%02d:%02d" % (m // 60, m % 60), himmel, t_luft_c, wind, nord_grad)
            ein = einstrahlung(flaechen, env)
            t_eq = _loese(material["alpha"], material["eps"], ein[1], ein[2], env)
            h = env.h_konv + 4.0 * material["eps"] * SIGMA * t ** 3
            tau = material["dichte"] * material["cp"] * va / h
            if not (tag == 0 and k == 0):
                t = t_eq + (t - t_eq) * math.exp(-dt / tau)
            if tag == tage - 1:
                ergebnis.append((minuten / 60.0, t - 273.15, env.elevation))
    return ergebnis

