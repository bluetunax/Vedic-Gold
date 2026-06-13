"""
Ephemeris data loader.

The numeric constants of the theory (lunar series, planetary elements, ayanamsa
anchors) live in JSON files under ``vedic_engine/data/`` rather than inline in
the algorithm code -- the same separation Swiss Ephemeris makes with its .se1
files. This module locates those files relative to the package, reads each one
exactly once (cached), and adapts them into the structures the algorithms expect.

Override the data directory with the VEDIC_EPHE_PATH environment variable
(analogous to Swiss Ephemeris' SE_EPHE_PATH / swe_set_ephe_path).
"""
from __future__ import annotations

import functools
import json
import os
from pathlib import Path

_DEFAULT_DIR = Path(__file__).resolve().parent / "data"


def data_dir() -> Path:
    return Path(os.environ.get("VEDIC_EPHE_PATH", _DEFAULT_DIR))


@functools.lru_cache(maxsize=None)
def _load(filename: str) -> dict:
    path = data_dir() / filename
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"ephemeris data file not found: {path}. "
            f"Set VEDIC_EPHE_PATH to the directory containing the JSON data files."
        ) from e


def clear_cache() -> None:
    """Drop cached data (e.g. after changing VEDIC_EPHE_PATH)."""
    _load.cache_clear()


# -- Moon -------------------------------------------------------------------
def moon_longitude_terms() -> list[tuple]:
    return [tuple(r) for r in _load("moon_elp2000.json")["longitude_terms"]]


def moon_latitude_terms() -> list[tuple]:
    return [tuple(r) for r in _load("moon_elp2000.json")["latitude_terms"]]


# -- Planets ----------------------------------------------------------------
_ELEM_KEYS = ("a", "e", "I", "L", "long_peri", "long_node")


def planetary_elements() -> dict[str, tuple[tuple, tuple]]:
    """Return {name: ((values...), (rates...))} matching the algorithm's layout."""
    raw = _load("planets_standish.json")["elements"]
    out = {}
    for name, body in raw.items():
        values = tuple(body[k] for k in _ELEM_KEYS)
        rates = tuple(body["rates"][k] for k in _ELEM_KEYS)
        out[name] = (values, rates)
    return out


def planetary_extra_terms() -> dict[str, tuple]:
    raw = _load("planets_standish.json")["extra_terms"]
    return {name: (t["b"], t["c"], t["s"], t["f"]) for name, t in raw.items()}


# -- Ayanamsa ---------------------------------------------------------------
def ayanamsa_anchors() -> dict[str, float]:
    return dict(_load("ayanamsa.json")["anchors_j2000_deg"])
