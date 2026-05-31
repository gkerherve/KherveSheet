"""Curve Fitting — KherveFitting-style peak fitting workbench.

A non-modal dialog that fits a composite model (a sum of user-added
functions on top of a chosen background) to an X/Y data range picked from
the sheet, using lmfit.  Any built-in lmfit model can be added, as can
user-built custom functions (an arbitrary expression in ``x``).  Each
added function exposes a full parameter editor (value / min / max / vary).
Results are previewed live in an embedded plot and a fit report; the
component curves, total fit and residual are written back to the sheet
only when the user clicks *Apply to Sheet*.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from typing import Optional

import numpy as np

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QMessageBox, QSplitter, QWidget, QTextEdit, QListWidget, QLineEdit,
)

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as \
    FigureCanvas
from matplotlib.figure import Figure

from .sheet import SheetWidget, col_index_to_letter
from .solver import _PickLineEdit, _parse_range, _selection_ref_str
from . import fit_models as fm


def _range_to_col_rows(text: str):
    """Parse a picked range into (col, row_start, row_end). Uses the
    first column of the range; returns None if nothing parseable."""
    cells = _parse_range(text)
    if not cells:
        return None
    cols = sorted({c for _, c in cells})
    rows = sorted({r for r, _ in cells})
    return cols[0], rows[0], rows[-1]


def _fmt_bound(v):
    """Format a parameter bound for display (blank when infinite)."""
    if v is None or not np.isfinite(v):
        return ""
    return f"{v:g}"


# ── Custom-function builder dialog ──────────────────────────────────

class _CustomFunctionDialog(QDialog):
    """Build a custom fit function from an expression in x."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Function")
        self.resize(460, 200)
        self.result_key = None
        self.result_label = None
        self.result_expr = None

        lay = QVBoxLayout(self)
        form = QFormLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. MyDecay")
        self._expr = QLineEdit()
        self._expr.setPlaceholderText(
            "a * exp(-(x - c)**2 / (2 * w**2)) + d")
        form.addRow("Name:", self._name)
        form.addRow("f(x) =", self._expr)
        lay.addLayout(form)

        hint = QLabel(
            "Use <b>x</b> and any parameter names. Available functions: "
            "exp, log, ln, log10, sqrt, sin, cos, tan, arctan, sinh, "
            "cosh, tanh, abs, sign, where, erf, erfc, gamma, pi, e.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#555; font-size:11px;")
        lay.addWidget(hint)

        self._preview = QLabel()
        self._preview.setWordWrap(True)
        lay.addWidget(self._preview)
        self._expr.textChanged.connect(self._update_preview)

        row = QHBoxLayout()
        row.addStretch()
        ok = QPushButton("Add")
        cancel = QPushButton("Cancel")
        row.addWidget(ok)
        row.addWidget(cancel)
        lay.addLayout(row)
        ok.clicked.connect(self._on_ok)
        cancel.clicked.connect(self.reject)

    def _update_preview(self):
        try:
            params = fm.custom_param_names(self._expr.text().strip())
            self._preview.setText(
                "Parameters: " + (", ".join(params) or "(none yet)"))
            self._preview.setStyleSheet("color:#2a7;")
        except SyntaxError:
            self._preview.setText("Parameters: (incomplete expression)")
            self._preview.setStyleSheet("color:#a55;")

    def _on_ok(self):
        label = self._name.text().strip()
        expr = self._expr.text().strip()
        if not label:
            QMessageBox.warning(self, "Custom Function",
                                "Give the function a name.")
            return
        try:
            key = "custom:" + label
            fm.make_custom_function(key, label, expr)  # validate
        except ValueError as exc:
            QMessageBox.warning(self, "Custom Function", str(exc))
            return
        self.result_key, self.result_label, self.result_expr = \
            key, label, expr
        self.accept()


# ── Main fitting dialog ─────────────────────────────────────────────

