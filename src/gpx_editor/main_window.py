"""MainWindow — assembles all widgets and wires signals."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
)
from PySide6.QtCore import Qt

from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.io.tcx_reader import read_tcx
from gpx_editor.models.route import RouteData
from gpx_editor.ui.elevation_widget import ElevationWidget
from gpx_editor.ui.map_widget import MapWidget
from gpx_editor.ui.right_panel import RightPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._route: RouteData | None = None
        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
        self.setWindowTitle("GPX Editor")
        self.resize(1400, 800)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        # Left side: vertical splitter → map (top) + elevation (bottom)
        self.map_widget = MapWidget()
        self.elevation_widget = ElevationWidget()

        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.addWidget(self.map_widget)
        left_splitter.addWidget(self.elevation_widget)
        left_splitter.setStretchFactor(0, 3)
        left_splitter.setStretchFactor(1, 1)

        # Right side: tab panel with the three tables
        self.right_panel = RightPanel()

        # Outer horizontal splitter
        outer_splitter = QSplitter(Qt.Horizontal)
        outer_splitter.addWidget(left_splitter)
        outer_splitter.addWidget(self.right_panel)
        outer_splitter.setStretchFactor(0, 1)
        outer_splitter.setStretchFactor(1, 1)

        self.setCentralWidget(outer_splitter)

        # Row selection in any table → zoom map + move elevation cursor
        self.right_panel.track_table.row_selected.connect(self._on_track_row_selected)
        self.right_panel.cue_table.row_selected.connect(self._on_waypoint_row_selected)
        self.right_panel.poi_table.row_selected.connect(self._on_waypoint_row_selected)

    def _setup_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        open_act = file_menu.addAction("&Open…")
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._open_file)

        file_menu.addSeparator()

        exit_act = file_menu.addAction("E&xit")
        exit_act.setShortcut("Ctrl+Q")
        exit_act.triggered.connect(self.close)

    def _setup_status_bar(self) -> None:
        self._status_label = QLabel("No file loaded")
        self.statusBar().addWidget(self._status_label)

    # ------------------------------------------------------------------
    # Slots
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
        self._load_file(Path(path))

    def _load_file(self, path: Path) -> None:
        try:
            if path.suffix.lower() == ".gpx":
                route = read_gpx(path)
            elif path.suffix.lower() == ".tcx":
                route = read_tcx(path)
            else:
                QMessageBox.warning(self, "Unsupported format", f"Unknown file type: {path.suffix}")
                return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error loading file", str(exc))
            return

        self._route = route
        self.map_widget.load_route(route)
        self.elevation_widget.load_route(route)
        self.right_panel.load_route(route)
        self.setWindowTitle(f"GPX Editor — {path.name}")
        self._update_status()

    def _on_track_row_selected(self, row: int, lat: float, lon: float) -> None:
        self.map_widget.zoom_to(lat, lon)
        if self._route is not None and row < len(self._route.track_points):
            dist = float(self._route.track_points["distance"][row])
            self.elevation_widget.move_cursor(dist)

    def _on_waypoint_row_selected(self, _row: int, lat: float, lon: float) -> None:
        self.map_widget.zoom_to(lat, lon)

    def _update_status(self) -> None:
        if self._route is None:
            self._status_label.setText("No file loaded")
            return
        tp = self._route.track_points
        total_km = (
            float(tp["distance"][-1]) / 1000.0 if len(tp) > 0 else 0.0
        )
        self._status_label.setText(
            f"{len(tp)} track points  •  "
            f"{len(self._route.cues)} cues  •  "
            f"{len(self._route.pois)} POIs  •  "
            f"{total_km:.1f} km"
        )
