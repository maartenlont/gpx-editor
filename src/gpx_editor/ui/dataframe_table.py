"""Generic QAbstractTableModel over a Polars DataFrame + a table widget with row selection."""

from __future__ import annotations

from collections.abc import Callable

import polars as pl
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import QHeaderView, QMenu, QTableView, QVBoxLayout, QWidget


def _format(col: str, value: object) -> str:
    if value is None:
        return ""
    if col == "distance":
        return f"{float(value) / 1000:.2f} km"
    if col in ("lat", "lon"):
        return f"{float(value):.6f}"
    if col == "elevation":
        return f"{float(value):.1f} m"
    if col == "symbol":
        return str(value).replace("_", " ").title()
    return str(value)


# Columns whose filter comparison should be case-insensitive
_CASE_INSENSITIVE_COLS: frozenset[str] = frozenset({"symbol", "name"})

# Sentinel stored in _filter_val when the user selected "None" (hide all rows)
_HIDE_ALL = "\x00"


class DataFrameModel(QAbstractTableModel):
    def __init__(
        self,
        df: pl.DataFrame,
        hidden_cols: tuple[str, ...] = ("index",),
        icon_col: str | None = None,
        icon_fn: Callable[[dict], QIcon] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._hidden = set(hidden_cols)
        self._df = df
        self._cols = [c for c in df.columns if c not in self._hidden]
        self._icon_col = icon_col
        self._icon_fn = icon_fn
        self._filter_active_col: str | None = None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(self._df)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(self._cols)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        col = self._cols[index.column()]
        if role == Qt.DecorationRole and col == self._icon_col and self._icon_fn is not None:
            return self._icon_fn(self._df.row(index.row(), named=True))
        if role == Qt.DisplayRole:
            if col == self._icon_col and self._icon_fn is not None:
                return None  # icon column: no text, decoration only
            value = self._df[index.row(), col]
            return _format(col, value)
        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole,
    ) -> str | None:
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            col = self._cols[section]
            if col == self._filter_active_col:
                return f"{col} ▼"
            return col
        return None

    def set_filter_col(self, col: str | None) -> None:
        self._filter_active_col = col
        if self._cols:
            self.headerDataChanged.emit(Qt.Horizontal, 0, len(self._cols) - 1)

    def load(self, df: pl.DataFrame) -> None:
        self.beginResetModel()
        self._df = df
        self._cols = [c for c in df.columns if c not in self._hidden]
        self.endResetModel()

    def row_lat_lon(self, row: int) -> tuple[float, float] | None:
        if "lat" not in self._df.columns or "lon" not in self._df.columns:
            return None
        if row >= len(self._df):
            return None
        return float(self._df["lat"][row]), float(self._df["lon"][row])


_ICON_COL_WIDTH = 26  # pixels for an icon-only column


