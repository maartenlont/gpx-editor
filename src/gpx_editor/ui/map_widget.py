"""Interactive map widget: Folium/Leaflet rendered inside QWebEngineView."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np
import folium
from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from gpx_editor.models.route import RouteData

_PLACEHOLDER_HTML = """
<html>
<body style="background:#1e1e1e;display:flex;align-items:center;
             justify-content:center;height:100vh;margin:0;">
  <p style="color:#666;font-family:sans-serif;font-size:16px;">
    Open a GPX or TCX file to display the map
  </p>
</body>
</html>
"""

# cue_type (lower-case) → (Bootstrap Glyphicon name, folium color)
_CUE_ICON: dict[str, tuple[str, str]] = {
    "left":          ("arrow-left",  "red"),
    "turn left":     ("arrow-left",  "red"),
    "sharp left":    ("arrow-left",  "darkred"),
    "slight left":   ("arrow-left",  "orange"),
    "bear left":     ("arrow-left",  "orange"),
    "fork left":     ("arrow-left",  "orange"),
    "right":         ("arrow-right", "red"),
    "turn right":    ("arrow-right", "red"),
    "sharp right":   ("arrow-right", "darkred"),
    "slight right":  ("arrow-right", "orange"),
    "bear right":    ("arrow-right", "orange"),
    "fork right":    ("arrow-right", "orange"),
    "straight":      ("arrow-up",    "blue"),
    "continue":      ("arrow-up",    "blue"),
    "u-turn":        ("repeat",      "darkred"),
    "uturn":         ("repeat",      "darkred"),
    "roundabout":    ("refresh",     "purple"),
}
_DEFAULT_CUE_ICON = ("map-marker", "red")

# POI name (lower-case) → (Bootstrap Glyphicon name, folium color)
_POI_NAME_ICON: dict[str, tuple[str, str]] = {
    # Navigation cues
    "start":         ("flag",        "green"),
    "right":         ("arrow-right", "red"),
    "left":          ("arrow-left",  "red"),
    "sharp right":   ("arrow-right", "darkred"),
    "sharp left":    ("arrow-left",  "darkred"),
    "slight right":  ("arrow-right", "orange"),
    "slight left":   ("arrow-left",  "orange"),
    # Climb categories (cadetblue → blue → orange → red = easiest → hardest)
    "4th category":  ("chevron-up",  "cadetblue"),
    "3rd category":  ("chevron-up",  "blue"),
    "2nd category":  ("chevron-up",  "orange"),
    "1st category":  ("chevron-up",  "red"),
    # Fuel / pump stations
    "bp":            ("flash",       "darkgreen"),
    "omv":           ("flash",       "red"),
    # Points of interest
    "coffee":        ("coffee",      "beige"),
    "food":          ("cutlery",     "beige"),
    "restaurant":    ("cutlery",     "beige"),
    "water":         ("tint",        "blue"),
    "water fountain":("tint",        "blue"),
    "parking":       ("car",         "gray"),
    "hospital":      ("plus-sign",   "red"),
    "bike":          ("wrench",      "darkblue"),
    "photo":         ("camera",      "purple"),
    "summit":        ("flag",        "darkred"),
    "waypoint":      ("map-marker",  "green"),
    "generic":       ("info-sign",   "green"),
}
_DEFAULT_POI_ICON = ("info-sign", "green")

# Maximum polyline points sent to Leaflet; larger tracks are downsampled.
_MAX_POLYLINE_PTS = 5_000


def _simplify(lats: list[float], lons: list[float]) -> tuple[list[float], list[float]]:
    """Stride-downsample a track to at most _MAX_POLYLINE_PTS points.

    First and last points are always preserved so the route ends correctly.
    """
    n = len(lats)
    if n <= _MAX_POLYLINE_PTS:
        return lats, lons
    step = max(2, n // _MAX_POLYLINE_PTS)
    arr_lat = np.array(lats)
    arr_lon = np.array(lons)
    idx = np.arange(0, n, step)
    if idx[-1] != n - 1:
        idx = np.append(idx, n - 1)
    return arr_lat[idx].tolist(), arr_lon[idx].tolist()


class MapWidget(QWebEngineView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Folium loads Leaflet.js and OSM tiles from CDN; allow file:// pages to
        # make those remote requests (blocked by default in QWebEngineView).
        self.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self._tmp_path: str | None = None
        self._map_js_name: str | None = None
        self._map_ready = False
        self.setHtml(_PLACEHOLDER_HTML)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_route(self, route: RouteData) -> None:
        tp = route.track_points
        if len(tp) == 0:
            self.setHtml(_PLACEHOLDER_HTML)
            return

        lats = tp["lat"].to_list()
        lons = tp["lon"].to_list()
        center = [sum(lats) / len(lats), sum(lons) / len(lons)]

        m = folium.Map(location=center, zoom_start=13, control_scale=True)

        # Track polyline — simplified for large files
        s_lats, s_lons = _simplify(lats, lons)
        folium.PolyLine(
            list(zip(s_lats, s_lons)), color="#1565C0", weight=3, opacity=0.85
        ).add_to(m)

        # Cue markers
        for row in route.cues.iter_rows(named=True):
            key = row["cue_type"].lower() if row["cue_type"] else ""
            icon_name, color = _CUE_ICON.get(key, _DEFAULT_CUE_ICON)
            folium.Marker(
                [row["lat"], row["lon"]],
                popup=folium.Popup(
                    f"<b>{row['name']}</b><br>{row['cue_type']}", max_width=200
                ),
                tooltip=row["name"],
                icon=folium.Icon(color=color, icon=icon_name),
            ).add_to(m)

        # POI markers — icon mapped from name column
        for row in route.pois.iter_rows(named=True):
            name_key = (row["name"] or "").lower()
            icon_name, color = _POI_NAME_ICON.get(name_key, _DEFAULT_POI_ICON)
            folium.Marker(
                [row["lat"], row["lon"]],
                popup=folium.Popup(
                    f"<b>{row['name']}</b><br>{row.get('description', '')}", max_width=200
                ),
                tooltip=row["name"],
                icon=folium.Icon(color=color, icon=icon_name),
            ).add_to(m)

        # Fit map to track bounds
        m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])

        self._map_js_name = m.get_name()
        self._save_and_load(m)

    def zoom_to(self, lat: float, lon: float, zoom: int = 16) -> None:
        if self._map_ready:
            self.page().runJavaScript(
                f"if (window._gpxMap) {{ window._gpxMap.setView([{lat}, {lon}], {zoom}); }}"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save_and_load(self, m: folium.Map) -> None:
        if self._tmp_path and Path(self._tmp_path).exists():
            try:
                os.unlink(self._tmp_path)
            except OSError:
                pass

        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        m.save(path)
        self._tmp_path = path
        self._map_ready = False

        # Disconnect any stale handler from a previous load before reconnecting.
        try:
            self.loadFinished.disconnect(self._on_map_loaded)
        except RuntimeError:
            pass
        self.loadFinished.connect(self._on_map_loaded)
        self.load(QUrl.fromLocalFile(path))

    def _on_map_loaded(self, ok: bool) -> None:
        try:
            self.loadFinished.disconnect(self._on_map_loaded)
        except RuntimeError:
            pass
        if ok and self._map_js_name:
            # Set a stable alias now that the page JS has fully executed.
            self.page().runJavaScript(
                f"window._gpxMap = {self._map_js_name};",
                lambda _: setattr(self, "_map_ready", True),
            )
