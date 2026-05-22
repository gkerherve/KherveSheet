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


# ── Shared QSS fragments ─────────────────────────────────────────
_COMMON_QSS = """
QToolBar { padding: 0px; margin: 0px; spacing: 1px; }
QToolButton { padding: 1px; margin: 0px; }
"""

# ── Light theme ──────────────────────────────────────────────────
_LIGHT_QSS = _COMMON_QSS + """
QMainWindow, QDialog { background: #f4f5f7; }
QMenuBar {
    background: #ffffff;
    border-bottom: 1px solid #d4d6db;
    padding: 2px;
}
QMenuBar::item:selected { background: #cce0f8; }
QToolBar { background: #ffffff; border-bottom: 1px solid #d4d6db; }
QStatusBar { background: #f0f0f0; border-top: 1px solid #d4d6db; }
QTabBar::tab {
    background: #e9ecef; border: 1px solid #c8ccd1;
    padding: 3px 10px; margin-right: 1px;
}
QTabBar::tab:selected { background: #ffffff; border-bottom-color: #ffffff; }
QTabBar::tab:hover { background: #d8e4f0; }
QPushButton {
    background: #fafafa; border: 1px solid #aab0b8;
    padding: 3px 10px; border-radius: 3px;
}
QPushButton:hover  { background: #e6efff; border-color: #3a78b4; }
QPushButton:pressed { background: #cce0f8; }
QToolButton:hover { background: #e6efff; border-radius: 3px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: white; border: 1px solid #b8bcc3;
    border-radius: 2px; padding: 2px 4px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #3a78b4;
}
QGroupBox {
    border: 1px solid #c8ccd1; border-radius: 4px;
    margin-top: 8px; padding-top: 8px;
}
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QTreeWidget, QListWidget, QTableWidget {
    background: white; alternate-background-color: #f7f8fa;
    border: 1px solid #c8ccd1;
}
QHeaderView::section {
    background: #f0f2f5; border: 1px solid #d4d6db;
    padding: 2px 4px;
}
"""

_LIGHT_PALETTE = {
    "Window": "#f4f5f7", "WindowText": "#202329",
    "Base": "#ffffff", "AlternateBase": "#f7f8fa",
    "ToolTipBase": "#fffbcc", "ToolTipText": "#202329",
    "Text": "#202329", "Button": "#fafafa",
    "ButtonText": "#202329", "Highlight": "#3a78b4",
    "HighlightedText": "#ffffff", "Link": "#1a5fa3",
}

# ── Dark theme ───────────────────────────────────────────────────
_DARK_QSS = _COMMON_QSS + """
QMainWindow, QDialog { background: #1e1e2e; }
QMenuBar {
    background: #2a2a3c; color: #e0e0e0;
    border-bottom: 1px solid #3a3a4c; padding: 2px;
}
QMenuBar::item:selected { background: #3a5580; }
QMenu { background: #2a2a3c; color: #e0e0e0; border: 1px solid #3a3a4c; }
QMenu::item:selected { background: #3a5580; }
QToolBar { background: #2a2a3c; border-bottom: 1px solid #3a3a4c; }
QStatusBar { background: #252535; color: #c0c0c0; border-top: 1px solid #3a3a4c; }
QTabBar::tab {
    background: #2a2a3c; color: #c0c0c0;
    border: 1px solid #3a3a4c; padding: 3px 10px; margin-right: 1px;
}
QTabBar::tab:selected { background: #1e1e2e; color: #ffffff; border-bottom-color: #1e1e2e; }
QTabBar::tab:hover { background: #35354a; }
QPushButton {
    background: #35354a; color: #e0e0e0;
    border: 1px solid #4a4a5e; padding: 3px 10px; border-radius: 3px;
}
QPushButton:hover  { background: #3a5580; border-color: #5588bb; }
QPushButton:pressed { background: #2a4570; }
QToolButton { color: #e0e0e0; }
QToolButton:hover { background: #3a5580; border-radius: 3px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #2e2e40; color: #e0e0e0;
    border: 1px solid #4a4a5e; border-radius: 2px; padding: 2px 4px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #5588bb;
}
QComboBox QAbstractItemView { background: #2e2e40; color: #e0e0e0; }
QGroupBox {
    color: #c0c0c0; border: 1px solid #4a4a5e;
    border-radius: 4px; margin-top: 8px; padding-top: 8px;
}
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QTreeWidget, QListWidget, QTableWidget {
    background: #1e1e2e; color: #e0e0e0;
    alternate-background-color: #252535;
    border: 1px solid #3a3a4c; gridline-color: #3a3a4c;
}
QHeaderView::section {
    background: #2a2a3c; color: #c0c0c0;
    border: 1px solid #3a3a4c; padding: 2px 4px;
}
QLabel { color: #e0e0e0; }
QScrollBar:vertical, QScrollBar:horizontal { background: #2a2a3c; }
QScrollBar::handle { background: #4a4a5e; border-radius: 3px; }
QScrollBar::handle:hover { background: #5a5a70; }
"""

