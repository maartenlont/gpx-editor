"""Copy cues and POIs from a source route into a target route by proximity."""

from __future__ import annotations

import numpy as np
import polars as pl

from gpx_editor.io._distance import nearest_index
from gpx_editor.models.route import RouteData, empty_cues, empty_pois


def copy_cues_pois(
    source: RouteData,
    target: RouteData,
    threshold_m: float = 10.0,
) -> RouteData:
    """Return a new RouteData with cues/POIs from *source* merged into *target*.

    For each cue/POI in *source*, the nearest track point in *target* is found.
    If that distance is ≤ *threshold_m*, the item is copied with lat/lon/distance
    snapped to that track point.  The result is sorted by distance and re-indexed.

    Neither *source* nor *target* is mutated.
    """
    if len(target.track_points) == 0:
        return RouteData(
            track_points=target.track_points,
            cues=target.cues,
            pois=target.pois,
            source_file=target.source_file,
        )

    t_lats = target.track_points["lat"].to_numpy()
    t_lons = target.track_points["lon"].to_numpy()
    t_dists = target.track_points["distance"].to_numpy()

    copied_cues = _filter_and_snap(source.cues, t_lats, t_lons, t_dists, threshold_m, empty_cues)
    copied_pois = _filter_and_snap(source.pois, t_lats, t_lons, t_dists, threshold_m, empty_pois)

    return RouteData(
        track_points=target.track_points,
        cues=_combine(target.cues, copied_cues),
        pois=_combine(target.pois, copied_pois),
        source_file=target.source_file,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _filter_and_snap(
    waypoints: pl.DataFrame,
    t_lats: np.ndarray,
    t_lons: np.ndarray,
    t_dists: np.ndarray,
    threshold_m: float,
    empty_factory,
) -> pl.DataFrame:
    """Return rows of *waypoints* that are within *threshold_m* of a target track
    point, with lat/lon/distance replaced by the snapped track-point values."""
    if len(waypoints) == 0:
        return empty_factory()

    kept: list[dict] = []
    for row in waypoints.iter_rows(named=True):
        snap_idx, dist_m = nearest_index(row["lat"], row["lon"], t_lats, t_lons)
        if dist_m <= threshold_m:
            new_row = dict(row)
            new_row["lat"] = float(t_lats[snap_idx])
            new_row["lon"] = float(t_lons[snap_idx])
            new_row["distance"] = float(t_dists[snap_idx])
            kept.append(new_row)

    if not kept:
        return empty_factory()

    return pl.DataFrame(kept, schema=waypoints.schema)


def _combine(existing: pl.DataFrame, new: pl.DataFrame) -> pl.DataFrame:
    """Concatenate *existing* and *new*, sort by distance, and reset index."""
    if len(new) == 0:
        return existing
    combined = pl.concat([existing, new]) if len(existing) > 0 else new
    combined = combined.sort("distance")
    combined = combined.with_columns(
        pl.Series("index", list(range(len(combined))), dtype=pl.Int64)
    )
    return combined
