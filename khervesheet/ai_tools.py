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
from PyQt5.QtWidgets import QTableWidgetItem

from .sheet import (
    SheetWidget, col_index_to_letter, letter_to_col_index,
    FormatCellsCmd, _snapshot_format,
)
from .cellformat import CellFormat


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
            "format_cells": self.tool_format_cells,
            "insert_chart": self.tool_insert_chart,
            "add_sheet": self.tool_add_sheet,
            "search_functions": self.tool_search_functions,
            "get_function_details": self.tool_get_function_details,
            "list_charts": self.tool_list_charts,
            "get_chart_details": self.tool_get_chart_details,
            "clone_chart": self.tool_clone_chart,
            "modify_chart": self.tool_modify_chart,
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
        count = 0
        for dr, row_vals in enumerate(values):
            for dc, val in enumerate(row_vals):
                r, c = r1 + dr, c1 + dc
                sval = str(val)
                if sval == sheet.cell_text(r, c):
                    continue
                self._commit_cell(sheet, r, c, sval)
                count += 1
        return {"cells_written": count}

    def tool_set_formula(self, inp: dict) -> dict:
        sheet = self._sheet(inp["sheet_name"])
        formula = inp["formula"]
        if not formula.startswith("="):
            formula = "=" + formula
        r, c = parse_a1(inp["cell"])
        self._commit_cell(sheet, r, c, formula)
        return {"cell": inp["cell"], "formula": formula}

    def tool_format_cells(self, inp: dict) -> dict:
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
        # Read X and Y data.
        xr1, xc1, xr2, xc2 = parse_range(inp["x_range"])
        yr1, yc1, yr2, yc2 = parse_range(inp["y_range"])
        import numpy as np
        x_vals = []
        for r in range(xr1, xr2 + 1):
            t = sheet.cell_text(r, xc1)
            try:
                x_vals.append(float(t))
            except (ValueError, TypeError):
                x_vals.append(float('nan'))
        y_vals = []
        for r in range(yr1, yr2 + 1):
            t = sheet.cell_text(r, yc1)
            try:
                y_vals.append(float(t))
            except (ValueError, TypeError):
                y_vals.append(float('nan'))
        x = np.array(x_vals)
        y = np.array(y_vals)
        if len(x) == 0 or len(y) == 0:
            return {"error": "No numeric data found in the specified ranges."}
        # Create chart on the sheet viewport.
        from .graph import EmbeddedChart
        viewport = sheet.table.viewport()
        chart = EmbeddedChart(
            x, y, "Data", chart_type, sheet, viewport,
            x_col=xc1, y_col=yc1,
            row_start=xr1, row_end=xr2)
        offset = len(sheet._charts) * 30
        chart.move(40 + offset, 40 + offset)
        sheet._charts.append(chart)
        sheet.data_changed.connect(chart._on_data_changed)
        return {"chart_created": True, "chart_type": chart_type}

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
