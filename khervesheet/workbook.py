"""WorkbookWidget — QTabWidget managing multiple SheetWidgets.

Bottom tab bar with navigation cluster, double-click rename,
right-click context menu.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from typing import List, Optional

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QToolButton,
    QMenu, QInputDialog, QMessageBox, QTableWidgetItem,
)

from .sheet import SheetWidget


class _RenameableTabBar(QTabWidget):
    """QTabWidget that renames tabs on double-click."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabBarDoubleClicked.connect(self._on_double_click)

    def _on_double_click(self, idx):
        if idx < 0:
            return
        cur = self.tabText(idx)
        from PyQt5.QtWidgets import QInputDialog
        new, ok = QInputDialog.getText(
            self, "Rename Sheet", "Name:", text=cur)
        if ok and new.strip():
            self.setTabText(idx, new.strip())


class WorkbookWidget(QWidget):
    """Container for multiple SheetWidgets with Excel-style bottom tabs."""

    _counter = 0

    def __init__(self, title: Optional[str] = None):
        super().__init__()
        WorkbookWidget._counter += 1
        self.title = title or f"Workbook{WorkbookWidget._counter}"
        self.file_path: Optional[str] = None

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self.tabs = _RenameableTabBar()
        self.tabs.setTabPosition(QTabWidget.South)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(
            self._tab_menu)

        # Bottom-left corner cluster:  ◀  ▶  +  ∨
        corner = QWidget()
        ch = QHBoxLayout(corner)
        ch.setContentsMargins(0, 0, 0, 0)
        ch.setSpacing(0)

        _BTN = 32

        def _mk(text, tip, fn):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setAutoRaise(True)
            b.setFixedSize(_BTN, _BTN)
            f = b.font()
            f.setPointSize(12)
            b.setFont(f)
            b.clicked.connect(fn)
            return b

        self._btn_prev = _mk("◀", "Previous sheet",
                              self._goto_prev_sheet)
        self._btn_next = _mk("▶", "Next sheet",
                              self._goto_next_sheet)
        self._btn_add = _mk("+", "Add sheet",
                             lambda: self.add_sheet())
        self._btn_list = QToolButton()
        self._btn_list.setText("∨")
        self._btn_list.setToolTip("Show all sheets")
        self._btn_list.setAutoRaise(True)
        self._btn_list.setFixedSize(_BTN, _BTN)
        f = self._btn_list.font()
        f.setPointSize(12)
        self._btn_list.setFont(f)
        self._btn_list.setPopupMode(QToolButton.InstantPopup)
        self._btn_list.clicked.connect(self._show_sheet_list)

        for b in (self._btn_prev, self._btn_next,
                  self._btn_add, self._btn_list):
            ch.addWidget(b)

        self.tabs.setCornerWidget(corner, Qt.BottomLeftCorner)
        v.addWidget(self.tabs)

        # Create default sheets
        for i in range(3):
            self.add_sheet(f"Sheet{i + 1}")
        self.tabs.setCurrentIndex(0)

    # ── Navigation ───────────────────────────────────────────────────
    def _goto_prev_sheet(self):
        i = self.tabs.currentIndex()
        if i > 0:
            self.tabs.setCurrentIndex(i - 1)

    def _goto_next_sheet(self):
        i = self.tabs.currentIndex()
        if i < self.tabs.count() - 1:
            self.tabs.setCurrentIndex(i + 1)

    def _show_sheet_list(self):
        menu = QMenu(self)
        cur = self.tabs.currentIndex()
        for i in range(self.tabs.count()):
            act = menu.addAction(self.tabs.tabText(i))
            act.setCheckable(True)
            act.setChecked(i == cur)
            act.triggered.connect(
                lambda _=False, idx=i: self.tabs.setCurrentIndex(idx))
        menu.exec_(self._btn_list.mapToGlobal(
            self._btn_list.rect().bottomLeft()))

    # ── Sheet management ─────────────────────────────────────────────
    def add_sheet(self, name: Optional[str] = None) -> SheetWidget:
        s = SheetWidget()
        if not name:
            idx = self.tabs.count() + 1
            name = f"Sheet{idx}"
        self.tabs.addTab(s, name)
        self.tabs.setCurrentWidget(s)
        return s

    def current_sheet(self) -> Optional[SheetWidget]:
        return self.tabs.currentWidget() if self.tabs.count() else None

    def all_sheets(self) -> List[SheetWidget]:
        return [self.tabs.widget(i) for i in range(self.tabs.count())]

    def sheet_names(self) -> List[str]:
        return [self.tabs.tabText(i) for i in range(self.tabs.count())]

    def _close_tab(self, idx: int):
        if self.tabs.count() <= 1:
            return
        if QMessageBox.question(
                self, "Delete Sheet",
                f"Delete '{self.tabs.tabText(idx)}'?") \
                != QMessageBox.Yes:
            return
        w = self.tabs.widget(idx)
        self.tabs.removeTab(idx)
        w.deleteLater()

    def _tab_menu(self, pos: QPoint):
        bar = self.tabs.tabBar()
        idx = bar.tabAt(pos)
        menu = QMenu(self)
        menu.addAction("New Sheet", lambda: self.add_sheet())
        if idx >= 0:
            menu.addAction("Rename Sheet…",
                           lambda: self._rename_tab(idx))
            if self.tabs.count() > 1:
                menu.addAction("Delete Sheet",
                               lambda: self._close_tab(idx))
            menu.addSeparator()
            menu.addAction("Duplicate Sheet",
                           lambda: self._duplicate_tab(idx))
            menu.addSeparator()
            if idx > 0:
                menu.addAction("Move Left",
                               lambda: self._move_tab(idx, idx - 1))
            if idx < self.tabs.count() - 1:
                menu.addAction("Move Right",
                               lambda: self._move_tab(idx, idx + 1))
        menu.exec_(bar.mapToGlobal(pos))

    def _rename_tab(self, idx: int):
        cur = self.tabs.tabText(idx)
        new, ok = QInputDialog.getText(
            self, "Rename Sheet", "Name:", text=cur)
        if ok and new.strip():
            self.tabs.setTabText(idx, new.strip())

    def _duplicate_tab(self, idx: int):
        src = self.tabs.widget(idx)
        if not isinstance(src, SheetWidget):
            return
        name = self.tabs.tabText(idx) + " copy"
        s = self.add_sheet(name)
        s.table.setColumnCount(src.column_count())
        s.table.setRowCount(src.row_count())
        s._refresh_headers()
        s.table.blockSignals(True)
        for r in range(src.row_count()):
            for c in range(src.column_count()):
                it = src.table.item(r, c)
                if it:
                    s.table.setItem(r, c, QTableWidgetItem(it.text()))
        s.table.blockSignals(False)
        # Copy designations
        s._col_designations = dict(src._col_designations)

    def _move_tab(self, from_idx: int, to_idx: int):
        text = self.tabs.tabText(from_idx)
        widget = self.tabs.widget(from_idx)
        self.tabs.removeTab(from_idx)
        self.tabs.insertTab(to_idx, widget, text)
        self.tabs.setCurrentIndex(to_idx)

    # ── Proxy to current sheet ───────────────────────────────────────
    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        try:
            tabs = object.__getattribute__(self, "tabs")
        except AttributeError as exc:
            raise AttributeError(name) from exc
        sheet = tabs.currentWidget()
        if sheet is None:
            raise AttributeError(name)
        return getattr(sheet, name)
