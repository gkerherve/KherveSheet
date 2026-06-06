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
        _install_recursion_watchdog()
    except Exception:
        try:
            faulthandler.enable()
        except Exception:
            pass


def _install_recursion_watchdog(threshold=550, interval=0.05):
    """Capture *and* break a runaway recursion on the main thread.

    A recursion that crosses the Python↔C boundary (Qt signals, numpy,
    matplotlib) can overflow the *native* stack at well under Python's
    own recursion limit, aborting the process with
    STATUS_STACK_BUFFER_OVERRUN (0xC0000409) via Windows ``__fastfail`` —
    which bypasses ``faulthandler`` and leaves no traceback.

    A sampling watchdog (a) dumps the offending stack to the crash log so
    the recursive cycle is identifiable, and (b) injects an exception
    into the main thread to unwind it before the native stack overflows,
    turning a hard crash into a caught, logged error.  The injection uses
    the same ``PyThreadState_SetAsyncExc`` mechanism the =PY timeout relies
    on; the exception propagates up through the recursive call chain and
    is caught by the broad ``except`` guards in the recalc / formula code.
    """
    import ctypes
    import threading
    import time

    main_id = threading.get_ident()  # called on the main thread at startup

    def _depth(frame):
        n = 0
        while frame is not None:
            n += 1
            frame = frame.f_back
        return n

    armed = [True]

    def _watch():
        while True:
            time.sleep(interval)
            try:
                frame = sys._current_frames().get(main_id)
                if frame is None:
                    continue
                d = _depth(frame)
                if d >= threshold and armed[0]:
                    armed[0] = False  # one episode per excursion
                    if _CRASH_LOG_FILE is not None:
                        _CRASH_LOG_FILE.write(
                            "\n=== Recursion watchdog: main-thread "
                            f"stack depth {d} — breaking runaway ===\n")
                        _CRASH_LOG_FILE.flush()
                        # C-level atomic snapshot of all threads — robust
                        # against the live main thread mutating its frames.
                        faulthandler.dump_traceback(
                            file=_CRASH_LOG_FILE, all_threads=True)
                        _CRASH_LOG_FILE.write("=== end watchdog dump ===\n")
                        _CRASH_LOG_FILE.flush()
                    # Unwind the runaway before the native stack overflows.
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(
                        ctypes.c_long(main_id),
                        ctypes.py_object(RecursionError))
                elif d < threshold // 2:
                    armed[0] = True  # re-arm once depth is healthy again
            except Exception:
                pass

    threading.Thread(target=_watch, name="recursion-watchdog",
                     daemon=True).start()


def _make_app_icon():
    """Build the app icon via the icons module (qtawesome themed)."""
    from .icons import init_app_icon
    return init_app_icon()


