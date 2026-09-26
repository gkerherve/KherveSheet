"""Trendline — curve fitting dialog for embedded charts.

Provides a comprehensive set of fit models via scipy.optimize.curve_fit,
displays the fitted curve on the chart, and reports equation, R², and
goodness-of-fit statistics.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox,
    QTextEdit, QGroupBox, QRadioButton, QButtonGroup,
    QFormLayout, QSplitter, QWidget, QMessageBox, QLineEdit,
    QScrollArea, QFrame,
)

from .core.fitting import (  # noqa: F401 (re-exported)
    MODELS,
    MOVING_AVERAGE_KEY,
    TrendlineInfo,
    _build_poly_func,
    _compute_gof,
    _model_allometric,
    _model_boltzmann,
    _model_cubic,
    _model_double_exp,
    _model_error_function,
    _model_exp_decay,
    _model_exponential,
    _model_gaussian,
    _model_hill,
    _model_hyperbolic,
    _model_inverse,
    _model_linear,
    _model_logarithmic,
    _model_logistic,
    _model_lorentzian,
    _model_michaelis_menten,
    _model_power,
    _model_quadratic,
    _model_reciprocal_quadratic,
    _model_sine,
    _model_sqrt,
    _model_stretched_exp,
    _p0_auto,
    _safe_exp,
    _smart_p0,
    fit_series,
)


# ── Trendline Dialog ────────────────────────────────────────────────

class TrendlineDialog(QDialog):
    """Add / edit trendline on an EmbeddedChart."""

    def __init__(self, chart, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Trendline")
        self.setMinimumSize(680, 520)
        self._chart = chart
        self._current_trendline: Optional[TrendlineInfo] = None

        self._build_ui()

    def _build_ui(self):
        outer = QHBoxLayout(self)

        # ── Left panel: options ─────────────────────────────────────
        left = QVBoxLayout()

        # Series picker (exclude trendline series)
        grp_series = QGroupBox("Data Series")
        sl = QVBoxLayout(grp_series)
        self._series_combo = QComboBox()
        for i, s in enumerate(self._chart._series):
            if s.get("is_trendline"):
                continue
            self._series_combo.addItem(
                s.get("label", f"Series {i + 1}"), i)
        sl.addWidget(self._series_combo)
        left.addWidget(grp_series)

        # Model picker
        grp_model = QGroupBox("Trendline Type")
        ml = QVBoxLayout(grp_model)
        self._model_combo = QComboBox()
        model_names = list(MODELS.keys()) + [MOVING_AVERAGE_KEY]
        self._model_combo.addItems(model_names)
        ml.addWidget(self._model_combo)

        # Polynomial order spinner
        poly_row = QHBoxLayout()
        self._order_label = QLabel("Order:")
        self._order_spin = QSpinBox()
        self._order_spin.setRange(2, 20)
        self._order_spin.setValue(4)
        poly_row.addWidget(self._order_label)
        poly_row.addWidget(self._order_spin)
        poly_row.addStretch()
        ml.addLayout(poly_row)

        # Moving average period
        ma_row = QHBoxLayout()
        self._ma_label = QLabel("Period:")
        self._ma_spin = QSpinBox()
        self._ma_spin.setRange(2, 100)
        self._ma_spin.setValue(2)
        ma_row.addWidget(self._ma_label)
        ma_row.addWidget(self._ma_spin)
        ma_row.addStretch()
        ml.addLayout(ma_row)

        left.addWidget(grp_model)

        # Display options
        grp_disp = QGroupBox("Display on Chart")
        dl = QVBoxLayout(grp_disp)
        self._show_eq_chk = QCheckBox("Display Equation")
        self._show_r2_chk = QCheckBox("Display R² value")
        dl.addWidget(self._show_eq_chk)
        dl.addWidget(self._show_r2_chk)
        left.addWidget(grp_disp)

        # Fit button
        self._fit_btn = QPushButton("Fit")
        self._fit_btn.setStyleSheet(
            "QPushButton { font-weight: bold; padding: 6px 20px; }")
        left.addWidget(self._fit_btn)

        # Remove / Close
        btn_row = QHBoxLayout()
        self._remove_btn = QPushButton("Remove Trendline")
        self._close_btn = QPushButton("Close")
        btn_row.addWidget(self._remove_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._close_btn)
        left.addLayout(btn_row)

        left.addStretch()

        # ── Right panel: report ─────────────────────────────────────
        right = QVBoxLayout()
        right.addWidget(QLabel("Fit Report"))
        self._report = QTextEdit()
        self._report.setReadOnly(True)
        self._report.setFont(QFont("Consolas", 9))
        self._report.setMinimumWidth(300)
        right.addWidget(self._report)

        # Assemble
        left_w = QWidget()
        left_w.setLayout(left)
        right_w = QWidget()
        right_w.setLayout(right)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_w)
        splitter.addWidget(right_w)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter)

        # Connections
        self._model_combo.currentTextChanged.connect(self._on_model_changed)
        self._fit_btn.clicked.connect(self._do_fit)
        self._remove_btn.clicked.connect(self._remove_trendline)
        self._close_btn.clicked.connect(self.accept)
        self._show_eq_chk.toggled.connect(self._toggle_annotations)
        self._show_r2_chk.toggled.connect(self._toggle_annotations)

        self._on_model_changed(self._model_combo.currentText())

    # ── Show/hide order/period spinners ─────────────────────────────

    def _on_model_changed(self, name):
        is_poly = (name == "Polynomial")
        is_ma = (name == MOVING_AVERAGE_KEY)
        self._order_label.setVisible(is_poly)
        self._order_spin.setVisible(is_poly)
        self._ma_label.setVisible(is_ma)
        self._ma_spin.setVisible(is_ma)

    # ── Perform fit ─────────────────────────────────────────────────

    def _do_fit(self):
        idx = self._series_combo.currentData()
        if idx is None or idx >= len(self._chart._series):
            return
        s = self._chart._series[idx]
        x_raw = np.asarray(s["x"], dtype=float)
        y_raw = np.asarray(s["y"], dtype=float)

        # Remove NaNs
        mask = np.isfinite(x_raw) & np.isfinite(y_raw)
        x = x_raw[mask]
        y = y_raw[mask]
        if len(x) < 2:
            QMessageBox.warning(self, "Trendline",
                                "Not enough data points (need at least 2).")
            return

        model_name = self._model_combo.currentText()

        # Remove previous trendline for the current source series
        self._remove_current_trendline()

        info = TrendlineInfo()
        info.series_idx = idx
        info.model_name = model_name
        info.show_equation = self._show_eq_chk.isChecked()
        info.show_r_squared = self._show_r2_chk.isChecked()

        if model_name == MOVING_AVERAGE_KEY:
            period = self._ma_spin.value()
            info.ma_period = period
            self._fit_moving_average(x, y, period, info)
        elif model_name == "Polynomial":
            order = self._order_spin.value()
            info.poly_order = order
            self._fit_polynomial(x, y, order, info)
        else:
            fit = fit_series(x, y, model_name)
            if "error" in fit:
                self._report.setPlainText(
                    f"{fit['error']}\n\n"
                    f"Try different initial data or another model.")
                return

            params, errors, gof = (fit["params"], fit["errors"],
                                   fit["gof"])
            info.params = dict(params)
            info.equation = fit["equation"]
            info.gof = gof

            x_smooth = np.linspace(np.nanmin(x), np.nanmax(x), 300)
            try:
                y_smooth = fit["predict"](x_smooth)
            except Exception:
                y_smooth = np.full_like(x_smooth, np.nan)
            label = f"{info.model_name} fit"
            self._add_fit_series(x_smooth, y_smooth, label, info)
            self._show_report(model_name, params, errors, gof,
                              info.equation)

        self._current_trendline = info

        # Store on chart for serialisation
        if not hasattr(self._chart, '_trendlines'):
            self._chart._trendlines = []
        # Replace existing trendline for same source series, or add new
        replaced = False
        for i, t in enumerate(self._chart._trendlines):
            if t.series_idx == idx:
                self._chart._trendlines[i] = info
                replaced = True
                break
        if not replaced:
            self._chart._trendlines.append(info)

    def _fit_polynomial(self, x, y, order, info: TrendlineInfo):
        if order >= len(x):
            QMessageBox.warning(self, "Trendline",
                                f"Polynomial order {order} requires at least "
                                f"{order + 1} data points (have {len(x)}).")
            return

        coeffs = np.polyfit(x, y, order)
        y_fit = np.polyval(coeffs, x)
        gof = _compute_gof(y, y_fit, order + 1)

        _, param_names, eq_template = _build_poly_func(order)
        params = dict(zip(param_names, coeffs))
        info.params = {k: float(v) for k, v in params.items()}
        info.equation = eq_template.format(**params)
        info.gof = gof

        x_smooth = np.linspace(np.nanmin(x), np.nanmax(x), 300)
        y_smooth = np.polyval(coeffs, x_smooth)
        label = f"Poly({order}) fit"
        self._add_fit_series(x_smooth, y_smooth, label, info)

        # Report
        lines = [f"Polynomial Fit (order {order})",
                 "=" * 40, "",
                 f"Equation: {info.equation}", ""]
        lines.append("Parameters:")
        for name, val in params.items():
            lines.append(f"  {name:>6s} = {val: .8g}")
        lines += ["", "Goodness of Fit:", "-" * 30]
        for k, v in gof.items():
            lines.append(f"  {k:<16s} = {v: .8g}")
        self._report.setPlainText("\n".join(lines))

    def _fit_moving_average(self, x, y, period, info: TrendlineInfo):
        if period > len(y):
            QMessageBox.warning(self, "Trendline",
                                f"Period {period} is larger than data length.")
            return
        kernel = np.ones(period) / period
        y_ma = np.convolve(y, kernel, mode='valid')
        x_ma = x[period - 1:]

        y_interp = np.interp(x, x_ma, y_ma)
        gof = _compute_gof(y, y_interp, period)
        info.equation = f"Moving Average (period={period})"
        info.gof = gof
        info.params = {"period": period}

        label = f"MA({period})"
        self._add_fit_series(x_ma, y_ma, label, info)

        lines = [f"Moving Average (period={period})",
                 "=" * 40, ""]
        lines += ["Goodness of Fit:", "-" * 30]
        for k, v in gof.items():
            lines.append(f"  {k:<16s} = {v: .8g}")
        self._report.setPlainText("\n".join(lines))

    def _add_fit_series(self, x, y, label, info: TrendlineInfo):
        """Add the trendline as a real chart series."""
        chart = self._chart
        chart.add_series(np.asarray(x), np.asarray(y), label, "Line")
        fit_idx = len(chart._series) - 1
        info.fit_series_idx = fit_idx
        # Mark series as a trendline
        chart._series[fit_idx]["is_trendline"] = True
        # Style the artist: dashed, red, thin
        artist = chart._series[fit_idx].get("artist")
        if artist is not None and hasattr(artist, 'set_linestyle'):
            artist.set_linestyle(info.linestyle)
            artist.set_color(info.color)
            artist.set_linewidth(info.linewidth)
            # Remove marker if any
            if hasattr(artist, 'set_marker'):
                artist.set_marker('')
        self._add_annotations(info)
        chart._canvas.draw_idle()

    def _show_report(self, model_name, params, errors, gof, equation):
        lines = [f"{model_name} Fit",
                 "=" * 40, "",
                 f"Equation: {equation}", ""]
        lines.append("Parameters:")
        for name in params:
            v = params[name]
            e = errors.get(name, 0)
            lines.append(f"  {name:>8s} = {v: .8g}  ± {e:.4g}")
        lines += ["", "Goodness of Fit:", "-" * 30]
        for k, v in gof.items():
            lines.append(f"  {k:<16s} = {v: .8g}")
        self._report.setPlainText("\n".join(lines))

    # ── Annotations on chart ────────────────────────────────────────

    def _add_annotations(self, info: TrendlineInfo):
        ax = self._chart._ax
        # Position in axes coordinates (top-left area)
        y_pos = 0.95
        if info.show_equation and info.equation:
            info.eq_artist = ax.text(
                0.05, y_pos, info.equation,
                transform=ax.transAxes, fontsize=8,
                verticalalignment='top',
                bbox=dict(boxstyle='round,pad=0.3',
                          facecolor='wheat', alpha=0.7))
            y_pos -= 0.08
        if info.show_r_squared and "R²" in info.gof:
            r2 = info.gof["R²"]
            info.r2_artist = ax.text(
                0.05, y_pos, f"R² = {r2:.6f}",
                transform=ax.transAxes, fontsize=8,
                verticalalignment='top',
                bbox=dict(boxstyle='round,pad=0.3',
                          facecolor='wheat', alpha=0.7))

    def _toggle_annotations(self):
        if self._current_trendline is None:
            return
        info = self._current_trendline
        # Remove old annotations
        if info.eq_artist:
            try:
                info.eq_artist.remove()
            except Exception:
                pass
            info.eq_artist = None
        if info.r2_artist:
            try:
                info.r2_artist.remove()
            except Exception:
                pass
            info.r2_artist = None
        info.show_equation = self._show_eq_chk.isChecked()
        info.show_r_squared = self._show_r2_chk.isChecked()
        self._add_annotations(info)
        self._chart._canvas.draw_idle()

    # ── Remove trendline ────────────────────────────────────────────

    def _remove_current_trendline(self):
        """Remove the current fit's series from the chart."""
        if self._current_trendline:
            _remove_trendline_series(
                self._chart, self._current_trendline)
            # Remove from chart's trendline list
            if hasattr(self._chart, '_trendlines'):
                try:
                    self._chart._trendlines.remove(
                        self._current_trendline)
                except ValueError:
                    pass
            self._current_trendline = None

    def _remove_trendline(self):
        """Remove ALL trendlines from the chart."""
        _remove_all_trendlines(self._chart)
        self._current_trendline = None
        self._report.clear()
        self._chart._canvas.draw_idle()


