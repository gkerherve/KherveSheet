"""Application entry point.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import faulthandler
import os
import sys
import tempfile

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication, QStyleFactory

from . import APP_NAME


_CRASH_LOG_FILE = None


def _enable_crash_logging():
    global _CRASH_LOG_FILE
    try:
        path = os.path.join(tempfile.gettempdir(), "khervesheet_crash.log")
        _CRASH_LOG_FILE = open(path, "a+", encoding="utf-8", buffering=1)
        _CRASH_LOG_FILE.write("\n=== KherveSheet start ===\n")
        _CRASH_LOG_FILE.flush()
        faulthandler.enable(file=_CRASH_LOG_FILE, all_threads=True)
        try:
            sys.stderr.write(f"[KherveSheet] crash log: {path}\n")
        except Exception:
            pass
    except Exception:
        try:
            faulthandler.enable()
        except Exception:
            pass


def _make_app_icon():
    """Build the app icon via the icons module (qtawesome themed)."""
    from .icons import init_app_icon
    return init_app_icon()


_LIGHT_QSS = """
QMainWindow, QDialog { background: #f4f5f7; }
QMenuBar {
    background: #ffffff;
    border-bottom: 1px solid #d4d6db;
    padding: 2px;
}
QMenuBar::item:selected { background: #cce0f8; }
QToolBar {
    background: #ffffff;
    border-bottom: 1px solid #d4d6db;
    spacing: 2px;
}
QStatusBar {
    background: #f0f0f0;
    border-top: 1px solid #d4d6db;
}
QTabBar::tab {
    background: #e9ecef;
    border: 1px solid #c8ccd1;
    padding: 3px 10px;
    margin-right: 1px;
}
QTabBar::tab:selected {
    background: #ffffff;
    border-bottom-color: #ffffff;
}
QTabBar::tab:hover { background: #d8e4f0; }
QPushButton {
    background: #fafafa;
    border: 1px solid #aab0b8;
    padding: 3px 10px;
    border-radius: 3px;
}
QPushButton:hover  { background: #e6efff; border-color: #3a78b4; }
QPushButton:pressed { background: #cce0f8; }
QToolButton:hover { background: #e6efff; border-radius: 3px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: white;
    border: 1px solid #b8bcc3;
    border-radius: 2px;
    padding: 2px 4px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #3a78b4;
}
QGroupBox {
    border: 1px solid #c8ccd1;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QTreeWidget, QListWidget, QTableWidget {
    background: white;
    alternate-background-color: #f7f8fa;
    border: 1px solid #c8ccd1;
}
"""


def _apply_palette(app):
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#f4f5f7"))
    pal.setColor(QPalette.WindowText, QColor("#202329"))
    pal.setColor(QPalette.Base, QColor("#ffffff"))
    pal.setColor(QPalette.AlternateBase, QColor("#f7f8fa"))
    pal.setColor(QPalette.ToolTipBase, QColor("#fffbcc"))
    pal.setColor(QPalette.ToolTipText, QColor("#202329"))
    pal.setColor(QPalette.Text, QColor("#202329"))
    pal.setColor(QPalette.Button, QColor("#fafafa"))
    pal.setColor(QPalette.ButtonText, QColor("#202329"))
    pal.setColor(QPalette.Highlight, QColor("#3a78b4"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.Link, QColor("#1a5fa3"))
    app.setPalette(pal)


def main():
    _enable_crash_logging()

    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("KherveSheet")
    app.setOrganizationDomain("khervesheet.local")

    try:
        QApplication.setStyle(QStyleFactory.create("Fusion"))
    except Exception:
        pass
    _apply_palette(app)
    app.setStyleSheet(_LIGHT_QSS)

    icon = _make_app_icon()
    app.setWindowIcon(icon)

    from .mainwindow import MainWindow
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
