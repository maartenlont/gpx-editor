"""Application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from gpx_editor.main_window import MainWindow


def run() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