# ── Helper functions for trendline management ───────────────────────

def _remove_trendline_series(chart, info: TrendlineInfo):
    """Remove the fit series and annotations for one trendline."""
    # Remove annotations
    for attr in ('eq_artist', 'r2_artist'):
        obj = getattr(info, attr, None)
        if obj is not None:
            try:
                obj.remove()
            except Exception:
                pass
            setattr(info, attr, None)
    # Remove the series from the chart
    fit_idx = info.fit_series_idx
    if fit_idx < 0 or fit_idx >= len(chart._series):
        return
    s = chart._series[fit_idx]
    artist = s.get("artist")
    if artist is not None:
        try:
            artist.remove()
        except Exception:
            pass
    chart._series.pop(fit_idx)
    if fit_idx < len(chart._y_cols):
        chart._y_cols.pop(fit_idx)
    # Refresh legend
    leg = chart._ax.legend(loc="best", framealpha=0.8, fontsize=8)
    if leg:
        leg.set_draggable(True)
    # Adjust fit_series_idx on remaining trendlines
    for t in getattr(chart, '_trendlines', []):
        if t is not info and t.fit_series_idx > fit_idx:
            t.fit_series_idx -= 1
    info.fit_series_idx = -1


def _remove_all_trendlines(chart):
    """Remove ALL trendline series and annotations from *chart*."""
    trendlines = getattr(chart, '_trendlines', [])
    # Remove annotations first
    for info in trendlines:
        for attr in ('eq_artist', 'r2_artist'):
            obj = getattr(info, attr, None)
            if obj is not None:
                try:
                    obj.remove()
                except Exception:
                    pass
    # Remove series marked as trendlines (iterate in reverse to keep indices valid)
    to_remove = []
    for i, s in enumerate(chart._series):
        if s.get("is_trendline"):
            to_remove.append(i)
    for i in reversed(to_remove):
        artist = chart._series[i].get("artist")
        if artist is not None:
            try:
                artist.remove()
            except Exception:
                pass
        chart._series.pop(i)
        if i < len(chart._y_cols):
            chart._y_cols.pop(i)
    chart._trendlines.clear()
    # Refresh legend
    if chart._series:
        leg = chart._ax.legend(loc="best", framealpha=0.8, fontsize=8)
        if leg:
            leg.set_draggable(True)
    chart._canvas.draw_idle()


