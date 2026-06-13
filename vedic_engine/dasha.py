"""
Vimshottari dasha -- the 120-year nakshatra-based planetary period system.

Driven entirely by the Moon's sidereal longitude at birth: the nakshatra the
Moon occupies fixes the running mahadasha and how much of it is already spent.
Each mahadasha is subdivided into antardashas in the same canonical lord order.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .chart import NAK_SPAN, nakshatra_of

# Order and length (years) of the nine dasha lords. Sum = 120.
DASHA_SEQUENCE = [
    ("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10), ("Mars", 7),
    ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17),
]
TOTAL_YEARS = 120
DAYS_PER_YEAR = 365.25   # Vimshottari convention (Julian year)

_LORDS = [name for name, _ in DASHA_SEQUENCE]
_YEARS = {name: yrs for name, yrs in DASHA_SEQUENCE}


def _add_years(start: datetime, years: float) -> datetime:
    return start + timedelta(days=years * DAYS_PER_YEAR)


def _antardashas(maha_lord: str, maha_start: datetime, maha_years: float):
    """(lord, start_dt, end_dt, years) for each sub-period of one mahadasha."""
    out = []
    start_idx = _LORDS.index(maha_lord)
    cursor = maha_start
    for k in range(9):
        lord = _LORDS[(start_idx + k) % 9]
        years = maha_years * _YEARS[lord] / TOTAL_YEARS
        end = _add_years(cursor, years)
        out.append((lord, cursor, end, round(years, 4)))
        cursor = end
    return out


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def vimshottari(moon_sidereal_lon: float, birth: datetime,
                reference: datetime | None = None) -> dict:
    """Full mahadasha timeline + the period running at ``reference`` (def. now)."""
    birth = _utc(birth)
    reference = datetime.now(timezone.utc) if reference is None else _utc(reference)

    nak = nakshatra_of(moon_sidereal_lon)
    first_idx = nak["index"] % 9
    first_lord = _LORDS[first_idx]
    fraction = (moon_sidereal_lon % NAK_SPAN) / NAK_SPAN
    elapsed_first = fraction * _YEARS[first_lord]

    # The mahadasha running at birth began this far in the past.
    cursor = _add_years(birth, -elapsed_first)

    timeline = []
    current = None
    for k in range(9):
        lord = _LORDS[(first_idx + k) % 9]
        years = _YEARS[lord]
        end = _add_years(cursor, years)
        subs = _antardashas(lord, cursor, years)

        if cursor <= reference < end:
            sub = next((s for s in subs if s[1] <= reference < s[2]), None)
            current = {
                "mahadasha": lord,
                "mahadasha_start": cursor.isoformat(),
                "mahadasha_end": end.isoformat(),
                "antardasha": sub[0] if sub else None,
                "antardasha_start": sub[1].isoformat() if sub else None,
                "antardasha_end": sub[2].isoformat() if sub else None,
                "as_of": reference.isoformat(),
            }

        timeline.append({
            "lord": lord,
            "start": cursor.isoformat(),
            "end": end.isoformat(),
            "years": years,
            "antardashas": [{"lord": s[0], "start": s[1].isoformat(),
                             "end": s[2].isoformat(), "years": s[3]}
                            for s in subs],
        })
        cursor = end

    return {
        "moon_nakshatra": nak["name"],
        "moon_nakshatra_lord": first_lord,
        "balance_at_birth": {
            "lord": first_lord,
            "years_remaining": round(_YEARS[first_lord] - elapsed_first, 4),
        },
        "timeline": timeline,
        "current": current,
    }
