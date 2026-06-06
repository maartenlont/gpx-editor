"""Serialise a RouteData to a GPX file."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import polars as pl

from gpx_editor.io._course_point_types import symbol_to_garmin, to_garmin
from gpx_editor.models.route import RouteData

_GPX_NS = "http://www.topografix.com/GPX/1/1"
_XSI = "http://www.w3.org/2001/XMLSchema-instance"
_SCHEMA_LOC = (
    "http://www.topografix.com/GPX/1/1 "
    "http://www.topografix.com/GPX/1/1/gpx.xsd"
)
_TPEXT_NS = "http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
_RWGPS_NS = "http://ridewithgps.com/rte"


def _sub(parent: ET.Element, tag: str, text: str | None = None, **attrib: str) -> ET.Element:
    el = ET.SubElement(parent, tag, attrib)
    if text is not None:
        el.text = text
    return el


def write_gpx(route: RouteData, path: str | Path, *, rwgps_compatible: bool = False) -> None:
    """
    Write *route* to *path* as a GPX 1.1 file.
    
    If *rwgps_compatible* is True, cues are written as <rte>/<rtept> elements
    with RideWithGPS extensions instead of <wpt> elements.
    """
    ET.register_namespace("", _GPX_NS)
    ET.register_namespace("gpxtpx", _TPEXT_NS)
    if rwgps_compatible:
        ET.register_namespace("rwgps", _RWGPS_NS)

    root = ET.Element(
        f"{{{_GPX_NS}}}gpx",
        {
            "version": "1.1",
            "creator": "gpx-editor",
            f"{{{_XSI}}}schemaLocation": _SCHEMA_LOC,
        },
    )

    if rwgps_compatible:
        _write_pois_only(root, route.pois)
        _write_route_with_cues(root, route.cues, route.track_points)
    else:
        _write_waypoints(root, route.cues, route.pois)
    _write_track(root, route.track_points)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(str(path), encoding="utf-8", xml_declaration=True)


# ---------------------------------------------------------------------------
# Waypoints
# ---------------------------------------------------------------------------

def _write_waypoints(
    root: ET.Element, cues: pl.DataFrame, pois: pl.DataFrame,
) -> None:
    for row in cues.iter_rows(named=True):
        wpt = _sub(root, f"{{{_GPX_NS}}}wpt", lat=str(row["lat"]), lon=str(row["lon"]))
        if row["name"]:
            _sub(wpt, f"{{{_GPX_NS}}}name", row["name"])
        if row["description"]:
            _sub(wpt, f"{{{_GPX_NS}}}desc", row["description"])
        _sub(wpt, f"{{{_GPX_NS}}}type", to_garmin(row["cue_type"] or "", "Left"))

    for row in pois.iter_rows(named=True):
        wpt = _sub(root, f"{{{_GPX_NS}}}wpt", lat=str(row["lat"]), lon=str(row["lon"]))
        if row["name"]:
            _sub(wpt, f"{{{_GPX_NS}}}name", row["name"])
        if row["description"]:
            _sub(wpt, f"{{{_GPX_NS}}}desc", row["description"])
        if row["symbol"]:
            _sub(wpt, f"{{{_GPX_NS}}}sym", row["symbol"])
        _sub(wpt, f"{{{_GPX_NS}}}type", symbol_to_garmin(row["symbol"] or ""))


def _write_pois_only(root: ET.Element, pois: pl.DataFrame) -> None:
    """Write only POIs as <wpt> elements (cues go in <rte>)."""
    for row in pois.iter_rows(named=True):
        wpt = _sub(root, f"{{{_GPX_NS}}}wpt", lat=str(row["lat"]), lon=str(row["lon"]))
        if row["name"]:
            _sub(wpt, f"{{{_GPX_NS}}}name", row["name"])
        if row["description"]:
            _sub(wpt, f"{{{_GPX_NS}}}desc", row["description"])
        if row["symbol"]:
            _sub(wpt, f"{{{_GPX_NS}}}sym", row["symbol"])
        _sub(wpt, f"{{{_GPX_NS}}}type", symbol_to_garmin(row["symbol"] or ""))


def _write_route_with_cues(
    root: ET.Element, cues: pl.DataFrame, track_points: pl.DataFrame,
) -> None:
    """Write cues as <rte>/<rtept> with RideWithGPS extensions."""
    if len(cues) == 0:
        return

    rte = _sub(root, f"{{{_GPX_NS}}}rte")
    _sub(rte, f"{{{_GPX_NS}}}name", "Route")

    for row in cues.iter_rows(named=True):
        rtept = _sub(rte, f"{{{_GPX_NS}}}rtept", lat=str(row["lat"]), lon=str(row["lon"]))
        if row["name"]:
            _sub(rtept, f"{{{_GPX_NS}}}name", row["name"])
        if row["description"]:
            _sub(rtept, f"{{{_GPX_NS}}}desc", row["description"])

        ext = _sub(rtept, f"{{{_GPX_NS}}}extensions")
        if row["cue_type"]:
            _sub(ext, f"{{{_RWGPS_NS}}}cue", row["cue_type"])
        if row["description"]:
            _sub(ext, f"{{{_RWGPS_NS}}}description", row["description"])


# ---------------------------------------------------------------------------
# Track
# ---------------------------------------------------------------------------

def _write_track(root: ET.Element, track_points: pl.DataFrame) -> None:
    if len(track_points) == 0:
        return
    trk = _sub(root, f"{{{_GPX_NS}}}trk")
    trkseg = _sub(trk, f"{{{_GPX_NS}}}trkseg")

    has_hr = "hr" in track_points.columns
    has_cad = "cadence" in track_points.columns
    has_pwr = "power" in track_points.columns

    for row in track_points.iter_rows(named=True):
        trkpt = _sub(
            trkseg,
            f"{{{_GPX_NS}}}trkpt",
            lat=str(row["lat"]),
            lon=str(row["lon"]),
        )
        if row.get("elevation") is not None:
            _sub(trkpt, f"{{{_GPX_NS}}}ele", str(row["elevation"]))
        if row.get("time") is not None:
            _sub(trkpt, f"{{{_GPX_NS}}}time", row["time"].isoformat() + "Z")

        hr = row.get("hr") if has_hr else None
        cad = row.get("cadence") if has_cad else None
        pwr = row.get("power") if has_pwr else None
        if any(v is not None for v in (hr, cad, pwr)):
            ext = _sub(trkpt, f"{{{_GPX_NS}}}extensions")
            tpe = _sub(ext, f"{{{_TPEXT_NS}}}TrackPointExtension")
            if hr is not None:
                _sub(tpe, f"{{{_TPEXT_NS}}}hr", str(hr))
            if cad is not None:
                _sub(tpe, f"{{{_TPEXT_NS}}}cad", str(cad))
            if pwr is not None:
                _sub(tpe, f"{{{_TPEXT_NS}}}power", str(pwr))
