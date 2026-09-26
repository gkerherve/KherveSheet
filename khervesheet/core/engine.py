"""A complete workbook without Qt: what KherveCELL runs in the browser.

It follows the desktop sheet step for step, so the same workbook computes
the same values in both:

- typing a value or formula     → ``SheetWidget._on_cell_changed_impl``
- dependencies and recalculation → ``_register_deps`` / ``_recalc_from_seeds``
- cross-sheet refresh            → ``WorkbookWidget.refresh_cross_sheet``
- loading a saved workbook       → the cell pass of ``MainWindow._load_ksheet``

Cells are addressed (row, col), 0-based.  A cell has a *source* (what was
typed: a value or a formula) and a *text* (what is shown).  Formulas read
the shown text of other cells, exactly as the desktop sheet does.

Python (=PY) cells are kept but not run here yet.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from .compiler import compile_formula, evaluate_cell
from .functions import build_namespace, lower_names
from .numbers import format_number, format_value
from .refs import XREF_PATTERN, parse_cell_refs
from .values import CellValues

Cell = Tuple[int, int]

DEFAULT_ROWS = 5000
DEFAULT_COLS = 50
PY_MARKER = "=PY"
PYTHON_NOT_RUN = "⟨Python — not run⟩"

_DECIMALS = {"0": 0, "0.0": 1, "0.00": 2, "0.000": 3, "0.0000": 4}


def is_python_source(text) -> bool:
    """True if *text* is a Python cell: the =PY marker, then the end, a
    space or a line break (so =PYTHAGORAS(…) stays a formula).

    Same rule as ``python_engine.is_python_source`` on the desktop."""
    if not isinstance(text, str):
        return False
    s = text.lstrip()
    return (s[:len(PY_MARKER)].upper() == PY_MARKER
            and s[len(PY_MARKER):len(PY_MARKER) + 1] in ("", " ", "\n",
                                                         "\r", "\t"))


class Sheet(CellValues):
    """One sheet of cells.  Create through ``Workbook.add_sheet``."""

    def __init__(self, workbook: "Workbook", name: str,
                 rows: int = DEFAULT_ROWS, cols: int = DEFAULT_COLS):
        self.workbook = workbook
        self.name = name
        self.rows = rows
        self.cols = cols
        #: What was typed in each non-empty cell.
        self.sources: Dict[Cell, str] = {}
        #: What each non-empty cell shows.
        self.texts: Dict[Cell, str] = {}
        #: Number formats ("General", "0.00", "Currency:€", …).
        self.cell_formats: Dict[Cell, str] = {}
        self.column_formats: Dict[int, str] = {}
        self.default_format = "General"

        self._cell_formulas: Dict[Cell, str] = {}
        self._dependents: Dict[Cell, set] = {}
        self._xref_cells: set = set()
        self._compiled_cache: dict = {}
        #: Exact numbers behind rounded text (see core.values).
        self._precise: dict = {}
        self._last_raw = None
        self._eval_ns = None
        self._eval_ns_lower = None

    # ── Reading ──────────────────────────────────────────────────────
    def text(self, row: int, col: int) -> str:
        return self.texts.get((row, col), "")

    def source(self, row: int, col: int) -> str:
        return self.sources.get((row, col), "")

    def formula(self, row: int, col: int) -> Optional[str]:
        return self._cell_formulas.get((row, col))

    # CellValues host interface.
    def _cell_text(self, r, c):
        return self.texts.get((r, c), "")

    def row_count(self) -> int:
        return self.rows

    def _workbook(self):
        return self.workbook

    # ── Typing into a cell ───────────────────────────────────────────
    def set_cell(self, row: int, col: int, source: str) -> List[tuple]:
        """Type *source* into a cell, like pressing Enter on the desktop.

        Returns what changed on screen, across the workbook:
        ``[(sheet name, row, col, text), …]``."""
        with self.workbook._collect() as changes:
            self._type(row, col, source or "")
            self._recalc_from_seeds([(row, col)])
            self.workbook.refresh_cross_sheet()
        return changes

    def _type(self, row, col, text):
        self._ensure_size(row, col)
        key = (row, col)
        if text:
            self.sources[key] = text
        else:
            self.sources.pop(key, None)
        dec = self._cell_decimals(row, col)

        if text == "=":
            # A bare "=" starts formula entry on the desktop; it is
            # never a value.
            self.sources.pop(key, None)
            self._write(row, col, "")
            return
        if is_python_source(text):
            self._cell_formulas[key] = text
            self._unregister_deps(row, col)
            self._write(row, col, PYTHON_NOT_RUN)
            return
        if text.startswith("="):
            self._cell_formulas[key] = text
            self._register_deps(row, col, text)
            display = self._apply_cell_number_format(
                str(self._evaluate_formula(text, row, col, dec)), row, col)
            self._write(row, col, display)
            self._remember_value(row, col, display, self._last_raw)
            return

        self._cell_formulas.pop(key, None)
        self._unregister_deps(row, col)
        typed_number = None
        if text:
            try:
                typed_number = float(text)
                text = str(format_number(typed_number, dec))
            except ValueError:
                pass
        display = self._apply_cell_number_format(text, row, col)
        self._write(row, col, display)
        self._remember_value(row, col, display, typed_number)

    def _write(self, row, col, text):
        key = (row, col)
        if self.texts.get(key, "") == text:
            return
        if text:
            self.texts[key] = text
        else:
            self.texts.pop(key, None)
        self.workbook._changed(self, row, col, text)

    def _ensure_size(self, row, col):
        if row >= self.rows:
            self.rows = row + 1
        if col >= self.cols:
            self.cols = col + 1

    # ── Number formats ───────────────────────────────────────────────
    def _number_format(self, row, col):
        nf = self.cell_formats.get((row, col))
        if not nf:
            nf = self.column_formats.get(col)
        return nf

    def _cell_decimals(self, row, col):
        """Decimal precision for a cell based on its format."""
        nf = self.cell_formats.get((row, col))
        if not nf:
            nf = self.column_formats.get(col, self.default_format)
        return _DECIMALS.get(nf, 3)

    def _apply_cell_number_format(self, text, row, col):
        """Numbers show two decimals unless the cell or column says
        otherwise (as on the desktop)."""
        nf = self._number_format(row, col)
        if nf == "Text" or not text:
            return text
        if not nf or nf == "General":
            try:
                val = float(text)
                if abs(val) >= 1e15:
                    return f"{val:.2E}"
                return f"{val:.2f}"
            except (ValueError, TypeError):
                return text
        return format_value(text, nf)

    def set_number_format(self, row, col, fmt: Optional[str]) -> List[tuple]:
        """Give a cell a number format (None: back to the column's)."""
        if fmt:
            self.cell_formats[(row, col)] = fmt
        else:
            self.cell_formats.pop((row, col), None)
        source = self.sources.get((row, col))
        return self.set_cell(row, col, source) if source else []

    # ── Formulas ─────────────────────────────────────────────────────
    def _build_eval_ns(self):
        if self._eval_ns is None:
            self._eval_ns = build_namespace(self)
            self._eval_ns_lower = lower_names(self._eval_ns)
        return self._eval_ns

    def _compile_formula(self, formula):
        self._build_eval_ns()
        return compile_formula(formula, self._eval_ns, self._eval_ns_lower)

    def _evaluate_formula(self, formula: str, row: int, col: int,
                          decimals: int = 3):
        """Evaluate a cell formula and return its display; a list result
        spills below (see core.compiler.evaluate_cell)."""
        return evaluate_cell(self, formula, row, col, decimals)

    def _spill_array(self, values, row, col):
        for i, v in enumerate(values[1:], start=1):
            self._ensure_size(row + i, col)
            text = str(format_number(v))
            self._write(row + i, col, text)
            self._remember_value(row + i, col, text, v)

    # ── Dependencies ─────────────────────────────────────────────────
    def _register_deps(self, row, col, formula):
        self._unregister_deps(row, col)
        for ref in parse_cell_refs(formula):
            self._dependents.setdefault(ref, set()).add((row, col))
        if XREF_PATTERN.search(formula or ""):
            self._xref_cells.add((row, col))
        else:
            self._xref_cells.discard((row, col))

    def _unregister_deps(self, row, col):
        key = (row, col)
        self._xref_cells.discard(key)
        for deps in self._dependents.values():
            deps.discard(key)

    def _recalc_from_seeds(self, seeds: Iterable[Cell]):
        """Re-evaluate every formula that depends on *seeds*, each after
        all of its inputs (topological order)."""
        affected = set()
        stack = list(seeds)
        while stack:
            for dep in self._dependents.get(stack.pop(), ()):
                if dep not in affected:
                    affected.add(dep)
                    stack.append(dep)
        if not affected:
            return
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
        if len(order) < len(affected):   # cycle: best effort
            done = set(order)
            order.extend(k for k in affected if k not in done)
        for (r, c) in order:
            self._reeval_formula_cell(r, c)

    def _reeval_formula_cell(self, r, c):
        formula = self._cell_formulas.get((r, c))
        if not formula or is_python_source(formula):
            return
        dec = self._cell_decimals(r, c)
        result = self._apply_cell_number_format(
            str(self._evaluate_formula(formula, r, c, dec)), r, c)
        self._write(r, c, result)
        self._remember_value(r, c, result, self._last_raw)


class Workbook:
    """Sheets, looked up by name like the desktop workbook."""

    def __init__(self):
        self.sheets: List[Sheet] = []
        self._in_xref_refresh = False
        self._changes: Optional[List[tuple]] = None

    # ── Sheets ───────────────────────────────────────────────────────
    def add_sheet(self, name: Optional[str] = None,
                  rows: int = DEFAULT_ROWS, cols: int = DEFAULT_COLS) -> Sheet:
        if not name:
            name = f"Sheet{len(self.sheets) + 1}"
        if self.sheet_by_name(name) is not None:
            raise ValueError(f"A sheet is already called {name!r}")
        sheet = Sheet(self, name, rows, cols)
        self.sheets.append(sheet)
        return sheet

    def sheet_by_name(self, name: str) -> Optional[Sheet]:
        """Find a sheet by name (case-insensitive, quotes ignored)."""
        if not name:
            return None
        target = name.strip().strip("'").lower()
        for sheet in self.sheets:
            if sheet.name.lower() == target:
                return sheet
        return None

    def sheet_names(self) -> List[str]:
        return [sheet.name for sheet in self.sheets]

    def rename_sheet(self, old: str, new: str) -> List[tuple]:
        sheet = self.sheet_by_name(old)
        if sheet is None:
            raise KeyError(old)
        other = self.sheet_by_name(new)
        if other is not None and other is not sheet:
            raise ValueError(f"A sheet is already called {new!r}")
        sheet.name = new
        with self._collect() as changes:
            self.refresh_cross_sheet()
        return changes

    def remove_sheet(self, name: str) -> List[tuple]:
        sheet = self.sheet_by_name(name)
        if sheet is None:
            raise KeyError(name)
        self.sheets.remove(sheet)
        with self._collect() as changes:
            self.refresh_cross_sheet()
        return changes

    # ── Recalculation ────────────────────────────────────────────────
    def refresh_cross_sheet(self):
        """Re-evaluate every cross-sheet formula and cascade locally."""
        if self._in_xref_refresh:
            return
        self._in_xref_refresh = True
        try:
            for sheet in self.sheets:
                cells = list(sheet._xref_cells)
                if not cells:
                    continue
                for (r, c) in cells:
                    sheet._reeval_formula_cell(r, c)
                sheet._recalc_from_seeds(cells)
        finally:
            self._in_xref_refresh = False

    def load(self, cells: Dict[str, Dict[Cell, str]]) -> None:
        """Fill sheets from saved sources, as opening a .ksheet does:
        values as they are, then formulas evaluated twice so formulas
        that read other formulas settle."""
        pending = []
        for name, sheet_cells in cells.items():
            sheet = self.sheet_by_name(name) or self.add_sheet(name)
            for (r, c), text in sheet_cells.items():
                if not text:
                    continue
                sheet._ensure_size(r, c)
                sheet.sources[(r, c)] = text
                if is_python_source(text):
                    sheet._cell_formulas[(r, c)] = text
                    sheet.texts[(r, c)] = PYTHON_NOT_RUN
                elif text.startswith("="):
                    sheet._cell_formulas[(r, c)] = text
                    pending.append((sheet, r, c, text))
                else:
                    sheet.texts[(r, c)] = text
        for _pass in range(2):
            for sheet, r, c, formula in pending:
                if _pass == 0:
                    sheet._register_deps(r, c, formula)
                result = str(sheet._evaluate_formula(formula, r, c))
                if result:
                    sheet.texts[(r, c)] = result
                else:
                    sheet.texts.pop((r, c), None)
                sheet._remember_value(r, c, result, sheet._last_raw)

    # ── Change collection ────────────────────────────────────────────
    def _changed(self, sheet: Sheet, row: int, col: int, text: str):
        if self._changes is not None:
            self._changes.append((sheet.name, row, col, text))

    def _collect(self):
        workbook = self

        class _Collector:
            def __enter__(self):
                self.outer = workbook._changes
                if self.outer is None:
                    workbook._changes = []
                    self.changes = workbook._changes
                else:
                    self.changes = []   # nested: the outer call reports
                return self.changes

            def __exit__(self, *exc):
                if self.outer is None:
                    # Last write per cell wins, in first-change order.
                    latest = {}
                    for name, r, c, text in workbook._changes:
                        latest[(name, r, c)] = text
                    self.changes[:] = [(n, r, c, t)
                                       for (n, r, c), t in latest.items()]
                    workbook._changes = None
                return False

        return _Collector()
