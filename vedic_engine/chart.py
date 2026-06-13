"""
Chart layer: turns of-date tropical longitudes into Jyotisa quantities --
rashi, nakshatra + pada, navamsa, lagna (ascendant), and whole-sign bhavas.

Sidereal longitudes are obtained by subtracting a single of-date ayanamsa from
the tropical longitudes ephemeris.py produces, exactly as that module promises.
"""
from __future__ import annotations

import math
from datetime import datetime

from . import ephemeris as _eph
from .ayanamsa import ayanamsa
from .timeutil import (DEG, norm360, julian_day, local_sidereal_time,
                       mean_obliquity, julian_centuries_tt)

# 12 rashis (sanskrit, english) -------------------------------------------
RASHIS = [
    ("Mesha", "Aries"), ("Vrishabha", "Taurus"), ("Mithuna", "Gemini"),
    ("Karka", "Cancer"), ("Simha", "Leo"), ("Kanya", "Virgo"),
    ("Tula", "Libra"), ("Vrishchika", "Scorpio"), ("Dhanu", "Sagittarius"),
    ("Makara", "Capricorn"), ("Kumbha", "Aquarius"), ("Meena", "Pisces"),
]

# 27 nakshatras ------------------------------------------------------------
NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada",
    "Revati",
]

# Vimshottari lord order, used here to label each nakshatra's ruling graha.
_NAK_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars",
              "Rahu", "Jupiter", "Saturn", "Mercury"]

NAK_SPAN = 360.0 / 27.0       # 13 deg 20'
PADA_SPAN = NAK_SPAN / 4.0    # 3 deg 20'
NAVAMSA_SPAN = 360.0 / 108.0  # 3 deg 20' (108 navamsas across the zodiac)


def rashi_of(longitude: float) -> dict:
    lon = norm360(longitude)
    idx = int(lon // 30.0)
    san, eng = RASHIS[idx]
    return {"index": idx, "sanskrit": san, "english": eng,
            "degrees_in_sign": round(lon - 30.0 * idx, 6)}


def nakshatra_of(longitude: float) -> dict:
    lon = norm360(longitude)
    idx = int(lon // NAK_SPAN)
    pada = int((lon - idx * NAK_SPAN) // PADA_SPAN) + 1
    return {"index": idx, "name": NAKSHATRAS[idx], "pada": pada,
            "lord": _NAK_LORDS[idx % 9]}


def navamsa_of(longitude: float) -> dict:
    idx = int(norm360(longitude) // NAVAMSA_SPAN) % 12
    san, eng = RASHIS[idx]
    return {"index": idx, "sanskrit": san, "english": eng}


def _placement(sidereal_lon: float) -> dict:
    nak = nakshatra_of(sidereal_lon)
    return {
        "longitude_sidereal": round(norm360(sidereal_lon), 6),
        "rashi": rashi_of(sidereal_lon),
        "nakshatra": nak["name"],
        "nakshatra_index": nak["index"],
        "nakshatra_lord": nak["lord"],
        "pada": nak["pada"],
        "navamsa": navamsa_of(sidereal_lon),
    }


# Lagna (ascendant) --------------------------------------------------------
def ascendant_tropical(jd_ut: float, T_tt: float,
                       latitude: float, longitude_east: float) -> float:
    """Tropical ecliptic longitude of the rising point (degrees)."""
    lst = local_sidereal_time(jd_ut, longitude_east)   # = RAMC, degrees
    theta = lst * DEG
    e = mean_obliquity(T_tt) * DEG
    phi = latitude * DEG
    asc = math.atan2(math.cos(theta),
                     -(math.sin(theta) * math.cos(e) + math.tan(phi) * math.sin(e)))
    return norm360(math.degrees(asc))


def lagna(dt: datetime, latitude: float, longitude_east: float,
          ayanamsa_system: str = "lahiri") -> dict:
    jd_ut = julian_day(dt)
    T = julian_centuries_tt(dt)
    trop = ascendant_tropical(jd_ut, T, latitude, longitude_east)
    sid = norm360(trop - ayanamsa(T, ayanamsa_system))
    out = _placement(sid)
    out["longitude_tropical"] = round(trop, 6)
    return out


# Houses (whole sign -- classical Vedic default) ---------------------------
def whole_sign_houses(lagna_rashi_index: int) -> list[dict]:
    houses = []
    for h in range(12):
        sign_idx = (lagna_rashi_index + h) % 12
        san, eng = RASHIS[sign_idx]
        houses.append({"house": h + 1, "rashi_index": sign_idx,
                       "sanskrit": san, "english": eng})
    return houses


def bhava_of(graha_rashi_index: int, lagna_rashi_index: int) -> int:
    return ((graha_rashi_index - lagna_rashi_index) % 12) + 1


def grahas(dt: datetime, lagna_rashi_index: int,
           ayanamsa_system: str = "lahiri") -> dict:
    T = julian_centuries_tt(dt)
    aya = ayanamsa(T, ayanamsa_system)
    out = {}
    for name, info in _eph.all_tropical(T).items():
        sid = norm360(info["tropical"] - aya)
        p = _placement(sid)
        p["longitude_tropical"] = round(info["tropical"], 6)
        p["speed_per_day"] = round(info["speed_per_day"], 6)
        p["retrograde"] = info["retrograde"]
        p["bhava"] = bhava_of(p["rashi"]["index"], lagna_rashi_index)
        out[name] = p
    return out
