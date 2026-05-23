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


def shift_formula(formula: str, d_row: int, d_col: int) -> str:
    """Shift cell references in *formula* by (d_row, d_col).

    Handles Excel-style absolute references:
      $A$1 — both fixed    $A1 — column fixed    A$1 — row fixed
      A1   — both relative
    """
    import re

    def _shift(m):
        dollar_col = m.group(1) or ""   # '$' or ''
        letters = m.group(2)
        dollar_row = m.group(3) or ""   # '$' or ''
        row_num = int(m.group(4))

        if not dollar_col:
            new_col = letter_to_col_index(letters) + d_col
            if new_col < 0:
                new_col = 0
            letters = col_index_to_letter(new_col)
        if not dollar_row:
            row_num += d_row
            if row_num < 1:
                row_num = 1

        return f"{dollar_col}{letters}{dollar_row}{row_num}"

    # Match optional $ before letters and optional $ before digits.
    return re.sub(
        r'(\$?)([A-Z]+)(\$?)(\d+)',
        _shift, formula, flags=re.IGNORECASE)


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


def _format_number(value):
    """Format a numeric result for cell display.

    Rules:
    - Integers display without decimals: 2, 100, -5
    - Floats show up to 3 decimal places by default, trailing zeros
      stripped: 3.14, 0.5, 2 (not 2.000)
    - If the number has meaningful precision beyond 3 decimals, show
      all significant digits up to 10: 3.14159265
    - Non-numeric results pass through unchanged.
    """
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return value
    if not isinstance(value, float):
        return value
    # Exact integer floats.
    if value == int(value) and abs(value) < 1e15:
        return int(value)
    # Round to 10 significant decimals to remove float noise.
    rounded = round(value, 10)
    # Format with up to 10 decimals, then strip trailing zeros.
    s = f"{rounded:.10f}"
    s = s.rstrip("0").rstrip(".")
    return s


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
        self._formula_bar.textChanged.connect(self._on_formula_bar_text)

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

        # ── Cell format delegate (borders) ──────────────────────────
        from .cellformat import CellFormat, CellFormatDelegate
        self._cell_formats: dict = {}    # (row, col) → CellFormat
        self._fmt_delegate = CellFormatDelegate(
            self._cell_formats, self.table)
        self.table.setItemDelegate(self._fmt_delegate)

        # ── Internal state ───────────────────────────────────────────
        self._shadow: dict = {}          # (row, col) → last-known text
        self._cell_formulas: dict = {}   # (row, col) → "=formula"
        self._dependents: dict = {}      # (row, col) → set of (r, c) that depend on it
        self._col_formats: dict = {}     # col → format string
        self._col_designations: dict = {}  # col → "X" or "Y"

        # Formula entry mode: when editing a formula, clicking a cell
        # inserts a cell reference instead of navigating.
        self._formula_entry_cell = None   # (row, col) being edited
        self._ref_highlight_active = False
        # Arrow-key cell reference navigation state.
        self._arrow_nav_active = False
        self._arrow_nav_pos = None       # (row, col) of ref cursor
        self._arrow_nav_ref_span = None  # (start, end) char indices in editor

        # Signals
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.currentCellChanged.connect(self._on_current_cell_changed)

        # ── Drag-fill state ──────────────────────────────────────────
        self._fill_dragging = False
        self._fill_anchor_range = None
        self._fill_end_row = None
        self.table.viewport().setMouseTracking(True)
        self.table.viewport().installEventFilter(self)
        self.table.installEventFilter(self)
        self._formula_bar.installEventFilter(self)

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

    # ── Cell formatting (fill + borders) ───────────────────────────
    def set_cell_bg(self, row: int, col: int,
                    color_hex: Optional[str]):
        """Set the background colour of a single cell."""
        from .cellformat import CellFormat
        cf = self._cell_formats.setdefault((row, col), CellFormat())
        cf.bg_color = color_hex
        it = self.table.item(row, col)
        if it is None:
            it = QTableWidgetItem("")
            self.table.setItem(row, col, it)
        if color_hex:
            it.setBackground(QColor(color_hex))
        else:
            it.setBackground(QBrush())   # reset to default
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
        self._cell_formats.pop((row, col), None)
        it = self.table.item(row, col)
        if it:
            it.setBackground(QBrush())
        self.table.viewport().update()

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
        # Clear formula highlights when navigating away (unless in
        # formula entry mode where clicking inserts a ref).
        if self._formula_entry_cell is None:
            self._clear_ref_highlights()

        if row < 0 or col < 0:
            self._cell_ref_label.setText("")
            self._formula_bar.clear()
            return

        ref = f"{col_index_to_letter(col)}{row + 1}"
        self._cell_ref_label.setText(ref)
        # Show formula if cell has one, otherwise show value.
        formula = self._cell_formulas.get((row, col))
        if formula:
            self._formula_bar.setText(formula)
            # Show ref highlights for existing formulas when selected.
            if not self._formula_bar.hasFocus():
                self._update_ref_highlights(formula)
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
            self._register_deps(row, col, new_text)
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
            self._unregister_deps(row, col)
            # Format plain numbers (strip trailing zeros).
            if new_text:
                try:
                    v = float(new_text)
                    formatted = str(_format_number(v))
                    if formatted != new_text:
                        self.table.blockSignals(True)
                        it.setText(formatted)
                        self.table.blockSignals(False)
                        new_text = formatted
                except ValueError:
                    pass

        self._shadow[(row, col)] = new_text

        if self._undo_stack and old_text != new_text:
            cmd = CellEditCmd(self, row, col, old_text, new_text)
            self._undo_stack.push(cmd)

        self.data_changed.emit(col)

        # Recalculate any cells that depend on this one.
        self._recalc_dependents(row, col)

    # ── Dependency tracking ──────────────────────────────────────────
    def _register_deps(self, row, col, formula):
        """Parse *formula* for cell refs and register (row, col) as
        a dependent of each referenced cell."""
        self._unregister_deps(row, col)
        refs = self._parse_cell_refs(formula)
        for ref_key in refs:
            self._dependents.setdefault(ref_key, set()).add((row, col))

    def _unregister_deps(self, row, col):
        """Remove (row, col) from all dependency sets."""
        key = (row, col)
        for deps in self._dependents.values():
            deps.discard(key)

    def _recalc_dependents(self, row, col, visited=None):
        """Re-evaluate cells that depend on (row, col), recursively."""
        if visited is None:
            visited = set()
        deps = self._dependents.get((row, col))
        if not deps:
            return
        for (dr, dc) in list(deps):
            if (dr, dc) in visited:
                continue
            visited.add((dr, dc))
            formula = self._cell_formulas.get((dr, dc))
            if not formula:
                continue
            result = str(self._evaluate_formula(formula, dr, dc))
            self.table.blockSignals(True)
            it = self.table.item(dr, dc)
            if it is None:
                it = QTableWidgetItem(result)
                self.table.setItem(dr, dc, it)
            else:
                it.setText(result)
            self._shadow[(dr, dc)] = result
            self.table.blockSignals(False)
            # Cascade: recalc cells that depend on this one too.
            self._recalc_dependents(dr, dc, visited)

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
            self._update_ref_highlights(text)
        elif not text.startswith("="):
            self._formula_entry_cell = None
            self._clear_ref_highlights()

    def _exit_formula_mode(self):
        self._formula_entry_cell = None
        self._arrow_nav_active = False
        self._arrow_nav_pos = None
        self._arrow_nav_ref_span = None
        self._clear_ref_highlights()

    def _apply_formula_bar(self):
        self._formula_entry_cell = None
        self._arrow_nav_active = False
        self._arrow_nav_pos = None
        self._arrow_nav_ref_span = None
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

    # ── Formula reference highlighting ─────────────────────────────
    _REF_PATTERN = None  # compiled lazily

    def _parse_cell_refs(self, formula_text: str):
        """Extract unique (row, col) positions from cell references
        in *formula_text*.  Returns a list of (row, col) in the order
        each ref first appears."""
        import re
        if self._REF_PATTERN is None:
            SheetWidget._REF_PATTERN = re.compile(
                r'\$?([A-Za-z]{1,3})\$?(\d{1,7})')
        seen = set()
        result = []
        for m in self._REF_PATTERN.finditer(formula_text):
            letters = m.group(1).upper()
            row_num = int(m.group(2))
            c = letter_to_col_index(letters)
            r = row_num - 1
            if r < 0 or c < 0:
                continue
            key = (r, c)
            if key not in seen:
                seen.add(key)
                result.append(key)
        return result

    def _update_ref_highlights(self, text: str):
        """Parse cell refs from *text* and highlight them on the grid."""
        from .cellformat import CellFormatDelegate
        delegate = self._fmt_delegate
        refs = self._parse_cell_refs(text)
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
        for (r, c) in old:
            idx = self.table.model().index(r, c)
            self.table.update(idx)

    # ── Formula evaluation (basic) ───────────────────────────────────
    def _evaluate_formula(self, formula: str, row: int, col: int):
        """Evaluate a cell formula.

        Supports:
        - Cell refs: A1, b5, AA12 (case-insensitive)
        - Arithmetic: A1+5, A1*A3, A1^2, A1**2
        - Range functions: SUM(A1:A10), AVERAGE(B1:B20)
        - Whole-column functions: max(A), min(B), mean(A),
          sum(C), average(A), count(A)
        - Math: abs, round, int, float, math.*, np.*
        """
        expr = formula[1:]  # strip leading =
        try:
            import math
            import re

            import datetime as _dt

            def _mean(vals):
                v = list(vals)
                return sum(v) / len(v) if v else 0

            # ── Date & Time helpers ──────────────────────────────
            def _DATE(y, m, d):
                return _dt.date(int(y), int(m), int(d)).isoformat()

            def _TODAY():
                return _dt.date.today().isoformat()

            def _NOW():
                return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            def _TIME(h, m, s=0):
                return _dt.time(int(h), int(m), int(s)).isoformat()

            def _YEAR(d):
                return _dt.date.fromisoformat(str(d)).year

            def _MONTH(d):
                return _dt.date.fromisoformat(str(d)).month

            def _DAY(d):
                return _dt.date.fromisoformat(str(d)).day

            def _HOUR(t):
                return _dt.time.fromisoformat(str(t)).hour

            def _MINUTE(t):
                return _dt.time.fromisoformat(str(t)).minute

            def _SECOND(t):
                return _dt.time.fromisoformat(str(t)).second

            def _DAYS(end, start):
                a = _dt.date.fromisoformat(str(end))
                b = _dt.date.fromisoformat(str(start))
                return (a - b).days

            def _WEEKDAY(d):
                return _dt.date.fromisoformat(str(d)).isoweekday()

            # ── Text helpers ─────────────────────────────────────
            def _LEFT(t, n=1):
                return str(t)[:int(n)]

            def _RIGHT(t, n=1):
                return str(t)[-int(n):]

            def _MID(t, start, n):
                s = str(t)
                return s[int(start) - 1:int(start) - 1 + int(n)]

            def _LEN(t):
                return len(str(t))

            def _LOWER(t):
                return str(t).lower()

            def _UPPER(t):
                return str(t).upper()

            def _PROPER(t):
                return str(t).title()

            def _TRIM(t):
                return " ".join(str(t).split())

            def _CONCAT(*args):
                return "".join(str(a) for a in args)

            def _SUBSTITUTE(t, old, new, instance=None):
                s = str(t)
                if instance is None:
                    return s.replace(str(old), str(new))
                # Replace only the n-th occurrence.
                count = 0
                idx = 0
                old_s, new_s = str(old), str(new)
                while True:
                    pos = s.find(old_s, idx)
                    if pos == -1:
                        return s
                    count += 1
                    if count == int(instance):
                        return s[:pos] + new_s + s[pos + len(old_s):]
                    idx = pos + 1

            def _REPT(t, n):
                return str(t) * int(n)

            def _FIND(find, within, start=1):
                pos = str(within).find(str(find), int(start) - 1)
                return pos + 1 if pos >= 0 else "#VALUE!"

            def _REPLACE(old, start, n, new):
                s = str(old)
                i = int(start) - 1
                return s[:i] + str(new) + s[i + int(n):]

            def _EXACT(a, b):
                return str(a) == str(b)

            def _VALUE(t):
                return float(str(t))

            def _TEXT(v, fmt):
                return format(float(v), str(fmt))

            # ── Logical helpers ──────────────────────────────────
            def _IF(cond, true_val, false_val=""):
                return true_val if cond else false_val

            def _AND(*args):
                return all(args)

            def _OR(*args):
                return any(args)

            def _NOT(val):
                return not val

            def _IFERROR(val, fallback):
                # Evaluated eagerly so errors in val are already
                # caught by the outer try/except — use as best-effort.
                return val if val != "#ERROR" else fallback

            def _XOR(*args):
                return sum(bool(a) for a in args) % 2 == 1

            # ── Math extras ──────────────────────────────────────
            def _MOD(n, d):
                return float(n) % float(d)

            def _POWER(n, p):
                return float(n) ** float(p)

            def _QUOTIENT(n, d):
                return int(float(n) // float(d))

            def _SIGN(n):
                n = float(n)
                return 1 if n > 0 else (-1 if n < 0 else 0)

            def _EVEN(n):
                n = math.ceil(abs(float(n)))
                return n + (n % 2) if float(n) >= 0 else -(n + (n % 2))  # noqa: E501

            def _ODD(n):
                n = math.ceil(abs(float(n)))
                if n % 2 == 0:
                    n += 1
                return n if float(n) >= 0 else -n

            def _FACT(n):
                return math.factorial(int(n))

            def _GCD(*args):
                from math import gcd
                result = int(args[0])
                for a in args[1:]:
                    result = gcd(result, int(a))
                return result

            def _LCM(*args):
                from math import gcd
                result = int(args[0])
                for a in args[1:]:
                    result = result * int(a) // gcd(result, int(a))
                return result

            def _RAND():
                import random
                return random.random()

            def _RANDBETWEEN(lo, hi):
                import random
                return random.randint(int(lo), int(hi))

            def _ROUNDDOWN(n, d):
                m = 10 ** int(d)
                return math.trunc(float(n) * m) / m

            def _ROUNDUP(n, d):
                m = 10 ** int(d)
                v = float(n) * m
                return (math.ceil(v) if v >= 0
                        else math.floor(v)) / m

            def _TRUNC(n, d=0):
                m = 10 ** int(d)
                return math.trunc(float(n) * m) / m

            def _COMBIN(n, k):
                return math.comb(int(n), int(k))

            def _DEGREES(r):
                return math.degrees(float(r))

            def _RADIANS(d):
                return math.radians(float(d))

            ns = {"__builtins__": {}, "math": math, "np": np,
                  "abs": abs, "round": round, "int": int, "float": float,
                  "sum": sum, "min": min, "max": max, "len": len,
                  "mean": _mean, "avg": _mean,
                  "PI": math.pi, "pi": math.pi,
                  "sqrt": math.sqrt, "log": math.log,
                  "log10": math.log10, "exp": math.exp,
                  "sin": math.sin, "cos": math.cos, "tan": math.tan,
                  "asin": math.asin, "acos": math.acos, "atan": math.atan,
                  "atan2": math.atan2,
                  "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
                  "asinh": math.asinh, "acosh": math.acosh, "atanh": math.atanh,
                  # Date & Time
                  "DATE": _DATE, "TODAY": _TODAY, "NOW": _NOW,
                  "TIME": _TIME, "YEAR": _YEAR, "MONTH": _MONTH,
                  "DAY": _DAY, "HOUR": _HOUR, "MINUTE": _MINUTE,
                  "SECOND": _SECOND, "DAYS": _DAYS, "WEEKDAY": _WEEKDAY,
                  # Text
                  "LEFT": _LEFT, "RIGHT": _RIGHT, "MID": _MID,
                  "LEN": _LEN, "LOWER": _LOWER, "UPPER": _UPPER,
                  "PROPER": _PROPER, "TRIM": _TRIM,
                  "CONCAT": _CONCAT, "CONCATENATE": _CONCAT,
                  "SUBSTITUTE": _SUBSTITUTE, "REPT": _REPT,
                  "FIND": _FIND, "REPLACE": _REPLACE,
                  "EXACT": _EXACT, "VALUE": _VALUE, "TEXT": _TEXT,
                  # Logical
                  "IF": _IF, "AND": _AND, "OR": _OR, "NOT": _NOT,
                  "IFERROR": _IFERROR, "XOR": _XOR,
                  "TRUE": True, "FALSE": False,
                  # Math extras
                  "MOD": _MOD, "POWER": _POWER,
                  "QUOTIENT": _QUOTIENT, "SIGN": _SIGN,
                  "EVEN": _EVEN, "ODD": _ODD, "FACT": _FACT,
                  "GCD": _GCD, "LCM": _LCM,
                  "RAND": _RAND, "RANDBETWEEN": _RANDBETWEEN,
                  "ROUNDDOWN": _ROUNDDOWN, "ROUNDUP": _ROUNDUP,
                  "TRUNC": _TRUNC, "COMBIN": _COMBIN,
                  "DEGREES": _DEGREES, "RADIANS": _RADIANS,
                  "LN": math.log, "PRODUCT": math.prod,
                  }

            # 1. Expand range functions: SUM(A1:A10)
            expr = self._expand_range_functions(expr)

            # 2. Expand whole-column functions: max(A), min(B), etc.
            expr = self._expand_column_functions(expr)

            # 3. Replace cell refs like A1, B5 with numeric values.
            def _cell_ref(m):
                letters = m.group(1)
                rnum = int(m.group(2)) - 1
                c = letter_to_col_index(letters)
                it = self.table.item(rnum, c)
                if it and it.text():
                    try:
                        return str(float(it.text()))
                    except ValueError:
                        return "0"
                return "0"

            # Match cell refs: 1-3 letters + digits (A1, AB12, etc.)
            # but not known functions like log10, exp2.
            _SKIP = {"log", "exp", "sin", "cos", "tan", "sqrt",
                     "abs", "int", "sum", "min", "max", "len",
                     "avg", "mean", "count", "stdev", "round",
                     "float", "math", "PI", "pi", "np",
                     "asin", "acos", "atan",
                     "sinh", "cosh", "tanh",
                     "asinh", "acosh", "atanh",
                     "DATE", "TODAY", "NOW", "TIME",
                     "YEAR", "MONTH", "DAY", "HOUR",
                     "MINUTE", "SECOND", "DAYS", "WEEKDAY",
                     "LEFT", "RIGHT", "MID", "LEN",
                     "LOWER", "UPPER", "PROPER", "TRIM",
                     "CONCAT", "CONCATENATE", "SUBSTITUTE",
                     "REPT", "FIND", "REPLACE", "EXACT",
                     "VALUE", "TEXT",
                     "IF", "AND", "OR", "NOT",
                     "IFERROR", "XOR", "TRUE", "FALSE",
                     "MOD", "POWER", "QUOTIENT", "SIGN",
                     "EVEN", "ODD", "FACT", "GCD", "LCM",
                     "RAND", "RANDBETWEEN",
                     "ROUNDDOWN", "ROUNDUP", "TRUNC",
                     "COMBIN", "DEGREES", "RADIANS",
                     "LN", "PRODUCT"}

            def _safe_cell_ref(m):
                name = m.group(1)
                if name.lower() in {s.lower() for s in _SKIP}:
                    return m.group(0)
                return _cell_ref(m)

            expr = re.sub(r'\b([A-Za-z]{1,3})(\d+)\b',
                          _safe_cell_ref, expr)

            # 4. Replace ^ with ** for exponentiation.
            expr = expr.replace("^", "**")

            result = eval(expr, ns)  # noqa: S307
            return _format_number(result)
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

            if func in ("sum",):
                return str(sum(vals)) if vals else "0"
            elif func in ("average", "avg", "mean"):
                return (str(sum(vals) / len(vals))
                        if vals else "0")
            elif func == "min":
                return str(min(vals)) if vals else "0"
            elif func == "max":
                return str(max(vals)) if vals else "0"
            elif func == "count":
                return str(len(vals))
            elif func == "stdev":
                if len(vals) < 2:
                    return "0"
                m_ = sum(vals) / len(vals)
                return str((sum((v - m_)**2 for v in vals)
                            / (len(vals) - 1)) ** 0.5)
            return m.group(0)

        pattern = (r'(SUM|AVERAGE|AVG|MEAN|MIN|MAX|COUNT|STDEV)'
                   r'\s*\(\s*'
                   r'([A-Z]+)(\d+)\s*:\s*([A-Z]+)(\d+)\s*\)')
        return re.sub(pattern, _expand_range, expr,
                      flags=re.IGNORECASE)

    def _expand_column_functions(self, expr: str) -> str:
        """Expand whole-column functions like max(A), min(B),
        mean(A), sum(C), average(A), count(A)."""
        import re

        def _expand_col(m):
            func = m.group(1).lower()
            col_letter = m.group(2).upper()
            c = letter_to_col_index(col_letter)
            vals = []
            for r in range(self.row_count()):
                it = self.table.item(r, c)
                if it and it.text():
                    try:
                        vals.append(float(it.text()))
                    except ValueError:
                        pass

            if func in ("sum",):
                return str(sum(vals)) if vals else "0"
            elif func in ("average", "avg", "mean"):
                return (str(sum(vals) / len(vals))
                        if vals else "0")
            elif func == "min":
                return str(min(vals)) if vals else "0"
            elif func == "max":
                return str(max(vals)) if vals else "0"
            elif func == "count":
                return str(len(vals))
            elif func == "stdev":
                if len(vals) < 2:
                    return "0"
                m_ = sum(vals) / len(vals)
                return str((sum((v - m_)**2 for v in vals)
                            / (len(vals) - 1)) ** 0.5)
            return m.group(0)

        # Match func(A) where A is one or more letters (no digit).
        pattern = (r'(SUM|AVERAGE|AVG|MEAN|MIN|MAX|COUNT|STDEV)'
                   r'\s*\(\s*([A-Z]+)\s*\)')
        return re.sub(pattern, _expand_col, expr,
                      flags=re.IGNORECASE)

    # ── Plot types ───────────────────────────────────────────────────
    PLOT_TYPES = [
        "Line", "Scatter", "Line+Symbol", "Bar", "Step",
        "Stem", "Histogram", "Box",
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
        for d in ("X", "Y"):
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

    def _cell_menu(self, pos):
        menu = QMenu(self)

        # Plot submenu first (like KhervePlot)
        sel = self.selected_columns()
        if sel:
            self._add_plot_submenu(menu, sel)
            menu.addSeparator()

        menu.addAction("Cu&t", self._cut_selection)
        menu.addAction("&Copy", self._copy_selection)
        menu.addAction("&Paste", self._paste_clipboard)
        menu.addAction("Cl&ear", self._clear_selection)

        menu.addSeparator()

        menu.addAction("Insert Row Above", self._insert_row_above)
        menu.addAction("Insert Row Below", self._insert_row_below)
        menu.addAction("Delete Row(s)", self._delete_selected_rows)
        menu.addAction("Add 10 Rows", self._add_10_rows)

        menu.exec_(self.table.viewport().mapToGlobal(pos))

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

    def eventFilter(self, obj, event):
        # ── Formula bar arrow key interception ───────────────────
        if obj is self._formula_bar and event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
                if (self._formula_entry_cell is not None
                        and self._should_arrow_insert_ref(self._formula_bar)):
                    if self._handle_arrow_key(key, self._formula_bar):
                        return True
            elif key == Qt.Key_Escape:
                self._exit_formula_mode()
            else:
                # Any non-arrow key breaks arrow nav mode.
                self._arrow_nav_active = False
                self._arrow_nav_pos = None
                self._arrow_nav_ref_span = None

        # ── Table-level key interception for inline "=" editors ────
        if obj is self.table and event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
                # Find active inline editor.
                editor = self._find_inline_editor()
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
            # Deselect any selected chart when clicking on the grid.
            prev = getattr(self, '_selected_chart', None)
            if prev:
                prev._set_selected(False)
                self._selected_chart = None

            # Formula entry mode: insert cell ref on click.
            # Check both explicit formula mode (formula bar) and
            # inline cell editor starting with "=".
            formula_cell = self._formula_entry_cell
            inline_editor = None
            if formula_cell is None:
                # Check for active inline cell editor with "=" text.
                editor = self.table.findChild(QLineEdit, "",
                                              Qt.FindDirectChildrenOnly)
                if editor is None:
                    # Editor may be a child of the viewport.
                    vp = self.table.viewport()
                    for child in vp.children():
                        if isinstance(child, QLineEdit):
                            editor = child
                            break
                if editor and editor is not self._formula_bar:
                    txt = editor.text()
                    if txt.startswith("="):
                        r = self.table.currentRow()
                        c = self.table.currentColumn()
                        if r >= 0 and c >= 0:
                            formula_cell = (r, c)
                            inline_editor = editor

            if formula_cell is not None:
                idx = self.table.indexAt(event.pos())
                if idx.isValid():
                    r, c = idx.row(), idx.column()
                    fc_r, fc_c = formula_cell
                    if (r, c) != (fc_r, fc_c):
                        ref = col_index_to_letter(c) + str(r + 1)
                        target = inline_editor or self._formula_bar
                        cp = target.cursorPosition()
                        text = target.text()
                        target.setText(text[:cp] + ref + text[cp:])
                        target.setCursorPosition(cp + len(ref))
                        target.setFocus()
                        # Reset arrow nav — click takes over.
                        self._arrow_nav_active = False
                        self._arrow_nav_pos = None
                        self._arrow_nav_ref_span = None
                        return True  # consume click

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
                else:
                    # Value fill: detect numeric patterns.
                    pattern = self._detect_pattern(vals)
                    for r in range(src_bot + 1, fill_end + 1):
                        idx = r - src_top
                        text = self._pattern_value(
                            pattern, idx, vals)
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