def restore_trendline(chart, info: TrendlineInfo):
    """Redraw a trendline from saved TrendlineInfo onto *chart*."""
    if info.series_idx >= len(chart._series):
        return
    s = chart._series[info.series_idx]
    x_raw = np.asarray(s["x"], dtype=float)
    y_raw = np.asarray(s["y"], dtype=float)
    mask = np.isfinite(x_raw) & np.isfinite(y_raw)
    x = x_raw[mask]
    if len(x) < 2:
        return

    model_name = info.model_name

    if model_name == MOVING_AVERAGE_KEY:
        period = info.ma_period
        kernel = np.ones(period) / period
        y_ma = np.convolve(y_raw[mask], kernel, mode='valid')
        x_ma = x[period - 1:]
        x_fit, y_fit = x_ma, y_ma
        label = f"MA({period})"
    elif model_name == "Polynomial":
        order = info.poly_order
        coeffs = [info.params.get(f"a{i}", 0) for i in range(order + 1)]
        x_fit = np.linspace(np.nanmin(x), np.nanmax(x), 300)
        y_fit = np.polyval(coeffs, x_fit)
        label = f"Poly({order}) fit"
    else:
        model = MODELS.get(model_name)
        if model is None or model["func"] is None:
            return
        func = model["func"]
        popt = [info.params.get(p, 0) for p in model["params"]]
        x_fit = np.linspace(np.nanmin(x), np.nanmax(x), 300)
        try:
            y_fit = func(x_fit, *popt)
        except Exception:
            return
        label = f"{model_name} fit"

    # Add as a real series
    chart.add_series(np.asarray(x_fit), np.asarray(y_fit), label, "Line")
    fit_idx = len(chart._series) - 1
    info.fit_series_idx = fit_idx
    chart._series[fit_idx]["is_trendline"] = True
    artist = chart._series[fit_idx].get("artist")
    if artist is not None and hasattr(artist, 'set_linestyle'):
        artist.set_linestyle(info.linestyle)
        artist.set_color(info.color)
        artist.set_linewidth(info.linewidth)
        if hasattr(artist, 'set_marker'):
            artist.set_marker('')

    # Annotations
    ax = chart._ax
    y_pos = 0.95
    if info.show_equation and info.equation:
        info.eq_artist = ax.text(
            0.05, y_pos, info.equation,
            transform=ax.transAxes, fontsize=8,
            verticalalignment='top',
            bbox=dict(boxstyle='round,pad=0.3',
                      facecolor='wheat', alpha=0.7))
        y_pos -= 0.08
    if info.show_r_squared and "R²" in info.gof:
        r2 = info.gof["R²"]
        if np.isfinite(r2):
            info.r2_artist = ax.text(
                0.05, y_pos, f"R² = {r2:.6f}",
                transform=ax.transAxes, fontsize=8,
                verticalalignment='top',
                bbox=dict(boxstyle='round,pad=0.3',
                          facecolor='wheat', alpha=0.7))
