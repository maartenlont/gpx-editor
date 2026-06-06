"""MainWindow — assembles all widgets and wires signals."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
)

from gpx_editor.io._distance import nearest_index
from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.io.gpx_writer import write_gpx
from gpx_editor.io.tcx_reader import read_tcx
from gpx_editor.io.tcx_writer import write_tcx
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

        # Wire route list signals
        self.right_panel.route_list.active_changed.connect(self._on_route_active_changed)
        self.right_panel.route_list.color_changed.connect(self._on_route_color_changed)
        self.right_panel.route_list.visibility_changed.connect(self._on_route_visibility_changed)
        self.right_panel.route_list.route_removed.connect(self._on_route_removed)

    def _setup_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        open_act = file_menu.addAction("&Open…")
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._open_file)

        self._clear_act = file_menu.addAction("&Clear All")
        self._clear_act.triggered.connect(self._clear_all)

        file_menu.addSeparator()

        self._save_act = file_menu.addAction("&Save As…")
        self._save_act.setShortcut("Ctrl+S")
        self._save_act.setEnabled(False)
        self._save_act.triggered.connect(self._save_as)

        file_menu.addSeparator()

        exit_act = file_menu.addAction("E&xit")
        exit_act.setShortcut("Ctrl+Q")
        exit_act.triggered.connect(self.close)

        edit_menu = self.menuBar().addMenu("&Edit")
        self._merge_act = edit_menu.addAction("&Merge Cues && POIs…")
        self._merge_act.setEnabled(False)
        self._merge_act.triggered.connect(self._open_merge_dialog)

    def _setup_status_bar(self) -> None:
        self._status_label = QLabel("No file loaded")
        self.statusBar().addWidget(self._status_label)

    # ------------------------------------------------------------------
    # File slots
    # ------------------------------------------------------------------

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open GPX / TCX file",
            str(self._open_path.parent) if self._open_path else "",
            "Route files (*.gpx *.tcx);;GPX files (*.gpx);;TCX files (*.tcx)",
        )
        if not path:
            return
        route = self._read_file(Path(path))
        if route is None:
            return
        used_colors = [e.color for e in self._routes]
        color = next_color(used_colors)
        label = Path(path).stem
        entry = RouteEntry(route=route, color=color, label=label)
        self._routes.append(entry)
        self._active_index = len(self._routes) - 1
        self._open_path = Path(path)
        self._merge_act.setEnabled(len(self._routes) >= 2)
        self._refresh_view()
        self._set_dirty(False)

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
            if path.suffix.lower() == ".gpx":
                return read_gpx(path)
            if path.suffix.lower() == ".tcx":
                return read_tcx(path)
            QMessageBox.warning(self, "Unsupported format", f"Unknown file type: {path.suffix}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error loading file", str(exc))
        return None

    def _save_as(self) -> None:
        if not self._routes or self._active_index < 0:
            return
        active_entry = self._routes[self._active_index]
        start_dir = str(self._open_path.parent) if self._open_path else ""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save route as…",
            start_dir,
            "GPX file (*.gpx);;TCX file (*.tcx)",
        )
        if not path:
            return
        out = Path(path)
        if out.suffix.lower() not in (".gpx", ".tcx"):
            out = out.with_suffix(".gpx")
        try:
            if out.suffix.lower() == ".gpx":
                write_gpx(active_entry.route, out)
            else:
                write_tcx(active_entry.route, out)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error saving file", str(exc))
            return
        self._open_path = out
        self._set_dirty(False)

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
            self._refresh_view()

    def _on_route_visibility_changed(self, index: int, visible: bool) -> None:
        if 0 <= index < len(self._routes):
            entry = self._routes[index]
            self._routes[index] = RouteEntry(
                route=entry.route,
                color=entry.color,
                label=entry.label,
                visible=visible,
            )
            self._refresh_view()

    def _on_route_removed(self, index: int) -> None:
        if 0 <= index < len(self._routes):
            self._routes.pop(index)
            # Clamp active_index to valid range
            if not self._routes:
                self._active_index = -1
            elif self._active_index >= len(self._routes):
                self._active_index = len(self._routes) - 1
            self._merge_act.setEnabled(len(self._routes) >= 2)
            self._refresh_view()

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
    # View refresh
    # ------------------------------------------------------------------

    def _refresh_view(self) -> None:
        """Reload all widgets from the current routes list."""
        self.map_widget.load_routes(self._routes, self._active_index)
        self.elevation_widget.load_routes(self._routes, self._active_index)
        self.right_panel.set_routes(self._routes, self._active_index)

        if 0 <= self._active_index < len(self._routes):
            self.right_panel.load_route(self._routes[self._active_index].route)

        self._update_status()
        self._update_title()

    # ------------------------------------------------------------------
    # Internal state helpers
    # ------------------------------------------------------------------

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self._save_act.setEnabled(bool(self._routes) and self._active_index >= 0)
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
            f"{routes_info}"
        )
