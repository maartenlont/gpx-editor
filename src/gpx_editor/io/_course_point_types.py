"""
Canonical Garmin course point type strings and conversion helpers.

Garmin Connect, Garmin devices, GPX, and TCX all use the same set of
title-case strings for course point types (e.g. "Left", "U Turn",
"Left Fork").  FIT uses integer enums; fitparse returns them as
lowercase snake_case names (e.g. "left_fork").

This module is the single source of truth for all type conversions.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Canonical Garmin type strings (used verbatim in GPX <type> and TCX <PointType>)
# ---------------------------------------------------------------------------

#: Navigation types — classified as *cues* in our data model.
GARMIN_NAV_TYPES: frozenset[str] = frozenset({
    "Left", "Right", "Straight",
    "Slight Left", "Slight Right",
    "Sharp Left", "Sharp Right",
    "U Turn",
    "Left Fork", "Right Fork", "Middle Fork",
})

#: POI types — classified as *POIs* in our data model.
GARMIN_POI_TYPES: frozenset[str] = frozenset({
    "Generic", "Summit", "Valley", "Water", "Food", "Danger",
    "First Aid", "Sprint",
    "Fourth Category", "Third Category", "Second Category",
    "First Category", "Hors Category",
    "Segment Start", "Segment End",
})

ALL_GARMIN_TYPES: frozenset[str] = GARMIN_NAV_TYPES | GARMIN_POI_TYPES


# ---------------------------------------------------------------------------
# Any-input → Garmin canonical (for writers and normalisation)
# ---------------------------------------------------------------------------

# All keys are lowercase so lookup is always `.lower()` of the input.
_TO_GARMIN: dict[str, str] = {
    # Navigation types — Garmin title-case (already correct after .lower())
    "left": "Left",
    "right": "Right",
    "straight": "Straight",
    "slight left": "Slight Left",
    "slight right": "Slight Right",
    "sharp left": "Sharp Left",
    "sharp right": "Sharp Right",
    "u turn": "U Turn",
    "left fork": "Left Fork",
    "right fork": "Right Fork",
    "middle fork": "Middle Fork",
    # FIT snake_case names (returned by fitparse)
    "slight_left": "Slight Left",
    "slight_right": "Slight Right",
    "sharp_left": "Sharp Left",
    "sharp_right": "Sharp Right",
    "u_turn": "U Turn",
    "left_fork": "Left Fork",
    "right_fork": "Right Fork",
    "middle_fork": "Middle Fork",
    "first_aid": "First Aid",
    # Our legacy internal strings
    "u-turn": "U Turn",
    "uturn": "U Turn",
    "turn left": "Left",
    "turn right": "Right",
    "bear left": "Slight Left",
    "bear right": "Slight Right",
    "fork left": "Left Fork",
    "fork right": "Right Fork",
    "continue": "Straight",
    "roundabout": "Left",
    # POI types
    "generic": "Generic",
    "summit": "Summit",
    "valley": "Valley",
    "water": "Water",
    "food": "Food",
    "danger": "Danger",
    "first aid": "First Aid",
    "sprint": "Sprint",
    "fourth category": "Fourth Category",
    "third category": "Third Category",
    "second category": "Second Category",
    "first category": "First Category",
    "hors category": "Hors Category",
    "hors_category": "Hors Category",
    "fourth_category": "Fourth Category",
    "third_category": "Third Category",
    "second_category": "Second Category",
    "first_category": "First Category",
    "segment start": "Segment Start",
    "segment end": "Segment End",
    "segment_start": "Segment Start",
    "segment_end": "Segment End",
}


def to_garmin(type_str: str, fallback: str = "Generic") -> str:
    """Return the canonical Garmin type string for any input type string."""
    return _TO_GARMIN.get((type_str or "").strip().lower(), fallback)


def is_nav_type(type_str: str) -> bool:
    """Return True if *type_str* (any case/format) is a navigation cue type."""
    canonical = to_garmin(type_str, "")
    return canonical in GARMIN_NAV_TYPES


# ---------------------------------------------------------------------------
# POI symbol → Garmin type (for writers)
# ---------------------------------------------------------------------------

_SYMBOL_TO_GARMIN: dict[str, str] = {
    "water": "Water",
    "drinking_water": "Water",
    "fuel": "Food",
    "restaurant": "Food",
    "cafe": "Food",
    "food": "Food",
    "shopping": "Food",
    "supermarket": "Food",
    "convenience": "Food",
    "pharmacy": "First Aid",
    "first_aid": "First Aid",
    "camping": "Generic",
    "camp_site": "Generic",
    "lodging": "Generic",
    "parking": "Generic",
    "summit": "Summit",
    "valley": "Valley",
    "danger": "Danger",
    "sprint": "Sprint",
    "generic": "Generic",
}


def symbol_to_garmin(symbol: str) -> str:
    """Map a POI symbol to the most appropriate Garmin course point type."""
    return _SYMBOL_TO_GARMIN.get((symbol or "").strip().lower(), "Generic")


# ---------------------------------------------------------------------------
# Garmin type → POI symbol (for readers)
# ---------------------------------------------------------------------------

_GARMIN_TO_SYMBOL: dict[str, str] = {
    "generic": "",
    "summit": "summit",
    "valley": "valley",
    "water": "water",
    "food": "food",
    "danger": "danger",
    "first aid": "first_aid",
    "sprint": "sprint",
    "fourth category": "fourth_category",
    "third category": "third_category",
    "second category": "second_category",
    "first category": "first_category",
    "hors category": "hors_category",
}


def garmin_to_symbol(type_str: str) -> str:
    """Map a Garmin POI type string to a POI symbol. Returns '' for Generic."""
    return _GARMIN_TO_SYMBOL.get((type_str or "").strip().lower(), "")


# ---------------------------------------------------------------------------
# FIT ↔ Garmin (integer enum ↔ title-case string)
# ---------------------------------------------------------------------------

_GARMIN_TO_FIT: dict[str, int] = {
    "Generic": 0,
    "Summit": 1,
    "Valley": 2,
    "Water": 3,
    "Food": 4,
    "Danger": 5,
    "Left": 6,
    "Right": 7,
    "Straight": 8,
    "First Aid": 9,
    "Fourth Category": 10,
    "Third Category": 11,
    "Second Category": 12,
    "First Category": 13,
    "Hors Category": 14,
    "Sprint": 15,
    "Left Fork": 16,
    "Right Fork": 17,
    "Middle Fork": 18,
    "Slight Left": 19,
    "Sharp Left": 20,
    "Slight Right": 21,
    "Sharp Right": 22,
    "U Turn": 23,
    "Segment Start": 24,
    "Segment End": 25,
}

_FIT_TO_GARMIN: dict[int, str] = {v: k for k, v in _GARMIN_TO_FIT.items()}


def garmin_to_fit_int(type_str: str) -> int:
    """Map a Garmin type string (any format) to its FIT enum integer."""
    canonical = to_garmin(type_str, "Generic")
    return _GARMIN_TO_FIT.get(canonical, 0)


def fit_int_to_garmin(fit_value: int) -> str:
    """Map a FIT enum integer to its Garmin type string."""
    return _FIT_TO_GARMIN.get(fit_value, "Generic")
