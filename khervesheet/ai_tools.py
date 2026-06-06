"""AI tool executor — spreadsheet manipulation tools for the Claude API.

Provides the ``AiToolExecutor`` class whose methods map 1-to-1 to the
tools exposed to the Claude model.  Every mutating tool is wrapped in
the shared QUndoStack so that Ctrl+Z reverts an entire AI turn.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTableWidgetItem, QUndoCommand

from .sheet import (
    SheetWidget, col_index_to_letter, letter_to_col_index,
    FormatCellsCmd, _snapshot_format,
)
from .cellformat import CellFormat


class _BulkWriteUndo(QUndoCommand):
    """Single undo command for a batch of AI cell writes."""

    def __init__(self, sheet, old_vals, new_vals):
        super().__init__(f"AI: write {len(new_vals)} cells")
        self._sheet = sheet
        self._old = old_vals  # {(r,c): old_text}
        self._new = new_vals  # {(r,c): new_text}
        self._first = True

    def redo(self):
        if self._first:
            self._first = False
            return  # values already written
        self._apply(self._new)

    def undo(self):
        self._apply(self._old)

    def _apply(self, vals):
        s = self._sheet
        s.table.blockSignals(True)
        for (r, c), text in vals.items():
            it = s.table.item(r, c)
            if it is None:
                it = QTableWidgetItem(text)
                s.table.setItem(r, c, it)
            else:
                it.setText(text)
            s._shadow[(r, c)] = text
        s.table.blockSignals(False)


# ── Range parsing ──────────────────────────────────────────────────

_A1_RE = re.compile(r"^\$?([A-Za-z]{1,3})\$?(\d{1,7})$")


def parse_a1(ref: str) -> Tuple[int, int]:
    """Parse a single A1 reference → (row, col), 0-indexed.

    Raises ``ValueError`` on bad input.
    """
    m = _A1_RE.match(ref.strip())
    if not m:
        raise ValueError(f"Invalid cell reference: {ref!r}")
    col = letter_to_col_index(m.group(1))
    row = int(m.group(2)) - 1
    return row, col


def parse_range(range_str: str) -> Tuple[int, int, int, int]:
    """Parse 'A1:C5' → (row_start, col_start, row_end, col_end), 0-indexed.

    A single cell like 'B3' is treated as a 1×1 range.
    """
    parts = range_str.split(":")
    r1, c1 = parse_a1(parts[0])
    if len(parts) == 1:
        return r1, c1, r1, c1
    r2, c2 = parse_a1(parts[1])
    # Normalise so start ≤ end.
    return min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2)


def _range_label(r1: int, c1: int, r2: int, c2: int) -> str:
    """Build a human-readable A1:B2 label from 0-indexed coords."""
    tl = f"{col_index_to_letter(c1)}{r1 + 1}"
    br = f"{col_index_to_letter(c2)}{r2 + 1}"
    return tl if tl == br else f"{tl}:{br}"


# ── Tool executor ──────────────────────────────────────────────────

_MAX_READ_ROWS = 500  # cap read_cells to avoid blowing context window


class AiToolExecutor:
    """Executes AI tool calls by manipulating the spreadsheet.

    All public ``tool_*`` methods accept a dict of tool inputs and
    return a JSON-serialisable result dict.  Mutating tools push
    undo commands onto *mainwindow._undo_stack*.
    """

    def __init__(self, mainwindow):
        self._mw = mainwindow
        self._dispatch = {
            "get_sheet_info": self.tool_get_sheet_info,
            "read_cells": self.tool_read_cells,
            "read_selection": self.tool_read_selection,
            "write_cells": self.tool_write_cells,
            "set_formula": self.tool_set_formula,
            "set_python_cell": self.tool_set_python_cell,
            "format_cells": self.tool_format_cells,
            "insert_chart": self.tool_insert_chart,
            "add_sheet": self.tool_add_sheet,
            "search_functions": self.tool_search_functions,
            "get_function_details": self.tool_get_function_details,
            "list_charts": self.tool_list_charts,
            "get_chart_details": self.tool_get_chart_details,
            "clone_chart": self.tool_clone_chart,
            "modify_chart": self.tool_modify_chart,
            "delete_charts": self.tool_delete_charts,
            "apply_table_style": self.tool_apply_table_style,
            "save_as_template": self.tool_save_as_template,
            "set_column_width": self.tool_set_column_width,
            "merge_cells": self.tool_merge_cells,
            "auto_fit_columns": self.tool_auto_fit_columns,
        }

    # ── Dispatcher ──────────────────────────────────────────────

    def execute(self, tool_name: str,
                tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Run a tool by name.  Returns a result dict."""
        fn = self._dispatch.get(tool_name)
        if fn is None:
            return {"error": f"Unknown tool: {tool_name!r}"}
        try:
            return fn(tool_input)
        except Exception as exc:
            return {"error": str(exc)}

    # ── Helpers ─────────────────────────────────────────────────

    def _sheet(self, name: str) -> SheetWidget:
        """Resolve a sheet by name, raising on miss."""
        s = self._mw._workbook.sheet_by_name(name)
        if s is None:
            names = ", ".join(self._mw._workbook.sheet_names())
            raise ValueError(
                f"Sheet {name!r} not found. Available: {names}")
        return s

    @property
    def _undo(self):
        return self._mw._undo_stack

    # ── Read-only tools ─────────────────────────────────────────

    def tool_get_sheet_info(self, _inp: dict) -> dict:
        sheets = []
        wb = self._mw._workbook
        for s in wb.all_sheets():
            name = wb.name_of_sheet(s)
            sheets.append({
                "name": name,
                "rows": s.row_count(),
                "cols": s.column_count(),
            })
        return {"sheets": sheets}

    def tool_read_cells(self, inp: dict) -> dict:
        sheet = self._sheet(inp["sheet_name"])
        r1, c1, r2, c2 = parse_range(inp["range"])
        # Cap row count.
        truncated = False
        if r2 - r1 + 1 > _MAX_READ_ROWS:
            r2 = r1 + _MAX_READ_ROWS - 1
            truncated = True
        rows: List[List[str]] = []
        for r in range(r1, r2 + 1):
            row = []
            for c in range(c1, c2 + 1):
                row.append(sheet.cell_text(r, c))
            rows.append(row)
        result: dict = {"values": rows}
        if truncated:
            result["truncated"] = True
            result["note"] = (
                f"Only the first {_MAX_READ_ROWS} rows were returned.")
        return result

    def tool_read_selection(self, _inp: dict) -> dict:
        sheet = self._mw._active_sheet()
        if sheet is None:
            return {"error": "No active sheet."}
        wb = self._mw._workbook
        name = wb.name_of_sheet(sheet)
        sel = sheet.table.selectedRanges()
        if not sel:
            return {"sheet": name, "range": None, "values": []}
        s = sel[0]
        r1, c1 = s.topRow(), s.leftColumn()
        r2, c2 = s.bottomRow(), s.rightColumn()
        rows: List[List[str]] = []
        for r in range(r1, r2 + 1):
            row = []
            for c in range(c1, c2 + 1):
                row.append(sheet.cell_text(r, c))
            rows.append(row)
        rng = _range_label(r1, c1, r2, c2)
        return {"sheet": name, "range": rng, "values": rows}

    # ── Mutating tools ──────────────────────────────────────────

    def _commit_cell(self, sheet: SheetWidget, r: int, c: int,
                     text: str) -> None:
        """Write *text* into a cell through the normal edit path.

        Sets the raw text with signals blocked, then invokes
        ``_on_cell_changed`` so that the value is evaluated as a
        formula (if it starts with '='), dependencies are registered,
        dependents recalculated, charts refreshed via *data_changed*,
        and an undo command is pushed.  Mirrors the formula-bar commit.
        """
        sheet.table.blockSignals(True)
        it = sheet.table.item(r, c)
        if it is None:
            it = QTableWidgetItem(text)
            sheet.table.setItem(r, c, it)
        else:
            it.setText(text)
        sheet.table.blockSignals(False)
        sheet._on_cell_changed(r, c)

    def tool_write_cells(self, inp: dict) -> dict:
        sheet = self._sheet(inp["sheet_name"])
        values: List[List[str]] = inp["values"]
        r1, c1, _, _ = parse_range(inp["range"])
        # Normalise: if the model sends a flat list of scalars (1-D)
        # instead of a 2-D array, wrap each element into its own row.
        # Also guard against bare strings being iterated char-by-char.
        normalised: List[List[str]] = []
        for row_vals in values:
            if isinstance(row_vals, str):
                normalised.append([row_vals])
            elif isinstance(row_vals, list):
                normalised.append(row_vals)
            else:
                normalised.append([str(row_vals)])
        # Collect cells to write.
        writes: List[tuple] = []  # (row, col, text)
        for dr, row_vals in enumerate(normalised):
            for dc, val in enumerate(row_vals):
                r, c = r1 + dr, c1 + dc
                sval = str(val)
                if sval == sheet.cell_text(r, c):
                    continue
                writes.append((r, c, sval))
        if not writes:
            return {"cells_written": 0}
        self._bulk_write(sheet, writes)
        return {"cells_written": len(writes)}

    def _bulk_write(self, sheet: SheetWidget, writes: List[tuple]):
        """Fast-path bulk write: set all cells, then evaluate formulas
        and recalc once.  Much faster than per-cell _commit_cell for
        large batches (avoids redundant recalcs and per-cell undo)."""
        from .app import _CRASH_LOG_FILE
        from .python_engine import is_python_source
        from .sheet import _format_number

        def _log(msg):
            if _CRASH_LOG_FILE is not None:
                _CRASH_LOG_FILE.write(f"  [bulk] {msg}\n")
                _CRASH_LOG_FILE.flush()

        _log(f"start: {len(writes)} cells")

        # 1. Record old values for a single undo command.
        old_vals = {}
        for r, c, sval in writes:
            old_vals[(r, c)] = sheet.cell_text(r, c)

        # 2. Set all cell text, suppressing signals and recalc.
        sheet.table.blockSignals(True)
        for r, c, sval in writes:
            it = sheet.table.item(r, c)
            if it is None:
                it = QTableWidgetItem(sval)
                sheet.table.setItem(r, c, it)
            else:
                it.setText(sval)
            sheet._shadow[(r, c)] = sval
        sheet.table.blockSignals(False)
        _log("step2 setText done")

        # 3. Evaluate formulas (=...) and Python cells (=PY) in a
        #    second pass, and register dependencies.
        formula_cells = []
        changed_cols = set()
        dec = 2  # default precision
        for r, c, sval in writes:
            changed_cols.add(c)
            if is_python_source(sval):
                sheet._cell_formulas[(r, c)] = sval
                sheet._register_py_deps(r, c, sval)
                _log(f"step3 eval =PY ({r},{c})")
                try:
                    display = sheet._evaluate_python(sval, r, c, dec)
                except Exception:
                    import traceback
                    display = "#PYERR"
                    sheet._py_errors[(r, c)] = traceback.format_exc()
                _log(f"step3 =PY ({r},{c}) → {display!r:.60}")
                sheet.table.blockSignals(True)
                it = sheet.table.item(r, c)
                if it:
                    it.setText(display)
                sheet.table.blockSignals(False)
                sheet._shadow[(r, c)] = display
            elif sval.startswith("="):
                sheet._cell_formulas[(r, c)] = sval
                sheet._register_deps(r, c, sval)
                formula_cells.append((r, c))
            else:
                sheet._cell_formulas.pop((r, c), None)
                sheet._unregister_deps(r, c)
                # Format plain numbers.
                if sval:
                    try:
                        v = float(sval)
                        formatted = str(_format_number(v, dec))
                        if formatted != sval:
                            sheet.table.blockSignals(True)
                            it = sheet.table.item(r, c)
                            if it:
                                it.setText(formatted)
                            sheet.table.blockSignals(False)
                            sheet._shadow[(r, c)] = formatted
                    except ValueError:
                        pass

        # 4. Evaluate spreadsheet formulas.
        if formula_cells:
            _log(f"step4 eval {len(formula_cells)} formulas")
        for r, c in formula_cells:
            formula = sheet._cell_formulas.get((r, c))
            if not formula:
                continue
            result = str(sheet._evaluate_formula(formula, r, c, dec))
            result = sheet._apply_cell_number_format(result, r, c)
            sheet.table.blockSignals(True)
            it = sheet.table.item(r, c)
            if it is None:
                it = QTableWidgetItem(result)
                sheet.table.setItem(r, c, it)
            else:
                it.setText(result)
            sheet.table.blockSignals(False)
            sheet._shadow[(r, c)] = result

        # 5. Recalc dependents once for all changed cells.
        all_seeds = [(r, c) for r, c, _ in writes]
        _log(f"step5 recalc_from_seeds ({len(all_seeds)} seeds)")
        sheet._recalc_from_seeds(all_seeds)
        _log("step5 recalc done")

        # 6. Push one undo command for the whole batch.
        if sheet._undo_stack is not None:
            new_vals = {}
            for r, c, _ in writes:
                new_vals[(r, c)] = sheet.cell_text(r, c)
            cmd = _BulkWriteUndo(sheet, old_vals, new_vals)
            sheet._undo_stack.push(cmd)

        # 7. Emit data_changed once per affected column.
        _log(f"step7 data_changed cols={sorted(changed_cols)}")
        for c in changed_cols:
            sheet.data_changed.emit(c)
        _log("done")

    def tool_set_formula(self, inp: dict) -> dict:
        sheet = self._sheet(inp["sheet_name"])
        formula = inp["formula"]
        if not formula.startswith("="):
            formula = "=" + formula
        r, c = parse_a1(inp["cell"])
        self._bulk_write(sheet, [(r, c, formula)])
        return {"cell": inp["cell"], "formula": formula}

    def tool_set_python_cell(self, inp: dict) -> dict:
        """Write a Python (=PY) program into a cell.

        The *code* runs in the workbook-wide shared namespace; the value of
        its trailing expression becomes the cell's result.  Use ks("A1") /
        ks("A1:B10") inside the code to read grid values.
        """
        sheet = self._sheet(inp["sheet_name"])
        code = inp["code"]
        # Strip a leading =PY marker if the model included one.
        stripped = code.lstrip()
        if stripped[:3].upper() == "=PY":
            code = stripped[3:].lstrip("\n")
        text = "=PY\n" + code
        r, c = parse_a1(inp["cell"])
        try:
            self._bulk_write(sheet, [(r, c, text)])
        except Exception as exc:
            return {"cell": inp["cell"], "error": str(exc)}
        result = sheet.cell_text(r, c)
        out = {"cell": inp["cell"], "result": result}
        if result == "#PYERR":
            err = sheet._py_errors.get((r, c), "Python error")
            lines = err.strip().splitlines()
            out["error"] = lines[-1] if lines else "Python error"
        return out

    def tool_format_cells(self, inp: dict) -> dict:
        from .app import _CRASH_LOG_FILE
        if _CRASH_LOG_FILE is not None:
            _CRASH_LOG_FILE.write(
                f"  [format] range={inp.get('range')} "
                f"props={inp.get('format_props')}\n")
            _CRASH_LOG_FILE.flush()
        sheet = self._sheet(inp["sheet_name"])
        r1, c1, r2, c2 = parse_range(inp["range"])
        props = inp.get("format_props", {})
        # Map alignment string → Qt flag.
        _align_map = {
            "left": Qt.AlignLeft | Qt.AlignVCenter,
            "center": Qt.AlignHCenter | Qt.AlignVCenter,
            "right": Qt.AlignRight | Qt.AlignVCenter,
        }
        old_fmts: Dict[Tuple[int, int], Optional[CellFormat]] = {}
        new_fmts: Dict[Tuple[int, int], CellFormat] = {}
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                existing = sheet._cell_formats.get((r, c))
                old_fmts[(r, c)] = _snapshot_format(existing)
                cf = _snapshot_format(existing) or CellFormat()
                if "bg_color" in props:
                    cf.bg_color = props["bg_color"]
                if "font_color" in props:
                    cf.font_color = props["font_color"]
                if "bold" in props:
                    cf.bold = props["bold"]
                if "italic" in props:
                    cf.italic = props["italic"]
                if "underline" in props:
                    cf.underline = props["underline"]
                if "font_family" in props:
                    cf.font_family = props["font_family"]
                if "font_size" in props:
                    cf.font_size = float(props["font_size"])
                if "alignment" in props:
                    cf.alignment = _align_map.get(
                        props["alignment"],
                        Qt.AlignLeft | Qt.AlignVCenter)
                if "number_format" in props:
                    cf.number_format = props["number_format"]
                new_fmts[(r, c)] = cf
        label = f"AI: format {_range_label(r1, c1, r2, c2)}"
        cmd = FormatCellsCmd(sheet, old_fmts, new_fmts, label)
        cmd._first_redo_done = False
        self._undo.push(cmd)
        # Apply visually.
        cmd._apply(new_fmts)
        return {"cells_formatted": len(new_fmts)}

    def tool_insert_chart(self, inp: dict) -> dict:
        sheet = self._sheet(inp["sheet_name"])
        chart_type = inp["chart_type"]
        valid_types = [
            "Line", "Scatter", "Line+Symbol", "Bar", "Step",
            "Stem", "Histogram", "Box", "Heatmap", "3D Surface",
        ]
        if chart_type not in valid_types:
            return {"error": f"Invalid chart_type {chart_type!r}. "
                    f"Valid: {valid_types}"}
        import numpy as np
        from .graph import parse_time_column
        # Read X data — detect categorical (text) or time labels.
        xr1, xc1, xr2, xc2 = parse_range(inp["x_range"])
        x_vals = []
        x_labels = []
        for r in range(xr1, xr2 + 1):
            t = sheet.cell_text(r, xc1)
            x_labels.append(t)
            try:
                x_vals.append(float(t))
            except (ValueError, TypeError):
                x_vals.append(float('nan'))
        x = np.array(x_vals)
        nan_count = int(np.isnan(x).sum())
        cat_labels = None
        is_time = False
        if nan_count > len(x) / 2 and len(x) > 0:
            # Try time parsing first.
            t_hours, _ = parse_time_column(x_labels)
            if t_hours is not None:
                x = t_hours
                is_time = True
            else:
                # Categorical X — use integer positions.
                cat_labels = x_labels
                x = np.arange(len(x_labels), dtype=float)
        if len(x) == 0:
            return {"error": "No X data found."}

        # Build list of (row_start, col, row_end) for each Y series.
        # Supports: single column "D5:D14", multi-column "D5:H14",
        # or comma-separated "D5:D14,E5:E14,F5:F14".
        y_range_str = inp["y_range"]
        y_columns = []  # list of (row_start, col_index, row_end)
        for part in y_range_str.split(","):
            part = part.strip()
            if not part:
                continue
            yr1, yc1, yr2, yc2 = parse_range(part)
            for c in range(yc1, yc2 + 1):
                y_columns.append((yr1, c, yr2))
        if not y_columns:
            return {"error": "No Y range specified."}

        from .graph import EmbeddedChart
        viewport = sheet.table.viewport()
        chart = None
        series_count = 0

        for yr1, yc, yr2 in y_columns:
            y_vals = []
            for r in range(yr1, yr2 + 1):
                t = sheet.cell_text(r, yc)
                try:
                    y_vals.append(float(t))
                except (ValueError, TypeError):
                    y_vals.append(float('nan'))
            y = np.array(y_vals)
            if len(y) == 0:
                continue
            label = col_index_to_letter(yc)
            if chart is None:
                chart = EmbeddedChart(
                    x, y, label, chart_type, sheet, viewport,
                    x_col=xc1, y_col=yc,
                    row_start=xr1, row_end=xr2)
            else:
                chart.add_series(
                    x, y, label, chart_type,
                    x_col=xc1, y_col=yc,
                    row_start=xr1, row_end=xr2)
            series_count += 1

        if chart is None:
            return {"error": "No numeric Y data found in the specified ranges."}
        if is_time:
            chart._apply_time_x()
            chart._canvas.draw_idle()
        elif cat_labels is not None:
            chart._apply_categorical_x(cat_labels)
            chart._canvas.draw_idle()
        offset = len(sheet._charts) * 30
        chart.move(40 + offset, 40 + offset)
        sheet._charts.append(chart)
        sheet.data_changed.connect(chart._on_data_changed)
        return {"chart_created": True, "chart_type": chart_type,
                "series_count": series_count}

    def tool_add_sheet(self, inp: dict) -> dict:
        name = inp["name"]
        wb = self._mw._workbook
        # Check for duplicate name.
        if wb.sheet_by_name(name) is not None:
            return {"error": f"Sheet {name!r} already exists."}
        s = wb.add_sheet(name)
        self._mw._wire_undo_to_sheets()
        return {"sheet_name": wb.name_of_sheet(s)}

    # ── Capability database ─────────────────────────────────────

    def tool_search_functions(self, inp: dict) -> dict:
        from . import ai_catalog
        query = inp.get("query", "")
        category = inp.get("category", "")
        limit = int(inp.get("limit", 25))
        results = ai_catalog.search(query, category, limit)
        return {
            "results": results,
            "count": len(results),
            "categories": ai_catalog.all_categories(),
        }

    def tool_get_function_details(self, inp: dict) -> dict:
        from . import ai_catalog
        names = inp.get("names", [])
        if isinstance(names, str):
            names = [names]
        return {"details": ai_catalog.details(names)}

    # ── Chart introspection & cloning ───────────────────────────

    def _chart_spec(self, sheet: SheetWidget, chart) -> dict:
        """Build a readable spec for *chart*: style + which columns
        feed each series (X/Y as column letters)."""
        tpl = chart.to_template()  # style + column mapping, no raw data
        chart_x = tpl.get("x_col")
        series_out = []
        for sd in tpl.get("series", []):
            xc = sd.get("x_col", chart_x)
            yc = sd.get("y_col")
            series_out.append({
                "label": sd.get("label"),
                "plot_type": sd.get("plot_type"),
                "x_column": (col_index_to_letter(xc)
                             if xc is not None else "row index"),
                "y_column": (col_index_to_letter(yc)
                             if yc is not None else None),
                "color": sd.get("color"),
                "linestyle": sd.get("linestyle"),
                "linewidth": sd.get("linewidth"),
                "marker": sd.get("marker"),
                "markersize": sd.get("markersize"),
                "row_start": (sd.get("y_row_start", sd.get("x_row_start"))),
                "row_end": (sd.get("y_row_end", sd.get("x_row_end"))),
            })
        return {
            "title": tpl.get("title", ""),
            "xlabel": tpl.get("xlabel", ""),
            "ylabel": tpl.get("ylabel", ""),
            "xscale": tpl.get("xscale", "linear"),
            "yscale": tpl.get("yscale", "linear"),
            "width": tpl.get("width"),
            "height": tpl.get("height"),
            "series": series_out,
        }

    def tool_list_charts(self, inp: dict) -> dict:
        sheet = self._sheet(inp["sheet_name"])
        charts = getattr(sheet, "_charts", []) or []
        out = []
        for i, ch in enumerate(charts):
            try:
                spec = self._chart_spec(sheet, ch)
            except Exception as exc:
                spec = {"error": str(exc)}
            out.append({
                "index": i,
                "title": spec.get("title", ""),
                "series_count": len(spec.get("series", [])),
                "series": spec.get("series", []),
            })
        return {"sheet": inp["sheet_name"], "charts": out,
                "count": len(out)}

    def tool_get_chart_details(self, inp: dict) -> dict:
        sheet = self._sheet(inp["sheet_name"])
        charts = getattr(sheet, "_charts", []) or []
        idx = int(inp.get("chart_index", 0))
        if idx < 0 or idx >= len(charts):
            return {"error": f"Chart index {idx} out of range "
                    f"(sheet has {len(charts)} chart(s))."}
        return {"chart": self._chart_spec(sheet, charts[idx]),
                "index": idx}

    def tool_clone_chart(self, inp: dict) -> dict:
        """Recreate a chart — with its exact style and column mapping —
        on a target sheet, pulling live data from that target sheet."""
        src = self._sheet(inp["source_sheet"])
        charts = getattr(src, "_charts", []) or []
        idx = int(inp.get("chart_index", 0))
        if idx < 0 or idx >= len(charts):
            return {"error": f"Chart index {idx} out of range "
                    f"(source sheet has {len(charts)} chart(s))."}
        target_name = inp.get("target_sheet") or inp["source_sheet"]
        target = self._sheet(target_name)
        tpl = charts[idx].to_template()
        from .graph import EmbeddedChart
        viewport = target.table.viewport()
        chart = EmbeddedChart.from_template(tpl, target, viewport)
        if chart is None:
            return {"error": "Could not rebuild the chart — the target "
                    "sheet may lack numeric data in the mapped columns."}
        if not hasattr(target, "_charts"):
            target._charts = []
        offset = len(target._charts) * 30
        chart.move(40 + offset, 40 + offset)
        chart.show()
        chart.raise_()
        target._charts.append(chart)
        return {"cloned": True, "target_sheet": target_name,
                "spec": self._chart_spec(target, chart)}

    def tool_modify_chart(self, inp: dict) -> dict:
        """Edit a chart's axes/labels in place: invert axes, set scales,
        title, axis labels, gridlines."""
        sheet = self._sheet(inp["sheet_name"])
        charts = getattr(sheet, "_charts", []) or []
        idx = int(inp.get("chart_index", 0))
        if idx < 0 or idx >= len(charts):
            return {"error": f"Chart index {idx} out of range "
                    f"(sheet has {len(charts)} chart(s))."}
        chart = charts[idx]
        kwargs = {}
        for key in ("invert_x", "invert_y", "grid"):
            if key in inp:
                kwargs[key] = bool(inp[key])
        for key in ("x_scale", "y_scale", "title", "x_label", "y_label"):
            if key in inp:
                kwargs[key] = inp[key]
        if not kwargs:
            return {"error": "No changes specified. Provide at least one "
                    "of: invert_x, invert_y, x_scale, y_scale, title, "
                    "x_label, y_label, grid."}
        try:
            applied = chart.set_axis_options(**kwargs)
        except ValueError as exc:
            return {"error": f"Invalid value: {exc}"}
        return {"modified": True, "index": idx, "applied": applied}

    def tool_delete_charts(self, inp: dict) -> dict:
        """Delete charts from a sheet by index list or 'all'."""
        sheet = self._sheet(inp["sheet_name"])
        charts = getattr(sheet, "_charts", []) or []
        indices_str = inp.get("indices", "all").strip()
        if indices_str.lower() == "all":
            to_delete = list(range(len(charts)))
        else:
            to_delete = []
            for part in indices_str.split(","):
                part = part.strip()
                if part.isdigit():
                    to_delete.append(int(part))
        # Validate.
        for idx in to_delete:
            if idx < 0 or idx >= len(charts):
                return {"error": f"Chart index {idx} out of range "
                        f"(sheet has {len(charts)} chart(s))."}
        # Delete in reverse order so indices stay valid.
        deleted = 0
        for idx in sorted(set(to_delete), reverse=True):
            ch = charts.pop(idx)
            try:
                sheet.data_changed.disconnect(ch._on_data_changed)
            except (TypeError, RuntimeError):
                pass
            ch.setParent(None)
            ch.deleteLater()
            deleted += 1
        return {"deleted": deleted}

    # ── New tools ──────────────────────────────────────────────

    def tool_apply_table_style(self, inp: dict) -> dict:
        """Apply a built-in table design style to a cell range."""
        sheet = self._sheet(inp["sheet_name"])
        r1, c1, r2, c2 = parse_range(inp["range"])
        style_name = inp["style_name"]
        use_header = inp.get("header_row", True)
        use_banding = inp.get("banded_rows", True)

        from .table_styles import BUILTIN_STYLES
        from .cellformat import BorderSpec

        style = None
        # Case-insensitive lookup.
        for s in BUILTIN_STYLES:
            if s.name.lower() == style_name.lower():
                style = s
                break
        if style is None:
            names = [s.name for s in BUILTIN_STYLES[:20]]
            return {"error": f"Style {style_name!r} not found. "
                    f"Examples: {names}"}

        from PyQt5.QtCore import Qt

        old_fmts = {}
        new_fmts = {}
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                existing = sheet._cell_formats.get((r, c))
                old_fmts[(r, c)] = _snapshot_format(existing)
                cf = CellFormat()
                is_header = (r == r1 and use_header)
                if is_header:
                    cf.bg_color = style.header_bg
                    cf.font_color = style.header_fg
                    cf.bold = style.header_bold
                    cf.alignment = Qt.AlignHCenter | Qt.AlignVCenter
                else:
                    data_row = r - r1 - (1 if use_header else 0)
                    if use_banding and data_row % 2 == 1:
                        cf.bg_color = style.odd_bg
                    else:
                        cf.bg_color = style.even_bg
                    cf.font_color = style.text_fg
                # Borders.
                if style.border_color:
                    bc = style.border_color
                    if style.border_outer:
                        if r == r1:
                            cf.border_top = BorderSpec(color=bc, width=1)
                        if r == r2:
                            cf.border_bottom = BorderSpec(color=bc, width=1)
                        if c == c1:
                            cf.border_left = BorderSpec(color=bc, width=1)
                        if c == c2:
                            cf.border_right = BorderSpec(color=bc, width=1)
                    if style.border_inner:
                        if c < c2:
                            cf.border_right = BorderSpec(color=bc, width=1)
                        if r < r2:
                            cf.border_bottom = BorderSpec(color=bc, width=1)
                if is_header and style.border_header_bottom:
                    bc = style.border_color or style.header_bg
                    cf.border_bottom = BorderSpec(color=bc, width=2)
                new_fmts[(r, c)] = cf

        label = f"AI: table style {_range_label(r1, c1, r2, c2)}"
        cmd = FormatCellsCmd(sheet, old_fmts, new_fmts, label)
        cmd._first_redo_done = False
        self._undo.push(cmd)
        cmd._apply(new_fmts)
        return {"styled": True, "style": style.name,
                "cells": len(new_fmts)}

    def tool_save_as_template(self, inp: dict) -> dict:
        """Save the current workbook as a template .ksheet file.

        Templates are written to the per-user, writable templates folder
        (the bundled examples folder is read-only when frozen)."""
        import os
        from . import resources
        name = inp["name"].strip()
        category = inp["category"].strip()
        templates_dir = os.path.join(resources.user_templates_dir(), category)
        os.makedirs(templates_dir, exist_ok=True)
        path = os.path.join(templates_dir, f"{name}.ksheet")
        try:
            self._mw._save_to_ksheet(path)
            return {"saved": True, "path": path}
        except Exception as exc:
            return {"error": f"Failed to save template: {exc}"}

    def tool_set_column_width(self, inp: dict) -> dict:
        """Set column widths."""
        sheet = self._sheet(inp["sheet_name"])
        width = int(inp["width"])
        cols_str = inp["columns"].strip()
        cols = []
        for part in cols_str.split(","):
            part = part.strip()
            if ":" in part:
                a, b = part.split(":")
                ca = letter_to_col_index(a.strip())
                cb = letter_to_col_index(b.strip())
                cols.extend(range(ca, cb + 1))
            else:
                cols.append(letter_to_col_index(part))
        for c in cols:
            sheet.table.setColumnWidth(c, width)
        return {"columns_resized": len(cols), "width": width}

    def tool_merge_cells(self, inp: dict) -> dict:
        """Merge a range of cells."""
        sheet = self._sheet(inp["sheet_name"])
        r1, c1, r2, c2 = parse_range(inp["range"])
        row_span = r2 - r1 + 1
        col_span = c2 - c1 + 1
        if row_span == 1 and col_span == 1:
            return {"error": "Range must span more than one cell."}
        sheet.table.setSpan(r1, c1, row_span, col_span)
        sheet._merged_ranges.append((r1, c1, row_span, col_span))
        return {"merged": True,
                "range": _range_label(r1, c1, r2, c2)}

    def tool_auto_fit_columns(self, inp: dict) -> dict:
        """Auto-fit column widths to content."""
        sheet = self._sheet(inp["sheet_name"])
        cols_str = inp.get("columns", "").strip()
        if cols_str:
            cols = []
            if ":" in cols_str:
                a, b = cols_str.split(":")
                ca = letter_to_col_index(a.strip())
                cb = letter_to_col_index(b.strip())
                cols = list(range(ca, cb + 1))
            else:
                for part in cols_str.split(","):
                    cols.append(letter_to_col_index(part.strip()))
        else:
            # Auto-detect: fit all columns that have data.
            max_col = 0
            for (r, c) in sheet._shadow:
                if c > max_col:
                    max_col = c
            cols = list(range(0, max_col + 1))
        for c in cols:
            sheet.table.resizeColumnToContents(c)
        return {"columns_fitted": len(cols)}
