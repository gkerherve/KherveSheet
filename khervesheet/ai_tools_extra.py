"""Document I/O and analysis tools for the AI / MCP tool layer.

``ai_tools.py`` covers the grid: cells, formatting, charts.  This
module adds the two things an agent driving KherveSheet from outside
could not otherwise reach —

* **the document**: open, save, export, and ask what file is loaded;
* **the analysis dialogs**: Solver, trendline fitting and lmfit peak
  fitting, run headlessly through the same code the dialogs use.

Kept separate from ``ai_tools.py`` to hold both modules near the
project's 1500-line ceiling.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List

import numpy as np

from .ai_tools import parse_range, parse_a1

#: Extensions we can write, mapped to the MainWindow writer.
_SAVE_FORMATS = {
    ".ksheet": "_save_to_ksheet",
    ".csv": "_save_to_csv",
    ".xlsx": "_save_to_excel",
}

#: Saving to these keeps the document pointed at the file; an Excel
#: export does not, mirroring what File ▸ Save As does.
_ADOPTS_PATH = (".ksheet", ".csv")


# ── Shared helpers ─────────────────────────────────────────────────

def _numeric_range(sheet, range_str: str):
    """Read a range as a 1-D float array, column-major.

    Non-numeric cells (a header, a gap) become NaN rather than an
    error: fitting tools mask them out, which is what a user selecting
    a column including its header expects.
    """
    r1, c1, r2, c2 = parse_range(range_str)
    vals: List[float] = []
    for c in range(c1, c2 + 1):
        for r in range(r1, r2 + 1):
            try:
                vals.append(float(sheet.cell_text(r, c)))
            except (TypeError, ValueError):
                vals.append(np.nan)
    return np.asarray(vals, dtype=float)


def _write_columns(sheet, start_cell: str, columns: List[tuple],
                   label: str) -> dict:
    """Write (header, array) columns from *start_cell* downwards.

    One undo command for the lot, matching how the Curve Fitting
    dialog's Apply writes its results.
    """
    from .sheet import BulkCellEditCmd

    r0, c0 = parse_a1(start_cell)
    changes = []
    for j, (header, arr) in enumerate(columns):
        c = c0 + j
        changes.append((r0, c, sheet.cell_text(r0, c), str(header)))
        for k, v in enumerate(arr):
            if v is None or not np.isfinite(v):
                continue
            r = r0 + 1 + k
            changes.append((r, c, sheet.cell_text(r, c), f"{float(v):.6g}"))
    for r, c, _old, new in changes:
        sheet._set_cell_quiet(r, c, new)
    if sheet._undo_stack is not None:
        sheet._undo_stack.push(BulkCellEditCmd(sheet, changes, label))
    for j in range(len(columns)):
        sheet.data_changed.emit(c0 + j)
    return {"columns_written": len(columns),
            "start_cell": start_cell,
            "cells_written": len(changes)}


def _clean_floats(obj):
    """Make numpy scalars and non-finite floats JSON-safe.

    Booleans are left alone: ``bool`` is a subclass of ``int``, and
    turning ``solved: True`` into ``solved: 1`` loses the distinction a
    client is checking for.
    """
    if isinstance(obj, dict):
        return {k: _clean_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_floats(v) for v in obj]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return f if np.isfinite(f) else None
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    return obj


# ── Document tools ─────────────────────────────────────────────────

def tool_get_document_info(ex, _inp: dict) -> dict:
    mw = ex._mw
    path = getattr(mw, "_current_file", None)
    ext = os.path.splitext(path)[1].lower() if path else ""
    return {
        "file_path": path,
        "file_name": os.path.basename(path) if path else None,
        "unsaved_changes": not mw._undo_stack.isClean(),
        "can_save_in_place": bool(path and ext in _ADOPTS_PATH),
        "sheets": [mw._workbook.name_of_sheet(s)
                   for s in mw._workbook.all_sheets()],
        "save_formats": sorted(_SAVE_FORMATS),
    }


def tool_save_workbook(ex, inp: dict) -> dict:
    mw = ex._mw
    path = (inp.get("path") or "").strip() or None
    if path is None:
        path = getattr(mw, "_current_file", None)
        if not path:
            return {"error": "This workbook has never been saved, so "
                             "there is no path to save it to. Pass "
                             "'path' with a full filename."}
        if os.path.splitext(path)[1].lower() not in _ADOPTS_PATH:
            return {"error": f"{path} was imported, and overwriting it "
                             "would corrupt the original. Pass 'path' "
                             "with a .ksheet filename instead."}
    path = os.path.abspath(os.path.expanduser(path))
    ext = os.path.splitext(path)[1].lower()
    writer = _SAVE_FORMATS.get(ext)
    if writer is None:
        what = ext or "a file with no extension"
        return {"error": f"Cannot save to {what}. "
                         f"Use one of {sorted(_SAVE_FORMATS)}."}
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        return {"error": f"Directory does not exist: {parent}"}
    getattr(mw, writer)(path)
    if ext in _ADOPTS_PATH:
        mw._current_file = path
        mw._add_recent(path)
        mw._update_title()
        mw._undo_stack.setClean()
    return {"saved": path, "format": ext.lstrip("."),
            "adopted_as_current_file": ext in _ADOPTS_PATH}


def tool_open_workbook(ex, inp: dict) -> dict:
    mw = ex._mw
    path = (inp.get("path") or "").strip()
    if not path:
        return {"error": "Pass 'path' — opening a file dialog is not "
                         "possible from a tool call."}
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(path):
        return {"error": f"No such file: {path}"}
    if (not mw._undo_stack.isClean()
            and not inp.get("discard_unsaved_changes")):
        return {"error": "The open workbook has unsaved changes. Save "
                         "it first, or call again with "
                         "discard_unsaved_changes=true to lose them."}
    if not mw._open_path(path):
        return {"error": f"Unrecognised file type: {path}. Open "
                         ".ksheet, .csv, .xlsx or .xlsm."}
    mw._undo_stack.clear()
    return {"opened": path,
            "sheets": [mw._workbook.name_of_sheet(s)
                       for s in mw._workbook.all_sheets()]}


def tool_new_workbook(ex, inp: dict) -> dict:
    mw = ex._mw
    if (not mw._undo_stack.isClean()
            and not inp.get("discard_unsaved_changes")):
        return {"error": "The open workbook has unsaved changes. Save "
                         "it first, or call again with "
                         "discard_unsaved_changes=true to lose them."}
    mw._undo_stack.setClean()   # _new_workbook would otherwise prompt
    mw._new_workbook()
    return {"created": True,
            "sheets": [mw._workbook.name_of_sheet(s)
                       for s in mw._workbook.all_sheets()]}


# ── Analysis tools ─────────────────────────────────────────────────

def tool_run_solver(ex, inp: dict) -> dict:
    from .solver import solve_headless

    sheet = ex._sheet(inp["sheet_name"])
    spec = {
        "objective_cell": inp["objective_cell"],
        "variable_cells": inp["variable_cells"],
        "goal": inp.get("goal", "min"),
        "target_value": inp.get("target_value"),
        "constraints": inp.get("constraints") or [],
        "method": inp.get("method"),
        "non_negative": inp.get("non_negative", False),
    }
    if spec["goal"] in ("value", "target") and spec["target_value"] is None:
        return {"error": "goal='value' needs a target_value."}
    return _clean_floats(solve_headless(sheet, spec))


def tool_fit_trendline(ex, inp: dict) -> dict:
    from .trendline import fit_series

    sheet = ex._sheet(inp["sheet_name"])
    x = _numeric_range(sheet, inp["x_range"])
    y = _numeric_range(sheet, inp["y_range"])
    if len(x) != len(y):
        return {"error": f"x_range has {len(x)} cells but y_range has "
                         f"{len(y)}; they must match."}
    fit = fit_series(x, y, inp.get("model", "Linear"),
                     poly_order=int(inp.get("poly_order", 4)),
                     ma_period=int(inp.get("ma_period", 2)))
    if "error" in fit:
        return {"error": fit["error"]}
    out = {"model": fit["model"], "equation": fit["equation"],
           "params": fit["params"], "errors": fit["errors"],
           "goodness_of_fit": fit["gof"]}
    start = inp.get("output_cell")
    if start:
        mask = np.isfinite(x) & np.isfinite(y)
        fitted = np.full(len(x), np.nan)
        try:
            fitted[mask] = fit["predict"](x[mask])
        except Exception as exc:
            out["write_error"] = f"Could not evaluate the fit: {exc}"
            return _clean_floats(out)
        out["written"] = _write_columns(
            sheet, start, [(f"{fit['model']} fit", fitted)],
            "Trendline fit")
    return _clean_floats(out)


def tool_fit_peaks(ex, inp: dict) -> dict:
    from . import peakfit

    sheet = ex._sheet(inp["sheet_name"])
    x = _numeric_range(sheet, inp["x_range"])
    y = _numeric_range(sheet, inp["y_range"])
    if len(x) != len(y):
        return {"error": f"x_range has {len(x)} cells but y_range has "
                         f"{len(y)}; they must match."}
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 3:
        return {"error": "Need at least 3 numeric (x, y) points to fit."}
    xf, yf = x[mask], y[mask]

    bg_key = peakfit.background_by_name(inp.get("background", "none"))
    if bg_key is None:
        return {"error": f"Unknown background {inp.get('background')!r}. "
                         "Call list_fit_models for the choices."}
    shapes = inp.get("peaks") or []
    if not shapes:
        return {"error": "Pass 'peaks' — at least one shape to fit."}
    names = [p if isinstance(p, str) else p.get("model", "")
             for p in shapes]
    seeds = [{} if isinstance(p, str)
             else {k: v for k, v in p.items() if k != "model"}
             for p in shapes]
    try:
        peaks = peakfit.make_peaks(names, xf, yf, seeds)
        fit = peakfit.run_fit(xf, yf, peaks, bg_key)
    except Exception as exc:
        return {"error": f"Fit failed: {exc}"}

    result = fit["result"]
    out = peakfit.summarise(result, peaks)
    out["background"] = bg_key

    start = inp.get("output_cell")
    if start:
        comps = result.eval_components(x=xf)
        columns = [("x", xf), ("data", yf)]
        if fit["background"] is not None:
            columns.append(("background", fit["background"]))
        for pk in peaks:
            arr = comps.get(pk["prefix"])
            if arr is not None:
                columns.append((f"{pk['prefix'].rstrip('_')} "
                                f"{pk['func'].label}", np.asarray(arr)))
        total = np.asarray(result.best_fit)
        if fit["background"] is not None:
            total = total + fit["background"]
        columns.append(("fit", total))
        columns.append(("residual", yf - total))
        out["written"] = _write_columns(sheet, start, columns,
                                        "Peak fit")
    return _clean_floats(out)


def tool_list_fit_models(ex, inp: dict) -> dict:
    from . import fit_models as fm
    from . import peakfit
    from .trendline import MODELS, MOVING_AVERAGE_KEY

    kind = (inp.get("kind") or "all").lower()
    out: Dict[str, Any] = {}
    if kind in ("all", "trendline"):
        out["trendline_models"] = (list(MODELS.keys())
                                   + [MOVING_AVERAGE_KEY])
    if kind in ("all", "peak"):
        out["peak_shapes"] = [
            {"name": f.label, "group": f.group,
             "formula": f.formula, "description": f.description}
            for f in peakfit.available_functions()]
        out["backgrounds"] = [label for _k, label, _d in fm.BACKGROUNDS]
    return out


# ── Registration ───────────────────────────────────────────────────

def build_dispatch(ex) -> Dict[str, Callable[[dict], dict]]:
    """Bind every tool in this module to *ex* (an ``AiToolExecutor``)."""
    return {
        "get_document_info": lambda i: tool_get_document_info(ex, i),
        "save_workbook": lambda i: tool_save_workbook(ex, i),
        "open_workbook": lambda i: tool_open_workbook(ex, i),
        "new_workbook": lambda i: tool_new_workbook(ex, i),
        "run_solver": lambda i: tool_run_solver(ex, i),
        "fit_trendline": lambda i: tool_fit_trendline(ex, i),
        "fit_peaks": lambda i: tool_fit_peaks(ex, i),
        "list_fit_models": lambda i: tool_list_fit_models(ex, i),
        "insert_control": lambda i: tool_insert_control(ex, i),
    }


#: Tools that only inspect; used by the bridge's read-only access level.
READ_ONLY = frozenset({"get_document_info", "list_fit_models"})


# ── Interactive cells ──────────────────────────────────────────────

def tool_insert_control(ex, inp: dict) -> dict:
    """Turn cells into checkboxes or dropdowns.

    Both are ordinary cells whose *value* is text — "TRUE"/"FALSE" for
    a checkbox, the chosen option for a dropdown — so a formula or a
    =PY cell reads them like any other cell.  That is what makes them
    usable as controls rather than decoration.
    """
    from .ai_tools import parse_range
    from .insert_ops import insert_checkbox, mark_dropdown_cell

    sheet = ex._sheet(inp["sheet_name"])
    kind = inp.get("kind")
    if kind not in ("checkbox", "dropdown", "button"):
        return {"error": "kind must be 'checkbox', 'dropdown' or "
                         "'button'."}
    r1, c1, r2, c2 = parse_range(inp["range"])
    cells = [(r, c) for r in range(r1, r2 + 1)
             for c in range(c1, c2 + 1)]
    if len(cells) > 500:
        return {"error": f"{len(cells)} cells is too many for one call "
                         "(limit 500)."}

    if kind == "checkbox":
        checked = bool(inp.get("checked", False))
        for r, c in cells:
            insert_checkbox(sheet, r, c, checked=checked)
        return {"created": "checkbox", "cells": len(cells),
                "value": "TRUE" if checked else "FALSE",
                "note": ("The cell reads 'TRUE' or 'FALSE'. Reference it "
                         "from a formula or with ks() in a =PY cell.")}

    if kind == "button":
        from .cell_buttons import insert_button
        spec = {k: inp[k] for k in
                ("label", "mode", "target", "value", "reset", "run",
                 "color") if k in inp}
        try:
            for r, c in cells:
                stored = insert_button(sheet, r, c, spec)
        except ValueError as exc:
            return {"error": str(exc)}
        return {"created": "button", "cells": len(cells),
                "spec": stored,
                "note": ("Clicking it runs the action. A 'pulse' button "
                         "writes the value, re-runs the =PY cell, then "
                         "resets — so the same click can be made again.")}

    items = [str(i) for i in (inp.get("items") or []) if str(i).strip()]
    if not items:
        return {"error": "A dropdown needs at least one entry in 'items'."}
    if not hasattr(sheet, "_cell_dropdowns"):
        sheet._cell_dropdowns = {}
    default = inp.get("default")
    if default is not None and default not in items:
        return {"error": f"default {default!r} is not one of {items}."}
    default = default if default is not None else items[0]
    from PyQt5.QtWidgets import QTableWidgetItem
    for r, c in cells:
        sheet._cell_dropdowns[(r, c)] = items
        it = sheet.table.item(r, c)
        if it is None:
            it = QTableWidgetItem(default)
            sheet.table.setItem(r, c, it)
        elif not it.text():
            it.setText(default)
        sheet._shadow[(r, c)] = it.text()
        mark_dropdown_cell(sheet, r, c)
    return {"created": "dropdown", "cells": len(cells), "items": items,
            "default": default,
            "note": ("The cell reads whichever option is selected.")}
