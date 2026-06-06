"""Interactive map widget: Folium/Leaflet rendered inside QWebEngineView."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import folium
import numpy as np
from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from gpx_editor.models.route import RouteData
from gpx_editor.models.route_entry import RouteEntry
from gpx_editor.ui.poi_icons import (
    CUE_ICON as _CUE_ICON,
)
from gpx_editor.ui.poi_icons import (
    DEFAULT_CUE_ICON as _DEFAULT_CUE_ICON,
)
from gpx_editor.ui.poi_icons import (
    DEFAULT_POI_ICON as _DEFAULT_POI_ICON,
)
from gpx_editor.ui.poi_icons import (
    POI_NAME_ICON as _POI_NAME_ICON,
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

# OSM symbol → pictogram mapping for map markers
_OSM_SYMBOL_PICTOGRAM: dict[str, str] = {
    "water":       "💧",
    "fuel":        "⛽",
    "lodging":     "🛏️",
    "convenience": "🏪",
    "shopping":    "🛒",
    "restaurant":  "🍽️",
    "cafe":        "☕",
    "parking":     "🅿️",
    "camping":     "⛺",
    "pharmacy":    "💊",
    "generic":     "📍",
}

# Injected once after the map is ready: creates the OSM overlay layer and
# a global helper so popup buttons can reach the Python backend.
_OSM_LAYER_JS = """
window._osmLayer = L.layerGroup().addTo(window._gpxMap);
window._addOsmPoi = function(lat, lon, name, desc, symbol, wptype) {
    if (typeof backend !== 'undefined') {
        backend.onOsmPoiAdd(lat, lon, name, desc, symbol, wptype);
    }
};
"""

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
    osm_poi_add = Signal(float, float, str, str, str, str)  # lat, lon, name, desc, symbol, wptype

    @Slot(float, float)
    def onMapClick(self, lat: float, lon: float) -> None:
        self.map_clicked.emit(lat, lon)

    @Slot(float, float, str, str, str, str)
    def onOsmPoiAdd(
        self, lat: float, lon: float, name: str, description: str, symbol: str, wptype: str,
    ) -> None:
        self.osm_poi_add.emit(lat, lon, name, description, symbol, wptype)


class MapWidget(QWebEngineView):
    # Emitted when the user clicks the map while "+ POI" mode is active.
    poi_requested = Signal(float, float)
    # Emitted when the user clicks an OSM overlay marker button (cue or poi).
    osm_poi_add = Signal(float, float, str, str, str, str)  # lat, lon, name, desc, symbol, wptype

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True,
        )
        self._tmp_path: str | None = None
        self._map_js_name: str | None = None
        self._map_ready = False
        self._map_loaded_connected = False
        self._osm_df = None           # persisted across map reloads
        self._restore_view: list | None = None  # [lat, lng, zoom] to restore after reload

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

        if self._restore_view is None:
            m.fit_bounds([[min(all_lats), min(all_lons)], [max(all_lats), max(all_lons)]])
        # else: _on_map_loaded will restore the captured view instead

        self._map_js_name = m.get_name()
        self._save_and_load(m)

    def get_current_view(self, callback) -> None:
        """Call callback([lat, lng, zoom]) with the live map state, or None if not ready."""
        if not self._map_ready:
            callback(None)
            return
        self.page().runJavaScript(
            "(function() {"
            "  if (!window._gpxMap) return null;"
            "  var c = window._gpxMap.getCenter();"
            "  return [c.lat, c.lng, window._gpxMap.getZoom()];"
            "})()",
            callback,
        )

    def schedule_view_restore(self, view: list) -> None:
        """Ask the next map reload to restore *view* instead of fitting bounds."""
        self._restore_view = view

    def zoom_to(self, lat: float, lon: float, zoom: int = 16) -> None:
        if self._map_ready:
            self.page().runJavaScript(
                f"if (window._gpxMap) {{ window._gpxMap.setView([{lat}, {lon}], {zoom}); }}",
            )

    def load_osm_pois(self, df) -> None:
        """Store and inject OSM POI markers. Persists across map reloads."""
        self._osm_df = df
        self._inject_osm_pois()

    def add_poi_marker(self, lat: float, lon: float, name: str, symbol: str) -> None:
        """Inject a single track-POI marker into the live map without reloading."""
        if not self._map_ready:
            return
        name_j = json.dumps(name)
        sym_j = json.dumps(symbol)
        popup_j = json.dumps(f"<b>{name}</b><br><i>{symbol}</i>")
        js = (
            f"(function(){{"
            f"  var icon = L.divIcon({{"
            f"    html: '<div style=\"width:12px;height:12px;border-radius:50%;"
            f"background:#2E7D32;border:2px solid white;"
            f"box-shadow:0 0 4px rgba(0,0,0,0.5)\"></div>',"
            f"    iconSize:[16,16], iconAnchor:[8,8], className:''"
            f"  }});"
            f"  L.marker([{lat},{lon}],{{icon:icon}})"
            f"    .bindPopup({popup_j})"
            f"    .addTo(window._gpxMap);"
            f"}})();"
        )
        self.page().runJavaScript(js)

    def clear_osm_pois(self) -> None:
        """Remove all OSM overlay markers and clear the stored overlay."""
        self._osm_df = None
        if self._map_ready:
            self.page().runJavaScript(
                "if (window._osmLayer) { window._osmLayer.clearLayers(); }",
            )

    def get_viewport_bbox(self, callback) -> None:
        """Call callback(south, west, north, east) with the current map viewport, or None."""
        if not self._map_ready:
            callback(None)
            return
        self.page().runJavaScript(
            "(function() {"
            "  if (!window._gpxMap) return null;"
            "  var b = window._gpxMap.getBounds();"
            "  return [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()];"
            "})()",
            callback,
        )

    def _inject_osm_pois(self) -> None:
        """(Re-)inject the stored OSM overlay into the live map."""
        if not self._map_ready or self._osm_df is None:
            return
        rows = self._osm_df.to_dicts()
        # Build a single JSON array; JS does the rest in one forEach — much faster
        # than one runJavaScript call per marker.
        data = [
            {
                "lat": r["lat"], "lon": r["lon"],
                "name": r["name"] or "", "desc": r["description"] or "",
                "symbol": r["symbol"] or "generic",
                "pictogram": _OSM_SYMBOL_PICTOGRAM.get(r["symbol"] or "generic", "📍"),
            }
            for r in rows
        ]
        data_j = json.dumps(data)
        js = f"""
