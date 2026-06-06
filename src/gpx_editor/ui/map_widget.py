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
from gpx_editor.models.route_entry import RouteEntry
from gpx_editor.ui.poi_icons import (
    CUE_ICON as _CUE_ICON,
    DEFAULT_CUE_ICON as _DEFAULT_CUE_ICON,
    POI_NAME_ICON as _POI_NAME_ICON,
    DEFAULT_POI_ICON as _DEFAULT_POI_ICON,
)

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

    def load_routes(self, entries: list[RouteEntry], active_index: int) -> None:
        """Render all visible routes; cue/POI markers only for the active entry."""
        visible = [e for e in entries if e.visible]
        if not visible:
            self.setHtml(_PLACEHOLDER_HTML)
            return

        # Collect all track points from visible entries for bounds/center
        all_lats: list[float] = []
        all_lons: list[float] = []
        for entry in visible:
            tp = entry.route.track_points
            if len(tp) > 0:
                all_lats.extend(tp["lat"].to_list())
                all_lons.extend(tp["lon"].to_list())

        if not all_lats:
            self.setHtml(_PLACEHOLDER_HTML)
            return

        center = [sum(all_lats) / len(all_lats), sum(all_lons) / len(all_lons)]
        m = folium.Map(location=center, zoom_start=13, control_scale=True)

        # Draw one PolyLine per visible entry
        for entry in visible:
            tp = entry.route.track_points
            if len(tp) == 0:
                continue
            lats = tp["lat"].to_list()
            lons = tp["lon"].to_list()
            s_lats, s_lons = _simplify(lats, lons)
            folium.PolyLine(
                list(zip(s_lats, s_lons)),
                color=entry.color,
                weight=3,
                opacity=0.85,
            ).add_to(m)

        # Draw cue/POI markers only for the active entry
        if 0 <= active_index < len(entries):
            active_entry = entries[active_index]
            if active_entry.visible:
                self._add_markers(m, active_entry.route)

        # Fit map to track bounds
        m.fit_bounds([[min(all_lats), min(all_lons)], [max(all_lats), max(all_lons)]])

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

    def _add_markers(self, m: folium.Map, route: RouteData) -> None:
        """Add cue and POI markers from *route* to the folium map *m*."""
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
