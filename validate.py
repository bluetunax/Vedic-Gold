"""
Reference-point validation. Run:  python validate.py

Hard checks (engine fails CI if these break):
  * Sun apparent longitude at J2000.0      ~ 280.37 deg
  * Lahiri ayanamsa at J2000.0             ~ 23.853 deg
  * Mesha Sankranti 2024 (Sun -> sidereal Aries) lands 13-14 Apr UTC
  * Mars retrograde flag set in mid-Jan 2025

Informational (printed, not asserted -- depend on of-date sign boundaries):
  * Jupiter / Saturn rashi on 2025-01-01
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from vedic_engine import compute_chart
from vedic_engine.ephemeris import sun_longitude
from vedic_engine.ayanamsa import ayanamsa
from vedic_engine.chart import rashi_of
from vedic_engine.timeutil import julian_centuries_tt, norm360

PASS, FAIL = "PASS", "FAIL"
_failures = 0


def check(name, ok, detail=""):
    global _failures
    if not ok:
        _failures += 1
    print(f"  [{PASS if ok else FAIL}] {name}{('  -- ' + detail) if detail else ''}")


def _sidereal_sun(dt):
    T = julian_centuries_tt(dt)
    return norm360(sun_longitude(T) - ayanamsa(T, "lahiri"))


def main():
    print("vedic_engine validation")
    print("-" * 60)

    # 1. Sun apparent longitude at J2000.0 (tropical, of-date == J2000)
    sun_j2000 = sun_longitude(0.0)
    check("Sun longitude @ J2000 ~ 280.37 deg",
          abs(sun_j2000 - 280.37) < 0.05, f"{sun_j2000:.4f}")

    # 2. Lahiri ayanamsa at J2000.0
    aya = ayanamsa(0.0, "lahiri")
    check("Lahiri ayanamsa @ J2000 ~ 23.853 deg",
          abs(aya - 23.85304) < 0.001, f"{aya:.5f}")

    # 3. Mesha Sankranti 2024: sidereal Sun crosses 0 deg. Scan April for the
    #    instant longitude wraps 360 -> 0, assert it is 13-14 April UTC.
    cross = None
    t = datetime(2024, 4, 10, tzinfo=timezone.utc)
    prev = _sidereal_sun(t)
    end = datetime(2024, 4, 18, tzinfo=timezone.utc)
    while t < end:
        t += timedelta(minutes=30)
        cur = _sidereal_sun(t)
        if prev > 300 and cur < 60:   # wrapped past 360 -> 0
            cross = t
            break
        prev = cur
    check("Mesha Sankranti 2024 on 13-14 Apr UTC",
          cross is not None and cross.month == 4 and cross.day in (13, 14),
          cross.isoformat() if cross else "no crossing found")

    # 4. Mars retrograde in mid-January 2025 (retro window Dec 2024 - Feb 2025)
    chart = compute_chart(datetime(2025, 1, 15, tzinfo=timezone.utc),
                          latitude=19.076, longitude=72.877)
    mars = chart["planets"]["mars"]
    check("Mars retrograde mid-Jan 2025", mars["retrograde"] is True,
          f"speed {mars['speed_per_day']:.4f} deg/day, in {mars['rashi']['english']}")

    # -- informational ----------------------------------------------------
    print("\n  (informational -- of-date sidereal placements 2025-01-01)")
    for body in ("jupiter", "saturn", "mars"):
        c = compute_chart(datetime(2025, 1, 1, tzinfo=timezone.utc),
                          latitude=19.076, longitude=72.877)
        p = c["planets"][body]
        print(f"    {body.capitalize():9} {p['rashi']['english']:11} "
              f"{p['longitude_sidereal']:7.3f} deg  "
              f"{'Rx' if p['retrograde'] else ''}")

    print("-" * 60)
    if _failures:
        print(f"{_failures} check(s) FAILED")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
