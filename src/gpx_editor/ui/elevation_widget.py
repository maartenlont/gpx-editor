"""Elevation profile widget using matplotlib embedded in PySide6."""

from __future__ import annotations

import matplotlib

matplotlib.use("QtAgg")  # must be set before pyplot import

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.transforms import blended_transform_factory
from PySide6.QtCore import Signal

from gpx_editor.models.route import RouteData
from gpx_editor.models.route_entry import RouteEntry
from gpx_editor.ui.poi_icons import (
    _FOLIUM_HEX,
    _GLYPH_CHAR,
    CUE_ICON,
    DEFAULT_CUE_ICON,
    DEFAULT_POI_ICON,
    POI_NAME_ICON,
)


def _format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as h:mm:ss."""
    s = int(max(0.0, seconds))
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h}:{m:02d}:{sec:02d}"


class ElevationWidget(FigureCanvasQTAgg):
    # Emits distance in metres when the user clicks on the chart
    location_clicked = Signal(float)

    def __init__(self, parent=None) -> None:
        fig = Figure(figsize=(5, 2))
        fig.subplots_adjust(left=0.08, right=0.99, top=0.92, bottom=0.22)
        super().__init__(fig)
        self._ax = fig.add_subplot(111)
        self._cursor: Line2D | None = None
        self._hover_vline: Line2D | None = None
        self._hover_text = None
        self._dist_km_arr: np.ndarray = np.array([])
        self._elapsed_s_arr: np.ndarray | None = None
        self._clear_axes()
        self.mpl_connect("button_press_event", self._on_click)
        self.mpl_connect("motion_notify_event", self._on_motion)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_routes(self, entries: list[RouteEntry], active_index: int) -> None:
        """Plot all visible routes; active route at full opacity, others dimmed."""
        self._ax.clear()
        self._cursor = None
        self._hover_vline = None
        self._hover_text = None
        self._dist_km_arr = np.array([])
        self._elapsed_s_arr = None
        self._clear_axes()

        # Pre-compute distance/time arrays for the active route (used by hover)
        if 0 <= active_index < len(entries) and entries[active_index].visible:
            tp = entries[active_index].route.track_points
            if len(tp) > 0:
                self._dist_km_arr = np.array(tp["distance"].to_list()) / 1000.0
                if "time" in tp.columns:
                    times = tp["time"].to_list()
                    t0 = next((t for t in times if t is not None), None)
                    if t0 is not None:
                        self._elapsed_s_arr = np.array([
                            (t - t0).total_seconds() if t is not None else np.nan
                            for t in times
                        ])

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
                x=0, color="#E53935", linewidth=1.2, linestyle="--", visible=False, zorder=3,
            )

        # Plot icons for cues and POIs on the active route
        if active_entry is not None and active_entry.visible:
            self._plot_waypoint_icons(active_entry.route)

        if max_dist_km > 0:
            self._ax.set_xlim(0, max_dist_km)

        # Create hover indicator objects (recreated each load because _ax.clear() destroys them)
        self._hover_vline = self._ax.axvline(
            x=0, color="#666", linewidth=0.8, linestyle=":", visible=False, zorder=4,
        )
        blend = blended_transform_factory(self._ax.transData, self._ax.transAxes)
        self._hover_text = self._ax.text(
            0, 0.97, "",
            transform=blend, va="top", ha="left", fontsize=7.5,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", alpha=0.88, ec="#bbb", lw=0.7),
            zorder=10, visible=False,
        )

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

    def _plot_waypoint_icons(self, route: RouteData) -> None:
        """Plot small icons for cues and POIs at their positions on the elevation profile."""
        tp = route.track_points
        if len(tp) == 0:
            return

        # Build quick lookup: distance → elevation
        dist_list = tp["distance"].to_list()
        elev_list = tp["elevation"].to_list()

        def get_elev_at_dist(target_dist: float) -> float | None:
            """Find elevation at the closest track point to target_dist."""
            if not dist_list:
                return None
            # Binary-ish search: find closest
            best_idx = 0
            best_diff = abs(dist_list[0] - target_dist)
            for i, d in enumerate(dist_list):
                diff = abs(d - target_dist)
                if diff < best_diff:
                    best_diff = diff
                    best_idx = i
            return elev_list[best_idx]

        # Plot cues
        for row in route.cues.iter_rows(named=True):
            dist_m = row.get("distance")
            if dist_m is None:
                continue
            elev = get_elev_at_dist(dist_m)
            if elev is None:
                continue

            cue_type = (row.get("cue_type") or "").lower()
            glyph_name, color_name = CUE_ICON.get(cue_type, DEFAULT_CUE_ICON)
            char = _GLYPH_CHAR.get(glyph_name, "●")
            hex_color = _FOLIUM_HEX.get(color_name, "#D63E2A")

            dist_km = dist_m / 1000.0
            self._ax.plot(dist_km, elev, marker="o", markersize=10,
                          color=hex_color, markeredgecolor="white",
                          markeredgewidth=1.0, zorder=5)
            self._ax.annotate(char, (dist_km, elev), fontsize=7, fontweight="bold",
                              color="white", ha="center", va="center", zorder=6)

        # Plot POIs
        for row in route.pois.iter_rows(named=True):
            dist_m = row.get("distance")
            if dist_m is None:
                continue
            elev = get_elev_at_dist(dist_m)
            if elev is None:
                continue

            name = (row.get("name") or "").lower()
            glyph_name, color_name = POI_NAME_ICON.get(name, DEFAULT_POI_ICON)
            char = _GLYPH_CHAR.get(glyph_name, "●")
            hex_color = _FOLIUM_HEX.get(color_name, "#72AF26")

            dist_km = dist_m / 1000.0
            self._ax.plot(dist_km, elev, marker="o", markersize=10,
                          color=hex_color, markeredgecolor="white",
                          markeredgewidth=1.0, zorder=5)
            self._ax.annotate(char, (dist_km, elev), fontsize=7, fontweight="bold",
                              color="white", ha="center", va="center", zorder=6)

    def _on_motion(self, event) -> None:
        if self._hover_vline is None or self._hover_text is None:
            return
        if event.inaxes != self._ax or event.xdata is None or len(self._dist_km_arr) == 0:
            if self._hover_vline.get_visible():
                self._hover_vline.set_visible(False)
                self._hover_text.set_visible(False)
                self.draw_idle()
            return

        x_km = float(event.xdata)
        idx = int(np.argmin(np.abs(self._dist_km_arr - x_km)))

        parts = [f"{x_km:.2f} km"]
        if (
            self._elapsed_s_arr is not None
            and idx < len(self._elapsed_s_arr)
            and not np.isnan(self._elapsed_s_arr[idx])
        ):
            parts.append(_format_elapsed(float(self._elapsed_s_arr[idx])))

        # Flip ha so the label stays inside the axes near the right edge
        xlim = self._ax.get_xlim()
        if x_km > 0.65 * (xlim[0] + xlim[1]):
            self._hover_text.set_ha("right")
        else:
            self._hover_text.set_ha("left")
        self._hover_text.set_x(x_km)
        self._hover_text.set_text("\n".join(parts))
        self._hover_text.set_visible(True)
        self._hover_vline.set_xdata([x_km, x_km])
        self._hover_vline.set_visible(True)
        self.draw_idle()

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
