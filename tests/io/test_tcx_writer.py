"""Round-trip tests: read TCX → write → read back and compare."""

import pytest
from gpx_editor.io.tcx_reader import read_tcx, read_tcx_string
from gpx_editor.io.tcx_writer import write_tcx
from tests.conftest import SAMPLE_TCX, SAMPLE_TCX_NO_COURSE_POINTS


def _round_trip(xml: str, tmp_path):
    original = read_tcx_string(xml)
    out = tmp_path / "out.tcx"
    write_tcx(original, out)
    return read_tcx(out)


class TestRoundTrip:
    def test_track_point_count_preserved(self, tmp_path):
        rt = _round_trip(SAMPLE_TCX, tmp_path)
        assert len(rt.track_points) == 4

    def test_track_coords_preserved(self, tmp_path):
        original = read_tcx_string(SAMPLE_TCX)
        rt = _round_trip(SAMPLE_TCX, tmp_path)
        assert rt.track_points["lat"].to_list() == pytest.approx(
            original.track_points["lat"].to_list()
        )
        assert rt.track_points["lon"].to_list() == pytest.approx(
            original.track_points["lon"].to_list()
        )

    def test_elevation_preserved(self, tmp_path):
        original = read_tcx_string(SAMPLE_TCX)
        rt = _round_trip(SAMPLE_TCX, tmp_path)
        assert rt.track_points["elevation"].to_list() == pytest.approx(
            original.track_points["elevation"].to_list()
        )

    def test_hr_preserved(self, tmp_path):
        original = read_tcx_string(SAMPLE_TCX)
        rt = _round_trip(SAMPLE_TCX, tmp_path)
        # Only points that had HR in the original should match
        orig_hr = original.track_points["hr"].to_list()
        rt_hr = rt.track_points["hr"].to_list()
        for o, r in zip(orig_hr, rt_hr):
            if o is not None:
                assert r == o

    def test_cue_count_preserved(self, tmp_path):
        rt = _round_trip(SAMPLE_TCX, tmp_path)
        assert len(rt.cues) == 1

    def test_cue_name_preserved(self, tmp_path):
        rt = _round_trip(SAMPLE_TCX, tmp_path)
        assert rt.cues["name"][0] == "Turn Right"

    def test_cue_type_preserved(self, tmp_path):
        rt = _round_trip(SAMPLE_TCX, tmp_path)
        assert rt.cues["cue_type"][0] == "Right"

    def test_poi_count_preserved(self, tmp_path):
        rt = _round_trip(SAMPLE_TCX, tmp_path)
        assert len(rt.pois) == 1

    def test_poi_name_preserved(self, tmp_path):
        rt = _round_trip(SAMPLE_TCX, tmp_path)
        assert rt.pois["name"][0] == "Water fountain"

    def test_empty_course_points_round_trip(self, tmp_path):
        rt = _round_trip(SAMPLE_TCX_NO_COURSE_POINTS, tmp_path)
        assert len(rt.cues) == 0
        assert len(rt.pois) == 0

    def test_output_file_is_valid_xml(self, tmp_path):
        import xml.etree.ElementTree as ET
        original = read_tcx_string(SAMPLE_TCX)
        out = tmp_path / "out.tcx"
        write_tcx(original, out)
        ET.parse(out)
