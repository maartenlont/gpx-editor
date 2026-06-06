"""Round-trip tests: read GPX → write → read back and compare."""

import pytest
from gpx_editor.io.gpx_reader import read_gpx, read_gpx_string
from gpx_editor.io.gpx_writer import write_gpx
from tests.conftest import SAMPLE_GPX, SAMPLE_GPX_NO_WAYPOINTS, SAMPLE_GPX_MINIMAL


def _round_trip(xml: str, tmp_path):
    original = read_gpx_string(xml)
    out = tmp_path / "out.gpx"
    write_gpx(original, out)
    return read_gpx(out)


class TestRoundTrip:
    def test_track_point_count_preserved(self, tmp_path):
        rt = _round_trip(SAMPLE_GPX, tmp_path)
        assert len(rt.track_points) == 4

    def test_track_coords_preserved(self, tmp_path):
        original = read_gpx_string(SAMPLE_GPX)
        rt = _round_trip(SAMPLE_GPX, tmp_path)
        assert rt.track_points["lat"].to_list() == pytest.approx(
            original.track_points["lat"].to_list()
        )
        assert rt.track_points["lon"].to_list() == pytest.approx(
            original.track_points["lon"].to_list()
        )

    def test_elevation_preserved(self, tmp_path):
        original = read_gpx_string(SAMPLE_GPX)
        rt = _round_trip(SAMPLE_GPX, tmp_path)
        assert rt.track_points["elevation"].to_list() == pytest.approx(
            original.track_points["elevation"].to_list()
        )

    def test_cue_count_preserved(self, tmp_path):
        rt = _round_trip(SAMPLE_GPX, tmp_path)
        assert len(rt.cues) == 1

    def test_cue_name_preserved(self, tmp_path):
        rt = _round_trip(SAMPLE_GPX, tmp_path)
        assert rt.cues["name"][0] == "Turn Left"

    def test_cue_type_preserved(self, tmp_path):
        rt = _round_trip(SAMPLE_GPX, tmp_path)
        assert rt.cues["cue_type"][0] == "Left"

    def test_poi_count_preserved(self, tmp_path):
        rt = _round_trip(SAMPLE_GPX, tmp_path)
        assert len(rt.pois) == 1

    def test_poi_name_preserved(self, tmp_path):
        rt = _round_trip(SAMPLE_GPX, tmp_path)
        assert rt.pois["name"][0] == "Coffee stop"

    def test_empty_waypoints_round_trip(self, tmp_path):
        rt = _round_trip(SAMPLE_GPX_NO_WAYPOINTS, tmp_path)
        assert len(rt.cues) == 0
        assert len(rt.pois) == 0

    def test_missing_elevation_round_trip(self, tmp_path):
        rt = _round_trip(SAMPLE_GPX_MINIMAL, tmp_path)
        assert rt.track_points["elevation"].is_null().all()

    def test_distance_recalculated_after_round_trip(self, tmp_path):
        original = read_gpx_string(SAMPLE_GPX)
        rt = _round_trip(SAMPLE_GPX, tmp_path)
        # Distance is recomputed by the reader, so values should match closely
        assert rt.track_points["distance"].to_list() == pytest.approx(
            original.track_points["distance"].to_list(), abs=0.01
        )

    def test_output_file_is_valid_xml(self, tmp_path):
        import xml.etree.ElementTree as ET
        original = read_gpx_string(SAMPLE_GPX)
        out = tmp_path / "out.gpx"
        write_gpx(original, out)
        # Should not raise
        ET.parse(out)


class TestRideWithGPSCompatibility:
    def test_rwgps_mode_writes_rte_element(self, tmp_path):
        import xml.etree.ElementTree as ET
        original = read_gpx_string(SAMPLE_GPX)
        out = tmp_path / "out.gpx"
        write_gpx(original, out, rwgps_compatible=True)
        tree = ET.parse(out)
        root = tree.getroot()
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        rte = root.find("gpx:rte", ns)
        assert rte is not None, "Expected <rte> element in RWGPS mode"

    def test_rwgps_mode_cues_as_rtept(self, tmp_path):
        import xml.etree.ElementTree as ET
        original = read_gpx_string(SAMPLE_GPX)
        out = tmp_path / "out.gpx"
        write_gpx(original, out, rwgps_compatible=True)
        tree = ET.parse(out)
        root = tree.getroot()
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        rte = root.find("gpx:rte", ns)
        rtepts = rte.findall("gpx:rtept", ns)
        assert len(rtepts) == 1, "Expected 1 rtept for the cue"

    def test_rwgps_mode_has_cue_extension(self, tmp_path):
        import xml.etree.ElementTree as ET
        original = read_gpx_string(SAMPLE_GPX)
        out = tmp_path / "out.gpx"
        write_gpx(original, out, rwgps_compatible=True)
        tree = ET.parse(out)
        root = tree.getroot()
        ns = {
            "gpx": "http://www.topografix.com/GPX/1/1",
            "rwgps": "http://ridewithgps.com/rte",
        }
        rtept = root.find(".//gpx:rtept", ns)
        ext = rtept.find("gpx:extensions", ns)
        cue = ext.find("rwgps:cue", ns)
        assert cue is not None
        assert cue.text == "Left"

    def test_rwgps_mode_pois_still_as_wpt(self, tmp_path):
        import xml.etree.ElementTree as ET
        original = read_gpx_string(SAMPLE_GPX)
        out = tmp_path / "out.gpx"
        write_gpx(original, out, rwgps_compatible=True)
        tree = ET.parse(out)
        root = tree.getroot()
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        wpts = root.findall("gpx:wpt", ns)
        # Only POIs should be wpt (cues go to rte/rtept)
        assert len(wpts) == 1
        assert wpts[0].find("gpx:name", ns).text == "Coffee stop"

    def test_default_mode_no_rte_element(self, tmp_path):
        import xml.etree.ElementTree as ET
        original = read_gpx_string(SAMPLE_GPX)
        out = tmp_path / "out.gpx"
        write_gpx(original, out, rwgps_compatible=False)
        tree = ET.parse(out)
        root = tree.getroot()
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        rte = root.find("gpx:rte", ns)
        assert rte is None, "Default mode should not have <rte> element"
