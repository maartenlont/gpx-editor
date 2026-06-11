"""Tests for logic/merge.py — copy_cues_pois()."""

import pytest
import polars as pl

from gpx_editor.io._distance import haversine
from gpx_editor.logic.merge import copy_cues_pois
from gpx_editor.models.route import RouteData, empty_cues, empty_pois

# ---------------------------------------------------------------------------
# Shared coordinates
#
# Target track:
#   pt0  (52.3700, 4.8950)  distance = 0 m
#   pt1  (52.3710, 4.8960)  distance ≈ 130 m
#
# Source cues / POIs are placed at known offsets so we can reason about
# which ones are within / outside the default 10 m threshold.
#
#   CUE_NEAR  (52.37003, 4.89503)  ≈  3.9 m from pt0  → inside  10 m
#   CUE_FAR   (52.3720,  4.8970 )  ≈ 261 m from pt0   → outside 10 m
#   POI_NEAR  (52.37098, 4.89598)  ≈  2.5 m from pt1  → inside  10 m
#   POI_FAR   (52.3730,  4.8980 )  ≈ far               → outside 10 m
# ---------------------------------------------------------------------------

PT0 = (52.3700, 4.8950)
PT1 = (52.3710, 4.8960)
PT1_DIST_M = float(haversine(*PT0, *PT1))   # ≈ 130 m

CUE_NEAR  = (52.37003, 4.89503)   # ≈  3.9 m from PT0
CUE_FAR   = (52.3720,  4.8970 )   # ≈ 261 m from nearest target point
POI_NEAR  = (52.37098, 4.89598)   # ≈  2.5 m from PT1
POI_FAR   = (52.3730,  4.8980 )   # far from both


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _make_track(points: list[tuple[float, float, float]]) -> pl.DataFrame:
    """Build a minimal track_points DataFrame from (lat, lon, dist_m) tuples."""
    rows = [
        {
            "index": i,
            "lat": lat,
            "lon": lon,
            "elevation": 5.0,
            "time": None,
            "distance": dist,
            "hr": None,
            "cadence": None,
            "power": None,
        }
        for i, (lat, lon, dist) in enumerate(points)
    ]
    return pl.DataFrame(rows, schema={
        "index": pl.Int64,
        "lat": pl.Float64,
        "lon": pl.Float64,
        "elevation": pl.Float64,
        "time": pl.Datetime("us", "UTC"),
        "distance": pl.Float64,
        "hr": pl.Int32,
        "cadence": pl.Int32,
        "power": pl.Int32,
    })


def _make_cues(items: list[tuple[float, float, str]]) -> pl.DataFrame:
    """Build a cues DataFrame from (lat, lon, name) tuples."""
    rows = [
        {
            "index": i,
            "lat": lat,
            "lon": lon,
            "name": name,
            "description": "",
            "cue_type": "Left",
            "distance": 0.0,
        }
        for i, (lat, lon, name) in enumerate(items)
    ]
    return pl.DataFrame(rows, schema={
        "index": pl.Int64,
        "lat": pl.Float64,
        "lon": pl.Float64,
        "name": pl.String,
        "description": pl.String,
        "cue_type": pl.String,
        "distance": pl.Float64,
    })


def _make_pois(items: list[tuple[float, float, str]]) -> pl.DataFrame:
    rows = [
        {
            "index": i,
            "lat": lat,
            "lon": lon,
            "name": name,
            "description": "",
            "symbol": "Generic",
            "distance": 0.0,
        }
        for i, (lat, lon, name) in enumerate(items)
    ]
    return pl.DataFrame(rows, schema={
        "index": pl.Int64,
        "lat": pl.Float64,
        "lon": pl.Float64,
        "name": pl.String,
        "description": pl.String,
        "symbol": pl.String,
        "distance": pl.Float64,
    })


@pytest.fixture()
def target() -> RouteData:
    tp = _make_track([(*PT0, 0.0), (*PT1, PT1_DIST_M)])
    return RouteData(track_points=tp)


@pytest.fixture()
def source_with_cues() -> RouteData:
    tp = _make_track([(*PT0, 0.0)])  # source track doesn't matter for merge
    cues = _make_cues([(CUE_NEAR[0], CUE_NEAR[1], "Near cue")])
    return RouteData(track_points=tp, cues=cues)


@pytest.fixture()
def source_with_far_cue() -> RouteData:
    tp = _make_track([(*PT0, 0.0)])
    cues = _make_cues([(CUE_FAR[0], CUE_FAR[1], "Far cue")])
    return RouteData(track_points=tp, cues=cues)


