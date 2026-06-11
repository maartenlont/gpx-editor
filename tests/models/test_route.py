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


def _make_track(points: list[tuple[float, float]]) -> pl.DataFrame:
    """Build minimal track_points DataFrame from (lat, lon) tuples."""
    return pl.DataFrame([
        {"index": i, "lat": lat, "lon": lon, "elevation": 0.0,
         "time": None, "distance": 0.0, "hr": None, "cadence": None, "power": None}
        for i, (lat, lon) in enumerate(points)
    ], schema=TRACK_POINTS_SCHEMA)


class TestRouteDataHash:
    def test_empty_routes_have_same_hash(self):
        r1 = RouteData()
        r2 = RouteData()
        assert hash(r1) == hash(r2)
        assert r1 == r2

    def test_routes_with_same_track_have_same_hash(self):
        tp = _make_track([(52.0, 4.0), (52.1, 4.1)])
        r1 = RouteData(track_points=tp)
        r2 = RouteData(track_points=tp.clone())
        assert hash(r1) == hash(r2)
        assert r1 == r2

    def test_routes_with_different_tracks_have_different_hash(self):
        r1 = RouteData(track_points=_make_track([(52.0, 4.0)]))
        r2 = RouteData(track_points=_make_track([(53.0, 5.0)]))
        assert hash(r1) != hash(r2)
        assert r1 != r2

    def test_different_cues_same_track_have_same_hash(self):
        """Hash ignores cues - only track_points matter."""
        tp = _make_track([(52.0, 4.0)])
        cue1 = pl.DataFrame([{"index": 0, "lat": 52.0, "lon": 4.0,
            "name": "A", "description": "", "cue_type": "Left", "distance": 0.0}],
            schema=CUES_SCHEMA)
        cue2 = pl.DataFrame([{"index": 0, "lat": 52.0, "lon": 4.0,
            "name": "B", "description": "", "cue_type": "Right", "distance": 0.0}],
            schema=CUES_SCHEMA)
        r1 = RouteData(track_points=tp, cues=cue1)
        r2 = RouteData(track_points=tp.clone(), cues=cue2)
        assert hash(r1) == hash(r2)
        assert r1 == r2

    def test_route_is_hashable_for_set(self):
        """Routes can be used in sets."""
        r1 = RouteData(track_points=_make_track([(52.0, 4.0)]))
        r2 = RouteData(track_points=_make_track([(52.0, 4.0)]))
        r3 = RouteData(track_points=_make_track([(53.0, 5.0)]))
        s = {r1, r2, r3}
        assert len(s) == 2  # r1 and r2 have same hash

    def test_ne_returns_true_for_different_tracks(self):
        r1 = RouteData(track_points=_make_track([(52.0, 4.0)]))
        r2 = RouteData(track_points=_make_track([(53.0, 5.0)]))
        assert r1 != r2

    def test_eq_returns_notimplemented_for_non_route(self):
        r = RouteData()
        assert r.__eq__("not a route") is NotImplemented
        assert r.__ne__("not a route") is NotImplemented
