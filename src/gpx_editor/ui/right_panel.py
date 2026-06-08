"""Right panel: QTabWidget containing routes list, track-points, cues, and POIs tables."""

from __future__ import annotations

import polars as pl
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from gpx_editor.models.route import (
    RouteData,
    empty_cues,
    empty_pois,
    empty_track_points,
)
from gpx_editor.models.route_entry import RouteEntry
from gpx_editor.ui.dataframe_table import DataFrameTableWidget
from gpx_editor.ui.poi_icons import poi_icon_for_row
from gpx_editor.ui.review_toolbar import ReviewToolbar
from gpx_editor.ui.route_list_widget import RouteListWidget


def _reorder(df: pl.DataFrame, order: list[str]) -> pl.DataFrame:
    """Return *df* with visible columns in *order*; unknown/extra columns appended."""
    ordered = [c for c in order if c in df.columns]
    extra = [c for c in df.columns if c not in set(order) and c != "index"]
    return df.select(["index"] + ordered + extra)


class RightPanel(QTabWidget):
    # Emits (row, lat, lon) whenever any table row is clicked
    row_selected = Signal(int, float, float)
    # Emits when the user changes a filter on the cue or POI table
    filter_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._last_route: RouteData | None = None

        # Tab 0: Routes list
        self.route_list = RouteListWidget()

        # Tabs 1, 2, 3: data tables
        self.track_table = DataFrameTableWidget(empty_track_points())
        self.cue_table = DataFrameTableWidget(
            empty_cues(),
            editable_cols=["name", "cue_type", "description"],
            show_checkboxes=True,
        )
        self.poi_table = DataFrameTableWidget(
            empty_pois(),
            icon_col="symbol",
            icon_fn=poi_icon_for_row,
            editable_cols=["name", "symbol", "description"],
            show_checkboxes=True,
        )

        # Wrap cue and POI tables with review toolbars
        self.cue_toolbar = ReviewToolbar()
        cue_container = QWidget()
        cue_layout = QVBoxLayout(cue_container)
        cue_layout.setContentsMargins(0, 0, 0, 0)
        cue_layout.setSpacing(0)
        cue_layout.addWidget(self.cue_toolbar)
        cue_layout.addWidget(self.cue_table)

        self.poi_toolbar = ReviewToolbar()
        poi_container = QWidget()
        poi_layout = QVBoxLayout(poi_container)
        poi_layout.setContentsMargins(0, 0, 0, 0)
        poi_layout.setSpacing(0)
        poi_layout.addWidget(self.poi_toolbar)
        poi_layout.addWidget(self.poi_table)

        self.addTab(self.route_list, "Routes")
        self.addTab(self.track_table, "Track Points")
        self.addTab(cue_container, "Cues")
        self.addTab(poi_container, "POIs")

        # Wire review toolbar signals
        self.cue_toolbar.delete_requested.connect(self.cue_table.delete_current_and_select_next)
        self.cue_toolbar.skip_requested.connect(self.cue_table.select_next_row)
        self.poi_toolbar.delete_requested.connect(self.poi_table.delete_current_and_select_next)
        self.poi_toolbar.skip_requested.connect(self.poi_table.select_next_row)

        for tbl in (self.track_table, self.cue_table, self.poi_table):
            tbl.row_selected.connect(self.row_selected)

        self.cue_table.filter_changed.connect(self._on_filter_changed)
        self.poi_table.filter_changed.connect(self._on_filter_changed)

    def _on_filter_changed(self) -> None:
        self._update_tab_texts()
        self.filter_changed.emit()

    def set_routes(self, entries: list[RouteEntry], active_index: int) -> None:
        """Delegate to the route list widget."""
        self.route_list.set_routes(entries, active_index)

    def focus_cue(self, index_val: int) -> None:
        """Switch to the Cues tab and select the row with the given stable index."""
        self.setCurrentIndex(2)
        self.cue_table.select_row_by_index_val(index_val)

    def focus_poi(self, index_val: int) -> None:
        """Switch to the POIs tab and select the row with the given stable index."""
        self.setCurrentIndex(3)
        self.poi_table.select_row_by_index_val(index_val)

    def select_nearest_distance(self, distance_m: float) -> None:
        """Select the nearest row in whichever data tab is currently visible."""
        tables = [self.track_table, self.cue_table, self.poi_table]
        idx = self.currentIndex() - 1  # offset by 1 for the Routes tab
        if 0 <= idx < len(tables):
            tables[idx].select_nearest_distance(distance_m)

    def load_route(self, route: RouteData) -> None:
        self._last_route = route
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
        self._update_tab_texts()

    def _update_tab_texts(self) -> None:
        """Update tab labels; append filter hint when a filter is active."""
        route = self._last_route
        n_tp    = len(route.track_points) if route is not None else 0
        n_cues  = len(route.cues)         if route is not None else 0
        n_pois  = len(route.pois)         if route is not None else 0

        n_cues_vis = len(self.cue_table.visible_df)
        n_pois_vis = len(self.poi_table.visible_df)

        self.setTabText(1, f"Track Points ({n_tp})")

        if n_cues_vis < n_cues:
            self.setTabText(2, f"Cues ({n_cues_vis}/{n_cues} ▼)")
        else:
            self.setTabText(2, f"Cues ({n_cues})")

        if n_pois_vis < n_pois:
            self.setTabText(3, f"POIs ({n_pois_vis}/{n_pois} ▼)")
        else:
            self.setTabText(3, f"POIs ({n_pois})")