@pytest.fixture()
def source_with_mixed_cues() -> RouteData:
    tp = _make_track([(*PT0, 0.0)])
    cues = _make_cues([
        (*CUE_NEAR, "Near cue"),
        (*CUE_FAR,  "Far cue"),
    ])
    return RouteData(track_points=tp, cues=cues)


@pytest.fixture()
def source_with_pois() -> RouteData:
    tp = _make_track([(*PT0, 0.0)])
    pois = _make_pois([(*POI_NEAR, "Near POI"), (*POI_FAR, "Far POI")])
    return RouteData(track_points=tp, pois=pois)


# ---------------------------------------------------------------------------
# Distance sanity checks (verifies our coordinate choices above)
# ---------------------------------------------------------------------------

def test_cue_near_is_within_10m():
    assert float(haversine(*PT0, *CUE_NEAR)) < 10.0


def test_cue_far_is_outside_10m():
    dist_from_pt0 = float(haversine(*PT0, *CUE_FAR))
    dist_from_pt1 = float(haversine(*PT1, *CUE_FAR))
    assert min(dist_from_pt0, dist_from_pt1) > 10.0


def test_poi_near_is_within_10m():
    assert float(haversine(*PT1, *POI_NEAR)) < 10.0


# ---------------------------------------------------------------------------
# Core behaviour
# ---------------------------------------------------------------------------

class TestCopyCueWithinThreshold:
    def test_cue_is_copied(self, target, source_with_cues):
        result = copy_cues_pois(source_with_cues, target)
        assert len(result.cues) == 1

    def test_cue_name_preserved(self, target, source_with_cues):
        result = copy_cues_pois(source_with_cues, target)
        assert result.cues["name"][0] == "Near cue"

    def test_cue_snapped_to_nearest_track_point(self, target, source_with_cues):
        result = copy_cues_pois(source_with_cues, target)
        assert result.cues["lat"][0] == pytest.approx(PT0[0])
        assert result.cues["lon"][0] == pytest.approx(PT0[1])

    def test_cue_distance_matches_target_track(self, target, source_with_cues):
        result = copy_cues_pois(source_with_cues, target)
        assert result.cues["distance"][0] == pytest.approx(0.0)


class TestCueOutsideThreshold:
    def test_cue_not_copied(self, target, source_with_far_cue):
        result = copy_cues_pois(source_with_far_cue, target)
        assert len(result.cues) == 0

    def test_cue_copied_when_threshold_raised(self, target, source_with_far_cue):
        result = copy_cues_pois(source_with_far_cue, target, threshold_m=300.0)
        assert len(result.cues) == 1


class TestThresholdBoundary:
    def test_cue_at_exactly_threshold_is_copied(self, target):
        # Place a cue at a known distance from PT0, use that distance as threshold
        actual_dist = float(haversine(*PT0, *CUE_NEAR))
        cues = _make_cues([(*CUE_NEAR, "boundary cue")])
        source = RouteData(track_points=_make_track([(*PT0, 0.0)]), cues=cues)

        result_in = copy_cues_pois(source, target, threshold_m=actual_dist)
        assert len(result_in.cues) == 1

    def test_cue_just_outside_threshold_not_copied(self, target):
        actual_dist = float(haversine(*PT0, *CUE_NEAR))
        cues = _make_cues([(*CUE_NEAR, "boundary cue")])
        source = RouteData(track_points=_make_track([(*PT0, 0.0)]), cues=cues)

        result_out = copy_cues_pois(source, target, threshold_m=actual_dist - 0.01)
        assert len(result_out.cues) == 0


class TestMixedCues:
    def test_only_near_cue_copied(self, target, source_with_mixed_cues):
        result = copy_cues_pois(source_with_mixed_cues, target)
        assert len(result.cues) == 1
        assert result.cues["name"][0] == "Near cue"


class TestEmptySource:
    def test_empty_source_cues_leaves_target_unchanged(self, target):
        source = RouteData(track_points=_make_track([(*PT0, 0.0)]))
        result = copy_cues_pois(source, target)
        assert len(result.cues) == 0
        assert result.track_points.equals(target.track_points)

    def test_empty_source_pois_leaves_target_unchanged(self, target):
        source = RouteData(track_points=_make_track([(*PT0, 0.0)]))
        result = copy_cues_pois(source, target)
        assert len(result.pois) == 0


