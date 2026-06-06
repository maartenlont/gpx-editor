"""Right panel: QTabWidget containing routes list, track-points, cues, and POIs tables."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget

import polars as pl

from gpx_editor.models.route import RouteData, empty_cues, empty_pois, empty_track_points
from gpx_editor.models.route_entry import RouteEntry
from gpx_editor.ui.dataframe_table import DataFrameTableWidget
from gpx_editor.ui.poi_icons import poi_icon_for_row
from gpx_editor.ui.route_list_widget import RouteListWidget


def _reorder(df: pl.DataFrame, order: list[str]) -> pl.DataFrame:
    """Return *df* with visible columns in *order*; unknown/extra columns appended."""
    ordered = [c for c in order if c in df.columns]
    extra = [c for c in df.columns if c not in set(order) and c != "index"]
    return df.select(["index"] + ordered + extra)


class RightPanel(QTabWidget):
    # Emits (row, lat, lon) whenever any table row is clicked
    row_selected = Signal(int, float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Tab 0: Routes list
        self.route_list = RouteListWidget()

        # Tabs 1, 2, 3: data tables
        self.track_table = DataFrameTableWidget(empty_track_points())
        self.cue_table = DataFrameTableWidget(empty_cues())
        self.poi_table = DataFrameTableWidget(
            empty_pois(), icon_col="symbol", icon_fn=poi_icon_for_row
        )

        self.addTab(self.route_list, "Routes")
        self.addTab(self.track_table, "Track Points")
        self.addTab(self.cue_table, "Cues")
        self.addTab(self.poi_table, "POIs")

        for tbl in (self.track_table, self.cue_table, self.poi_table):
            tbl.row_selected.connect(self.row_selected)

    def set_routes(self, entries: list[RouteEntry], active_index: int) -> None:
        """Delegate to the route list widget."""
        self.route_list.set_routes(entries, active_index)

    def select_nearest_distance(self, distance_m: float) -> None:
        """Select the nearest row in whichever data tab is currently visible.

        Tab index 0 is the Routes tab; data tabs are at indices 1, 2, 3.
        """
        tables = [self.track_table, self.cue_table, self.poi_table]
        idx = self.currentIndex() - 1  # offset by 1 for the Routes tab
        if 0 <= idx < len(tables):
            tables[idx].select_nearest_distance(distance_m)

    def load_route(self, route: RouteData) -> None:
        self.track_table.load(_reorder(
            route.track_points.sort("distance"),
            ["distance", "lat", "lon", "elevation", "time", "hr", "cadence", "power"],
        ))
        self.cue_table.load(_reorder(
            route.cues.sort("distance"),
            ["distance", "name", "description", "cue_type", "lat", "lon"],
        ))
        self.poi_table.load(_reorder(
            route.pois.sort("distance"),
            ["distance", "symbol", "name", "description", "lat", "lon"],
        ))
        self.setTabText(1, f"Track Points ({len(route.track_points)})")
        self.setTabText(2, f"Cues ({len(route.cues)})")
        self.setTabText(3, f"POIs ({len(route.pois)})")
