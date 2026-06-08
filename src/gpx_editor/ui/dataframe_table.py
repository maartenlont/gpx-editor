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

_CHECKBOX_COL_WIDTH = 24
_ICON_COL_WIDTH = 26


class DataFrameModel(QAbstractTableModel):
    def __init__(
        self,
        df: pl.DataFrame,
        hidden_cols: tuple[str, ...] = ("index",),
        icon_col: str | None = None,
        icon_fn: Callable[[dict], QIcon] | None = None,
        show_checkboxes: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._hidden = set(hidden_cols)
        self._df = df
        self._cols = [c for c in df.columns if c not in self._hidden]
        self._icon_col = icon_col
        self._icon_fn = icon_fn
        self._filter_active_col: str | None = None
        self._show_checkboxes = show_checkboxes
        self._checked_index_vals: set[int] = set()

    # ------------------------------------------------------------------
    # Checkbox helpers
    # ------------------------------------------------------------------

    def _col_offset(self) -> int:
        return 1 if self._show_checkboxes else 0

    def checked_index_vals(self) -> set[int]:
        return set(self._checked_index_vals)

    def clear_checks(self) -> None:
        if not self._checked_index_vals:
            return
        self._checked_index_vals.clear()
        if len(self._df) > 0:
            self.dataChanged.emit(
                self.index(0, 0), self.index(len(self._df) - 1, 0), [Qt.CheckStateRole],
            )

    # ------------------------------------------------------------------
    # QAbstractTableModel overrides
    # ------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(self._df)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(self._cols) + self._col_offset()

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.NoItemFlags
        if self._show_checkboxes and index.column() == 0:
            return Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None

        # Checkbox column
        if self._show_checkboxes and index.column() == 0:
            if role == Qt.CheckStateRole and "index" in self._df.columns:
                idx_val = int(self._df["index"][index.row()])
                return Qt.Checked if idx_val in self._checked_index_vals else Qt.Unchecked
            return None

        col_idx = index.column() - self._col_offset()
        if col_idx < 0 or col_idx >= len(self._cols):
            return None
        col = self._cols[col_idx]

        if role == Qt.DecorationRole and col == self._icon_col and self._icon_fn is not None:
            return self._icon_fn(self._df.row(index.row(), named=True))
        if role == Qt.DisplayRole:
            if col == self._icon_col and self._icon_fn is not None:
                return None  # icon column: no text, decoration only
            value = self._df[index.row(), col]
            return _format(col, value)
        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole) -> bool:
        if not index.isValid():
            return False
        if self._show_checkboxes and index.column() == 0 and role == Qt.CheckStateRole:
            if "index" not in self._df.columns or index.row() >= len(self._df):
                return False
            idx_val = int(self._df["index"][index.row()])
            if value == Qt.Checked:
                self._checked_index_vals.add(idx_val)
            else:
                self._checked_index_vals.discard(idx_val)
            self.dataChanged.emit(index, index, [Qt.CheckStateRole])
            return True
        return False

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole,
    ) -> str | None:
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if self._show_checkboxes and section == 0:
                return ""
            col_idx = section - self._col_offset()
            if 0 <= col_idx < len(self._cols):
                col = self._cols[col_idx]
                if col == self._filter_active_col:
                    return f"{col} ▼"
                return col
        return None

    def set_filter_col(self, col: str | None) -> None:
        self._filter_active_col = col
        total_cols = len(self._cols) + self._col_offset()
        if total_cols > 0:
            self.headerDataChanged.emit(Qt.Horizontal, 0, total_cols - 1)

    def load(self, df: pl.DataFrame) -> None:
        self.beginResetModel()
        self._df = df
        self._cols = [c for c in df.columns if c not in self._hidden]
        self._checked_index_vals.clear()
        self.endResetModel()

    def row_lat_lon(self, row: int) -> tuple[float, float] | None:
        if "lat" not in self._df.columns or "lon" not in self._df.columns:
            return None
        if row >= len(self._df):
            return None
        return float(self._df["lat"][row]), float(self._df["lon"][row])