_DARK_PALETTE = {
    "Window": "#1e1e2e", "WindowText": "#e0e0e0",
    "Base": "#1e1e2e", "AlternateBase": "#252535",
    "ToolTipBase": "#35354a", "ToolTipText": "#e0e0e0",
    "Text": "#e0e0e0", "Button": "#35354a",
    "ButtonText": "#e0e0e0", "Highlight": "#3a6eb5",
    "HighlightedText": "#ffffff", "Link": "#6aadff",
}

# ── Blue Dark ────────────────────────────────────────────────────
_BLUE_DARK_QSS = _COMMON_QSS + """
QMainWindow, QDialog { background: #1a2332; }
QMenuBar {
    background: #1f2b3d; color: #d0d8e0;
    border-bottom: 1px solid #2a3a50; padding: 2px;
}
QMenuBar::item:selected { background: #2a4a6e; }
QMenu { background: #1f2b3d; color: #d0d8e0; border: 1px solid #2a3a50; }
QMenu::item:selected { background: #2a4a6e; }
QToolBar { background: #1f2b3d; border-bottom: 1px solid #2a3a50; }
QStatusBar { background: #172030; color: #a0b0c0; border-top: 1px solid #2a3a50; }
QTabBar::tab {
    background: #1f2b3d; color: #a0b0c0;
    border: 1px solid #2a3a50; padding: 3px 10px; margin-right: 1px;
}
QTabBar::tab:selected { background: #1a2332; color: #ffffff; border-bottom-color: #1a2332; }
QTabBar::tab:hover { background: #253550; }
QPushButton {
    background: #253550; color: #d0d8e0;
    border: 1px solid #3a5070; padding: 3px 10px; border-radius: 3px;
}
QPushButton:hover  { background: #2a5580; border-color: #4a80b0; }
QPushButton:pressed { background: #1e4060; }
QToolButton { color: #d0d8e0; }
QToolButton:hover { background: #2a5580; border-radius: 3px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #1a2a3e; color: #d0d8e0;
    border: 1px solid #3a5070; border-radius: 2px; padding: 2px 4px;
}
QComboBox QAbstractItemView { background: #1a2a3e; color: #d0d8e0; }
QTreeWidget, QListWidget, QTableWidget {
    background: #1a2332; color: #d0d8e0;
    alternate-background-color: #1e2a3a;
    border: 1px solid #2a3a50; gridline-color: #2a3a50;
}
QHeaderView::section {
    background: #1f2b3d; color: #a0b0c0;
    border: 1px solid #2a3a50; padding: 2px 4px;
}
QLabel { color: #d0d8e0; }
QScrollBar:vertical, QScrollBar:horizontal { background: #1f2b3d; }
QScrollBar::handle { background: #3a5070; border-radius: 3px; }
"""

