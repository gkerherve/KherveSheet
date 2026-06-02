"""Science — additional data-analysis tool dialogs (wave 2).

Baseline subtraction, crop, band-pass filter, calibration, resampling,
cross-correlation, signal-to-noise, Hilbert envelope, Kramers-Kronig
transform, and deconvolution.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import numpy as np

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QLabel, QMessageBox, QSpinBox, QWidget,
)

from .science import ScienceToolDialog
from .solver import _PickLineEdit


# ── Baseline subtraction ───────────────────────────────────────────────

_BL_METHODS = [
    "Polynomial",
    "Linear",
    "ALS (Asymmetric Least Squares)",
    "SNIP (Peak Clipping)",
    "Rubberband (Convex Hull)",
    "Rolling Ball",
    "LOWESS",
    "Median Filter",
    "Shirley (XPS)",
    "Tougaard (XPS)",
    "Spline",
]

# Which parameter widgets each method needs (index into _BL_METHODS).
_NEED_DEGREE   = {0}                  # Polynomial
_NEED_LAM_P    = {2}                  # ALS
_NEED_ITERS    = {3}                  # SNIP
_NEED_RADIUS   = {5}                  # Rolling Ball
_NEED_WINDOW   = {7}                  # Median Filter
_NEED_FRACTION = {6}                  # LOWESS
_NEED_SMOOTH   = {10}                 # Spline
_NEED_REVERSE  = {8, 9}              # Shirley, Tougaard
_NEED_TOUG     = {9}                  # Tougaard B, C params


class BaselineDialog(ScienceToolDialog):
    TITLE = "Baseline Subtraction"

    def _build_options(self, form: QFormLayout):
        self._method = QComboBox()
        self._method.addItems(_BL_METHODS)
        form.addRow("Method:", self._method)

        # ── Polynomial degree ───────────────────────────────────────
        self._deg_label = QLabel("Degree:")
        self._degree = QSpinBox()
        self._degree.setRange(1, 10)
        self._degree.setValue(3)
        form.addRow(self._deg_label, self._degree)

        # ── ALS: lambda + asymmetry ─────────────────────────────────
        self._lam_label = QLabel("Lambda:")
        self._lam = QDoubleSpinBox()
        self._lam.setRange(1e2, 1e10)
        self._lam.setValue(1e6)
        self._lam.setDecimals(0)
        form.addRow(self._lam_label, self._lam)

        self._p_label = QLabel("Asymmetry p:")
        self._p = QDoubleSpinBox()
        self._p.setRange(0.001, 0.5)
        self._p.setValue(0.01)
        self._p.setDecimals(3)
        self._p.setSingleStep(0.001)
        form.addRow(self._p_label, self._p)

        # ── SNIP iterations ─────────────────────────────────────────
        self._iter_label = QLabel("Iterations:")
        self._iters = QSpinBox()
        self._iters.setRange(1, 500)
        self._iters.setValue(40)
        form.addRow(self._iter_label, self._iters)

        # ── Rolling Ball radius ─────────────────────────────────────
        self._rad_label = QLabel("Radius (pts):")
        self._radius = QSpinBox()
        self._radius.setRange(1, 10_000)
        self._radius.setValue(50)
        form.addRow(self._rad_label, self._radius)

        # ── Median filter window ────────────────────────────────────
        self._win_label = QLabel("Window (pts):")
        self._window = QSpinBox()
        self._window.setRange(3, 10_001)
        self._window.setValue(51)
        self._window.setSingleStep(2)
        form.addRow(self._win_label, self._window)

        # ── LOWESS fraction ─────────────────────────────────────────
        self._frac_label = QLabel("Fraction:")
        self._fraction = QDoubleSpinBox()
        self._fraction.setRange(0.01, 1.0)
        self._fraction.setValue(0.1)
        self._fraction.setDecimals(3)
        self._fraction.setSingleStep(0.01)
        form.addRow(self._frac_label, self._fraction)

        # ── Spline smoothing factor ─────────────────────────────────
        self._smo_label = QLabel("Smoothing:")
        self._smooth = QDoubleSpinBox()
        self._smooth.setRange(0.0, 1e15)
        self._smooth.setValue(0.0)
        self._smooth.setDecimals(2)
        self._smooth.setSpecialValueText("auto")
        form.addRow(self._smo_label, self._smooth)

        # ── Shirley / Tougaard: reverse flag ────────────────────────
        self._reverse = QCheckBox("Reverse (inelastic tail at low x)")
        self._rev_label = QLabel("")          # spacer label for form row
        form.addRow(self._rev_label, self._reverse)

        # ── Tougaard B, C parameters ───────────────────────────────
        self._tB_label = QLabel("B:")
        self._tB = QDoubleSpinBox()
        self._tB.setRange(0, 1e12)
        self._tB.setValue(2866.0)
        self._tB.setDecimals(1)
        form.addRow(self._tB_label, self._tB)

        self._tC_label = QLabel("C (eV\u00b2):")
        self._tC = QDoubleSpinBox()
        self._tC.setRange(0.01, 1e12)
        self._tC.setValue(1643.0)
        self._tC.setDecimals(1)
        form.addRow(self._tC_label, self._tC)

        # ── Collect widget groups for toggling ──────────────────────
        self._groups = {
            "degree":   (self._deg_label, self._degree),
            "lam_p":    (self._lam_label, self._lam,
                         self._p_label, self._p),
            "iters":    (self._iter_label, self._iters),
            "radius":   (self._rad_label, self._radius),
            "window":   (self._win_label, self._window),
            "fraction": (self._frac_label, self._fraction),
            "smooth":   (self._smo_label, self._smooth),
            "reverse":  (self._rev_label, self._reverse),
            "tougaard": (self._tB_label, self._tB,
                         self._tC_label, self._tC),
        }

        self._method.currentIndexChanged.connect(self._toggle_method)
        self._toggle_method(0)

    # ── Visibility ──────────────────────────────────────────────────

    def _toggle_method(self, idx):
        _show = {
            "degree":   idx in _NEED_DEGREE,
            "lam_p":    idx in _NEED_LAM_P,
            "iters":    idx in _NEED_ITERS,
            "radius":   idx in _NEED_RADIUS,
            "window":   idx in _NEED_WINDOW,
            "fraction": idx in _NEED_FRACTION,
            "smooth":   idx in _NEED_SMOOTH,
            "reverse":  idx in _NEED_REVERSE,
            "tougaard": idx in _NEED_TOUG,
        }
        for key, widgets in self._groups.items():
            vis = _show[key]
            for w in widgets:
                w.setVisible(vis)

    # ── Compute ─────────────────────────────────────────────────────

    def _compute(self, x, y):                        # noqa: C901
        idx = self._method.currentIndex()

        if idx == 0:                                 # Polynomial
            c = np.polyfit(x, y, self._degree.value())
            baseline = np.polyval(c, x)

        elif idx == 1:                               # Linear
            c = np.polyfit(x, y, 1)
            baseline = np.polyval(c, x)

        elif idx == 2:                               # ALS
            from .fit_models import als_background
            baseline = als_background(
                x, y, lam=self._lam.value(), p=self._p.value())

        elif idx == 3:                               # SNIP
            baseline = self._snip(y, self._iters.value())

        elif idx == 4:                               # Rubberband
            baseline = self._rubberband(x, y)

        elif idx == 5:                               # Rolling Ball
            baseline = self._rolling_ball(y, self._radius.value())

        elif idx == 6:                               # LOWESS
            baseline = self._lowess(x, y, self._fraction.value())

        elif idx == 7:                               # Median Filter
            win = self._window.value()
            if win % 2 == 0:
                win += 1
            from scipy.ndimage import median_filter
            baseline = median_filter(y, size=win).astype(float)

        elif idx == 8:                               # Shirley
            from .fit_models import shirley_background
            baseline = shirley_background(
                x, y, reverse=self._reverse.isChecked())

        elif idx == 9:                               # Tougaard
            baseline = self._tougaard(
                x, y,
                B=self._tB.value(), C=self._tC.value(),
                reverse=self._reverse.isChecked())

        else:                                        # Spline
            baseline = self._spline(x, y, self._smooth.value())

        return [("baseline", baseline), ("subtracted", y - baseline)]

    # ── Algorithm helpers ───────────────────────────────────────────

    @staticmethod
    def _snip(y, n_iter):
        """SNIP (Statistics-sensitive Non-linear Iterative Peak-clipping).

        Operates in LLS (Log-Log-Square-root) space so that the clipping
        adapts to Poisson-like counting statistics (Ryan et al. 1988).
        """
        v = np.log(np.log(np.sqrt(np.clip(y, 1, None) + 1) + 1) + 1)
        for p in range(1, n_iter + 1):
            rolled = np.minimum(
                np.roll(v, p, axis=0), np.roll(v, -p, axis=0))
            # Fix boundary artefacts.
            rolled[:p] = v[:p]
            rolled[-p:] = v[-p:]
            v = np.minimum(v, (rolled + v) / 2.0)
        # Invert LLS transform.
        baseline = (np.exp(np.exp(v) - 1) - 1) ** 2 - 1
        return np.clip(baseline, 0, None)

    @staticmethod
    def _rubberband(x, y):
        """Convex-hull (rubberband) baseline — lower hull only."""
        from scipy.spatial import ConvexHull
        pts = np.column_stack((x, y))
        hull = ConvexHull(pts)
        # Select vertices on the *lower* hull (connecting leftmost to
        # rightmost along the bottom).
        verts = hull.vertices
        verts = verts[np.argsort(x[verts])]
        # Walk from left to right keeping only vertices whose y is below
        # or equal to the line connecting the endpoints.
        x_lo, x_hi = x.min(), x.max()
        y_lo = y[np.argmin(np.abs(x - x_lo))]
        y_hi = y[np.argmin(np.abs(x - x_hi))]
        lower = []
        for v in verts:
            # Below the straight line between first and last data point.
            frac = (x[v] - x_lo) / (x_hi - x_lo) if x_hi != x_lo else 0.5
            y_line = y_lo + frac * (y_hi - y_lo)
            if y[v] <= y_line or v == verts[0] or v == verts[-1]:
                lower.append(v)
        if len(lower) < 2:
            lower = [verts[0], verts[-1]]
        lower = np.array(lower)
        baseline = np.interp(x, x[lower], y[lower])
        return baseline

    @staticmethod
    def _rolling_ball(y, radius):
        """Rolling-ball baseline via morphological erosion + dilation."""
        from scipy.ndimage import minimum_filter1d, maximum_filter1d
        size = 2 * radius + 1
        eroded = minimum_filter1d(y, size=size)
        baseline = maximum_filter1d(eroded, size=size)
        return baseline.astype(float)

    @staticmethod
    def _lowess(x, y, frac):
        """LOWESS (locally weighted scatterplot smoothing) baseline."""
        try:
            from statsmodels.nonparametric.smoothers_lowess import lowess
            result = lowess(y, x, frac=frac, return_sorted=False)
            return result
        except ImportError:
            # Fallback: Savitzky-Golay with equivalent window.
            from scipy.signal import savgol_filter
            win = max(3, int(frac * len(y)) | 1)
            win = min(win, len(y) if len(y) % 2 else len(y) - 1)
            return savgol_filter(y, win, min(2, win - 1))

    @staticmethod
    def _tougaard(x, y, B=2866.0, C=1643.0, reverse=False,
                  max_iter=30, tol=1e-6):
        """Two-parameter universal Tougaard background.

        K(T) = B·T / (C + T²)²  is the universal inelastic cross-section.
        The background at energy E is the integral of K(E'-E)·J(E') over
        the inelastic-loss region, iterated until convergence.
        """
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        n = len(y)
        if n < 2:
            return np.zeros_like(y)
        order = np.argsort(x)
        xs, ys = x[order], y[order]
        if reverse:
            xs, ys = xs[::-1], ys[::-1]
        dx = np.abs(np.diff(xs))
        dx = np.append(dx, dx[-1])
        bg = np.zeros(n)
        j = ys.copy()
        for _ in range(max_iter):
            old_bg = bg.copy()
            for i in range(n):
                T = xs[i + 1:] - xs[i] if not reverse else xs[i] - xs[i + 1:]
                T = np.abs(T)
                mask = T > 0
                if not mask.any():
                    continue
                K = B * T[mask] / (C + T[mask] ** 2) ** 2
                bg[i] = np.sum(K * j[i + 1:][mask] * dx[i + 1:][mask])
            j = ys - bg
            if np.max(np.abs(bg - old_bg)) < tol * (np.max(np.abs(bg)) + 1e-12):
                break
        if reverse:
            bg = bg[::-1]
        out = np.empty(n)
        out[order] = bg
        return out

    @staticmethod
    def _spline(x, y, smooth):
        """Smoothing spline baseline."""
        from scipy.interpolate import UnivariateSpline
        s = None if smooth == 0.0 else smooth
        spl = UnivariateSpline(x, y, s=s)
        return spl(x)


# ── Crop ────────────────────────────────────────────────────────────────

class CropDialog(ScienceToolDialog):
    TITLE = "Crop"
    EMIT_X = True

    def _build_options(self, form: QFormLayout):
        self._x_min = QDoubleSpinBox()
        self._x_min.setRange(-1e15, 1e15)
        self._x_min.setDecimals(6)
        self._x_max = QDoubleSpinBox()
        self._x_max.setRange(-1e15, 1e15)
        self._x_max.setDecimals(6)
        form.addRow("X min:", self._x_min)
        form.addRow("X max:", self._x_max)

    def _compute(self, x, y):
        mask = (x >= self._x_min.value()) & (x <= self._x_max.value())
        xc, yc = x[mask], y[mask]
        if xc.size == 0:
            raise ValueError("No data points in the selected range.")
        return [("x_crop", xc), ("y_crop", yc)]


# ── Band-pass filter ───────────────────────────────────────────────────

class BandpassFilterDialog(ScienceToolDialog):
    TITLE = "Band-pass Filter"

    def _build_options(self, form: QFormLayout):
        self._ftype = QComboBox()
        self._ftype.addItems(["Band-pass", "Low-pass",
                              "High-pass", "Band-stop (Notch)"])
        form.addRow("Type:", self._ftype)

        self._lo_label = QLabel("Low cutoff:")
        self._lo = QDoubleSpinBox()
        self._lo.setRange(0, 1e12)
        self._lo.setValue(0.1)
        self._lo.setDecimals(6)
        form.addRow(self._lo_label, self._lo)

        self._hi_label = QLabel("High cutoff:")
        self._hi = QDoubleSpinBox()
        self._hi.setRange(0, 1e12)
        self._hi.setValue(10.0)
        self._hi.setDecimals(6)
        form.addRow(self._hi_label, self._hi)

        self._order = QSpinBox()
        self._order.setRange(1, 10)
        self._order.setValue(4)
        form.addRow("Order:", self._order)

        self._ftype.currentIndexChanged.connect(self._toggle_cutoffs)
        self._toggle_cutoffs(0)

    def _toggle_cutoffs(self, idx):
        # 0=band-pass  1=low-pass  2=high-pass  3=band-stop
        show_lo = idx in (0, 2, 3)
        show_hi = idx in (0, 1, 3)
        self._lo.setVisible(show_lo)
        self._lo_label.setVisible(show_lo)
        self._hi.setVisible(show_hi)
        self._hi_label.setVisible(show_hi)

    def _compute(self, x, y):
        from scipy.signal import butter, sosfilt
        dt = abs(float(np.mean(np.diff(x))))
        if dt == 0:
            raise ValueError("X spacing is zero — cannot compute sample rate.")
        fs = 1.0 / dt
        nyq = fs / 2.0
        order = self._order.value()
        idx = self._ftype.currentIndex()
        if idx == 0:
            sos = butter(order, [self._lo.value() / nyq,
                                 self._hi.value() / nyq],
                         btype="band", output="sos")
        elif idx == 1:
            sos = butter(order, self._hi.value() / nyq,
                         btype="low", output="sos")
        elif idx == 2:
            sos = butter(order, self._lo.value() / nyq,
                         btype="high", output="sos")
        else:
            sos = butter(order, [self._lo.value() / nyq,
                                 self._hi.value() / nyq],
                         btype="bandstop", output="sos")
        return [("filtered", sosfilt(sos, y))]


# ── Calibration ─────────────────────────────────────────────────────────

class CalibrationDialog(ScienceToolDialog):
    TITLE = "Calibration"
    EMIT_X = True

    def _build_options(self, form: QFormLayout):
        for attr, label, default in [
            ("_x_shift", "X shift:", 0.0),
            ("_x_scale", "X scale:", 1.0),
            ("_y_offset", "Y offset:", 0.0),
            ("_y_scale", "Y scale:", 1.0),
        ]:
            sb = QDoubleSpinBox()
            sb.setRange(-1e12, 1e12)
            sb.setDecimals(6)
            sb.setValue(default)
            setattr(self, attr, sb)
            form.addRow(label, sb)

    def _compute(self, x, y):
        x_new = x * self._x_scale.value() + self._x_shift.value()
        y_new = y * self._y_scale.value() + self._y_offset.value()
        return [("x_cal", x_new), ("y_cal", y_new)]


# ── Resampling ──────────────────────────────────────────────────────────

class ResampleDialog(ScienceToolDialog):
    TITLE = "Resampling"
    EMIT_X = True

    def _build_options(self, form: QFormLayout):
        self._npts = QSpinBox()
        self._npts.setRange(2, 1_000_000)
        self._npts.setValue(200)
        self._method = QComboBox()
        self._method.addItems(["linear", "cubic", "nearest"])
        form.addRow("Points:", self._npts)
        form.addRow("Method:", self._method)

    def _compute(self, x, y):
        from scipy.interpolate import interp1d
        f = interp1d(x, y, kind=self._method.currentText())
        xn = np.linspace(x.min(), x.max(), self._npts.value())
        return [("x_resamp", xn), ("y_resamp", f(xn))]


# ── Cross-correlation ───────────────────────────────────────────────────

class CrossCorrelationDialog(ScienceToolDialog):
    TITLE = "Cross-Correlation"
    EMIT_X = True

    def _build_options(self, form: QFormLayout):
        self._y2 = _PickLineEdit(self)
        self._y2.setPlaceholderText("Y2 range, e.g. $C$2:$C$500")
        form.addRow("Y2:", self._y2)

    def _on_apply(self):
        xy = self._read_xy()
        if xy is None:
            return
        x, y1 = xy
        y2 = self._values(self._y2.text())
        if y2.size == 0:
            QMessageBox.warning(self, self.TITLE, "Select a Y2 range.")
            return
        n = min(len(y1), len(y2))
        y1, y2, x = y1[:n], y2[:n], x[:n]
        mask = np.isfinite(y1) & np.isfinite(y2)
        y1, y2, x = y1[mask], y2[mask], x[mask]
        n = len(y1)
        if n < 2:
            QMessageBox.warning(self, self.TITLE,
                                "Need at least 2 finite points.")
            return
        s1, s2 = y1.std(), y2.std()
        if s1 == 0 or s2 == 0:
            QMessageBox.warning(self, self.TITLE,
                                "Constant signal — cannot normalise.")
            return
        a = (y1 - y1.mean()) / s1
        b = (y2 - y2.mean()) / s2
        corr = np.correlate(a, b, mode="full") / n
        dx = float(np.mean(np.diff(x))) if n > 1 else 1.0
        lags = np.arange(-(n - 1), n) * dx
        try:
            self._write_columns([("lag", lags), ("correlation", corr)])
        except Exception as exc:
            QMessageBox.critical(self, self.TITLE,
                                 f"Computation failed:\n{exc}")


# ── Signal-to-noise ratio ──────────────────────────────────────────────

class SNRDialog(ScienceToolDialog):
    TITLE = "Signal-to-Noise Ratio"

    def _build_options(self, form: QFormLayout):
        self._method = QComboBox()
        self._method.addItems(["RMS", "Peak-to-Peak", "Standard deviation"])
        form.addRow("Method:", self._method)
        self._sig_lo = QDoubleSpinBox()
        self._sig_hi = QDoubleSpinBox()
        self._noi_lo = QDoubleSpinBox()
        self._noi_hi = QDoubleSpinBox()
        for sb in (self._sig_lo, self._sig_hi,
                   self._noi_lo, self._noi_hi):
            sb.setRange(-1e15, 1e15)
            sb.setDecimals(6)
        form.addRow("Signal x-min:", self._sig_lo)
        form.addRow("Signal x-max:", self._sig_hi)
        form.addRow("Noise x-min:", self._noi_lo)
        form.addRow("Noise x-max:", self._noi_hi)

    def _compute(self, x, y):
        y_sig = y[(x >= self._sig_lo.value()) & (x <= self._sig_hi.value())]
        y_noi = y[(x >= self._noi_lo.value()) & (x <= self._noi_hi.value())]
        if y_sig.size == 0 or y_noi.size == 0:
            raise ValueError("Signal or noise region is empty.")
        method = self._method.currentText()
        if method == "RMS":
            s = np.sqrt(np.mean(y_sig ** 2))
            n = np.sqrt(np.mean(y_noi ** 2))
        elif method == "Peak-to-Peak":
            s, n = np.ptp(y_sig), np.ptp(y_noi)
        else:
            s, n = np.std(y_sig), np.std(y_noi)
        if n == 0:
            raise ValueError("Noise measure is zero — cannot compute SNR.")
        snr = 20 * np.log10(s / n)
        QMessageBox.information(self, self.TITLE,
                                f"SNR = {snr:.4f} dB  ({method})")
        return [("SNR_dB", np.array([snr]))]


# ── Hilbert envelope ───────────────────────────────────────────────────

class EnvelopeDialog(ScienceToolDialog):
    TITLE = "Envelope"

    def _build_options(self, form: QFormLayout):
        self._output = QComboBox()
        self._output.addItems([
            "Amplitude envelope",
            "Instantaneous phase",
            "Instantaneous frequency",
            "Analytic signal (real)",
            "Analytic signal (imag)",
        ])
        form.addRow("Output:", self._output)

    def _compute(self, x, y):
        from scipy.signal import hilbert
        analytic = hilbert(y)
        choice = self._output.currentText()
        if choice == "Amplitude envelope":
            return [("envelope", np.abs(analytic))]
        if choice == "Instantaneous phase":
            return [("phase", np.unwrap(np.angle(analytic)))]
        if choice == "Instantaneous frequency":
            phase = np.unwrap(np.angle(analytic))
            dx = float(np.mean(np.diff(x))) if x.size > 1 else 1.0
            freq = np.gradient(phase, dx) / (2.0 * np.pi)
            return [("inst_freq", freq)]
        if choice == "Analytic signal (real)":
            return [("analytic_re", analytic.real)]
        return [("analytic_im", analytic.imag)]


# ── Kramers-Kronig ─────────────────────────────────────────────────────

class KramersKronigDialog(ScienceToolDialog):
    TITLE = "Kramers-Kronig"

    def _build_options(self, form: QFormLayout):
        self._direction = QComboBox()
        self._direction.addItems([
            "Real \u2192 Imaginary (KK1)",
            "Imaginary \u2192 Real (KK2)",
        ])
        form.addRow("Direction:", self._direction)

    def _compute(self, x, y):
        from scipy.signal import hilbert as _hilbert
        analytic = _hilbert(y)
        if self._direction.currentIndex() == 0:
            return [("KK_imag", -analytic.imag)]
        return [("KK_real", analytic.real)]


# ── Deconvolution ───────────────────────────────────────────────────────

class DeconvolutionDialog(ScienceToolDialog):
    TITLE = "Deconvolution"

    def _build_options(self, form: QFormLayout):
        self._method = QComboBox()
        self._method.addItems(["Wiener", "Richardson-Lucy"])
        form.addRow("Method:", self._method)

        self._sigma = QDoubleSpinBox()
        self._sigma.setRange(0.1, 100.0)
        self._sigma.setValue(3.0)
        self._sigma.setDecimals(2)
        form.addRow("Kernel \u03c3 (pts):", self._sigma)

        self._snr_label = QLabel("SNR estimate:")
        self._snr = QDoubleSpinBox()
        self._snr.setRange(0.001, 1000.0)
        self._snr.setValue(10.0)
        self._snr.setDecimals(3)
        form.addRow(self._snr_label, self._snr)

        self._iter_label = QLabel("Iterations:")
        self._iters = QSpinBox()
        self._iters.setRange(1, 500)
        self._iters.setValue(30)
        form.addRow(self._iter_label, self._iters)

        self._method.currentIndexChanged.connect(self._toggle_params)
        self._toggle_params(0)

    def _toggle_params(self, _idx=0):
        wiener = self._method.currentIndex() == 0
        self._snr.setVisible(wiener)
        self._snr_label.setVisible(wiener)
        self._iters.setVisible(not wiener)
        self._iter_label.setVisible(not wiener)

    def _compute(self, x, y):
        sigma = self._sigma.value()
        hw = int(np.ceil(4 * sigma))
        t = np.arange(-hw, hw + 1, dtype=float)
        kernel = np.exp(-0.5 * (t / sigma) ** 2)
        kernel /= kernel.sum()

        if self._method.currentIndex() == 0:
            n = len(y)
            H = np.fft.fft(kernel, n)
            G = np.fft.fft(y, n)
            snr_val = self._snr.value()
            result = np.fft.ifft(
                G * np.conj(H) / (np.abs(H) ** 2 + 1.0 / snr_val)
            ).real
        else:
            from scipy.signal import fftconvolve
            estimate = y.copy().astype(float)
            kernel_flip = kernel[::-1]
            for _ in range(self._iters.value()):
                conv = fftconvolve(estimate, kernel, mode="same")
                conv[conv == 0] = 1e-30
                estimate *= fftconvolve(y / conv, kernel_flip, mode="same")
            result = estimate
        return [("deconv", result)]


#: Extra tools to append to the Science menu.
EXTRA_TOOLS = [
    ("Baseline Subtraction\u2026", BaselineDialog),
    ("Crop\u2026",                 CropDialog),
    ("Band-pass Filter\u2026",    BandpassFilterDialog),
    ("Calibration\u2026",         CalibrationDialog),
    ("Resampling\u2026",          ResampleDialog),
    ("Cross-Correlation\u2026",   CrossCorrelationDialog),
    ("Signal-to-Noise\u2026",     SNRDialog),
    ("Envelope\u2026",            EnvelopeDialog),
    ("Kramers-Kronig\u2026",      KramersKronigDialog),
    ("Deconvolution\u2026",       DeconvolutionDialog),
]
