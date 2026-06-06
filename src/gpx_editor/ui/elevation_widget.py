"""Elevation profile widget using matplotlib embedded in PySide6."""

from __future__ import annotations

import matplotlib
matplotlib.use("QtAgg")  # must be set before pyplot import

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from PySide6.QtCore import Signal

from gpx_editor.models.route import RouteData


class ElevationWidget(FigureCanvasQTAgg):
    # Emits distance in metres when the user clicks on the chart
    location_clicked = Signal(float)

    def __init__(self, parent=None) -> None:
        fig = Figure(figsize=(5, 2))
        fig.subplots_adjust(left=0.08, right=0.99, top=0.92, bottom=0.22)
        super().__init__(fig)
        self._ax = fig.add_subplot(111)
        self._cursor: Line2D | None = None
        self._clear_axes()
        self.mpl_connect("button_press_event", self._on_click)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_route(self, route: RouteData) -> None:
        self._ax.clear()
        self._cursor = None
        self._clear_axes()
        tp = route.track_points
        if len(tp) == 0 or tp["elevation"].is_null().all():
            self.draw()
            return

        dist_km = [d / 1000.0 for d in tp["distance"].to_list()]
        elev = [e if e is not None else float("nan") for e in tp["elevation"].to_list()]

        self._ax.plot(dist_km, elev, color="#1565C0", linewidth=1.5, zorder=2)
        self._ax.fill_between(dist_km, elev, alpha=0.25, color="#1565C0", zorder=1)
        self._cursor = self._ax.axvline(
            x=0, color="#E53935", linewidth=1.2, linestyle="--", visible=False, zorder=3
        )
        self._ax.set_xlim(0, max(dist_km) if dist_km else 1)
        self.draw()

    def move_cursor(self, distance_m: float) -> None:
        if self._cursor is None:
            return
        self._cursor.set_xdata([distance_m / 1000.0, distance_m / 1000.0])
        self._cursor.set_visible(True)
        self.draw()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_click(self, event) -> None:
        if event.inaxes != self._ax or event.xdata is None:
            return
        self.location_clicked.emit(event.xdata * 1000.0)  # km → metres

    def _clear_axes(self) -> None:
        self._ax.set_xlabel("Distance (km)", fontsize=8)
        self._ax.set_ylabel("Elevation (m)", fontsize=8)
        self._ax.tick_params(labelsize=7)
        self._ax.set_facecolor("#f8f8f8")
        self.figure.patch.set_facecolor("#ffffff")
        self._ax.grid(True, linewidth=0.4, alpha=0.6)
