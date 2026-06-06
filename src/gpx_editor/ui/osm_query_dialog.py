"""Dialog for querying OSM POIs by category and buffer distance."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
)

from gpx_editor.io.osm_reader import OSM_CATEGORIES


class OsmQueryDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import OSM POIs")
        self.setMinimumWidth(320)

        self._category_box = QComboBox()
        self._category_box.addItems(list(OSM_CATEGORIES.keys()))

        self._buffer_spin = QSpinBox()
        self._buffer_spin.setRange(50, 5_000)
        self._buffer_spin.setValue(100)
        self._buffer_spin.setSuffix(" m")

        form = QFormLayout()
        form.addRow("POI Type:", self._category_box)
        form.addRow("Buffer:", self._buffer_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Query")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def category(self) -> str:
        return self._category_box.currentText()

    def buffer_m(self) -> int:
        return self._buffer_spin.value()
