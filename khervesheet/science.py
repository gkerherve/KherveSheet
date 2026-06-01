"""Science — data-analysis tools as small pop-up dialogs.

Each tool reads an X/Y range from the active sheet (X blank = sample
index), applies a numerical transform (normalise, integrate, derive,
smooth, FFT, interpolate, find peaks) and writes the result into new
columns starting at a cell the user picks.  Every write goes through a
single ``BulkCellEditCmd`` so it is fully undoable.

The dialogs are non-modal and share the Solver-style cell-pick machinery
(click a reference field, then click / drag a range in the sheet).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from typing import List, Optional, Tuple

import numpy as np

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QGroupBox, QMessageBox,
    QDoubleSpinBox, QSpinBox, QWidget,
)

from .sheet import SheetWidget, BulkCellEditCmd, col_index_to_letter
from .solver import (
    _PickLineEdit, _parse_range, _selection_ref_str,
    _PICK_STYLE, _NORMAL_STYLE,
)


# ── Base tool dialog ────────────────────────────────────────────────

class ScienceToolDialog(QDialog):
    """Common scaffold for every Science tool.

    Subclasses set ``TITLE`` and implement :meth:`_build_options` (extra
    widgets) and :meth:`_compute` (returns a list of ``(header, array)``
    output columns).  The base class supplies the Output-location row,
    the X/Y data group, cell-pick support and the result writer.
    """

    TITLE = "Science Tool"
    #: when True an X column is written next to the result.  Off by
    #: default: transforms that leave X unchanged (normalise, integrate,
    #: derivative, smooth) already have X in the source, so a copy would
    #: just be a confusing duplicate.  Tools that produce a *new* X
    #: (FFT, interpolation, find peaks) emit it as their own column.
    EMIT_X = False

    def __init__(self, sheet: SheetWidget, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.TITLE)
        self.setWindowModality(Qt.NonModal)
        self.setMinimumWidth(420)
        self._sheet = sheet
        self._active_edit: Optional[_PickLineEdit] = None

        self._build_ui()
        self._pre_fill()

        self._sheet.table.itemSelectionChanged.connect(
            self._on_sheet_selection)

    # ── UI ──────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # --- Output location -----------------------------------------
        out_box = QGroupBox("Output")
        out_form = QFormLayout(out_box)
        self._out_edit = _PickLineEdit(self)
        self._out_edit.setPlaceholderText(
            "Top-left cell, e.g. $D$1  (blank = next free column)")
        out_form.addRow("Add results to:", self._out_edit)
        self._out_hint = QLabel("")
        self._out_hint.setStyleSheet("color: #666;")
        out_form.addRow("", self._out_hint)
        self._out_edit.textChanged.connect(self._update_out_hint)
        layout.addWidget(out_box)

        # --- Data -----------------------------------------------------
        data_box = QGroupBox("Data")
        data_form = QFormLayout(data_box)
        self._x_edit = _PickLineEdit(self)
        self._x_edit.setPlaceholderText(
            "X range, e.g. $A$2:$A$500  (blank = sample index)")
        self._y_edit = _PickLineEdit(self)
        self._y_edit.setPlaceholderText("Y range, e.g. $B$2:$B$500")
        data_form.addRow("X:", self._x_edit)
        data_form.addRow("Y:", self._y_edit)
        layout.addWidget(data_box)

        # --- Tool-specific options -----------------------------------
        opt_box = QGroupBox("Options")
        self._opt_form = QFormLayout(opt_box)
        self._build_options(self._opt_form)
        layout.addWidget(opt_box)

        # --- Buttons --------------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._apply_btn = QPushButton("Compute && Write")
        self._close_btn = QPushButton("Close")
        btn_row.addWidget(self._apply_btn)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

        self._apply_btn.clicked.connect(self._on_apply)
        self._close_btn.clicked.connect(self.close)

    def _build_options(self, form: QFormLayout):
        """Override to add tool-specific option widgets."""

    def _pre_fill(self):
        """Pre-fill Y (and X) from the current sheet selection."""
        ref = _selection_ref_str(self._sheet)
        if ref:
            self._y_edit.setText(ref)
        self._set_active_pick(self._y_edit)
        self._update_out_hint()

    # ── Cell-pick machinery (mirrors SolverDialog) ───────────────────

    def _set_active_pick(self, edit: _PickLineEdit):
        if self._active_edit and self._active_edit is not edit:
            self._active_edit.setStyleSheet(_NORMAL_STYLE)
        self._active_edit = edit
        edit.setStyleSheet(_PICK_STYLE)

    def _on_sheet_selection(self):
        if self._active_edit is None or not self.isVisible():
            return
        ref = _selection_ref_str(self._sheet)
        if ref:
            self._active_edit.setText(ref)
            self.activateWindow()

    def _update_out_hint(self):
        sr, sc = self._resolve_output_start()
        self._out_hint.setText(
            f"→ writing to column {col_index_to_letter(sc)} "
            f"(row {sr + 1} onward)")

    # ── Data access ──────────────────────────────────────────────────

    def _values(self, text: str) -> np.ndarray:
        out = []
        for (r, c) in _parse_range(text):
            t = self._sheet.cell_text(r, c)
            try:
                out.append(float(t))
            except (TypeError, ValueError):
                out.append(np.nan)
        return np.array(out, dtype=float)

    def _read_xy(self) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        y = self._values(self._y_edit.text())
        if y.size == 0:
            QMessageBox.warning(self, self.TITLE, "Select a Y range first.")
            return None
        xt = self._x_edit.text().strip()
        x = self._values(xt) if xt else np.arange(y.size, dtype=float)
        n = min(x.size, y.size)
        x, y = x[:n], y[:n]
        mask = np.isfinite(x) & np.isfinite(y)
        x, y = x[mask], y[mask]
        if x.size < 2:
            QMessageBox.warning(
                self, self.TITLE,
                "Need at least two finite data points.")
            return None
        # Sort by X so derivative / integral / interpolation behave.
        order = np.argsort(x)
        return x[order], y[order]

    # ── Output ────────────────────────────────────────────────────────

    def _resolve_output_start(self) -> Tuple[int, int]:
        ref = self._out_edit.text().strip()
        if ref:
            # Accept a single cell ($C$1) or a range ($C$1:$C$1000) /
            # comma-list — results always start at the top-left cell.
            cells = _parse_range(ref)
            if cells:
                rows = [r for r, _c in cells]
                cols = [c for _r, c in cells]
                return (min(rows), min(cols))
        return (0, self._sheet.column_count())

    def _write_columns(self, cols: List[Tuple[str, np.ndarray]]):
        if not cols:
            return
        sr, sc = self._resolve_output_start()
        n_rows = max((sr + 1 + len(arr)) for _h, arr in cols)
        n_cols = sc + len(cols)
        tbl = self._sheet.table
        if tbl.columnCount() < n_cols:
            tbl.setColumnCount(n_cols)
        if tbl.rowCount() < n_rows:
            tbl.setRowCount(n_rows)

        changes = []
        for j, (header, arr) in enumerate(cols):
            c = sc + j
            old = self._sheet.cell_text(sr, c)
            changes.append((sr, c, old, header))
            for k, v in enumerate(arr):
                if not np.isfinite(v):
                    continue
                r = sr + 1 + k
                old = self._sheet.cell_text(r, c)
                changes.append((r, c, old, f"{v:.6g}"))

        for r, c, _old, new in changes:
            self._sheet._set_cell_quiet(r, c, new)
        if self._sheet._undo_stack is not None:
            self._sheet._undo_stack.push(
                BulkCellEditCmd(self._sheet, changes, self.TITLE))
        for j in range(len(cols)):
            self._sheet.data_changed.emit(sc + j)

        QMessageBox.information(
            self, self.TITLE,
            f"Wrote {len(cols)} column(s) starting at "
            f"{col_index_to_letter(sc)}{sr + 1}.")

    # ── Compute hook ─────────────────────────────────────────────────

    def _compute(self, x: np.ndarray, y: np.ndarray
                 ) -> List[Tuple[str, np.ndarray]]:
        raise NotImplementedError

    def _on_apply(self):
        xy = self._read_xy()
        if xy is None:
            return
        try:
            cols = self._compute(*xy)
        except ImportError as exc:
            QMessageBox.critical(
                self, self.TITLE,
                f"This tool needs a library that is not installed:\n{exc}")
            return
        except Exception as exc:  # noqa: BLE001 — surface to the user
            QMessageBox.critical(self, self.TITLE, f"Computation failed:\n{exc}")
            return
        if cols:
            self._write_columns(cols)

    # ── Cleanup ──────────────────────────────────────────────────────

    def closeEvent(self, ev):
        try:
            self._sheet.table.itemSelectionChanged.disconnect(
                self._on_sheet_selection)
        except (TypeError, RuntimeError):
            pass
        super().closeEvent(ev)


# ── Normalisation ───────────────────────────────────────────────────

class NormaliseDialog(ScienceToolDialog):
    TITLE = "Normalisation"

    def _build_options(self, form: QFormLayout):
        self._lo = QDoubleSpinBox()
        self._lo.setRange(-1e12, 1e12)
        self._lo.setDecimals(6)
        self._lo.setValue(0.0)
        self._hi = QDoubleSpinBox()
        self._hi.setRange(-1e12, 1e12)
        self._hi.setDecimals(6)
        self._hi.setValue(1.0)
        row = QHBoxLayout()
        w = QWidget()
        w.setLayout(row)
        row.addWidget(QLabel("min"))
        row.addWidget(self._lo)
        row.addSpacing(12)
        row.addWidget(QLabel("max"))
        row.addWidget(self._hi)
        row.addStretch()
        form.addRow("Scale to:", w)

    def _compute(self, x, y):
        lo, hi = self._lo.value(), self._hi.value()
        ymin, ymax = float(np.min(y)), float(np.max(y))
        if ymax == ymin:
            raise ValueError("Y is constant — cannot normalise.")
        yn = (y - ymin) / (ymax - ymin) * (hi - lo) + lo
        cols = []
        if self.EMIT_X:
            cols.append(("x", x))
        cols.append((f"norm[{lo:g},{hi:g}]", yn))
        return cols


# ── Integration ─────────────────────────────────────────────────────

class IntegrateDialog(ScienceToolDialog):
    TITLE = "Integration"

    def _build_options(self, form: QFormLayout):
        self._mode = QComboBox()
        self._mode.addItems(["Cumulative", "Definite (total only)"])
        form.addRow("Mode:", self._mode)

    def _compute(self, x, y):
        from numpy import trapz
        if self._mode.currentIndex() == 1:
            total = float(trapz(y, x))
            QMessageBox.information(
                self, self.TITLE, f"Definite integral = {total:.6g}")
            return [("integral", np.array([total]))]
        try:
            from scipy.integrate import cumulative_trapezoid as _cumtrap
        except ImportError:
            from scipy.integrate import cumtrapz as _cumtrap
        cum = _cumtrap(y, x, initial=0.0)
        cols = []
        if self.EMIT_X:
            cols.append(("x", x))
        cols.append(("cum_integral", cum))
        return cols


# ── Derivative ──────────────────────────────────────────────────────

class DerivativeDialog(ScienceToolDialog):
    TITLE = "Derivative"

    def _build_options(self, form: QFormLayout):
        self._order = QComboBox()
        self._order.addItems(["1st order", "2nd order"])
        form.addRow("Order:", self._order)

    def _compute(self, x, y):
        d = np.gradient(y, x)
        label = "dy/dx"
        if self._order.currentIndex() == 1:
            d = np.gradient(d, x)
            label = "d2y/dx2"
        cols = []
        if self.EMIT_X:
            cols.append(("x", x))
        cols.append((label, d))
        return cols


# ── Smoothing ───────────────────────────────────────────────────────

class SmoothDialog(ScienceToolDialog):
    TITLE = "Smooth"

    def _build_options(self, form: QFormLayout):
        self._method = QComboBox()
        self._method.addItems(["Moving average", "Savitzky-Golay"])
        self._window = QSpinBox()
        self._window.setRange(2, 999)
        self._window.setValue(5)
        self._poly = QSpinBox()
        self._poly.setRange(1, 10)
        self._poly.setValue(2)
        form.addRow("Method:", self._method)
        form.addRow("Window:", self._window)
        form.addRow("Poly order:", self._poly)
        self._method.currentIndexChanged.connect(
            lambda _i: self._poly.setEnabled(
                self._method.currentIndex() == 1))
        self._poly.setEnabled(False)

    def _compute(self, x, y):
        win = self._window.value()
        if self._method.currentIndex() == 1:
            from scipy.signal import savgol_filter
            if win % 2 == 0:
                win += 1
            win = min(win, y.size if y.size % 2 else y.size - 1)
            poly = min(self._poly.value(), win - 1)
            ys = savgol_filter(y, win, poly)
            label = f"savgol{win}"
        else:
            win = min(win, y.size)
            kernel = np.ones(win) / win
            ys = np.convolve(y, kernel, mode="same")
            label = f"avg{win}"
        cols = []
        if self.EMIT_X:
            cols.append(("x", x))
        cols.append((label, ys))
        return cols


# ── FFT ─────────────────────────────────────────────────────────────

class FFTDialog(ScienceToolDialog):
    TITLE = "FFT"
    EMIT_X = False

    def _build_options(self, form: QFormLayout):
        self._kind = QComboBox()
        self._kind.addItems(["Magnitude", "Power", "Amplitude"])
        form.addRow("Spectrum:", self._kind)

    def _compute(self, x, y):
        n = y.size
        dx = float(np.mean(np.diff(x))) if n > 1 else 1.0
        if dx <= 0:
            dx = 1.0
        freq = np.fft.rfftfreq(n, d=dx)
        spec = np.fft.rfft(y)
        kind = self._kind.currentText()
        if kind == "Power":
            mag = (np.abs(spec) ** 2) / n
            label = "power"
        elif kind == "Amplitude":
            mag = np.abs(spec) * 2.0 / n
            label = "amplitude"
        else:
            mag = np.abs(spec)
            label = "magnitude"
        return [("freq", freq), (label, mag)]


# ── Interpolation ───────────────────────────────────────────────────

class InterpolateDialog(ScienceToolDialog):
    TITLE = "Interpolation"

    def _build_options(self, form: QFormLayout):
        self._npts = QSpinBox()
        self._npts.setRange(2, 1_000_000)
        self._npts.setValue(200)
        self._kind = QComboBox()
        self._kind.addItems(["linear", "cubic", "quadratic", "nearest"])
        form.addRow("Points:", self._npts)
        form.addRow("Method:", self._kind)

    def _compute(self, x, y):
        from scipy.interpolate import interp1d
        # interp1d needs strictly increasing, unique X.
        x, idx = np.unique(x, return_index=True)
        y = y[idx]
        if x.size < 2:
            raise ValueError("Need at least two unique X values.")
        f = interp1d(x, y, kind=self._kind.currentText(),
                     bounds_error=False, fill_value="extrapolate")
        xn = np.linspace(x.min(), x.max(), self._npts.value())
        yn = f(xn)
        return [("x_interp", xn), ("y_interp", yn)]


# ── Find peaks ──────────────────────────────────────────────────────

class FindPeaksDialog(ScienceToolDialog):
    TITLE = "Find Peaks"
    EMIT_X = False

    def _build_options(self, form: QFormLayout):
        self._height = QLineEdit()
        self._height.setPlaceholderText("min height (blank = none)")
        self._prom = QLineEdit()
        self._prom.setPlaceholderText("min prominence (blank = none)")
        self._dist = QSpinBox()
        self._dist.setRange(1, 1_000_000)
        self._dist.setValue(1)
        form.addRow("Height:", self._height)
        form.addRow("Prominence:", self._prom)
        form.addRow("Distance (pts):", self._dist)

    @staticmethod
    def _opt_float(text):
        text = text.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _compute(self, x, y):
        from scipy.signal import find_peaks
        kw = {"distance": self._dist.value()}
        h = self._opt_float(self._height.text())
        if h is not None:
            kw["height"] = h
        p = self._opt_float(self._prom.text())
        if p is not None:
            kw["prominence"] = p
        idx, _props = find_peaks(y, **kw)
        if idx.size == 0:
            QMessageBox.information(
                self, self.TITLE, "No peaks found with these settings.")
            return []
        return [("peak_x", x[idx]), ("peak_y", y[idx])]


#: (label, dialog class) entries for the Science menu, in display order.
TOOLS = [
    ("Normalisation…", NormaliseDialog),
    ("Integration…", IntegrateDialog),
    ("Derivative…", DerivativeDialog),
    ("Smooth…", SmoothDialog),
    ("FFT…", FFTDialog),
    ("Interpolation…", InterpolateDialog),
    ("Find Peaks…", FindPeaksDialog),
]
