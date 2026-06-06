"""Right panel: QTabWidget containing track-points, cues, and POIs tables."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget

from gpx_editor.models.route import RouteData, empty_cues, empty_pois, empty_track_points
from gpx_editor.ui.dataframe_table import DataFrameTableWidget


class RightPanel(QTabWidget):
    # Emits (row, lat, lon) whenever any table row is clicked
    row_selected = Signal(int, float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.track_table = DataFrameTableWidget(empty_track_points())
        self.cue_table = DataFrameTableWidget(empty_cues())
        self.poi_table = DataFrameTableWidget(empty_pois())

        self.addTab(self.track_table, "Track Points")
        self.addTab(self.cue_table, "Cues")
        self.addTab(self.poi_table, "POIs")

        for tbl in (self.track_table, self.cue_table, self.poi_table):
            tbl.row_selected.connect(self.row_selected)

    def load_route(self, route: RouteData) -> None:
        self.track_table.load(route.track_points)
        self.cue_table.load(route.cues)
        self.poi_table.load(route.pois)
        # Update tab labels with counts
        self.setTabText(0, f"Track Points ({len(route.track_points)})")
        self.setTabText(1, f"Cues ({len(route.cues)})")
        self.setTabText(2, f"POIs ({len(route.pois)})")
