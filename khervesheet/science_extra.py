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

from PyQt5.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QLabel, QMessageBox, QSpinBox, QWidget,
)

from .science import ScienceToolDialog
from .solver import _PickLineEdit


# ── Baseline subtraction ───────────────────────────────────────────────

class BaselineDialog(ScienceToolDialog):
    TITLE = "Baseline Subtraction"

    def _build_options(self, form: QFormLayout):
        self._method = QComboBox()
        self._method.addItems(["Polynomial",
                               "ALS (Asymmetric Least Squares)"])
        form.addRow("Method:", self._method)

        # Polynomial options
        self._deg_label = QLabel("Degree:")
        self._degree = QSpinBox()
        self._degree.setRange(1, 10)
        self._degree.setValue(3)
        form.addRow(self._deg_label, self._degree)

        # ALS options
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

        self._method.currentIndexChanged.connect(self._toggle_method)
        self._toggle_method(0)

    def _toggle_method(self, idx):
        poly = idx == 0
        self._degree.setVisible(poly)
        self._deg_label.setVisible(poly)
        self._lam.setVisible(not poly)
        self._lam_label.setVisible(not poly)
        self._p.setVisible(not poly)
        self._p_label.setVisible(not poly)

    def _compute(self, x, y):
        if self._method.currentIndex() == 0:
            coeffs = np.polyfit(x, y, self._degree.value())
            baseline = np.polyval(coeffs, x)
        else:
            from scipy import sparse
            n = len(y)
            D = sparse.diags([1, -2, 1], [0, 1, 2], shape=(n - 2, n))
            lam = self._lam.value()
            p = self._p.value()
            w = np.ones(n)
            for _ in range(15):
                W = sparse.diags(w)
                Z = W + lam * D.T.dot(D)
                baseline = sparse.linalg.spsolve(Z, w * y)
                w = np.where(y > baseline, p, 1 - p)
        return [("baseline", baseline), ("subtracted", y - baseline)]


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
