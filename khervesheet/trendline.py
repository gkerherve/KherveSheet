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

# ── Fit model definitions ───────────────────────────────────────────
#
# Each model is a dict with:
#   "func"    : callable(x, *params) → y
#   "p0"      : default initial guesses  (or callable(x,y) → list)
#   "eq"      : format string for the equation display
#   "params"  : list of parameter names
#   "extra"   : optional extra widget key (e.g. "order" for polynomial)

def _safe_exp(x):
    return np.exp(np.clip(x, -500, 500))


def _model_linear(x, a, b):
    return a * x + b

def _model_quadratic(x, a, b, c):
    return a * x**2 + b * x + c

def _model_cubic(x, a, b, c, d):
    return a * x**3 + b * x**2 + c * x + d

def _model_exponential(x, a, b):
    return a * _safe_exp(b * x)

def _model_exp_decay(x, a, b, c):
    return a * _safe_exp(-b * x) + c

def _model_logarithmic(x, a, b):
    return a * np.log(np.maximum(x, 1e-300)) + b

def _model_power(x, a, b):
    return a * np.power(np.maximum(x, 1e-300), b)

def _model_sqrt(x, a, b):
    return a * np.sqrt(np.maximum(x, 0)) + b

def _model_inverse(x, a, b):
    return a / np.maximum(np.abs(x), 1e-300) + b

def _model_logistic(x, L, k, x0, b):
    return L / (1 + _safe_exp(-k * (x - x0))) + b

def _model_gaussian(x, a, mu, sigma):
    return a * np.exp(-0.5 * ((x - mu) / np.maximum(np.abs(sigma), 1e-300))**2)

def _model_lorentzian(x, a, x0, gamma):
    return a * gamma**2 / ((x - x0)**2 + gamma**2)

def _model_sine(x, a, omega, phi, c):
    return a * np.sin(omega * x + phi) + c

def _model_hill(x, vmax, kd, n):
    xp = np.maximum(x, 0)
    return vmax * xp**n / (kd**n + xp**n + 1e-300)

def _model_michaelis_menten(x, vmax, km):
    return vmax * x / (km + x + 1e-300)

def _model_boltzmann(x, a1, a2, x0, dx):
    return (a1 - a2) / (1 + _safe_exp((x - x0) / np.maximum(np.abs(dx), 1e-300))) + a2

def _model_double_exp(x, a1, t1, a2, t2, c):
    return a1 * _safe_exp(-x / np.maximum(np.abs(t1), 1e-300)) + \
           a2 * _safe_exp(-x / np.maximum(np.abs(t2), 1e-300)) + c

def _model_stretched_exp(x, a, tau, beta, c):
    return a * np.exp(-(np.maximum(x, 0) / np.maximum(np.abs(tau), 1e-300))**np.clip(beta, 0.01, 10)) + c

def _model_allometric(x, a, b, c):
    return a * np.power(np.maximum(x, 1e-300), b) + c

def _model_reciprocal_quadratic(x, a, b, c):
    denom = a * x**2 + b * x + c
    return 1.0 / np.where(np.abs(denom) < 1e-300, 1e-300, denom)

def _model_hyperbolic(x, a, b):
    return a * x / (b + x + 1e-300)

def _model_error_function(x, a, b, c, d):
    from scipy.special import erf
    return a * erf(b * (x - c)) + d


def _p0_auto(x, y):
    """Fallback initial guess: amplitude ~ range, offset ~ mean."""
    return [np.nanmax(y) - np.nanmin(y), 1.0, np.nanmean(x), np.nanmean(y)]