class DataFrameTableWidget(QWidget):
    """QTableView backed by a DataFrameModel; emits row_selected(row, lat, lon)."""

    row_selected = Signal(int, float, float)
    # Emits a list of stable index values to delete (one or many)
    rows_deleted = Signal(list)
    row_updated = Signal(int, object)  # (index_val, dict of new values)
    filter_changed = Signal()  # emitted when user changes or clears the column filter

    def __init__(
        self,
        df: pl.DataFrame | None = None,
        icon_col: str | None = None,
        icon_fn: Callable[[dict], QIcon] | None = None,
        editable_cols: list[str] | None = None,
        show_checkboxes: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._icon_col = icon_col
        self._editable_cols = editable_cols
        self._full_df: pl.DataFrame = df if df is not None else pl.DataFrame()
        self._filter_col: str | None = None
        self._filter_val: str | None = None
        self._pending_select_row: int | None = None

        self._model = DataFrameModel(
            self._full_df,
            icon_col=icon_col,
            icon_fn=icon_fn,
            show_checkboxes=show_checkboxes,
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

        self._fix_column_widths()

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
        # Restore selection to the row that was pending (e.g. after a delete)
        if self._pending_select_row is not None:
            row = min(self._pending_select_row, len(self._model._df) - 1)
            if row >= 0:
                self._view.selectionModel().blockSignals(True)
                self._view.selectRow(row)
                self._view.selectionModel().blockSignals(False)
                self._view.scrollTo(self._model.index(row, 0))
            self._pending_select_row = None

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

    def current_row(self) -> int:
        """Return the currently selected row index, or -1 if none."""
        idx = self._view.currentIndex()
        return idx.row() if idx.isValid() else -1

    def select_next_row(self) -> None:
        """Move selection to the next row (wraps to first if at end)."""
        df = self._model._df
        if len(df) == 0:
            return
        current = self.current_row()
        next_row = (current + 1) % len(df) if current >= 0 else 0
        self._view.selectRow(next_row)
        self._view.scrollTo(self._model.index(next_row, 0))

    def delete_current_and_select_next(self) -> None:
        """Delete checked rows (if any) or the current row, then select the next row.

        Emits rows_deleted with the stable index values of all deleted rows.
        After the subsequent data reload, the row at the same visual position
        is automatically re-selected (handled in load()).
        """
        df = self._model._df
        if len(df) == 0 or "index" not in df.columns:
            return

        checked = self._model.checked_index_vals()
        if checked:
            # Bulk delete: find the lowest visual row of the checked set so we
            # can scroll back there after the table rebuilds.
            visual_rows = [
                i for i in range(len(df)) if int(df["index"][i]) in checked
            ]
            self._pending_select_row = min(visual_rows) if visual_rows else 0
            self.rows_deleted.emit(list(checked))
        else:
            current = self.current_row()
            if current < 0:
                return
            self._pending_select_row = current
            self.rows_deleted.emit([int(df["index"][current])])

    # ------------------------------------------------------------------
    # Filter
    # ------------------------------------------------------------------

    def _on_header_clicked(self, logical_index: int) -> None:
        # Skip the checkbox column
        col_idx = logical_index - self._model._col_offset()
        if col_idx < 0 or col_idx >= len(self._model._cols):
            return
        col = self._model._cols[col_idx]
        if col not in self._full_df.columns:
            return

        # Build unique menu items: formatted display string → raw stored value.
        raw_vals = self._full_df[col].drop_nulls().to_list()
        seen: dict[str, str] = {}  # display → raw (first occurrence wins)
        for v in raw_vals:
            raw = str(v)
            if not raw.strip():
                continue
            display = _format(col, v)
            if display not in seen:
                seen[display] = raw
        items = sorted(seen.items())

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
        self._fix_column_widths()

    def _fix_column_widths(self) -> None:
        hdr = self._view.horizontalHeader()
        if self._model._show_checkboxes:
            hdr.setSectionResizeMode(0, QHeaderView.Fixed)
            self._view.setColumnWidth(0, _CHECKBOX_COL_WIDTH)
        if self._icon_col and self._icon_col in self._model._cols:
            icon_idx = self._model._cols.index(self._icon_col) + self._model._col_offset()
            hdr.setSectionResizeMode(icon_idx, QHeaderView.Fixed)
            self._view.setColumnWidth(icon_idx, _ICON_COL_WIDTH)

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
            self._pending_select_row = row
            self.rows_deleted.emit([index_val])

    def _on_row_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            return
        row = current.row()
        coords = self._model.row_lat_lon(row)
        if coords:
            self.row_selected.emit(row, *coords)