class DataFrameTableWidget(QWidget):
    """QTableView backed by a DataFrameModel; emits row_selected(row, lat, lon)."""

    row_selected = Signal(int, float, float)
    # index_val is the value of the hidden 'index' column (stable row identity)
    row_deleted = Signal(int)
    row_updated = Signal(int, object)  # (index_val, dict of new values)
    filter_changed = Signal()  # emitted when user changes or clears the column filter

    def __init__(
        self,
        df: pl.DataFrame | None = None,
        icon_col: str | None = None,
        icon_fn: Callable[[dict], QIcon] | None = None,
        editable_cols: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._icon_col = icon_col
        self._editable_cols = editable_cols
        self._full_df: pl.DataFrame = df if df is not None else pl.DataFrame()
        self._filter_col: str | None = None
        self._filter_val: str | None = None

        self._model = DataFrameModel(
            self._full_df,
            icon_col=icon_col,
            icon_fn=icon_fn,
        )
        self._view = QTableView()
        self._view.setModel(self._model)
        self._view.setSelectionBehavior(QTableView.SelectRows)
        self._view.setSelectionMode(QTableView.SingleSelection)
        self._view.setAlternatingRowColors(True)

        hdr = self._view.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setStretchLastSection(True)
        hdr.setSectionsClickable(True)
        hdr.setCursor(Qt.PointingHandCursor)
        hdr.sectionClicked.connect(self._on_header_clicked)

        self._view.verticalHeader().setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._view.selectionModel().currentRowChanged.connect(self._on_row_changed)

        self._view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._on_context_menu)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def visible_df(self) -> pl.DataFrame:
        """The currently displayed (possibly filtered) DataFrame."""
        return self._model._df

    @property
    def full_df(self) -> pl.DataFrame:
        """The complete unfiltered DataFrame (used for saving)."""
        return self._full_df

    def load(self, df: pl.DataFrame) -> None:
        self._full_df = df
        self._apply_filter()

    def select_row_by_index_val(self, index_val: int) -> None:
        """Select and scroll to the row whose 'index' column equals *index_val*."""
        df = self._model._df
        if "index" not in df.columns or len(df) == 0:
            return
        matches = (df["index"] == index_val).to_list()
        if True not in matches:
            return
        row = matches.index(True)
        self._view.selectionModel().blockSignals(True)
        self._view.selectRow(row)
        self._view.selectionModel().blockSignals(False)
        self._view.scrollTo(self._model.index(row, 0))

    def select_nearest_distance(self, distance_m: float) -> None:
        """Select and scroll to the row whose distance is closest to *distance_m*."""
        df = self._model._df
        if "distance" not in df.columns or len(df) == 0:
            return
        idx = int((df["distance"] - distance_m).abs().arg_min())
        self._view.selectionModel().blockSignals(True)
        self._view.selectRow(idx)
        self._view.selectionModel().blockSignals(False)
        self._view.scrollTo(self._model.index(idx, 0))

    # ------------------------------------------------------------------
    # Filter
    # ------------------------------------------------------------------

    def _on_header_clicked(self, logical_index: int) -> None:
        if logical_index >= len(self._model._cols):
            return
        col = self._model._cols[logical_index]
        if col not in self._full_df.columns:
            return

        # Build unique menu items: formatted display string → raw stored value.
        # Using _format() keeps the menu consistent with what the table shows.
        raw_vals = self._full_df[col].drop_nulls().to_list()
        seen: dict[str, str] = {}  # display → raw (first occurrence wins)
        for v in raw_vals:
            raw = str(v)
            if not raw.strip():
                continue
            display = _format(col, v)
            if display not in seen:
                seen[display] = raw
        items = sorted(seen.items())  # sorted by display label

        menu = QMenu(self._view)
        show_all = menu.addAction("Show all")
        show_all.setCheckable(True)
        show_all.setChecked(self._filter_col != col)

        hide_all = menu.addAction("None")
        hide_all.setCheckable(True)
        hide_all.setChecked(self._filter_col == col and self._filter_val == _HIDE_ALL)

        menu.addSeparator()

        val_acts: dict = {}
        for display, raw in items:
            act = menu.addAction(display)
            act.setCheckable(True)
            act.setChecked(
                self._filter_col == col
                and self._filter_val is not None
                and self._filter_val != _HIDE_ALL
                and self._filter_val.lower() == raw.lower()
            )
            val_acts[act] = raw

        action = menu.exec(QCursor.pos())
        if action is None:
            return

        if action is show_all:
            if self._filter_col is not None:
                self._filter_col = None
                self._filter_val = None
                self._apply_filter()
                self.filter_changed.emit()
        elif action is hide_all:
            already_hidden = self._filter_col == col and self._filter_val == _HIDE_ALL
            if already_hidden:
                self._filter_col = None
                self._filter_val = None
            else:
                self._filter_col = col
                self._filter_val = _HIDE_ALL
            self._apply_filter()
            self.filter_changed.emit()
        elif action in val_acts:
            chosen_raw = val_acts[action]
            already_active = (
                self._filter_col == col
                and self._filter_val is not None
                and self._filter_val != _HIDE_ALL
                and self._filter_val.lower() == chosen_raw.lower()
            )
            if already_active:
                self._filter_col = None
                self._filter_val = None
            else:
                self._filter_col = col
                self._filter_val = chosen_raw
            self._apply_filter()
            self.filter_changed.emit()

    def _apply_filter(self) -> None:
        if self._filter_col is None:
            display_df = self._full_df
        elif self._filter_val == _HIDE_ALL:
            display_df = self._full_df.clear()
        else:
            col = self._filter_col
            val = self._filter_val or ""
            if col in self._full_df.columns:
                if col in _CASE_INSENSITIVE_COLS:
                    display_df = self._full_df.filter(
                        pl.col(col).cast(pl.String).str.to_lowercase() == val.lower(),
                    )
                else:
                    display_df = self._full_df.filter(
                        pl.col(col).cast(pl.String) == val,
                    )
            else:
                display_df = self._full_df
        self._model.load(display_df)
        self._model.set_filter_col(self._filter_col)
        self._fix_icon_col_width()

    def _fix_icon_col_width(self) -> None:
        if self._icon_col and self._icon_col in self._model._cols:
            idx = self._model._cols.index(self._icon_col)
            hdr = self._view.horizontalHeader()
            hdr.setSectionResizeMode(idx, QHeaderView.Fixed)
            self._view.setColumnWidth(idx, _ICON_COL_WIDTH)

    # ------------------------------------------------------------------
    # Context menu (right-click on row)
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        idx = self._view.indexAt(pos)
        if not idx.isValid():
            return
        if "index" not in self._model._df.columns:
            return
        row = idx.row()
        index_val = int(self._model._df["index"][row])

        menu = QMenu(self._view)
        edit_act = menu.addAction("Edit properties…") if self._editable_cols else None
        delete_act = menu.addAction("Delete")

        action = menu.exec(QCursor.pos())
        if action is None:
            return

        if edit_act is not None and action == edit_act:
            from gpx_editor.ui.row_edit_dialog import RowEditDialog
            row_data = self._model._df.row(row, named=True)
            dlg = RowEditDialog(row_data, self._editable_cols, parent=self._view)
            if dlg.exec() == RowEditDialog.DialogCode.Accepted:
                self.row_updated.emit(index_val, dlg.get_values())
        elif action == delete_act:
            self.row_deleted.emit(index_val)

    def _on_row_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            return
        row = current.row()
        coords = self._model.row_lat_lon(row)
        if coords:
            self.row_selected.emit(row, *coords)
