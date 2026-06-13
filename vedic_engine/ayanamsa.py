"""
Ayanamsa: the angular offset between the tropical (season-based) zodiac and the
sidereal (star-based) zodiac used in Jyotisa.

Lahiri (Chitrapaksha) is the Government of India standard and the default here.
We anchor it to its well-established J2000 value (23 deg 51' 11" ~= 23.85304 deg)
and grow it with accumulated precession, which matches published Lahiri values
to within an arc-minute across the 19th-22nd centuries.
"""
from __future__ import annotations

from .timeutil import precession_since_j2000
from . import ephemeris_data as _data

# Ayanamsa value at J2000.0, in degrees, loaded from
# vedic_engine/data/ayanamsa.json. The value is grown by precession at runtime.
_ANCHOR_J2000 = _data.ayanamsa_anchors()


def ayanamsa(T: float, system: str = "lahiri") -> float:
    """Ayanamsa in degrees for Julian centuries T (TT) since J2000."""
    key = system.lower()
    if key not in _ANCHOR_J2000:
        raise ValueError(f"Unknown ayanamsa '{system}'. "
                         f"Options: {', '.join(_ANCHOR_J2000)}")
    return _ANCHOR_J2000[key] + precession_since_j2000(T)


def available() -> list[str]:
    return list(_ANCHOR_J2000)
