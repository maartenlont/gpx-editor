"""Route list widget — shows all loaded routes with visibility, color, label, remove."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gpx_editor.models.route_entry import PALETTE, RouteEntry


def _color_icon(hex_color: str, size: int = 16) -> QIcon:
    """Return a solid-color square QIcon for use in combo boxes."""
    px = QPixmap(size, size)
    px.fill(QColor(hex_color))
    return QIcon(px)


class RouteListWidget(QWidget):
    active_changed = Signal(int)
    color_changed = Signal(int, str)
    visibility_changed = Signal(int, bool)
    route_removed = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._updating = False

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["", "Color", "Route", ""])
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Column widths
        self._table.setColumnWidth(0, 30)   # checkbox
        self._table.setColumnWidth(1, 90)   # color combo
        # col 2 (label) gets remaining width via stretch
        self._table.horizontalHeader().setSectionResizeMode(2, self._table.horizontalHeader().ResizeMode.Stretch)
        self._table.setColumnWidth(3, 30)   # remove button

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table)

        self._table.selectionModel().currentRowChanged.connect(
            lambda current, _prev: self._on_current_row_changed(current.row())
        )
        self._table.itemChanged.connect(self._on_item_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_routes(self, entries: list[RouteEntry], active_index: int) -> None:
        """Rebuild the table from *entries*, selecting *active_index*."""
        self._updating = True
        self._table.setRowCount(0)
        for row_idx, entry in enumerate(entries):
            self._table.insertRow(row_idx)

            # Col 0: visibility checkbox
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check_item.setCheckState(Qt.Checked if entry.visible else Qt.Unchecked)
            self._table.setItem(row_idx, 0, check_item)

            # Col 1: color combo box
            combo = QComboBox()
            for hex_color, name in PALETTE:
                combo.addItem(_color_icon(hex_color), name, hex_color)
            # Select current color
            for i in range(combo.count()):
                if combo.itemData(i) == entry.color:
                    combo.setCurrentIndex(i)
                    break
            combo.currentIndexChanged.connect(
                lambda _idx, r=row_idx, c=combo: self._on_color_changed(r, c)
            )
            self._table.setCellWidget(row_idx, 1, combo)

            # Col 2: label (read-only)
            label_item = QTableWidgetItem(entry.label)
            label_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._table.setItem(row_idx, 2, label_item)

            # Col 3: remove button
            remove_btn = QPushButton("×")
            remove_btn.setFixedWidth(28)
            remove_btn.clicked.connect(
                lambda _checked=False, r=row_idx: self.route_removed.emit(r)
            )
            self._table.setCellWidget(row_idx, 3, remove_btn)

        self._updating = False

        # Select active row — block the selection model (not just the widget)
        # because currentRowChanged belongs to the selection model and
        # blockSignals(True) on the QTableWidget doesn't silence it.
        if 0 <= active_index < len(entries):
            sm = self._table.selectionModel()
            sm.blockSignals(True)
            self._table.setCurrentCell(active_index, 2)
            sm.blockSignals(False)

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_current_row_changed(self, current_row: int) -> None:
        if self._updating:
            return
        if current_row >= 0:
            self.active_changed.emit(current_row)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating:
            return
        if item.column() == 0:
            row = item.row()
            visible = item.checkState() == Qt.Checked
            self.visibility_changed.emit(row, visible)

    def _on_color_changed(self, row: int, combo: QComboBox) -> None:
        if self._updating:
            return
        hex_color: str = combo.currentData()
        self.color_changed.emit(row, hex_color)
