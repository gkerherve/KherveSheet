"""SheetWidget — a single spreadsheet grid tab.

Excel-style grid with A-Z/AA-AZ column headers, 1-based row numbers,
a formula bar, fill handle, and number formatting.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from typing import List, Optional

import numpy as np

from PyQt5.QtCore import Qt, QEvent, QRect, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QBrush
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QMenu, QInputDialog, QLineEdit, QLabel, QAbstractItemView,
    QHeaderView, QStyledItemDelegate, QApplication,
    QTableWidgetSelectionRange,
)


# ── Number format constants ──────────────────────────────────────────
NUMBER_FORMATS = [
    "General",
    "0",
    "0.0",
    "0.00",
    "0.000",
    "0.0000",
    "Scientific",
    "Date",
    "Time",
    "Text",
]

# ── Column letter helpers ────────────────────────────────────────────
def col_index_to_letter(idx: int) -> str:
    """0 → A, 1 → B, … 25 → Z, 26 → AA, 27 → AB, …"""
    result = ""
    while True:
        result = chr(ord('A') + idx % 26) + result
        idx = idx // 26 - 1
        if idx < 0:
            break
    return result


def letter_to_col_index(letters: str) -> int:
    """A → 0, B → 1, … Z → 25, AA → 26, AB → 27, …"""
    result = 0
    for ch in letters.upper():
        result = result * 26 + (ord(ch) - ord('A') + 1)
    return result - 1


# ── Cell format storage ──────────────────────────────────────────────
def _format_value(raw: str, fmt: str) -> str:
    """Display-format a raw cell value according to the format string."""
    if fmt == "General" or fmt == "Text" or not raw:
        return raw
    try:
        val = float(raw)
    except (ValueError, TypeError):
        return raw
    if fmt == "0":
        return f"{val:.0f}"
    elif fmt == "0.0":
        return f"{val:.1f}"
    elif fmt == "0.00":
        return f"{val:.2f}"
    elif fmt == "0.000":
        return f"{val:.3f}"
    elif fmt == "0.0000":
        return f"{val:.4f}"
    elif fmt == "Scientific":
        return f"{val:.4e}"
    return raw


# ── Undo command for cell edits ──────────────────────────────────────
from PyQt5.QtWidgets import QUndoCommand


class CellEditCmd(QUndoCommand):
    """Single-cell text edit on a SheetWidget."""

    def __init__(self, sheet, row, col, old_text, new_text):
        label = f"Edit {col_index_to_letter(col)}{row + 1}"
        super().__init__(label)
        self.sheet = sheet
        self.row = row
        self.col = col
        self.old = old_text
        self.new = new_text

    def undo(self):
        self.sheet._set_cell_quiet(self.row, self.col, self.old)

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            self.sheet._shadow[(self.row, self.col)] = self.new
            return
        self.sheet._set_cell_quiet(self.row, self.col, self.new)


class BulkCellEditCmd(QUndoCommand):
    """Batch of cell edits pushed as a single undo step."""

    def __init__(self, sheet, changes, label="Bulk edit"):
        super().__init__(label)
        self.sheet = sheet
        self.changes = changes  # [(row, col, old, new), ...]

    def undo(self):
        self.sheet.table.blockSignals(True)
        for row, col, old, _new in reversed(self.changes):
            self.sheet._set_cell_quiet(row, col, old)
        self.sheet.table.blockSignals(False)

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            for row, col, _old, new in self.changes:
                self.sheet._shadow[(row, col)] = new
            return
        self.sheet.table.blockSignals(True)
        for row, col, _old, new in self.changes:
            self.sheet._set_cell_quiet(row, col, new)
        self.sheet.table.blockSignals(False)


# ── SheetWidget ──────────────────────────────────────────────────────
class SheetWidget(QWidget):
    """A single Excel-style spreadsheet grid."""

    data_changed = pyqtSignal(int)  # emits column index on data change

    def __init__(self, rows: int = 1000, cols: int = 26):
        super().__init__()
        self._undo_stack = None  # set by MainWindow after construction
        self._default_format = "General"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Formula bar ──────────────────────────────────────────────
        fbar_widget = QWidget()
        fbar = QHBoxLayout(fbar_widget)
        fbar.setContentsMargins(4, 2, 4, 2)
        fbar.setSpacing(4)

        cell_lbl = QLabel("Cell:")
        cell_lbl.setMinimumWidth(28)
        self._cell_ref_label = QLabel("")
        self._cell_ref_label.setMinimumWidth(60)
        self._cell_ref_label.setStyleSheet(
            "background:#fafafa; border:1px solid #b8bcc3; "
            "padding:1px 4px;")
        fx_lbl = QLabel(" = ")
        fx_lbl.setStyleSheet("color:#3a78b4; font-weight:bold;")
        self._formula_bar = QLineEdit()
        self._formula_bar.setPlaceholderText(
            "Value or =formula  (e.g. =SUM(A1:A10), =B1+C1)")
        self._formula_bar.returnPressed.connect(self._apply_formula_bar)

        fbar.addWidget(cell_lbl)
        fbar.addWidget(self._cell_ref_label)
        fbar.addWidget(fx_lbl)
        fbar.addWidget(self._formula_bar, stretch=1)
        layout.addWidget(fbar_widget)

        # ── Table ────────────────────────────────────────────────────
        self.table = QTableWidget(rows, cols)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.table.setFont(QFont("Segoe UI", 9))
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.verticalHeader().setMinimumSectionSize(16)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.horizontalHeader().setDefaultSectionSize(80)
        self.table.horizontalHeader().setMinimumSectionSize(40)
        self.table.setShowGrid(True)

        # Column and row headers
        self._refresh_headers()

        # Context menus
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setContextMenuPolicy(
            Qt.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested.connect(
            self._header_menu)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._cell_menu)

        layout.addWidget(self.table)

        # ── Internal state ───────────────────────────────────────────
        self._shadow: dict = {}          # (row, col) → last-known text
        self._cell_formulas: dict = {}   # (row, col) → "=formula"
        self._col_formats: dict = {}     # col → format string
        self._col_designations: dict = {}  # col → "X" or "Y"

        # Signals
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.currentCellChanged.connect(self._on_current_cell_changed)

        # ── Drag-fill state ──────────────────────────────────────────
        self._fill_dragging = False
        self._fill_anchor_range = None
        self._fill_end_row = None
        self.table.viewport().setMouseTracking(True)
        self.table.viewport().installEventFilter(self)

    # ── Public API ───────────────────────────────────────────────────
    def column_count(self) -> int:
        return self.table.columnCount()

    def row_count(self) -> int:
        return self.table.rowCount()

    def cell_text(self, row: int, col: int) -> str:
        it = self.table.item(row, col)
        return it.text() if it else ""

    def numeric_column(self, col: int) -> np.ndarray:
        """Return column data as a float array (NaN for non-numeric)."""
        vals = []
        for r in range(self.row_count()):
            it = self.table.item(r, col)
            if it:
                try:
                    vals.append(float(it.text()))
                except (ValueError, TypeError):
                    vals.append(np.nan)
            else:
                vals.append(np.nan)
        return np.array(vals)

    def set_designation(self, col: int, desig: str):
        self._col_designations[col] = desig

    def get_designation(self, col: int) -> str:
        return self._col_designations.get(col, "Y" if col > 0 else "X")

    def column_display_name(self, col: int) -> str:
        return col_index_to_letter(col)

    # ── Headers ──────────────────────────────────────────────────────
    def _refresh_headers(self):
        # Column headers: A, B, C, ... Z, AA, AB...
        labels = [col_index_to_letter(i)
                  for i in range(self.table.columnCount())]
        self.table.setHorizontalHeaderLabels(labels)
        # Row headers: 1, 2, 3...
        row_labels = [str(i + 1) for i in range(self.table.rowCount())]
        self.table.setVerticalHeaderLabels(row_labels)

    # ── Cell ref display ─────────────────────────────────────────────
    def _on_current_cell_changed(self, row, col, prev_row, prev_col):
        if row < 0 or col < 0:
            self._cell_ref_label.setText("")
            self._formula_bar.clear()
            return
        ref = f"{col_index_to_letter(col)}{row + 1}"
        self._cell_ref_label.setText(ref)
        # Show formula if cell has one, otherwise show value
        formula = self._cell_formulas.get((row, col))
        if formula:
            self._formula_bar.setText(formula)
        else:
            it = self.table.item(row, col)
            self._formula_bar.setText(it.text() if it else "")

    # ── Cell editing ─────────────────────────────────────────────────
    def _on_cell_changed(self, row, col):
        it = self.table.item(row, col)
        new_text = it.text() if it else ""
        old_text = self._shadow.get((row, col), "")

        # Detect formula
        if new_text.startswith("="):
            self._cell_formulas[(row, col)] = new_text
            result = self._evaluate_formula(new_text, row, col)
            self.table.blockSignals(True)
            if it is None:
                it = QTableWidgetItem(str(result))
                self.table.setItem(row, col, it)
            else:
                it.setText(str(result))
            self.table.blockSignals(False)
            new_text = str(result)
        else:
            self._cell_formulas.pop((row, col), None)

        self._shadow[(row, col)] = new_text

        if self._undo_stack and old_text != new_text:
            cmd = CellEditCmd(self, row, col, old_text, new_text)
            self._undo_stack.push(cmd)

        self.data_changed.emit(col)

    def _set_cell_quiet(self, row, col, text):
        """Set cell text without triggering signals."""
        self.table.blockSignals(True)
        it = self.table.item(row, col)
        if it is None:
            it = QTableWidgetItem(text)
            self.table.setItem(row, col, it)
        else:
            it.setText(text)
        self._shadow[(row, col)] = text
        self.table.blockSignals(False)

    def _apply_formula_bar(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        row, col = idx.row(), idx.column()
        text = self._formula_bar.text()
        self.table.blockSignals(True)
        try:
            it = self.table.item(row, col)
            if it is None:
                it = QTableWidgetItem(text)
                self.table.setItem(row, col, it)
            else:
                it.setText(text)
        finally:
            self.table.blockSignals(False)
        self._on_cell_changed(row, col)

    # ── Formula evaluation (basic) ───────────────────────────────────
    def _evaluate_formula(self, formula: str, row: int, col: int):
        """Evaluate a cell formula. Basic implementation — will be
        extended by formula_engine.py."""
        expr = formula[1:]  # strip leading =
        try:
            # Simple math evaluation with numpy
            import math
            ns = {"__builtins__": {}, "math": math, "np": np,
                  "abs": abs, "round": round, "int": int, "float": float,
                  "sum": sum, "min": min, "max": max, "len": len}

            # Expand SUM(A1:A10) BEFORE replacing individual cell refs,
            # otherwise A1 inside the range gets resolved first and
            # the range regex can't match.
            import re
            expr = self._expand_range_functions(expr)

            # Replace remaining cell refs like A1, B5 with values
            def _cell_ref(m):
                letters = m.group(1)
                rnum = int(m.group(2)) - 1  # 0-based row
                c = letter_to_col_index(letters)
                it = self.table.item(rnum, c)
                if it and it.text():
                    try:
                        return str(float(it.text()))
                    except ValueError:
                        return "0"
                return "0"

            expr = re.sub(r'\b([A-Z]+)(\d+)\b', _cell_ref, expr,
                          flags=re.IGNORECASE)

            result = eval(expr, ns)  # noqa: S307
            if isinstance(result, float):
                if result == int(result) and abs(result) < 1e15:
                    return int(result)
                return round(result, 10)
            return result
        except Exception:
            return "#ERROR"

    def _expand_range_functions(self, expr: str) -> str:
        """Expand SUM(A1:A10) style range references."""
        import re

        def _expand_range(m):
            func = m.group(1).lower()
            start_col = m.group(2)
            start_row = int(m.group(3))
            end_col = m.group(4)
            end_row = int(m.group(5))

            c1 = letter_to_col_index(start_col)
            c2 = letter_to_col_index(end_col)
            vals = []
            for c in range(c1, c2 + 1):
                for r in range(start_row - 1, end_row):
                    it = self.table.item(r, c)
                    if it and it.text():
                        try:
                            vals.append(float(it.text()))
                        except ValueError:
                            pass

            if func == "sum":
                return str(sum(vals)) if vals else "0"
            elif func == "average":
                return str(sum(vals) / len(vals)) if vals else "0"
            elif func == "min":
                return str(min(vals)) if vals else "0"
            elif func == "max":
                return str(max(vals)) if vals else "0"
            elif func == "count":
                return str(len(vals))
            return m.group(0)

        pattern = (r'(SUM|AVERAGE|MIN|MAX|COUNT)\s*\(\s*'
                   r'([A-Z]+)(\d+)\s*:\s*([A-Z]+)(\d+)\s*\)')
        return re.sub(pattern, _expand_range, expr, flags=re.IGNORECASE)

    # ── Right-click menus ────────────────────────────────────────────
    def _header_menu(self, pos):
        col = self.table.horizontalHeader().logicalIndexAt(pos)
        if col < 0:
            return
        menu = QMenu(self)

        # Designation
        desig_menu = menu.addMenu("Set As")
        for d in ("X", "Y"):
            act = desig_menu.addAction(d)
            act.triggered.connect(
                lambda _, d=d, c=col: self.set_designation(c, d))

        menu.addSeparator()

        # Column operations
        menu.addAction("Insert Column Left",
                       lambda: self._insert_column(col))
        menu.addAction("Insert Column Right",
                       lambda: self._insert_column(col + 1))
        menu.addAction("Delete Column",
                       lambda: self._delete_column(col))
        menu.addSeparator()
        menu.addAction("Column Width…",
                       lambda: self._set_column_width(col))

        # Sort
        menu.addSeparator()
        menu.addAction("Sort A → Z",
                       lambda: self._sort_column(col, Qt.AscendingOrder))
        menu.addAction("Sort Z → A",
                       lambda: self._sort_column(col, Qt.DescendingOrder))

        menu.exec_(self.table.horizontalHeader().mapToGlobal(pos))

    def _cell_menu(self, pos):
        menu = QMenu(self)

        menu.addAction("Cut", self._cut_selection,
                       "Ctrl+X")
        menu.addAction("Copy", self._copy_selection,
                       "Ctrl+C")
        menu.addAction("Paste", self._paste_clipboard,
                       "Ctrl+V")
        menu.addAction("Clear", self._clear_selection,
                       "Del")

        menu.addSeparator()

        menu.addAction("Insert Row Above", self._insert_row_above)
        menu.addAction("Insert Row Below", self._insert_row_below)
        menu.addAction("Delete Row(s)", self._delete_selected_rows)
        menu.addAction("Add 10 Rows", self._add_10_rows)

        menu.addSeparator()

        # Plot submenu
        plot_menu = menu.addMenu("Plot")
        for pt in ("Line", "Scatter", "Line+Symbol", "Bar"):
            act = plot_menu.addAction(pt)
            act.triggered.connect(
                lambda _, t=pt: self._request_plot(t))

        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _request_plot(self, plot_type: str):
        """Signal to MainWindow to create a chart from selected data."""
        mw = self.window()
        if mw and hasattr(mw, "plot_from_sheet"):
            mw.plot_from_sheet(self, plot_type)

    # ── Clipboard operations ─────────────────────────────────────────
    def _cut_selection(self):
        self._copy_selection()
        self._clear_selection()

    def _copy_selection(self):
        sel = self.table.selectedRanges()
        if not sel:
            return
        s = sel[0]
        rows = []
        for r in range(s.topRow(), s.bottomRow() + 1):
            row_data = []
            for c in range(s.leftColumn(), s.rightColumn() + 1):
                it = self.table.item(r, c)
                row_data.append(it.text() if it else "")
            rows.append("\t".join(row_data))
        QApplication.clipboard().setText("\n".join(rows))

    def _paste_clipboard(self):
        text = QApplication.clipboard().text()
        if not text:
            return
        row = self.table.currentRow()
        col = self.table.currentColumn()
        if row < 0 or col < 0:
            return
        changes = []
        self.table.blockSignals(True)
        try:
            for dr, line in enumerate(text.split("\n")):
                if not line:
                    continue
                for dc, val in enumerate(line.split("\t")):
                    r, c = row + dr, col + dc
                    if r >= self.row_count() or c >= self.column_count():
                        continue
                    it = self.table.item(r, c)
                    old = it.text() if it else ""
                    if it is None:
                        it = QTableWidgetItem(val)
                        self.table.setItem(r, c, it)
                    else:
                        it.setText(val)
                    self._shadow[(r, c)] = val
                    if old != val:
                        changes.append((r, c, old, val))
        finally:
            self.table.blockSignals(False)
        if changes and self._undo_stack:
            self._undo_stack.push(
                BulkCellEditCmd(self, changes, "Paste"))

    def _clear_selection(self):
        sel = self.table.selectedRanges()
        if not sel:
            return
        changes = []
        self.table.blockSignals(True)
        try:
            for s in sel:
                for r in range(s.topRow(), s.bottomRow() + 1):
                    for c in range(s.leftColumn(), s.rightColumn() + 1):
                        it = self.table.item(r, c)
                        old = it.text() if it else ""
                        if old:
                            if it is None:
                                it = QTableWidgetItem("")
                                self.table.setItem(r, c, it)
                            else:
                                it.setText("")
                            self._shadow[(r, c)] = ""
                            changes.append((r, c, old, ""))
        finally:
            self.table.blockSignals(False)
        if changes and self._undo_stack:
            self._undo_stack.push(
                BulkCellEditCmd(self, changes, "Clear"))

    # ── Row/column operations ────────────────────────────────────────
    def _insert_row_above(self):
        row = self.table.currentRow()
        if row < 0:
            row = 0
        self.table.insertRow(row)
        self._refresh_headers()

    def _insert_row_below(self):
        row = self.table.currentRow()
        if row < 0:
            row = self.row_count() - 1
        self.table.insertRow(row + 1)
        self._refresh_headers()

    def _delete_selected_rows(self):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()),
                      reverse=True)
        for r in rows:
            self.table.removeRow(r)
        self._refresh_headers()

    def _add_10_rows(self):
        cur = self.row_count()
        for _ in range(10):
            self.table.insertRow(cur)
            cur += 1
        self._refresh_headers()

    def _insert_column(self, col: int):
        self.table.insertColumn(col)
        # Shift designations
        new_desigs = {}
        for c, d in self._col_designations.items():
            if c >= col:
                new_desigs[c + 1] = d
            else:
                new_desigs[c] = d
        self._col_designations = new_desigs
        self._refresh_headers()

    def _delete_column(self, col: int):
        if self.column_count() <= 1:
            return
        self.table.removeColumn(col)
        # Shift designations
        new_desigs = {}
        for c, d in self._col_designations.items():
            if c == col:
                continue
            if c > col:
                new_desigs[c - 1] = d
            else:
                new_desigs[c] = d
        self._col_designations = new_desigs
        self._refresh_headers()

    def _set_column_width(self, col: int):
        cur = self.table.columnWidth(col)
        w, ok = QInputDialog.getInt(self, "Column Width",
                                    "Width (pixels):", cur, 20, 500)
        if ok:
            self.table.setColumnWidth(col, w)

    def _sort_column(self, col: int, order):
        self.table.sortItems(col, order)

    # ── Drag-fill (Excel-style auto-fill) ────────────────────────────
    _HANDLE_PX = 6

    def _fill_handle_rect(self):
        sel = self.table.selectedRanges()
        if not sel:
            r = self.table.currentRow()
            c = self.table.currentColumn()
            if r < 0 or c < 0:
                return None
            sel = [QTableWidgetSelectionRange(r, c, r, c)]
        s = sel[0]
        item = self.table.item(s.bottomRow(), s.rightColumn())
        if item is not None:
            cell_rect = self.table.visualItemRect(item)
        else:
            cell_rect = self.table.visualRect(
                self.table.model().index(s.bottomRow(), s.rightColumn()))
        if cell_rect.isNull():
            x = self.table.columnViewportPosition(s.rightColumn())
            w = self.table.columnWidth(s.rightColumn())
            y = self.table.rowViewportPosition(s.bottomRow())
            h = self.table.rowHeight(s.bottomRow())
            cell_rect = QRect(x, y, w, h)
        hp = self._HANDLE_PX
        return QRect(cell_rect.right() - hp, cell_rect.bottom() - hp,
                     hp * 2, hp * 2)

    def eventFilter(self, obj, event):
        if obj is not self.table.viewport():
            return super().eventFilter(obj, event)
        etype = event.type()

        if etype == QEvent.MouseMove and not self._fill_dragging:
            hr = self._fill_handle_rect()
            if hr and hr.contains(event.pos()):
                self.table.viewport().setCursor(Qt.CrossCursor)
            else:
                self.table.viewport().unsetCursor()

        elif (etype == QEvent.MouseButtonPress
              and event.button() == Qt.LeftButton):
            hr = self._fill_handle_rect()
            if hr and hr.contains(event.pos()):
                sel = self.table.selectedRanges()
                if not sel:
                    r = self.table.currentRow()
                    c = self.table.currentColumn()
                    if r >= 0 and c >= 0:
                        sel = [QTableWidgetSelectionRange(r, c, r, c)]
                if sel:
                    self._fill_dragging = True
                    self._fill_anchor_range = sel[0]
                    self._fill_end_row = sel[0].bottomRow()
                    return True

        elif etype == QEvent.MouseMove and self._fill_dragging:
            row = self.table.rowAt(event.pos().y())
            if row >= 0:
                self._fill_end_row = row
                self._preview_fill()
            return True

        elif etype == QEvent.MouseButtonRelease and self._fill_dragging:
            self._fill_dragging = False
            self.table.viewport().unsetCursor()
            self._apply_fill()
            return True

        return super().eventFilter(obj, event)

    def _preview_fill(self):
        s = self._fill_anchor_range
        if s is None:
            return
        self.table.clearSelection()
        self.table.setRangeSelected(
            QTableWidgetSelectionRange(
                s.topRow(), s.leftColumn(),
                self._fill_end_row, s.rightColumn()),
            True)

    def _apply_fill(self):
        s = self._fill_anchor_range
        if s is None:
            return
        src_top = s.topRow()
        src_bot = s.bottomRow()
        fill_end = self._fill_end_row
        if fill_end <= src_bot:
            return

        changes = []
        self.table.blockSignals(True)
        try:
            for c in range(s.leftColumn(), s.rightColumn() + 1):
                vals = []
                for r in range(src_top, src_bot + 1):
                    it = self.table.item(r, c)
                    vals.append(it.text() if it else "")
                pattern = self._detect_pattern(vals)
                for r in range(src_bot + 1, fill_end + 1):
                    idx = r - src_top
                    text = self._pattern_value(pattern, idx, vals)
                    it = self.table.item(r, c)
                    old = it.text() if it else ""
                    if it is None:
                        it = QTableWidgetItem(text)
                        self.table.setItem(r, c, it)
                    else:
                        it.setText(text)
                    self._shadow[(r, c)] = text
                    if old != text:
                        changes.append((r, c, old, text))
        finally:
            self.table.blockSignals(False)
        if changes and self._undo_stack:
            self._undo_stack.push(
                BulkCellEditCmd(self, changes, "Drag fill"))
        self._fill_anchor_range = None

    def _detect_pattern(self, vals):
        nums = []
        for v in vals:
            try:
                nums.append(float(v))
            except (ValueError, TypeError):
                nums.append(None)
        if all(n is not None for n in nums) and len(nums) >= 2:
            diffs = [nums[i + 1] - nums[i] for i in range(len(nums) - 1)]
            if all(abs(d - diffs[0]) < 1e-12 for d in diffs):
                return {"type": "linear", "start": nums[0],
                        "step": diffs[0]}
            return {"type": "numeric_repeat", "values": nums}
        if all(n is not None for n in nums) and len(nums) == 1:
            return {"type": "constant", "value": vals[0]}
        return {"type": "repeat", "values": vals}

    def _pattern_value(self, pattern, idx, source_vals):
        pt = pattern["type"]
        src_n = len(source_vals)
        if pt == "linear":
            val = pattern["start"] + pattern["step"] * idx
            if (pattern["step"] == int(pattern["step"])
                    and pattern["start"] == int(pattern["start"])):
                return str(int(val))
            return f"{val:g}"
        elif pt == "constant":
            return pattern["value"]
        elif pt == "numeric_repeat":
            return f"{pattern['values'][idx % src_n]:g}"
        else:
            return pattern["values"][idx % src_n]