class FittingDialog(QDialog):
    """Interactive lmfit-based peak fitting dialog (non-modal)."""

    # Parameter-editor columns.
    _COLS = ["Parameter", "Value", "Min", "Max", "Vary"]

    def __init__(self, sheet: SheetWidget, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Curve Fitting")
        self.setWindowModality(Qt.NonModal)
        self.resize(1080, 660)
        self._sheet = sheet
        self._active_edit: Optional[_PickLineEdit] = None
        self._result = None          # last lmfit ModelResult
        self._fit_arrays = None      # (x_full, labels, comps, bg, total)
        self._peaks = []             # list of peak dicts
        self._cur_peak = -1          # index into _peaks shown in editor
        # Custom functions persist on the sheet for the session.
        if not hasattr(sheet, "_fit_custom"):
            sheet._fit_custom = {}
        self._custom_store = sheet._fit_custom
        self._functions = []         # available FitFunction list

        self._build_ui()
        self._refresh_function_combo()
        self._sheet.table.itemSelectionChanged.connect(
            self._on_sheet_selection)
        sel = _selection_ref_str(self._sheet)
        if sel:
            self._y_edit.setText(sel)

    # ── Cell-pick machinery ─────────────────────────────────────────

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

        left = QWidget()
        col = QVBoxLayout(left)

        # Data
        data_box = QGroupBox("Data")
        form = QFormLayout(data_box)
        self._x_edit = _PickLineEdit(self)
        self._x_edit.setPlaceholderText(
            "X range, e.g. $A$2:$A$500 (blank = row number)")
        self._y_edit = _PickLineEdit(self)
        self._y_edit.setPlaceholderText("Y data range, e.g. $B$2:$B$500")
        form.addRow("X:", self._x_edit)
        form.addRow("Y:", self._y_edit)
        col.addWidget(data_box)

        # Background
        bg_box = QGroupBox("Background")
        bg_form = QFormLayout(bg_box)
        self._bg_combo = QComboBox()
        for key, label, _deg in fm.BACKGROUNDS:
            self._bg_combo.addItem(label, key)
        bg_form.addRow("Type:", self._bg_combo)
        col.addWidget(bg_box)

        # Functions: add row + list of added peaks
        fn_box = QGroupBox("Functions")
        fv = QVBoxLayout(fn_box)
        add_row = QHBoxLayout()
        self._fn_combo = QComboBox()
        self._fn_combo.setMinimumWidth(180)
        add_row.addWidget(self._fn_combo, 1)
        self._add_btn = QPushButton("Add")
        self._custom_btn = QPushButton("Custom…")
        add_row.addWidget(self._add_btn)
        add_row.addWidget(self._custom_btn)
        fv.addLayout(add_row)

        self._peak_list = QListWidget()
        self._peak_list.setMaximumHeight(110)
        fv.addWidget(self._peak_list)
        del_row = QHBoxLayout()
        self._del_btn = QPushButton("Delete")
        del_row.addStretch()
        del_row.addWidget(self._del_btn)
        fv.addLayout(del_row)
        col.addWidget(fn_box)

        self._add_btn.clicked.connect(self._add_selected_function)
        self._custom_btn.clicked.connect(self._build_custom_function)
        self._del_btn.clicked.connect(self._delete_peak)
        self._peak_list.currentRowChanged.connect(self._show_peak_params)

        # Parameter editor
        pe_box = QGroupBox("Parameters")
        pev = QVBoxLayout(pe_box)
        self._table = QTableWidget(0, len(self._COLS))
        self._table.setHorizontalHeaderLabels(self._COLS)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.itemChanged.connect(self._on_param_edited)
        pev.addWidget(self._table)
        col.addWidget(pe_box, 1)

        # Actions
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

        # Right: plot + report
        right = QWidget()
        rcol = QVBoxLayout(right)
        self._figure = Figure(figsize=(5, 4), dpi=100, tight_layout=True)
        self._canvas = FigureCanvas(self._figure)
        self._ax = self._figure.add_subplot(111)
        rcol.addWidget(self._canvas, 1)
        self._report = QTextEdit()
        self._report.setReadOnly(True)
        self._report.setMaximumHeight(160)
        self._report.setStyleSheet("font-family: monospace;")
        rcol.addWidget(self._report)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([450, 630])

        self._set_active_pick(self._y_edit)

    # ── Function combo / adding ─────────────────────────────────────

    def _refresh_function_combo(self):
        self._functions = fm.all_functions(self._custom_store)
        self._fn_combo.clear()
        last_group = None
        for i, f in enumerate(self._functions):
            if f.group != last_group:
                # Group caption as a (disabled) separator-style header.
                self._fn_combo.insertSeparator(self._fn_combo.count())
                last_group = f.group
            self._fn_combo.addItem(f"{f.label}  ·  {f.group}", i)
        # Land on the first real entry, not the leading group separator.
        for i in range(self._fn_combo.count()):
            if self._fn_combo.itemData(i) is not None:
                self._fn_combo.setCurrentIndex(i)
                break

    def _add_selected_function(self):
        idx = self._fn_combo.currentData()
        if idx is None or idx < 0 or idx >= len(self._functions):
            return
        self._add_peak(self._functions[idx])

    def _build_custom_function(self):
        dlg = _CustomFunctionDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        self._custom_store[dlg.result_key] = {
            "label": dlg.result_label, "expr": dlg.result_expr}
        self._refresh_function_combo()
        # Select and add the freshly-built function.
        for i, f in enumerate(self._functions):
            if f.key == dlg.result_key:
                self._add_peak(f)
                break

    def _add_peak(self, func: fm.FitFunction):
        prefix = f"p{len(self._peaks)}_"
        params = self._initial_params(func, prefix)
        self._peaks.append({"func": func, "prefix": prefix,
                            "params": params})
        self._peak_list.addItem(f"{len(self._peaks)}: {func.label}")
        self._peak_list.setCurrentRow(self._peak_list.count() - 1)

    def _initial_params(self, func, prefix):
        """Build the editable parameter dict for a new function, seeding
        values from lmfit's own guess when the data is available."""
        model = func.make_model(prefix)
        pars = model.make_params()
        x, y = self._read_xy(silent=True)
        if x is not None:
            mask = np.isfinite(x) & np.isfinite(y)
            if mask.sum() >= 3:
                try:
                    g = model.guess(y[mask], x=x[mask])
                    for k in pars:
                        if k in g:
                            pars[k].set(value=g[k].value)
                except Exception:
                    pass
        out = {}
        for full, par in pars.items():
            # Skip derived parameters (lmfit exposes e.g. a Gaussian's
            # fwhm/height as constrained expressions) — they are computed
            # from the free ones and must not be edited directly.
            if par.expr:
                continue
            name = full[len(prefix):]
            val = par.value
            if val is None or not np.isfinite(val):
                val = 1.0
            out[name] = {"value": float(val), "min": par.min,
                         "max": par.max, "vary": bool(par.vary)}
        return out

    def _delete_peak(self):
        row = self._peak_list.currentRow()
        if row < 0:
            return
        self._peaks.pop(row)
        self._peak_list.takeItem(row)
        # Re-key prefixes so they stay p0_, p1_, … and relabel the list.
        for i, pk in enumerate(self._peaks):
            pk["prefix"] = f"p{i}_"
            self._peak_list.item(i).setText(f"{i + 1}: {pk['func'].label}")
        self._show_peak_params(self._peak_list.currentRow())

    # ── Parameter editor ────────────────────────────────────────────

    def _show_peak_params(self, row):
        self._cur_peak = row
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        if 0 <= row < len(self._peaks):
            params = self._peaks[row]["params"]
            for name, spec in params.items():
                r = self._table.rowCount()
                self._table.insertRow(r)
                name_it = QTableWidgetItem(name)
                name_it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self._table.setItem(r, 0, name_it)
                self._table.setItem(r, 1, QTableWidgetItem(
                    f"{spec['value']:g}"))
                self._table.setItem(r, 2, QTableWidgetItem(
                    _fmt_bound(spec["min"])))
                self._table.setItem(r, 3, QTableWidgetItem(
                    _fmt_bound(spec["max"])))
                vary_it = QTableWidgetItem()
                vary_it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled
                                 | Qt.ItemIsUserCheckable)
                vary_it.setCheckState(
                    Qt.Checked if spec["vary"] else Qt.Unchecked)
                self._table.setItem(r, 4, vary_it)
        self._table.blockSignals(False)

    def _on_param_edited(self, item):
        if not (0 <= self._cur_peak < len(self._peaks)):
            return
        params = self._peaks[self._cur_peak]["params"]
        name = self._table.item(item.row(), 0).text()
        spec = params.get(name)
        if spec is None:
            return
        c = item.column()
        if c == 1:
            try:
                spec["value"] = float(item.text())
            except ValueError:
                pass
        elif c == 2:
            txt = item.text().strip()
            spec["min"] = -np.inf if txt == "" else self._to_float(
                txt, -np.inf)
        elif c == 3:
            txt = item.text().strip()
            spec["max"] = np.inf if txt == "" else self._to_float(
                txt, np.inf)
        elif c == 4:
            spec["vary"] = item.checkState() == Qt.Checked

    @staticmethod
    def _to_float(txt, default):
        try:
            return float(txt)
        except ValueError:
            return default

    # ── Data access ─────────────────────────────────────────────────

    def _read_xy(self, silent=False):
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
            x_full = self._sheet.numeric_column(xinfo[0])[r0:r1 + 1]
            x_full = x_full[:len(y_full)]
            if len(x_full) < len(y_full):
                x_full = np.concatenate(
                    [x_full, np.full(len(y_full) - len(x_full), np.nan)])
        return x_full, y_full

    # ── Fitting ─────────────────────────────────────────────────────

    def _fit(self):
        try:
            import lmfit  # noqa: F401
        except ImportError:
            QMessageBox.critical(
                self, "Missing Dependency",
                "lmfit is required for Curve Fitting.\n"
                "Install it with:  pip install lmfit")
            return

        x_full, y_full = self._read_xy()
        if x_full is None:
            return
        if not self._peaks:
            QMessageBox.warning(self, "Curve Fitting",
                                "Add at least one function to fit.")
            return
        mask = np.isfinite(x_full) & np.isfinite(y_full)
        if mask.sum() < 3:
            QMessageBox.warning(self, "Curve Fitting",
                                "Not enough numeric data points to fit.")
            return
        x, y = x_full[mask], y_full[mask]

        bg_key = self._bg_combo.currentData()
        y_target = y
        if bg_key == "shirley":
            y_target = y - fm.shirley_background(x, y)
        elif bg_key == "tougaard":
            y_target = y - fm.tougaard_background(x, y)

        # Build composite model and parameter set.
        comp = None
        for pk in self._peaks:
            m = pk["func"].make_model(pk["prefix"])
            comp = m if comp is None else comp + m
        deg = fm.background_degree(bg_key)
        if deg is not None and deg >= 0:
            from lmfit.models import PolynomialModel
            comp = comp + PolynomialModel(degree=deg, prefix="bg_")

        params = comp.make_params()
        for pk in self._peaks:
            for name, spec in pk["params"].items():
                full = pk["prefix"] + name
                if full in params:
                    params[full].set(
                        value=spec["value"], min=spec["min"],
                        max=spec["max"], vary=spec["vary"])
        if deg is not None and deg >= 0:
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
        # Write fitted values back into the editor so the user sees them.
        for pk in self._peaks:
            for name in pk["params"]:
                full = pk["prefix"] + name
                if full in result.params:
                    pk["params"][name]["value"] = result.params[full].value
        self._show_peak_params(self._cur_peak)

        self._build_fit_arrays(x_full, bg_key, result)
        self._draw(x_full, y_full)
        self._write_report(result, x_full, y_full)
        self._apply_btn.setEnabled(True)

    def _build_fit_arrays(self, x_full, bg_key, result):
        finite = np.isfinite(x_full)
        fill = np.nanmedian(x_full[finite]) if finite.any() else 0.0
        xf = np.where(finite, x_full, fill)
        comps = result.eval_components(x=xf)

        def _as_array(v):
            # Some components (e.g. Constant) return a scalar; broadcast.
            return np.broadcast_to(
                np.asarray(v, dtype=float), xf.shape).astype(float)

        labels, arrays = [], []
        for i, pk in enumerate(self._peaks):
            arr = _as_array(comps[pk["prefix"]]).copy()
            arr[~finite] = np.nan
            labels.append(f"{pk['func'].label} {i + 1}")
            arrays.append(arr)
        if bg_key in ("shirley", "tougaard"):
            yf = self._read_xy(silent=True)[1]
            yf = np.nan_to_num(yf)
            bg = (fm.shirley_background(xf, yf) if bg_key == "shirley"
                  else fm.tougaard_background(xf, yf))
            bg[~finite] = np.nan
        elif "bg_" in comps:
            bg = _as_array(comps["bg_"]).copy()
            bg[~finite] = np.nan
        else:
            bg = None
        total = (np.nansum(arrays, axis=0) if arrays
                 else np.zeros_like(xf))
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
            self._ax.plot(x_full, bg, "--", color="#888", lw=1,
                          label="background")
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
        lines = [f"R^2 = {r2:.6f}    reduced chi^2 = {result.redchi:.6g}",
                 f"points = {int(mask.sum())}    "
                 f"varied params = {result.nvarys}", ""]
        for name, par in result.params.items():
            err = "" if par.stderr is None else f" +/- {par.stderr:.4g}"
            lines.append(f"  {name:16s} = {par.value:.6g}{err}")
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
        _x2, y_full = self._read_xy(silent=True)
        resid = y_full - total

        out_cols = []
        if bg is not None:
            out_cols.append(("fit_background", bg))
        for lbl, arr in zip(labels, arrays):
            out_cols.append((f"fit_{lbl.replace(' ', '_')}", arr))
        out_cols.append(("fit_total", total))
        out_cols.append(("fit_residual", resid))

        start_col = ycol + 2
        need_cols = start_col + len(out_cols)
        if self._sheet.table.columnCount() < need_cols:
            self._sheet.table.setColumnCount(need_cols)

        write_header = r0 > 0
        changes = []
        for j, (header, arr) in enumerate(out_cols):
            c = start_col + j
            if write_header:
                old = self._sheet.cell_text(r0 - 1, c)
                changes.append((r0 - 1, c, old, header))
            for k, v in enumerate(arr):
                if not np.isfinite(v):
                    continue
                r = r0 + k
                old = self._sheet.cell_text(r, c)
                changes.append((r, c, old, f"{v:.6g}"))

        for r, c, _old, new in changes:
            self._sheet._set_cell_quiet(r, c, new)
        if self._sheet._undo_stack is not None:
            from .sheet import BulkCellEditCmd
            self._sheet._undo_stack.push(
                BulkCellEditCmd(self._sheet, changes, "Curve Fitting"))
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
