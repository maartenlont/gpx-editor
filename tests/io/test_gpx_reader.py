import pytest
import polars as pl
from gpx_editor.io.gpx_reader import read_gpx_string
from tests.conftest import (
    SAMPLE_GPX,
    SAMPLE_GPX_WITH_EXTENSIONS,
    SAMPLE_GPX_NO_WAYPOINTS,
    SAMPLE_GPX_MINIMAL,
)


class TestTrackPoints:
    def test_count(self):
        route = read_gpx_string(SAMPLE_GPX)
        assert len(route.track_points) == 4

    def test_columns_present(self):
        route = read_gpx_string(SAMPLE_GPX)
        expected = {"index", "lat", "lon", "elevation", "time", "distance", "hr", "cadence", "power"}
        assert expected.issubset(set(route.track_points.columns))

    def test_first_point_coords(self):
        route = read_gpx_string(SAMPLE_GPX)
        row = route.track_points.row(0, named=True)
        assert row["lat"] == pytest.approx(52.3700)
        assert row["lon"] == pytest.approx(4.8950)

    def test_elevation_parsed(self):
        route = read_gpx_string(SAMPLE_GPX)
        elevations = route.track_points["elevation"].to_list()
        assert elevations[0] == pytest.approx(5.0)
        assert elevations[2] == pytest.approx(6.0)

    def test_time_parsed(self):
        route = read_gpx_string(SAMPLE_GPX)
        t = route.track_points["time"][0]
        assert t is not None
        assert t.year == 2024

    def test_distance_starts_at_zero(self):
        route = read_gpx_string(SAMPLE_GPX)
        assert route.track_points["distance"][0] == pytest.approx(0.0)

    def test_distance_monotonically_increasing(self):
        route = read_gpx_string(SAMPLE_GPX)
        dists = route.track_points["distance"].to_list()
        assert all(dists[i] < dists[i + 1] for i in range(len(dists) - 1))

    def test_distance_reasonable_magnitude(self):
        # 4 points separated by ~10 m each → total should be in range 30–150 m
        route = read_gpx_string(SAMPLE_GPX)
        total = route.track_points["distance"][-1]
        assert 20 < total < 200

    def test_missing_elevation_is_null(self):
        route = read_gpx_string(SAMPLE_GPX_MINIMAL)
        assert route.track_points["elevation"].is_null().all()

    def test_missing_time_is_null(self):
        route = read_gpx_string(SAMPLE_GPX_MINIMAL)
        assert route.track_points["time"].is_null().all()

    def test_hr_and_cadence_parsed_from_extensions(self):
        route = read_gpx_string(SAMPLE_GPX_WITH_EXTENSIONS)
        assert route.track_points["hr"][0] == 145
        assert route.track_points["cadence"][0] == 90
        assert route.track_points["hr"][1] == 148
        assert route.track_points["cadence"][1] == 92

    def test_no_extensions_gives_null_hr(self):
        route = read_gpx_string(SAMPLE_GPX)
        assert route.track_points["hr"].is_null().all()


class TestCues:
    def test_one_cue_found(self):
        route = read_gpx_string(SAMPLE_GPX)
        assert len(route.cues) == 1

    def test_cue_name(self):
        route = read_gpx_string(SAMPLE_GPX)
        assert route.cues["name"][0] == "Turn Left"

    def test_cue_type(self):
        route = read_gpx_string(SAMPLE_GPX)
        assert route.cues["cue_type"][0] == "Left"

    def test_cue_description(self):
        route = read_gpx_string(SAMPLE_GPX)
        assert route.cues["description"][0] == "Sharp corner"

    def test_cue_coords(self):
        route = read_gpx_string(SAMPLE_GPX)
        assert route.cues["lat"][0] == pytest.approx(52.3702)
        assert route.cues["lon"][0] == pytest.approx(4.8952)

    def test_cue_distance_snapped_to_nearest_track_point(self):
        route = read_gpx_string(SAMPLE_GPX)
        # cue at (52.3702, 4.8952) matches track point index 2 exactly
        tp_dist = route.track_points.filter(pl.col("index") == 2)["distance"][0]
        assert route.cues["distance"][0] == pytest.approx(tp_dist)

    def test_no_cues_when_no_waypoints(self):
        route = read_gpx_string(SAMPLE_GPX_NO_WAYPOINTS)
        assert len(route.cues) == 0

    def test_cues_schema(self):
        route = read_gpx_string(SAMPLE_GPX)
        assert route.cues.schema["lat"] == pl.Float64
        assert route.cues.schema["distance"] == pl.Float64


class TestPOIs:
    def test_one_poi_found(self):
        route = read_gpx_string(SAMPLE_GPX)
        assert len(route.pois) == 1

    def test_poi_name(self):
        route = read_gpx_string(SAMPLE_GPX)
        assert route.pois["name"][0] == "Coffee stop"

    def test_poi_symbol(self):
        route = read_gpx_string(SAMPLE_GPX)
        assert route.pois["symbol"][0] == "Coffee"

    def test_no_pois_when_no_waypoints(self):
        route = read_gpx_string(SAMPLE_GPX_NO_WAYPOINTS)
        assert len(route.pois) == 0