# ── Shared QSS fragments ─────────────────────────────────────────
_COMMON_QSS = """
QToolBar { padding: 0px; margin: 0px; spacing: 1px; }
/* Give tool buttons a full QSS box (transparent border/background) in
   EVERY state. Without a base box, Qt draws the button natively when
   idle but switches to the stylesheet renderer on :hover — that path
   change resizes the (HiDPI) icon, so it visibly grows on hover. A
   consistent box keeps the icon one fixed size in all states. */
QToolButton {
    padding: 1px; margin: 0px;
    background: transparent;
    border: 1px solid transparent; border-radius: 3px;
}
QToolButton:hover { border: 1px solid transparent; }
QToolButton:pressed { border: 1px solid transparent; }
QToolButton:checked { border: 1px solid transparent; }
/* Flatten the drop-down (menu) half of MenuButtonPopup tool buttons so it
   doesn't draw its own raised/bevelled frame on hover. */
QToolButton::menu-button { border: none; background: transparent; width: 14px; }
QToolButton::menu-arrow { width: 8px; height: 8px; }
QSpinBox, QDoubleSpinBox { min-height: 22px; }
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    min-width: 18px; min-height: 10px;
}
QToolBar QComboBox, QToolBar QFontComboBox {
    border: 1px solid palette(mid);
    border-radius: 4px;
    padding: 3px 6px;
    min-height: 20px;
}
QToolBar QComboBox:hover, QToolBar QFontComboBox:hover {
    border-color: palette(highlight);
}
/* Do NOT style ::drop-down without also supplying a ::down-arrow image:
   styling the drop-down subcontrol turns off Qt's native rendering and
   the dropdown arrow disappears. We rely on the native arrow instead. */
#layoutToolStrip {
    background: palette(button);
    border-right: 1px solid palette(mid);
}
#layoutFlyout {
    background: palette(base);
    border: 1px solid palette(mid);
    border-radius: 4px;
}
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
QTabWidget::pane {
    border-top: 2px solid #3a78b4;
    background: #ffffff;
}
QTabBar::tab {
    background: #e9ecef;
    color: #707680;
    padding: 7px 20px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 2px;
    border: 1px solid transparent;
    border-bottom: none;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #202329;
    border: 1px solid #3a78b4;
    border-bottom: 2px solid #ffffff;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background: #d8e4f0;
    color: #202329;
}
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
QTabWidget::pane {
    border-top: 2px solid #5588bb;
    background: #1e1e2e;
}
QTabBar::tab {
    background: #2a2a3c; color: #909090;
    padding: 7px 20px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 2px;
    border: 1px solid transparent;
    border-bottom: none;
}
QTabBar::tab:selected {
    background: #1e1e2e; color: #ffffff;
    border: 1px solid #5588bb;
    border-bottom: 2px solid #1e1e2e;
    font-weight: bold;
}
QTabBar::tab:hover:!selected { background: #35354a; color: #e0e0e0; }
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
QTabWidget::pane {
    border-top: 2px solid #2a6eb5;
    background: #1a2332;
}
QTabBar::tab {
    background: #1f2b3d; color: #a0b0c0;
    padding: 7px 20px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 2px;
    border: 1px solid transparent;
    border-bottom: none;
}
QTabBar::tab:selected {
    background: #1a2332; color: #ffffff;
    border: 1px solid #2a6eb5;
    border-bottom: 2px solid #1a2332;
    font-weight: bold;
}
QTabBar::tab:hover:!selected { background: #253550; color: #d0d8e0; }
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
QTabWidget::pane {
    border-top: 2px solid #b8903a;
    background: #fff8f0;
}
QTabBar::tab {
    background: #f0e8d8; color: #8a7a60;
    padding: 7px 20px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 2px;
    border: 1px solid transparent;
    border-bottom: none;
}
QTabBar::tab:selected {
    background: #fff8f0; color: #3a3020;
    border: 1px solid #b8903a;
    border-bottom: 2px solid #fff8f0;
    font-weight: bold;
}
QTabBar::tab:hover:!selected { background: #f0dcc0; color: #3a3020; }
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
    background: #ffffff; alternate-background-color: #f6f6f8;
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
    "Base": "#ffffff", "AlternateBase": "#f6f6f8",
    "ToolTipBase": "#fff8e0", "ToolTipText": "#3a3020",
    "Text": "#3a3020", "Button": "#faf4e8",
    "ButtonText": "#3a3020", "Highlight": "#b8903a",
    "HighlightedText": "#ffffff", "Link": "#8a6a20",
}

# ── Quick theme generator ────────────────────────────────────────

def _gen_theme(bg, bg2, fg, fg2, accent, border, base, alt_base,
               btn, btn_hover, menu_sel, link, is_dark=False):
    """Generate (QSS, palette) from a compact colour spec.

    Light themes always get a WHITE data grid with a neutral zebra —
    only the chrome (menus, toolbars, tabs, headers) carries the theme
    tint. Dark themes keep their darker *base* so cells stay legible.
    """
    if not is_dark:
        base = "#ffffff"
        alt_base = "#f6f6f8"
    qss = _COMMON_QSS + f"""
