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
    "First Aid", "Sprint", "Checkpoint",
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
    "checkpoint": "Checkpoint",
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
    # Water
    "water": "Water",
    "drinking water": "Water",
    "drinking_water": "Water",
    "water tap": "Water",
    "water fountain": "Water",
    "fountain": "Water",
    "tap": "Water",
    "spring": "Water",
    "tint": "Water",  # app glyphicon name
    # Food / drink
    "food": "Food",
    "restaurant": "Food",
    "cafe": "Food",
    "coffee": "Food",
    "cutlery": "Food",  # app glyphicon name
    "bar": "Food",
    "pub": "Food",
    "bakery": "Food",
    "snack": "Food",
    "fast food": "Food",
    "fast_food": "Food",
    "supermarket": "Food",
    "convenience": "Food",
    "shopping": "Food",
    "shop": "Food",
    "market": "Food",
    "grocery": "Food",
    "fuel": "Food",  # fuel stations often sell food/drinks
    # First aid / medical
    "pharmacy": "First Aid",
    "first_aid": "First Aid",
    "first aid": "First Aid",
    "hospital": "First Aid",
    "medical": "First Aid",
    "health": "First Aid",
    "doctor": "First Aid",
    "clinic": "First Aid",
    "plus-sign": "First Aid",  # app glyphicon name
    # Summit
    "summit": "Summit",
    "peak": "Summit",
    "top": "Summit",
    "col": "Summit",
    "pass": "Summit",
    "flag": "Summit",  # app glyphicon name
    "chevron-up": "Summit",  # app glyphicon name
    # Climb categories — all common input variants
    "4th category": "Fourth Category",
    "4th cat": "Fourth Category",
    "cat 4": "Fourth Category",
    "category 4": "Fourth Category",
    "fourth category": "Fourth Category",
    "fourth_category": "Fourth Category",  # stored by garmin_to_symbol()
    "3rd category": "Third Category",
    "3rd cat": "Third Category",
    "cat 3": "Third Category",
    "category 3": "Third Category",
    "third category": "Third Category",
    "third_category": "Third Category",
    "2nd category": "Second Category",
    "2nd cat": "Second Category",
    "cat 2": "Second Category",
    "category 2": "Second Category",
    "second category": "Second Category",
    "second_category": "Second Category",
    "1st category": "First Category",
    "1st cat": "First Category",
    "cat 1": "First Category",
    "category 1": "First Category",
    "first category": "First Category",
    "first_category": "First Category",
    "hors category": "Hors Category",
    "hors cat": "Hors Category",
    "hors catégorie": "Hors Category",
    "hors_category": "Hors Category",  # stored by garmin_to_symbol()
    "hc": "Hors Category",
    "h.c.": "Hors Category",
    "hors": "Hors Category",
    # Valley
    "valley": "Valley",
    "canyon": "Valley",
    # Danger
    "danger": "Danger",
    "hazard": "Danger",
    "warning": "Danger",
    "caution": "Danger",
    # Sprint
    "sprint": "Sprint",
    # Checkpoints (CP / TCP naming used in cycling events)
    "checkpoint": "Checkpoint",
    # cp and tcp are handled by pattern matching in garmin_type_for_name
    # Generic / accommodation / misc
    "camping": "Generic",
    "camp_site": "Generic",
    "camp": "Generic",
    "tent": "Generic",
    "lodging": "Generic",
    "hotel": "Generic",
    "motel": "Generic",
    "hostel": "Generic",
    "parking": "Generic",
    "bike": "Generic",
    "bike repair": "Generic",
    "photo": "Generic",
    "camera": "Generic",
    "waypoint": "Generic",
    "generic": "Generic",
    "info-sign": "Generic",  # app glyphicon name
    "map-marker": "Generic",  # app glyphicon name
    "flash": "Generic",  # app glyphicon name (fuel station icon)
}

# Keyword fragments for greedy fallback (checked after exact match fails).
# Checked in order; first match wins.
_KEYWORD_RULES: list[tuple[str, str]] = [
    ("water", "Water"),
    ("drink", "Water"),
    ("tap", "Water"),
    ("spring", "Water"),
    ("fountain", "Water"),
    ("food", "Food"),
    ("eat", "Food"),
    ("cafe", "Food"),
    ("coffee", "Food"),
    ("restaurant", "Food"),
    ("bar", "Food"),
    ("pub", "Food"),
    ("shop", "Food"),
    ("market", "Food"),
    ("bakery", "Food"),
    ("snack", "Food"),
    ("aid", "First Aid"),
    ("hospital", "First Aid"),
    ("pharmac", "First Aid"),
    ("medical", "First Aid"),
    ("doctor", "First Aid"),
    ("clinic", "First Aid"),
    ("hors", "Hors Category"),
    ("summit", "Summit"),
    ("peak", "Summit"),
    ("valley", "Valley"),
    ("danger", "Danger"),
    ("hazard", "Danger"),
    ("sprint", "Sprint"),
    ("checkpoint", "Checkpoint"),
]