MODELS: Dict[str, dict] = {
    "Linear": {
        "func": _model_linear,
        "params": ["a", "b"],
        "eq": "y = {a:.6g}·x + {b:.6g}",
    },
    "Quadratic": {
        "func": _model_quadratic,
        "params": ["a", "b", "c"],
        "eq": "y = {a:.6g}·x² + {b:.6g}·x + {c:.6g}",
    },
    "Cubic": {
        "func": _model_cubic,
        "params": ["a", "b", "c", "d"],
        "eq": "y = {a:.6g}·x³ + {b:.6g}·x² + {c:.6g}·x + {d:.6g}",
    },
    "Polynomial": {
        "func": None,  # built dynamically based on order
        "params": [],
        "eq": "",
        "extra": "order",
    },
    "Exponential": {
        "func": _model_exponential,
        "params": ["a", "b"],
        "eq": "y = {a:.6g}·exp({b:.6g}·x)",
    },
    "Exponential Decay": {
        "func": _model_exp_decay,
        "params": ["a", "b", "c"],
        "eq": "y = {a:.6g}·exp(−{b:.6g}·x) + {c:.6g}",
    },
    "Double Exponential": {
        "func": _model_double_exp,
        "params": ["a1", "t1", "a2", "t2", "c"],
        "eq": "y = {a1:.6g}·exp(−x/{t1:.6g}) + {a2:.6g}·exp(−x/{t2:.6g}) + {c:.6g}",
    },
    "Stretched Exponential": {
        "func": _model_stretched_exp,
        "params": ["a", "tau", "beta", "c"],
        "eq": "y = {a:.6g}·exp(−(x/{tau:.6g})^{beta:.6g}) + {c:.6g}",
    },
    "Logarithmic": {
        "func": _model_logarithmic,
        "params": ["a", "b"],
        "eq": "y = {a:.6g}·ln(x) + {b:.6g}",
    },
    "Power": {
        "func": _model_power,
        "params": ["a", "b"],
        "eq": "y = {a:.6g}·x^{b:.6g}",
    },
    "Allometric (Power + c)": {
        "func": _model_allometric,
        "params": ["a", "b", "c"],
        "eq": "y = {a:.6g}·x^{b:.6g} + {c:.6g}",
    },
    "Square Root": {
        "func": _model_sqrt,
        "params": ["a", "b"],
        "eq": "y = {a:.6g}·√x + {b:.6g}",
    },
    "Inverse (1/x)": {
        "func": _model_inverse,
        "params": ["a", "b"],
        "eq": "y = {a:.6g}/x + {b:.6g}",
    },
    "Hyperbolic (ax/(b+x))": {
        "func": _model_hyperbolic,
        "params": ["a", "b"],
        "eq": "y = {a:.6g}·x / ({b:.6g} + x)",
    },
    "Reciprocal Quadratic": {
        "func": _model_reciprocal_quadratic,
        "params": ["a", "b", "c"],
        "eq": "y = 1 / ({a:.6g}·x² + {b:.6g}·x + {c:.6g})",
    },
    "Logistic (Sigmoid)": {
        "func": _model_logistic,
        "params": ["L", "k", "x0", "b"],
        "eq": "y = {L:.6g} / (1 + exp(−{k:.6g}·(x−{x0:.6g}))) + {b:.6g}",
    },
    "Boltzmann Sigmoid": {
        "func": _model_boltzmann,
        "params": ["a1", "a2", "x0", "dx"],
        "eq": "y = ({a1:.6g}−{a2:.6g}) / (1+exp((x−{x0:.6g})/{dx:.6g})) + {a2:.6g}",
    },
    "Gaussian": {
        "func": _model_gaussian,
        "params": ["a", "mu", "sigma"],
        "eq": "y = {a:.6g}·exp(−0.5·((x−{mu:.6g})/{sigma:.6g})²)",
    },
    "Lorentzian": {
        "func": _model_lorentzian,
        "params": ["a", "x0", "gamma"],
        "eq": "y = {a:.6g}·γ² / ((x−{x0:.6g})² + {gamma:.6g}²)",
    },
    "Sine Wave": {
        "func": _model_sine,
        "params": ["a", "omega", "phi", "c"],
        "eq": "y = {a:.6g}·sin({omega:.6g}·x + {phi:.6g}) + {c:.6g}",
    },
    "Hill Equation": {
        "func": _model_hill,
        "params": ["Vmax", "Kd", "n"],
        "eq": "y = {Vmax:.6g}·x^{n:.6g} / ({Kd:.6g}^{n:.6g} + x^{n:.6g})",
    },
    "Michaelis-Menten": {
        "func": _model_michaelis_menten,
        "params": ["Vmax", "Km"],
        "eq": "y = {Vmax:.6g}·x / ({Km:.6g} + x)",
    },
    "Error Function (erf)": {
        "func": _model_error_function,
        "params": ["a", "b", "c", "d"],
        "eq": "y = {a:.6g}·erf({b:.6g}·(x−{c:.6g})) + {d:.6g}",
    },
}

# Moving average is separate (not curve_fit)
MOVING_AVERAGE_KEY = "Moving Average"


# ── Goodness-of-fit helpers ─────────────────────────────────────────

