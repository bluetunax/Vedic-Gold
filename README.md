# Vedic Gold

A **from-scratch sidereal (Jyotisa / Vedic) astrology engine** in pure Python.
No external ephemeris files, no third-party astrology APIs, and (for the core
engine) no third-party packages at all. Built because hosted Vedic-astrology
APIs tend to be buggy and disagree with each other.

## What it computes

- **Grahas** (Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu):
  sidereal longitude, rashi (sign), nakshatra + pada, navamsa sign, bhava
  (house), daily speed, and retrograde flag.
- **Lagna** (ascendant) with its rashi, nakshatra and navamsa.
- **Houses** — whole-sign (the classical Vedic default).
- **Navamsa (D9)** divisional chart placements.
- **Vimshottari dasha** — full mahadasha timeline with antardashas, plus the
  period running *now*.
- **Ayanamsa** — Lahiri (default), Raman, Krishnamurti, Fagan–Bradley.

## How the astronomy works

| Body | Method | Typical accuracy |
|------|--------|------------------|
| Sun | Meeus ch. 25 (apparent geocentric) | ~0.01° |
| Moon | Meeus ch. 47 truncated ELP-2000/82 (~60+30 terms) | sub-arc-minute in longitude |
| Planets | JPL/Standish Keplerian elements, heliocentric Kepler solution differenced against Earth | ~arc-minute, valid **1800–2050** |
| Rahu/Ketu | mean lunar node | exact (mean) |

Times are converted from UTC to Terrestrial Time via an approximate Delta-T
model before evaluating the series. Ayanamsa is anchored to its J2000 value and
grown with IAU-2006 precession.

**Validated** against: Sun longitude at J2000 (280.37°), Mesha Sankranti 2024
crossing (late April 13 UTC), Lahiri ayanamsa values (23.853° @ 2000), and
real 2025 transits (Mars retrograde in Cancer, Jupiter in Taurus, Saturn
leaving Aquarius). See `validate.py`.

> Accuracy is more than enough for sign/nakshatra/house/dasha work. For arc-
> second positions across millennia (e.g. ancient or far-future dates), swap the
> ephemeris for Swiss Ephemeris — see "Upgrade path" below.

## Setup

The core engine has no third-party runtime dependencies, so this is mostly
about pinning the interpreter:

```bash
conda env create -f environment.yml
conda activate vedic-engine
python validate.py          # run the reference-point checks
```

Optional extras (Swiss Ephemeris upgrade path, FastAPI server, etc.) are
commented in `environment.yml` — uncomment what you need.

## Usage (command line)

The quickest way to get a chart. Enter a **local clock time** and a **city** —
the timezone (including historical daylight-saving) and coordinates are resolved
for you from a small built-in gazetteer (`data/cities.json`).

```bash
# interactive: just run it and answer the prompts
python -m vedic_engine

# by city + local birth time
python -m vedic_engine "1990-08-15 15:00" --city Mumbai
python -m vedic_engine "1988-06-20 14:30" --city "Hyderabad, IN"

# by coordinates + timezone (for places not in the gazetteer)
python -m vedic_engine "1990-08-15 15:00" --lat 19.08 --lon 72.88 --tz Asia/Kolkata

# by an absolute UTC instant (append Z; no city/tz needed)
python -m vedic_engine "1990-08-15T09:30:00Z" --lat 19.08 --lon 72.88

# full JSON instead of the readable summary
python -m vedic_engine "1990-08-15 15:00" --city Mumbai --json
```

A zoneless time is read as the place's **local** time when a city or `--tz` is
given, otherwise as UTC. The gazetteer is a convenience, not a full geocoder —
fall back to `--lat/--lon/--tz` for anything it doesn't know.

## Usage (library)

```python
from datetime import datetime, timezone
from vedic_engine import compute_chart

chart = compute_chart(
    datetime(1990, 8, 15, 9, 30, tzinfo=timezone.utc),  # birth moment (UTC)
    latitude=19.076, longitude=72.877,                  # Mumbai
    ayanamsa_system="lahiri",
)
print(chart["lagna"]["rashi"]["english"])
print(chart["planets"]["moon"]["nakshatra"])
print(chart["vimshottari_dasha"]["current"])
```

> Pass the birth time in **UTC** (or an aware datetime in any zone — it's
> converted). A local 15:00 IST birth is `09:30Z`.

## Usage (API)

```bash
python -m api.server 8000
```

```bash
curl "http://localhost:8000/chart?datetime=1990-08-15T09:30:00Z&lat=19.076&lon=72.877"
curl -X POST http://localhost:8000/chart \
     -H 'Content-Type: application/json' \
     -d '{"datetime":"1990-08-15T09:30:00Z","lat":19.076,"lon":72.877,"ayanamsa":"lahiri"}'
```

Endpoints: `GET /health`, `GET /ayanamsas`, `GET|POST /chart`.

## Layout

```
vedic_engine/
  data/                      <-- constants live here, not in code
    moon_elp2000.json        lunar series coefficients (Meeus 47.A / 47.B)
    planets_standish.json    planetary Keplerian elements + rates
    ayanamsa.json            ayanamsa J2000 anchor values
  ephemeris_data.py  loads + caches the data files (set VEDIC_EPHE_PATH to relocate)
  timeutil.py   JD, Delta-T, sidereal time, obliquity, precession
  ayanamsa.py   Lahiri + alternatives (reads anchors from data/)
  ephemeris.py  Sun / Moon / planets / nodes  (algorithms only, no constants)
  chart.py      rashi, nakshatra, lagna, houses, navamsa
  dasha.py      Vimshottari
  __init__.py   compute_chart() — assembles the full kundli
api/
  server.py     stdlib HTTP JSON API
validate.py     reference-point checks
```

## Where the constants live

The numeric constants of the theory are **data, not code**. They sit in
`vedic_engine/data/*.json` and are loaded once at runtime by `ephemeris_data.py`
— the same separation Swiss Ephemeris makes with its `.se1` files (it just uses
a packed binary format; we use readable JSON). The algorithm modules contain no
embedded tables.

Point the engine at a different data directory with an environment variable:

```bash
export VEDIC_EPHE_PATH=/path/to/your/data   # analogous to SE's ephemeris path
```

Missing or unreadable files raise a clear error rather than silently falling
back, so you always know which constants are in effect. Swapping JSON for a
packed binary later is purely a change inside `ephemeris_data.py`; nothing else
moves.

## Upgrade path (when you have internet / production accuracy)

The engine is structured so the **astronomy is isolated in `ephemeris.py`**.
To get Swiss-Ephemeris-grade precision, `pip install pyswisseph` and replace the
body functions with `swe.calc_ut(...)` calls — the Jyotisa layer (chart, dasha,
ayanamsa selection) stays unchanged because it only consumes longitudes.

## Known limitations / deliberate scope

- Planets use mean-element theory → best within **1800–2050**.
- Mean lunar node only (True node is a small addition if you want it).
- Whole-sign houses only (Placidus/Sripati can be layered on the same lagna).
- One divisional chart (D9). Others (D10, D12, …) follow the same pattern in
  `chart.py`.
- Nutation is omitted (sub-arc-second effect, irrelevant to signs/nakshatras).
