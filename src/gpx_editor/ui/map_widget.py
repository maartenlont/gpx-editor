"""Interactive map widget: Folium/Leaflet rendered inside QWebEngineView."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import json

import numpy as np
import folium
from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
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

# Injected after the map alias is set: adds the "+ POI" Leaflet control and
# a click handler that forwards coordinates to the Python backend.
_ADD_POI_JS = """
(function () {
    var _addPoiMode = false;
    var _addPoiBtn = null;

    var AddPoiControl = L.Control.extend({
        options: { position: 'topleft' },
        onAdd: function (map) {
            var btn = L.DomUtil.create('button', '');
            btn.innerHTML = '+ POI';
            btn.title = 'Activate, then click the map to place a POI';
            btn.style.cssText = [
                'display:block', 'padding:4px 9px',
                'background:white', 'border:2px solid rgba(0,0,0,0.2)',
                'border-radius:4px', 'cursor:pointer',
                'font-size:12px', 'font-family:sans-serif', 'margin-top:2px'
            ].join(';');
            _addPoiBtn = btn;
            L.DomEvent.on(btn, 'click', function (e) {
                L.DomEvent.stopPropagation(e);
                _addPoiMode = !_addPoiMode;
                btn.style.background = _addPoiMode ? '#e74c3c' : 'white';
                btn.style.color    = _addPoiMode ? 'white'   : '';
                var lc = document.querySelector('.leaflet-container');
                if (lc) lc.style.cursor = _addPoiMode ? 'crosshair' : '';
            });
            return btn;
        }
    });
    new AddPoiControl().addTo(window._gpxMap);

    window._gpxMap.on('click', function (e) {
        if (_addPoiMode && typeof backend !== 'undefined') {
            backend.onMapClick(e.latlng.lat, e.latlng.lng);
        }
    });
}());
"""

# Injected once after the map is ready: creates the OSM overlay layer.
_OSM_LAYER_JS = "window._osmLayer = L.layerGroup().addTo(window._gpxMap);"

# Maximum polyline points sent to Leaflet; larger tracks are downsampled.
_MAX_POLYLINE_PTS = 5_000


def _simplify(lats: list[float], lons: list[float]) -> tuple[list[float], list[float]]:
    """Stride-downsample a track to at most _MAX_POLYLINE_PTS points."""
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


class _MapBackend(QObject):
    """Thin QObject bridge: Leaflet JS ↔ Python signals."""

    map_clicked = Signal(float, float)
    osm_poi_add = Signal(float, float, str, str, str)

    @Slot(float, float)
    def onMapClick(self, lat: float, lon: float) -> None:
        self.map_clicked.emit(lat, lon)

    @Slot(float, float, str, str, str)
    def onOsmPoiAdd(
        self, lat: float, lon: float, name: str, description: str, symbol: str
    ) -> None:
        self.osm_poi_add.emit(lat, lon, name, description, symbol)


class MapWidget(QWebEngineView):
    # Emitted when the user clicks the map while "+ POI" mode is active.
    poi_requested = Signal(float, float)
    # Emitted when the user right-clicks an OSM overlay marker.
    osm_poi_add = Signal(float, float, str, str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self._tmp_path: str | None = None
        self._map_js_name: str | None = None
        self._map_ready = False
        self._map_loaded_connected = False
        self._osm_df = None  # persisted across map reloads

        # Wire JS↔Python bridge via QWebChannel
        self._backend = _MapBackend()
        self._backend.map_clicked.connect(self.poi_requested)
        self._backend.osm_poi_add.connect(self.osm_poi_add)
        self._channel = QWebChannel(self.page())
        self._channel.registerObject("backend", self._backend)
        self.page().setWebChannel(self._channel)

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

        for entry in visible:
            tp = entry.route.track_points
            if len(tp) == 0:
                continue
            s_lats, s_lons = _simplify(tp["lat"].to_list(), tp["lon"].to_list())
            folium.PolyLine(
                list(zip(s_lats, s_lons)),
                color=entry.color,
                weight=3,
                opacity=0.85,
            ).add_to(m)

        if 0 <= active_index < len(entries):
            active_entry = entries[active_index]
            if active_entry.visible:
                self._add_markers(m, active_entry.route)

        m.fit_bounds([[min(all_lats), min(all_lons)], [max(all_lats), max(all_lons)]])

        self._map_js_name = m.get_name()
        self._save_and_load(m)

    def zoom_to(self, lat: float, lon: float, zoom: int = 16) -> None:
        if self._map_ready:
            self.page().runJavaScript(
                f"if (window._gpxMap) {{ window._gpxMap.setView([{lat}, {lon}], {zoom}); }}"
            )

    def load_osm_pois(self, df) -> None:
        """Store and inject OSM POI markers. Persists across map reloads."""
        self._osm_df = df
        self._inject_osm_pois()

    def clear_osm_pois(self) -> None:
        """Remove all OSM overlay markers and clear the stored overlay."""
        self._osm_df = None
        if self._map_ready:
            self.page().runJavaScript(
                "if (window._osmLayer) { window._osmLayer.clearLayers(); }"
            )

    def _inject_osm_pois(self) -> None:
        """(Re-)inject the stored OSM overlay into the live map."""
        if not self._map_ready or self._osm_df is None:
            return
        self.page().runJavaScript(
            "if (window._osmLayer) { window._osmLayer.clearLayers(); }"
        )
        rows = self._osm_df.to_dicts()
        if not rows:
            return
        js_parts = ["(function() {"]
        for row in rows:
            lat = row["lat"]
            lon = row["lon"]
            name = json.dumps(row["name"] or "")
            desc = json.dumps(row["description"] or "")
            symbol = json.dumps(row["symbol"] or "generic")
            popup_html = json.dumps(
                f"<b>{row['name'] or ''}</b>"
                + (f"<br>{row['description']}" if row["description"] else "")
                + "<br><i>Right-click to add to track</i>"
            )
            js_parts.append(
                f"(function() {{"
                f"  var m = L.circleMarker([{lat}, {lon}], "
                f"    {{radius:8, color:'#1565C0', fillColor:'#42A5F5',"
                f"     fillOpacity:0.85, weight:2}});"
                f"  m.bindPopup({popup_html});"
                f"  m.on('contextmenu', function(e) {{"
                f"    L.DomEvent.stopPropagation(e);"
                f"    if (typeof backend !== 'undefined') {{"
                f"      backend.onOsmPoiAdd({lat}, {lon}, {name}, {desc}, {symbol});"
                f"    }}"
                f"  }});"
                f"  m.addTo(window._osmLayer);"
                f"}})();"
            )
        js_parts.append("})();")
        self.page().runJavaScript("\n".join(js_parts))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_markers(self, m: folium.Map, route: RouteData) -> None:
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

        # Inject qwebchannel.js and channel initialisation into the saved HTML.
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
        html = html.replace(
            "</head>",
            '<script src="qrc:///qtwebchannel/qwebchannel.js"></script>\n</head>',
            1,
        )
        html = html.replace(
            "</body>",
            "<script>\n"
            "var backend;\n"
            "new QWebChannel(qt.webChannelTransport, function(ch) {\n"
            "    backend = ch.objects.backend;\n"
            "});\n"
            "</script>\n</body>",
            1,
        )
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)

        self._tmp_path = path
        self._map_ready = False

        if self._map_loaded_connected:
            self.loadFinished.disconnect(self._on_map_loaded)
        self.loadFinished.connect(self._on_map_loaded)
        self._map_loaded_connected = True
        self.load(QUrl.fromLocalFile(path))

    def _on_map_loaded(self, ok: bool) -> None:
        if self._map_loaded_connected:
            self.loadFinished.disconnect(self._on_map_loaded)
            self._map_loaded_connected = False
        if ok and self._map_js_name:
            js = (
                f"window._gpxMap = {self._map_js_name};\n"
                f"{_OSM_LAYER_JS}\n"
                f"{_ADD_POI_JS}"
            )

            def _on_ready(_):
                self._map_ready = True
                self._inject_osm_pois()

            self.page().runJavaScript(js, _on_ready)