class TestExistingTargetWaypointsPreserved:
    def test_existing_cues_kept(self, target, source_with_cues):
        # Use a different cue_type to avoid deduplication with merged cue
        existing_cue = pl.DataFrame([{
            "index": 0,
            "lat": PT1[0],
            "lon": PT1[1],
            "name": "Existing target cue",
            "description": "",
            "cue_type": "Right",  # Different from "Left" used by _make_cues
            "distance": 0.0,
        }], schema={
            "index": pl.Int64, "lat": pl.Float64, "lon": pl.Float64,
            "name": pl.String, "description": pl.String,
            "cue_type": pl.String, "distance": pl.Float64,
        })
        target_with_cue = RouteData(
            track_points=target.track_points, cues=existing_cue
        )
        result = copy_cues_pois(source_with_cues, target_with_cue)
        assert len(result.cues) == 2
        names = set(result.cues["name"].to_list())
        assert "Near cue" in names
        assert "Existing target cue" in names

    def test_existing_pois_kept(self, target, source_with_pois):
        existing_poi = _make_pois([(*PT0, "Existing POI")])
        target_with_poi = RouteData(
            track_points=target.track_points, pois=existing_poi
        )
        result = copy_cues_pois(source_with_pois, target_with_poi)
        assert len(result.pois) >= 1
        assert "Existing POI" in result.pois["name"].to_list()


class TestSortingAndIndexing:
    def test_result_sorted_by_distance(self, target, source_with_cues):
        # Put an existing cue on pt1 (dist ≈ 130m), merged cue goes to pt0 (dist=0)
        existing_cue = _make_cues([(*PT1, "Late cue")])
        target_with_cue = RouteData(
            track_points=target.track_points, cues=existing_cue
        )
        # Manually set the distance for the existing cue to PT1_DIST_M
        updated_cue = target_with_cue.cues.with_columns(
            pl.lit(PT1_DIST_M).alias("distance")
        )
        target_with_cue = RouteData(
            track_points=target.track_points, cues=updated_cue
        )
        result = copy_cues_pois(source_with_cues, target_with_cue)
        dists = result.cues["distance"].to_list()
        assert dists == sorted(dists)

    def test_index_column_is_sequential(self, target, source_with_mixed_cues):
        # source has 2 cues; only 1 within threshold → result has 1 cue
        result = copy_cues_pois(source_with_mixed_cues, target)
        assert result.cues["index"].to_list() == list(range(len(result.cues)))

    def test_poi_index_sequential(self, target, source_with_pois):
        result = copy_cues_pois(source_with_pois, target)
        assert result.pois["index"].to_list() == list(range(len(result.pois)))


class TestImmutability:
    def test_source_cues_not_mutated(self, target, source_with_cues):
        original_len = len(source_with_cues.cues)
        copy_cues_pois(source_with_cues, target)
        assert len(source_with_cues.cues) == original_len

    def test_target_cues_not_mutated(self, target, source_with_cues):
        original_len = len(target.cues)
        copy_cues_pois(source_with_cues, target)
        assert len(target.cues) == original_len

    def test_target_track_points_preserved(self, target, source_with_cues):
        result = copy_cues_pois(source_with_cues, target)
        assert result.track_points.equals(target.track_points)


class TestEmptyTargetTrack:
    def test_returns_target_unchanged_when_no_track(self, source_with_cues):
        empty_target = RouteData()
        result = copy_cues_pois(source_with_cues, empty_target)
        assert len(result.cues) == 0
        assert len(result.track_points) == 0


class TestPOIs:
    def test_near_poi_copied(self, target, source_with_pois):
        result = copy_cues_pois(source_with_pois, target)
        poi_names = result.pois["name"].to_list()
        assert "Near POI" in poi_names

    def test_far_poi_not_copied(self, target, source_with_pois):
        result = copy_cues_pois(source_with_pois, target)
        poi_names = result.pois["name"].to_list()
        assert "Far POI" not in poi_names

    def test_poi_snapped_to_nearest_track_point(self, target, source_with_pois):
        result = copy_cues_pois(source_with_pois, target)
        near = result.pois.filter(pl.col("name") == "Near POI")
        assert near["lat"][0] == pytest.approx(PT1[0])
        assert near["lon"][0] == pytest.approx(PT1[1])

    def test_poi_distance_matches_target_track(self, target, source_with_pois):
        result = copy_cues_pois(source_with_pois, target)
        near = result.pois.filter(pl.col("name") == "Near POI")
        assert near["distance"][0] == pytest.approx(PT1_DIST_M)