def symbol_to_garmin(symbol: str) -> str:
    """Map a POI symbol to the most appropriate Garmin course point type.

    Tries exact dict lookup, then keyword scan. Returns "Generic" if no match.
    """
    s = (symbol or "").strip().lower()
    if not s:
        return "Generic"
    result = _SYMBOL_TO_GARMIN.get(s)
    if result:
        return result
    for keyword, garmin_type in _KEYWORD_RULES:
        if keyword in s:
            return garmin_type
    return "Generic"


def garmin_type_for_poi(symbol: str, name: str = "") -> str:
    """Return the Garmin course point type for a POI.

    Checks *symbol* first; if that resolves to Generic, checks *name* as a
    fallback so that POIs with an empty symbol but a descriptive name (e.g.
    "Water Tap", "CP3") still get the right type.
    """
    result = symbol_to_garmin(symbol)
    if result == "Generic" and name:
        result = symbol_to_garmin(name)
    return result


def garmin_type_for_name(name: str, fallback: str = "Generic") -> str:
    """Return the Garmin course point type based on course point name.
    
    Maps names containing turn direction keywords to appropriate PointType:
    - "Sharp Left", "Slight Left", "Left", "Turn Left" → "Left"
    - "Sharp Right", "Slight Right", "Right", "Turn Right" → "Right"
    - "Straight", "Continue" → "Straight"
    
    Falls back to keyword matching for POI types, then to *fallback*.
    """
    if not name:
        return fallback

    name_lower = name.lower().strip()

    # Direct turn direction mappings
    turn_mappings = {
        "sharp left": "Left",
        "slight left": "Left",
        "left": "Left",
        "turn left": "Left",
        "sharp right": "Right",
        "slight right": "Right",
        "right": "Right",
        "turn right": "Right",
        "straight": "Straight",
        "continue": "Straight",
    }

    # Check for exact turn direction phrases first
    for phrase, point_type in turn_mappings.items():
        if name_lower == phrase:
            return point_type

    # Check if name starts with turn direction
    for phrase, point_type in turn_mappings.items():
        if name_lower.startswith(phrase):
            return point_type

    # Check for CP/TCP patterns (e.g., "CP", "CP 1", "CP1", "TCP", "TCP 5")
    flat = name_lower.replace(" ", "")
    if flat == "cp" or (flat.startswith("cp") and len(flat) > 2 and flat[2:].isdigit()):
        return "Checkpoint"
    if flat == "tcp" or (flat.startswith("tcp") and len(flat) > 3 and flat[3:].isdigit()):
        return "Checkpoint"

    # Check for POI keywords as fallback
    result = symbol_to_garmin(name)
    return result if result != "Generic" else fallback


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
    "checkpoint": "checkpoint",
    "fourth category": "fourth_category",
    "third category": "third_category",
    "second category": "second_category",
    "first category": "first_category",
    "hors category": "hors_category",
}


def garmin_to_symbol(type_str: str) -> str:
    """Map a Garmin POI type string to a POI symbol. Returns '' for Generic."""
    normalized = (type_str or "").strip().lower()
    
    # Check for exact match first
    symbol = _GARMIN_TO_SYMBOL.get(normalized)
    if symbol is not None:
        return symbol
    
    # Check for CP N pattern (where N is an integer)
    if normalized.startswith("cp ") and normalized[3:].isdigit():
        return "checkpoint"
    
    # Check for TCP N pattern (where N is an integer)
    if normalized.startswith("tcp ") and normalized[4:].isdigit():
        return "checkpoint"
    
    return ""


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
    "Checkpoint": 26,
}

_FIT_TO_GARMIN: dict[int, str] = {v: k for k, v in _GARMIN_TO_FIT.items()}


def garmin_to_fit_int(type_str: str) -> int:
    """Map a Garmin type string (any format) to its FIT enum integer."""
    canonical = to_garmin(type_str, "Generic")
    return _GARMIN_TO_FIT.get(canonical, 0)


def fit_int_to_garmin(fit_value: int) -> str:
    """Map a FIT enum integer to its Garmin type string."""
    return _FIT_TO_GARMIN.get(fit_value, "Generic")
