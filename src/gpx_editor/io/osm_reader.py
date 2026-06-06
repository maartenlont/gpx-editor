"""Query OpenStreetMap via Overpass API and return Polars DataFrames."""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request

import polars as pl

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_USER_AGENT = "gpx-editor/1.0 (https://github.com/local/gpx_editor)"

OSM_CATEGORIES: dict[str, list[tuple[str, str]]] = {
    "Drinking Water":    [("amenity", "drinking_water")],
    "Fuel Station":      [("amenity", "fuel")],
    "Hotel":             [("tourism", "hotel")],
    "Motel":             [("tourism", "motel")],
    "Convenience Store": [("shop", "convenience")],
    "Supermarket":       [("shop", "supermarket")],
    "Restaurant":        [("amenity", "restaurant")],
    "Cafe":              [("amenity", "cafe")],
    "Parking":           [("amenity", "parking")],
    "Campsite":          [("tourism", "camp_site")],
    "Pharmacy":          [("amenity", "pharmacy")],
}

_SYMBOL_MAP: dict[str, str] = {
    "drinking_water": "water",
    "fuel":           "fuel",
    "hotel":          "lodging",
    "motel":          "lodging",
    "convenience":    "convenience",
    "supermarket":    "shopping",
    "restaurant":     "restaurant",
    "cafe":           "cafe",
    "parking":        "parking",
    "camp_site":      "camping",
    "pharmacy":       "pharmacy",
}

_OSM_RESULT_SCHEMA = {
    "lat":         pl.Float64,
    "lon":         pl.Float64,
    "name":        pl.String,
    "description": pl.String,
    "symbol":      pl.String,
}


def track_bbox(
    track_points: pl.DataFrame,
    buffer_m: float,
) -> tuple[float, float, float, float]:
    """Return (south, west, north, east) of the track expanded by buffer_m metres."""
    lats = track_points["lat"]
    lons = track_points["lon"]
    min_lat, max_lat = float(lats.min()), float(lats.max())  # type: ignore[arg-type]
    min_lon, max_lon = float(lons.min()), float(lons.max())  # type: ignore[arg-type]

    lat_deg = buffer_m / 111_000.0
    mid_lat = (min_lat + max_lat) / 2.0
    lon_deg = buffer_m / (111_000.0 * math.cos(math.radians(mid_lat)))

    return (
        min_lat - lat_deg,
        min_lon - lon_deg,
        max_lat + lat_deg,
        max_lon + lon_deg,
    )


def query_osm_pois(
    south: float,
    west: float,
    north: float,
    east: float,
    tags: list[tuple[str, str]],
    timeout: int = 25,
) -> pl.DataFrame:
    """Query Overpass API for nodes/ways matching the given (key, value) tags.

    Returns a DataFrame with columns: lat, lon, name, description, symbol.
    """
    bbox = f"{south},{west},{north},{east}"
    tag_clauses = "".join(
        f'  node["{k}"="{v}"]({bbox});\n  way["{k}"="{v}"]({bbox});\n'
        for k, v in tags
    )
    query = f"[out:json][timeout:{timeout}];\n(\n{tag_clauses});\nout center;"

    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        _OVERPASS_URL,
        data=data,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
        payload = json.loads(resp.read().decode())

    rows: list[dict] = []
    for element in payload.get("elements", []):
        row = _element_to_row(element, tags)
        if row is not None:
            rows.append(row)

    if not rows:
        return pl.DataFrame(schema=_OSM_RESULT_SCHEMA)

    return pl.DataFrame(rows, schema=_OSM_RESULT_SCHEMA)


def _element_to_row(element: dict, query_tags: list[tuple[str, str]]) -> dict | None:
    t = element.get("tags", {})
    etype = element.get("type", "")

    if etype == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    elif etype == "way":
        # "out center" puts centroid in element["center"]
        center = element.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")
    else:
        return None

    if lat is None or lon is None:
        return None

    name = t.get("name") or t.get("ref") or ""
    description = t.get("description") or t.get("opening_hours") or ""
    symbol = _resolve_symbol(t, query_tags)

    return {
        "lat":         float(lat),
        "lon":         float(lon),
        "name":        name,
        "description": description,
        "symbol":      symbol,
    }


def _resolve_symbol(osm_tags: dict, query_tags: list[tuple[str, str]]) -> str:
    for key, value in query_tags:
        if osm_tags.get(key) == value:
            return _SYMBOL_MAP.get(value, value)
    return "generic"
