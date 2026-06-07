"""Serialise a RouteData to a TCX (Training Center XML) file."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import polars as pl

from gpx_editor.io._course_point_types import garmin_type_for_name, garmin_type_for_poi, to_garmin
from gpx_editor.models.route import RouteData

_NS = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
_XSI = "http://www.w3.org/2001/XMLSchema-instance"
_SCHEMA_LOC = (
    "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 "
    "http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd"
)


def _t(local: str) -> str:
    return f"{{{_NS}}}{local}"


def _sub(parent: ET.Element, local: str, text: str | None = None) -> ET.Element:
    el = ET.SubElement(parent, _t(local))
    if text is not None:
        el.text = text
    return el


def write_tcx(route: RouteData, path: str | Path) -> None:
    """Write *route* to *path* as a TCX Course file."""
    ET.register_namespace("", _NS)

    root = ET.Element(
        _t("TrainingCenterDatabase"),
        {f"{{{_XSI}}}schemaLocation": _SCHEMA_LOC},
    )

    courses = _sub(root, "Courses")
    course = _sub(courses, "Course")
    _sub(course, "Name", "Route")

    _write_course_points(course, route.cues, route.pois)
    _write_track(course, route.track_points)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(str(path), encoding="utf-8", xml_declaration=True)


# ---------------------------------------------------------------------------
# Course points
# ---------------------------------------------------------------------------

def _write_course_points(
    course: ET.Element, cues: pl.DataFrame, pois: pl.DataFrame,
) -> None:
    for row in cues.iter_rows(named=True):
        cp = _sub(course, "CoursePoint")
        _sub(cp, "Name", row["name"] or "")
        pos = _sub(cp, "Position")
        _sub(pos, "LatitudeDegrees", str(row["lat"]))
        _sub(pos, "LongitudeDegrees", str(row["lon"]))
        # Use name-based mapping first, fallback to cue_type mapping
        point_type = garmin_type_for_name(row["name"] or "", to_garmin(row["cue_type"] or "", "Left"))
        _sub(cp, "PointType", point_type)
        if row["description"]:
            _sub(cp, "Notes", row["description"])

    for row in pois.iter_rows(named=True):
        cp = _sub(course, "CoursePoint")
        _sub(cp, "Name", row["name"] or "")
        pos = _sub(cp, "Position")
        _sub(pos, "LatitudeDegrees", str(row["lat"]))
        _sub(pos, "LongitudeDegrees", str(row["lon"]))
        # Use name-based mapping first, fallback to symbol-based mapping
        point_type = garmin_type_for_name(row["name"] or "", garmin_type_for_poi(row["symbol"] or "", row["name"] or ""))
        _sub(cp, "PointType", point_type)
        if row["description"]:
            _sub(cp, "Notes", row["description"])


# ---------------------------------------------------------------------------
# Track
# ---------------------------------------------------------------------------

def _write_track(course: ET.Element, track_points: pl.DataFrame) -> None:
    if len(track_points) == 0:
        return
    track = _sub(course, "Track")

    for row in track_points.iter_rows(named=True):
        tp = _sub(track, "Trackpoint")
        if row.get("time") is not None:
            _sub(tp, "Time", row["time"].isoformat() + "Z")
        pos = _sub(tp, "Position")
        _sub(pos, "LatitudeDegrees", str(row["lat"]))
        _sub(pos, "LongitudeDegrees", str(row["lon"]))
        if row.get("elevation") is not None:
            _sub(tp, "AltitudeMeters", str(row["elevation"]))
        if row.get("hr") is not None:
            hr_el = _sub(tp, "HeartRateBpm")
            _sub(hr_el, "Value", str(row["hr"]))
        if row.get("cadence") is not None:
            _sub(tp, "Cadence", str(row["cadence"]))
