"""Parse a TCX file into a RouteData (three Polars DataFrames)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import polars as pl

from gpx_editor.io._distance import cumulative_distance, nearest_index
from gpx_editor.models.route import RouteData

_NS = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"

# TCX CoursePoint PointTypes that map to cues (everything else → POI / Generic)
_CUE_POINT_TYPES = {
    "Left", "Right", "Straight", "SlightLeft", "SlightRight",
    "SharpLeft", "SharpRight", "UTurn", "BearLeft", "BearRight",
    "Fork Left", "Fork Right", "Roundabout",
}


def _t(local: str) -> str:
    return f"{{{_NS}}}{local}"


def _text(el: ET.Element, *path: str) -> Optional[str]:
    node = el
    for part in path:
        node = node.find(_t(part))
        if node is None:
            return None
    return node.text


def _parse_time(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    text = text.rstrip("Z")
    try:
        return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _is_cue(point_type: Optional[str]) -> bool:
    if not point_type:
        return False
    return point_type.strip() in _CUE_POINT_TYPES


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_tcx(path: str | Path) -> RouteData:
    """Parse a TCX file and return a RouteData."""
    tree = ET.parse(path)
    root = tree.getroot()
    track_points = _parse_track_points(root)
    cues, pois = _parse_course_points(root, track_points)
    return RouteData(
        track_points=track_points,
        cues=cues,
        pois=pois,
        source_file=str(path),
    )


def read_tcx_string(xml: str) -> RouteData:
    root = ET.fromstring(xml)
    track_points = _parse_track_points(root)
    cues, pois = _parse_course_points(root, track_points)
    return RouteData(track_points=track_points, cues=cues, pois=pois)


# ---------------------------------------------------------------------------
# Internal parsers
# ---------------------------------------------------------------------------

def _parse_track_points(root: ET.Element) -> pl.DataFrame:
    rows: list[dict] = []
    idx = 0

    # TCX can be Activity or Course; both contain <Track>/<Trackpoint>
    for trackpoint in root.iter(_t("Trackpoint")):
        pos = trackpoint.find(_t("Position"))
        if pos is None:
            continue
        lat_text = _text(pos, "LatitudeDegrees")
        lon_text = _text(pos, "LongitudeDegrees")
        if lat_text is None or lon_text is None:
            continue

        lat = float(lat_text)
        lon = float(lon_text)
        ele_text = _text(trackpoint, "AltitudeMeters")
        time_text = _text(trackpoint, "Time")

        hr_el = trackpoint.find(_t("HeartRateBpm"))
        hr = None
        if hr_el is not None:
            hr_text = _text(hr_el, "Value")
            hr = int(hr_text) if hr_text else None

        cad_text = _text(trackpoint, "Cadence")
        cadence = int(cad_text) if cad_text else None

        # Power is in extensions (Garmin TPX)
        power = None
        ext = trackpoint.find(_t("Extensions"))
        if ext is not None:
            for child in ext:
                pw = child.find("{http://www.garmin.com/xmlschemas/ActivityExtension/v2}Watts")
                if pw is not None and pw.text:
                    power = int(float(pw.text))

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


def _parse_course_points(
    root: ET.Element, track_points: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame]:
    from gpx_editor.models.route import empty_cues, empty_pois

    track_lats = track_points["lat"].to_numpy() if len(track_points) > 0 else np.array([])
    track_lons = track_points["lon"].to_numpy() if len(track_points) > 0 else np.array([])
    track_dists = track_points["distance"].to_numpy() if len(track_points) > 0 else np.array([])

    cue_rows: list[dict] = []
    poi_rows: list[dict] = []

    for cp in root.iter(_t("CoursePoint")):
        pos = cp.find(_t("Position"))
        if pos is None:
            continue
        lat_text = _text(pos, "LatitudeDegrees")
        lon_text = _text(pos, "LongitudeDegrees")
        if lat_text is None or lon_text is None:
            continue

        lat = float(lat_text)
        lon = float(lon_text)
        name = _text(cp, "Name") or ""
        notes = _text(cp, "Notes") or ""
        point_type = _text(cp, "PointType") or "Generic"

        if len(track_lats) > 0:
            snap_idx, _ = nearest_index(lat, lon, track_lats, track_lons)
            dist = float(track_dists[snap_idx])
        else:
            dist = 0.0

        if _is_cue(point_type):
            cue_rows.append({
                "index": len(cue_rows),
                "lat": lat,
                "lon": lon,
                "name": name,
                "description": notes,
                "cue_type": point_type,
                "distance": dist,
            })
        else:
            poi_rows.append({
                "index": len(poi_rows),
                "lat": lat,
                "lon": lon,
                "name": name,
                "description": notes,
                "symbol": point_type,
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
