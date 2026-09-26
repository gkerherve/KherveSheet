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

from .core.compiler import CELLREF_SKIP, compile_formula
from .core.functions import build_namespace, lower_names
from .core.numbers import format_number as _format_number  # noqa: F401
from .core.numbers import format_value as _format_value
from .core.refs import (  # noqa: F401 - re-exported for other modules
    XREF_PATTERN as _XREF_PATTERN,
    col_index_to_letter,
    REF_PATTERN,
    RANGE_PATTERN,
    function_names,
    letter_to_col_index,
    parse_cell_refs,
    quote_sheet_name as _quote_sheet_name,
    shift_formula,
)
from .core.values import CellValues

from .python_engine import (
    PY_MARKER, PythonHighlighter, badge_for, extract_refs,
    is_python_source, strip_marker,
)

from PyQt5.QtCore import Qt, QEvent, QRect, QSize, QTimer, pyqtSignal
from PyQt5.QtGui import (QColor, QFont, QPainter, QPen, QPixmap, QBrush,
                         QIcon)
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QMenu, QInputDialog, QLineEdit, QLabel, QAbstractItemView,
    QHeaderView, QStyledItemDelegate, QApplication,
    QTableWidgetSelectionRange, QAbstractItemDelegate,
    QPlainTextEdit, QSizePolicy, QFrame, QToolButton,
)


# ── Resizable formula bar widget ─────────────────────────────────────

class _FormulaEdit(QPlainTextEdit):
    """QPlainTextEdit that exposes the same API as QLineEdit.

    This lets the formula bar be resized vertically (by dragging the
    grip below it) while keeping the rest of SheetWidget's code unchanged.
    """

    returnPressed = pyqtSignal()
    textEdited = pyqtSignal(str)       # renamed to avoid shadowing QPlainTextEdit.textChanged
    popOutRequested = pyqtSignal()     # pop-out editor button clicked
    loopPeriodRequested = pyqtSignal() # loop-period button clicked
    loopPlayRequested = pyqtSignal()   # play/resume loop
    loopStopRequested = pyqtSignal()   # stop/pause loop

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabChangesFocus(True)
        self.setWordWrapMode(0)  # QTextOption.NoWrap — horizontal scroll
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.NoFrame)
        # Start as a single-line bar; user can drag the grip to enlarge.
        self.setMinimumHeight(22)
        self.setMaximumHeight(22)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # Forward the built-in textChanged (no args) as textEdited(str)
        # so callers get the QLineEdit-compatible signature.
        super().textChanged.connect(
            lambda: self.textEdited.emit(self.toPlainText()))
        # Python-cell mode: monospace + syntax highlight + Enter=newline,
        # Ctrl+Enter=commit (the inverse of normal-formula behaviour).
        self._python_mode = False
        self._highlighter = None
        self._normal_font = self.font()
        # A Python "PY" badge pinned to the right edge while editing a
        # Python cell (matches the badge drawn on =PY grid cells).
        from .python_engine import PyBadge
        self._py_badge = PyBadge(self)
        self._py_badge.hide()
        # Pop-out button: opens a larger editor for the cell's program.
        self._pop_btn = QToolButton(self)
        self._pop_btn.setToolTip("Open Python in a larger editor")
        self._pop_btn.setCursor(Qt.PointingHandCursor)
        self._pop_btn.setAutoRaise(True)
        self._pop_btn.setFocusPolicy(Qt.NoFocus)
        try:
            from . import icons
            # Bake to a pixmap (themed icons can render blank on tool
            # buttons — see themed-icon-blank-gotcha).
            pm = icons.themed_icon(
                "mdi.open-in-new", color="#3776ab").pixmap(22, 22)
            if not pm.isNull():
                self._pop_btn.setIcon(QIcon(pm))
            else:
                self._pop_btn.setText("⤢")
        except Exception:
            self._pop_btn.setText("⤢")
        self._pop_btn.clicked.connect(self.popOutRequested)
        self._pop_btn.hide()
        # Loop control buttons: period (clock), play/stop (toggle).
        _btn_sz = QSize(22, 22)
        self._loop_period_btn = QToolButton(self)
        self._loop_period_btn.setToolTip("Set loop period (auto-refresh interval)")
        self._loop_period_btn.setCursor(Qt.PointingHandCursor)
        self._loop_period_btn.setAutoRaise(True)
        self._loop_period_btn.setFocusPolicy(Qt.NoFocus)
        self._loop_period_btn.setIconSize(_btn_sz)
        self._loop_play_btn = QToolButton(self)
        self._loop_play_btn.setToolTip("Start loop")
        self._loop_play_btn.setCursor(Qt.PointingHandCursor)
        self._loop_play_btn.setAutoRaise(True)
        self._loop_play_btn.setFocusPolicy(Qt.NoFocus)
        self._loop_play_btn.setIconSize(_btn_sz)
        self._loop_stop_btn = QToolButton(self)
        self._loop_stop_btn.setToolTip("Stop loop")
        self._loop_stop_btn.setCursor(Qt.PointingHandCursor)
        self._loop_stop_btn.setAutoRaise(True)
        self._loop_stop_btn.setFocusPolicy(Qt.NoFocus)
        self._loop_stop_btn.setIconSize(_btn_sz)
        try:
            from . import icons
            pm_period = icons.themed_icon(
                "mdi.timer-outline", color="#3776ab").pixmap(22, 22)
            pm_play = icons.themed_icon(
                "mdi.play", color="#27ae60").pixmap(22, 22)
            pm_stop = icons.themed_icon(
                "mdi.stop", color="#c0392b").pixmap(22, 22)
            if not pm_period.isNull():
                self._loop_period_btn.setIcon(QIcon(pm_period))
            else:
                self._loop_period_btn.setText("⏱")
            if not pm_play.isNull():
                self._loop_play_btn.setIcon(QIcon(pm_play))
            else:
                self._loop_play_btn.setText("▶")
            if not pm_stop.isNull():
                self._loop_stop_btn.setIcon(QIcon(pm_stop))
            else:
                self._loop_stop_btn.setText("⏹")
        except Exception:
            self._loop_period_btn.setText("⏱")
            self._loop_play_btn.setText("▶")
            self._loop_stop_btn.setText("⏹")
        self._loop_period_btn.clicked.connect(self.loopPeriodRequested)
        self._loop_play_btn.clicked.connect(self.loopPlayRequested)
        self._loop_stop_btn.clicked.connect(self.loopStopRequested)
        self._loop_period_btn.hide()
        self._loop_play_btn.hide()
        self._loop_stop_btn.hide()
        self._loop_active = False  # tracks whether loop is running
        # Also set iconSize on the pop-out button.
        self._pop_btn.setIconSize(_btn_sz)

    def set_python_mode(self, on: bool):
        """Switch the bar between Excel-formula and Python-cell editing."""
        if on == self._python_mode:
            return
        self._python_mode = on
        if on:
            mono = QFont("Consolas")
            mono.setStyleHint(QFont.Monospace)
            mono.setPointSize(10)
            self.setFont(mono)
            if self._highlighter is None:
                self._highlighter = PythonHighlighter(self.document())
            # Grow to a few lines so multi-line code is comfortable.
            if self.maximumHeight() <= 22:
                self.setMaximumHeight(96)
            self.setMinimumHeight(72)
            # Very faint green background + PY strip, like a =PY grid cell.
            self.setStyleSheet("QPlainTextEdit{background:#f5f9fc;}")
            self._py_badge.show()
            self._py_badge.raise_()
            self._pop_btn.show()
            self._pop_btn.raise_()
            self._loop_period_btn.show()
            self._loop_period_btn.raise_()
            self._update_loop_buttons()
            self._position_py_badge()
        else:
            if self._highlighter is not None:
                self._highlighter.setDocument(None)
                self._highlighter = None
            self.setFont(self._normal_font)
            self.setMinimumHeight(22)
            self.setMaximumHeight(22)
            self.setStyleSheet("")
            self._py_badge.hide()
            self._pop_btn.hide()
            self._loop_period_btn.hide()
            self._loop_play_btn.hide()
            self._loop_stop_btn.hide()

    def _update_loop_buttons(self):
        """Show play or stop based on whether the loop is active."""
        if self._loop_active:
            self._loop_play_btn.hide()
            self._loop_stop_btn.show()
            self._loop_stop_btn.raise_()
        else:
            self._loop_stop_btn.hide()
            self._loop_play_btn.show()
            self._loop_play_btn.raise_()

    def set_loop_active(self, active: bool):
        """Update the play/stop button state."""
        self._loop_active = active
        if self._python_mode:
            self._update_loop_buttons()
            self._position_py_badge()

    def _position_py_badge(self):
        """Pin the PY strip (full-height) to the right edge and the
        loop/pop-out buttons just to its left, clear of the scrollbar."""
        sb = self.verticalScrollBar()
        margin = sb.width() if sb.isVisible() else 0
        bw = 22
        x = self.width() - bw - margin
        self._py_badge.setGeometry(x, 0, bw, self.height())
        # Position buttons top-right, right to left: pop-out, play/stop, period.
        btn_size = 28
        ty = 2  # pin to top
        bx = x - btn_size - 2
        self._pop_btn.setFixedSize(btn_size, btn_size)
        self._pop_btn.move(bx, ty)
        bx -= btn_size + 2
        # Play/stop share the same position (only one visible at a time).
        self._loop_play_btn.setFixedSize(btn_size, btn_size)
        self._loop_play_btn.move(bx, ty)
        self._loop_stop_btn.setFixedSize(btn_size, btn_size)
        self._loop_stop_btn.move(bx, ty)
        bx -= btn_size + 2
        self._loop_period_btn.setFixedSize(btn_size, btn_size)
        self._loop_period_btn.move(bx, ty)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._python_mode:
            self._position_py_badge()

    # ── QLineEdit-compatible API ─────────────────────────────────────
    def text(self):
        return self.toPlainText()

    def setText(self, t):
        self.setPlainText(t)

    def cursorPosition(self):
        return self.textCursor().position()

    def setCursorPosition(self, pos):
        tc = self.textCursor()
        tc.setPosition(min(pos, len(self.toPlainText())))
        self.setTextCursor(tc)

    # Enter applies the formula; Ctrl+Enter / Alt+Enter insert a newline.
    # In Python mode the two are swapped: Enter inserts a newline and
    # Ctrl+Enter commits, so multi-line code is the natural case.
    def keyPressEvent(self, event):
        is_return = event.key() in (Qt.Key_Return, Qt.Key_Enter)
        ctrl_alt = event.modifiers() & (Qt.ControlModifier | Qt.AltModifier)
        if self._python_mode:
            if is_return and (event.modifiers() & Qt.ControlModifier):
                self.returnPressed.emit()
                return
            super().keyPressEvent(event)
            return
        if is_return and not ctrl_alt:
            self.returnPressed.emit()
            return
        super().keyPressEvent(event)


class _FormulaBarGrip(QWidget):
    """Thin drag-handle between the formula bar and the table.

    Dragging it vertically resizes the formula bar (``_FormulaEdit``).
    """

    def __init__(self, formula_edit, parent=None):
        super().__init__(parent)
        self._fe = formula_edit
        self.setFixedHeight(4)
        self.setCursor(Qt.SplitVCursor)
        self.setStyleSheet(
            "background: qlineargradient(y1:0, y2:1, "
            "stop:0 #d0d0d0, stop:1 #c0c0c0);")
        self._drag_y = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_y = event.globalY()
            self._start_h = self._fe.maximumHeight()

    def mouseMoveEvent(self, event):
        if self._drag_y is not None:
            delta = event.globalY() - self._drag_y
            new_h = max(22, self._start_h + delta)
            self._fe.setMaximumHeight(new_h)

    def mouseReleaseEvent(self, event):
        self._drag_y = None

    def mouseDoubleClickEvent(self, event):
        # Double-click resets to single-line height.
        self._fe.setMaximumHeight(22)


# ── Number format constants ──────────────────────────────────────────
NUMBER_FORMATS = [
    "General",
    "0",
    "0.0",
    "0.00",
    "0.000",
    "0.0000",
    "Scientific",
    "Percentage",
    "Currency",
    "Date",
    "Time",
    "Text",
]

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


class FormatCellsCmd(QUndoCommand):
    """Undo/redo for cell formatting changes."""

    def __init__(self, sheet, old_formats, new_formats,
                 label="Format Cells"):
        """
        *old_formats* / *new_formats*: dict mapping (row, col) to a
        CellFormat snapshot (deep copy) or None (meaning no format).
        """
        super().__init__(label)
        self.sheet = sheet
        self.old_formats = old_formats
        self.new_formats = new_formats

    def undo(self):
        self._apply(self.old_formats)

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            return
        self._apply(self.new_formats)

    def _apply(self, fmts):
        """Restore cell formats and visual state."""
        from .cellformat import CellFormat
        sheet = self.sheet
        sheet.table.blockSignals(True)
        for (r, c), cf in fmts.items():
            if cf is None:
                sheet._cell_formats.pop((r, c), None)
                it = sheet.table.item(r, c)
                if it:
                    it.setBackground(QBrush())
                    it.setForeground(QBrush())
            else:
                sheet._cell_formats[(r, c)] = cf
                it = sheet.table.item(r, c)
                if it is None:
                    it = QTableWidgetItem("")
                    sheet.table.setItem(r, c, it)
                # Apply visual state.
                if cf.bg_color:
                    it.setBackground(QColor(cf.bg_color))
                else:
                    it.setBackground(QBrush())
                if cf.font_color:
                    it.setForeground(QColor(cf.font_color))
                else:
                    it.setForeground(QBrush())
                if cf.alignment is not None:
                    it.setTextAlignment(cf.alignment)
                f = it.font()
                if cf.bold is not None:
                    f.setBold(cf.bold)
                if cf.italic is not None:
                    f.setItalic(cf.italic)
                if cf.underline is not None:
                    f.setUnderline(cf.underline)
                if cf.font_family is not None:
                    f.setFamily(cf.font_family)
                if cf.font_size is not None:
                    f.setPointSizeF(cf.font_size)
                it.setFont(f)
        sheet.table.blockSignals(False)
        sheet.table.viewport().update()


# Cross-sheet cell clipboard: holds the per-cell metadata (formatting,
# checkbox/dropdown/note/sparkline state) of the last in-app copy, keyed
# to the clipboard text so an external copy never inherits stale meta.
_CELL_CLIPBOARD = None


def _snapshot_format(cf):
    """Deep-copy a CellFormat for undo snapshots."""
    from .cellformat import CellFormat, BorderSpec
    if cf is None:
        return None
    new = CellFormat()
    new.bg_color = cf.bg_color
    for side in ("top", "bottom", "left", "right"):
        orig = getattr(cf, f"border_{side}")
        if orig is not None:
            setattr(new, f"border_{side}",
                    BorderSpec(orig.style, orig.color, orig.width))
    new.bold = cf.bold
    new.italic = cf.italic
    new.underline = cf.underline
    new.font_family = cf.font_family
    new.font_size = cf.font_size
    new.font_color = cf.font_color
    new.alignment = cf.alignment
    new.number_format = cf.number_format
    new.wrap_text = cf.wrap_text
    return new


class InsertRowCmd(QUndoCommand):
    """Undo/redo for inserting a row."""

    def __init__(self, sheet, row):
        super().__init__(f"Insert row {row + 1}")
        self.sheet = sheet
        self.row = row

    def undo(self):
        self.sheet.table.blockSignals(True)
        self.sheet.table.removeRow(self.row)
        self.sheet.table.blockSignals(False)
        self.sheet._refresh_headers()

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            return
        self.sheet.table.blockSignals(True)
        self.sheet.table.insertRow(self.row)
        self.sheet.table.blockSignals(False)
        self.sheet._refresh_headers()


class DeleteRowsCmd(QUndoCommand):
    """Undo/redo for deleting one or more rows."""

    def __init__(self, sheet, rows_data, label="Delete rows"):
        super().__init__(label)
        self.sheet = sheet
        # rows_data: sorted list of (row_index, [(col, text, formula), ...])
        self.rows_data = rows_data

    def undo(self):
        self.sheet.table.blockSignals(True)
        for row_idx, cells in self.rows_data:
            self.sheet.table.insertRow(row_idx)
            for col, text, formula in cells:
                it = QTableWidgetItem(text)
                self.sheet.table.setItem(row_idx, col, it)
                self.sheet._shadow[(row_idx, col)] = text
                if formula:
                    self.sheet._cell_formulas[(row_idx, col)] = formula
        self.sheet.table.blockSignals(False)
        self.sheet._refresh_headers()

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            return
        self.sheet.table.blockSignals(True)
        for row_idx, _cells in reversed(self.rows_data):
            self.sheet.table.removeRow(row_idx)
        self.sheet.table.blockSignals(False)
        self.sheet._refresh_headers()


class InsertCellsCmd(QUndoCommand):
    """Undo/redo for inserting blank cells (shift down) in specific columns."""

    def __init__(self, sheet, rows, cols):
        super().__init__("Insert cells")
        self.sheet = sheet
        self.rows = rows  # sorted list of row indices
        self.cols = cols  # sorted list of col indices

    def _shift_down(self):
        """Shift cells down in self.cols starting at the top selected row."""
        s = self.sheet
        n = len(self.rows)
        start = self.rows[0]
        total = s.table.rowCount()
        s.table.blockSignals(True)
        for c in self.cols:
            # Move cells from bottom up to make room.
            for r in range(total - 1, start + n - 1, -1):
                src = r - n
                it = s.table.item(src, c)
                text = it.text() if it else ""
                dst_it = s.table.item(r, c)
                if dst_it is None:
                    dst_it = QTableWidgetItem()
                    s.table.setItem(r, c, dst_it)
                dst_it.setText(text)
                s._shadow[(r, c)] = text
                # Shift formulas.
                f = s._cell_formulas.pop((src, c), None)
                if f:
                    s._cell_formulas[(r, c)] = f
                # Shift formats.
                fmt = s._cell_formats.pop((src, c), None)
                if fmt:
                    s._cell_formats[(r, c)] = fmt
            # Clear the inserted cells.
            for r in range(start, start + n):
                it = s.table.item(r, c)
                if it:
                    it.setText("")
                s._shadow.pop((r, c), None)
                s._cell_formulas.pop((r, c), None)
                s._cell_formats.pop((r, c), None)
        s.table.blockSignals(False)
        s.table.viewport().update()

    def _shift_up(self):
        """Reverse: shift cells back up."""
        s = self.sheet
        n = len(self.rows)
        start = self.rows[0]
        total = s.table.rowCount()
        s.table.blockSignals(True)
        for c in self.cols:
            for r in range(start, total - n):
                src = r + n
                it = s.table.item(src, c)
                text = it.text() if it else ""
                dst_it = s.table.item(r, c)
                if dst_it is None:
                    dst_it = QTableWidgetItem()
                    s.table.setItem(r, c, dst_it)
                dst_it.setText(text)
                s._shadow[(r, c)] = text
                f = s._cell_formulas.pop((src, c), None)
                if f:
                    s._cell_formulas[(r, c)] = f
                fmt = s._cell_formats.pop((src, c), None)
                if fmt:
                    s._cell_formats[(r, c)] = fmt
            # Clear the vacated cells at the bottom.
            for r in range(total - n, total):
                it = s.table.item(r, c)
                if it:
                    it.setText("")
                s._shadow.pop((r, c), None)
                s._cell_formulas.pop((r, c), None)
                s._cell_formats.pop((r, c), None)
        s.table.blockSignals(False)
        s.table.viewport().update()

    def undo(self):
        self._shift_up()

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            return
        self._shift_down()


class DeleteCellsCmd(QUndoCommand):
    """Undo/redo for deleting cells (shift up) in specific columns."""

    def __init__(self, sheet, rows, cols, saved):
        super().__init__("Delete cells")
        self.sheet = sheet
        self.rows = rows
        self.cols = cols
        # saved: {(r, c): (text, formula, fmt)} for deleted cells
        self.saved = saved

    def _shift_up(self):
        s = self.sheet
        n = len(self.rows)
        start = self.rows[0]
        total = s.table.rowCount()
        s.table.blockSignals(True)
        for c in self.cols:
            for r in range(start, total - n):
                src = r + n
                it = s.table.item(src, c)
                text = it.text() if it else ""
                dst_it = s.table.item(r, c)
                if dst_it is None:
                    dst_it = QTableWidgetItem()
                    s.table.setItem(r, c, dst_it)
                dst_it.setText(text)
                s._shadow[(r, c)] = text
                f = s._cell_formulas.pop((src, c), None)
                if f:
                    s._cell_formulas[(r, c)] = f
                fmt = s._cell_formats.pop((src, c), None)
                if fmt:
                    s._cell_formats[(r, c)] = fmt
            for r in range(total - n, total):
                it = s.table.item(r, c)
                if it:
                    it.setText("")
                s._shadow.pop((r, c), None)
                s._cell_formulas.pop((r, c), None)
                s._cell_formats.pop((r, c), None)
        s.table.blockSignals(False)
        s.table.viewport().update()

    def _shift_down_restore(self):
        s = self.sheet
        n = len(self.rows)
        start = self.rows[0]
        total = s.table.rowCount()
        s.table.blockSignals(True)
        for c in self.cols:
            for r in range(total - 1, start + n - 1, -1):
                src = r - n
                it = s.table.item(src, c)
                text = it.text() if it else ""
                dst_it = s.table.item(r, c)
                if dst_it is None:
                    dst_it = QTableWidgetItem()
                    s.table.setItem(r, c, dst_it)
                dst_it.setText(text)
                s._shadow[(r, c)] = text
                f = s._cell_formulas.pop((src, c), None)
                if f:
                    s._cell_formulas[(r, c)] = f
                fmt = s._cell_formats.pop((src, c), None)
                if fmt:
                    s._cell_formats[(r, c)] = fmt
        # Restore deleted cells.
        for (r, c), (text, formula, fmt) in self.saved.items():
            it = s.table.item(r, c)
            if it is None:
                it = QTableWidgetItem()
                s.table.setItem(r, c, it)
            it.setText(text)
            s._shadow[(r, c)] = text
            if formula:
                s._cell_formulas[(r, c)] = formula
            if fmt:
                s._cell_formats[(r, c)] = fmt
        s.table.blockSignals(False)
        s.table.viewport().update()

    def undo(self):
        self._shift_down_restore()

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            return
        self._shift_up()


class InsertColumnCmd(QUndoCommand):
    """Undo/redo for inserting a column."""

    def __init__(self, sheet, col, old_designations):
        super().__init__(f"Insert column {col_index_to_letter(col)}")
        self.sheet = sheet
        self.col = col
        self.old_desigs = dict(old_designations)

    def undo(self):
        self.sheet.table.blockSignals(True)
        self.sheet.table.removeColumn(self.col)
        self.sheet._shift_cell_dicts(self.col, -1)
        self.sheet._col_designations = dict(self.old_desigs)
        self.sheet.table.blockSignals(False)
        self.sheet._shift_charts(self.col, -1)
        self.sheet._refresh_headers()

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            return
        self.sheet.table.blockSignals(True)
        self.sheet.table.insertColumn(self.col)
        self.sheet._shift_cell_dicts(self.col, +1)
        # Shift designations.
        new_desigs = {}
        for c, d in self.old_desigs.items():
            if c >= self.col:
                new_desigs[c + 1] = d
            else:
                new_desigs[c] = d
        self.sheet._col_designations = new_desigs
        self.sheet.table.blockSignals(False)
        self.sheet._shift_charts(self.col, +1)
        self.sheet._refresh_headers()


