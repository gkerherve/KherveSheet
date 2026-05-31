"""Curve Fitting — KherveFitting-style peak fitting workbench.

A non-modal dialog that fits a composite model (a sum of user-added
peak/curve functions on top of a chosen background) to an X/Y data range
picked from the sheet, using lmfit.  Results are previewed live in an
embedded plot and a fit report; the component curves, total fit and
residual are written back to the sheet only when the user clicks
*Apply to Sheet*.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from typing import List, Optional

import numpy as np

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QMessageBox, QSplitter, QWidget, QTextEdit, QCheckBox,
)

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as \
    FigureCanvas
from matplotlib.figure import Figure

from .sheet import SheetWidget, col_index_to_letter
from .solver import _PickLineEdit, _parse_range, _selection_ref_str
from . import fit_models as fm

# Generic parameter columns shown in the peak table.  They map by
# position onto each model's parameter list, which is always ordered
# [height, center, <width>, <shape>] (see fit_models.PEAK_MODELS).
_PARAM_COLS = ["Height", "Center", "Width", "Shape"]


def _range_to_col_rows(text: str):
    """Parse a picked range into (col, row_start, row_end). Uses the
    first column of the range; returns None if nothing parseable."""
    cells = _parse_range(text)
    if not cells:
        return None
    cols = sorted({c for _, c in cells})
    rows = sorted({r for r, _ in cells})
    return cols[0], rows[0], rows[-1]


def _param_bounds(model_key: str, pname: str, x):
    """Sensible (min, max) bounds for a fitted parameter."""
    xmin, xmax = float(np.nanmin(x)), float(np.nanmax(x))
    span = (xmax - xmin) or 1.0
    if pname == "center":
        return (xmin - 0.1 * span, xmax + 0.1 * span)
    if pname in ("fwhm", "sigma", "gamma", "width"):
        return (1e-9, 5.0 * span)
    if pname == "tau":
        return (1e-9, 100.0 * span)
    if pname == "fraction":
        return (0.0, 1.0)
    if pname == "expo":
        return (0.5, 100.0)
    if pname == "asym":
        return (0.0, 0.95) if model_key == "doniach_sunjic" \
            else (-0.95, 0.95)
    return (None, None)


class FittingDialog(QDialog):
    """Interactive lmfit-based peak fitting dialog (non-modal)."""

    def __init__(self, sheet: SheetWidget, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Curve Fitting")
        self.setWindowModality(Qt.NonModal)
        self.resize(1040, 640)
        self._sheet = sheet
        self._active_edit: Optional[_PickLineEdit] = None
        self._result = None          # last lmfit ModelResult
        self._fit_arrays = None      # (x_full, components, total, resid)

        self._build_ui()
        self._sheet.table.itemSelectionChanged.connect(
            self._on_sheet_selection)
        # Pre-fill from the current selection (treat it as the Y data).
        sel = _selection_ref_str(self._sheet)
        if sel:
            self._y_edit.setText(sel)

    # ── Cell-pick machinery (mirrors the Solver dialog) ─────────────

    def _set_active_pick(self, edit: _PickLineEdit):
        if self._active_edit and self._active_edit is not edit:
            self._active_edit.setStyleSheet("")
        self._active_edit = edit
        edit.setStyleSheet(
            "QLineEdit { border: 2px solid #3a78b4; background: #eef4fb; }")

    def _on_sheet_selection(self):
        if self._active_edit is None or not self.isVisible():
            return
        ref = _selection_ref_str(self._sheet)
        if ref:
            self._active_edit.setText(ref)
            self.activateWindow()

    # ── UI ──────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        outer.addWidget(splitter)

        # --- Left: controls ---
        left = QWidget()
        col = QVBoxLayout(left)

        data_box = QGroupBox("Data")
        form = QFormLayout(data_box)
        self._x_edit = _PickLineEdit(self)
        self._x_edit.setPlaceholderText("X column range, e.g. $A$2:$A$500 "
                                        "(blank = row number)")
        self._y_edit = _PickLineEdit(self)
        self._y_edit.setPlaceholderText("Y data range, e.g. $B$2:$B$500")
        form.addRow("X:", self._x_edit)
        form.addRow("Y:", self._y_edit)
        col.addWidget(data_box)

        bg_box = QGroupBox("Background")
        bg_form = QFormLayout(bg_box)
        self._bg_combo = QComboBox()
        for key, label, _deg in fm.BACKGROUNDS:
            self._bg_combo.addItem(label, key)
        bg_form.addRow("Type:", self._bg_combo)
        col.addWidget(bg_box)

        # Peak table
        peak_box = QGroupBox("Functions")
        pv = QVBoxLayout(peak_box)
        self._table = QTableWidget(0, 1 + len(_PARAM_COLS))
        self._table.setHorizontalHeaderLabels(["Function"] + _PARAM_COLS)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        pv.addWidget(self._table)

        prow = QHBoxLayout()
        self._add_btn = QPushButton("Add Function")
        self._del_btn = QPushButton("Delete")
        prow.addWidget(self._add_btn)
        prow.addWidget(self._del_btn)
        prow.addStretch()
        pv.addLayout(prow)
        col.addWidget(peak_box, 1)

        self._add_btn.clicked.connect(lambda: self._add_peak())
        self._del_btn.clicked.connect(self._delete_peak)

        # Action buttons
        arow = QHBoxLayout()
        self._fit_btn = QPushButton("Fit")
        self._apply_btn = QPushButton("Apply to Sheet")
        self._apply_btn.setEnabled(False)
        self._close_btn = QPushButton("Close")
        arow.addWidget(self._fit_btn)
        arow.addWidget(self._apply_btn)
        arow.addStretch()
        arow.addWidget(self._close_btn)
        col.addLayout(arow)
        self._fit_btn.clicked.connect(self._fit)
        self._apply_btn.clicked.connect(self._apply_to_sheet)
        self._close_btn.clicked.connect(self.reject)

        splitter.addWidget(left)

        # --- Right: plot + report ---
        right = QWidget()
        rcol = QVBoxLayout(right)
        self._figure = Figure(figsize=(5, 4), dpi=100, tight_layout=True)
        self._canvas = FigureCanvas(self._figure)
        self._ax = self._figure.add_subplot(111)
        rcol.addWidget(self._canvas, 1)
        self._report = QTextEdit()
        self._report.setReadOnly(True)
        self._report.setMaximumHeight(150)
        self._report.setStyleSheet("font-family: monospace;")
        rcol.addWidget(self._report)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([430, 610])

        self._set_active_pick(self._y_edit)

    # ── Peak table management ───────────────────────────────────────

    def _add_peak(self, model_key="gaussian"):
        row = self._table.rowCount()
        self._table.insertRow(row)
        combo = QComboBox()
        for m in fm.PEAK_MODELS.values():
            combo.addItem(m.label, m.key)
        idx = combo.findData(model_key)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(
            lambda _i, r=row: self._sync_row_enabled(r))
        self._table.setCellWidget(row, 0, combo)

        # Guess initial values from the data if available.
        x, y = self._read_xy(silent=True)
        model = fm.PEAK_MODELS[model_key]
        if x is not None and len(x):
            center = float(np.nanmedian(x))
            guess = model.guess(x, y, center)
        else:
            guess = {p: 1.0 for p in model.params}
            guess["fraction"] = guess.get("fraction", 0.5)
        # Map [height, center, width, shape] columns onto model params.
        vals = self._guess_to_cols(model, guess)
        for c, v in enumerate(vals, start=1):
            item = QTableWidgetItem("" if v is None else f"{v:g}")
            if v is None:
                item.setFlags(Qt.ItemIsSelectable)
            self._table.setItem(row, c, item)
        self._sync_row_enabled(row)

    @staticmethod
    def _guess_to_cols(model, guess):
        """Return [height, center, width, shape] values for the table,
        with None where the model has no such parameter."""
        vals = [None, None, None, None]
        for i, pname in enumerate(model.params):
            if i < 4:
                vals[i if i < 3 else 3] = guess.get(pname)
        return [vals[0], vals[1], vals[2], vals[3]]

    def _sync_row_enabled(self, row):
        """Grey out the Shape (and unused) cells for models that don't
        use them, and refresh guessed values when the type changes."""
        combo = self._table.cellWidget(row, 0)
        if combo is None:
            return
        model = fm.PEAK_MODELS[combo.currentData()]
        nparams = len(model.params)
        # Column index 4 == Shape (model param index 3).
        for c, pidx in ((3, 2), (4, 3)):
            item = self._table.item(row, c)
            if item is None:
                item = QTableWidgetItem("")
                self._table.setItem(row, c, item)
            used = pidx < nparams
            if used:
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled
                              | Qt.ItemIsEditable)
                if not item.text():
                    item.setText("1")
            else:
                item.setText("")
                item.setFlags(Qt.ItemIsSelectable)

    def _delete_peak(self):
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)

    def _collect_peaks(self):
        """Return [(model, {param: value}), ...] from the table."""
        peaks = []
        for row in range(self._table.rowCount()):
            combo = self._table.cellWidget(row, 0)
            if combo is None:
                continue
            model = fm.PEAK_MODELS[combo.currentData()]
            init = {}
            for i, pname in enumerate(model.params):
                col = 1 + (i if i < 3 else 3)
                item = self._table.item(row, col)
                try:
                    init[pname] = float(item.text())
                except (ValueError, AttributeError, TypeError):
                    init[pname] = 1.0
            peaks.append((model, init))
        return peaks

    # ── Data access ─────────────────────────────────────────────────

    def _read_xy(self, silent=False):
        """Read the X and Y arrays from the picked ranges. Returns
        (x, y) full arrays over the Y row span (NaNs preserved)."""
        yinfo = _range_to_col_rows(self._y_edit.text())
        if yinfo is None:
            if not silent:
                QMessageBox.warning(self, "Curve Fitting",
                                    "Pick a Y data range first.")
            return None, None
        ycol, r0, r1 = yinfo
        y_full = self._sheet.numeric_column(ycol)[r0:r1 + 1]
        xinfo = _range_to_col_rows(self._x_edit.text())
        if xinfo is None:
            x_full = np.arange(len(y_full), dtype=float)
        else:
            xcol = xinfo[0]
            x_full = self._sheet.numeric_column(xcol)[r0:r1 + 1]
            x_full = x_full[:len(y_full)]
            if len(x_full) < len(y_full):
                x_full = np.concatenate(
                    [x_full, np.full(len(y_full) - len(x_full), np.nan)])
        return x_full, y_full

    # ── Fitting ─────────────────────────────────────────────────────

    def _fit(self):
        try:
            import lmfit
        except ImportError:
            QMessageBox.critical(
                self, "Missing Dependency",
                "lmfit is required for Curve Fitting.\n"
                "Install it with:  pip install lmfit")
            return

        x_full, y_full = self._read_xy()
        if x_full is None:
            return
        peaks = self._collect_peaks()
        if not peaks:
            QMessageBox.warning(self, "Curve Fitting",
                                "Add at least one function to fit.")
            return

        mask = np.isfinite(x_full) & np.isfinite(y_full)
        if mask.sum() < 3:
            QMessageBox.warning(self, "Curve Fitting",
                                "Not enough numeric data points to fit.")
            return
        x = x_full[mask]
        y = y_full[mask]

        bg_key = self._bg_combo.currentData()
        data_bg = None  # pre-computed Shirley/Tougaard over the fit x
        y_target = y
        if bg_key == "shirley":
            data_bg = fm.shirley_background(x, y)
            y_target = y - data_bg
        elif bg_key == "tougaard":
            data_bg = fm.tougaard_background(x, y)
            y_target = y - data_bg

        # Build the composite model: sum of peaks + analytic background.
        comp = None
        for i, (model, _init) in enumerate(peaks):
            m = lmfit.Model(model.func, prefix=f"p{i}_")
            comp = m if comp is None else comp + m
        deg = fm.background_degree(bg_key)
        if deg is not None and deg >= 0:
            from lmfit.models import PolynomialModel
            bg_model = PolynomialModel(degree=deg, prefix="bg_")
            comp = comp + bg_model

        params = comp.make_params()
        for i, (model, init) in enumerate(peaks):
            for pname, val in init.items():
                p = params[f"p{i}_{pname}"]
                lo, hi = _param_bounds(model.key, pname, x)
                p.set(value=val, min=lo, max=hi)
        if deg is not None and deg >= 0:
            # lmfit's PolynomialModel leaves every coefficient at -inf,
            # which evaluates to NaN — seed them all to finite values
            # (constant term from the data baseline, rest at zero).
            params["bg_c0"].set(value=float(np.nanmin(y_target)))
            for d in range(1, deg + 1):
                params[f"bg_c{d}"].set(value=0.0)

        try:
            result = comp.fit(y_target, params, x=x)
        except Exception as exc:
            QMessageBox.critical(self, "Curve Fitting",
                                 f"Fit failed:\n{exc}")
            return

        self._result = result
        self._build_fit_arrays(x_full, peaks, bg_key, result)
        self._draw(x_full, y_full)
        self._write_report(result, x_full, y_full)
        self._apply_btn.setEnabled(True)

    def _build_fit_arrays(self, x_full, peaks, bg_key, result):
        """Evaluate every component over the full row span for plotting
        and sheet output. Stores (labels, comp_arrays, bg, total)."""
        finite = np.isfinite(x_full)
        xf = np.where(finite, x_full, np.nanmedian(x_full[finite]))
        comps = result.eval_components(x=xf)
        labels, arrays = [], []
        for i, (model, _init) in enumerate(peaks):
            arr = np.asarray(comps[f"p{i}_"], dtype=float)
            arr[~finite] = np.nan
            labels.append(f"{model.label} {i + 1}")
            arrays.append(arr)
        # Background curve.
        if bg_key in ("shirley", "tougaard"):
            yf = self._read_xy(silent=True)[1]
            if bg_key == "shirley":
                bg = fm.shirley_background(xf, np.nan_to_num(yf))
            else:
                bg = fm.tougaard_background(xf, np.nan_to_num(yf))
            bg[~finite] = np.nan
        elif "bg_" in comps:
            bg = np.asarray(comps["bg_"], dtype=float)
            bg[~finite] = np.nan
        else:
            bg = None
        total = np.nansum(
            [a for a in arrays], axis=0) if arrays else np.zeros_like(xf)
        if bg is not None:
            total = total + np.nan_to_num(bg)
        total[~finite] = np.nan
        self._fit_arrays = (x_full, labels, arrays, bg, total)

    # ── Plot & report ───────────────────────────────────────────────

    def _draw(self, x_full, y_full):
        self._ax.clear()
        _x, labels, arrays, bg, total = self._fit_arrays
        self._ax.plot(x_full, y_full, "o", ms=3, color="#3a78b4",
                      label="data", zorder=1)
        if bg is not None:
            self._ax.plot(x_full, bg, "--", color="#888",
                          lw=1, label="background")
        for lbl, arr in zip(labels, arrays):
            self._ax.plot(x_full, arr, lw=1, alpha=0.8, label=lbl)
        self._ax.plot(x_full, total, "-", color="#c0392b", lw=1.6,
                      label="total fit", zorder=3)
        self._ax.legend(loc="best", fontsize=7, framealpha=0.8)
        self._ax.relim()
        self._ax.autoscale_view()
        self._canvas.draw_idle()

    def _write_report(self, result, x_full, y_full):
        mask = np.isfinite(x_full) & np.isfinite(y_full)
        _x, _l, _a, _bg, total = self._fit_arrays
        resid = y_full - total
        ss_res = float(np.nansum(resid[mask] ** 2))
        ss_tot = float(np.nansum((y_full[mask] - np.nanmean(
            y_full[mask])) ** 2)) or 1.0
        r2 = 1.0 - ss_res / ss_tot
        lines = [f"R² = {r2:.6f}    reduced χ² = {result.redchi:.6g}",
                 f"points = {int(mask.sum())}    "
                 f"params = {result.nvarys}", ""]
        for name, par in result.params.items():
            err = "" if par.stderr is None else f" ± {par.stderr:.4g}"
            lines.append(f"  {name:14s} = {par.value:.6g}{err}")
        self._report.setPlainText("\n".join(lines))

    # ── Write results back to the sheet ─────────────────────────────

    def _apply_to_sheet(self):
        if self._fit_arrays is None:
            return
        yinfo = _range_to_col_rows(self._y_edit.text())
        if yinfo is None:
            return
        ycol, r0, _r1 = yinfo
        x_full, labels, arrays, bg, total = self._fit_arrays
        x_full2, y_full = self._read_xy(silent=True)
        resid = y_full - total

        # Build the columns to write: each component, background, total,
        # residual — each with a header row label.
        out_cols = []
        if bg is not None:
            out_cols.append(("fit_background", bg))
        for lbl, arr in zip(labels, arrays):
            out_cols.append((f"fit_{lbl.replace(' ', '_')}", arr))
        out_cols.append(("fit_total", total))
        out_cols.append(("fit_residual", resid))

        # Place output starting two columns right of the Y column.
        start_col = ycol + 2
        need_cols = start_col + len(out_cols)
        if self._sheet.table.columnCount() < need_cols:
            self._sheet.table.setColumnCount(need_cols)

        # Write a header label in the row above the data, but only when
        # there is a free row there (data starting at the very top row
        # would otherwise clobber its own header).
        write_header = r0 > 0
        changes = []
        for j, (header, arr) in enumerate(out_cols):
            c = start_col + j
            if write_header:
                old = self._sheet.cell_text(r0 - 1, c)
                changes.append((r0 - 1, c, old, header))
            for k, v in enumerate(arr):
                r = r0 + k
                if not np.isfinite(v):
                    continue
                old = self._sheet.cell_text(r, c)
                changes.append((r, c, old, f"{v:.6g}"))

        # Write the cells now, then record the batch for undo (the
        # bulk-edit command's first redo only snapshots the shadow and
        # relies on the cells already being set — same as the Solver).
        for r, c, _old, new in changes:
            self._sheet._set_cell_quiet(r, c, new)
        if self._sheet._undo_stack is not None:
            from .sheet import BulkCellEditCmd
            self._sheet._undo_stack.push(
                BulkCellEditCmd(self._sheet, changes, "Curve Fitting"))
        # Refresh display + charts for the columns we touched.
        for j in range(len(out_cols)):
            self._sheet.data_changed.emit(start_col + j)
        QMessageBox.information(
            self, "Curve Fitting",
            f"Wrote {len(out_cols)} columns starting at "
            f"{col_index_to_letter(start_col)}.")

    # ── Cleanup ─────────────────────────────────────────────────────

    def _disconnect(self):
        try:
            self._sheet.table.itemSelectionChanged.disconnect(
                self._on_sheet_selection)
        except (TypeError, RuntimeError):
            pass

    def closeEvent(self, ev):
        self._disconnect()
        super().closeEvent(ev)

    def reject(self):
        self._disconnect()
        super().reject()
