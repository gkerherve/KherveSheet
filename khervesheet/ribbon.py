"""Excel-style ribbon: a green File button, text tabs with a green
underline, labelled groups of large and small buttons, dialog launchers
in the group corners and a Quick Access toolbar.

The ribbon only arranges things the window already owns — QActions,
menus and a few widgets — so it holds no state of its own.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""
from __future__ import annotations

import re

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAction, QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QSizePolicy,
    QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

ACCENT = "#217346"          # Excel green
_LARGE = QSize(32, 32)
_SMALL = QSize(16, 16)
_BODY_H = 78                # group area height: three small rows

_QSS = """
QTabWidget#ExcelRibbon::pane {{
    border: none; border-top: 1px solid palette(midlight);
    background: palette(base);
}}
QTabWidget#ExcelRibbon > QTabBar {{ background: palette(window); }}
QTabWidget#ExcelRibbon > QTabBar::tab {{
    background: transparent; border: none;
    padding: 5px 11px 4px 11px; margin: 0 1px;
    border-bottom: 3px solid transparent;
}}
QTabWidget#ExcelRibbon > QTabBar::tab:hover {{
    background: palette(midlight);
}}
QTabWidget#ExcelRibbon > QTabBar::tab:selected {{
    color: {accent}; font-weight: bold;
    border-bottom: 3px solid {accent};
}}
QWidget#RibbonPage {{ background: palette(base); }}
QWidget#RibbonPage QToolButton {{
    border: 1px solid transparent; border-radius: 3px; padding: 1px 2px;
}}
QWidget#RibbonPage QToolButton:hover {{
    background: {hover}; border-color: {hover_border};
}}
QWidget#RibbonPage QToolButton:checked,
QWidget#RibbonPage QToolButton:pressed {{
    background: {down}; border-color: {down_border};
}}
QWidget#RibbonPage QToolButton[popupMode="1"] {{ padding-right: 10px; }}
QWidget#RibbonPage QToolButton::menu-button {{
    border: none; width: 10px;
}}
QWidget#RibbonPage QToolButton::menu-arrow,
QWidget#RibbonPage QToolButton::menu-indicator {{
    width: 7px; height: 7px;
}}
QWidget#RibbonPage QToolButton[popupMode="2"] {{ padding-right: 9px; }}
QLabel#RibbonCaption {{ color: palette(dark); font-size: 10px; }}
QToolButton#RibbonLauncher {{
    border: none; padding: 0; font-size: 9px; color: palette(dark);
}}
QToolButton#RibbonFile {{
    background: {accent}; color: white; border: none;
    padding: 4px 14px; font-weight: bold;
}}
QToolButton#RibbonFile:hover {{ background: {dark}; }}
QToolButton#RibbonFile::menu-indicator {{ image: none; }}
QFrame#RibbonSep {{ color: palette(midlight); }}
"""


def accent_color() -> str:
    """The theme's accent: every theme sets it as the Highlight colour."""
    from PyQt5.QtGui import QPalette
    from PyQt5.QtWidgets import QApplication
    return QApplication.palette().color(QPalette.Highlight).name()


def ribbon_qss(accent: str) -> str:
    from PyQt5.QtGui import QColor
    c = QColor(accent)

    def tint(alpha: float) -> str:
        return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"
    return _QSS.format(accent=accent, hover=tint(0.14),
                       hover_border=tint(0.35), down=tint(0.28),
                       down_border=tint(0.6), dark=c.darker(130).name())


def short(text: str) -> str:
    """Menu text without the & accelerator, shortcut or ellipsis."""
    t = re.sub(r"&(?=[^&\s])", "", text.split("\t")[0])
    return t.replace("&&", "&").rstrip(".…").strip()


def _shown(text: str) -> str:
    """Button text with a literal & kept (Qt reads & as a mnemonic)."""
    return text.replace("&", "&&")


def _label(b: QToolButton, action: QAction, label: str | None) -> None:
    """Set the button's label. The button re-reads the action's icon
    text whenever the action changes (its tooltip, checked state), so
    the label lives there too, with a literal & kept."""
    text = _shown(label or short(action.text()))
    action.setIconText(text)
    b.setText(text)


def _button(action: QAction, large: bool, text: bool,
            label: str | None = None) -> QToolButton:
    b = QToolButton()
    b.setDefaultAction(action)
    b.setFocusPolicy(Qt.NoFocus)
    b.setAutoRaise(True)
    menu = action.property("ribbon_menu")
    if menu is not None:
        b.setMenu(menu)
        # A command with a menu beside it (Paste ▾) or a menu only.
        b.setPopupMode(QToolButton.InstantPopup
                       if action.property("ribbon_menu_only")
                       else QToolButton.MenuButtonPopup)
    if large:
        b.setIconSize(_LARGE)
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setMinimumWidth(46)
        b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        _label(b, action, label)
    else:
        b.setIconSize(_SMALL)
        if text:
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            _label(b, action, label)
        else:
            b.setToolButtonStyle(Qt.ToolButtonIconOnly)
    tip = short(action.text())
    if action.shortcut().toString():
        tip += f" ({action.shortcut().toString()})"
    if not action.toolTip() or action.toolTip() == action.text():
        action.setToolTip(tip)
    return b


class RibbonTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("RibbonPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(_BODY_H + 21)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(2, 2, 2, 1)
        self._lay.setSpacing(0)
        self._lay.addStretch(1)

    def add_group(self, label: str, *, large=(), rows=(),
                  text: bool = True, launcher=None) -> None:
        """One labelled group: `large` items as tall buttons, then `rows`
        (each a list of items) stacked as small buttons — Excel's three
        rows. Items are QActions, (QAction, label) pairs or widgets.
        `launcher` is a callable behind the ↘ corner button."""
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(3, 0, 3, 0)
        v.setSpacing(0)
        body = QHBoxLayout()
        body.setSpacing(1)
        for it in large:
            body.addWidget(self._item(it, True, True))
        if rows:
            grid = QGridLayout()
            grid.setSpacing(1)
            grid.setContentsMargins(2, 0, 0, 0)
            for r, row in enumerate(rows):
                line = QHBoxLayout()
                line.setSpacing(1)
                for it in row:
                    line.addWidget(self._item(it, False, text))
                line.addStretch(1)
                grid.addLayout(line, r, 0)
            body.addLayout(grid)
        frame = QWidget()
        frame.setFixedHeight(_BODY_H)
        frame.setLayout(body)
        body.setContentsMargins(0, 0, 0, 0)
        v.addWidget(frame)
        foot = QHBoxLayout()
        foot.setContentsMargins(0, 0, 0, 0)
        cap = QLabel(label)
        cap.setObjectName("RibbonCaption")
        cap.setFixedHeight(15)
        cap.setAlignment(Qt.AlignHCenter)
        foot.addWidget(cap, 1)
        if launcher is not None:
            lb = QToolButton()
            lb.setObjectName("RibbonLauncher")
            lb.setText("↘")
            lb.setToolTip(f"{label} settings")
            lb.setFocusPolicy(Qt.NoFocus)
            lb.clicked.connect(launcher)
            foot.addWidget(lb, 0, Qt.AlignRight)
        v.addLayout(foot)
        self._lay.insertWidget(self._lay.count() - 1, box)
        sep = QFrame()
        sep.setObjectName("RibbonSep")
        sep.setFrameShape(QFrame.VLine)
        self._lay.insertWidget(self._lay.count() - 1, sep)

    @staticmethod
    def _item(it, large: bool, text: bool) -> QWidget:
        if isinstance(it, tuple):
            return _button(it[0], large, text, it[1])
        if isinstance(it, QAction):
            return _button(it, large, text)
        return it


class Ribbon(QTabWidget):
    """Tabs of groups. Double-click a tab to collapse the ribbon to its
    tab row, as Excel does; clicking a tab then shows it again."""
    collapsedChanged = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ExcelRibbon")
        self.setDocumentMode(True)
        self.apply_accent(accent_color())
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._collapsed = False
        self.tabBar().setDrawBase(False)
        self.tabBar().tabBarDoubleClicked.connect(
            lambda _i: self.set_collapsed(not self._collapsed))
        self.tabBar().tabBarClicked.connect(self._on_tab_clicked)
        self._apply_height()

    def apply_accent(self, accent: str) -> None:
        """Recolour the ribbon to the theme (tab underline, File button,
        hover tints)."""
        self.accent = accent
        self.setStyleSheet(ribbon_qss(accent))

    def add_tab(self, name: str) -> RibbonTab:
        tab = RibbonTab()
        self.addTab(tab, name)
        self._apply_height()
        return tab

    def showEvent(self, ev) -> None:
        # The tab row only knows its height once styled and shown.
        super().showEvent(ev)
        self._apply_height()

    def set_file_menu(self, menu: QMenu) -> QToolButton:
        """The green File button at the left of the tab row."""
        b = QToolButton()
        b.setObjectName("RibbonFile")
        b.setProperty("tip_key", "file")
        b.setText("File")
        b.setMenu(menu)
        b.setPopupMode(QToolButton.InstantPopup)
        b.setFocusPolicy(Qt.NoFocus)
        self.setCornerWidget(b, Qt.TopLeftCorner)
        return b

    def set_quick_access(self, items) -> None:
        """Always-visible small buttons at the right of the tab row."""
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(4, 0, 4, 0)
        h.setSpacing(0)
        for a in items:
            if a is None:
                sep = QFrame()
                sep.setObjectName("RibbonSep")
                sep.setFrameShape(QFrame.VLine)
                h.addWidget(sep)
            elif isinstance(a, QAction):
                b = _button(a, False, False)
                b.setStyleSheet("QToolButton { border: none; padding: 2px; }"
                                "QToolButton:hover { background: palette(midlight); }")
                h.addWidget(b)
            else:
                h.addWidget(a)
        self.setCornerWidget(w, Qt.TopRightCorner)

    # ── collapse ────────────────────────────────────────────────────
    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, on: bool) -> None:
        self._collapsed = bool(on)
        self._apply_height()
        self.collapsedChanged.emit(self._collapsed)

    def _on_tab_clicked(self, _i: int) -> None:
        if self._collapsed:
            self.set_collapsed(False)

    def _apply_height(self) -> None:
        bar = max(self.tabBar().sizeHint().height(),
                  self.tabBar().height(), 26)
        self.setFixedHeight(bar + (0 if self._collapsed else _BODY_H + 23))