_BLUE_DARK_PALETTE = {
    "Window": "#1a2332", "WindowText": "#d0d8e0",
    "Base": "#1a2332", "AlternateBase": "#1e2a3a",
    "ToolTipBase": "#253550", "ToolTipText": "#d0d8e0",
    "Text": "#d0d8e0", "Button": "#253550",
    "ButtonText": "#d0d8e0", "Highlight": "#2a6eb5",
    "HighlightedText": "#ffffff", "Link": "#5aa0e8",
}

# ── Warm Light ───────────────────────────────────────────────────
_WARM_LIGHT_QSS = _COMMON_QSS + """
QMainWindow, QDialog { background: #faf6f0; }
QMenuBar {
    background: #fff8f0; border-bottom: 1px solid #e0d4c4;
    padding: 2px;
}
QMenuBar::item:selected { background: #f0dcc0; }
QToolBar { background: #fff8f0; border-bottom: 1px solid #e0d4c4; }
QStatusBar { background: #f4ece0; border-top: 1px solid #e0d4c4; }
QTabBar::tab {
    background: #f0e8d8; border: 1px solid #d8ccb8;
    padding: 3px 10px; margin-right: 1px;
}
QTabBar::tab:selected { background: #fff8f0; border-bottom-color: #fff8f0; }
QTabBar::tab:hover { background: #f0dcc0; }
QPushButton {
    background: #faf4e8; border: 1px solid #c8bca8;
    padding: 3px 10px; border-radius: 3px;
}
QPushButton:hover  { background: #f0dcc0; border-color: #a0845a; }
QToolButton:hover { background: #f0dcc0; border-radius: 3px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #fffcf6; border: 1px solid #d0c4b0;
    border-radius: 2px; padding: 2px 4px;
}
QTreeWidget, QListWidget, QTableWidget {
    background: #fffcf6; alternate-background-color: #faf4ea;
    border: 1px solid #d8ccb8;
}
QHeaderView::section {
    background: #f4ece0; border: 1px solid #d8ccb8;
    padding: 2px 4px;
}
QLabel { color: #3a3020; }
"""

_WARM_LIGHT_PALETTE = {
    "Window": "#faf6f0", "WindowText": "#3a3020",
    "Base": "#fffcf6", "AlternateBase": "#faf4ea",
    "ToolTipBase": "#fff8e0", "ToolTipText": "#3a3020",
    "Text": "#3a3020", "Button": "#faf4e8",
    "ButtonText": "#3a3020", "Highlight": "#b8903a",
    "HighlightedText": "#ffffff", "Link": "#8a6a20",
}

# ── Theme registry ───────────────────────────────────────────────
THEMES = {
    "Light":      (_LIGHT_QSS,      _LIGHT_PALETTE),
    "Dark":       (_DARK_QSS,       _DARK_PALETTE),
    "Blue Dark":  (_BLUE_DARK_QSS,  _BLUE_DARK_PALETTE),
    "Warm Light": (_WARM_LIGHT_QSS, _WARM_LIGHT_PALETTE),
}


def _apply_palette(app, palette_dict=None):
    pd = palette_dict or _LIGHT_PALETTE
    pal = QPalette()
    _role_map = {
        "Window": QPalette.Window, "WindowText": QPalette.WindowText,
        "Base": QPalette.Base, "AlternateBase": QPalette.AlternateBase,
        "ToolTipBase": QPalette.ToolTipBase, "ToolTipText": QPalette.ToolTipText,
        "Text": QPalette.Text, "Button": QPalette.Button,
        "ButtonText": QPalette.ButtonText, "Highlight": QPalette.Highlight,
        "HighlightedText": QPalette.HighlightedText, "Link": QPalette.Link,
    }
    for key, role in _role_map.items():
        if key in pd:
            pal.setColor(role, QColor(pd[key]))
    app.setPalette(pal)


def apply_theme(app, name: str):
    """Switch the application theme at runtime."""
    if name not in THEMES:
        return
    qss, pal_dict = THEMES[name]
    _apply_palette(app, pal_dict)
    app.setStyleSheet(qss)


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
    apply_theme(app, "Light")

    icon = _make_app_icon()
    app.setWindowIcon(icon)

    from .mainwindow import MainWindow
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
