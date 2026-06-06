import polars as pl
from gpx_editor.models.route import (
    RouteData,
    empty_track_points,
    empty_cues,
    empty_pois,
    TRACK_POINTS_SCHEMA,
    CUES_SCHEMA,
    POIS_SCHEMA,
)


def test_empty_track_points_has_correct_schema():
    df = empty_track_points()
    assert len(df) == 0
    for col, dtype in TRACK_POINTS_SCHEMA.items():
        assert col in df.columns
        assert df.schema[col] == dtype


def test_empty_cues_has_correct_schema():
    df = empty_cues()
    assert len(df) == 0
    for col, dtype in CUES_SCHEMA.items():
        assert col in df.columns


def test_empty_pois_has_correct_schema():
    df = empty_pois()
    assert len(df) == 0
    for col, dtype in POIS_SCHEMA.items():
        assert col in df.columns


def test_route_data_defaults_to_empty_frames():
    route = RouteData()
    assert len(route.track_points) == 0
    assert len(route.cues) == 0
    assert len(route.pois) == 0
    assert route.source_file == ""


def test_route_data_source_file():
    route = RouteData(source_file="/tmp/test.gpx")
    assert route.source_file == "/tmp/test.gpx"


def test_route_data_accepts_dataframes():
    tp = empty_track_points()
    cues = empty_cues()
    pois = empty_pois()
    route = RouteData(track_points=tp, cues=cues, pois=pois)
    assert isinstance(route.track_points, pl.DataFrame)
    assert isinstance(route.cues, pl.DataFrame)
    assert isinstance(route.pois, pl.DataFrame)
