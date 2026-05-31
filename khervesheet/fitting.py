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
    QCheckBox,
)

from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
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
    _COLS = ["Parameter", "Value", "Min", "Max", "Vary", "Expr"]

    def __init__(self, sheet: SheetWidget, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Curve Fitting")
        self.setWindowModality(Qt.NonModal)
        self.resize(1080, 660)
        self._sheet = sheet
        self._active_edit: Optional[_PickLineEdit] = None
        self._result = None          # last lmfit ModelResult
        self._fit_arrays = None      # (x_full, labels, comps, bg, total)
        self._fit_ctx = None         # ranges used for the last fit
        self._data_bg_full = None    # computed data background (x_full)
        # Draggable region delimiters (data X coords) bounding the fit /
        # background / residual range.  None until data is first shown.
        self._range_lo = None
        self._range_hi = None
        self._range_lines = []       # the two axvline artists
        self._drag_line = None       # which delimiter is being dragged
        self._fit_region = None      # (lo, hi) used by the last fit
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
        # Live data preview: redraw the raw points whenever a range
        # changes (typed or picked from the sheet).
        self._x_edit.textChanged.connect(self._preview_data)
        self._y_edit.textChanged.connect(self._preview_data)
        # Restore the previous session if this sheet was fitted before;
        # otherwise pre-fill the Y range from the current selection.
        saved = getattr(sheet, "_fit_config", None)
        if saved:
            self._restore_state(saved)
        else:
            sel = _selection_ref_str(self._sheet)
            if sel:
                self._y_edit.setText(sel)
        if self._peaks:
            self._show_peak_params(0)
        self._preview_data()

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
        self._help_btn = QPushButton("?")
        self._help_btn.setFixedWidth(28)
        self._help_btn.setToolTip("Show the equation, source and "
                                  "parameters of every function")
        add_row.addWidget(self._add_btn)
        add_row.addWidget(self._custom_btn)
        add_row.addWidget(self._help_btn)
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
        self._help_btn.clicked.connect(self._show_help)
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
        self._fit_help_btn = QPushButton("?")
        self._fit_help_btn.setFixedWidth(28)
        self._fit_help_btn.setToolTip(
            "How to constrain peaks against one another")
        self._fit_help_btn.clicked.connect(self._show_constraint_help)
        self._apply_btn = QPushButton("Apply to Sheet")
        self._apply_btn.setEnabled(False)
        self._chart_chk = QCheckBox("Create chart")
        self._chart_chk.setChecked(True)
        self._chart_chk.setToolTip(
            "On apply, also drop a chart on the sheet with the data as "
            "points and every fitted curve as a line")
        self._close_btn = QPushButton("Close")
        arow.addWidget(self._fit_btn)
        arow.addWidget(self._fit_help_btn)
        arow.addWidget(self._apply_btn)
        arow.addWidget(self._chart_chk)
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
        # Pan / box-zoom / save toolbar (matplotlib's own).
        self._nav = NavigationToolbar(self._canvas, self)
        rcol.addWidget(self._nav)
        rcol.addWidget(self._canvas, 1)
        # Drag handlers for the region delimiter lines.
        self._canvas.mpl_connect("button_press_event", self._on_line_press)
        self._canvas.mpl_connect("motion_notify_event",
                                 self._on_line_motion)
        self._canvas.mpl_connect("button_release_event",
                                 self._on_line_release)
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

    def _show_help(self):
        """Pop a reference of every function: equation, source, params."""
        rows = fm.function_help(self._custom_store)
        html = ["<html><body style='font-family:sans-serif;'>",
                "<h3>Fitting functions</h3>",
                "<p>Peak <b>height</b> is reported via lmfit's derived "
                "parameters in the fit report; the editor exposes the "
                "free parameters below. The Young (1993) pseudo-Voigt "
                "convention is pV = η·L + (1-η)·G.</p>",
                "<p><b>Per-peak limits:</b> each added function has its "
                "own Min/Max/Vary. <b>Tie peaks together</b> with the "
                "<i>Expr</i> column, referencing other peaks by the "
                "prefix shown in the list — e.g. <code>p0_center+1.5</code>"
                " or <code>0.5*p0_amplitude</code>.</p>",
                "<table cellspacing='0' cellpadding='4' border='1' "
                "style='border-collapse:collapse;'>",
                "<tr style='background:#eef4fb;'><th>Function</th>"
                "<th>Source</th><th>Equation</th><th>Parameters</th>"
                "<th>Notes</th></tr>"]
        last_group = None
        for r in rows:
            if r["group"] != last_group:
                last_group = r["group"]
                html.append(
                    f"<tr style='background:#f4f4f4;'><td colspan='5'>"
                    f"<b>{last_group}</b></td></tr>")
            html.append(
                "<tr>"
                f"<td><b>{r['label']}</b></td>"
                f"<td>{r['source']}</td>"
                f"<td><code>{r['formula'] or '—'}</code></td>"
                f"<td>{', '.join(r['params'])}</td>"
                f"<td>{r['description']}</td></tr>")
        html.append("</table></body></html>")

        dlg = QDialog(self)
        dlg.setWindowTitle("Fitting Functions — Reference")
        dlg.resize(820, 560)
        lay = QVBoxLayout(dlg)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setHtml("".join(html))
        lay.addWidget(view)
        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn)
        lay.addLayout(row)
        dlg.exec_()

    def _show_constraint_help(self):
        """Explain how to constrain peaks against one another."""
        html = """
<html><body style='font-family:sans-serif;'>
<h3>Constraining peaks against one another</h3>

<p>Each added function has its own row of parameters. Two kinds of
limits are available:</p>

<h4>1. Per-peak bounds</h4>
<p>Select a peak in the list, then set <b>Min</b> / <b>Max</b> on any of
its parameters, or untick <b>Vary</b> to hold a parameter fixed. These
apply only to the selected peak, so every peak can be bounded
differently.</p>

<h4>2. Tying peaks together (the <i>Expr</i> column)</h4>
<p>Type a formula in the <b>Expr</b> column to make a parameter follow
another one. Reference any parameter as
<code>&lt;prefix&gt;_&lt;name&gt;</code>, where the prefix is shown in
the function list (e.g. <code>[p0]</code>, <code>[p1]</code>). When a
parameter has an expression it is computed, not fitted (its Min/Max/Vary
are ignored).</p>

<p><b>Examples</b> (peak&nbsp;1 = <code>p0</code>, peak&nbsp;2 =
<code>p1</code>):</p>
<table cellspacing='0' cellpadding='4' border='1'
       style='border-collapse:collapse;'>
<tr style='background:#eef4fb;'><th>On parameter</th><th>Expr</th>
<th>Effect</th></tr>
<tr><td>p1 center</td><td><code>p0_center + 1.5</code></td>
<td>Peak 2 sits a fixed 1.5 above peak 1 (spin-orbit splitting).</td></tr>
<tr><td>p1 amplitude</td><td><code>0.5 * p0_amplitude</code></td>
<td>Fixed 2:1 area ratio between the two peaks.</td></tr>
<tr><td>p1 sigma</td><td><code>p0_sigma</code></td>
<td>Both peaks share the same width.</td></tr>
<tr><td>p1 fwhm</td><td><code>p0_fwhm</code></td>
<td>Equal FWHM across peaks.</td></tr>
</table>

<p>You can use any parameter of any peak and ordinary arithmetic
(<code>+ - * /</code>, parentheses, powers). Circular references (A
depends on B and B on A) are not allowed.</p>

<p><b>Tip:</b> to keep a doublet's separation and ratio fixed while
fitting the pair as one, give peak&nbsp;2 an <code>Expr</code> on its
centre and amplitude referencing peak&nbsp;1, and leave peak&nbsp;1 free.</p>
</body></html>"""
        dlg = QDialog(self)
        dlg.setWindowTitle("Constraining Peaks — Help")
        dlg.resize(640, 520)
        lay = QVBoxLayout(dlg)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setHtml(html)
        lay.addWidget(view)
        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn)
        lay.addLayout(row)
        dlg.exec_()

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
        self._peak_list.addItem(
            f"{len(self._peaks)}: {func.label}  [{prefix.rstrip('_')}]")
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
                # Never set a value on a constrained (derived) parameter —
                # lmfit's set(value=) silently drops the expression, which
                # would free parameters like a Voigt's gamma/fwhm/height
                # and break the model.
                if func.guesser is not None:
                    try:
                        for k, v in func.guesser(x[mask], y[mask]).items():
                            full = prefix + k
                            if full in pars and not pars[full].expr:
                                pars[full].set(value=v)
                    except Exception:
                        pass
                else:
                    try:
                        g = model.guess(y[mask], x=x[mask])
                        for k in pars:
                            if k in g and not pars[k].expr:
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
                         "max": par.max, "vary": bool(par.vary),
                         "expr": ""}
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
            self._peak_list.item(i).setText(
                f"{i + 1}: {pk['func'].label}  [p{i}]")
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
                expr_it = QTableWidgetItem(spec.get("expr", ""))
                expr_it.setToolTip(
                    "Tie this parameter to others, e.g. "
                    "p0_center+1.5 or 0.5*p0_amplitude (peak prefixes "
                    "are shown in the list above)")
                self._table.setItem(r, 5, expr_it)
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
        elif c == 5:
            spec["expr"] = item.text().strip()

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
        # Remember the exact ranges used for this fit, so Apply/chart use
        # them rather than re-reading the edit fields — which get
        # overwritten the moment the user clicks in the sheet (cell-pick).
        yinfo = _range_to_col_rows(self._y_edit.text())
        xinfo = _range_to_col_rows(self._x_edit.text())
        self._fit_ctx = {
            "ycol": yinfo[0], "r0": yinfo[1], "r1": yinfo[2],
            "xcol": xinfo[0] if xinfo else None,
            "y_full": y_full.copy(),
        }
        mask = np.isfinite(x_full) & np.isfinite(y_full)
        # Restrict to the region between the delimiter lines, if set.
        self._fit_region = self._region()
        if self._fit_region is not None:
            mask = mask & (x_full >= self._fit_region[0]) \
                & (x_full <= self._fit_region[1])
        if mask.sum() < 3:
            QMessageBox.warning(
                self, "Curve Fitting",
                "Not enough numeric data points in the selected range "
                "to fit. Move the green delimiter lines wider.")
            return
        x, y = x_full[mask], y_full[mask]

        bg_key = self._bg_combo.currentData()
        is_data = fm.is_data_background(bg_key)
        is_active = fm.is_active_background(bg_key)
        reverse = bg_key.endswith("_rev")

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
                if full not in params:
                    continue
                expr = spec.get("expr", "").strip()
                if expr:
                    # Tie this parameter to others (inter-peak constraint).
                    params[full].set(value=spec["value"], expr=expr)
                else:
                    params[full].set(
                        value=spec["value"], min=spec["min"],
                        max=spec["max"], vary=spec["vary"], expr="")
        if deg is not None and deg >= 0:
            params["bg_c0"].set(value=float(np.nanmin(y)))
            for d in range(1, deg + 1):
                params[f"bg_c{d}"].set(value=0.0)

        self._data_bg_full = None
        try:
            if is_data:
                bg = fm.data_background(bg_key, x, y)
                if is_active:
                    # Refine the Shirley from the fitted peak model until
                    # the background stops changing (or 12 passes).
                    tol = 1e-4 * (float(np.ptp(y)) + 1e-9)
                    for _ in range(12):
                        result = comp.fit(y - bg, params, x=x)
                        params = result.params
                        new_bg = fm.active_shirley_background(
                            x, y, result.best_fit, reverse=reverse)
                        done = np.max(np.abs(new_bg - bg)) <= tol
                        bg = new_bg
                        if done:
                            break
                result = comp.fit(y - bg, params, x=x)
                bg_full = np.full(len(x_full), np.nan)
                bg_full[mask] = bg
                self._data_bg_full = bg_full
            else:
                result = comp.fit(y, params, x=x)
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
        self._save_to_sheet()  # remember settings/params in the file

    def _build_fit_arrays(self, x_full, bg_key, result):
        finite = np.isfinite(x_full)
        # Restrict everything the fit produced to the region between the
        # delimiters (background/peaks/total/residual are only meaningful
        # there); the raw data scatter still shows the full range.
        region = self._fit_region
        if region is not None:
            finite = finite & (x_full >= region[0]) & (x_full <= region[1])
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
        if self._data_bg_full is not None:
            # Use the background actually computed during the fit (the
            # active variants depend on the peak model, so they can't be
            # recomputed from the data alone).
            bg = self._data_bg_full.copy()
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

    # ── Region delimiters ───────────────────────────────────────────

    def _region(self):
        """Current fit region as (lo, hi), or None if not both set."""
        if self._range_lo is None or self._range_hi is None:
            return None
        return (min(self._range_lo, self._range_hi),
                max(self._range_lo, self._range_hi))

    def _add_range_lines(self, x_full):
        """Draw the two draggable region delimiters on the current axes,
        initialising them to the data extent the first time."""
        finite = np.asarray(x_full, dtype=float)
        finite = finite[np.isfinite(finite)]
        if finite.size == 0:
            return
        xmin, xmax = float(finite.min()), float(finite.max())
        if self._range_lo is None or self._range_hi is None:
            self._range_lo, self._range_hi = xmin, xmax
        else:
            # Keep within the data, but don't collapse the range.
            self._range_lo = min(max(self._range_lo, xmin), xmax)
            self._range_hi = min(max(self._range_hi, xmin), xmax)
        self._range_lines = [
            self._ax.axvline(self._range_lo, color="#27ae60", lw=1.3,
                             ls="--", zorder=5),
            self._ax.axvline(self._range_hi, color="#27ae60", lw=1.3,
                             ls="--", zorder=5),
        ]

    def _on_line_press(self, event):
        # Ignore while a pan/zoom tool is active, or outside the axes.
        if (getattr(self._nav, "mode", "") or event.inaxes is not self._ax
                or event.x is None or not self._range_lines):
            return
        trans = self._ax.transData
        best, best_d = None, 8.0  # pixel tolerance
        for i, val in enumerate((self._range_lo, self._range_hi)):
            if val is None:
                continue
            xpix = trans.transform((val, 0))[0]
            d = abs(event.x - xpix)
            if d < best_d:
                best, best_d = i, d
        self._drag_line = best

    def _on_line_motion(self, event):
        if (self._drag_line is None or event.inaxes is not self._ax
                or event.xdata is None):
            return
        if self._drag_line == 0:
            self._range_lo = float(event.xdata)
        else:
            self._range_hi = float(event.xdata)
        line = self._range_lines[self._drag_line]
        line.set_xdata([event.xdata, event.xdata])
        self._canvas.draw_idle()

    def _on_line_release(self, event):
        self._drag_line = None

    def _preview_data(self):
        """Show the picked X/Y data on the plot before any fit, so the
        user can confirm the selection is right.  Once a fit exists the
        plot keeps showing it (range edits from clicking cells must not
        wipe the result), until the user fits again."""
        if self._result is not None:
            return
        x_full, y_full = self._read_xy(silent=True)
        self._ax.clear()
        if (x_full is None or not np.isfinite(np.asarray(
                y_full, dtype=float)).any()):
            self._ax.text(
                0.5, 0.5, "Select X and Y data ranges",
                ha="center", va="center", color="#888",
                transform=self._ax.transAxes)
            self._canvas.draw_idle()
            return
        self._ax.plot(x_full, y_full, "o", ms=3, color="#3a78b4",
                      label="data")
        self._ax.legend(loc="best", fontsize=7, framealpha=0.8)
        self._ax.relim()
        self._ax.autoscale_view()
        self._add_range_lines(x_full)
        self._canvas.draw_idle()

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
        # Residual, drawn below the data so it doesn't overlap the peaks.
        resid = y_full - total
        finite = np.isfinite(resid)
        if finite.any():
            span = np.nanmax(y_full) - np.nanmin(y_full)
            offset = np.nanmin(y_full) - 0.12 * (span or 1.0)
            self._ax.plot(x_full, resid + offset, "-", color="#7f8c8d",
                          lw=0.8, label="residual", zorder=2)
            self._ax.axhline(offset, color="#cccccc", lw=0.6, zorder=1)
        self._ax.legend(loc="best", fontsize=7, framealpha=0.8)
        self._ax.relim()
        self._ax.autoscale_view()
        self._add_range_lines(x_full)
        self._canvas.draw_idle()

    def _write_report(self, result, x_full, y_full):
        mask = np.isfinite(x_full) & np.isfinite(y_full)
        region = self._fit_region
        if region is not None:
            mask = mask & (x_full >= region[0]) & (x_full <= region[1])
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
        if self._fit_arrays is None or self._fit_ctx is None:
            return
        ctx = self._fit_ctx
        ycol, r0, r1 = ctx["ycol"], ctx["r0"], ctx["r1"]
        x_full, labels, arrays, bg, total = self._fit_arrays
        y_full = ctx["y_full"]
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

        # Decide where the column headers go. If the first row of the Y
        # selection is a text header (non-numeric), the fit headers sit on
        # that same row; if it's numeric data, put them in the row above
        # (when there is one).
        def _is_number(t):
            try:
                float(t)
                return True
            except (TypeError, ValueError):
                return False

        if not _is_number(self._sheet.cell_text(r0, ycol)):
            header_row = r0          # selection includes a text header
        elif r0 > 0:
            header_row = r0 - 1      # header sits just above the data
        else:
            header_row = None        # data starts at the very top row

        changes = []
        for j, (header, arr) in enumerate(out_cols):
            c = start_col + j
            if header_row is not None:
                old = self._sheet.cell_text(header_row, c)
                changes.append((header_row, c, old, header))
            for k, v in enumerate(arr):
                r = r0 + k
                if r == header_row or not np.isfinite(v):
                    continue
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

        if self._chart_chk.isChecked():
            self._make_result_chart(ycol, ctx["xcol"], r0, r1, start_col,
                                    out_cols)

        QMessageBox.information(
            self, "Curve Fitting",
            f"Wrote {len(out_cols)} columns starting at "
            f"{col_index_to_letter(start_col)}.")

    def _make_result_chart(self, ycol, xcol, r0, r1, start_col, out_cols):
        """Drop an embedded chart on the sheet: the raw data as points
        and every fitted curve (background, components, total, residual)
        as a line.  Series reference the sheet columns, so they update
        live if the data or a re-fit changes."""
        from .graph import EmbeddedChart
        sheet = self._sheet

        def _xy(col):
            y = sheet.numeric_column(col)[r0:r1 + 1]
            if xcol is not None:
                xx = sheet.numeric_column(xcol)[r0:r1 + 1]
            else:
                xx = np.arange(len(y), dtype=float)
            n = min(len(xx), len(y))
            xx, y = xx[:n], y[:n]
            m = ~(np.isnan(xx) | np.isnan(y))
            return xx[m], y[m]

        dx, dy = _xy(ycol)
        if len(dx) == 0:
            return
        data_label = (sheet.cell_text(r0 - 1, ycol).strip() if r0 > 0
                      else "") or "data"
        viewport = sheet.table.viewport()
        chart = EmbeddedChart(
            dx, dy, data_label, "Scatter", sheet, viewport,
            x_col=xcol, y_col=ycol, row_start=r0, row_end=r1)
        offset = len(sheet._charts) * 30
        chart.move(60 + offset, 60 + offset)
        sheet._charts.append(chart)
        sheet.data_changed.connect(chart._on_data_changed)
        for j, (header, _arr) in enumerate(out_cols):
            c = start_col + j
            cx, cy = _xy(c)
            if len(cx):
                chart.add_series(cx, cy, header, "Line", x_col=xcol,
                                 y_col=c, row_start=r0, row_end=r1)

    # ── State persistence (remembered in the .ksheet file) ──────────

    def _get_state(self) -> dict:
        """Capture everything the dialog needs to be restored later."""
        return {
            "x": self._x_edit.text(),
            "y": self._y_edit.text(),
            "background": self._bg_combo.currentData(),
            "range_lo": self._range_lo,
            "range_hi": self._range_hi,
            "create_chart": self._chart_chk.isChecked(),
            "custom": dict(self._custom_store),
            "peaks": [
                {"key": pk["func"].key, "params": pk["params"]}
                for pk in self._peaks
            ],
        }

    def _restore_state(self, state: dict):
        """Rebuild the dialog from a saved state dict."""
        self._custom_store.update(state.get("custom", {}) or {})
        self._refresh_function_combo()
        by_key = {f.key: f for f in self._functions}

        self._x_edit.setText(state.get("x", ""))
        self._y_edit.setText(state.get("y", ""))
        bg = state.get("background")
        if bg is not None:
            i = self._bg_combo.findData(bg)
            if i >= 0:
                self._bg_combo.setCurrentIndex(i)
        self._range_lo = state.get("range_lo")
        self._range_hi = state.get("range_hi")
        self._chart_chk.setChecked(bool(state.get("create_chart", True)))

        self._peaks = []
        self._peak_list.clear()
        for i, pkd in enumerate(state.get("peaks", [])):
            func = by_key.get(pkd.get("key"))
            if func is None:
                continue
            prefix = f"p{len(self._peaks)}_"
            self._peaks.append({"func": func, "prefix": prefix,
                                "params": pkd.get("params", {})})
            self._peak_list.addItem(
                f"{len(self._peaks)}: {func.label}  [{prefix.rstrip('_')}]")
        if self._peaks:
            self._peak_list.setCurrentRow(0)

    def _save_to_sheet(self):
        self._sheet._fit_config = self._get_state()

    # ── Cleanup ─────────────────────────────────────────────────────

    def _disconnect(self):
        try:
            self._sheet.table.itemSelectionChanged.disconnect(
                self._on_sheet_selection)
        except (TypeError, RuntimeError):
            pass

    def closeEvent(self, ev):
        self._save_to_sheet()
        self._disconnect()
        super().closeEvent(ev)

    def reject(self):
        self._save_to_sheet()
        self._disconnect()
        super().reject()
