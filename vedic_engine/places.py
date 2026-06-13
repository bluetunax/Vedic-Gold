"""
Place + time resolution for the CLI and server.

Lets a person type a city name (resolved against data/cities.json) instead of
decimal coordinates, and enter their *local clock time* instead of UTC. The
local -> UTC conversion (including historical daylight-saving rules) uses the
stdlib ``zoneinfo`` / IANA tz database. The gazetteer is a convenience, not an
exhaustive geocoder -- fall back to explicit lat/lon (+ tz) for anything else.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    _HAVE_TZ = True
except ImportError:  # Python < 3.9
    _HAVE_TZ = False

    class ZoneInfoNotFoundError(Exception):
        pass

_CITIES_PATH = Path(__file__).resolve().parent / "data" / "cities.json"
_LATLON_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$")


def _norm(s: str) -> str:
    return " ".join(s.strip().lower().split())


def load_cities() -> list[dict]:
    with open(_CITIES_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)["cities"]


def find_city(query: str) -> dict:
    """Resolve a city name to its record. Accepts 'Mumbai' or 'Hyderabad, IN'."""
    cities = load_cities()
    raw = query.strip()
    cc = None
    if "," in raw:
        head, tail = raw.rsplit(",", 1)
        tail = tail.strip()
        if len(tail) == 2 and tail.isalpha():
            cc, raw = tail.upper(), head
    key = _norm(raw)

    index: dict[str, list[dict]] = {}
    for c in cities:
        for n in [c["name"], *c.get("aliases", [])]:
            index.setdefault(_norm(n), []).append(c)

    matches = index.get(key, [])
    if cc:
        matches = [m for m in matches if m["country"].upper() == cc] or matches
    if not matches:
        raise ValueError(
            f"city {query!r} is not in the built-in list. Use coordinates "
            f"instead, e.g. --lat 19.08 --lon 72.88 --tz Asia/Kolkata")
    if len(matches) > 1:
        opts = ", ".join(f"{m['name']}, {m['country']}" for m in matches)
        raise ValueError(f"{query!r} is ambiguous ({opts}); add a country code, "
                         f"e.g. '{matches[0]['name']}, {matches[0]['country']}'.")
    return matches[0]


def get_zone(tz_name: str):
    if not _HAVE_TZ:
        raise ValueError("zoneinfo is unavailable in this Python; pass a UTC "
                         "time (append 'Z') or upgrade to Python 3.9+.")
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        raise ValueError(
            f"unknown timezone {tz_name!r}; use an IANA name like 'Asia/Kolkata' "
            f"or 'America/New_York'. (If your environment lacks the tz database, "
            f"`pip install tzdata`.)")


def parse_datetime(s: str) -> datetime:
    """Parse ISO ('...Z', with offset, or naive) or 'YYYY-MM-DD[ HH:MM[:SS]]'."""
    s = s.strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"could not parse date/time {s!r}; try 'YYYY-MM-DD HH:MM'.")


def looks_like_latlon(s: str):
    """Return (lat, lon) if the string is a coordinate pair, else None."""
    m = _LATLON_RE.match(s)
    return (float(m.group(1)), float(m.group(2))) if m else None


def resolve_moment(dt_str: str, *, lat=None, lon=None, city=None, tz=None):
    """Turn flexible inputs into (dt_utc, lat, lon, info).

    info carries what was resolved (place label, timezone used, local time) for
    echoing back to the user. Raises ValueError on missing/invalid input.
    """
    place = None
    if city:
        c = find_city(city)
        lat, lon = c["lat"], c["lon"]
        tz = tz or c["tz"]
        place = f"{c['name']}, {c['country']}"

    if lat is None or lon is None:
        raise ValueError("need a city (--city) or coordinates (--lat and --lon).")
    lat, lon = float(lat), float(lon)

    dt = parse_datetime(dt_str)
    if dt.tzinfo is not None:
        dt_utc = dt.astimezone(timezone.utc)
        used_tz, local_iso = "explicit-offset", dt.isoformat()
    elif tz:
        local = dt.replace(tzinfo=get_zone(tz))
        dt_utc, used_tz, local_iso = local.astimezone(timezone.utc), tz, local.isoformat()
    else:
        dt_utc = dt.replace(tzinfo=timezone.utc)
        used_tz, local_iso = "UTC (assumed -- no timezone given)", dt_utc.isoformat()

    info = {"place": place, "timezone": used_tz, "local_time": local_iso,
            "datetime_utc": dt_utc.isoformat(), "lat": lat, "lon": lon}
    return dt_utc, lat, lon, info
