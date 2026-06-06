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
from gpx_editor.models.route import RouteData
from gpx_editor.ui.elevation_widget import ElevationWidget
from gpx_editor.ui.map_widget import MapWidget
from gpx_editor.ui.right_panel import RightPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._route: RouteData | None = None
        self._second_route: RouteData | None = None
        self._pre_merge_route: RouteData | None = None
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

    def _setup_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        open_act = file_menu.addAction("&Open…")
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._open_file)

        self._open_second_act = file_menu.addAction("Open &Second File…")
        self._open_second_act.setEnabled(False)
        self._open_second_act.triggered.connect(self._open_second_file)

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
    # Public helpers
    # ------------------------------------------------------------------

    def set_route(self, route: RouteData, dirty: bool = True) -> None:
        """Replace the active route and refresh all widgets."""
        self._route = route
        self.map_widget.load_route(route)
        self.elevation_widget.load_route(route)
        self.right_panel.load_route(route)
        self._set_dirty(dirty)
        self._update_status()

    # ------------------------------------------------------------------
    # File slots
    # ------------------------------------------------------------------

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open GPX / TCX file",
            "",
            "Route files (*.gpx *.tcx);;GPX files (*.gpx);;TCX files (*.tcx)",
        )
        if not path:
            return
        route = self._read_file(Path(path))
        if route is None:
            return
        self._open_path = Path(path)
        self._second_route = None
        self._open_second_act.setEnabled(True)
        self._merge_act.setEnabled(False)
        self.set_route(route, dirty=False)

    def _open_second_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open second GPX / TCX file",
            str(self._open_path.parent) if self._open_path else "",
            "Route files (*.gpx *.tcx);;GPX files (*.gpx);;TCX files (*.tcx)",
        )
        if not path:
            return
        route = self._read_file(Path(path))
        if route is None:
            return
        self._second_route = route
        self._merge_act.setEnabled(True)
        self.statusBar().showMessage(
            f"Second file loaded: {Path(path).name}  —  ready to merge", 5000
        )

    def _read_file(self, path: Path) -> RouteData | None:
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
        if self._route is None:
            return
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
                write_gpx(self._route, out)
            else:
                write_tcx(self._route, out)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error saving file", str(exc))
            return
        self._open_path = out
        self._set_dirty(False)

    # ------------------------------------------------------------------
    # Merge slot
    # ------------------------------------------------------------------

    def _open_merge_dialog(self) -> None:
        if self._route is None or self._second_route is None:
            return

        # Import here to avoid circular import at module level
        from gpx_editor.ui.merge_dialog import MergeDialog

        self._pre_merge_route = self._route

        dlg = MergeDialog(
            source=self._route,           # copy cues/POIs FROM the primary file
            target=self._second_route,    # INTO the second file's track
            parent=self,
        )
        dlg.preview_requested.connect(lambda r: self.set_route(r, dirty=True))

        if dlg.exec() == MergeDialog.DialogCode.Accepted:
            # Route already updated via preview_requested; just ensure dirty flag
            self._set_dirty(True)
        else:
            # Cancelled — restore the route that was active before the dialog opened
            self.set_route(self._pre_merge_route, dirty=False)

        self._pre_merge_route = None

    # ------------------------------------------------------------------
    # Row-selection slots
    # ------------------------------------------------------------------

    def _on_track_row_selected(self, row: int, lat: float, lon: float) -> None:
        self.map_widget.zoom_to(lat, lon)
        if self._route is not None and row < len(self._route.track_points):
            dist = float(self._route.track_points["distance"][row])
            self.elevation_widget.move_cursor(dist)

    def _on_elevation_clicked(self, distance_m: float) -> None:
        if self._route is None or len(self._route.track_points) == 0:
            return
        tp = self._route.track_points
        dists = tp["distance"].to_numpy()
        idx = int(np.argmin(np.abs(dists - distance_m)))
        self.map_widget.zoom_to(float(tp["lat"][idx]), float(tp["lon"][idx]))
        self.elevation_widget.move_cursor(float(dists[idx]))
        self.right_panel.select_nearest_distance(float(dists[idx]))

    def _on_waypoint_row_selected(self, _row: int, lat: float, lon: float) -> None:
        self.map_widget.zoom_to(lat, lon)
        if self._route is not None and len(self._route.track_points) > 0:
            tp = self._route.track_points
            idx, _ = nearest_index(lat, lon, tp["lat"].to_numpy(), tp["lon"].to_numpy())
            self.elevation_widget.move_cursor(float(tp["distance"][idx]))

    # ------------------------------------------------------------------
    # Internal state helpers
    # ------------------------------------------------------------------

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self._save_act.setEnabled(self._route is not None)
        self._update_title()

    def _update_title(self) -> None:
        if self._open_path:
            marker = " *" if self._dirty else ""
            self.setWindowTitle(f"GPX Editor — {self._open_path.name}{marker}")
        else:
            self.setWindowTitle("GPX Editor")

    def _update_status(self) -> None:
        if self._route is None:
            self._status_label.setText("No file loaded")
            return
        tp = self._route.track_points
        total_km = float(tp["distance"][-1]) / 1000.0 if len(tp) > 0 else 0.0
        self._status_label.setText(
            f"{len(tp)} track points  •  "
            f"{len(self._route.cues)} cues  •  "
            f"{len(self._route.pois)} POIs  •  "
            f"{total_km:.1f} km"
        )
