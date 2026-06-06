"""Elevation profile widget using matplotlib embedded in PySide6."""

from __future__ import annotations

import matplotlib
matplotlib.use("QtAgg")  # must be set before pyplot import

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from PySide6.QtCore import Signal

from gpx_editor.models.route import RouteData
from gpx_editor.models.route_entry import RouteEntry


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

    def load_routes(self, entries: list[RouteEntry], active_index: int) -> None:
        """Plot all visible routes; active route at full opacity, others dimmed."""
        self._ax.clear()
        self._cursor = None
        self._clear_axes()

        visible = [(i, e) for i, e in enumerate(entries) if e.visible]
        if not visible:
            self.draw()
            return

        max_dist_km = 0.0
        active_entry = entries[active_index] if 0 <= active_index < len(entries) else None

        for i, entry in visible:
            tp = entry.route.track_points
            if len(tp) == 0 or tp["elevation"].is_null().all():
                continue

            dist_km = [d / 1000.0 for d in tp["distance"].to_list()]
            elev = [e if e is not None else float("nan") for e in tp["elevation"].to_list()]

            is_active = (i == active_index)
            if is_active:
                lw = 1.5
                alpha_line = 1.0
                alpha_fill = 0.15
            else:
                lw = 0.8
                alpha_line = 0.35
                alpha_fill = 0.0  # no fill for inactive routes

            self._ax.plot(dist_km, elev, color=entry.color, linewidth=lw, alpha=alpha_line, zorder=2)
            if is_active and alpha_fill > 0:
                self._ax.fill_between(dist_km, elev, alpha=alpha_fill, color=entry.color, zorder=1)

            if dist_km:
                max_dist_km = max(max_dist_km, max(dist_km))

        # Add axvline cursor for the active entry context
        if active_entry is not None:
            self._cursor = self._ax.axvline(
                x=0, color="#E53935", linewidth=1.2, linestyle="--", visible=False, zorder=3
            )

        if max_dist_km > 0:
            self._ax.set_xlim(0, max_dist_km)
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