def _compute_gof(y_data, y_fit, n_params):
    """Return dict of goodness-of-fit statistics."""
    residuals = y_data - y_fit
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((y_data - np.mean(y_data))**2)
    n = len(y_data)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    adj_r2 = (1 - (1 - r_squared) * (n - 1) / (n - n_params - 1)
              if n > n_params + 1 else np.nan)
    rmse = np.sqrt(ss_res / n) if n > 0 else np.nan
    chi2_red = ss_res / (n - n_params) if n > n_params else np.nan
    aic = n * np.log(ss_res / n) + 2 * n_params if n > 0 and ss_res > 0 else np.nan
    bic = (n * np.log(ss_res / n) + n_params * np.log(n)
           if n > 0 and ss_res > 0 else np.nan)
    return {
        "R²": r_squared,
        "Adjusted R²": adj_r2,
        "RMSE": rmse,
        "Reduced χ²": chi2_red,
        "AIC": aic,
        "BIC": bic,
        "SS_res": ss_res,
        "SS_tot": ss_tot,
    }


def _build_poly_func(order):
    """Return (func, params, eq_template) for a polynomial of given order."""
    param_names = [f"a{i}" for i in range(order + 1)]

    def poly(x, *coeffs):
        return np.polyval(coeffs, x)

    terms = []
    for i in range(order + 1):
        exp = order - i
        if exp == 0:
            terms.append("{" + f"a{i}" + ":.6g}")
        elif exp == 1:
            terms.append("{" + f"a{i}" + ":.6g}·x")
        else:
            terms.append("{" + f"a{i}" + f":.6g}}·x^{exp}")
    eq = "y = " + " + ".join(terms)
    return poly, param_names, eq


def _smart_p0(model_name, x, y):
    """Heuristic initial guesses per model."""
    amp = np.nanmax(y) - np.nanmin(y)
    mn_y = np.nanmean(y)
    mn_x = np.nanmean(x)
    std_x = np.nanstd(x) or 1.0
    std_y = np.nanstd(y) or 1.0

    p0_map = {
        "Linear": [std_y / std_x, mn_y],
        "Quadratic": [0.0, std_y / std_x, mn_y],
        "Cubic": [0.0, 0.0, std_y / std_x, mn_y],
        "Exponential": [mn_y or 1.0, 0.01],
        "Exponential Decay": [amp, 1.0 / std_x, np.nanmin(y)],
        "Double Exponential": [amp / 2, std_x, amp / 2, std_x * 2, np.nanmin(y)],
        "Stretched Exponential": [amp, std_x, 1.0, np.nanmin(y)],
        "Logarithmic": [std_y, mn_y],
        "Power": [1.0, 1.0],
        "Allometric (Power + c)": [1.0, 1.0, 0.0],
        "Square Root": [std_y, mn_y],
        "Inverse (1/x)": [std_y * mn_x, mn_y],
        "Hyperbolic (ax/(b+x))": [np.nanmax(y) or 1.0, mn_x or 1.0],
        "Reciprocal Quadratic": [1.0, 0.0, 1.0],
        "Logistic (Sigmoid)": [amp, 1.0 / std_x, mn_x, np.nanmin(y)],
        "Boltzmann Sigmoid": [np.nanmax(y), np.nanmin(y), mn_x, std_x],
        "Gaussian": [amp, mn_x, std_x],
        "Lorentzian": [amp, mn_x, std_x],
        "Sine Wave": [amp / 2, 2 * np.pi / (std_x * 4), 0, mn_y],
        "Hill Equation": [np.nanmax(y) or 1.0, mn_x or 1.0, 1.0],
        "Michaelis-Menten": [np.nanmax(y) or 1.0, mn_x or 1.0],
        "Error Function (erf)": [amp / 2, 1.0 / std_x, mn_x, mn_y],
    }
    return p0_map.get(model_name, [1.0] * len(MODELS.get(model_name, {}).get("params", [])))


