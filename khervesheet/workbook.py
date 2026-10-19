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


_SHEET_TABS_QSS = """
QTabWidget#SheetTabs > QTabBar { background: palette(window); }
QTabWidget#SheetTabs > QTabBar::tab {
    background: transparent; color: palette(text);
    padding: 2px 12px; margin: 0; min-width: 0;
    border: none; border-radius: 0;
    border-right: 1px solid palette(mid);
    font-weight: normal;
}
QTabWidget#SheetTabs > QTabBar::tab:hover:!selected {
    background: palette(midlight);
}
QTabWidget#SheetTabs > QTabBar::tab:selected {
    background: palette(base); color: #217346; font-weight: bold;
    border-bottom: 2px solid #217346;
}
QTabWidget#SheetTabs QToolButton { padding: 0; }
"""


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
        # Excel's sheet tabs: small, flat, no close button (Delete Sheet
        # is on the right-click menu), the active one white with a
        # green underline.
        self.tabs.setTabsClosable(False)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setObjectName("SheetTabs")
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setElideMode(Qt.ElideNone)
        self.tabs.setStyleSheet(_SHEET_TABS_QSS)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(
            self._tab_menu)

        # Bottom-left corner cluster:  ◀  ▶  +  ∨
        corner = QWidget()
        ch = QHBoxLayout(corner)
        ch.setContentsMargins(0, 0, 0, 0)
        ch.setSpacing(0)

        _BTN = 22

        def _mk(text, tip, fn):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setAutoRaise(True)
            b.setFixedSize(_BTN, _BTN)
            f = b.font()
            f.setPointSize(9)
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
        f.setPointSize(9)
        self._btn_list.setFont(f)
        self._btn_list.setPopupMode(QToolButton.InstantPopup)
        self._btn_list.clicked.connect(self._show_sheet_list)

        for b in (self._btn_prev, self._btn_next,
                  self._btn_add, self._btn_list):
            ch.addWidget(b)

        self.tabs.setCornerWidget(corner, Qt.BottomLeftCorner)
        v.addWidget(self.tabs)

        self._combined_tab = None

        # Cross-sheet formula support.
        self._active_formula_sheet = None  # sheet currently entering "="
        self._in_xref_refresh = False      # re-entrancy guard

        # Create default sheets
        for i in range(3):
            self.add_sheet(f"Sheet{i + 1}")
        self.ensure_layout_tabs()
        self.tabs.setCurrentIndex(0)
        self.tabs.currentChanged.connect(self._on_current_changed)

    # ── Publication layout tab (always pinned rightmost) ─────────────
    def ensure_layout_tabs(self):
        """Create the layout tab if missing and pin it last."""
        from .plot_layout import CombinedLayoutTab
        if (self._combined_tab is None
                or self.tabs.indexOf(self._combined_tab) < 0):
            self._combined_tab = CombinedLayoutTab(self)
            self.tabs.addTab(self._combined_tab, "Layout")
        self._pin_layout_tabs()

    def _pin_layout_tabs(self):
        """Move the layout tab to the far right and strip its close
        button so it cannot be deleted like a sheet."""
        from PyQt5.QtWidgets import QTabBar
        bar = self.tabs.tabBar()
        tab = self._combined_tab
        if tab is None:
            return
        idx = self.tabs.indexOf(tab)
        if idx < 0:
            return
        last = self.tabs.count() - 1
        if idx != last:
            bar.moveTab(idx, last)
            idx = self.tabs.indexOf(tab)
        bar.setTabButton(idx, QTabBar.RightSide, None)
        bar.setTabButton(idx, QTabBar.LeftSide, None)

    def _on_current_changed(self, idx):
        w = self.tabs.widget(idx)
        from .plot_layout import is_layout_tab
        if is_layout_tab(w):
            w.rebuild_from_workbook()

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
            idx = len(self.all_sheets()) + 1
            name = f"Sheet{idx}"
        # Insert before any layout tabs so they stay rightmost.
        self.tabs.addTab(s, name)
        self._pin_layout_tabs()
        self.tabs.setCurrentWidget(s)
        return s

    def current_sheet(self) -> Optional[SheetWidget]:
        w = self.tabs.currentWidget()
        if isinstance(w, SheetWidget):
            return w
        sheets = self.all_sheets()
        return sheets[0] if sheets else None

    def all_sheets(self) -> List[SheetWidget]:
        return [self.tabs.widget(i) for i in range(self.tabs.count())
                if isinstance(self.tabs.widget(i), SheetWidget)]

    def sheet_names(self) -> List[str]:
        return [self.tabs.tabText(i) for i in range(self.tabs.count())
                if isinstance(self.tabs.widget(i), SheetWidget)]

    # ── Cross-sheet formula support ──────────────────────────────────
    def sheet_by_name(self, name: str) -> Optional[SheetWidget]:
        """Find a sheet by its tab name (case-insensitive)."""
        if not name:
            return None
        target = name.strip().strip("'").lower()
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if (isinstance(w, SheetWidget)
                    and self.tabs.tabText(i).lower() == target):
                return w
        return None

    def name_of_sheet(self, sheet) -> str:
        """Tab name for a SheetWidget (empty string if not found)."""
        idx = self.tabs.indexOf(sheet)
        return self.tabs.tabText(idx) if idx >= 0 else ""

    def set_active_formula(self, sheet):
        self._active_formula_sheet = sheet

    def clear_active_formula(self, sheet):
        if self._active_formula_sheet is sheet:
            self._active_formula_sheet = None

    def refresh_cross_sheet(self):
        """Re-evaluate every cross-sheet formula across all sheets and
        cascade their local dependents.  Guarded against re-entrancy so
        the cascade can't loop back into another refresh."""
        if self._in_xref_refresh:
            return
        self._in_xref_refresh = True
        try:
            for s in self.all_sheets():
                cells = list(getattr(s, "_xref_cells", ()) or ())
                if not cells:
                    continue
                for (r, c) in cells:
                    s._reeval_formula_cell(r, c)
                s._recalc_from_seeds(cells)
        finally:
            self._in_xref_refresh = False

    def _close_tab(self, idx: int):
        if not isinstance(self.tabs.widget(idx), SheetWidget):
            return
        if len(self.all_sheets()) <= 1:
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
        if idx >= 0 and isinstance(self.tabs.widget(idx), SheetWidget):
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
        self._pin_layout_tabs()
        self.tabs.setCurrentIndex(self.tabs.indexOf(widget))

    # ── Proxy to current sheet ───────────────────────────────────────
    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        try:
            tabs = object.__getattribute__(self, "tabs")
        except AttributeError as exc:
            raise AttributeError(name) from exc
        sheet = tabs.currentWidget()
        if not isinstance(sheet, SheetWidget):
            sheet = self.current_sheet()
        if sheet is None:
            raise AttributeError(name)
        return getattr(sheet, name)
