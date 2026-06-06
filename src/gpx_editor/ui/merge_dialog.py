"""Dialog for merging cues and POIs from a source route into a target route."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from gpx_editor.logic.merge import copy_cues_pois
from gpx_editor.models.route import RouteData


class MergeDialog(QDialog):
    """Non-blocking merge configuration dialog.

    Emits ``preview_requested(RouteData)`` whenever the user wants to see the
    result of the current settings.  The parent window should connect this
    signal to its ``set_route`` method so the map and tables update live.

    On ``accept`` the last emitted route is already applied.
    On ``reject`` the caller is responsible for reverting to the original route.
    """

    preview_requested = Signal(RouteData)

    def __init__(
        self,
        source: RouteData,
        target: RouteData,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._source = source
        self._target = target
        self._setup_ui()
        self.setWindowTitle("Merge Cues & POIs")
        self.setMinimumWidth(440)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Route info
        info_box = QGroupBox("Routes")
        info_form = QFormLayout(info_box)
        source_name = Path(self._source.source_file).name if self._source.source_file else "—"
        target_name = Path(self._target.source_file).name if self._target.source_file else "—"
        info_form.addRow("Copy cues/POIs from:", QLabel(f"<b>{source_name}</b>"))
        info_form.addRow(
            "",
            QLabel(
                f"{len(self._source.cues)} cues · {len(self._source.pois)} POIs"
            ),
        )
        info_form.addRow("Into track from:", QLabel(f"<b>{target_name}</b>"))
        info_form.addRow(
            "",
            QLabel(
                f"{len(self._target.track_points):,} track points · "
                f"{len(self._target.cues)} existing cues · "
                f"{len(self._target.pois)} existing POIs"
            ),
        )
        layout.addWidget(info_box)

        # Threshold
        threshold_box = QGroupBox("Settings")
        threshold_form = QFormLayout(threshold_box)
        self._threshold_spin = QDoubleSpinBox()
        self._threshold_spin.setRange(1.0, 500.0)
        self._threshold_spin.setValue(10.0)
        self._threshold_spin.setSuffix(" m")
        self._threshold_spin.setSingleStep(5.0)
        self._threshold_spin.setDecimals(1)
        threshold_form.addRow("Snap radius:", self._threshold_spin)
        layout.addWidget(threshold_box)

        # Result summary label
        self._result_label = QLabel("")
        self._result_label.setWordWrap(True)
        layout.addWidget(self._result_label)

        # Buttons
        btn_row = QHBoxLayout()
        self._preview_btn = QPushButton("Preview")
        self._preview_btn.clicked.connect(self._on_preview)
        btn_row.addWidget(self._preview_btn)
        btn_row.addStretch()

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        apply_btn = self._button_box.button(QDialogButtonBox.StandardButton.Apply)
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._on_apply)
        self._button_box.rejected.connect(self.reject)
        btn_row.addWidget(self._button_box)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _run_merge(self) -> RouteData:
        return copy_cues_pois(self._source, self._target, self._threshold_spin.value())

    def _on_preview(self) -> None:
        merged = self._run_merge()
        added_cues = len(merged.cues) - len(self._target.cues)
        added_pois = len(merged.pois) - len(self._target.pois)
        self._result_label.setText(
            f"Preview: <b>{added_cues}</b> cue(s) and <b>{added_pois}</b> POI(s) "
            f"would be copied within {self._threshold_spin.value():.0f} m."
        )
        self.preview_requested.emit(merged)

    def _on_apply(self) -> None:
        merged = self._run_merge()
        self.preview_requested.emit(merged)
        self.accept()
