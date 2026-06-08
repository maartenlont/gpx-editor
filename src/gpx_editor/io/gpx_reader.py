"""Parse a GPX file into a RouteData (three Polars DataFrames)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl

from gpx_editor.io._course_point_types import garmin_to_symbol, is_nav_type, to_garmin
from gpx_editor.io._distance import cumulative_distance, nearest_index
from gpx_editor.models.route import RouteData

# ---------------------------------------------------------------------------
# XML namespaces
# ---------------------------------------------------------------------------
_NS = {
    "gpx": "http://www.topografix.com/GPX/1/1",
    "gpxtpx": "http://www.garmin.com/xmlschemas/TrackPointExtension/v1",
    "gpxx": "http://www.garmin.com/xmlschemas/GpxExtensions/v3",
}


def _tag(ns_key: str, local: str) -> str:
    return f"{{{_NS[ns_key]}}}{local}"


def _find_text(el: ET.Element, *path: str, ns: str = "gpx") -> str | None:
    """Walk a dotted path under *el* using the given namespace prefix."""
    node = el
    for part in path:
        node = node.find(_tag(ns, part))
        if node is None:
            return None
    return node.text


def _parse_time(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.rstrip("Z")
    try:
        return datetime.fromisoformat(text).replace(tzinfo=UTC)
    except ValueError:
        return None


def _is_cue_type(type_text: str | None) -> bool:
    return is_nav_type(type_text or "")


def _garmin_categories(wpt: ET.Element) -> list[str]:
    """Return Garmin WaypointExtension category strings, if present."""
    ext = wpt.find(_tag("gpx", "extensions"))
    if ext is None:
        return []
    wext = ext.find(_tag("gpxx", "WaypointExtension"))
    if wext is None:
        return []
    cats = wext.find(_tag("gpxx", "Categories"))
    if cats is None or not cats.text:
        return []
    return [c.strip() for c in cats.text.split(";") if c.strip()]


def _classify_wpt(wpt: ET.Element) -> str:
    """Return 'cue', 'poi', based on type field and Garmin extensions."""
    type_text = _find_text(wpt, "type")
    if _is_cue_type(type_text):
        return "cue"
    # Check Garmin extension categories
    for cat in _garmin_categories(wpt):
        if _is_cue_type(cat):
            return "cue"
    return "poi"


def _trkpt_extensions(trkpt: ET.Element) -> tuple[int | None, int | None, int | None]:
    """Return (hr, cadence, power) from Garmin TrackPointExtension."""
    ext = trkpt.find(_tag("gpx", "extensions"))
    if ext is None:
        return None, None, None
    tpe = ext.find(_tag("gpxtpx", "TrackPointExtension"))
    if tpe is None:
        return None, None, None

    def _int(tag: str) -> int | None:
        el = tpe.find(_tag("gpxtpx", tag))
        try:
            return int(el.text) if el is not None and el.text else None
        except (ValueError, TypeError):
            return None

    return _int("hr"), _int("cad"), _int("power")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_gpx(path: str | Path) -> RouteData:
    """Parse a GPX file and return a RouteData."""
    tree = ET.parse(path)
    root = tree.getroot()

    # Strip namespace from root tag for version detection (not strictly needed)
    track_points = _parse_track_points(root)
    cues, pois = _parse_waypoints(root, track_points)

    return RouteData(
        track_points=track_points,
        cues=cues,
        pois=pois,
        source_file=str(path),
    )


def read_gpx_string(xml: str) -> RouteData:
    """Parse a GPX XML string and return a RouteData (useful for tests)."""
    root = ET.fromstring(xml)
    track_points = _parse_track_points(root)
    cues, pois = _parse_waypoints(root, track_points)
    return RouteData(track_points=track_points, cues=cues, pois=pois)


# ---------------------------------------------------------------------------
# Internal parsers
# ---------------------------------------------------------------------------

def _parse_track_points(root: ET.Element) -> pl.DataFrame:
    rows: list[dict] = []
    idx = 0
    for trk in root.findall(_tag("gpx", "trk")):
        for trkseg in trk.findall(_tag("gpx", "trkseg")):
            for trkpt in trkseg.findall(_tag("gpx", "trkpt")):
                lat = float(trkpt.attrib["lat"])
                lon = float(trkpt.attrib["lon"])
                ele_text = _find_text(trkpt, "ele")
                time_text = _find_text(trkpt, "time")
                hr, cadence, power = _trkpt_extensions(trkpt)
                rows.append({
                    "index": idx,
                    "lat": lat,
                    "lon": lon,
                    "elevation": float(ele_text) if ele_text is not None else None,
                    "time": _parse_time(time_text),
                    "hr": hr,
                    "cadence": cadence,
                    "power": power,
                })
                idx += 1

    if not rows:
        from gpx_editor.models.route import empty_track_points
        return empty_track_points()

    lats = np.array([r["lat"] for r in rows])
    lons = np.array([r["lon"] for r in rows])
    distances = cumulative_distance(lats, lons)
    for i, r in enumerate(rows):
        r["distance"] = float(distances[i])

    return pl.DataFrame(rows, schema={
        "index": pl.Int64,
        "lat": pl.Float64,
        "lon": pl.Float64,
        "elevation": pl.Float64,
        "time": pl.Datetime("us", "UTC"),
        "distance": pl.Float64,
        "hr": pl.Int32,
        "cadence": pl.Int32,
        "power": pl.Int32,
    })


def _parse_waypoints(
    root: ET.Element, track_points: pl.DataFrame,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    from gpx_editor.models.route import empty_cues, empty_pois

    track_lats = track_points["lat"].to_numpy() if len(track_points) > 0 else np.array([])
    track_lons = track_points["lon"].to_numpy() if len(track_points) > 0 else np.array([])
    track_dists = track_points["distance"].to_numpy() if len(track_points) > 0 else np.array([])

    cue_rows: list[dict] = []
    poi_rows: list[dict] = []

    for wpt in root.findall(_tag("gpx", "wpt")):
        lat = float(wpt.attrib["lat"])
        lon = float(wpt.attrib["lon"])
        name = _find_text(wpt, "name") or ""
        desc = _find_text(wpt, "desc") or ""
        sym = _find_text(wpt, "sym") or ""
        type_text = _find_text(wpt, "type") or ""

        # Snap to nearest track point for distance
        if len(track_lats) > 0:
            snap_idx, _ = nearest_index(lat, lon, track_lats, track_lons)
            dist = float(track_dists[snap_idx])
        else:
            dist = 0.0

        kind = _classify_wpt(wpt)
        if kind == "cue":
            cue_rows.append({
                "index": len(cue_rows),
                "lat": lat,
                "lon": lon,
                "name": name,
                "description": desc,
                "cue_type": to_garmin(type_text, type_text),
                "distance": dist,
            })
        else:
            # If <sym> is absent, derive a symbol from the Garmin <type> string.
            resolved_sym = sym or garmin_to_symbol(type_text)
            poi_rows.append({
                "index": len(poi_rows),
                "lat": lat,
                "lon": lon,
                "name": name,
                "description": desc,
                "symbol": resolved_sym,
                "distance": dist,
            })

    cues = pl.DataFrame(cue_rows, schema={
        "index": pl.Int64,
        "lat": pl.Float64,
        "lon": pl.Float64,
        "name": pl.String,
        "description": pl.String,
        "cue_type": pl.String,
        "distance": pl.Float64,
    }) if cue_rows else empty_cues()

    pois = pl.DataFrame(poi_rows, schema={
        "index": pl.Int64,
        "lat": pl.Float64,
        "lon": pl.Float64,
        "name": pl.String,
        "description": pl.String,
        "symbol": pl.String,
        "distance": pl.Float64,
    }) if poi_rows else empty_pois()

    return cues, pois