QMainWindow, QDialog {{ background: {bg}; }}
QMenuBar {{
    background: {bg2}; color: {fg};
    border-bottom: 1px solid {border}; padding: 2px;
}}
QMenuBar::item:selected {{ background: {menu_sel}; }}
QMenu {{ background: {bg2}; color: {fg}; border: 1px solid {border}; }}
QMenu::item:selected {{ background: {menu_sel}; }}
QToolBar {{ background: {bg2}; border-bottom: 1px solid {border}; }}
QStatusBar {{ background: {alt_base}; color: {fg2};
    border-top: 1px solid {border}; }}
QTabWidget::pane {{
    border-top: 2px solid {accent};
    background: {bg};
}}
QTabBar::tab {{
    background: {alt_base}; color: {fg2};
    padding: 7px 20px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 2px;
    border: 1px solid transparent;
    border-bottom: none;
}}
QTabBar::tab:selected {{
    background: {bg}; color: {fg};
    border: 1px solid {accent};
    border-bottom: 2px solid {bg};
    font-weight: bold;
}}
QTabBar::tab:hover:!selected {{ background: {btn_hover}; color: {fg}; }}
QPushButton {{
    background: {btn}; color: {fg};
    border: 1px solid {border}; padding: 3px 10px; border-radius: 3px;
}}
QPushButton:hover  {{ background: {btn_hover}; border-color: {accent}; }}
QPushButton:pressed {{ background: {menu_sel}; }}
QToolButton {{ color: {fg}; }}
QToolButton:hover {{ background: {btn_hover}; border-radius: 3px; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {base}; color: {fg};
    border: 1px solid {border}; border-radius: 2px; padding: 2px 4px;
}}
QComboBox QAbstractItemView {{ background: {base}; color: {fg}; }}
QTreeWidget, QListWidget, QTableWidget {{
    background: {base}; color: {fg};
    alternate-background-color: {alt_base};
    border: 1px solid {border}; gridline-color: {border};
}}
QHeaderView::section {{
    background: {bg2}; color: {fg2};
    border: 1px solid {border}; padding: 2px 4px;
}}
QLabel {{ color: {fg}; }}
QScrollBar:vertical, QScrollBar:horizontal {{ background: {bg2}; }}
QScrollBar::handle {{ background: {border}; border-radius: 3px; }}
QScrollBar::handle:hover {{ background: {accent}; }}
"""
    pal = {
        "Window": bg, "WindowText": fg,
        "Base": base, "AlternateBase": alt_base,
        "ToolTipBase": btn, "ToolTipText": fg,
        "Text": fg, "Button": btn,
        "ButtonText": fg, "Highlight": accent,
        "HighlightedText": "#ffffff", "Link": link,
    }
    return qss, pal


# ── Theme registry ───────────────────────────────────────────────
THEMES = {
    "Light":      (_LIGHT_QSS,      _LIGHT_PALETTE),
    "Dark":       (_DARK_QSS,       _DARK_PALETTE),
    "Blue Dark":  (_BLUE_DARK_QSS,  _BLUE_DARK_PALETTE),
    "Warm Light": (_WARM_LIGHT_QSS, _WARM_LIGHT_PALETTE),

    # ── Additional light themes ─────────────────────────────────
    "Arctic": _gen_theme(
        "#f0f5fa", "#ffffff", "#1a2a3a", "#5a6a7a", "#2a8ad0",
        "#c8d4e0", "#ffffff", "#eaf0f6", "#f5f8fc",
        "#dce8f4", "#bcd4f0", "#1a6fbb"),
    "Mint": _gen_theme(
        "#f0faf5", "#f8fffc", "#1a3a2a", "#5a7a6a", "#28a060",
        "#c0dcc8", "#ffffff", "#e8f5ee", "#f2faf6",
        "#d0f0dc", "#b0e0c4", "#1a8a50"),
    "Rose": _gen_theme(
        "#faf0f3", "#fff8fa", "#3a1a22", "#7a5a62", "#c0506a",
        "#e0c0ca", "#fff5f8", "#f8eaef", "#fcf2f5",
        "#f4d8e0", "#e8bcc8", "#a83050"),
    "Lavender": _gen_theme(
        "#f4f0fa", "#faf8ff", "#2a1a3a", "#6a5a7a", "#7a50b0",
        "#d0c0e0", "#fdf8ff", "#eeE8f5", "#f6f2fa",
        "#e4d8f0", "#d0c0e4", "#6a40a0"),
    "Peach": _gen_theme(
        "#fdf6f0", "#fffaf5", "#3a2a1a", "#7a6a5a", "#d08040",
        "#e4d0b8", "#fffcf8", "#f8f0e8", "#fdf8f2",
        "#f4e0cc", "#e8ccb0", "#b06820"),
    "Sage": _gen_theme(
        "#f2f5f0", "#f8faf6", "#2a3020", "#5a6450", "#5a8a40",
        "#c8d4c0", "#fafcf8", "#eef2ea", "#f4f8f2",
        "#dce8d4", "#c0d8b4", "#488830"),
    "Sky": _gen_theme(
        "#f0f8ff", "#f8fcff", "#1a2838", "#5a6878", "#3090d0",
        "#c0d8f0", "#ffffff", "#eaf4ff", "#f4faff",
        "#d4e8fa", "#b8d8f4", "#2070b0"),
    "Sand": _gen_theme(
        "#f8f4ee", "#fffcf5", "#38301a", "#7a7060", "#b89040",
        "#dcd0b8", "#fffcf4", "#f4eee4", "#faf6ee",
        "#f0e0c8", "#e0ccaa", "#987020"),
    "Coral": _gen_theme(
        "#fef5f2", "#fff9f7", "#3a2020", "#7a5050", "#e06050",
        "#e8c8c0", "#fff8f5", "#faefeb", "#fcf5f2",
        "#f4d4cc", "#e8b8b0", "#c04030"),

    # ── Green light themes (white grid, green chrome) ───────────
    "Emerald": _gen_theme(
        "#eef7f1", "#d4f0df", "#0d2a1d", "#2e5a44", "#0a9d5b",
        "#a8dcbd", "#ffffff", "#f6f6f8", "#e2f3ea",
        "#bfe9cf", "#bfe9cf", "#0a7d49"),
    "Fern": _gen_theme(
        "#f1f7ec", "#e0f0d0", "#1f3215", "#42603a", "#4f9e2e",
        "#bcd8a8", "#ffffff", "#f6f6f8", "#e8f3dd",
        "#d3ebbd", "#d3ebbd", "#3d7e22"),
    "Pistachio": _gen_theme(
        "#f3f8ec", "#e8f2d4", "#2a3318", "#4e5c34", "#86b73a",
        "#cce0a8", "#ffffff", "#f6f6f8", "#ecf4dc",
        "#dcecbc", "#dcecbc", "#6e9a28"),
    "Seafoam": _gen_theme(
        "#ecf7f3", "#d2f0e8", "#0e2e28", "#36605a", "#16a98a",
        "#a8ddd0", "#ffffff", "#f6f6f8", "#dff3ee",
        "#bce8de", "#bce8de", "#0e8a70"),
    "Olive": _gen_theme(
        "#f5f5ec", "#e8e8cc", "#2e2e16", "#565636", "#8a8a30",
        "#cccca0", "#ffffff", "#f6f6f8", "#eeeedc",
        "#dcdcb8", "#dcdcb8", "#6e6e22"),
    "Teal": _gen_theme(
        "#ecf6f7", "#d2eeef", "#0e2a2e", "#365e62", "#179a9a",
        "#a8dadc", "#ffffff", "#f6f6f8", "#def2f3",
        "#bce6e8", "#bce6e8", "#0e7d7d"),
    "Jade": _gen_theme(
        "#eef7f2", "#d8f0e2", "#122e22", "#3a5e4e", "#2aa66f",
        "#b0ddc6", "#ffffff", "#f6f6f8", "#e2f3ea",
        "#c2e8d2", "#c2e8d2", "#1e8456"),

    # ── Additional dark themes ──────────────────────────────────
    "Pine": _gen_theme(
        "#16241c", "#1e2e24", "#c8d8cc", "#84a890", "#3aa860",
        "#2e4636", "#101c16", "#1a281e", "#26362c",
        "#34483a", "#2a5038", "#5ec882", is_dark=True),
    "Charcoal": _gen_theme(
        "#222226", "#2c2c32", "#d8d8dc", "#909098", "#5898d0",
        "#3c3c44", "#1e1e22", "#282830", "#343438",
        "#40404a", "#3a6090", "#70b0e8", is_dark=True),
    "Midnight": _gen_theme(
        "#0e1420", "#141c2a", "#c8d0e0", "#8090a8", "#4488cc",
        "#202838", "#0a1018", "#121a28", "#1c2838",
        "#283850", "#2a5588", "#5ea0e0", is_dark=True),
    "Dracula": _gen_theme(
        "#282a36", "#343746", "#f8f8f2", "#a0a0b0", "#bd93f9",
        "#44475a", "#21222c", "#2c2e3a", "#3a3d50",
        "#44475a", "#6272a4", "#8be9fd", is_dark=True),
    "Monokai": _gen_theme(
        "#272822", "#3e3d32", "#f8f8f2", "#a0a090", "#a6e22e",
        "#49483e", "#1e1f1a", "#2e2f28", "#3a3b32",
        "#49483e", "#66d9ef", "#fd971f", is_dark=True),
    "Nord": _gen_theme(
        "#2e3440", "#3b4252", "#d8dee9", "#8090a0", "#88c0d0",
        "#434c5e", "#272d38", "#323845", "#434c5e",
        "#4c566a", "#5e81ac", "#81a1c1", is_dark=True),
    "Solarized Dark": _gen_theme(
        "#002b36", "#073642", "#839496", "#657b83", "#268bd2",
        "#2a4a55", "#001e28", "#073642", "#0a3845",
        "#1a4a5a", "#2aa198", "#6c71c4", is_dark=True),
    "Solarized Light": _gen_theme(
        "#fdf6e3", "#eee8d5", "#586e75", "#839496", "#268bd2",
        "#d3c6a6", "#fdf6e3", "#f5efd7", "#f0e8cc",
        "#e8dcc0", "#ccd6a0", "#6c71c4"),
    "Gruvbox Dark": _gen_theme(
        "#282828", "#3c3836", "#ebdbb2", "#a89984", "#d79921",
        "#504945", "#1d2021", "#32302f", "#3c3836",
        "#504945", "#83a598", "#fe8019", is_dark=True),
    "Gruvbox Light": _gen_theme(
        "#fbf1c7", "#f2e5bc", "#3c3836", "#7c6f64", "#d79921",
        "#d5c4a1", "#fbf1c7", "#f2e5bc", "#ebdbb2",
        "#d5c4a1", "#b8bb26", "#af3a03"),
    "Forest": _gen_theme(
        "#1a2418", "#222e20", "#c8d8c0", "#80a070", "#50a850",
        "#304830", "#141e14", "#1e2a1c", "#2a3828",
        "#384838", "#508848", "#70c870", is_dark=True),
    "Ocean": _gen_theme(
        "#0c1a28", "#142232", "#b0c8e0", "#7090b0", "#3098d0",
        "#1c3048", "#081420", "#10202e", "#1c3040",
        "#244058", "#2878a8", "#50b8f0", is_dark=True),
    "Plum": _gen_theme(
        "#1e1628", "#281e34", "#d0c0e0", "#9080a8", "#a060c8",
        "#382850", "#161020", "#201828", "#302240",
        "#402e58", "#7848a0", "#c080f0", is_dark=True),
    "Copper": _gen_theme(
        "#2a2018", "#342820", "#e0d0c0", "#a89080", "#c88040",
        "#483828", "#201810", "#2e221a", "#3c3028",
        "#504038", "#a86828", "#e0a050", is_dark=True),
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
    from PyQt5.QtCore import QSettings
    settings = QSettings("KherveSheet", "KherveSheet")
    saved_theme = settings.value("theme", "Emerald")
    if saved_theme not in THEMES:
        saved_theme = "Emerald"
    apply_theme(app, saved_theme)

    icon = _make_app_icon()
    app.setWindowIcon(icon)

    from .mainwindow import MainWindow
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