class TestDeduplication:
    """Verify that duplicates (same type at same distance) are deduplicated."""

    def test_cue_with_description_kept_over_empty(self, target):
        """When two cues have same type/distance, keep the one with description."""
        existing_cue = pl.DataFrame([{
            "index": 0,
            "lat": PT0[0], "lon": PT0[1],
            "name": "No desc", "description": "",
            "cue_type": "Left", "distance": 0.0,
        }], schema={
            "index": pl.Int64, "lat": pl.Float64, "lon": pl.Float64,
            "name": pl.String, "description": pl.String,
            "cue_type": pl.String, "distance": pl.Float64,
        })
        source_cue = pl.DataFrame([{
            "index": 0,
            "lat": CUE_NEAR[0], "lon": CUE_NEAR[1],
            "name": "With desc", "description": "Important note",
            "cue_type": "Left", "distance": 0.0,
        }], schema={
            "index": pl.Int64, "lat": pl.Float64, "lon": pl.Float64,
            "name": pl.String, "description": pl.String,
            "cue_type": pl.String, "distance": pl.Float64,
        })
        target_with_cue = RouteData(track_points=target.track_points, cues=existing_cue)
        source = RouteData(track_points=_make_track([(*PT0, 0.0)]), cues=source_cue)

        result = copy_cues_pois(source, target_with_cue)

        assert len(result.cues) == 1
        assert result.cues["name"][0] == "With desc"
        assert result.cues["description"][0] == "Important note"

    def test_first_cue_kept_when_both_have_description(self, target):
        """When both cues have descriptions, keep the first (existing target)."""
        existing_cue = pl.DataFrame([{
            "index": 0,
            "lat": PT0[0], "lon": PT0[1],
            "name": "First", "description": "First description",
            "cue_type": "Left", "distance": 0.0,
        }], schema={
            "index": pl.Int64, "lat": pl.Float64, "lon": pl.Float64,
            "name": pl.String, "description": pl.String,
            "cue_type": pl.String, "distance": pl.Float64,
        })
        source_cue = pl.DataFrame([{
            "index": 0,
            "lat": CUE_NEAR[0], "lon": CUE_NEAR[1],
            "name": "Second", "description": "Second description",
            "cue_type": "Left", "distance": 0.0,
        }], schema={
            "index": pl.Int64, "lat": pl.Float64, "lon": pl.Float64,
            "name": pl.String, "description": pl.String,
            "cue_type": pl.String, "distance": pl.Float64,
        })
        target_with_cue = RouteData(track_points=target.track_points, cues=existing_cue)
        source = RouteData(track_points=_make_track([(*PT0, 0.0)]), cues=source_cue)

        result = copy_cues_pois(source, target_with_cue)

        assert len(result.cues) == 1
        assert result.cues["name"][0] == "First"

    def test_different_types_not_deduplicated(self, target):
        """Cues with different types at same distance are both kept."""
        existing_cue = pl.DataFrame([{
            "index": 0,
            "lat": PT0[0], "lon": PT0[1],
            "name": "Left turn", "description": "",
            "cue_type": "Left", "distance": 0.0,
        }], schema={
            "index": pl.Int64, "lat": pl.Float64, "lon": pl.Float64,
            "name": pl.String, "description": pl.String,
            "cue_type": pl.String, "distance": pl.Float64,
        })
        source_cue = pl.DataFrame([{
            "index": 0,
            "lat": CUE_NEAR[0], "lon": CUE_NEAR[1],
            "name": "Right turn", "description": "",
            "cue_type": "Right", "distance": 0.0,
        }], schema={
            "index": pl.Int64, "lat": pl.Float64, "lon": pl.Float64,
            "name": pl.String, "description": pl.String,
            "cue_type": pl.String, "distance": pl.Float64,
        })
        target_with_cue = RouteData(track_points=target.track_points, cues=existing_cue)
        source = RouteData(track_points=_make_track([(*PT0, 0.0)]), cues=source_cue)

        result = copy_cues_pois(source, target_with_cue)

        assert len(result.cues) == 2

    def test_poi_with_description_kept_over_empty(self, target):
        """When two POIs have same symbol/distance, keep the one with description."""
        existing_poi = pl.DataFrame([{
            "index": 0,
            "lat": PT1[0], "lon": PT1[1],
            "name": "No desc", "description": "",
            "symbol": "Water", "distance": PT1_DIST_M,
        }], schema={
            "index": pl.Int64, "lat": pl.Float64, "lon": pl.Float64,
            "name": pl.String, "description": pl.String,
            "symbol": pl.String, "distance": pl.Float64,
        })
        source_poi = pl.DataFrame([{
            "index": 0,
            "lat": POI_NEAR[0], "lon": POI_NEAR[1],
            "name": "With desc", "description": "Water fountain here",
            "symbol": "Water", "distance": 0.0,
        }], schema={
            "index": pl.Int64, "lat": pl.Float64, "lon": pl.Float64,
            "name": pl.String, "description": pl.String,
            "symbol": pl.String, "distance": pl.Float64,
        })
        target_with_poi = RouteData(track_points=target.track_points, pois=existing_poi)
        source = RouteData(track_points=_make_track([(*PT0, 0.0)]), pois=source_poi)

        result = copy_cues_pois(source, target_with_poi)

        assert len(result.pois) == 1
        assert result.pois["name"][0] == "With desc"
