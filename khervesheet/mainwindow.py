"""Main window shell — menus, toolbars, status bar.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow, QStatusBar, QLabel,
)

from . import APP_NAME, __version__


class MainWindow(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = None
        self._init_ui()

    def _init_ui(self):
        self._update_title()
        self.resize(1280, 800)

        # Status bar
        self.setStatusBar(QStatusBar())
        self._status_label = QLabel("Ready")
        self.statusBar().addWidget(self._status_label)
        self.statusBar().showMessage("Ready")

    def _update_title(self):
        name = self._current_file or "Untitled"
        self.setWindowTitle(f"{APP_NAME} v{__version__} \u2014 {name}")
