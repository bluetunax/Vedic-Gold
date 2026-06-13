"""
Time and reference-frame utilities for the sidereal engine.

  * Julian Day from a (UTC) datetime.
  * Delta-T (TT - UT) via the Espenak & Meeus (2006) piecewise polynomials, so
    the dynamical-time series in ephemeris.py are evaluated at the right epoch.
  * Mean obliquity of the ecliptic (IAU).
  * Greenwich / local mean sidereal time (nutation omitted -- sub-arc-second).
  * IAU-2006 general precession in longitude, used both to carry J2000
    positions to of-date and to grow the ayanamsa anchor.

Angles are in degrees unless a name says otherwise. ``T`` is always Julian
centuries of Terrestrial Time since J2000.0 (JD 2451545.0 TT).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

DEG = math.pi / 180.0   # multiply degrees -> radians
RAD = 180.0 / math.pi   # multiply radians -> degrees

J2000_JD = 2451545.0
JULIAN_CENTURY = 36525.0


def norm360(x: float) -> float:
    """Normalize an angle to [0, 360)."""
    return x % 360.0


def norm180(x: float) -> float:
    """Normalize an angle to (-180, 180]."""
    return ((x + 180.0) % 360.0) - 180.0


# --------------------------------------------------------------------------
# Julian Day  (Meeus ch. 7) -- proleptic Gregorian calendar
# --------------------------------------------------------------------------
def julian_day(dt: datetime) -> float:
    """Julian Day for an aware/naive UTC datetime (naive is treated as UTC)."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    Y, M = dt.year, dt.month
    day_frac = (dt.day
                + (dt.hour
                   + (dt.minute
                      + (dt.second + dt.microsecond / 1e6) / 60.0) / 60.0) / 24.0)
    if M <= 2:
        Y -= 1
        M += 12
    A = math.floor(Y / 100.0)
    B = 2 - A + math.floor(A / 4.0)
    return (math.floor(365.25 * (Y + 4716))
            + math.floor(30.6001 * (M + 1))
            + day_frac + B - 1524.5)


def julian_centuries_ut(jd_ut: float) -> float:
    return (jd_ut - J2000_JD) / JULIAN_CENTURY


# --------------------------------------------------------------------------
# Delta-T  (Espenak & Meeus 2006 polynomial expressions), seconds
# --------------------------------------------------------------------------
def delta_t_seconds(year: float) -> float:
    """Approximate TT - UT in seconds for a (possibly fractional) year."""
    y = year
    if 2005 <= y <= 2050:
        t = y - 2000
        return 62.92 + 0.32217 * t + 0.005589 * t * t
    if 1986 <= y < 2005:
        t = y - 2000
        return (63.86 + 0.3345 * t - 0.060374 * t**2 + 0.0017275 * t**3
                + 0.000651814 * t**4 + 0.00002373599 * t**5)
    if 1961 <= y < 1986:
        t = y - 1975
        return 45.45 + 1.067 * t - t**2 / 260.0 - t**3 / 718.0
    if 1941 <= y < 1961:
        t = y - 1950
        return 29.07 + 0.407 * t - t**2 / 233.0 + t**3 / 2547.0
    if 1920 <= y < 1941:
        t = y - 1920
        return 21.20 + 0.84493 * t - 0.076100 * t**2 + 0.0020936 * t**3
    if 1900 <= y < 1920:
        t = y - 1900
        return (-2.79 + 1.494119 * t - 0.0598939 * t**2
                + 0.0061966 * t**3 - 0.000197 * t**4)
    if 1860 <= y < 1900:
        t = y - 1860
        return (7.62 + 0.5737 * t - 0.251754 * t**2 + 0.01680668 * t**3
                - 0.0004473624 * t**4 + t**5 / 233174.0)
    if 1800 <= y < 1860:
        t = y - 1800
        return (13.72 - 0.332447 * t + 0.0068612 * t**2 + 0.0041116 * t**3
                - 0.00037436 * t**4 + 0.0000121272 * t**5
                - 0.0000001699 * t**6 + 0.000000000875 * t**7)
    # Far outside the supported window: Morrison & Stephenson parabola (rough).
    u = (y - 1820) / 100.0
    return -20.0 + 32.0 * u * u


def fractional_year(dt: datetime) -> float:
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    else:
        dt = dt.replace(tzinfo=timezone.utc)
    start = datetime(dt.year, 1, 1, tzinfo=timezone.utc)
    nxt = datetime(dt.year + 1, 1, 1, tzinfo=timezone.utc)
    return dt.year + (dt - start).total_seconds() / (nxt - start).total_seconds()


def julian_centuries_tt(dt: datetime) -> float:
    """Julian centuries of TT since J2000 for a UTC datetime (applies Delta-T)."""
    jd_ut = julian_day(dt)
    jd_tt = jd_ut + delta_t_seconds(fractional_year(dt)) / 86400.0
    return (jd_tt - J2000_JD) / JULIAN_CENTURY


# --------------------------------------------------------------------------
# Obliquity, sidereal time, precession
# --------------------------------------------------------------------------
def mean_obliquity(T: float) -> float:
    """Mean obliquity of the ecliptic, degrees (Meeus 22.2)."""
    seconds = 84381.448 - 46.8150 * T - 0.00059 * T * T + 0.001813 * T**3
    return seconds / 3600.0


def gmst(jd_ut: float) -> float:
    """Greenwich Mean Sidereal Time in degrees (Meeus 12.4)."""
    d = jd_ut - J2000_JD
    T = d / JULIAN_CENTURY
    theta = (280.46061837 + 360.98564736629 * d
             + 0.000387933 * T * T - T**3 / 38710000.0)
    return norm360(theta)


def local_sidereal_time(jd_ut: float, longitude_east_deg: float) -> float:
    """Local mean sidereal time in degrees; east longitude positive."""
    return norm360(gmst(jd_ut) + longitude_east_deg)


def precession_since_j2000(T: float) -> float:
    """IAU-2006 general precession in longitude since J2000, degrees."""
    p_arcsec = (5028.796195 * T + 1.1054348 * T * T + 0.00007964 * T**3
                - 0.000023857 * T**4 - 0.0000000383 * T**5)
    return p_arcsec / 3600.0
