"""
vedic_engine -- a from-scratch sidereal (Jyotisa / Vedic) astrology engine.

``compute_chart(dt, latitude, longitude, ayanamsa_system="lahiri")`` assembles a
full kundli: lagna, grahas (rashi / nakshatra / navamsa / bhava / speed /
retrograde), whole-sign houses, the navamsa (D9) chart, and the Vimshottari
dasha timeline plus the period running now.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import chart as _chart
from .ayanamsa import ayanamsa, available as ayanamsa_systems
from .dasha import vimshottari
from .timeutil import julian_day, julian_centuries_tt

__all__ = ["compute_chart", "ayanamsa_systems"]


def compute_chart(dt: datetime,
                  latitude: float,
                  longitude: float,
                  ayanamsa_system: str = "lahiri",
                  reference: datetime | None = None) -> dict:
    """Compute a full Vedic birth chart.

    Parameters
    ----------
    dt : datetime
        Birth moment. Naive datetimes are assumed UTC; aware ones are converted.
    latitude, longitude : float
        Geographic latitude and east-positive longitude, in degrees.
    ayanamsa_system : str
        One of ``vedic_engine.ayanamsa_systems()``.
    reference : datetime, optional
        Moment for the "currently running" dasha (defaults to now, UTC).
    """
    dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

    T = julian_centuries_tt(dt)
    jd_ut = julian_day(dt)

    lagna = _chart.lagna(dt, latitude, longitude, ayanamsa_system)
    lagna_rashi_idx = lagna["rashi"]["index"]

    grahas = _chart.grahas(dt, lagna_rashi_idx, ayanamsa_system)
    houses = _chart.whole_sign_houses(lagna_rashi_idx)

    # Navamsa (D9): the same bodies projected to their navamsa signs, with the
    # navamsa of the lagna as house 1.
    nav_lagna_idx = lagna["navamsa"]["index"]
    navamsa = {
        "lagna": lagna["navamsa"],
        "planets": {
            name: {"navamsa": info["navamsa"],
                   "bhava": _chart.bhava_of(info["navamsa"]["index"], nav_lagna_idx)}
            for name, info in grahas.items()
        },
    }

    dasha = vimshottari(grahas["moon"]["longitude_sidereal"], dt, reference)

    return {
        "input": {
            "datetime_utc": dt.isoformat(),
            "latitude": latitude,
            "longitude": longitude,
            "ayanamsa_system": ayanamsa_system,
            "julian_day_ut": round(jd_ut, 6),
        },
        "ayanamsa": {
            "system": ayanamsa_system,
            "value_deg": round(ayanamsa(T, ayanamsa_system), 6),
        },
        "lagna": lagna,
        "planets": grahas,
        "houses": houses,
        "navamsa": navamsa,
        "vimshottari_dasha": dasha,
    }
