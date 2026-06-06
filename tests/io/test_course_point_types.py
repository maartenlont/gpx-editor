"""End-to-end tests for Garmin course-point type mapping across all formats.

Verifies that:
- Various internal / legacy cue_type strings are normalised to Garmin title-case
  when written to GPX / TCX / FIT and read back.
- POI symbols are mapped to the correct Garmin course-point type on write and the
  symbol is restored on read.
- Garmin-format type strings coming from external files (e.g. "U Turn",
  "Left Fork") are classified correctly as cues, not POIs.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import polars as pl
import pytest

from gpx_editor.io._course_point_types import (
    garmin_type_for_poi,
    is_nav_type,
    symbol_to_garmin,
    to_garmin,
)
from gpx_editor.io.fit_reader import read_fit
from gpx_editor.io.fit_writer import write_fit
from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.io.gpx_writer import write_gpx
from gpx_editor.io.tcx_reader import read_tcx
from gpx_editor.io.tcx_writer import write_tcx
from gpx_editor.models.route import RouteData, empty_pois, empty_track_points

_GPX_NS = {"gpx": "http://www.topografix.com/GPX/1/1"}
_TCX_NS = {"t": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cues(cue_types: list[str]) -> pl.DataFrame:
    n = len(cue_types)
    return pl.DataFrame({
        "index":       list(range(n)),
        "lat":         [51.0] * n,
        "lon":         [4.0] * n,
        "name":        [f"P{i}" for i in range(n)],
        "description": [""] * n,
        "cue_type":    cue_types,
        "distance":    [float(i * 100) for i in range(n)],
    }, schema={
        "index": pl.Int64, "lat": pl.Float64, "lon": pl.Float64,
        "name": pl.String, "description": pl.String,
        "cue_type": pl.String, "distance": pl.Float64,
    })


def _make_pois(symbols: list[str]) -> pl.DataFrame:
    n = len(symbols)
    return pl.DataFrame({
        "index":       list(range(n)),
        "lat":         [51.0] * n,
        "lon":         [4.0] * n,
        "name":        [f"P{i}" for i in range(n)],
        "description": [""] * n,
        "symbol":      symbols,
        "distance":    [float(i * 100) for i in range(n)],
    }, schema={
        "index": pl.Int64, "lat": pl.Float64, "lon": pl.Float64,
        "name": pl.String, "description": pl.String,
        "symbol": pl.String, "distance": pl.Float64,
    })


def _route(cue_types=None, symbols=None) -> RouteData:
    cues = _make_cues(cue_types) if cue_types else _make_cues([])
    pois = _make_pois(symbols) if symbols else empty_pois()
    return RouteData(track_points=empty_track_points(), cues=cues, pois=pois)


# ---------------------------------------------------------------------------
# Unit tests: _course_point_types helpers
# ---------------------------------------------------------------------------

class TestToGarmin:
    @pytest.mark.parametrize("internal,expected", [
        ("left",        "Left"),
        ("right",       "Right"),
        ("u-turn",      "U Turn"),
        ("uturn",       "U Turn"),
        ("u turn",      "U Turn"),
        ("u_turn",      "U Turn"),
        ("fork left",   "Left Fork"),
        ("left fork",   "Left Fork"),
        ("left_fork",   "Left Fork"),
        ("slight_left", "Slight Left"),
        ("sharp_right", "Sharp Right"),
        ("roundabout",  "Left"),
        ("bear left",   "Slight Left"),
        ("continue",    "Straight"),
        ("Left",        "Left"),         # already canonical
        ("Straight",    "Straight"),
        ("U Turn",      "U Turn"),
    ])
    def test_cue_normalisation(self, internal, expected):
        assert to_garmin(internal) == expected

    @pytest.mark.parametrize("sym,expected", [
        # Exact matches
        ("water",            "Water"),
        ("drinking_water",   "Water"),
        ("water fountain",   "Water"),
        ("tap",              "Water"),
        ("fuel",             "Food"),
        ("restaurant",       "Food"),
        ("cafe",             "Food"),
        ("coffee",           "Food"),
        ("pharmacy",         "First Aid"),
        ("hospital",         "First Aid"),
        ("first aid",        "First Aid"),
        ("camping",          "Generic"),
        ("lodging",          "Generic"),
        ("summit",           "Summit"),
        ("peak",             "Summit"),
        ("valley",           "Valley"),
        ("danger",           "Danger"),
        # App glyphicon names used as symbols
        ("tint",             "Water"),
        ("cutlery",          "Food"),
        ("flag",             "Summit"),
        ("plus-sign",        "First Aid"),
        # Greedy keyword fallback (freeform user text)
        ("Water Tap",        "Water"),
        ("drinking water",   "Water"),
        ("Coffee Stop",      "Food"),
        ("food stop",        "Food"),
        ("bakery shop",      "Food"),
        ("medical center",   "First Aid"),
        ("hospital ward",    "First Aid"),
        ("mountain peak",    "Summit"),
        ("river valley",     "Valley"),
        ("danger zone",      "Danger"),
        # Climb categories — ordinal and word forms
        ("4th category",     "Fourth Category"),
        ("4th cat",          "Fourth Category"),
        ("cat 4",            "Fourth Category"),
        ("fourth category",  "Fourth Category"),
        ("fourth_category",  "Fourth Category"),   # stored by garmin_to_symbol()
        ("3rd category",     "Third Category"),
        ("third_category",   "Third Category"),
        ("2nd category",     "Second Category"),
        ("second_category",  "Second Category"),
        ("1st category",     "First Category"),
        ("first_category",   "First Category"),
        ("hors category",    "Hors Category"),
        ("hors_category",    "Hors Category"),     # stored by garmin_to_symbol()
        ("hors cat",         "Hors Category"),
        ("hc",               "Hors Category"),
        ("hors",             "Hors Category"),
        # Greedy keyword for HC
        ("Hors Catégorie",   "Hors Category"),
        # Genuinely unmapped
        ("photo",            "Generic"),
        ("bike",             "Generic"),
        ("",                 "Generic"),
        ("unknown xyz",      "Generic"),
    ])
    def test_symbol_to_garmin(self, sym, expected):
        assert symbol_to_garmin(sym) == expected


class TestIsNavType:
    @pytest.mark.parametrize("t", [
        "left", "right", "straight", "Left", "Right", "Straight",
        "u-turn", "u_turn", "U Turn", "u turn",
        "fork left", "left fork", "Left Fork",
        "slight left", "slight_left", "Slight Left",
        "sharp right", "sharp_right", "Sharp Right",
    ])
    def test_nav_types_classified_as_cue(self, t):
        assert is_nav_type(t) is True

    @pytest.mark.parametrize("t", [
        "water", "Water", "food", "Food", "generic", "Generic",
        "summit", "Summit", "pharmacy", "", "unknown",
    ])
    def test_poi_types_not_classified_as_cue(self, t):
        assert is_nav_type(t) is False


# ---------------------------------------------------------------------------
# GPX writer: <type> values are Garmin title-case
# ---------------------------------------------------------------------------

class TestGpxWriterTypes:
    def test_cue_types_are_title_case(self, tmp_path):
        route = _route(cue_types=["left", "u-turn", "fork left", "slight_right"])
        out = tmp_path / "out.gpx"
        write_gpx(route, out)
        tree = ET.parse(out)
        types = [el.text for el in tree.getroot().findall(".//gpx:wpt/gpx:type", _GPX_NS)]
        assert types == ["Left", "U Turn", "Left Fork", "Slight Right"]

    def test_poi_gets_type_element(self, tmp_path):
        route = _route(symbols=["water", "fuel", "pharmacy"])
        out = tmp_path / "out.gpx"
        write_gpx(route, out)
        tree = ET.parse(out)
        types = [el.text for el in tree.getroot().findall(".//gpx:wpt/gpx:type", _GPX_NS)]
        assert types == ["Water", "Food", "First Aid"]

    def test_poi_sym_still_written(self, tmp_path):
        route = _route(symbols=["water"])
        out = tmp_path / "out.gpx"
        write_gpx(route, out)
        tree = ET.parse(out)
        syms = [el.text for el in tree.getroot().findall(".//gpx:wpt/gpx:sym", _GPX_NS)]
        assert syms == ["water"]


# ---------------------------------------------------------------------------
# GPX round-trip
# ---------------------------------------------------------------------------

class TestGpxRoundTrip:
    @pytest.mark.parametrize("internal,canonical", [
        ("left",      "Left"),
        ("u-turn",    "U Turn"),
        ("fork left", "Left Fork"),
        ("roundabout","Left"),
    ])
    def test_cue_type_normalised_on_read_back(self, tmp_path, internal, canonical):
        route = _route(cue_types=[internal])
        out = tmp_path / "out.gpx"
        write_gpx(route, out)
        loaded = read_gpx(out)
        assert len(loaded.cues) == 1
        assert loaded.cues["cue_type"][0] == canonical

    def test_water_poi_survives_round_trip(self, tmp_path):
        route = _route(symbols=["water"])
        out = tmp_path / "out.gpx"
        write_gpx(route, out)
        loaded = read_gpx(out)
        assert len(loaded.pois) == 1
        assert loaded.pois["symbol"][0] == "water"

    def test_climb_categories_round_trip(self, tmp_path):
        """All five climb categories survive a write→read cycle with correct types."""
        symbols = ["fourth_category", "third_category", "second_category",
                   "first_category", "hors_category"]
        expected = ["Fourth Category", "Third Category", "Second Category",
                    "First Category", "Hors Category"]
        route = _route(symbols=symbols)
        out = tmp_path / "cats.gpx"
        write_gpx(route, out)
        # Check raw <type> elements
        tree = ET.parse(out)
        types = [el.text for el in tree.getroot().findall(".//gpx:wpt/gpx:type", _GPX_NS)]
        assert types == expected
        # Check round-trip: symbols survive as the canonical garmin_to_symbol values
        loaded = read_gpx(out)
        assert loaded.pois["symbol"].to_list() == symbols

    def test_garmin_type_u_turn_read_as_cue(self, tmp_path):
        """A GPX file from Garmin Connect with <type>U Turn</type> must become a cue."""
        gpx = """\