class DeleteColumnCmd(QUndoCommand):
    """Undo/redo for deleting a column."""

    def __init__(self, sheet, col, col_data, old_designations,
                 col_meta=None):
        super().__init__(
            f"Delete column {col_index_to_letter(col)}")
        self.sheet = sheet
        self.col = col
        # col_data: [(row, text, formula), ...]
        self.col_data = col_data
        self.old_desigs = dict(old_designations)
        self.col_meta = col_meta or {}

    def undo(self):
        self.sheet.table.blockSignals(True)
        self.sheet.table.insertColumn(self.col)
        self.sheet._shift_cell_dicts(self.col, +1)
        for row, text, formula in self.col_data:
            it = QTableWidgetItem(text)
            self.sheet.table.setItem(row, self.col, it)
            self.sheet._shadow[(row, self.col)] = text
            if formula:
                self.sheet._cell_formulas[(row, self.col)] = formula
        self.sheet._restore_column_meta(self.col, self.col_meta)
        self.sheet._col_designations = dict(self.old_desigs)
        self.sheet.table.blockSignals(False)
        self.sheet._shift_charts(self.col, +1)
        self.sheet._refresh_headers()

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            return
        self.sheet.table.blockSignals(True)
        self.sheet.table.removeColumn(self.col)
        self.sheet._shift_cell_dicts(self.col, -1)
        # Shift designations.
        new_desigs = {}
        for c, d in self.old_desigs.items():
            if c == self.col:
                continue
            if c > self.col:
                new_desigs[c - 1] = d
            else:
                new_desigs[c] = d
        self.sheet._col_designations = new_desigs
        self.sheet.table.blockSignals(False)
        self.sheet._shift_charts(self.col, -1)
        self.sheet._refresh_headers()


class SortColumnCmd(QUndoCommand):
    """Undo/redo for sorting by a column."""

    def __init__(self, sheet, old_data, label="Sort"):
        super().__init__(label)
        self.sheet = sheet
        # old_data: [(row, [(col, text, formula), ...]), ...]
        self.old_data = old_data

    def undo(self):
        self._restore(self.old_data)

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            # Snapshot new state for redo.
            self.new_data = self._snapshot()
            return
        self._restore(self.new_data)

    def _snapshot(self):
        s = self.sheet
        data = []
        for r in range(s.table.rowCount()):
            cells = []
            for c in range(s.table.columnCount()):
                it = s.table.item(r, c)
                text = it.text() if it else ""
                formula = s._cell_formulas.get((r, c))
                cells.append((c, text, formula))
            data.append((r, cells))
        return data

    def _restore(self, data):
        s = self.sheet
        s.table.blockSignals(True)
        s._cell_formulas.clear()
        s._shadow.clear()
        for r, cells in data:
            for c, text, formula in cells:
                it = s.table.item(r, c)
                if it is None:
                    it = QTableWidgetItem(text)
                    s.table.setItem(r, c, it)
                else:
                    it.setText(text)
                s._shadow[(r, c)] = text
                if formula:
                    s._cell_formulas[(r, c)] = formula
        s.table.blockSignals(False)


class MergeCellsCmd(QUndoCommand):
    """Undo/redo for merging cells."""

    def __init__(self, sheet, r, c, rs, cs, cleared_cells):
        super().__init__("Merge cells")
        self.sheet = sheet
        self.r, self.c, self.rs, self.cs = r, c, rs, cs
        # cleared_cells: [(row, col, old_text), ...]
        self.cleared = cleared_cells

    def undo(self):
        self.sheet.table.blockSignals(True)
        self.sheet.table.setSpan(self.r, self.c, 1, 1)
        # Remove from merged_ranges.
        self.sheet._merged_ranges = [
            m for m in self.sheet._merged_ranges
            if m != (self.r, self.c, self.rs, self.cs)]
        # Restore cleared cells.
        for row, col, text in self.cleared:
            it = self.sheet.table.item(row, col)
            if it is None:
                it = QTableWidgetItem(text)
                self.sheet.table.setItem(row, col, it)
            else:
                it.setText(text)
            self.sheet._shadow[(row, col)] = text
        self.sheet.table.blockSignals(False)

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            return
        self.sheet.table.blockSignals(True)
        for row, col, _text in self.cleared:
            it = self.sheet.table.item(row, col)
            if it:
                it.setText("")
            self.sheet._shadow[(row, col)] = ""
        self.sheet.table.setSpan(self.r, self.c, self.rs, self.cs)
        self.sheet._merged_ranges.append(
            (self.r, self.c, self.rs, self.cs))
        self.sheet.table.blockSignals(False)


class UnmergeCellsCmd(QUndoCommand):
    """Undo/redo for unmerging cells."""

    def __init__(self, sheet, unmerged):
        super().__init__("Unmerge cells")
        self.sheet = sheet
        # unmerged: [(r, c, rs, cs), ...]
        self.unmerged = unmerged

    def undo(self):
        self.sheet.table.blockSignals(True)
        for r, c, rs, cs in self.unmerged:
            self.sheet.table.setSpan(r, c, rs, cs)
            self.sheet._merged_ranges.append((r, c, rs, cs))
        self.sheet.table.blockSignals(False)

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            return
        self.sheet.table.blockSignals(True)
        for r, c, rs, cs in self.unmerged:
            self.sheet.table.setSpan(r, c, 1, 1)
            self.sheet._merged_ranges = [
                m for m in self.sheet._merged_ranges
                if m != (r, c, rs, cs)]
        self.sheet.table.blockSignals(False)


class SetDesignationCmd(QUndoCommand):
    """Undo/redo for column designation changes."""

    def __init__(self, sheet, col, old_desig, new_desig):
        super().__init__(
            f"Set {col_index_to_letter(col)} = {new_desig}")
        self.sheet = sheet
        self.col = col
        self.old_desig = old_desig
        self.new_desig = new_desig

    def undo(self):
        if self.old_desig is None:
            self.sheet._col_designations.pop(self.col, None)
        else:
            self.sheet._col_designations[self.col] = self.old_desig
        self.sheet._refresh_headers()

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            return
        self.sheet._col_designations[self.col] = self.new_desig
        self.sheet._refresh_headers()


class SetNumberFormatCmd(QUndoCommand):
    """Undo/redo for column number format changes."""

    def __init__(self, sheet, changes, label="Number Format"):
        super().__init__(label)
        self.sheet = sheet
        # changes: [(col, old_fmt, new_fmt), ...]
        self.changes = changes

    def undo(self):
        for col, old_fmt, _new_fmt in self.changes:
            if old_fmt:
                self.sheet._col_formats[col] = old_fmt
            else:
                self.sheet._col_formats.pop(col, None)

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            return
        for col, _old_fmt, new_fmt in self.changes:
            self.sheet._col_formats[col] = new_fmt


class ResizeSectionsCmd(QUndoCommand):
    """Undo/redo for column-width or row-height changes."""

    def __init__(self, sheet, old_sizes, new_sizes, axis, label):
        """
        *old_sizes* / *new_sizes*: dict mapping index → pixel size.
        *axis*: 'col' or 'row'.
        """
        super().__init__(label)
        self.sheet = sheet
        self.old_sizes = old_sizes
        self.new_sizes = new_sizes
        self.axis = axis

    def _apply(self, sizes):
        self.sheet._resizing_sections = True
        if self.axis == 'col':
            for idx, sz in sizes.items():
                self.sheet.table.setColumnWidth(idx, sz)
        else:
            for idx, sz in sizes.items():
                self.sheet.table.setRowHeight(idx, sz)
        self.sheet._resizing_sections = False

    def undo(self):
        self._apply(self.old_sizes)

    def redo(self):
        if not getattr(self, "_first_redo_done", False):
            self._first_redo_done = True
            return
        self._apply(self.new_sizes)


class _MarchingAntsOverlay(QWidget):
    """Transparent overlay child of the table viewport that paints the
    animated dashed border around the copied range. Painting in a real
    paintEvent (rather than on the viewport outside its own paint) is the
    only reliable way to draw on top of a QAbstractScrollArea."""

    def __init__(self, sheet):
        super().__init__(sheet.table.viewport())
        self._sheet = sheet
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.hide()

    def paintEvent(self, event):
        rng = self._sheet._marching_range
        if rng is None:
            return
        painter = QPainter(self)
        self._sheet._paint_marching_ants(painter)
        painter.end()


