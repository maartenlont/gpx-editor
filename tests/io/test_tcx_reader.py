import pytest
import polars as pl
from gpx_editor.io.tcx_reader import read_tcx_string
from tests.conftest import SAMPLE_TCX, SAMPLE_TCX_NO_COURSE_POINTS


class TestTrackPoints:
    def test_count(self):
        route = read_tcx_string(SAMPLE_TCX)
        assert len(route.track_points) == 4

    def test_coords(self):
        route = read_tcx_string(SAMPLE_TCX)
        row = route.track_points.row(0, named=True)
        assert row["lat"] == pytest.approx(52.3700)
        assert row["lon"] == pytest.approx(4.8950)

    def test_elevation_parsed(self):
        route = read_tcx_string(SAMPLE_TCX)
        assert route.track_points["elevation"][0] == pytest.approx(5.0)

    def test_time_parsed(self):
        route = read_tcx_string(SAMPLE_TCX)
        assert route.track_points["time"][0].year == 2024

    def test_hr_parsed(self):
        route = read_tcx_string(SAMPLE_TCX)
        assert route.track_points["hr"][0] == 140
        assert route.track_points["hr"][1] == 142

    def test_cadence_parsed(self):
        route = read_tcx_string(SAMPLE_TCX)
        assert route.track_points["cadence"][0] == 88
        assert route.track_points["cadence"][1] == 89

    def test_missing_cadence_is_null(self):
        route = read_tcx_string(SAMPLE_TCX)
        # 3rd and 4th points have no cadence
        assert route.track_points["cadence"][2] is None

    def test_distance_starts_at_zero(self):
        route = read_tcx_string(SAMPLE_TCX)
        assert route.track_points["distance"][0] == pytest.approx(0.0)

    def test_distance_monotonically_increasing(self):
        route = read_tcx_string(SAMPLE_TCX)
        dists = route.track_points["distance"].to_list()
        assert all(dists[i] < dists[i + 1] for i in range(len(dists) - 1))


class TestCues:
    def test_one_cue_found(self):
        route = read_tcx_string(SAMPLE_TCX)
        assert len(route.cues) == 1

    def test_cue_name(self):
        route = read_tcx_string(SAMPLE_TCX)
        assert route.cues["name"][0] == "Turn Right"

    def test_cue_type(self):
        route = read_tcx_string(SAMPLE_TCX)
        assert route.cues["cue_type"][0] == "Right"

    def test_cue_notes(self):
        route = read_tcx_string(SAMPLE_TCX)
        assert route.cues["description"][0] == "Go right here"

    def test_no_cues_when_no_course_points(self):
        route = read_tcx_string(SAMPLE_TCX_NO_COURSE_POINTS)
        assert len(route.cues) == 0


class TestPOIs:
    def test_one_poi_found(self):
        route = read_tcx_string(SAMPLE_TCX)
        assert len(route.pois) == 1

    def test_poi_name(self):
        route = read_tcx_string(SAMPLE_TCX)
        assert route.pois["name"][0] == "Water fountain"

    def test_poi_symbol_is_empty_for_generic(self):
        route = read_tcx_string(SAMPLE_TCX)
        assert route.pois["symbol"][0] == ""

    def test_no_pois_when_no_course_points(self):
        route = read_tcx_string(SAMPLE_TCX_NO_COURSE_POINTS)
        assert len(route.pois) == 0