(function() {{
  if (window._osmLayer) window._osmLayer.clearLayers();
  var pois = {data_j};
  pois.forEach(function(d) {{
    var name = d.name || '(unnamed)';
    var tipHtml  = '<b>' + name + '</b><br><i>' + d.symbol + '</i>';
    var popLines = ['<b>' + name + '</b>'];
    if (d.desc) popLines.push(d.desc);
    popLines.push('<i>Type: ' + d.symbol + '</i>');
    popLines.push('<div style="margin-top:6px;display:flex;gap:4px;">');
    popLines.push('<button class="osm-add-cue-btn" style="padding:3px 8px;cursor:pointer;background:#E65100;color:white;border:none;border-radius:3px">+ Cue</button>');
    popLines.push('<button class="osm-add-poi-btn" style="padding:3px 8px;cursor:pointer;background:#2E7D32;color:white;border:none;border-radius:3px">+ POI</button>');
    popLines.push('</div>');
    var icon = L.divIcon({{
      html: '<div style="display:flex;align-items:center;justify-content:center;' +
            'width:28px;height:28px;border-radius:50%;background:#1565C0;' +
            'border:2px solid white;box-shadow:0 2px 5px rgba(0,0,0,0.3);' +
            'font-size:14px;">' + d.pictogram + '</div>',
      iconSize: [28, 28],
      iconAnchor: [14, 14],
      popupAnchor: [0, -14],
      className: ''
    }});
    var m = L.marker([d.lat, d.lon], {{ icon: icon }});
    m.bindTooltip(tipHtml, {{sticky:true}});
    m.bindPopup(popLines.join('<br>'), {{maxWidth:260}});
    m.on('popupopen', function() {{
      var popup = m.getPopup().getElement();
      var cueBtn = popup.querySelector('.osm-add-cue-btn');
      var poiBtn = popup.querySelector('.osm-add-poi-btn');
      if (cueBtn) cueBtn.addEventListener('click', function() {{
        window._addOsmPoi(d.lat, d.lon, d.name, d.desc, d.symbol, 'cue');
      }});
      if (poiBtn) poiBtn.addEventListener('click', function() {{
        window._addOsmPoi(d.lat, d.lon, d.name, d.desc, d.symbol, 'poi');
      }});
    }});
    m.addTo(window._osmLayer);
  }});
}})();
"""
        self.page().runJavaScript(js)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_markers(self, m: folium.Map, route: RouteData) -> None:
        for row in route.cues.iter_rows(named=True):
            key = row["cue_type"].lower() if row["cue_type"] else ""
            icon_name, color = _CUE_ICON.get(key, _DEFAULT_CUE_ICON)
            dist_km = row["distance"] / 1000.0 if row["distance"] is not None else None
            popup_parts = [f"<b>{row['name']}</b>", row["cue_type"] or ""]
            if dist_km is not None:
                popup_parts.append(f"📍 {dist_km:.2f} km")
            folium.Marker(
                [row["lat"], row["lon"]],
                popup=folium.Popup("<br>".join(p for p in popup_parts if p), max_width=200),
                tooltip=row["name"],
                icon=folium.Icon(color=color, icon=icon_name),
            ).add_to(m)

        for row in route.pois.iter_rows(named=True):
            name_key = (row["name"] or "").lower()
            icon_name, color = _POI_NAME_ICON.get(name_key, _DEFAULT_POI_ICON)
            dist_km = row["distance"] / 1000.0 if row["distance"] is not None else None
            popup_parts = [f"<b>{row['name']}</b>", row.get("description") or ""]
            if dist_km is not None:
                popup_parts.append(f"📍 {dist_km:.2f} km")
            folium.Marker(
                [row["lat"], row["lon"]],
                popup=folium.Popup("<br>".join(p for p in popup_parts if p), max_width=200),
                tooltip=f"{row['name']} ({dist_km:.2f} km)" if dist_km is not None else row["name"],
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
                if self._restore_view is not None:
                    lat, lng, zoom = self._restore_view
                    self.page().runJavaScript(
                        f"window._gpxMap.setView([{lat},{lng}],{zoom},{{animate:false}});",
                    )
                    self._restore_view = None
                self._inject_osm_pois()

            self.page().runJavaScript(js, _on_ready)