<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <wpt lat="51.0" lon="4.0"><name>UT</name><type>U Turn</type></wpt>
  <wpt lat="51.0" lon="4.0"><name>LF</name><type>Left Fork</type></wpt>
  <wpt lat="51.0" lon="4.0"><name>W</name><type>Water</type></wpt>
</gpx>"""
        out = tmp_path / "garmin.gpx"
        out.write_text(gpx)
        loaded = read_gpx(out)
        assert len(loaded.cues) == 2
        assert loaded.cues["cue_type"].to_list() == ["U Turn", "Left Fork"]
        assert len(loaded.pois) == 1
        assert loaded.pois["symbol"][0] == "water"


# ---------------------------------------------------------------------------
# TCX writer: <PointType> values are Garmin title-case
# ---------------------------------------------------------------------------

class TestTcxWriterTypes:
    def test_cue_types_are_title_case(self, tmp_path):
        route = _route(cue_types=["left", "u-turn", "sharp_left"])
        out = tmp_path / "out.tcx"
        write_tcx(route, out)
        tree = ET.parse(out)
        types = [el.text for el in tree.getroot().findall(".//t:PointType", _TCX_NS)]
        assert types == ["Left", "U Turn", "Sharp Left"]

    def test_poi_gets_meaningful_type(self, tmp_path):
        route = _route(symbols=["water", "pharmacy"])
        out = tmp_path / "out.tcx"
        write_tcx(route, out)
        tree = ET.parse(out)
        types = [el.text for el in tree.getroot().findall(".//t:PointType", _TCX_NS)]
        assert types == ["Water", "First Aid"]


# ---------------------------------------------------------------------------
# TCX round-trip
# ---------------------------------------------------------------------------

class TestTcxRoundTrip:
    def test_cue_type_normalised(self, tmp_path):
        route = _route(cue_types=["left", "slight_right"])
        out = tmp_path / "out.tcx"
        write_tcx(route, out)
        loaded = read_tcx(out)
        assert loaded.cues["cue_type"].to_list() == ["Left", "Slight Right"]

    def test_water_poi_survives(self, tmp_path):
        route = _route(symbols=["water"])
        out = tmp_path / "out.tcx"
        write_tcx(route, out)
        loaded = read_tcx(out)
        assert len(loaded.pois) == 1
        assert loaded.pois["symbol"][0] == "water"


# ---------------------------------------------------------------------------
# FIT round-trip
# ---------------------------------------------------------------------------

class TestFitRoundTrip:
    def test_cue_types_normalised(self, tmp_path):
        route = _route(cue_types=["left", "u-turn", "left_fork"])
        out = tmp_path / "out.fit"
        write_fit(route, out)
        loaded = read_fit(out)
        assert loaded.cues["cue_type"].to_list() == ["Left", "U Turn", "Left Fork"]

    def test_water_poi_survives(self, tmp_path):
        route = _route(symbols=["water"])
        out = tmp_path / "out.fit"
        write_fit(route, out)
        loaded = read_fit(out)
        assert len(loaded.pois) == 1
        assert loaded.pois["symbol"][0] == "water"

    def test_cue_count_preserved(self, tmp_path):
        route = _route(cue_types=["left", "right", "straight"])
        out = tmp_path / "out.fit"
        write_fit(route, out)
        loaded = read_fit(out)
        assert len(loaded.cues) == 3


# ---------------------------------------------------------------------------
# garmin_type_for_poi: name fallback
# ---------------------------------------------------------------------------

class TestGarminTypeForPoi:
    @pytest.mark.parametrize("symbol,name,expected", [
        # Symbol wins when it resolves to something meaningful
        ("water",     "Water Stop",  "Water"),
        ("pharmacy",  "Pharmacy",    "First Aid"),
        # Empty symbol → name fallback
        ("",          "Water Tap",   "Water"),
        ("",          "Drinking Water", "Water"),
        ("",          "Coffee Stop", "Food"),
        ("",          "Medical Aid", "First Aid"),
        # CP/TCP prefix in name → Generic
        ("",          "CP1",         "Generic"),
        ("",          "CP 3",        "Generic"),
        ("",          "TCP2",        "Generic"),
        ("",          "TCP 10",      "Generic"),
        # Both empty → Generic
        ("",          "",            "Generic"),
        # Truly unmapped name → Generic
        ("",          "Some Place",  "Generic"),
    ])
    def test_name_fallback(self, symbol, name, expected):
        assert garmin_type_for_poi(symbol, name) == expected

    def test_gpx_water_name_fallback_round_trip(self, tmp_path):
        """A POI with empty symbol but name 'Water Tap' should write Water in GPX."""
        import xml.etree.ElementTree as ET
        pois = pl.DataFrame({
            "index":       [0],
            "lat":         [51.0],
            "lon":         [4.0],
            "name":        ["Water Tap"],
            "description": [""],
            "symbol":      [""],
            "distance":    [0.0],
        }, schema={
            "index": pl.Int64, "lat": pl.Float64, "lon": pl.Float64,
            "name": pl.String, "description": pl.String,
            "symbol": pl.String, "distance": pl.Float64,
        })
        from gpx_editor.models.route import RouteData, empty_cues, empty_track_points
        route = RouteData(track_points=empty_track_points(), cues=empty_cues(), pois=pois)
        out = tmp_path / "water.gpx"
        write_gpx(route, out)
        tree = ET.parse(out)
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        types = [el.text for el in tree.getroot().findall(".//gpx:wpt/gpx:type", ns)]
        assert types == ["Water"]
