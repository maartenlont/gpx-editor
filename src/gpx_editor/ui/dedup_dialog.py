"""Dialog for removing duplicate cues and POIs from the active route."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)

from gpx_editor.models.route import RouteData


class DedupDialog(QDialog):
    """Let the user choose a distance tolerance and preview how many duplicates
    will be removed before committing."""

    def __init__(self, route: RouteData, parent=None) -> None:
        super().__init__(parent)
        self._route = route
        self._setup_ui()
        self.setWindowTitle("Remove Duplicates")
        self.setMinimumWidth(360)
        self._update_preview()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        settings_box = QGroupBox("Settings")
        form = QFormLayout(settings_box)

        self._dist_spin = QDoubleSpinBox()
        self._dist_spin.setRange(0.0, 10_000.0)
        self._dist_spin.setValue(10.0)
        self._dist_spin.setSuffix(" m")
        self._dist_spin.setSingleStep(5.0)
        self._dist_spin.setDecimals(1)
        self._dist_spin.setToolTip(
            "Two waypoints with the same name are considered duplicates\n"
            "if they are no further apart than this distance along the track."
        )
        form.addRow("Max distance between duplicates:", self._dist_spin)
        layout.addWidget(settings_box)

        self._preview_label = QLabel()
        self._preview_label.setWordWrap(True)
        layout.addWidget(self._preview_label)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._ok_btn = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setText("Remove Duplicates")
        self._ok_btn.setDefault(True)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._dist_spin.valueChanged.connect(self._update_preview)

    def _update_preview(self) -> None:
        threshold = self._dist_spin.value()
        deduped = self._route.deduplicate(max_distance_m=threshold)
        n_cue = len(self._route.cues) - len(deduped.cues)
        n_poi = len(self._route.pois) - len(deduped.pois)
        total = n_cue + n_poi

        cue_line = (
            f"Cues: {n_cue} duplicate(s) removed "
            f"({len(self._route.cues)} → {len(deduped.cues)})"
        )
        poi_line = (
            f"POIs: {n_poi} duplicate(s) removed "
            f"({len(self._route.pois)} → {len(deduped.pois)})"
        )
        if total == 0:
            color = "gray"
            summary = "No duplicates found with current settings."
        else:
            color = "#1565C0"
            summary = f"{total} duplicate(s) will be removed."

        self._preview_label.setText(
            f"<span style='color:{color};'>{summary}</span><br>"
            f"<small>{cue_line}<br>{poi_line}</small>"
        )
        self._ok_btn.setEnabled(total > 0)

    def threshold_m(self) -> float:
        return self._dist_spin.value()
