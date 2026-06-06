"""Generic QAbstractTableModel over a Polars DataFrame + a table widget with row selection."""

from __future__ import annotations

from typing import Optional

import polars as pl
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import QHeaderView, QTableView, QVBoxLayout, QWidget


def _format(col: str, value: object) -> str:
    if value is None:
        return ""
    if col == "distance":
        return f"{float(value) / 1000:.2f} km"
    if col in ("lat", "lon"):
        return f"{float(value):.6f}"
    if col == "elevation":
        return f"{float(value):.1f} m"
    return str(value)


class DataFrameModel(QAbstractTableModel):
    def __init__(
        self,
        df: pl.DataFrame,
        hidden_cols: tuple[str, ...] = ("index",),
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._hidden = set(hidden_cols)
        self._df = df
        self._cols = [c for c in df.columns if c not in self._hidden]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(self._df)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(self._cols)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Optional[str]:
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            col = self._cols[index.column()]
            value = self._df[index.row(), col]
            return _format(col, value)
        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Optional[str]:
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._cols[section]
        return None

    def load(self, df: pl.DataFrame) -> None:
        self.beginResetModel()
        self._df = df
        self._cols = [c for c in df.columns if c not in self._hidden]
        self.endResetModel()

    def row_lat_lon(self, row: int) -> Optional[tuple[float, float]]:
        if "lat" not in self._df.columns or "lon" not in self._df.columns:
            return None
        if row >= len(self._df):
            return None
        return float(self._df["lat"][row]), float(self._df["lon"][row])


class DataFrameTableWidget(QWidget):
    """QTableView backed by a DataFrameModel; emits row_selected(row, lat, lon)."""

    row_selected = Signal(int, float, float)

    def __init__(self, df: Optional[pl.DataFrame] = None, parent=None) -> None:
        super().__init__(parent)
        self._model = DataFrameModel(df if df is not None else pl.DataFrame())
        self._view = QTableView()
        self._view.setModel(self._model)
        self._view.setSelectionBehavior(QTableView.SelectRows)
        self._view.setSelectionMode(QTableView.SingleSelection)
        self._view.setAlternatingRowColors(True)
        self._view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._view.horizontalHeader().setStretchLastSection(True)
        self._view.verticalHeader().setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._view.selectionModel().currentRowChanged.connect(self._on_row_changed)

    def load(self, df: pl.DataFrame) -> None:
        self._model.load(df)

    def select_nearest_distance(self, distance_m: float) -> None:
        """Select and scroll to the row whose distance is closest to *distance_m*.

        Signals are blocked during the programmatic selection to avoid a
        feedback loop back into the elevation widget / map.
        """
        df = self._model._df
        if "distance" not in df.columns or len(df) == 0:
            return
        idx = int((df["distance"] - distance_m).abs().arg_min())
        self._view.selectionModel().blockSignals(True)
        self._view.selectRow(idx)
        self._view.selectionModel().blockSignals(False)
        self._view.scrollTo(self._model.index(idx, 0))

    def _on_row_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            return
        row = current.row()
        coords = self._model.row_lat_lon(row)
        if coords:
            self.row_selected.emit(row, *coords)
