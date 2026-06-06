"""Serialise a RouteData to a GPX file."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import polars as pl

from gpx_editor.models.route import RouteData

_GPX_NS = "http://www.topografix.com/GPX/1/1"
_XSI = "http://www.w3.org/2001/XMLSchema-instance"
_SCHEMA_LOC = (
    "http://www.topografix.com/GPX/1/1 "
    "http://www.topografix.com/GPX/1/1/gpx.xsd"
)
_TPEXT_NS = "http://www.garmin.com/xmlschemas/TrackPointExtension/v1"


def _sub(parent: ET.Element, tag: str, text: str | None = None, **attrib: str) -> ET.Element:
    el = ET.SubElement(parent, tag, attrib)
    if text is not None:
        el.text = text
    return el


def write_gpx(route: RouteData, path: str | Path) -> None:
    """Write *route* to *path* as a GPX 1.1 file."""
    ET.register_namespace("", _GPX_NS)
    ET.register_namespace("gpxtpx", _TPEXT_NS)

    root = ET.Element(
        f"{{{_GPX_NS}}}gpx",
        {
            "version": "1.1",
            "creator": "gpx-editor",
            f"{{{_XSI}}}schemaLocation": _SCHEMA_LOC,
        },
    )

    _write_waypoints(root, route.cues, route.pois)
    _write_track(root, route.track_points)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(str(path), encoding="utf-8", xml_declaration=True)


# ---------------------------------------------------------------------------
# Waypoints
# ---------------------------------------------------------------------------

def _write_waypoints(
    root: ET.Element, cues: pl.DataFrame, pois: pl.DataFrame
) -> None:
    for row in cues.iter_rows(named=True):
        wpt = _sub(root, f"{{{_GPX_NS}}}wpt", lat=str(row["lat"]), lon=str(row["lon"]))
        if row["name"]:
            _sub(wpt, f"{{{_GPX_NS}}}name", row["name"])
        if row["description"]:
            _sub(wpt, f"{{{_GPX_NS}}}desc", row["description"])
        if row["cue_type"]:
            _sub(wpt, f"{{{_GPX_NS}}}type", row["cue_type"])

    for row in pois.iter_rows(named=True):
        wpt = _sub(root, f"{{{_GPX_NS}}}wpt", lat=str(row["lat"]), lon=str(row["lon"]))
        if row["name"]:
            _sub(wpt, f"{{{_GPX_NS}}}name", row["name"])
        if row["description"]:
            _sub(wpt, f"{{{_GPX_NS}}}desc", row["description"])
        if row["symbol"]:
            _sub(wpt, f"{{{_GPX_NS}}}sym", row["symbol"])


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
