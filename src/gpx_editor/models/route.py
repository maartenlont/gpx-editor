from dataclasses import dataclass, field
import polars as pl


# Canonical column schemas — used by readers and tests to ensure consistency.
TRACK_POINTS_SCHEMA: dict[str, type] = {
    "index": pl.Int64,
    "lat": pl.Float64,
    "lon": pl.Float64,
    "elevation": pl.Float64,
    "time": pl.Datetime("us", "UTC"),
    "distance": pl.Float64,
    "hr": pl.Int32,
    "cadence": pl.Int32,
    "power": pl.Int32,
}

CUES_SCHEMA: dict[str, type] = {
    "index": pl.Int64,
    "lat": pl.Float64,
    "lon": pl.Float64,
    "name": pl.String,
    "description": pl.String,
    "cue_type": pl.String,
    "distance": pl.Float64,
}

POIS_SCHEMA: dict[str, type] = {
    "index": pl.Int64,
    "lat": pl.Float64,
    "lon": pl.Float64,
    "name": pl.String,
    "description": pl.String,
    "symbol": pl.String,
    "distance": pl.Float64,
}


def empty_track_points() -> pl.DataFrame:
    return pl.DataFrame(schema=TRACK_POINTS_SCHEMA)


def empty_cues() -> pl.DataFrame:
    return pl.DataFrame(schema=CUES_SCHEMA)


def empty_pois() -> pl.DataFrame:
    return pl.DataFrame(schema=POIS_SCHEMA)


@dataclass
class RouteData:
    track_points: pl.DataFrame = field(default_factory=empty_track_points)
    cues: pl.DataFrame = field(default_factory=empty_cues)
    pois: pl.DataFrame = field(default_factory=empty_pois)
    source_file: str = ""
