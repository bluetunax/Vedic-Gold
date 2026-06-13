"""
Command-line entry point.

Interactive (just run it, then answer the prompts):
    python -m vedic_engine

By city + local clock time (the easy way):
    python -m vedic_engine "1990-08-15 15:00" --city Mumbai
    python -m vedic_engine "1988-06-20 14:30" --city Saugatuck

By coordinates + timezone:
    python -m vedic_engine "1990-08-15 15:00" --lat 19.08 --lon 72.88 --tz Asia/Kolkata

By an absolute UTC time (append Z; no city/tz needed):
    python -m vedic_engine "1990-08-15T09:30:00Z" --lat 19.08 --lon 72.88 --json

Times entered without a zone are read as that place's local clock time when a
city/timezone is supplied, otherwise as UTC.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from . import compute_chart
from .ayanamsa import available
from .places import resolve_moment, looks_like_latlon


def _dms(deg: float) -> str:
    x = deg % 30.0
    d = int(x)
    m_f = (x - d) * 60.0
    m = int(m_f)
    s = int(round((m_f - m) * 60.0))
    if s == 60:
        s, m = 0, m + 1
    return f"{d:2d} {m:02d}' {s:02d}\""


def _print_human(chart: dict, info: dict) -> None:
    inp = chart["input"]
    aya = chart["ayanamsa"]
    where = info.get("place") or f"lat {info['lat']}, lon {info['lon']}"
    print("=" * 70)
    print(f"  VEDIC BIRTH CHART   {where}")
    print(f"  born {info['local_time']}  [{info['timezone']}]")
    print(f"       = {inp['datetime_utc']} UTC")
    print(f"  ayanamsa {aya['system']} = {aya['value_deg']:.4f} deg")
    print("=" * 70)

    lg = chart["lagna"]
    print(f"\nLagna (Ascendant) : {lg['rashi']['english']} ({lg['rashi']['sanskrit']})"
          f"  {_dms(lg['longitude_sidereal'])}   {lg['nakshatra']} pada {lg['pada']}")

    print("\nGrahas")
    print(f"  {'Planet':9}{'Rashi':12}{'Pos in sign':14}{'Nakshatra':16}{'Pd':3}{'Ho':3} R")
    print("  " + "-" * 62)
    for name, p in chart["planets"].items():
        retro = "Rx" if p["retrograde"] else ""
        print(f"  {name.capitalize():9}{p['rashi']['english']:12}"
              f"{_dms(p['longitude_sidereal']):14}{p['nakshatra']:16}"
              f"{p['pada']:<3}{p['bhava']:<3} {retro}")

    d = chart["vimshottari_dasha"]
    cur = d["current"]
    print(f"\nVimshottari dasha   (Moon in {d['moon_nakshatra']}, "
          f"balance {d['balance_at_birth']['years_remaining']:.2f} yr "
          f"of {d['moon_nakshatra_lord']} at birth)")
    if cur:
        print(f"  NOW: {cur['mahadasha']} maha / {cur['antardasha']} antar   "
              f"({cur['mahadasha_start'][:10]} -> {cur['mahadasha_end'][:10]}, "
              f"as of {cur['as_of'][:10]})")
    print("  Mahadasha timeline:")
    for m in d["timeline"]:
        print(f"     {m['lord']:9}{m['start'][:10]} -> {m['end'][:10]}  ({m['years']} yr)")
    print()


def _prompt(msg: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"{msg}{suffix}: ").strip()
    except EOFError:
        val = ""
    return val or default


def _interactive() -> dict:
    print("Vedic birth chart -- enter your birth details.\n"
          "(Press Ctrl-C to cancel.)\n")
    date = ""
    while not date:
        date = _prompt("Birth date (YYYY-MM-DD)")
    time = _prompt("Birth time (24h HH:MM, local clock time)", "00:00")
    place = ""
    while not place:
        place = _prompt("Birth city  (or 'lat,lon')")

    kwargs = {}
    coords = looks_like_latlon(place)
    if coords:
        kwargs["lat"], kwargs["lon"] = coords
        tz = _prompt("Timezone (IANA, e.g. America/Detroit; blank = UTC)")
        if tz:
            kwargs["tz"] = tz
    else:
        kwargs["city"] = place

    aya = _prompt(f"Ayanamsa {tuple(available())}", "lahiri")
    kwargs["ayanamsa"] = aya
    kwargs["datetime"] = f"{date} {time}"
    return kwargs


def _run(datetime_str, ayanamsa="lahiri", *, lat=None, lon=None, city=None,
         tz=None, as_json=False):
    dt_utc, lat, lon, info = resolve_moment(datetime_str, lat=lat, lon=lon,
                                            city=city, tz=tz)
    if ayanamsa not in available():
        raise SystemExit(f"unknown ayanamsa '{ayanamsa}'; options: "
                         f"{', '.join(available())}")
    chart = compute_chart(dt_utc, lat, lon, ayanamsa)
    chart["input"]["resolved"] = info  # echo what we parsed

    if as_json:
        json.dump(chart, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _print_human(chart, info)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m vedic_engine",
        description="Compute a sidereal (Vedic / Jyotisa) birth chart. "
                    "Run with no arguments for interactive prompts.")
    ap.add_argument("datetime", nargs="?",
                    help="Birth date/time, e.g. '1990-08-15 15:00' (local if a "
                         "city/timezone is given) or '1990-08-15T09:30:00Z' (UTC).")
    ap.add_argument("--city", help="Birth city (resolved to lat/lon/timezone).")
    ap.add_argument("--lat", type=float, help="Latitude (deg).")
    ap.add_argument("--lon", type=float, help="Longitude (deg, east positive).")
    ap.add_argument("--tz", help="IANA timezone, e.g. 'America/New_York'. "
                                 "Interprets a zoneless time as local.")
    ap.add_argument("--ayanamsa", default="lahiri", choices=available(),
                    help="Ayanamsa system (default: lahiri).")
    ap.add_argument("--json", action="store_true",
                    help="Emit full JSON instead of the readable summary.")
    args = ap.parse_args(argv)

    try:
        if args.datetime is None and not (args.city or (args.lat is not None)):
            kw = _interactive()
            _run(kw.pop("datetime"), kw.pop("ayanamsa", "lahiri"),
                 as_json=args.json, **kw)
        else:
            if args.datetime is None:
                raise SystemExit("provide a birth date/time, e.g. "
                                 "\"1990-08-15 15:00\" --city Mumbai")
            _run(args.datetime, args.ayanamsa, lat=args.lat, lon=args.lon,
                 city=args.city, tz=args.tz, as_json=args.json)
    except ValueError as e:
        raise SystemExit(f"error: {e}")
    except KeyboardInterrupt:
        print("\ncancelled.")
        return 130
    except BrokenPipeError:
        # Output was piped to something that closed early (e.g. `head`); exit
        # quietly instead of dumping a flush-time traceback.
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except OSError:
            pass
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
