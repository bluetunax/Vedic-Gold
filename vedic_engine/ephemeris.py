"""
Analytic geocentric ephemeris (no external data files).

  * Sun   - Meeus ch. 25 (apparent geocentric longitude, ~0.01 deg).
  * Moon  - Meeus ch. 47 truncated ELP-2000/82 series (~ sub-arc-minute in
            longitude, which is what matters for nakshatra / dasha).
  * Planets - E.M. Standish, "Keplerian Elements for Approximate Positions of
            the Major Planets" (JPL). Heliocentric Kepler solution differenced
            against Earth, valid ~1800-2050 to arc-minute level. Plenty for
            sign / nakshatra placement.
  * Nodes - mean lunar node (Rahu), Ketu opposite.

All functions return *of-date tropical* ecliptic longitude in degrees, so the
chart layer can subtract a single of-date ayanamsa uniformly.
"""
from __future__ import annotations

import math
from .timeutil import DEG, RAD, norm360, precession_since_j2000
from . import ephemeris_data as _data

# --------------------------------------------------------------------------
# SUN  (Meeus ch. 25)
# --------------------------------------------------------------------------
def sun_longitude(T: float) -> float:
    L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T
    M = 357.52911 + 35999.05029 * T - 0.0001537 * T * T
    Mr = M * DEG
    C = ((1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(Mr)
         + (0.019993 - 0.000101 * T) * math.sin(2 * Mr)
         + 0.000289 * math.sin(3 * Mr))
    true_long = L0 + C
    omega = 125.04 - 1934.136 * T
    app = true_long - 0.00569 - 0.00478 * math.sin(omega * DEG)
    return norm360(app)


# --------------------------------------------------------------------------
# MOON  (Meeus ch. 47)
# --------------------------------------------------------------------------
# Periodic-term coefficients (Meeus tables 47.A / 47.B) are loaded from
# vedic_engine/data/moon_elp2000.json at import time -- see ephemeris_data.py.
# Each row is (amplitude_1e-6_deg, D, M, M', F). The amplitudes are constants of
# the lunar theory; the date enters only through D, M, M', F below.
_MOON_LON = _data.moon_longitude_terms()
_MOON_LAT = _data.moon_latitude_terms()


def _moon(T: float) -> tuple[float, float]:
    """Return (geocentric ecliptic longitude, latitude) of the Moon, degrees."""
    Lp = norm360(218.3164477 + 481267.88123421 * T - 0.0015786 * T**2
                 + T**3 / 538841.0 - T**4 / 65194000.0)
    D = norm360(297.8501921 + 445267.1114034 * T - 0.0018819 * T**2
                + T**3 / 545868.0 - T**4 / 113065000.0)
    M = norm360(357.5291092 + 35999.0502909 * T - 0.0001536 * T**2
                + T**3 / 24490000.0)
    Mp = norm360(134.9633964 + 477198.8675055 * T + 0.0087414 * T**2
                 + T**3 / 69699.0 - T**4 / 14712000.0)
    F = norm360(93.2720950 + 483202.0175233 * T - 0.0036539 * T**2
                - T**3 / 3526000.0 + T**4 / 863310000.0)
    E = 1.0 - 0.002516 * T - 0.0000074 * T * T

    A1 = norm360(119.75 + 131.849 * T)
    A2 = norm360(53.09 + 479264.290 * T)
    A3 = norm360(313.45 + 481266.484 * T)

    sl = 0.0
    for c, d, m, mp, f in _MOON_LON:
        arg = (d * D + m * M + mp * Mp + f * F) * DEG
        coeff = c
        if abs(m) == 1:
            coeff *= E
        elif abs(m) == 2:
            coeff *= E * E
        sl += coeff * math.sin(arg)
    sl += 3958 * math.sin(A1 * DEG) + 1962 * math.sin((Lp - F) * DEG) + 318 * math.sin(A2 * DEG)

    sb = 0.0
    for c, d, m, mp, f in _MOON_LAT:
        arg = (d * D + m * M + mp * Mp + f * F) * DEG
        coeff = c
        if abs(m) == 1:
            coeff *= E
        elif abs(m) == 2:
            coeff *= E * E
        sb += coeff * math.sin(arg)
    sb += (-2235 * math.sin(Lp * DEG) + 382 * math.sin(A3 * DEG)
           + 175 * math.sin((A1 - F) * DEG) + 175 * math.sin((A1 + F) * DEG)
           + 127 * math.sin((Lp - Mp) * DEG) - 115 * math.sin((Lp + Mp) * DEG))

    lon = norm360(Lp + sl / 1_000_000.0)
    lat = sb / 1_000_000.0
    return lon, lat


def moon_longitude(T: float) -> float:
    return _moon(T)[0]


# --------------------------------------------------------------------------
# PLANETS  (Standish Keplerian elements, J2000 ecliptic frame)
# Elements + per-century rates are loaded from
# vedic_engine/data/planets_standish.json. Layout per body:
#   ((a, e, I, L, long_peri, long_node), (their rates per Julian century))
# The _EXTRA dict holds the giants' long-period mean-anomaly corrections.
# These are orbit constants; the date enters only as T in _heliocentric().
# --------------------------------------------------------------------------
_ELEMENTS = _data.planetary_elements()
_EXTRA = _data.planetary_extra_terms()


def _kepler(M_deg: float, e: float) -> float:
    """Solve Kepler's equation, return eccentric anomaly E in radians."""
    M = math.radians(((M_deg + 180.0) % 360.0) - 180.0)
    E = M + e * math.sin(M)
    for _ in range(12):
        dE = (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
        E -= dE
        if abs(dE) < 1e-9:
            break
    return E


def _heliocentric(name: str, T: float) -> tuple[float, float, float]:
    (a0, e0, I0, L0, w0, O0), (da, de, dI, dL, dw, dO) = _ELEMENTS[name]
    a = a0 + da * T
    e = e0 + de * T
    I = I0 + dI * T
    L = L0 + dL * T
    w = w0 + dw * T   # longitude of perihelion (varpi)
    O = O0 + dO * T   # longitude of ascending node

    M = L - w
    if name in _EXTRA:
        b, c, s, f = _EXTRA[name]
        M += b * T * T + c * math.cos(math.radians(f * T)) + s * math.sin(math.radians(f * T))

    E = _kepler(M, e)
    # position in orbital plane
    xp = a * (math.cos(E) - e)
    yp = a * math.sqrt(1 - e * e) * math.sin(E)

    wr = math.radians(w - O)   # argument of perihelion
    Ir = math.radians(I)
    Or = math.radians(O)
    cw, sw = math.cos(wr), math.sin(wr)
    cI, sI = math.cos(Ir), math.sin(Ir)
    cO, sO = math.cos(Or), math.sin(Or)

    x = (cw * cO - sw * sO * cI) * xp + (-sw * cO - cw * sO * cI) * yp
    y = (cw * sO + sw * cO * cI) * xp + (-sw * sO + cw * cO * cI) * yp
    z = (sw * sI) * xp + (cw * sI) * yp
    return x, y, z


def planet_longitude(name: str, T: float) -> float:
    """Of-date tropical geocentric ecliptic longitude of a planet, degrees."""
    name = name.lower()
    xe, ye, ze = _heliocentric("earth", T)
    xp, yp, zp = _heliocentric(name, T)
    xg, yg = xp - xe, yp - ye
    lon_j2000 = math.degrees(math.atan2(yg, xg))
    # J2000 ecliptic -> of-date by adding accumulated precession in longitude.
    return norm360(lon_j2000 + precession_since_j2000(T))


# --------------------------------------------------------------------------
# LUNAR NODE  (mean, of-date)  Rahu = ascending node, Ketu opposite.
# --------------------------------------------------------------------------
def rahu_longitude(T: float) -> float:
    omega = (125.0445479 - 1934.1362891 * T + 0.0020754 * T * T
             + T**3 / 467441.0 - T**4 / 60616000.0)
    return norm360(omega)


# --------------------------------------------------------------------------
# Convenience: all grahas as of-date tropical longitudes, plus daily motion.
# --------------------------------------------------------------------------
GRAHAS = ["sun", "moon", "mercury", "venus", "mars",
          "jupiter", "saturn", "rahu", "ketu"]


def _tropical_longitude(name: str, T: float) -> float:
    if name == "sun":
        return sun_longitude(T)
    if name == "moon":
        return moon_longitude(T)
    if name == "rahu":
        return rahu_longitude(T)
    if name == "ketu":
        return norm360(rahu_longitude(T) + 180.0)
    return planet_longitude(name, T)


def all_tropical(T: float) -> dict[str, dict]:
    """Longitude + crude daily speed (for retrograde flag) for each graha."""
    dT = 0.5 / 36525.0  # half a day in centuries, central difference
    out = {}
    for g in GRAHAS:
        lon = _tropical_longitude(g, T)
        lon_p = _tropical_longitude(g, T + dT)
        lon_m = _tropical_longitude(g, T - dT)
        # unwrap the difference across 0/360
        diff = ((lon_p - lon_m + 540.0) % 360.0) - 180.0
        speed = diff  # degrees per day (since 2*dT == 1 day)
        out[g] = {"tropical": lon, "speed_per_day": speed,
                  "retrograde": speed < 0 and g not in ("rahu", "ketu")}
    # Rahu/Ketu are always retrograde by convention (mean node moves backwards)
    out["rahu"]["retrograde"] = True
    out["ketu"]["retrograde"] = True
    return out