def fit_series(x, y, model_name: str, poly_order: int = 4,
               ma_period: int = 2) -> dict:
    """Fit one model to (x, y) and report the result.

    Free of Qt and of the chart, so the same fit can be run from the
    Trendline dialog, a script, or the AI / MCP tool layer.  Returns a
    dict with *params*, *errors*, *gof*, *equation* and a callable
    *predict*; on failure the dict carries only *error*.
    """
    from scipy.optimize import curve_fit

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if len(x) < 2:
        return {"error": "Not enough data points (need at least 2)."}

    # Tool callers write "polynomial" or "linear"; match case-blind.
    known = [MOVING_AVERAGE_KEY, "Polynomial", *MODELS]
    model_name = next((k for k in known
                       if k.lower() == str(model_name).lower()), model_name)

    if model_name == MOVING_AVERAGE_KEY:
        if ma_period > len(y):
            return {"error": f"Period {ma_period} is larger than the "
                             f"data length ({len(y)})."}
        kernel = np.ones(ma_period) / ma_period
        y_ma = np.convolve(y, kernel, mode="valid")
        x_ma = x[ma_period - 1:]
        y_fit = np.interp(x, x_ma, y_ma)
        return {"model": model_name, "params": {"period": ma_period},
                "errors": {}, "gof": _compute_gof(y, y_fit, ma_period),
                "equation": f"Moving Average (period={ma_period})",
                "predict": lambda xs: np.interp(xs, x_ma, y_ma)}

    if model_name == "Polynomial":
        if poly_order >= len(x):
            return {"error": f"Polynomial order {poly_order} needs at "
                             f"least {poly_order + 1} points "
                             f"(have {len(x)})."}
        coeffs = np.polyfit(x, y, poly_order)
        _, names, eq_template = _build_poly_func(poly_order)
        params = dict(zip(names, (float(c) for c in coeffs)))
        return {"model": f"Polynomial (order {poly_order})",
                "params": params, "errors": {},
                "gof": _compute_gof(y, np.polyval(coeffs, x),
                                    poly_order + 1),
                "equation": eq_template.format(**params),
                "predict": lambda xs: np.polyval(coeffs, xs)}

    model = MODELS.get(model_name)
    if model is None:
        return {"error": f"Unknown model {model_name!r}."}
    func = model["func"]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            popt, pcov = curve_fit(
                func, x, y, p0=_smart_p0(model_name, x, y), maxfev=50000)
        perr = np.sqrt(np.diag(pcov))
    except Exception as exc:
        return {"error": f"Fit failed for {model_name}: {exc}"}

    names = model["params"]
    params = dict(zip(names, (float(v) for v in popt)))
    return {"model": model_name, "params": params,
            "errors": dict(zip(names, (float(e) for e in perr))),
            "gof": _compute_gof(y, func(x, *popt), len(popt)),
            "equation": model["eq"].format(**params),
            "predict": lambda xs: func(xs, *popt)}


# ── Trendline data class ────────────────────────────────────────────

class TrendlineInfo:
    """Stores everything needed to recreate a trendline.

    Trendlines are added as regular chart series (flagged with
    ``is_trendline=True``) so they appear in Plot Details and can
    be removed from there.
    """

    def __init__(self):
        self.series_idx: int = 0       # source series being fitted
        self.model_name: str = "Linear"
        self.poly_order: int = 4
        self.ma_period: int = 2
        self.params: dict = {}         # fitted parameter values
        self.equation: str = ""
        self.gof: dict = {}
        self.eq_artist = None          # text annotation on chart
        self.r2_artist = None          # text annotation on chart
        self.show_equation: bool = False
        self.show_r_squared: bool = False
        self.color: str = "#ff0000"
        self.linestyle: str = "--"
        self.linewidth: float = 1.5
        self.fit_series_idx: int = -1  # index in chart._series

    def to_dict(self):
        d = {
            "series_idx": self.series_idx,
            "model_name": self.model_name,
            "params": self.params,
            "equation": self.equation,
            "gof": {k: (v if np.isfinite(v) else None)
                    for k, v in self.gof.items()},
            "show_equation": self.show_equation,
            "show_r_squared": self.show_r_squared,
            "color": self.color,
            "linestyle": self.linestyle,
            "linewidth": self.linewidth,
        }
        if self.model_name == "Polynomial":
            d["poly_order"] = self.poly_order
        if self.model_name == MOVING_AVERAGE_KEY:
            d["ma_period"] = self.ma_period
        return d

    @classmethod
    def from_dict(cls, d):
        t = cls()
        t.series_idx = d.get("series_idx", 0)
        t.model_name = d.get("model_name", "Linear")
        t.poly_order = d.get("poly_order", 4)
        t.ma_period = d.get("ma_period", 2)
        t.params = d.get("params", {})
        t.equation = d.get("equation", "")
        t.gof = {k: (v if v is not None else np.nan)
                 for k, v in d.get("gof", {}).items()}
        t.show_equation = d.get("show_equation", False)
        t.show_r_squared = d.get("show_r_squared", False)
        t.color = d.get("color", "#ff0000")
        t.linestyle = d.get("linestyle", "--")
        t.linewidth = d.get("linewidth", 1.5)
        return t


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

    # Tool callers write "polynomial" or "linear"; match case-blind.
    known = [MOVING_AVERAGE_KEY, "Polynomial", *MODELS]
    model_name = next((k for k in known
                       if k.lower() == str(model_name).lower()), model_name)

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
