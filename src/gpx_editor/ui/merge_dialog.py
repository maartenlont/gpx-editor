"""Dialog for merging cues and POIs from one route into another."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)

from gpx_editor.logic.merge import copy_cues_pois
from gpx_editor.models.route import RouteData
from gpx_editor.models.route_entry import RouteEntry


class MergeDialog(QDialog):
    """
    Merge dialog for multi-route support.

    Takes a list of RouteEntry objects. The user picks a source (copy FROM)
    and a target (copy INTO). On Apply the merged route is stored and the
    dialog accepts. The caller retrieves the result via ``get_result()``.
    """

    def __init__(self, entries: list[RouteEntry], parent=None) -> None:
        super().__init__(parent)
        self._entries = entries
        self._result: tuple[RouteData, str] | None = None
        self._setup_ui()
        self.setWindowTitle("Merge Cues & POIs")
        self.setMinimumWidth(440)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Source / target selection
        routes_box = QGroupBox("Routes")
        routes_form = QFormLayout(routes_box)

        self._source_combo = QComboBox()
        self._target_combo = QComboBox()
        for entry in self._entries:
            self._source_combo.addItem(entry.label)
            self._target_combo.addItem(entry.label)

        # Default: source = 0, target = 1 (if available)
        self._source_combo.setCurrentIndex(0)
        self._target_combo.setCurrentIndex(1 if len(self._entries) > 1 else 0)

        routes_form.addRow("Copy cues/POIs from:", self._source_combo)
        routes_form.addRow("Into track of:", self._target_combo)
        layout.addWidget(routes_box)

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

        # Warning / result label
        self._info_label = QLabel("")
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

        # Buttons
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel,
        )
        self._apply_btn = self._button_box.button(QDialogButtonBox.StandardButton.Apply)
        self._apply_btn.setDefault(True)
        self._apply_btn.clicked.connect(self._on_apply)
        self._button_box.rejected.connect(self.reject)
        layout.addWidget(self._button_box)

        # Validate initial state and connect change signals
        self._validate()
        self._source_combo.currentIndexChanged.connect(self._validate)
        self._target_combo.currentIndexChanged.connect(self._validate)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        """Enable/disable Apply based on source != target."""
        src_idx = self._source_combo.currentIndex()
        tgt_idx = self._target_combo.currentIndex()
        if src_idx == tgt_idx:
            self._info_label.setText(
                "<span style='color:red;'>Source and target must be different routes.</span>",
            )
            self._apply_btn.setEnabled(False)
        else:
            self._info_label.setText("")
            self._apply_btn.setEnabled(True)

    def _on_apply(self) -> None:
        src_idx = self._source_combo.currentIndex()
        tgt_idx = self._target_combo.currentIndex()
        if src_idx == tgt_idx:
            return
        source = self._entries[src_idx]
        target = self._entries[tgt_idx]
        merged = copy_cues_pois(source.route, target.route, self._threshold_spin.value())
        label = f"Merged — {target.label}"
        self._result = (merged, label)
        self.accept()

    # ------------------------------------------------------------------
    # Public result access
    # ------------------------------------------------------------------

    def get_result(self) -> tuple[RouteData, str] | None:
        """Return ``(merged_route, label)`` if accepted, else ``None``."""
        return self._result
