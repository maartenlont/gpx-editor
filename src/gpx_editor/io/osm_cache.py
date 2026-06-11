"""Persistent per-route cache for OSM POI query results.

Directory layout (default: ~/.cache/gpx_editor/)::

    cache_table.csv              # index: route_hash, poi_type, radius_m
    <hash>_<type_safe>.csv       # POI data for one (route, category) pair
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import polars as pl

from gpx_editor.models.route import RouteData

_TABLE_FILE = "cache_table.csv"
_TABLE_SCHEMA = {
    "route_hash": pl.String,
    "poi_type":   pl.String,
    "radius_m":   pl.Float64,
}
_DATA_SCHEMA = {
    "lat":         pl.Float64,
    "lon":         pl.Float64,
    "name":        pl.String,
    "description": pl.String,
    "symbol":      pl.String,
}

# Default location: ~/.cache/gpx_editor/
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "gpx_editor"


def route_hash(route: RouteData) -> str:
    """Return a 16-char hex string that stably identifies *route*'s track geometry."""
    tp = route.track_points
    if len(tp) == 0:
        return "empty_route_0000"
    n = len(tp)
    step = max(1, n // 200)
    lats = tp["lat"][::step].to_list()
    lons = tp["lon"][::step].to_list()
    data = "".join(f"{la:.5f},{lo:.5f};" for la, lo in zip(lats, lons))
    return hashlib.md5(data.encode()).hexdigest()[:16]  # noqa: S324


def _safe_name(poi_type: str) -> str:
    """Sanitise *poi_type* so it can be used as part of a file name."""
    return poi_type.replace(" ", "_").replace("/", "_").replace("\\", "_")


class OsmCache:
    """Persistent per-route cache for OSM POI query results.

    The in-memory table maps (route_hash, poi_type) → radius_m.
    Each entry's POI data is stored in a separate CSV file.
    """

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
        self._dir = cache_dir
        self._table: dict[tuple[str, str], float] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, r_hash: str, poi_type: str) -> tuple[float, pl.DataFrame] | None:
        """Return *(cached_radius_m, df)* or *None* if no entry exists."""
        key = (r_hash, poi_type)
        if key not in self._table:
            return None
        path = self._data_path(r_hash, poi_type)
        if not path.exists():
            # Stale table entry without its data file — clean up.
            del self._table[key]
            self._save_table()
            return None
        try:
            df = pl.read_csv(path, schema_overrides=_DATA_SCHEMA)
        except Exception:  # noqa: BLE001
            return None
        return self._table[key], df

    def put(
        self, r_hash: str, poi_type: str, radius_m: float, df: pl.DataFrame,
    ) -> None:
        """Store *df* as the cache entry for *(r_hash, poi_type)* at *radius_m*."""
        self._dir.mkdir(parents=True, exist_ok=True)
        df.write_csv(self._data_path(r_hash, poi_type))
        self._table[(r_hash, poi_type)] = radius_m
        self._save_table()

    def entries_for_route(self, r_hash: str) -> list[tuple[str, float]]:
        """Return a sorted list of *(poi_type, radius_m)* for *r_hash*."""
        return sorted(
            [(pt, r) for (rh, pt), r in self._table.items() if rh == r_hash],
            key=lambda t: t[0],
        )

    def clear_route(self, r_hash: str) -> None:
        """Delete all entries (table row + data file) for *r_hash*."""
        keys = [(rh, pt) for rh, pt in list(self._table) if rh == r_hash]
        for key in keys:
            self._data_path(key[0], key[1]).unlink(missing_ok=True)
            del self._table[key]
        self._save_table()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _data_path(self, r_hash: str, poi_type: str) -> Path:
        return self._dir / f"{r_hash}_{_safe_name(poi_type)}.csv"

    def _load(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        table_path = self._dir / _TABLE_FILE
        if not table_path.exists():
            return
        try:
            df = pl.read_csv(table_path, schema_overrides=_TABLE_SCHEMA)
            for row in df.iter_rows(named=True):
                self._table[(row["route_hash"], row["poi_type"])] = float(row["radius_m"])
        except Exception:  # noqa: BLE001
            pass  # corrupt table → start fresh

    def _save_table(self) -> None:
        rows = [
            {"route_hash": rh, "poi_type": pt, "radius_m": r}
            for (rh, pt), r in self._table.items()
        ]
        df = pl.DataFrame(rows or [{"route_hash": "", "poi_type": "", "radius_m": 0.0}][:0],
                          schema=_TABLE_SCHEMA)
        if not rows:
            df = pl.DataFrame(schema=_TABLE_SCHEMA)
        df.write_csv(self._dir / _TABLE_FILE)
