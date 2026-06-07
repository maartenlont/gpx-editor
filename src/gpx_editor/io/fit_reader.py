"""Parse a FIT file into a RouteData (three Polars DataFrames)."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import fitparse
import numpy as np
import polars as pl

from gpx_editor.io._course_point_types import is_nav_type, to_garmin
from gpx_editor.io._distance import cumulative_distance, nearest_index
from gpx_editor.models.route import RouteData

# fitparse returns lat/lon in raw FIT semicircles (sint32); convert to degrees.
_SC_TO_DEG = 180.0 / (2**31)


def read_fit(path: str | Path) -> RouteData:
    """Parse a FIT file and return a RouteData."""
    fitfile = fitparse.FitFile(str(path))
    track_points = _parse_records(fitfile)
    cues, pois = _parse_course_points(fitfile, track_points)
    return RouteData(
        track_points=track_points,
        cues=cues,
        pois=pois,
        source_file=str(path),
    ).deduplicate().fix_symbols()


def _parse_records(fitfile: fitparse.FitFile) -> pl.DataFrame:
    rows: list[dict] = []
    idx = 0
    for msg in fitfile.get_messages("record"):
        d = {f.name: f.value for f in msg}
        lat_sc = d.get("position_lat")
        lon_sc = d.get("position_long")
        if lat_sc is None or lon_sc is None:
            continue

        lat = float(lat_sc) * _SC_TO_DEG
        lon = float(lon_sc) * _SC_TO_DEG

        # enhanced_altitude (uint32) preferred over altitude (uint16)
        ele = d.get("enhanced_altitude") or d.get("altitude")

        ts = d.get("timestamp")
        if ts is not None and ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        hr = d.get("heart_rate")
        cadence = d.get("cadence")
        power = d.get("power")

        rows.append({
            "index": idx,
            "lat": lat,
            "lon": lon,
            "elevation": float(ele) if ele is not None else None,
            "time": ts,
            "hr": int(hr) if hr is not None else None,
            "cadence": int(cadence) if cadence is not None else None,
            "power": int(power) if power is not None else None,
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
    fitfile: fitparse.FitFile, track_points: pl.DataFrame,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    from gpx_editor.models.route import empty_cues, empty_pois

    track_lats = track_points["lat"].to_numpy() if len(track_points) > 0 else np.array([])
    track_lons = track_points["lon"].to_numpy() if len(track_points) > 0 else np.array([])
    track_dists = track_points["distance"].to_numpy() if len(track_points) > 0 else np.array([])

    cue_rows: list[dict] = []
    poi_rows: list[dict] = []

    for msg in fitfile.get_messages("course_point"):
        d = {f.name: f.value for f in msg}
        lat_sc = d.get("position_lat")
        lon_sc = d.get("position_long")
        if lat_sc is None or lon_sc is None:
            continue

        lat = float(lat_sc) * _SC_TO_DEG
        lon = float(lon_sc) * _SC_TO_DEG
        name = str(d.get("name") or "")
        # fitparse returns snake_case enum names; normalise to Garmin title-case.
        raw_type = str(d.get("type") or "generic")
        canonical = to_garmin(raw_type, "Generic")

        if len(track_lats) > 0:
            snap_idx, _ = nearest_index(lat, lon, track_lats, track_lons)
            dist = float(track_dists[snap_idx])
        else:
            dist = 0.0

        if is_nav_type(raw_type):
            cue_rows.append({
                "index": len(cue_rows),
                "lat": lat,
                "lon": lon,
                "name": name,
                "description": "",
                "cue_type": canonical,
                "distance": dist,
            })
        else:
            from gpx_editor.io._course_point_types import garmin_to_symbol
            poi_rows.append({
                "index": len(poi_rows),
                "lat": lat,
                "lon": lon,
                "name": name,
                "description": "",
                "symbol": garmin_to_symbol(raw_type),
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
