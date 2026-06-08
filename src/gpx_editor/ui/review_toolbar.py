"""Review toolbar with delete/skip buttons for reviewing cues and POIs."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class ReviewToolbar(QWidget):
    """Toolbar with delete (red ✖) and skip (green ✔) buttons for row review.

    Emits:
        delete_requested: User clicked the delete button.
        skip_requested: User clicked the skip/next button.
    """

    delete_requested = Signal()
    skip_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._delete_btn = QPushButton("✖ Delete")
        self._delete_btn.setToolTip("Delete selected row and move to next (Ctrl+D)")
        self._delete_btn.setStyleSheet(
            "QPushButton { color: #c62828; font-weight: bold; }"
            "QPushButton:hover { background-color: #ffebee; }"
        )
        self._delete_btn.clicked.connect(self.delete_requested)

        self._skip_btn = QPushButton("✔ Skip")
        self._skip_btn.setToolTip("Move to next row (Ctrl+J)")
        self._skip_btn.setStyleSheet(
            "QPushButton { color: #2e7d32; font-weight: bold; }"
            "QPushButton:hover { background-color: #e8f5e9; }"
        )
        self._skip_btn.clicked.connect(self.skip_requested)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self._delete_btn)
        layout.addWidget(self._skip_btn)
        layout.addStretch()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable both buttons."""
        self._delete_btn.setEnabled(enabled)
        self._skip_btn.setEnabled(enabled)
