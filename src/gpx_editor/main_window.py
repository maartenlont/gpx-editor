"""MainWindow — assembles all widgets and wires signals."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
)

_RECENT_KEY = "recent_files"
_RECENT_MAX = 5
_QSETTINGS_ARGS = ("gpx-editor", "gpx-editor")

from gpx_editor.io._distance import nearest_index
from gpx_editor.io.fit_reader import read_fit
from gpx_editor.io.fit_writer import write_fit
from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.io.gpx_writer import write_gpx
from gpx_editor.io.osm_reader import OSM_CATEGORIES, query_osm_pois
from gpx_editor.io.tcx_reader import read_tcx
from gpx_editor.io.tcx_writer import write_tcx
from gpx_editor.models.route import CUES_SCHEMA, POIS_SCHEMA, RouteData
from gpx_editor.models.route_entry import RouteEntry, next_color
from gpx_editor.ui.elevation_widget import ElevationWidget
from gpx_editor.ui.map_widget import MapWidget
from gpx_editor.ui.right_panel import RightPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._routes: list[RouteEntry] = []
        self._active_index: int = -1
        self._open_path: Path | None = None
        self._dirty = False
        self._rwgps_compat: bool = False  # remembered across Save / Save As for GPX
        self._osm_cache: dict[tuple, object] = {}  # session cache: (category, bbox) → df
        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
        self._update_title()
        self.resize(1400, 800)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.map_widget = MapWidget()
        self.elevation_widget = ElevationWidget()

        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.addWidget(self.map_widget)
        left_splitter.addWidget(self.elevation_widget)
        left_splitter.setStretchFactor(0, 3)
        left_splitter.setStretchFactor(1, 1)

        self.right_panel = RightPanel()

        outer_splitter = QSplitter(Qt.Horizontal)
        outer_splitter.addWidget(left_splitter)
        outer_splitter.addWidget(self.right_panel)
        outer_splitter.setStretchFactor(0, 1)
        outer_splitter.setStretchFactor(1, 1)

        self.setCentralWidget(outer_splitter)

        self.right_panel.track_table.row_selected.connect(self._on_track_row_selected)
        self.right_panel.cue_table.row_selected.connect(self._on_waypoint_row_selected)
        self.right_panel.poi_table.row_selected.connect(self._on_waypoint_row_selected)
        self.elevation_widget.location_clicked.connect(self._on_elevation_clicked)
        self.map_widget.poi_requested.connect(self._on_poi_requested)
        self.map_widget.osm_poi_add.connect(self._on_osm_poi_add)

        # Wire route list signals
        self.right_panel.route_list.active_changed.connect(self._on_route_active_changed)
        self.right_panel.route_list.color_changed.connect(self._on_route_color_changed)
        self.right_panel.route_list.visibility_changed.connect(self._on_route_visibility_changed)
        self.right_panel.route_list.route_removed.connect(self._on_route_removed)
        self.right_panel.route_list.route_renamed.connect(self._on_route_renamed)

        # Wire filter signals — refresh map/elevation with the visible (filtered) subset
        self.right_panel.cue_table.filter_changed.connect(self._on_filter_changed)
        self.right_panel.poi_table.filter_changed.connect(self._on_filter_changed)

        # Wire cue/POI edit signals
        rp = self.right_panel
        rp.cue_table.row_deleted.connect(lambda idx: self._delete_waypoint("cues", idx))
        rp.cue_table.row_updated.connect(lambda idx, vals: self._update_waypoint("cues", idx, vals))
        rp.poi_table.row_deleted.connect(lambda idx: self._delete_waypoint("pois", idx))
        rp.poi_table.row_updated.connect(lambda idx, vals: self._update_waypoint("pois", idx, vals))

    def _setup_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        open_act = file_menu.addAction("&Open…")
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._open_file)

        self._recent_menu = file_menu.addMenu("Open &Recent")
        self._rebuild_recent_menu()

        self._clear_act = file_menu.addAction("&Clear All")
        self._clear_act.triggered.connect(self._clear_all)

        file_menu.addSeparator()

        self._save_act = file_menu.addAction("&Save")
        self._save_act.setShortcut("Ctrl+S")
        self._save_act.setEnabled(False)
        self._save_act.triggered.connect(self._save)

        self._save_as_act = file_menu.addAction("Save &As…")
        self._save_as_act.setShortcut("Ctrl+Shift+S")
        self._save_as_act.setEnabled(False)
        self._save_as_act.triggered.connect(self._save_as)

        file_menu.addSeparator()

        exit_act = file_menu.addAction("E&xit")
        exit_act.setShortcut("Ctrl+Q")
        exit_act.triggered.connect(self.close)

        edit_menu = self.menuBar().addMenu("&Edit")
        self._merge_act = edit_menu.addAction("&Merge Cues && POIs…")
        self._merge_act.setEnabled(False)
        self._merge_act.triggered.connect(self._open_merge_dialog)

        self._osm_act = edit_menu.addAction("Import &OSM POIs…")
        self._osm_act.setEnabled(False)
        self._osm_act.triggered.connect(self._open_osm_dialog)

        edit_menu.addSeparator()

        self._dedup_act = edit_menu.addAction("Remove &Duplicates…")
        self._dedup_act.setEnabled(False)
        self._dedup_act.triggered.connect(self._remove_duplicates)

        self._fix_symbols_act = edit_menu.addAction("Fix &Symbols")
        self._fix_symbols_act.setEnabled(False)
        self._fix_symbols_act.triggered.connect(self._fix_symbols)

    def _setup_status_bar(self) -> None:
        self._status_label = QLabel("No file loaded")
        self.statusBar().addWidget(self._status_label)

    # ------------------------------------------------------------------
    # File slots
    # ------------------------------------------------------------------

    def _open_file(self) -> None:
        start = str(self._open_path.parent) if self._open_path else ""
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open GPX / TCX file(s)",
            start,
            "Route files (*.gpx *.tcx *.fit);;GPX files (*.gpx);;TCX files (*.tcx);;FIT files (*.fit)",
        )
        for path in paths:
            self._load_path(Path(path))

    def _load_path(self, path: Path) -> bool:
        """Load a single file, append it as a new route, return True on success."""
        route = self._read_file(path)
        if route is None:
            return False
        used_colors = [e.color for e in self._routes]
        color = next_color(used_colors)
        entry = RouteEntry(route=route, color=color, label=path.stem)
        self._routes.append(entry)
        self._active_index = len(self._routes) - 1
        self._open_path = path
        self._merge_act.setEnabled(len(self._routes) >= 2)
        self._push_recent(path)
        self._refresh_view()
        self._set_dirty(False)
        return True

    # ------------------------------------------------------------------
    # Recent-files helpers
    # ------------------------------------------------------------------

    def _push_recent(self, path: Path) -> None:
        s = QSettings(*_QSETTINGS_ARGS)
        recent: list[str] = s.value(_RECENT_KEY, []) or []
        path_str = str(path)
        if path_str in recent:
            recent.remove(path_str)
        recent.insert(0, path_str)
        s.setValue(_RECENT_KEY, recent[:_RECENT_MAX])
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self) -> None:
        self._recent_menu.clear()
        s = QSettings(*_QSETTINGS_ARGS)
        recent: list[str] = s.value(_RECENT_KEY, []) or []
        if not recent:
            act = self._recent_menu.addAction("No recent files")
            act.setEnabled(False)
            return
        for path_str in recent:
            p = Path(path_str)
            label = f"{p.parent.name}/{p.name}" if p.parent.name else p.name
            act = self._recent_menu.addAction(label)
            act.setToolTip(path_str)
            act.triggered.connect(lambda checked=False, ps=path_str: self._open_recent(ps))
        self._recent_menu.addSeparator()
        clear_act = self._recent_menu.addAction("Clear Recent Files")
        clear_act.triggered.connect(self._clear_recent)

    def _open_recent(self, path_str: str) -> None:
        path = Path(path_str)
        if not path.exists():
            QMessageBox.warning(
                self, "File not found",
                f"'{path.name}' no longer exists at:\n{path_str}",
            )
            self._remove_recent(path_str)
            return
        self._load_path(path)

    def _remove_recent(self, path_str: str) -> None:
        s = QSettings(*_QSETTINGS_ARGS)
        recent: list[str] = s.value(_RECENT_KEY, []) or []
        if path_str in recent:
            recent.remove(path_str)
            s.setValue(_RECENT_KEY, recent)
        self._rebuild_recent_menu()

    def _clear_recent(self) -> None:
        QSettings(*_QSETTINGS_ARGS).remove(_RECENT_KEY)
        self._rebuild_recent_menu()

    def _clear_all(self) -> None:
        self._routes = []
        self._active_index = -1
        self._open_path = None
        # Reset all widgets to empty/placeholder state
        self.map_widget.load_routes([], -1)
        self.elevation_widget.load_routes([], -1)
        self.right_panel.set_routes([], -1)
        self.right_panel.setTabText(1, "Track Points")
        self.right_panel.setTabText(2, "Cues")
        self.right_panel.setTabText(3, "POIs")
        self._merge_act.setEnabled(False)
        self._set_dirty(False)
        self._update_title()
        self._status_label.setText("No file loaded")

    def _read_file(self, path: Path):
        try:
            suffix = path.suffix.lower()
            if suffix == ".gpx":
                return read_gpx(path)
            if suffix == ".tcx":
                return read_tcx(path)
            if suffix == ".fit":
                return read_fit(path)
            QMessageBox.warning(self, "Unsupported format", f"Unknown file type: {path.suffix}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error loading file", str(exc))
        return None

    def _save(self) -> None:
        """Overwrite the currently open file without prompting."""
        if not self._routes or self._active_index < 0 or self._open_path is None:
            return
        self._write_route(self._routes[self._active_index].route, self._open_path)

    def _save_as(self) -> None:
        if not self._routes or self._active_index < 0:
            return
        active_entry = self._routes[self._active_index]
        start_dir = str(self._open_path.parent) if self._open_path else ""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save route as…",
            start_dir,
            "GPX file (*.gpx);;TCX file (*.tcx);;FIT file (*.fit)",
        )
        if not path:
            return
        out = Path(path)
        if out.suffix.lower() not in (".gpx", ".tcx", ".fit"):
            out = out.with_suffix(".gpx")
        self._write_route(active_entry.route, out)

    def _write_route(self, route, out: Path) -> None:
        """Write *route* to *out*; asks about RideWithGPS compat for GPX files."""
        suffix = out.suffix.lower()
        if suffix == ".gpx":
            rwgps_compat = self._ask_rwgps_compatibility()
            if rwgps_compat is None:
                return
            self._rwgps_compat = rwgps_compat
        try:
            if suffix == ".gpx":
                write_gpx(route, out, rwgps_compatible=self._rwgps_compat)
            elif suffix == ".tcx":
                write_tcx(route, out)
            else:
                write_fit(route, out)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error saving file", str(exc))
            return
        self._open_path = out
        self._set_dirty(False)

    def _ask_rwgps_compatibility(self) -> bool | None:
        """Show dialog asking about RideWithGPS compatibility. Returns None if cancelled."""
        dialog = QDialog(self)
        dialog.setWindowTitle("GPX Export Options")
        layout = QVBoxLayout(dialog)

        checkbox = QCheckBox("RideWithGPS compatible (export cues as route points)")
        checkbox.setToolTip(
            "Enable this to see turn-by-turn cues in RideWithGPS.\n"
            "Cues will be written as route points with rwgps extensions.",
        )
        layout.addWidget(checkbox)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            return checkbox.isChecked()
        return None

    # ------------------------------------------------------------------
    # Merge slot
    # ------------------------------------------------------------------

    def _open_merge_dialog(self) -> None:
        if len(self._routes) < 2:
            return

        from gpx_editor.ui.merge_dialog import MergeDialog

        dlg = MergeDialog(self._routes, self)
        if dlg.exec() == MergeDialog.DialogCode.Accepted:
            result = dlg.get_result()
            if result is not None:
                merged_route, label = result
                used_colors = [e.color for e in self._routes]
                color = next_color(used_colors)
                new_entry = RouteEntry(route=merged_route, color=color, label=label)
                self._routes.append(new_entry)
                self._active_index = len(self._routes) - 1
                self._merge_act.setEnabled(len(self._routes) >= 2)
                self._refresh_view()
                self._set_dirty(True)

    # ------------------------------------------------------------------
    # Route list slots
    # ------------------------------------------------------------------

    def _on_route_active_changed(self, index: int) -> None:
        if self._active_index == index:
            return
        self._active_index = index
        self._refresh_view()

    def _on_route_color_changed(self, index: int, hex_color: str) -> None:
        if 0 <= index < len(self._routes):
            entry = self._routes[index]
            self._routes[index] = RouteEntry(
                route=entry.route,
                color=hex_color,
                label=entry.label,
                visible=entry.visible,
            )
            self._refresh_view_preserve_map()

    def _on_route_visibility_changed(self, index: int, visible: bool) -> None:
        if 0 <= index < len(self._routes):
            entry = self._routes[index]
            self._routes[index] = RouteEntry(
                route=entry.route,
                color=entry.color,
                label=entry.label,
                visible=visible,
            )
            self._refresh_view_preserve_map()

    def _refresh_view_preserve_map(self) -> None:
        """Reload all widgets while keeping the current map zoom and position."""
        def _do_refresh(view):
            if view:
                self.map_widget.schedule_view_restore(view)
            self._refresh_view()
        self.map_widget.get_current_view(_do_refresh)

    def _on_route_removed(self, index: int) -> None:
        if 0 <= index < len(self._routes):
            self._routes.pop(index)
            if not self._routes:
                self._active_index = -1
            elif self._active_index >= len(self._routes):
                self._active_index = len(self._routes) - 1
            self._merge_act.setEnabled(len(self._routes) >= 2)
            self._refresh_view()

    def _on_route_renamed(self, index: int, label: str) -> None:
        if 0 <= index < len(self._routes):
            e = self._routes[index]
            self._routes[index] = RouteEntry(
                route=e.route, color=e.color, label=label, visible=e.visible,
            )
            self._set_dirty(True)
            self._refresh_view()

    # ------------------------------------------------------------------
    # Waypoint (cue / POI) mutation slots
    # ------------------------------------------------------------------

    def _on_poi_requested(self, lat: float, lon: float) -> None:
        """User clicked the map in Add-POI mode: snap, prompt, append."""
        if self._active_index < 0 or not self._routes:
            return
        route = self._routes[self._active_index].route
        if len(route.track_points) == 0:
            QMessageBox.information(self, "No track", "Load a route with track points first.")
            return

        tp = route.track_points
        snap_idx, _ = nearest_index(lat, lon, tp["lat"].to_numpy(), tp["lon"].to_numpy())
        snap_lat = float(tp["lat"][snap_idx])
        snap_lon = float(tp["lon"][snap_idx])
        snap_dist = float(tp["distance"][snap_idx])

        from gpx_editor.ui.row_edit_dialog import RowEditDialog
        dlg = RowEditDialog(
            row_data={"name": "", "symbol": "", "description": ""},
            editable_cols=["name", "symbol", "description"],
            title="Add POI",
            parent=self,
        )
        if dlg.exec() != RowEditDialog.DialogCode.Accepted:
            return

        vals = dlg.get_values()
        name = (vals.get("name") or "").strip()
        if not name:
            return  # name is required

        existing = route.pois
        if len(existing) > 0:
            max_idx = existing["index"].max()
            next_idx = (int(max_idx) if max_idx is not None else 0) + 1
        else:
            next_idx = 0

        new_poi = pl.DataFrame(
            {
                "index":       [next_idx],
                "lat":         [snap_lat],
                "lon":         [snap_lon],
                "name":        [name],
                "description": [vals.get("description")],
                "symbol":      [vals.get("symbol")],
                "distance":    [snap_dist],
            },
            schema=POIS_SCHEMA,
        )
        self._update_active_route(pois=pl.concat([existing, new_poi]))

    def _delete_waypoint(self, attr: str, index_val: int) -> None:
        if self._active_index < 0 or not self._routes:
            return
        df: pl.DataFrame = getattr(self._routes[self._active_index].route, attr)
        new_df = df.filter(pl.col("index") != index_val)
        self._update_active_route(**{attr: new_df})

    def _update_waypoint(self, attr: str, index_val: int, new_vals: dict) -> None:
        if self._active_index < 0 or not self._routes:
            return
        df: pl.DataFrame = getattr(self._routes[self._active_index].route, attr)
        rows = df.to_dicts()
        for row in rows:
            if row["index"] == index_val:
                row.update(new_vals)
                break
        self._update_active_route(**{attr: pl.DataFrame(rows, schema=df.schema)})

    def _update_active_route(self, **kwargs) -> None:
        """Replace the active route's DataFrames with the given overrides."""
        if self._active_index < 0 or not self._routes:
            return
        e = self._routes[self._active_index]
        r = e.route
        new_route = RouteData(
            track_points=kwargs.get("track_points", r.track_points),
            cues=kwargs.get("cues", r.cues),
            pois=kwargs.get("pois", r.pois),
            source_file=r.source_file,
        )
        self._routes[self._active_index] = RouteEntry(
            route=new_route, color=e.color, label=e.label, visible=e.visible,
        )
        self._set_dirty(True)
        self._refresh_view()

    # ------------------------------------------------------------------
    # OSM import slots
    # ------------------------------------------------------------------

    def _open_osm_dialog(self) -> None:
        if self._active_index < 0 or not self._routes:
            return
        route = self._routes[self._active_index].route
        if len(route.track_points) == 0:
            QMessageBox.information(self, "No track", "Load a route with track points first.")
            return

        from gpx_editor.ui.osm_query_dialog import OsmQueryDialog
        dlg = OsmQueryDialog(self)
        if dlg.exec() != OsmQueryDialog.DialogCode.Accepted:
            return

        category = dlg.category()
        buffer_m = dlg.buffer_m()
        tags = OSM_CATEGORIES[category]
        tp = route.track_points

        def _run_query(viewport):
            if viewport:
                vs, vw, vn, ve = viewport
                # Restrict to track points inside the current viewport so that a
                # long route only queries the visible section.
                visible_tp = tp.filter(
                    (pl.col("lat") >= vs) & (pl.col("lat") <= vn) &
                    (pl.col("lon") >= vw) & (pl.col("lon") <= ve),
                )
                if len(visible_tp) == 0:
                    self._status_label.setText(
                        "No track visible in current map view — pan to the route first.",
                    )
                    return
            else:
                visible_tp = tp

            lats = visible_tp["lat"].to_list()
            lons = visible_tp["lon"].to_list()

            # Cache key: category + buffer + extent of the visible section (rounded
            # to ~110 m so minor panning doesn't bust the cache unnecessarily).
            cache_key = (
                category, buffer_m,
                round(min(lats), 3), round(min(lons), 3),
                round(max(lats), 3), round(max(lons), 3),
            )
            if cache_key in self._osm_cache:
                df = self._osm_cache[cache_key]
                cached = True
            else:
                self._status_label.setText(f"Querying OSM for '{category}'…")
                self.statusBar().repaint()
                try:
                    df = query_osm_pois(lats, lons, tags, buffer_m)
                except Exception as exc:  # noqa: BLE001
                    QMessageBox.critical(self, "OSM query failed", str(exc))
                    self._update_status()
                    return
                self._osm_cache[cache_key] = df
                cached = False

            n = len(df)
            suffix = " (cached)" if cached else ""
            self._status_label.setText(
                f"Found {n} OSM POI{'s' if n != 1 else ''}{suffix}"
                " — click a marker to add to track",
            )
            self.map_widget.load_osm_pois(df)

        self.map_widget.get_viewport_bbox(_run_query)

    def _on_osm_poi_add(
        self, lat: float, lon: float, name: str, description: str, symbol: str, wptype: str,
    ) -> None:
        """
        User clicked an OSM marker button: snap to track and append as cue or POI.

        Intentionally skips map reload so zoom/pan and OSM overlay are preserved.
        """
        if self._active_index < 0 or not self._routes:
            return
        route = self._routes[self._active_index].route
        if len(route.track_points) == 0:
            return

        tp = route.track_points
        snap_idx, _ = nearest_index(lat, lon, tp["lat"].to_numpy(), tp["lon"].to_numpy())
        snap_lat = float(tp["lat"][snap_idx])
        snap_lon = float(tp["lon"][snap_idx])
        snap_dist = float(tp["distance"][snap_idx])

        display_name = name.strip() if name.strip() else symbol or "OSM POI"

        if wptype == "cue":
            existing = route.cues
            if len(existing) > 0:
                max_idx = existing["index"].max()
                next_idx = (int(max_idx) if max_idx is not None else 0) + 1
            else:
                next_idx = 0

            new_cue = pl.DataFrame(
                {
                    "index":       [next_idx],
                    "lat":         [snap_lat],
                    "lon":         [snap_lon],
                    "name":        [display_name],
                    "description": [description or None],
                    "cue_type":    [symbol or None],
                    "distance":    [snap_dist],
                },
                schema=CUES_SCHEMA,
            )
            new_cues = pl.concat([existing, new_cue])
            new_pois = route.pois
        else:
            existing = route.pois
            if len(existing) > 0:
                max_idx = existing["index"].max()
                next_idx = (int(max_idx) if max_idx is not None else 0) + 1
            else:
                next_idx = 0

            new_poi = pl.DataFrame(
                {
                    "index":       [next_idx],
                    "lat":         [snap_lat],
                    "lon":         [snap_lon],
                    "name":        [display_name],
                    "description": [description or None],
                    "symbol":      [symbol or None],
                    "distance":    [snap_dist],
                },
                schema=POIS_SCHEMA,
            )
            new_pois = pl.concat([existing, new_poi])
            new_cues = route.cues

        # Update route data in-memory without triggering a map reload.
        e = self._routes[self._active_index]
        r = e.route
        new_route = RouteData(
            track_points=r.track_points,
            cues=new_cues,
            pois=new_pois,
            source_file=r.source_file,
        )
        self._routes[self._active_index] = RouteEntry(
            route=new_route, color=e.color, label=e.label, visible=e.visible,
        )
        # Refresh tables, elevation, and status bar — map stays at current zoom/pan
        # so the OSM overlay is preserved.
        self.right_panel.load_route(new_route)
        self.elevation_widget.load_routes(self._build_display_routes(), self._active_index)
        self._set_dirty(True)
        self._update_status()
        # Inject the new marker and focus the appropriate table.
        self.map_widget.add_poi_marker(snap_lat, snap_lon, display_name, symbol or "generic")
        if wptype == "cue":
            self.right_panel.focus_cue(next_idx)
        else:
            self.right_panel.focus_poi(next_idx)

    # ------------------------------------------------------------------
    # Row-selection slots
    # ------------------------------------------------------------------

    def _on_track_row_selected(self, row: int, lat: float, lon: float) -> None:
        self.map_widget.zoom_to(lat, lon)
        if self._active_index >= 0 and self._routes:
            route = self._routes[self._active_index].route
            if row < len(route.track_points):
                dist = float(route.track_points["distance"][row])
                self.elevation_widget.move_cursor(dist)

    def _on_elevation_clicked(self, distance_m: float) -> None:
        if self._active_index < 0 or not self._routes:
            return
        route = self._routes[self._active_index].route
        if len(route.track_points) == 0:
            return
        tp = route.track_points
        dists = tp["distance"].to_numpy()
        idx = int(np.argmin(np.abs(dists - distance_m)))
        self.map_widget.zoom_to(float(tp["lat"][idx]), float(tp["lon"][idx]))
        self.elevation_widget.move_cursor(float(dists[idx]))
        self.right_panel.select_nearest_distance(float(dists[idx]))

    def _on_waypoint_row_selected(self, _row: int, lat: float, lon: float) -> None:
        self.map_widget.zoom_to(lat, lon)
        if self._active_index >= 0 and self._routes:
            route = self._routes[self._active_index].route
            if len(route.track_points) > 0:
                tp = route.track_points
                idx, _ = nearest_index(lat, lon, tp["lat"].to_numpy(), tp["lon"].to_numpy())
                self.elevation_widget.move_cursor(float(tp["distance"][idx]))

    # ------------------------------------------------------------------
    # Dedup / fix-symbols slots
    # ------------------------------------------------------------------

    def _remove_duplicates(self) -> None:
        if self._active_index < 0 or not self._routes:
            return
        route = self._routes[self._active_index].route
        from gpx_editor.ui.dedup_dialog import DedupDialog
        dlg = DedupDialog(route, self)
        if dlg.exec() != DedupDialog.DialogCode.Accepted:
            return
        new_route = route.deduplicate(max_distance_m=dlg.threshold_m())
        self._update_active_route(cues=new_route.cues, pois=new_route.pois)

    def _fix_symbols(self) -> None:
        if self._active_index < 0 or not self._routes:
            return
        new_route = self._routes[self._active_index].route.fix_symbols()
        self._update_active_route(pois=new_route.pois)

    # ------------------------------------------------------------------
    # Filter slots
    # ------------------------------------------------------------------

    def _on_filter_changed(self) -> None:
        """Refresh map and elevation to show only the currently visible (filtered) items."""
        self._refresh_map_and_elevation()

    # ------------------------------------------------------------------
    # View refresh
    # ------------------------------------------------------------------

    def _refresh_view(self) -> None:
        """Reload all widgets from the current routes list."""
        self.right_panel.set_routes(self._routes, self._active_index)

        if 0 <= self._active_index < len(self._routes):
            self.right_panel.load_route(self._routes[self._active_index].route)

        # Load map and elevation using the filtered view from the tables.
        self._refresh_map_and_elevation()
        self._update_status()
        self._update_title()

    def _build_display_routes(self) -> list[RouteEntry]:
        """Return the routes list with filtered cues/pois substituted for the active route."""
        display_routes = list(self._routes)
        if 0 <= self._active_index < len(self._routes):
            e = self._routes[self._active_index]
            r = e.route
            display_route = RouteData(
                track_points=r.track_points,
                cues=self.right_panel.cue_table.visible_df,
                pois=self.right_panel.poi_table.visible_df,
                source_file=r.source_file,
            )
            display_routes[self._active_index] = RouteEntry(
                route=display_route,
                color=e.color,
                label=e.label,
                visible=e.visible,
            )
        return display_routes

    def _refresh_map_and_elevation(self) -> None:
        """Reload map and elevation using the currently visible (possibly filtered) data."""
        if not self._routes:
            self.map_widget.load_routes([], -1)
            self.elevation_widget.load_routes([], -1)
            return
        display_routes = self._build_display_routes()
        self.map_widget.load_routes(display_routes, self._active_index)
        self.elevation_widget.load_routes(display_routes, self._active_index)

    # ------------------------------------------------------------------
    # Internal state helpers
    # ------------------------------------------------------------------

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        has_active = bool(self._routes) and self._active_index >= 0
        self._save_act.setEnabled(has_active and self._open_path is not None)
        self._save_as_act.setEnabled(has_active)
        self._osm_act.setEnabled(
            has_active
            and len(self._routes[self._active_index].route.track_points) > 0,
        )
        self._dedup_act.setEnabled(has_active)
        self._fix_symbols_act.setEnabled(has_active)
        self._update_title()

    def _update_title(self) -> None:
        if self._open_path:
            marker = " *" if self._dirty else ""
            self.setWindowTitle(f"GPX Editor — {self._open_path.name}{marker}")
        else:
            self.setWindowTitle("GPX Editor")

    def _update_status(self) -> None:
        if not self._routes or self._active_index < 0:
            self._status_label.setText("No file loaded")
            return
        route = self._routes[self._active_index].route
        tp = route.track_points
        total_km = float(tp["distance"][-1]) / 1000.0 if len(tp) > 0 else 0.0
        n_routes = len(self._routes)
        routes_info = f"  •  ({n_routes} routes)" if n_routes > 1 else ""
        self._status_label.setText(
            f"{len(tp)} track points  •  "
            f"{len(route.cues)} cues  •  "
            f"{len(route.pois)} POIs  •  "
            f"{total_km:.1f} km"
            f"{routes_info}",
        )