class _SelectionOverlay(QWidget):
    """Draws an Excel-style selection border and fill-handle square on
    top of the table viewport, replacing the default opaque highlight."""

    _HANDLE_PX = 4  # half-size of the fill-handle square

    def __init__(self, sheet):
        super().__init__(sheet.table.viewport())
        self._sheet = sheet
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)

    @staticmethod
    def _coalesce(ranges):
        """Merge overlapping/adjacent selection ranges into bounding rects.

        QTableWidget returns many 1-cell ranges when a merged cell
        (setSpan) is present anywhere in the table.  This method groups
        selected cells into contiguous rectangular blocks so that the
        overlay draws one border per block instead of per cell.
        """
        if not ranges:
            return ranges
        # If there are few ranges and they already look normal, skip.
        if len(ranges) <= 1:
            return ranges
        # Collect every selected cell.
        cells = set()
        for s in ranges:
            for r in range(s.topRow(), s.bottomRow() + 1):
                for c in range(s.leftColumn(), s.rightColumn() + 1):
                    cells.add((r, c))
        if not cells:
            return ranges
        # Flood-fill contiguous rectangular blocks.
        remaining = set(cells)
        blocks = []
        while remaining:
            seed = min(remaining)
            r1 = r2 = seed[0]
            c1 = c2 = seed[1]
            # Expand the bounding box as long as every cell inside it
            # is selected.
            changed = True
            while changed:
                changed = False
                # Try expanding right.
                if all((r, c2 + 1) in remaining or (r, c2 + 1) in (cells - remaining)
                       for r in range(r1, r2 + 1)) and \
                   any((r, c2 + 1) in remaining for r in range(r1, r2 + 1)):
                    c2 += 1
                    changed = True
                # Try expanding down.
                if all((r2 + 1, c) in remaining or (r2 + 1, c) in (cells - remaining)
                       for c in range(c1, c2 + 1)) and \
                   any((r2 + 1, c) in remaining for c in range(c1, c2 + 1)):
                    r2 += 1
                    changed = True
            # Remove all cells in this block.
            for r in range(r1, r2 + 1):
                for c in range(c1, c2 + 1):
                    remaining.discard((r, c))
            blocks.append(QTableWidgetSelectionRange(r1, c1, r2, c2))
        return blocks

    def paintEvent(self, event):
        table = self._sheet.table
        sel = table.selectedRanges()
        if not sel:
            r = table.currentRow()
            c = table.currentColumn()
            if r < 0 or c < 0:
                return
            sel = [QTableWidgetSelectionRange(r, c, r, c)]

        sel = self._coalesce(sel)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        # Use the palette highlight colour for the border.
        border_color = self.palette().highlight().color()

        for s in sel:
            # Compute bounding rect from top-left to bottom-right cell.
            r1, c1 = s.topRow(), s.leftColumn()
            r2, c2 = s.bottomRow(), s.rightColumn()

            tl_rect = table.visualRect(table.model().index(r1, c1))
            br_rect = table.visualRect(table.model().index(r2, c2))
            if tl_rect.isNull() and br_rect.isNull():
                continue

            # Handle partially-visible ranges.
            if tl_rect.isNull():
                tl_rect = br_rect
            if br_rect.isNull():
                br_rect = tl_rect

            x = tl_rect.left()
            y = tl_rect.top()
            w = br_rect.right() - tl_rect.left()
            h = br_rect.bottom() - tl_rect.top()

            # Draw 2 px solid border around the selection.
            pen = QPen(border_color, 2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(x, y, w, h)

        # Draw fill handle on last (primary) selection range.
        s = sel[0]
        br_rect = table.visualRect(
            table.model().index(s.bottomRow(), s.rightColumn()))
        if not br_rect.isNull():
            hp = self._HANDLE_PX
            hx = br_rect.right() - hp
            hy = br_rect.bottom() - hp
            painter.setPen(Qt.NoPen)
            painter.setBrush(border_color)
            painter.drawRect(hx, hy, hp * 2, hp * 2)

        painter.end()


# ── SheetWidget ──────────────────────────────────────────────────────
class SheetWidget(CellValues, QWidget):
    """A single Excel-style spreadsheet grid."""

    data_changed = pyqtSignal(int)  # emits column index on data change

    def __init__(self, rows: int = 1000, cols: int = 26):
        super().__init__()
        self._undo_stack = None  # set by MainWindow after construction
        self._default_format = "General"
        # When set, _recalc_dependents skips data_changed emissions so
        # charts are not redrawn on every recalc (used by the Solver,
        # which recalculates the model hundreds of times).
        self._suppress_recalc_signals = False
        # Formula evaluation cache: formula text → compiled code object
        # (or False if it failed to compile).  Compiled formulas read
        # live cell values at eval time via the _C/_AGG/_COL helpers, so
        # the cache never needs invalidating when values change — only a
        # change to the formula *text* yields a new key.  This keeps the
        # Solver's repeated recalculation off the regex/parse hot path.
        self._compiled_cache = {}
        self._eval_ns = None
        self._eval_ns_lower = None

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
        from PyQt5.QtWidgets import QToolButton
        self._fx_btn = QToolButton()
        self._fx_btn.setText("fx")
        self._fx_btn.setStyleSheet(
            "QToolButton { color:#3a78b4; font-weight:bold; "
            "font-style:italic; border:1px solid #b8bcc3; "
            "padding:1px 6px; background:#fafafa; }"
            "QToolButton:hover { background:#e0ecf8; }")
        self._fx_btn.setToolTip("Insert Function (Shift+F3)")
        self._fx_btn.clicked.connect(self._open_insert_function)
        self._formula_bar = _FormulaEdit()
        self._formula_bar.setPlaceholderText(
            "Value or =formula  (e.g. =SUM(A1:A10), =B1+C1)")
        self._formula_bar.returnPressed.connect(self._apply_formula_bar)
        self._formula_bar.textEdited.connect(self._on_formula_bar_text)
        self._formula_bar.popOutRequested.connect(self._open_python_popout)
        self._formula_bar.loopPeriodRequested.connect(self._on_loop_period)
        self._formula_bar.loopPlayRequested.connect(self._on_loop_play)
        self._formula_bar.loopStopRequested.connect(self._on_loop_stop)

        fbar.addWidget(cell_lbl)
        fbar.addWidget(self._cell_ref_label)
        fbar.addWidget(self._fx_btn)
        fbar.addWidget(self._formula_bar, stretch=1)
        layout.addWidget(fbar_widget)
        self._fbar_grip = _FormulaBarGrip(self._formula_bar)
        layout.addWidget(self._fbar_grip)

        # ── Table ────────────────────────────────────────────────────
        self.table = QTableWidget(rows, cols)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.table.setFont(QFont("Segoe UI", 9))
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.verticalHeader().setMinimumSectionSize(16)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setDefaultSectionSize(80)
        self.table.horizontalHeader().setMinimumSectionSize(40)
        self.table.setShowGrid(True)

        # Column and row headers
        self._col_designations: dict = {}  # col → "X" or "Y"
        self._refresh_headers()

        # Context menus
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setContextMenuPolicy(
            Qt.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested.connect(
            self._header_menu)
        self.table.verticalHeader().setSectionsClickable(True)
        self.table.verticalHeader().setContextMenuPolicy(
            Qt.CustomContextMenu)
        self.table.verticalHeader().customContextMenuRequested.connect(
            self._row_header_menu)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._cell_menu)

        layout.addWidget(self.table)

        # ── Cell format delegate (borders) ──────────────────────────
        from .cellformat import CellFormat, CellFormatDelegate
        self._cell_formats: dict = {}    # (row, col) → CellFormat
        self._fmt_delegate = CellFormatDelegate(
            self._cell_formats, self.table)
        self.table.setItemDelegate(self._fmt_delegate)

        # ── Insert-ops metadata (shared with delegate for painting) ──
        self._cell_notes: dict = {}
        self._cell_dropdowns: dict = {}
        self._cell_sparklines: dict = {}
        self._cell_links: dict = {}
        self._solver_config: dict = {}
        self._fmt_delegate._notes = self._cell_notes
        self._fmt_delegate._dropdowns = self._cell_dropdowns
        self._note_popup = None  # floating note widget
        self._copied_meta = None  # metadata from last copy
        self._copy_origin = None  # (top_row, left_col) of copy source

        # ── Internal state ───────────────────────────────────────────
        self._shadow: dict = {}          # (row, col) → last-known text
        self._cell_formulas: dict = {}   # (row, col) → "=formula"
        # Share the formulas dict with the delegate so it can tint =PY
        # cells green and draw the "PY" badge.
        self._fmt_delegate._cell_formulas = self._cell_formulas
        self._cell_objects: dict = {}    # (row, col) → live Python value (=PY)
        self._py_spills: dict = {}       # (row, col) → list of spilled cells
        self._py_errors: dict = {}       # (row, col) → traceback string
        self._py_stdout: dict = {}       # (row, col) → captured print output
        self._py_figures: dict = {}      # (row, col) → EmbeddedImage (plot)
        self._py_udf_names: set = set()  # UPPER names of Python funcs as UDFs
        self._py_loops: dict = {}        # (row, col) → loop interval seconds
        self._py_loop_saved: dict = {}   # (row, col) → last-used period (survives stop)
        self._py_loop_last: dict = {}    # (row, col) → last run monotonic time
        self._py_loop_timer = None       # QTimer ticking due loop cells
        self._py_loop_running = False     # guard against overlapping runs
        self._fmt_delegate._py_loops = self._py_loops
        # Cell buttons: {(row, col): spec}.  Shared by reference so the
        # delegate paints whatever is in it without a copy step.
        self._cell_buttons: dict = {}
        self._fmt_delegate._buttons = self._cell_buttons
        self._dependents: dict = {}      # (row, col) → set of (r, c) that depend on it
        self._xref_cells: set = set()    # formula cells using Sheet!ref
        self._col_formats: dict = {}     # col → format string
        self._merged_ranges: list = []   # [(r, c, row_span, col_span), ...]
        # Embedded overlay widgets on the grid viewport.
        self._charts: list = []
        self._images: list = []
        self._shapes: list = []
        self._equations: list = []

        # Overlay widgets (charts, images, shapes, equations) float as
        # children of the grid viewport.
        self.overlay_host = lambda: self.table.viewport()

        # Formula entry mode: when editing a formula, clicking a cell
        # inserts a cell reference instead of navigating.
        self._formula_entry_cell = None   # (row, col) being edited
        self._pick_drag = None            # click-drag inserting a range ref
        self._ref_highlight_active = False
        # Inline formula editor tracking: when an inline cell editor
        # contains "=" text, we save its state so a click on another cell
        # can insert a cell reference instead of navigating.
        self._inline_formula_text = None  # saved editor text on close
        self._inline_formula_pos = None   # saved cursor position
        self._inline_formula_cell = None  # (row, col) of the cell being edited
        # Tab-completion state for formula function names.
        self._tab_matches: list = []       # current matching function names
        self._tab_index: int = -1          # index in _tab_matches
        self._tab_prefix_pos: int = 0      # cursor pos where the prefix starts
        # Arrow-key cell reference navigation state.
        self._arrow_nav_active = False
        self._arrow_nav_pos = None       # (row, col) of ref cursor
        self._arrow_nav_ref_span = None  # (start, end) char indices in editor
        # Range-finder: draggable formula reference highlights.
        self._ref_tokens = []            # [{span,c1,r1,c2,r2,text}] for cur text
        self._ref_drag = None            # active drag state, or None

        # Signals
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.currentCellChanged.connect(self._on_current_cell_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.cellClicked.connect(self._on_cell_clicked)

        # Sync resize across selected columns / rows.
        self._resizing_sections = False  # recursion guard
        self._col_resize_snap: dict | None = None  # {col: old_width}
        self._row_resize_snap: dict | None = None  # {row: old_height}
        self.table.horizontalHeader().sectionResized.connect(
            self._on_column_resized)
        self.table.verticalHeader().sectionResized.connect(
            self._on_row_resized)
        self.table.horizontalHeader().installEventFilter(self)
        self.table.verticalHeader().installEventFilter(self)

        # ── Selection anchor/cursor for Shift+Arrow ───────────────────
        self._sel_anchor = None   # (row, col) fixed corner of selection
        self._sel_cursor = None   # (row, col) moving corner of selection

        # ── Drag-fill state ──────────────────────────────────────────
        self._fill_dragging = False
        self._fill_anchor_range = None
        self._fill_end_row = None
        self._fill_end_col = None
        self._fill_direction = None          # "down" or "right"

        # ── Selection border overlay (Excel-style) ────────────────────
        self._sel_overlay = _SelectionOverlay(self)
        self._sel_overlay.setGeometry(self.table.viewport().rect())
        self._sel_overlay.show()
        self._sel_overlay.raise_()
        self.table.itemSelectionChanged.connect(self._update_sel_overlay)

        # ── Marching ants (copy highlight) ───────────────────────────
        self._marching_range = None   # QTableWidgetSelectionRange or None
        self._march_offset = 0
        self._march_timer = QTimer(self)
        self._march_timer.timeout.connect(self._march_tick)
        self._ants_overlay = _MarchingAntsOverlay(self)
        self.table.horizontalScrollBar().valueChanged.connect(
            lambda _=0: (self._ants_overlay.update(),
                         self._sel_overlay.update()))
        self.table.verticalScrollBar().valueChanged.connect(
            lambda _=0: (self._ants_overlay.update(),
                         self._sel_overlay.update()))
        # Grow columns to keep the viewport filled when scrolling right.
        self.table.horizontalScrollBar().valueChanged.connect(
            self._on_hscroll)

        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)
        self.table.viewport().installEventFilter(self)
        self.table.installEventFilter(self)
        self._formula_bar.installEventFilter(self)

    # ── Public API ───────────────────────────────────────────────────
    def clear_all_data(self):
        """Reset every cell, format, formula, and overlay to a blank state."""
        self.table.blockSignals(True)
        self.table.clearContents()
        self.table.blockSignals(False)
        self._shadow.clear()
        self._cell_formulas.clear()
        self._cell_objects.clear()
        self._py_spills.clear()
        self._py_errors.clear()
        self._py_stdout.clear()
        self._py_figures.clear()
        self._py_loops.clear()
        self._cell_buttons.clear()
        self._py_loop_last.clear()
        self._stop_py_loops()
        self._dependents.clear()
        self._xref_cells.clear()
        self._cell_formats.clear()
        self._col_formats.clear()
        self._col_designations.clear()
        # Unmerge all spans.
        for (r, c, rs, cs) in list(self._merged_ranges):
            self.table.setSpan(r, c, 1, 1)
        self._merged_ranges.clear()
        # Remove embedded charts and images.
        for chart in getattr(self, '_charts', []):
            chart.setParent(None)
            chart.deleteLater()
        if hasattr(self, '_charts'):
            self._charts.clear()
        for img in getattr(self, '_images', []):
            img.setParent(None)
            img.deleteLater()
        if hasattr(self, '_images'):
            self._images.clear()
        for shp in getattr(self, '_shapes', []):
            shp.setParent(None)
            shp.deleteLater()
        if hasattr(self, '_shapes'):
            self._shapes.clear()
        for eq in getattr(self, '_equations', []):
            eq.setParent(None)
            eq.deleteLater()
        if hasattr(self, '_equations'):
            self._equations.clear()
        # Reset column widths to default.
        for c in range(self.table.columnCount()):
            self.table.setColumnWidth(c, 80)
        self._refresh_headers()

    def column_count(self) -> int:
        return self.table.columnCount()

    def row_count(self) -> int:
        return self.table.rowCount()

    def cell_text(self, row: int, col: int) -> str:
        it = self.table.item(row, col)
        return it.text() if it else ""

    def _cell_decimals(self, row, col):
        """Return decimal precision for a cell based on its format."""
        cf = self._cell_formats.get((row, col))
        nf = None
        if cf:
            nf = getattr(cf, 'number_format', None)
        if not nf:
            nf = self._col_formats.get(col, self._default_format)
        # Map format string to decimal count.
        fmt_map = {"0": 0, "0.0": 1, "0.00": 2, "0.000": 3, "0.0000": 4}
        return fmt_map.get(nf, 3)  # default 3

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

    def string_column(self, col: int) -> list:
        """Return column data as a list of strings (empty for blank)."""
        vals = []
        for r in range(self.row_count()):
            it = self.table.item(r, col)
            vals.append(it.text() if it else "")
        return vals

    def set_designation(self, col: int, desig: str):
        old_desig = self._col_designations.get(col)
        if desig.upper() == "NONE":
            self._col_designations.pop(col, None)
        else:
            self._col_designations[col] = desig
        self._refresh_headers()
        if self._undo_stack is not None:
            self._undo_stack.push(
                SetDesignationCmd(self, col, old_desig, desig))

    def get_designation(self, col: int) -> str:
        return self._col_designations.get(col, "None")

    def column_display_name(self, col: int) -> str:
        letter = col_index_to_letter(col)
        desig = self._col_designations.get(col, "None").upper()
        if desig == "NONE":
            return letter
        x_num = 0
        for i in range(col + 1):
            d = self._col_designations.get(i, "None").upper()
            if d == "X":
                x_num += 1
        return f"{letter}({desig.lower()}{x_num})"

    # ── Merge cells ─────────────────────────────────────────────────
    def merge_selection(self):
        """Merge the selected cells into one span."""
        sel = self.table.selectedRanges()
        if not sel:
            return
        rng = sel[0]
        r, c = rng.topRow(), rng.leftColumn()
        rs = rng.rowCount()
        cs = rng.columnCount()
        if rs <= 1 and cs <= 1:
            return
        # Keep top-left value, clear rest — track for undo.
        cleared = []
        for mr in range(r, r + rs):
            for mc in range(c, c + cs):
                if (mr, mc) != (r, c):
                    it = self.table.item(mr, mc)
                    old_text = it.text() if it else ""
                    if it:
                        it.setText("")
                    cleared.append((mr, mc, old_text))
        self.table.setSpan(r, c, rs, cs)
        self._merged_ranges.append((r, c, rs, cs))
        if self._undo_stack is not None:
            self._undo_stack.push(
                MergeCellsCmd(self, r, c, rs, cs, cleared))

    def unmerge_selection(self):
        """Unmerge any merged cells in the selection."""
        sel = self.table.selectedRanges()
        if not sel:
            return
        rng = sel[0]
        keep = []
        unmerged = []
        for (mr, mc, rs, cs) in self._merged_ranges:
            if (rng.topRow() <= mr <= rng.bottomRow() and
                    rng.leftColumn() <= mc <= rng.rightColumn()):
                self.table.setSpan(mr, mc, 1, 1)
                unmerged.append((mr, mc, rs, cs))
            else:
                keep.append((mr, mc, rs, cs))
        self._merged_ranges = keep
        if unmerged and self._undo_stack is not None:
            self._undo_stack.push(UnmergeCellsCmd(self, unmerged))

    def _apply_cell_number_format(self, text: str, row: int,
                                   col: int) -> str:
        """Apply per-cell number format to *text*.

        When no explicit format is set, numeric values default to 2
        decimal places (e.g. ``1`` → ``1.00``)."""
        cf = self._cell_formats.get((row, col))
        nf = cf.number_format if cf else None
        if not nf:
            nf = self._col_formats.get(col, None)
        if nf == "Text" or not text:
            return text
        # Default: display numbers with 2 decimal places.
        if not nf or nf == "General":
            try:
                val = float(text)
                return f"{val:.2f}"
            except (ValueError, TypeError):
                return text
        return _format_value(text, nf)

    # ── Cell formatting (fill + borders) ───────────────────────────
    def set_cell_bg(self, row: int, col: int,
                    color_hex: Optional[str]):
        """Set the background colour of a single cell."""
        from .cellformat import CellFormat
        cf = self._cell_formats.setdefault((row, col), CellFormat())
        cf.bg_color = color_hex
        self.table.blockSignals(True)
        it = self.table.item(row, col)
        if it is None:
            it = QTableWidgetItem("")
            self.table.setItem(row, col, it)
        if color_hex:
            it.setBackground(QColor(color_hex))
        else:
            it.setBackground(QBrush())   # reset to default
        self.table.blockSignals(False)
        if cf.is_empty():
            self._cell_formats.pop((row, col), None)

    def set_cell_borders(self, row: int, col: int,
                         sides: dict):
        """Set borders on a cell.

        *sides* maps side names ('top', 'bottom', 'left', 'right')
        to a BorderSpec or None (to remove).
        """
        from .cellformat import CellFormat
        cf = self._cell_formats.setdefault((row, col), CellFormat())
        for side, spec in sides.items():
            setattr(cf, f"border_{side}", spec)
        if cf.is_empty():
            self._cell_formats.pop((row, col), None)
        # Redraw affected area.
        self.table.viewport().update()

    def clear_cell_format(self, row: int, col: int):
        """Remove all formatting from a cell."""
        import copy
        old_fmt = self._cell_formats.get((row, col))
        if old_fmt is None:
            return  # nothing to clear
        if self._undo_stack is not None:
            from .undo_commands import ClearFormatCmd
            self._undo_stack.push(
                ClearFormatCmd(self, {(row, col): copy.deepcopy(old_fmt)}))
        else:
            self._cell_formats.pop((row, col), None)
            self.table.blockSignals(True)
            it = self.table.item(row, col)
            if it:
                it.setBackground(QBrush())
            self.table.blockSignals(False)
            self.table.viewport().update()

    # ── Headers ──────────────────────────────────────────────────────
    def _refresh_headers(self):
        # Column headers: plain "A" for undesignated columns,
        # "B(x1)", "C(y1)", "D(y1)", "E(x2)", "F(y2)", ... for designated.
        n = self.table.columnCount()
        x_num = 0       # current X group number
        col_labels = []  # (desig_upper, group_number) per column
        for i in range(n):
            desig = self._col_designations.get(i, "None").upper()
            if desig == "X":
                x_num += 1
            col_labels.append((desig, x_num))
        labels = []
        for i in range(n):
            letter = col_index_to_letter(i)
            d, num = col_labels[i]
            if d == "NONE":
                labels.append(letter)
            else:
                labels.append(f"{letter}({d.lower()}{num})")
        self.table.setHorizontalHeaderLabels(labels)
        # Row headers: 1, 2, 3...
        row_labels = [str(i + 1) for i in range(self.table.rowCount())]
        self.table.setVerticalHeaderLabels(row_labels)

    # Excel's hard limit on columns; never grow past this.
    MAX_COLS = 16384

    def _ensure_columns_fill_viewport(self):
        """Grow the column count so columns always fill the viewport,
        even when zoomed far out.  Keeps a small buffer past the edge so
        the grid never shows empty space to the right.  Never shrinks."""
        header = self.table.horizontalHeader()
        vp_w = self.table.viewport().width()
        if vp_w <= 0:
            return
        # Width of the columns currently laid out, plus the default size
        # for any beyond (interactive resizes are honoured via length()).
        used = header.length()
        col_w = max(1, header.defaultSectionSize())
        cur = self.table.columnCount()
        if used >= vp_w:
            # Already wider than the viewport; only top up the buffer.
            extra_needed = 0
        else:
            extra_needed = (vp_w - used) // col_w + 5
        target = min(self.MAX_COLS, cur + extra_needed)
        if target > cur:
            self.table.setColumnCount(target)
            self._refresh_headers()

    def _on_hscroll(self, value):
        """Add more columns when the user scrolls near the right edge."""
        sb = self.table.horizontalScrollBar()
        if sb.maximum() > 0 and value >= sb.maximum() - 1:
            cur = self.table.columnCount()
            target = min(self.MAX_COLS, cur + 20)
            if target > cur:
                self.table.setColumnCount(target)
                self._refresh_headers()

    # ── Cell ref display ─────────────────────────────────────────────
    def _on_current_cell_changed(self, row, col, prev_row, prev_col):
        self._update_sel_overlay()
        # Reset Shift+Arrow anchor when navigating normally.
        self._sel_anchor = None
        self._sel_cursor = None
        # Clear formula highlights when navigating away (unless in
        # formula entry mode where clicking inserts a ref).
        if self._formula_entry_cell is None:
            self._clear_ref_highlights()

        if row < 0 or col < 0:
            if self._formula_entry_cell is None:
                self._cell_ref_label.setText("")
                self._formula_bar.clear()
            return

        # Don't overwrite formula bar when actively editing a formula
        # (click-to-insert-ref or arrow-key nav).
        if self._formula_entry_cell is not None:
            return

        # Also check for inline editor with "=" text.
        editor = self._find_inline_editor()
        if editor and editor.text().startswith("="):
            return

        ref = f"{col_index_to_letter(col)}{row + 1}"
        self._cell_ref_label.setText(ref)
        # Show formula if cell has one, otherwise show value.
        formula = self._cell_formulas.get((row, col))
        if formula:
            self._formula_bar.set_python_mode(is_python_source(formula))
            self._formula_bar._py_badge.set_loop(self._py_loops.get((row, col)))
            self._formula_bar.set_loop_active(
                (row, col) in self._py_loops)
            self._formula_bar.setText(formula)
        else:
            self._formula_bar.set_python_mode(False)
            it = self.table.item(row, col)
            self._formula_bar.setText(it.text() if it else "")

    def _on_cell_clicked(self, row, col):
        """Open a validation dropdown when its ▼ arrow is clicked.

        Only the arrow region (right edge) triggers the popup, so a plain
        click still just selects the cell (e.g. to copy it)."""
        # Pop-out "Pick cell" mode: insert this cell's ks() ref instead.
        if getattr(self, "_py_pick_active", False) and \
                getattr(self, "_py_dialog", None):
            ref = f"{col_index_to_letter(col)}{row + 1}"
            self._py_dialog.insert_ref(ref)
            self._py_dialog.end_pick()
            self._py_pick_active = False
            return
        if (row, col) in self._cell_buttons:
            from .cell_buttons import click_button
            click_button(self, row, col)
            return
        if (row, col) not in self._cell_dropdowns:
            return
        from PyQt5.QtGui import QCursor
        vp = self.table.viewport()
        pos = vp.mapFromGlobal(QCursor.pos())
        right = (self.table.columnViewportPosition(col)
                 + self.table.columnWidth(col))
        if pos.x() >= right - 18:
            from .insert_ops import show_dropdown_for_cell
            show_dropdown_for_cell(self, row, col)

    def _on_cell_double_clicked(self, row, col):
        """Show formula ref highlights or dropdown when entering edit mode."""
        # Show dropdown popup if cell has one.
        dd = self._cell_dropdowns.get((row, col))
        if dd:
            from .insert_ops import show_dropdown_for_cell
            show_dropdown_for_cell(self, row, col)
            return
        formula = self._cell_formulas.get((row, col))
        if formula:
            self._update_ref_highlights(formula)
            # Show the formula in the formula bar.
            self._formula_bar.setText(formula)

    # ── Cell editing ─────────────────────────────────────────────────
    # ── Multi-select resize sync ──────────────────────────────────────
    def _selected_columns(self) -> set:
        """Return set of column indices that are part of the selection."""
        cols = set()
        for rng in self.table.selectedRanges():
            for c in range(rng.leftColumn(), rng.rightColumn() + 1):
                cols.add(c)
        return cols

    def _selected_rows(self) -> set:
        """Return set of row indices that are part of the selection."""
        rows = set()
        for rng in self.table.selectedRanges():
            for r in range(rng.topRow(), rng.bottomRow() + 1):
                rows.add(r)
        return rows

    def _on_column_resized(self, col, old_size, new_size):
        if self._resizing_sections:
            return
        # Snapshot the dragged column if we don't have one yet.
        if self._col_resize_snap is None:
            self._col_resize_snap = {col: old_size}
        elif col not in self._col_resize_snap:
            self._col_resize_snap[col] = old_size
        # Sync to other selected columns.
        sel_cols = self._selected_columns()
        if col in sel_cols and len(sel_cols) >= 2:
            self._resizing_sections = True
            for c in sel_cols:
                if c != col:
                    if c not in self._col_resize_snap:
                        self._col_resize_snap[c] = self.table.columnWidth(c)
                    self.table.setColumnWidth(c, new_size)
            self._resizing_sections = False

    def _on_row_resized(self, row, old_size, new_size):
        if self._resizing_sections:
            return
        if self._row_resize_snap is None:
            self._row_resize_snap = {row: old_size}
        elif row not in self._row_resize_snap:
            self._row_resize_snap[row] = old_size
        sel_rows = self._selected_rows()
        if row in sel_rows and len(sel_rows) >= 2:
            self._resizing_sections = True
            for r in sel_rows:
                if r != row:
                    if r not in self._row_resize_snap:
                        self._row_resize_snap[r] = self.table.rowHeight(r)
                    self.table.setRowHeight(r, new_size)
            self._resizing_sections = False

    def _finish_section_resize(self):
        """Push undo command for completed column/row resize."""
        if self._col_resize_snap is not None:
            old = self._col_resize_snap
            new = {c: self.table.columnWidth(c) for c in old}
            if old != new and self._undo_stack is not None:
                self._undo_stack.push(
                    ResizeSectionsCmd(self, old, new, 'col',
                                     "Resize columns"))
            self._col_resize_snap = None
        if self._row_resize_snap is not None:
            old = self._row_resize_snap
            new = {r: self.table.rowHeight(r) for r in old}
            if old != new and self._undo_stack is not None:
                self._undo_stack.push(
                    ResizeSectionsCmd(self, old, new, 'row',
                                     "Resize rows"))
            self._row_resize_snap = None

    def _on_cell_changed(self, row, col):
        # Re-entrancy depth guard.  Normal programmatic writes block
        # signals, so _on_cell_changed should never nest deeply.  A
        # self-referential or overlapping array spill (a formula whose
        # spill output feeds its own input) can re-enter this handler
        # without bound, overflowing the *native* stack and aborting the
        # process with STATUS_STACK_BUFFER_OVERRUN (0xC0000409) — a crash
        # faulthandler cannot catch.  Cap the depth so a pathological
        # cascade stops gracefully instead of killing the app.
        depth = getattr(self, "_cell_changed_depth", 0)
        if depth >= 40:
            return
        self._cell_changed_depth = depth + 1
        try:
            self._on_cell_changed_impl(row, col)
        finally:
            self._cell_changed_depth = depth

    def _on_cell_changed_impl(self, row, col):
        it = self.table.item(row, col)
        # A checkbox click changes CheckStateRole, not the text, so the
        # cell's value has to be mirrored across before anything reads
        # it.  Without this a checkbox is decoration: formulas and =PY
        # cells both see an empty cell however it is ticked.
        if it is not None and it.data(Qt.CheckStateRole) is not None:
            want = "TRUE" if it.checkState() == Qt.Checked else "FALSE"
            if it.text() != want:
                self.table.blockSignals(True)
                it.setText(want)
                self.table.blockSignals(False)
        new_text = it.text() if it else ""
        old_text = self._shadow.get((row, col), "")

        # Detect formula
        dec = self._cell_decimals(row, col)
        if new_text == "=":
            # Bare "=" committed (user typed = then clicked away).
            # Enter formula mode so the next click inserts a cell ref.
            self._formula_entry_cell = (row, col)
            self._formula_bar.blockSignals(True)
            self._formula_bar.setText("=")
            self._formula_bar.blockSignals(False)
            self._formula_bar.setFocus()
            self._formula_bar.setCursorPosition(1)
            # Restore cell to empty (don't evaluate bare =).
            self.table.blockSignals(True)
            if it:
                it.setText("")
            self.table.blockSignals(False)
            self._shadow[(row, col)] = ""
            return
        if is_python_source(new_text):
            if not strip_marker(new_text).strip():
                # "=PY" with no code yet — switch the bar to Python mode
                # and let the user type code there.
                self.table.blockSignals(True)
                if it:
                    it.setText("")
                self.table.blockSignals(False)
                self._shadow[(row, col)] = ""
                self._cell_formulas.pop((row, col), None)
                self._formula_entry_cell = (row, col)
                self._formula_bar.set_python_mode(True)
                self._formula_bar.blockSignals(True)
                self._formula_bar.setText(PY_MARKER + "\n")
                self._formula_bar.blockSignals(False)
                self._formula_bar.setFocus()
                self._formula_bar.setCursorPosition(len(PY_MARKER) + 1)
                return
            self._cell_formulas[(row, col)] = new_text
            self._register_py_deps(row, col, new_text)
            try:
                display = self._evaluate_python(new_text, row, col, dec)
            except Exception:
                import traceback
                display = "#PYERR"
                self._py_errors[(row, col)] = traceback.format_exc()
            self.table.blockSignals(True)
            if it is None:
                it = QTableWidgetItem(display)
                self.table.setItem(row, col, it)
            else:
                it.setText(display)
            self.table.blockSignals(False)
            new_text = display
        elif new_text.startswith("="):
            self._cell_formulas[(row, col)] = new_text
            self._register_deps(row, col, new_text)
            result = self._evaluate_formula(new_text, row, col, dec)
            display = str(result)
            # Apply per-cell number format to the computed result.
            display = self._apply_cell_number_format(
                display, row, col)
            self.table.blockSignals(True)
            if it is None:
                it = QTableWidgetItem(display)
                self.table.setItem(row, col, it)
            else:
                it.setText(display)
            self.table.blockSignals(False)
            new_text = display
        else:
            self._cell_formulas.pop((row, col), None)
            self._unregister_deps(row, col)
            # Format plain numbers (strip trailing zeros).
            if new_text:
                try:
                    v = float(new_text)
                    formatted = str(_format_number(v, dec))
                    if formatted != new_text:
                        self.table.blockSignals(True)
                        it.setText(formatted)
                        self.table.blockSignals(False)
                        new_text = formatted
                except ValueError:
                    pass
            # Apply per-cell number format.
            new_text = self._apply_cell_number_format(
                new_text, row, col)
            if it and it.text() != new_text:
                self.table.blockSignals(True)
                it.setText(new_text)
                self.table.blockSignals(False)

        self._shadow[(row, col)] = new_text

        # Collaborators' edits (live sharing) are not ours to undo.
        if (self._undo_stack is not None and old_text != new_text
                and not getattr(self, "_collab_applying", False)):
            cmd = CellEditCmd(self, row, col, old_text, new_text)
            self._undo_stack.push(cmd)

        if not self._suppress_recalc_signals:
            self.data_changed.emit(col)

        # Repaint any sparklines that reference this column.
        for (sr, sc), sp in self._fmt_delegate._sparklines.items():
            if sp.get("col") == col:
                idx = self.table.model().index(sr, sc)
                self.table.update(idx)

        # Recalculate any cells that depend on this one.
        self._recalc_dependents(row, col)
        # Refresh cross-sheet formulas elsewhere that may read this cell.
        self._refresh_cross_sheet()

    # ── Dependency tracking ──────────────────────────────────────────
    def _register_deps(self, row, col, formula):
        """Parse *formula* for cell refs and register (row, col) as
        a dependent of each referenced cell."""
        self._unregister_deps(row, col)
        refs = self._parse_cell_refs(formula)
        for ref_key in refs:
            self._dependents.setdefault(ref_key, set()).add((row, col))
        # Track cross-sheet formula cells so the workbook can refresh them.
        if _XREF_PATTERN.search(formula or ""):
            self._xref_cells.add((row, col))
        else:
            self._xref_cells.discard((row, col))

    def _register_py_deps(self, row, col, source):
        """Register dependencies for a =PY cell from its xl()/cell() refs."""
        self._unregister_deps(row, col)
        has_xref = False
        for ref in extract_refs(strip_marker(source)):
            if "!" in ref:
                has_xref = True
                continue
            for ref_key in self._parse_cell_refs("=" + ref):
                self._dependents.setdefault(ref_key, set()).add((row, col))
        if has_xref:
            self._xref_cells.add((row, col))
        else:
            self._xref_cells.discard((row, col))

    def _unregister_deps(self, row, col):
        """Remove (row, col) from all dependency sets."""
        key = (row, col)
        self._xref_cells.discard(key)
        for deps in self._dependents.values():
            deps.discard(key)

    def _recalc_dependents(self, row, col, visited=None,
                           decimals=None):
        """Re-evaluate every formula cell that transitively depends on
        (row, col), in topological order. See _recalc_from_seeds."""
        self._recalc_from_seeds([(row, col)], decimals=decimals)

    def _recalc_from_seeds(self, seeds, decimals=None, exclude=None):
        """Re-evaluate every formula cell that transitively depends on
        any cell in *seeds*, in topological order.

        *exclude* is a set of (row, col) cells to skip evaluating — used
        so a =PY cell that wrote its own inputs via ks_set does not
        re-trigger itself.

        Evaluating in dependency order is essential for aggregates: a
        cell like SUM(K2:K3002) must be recomputed only after *all* of
        its K inputs have updated, not after the first one (which a
        naive depth-first cascade would do, leaving the sum stale).

        Seeding from several cells at once (rather than one recalc per
        changed cell) avoids re-evaluating the shared downstream graph
        multiple times — important for the Solver, which changes many
        variable cells per objective evaluation.

        *decimals* overrides per-cell precision when set (used by the
        Solver to keep full precision during optimisation).
        """
        # 1. Collect all transitively-affected formula cells.
        affected = set()
        stack = list(seeds)
        while stack:
            for dep in self._dependents.get(stack.pop(), ()):
                if dep not in affected:
                    affected.add(dep)
                    stack.append(dep)
        if not affected:
            return

        # 2. Topologically order them. Edge u -> v means v depends on u
        #    (v is in _dependents[u]); evaluate u before v. The seed
        #    cell is not in *affected*, so cells depending only on it
        #    start with in-degree 0.
        indeg = {k: 0 for k in affected}
        adj = {k: [] for k in affected}
        for u in affected:
            for v in self._dependents.get(u, ()):
                if v in affected:
                    adj[u].append(v)
                    indeg[v] += 1
        queue = [k for k in affected if indeg[k] == 0]
        order = []
        while queue:
            u = queue.pop()
            order.append(u)
            for v in adj[u]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    queue.append(v)
        # Append any cells left in a dependency cycle (best effort).
        if len(order) < len(affected):
            order.extend(k for k in affected if k not in set(order))

        # 3. Evaluate in order.
        changed_cols = set()
        for (dr, dc) in order:
            if exclude and (dr, dc) in exclude:
                continue
            formula = self._cell_formulas.get((dr, dc))
            if not formula:
                continue
            dec = (decimals if decimals is not None
                   else self._cell_decimals(dr, dc))
            if is_python_source(formula):
                try:
                    result = self._evaluate_python(formula, dr, dc, dec)
                except Exception:
                    import traceback
                    result = "#PYERR"
                    self._py_errors[(dr, dc)] = traceback.format_exc()
            else:
                result = str(self._evaluate_formula(formula, dr, dc, dec))
            # Apply per-cell number format (skip during solver).
            if decimals is None and not is_python_source(formula):
                result = self._apply_cell_number_format(result, dr, dc)
            self.table.blockSignals(True)
            it = self.table.item(dr, dc)
            if it is None:
                it = QTableWidgetItem(result)
                self.table.setItem(dr, dc, it)
            else:
                it.setText(result)
            self._shadow[(dr, dc)] = result
            self.table.blockSignals(False)
            changed_cols.add(dc)
        # Notify charts about columns that changed via formula recalc.
        if not self._suppress_recalc_signals:
            for c in changed_cols:
                self.data_changed.emit(c)

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

    # ── Formula entry mode ─────────────────────────────────────────
    def _on_formula_bar_text(self, text):
        """Enter formula mode when the bar text starts with '='."""
        if text.startswith("=") and self._formula_bar.hasFocus():
            if self._formula_entry_cell is None:
                r = self.table.currentRow()
                c = self.table.currentColumn()
                if r >= 0 and c >= 0:
                    self._formula_entry_cell = (r, c)
            wb = self._workbook()
            if wb is not None:
                wb.set_active_formula(self)
            self._update_ref_highlights(text)
        elif not text.startswith("="):
            self._formula_entry_cell = None
            wb = self._workbook()
            if wb is not None:
                wb.clear_active_formula(self)
            self._clear_ref_highlights()

    def _exit_formula_mode(self):
        self._formula_entry_cell = None
        self._inline_formula_text = None
        self._inline_formula_cell = None
        self._inline_formula_pos = None
        self._arrow_nav_active = False
        self._arrow_nav_pos = None
        self._arrow_nav_ref_span = None
        if self._ref_drag is not None or self._pick_drag is not None:
            self._ref_drag = None
            self._pick_drag = None
            self._release_drag_grab()
        wb = self._workbook()
        if wb is not None:
            wb.clear_active_formula(self)
        self._clear_ref_highlights()
        # Restore formula bar to the current cell's stored value
        # and return focus to the grid so the cell is active again.
        row = self.table.currentRow()
        col = self.table.currentColumn()
        self._formula_bar.blockSignals(True)
        if row >= 0 and col >= 0:
            formula = self._cell_formulas.get((row, col))
            if formula:
                self._formula_bar.setText(formula)
            else:
                it = self.table.item(row, col)
                self._formula_bar.setText(it.text() if it else "")
        else:
            self._formula_bar.clear()
        self._formula_bar.blockSignals(False)
        # Restore the cell's display text (discard partial formula).
        if row >= 0 and col >= 0:
            old_text = self._shadow.get((row, col), "")
            self.table.blockSignals(True)
            it = self.table.item(row, col)
            if it:
                it.setText(old_text)
            self.table.blockSignals(False)
        self.table.setFocus()

    def _open_insert_function(self):
        """Open the Insert Function dialog and insert the chosen
        function into the formula bar."""
        from .formulas import InsertFunctionDialog
        dlg = InsertFunctionDialog(self)
        if dlg.exec_() == dlg.Accepted and dlg.selected_function:
            fn = dlg.selected_function
            bar = self._formula_bar
            bar.setText(f"={fn}()")
            bar.setFocus()
            bar.setCursorPosition(len(bar.text()) - 1)

    def _open_python_popout(self):
        """Open a larger, non-modal editor for the active cell's program.

        Running inside the dialog applies the code to the cell and shows
        the result/output without closing the window, so the user can
        iterate (and watch embedded plots appear on the grid).
        """
        from .python_engine import (
            PythonCellDialog, is_python_source, strip_marker,
        )
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        row, col = idx.row(), idx.column()
        ref = f"{col_index_to_letter(col)}{row + 1}"
        bar_text = self._formula_bar.text()
        if is_python_source(bar_text):
            code = strip_marker(bar_text)
        else:
            src = self._cell_formulas.get((row, col), "")
            code = strip_marker(src) if is_python_source(src) else ""
        old = getattr(self, "_py_dialog", None)
        if old is not None:
            old.close()
        dlg = PythonCellDialog(
            self, code, ref,
            run_cb=lambda c: self._run_python_from_dialog(row, col, c),
            help_cb=self._py_help,
            pick_cb=self._set_py_pick,
            loop_period_cb=self._on_loop_period,
            loop_play_cb=self._on_loop_play,
            loop_stop_cb=self._on_loop_stop,
            loop_active=(row, col) in self._py_loops)
        # Expose the runtime for the editor's autocomplete namespace.
        dlg._py_runtime_ref = self._py_runtime()
        self._py_dialog = dlg
        self._py_pick_active = False
        dlg.finished.connect(self._on_py_dialog_finished)
        dlg.show()
        dlg.raise_()

    def _on_py_dialog_finished(self, *_):
        self._py_dialog = None
        self._py_pick_active = False

    def _set_py_pick(self, active):
        """Arm/disarm 'click a cell to insert ks() ref' for the pop-out."""
        self._py_pick_active = bool(active)

    def _run_python_from_dialog(self, row, col, code):
        """Commit *code* to (row, col) as a =PY cell, run it, and return a
        result dict for the pop-out dialog's output pane."""
        text = PY_MARKER + "\n" + code
        self.table.blockSignals(True)
        it = self.table.item(row, col)
        if it is None:
            it = QTableWidgetItem()
            self.table.setItem(row, col, it)
        it.setText(text)
        self.table.blockSignals(False)
        self._on_cell_changed(row, col)
        # Keep the formula bar in sync if this is the active cell.
        cur = self.table.currentIndex()
        if cur.isValid() and (cur.row(), cur.column()) == (row, col):
            self._formula_bar.set_python_mode(True)
            self._formula_bar.blockSignals(True)
            self._formula_bar.setText(text)
            self._formula_bar.blockSignals(False)
        out_it = self.table.item(row, col)
        return {
            "result": out_it.text() if out_it is not None else "",
            "error": self._py_errors.get((row, col)),
            "stdout": self._py_stdout.get((row, col), ""),
            "has_plot": (row, col) in self._py_figures,
        }

    # ── Python auto-refresh loops ────────────────────────────────────
    def _set_py_loop(self, row, col, secs):
        """Set (or clear, when *secs* is falsy) the auto-refresh interval
        for a =PY cell, then (re)start or stop the loop timer."""
        if secs:
            self._py_loops[(row, col)] = float(secs)
            self._py_loop_saved[(row, col)] = float(secs)
            import time
            self._py_loop_last[(row, col)] = time.monotonic()
            self._start_py_loops()
        else:
            self._py_loops.pop((row, col), None)
            self._py_loop_last.pop((row, col), None)
            if not self._py_loops:
                self._stop_py_loops()
        # Refresh the cell badge and the formula bar badge.
        idx = self.table.model().index(row, col)
        self.table.update(idx)
        cur = self.table.currentIndex()
        if cur.isValid() and (cur.row(), cur.column()) == (row, col):
            self._formula_bar._py_badge.set_loop(self._py_loops.get((row, col)))

    def _start_py_loops(self):
        """Start the timer that re-runs due =PY loop cells.  The tick rate
        tracks the shortest loop period so sub-second loops (0.1 s, 0.5 s)
        fire on time, clamped to [50 ms, 1000 ms]."""
        if self._py_loop_timer is None:
            self._py_loop_timer = QTimer(self)
            self._py_loop_timer.timeout.connect(self._py_loop_tick)
        if self._py_loops:
            shortest = min(self._py_loops.values())
            interval = int(max(50, min(1000, shortest * 1000)))
            self._py_loop_timer.setInterval(interval)
            if not self._py_loop_timer.isActive():
                self._py_loop_timer.start()

    def _stop_py_loops(self):
        if self._py_loop_timer is not None:
            self._py_loop_timer.stop()

    def _py_loop_custom(self, row, col):
        """Prompt for a custom loop interval (seconds) for a =PY cell."""
        cur = float(self._py_loops.get((row, col), 10))
        secs, ok = QInputDialog.getDouble(
            self, "Python loop", "Re-run this cell every (seconds):",
            cur, 0.1, 86400, 1)
        if ok:
            self._set_py_loop(row, col, secs)

    # ── Formula-bar loop buttons ─────────────────────────────────────

    def _on_loop_period(self):
        """Set loop period for the current =PY cell via a popup menu.

        Only sets the period — does not start or stop the loop."""
        cur = self.table.currentIndex()
        if not cur.isValid():
            return
        row, col = cur.row(), cur.column()
        src = self._cell_formulas.get((row, col))
        if not is_python_source(src):
            return
        from PyQt5.QtWidgets import QMenu, QAction
        menu = QMenu(self)
        saved = self._py_loop_saved.get((row, col))
        presets = [
            ("0.1 s", 0.1), ("0.2 s", 0.2), ("0.5 s", 0.5),
            ("1 s", 1), ("2 s", 2), ("5 s", 5), ("10 s", 10),
            ("30 s", 30), ("1 min", 60), ("5 min", 300), ("15 min", 900),
        ]
        for label, secs in presets:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(saved is not None
                           and abs(saved - secs) < 0.01)
            act.triggered.connect(
                lambda checked, s=secs: self._save_loop_period(row, col, s))
        menu.addSeparator()
        custom_act = menu.addAction("Custom\u2026")
        custom_act.triggered.connect(
            lambda: self._save_loop_period_custom(row, col))
        btn = self._formula_bar._loop_period_btn
        menu.exec_(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _save_loop_period(self, row, col, secs):
        """Remember the period. If the loop is already running, update it."""
        self._py_loop_saved[(row, col)] = float(secs)
        if (row, col) in self._py_loops:
            # Loop is running — update the live interval.
            self._set_py_loop(row, col, secs)

    def _save_loop_period_custom(self, row, col):
        """Prompt for a custom interval and remember it."""
        cur = float(self._py_loop_saved.get((row, col), 1))
        secs, ok = QInputDialog.getDouble(
            self, "Python loop", "Re-run this cell every (seconds):",
            cur, 0.1, 86400, 1)
        if ok:
            self._save_loop_period(row, col, secs)

    def _on_loop_play(self):
        """Start the loop for the current =PY cell using the saved period."""
        cur = self.table.currentIndex()
        if not cur.isValid():
            return
        row, col = cur.row(), cur.column()
        src = self._cell_formulas.get((row, col))
        if not is_python_source(src):
            return
        secs = self._py_loop_saved.get((row, col), 1.0)
        self._set_py_loop(row, col, secs)
        self._sync_loop_ui(True)

    def _on_loop_stop(self):
        """Stop the loop but keep the saved period."""
        cur = self.table.currentIndex()
        if not cur.isValid():
            return
        row, col = cur.row(), cur.column()
        # Save the current period before clearing.
        if (row, col) in self._py_loops:
            self._py_loop_saved[(row, col)] = self._py_loops[(row, col)]
        self._set_py_loop(row, col, None)
        self._sync_loop_ui(False)

    def _sync_loop_ui(self, active: bool):
        """Keep formula-bar and pop-out dialog loop state in sync."""
        self._formula_bar.set_loop_active(active)
        dlg = getattr(self, "_py_dialog", None)
        if dlg is not None:
            dlg.set_loop_active(active)

    def _py_loop_tick(self):
        """Re-run any =PY loop cell whose interval has elapsed."""
        if not self._py_loops or self._py_loop_running:
            return
        import time
        now = time.monotonic()
        editor = self._find_inline_editor()
        cur = self.table.currentIndex()
        for (r, c), secs in list(self._py_loops.items()):
            src = self._cell_formulas.get((r, c))
            if not is_python_source(src):
                self._py_loops.pop((r, c), None)   # cell no longer =PY
                continue
            if now - self._py_loop_last.get((r, c), 0) < secs:
                continue
            # Don't clobber the cell while the user is editing it.
            if (editor is not None and cur.isValid()
                    and (cur.row(), cur.column()) == (r, c)):
                continue
            self._py_loop_last[(r, c)] = now
            self._py_loop_running = True
            try:
                self._reeval_formula_cell(r, c)    # re-run, no undo push
                self._recalc_dependents(r, c)
            except Exception:
                pass
            finally:
                self._py_loop_running = False

    def _py_help(self):
        """Open the Python examples (HTML page, or the in-app dialog)."""
        import os
        from . import resources
        page = resources.package_file("python_help.html")
        if os.path.exists(page):
            from PyQt5.QtCore import QUrl
            from PyQt5.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(page))
        else:
            from .python_engine import show_python_help
            show_python_help(self)

    def _apply_formula_bar(self):
        self._formula_entry_cell = None
        self._inline_formula_text = None
        self._inline_formula_cell = None
        self._inline_formula_pos = None
        self._arrow_nav_active = False
        self._arrow_nav_pos = None
        self._arrow_nav_ref_span = None
        if self._ref_drag is not None or self._pick_drag is not None:
            self._ref_drag = None
            self._pick_drag = None
            self._release_drag_grab()
        wb = self._workbook()
        if wb is not None:
            wb.clear_active_formula(self)
        self._clear_ref_highlights()
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

        # Move to next row (Excel-style Enter behavior).
        next_row = row + 1
        if next_row < self.row_count():
            self.table.setCurrentCell(next_row, col)
        self.table.setFocus()

    # ── Formula reference highlighting ─────────────────────────────
    # Patterns for ranges (A1:B10) and single refs (A1, $B$5), and the
    # function names that are not refs; shared with core.refs.
    _RANGE_PATTERN = RANGE_PATTERN
    _REF_PATTERN = REF_PATTERN
    _FUNC_NAMES = function_names()

    def _parse_cell_refs(self, formula_text: str):
        """Every (row, col) *formula_text* reads (see core.refs)."""
        return parse_cell_refs(formula_text)

    def _parse_ref_tokens(self, text: str):
        """Parse *text* into a list of reference tokens, each
        ``{"span": (start, end), "c1","r1","c2","r2", "text"}`` in the
        ORIGINAL string (cross-sheet tokens blanked length-preservingly so
        spans stay valid).  Used to drag the highlights ("range finder")."""
        # Ensure the shared patterns / func-name set are compiled.
        self._parse_cell_refs("")
        text = text or ""
        masked = _XREF_PATTERN.sub(
            lambda m: " " * (m.end() - m.start()), text)
        tokens = []
        used = []
        for m in self._RANGE_PATTERN.finditer(masked):
            c1 = letter_to_col_index(m.group(1).upper())
            r1 = int(m.group(2)) - 1
            c2 = letter_to_col_index(m.group(3).upper())
            r2 = int(m.group(4)) - 1
            tokens.append({"span": (m.start(), m.end()),
                           "c1": min(c1, c2), "r1": min(r1, r2),
                           "c2": max(c1, c2), "r2": max(r1, r2),
                           "text": text[m.start():m.end()]})
            used.append((m.start(), m.end()))
        for m in self._REF_PATTERN.finditer(masked):
            if any(s <= m.start() and m.end() <= e for s, e in used):
                continue
            letters = m.group(1).upper()
            if letters in self._FUNC_NAMES:
                continue
            c = letter_to_col_index(letters)
            r = int(m.group(2)) - 1
            tokens.append({"span": (m.start(), m.end()),
                           "c1": c, "r1": r, "c2": c, "r2": r,
                           "text": text[m.start():m.end()]})
        tokens.sort(key=lambda t: t["span"][0])
        return tokens

    def _update_ref_highlights(self, text: str):
        """Parse cell refs from *text* and highlight them on the grid."""
        from .cellformat import CellFormatDelegate
        delegate = self._fmt_delegate
        refs = self._parse_cell_refs(text)
        self._ref_tokens = self._parse_ref_tokens(text)
        colors = CellFormatDelegate.REF_COLORS
        new_highlights = {}
        for i, key in enumerate(refs):
            new_highlights[key] = colors[i % len(colors)]
        old = set(delegate._ref_highlights.keys())
        delegate._ref_highlights = new_highlights
        self._ref_highlight_active = bool(new_highlights)
        # Repaint affected cells.
        dirty = old | set(new_highlights.keys())
        for (r, c) in dirty:
            idx = self.table.model().index(r, c)
            self.table.update(idx)

    def _clear_ref_highlights(self):
        """Remove all formula reference highlights."""
        if not self._ref_highlight_active:
            return
        delegate = self._fmt_delegate
        old = set(delegate._ref_highlights.keys())
        delegate._ref_highlights.clear()
        self._ref_highlight_active = False
        self._ref_tokens = []
        for (r, c) in old:
            idx = self.table.model().index(r, c)
            self.table.update(idx)

    # ── Range finder: drag a reference highlight to move it ──────────
    def _active_formula_target(self):
        """The widget holding the in-progress formula text — the live
        inline cell editor (if its text starts with '='), else the
        formula bar.  None if no formula is being entered."""
        editor = self._find_inline_editor()
        if editor is not None and editor.text().startswith("="):
            return editor
        if (self._formula_entry_cell is not None
                and self._formula_bar.text().startswith("=")):
            return self._formula_bar
        return None

    def _ref_token_rect(self, tok):
        """Viewport rect spanning a token's cell range."""
        t = self.table
        x1 = t.columnViewportPosition(tok["c1"])
        y1 = t.rowViewportPosition(tok["r1"])
        x2 = t.columnViewportPosition(tok["c2"]) + t.columnWidth(tok["c2"])
        y2 = t.rowViewportPosition(tok["r2"]) + t.rowHeight(tok["r2"])
        return QRect(x1, y1, x2 - x1, y2 - y1)

    def _ref_token_at(self, pos):
        """Index of the reference token under *pos* (viewport coords),
        else None.  Single-cell refs are fully grabbable; multi-cell
        ranges grab on the border band only (so interior clicks still
        select / insert)."""
        band = 4
        for i, tok in enumerate(self._ref_tokens):
            rect = self._ref_token_rect(tok)
            single = (tok["c1"] == tok["c2"] and tok["r1"] == tok["r2"])
            if single:
                if rect.adjusted(-band, -band, band, band).contains(pos):
                    return i
                continue
            outer = rect.adjusted(band, band, -band, -band)
            if rect.contains(pos) and not outer.contains(pos):
                return i
        return None

    def _begin_ref_drag(self, idx, event):
        # Resolve the in-progress formula text and where it lives, being
        # permissive: the formula bar, a live in-cell editor, the tracked
        # inline-edit state, or the cell's stored formula.
        is_bar = False
        cell = None
        text0 = None
        cr, cc = self.table.currentRow(), self.table.currentColumn()
        if (self._formula_entry_cell is not None
                and self._formula_bar.text().startswith("=")):
            is_bar, cell, text0 = True, self._formula_entry_cell, \
                self._formula_bar.text()
        else:
            ed = self._find_inline_editor()
            if ed is not None and ed.text().startswith("="):
                cell, text0 = (cr, cc), ed.text()
            elif (self._inline_formula_cell is not None
                    and (self._inline_formula_text or "").startswith("=")):
                cell, text0 = (self._inline_formula_cell,
                               self._inline_formula_text)
            elif (cr, cc) in self._cell_formulas:
                cell, text0 = (cr, cc), self._cell_formulas[(cr, cc)]
        if text0 is None or cell is None:
            return False
        toks = self._parse_ref_tokens(text0)
        if idx < 0 or idx >= len(toks):
            return False
        pcell = self.table.indexAt(event.pos())
        if not pcell.isValid():
            return False
        tok = toks[idx]
        self._ref_drag = {
            "is_bar": is_bar, "cell": cell, "text0": text0,
            "span0": tok["span"], "token0": tok["text"],
            "press": (pcell.row(), pcell.column()), "last_text": text0,
        }
        vp = self.table.viewport()
        vp.setCursor(Qt.SizeAllCursor)
        # Explicit grab so move/release reach us even though the press was
        # consumed (the implicit grab is unreliable while a cell editor has
        # focus).
        try:
            vp.grabMouse()
        except Exception:
            pass
        return True

    def _set_inline_cell_formula(self, r, c, text):
        """Apply a live formula to a cell directly (used while dragging a
        reference when no in-cell editor is open)."""
        self._cell_formulas[(r, c)] = text
        self._register_deps(r, c, text)
        dec = self._cell_decimals(r, c)
        res = self._apply_cell_number_format(
            str(self._evaluate_formula(text, r, c, dec)), r, c)
        self._set_cell_quiet(r, c, res)

    def _ref_drag_move(self, event):
        d = self._ref_drag
        cell = self.table.indexAt(event.pos())
        if not cell.isValid():
            return
        new_tok = shift_formula(
            d["token0"], cell.row() - d["press"][0],
            cell.column() - d["press"][1])
        s, e = d["span0"]
        new_text = d["text0"][:s] + new_tok + d["text0"][e:]
        d["last_text"] = new_text
        cur = min(len(new_text), s + len(new_tok))
        if d["is_bar"]:
            bar = self._formula_bar
            bar.blockSignals(True)
            bar.setText(new_text)
            bar.setCursorPosition(cur)
            bar.blockSignals(False)
        else:
            r, c = d["cell"]
            ed = self._find_inline_editor()
            if ed is not None:
                ed.blockSignals(True)
                ed.setText(new_text)
                ed.setCursorPosition(cur)
                ed.blockSignals(False)
            else:
                # No live editor — drive the cell's formula directly.
                self._set_inline_cell_formula(r, c, new_text)
            # Keep tracked inline state in sync so the result survives an
            # editor that was destroyed by the press.
            self._inline_formula_cell = (r, c)
            self._inline_formula_text = new_text
            self._inline_formula_pos = cur
        self._update_ref_highlights(new_text)

    def _release_drag_grab(self):
        try:
            self.table.viewport().releaseMouse()
        except Exception:
            pass

    def _end_ref_drag(self):
        d = self._ref_drag
        self._ref_drag = None
        self.table.viewport().unsetCursor()
        self._release_drag_grab()
        if not d or d["is_bar"]:
            return  # the bar / live editor keeps the text; Enter commits
        if self._find_inline_editor() is not None:
            return  # still editing in-cell; Enter commits as usual
        # No editor open — commit the moved formula to the cell and recalc.
        r, c = d["cell"]
        self._set_inline_cell_formula(r, c, d["last_text"])
        self._recalc_dependents(r, c)
        self._refresh_cross_sheet()
        self._clear_ref_highlights()

    # ── Formula evaluation (basic) ───────────────────────────────────
    def _evaluate_formula(self, formula: str, row: int, col: int,
                          decimals: int = 3):
        """Evaluate a cell formula (compiled once, then cached).

        Supports cell refs (A1, $B$5), arithmetic (A1^2), range
        functions (SUM(A1:A10)), whole-column functions (max(A)) and a
        large library of Excel-style functions.  The formula is parsed
        and compiled to a Python code object the first time it is seen;
        thereafter the cached code is evaluated directly, reading live
        cell values through the _C/_AGG/_COL helpers.
        """
        try:
            code = self._compiled_cache.get(formula)
            if code is None:
                code = self._compile_formula(formula)
                self._compiled_cache[formula] = code
            if code is False:
                return "#ERROR"
            result = eval(code, self._build_eval_ns())  # noqa: S307
            # Array spill: if the formula returns a list, write the
            # remaining elements into the cells below and return the
            # first element for the formula cell itself.
            if isinstance(result, list) and len(result) > 1:
                self._spill_array(result, row, col)
                return _format_number(result[0], decimals)
            if isinstance(result, list) and len(result) == 1:
                return _format_number(result[0], decimals)
            return _format_number(result, decimals)
        except Exception:
            return "#ERROR"

    def _spill_array(self, values, row, col):
        """Write spill values into the cells below (row+1 …) silently.

        Signals are blocked so a spill whose output overlaps the
        formula's own input range cannot re-fire ``cellChanged`` and
        recurse back into ``_on_cell_changed`` — an unbounded cascade
        that would overflow the native stack (0xC0000409).
        """
        self.table.blockSignals(True)
        try:
            for i, v in enumerate(values[1:], start=1):
                r = row + i
                if r >= self.table.rowCount():
                    self.table.setRowCount(r + 1)
                item = self.table.item(r, col)
                if item is None:
                    from PyQt5.QtWidgets import QTableWidgetItem
                    item = QTableWidgetItem()
                    self.table.setItem(r, col, item)
                item.setData(Qt.EditRole, _format_number(v))
                self._shadow[(r, col)] = item.text()
        finally:
            self.table.blockSignals(False)

    # ── Python (=PY) cell evaluation ─────────────────────────────────
    def _py_runtime(self):
        """The PythonRuntime shared across this workbook (or this sheet)."""
        from .python_engine import PythonRuntime
        wb = self._workbook()
        host = wb if wb is not None else self
        rt = getattr(host, "_py_runtime_obj", None)
        if rt is None:
            rt = PythonRuntime()
            host._py_runtime_obj = rt
        return rt

    def _sync_py_udfs(self):
        """Expose user-defined Python functions as formula UDFs.

        Functions defined in =PY cells (in the shared namespace) become
        callable from ordinary ``=`` formulas, e.g. ``=MYFUNC(A1)``.
        Built-in formula functions are never overridden.
        """
        import builtins
        import types
        rt = self._py_runtime()
        g = getattr(rt, "_globals", None)
        if not g:
            return
        self._build_eval_ns()
        ns = self._eval_ns
        lower = self._eval_ns_lower
        bi = vars(builtins)
        reserved = {"ks", "xl", "cell", "ks_set", "write", "np", "numpy",
                    "plt", "pd", "pandas", "scipy", "math"}
        for name, obj in list(g.items()):
            if (name.startswith("_") or name in reserved
                    or name in bi or isinstance(obj, types.ModuleType)
                    or not callable(obj)):
                continue
            up = name.upper()
            # Don't shadow a real built-in formula function.
            if up in ns and up not in self._py_udf_names:
                continue
            ns[name] = obj
            ns[up] = obj
            lower.setdefault(name.lower(), name)
            lower.setdefault(up.lower(), up)
            self._py_udf_names.add(up)

    def _evaluate_python(self, source, row, col, decimals=3):
        """Run a =PY cell, store its live value, and return display text."""
        from .python_engine import PyResult, badge_for, strip_marker
        self._clear_py_outputs(row, col)
        res = self._py_runtime().run(strip_marker(source), self, row, col)
        # Recalc anything depending on cells this run wrote via ks_set,
        # but never re-run THIS cell (a cell that writes back to a value
        # it also reads must not retrigger itself).
        writes = getattr(self._py_runtime(), "_last_writes", None)
        if writes and not getattr(self, "_in_py_write_recalc", False):
            self._in_py_write_recalc = True
            try:
                self._recalc_from_seeds(list(writes), exclude={(row, col)})
            finally:
                self._in_py_write_recalc = False
        if res.stdout:
            self._py_stdout[(row, col)] = res.stdout
        else:
            self._py_stdout.pop((row, col), None)
        if not res.ok:
            self._py_errors[(row, col)] = res.error
            self._cell_objects.pop((row, col), None)
            it = self.table.item(row, col)
            if it is not None:
                # Show the last traceback line as the cell tooltip.
                lines = res.error.strip().splitlines()
                last = lines[-1] if lines else "Unknown error"
                it.setToolTip(last)
            return "#PYERR"
        self._py_errors.pop((row, col), None)
        # Make any functions this cell defined callable from = formulas.
        self._sync_py_udfs()
        it = self.table.item(row, col)
        if it is not None and it.toolTip():
            it.setToolTip("")
        val = res.value
        self._cell_objects[(row, col)] = val

        if res.kind == PyResult.FIGURE:
            self._embed_py_figure(res.figure, row, col)
            return "📈 plot"
        if res.kind == PyResult.IMAGE:
            self._embed_py_image(res.value, row, col)
            return "🖼 image"
        if res.kind == PyResult.NONE:
            self._cell_objects.pop((row, col), None)
            return ""
        if res.kind == PyResult.SCALAR:
            return val if isinstance(val, str) else str(
                _format_number(val, decimals))
        if res.kind == PyResult.ARRAY1D:
            self._py_spill(val, row, col, two_d=False)
            head = val[0] if val else ""
            return head if isinstance(head, str) else str(
                _format_number(head, decimals))
        if res.kind == PyResult.ARRAY2D:
            self._py_spill(val, row, col, two_d=True)
            head = val[0][0] if (val and val[0]) else ""
            return head if isinstance(head, str) else str(
                _format_number(head, decimals))
        return badge_for(val)

    def _py_write(self, coords, value, cur_cell, written):
        """Write *value* into the grid for ks_set(); records cells in
        *written* and never overwrites *cur_cell* (the running cell)."""
        from PyQt5.QtWidgets import QTableWidgetItem
        r1, c1, r2, c2 = coords
        # Normalise *value* into a 2-D list `block`.
        block = self._py_value_to_block(value, r1, c1, r2, c2)
        was = self.table.signalsBlocked()
        self.table.blockSignals(True)
        for i, rowvals in enumerate(block):
            for j, v in enumerate(rowvals):
                r, c = r1 + i, c1 + j
                if (r, c) == cur_cell:
                    continue  # never clobber the running cell
                if r >= self.table.rowCount():
                    self.table.setRowCount(r + 1)
                if c >= self.table.columnCount():
                    continue
                it = self.table.item(r, c)
                if it is None:
                    it = QTableWidgetItem()
                    self.table.setItem(r, c, it)
                # A written literal replaces any formula/object at target.
                self._cell_formulas.pop((r, c), None)
                self._cell_objects.pop((r, c), None)
                text = v if isinstance(v, str) else str(_format_number(v))
                it.setText(text)
                self._shadow[(r, c)] = text
                if written is not None:
                    written.add((r, c))
        self.table.blockSignals(was)

    @staticmethod
    def _py_value_to_block(value, r1, c1, r2, c2):
        """Shape a ks_set value into a 2-D list for the target range."""
        try:
            import numpy as np
        except Exception:
            np = None
        single_row = (r1 == r2 and c2 > c1)
        if np is not None and isinstance(value, np.ndarray):
            if value.ndim == 0:
                return [[value.item()]]
            if value.ndim == 1:
                v = value.tolist()
                return [v] if single_row else [[x] for x in v]
            return [list(row) for row in value.tolist()]
        if isinstance(value, (list, tuple)):
            seq = list(value)
            if seq and all(isinstance(x, (list, tuple)) for x in seq):
                return [list(x) for x in seq]
            return [seq] if single_row else [[x] for x in seq]
        # Scalar — fill the whole target range.
        return [[value for _ in range(c1, c2 + 1)]
                for _ in range(r1, r2 + 1)]

    def _py_spill(self, values, row, col, two_d=False):
        """Spill a list (1-D down a column, 2-D as a block); the anchor
        cell keeps the first element.  Records written cells so a later
        re-evaluation can clear them."""
        from PyQt5.QtWidgets import QTableWidgetItem
        written = []
        rows = values if two_d else [[v] for v in values]
        was_blocked = self.table.signalsBlocked()
        self.table.blockSignals(True)
        for i, rowvals in enumerate(rows):
            for j, v in enumerate(rowvals):
                if i == 0 and j == 0:
                    continue  # anchor handled by caller
                r, c = row + i, col + j
                if r >= self.table.rowCount():
                    self.table.setRowCount(r + 1)
                if c >= self.table.columnCount():
                    continue
                it = self.table.item(r, c)
                if it is None:
                    it = QTableWidgetItem()
                    self.table.setItem(r, c, it)
                text = v if isinstance(v, str) else str(_format_number(v))
                it.setText(text)
                self._shadow[(r, c)] = text
                written.append((r, c))
        self.table.blockSignals(was_blocked)
        if written:
            self._py_spills[(row, col)] = written

    def _clear_py_outputs(self, row, col):
        """Clear the previous spill range and embedded figure for a cell."""
        spilled = self._py_spills.pop((row, col), ())
        if spilled:
            was_blocked = self.table.signalsBlocked()
            self.table.blockSignals(True)
            for (r, c) in spilled:
                it = self.table.item(r, c)
                if it is not None:
                    it.setText("")
                    self._shadow[(r, c)] = ""
            self.table.blockSignals(was_blocked)
        fig = self._py_figures.pop((row, col), None) if hasattr(
            self, "_py_figures") else None
        if fig is not None:
            if fig in self._images:
                self._images.remove(fig)
            fig.deleteLater()

    def _embed_py_figure(self, figure, row, col):
        """Render a matplotlib Figure to an EmbeddedImage near the cell."""
        from io import BytesIO
        from PyQt5.QtGui import QPixmap
        from .embedded_image import EmbeddedImage
        if not hasattr(self, "_py_figures"):
            self._py_figures = {}
        buf = BytesIO()
        try:
            # Render at a higher DPI so the embedded plot stays sharp even
            # when enlarged by dragging.
            figure.savefig(buf, format="png", dpi=140, bbox_inches="tight")
        except Exception:
            return
        pm = QPixmap()
        pm.loadFromData(buf.getvalue(), "PNG")
        if pm.isNull():
            return
        img = EmbeddedImage(pm, self.table.viewport())
        # Keep the source figure so the image can export true vector
        # SVG/PDF (a saved/reloaded image falls back to raster).
        img.set_source_figure(figure)
        try:
            import matplotlib.pyplot as plt
            plt.close(figure)
        except Exception:
            pass
        self._place_py_embed(img, pm, row, col)

    def _embed_py_image(self, pixmap, row, col):
        """Embed a picture (QPixmap) produced by a =PY cell near the cell."""
        from .embedded_image import EmbeddedImage
        if pixmap is None or pixmap.isNull():
            return
        img = EmbeddedImage(pixmap, self.table.viewport())
        self._place_py_embed(img, pixmap, row, col)

    def _place_py_embed(self, img, pixmap, row, col):
        """Position a =PY plot/image overlay and size it to the rendered
        picture (capped) so it shows at a usable size by default — the
        user can still drag the handles to resize it further."""
        tw = min(pixmap.width(), 1100)
        th = min(pixmap.height(), 850)
        if tw > 0 and th > 0:
            img.resize(tw + 4, th + 4)
        x = (self.table.columnViewportPosition(col)
             + self.table.columnWidth(col) + 4)
        y = self.table.rowViewportPosition(row)
        img.move(max(0, x), max(0, y))
        img.show()
        self._images.append(img)
        self._py_figures[(row, col)] = img

    def _build_eval_ns(self):
        """Build the evaluation namespace once and cache it on self."""
        if self._eval_ns is not None:
            return self._eval_ns
        self._eval_ns = build_namespace(self)
        self._eval_ns_lower = lower_names(self._eval_ns)
        return self._eval_ns

    # Names that look like cell refs but are functions (see core.compiler).
    _CELLREF_SKIP = CELLREF_SKIP

    def _compile_formula(self, formula):
        """Compile *formula* to a reusable code object (see core.compiler)."""
        self._build_eval_ns()
        return compile_formula(formula, self._eval_ns, self._eval_ns_lower)

    # ── Cross-sheet support ──────────────────────────────────────────
    def _workbook(self):
        """Walk up to the owning WorkbookWidget, or None."""
        w = self.parent()
        while w is not None:
            if hasattr(w, "sheet_by_name") and hasattr(w, "all_sheets"):
                return w
            p = w.parent()
            if p is w:
                break
            w = p
        return None

    def _refresh_cross_sheet(self):
        wb = self._workbook()
        if wb is not None:
            wb.refresh_cross_sheet()

    def _reeval_formula_cell(self, r, c):
        """Re-evaluate one formula cell in place (used by cross-sheet
        refresh).  Leaves local-dependent cascading to the caller."""
        formula = self._cell_formulas.get((r, c))
        if not formula:
            return
        dec = self._cell_decimals(r, c)
        if is_python_source(formula):
            result = self._evaluate_python(formula, r, c, dec)
        else:
            result = self._apply_cell_number_format(
                str(self._evaluate_formula(formula, r, c, dec)), r, c)
        self._set_cell_quiet(r, c, result)

    def _pick_cross_sheet_ref(self, event):
        """If another sheet is mid-formula-entry, insert a reference to the
        clicked cell on *this* sheet into that sheet's formula bar.

        Returns True if the click was consumed."""
        wb = self._workbook()
        if wb is None:
            return False
        target = getattr(wb, "_active_formula_sheet", None)
        if (target is None or target is self
                or getattr(target, "_formula_entry_cell", None) is None):
            return False
        idx = self.table.indexAt(event.pos())
        if not idx.isValid():
            return False
        cell = col_index_to_letter(idx.column()) + str(idx.row() + 1)
        name = _quote_sheet_name(wb.name_of_sheet(self))
        ref = "{}!{}".format(name, cell)
        bar = target._formula_bar
        cp = bar.cursorPosition()
        text = bar.text()
        new_text = text[:cp] + ref + text[cp:]
        bar.setText(new_text)
        bar.setCursorPosition(cp + len(ref))
        target._update_ref_highlights(new_text)
        # Return to the originating sheet so the user can keep editing.
        wb.tabs.setCurrentWidget(target)
        bar.setFocus()
        return True

    # ── Compiled-formula runtime helpers ─────────────────────────────
    # _cell_val, _range_values, _agg_col… come from core.values.CellValues,
    # which reads cells through _cell_text().
    def _cell_text(self, r, c):
        it = self.table.item(r, c)
        return it.text() if it is not None else ""

    # ── Plot types ───────────────────────────────────────────────────
    PLOT_TYPES = [
        "Line", "Scatter", "Line+Symbol", "Bar", "Step",
        "Stem", "Histogram", "Box", "Heatmap", "3D Surface",
        "Pie", "Doughnut", "3D Pie",
    ]

    def _add_plot_submenu(self, menu, cols=None):
        """Add a Plot submenu with all plot types."""
        sel = self.selected_columns() if cols is None else cols
        label = "Plot"
        plot_menu = menu.addMenu(label)
        for pt in self.PLOT_TYPES:
            plot_menu.addAction(
                pt, lambda _=False, p=pt: self._request_plot(p))

    def selected_columns(self):
        """Return sorted list of columns with any selected cells."""
        return sorted(set(idx.column()
                          for idx in self.table.selectedIndexes()))

    # ── Right-click menus ────────────────────────────────────────────
    def _header_menu(self, pos):
        col = self.table.horizontalHeader().logicalIndexAt(pos)
        if col < 0:
            return
        sel = self.selected_columns()
        if col not in sel:
            self.table.selectColumn(col)
            sel = [col]
        menu = QMenu(self)

        # Plot submenu first (like KhervePlot)
        self._add_plot_submenu(menu, sel)
        menu.addSeparator()

        # Designation
        desig_menu = menu.addMenu("Set As")
        for d in ("X", "Y", "None"):
            desig_menu.addAction(
                d, lambda _=False, dd=d, cc=col:
                self.set_designation(cc, dd))

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

        menu.addSeparator()
        menu.addAction("Statistics on Column",
                       lambda: self._column_stats(col))

        menu.exec_(self.table.horizontalHeader().mapToGlobal(pos))

    def _row_header_menu(self, pos):
        """Context menu on the vertical (row) header."""
        row = self.table.verticalHeader().logicalIndexAt(pos)
        if row < 0:
            return
        # Ensure clicked row is part of the selection.
        sel_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        if row not in sel_rows:
            self.table.selectRow(row)
        menu = QMenu(self)
        menu.addAction("Insert Rows", self._insert_rows_from_selection)
        menu.addAction("Delete Rows", self._delete_selected_rows)
        menu.exec_(self.table.verticalHeader().mapToGlobal(pos))

    # ── Note / comment hover popup ─────────────────────────────────
    _NOTE_STYLE = (
        "QLabel {"
        "  background: #ffffa5;"
        "  border: 1px solid #c8c870;"
        "  padding: 8px 10px;"
        "  font-family: 'Segoe UI', sans-serif;"
        "  font-size: 11px;"
        "  color: #333;"
        "  min-width: 120px;"
        "  max-width: 260px;"
        "}"
    )
    _COMMENT_STYLE = (
        "QLabel {"
        "  background: #ffffff;"
        "  border: 1px solid #bbbbbb;"
        "  padding: 8px 10px;"
        "  font-family: 'Segoe UI', sans-serif;"
        "  font-size: 11px;"
        "  color: #333;"
        "  min-width: 120px;"
        "  max-width: 260px;"
        "}"
    )

    def _show_note_popup(self, row, col):
        """Show a floating sticky note for the cell."""
        note = self._cell_notes.get((row, col))
        if not note:
            self._hide_note_popup()
            return
        text = note.get("text", "") if isinstance(note, dict) else str(note)
        kind = note.get("kind", "note") if isinstance(note, dict) else "note"
        if not text:
            self._hide_note_popup()
            return

        if self._note_popup is None:
            from PyQt5.QtWidgets import QGraphicsDropShadowEffect
            self._note_popup = QLabel(self.table.viewport())
            self._note_popup.setWordWrap(True)
            self._note_popup.setMargin(0)
            shadow = QGraphicsDropShadowEffect(self._note_popup)
            shadow.setBlurRadius(12)
            shadow.setOffset(2, 2)
            shadow.setColor(QColor(0, 0, 0, 80))
            self._note_popup.setGraphicsEffect(shadow)

        self._note_popup.setStyleSheet(
            self._NOTE_STYLE if kind == "note" else self._COMMENT_STYLE)
        self._note_popup.setText(text)
        self._note_popup.adjustSize()
        # Position near the cell
        x = self.table.columnViewportPosition(col) + self.table.columnWidth(col)
        y = self.table.rowViewportPosition(row)
        # Keep within viewport
        vp = self.table.viewport()
        if x + self._note_popup.width() > vp.width():
            x = self.table.columnViewportPosition(col) - self._note_popup.width()
        if y + self._note_popup.height() > vp.height():
            y = vp.height() - self._note_popup.height()
        self._note_popup.move(max(0, x), max(0, y))
        self._note_popup.show()
        self._note_popup.raise_()

    def _hide_note_popup(self):
        if self._note_popup is not None:
            self._note_popup.hide()

    def _spell_word_at(self, pos):
        """Return (row, col, word, start, end) for the misspelled word
        under viewport point *pos*, or None."""
        from . import spellcheck
        if not (getattr(self._fmt_delegate, "_spell_enabled", False)
                and spellcheck.available()):
            return None
        idx = self.table.indexAt(pos)
        if not idx.isValid():
            return None
        row, col = idx.row(), idx.column()
        it = self.table.item(row, col)
        if it is None:
            return None
        text = it.text()
        if not spellcheck.should_check(text):
            return None
        cf = self._cell_formats.get((row, col))
        if cf and cf.wrap_text:
            return None
        from PyQt5.QtGui import QFontMetrics
        from PyQt5.QtCore import Qt
        rect = self.table.visualRect(idx).adjusted(3, 0, -3, 0)
        fm = QFontMetrics(it.font())
        align = int(it.textAlignment() or (Qt.AlignLeft | Qt.AlignVCenter))
        x = pos.x()
        for s, e, word, x0, x1 in spellcheck.iter_word_spans(
                text, fm, rect.left(), rect.width(), align):
            if x0 <= x <= x1 and spellcheck.is_misspelled(word):
                return row, col, word, s, e
        return None

    def _replace_word(self, row, col, start, end, new_word):
        """Replace text[start:end] in a cell with *new_word*."""
        it = self.table.item(row, col)
        if it is None:
            return
        old_text = it.text()
        new_text = old_text[:start] + new_word + old_text[end:]
        if self._undo_stack is not None:
            self._undo_stack.push(
                CellEditCmd(self, row, col, old_text, new_text))
        self._set_cell_quiet(row, col, new_text)

    def _cell_menu(self, pos):
        menu = QMenu(self)

        # Spelling suggestions for the word under the cursor (top).
        spell = self._spell_word_at(pos)
        if spell is not None:
            from . import spellcheck
            row, col, word, start, end = spell
            sugs = spellcheck.suggestions(word)
            if sugs:
                for sug in sugs:
                    act = menu.addAction(sug)
                    act.triggered.connect(
                        lambda _=False, s=sug: self._replace_word(
                            row, col, start, end, s))
                from PyQt5.QtGui import QFont
                bf = QFont()
                bf.setBold(True)
                for a in menu.actions():
                    a.setFont(bf)
            else:
                menu.addAction("(no suggestions)").setEnabled(False)
            menu.addAction(
                "Ignore All",
                lambda: (spellcheck.ignore_word(word),
                         self.table.viewport().update()))
            menu.addSeparator()

        # Python loop (auto-refresh) submenu — only for =PY cells.
        cidx = self.table.indexAt(pos)
        if cidx.isValid() and is_python_source(
                self._cell_formulas.get((cidx.row(), cidx.column()))):
            r0, c0 = cidx.row(), cidx.column()
            current = self._py_loops.get((r0, c0), 0)
            lm = menu.addMenu("Python loop (auto-refresh)")
            for label, sec in (("Off", 0), ("0.1 second", 0.1),
                               ("0.5 second", 0.5), ("1 second", 1),
                               ("5 seconds", 5),
                               ("10 seconds", 10), ("30 seconds", 30),
                               ("1 minute", 60), ("5 minutes", 300),
                               ("15 minutes", 900)):
                act = lm.addAction(label)
                act.setCheckable(True)
                act.setChecked(current == sec)
                act.triggered.connect(
                    lambda _=False, rr=r0, cc=c0, s=sec:
                    self._set_py_loop(rr, cc, s))
            lm.addSeparator()
            cact = lm.addAction("Custom…")
            cact.triggered.connect(
                lambda _=False, rr=r0, cc=c0: self._py_loop_custom(rr, cc))
            menu.addSeparator()

        # Plot submenu first (like KhervePlot)
        sel = self.selected_columns()
        if sel:
            self._add_plot_submenu(menu, sel)
            menu.addSeparator()

        menu.addAction("Cu&t", self._cut_selection)
        menu.addAction("&Copy", self._copy_selection)
        menu.addAction("&Paste", self._paste_clipboard)
        menu.addAction("Paste &Values Only", self._paste_values_only)
        menu.addAction("Cl&ear", self._clear_selection)

        menu.addSeparator()

        menu.addAction("Insert Cells", self._insert_cells)
        menu.addAction("Delete Cells", self._delete_cells)

        menu.addSeparator()
        menu.addAction("Format Cells\u2026",
                       lambda: self.window()._open_format_cells_dialog())

        # Note / Comment edit actions
        row = self.table.currentRow()
        col = self.table.currentColumn()
        note = self._cell_notes.get((row, col))
        if note:
            kind = note.get("kind", "note") if isinstance(note, dict) else "note"
            label = "Comment" if kind == "comment" else "Note"
            menu.addSeparator()
            menu.addAction(f"Edit {label}\u2026",
                           lambda: self._edit_note(row, col))
            menu.addAction(f"Delete {label}",
                           lambda: self._delete_note(row, col))
        else:
            menu.addSeparator()
            menu.addAction("Add Comment\u2026",
                           lambda: self._add_note(row, col, "comment"))
            menu.addAction("Add Note\u2026",
                           lambda: self._add_note(row, col, "note"))

        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _edit_note(self, row, col):
        """Open edit dialog for an existing note/comment."""
        note = self._cell_notes.get((row, col))
        if not note:
            return
        kind = note.get("kind", "note") if isinstance(note, dict) else "note"
        if kind == "comment":
            from .insert_ops import insert_comment
            # Temporarily select the cell so insert_comment targets it
            self.table.setCurrentCell(row, col)
            insert_comment(self, self.window())
        else:
            from .insert_ops import insert_note
            self.table.setCurrentCell(row, col)
            insert_note(self, self.window())

    def _delete_note(self, row, col):
        """Remove a note/comment from a cell."""
        existing = self._cell_notes.get((row, col))
        old_note = dict(existing) if isinstance(existing, dict) else None
        if self._undo_stack is not None:
            from .undo_commands import NoteCmd
            self._undo_stack.push(
                NoteCmd(self, row, col, old_note, None))
        else:
            self._cell_notes.pop((row, col), None)
            self._hide_note_popup()
            idx = self.table.model().index(row, col)
            self.table.update(idx)

    def _add_note(self, row, col, kind):
        """Add a new note or comment to the cell."""
        self.table.setCurrentCell(row, col)
        if kind == "comment":
            from .insert_ops import insert_comment
            insert_comment(self, self.window())
        else:
            from .insert_ops import insert_note
            insert_note(self, self.window())

    def _remove_sparkline(self):
        """Remove sparklines from selected cells."""
        from .insert_ops import remove_sparklines
        remove_sparklines(self)

    def _column_stats(self, col):
        """Show statistics for a single column."""
        import numpy as np
        data = self.numeric_column(col)
        valid = data[~np.isnan(data)]
        if len(valid) == 0:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "Statistics",
                                    "No numeric data in column.")
            return
        from PyQt5.QtWidgets import QMessageBox
        msg = (f"Column {col_index_to_letter(col)}\n\n"
               f"Count: {len(valid)}\n"
               f"Sum: {np.nansum(valid):.6g}\n"
               f"Mean: {np.nanmean(valid):.6g}\n"
               f"Std Dev: {np.nanstd(valid):.6g}\n"
               f"Min: {np.nanmin(valid):.6g}\n"
               f"Max: {np.nanmax(valid):.6g}\n"
               f"Median: {np.nanmedian(valid):.6g}")
        QMessageBox.information(self, "Statistics", msg)

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
        # Compute the bounding box of ALL selected ranges so that Qt's
        # range splitting (e.g. across row/column spans) doesn't silently
        # truncate the copy to just the first fragment.
        top = min(s.topRow() for s in sel)
        bot = max(s.bottomRow() for s in sel)
        left = min(s.leftColumn() for s in sel)
        right = max(s.rightColumn() for s in sel)
        # Build a set of selected cells for sparse selections (Ctrl+Click).
        selected = set()
        for s in sel:
            for r in range(s.topRow(), s.bottomRow() + 1):
                for c in range(s.leftColumn(), s.rightColumn() + 1):
                    selected.add((r, c))
        rows = []
        meta = {}  # (dr, dc) -> metadata dict
        for r in range(top, bot + 1):
            row_data = []
            for c in range(left, right + 1):
                dr, dc = r - top, c - left
                if (r, c) not in selected:
                    row_data.append("")
                    continue
                formula = self._cell_formulas.get((r, c))
                if formula and is_python_source(formula):
                    # =PY cells are multi-line — they would break the TSV
                    # row/column format.  Put display text into the TSV and
                    # carry the full source in metadata so paste restores it.
                    it = self.table.item(r, c)
                    row_data.append(it.text() if it else "")
                    cell_meta = meta.setdefault((dr, dc), {})
                    cell_meta["py_formula"] = formula
                elif formula:
                    row_data.append(formula)
                else:
                    it = self.table.item(r, c)
                    row_data.append(it.text() if it else "")
                # Collect metadata
                cell_meta = meta.get((dr, dc), {})
                it = self.table.item(r, c)
                # A real checkbox cell has CheckStateRole data set; the
                # ItemIsUserCheckable flag alone is on by default for every
                # item, so it must NOT be used to detect checkboxes.
                if it and it.data(Qt.CheckStateRole) is not None:
                    cell_meta["checkbox"] = (it.checkState() == Qt.Checked)
                if (r, c) in self._cell_dropdowns:
                    cell_meta["dropdown"] = self._cell_dropdowns[(r, c)]
                if (r, c) in self._cell_notes:
                    cell_meta["note"] = self._cell_notes[(r, c)]
                if (r, c) in self._cell_sparklines:
                    cell_meta["sparkline"] = self._cell_sparklines[(r, c)]
                if (r, c) in self._cell_formats:
                    cell_meta["format"] = _snapshot_format(
                        self._cell_formats[(r, c)])
                if cell_meta:
                    meta[(dr, dc)] = cell_meta
            rows.append("\t".join(row_data))
        clip_text = "\n".join(rows)
        QApplication.clipboard().setText(clip_text)
        self._copied_meta = meta
        self._copy_origin = (top, left)
        # Collect charts that overlap the copied bounding box.
        charts_data = []
        for ch in getattr(self, '_charts', []):
            cx, cy = ch.pos().x(), ch.pos().y()
            cw, ch2 = ch.width(), ch.height()
            # Check if the chart overlaps any cell in the selected range.
            mid_r = self.table.rowAt(cy + ch2 // 2)
            mid_c = self.table.columnAt(cx + cw // 2)
            if (top <= mid_r <= bot and left <= mid_c <= right):
                charts_data.append(ch.to_dict())
        # Share the metadata across sheets, tied to this clipboard text.
        global _CELL_CLIPBOARD
        _CELL_CLIPBOARD = {
            "text": clip_text, "meta": meta, "charts": charts_data,
        }
        # Start marching ants around the full bounding box.
        from PyQt5.QtWidgets import QTableWidgetSelectionRange
        self._start_marching_ants(
            QTableWidgetSelectionRange(top, left, bot, right))

    # ── Marching ants animation ──────────────────────────────────────
    def _start_marching_ants(self, sel_range):
        """Begin animated dashed border around the copied range."""
        self._marching_range = sel_range
        self._march_offset = 0
        self._sync_ants_overlay()
        self._ants_overlay.show()
        self._ants_overlay.raise_()
        self._ants_overlay.update()
        self._march_timer.start(150)  # ~7 fps animation

    def _clear_marching_ants(self):
        """Stop marching ants animation."""
        if self._marching_range is not None:
            self._marching_range = None
            self._march_timer.stop()
            self._ants_overlay.hide()

    def _update_sel_overlay(self):
        """Resize and repaint the selection border overlay."""
        vp = self.table.viewport()
        self._sel_overlay.setGeometry(vp.rect())
        self._sel_overlay.raise_()
        self._sel_overlay.update()

    def _sync_ants_overlay(self):
        """Keep the overlay covering the whole viewport."""
        vp = self.table.viewport()
        self._ants_overlay.setGeometry(vp.rect())

    def _march_tick(self):
        """Advance dash offset and repaint."""
        self._march_offset = (self._march_offset + 1) % 8
        self._sync_ants_overlay()
        self._ants_overlay.raise_()
        self._ants_overlay.update()

    def _paint_marching_ants(self, painter):
        """Draw the animated dashed border on the viewport."""
        rng = self._marching_range
        if rng is None:
            return
        # Use columnViewportPosition / rowViewportPosition for accuracy.
        x1 = self.table.columnViewportPosition(rng.leftColumn())
        y1 = self.table.rowViewportPosition(rng.topRow())
        x2 = (self.table.columnViewportPosition(rng.rightColumn())
               + self.table.columnWidth(rng.rightColumn()))
        y2 = (self.table.rowViewportPosition(rng.bottomRow())
               + self.table.rowHeight(rng.bottomRow()))
        rect = QRect(x1, y1, x2 - x1, y2 - y1)
        if rect.isEmpty():
            return
        pen = QPen(QColor(0, 120, 215), 2, Qt.CustomDashLine)
        pen.setDashPattern([4, 4])
        pen.setDashOffset(self._march_offset)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect.adjusted(1, 1, -1, -1))

    def _grow_for_paste(self, row, col, text):
        """Expand the grid so a paste block starting at (row, col) fits
        instead of silently truncating at the current extent (a fresh
        sheet only reaches column Z until scrolled).  Columns cap at
        MAX_COLS."""
        lines = [ln for ln in text.split("\n") if ln]
        if not lines:
            return
        need_rows = row + len(lines)
        need_cols = min(self.MAX_COLS,
                        col + max(ln.count("\t") + 1 for ln in lines))
        grew = False
        if need_rows > self.table.rowCount():
            self.table.setRowCount(need_rows)
            grew = True
        if need_cols > self.table.columnCount():
            self.table.setColumnCount(need_cols)
            grew = True
        if grew:
            self._refresh_headers()

    def _paste_values_only(self):
        """Paste clipboard content as plain values (no formulas)."""
        text = QApplication.clipboard().text()
        if not text:
            return
        row = self.table.currentRow()
        col = self.table.currentColumn()
        if row < 0 or col < 0:
            return
        self._grow_for_paste(row, col, text)
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
                    # Strip formula prefix — paste as plain value.
                    if val.startswith("="):
                        # Evaluate inline if possible, otherwise strip.
                        try:
                            result = self._evaluate_formula(val, r, c)
                            val = str(result)
                        except Exception:
                            pass
                    it = self.table.item(r, c)
                    old = it.text() if it else ""
                    if it is None:
                        it = QTableWidgetItem(val)
                        self.table.setItem(r, c, it)
                    else:
                        it.setText(val)
                    self._shadow[(r, c)] = val
                    # Remove any formula association for this cell.
                    self._cell_formulas.pop((r, c), None)
                    self._unregister_deps(r, c)
                    if old != val:
                        changes.append((r, c, old, val))
        finally:
            self.table.blockSignals(False)
        if changes and self._undo_stack is not None:
            self._undo_stack.push(
                BulkCellEditCmd(self, changes, "Paste Values"))
        self._clear_marching_ants()

    def _paste_clipboard(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            # If no text but clipboard has an image, paste as embedded
            mime = clipboard.mimeData()
            if mime and mime.hasImage():
                from PyQt5.QtGui import QPixmap
                pm = QPixmap(mime.imageData())
                if not pm.isNull():
                    # Delegate to MainWindow's _place_image via window()
                    win = self.window()
                    if hasattr(win, '_place_image'):
                        win._place_image(pm, "Paste Image")
            return
        row = self.table.currentRow()
        col = self.table.currentColumn()
        if row < 0 or col < 0:
            return
        self._grow_for_paste(row, col, text)
        # Use the shared in-app metadata only if it matches the clipboard
        # text (so it follows a copy across sheets, but an external paste
        # doesn't pick up stale formatting).
        meta = {}
        if _CELL_CLIPBOARD and _CELL_CLIPBOARD.get("text") == text:
            meta = _CELL_CLIPBOARD.get("meta") or {}
        changes = []
        old_fmts = {}
        new_fmts = {}
        formula_cells = []  # cells that need formula evaluation
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
                    if val.startswith("="):
                        # Store formula, register deps, evaluate.
                        self._cell_formulas[(r, c)] = val
                        self._register_deps(r, c, val)
                        dec = self._cell_decimals(r, c)
                        result = self._evaluate_formula(val, r, c, dec)
                        display = str(result)
                        display = self._apply_cell_number_format(
                            display, r, c)
                        if it is None:
                            it = QTableWidgetItem(display)
                            self.table.setItem(r, c, it)
                        else:
                            it.setText(display)
                        self._shadow[(r, c)] = display
                        if old != display:
                            changes.append((r, c, old, display))
                        formula_cells.append((r, c))
                    else:
                        self._cell_formulas.pop((r, c), None)
                        self._unregister_deps(r, c)
                        if it is None:
                            it = QTableWidgetItem(val)
                            self.table.setItem(r, c, it)
                        else:
                            it.setText(val)
                        self._shadow[(r, c)] = val
                        if old != val:
                            changes.append((r, c, old, val))
                    # Restore metadata from copy
                    if meta:
                        dm = meta.get((dr, dc))
                        if dm:
                            # =PY cells: the multi-line source was stored in
                            # metadata to avoid breaking TSV row format.
                            if "py_formula" in dm:
                                py_src = dm["py_formula"]
                                self._cell_formulas[(r, c)] = py_src
                                self._register_py_deps(r, c, py_src)
                                try:
                                    dec = self._cell_decimals(r, c)
                                    disp = self._evaluate_python(
                                        py_src, r, c, dec)
                                except Exception:
                                    import traceback
                                    disp = "#PYERR"
                                    self._py_errors[(r, c)] = \
                                        traceback.format_exc()
                                it.setText(disp)
                                self._shadow[(r, c)] = disp
                                formula_cells.append((r, c))
                            if "checkbox" in dm:
                                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                                it.setCheckState(
                                    Qt.Checked if dm["checkbox"] else Qt.Unchecked)
                                # Files written before checkboxes had a
                                # readable value carry empty text.
                                val = "TRUE" if dm["checkbox"] else "FALSE"
                                it.setText(val)
                                self._shadow[(r, c)] = val
                            if "dropdown" in dm:
                                self._cell_dropdowns[(r, c)] = dm["dropdown"]
                                it.setFlags(
                                    it.flags() & ~Qt.ItemIsEditable)
                            if "note" in dm:
                                self._cell_notes[(r, c)] = dm["note"]
                            if "sparkline" in dm:
                                self._cell_sparklines[(r, c)] = dm["sparkline"]
                                self._fmt_delegate._sparklines[(r, c)] = dm["sparkline"]
                            if "format" in dm:
                                old_fmts[(r, c)] = _snapshot_format(
                                    self._cell_formats.get((r, c)))
                                cf = _snapshot_format(dm["format"])
                                new_fmts[(r, c)] = cf
                                self._cell_formats[(r, c)] = cf
                                self._apply_format_to_item(it, cf)
        finally:
            self.table.blockSignals(False)
        if (changes or old_fmts) and self._undo_stack is not None:
            self._undo_stack.beginMacro("Paste")
            if changes:
                self._undo_stack.push(
                    BulkCellEditCmd(self, changes, "Paste"))
            if old_fmts:
                self._undo_stack.push(
                    FormatCellsCmd(self, old_fmts, new_fmts, "Paste Format"))
            self._undo_stack.endMacro()
        # Recalculate dependents of pasted formula cells.
        for r, c in formula_cells:
            self.data_changed.emit(c)
            self._recalc_dependents(r, c)
        self._refresh_cross_sheet()
        # Paste any charts that were inside the copied range.
        charts_list = (_CELL_CLIPBOARD or {}).get("charts") or []
        if charts_list and _CELL_CLIPBOARD.get("text") == text:
            from .graph import EmbeddedChart
            if not hasattr(self, '_charts'):
                self._charts = []
            viewport = self.table.viewport()
            for cd in charts_list:
                try:
                    ch = EmbeddedChart.from_dict(cd, self, viewport)
                    ch.show()
                    ch.raise_()
                    self._charts.append(ch)
                except Exception:
                    pass
        # Clear marching ants after paste.
        self._clear_marching_ants()

    def _clear_selection(self):
        sel = self.table.selectedRanges()
        if not sel:
            return
        changes = []
        old_fmts = {}
        new_fmts = {}
        sparklines = getattr(self, '_cell_sparklines', {})
        delegate_sp = self._fmt_delegate._sparklines
        notes = getattr(self, '_cell_notes', {})
        links = getattr(self, '_cell_links', {})
        dropdowns = getattr(self, '_cell_dropdowns', {})
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
                        # Clear checkbox flag
                        if it and (it.flags() & Qt.ItemIsUserCheckable):
                            it.setFlags(it.flags() & ~Qt.ItemIsUserCheckable)
                            it.setData(Qt.CheckStateRole, None)
                        # Clear cell formatting (fill, font, borders, align).
                        if (r, c) in self._cell_formats:
                            old_fmts[(r, c)] = _snapshot_format(
                                self._cell_formats.get((r, c)))
                            new_fmts[(r, c)] = None
                            self._cell_formats.pop((r, c), None)
                            if it is not None:
                                it.setBackground(QBrush())
                                it.setForeground(QBrush())
                                it.setFont(QFont(self.table.font()))
                                it.setTextAlignment(
                                    Qt.AlignLeft | Qt.AlignVCenter)
                        # Clear insert-ops metadata
                        sparklines.pop((r, c), None)
                        delegate_sp.pop((r, c), None)
                        notes.pop((r, c), None)
                        links.pop((r, c), None)
                        dropdowns.pop((r, c), None)
                        # Clear formula
                        self._cell_formulas.pop((r, c), None)
                        # Force repaint
                        idx = self.table.model().index(r, c)
                        self.table.update(idx)
        finally:
            self.table.blockSignals(False)
        if (changes or old_fmts) and self._undo_stack is not None:
            self._undo_stack.beginMacro("Clear")
            if changes:
                self._undo_stack.push(
                    BulkCellEditCmd(self, changes, "Clear"))
            if old_fmts:
                self._undo_stack.push(
                    FormatCellsCmd(self, old_fmts, new_fmts, "Clear Format"))
            self._undo_stack.endMacro()
        self.table.viewport().update()

    # ── Row/column operations ────────────────────────────────────────
    def _insert_rows_from_selection(self):
        """Insert N rows above the first selected row, where N = number of
        selected rows (minimum 1)."""
        sel_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        n = max(len(sel_rows), 1)
        start = sel_rows[0] if sel_rows else max(self.table.currentRow(), 0)
        for i in range(n):
            self.table.insertRow(start)
        self._refresh_headers()
        if self._undo_stack is not None:
            for i in range(n):
                self._undo_stack.push(InsertRowCmd(self, start + i))

    def _insert_row_above(self):
        row = self.table.currentRow()
        if row < 0:
            row = 0
        self.table.insertRow(row)
        self._refresh_headers()
        if self._undo_stack is not None:
            self._undo_stack.push(InsertRowCmd(self, row))

    def _insert_row_below(self):
        row = self.table.currentRow()
        if row < 0:
            row = self.row_count() - 1
        self.table.insertRow(row + 1)
        self._refresh_headers()
        if self._undo_stack is not None:
            self._undo_stack.push(InsertRowCmd(self, row + 1))

    def _insert_cells(self):
        """Insert blank cells, shifting existing cells down only in the
        selected columns (like Excel's Insert > Shift cells down)."""
        idxs = self.table.selectedIndexes()
        if not idxs:
            return
        rows = sorted(set(idx.row() for idx in idxs))
        cols = sorted(set(idx.column() for idx in idxs))
        cmd = InsertCellsCmd(self, rows, cols)
        cmd._shift_down()
        if self._undo_stack is not None:
            self._undo_stack.push(cmd)

    def _delete_cells(self):
        """Delete selected cells, shifting remaining cells up only in the
        selected columns (like Excel's Delete > Shift cells up)."""
        idxs = self.table.selectedIndexes()
        if not idxs:
            return
        rows = sorted(set(idx.row() for idx in idxs))
        cols = sorted(set(idx.column() for idx in idxs))
        # Snapshot the cells about to be deleted.
        saved = {}
        for r in rows:
            for c in cols:
                it = self.table.item(r, c)
                text = it.text() if it else ""
                formula = self._cell_formulas.get((r, c))
                fmt = self._cell_formats.get((r, c))
                saved[(r, c)] = (text, formula, fmt)
        cmd = DeleteCellsCmd(self, rows, cols, saved)
        cmd._shift_up()
        if self._undo_stack is not None:
            self._undo_stack.push(cmd)

    def _delete_selected_rows(self):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()),
                      reverse=True)
        # Snapshot row data for undo (ascending order for restore).
        rows_data = []
        for r in sorted(rows):
            cells = []
            for c in range(self.table.columnCount()):
                it = self.table.item(r, c)
                text = it.text() if it else ""
                formula = self._cell_formulas.get((r, c))
                cells.append((c, text, formula))
            rows_data.append((r, cells))
        for r in rows:
            self.table.removeRow(r)
        self._refresh_headers()
        if rows_data and self._undo_stack is not None:
            self._undo_stack.push(DeleteRowsCmd(self, rows_data))

    def _add_10_rows(self):
        cur = self.row_count()
        for _ in range(10):
            self.table.insertRow(cur)
            cur += 1
        self._refresh_headers()

    def _shift_charts(self, at: int, delta: int):
        """Shift plotted column references on every embedded chart when a
        column is inserted (delta=+1) or removed (delta=-1) at *at*, then
        re-read so charts follow their data like Excel."""
        for chart in getattr(self, "_charts", []):
            if chart.shift_column_refs(at, delta):
                chart._refresh_data()
                if getattr(chart, "_header_row", False):
                    chart._apply_header_labels()

    def _per_cell_dicts(self):
        """All (row, col)-keyed dicts that must track column inserts/deletes
        so fills, borders, fonts, formulas and metadata follow their data."""
        dicts = [self._cell_formats, self._cell_formulas, self._cell_notes,
                 self._cell_dropdowns, self._cell_sparklines,
                 self._cell_links, self._shadow]
        dg = getattr(self._fmt_delegate, "_sparklines", None)
        if isinstance(dg, dict):
            dicts.append(dg)
        return dicts

    def _shift_cell_dicts(self, at: int, delta: int):
        """Shift the column index of every per-cell dict when a column is
        inserted (delta=+1) or removed (delta=-1) at *at*. Mutates each dict
        in place to preserve the object identity shared with the delegate."""
        seen = set()
        for d in self._per_cell_dicts():
            if d is None or id(d) in seen:
                continue
            seen.add(id(d))
            new_d = {}
            for (r, c), v in d.items():
                if delta > 0:
                    nc = c + delta if c >= at else c
                else:
                    if c == at:
                        continue
                    nc = c + delta if c > at else c
                new_d[(r, nc)] = v
            d.clear()
            d.update(new_d)

    def _snapshot_column_meta(self, col: int) -> dict:
        """Snapshot per-cell formatting/metadata for one column so a column
        delete can be fully undone."""
        meta = {"formats": {}, "notes": {}, "dropdowns": {},
                "sparklines": {}, "links": {}}
        dg = getattr(self._fmt_delegate, "_sparklines", None)
        sources = {
            "formats": self._cell_formats,
            "notes": self._cell_notes,
            "dropdowns": self._cell_dropdowns,
            "sparklines": self._cell_sparklines if not isinstance(dg, dict)
            else dg,
            "links": self._cell_links,
        }
        for name, src in sources.items():
            for (r, c), v in src.items():
                if c == col:
                    meta[name][r] = (_snapshot_format(v)
                                     if name == "formats" else v)
        return meta

    def _restore_column_meta(self, col: int, meta: dict):
        """Restore metadata captured by :meth:`_snapshot_column_meta` and
        re-apply the visual cell format."""
        dg = getattr(self._fmt_delegate, "_sparklines", None)
        targets = {
            "notes": self._cell_notes,
            "dropdowns": self._cell_dropdowns,
            "sparklines": self._cell_sparklines if not isinstance(dg, dict)
            else dg,
            "links": self._cell_links,
        }
        for name, target in targets.items():
            for r, v in meta.get(name, {}).items():
                target[(r, col)] = v
        for r, cf in meta.get("formats", {}).items():
            if cf is None:
                continue
            self._cell_formats[(r, col)] = cf
            it = self.table.item(r, col)
            if it is None:
                it = QTableWidgetItem("")
                self.table.setItem(r, col, it)
            self._apply_format_to_item(it, cf)

    def _apply_format_to_item(self, it, cf):
        """Paint a CellFormat's item-stored visuals (fill/font/align)."""
        it.setBackground(QColor(cf.bg_color) if cf.bg_color else QBrush())
        it.setForeground(QColor(cf.font_color) if cf.font_color else QBrush())
        if cf.alignment is not None:
            it.setTextAlignment(cf.alignment)
        f = it.font()
        if cf.bold is not None:
            f.setBold(cf.bold)
        if cf.italic is not None:
            f.setItalic(cf.italic)
        if cf.underline is not None:
            f.setUnderline(cf.underline)
        if cf.font_family is not None:
            f.setFamily(cf.font_family)
        if cf.font_size is not None:
            f.setPointSizeF(cf.font_size)
        it.setFont(f)

    def _insert_column(self, col: int):
        old_desigs = dict(self._col_designations)
        self.table.insertColumn(col)
        self._shift_cell_dicts(col, +1)
        # Shift designations
        new_desigs = {}
        for c, d in old_desigs.items():
            if c >= col:
                new_desigs[c + 1] = d
            else:
                new_desigs[c] = d
        self._col_designations = new_desigs
        self._shift_charts(col, +1)
        self._refresh_headers()
        if self._undo_stack is not None:
            self._undo_stack.push(
                InsertColumnCmd(self, col, old_desigs))

    def _delete_column(self, col: int):
        if self.column_count() <= 1:
            return
        # Snapshot column data for undo.
        col_data = []
        for r in range(self.table.rowCount()):
            it = self.table.item(r, col)
            text = it.text() if it else ""
            formula = self._cell_formulas.get((r, col))
            col_data.append((r, text, formula))
        old_desigs = dict(self._col_designations)
        col_meta = self._snapshot_column_meta(col)
        self.table.removeColumn(col)
        self._shift_cell_dicts(col, -1)
        # Shift designations
        new_desigs = {}
        for c, d in old_desigs.items():
            if c == col:
                continue
            if c > col:
                new_desigs[c - 1] = d
            else:
                new_desigs[c] = d
        self._col_designations = new_desigs
        self._shift_charts(col, -1)
        self._refresh_headers()
        if self._undo_stack is not None:
            self._undo_stack.push(
                DeleteColumnCmd(self, col, col_data, old_desigs, col_meta))

    def _set_column_width(self, col: int):
        cur = self.table.columnWidth(col)
        w, ok = QInputDialog.getInt(self, "Column Width",
                                    "Width (pixels):", cur, 20, 500)
        if ok:
            self.table.setColumnWidth(col, w)

    def _sort_column(self, col: int, order):
        # Snapshot all data for undo.
        old_data = []
        for r in range(self.table.rowCount()):
            cells = []
            for c in range(self.table.columnCount()):
                it = self.table.item(r, c)
                text = it.text() if it else ""
                formula = self._cell_formulas.get((r, c))
                cells.append((c, text, formula))
            old_data.append((r, cells))
        self.table.sortItems(col, order)
        if self._undo_stack is not None:
            self._undo_stack.push(SortColumnCmd(self, old_data, "Sort"))

    # ── Drag-fill (Excel-style auto-fill) ────────────────────────────
    _HANDLE_PX = 6

    # ── Ctrl+Arrow navigation (Excel-style jump to data boundary) ──

    def _cell_has_data(self, r, c):
        """Return True if cell (r, c) contains non-empty text."""
        if r < 0 or c < 0:
            return False
        it = self.table.item(r, c)
        return bool(it and it.text())

    def _ctrl_arrow_jump(self, key, extend_selection):
        """Jump to the next data boundary in the arrow direction.

        If the current cell is non-empty, jump to the last non-empty cell
        in that direction.  If the current cell is empty, jump to the
        first non-empty cell.  If all cells in that direction are empty,
        stay put.

        *extend_selection*: if True, extend the selection (Shift held).
        """
        r = self.table.currentRow()
        c = self.table.currentColumn()
        if r < 0 or c < 0:
            return

        # When extending, start the walk from the current cursor
        # position (the moving corner of the selection), not from
        # the Qt current cell which may not have been updated.
        if extend_selection and self._sel_cursor is not None:
            r, c = self._sel_cursor

        dr, dc = {
            Qt.Key_Down: (1, 0), Qt.Key_Up: (-1, 0),
            Qt.Key_Right: (0, 1), Qt.Key_Left: (0, -1),
        }[key]

        max_r = self.table.rowCount() - 1
        max_c = self.table.columnCount() - 1

        nr, nc = r + dr, c + dc
        if self._cell_has_data(r, c):
            last_r, last_c = r, c
            while 0 <= nr <= max_r and 0 <= nc <= max_c:
                if not self._cell_has_data(nr, nc):
                    break
                last_r, last_c = nr, nc
                nr += dr
                nc += dc
            if (last_r, last_c) == (r, c):
                while 0 <= nr <= max_r and 0 <= nc <= max_c:
                    if self._cell_has_data(nr, nc):
                        last_r, last_c = nr, nc
                        break
                    nr += dr
                    nc += dc
            dest_r, dest_c = last_r, last_c
        else:
            dest_r, dest_c = r, c
            while 0 <= nr <= max_r and 0 <= nc <= max_c:
                if self._cell_has_data(nr, nc):
                    dest_r, dest_c = nr, nc
                    break
                nr += dr
                nc += dc

        if extend_selection:
            # Anchor is the fixed corner (where the user started).
            if self._sel_anchor is not None:
                anchor_r, anchor_c = self._sel_anchor
            else:
                anchor_r, anchor_c = self.table.currentRow(), \
                    self.table.currentColumn()

            # Build the new range from anchor to destination, also
            # preserving the existing selection extent.
            top = min(anchor_r, dest_r)
            bot = max(anchor_r, dest_r)
            left = min(anchor_c, dest_c)
            right = max(anchor_c, dest_c)
            sel = self.table.selectedRanges()
            if sel:
                s = sel[0]
                top = min(top, s.topRow())
                bot = max(bot, s.bottomRow())
                left = min(left, s.leftColumn())
                right = max(right, s.rightColumn())
            self.table.clearSelection()
            self.table.setRangeSelected(
                QTableWidgetSelectionRange(top, left, bot, right), True)
            self._sel_anchor = (anchor_r, anchor_c)
            # Cursor tracks the actual corner in the direction we moved.
            cur_r = bot if dr >= 0 else top
            cur_c = right if dc >= 0 else left
            if dr == 0:
                cur_r = dest_r
            if dc == 0:
                cur_c = dest_c
            self._sel_cursor = (cur_r, cur_c)
            idx = self.table.model().index(cur_r, cur_c)
            self.table.scrollTo(idx)
        else:
            self._sel_anchor = None
            self._sel_cursor = None
            self.table.clearSelection()
            self.table.setCurrentCell(dest_r, dest_c)

    def _shift_arrow_extend(self, key):
        """Extend (or contract) the selection by one cell in the arrow
        direction, keeping the anchor corner fixed — like Excel's
        Shift+Arrow."""
        dr, dc = {
            Qt.Key_Down: (1, 0), Qt.Key_Up: (-1, 0),
            Qt.Key_Right: (0, 1), Qt.Key_Left: (0, -1),
        }[key]
        max_r = self.table.rowCount() - 1
        max_c = self.table.columnCount() - 1

        r = self.table.currentRow()
        c = self.table.currentColumn()

        # Determine anchor (fixed corner) and cursor (moving corner).
        # If not already tracked (e.g. mouse selection), infer from the
        # current selection: anchor = top-left, cursor = bottom-right.
        if self._sel_anchor is None or self._sel_cursor is None:
            sel = self.table.selectedRanges()
            if sel:
                s = sel[0]
                self._sel_anchor = (s.topRow(), s.leftColumn())
                self._sel_cursor = (s.bottomRow(), s.rightColumn())
            else:
                self._sel_anchor = (r, c)
                self._sel_cursor = (r, c)

        anc_r, anc_c = self._sel_anchor
        cur_r, cur_c = self._sel_cursor

        # Move cursor by one cell.
        new_cur_r = min(max(cur_r + dr, 0), max_r)
        new_cur_c = min(max(cur_c + dc, 0), max_c)

        top = min(anc_r, new_cur_r)
        bot = max(anc_r, new_cur_r)
        left = min(anc_c, new_cur_c)
        right = max(anc_c, new_cur_c)

        self.table.clearSelection()
        self.table.setRangeSelected(
            QTableWidgetSelectionRange(top, left, bot, right), True)

        self._sel_anchor = (anc_r, anc_c)
        self._sel_cursor = (new_cur_r, new_cur_c)

        idx = self.table.model().index(new_cur_r, new_cur_c)
        self.table.scrollTo(idx)

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

    # ── Arrow-key formula reference helpers ────────────────────────
    _OPERATOR_CHARS = set("=+-*/^(,<>&")

    def _find_inline_editor(self):
        """Return the active inline QLineEdit cell editor, or None."""
        editor = self.table.findChild(QLineEdit, "",
                                      Qt.FindDirectChildrenOnly)
        if editor is None:
            vp = self.table.viewport()
            for child in vp.children():
                if isinstance(child, QLineEdit):
                    editor = child
                    break
        if editor is not None and editor is self._formula_bar:
            return None
        return editor

    def _ensure_item(self, row, col):
        """Return the QTableWidgetItem at (row, col), creating one if
        needed."""
        it = self.table.item(row, col)
        if it is None:
            it = QTableWidgetItem("")
            self.table.setItem(row, col, it)
        return it

    def _pick_drag_move(self, event):
        """Widen the just-inserted single ref into a range as the user
        drags from the clicked (anchor) cell to the current cell."""
        d = self._pick_drag
        cell = self.table.indexAt(event.pos())
        if not cell.isValid():
            return
        ar, ac = d["anchor"]
        r1, c1 = min(ar, cell.row()), min(ac, cell.column())
        r2, c2 = max(ar, cell.row()), max(ac, cell.column())
        if (r1, c1) == (r2, c2):
            ref = col_index_to_letter(c1) + str(r1 + 1)
        else:
            ref = (col_index_to_letter(c1) + str(r1 + 1) + ":"
                   + col_index_to_letter(c2) + str(r2 + 1))
        w = (self._formula_bar if d["where"] == "bar"
             else self._find_inline_editor())
        if w is None:
            return
        text = w.text()
        s = d["ins_start"]
        e = s + d["ref_len"]
        new_text = text[:s] + ref + text[e:]
        w.blockSignals(True)
        w.setText(new_text)
        w.setCursorPosition(s + len(ref))
        w.blockSignals(False)
        d["ref_len"] = len(ref)
        self._update_ref_highlights(new_text)

    def _end_pick_drag(self):
        self._pick_drag = None
        self._release_drag_grab()

    def _set_inline_editor_text(self, text, cursor_pos):
        """Set text and cursor on the active inline editor (deferred)."""
        editor = self._find_inline_editor()
        if editor:
            editor.setText(text)
            editor.setCursorPosition(cursor_pos)
            self._inline_formula_text = text
            self._inline_formula_pos = cursor_pos
            self._inline_formula_cell = (
                self.table.currentRow(), self.table.currentColumn())
            self._update_ref_highlights(text)

    def _should_arrow_insert_ref(self, editor):
        """Return True if an arrow key should insert/move a cell ref
        rather than move the text cursor."""
        if self._arrow_nav_active:
            return True
        text = editor.text()
        if not text.startswith("="):
            return False
        cp = editor.cursorPosition()
        if cp == 0:
            return False
        ch = text[cp - 1]
        return ch in self._OPERATOR_CHARS

    def _handle_arrow_key(self, key, editor):
        """Process an arrow key press during formula entry.
        Returns True if the event was consumed."""
        # Determine new reference cursor position.
        if self._arrow_nav_pos is not None:
            r, c = self._arrow_nav_pos
        else:
            r = self.table.currentRow()
            c = self.table.currentColumn()
            if r < 0 or c < 0:
                return False

        if key == Qt.Key_Up:
            r = max(0, r - 1)
        elif key == Qt.Key_Down:
            r = min(self.table.rowCount() - 1, r + 1)
        elif key == Qt.Key_Left:
            c = max(0, c - 1)
        elif key == Qt.Key_Right:
            c = min(self.table.columnCount() - 1, c + 1)
        else:
            return False

        ref = col_index_to_letter(c) + str(r + 1)
        text = editor.text()

        if self._arrow_nav_active and self._arrow_nav_ref_span:
            # Replace the previous arrow-inserted reference.
            start, end = self._arrow_nav_ref_span
            new_text = text[:start] + ref + text[end:]
            new_end = start + len(ref)
        else:
            # Insert a new reference at cursor position.
            cp = editor.cursorPosition()
            new_text = text[:cp] + ref + text[cp:]
            start = cp
            new_end = cp + len(ref)

        editor.blockSignals(True)
        editor.setText(new_text)
        editor.setCursorPosition(new_end)
        editor.blockSignals(False)

        self._arrow_nav_active = True
        self._arrow_nav_pos = (r, c)
        self._arrow_nav_ref_span = (start, new_end)

        # Update highlights from the full formula text.
        self._update_ref_highlights(new_text)
        return True

    # ── Tab completion for formula function names ─────────────────

    _FORMULA_FUNC_NAMES: list = []  # lazily populated

    @classmethod
    def _get_formula_func_names(cls):
        """Return sorted list of all known formula function names."""
        if not cls._FORMULA_FUNC_NAMES:
            from .formulas import FUNCTION_CATEGORIES
            names = set()
            for funcs in FUNCTION_CATEGORIES.values():
                names.update(funcs)
            cls._FORMULA_FUNC_NAMES = sorted(names)
        return cls._FORMULA_FUNC_NAMES

    def _handle_formula_tab(self, editor):
        """Tab-complete a function name in the formula bar.

        On first Tab press, find all functions matching the partial token
        before the cursor and replace it with the first match.  Subsequent
        Tab presses cycle through matches; Shift+Tab cycles backwards.
        Returns True if the event was consumed.
        """
        import re
        text = editor.text()
        if not text.startswith("="):
            return False

        # If we already have matches, cycle to the next one.
        if self._tab_matches:
            from PyQt5.QtWidgets import QApplication
            shift = (QApplication.keyboardModifiers() & Qt.ShiftModifier)
            step = -1 if shift else 1
            self._tab_index = (
                (self._tab_index + step) % len(self._tab_matches))
            replacement = self._tab_matches[self._tab_index]
            # Replace from prefix_pos to current cursor position.
            before = text[:self._tab_prefix_pos]
            # Find end of previous completion (cursor is right after it).
            cp = editor.cursorPosition()
            after = text[cp:]
            new_text = before + replacement + after
            editor.blockSignals(True)
            editor.setText(new_text)
            editor.setCursorPosition(
                self._tab_prefix_pos + len(replacement))
            editor.blockSignals(False)
            return True

        # First Tab: extract the partial token before cursor.
        cp = editor.cursorPosition()
        left = text[1:cp]  # strip leading "="
        # Find the last function-name token (letters, digits, dots).
        m = re.search(r'([A-Za-z][A-Za-z0-9._]*)$', left)
        if not m:
            return False
        prefix = m.group(1).upper()
        prefix_pos = 1 + m.start()  # absolute position in text

        all_funcs = self._get_formula_func_names()
        matches = [f for f in all_funcs if f.startswith(prefix)]
        if not matches:
            return False

        self._tab_matches = matches
        self._tab_index = 0
        self._tab_prefix_pos = prefix_pos

        replacement = matches[0]
        before = text[:prefix_pos]
        after = text[cp:]
        new_text = before + replacement + after
        editor.blockSignals(True)
        editor.setText(new_text)
        editor.setCursorPosition(prefix_pos + len(replacement))
        editor.blockSignals(False)
        return True

    def _toggle_absolute_ref(self, editor):
        """Cycle cell reference under cursor through A1→$A$1→A$1→$A1.

        Pressing F4 in the formula bar toggles the absolute/relative
        state of the nearest cell reference, matching Excel behaviour.
        """
        import re
        text = editor.text()
        cp = editor.cursorPosition()
        # Find all cell refs (with optional $ markers).
        pat = re.compile(r'(\$?)([A-Za-z]{1,3})(\$?)(\d{1,7})')
        for m in pat.finditer(text):
            if m.start() <= cp <= m.end():
                dc, letters, dr, digits = (
                    m.group(1), m.group(2), m.group(3), m.group(4))
                # Cycle: A1 → $A$1 → A$1 → $A1 → A1
                if not dc and not dr:
                    new = f"${letters}${digits}"
                elif dc and dr:
                    new = f"{letters}${digits}"
                elif not dc and dr:
                    new = f"${letters}{digits}"
                else:
                    new = f"{letters}{digits}"
                new_text = text[:m.start()] + new + text[m.end():]
                editor.blockSignals(True)
                editor.setText(new_text)
                # Place cursor at end of the replaced reference.
                editor.setCursorPosition(
                    m.start() + len(new))
                editor.blockSignals(False)
                break

    def _on_inline_editor_text(self, text):
        """Track inline editor text for click-to-insert-ref.

        When the text starts with '=', close the inline cell editor and
        redirect to the formula bar so that range-picking works reliably.
        The close/redirect is deferred so it runs outside the textChanged
        signal handler (Qt ignores closeEditor inside the signal).
        """
        r = self.table.currentRow()
        c = self.table.currentColumn()
        if r >= 0 and c >= 0 and text.startswith("="):
            self._inline_formula_cell = None
            self._inline_formula_text = None
            self._inline_formula_pos = None
            QTimer.singleShot(0, lambda: self._redirect_to_formula_bar(
                r, c, text))
        else:
            self._inline_formula_cell = None
            self._inline_formula_text = None
            self._inline_formula_pos = None
            self._clear_ref_highlights()

    def _redirect_to_formula_bar(self, row, col, text):
        """Close inline editor and move formula text to the formula bar."""
        editor = self._find_inline_editor()
        if editor is not None:
            self.table.closeEditor(
                editor, QAbstractItemDelegate.RevertModelData)
        # Restore the cell to its previous value (don't commit the '=…').
        self.table.blockSignals(True)
        it = self.table.item(row, col)
        old = self._shadow.get((row, col), "")
        if it is not None:
            it.setText(old)
        self.table.blockSignals(False)
        # Activate formula bar.
        self._formula_entry_cell = (row, col)
        self._formula_bar.blockSignals(True)
        self._formula_bar.setText(text)
        self._formula_bar.blockSignals(False)
        self._formula_bar.setFocus()
        self._formula_bar.setCursorPosition(len(text))
        wb = self._workbook()
        if wb is not None:
            wb.set_active_formula(self)
        self._update_ref_highlights(text)

    def eventFilter(self, obj, event):
        # ── Keep columns filling the viewport on resize ───────────
        if (obj is self.table.viewport()
                and event.type() == QEvent.Resize):
            self._ensure_columns_fill_viewport()

        # ── Detect inline editor creation on viewport ────────────
        # At ChildAdded time the widget may not yet be a QLineEdit in
        # Python's sip wrapper, so defer the isinstance check.
        if (obj is self.table.viewport()
                and event.type() == QEvent.ChildAdded):
            try:
                child = event.child()
                def _try_connect(w=child):
                    if (isinstance(w, QLineEdit)
                            and w is not self._formula_bar):
                        w.textChanged.connect(
                            self._on_inline_editor_text)
                QTimer.singleShot(0, _try_connect)
            except Exception:
                pass

        # ── Formula bar focus-in: show highlights for existing formula ──
        if obj is self._formula_bar and event.type() == QEvent.FocusIn:
            text = self._formula_bar.text()
            if text.startswith("="):
                self._update_ref_highlights(text)

        # ── Formula bar arrow key interception ───────────────────
        if obj is self._formula_bar and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Tab:
                if self._handle_formula_tab(self._formula_bar):
                    return True
            elif key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
                if (self._formula_entry_cell is not None
                        and self._should_arrow_insert_ref(self._formula_bar)):
                    if self._handle_arrow_key(key, self._formula_bar):
                        return True
            elif key == Qt.Key_Escape:
                self._exit_formula_mode()
            elif key == Qt.Key_F4:
                self._toggle_absolute_ref(self._formula_bar)
                return True
            else:
                # Any non-arrow/non-tab key resets tab completion.
                self._tab_matches.clear()
                self._tab_index = -1
                # Any non-arrow key breaks arrow nav mode.
                self._arrow_nav_active = False
                self._arrow_nav_pos = None
                self._arrow_nav_ref_span = None

        # ── Table-level key interception for inline "=" editors ────
        if obj is self.table and event.type() == QEvent.KeyPress:
            key = event.key()
            editor = self._find_inline_editor()

            # ── '=' with no editor → redirect straight to formula bar ──
            if (key == Qt.Key_Equal and editor is None
                    and self._formula_entry_cell is None):
                r = self.table.currentRow()
                c = self.table.currentColumn()
                if r >= 0 and c >= 0:
                    self._formula_entry_cell = (r, c)
                    self._formula_bar.setText("=")
                    self._formula_bar.setFocus()
                    self._formula_bar.setCursorPosition(1)
                    wb = self._workbook()
                    if wb is not None:
                        wb.set_active_formula(self)
                    return True          # eat the key

            # ── '=' typed into an existing inline editor → redirect ──
            if (key == Qt.Key_Equal and editor is not None
                    and not editor.text()):
                r = self.table.currentRow()
                c = self.table.currentColumn()
                if r >= 0 and c >= 0:
                    self.table.closeEditor(
                        editor, QAbstractItemDelegate.RevertModelData)
                    self._inline_formula_cell = None
                    self._inline_formula_text = None
                    self._formula_entry_cell = (r, c)
                    self._formula_bar.setText("=")
                    self._formula_bar.setFocus()
                    self._formula_bar.setCursorPosition(1)
                    wb = self._workbook()
                    if wb is not None:
                        wb.set_active_formula(self)
                    return True          # eat the key

            # ── Ctrl+Arrow / Ctrl+Shift+Arrow: jump to data boundary ──
            if (key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right)
                    and (event.modifiers() & Qt.ControlModifier)
                    and editor is None
                    and self._formula_entry_cell is None):
                extend = bool(event.modifiers() & Qt.ShiftModifier)
                self._ctrl_arrow_jump(key, extend)
                return True

            # ── Shift+Arrow: extend selection by one cell ──
            if (key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right)
                    and (event.modifiers() & Qt.ShiftModifier)
                    and not (event.modifiers() & Qt.ControlModifier)
                    and editor is None
                    and self._formula_entry_cell is None):
                self._shift_arrow_extend(key)
                return True

            if key == Qt.Key_Escape:
                if editor:
                    # Cancel inline edit without committing.
                    self.table.closeEditor(
                        editor, QAbstractItemDelegate.RevertModelData)
                    self._inline_formula_text = None
                    self._inline_formula_cell = None
                    return True
                if self._marching_range is not None:
                    self._clear_marching_ants()
                if self._formula_entry_cell is not None:
                    self._exit_formula_mode()
                    return True
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                # Commit inline edit and move to next row (Excel behavior).
                r = self.table.currentRow()
                c = self.table.currentColumn()
                if editor:
                    self.table.commitData(editor)
                    self.table.closeEditor(
                        editor, QAbstractItemDelegate.NoHint)
                self._inline_formula_text = None
                self._inline_formula_cell = None
                next_row = r + 1
                if next_row < self.row_count():
                    self.table.setCurrentCell(next_row, c)
                return True
            elif key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
                # Find active inline editor with formula.
                if editor and editor.text().startswith("="):
                    # Ensure formula entry mode is active.
                    if self._formula_entry_cell is None:
                        r = self.table.currentRow()
                        c = self.table.currentColumn()
                        if r >= 0 and c >= 0:
                            self._formula_entry_cell = (r, c)
                    if self._should_arrow_insert_ref(editor):
                        if self._handle_arrow_key(key, editor):
                            return True
            # Track inline formula state for click-to-insert-ref.
            if editor and editor.text().startswith("="):
                r = self.table.currentRow()
                c = self.table.currentColumn()
                if r >= 0 and c >= 0:
                    self._inline_formula_cell = (r, c)
                    self._inline_formula_text = editor.text()
                    self._inline_formula_pos = editor.cursorPosition()

        # ── Header resize: snapshot on press, push undo on release ──
        h_header = self.table.horizontalHeader()
        v_header = self.table.verticalHeader()
        if obj in (h_header, v_header):
            if event.type() == QEvent.MouseButtonPress:
                if obj is h_header:
                    sel = self._selected_columns()
                    self._col_resize_snap = {
                        c: self.table.columnWidth(c) for c in sel
                    } if sel else None
                else:
                    sel = self._selected_rows()
                    self._row_resize_snap = {
                        r: self.table.rowHeight(r) for r in sel
                    } if sel else None
            elif event.type() == QEvent.MouseButtonRelease:
                self._finish_section_resize()
            return super().eventFilter(obj, event)

        if obj is not self.table.viewport():
            return super().eventFilter(obj, event)
        etype = event.type()

        # ── Range-finder: dragging a reference highlight ─────────────
        if self._ref_drag is not None:
            if etype == QEvent.MouseMove:
                self._ref_drag_move(event)
                return True
            if etype == QEvent.MouseButtonRelease:
                self._end_ref_drag()
                return True

        # Click-drag widening a just-inserted reference into a range.
        if self._pick_drag is not None:
            if etype == QEvent.MouseMove:
                self._pick_drag_move(event)
                return True
            if etype == QEvent.MouseButtonRelease:
                self._end_pick_drag()
                return True

        # Keep overlays sized to the viewport.
        if etype == QEvent.Resize:
            self._update_sel_overlay()
            if self._marching_range is not None:
                self._sync_ants_overlay()

        if etype == QEvent.Leave:
            self._hide_note_popup()

        if etype == QEvent.MouseMove and not self._fill_dragging:
            # Move cursor when hovering a draggable reference highlight.
            if (self._ref_highlight_active
                    and self._ref_token_at(event.pos()) is not None):
                self.table.viewport().setCursor(Qt.SizeAllCursor)
            else:
                hr = self._fill_handle_rect()
                if hr and hr.contains(event.pos()):
                    self.table.viewport().setCursor(Qt.CrossCursor)
                else:
                    self.table.viewport().unsetCursor()
            # Note / comment hover popup
            pos = event.pos()
            idx = self.table.indexAt(pos)
            if idx.isValid():
                key = (idx.row(), idx.column())
                if key in self._cell_notes:
                    self._show_note_popup(idx.row(), idx.column())
                else:
                    self._hide_note_popup()
            else:
                self._hide_note_popup()

        elif (etype == QEvent.MouseButtonPress
              and event.button() == Qt.LeftButton):
            # Range finder: start dragging a reference highlight if the
            # press lands on one (takes precedence over click-to-insert).
            if self._ref_highlight_active:
                ti = self._ref_token_at(event.pos())
                if ti is not None and self._begin_ref_drag(ti, event):
                    return True
            # Cross-sheet pick: if another sheet is mid-formula-entry,
            # clicking a cell here inserts "<ThisSheet>!<ref>" into that
            # sheet's formula bar and returns focus to it.
            if (self._formula_entry_cell is None
                    and self._pick_cross_sheet_ref(event)):
                return True
            # Deselect any selected chart when clicking on the grid.
            prev = getattr(self, '_selected_chart', None)
            if prev:
                prev._set_selected(False)
                self._selected_chart = None

            # Deselect any selected overlay (shape / equation / image)
            # when clicking on the grid.
            from . import overlay as _ov
            _ov.deselect_all(self)

            # Capture inline editor state NOW, before Qt closes it.
            _live_editor = self._find_inline_editor()
            if (_live_editor and _live_editor.text().startswith("=")
                    and self._inline_formula_cell is None):
                r = self.table.currentRow()
                c = self.table.currentColumn()
                if r >= 0 and c >= 0:
                    self._inline_formula_cell = (r, c)
                    self._inline_formula_text = _live_editor.text()
                    self._inline_formula_pos = (
                        _live_editor.cursorPosition())

            # Formula entry mode: insert cell ref on click.
            # Check both explicit formula mode (formula bar) and
            # inline cell editor starting with "=".
            formula_cell = self._formula_entry_cell
            inline_editor = None
            saved_text = None
            saved_pos = 0
            if formula_cell is None:
                # Check for active inline cell editor with "=" text.
                editor = self._find_inline_editor()
                if editor and editor.text().startswith("="):
                    r = self.table.currentRow()
                    c = self.table.currentColumn()
                    if r >= 0 and c >= 0:
                        formula_cell = (r, c)
                        inline_editor = editor
                # Fallback: editor may already be gone, use saved state.
                if formula_cell is None and self._inline_formula_cell:
                    formula_cell = self._inline_formula_cell
                    saved_text = self._inline_formula_text
                    saved_pos = self._inline_formula_pos or 0

            if formula_cell is not None:
                idx = self.table.indexAt(event.pos())
                if idx.isValid():
                    r, c = idx.row(), idx.column()
                    fc_r, fc_c = formula_cell
                    if (r, c) != (fc_r, fc_c):
                        # Insert the clicked cell's reference NOW (consume
                        # the press so the editor stays open).  If the user
                        # then drags, the single ref is widened to a range
                        # (e.g. F3:F11) in _pick_drag_move.
                        ref = col_index_to_letter(c) + str(r + 1)
                        where = None
                        ins_start = 0
                        if inline_editor:
                            cp = inline_editor.cursorPosition()
                            text = inline_editor.text()
                            inline_editor.setText(text[:cp] + ref + text[cp:])
                            inline_editor.setCursorPosition(cp + len(ref))
                            inline_editor.setFocus()
                            self._update_ref_highlights(inline_editor.text())
                            where, ins_start = "editor", cp
                        elif saved_text is not None:
                            new_text = (saved_text[:saved_pos] + ref
                                        + saved_text[saved_pos:])
                            new_pos = saved_pos + len(ref)
                            self.table.setCurrentCell(fc_r, fc_c)
                            self.table.editItem(
                                self.table.item(fc_r, fc_c)
                                or self._ensure_item(fc_r, fc_c))
                            QTimer.singleShot(
                                0, lambda: self._set_inline_editor_text(
                                    new_text, new_pos))
                        else:
                            cp = self._formula_bar.cursorPosition()
                            text = self._formula_bar.text()
                            self._formula_bar.setText(
                                text[:cp] + ref + text[cp:])
                            self._formula_bar.setCursorPosition(cp + len(ref))
                            self._formula_bar.setFocus()
                            self._update_ref_highlights(
                                self._formula_bar.text())
                            where, ins_start = "bar", cp
                        self._arrow_nav_active = False
                        self._arrow_nav_pos = None
                        self._arrow_nav_ref_span = None
                        if where is not None:
                            self._pick_drag = {
                                "where": where, "anchor": (r, c),
                                "ins_start": ins_start, "ref_len": len(ref)}
                            try:
                                self.table.viewport().grabMouse()
                            except Exception:
                                pass
                        return True  # consume click
                    else:
                        # Clicked on the formula cell itself — clear state.
                        self._inline_formula_text = None
                        self._inline_formula_cell = None

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
                    self._fill_end_col = sel[0].rightColumn()
                    self._fill_direction = None  # decided on first move
                    return True

        elif (etype == QEvent.MouseButtonDblClick
              and event.button() == Qt.LeftButton):
            hr = self._fill_handle_rect()
            if hr and hr.contains(event.pos()):
                # Cancel any drag state from the preceding press.
                self._fill_dragging = False
                self._fill_anchor_range = None
                self._auto_fill_down()
                return True

        elif etype == QEvent.MouseMove and self._fill_dragging:
            row = self.table.rowAt(event.pos().y())
            col = self.table.columnAt(event.pos().x())
            s = self._fill_anchor_range
            if s is not None:
                # Determine direction from dominant axis on first move.
                # Positive dr/dc = down/right, negative = up/left.
                dr = (row - s.bottomRow()) if row >= 0 else 0
                dc = (col - s.rightColumn()) if col >= 0 else 0
                if dr >= 0 and row >= 0:
                    dr_top = 0
                else:
                    dr_top = (row - s.topRow()) if row >= 0 else 0
                if dc >= 0 and col >= 0:
                    dc_left = 0
                else:
                    dc_left = (col - s.leftColumn()) if col >= 0 else 0
                eff_dr = dr if dr != 0 else dr_top
                eff_dc = dc if dc != 0 else dc_left
                if self._fill_direction is None and (eff_dr or eff_dc):
                    self._fill_direction = (
                        "right" if abs(eff_dc) > abs(eff_dr) else "down")
                if self._fill_direction == "right":
                    if col >= 0:
                        self._fill_end_col = col
                        self._preview_fill()
                else:
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
        if self._fill_direction == "right":
            left = min(s.leftColumn(), self._fill_end_col)
            right = max(s.rightColumn(), self._fill_end_col)
            self.table.setRangeSelected(
                QTableWidgetSelectionRange(
                    s.topRow(), left, s.bottomRow(), right), True)
        else:
            top = min(s.topRow(), self._fill_end_row)
            bot = max(s.bottomRow(), self._fill_end_row)
            self.table.setRangeSelected(
                QTableWidgetSelectionRange(
                    top, s.leftColumn(), bot, s.rightColumn()), True)

    def _apply_fill(self):
        if self._fill_direction == "right":
            if self._fill_end_col > self._fill_anchor_range.rightColumn():
                self._apply_fill_right()
            elif self._fill_end_col < self._fill_anchor_range.leftColumn():
                self._apply_fill_left()
            return
        if self._fill_end_row > self._fill_anchor_range.bottomRow():
            self._apply_fill_down()
        elif self._fill_end_row < self._fill_anchor_range.topRow():
            self._apply_fill_up()

    def _apply_fill_down(self):
        s = self._fill_anchor_range
        if s is None:
            return
        src_top = s.topRow()
        src_bot = s.bottomRow()
        fill_end = self._fill_end_row
        if fill_end <= src_bot:
            return

        src_len = src_bot - src_top + 1
        changes = []
        self.table.blockSignals(True)
        try:
            for c in range(s.leftColumn(), s.rightColumn() + 1):
                # Check if any source cell has a formula.
                formulas = []
                vals = []
                for r in range(src_top, src_bot + 1):
                    it = self.table.item(r, c)
                    vals.append(it.text() if it else "")
                    formulas.append(
                        self._cell_formulas.get((r, c)))

                has_formulas = any(f is not None for f in formulas)

                if has_formulas:
                    # Formula fill: shift cell references.
                    for r in range(src_bot + 1, fill_end + 1):
                        src_idx = (r - src_top) % src_len
                        src_r = src_top + src_idx
                        f = formulas[src_idx]
                        if f:
                            d_row = r - src_r
                            shifted = shift_formula(f, d_row, 0)
                            self._cell_formulas[(r, c)] = shifted
                            result = self._evaluate_formula(
                                shifted, r, c)
                            text = str(result)
                        else:
                            text = vals[src_idx]
                            self._cell_formulas.pop((r, c), None)

                        self._shadow[(r, c)] = text
                        text = self._apply_cell_number_format(
                            text, r, c)
                        it = self.table.item(r, c)
                        old = it.text() if it else ""
                        if it is None:
                            it = QTableWidgetItem(text)
                            self.table.setItem(r, c, it)
                        else:
                            it.setText(text)
                        if old != text:
                            changes.append((r, c, old, text))
                else:
                    # Value fill: detect numeric patterns.
                    pattern = self._detect_pattern(vals)
                    for r in range(src_bot + 1, fill_end + 1):
                        idx = r - src_top
                        text = self._pattern_value(
                            pattern, idx, vals)
                        self._shadow[(r, c)] = text
                        text = self._apply_cell_number_format(
                            text, r, c)
                        it = self.table.item(r, c)
                        old = it.text() if it else ""
                        if it is None:
                            it = QTableWidgetItem(text)
                            self.table.setItem(r, c, it)
                        else:
                            it.setText(text)
                        if old != text:
                            changes.append((r, c, old, text))
        finally:
            self.table.blockSignals(False)
        if changes and self._undo_stack is not None:
            self._undo_stack.push(
                BulkCellEditCmd(self, changes, "Drag fill"))
        # Recalculate cells that depend on any changed cell.
        for r, c, _old, _new in changes:
            self._recalc_dependents(r, c)
        self._refresh_cross_sheet()
        self._fill_anchor_range = None

    def _apply_fill_right(self):
        """Fill horizontally (rightward) — mirrors _apply_fill_down."""
        s = self._fill_anchor_range
        if s is None:
            return
        src_left = s.leftColumn()
        src_right = s.rightColumn()
        fill_end = self._fill_end_col
        if fill_end <= src_right:
            return

        src_len = src_right - src_left + 1
        changes = []
        self.table.blockSignals(True)
        try:
            for r in range(s.topRow(), s.bottomRow() + 1):
                formulas = []
                vals = []
                for c in range(src_left, src_right + 1):
                    it = self.table.item(r, c)
                    vals.append(it.text() if it else "")
                    formulas.append(
                        self._cell_formulas.get((r, c)))

                has_formulas = any(f is not None for f in formulas)

                if has_formulas:
                    for c in range(src_right + 1, fill_end + 1):
                        src_idx = (c - src_left) % src_len
                        src_c = src_left + src_idx
                        f = formulas[src_idx]
                        if f:
                            d_col = c - src_c
                            shifted = shift_formula(f, 0, d_col)
                            self._cell_formulas[(r, c)] = shifted
                            result = self._evaluate_formula(
                                shifted, r, c)
                            text = str(result)
                        else:
                            text = vals[src_idx]
                            self._cell_formulas.pop((r, c), None)

                        self._shadow[(r, c)] = text
                        text = self._apply_cell_number_format(
                            text, r, c)
                        it = self.table.item(r, c)
                        old = it.text() if it else ""
                        if it is None:
                            it = QTableWidgetItem(text)
                            self.table.setItem(r, c, it)
                        else:
                            it.setText(text)
                        if old != text:
                            changes.append((r, c, old, text))
                else:
                    pattern = self._detect_pattern(vals)
                    for c in range(src_right + 1, fill_end + 1):
                        idx = c - src_left
                        text = self._pattern_value(
                            pattern, idx, vals)
                        self._shadow[(r, c)] = text
                        text = self._apply_cell_number_format(
                            text, r, c)
                        it = self.table.item(r, c)
                        old = it.text() if it else ""
                        if it is None:
                            it = QTableWidgetItem(text)
                            self.table.setItem(r, c, it)
                        else:
                            it.setText(text)
                        if old != text:
                            changes.append((r, c, old, text))
        finally:
            self.table.blockSignals(False)
        if changes and self._undo_stack is not None:
            self._undo_stack.push(
                BulkCellEditCmd(self, changes, "Drag fill"))
        for r, c, _old, _new in changes:
            self._recalc_dependents(r, c)
        self._refresh_cross_sheet()
        self._fill_anchor_range = None

    def _apply_fill_up(self):
        """Fill upward — mirrors _apply_fill_down."""
        s = self._fill_anchor_range
        if s is None:
            return
        src_top = s.topRow()
        src_bot = s.bottomRow()
        fill_end = self._fill_end_row
        if fill_end >= src_top:
            return

        src_len = src_bot - src_top + 1
        changes = []
        self.table.blockSignals(True)
        try:
            for c in range(s.leftColumn(), s.rightColumn() + 1):
                formulas = []
                vals = []
                for r in range(src_top, src_bot + 1):
                    it = self.table.item(r, c)
                    vals.append(it.text() if it else "")
                    formulas.append(self._cell_formulas.get((r, c)))

                has_formulas = any(f is not None for f in formulas)

                if has_formulas:
                    for r in range(src_top - 1, fill_end - 1, -1):
                        src_idx = (src_top - r) % src_len
                        src_r = src_top + (src_len - 1 - src_idx) % src_len
                        f = formulas[(src_len - 1 - src_idx) % src_len]
                        if f:
                            d_row = r - src_r
                            shifted = shift_formula(f, d_row, 0)
                            self._cell_formulas[(r, c)] = shifted
                            result = self._evaluate_formula(
                                shifted, r, c)
                            text = str(result)
                        else:
                            text = vals[(src_len - 1 - src_idx) % src_len]
                            self._cell_formulas.pop((r, c), None)

                        self._shadow[(r, c)] = text
                        text = self._apply_cell_number_format(text, r, c)
                        it = self.table.item(r, c)
                        old = it.text() if it else ""
                        if it is None:
                            it = QTableWidgetItem(text)
                            self.table.setItem(r, c, it)
                        else:
                            it.setText(text)
                        if old != text:
                            changes.append((r, c, old, text))
                else:
                    pattern = self._detect_pattern(vals)
                    for r in range(src_top - 1, fill_end - 1, -1):
                        idx = -(r - src_top)
                        text = self._pattern_value_reverse(
                            pattern, idx, vals)
                        self._shadow[(r, c)] = text
                        text = self._apply_cell_number_format(text, r, c)
                        it = self.table.item(r, c)
                        old = it.text() if it else ""
                        if it is None:
                            it = QTableWidgetItem(text)
                            self.table.setItem(r, c, it)
                        else:
                            it.setText(text)
                        if old != text:
                            changes.append((r, c, old, text))
        finally:
            self.table.blockSignals(False)
        if changes and self._undo_stack is not None:
            self._undo_stack.push(
                BulkCellEditCmd(self, changes, "Drag fill up"))
        for r, c, _old, _new in changes:
            self._recalc_dependents(r, c)
        self._refresh_cross_sheet()
        self._fill_anchor_range = None

    def _apply_fill_left(self):
        """Fill leftward — mirrors _apply_fill_right."""
        s = self._fill_anchor_range
        if s is None:
            return
        src_left = s.leftColumn()
        src_right = s.rightColumn()
        fill_end = self._fill_end_col
        if fill_end >= src_left:
            return

        src_len = src_right - src_left + 1
        changes = []
        self.table.blockSignals(True)
        try:
            for r in range(s.topRow(), s.bottomRow() + 1):
                formulas = []
                vals = []
                for c in range(src_left, src_right + 1):
                    it = self.table.item(r, c)
                    vals.append(it.text() if it else "")
                    formulas.append(self._cell_formulas.get((r, c)))

                has_formulas = any(f is not None for f in formulas)

                if has_formulas:
                    for c in range(src_left - 1, fill_end - 1, -1):
                        src_idx = (src_left - c) % src_len
                        src_c = src_left + (src_len - 1 - src_idx) % src_len
                        f = formulas[(src_len - 1 - src_idx) % src_len]
                        if f:
                            d_col = c - src_c
                            shifted = shift_formula(f, 0, d_col)
                            self._cell_formulas[(r, c)] = shifted
                            result = self._evaluate_formula(
                                shifted, r, c)
                            text = str(result)
                        else:
                            text = vals[(src_len - 1 - src_idx) % src_len]
                            self._cell_formulas.pop((r, c), None)

                        self._shadow[(r, c)] = text
                        text = self._apply_cell_number_format(text, r, c)
                        it = self.table.item(r, c)
                        old = it.text() if it else ""
                        if it is None:
                            it = QTableWidgetItem(text)
                            self.table.setItem(r, c, it)
                        else:
                            it.setText(text)
                        if old != text:
                            changes.append((r, c, old, text))
                else:
                    pattern = self._detect_pattern(vals)
                    for c in range(src_left - 1, fill_end - 1, -1):
                        idx = -(c - src_left)
                        text = self._pattern_value_reverse(
                            pattern, idx, vals)
                        self._shadow[(r, c)] = text
                        text = self._apply_cell_number_format(text, r, c)
                        it = self.table.item(r, c)
                        old = it.text() if it else ""
                        if it is None:
                            it = QTableWidgetItem(text)
                            self.table.setItem(r, c, it)
                        else:
                            it.setText(text)
                        if old != text:
                            changes.append((r, c, old, text))
        finally:
            self.table.blockSignals(False)
        if changes and self._undo_stack is not None:
            self._undo_stack.push(
                BulkCellEditCmd(self, changes, "Drag fill left"))
        for r, c, _old, _new in changes:
            self._recalc_dependents(r, c)
        self._refresh_cross_sheet()
        self._fill_anchor_range = None

    def _auto_fill_down(self):
        """Double-click fill handle: auto-fill down to match the extent
        of the adjacent column's data (Excel behaviour)."""
        sel = self.table.selectedRanges()
        if not sel:
            r = self.table.currentRow()
            c = self.table.currentColumn()
            if r < 0 or c < 0:
                return
            sel = [QTableWidgetSelectionRange(r, c, r, c)]
        s = sel[0]
        src_bot = s.bottomRow()
        left_col = s.leftColumn()
        right_col = s.rightColumn()

        # Find the data extent by scanning adjacent columns (left first,
        # then right) for the last non-empty row starting from src_bot.
        last_data_row = src_bot
        for adj_col in (left_col - 1, right_col + 1):
            if adj_col < 0 or adj_col >= self.table.columnCount():
                continue
            for r in range(src_bot + 1, self.row_count()):
                it = self.table.item(r, adj_col)
                if it and it.text().strip():
                    last_data_row = r
                else:
                    break
            if last_data_row > src_bot:
                break

        if last_data_row <= src_bot:
            return

        self._fill_anchor_range = s
        self._fill_end_row = last_data_row
        self._apply_fill()
        # Select the filled range.
        self.table.setRangeSelected(
            QTableWidgetSelectionRange(
                s.topRow(), left_col, last_data_row, right_col),
            True)

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
            return f"{val:.2f}"
        elif pt == "constant":
            return pattern["value"]
        elif pt == "numeric_repeat":
            return f"{pattern['values'][idx % src_n]:.2f}"
        else:
            return pattern["values"][idx % src_n]

    def _pattern_value_reverse(self, pattern, idx, source_vals):
        """Like _pattern_value but for filling in the reverse direction.
        idx=1 is one step before the source start, idx=2 is two steps, etc."""
        pt = pattern["type"]
        src_n = len(source_vals)
        if pt == "linear":
            val = pattern["start"] - pattern["step"] * idx
            return f"{val:.2f}"
        elif pt == "constant":
            return pattern["value"]
        elif pt == "numeric_repeat":
            return f"{pattern['values'][(-idx) % src_n]:.2f}"
        else:
            return pattern["values"][(-idx) % src_n]
