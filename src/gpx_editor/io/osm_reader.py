"""Query OpenStreetMap via Overpass API and return Polars DataFrames."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

import polars as pl

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_USER_AGENT = "gpx-editor/1.0 (https://github.com/local/gpx_editor)"

# Maximum number of coordinate pairs sent in the around: filter.
# Overpass handles long polylines well via POST, but beyond ~400 pairs
# the query string adds little precision while growing the request.
_MAX_AROUND_PTS = 400

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


def query_osm_pois(
    track_lats: list[float],
    track_lons: list[float],
    tags: list[tuple[str, str]],
    buffer_m: float,
    timeout: int = 60,
) -> pl.DataFrame:
    """
    Query Overpass for nodes/ways within *buffer_m* metres of the track polyline.

    Uses the Overpass ``around:RADIUS,lat,lon,...`` filter, which queries a true
    corridor around the track rather than a bounding box, so dense urban areas
    outside the route corridor are not included.

    Returns a DataFrame with columns: lat, lon, name, description, symbol.
    """
    coords = _downsample_track(track_lats, track_lons)
    coord_str = ",".join(f"{lat},{lon}" for lat, lon in coords)
    around = f"around:{int(buffer_m)},{coord_str}"

    tag_clauses = "".join(
        f'  node["{k}"="{v}"]({around});\n  way["{k}"="{v}"]({around});\n'
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


def _downsample_track(
    lats: list[float],
    lons: list[float],
    max_pts: int = _MAX_AROUND_PTS,
) -> list[tuple[float, float]]:
    """Stride-downsample track coordinates to at most *max_pts* pairs."""
    n = len(lats)
    if n <= max_pts:
        return list(zip(lats, lons))
    step = max(1, n // max_pts)
    indices = list(range(0, n, step))
    if indices[-1] != n - 1:
        indices.append(n - 1)
    return [(lats[i], lons[i]) for i in indices]


def _element_to_row(element: dict, query_tags: list[tuple[str, str]]) -> dict | None:
    t = element.get("tags", {})
    etype = element.get("type", "")

    if etype == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    elif etype == "way":
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
