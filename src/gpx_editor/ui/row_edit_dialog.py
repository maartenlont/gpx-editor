"""Generic single-row property editor dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)


class RowEditDialog(QDialog):
    """Shows a form with one QLineEdit per *editable_cols* field from *row_data*."""

    def __init__(
        self,
        row_data: dict,
        editable_cols: list[str],
        title: str = "Edit properties",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)
        self._fields: dict[str, QLineEdit] = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()

        for col in editable_cols:
            val = row_data.get(col)
            le = QLineEdit("" if val is None else str(val))
            self._fields[col] = le
            form.addRow(col.replace("_", " ").title() + ":", le)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_values(self) -> dict[str, str | None]:
        """Return edited values; empty string is returned as None."""
        result = {}
        for col, le in self._fields.items():
            text = le.text().strip()
            result[col] = text if text else None
        return result
