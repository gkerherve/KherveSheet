"""Model library for the Curve Fitting tool.

Peak / curve functions and background models commonly used across XRD,
XPS, Raman, FTIR, TGA, BET and AFM analysis.  Each peak model is
parameterised in spreadsheet-friendly terms — peak ``height``,
``center`` and full-width-at-half-maximum (``fwhm``) plus an optional
shape parameter — so the Curve Fitting dialog can present an intuitive
parameter table and assemble an lmfit composite model.

Backgrounds come in two flavours:

* *Analytic* (constant, linear, polynomial): their coefficients are
  fitted simultaneously with the peaks as ordinary lmfit parameters.
* *Data-derived* (Shirley, Tougaard): they depend on the spectrum
  itself, so they are pre-computed from the data, subtracted, and the
  peaks are fitted to the remainder.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from typing import Callable, Dict, List

import numpy as np

# ── Numerical helpers ───────────────────────────────────────────────

_SQRT_2PI = np.sqrt(2.0 * np.pi)
_FWHM_SIGMA = 2.0 * np.sqrt(2.0 * np.log(2.0))  # FWHM = sigma * this


def _safe(v, lo=1e-12):
    """Clamp a width to a tiny positive value to avoid divide-by-zero."""
    return np.maximum(v, lo) if isinstance(v, np.ndarray) else max(v, lo)


# ── Peak / curve functions (height-normalised) ──────────────────────
#
# Every function peaks at ``height`` at ``center`` (except the step /
# decay shapes, where ``height`` is the plateau / initial amplitude).
# lmfit introspects the argument names, so they double as parameter
# names in the fit.

def gaussian(x, height, center, fwhm):
    sigma = _safe(fwhm) / _FWHM_SIGMA
    return height * np.exp(-((x - center) ** 2) / (2.0 * sigma ** 2))


def lorentzian(x, height, center, fwhm):
    gamma = _safe(fwhm) / 2.0
    return height * gamma ** 2 / ((x - center) ** 2 + gamma ** 2)


def pseudo_voigt(x, height, center, fwhm, fraction):
    """Linear mix of Lorentzian (fraction) and Gaussian (1-fraction)."""
    f = min(max(fraction, 0.0), 1.0)
    return f * lorentzian(x, height, center, fwhm) \
        + (1.0 - f) * gaussian(x, height, center, fwhm)


def voigt(x, height, center, sigma, gamma):
    """True Voigt (Gaussian⊗Lorentzian), normalised to *height* at peak."""
    from scipy.special import wofz
    sigma = _safe(sigma)
    z0 = (1j * gamma) / (sigma * np.sqrt(2.0))
    norm = np.real(wofz(z0))  # value at the centre, to rescale to height
    z = ((x - center) + 1j * gamma) / (sigma * np.sqrt(2.0))
    val = np.real(wofz(z))
    return height * val / (norm if norm != 0 else 1.0)


def asym_lorentzian(x, height, center, fwhm, asym):
    """Split Lorentzian: independent half-widths either side of centre.

    *asym* > 0 widens the high-x side, < 0 the low-x side."""
    a = float(np.clip(asym, -0.95, 0.95))
    gamma = _safe(fwhm) / 2.0
    gl = gamma * (1.0 - a)
    gr = gamma * (1.0 + a)
    g = np.where(x < center, gl, gr)
    return height * g ** 2 / ((x - center) ** 2 + g ** 2)


def pearson7(x, height, center, fwhm, expo):
    """Pearson VII — the workhorse XRD peak shape (m=expo)."""
    m = max(expo, 0.5)
    w = _safe(fwhm) / 2.0
    denom = 1.0 + (2.0 ** (1.0 / m) - 1.0) * ((x - center) / w) ** 2
    return height * denom ** (-m)


def doniach_sunjic(x, height, center, fwhm, asym):
    """Doniach–Šunjić line shape (asymmetric core-level XPS peak)."""
    a = float(np.clip(asym, 0.0, 0.95))
    gamma = _safe(fwhm) / 2.0
    dx = x - center
    num = np.cos(np.pi * a / 2.0 + (1.0 - a) * np.arctan(dx / gamma))
    den = (dx ** 2 + gamma ** 2) ** ((1.0 - a) / 2.0)
    raw = num / den
    # Normalise so the maximum equals *height*.
    peak = np.nanmax(np.abs(raw)) or 1.0
    return height * raw / peak


def exp_gaussian(x, height, center, fwhm, tau):
    """Exponentially-modified Gaussian (asymmetric chromatographic /
    thermal peak). *tau* sets the trailing-edge decay."""
    from scipy.special import erfc
    sigma = _safe(fwhm) / _FWHM_SIGMA
    tau = _safe(abs(tau))
    arg = (sigma ** 2 - tau * (x - center)) / (np.sqrt(2.0) * sigma * tau)
    shape = np.exp(0.5 * (sigma / tau) ** 2 - (x - center) / tau) \
        * erfc(arg)
    peak = np.nanmax(shape) or 1.0
    return height * shape / peak


def logistic_step(x, height, center, width):
    """Logistic sigmoid step — TGA mass-loss / DSC transition."""
    w = _safe(width)
    return height / (1.0 + np.exp(-(x - center) / w))


def exp_decay(x, height, center, tau):
    """Single exponential decay measured from *center* (AFM/relaxation)."""
    tau = _safe(abs(tau))
    return height * np.exp(-(x - center) / tau)


# ── Parameter metadata ──────────────────────────────────────────────

class PeakModel:
    """One fittable peak/curve shape: a function plus parameter metadata.

    *params* lists the editable parameter names in display order. *guess*
    returns sensible starting values given the data and a chosen centre.
    """

    def __init__(self, key: str, label: str, func: Callable,
                 params: List[str], guess: Callable, group: str = ""):
        self.key = key
        self.label = label
        self.func = func
        self.params = params
        self.guess = guess
        self.group = group


def _basic_guess(extra=None):
    """Build a guess() for a height/center/fwhm peak with optional extras."""
    extra = extra or {}

    def guess(x, y, center):
        span = float(np.nanmax(x) - np.nanmin(x)) or 1.0
        idx = int(np.nanargmin(np.abs(x - center)))
        height = float(y[idx]) if np.isfinite(y[idx]) else float(
            np.nanmax(y))
        g = {"height": height, "center": float(center),
             "fwhm": span / 20.0}
        g.update(extra)
        return g
    return guess


# Voigt is parameterised by sigma/gamma rather than a single FWHM.
def _voigt_guess(x, y, center):
    span = float(np.nanmax(x) - np.nanmin(x)) or 1.0
    idx = int(np.nanargmin(np.abs(x - center)))
    height = float(y[idx]) if np.isfinite(y[idx]) else float(np.nanmax(y))
    return {"height": height, "center": float(center),
            "sigma": span / 40.0, "gamma": span / 40.0}


def _step_guess(x, y, center):
    return {"height": float(np.nanmax(y)), "center": float(center),
            "width": (float(np.nanmax(x) - np.nanmin(x)) or 1.0) / 20.0}


def _decay_guess(x, y, center):
    return {"height": float(np.nanmax(y)), "center": float(center),
            "tau": (float(np.nanmax(x) - np.nanmin(x)) or 1.0) / 5.0}


PEAK_MODELS: Dict[str, PeakModel] = {
    m.key: m for m in [
        PeakModel("gaussian", "Gaussian", gaussian,
                  ["height", "center", "fwhm"], _basic_guess(),
                  "General / TEM / FTIR"),
        PeakModel("lorentzian", "Lorentzian", lorentzian,
                  ["height", "center", "fwhm"], _basic_guess(),
                  "General / Raman"),
        PeakModel("pseudo_voigt", "Pseudo-Voigt", pseudo_voigt,
                  ["height", "center", "fwhm", "fraction"],
                  _basic_guess({"fraction": 0.5}), "XRD / XPS"),
        PeakModel("voigt", "Voigt", voigt,
                  ["height", "center", "sigma", "gamma"], _voigt_guess,
                  "XRD / XPS"),
        PeakModel("asym_lorentzian", "Asymmetric Lorentzian",
                  asym_lorentzian, ["height", "center", "fwhm", "asym"],
                  _basic_guess({"asym": 0.0}), "XPS / Raman"),
        PeakModel("pearson7", "Pearson VII", pearson7,
                  ["height", "center", "fwhm", "expo"],
                  _basic_guess({"expo": 2.0}), "XRD"),
        PeakModel("doniach_sunjic", "Doniach-Sunjic", doniach_sunjic,
                  ["height", "center", "fwhm", "asym"],
                  _basic_guess({"asym": 0.1}), "XPS"),
        PeakModel("exp_gaussian", "Exp.-modified Gaussian", exp_gaussian,
                  ["height", "center", "fwhm", "tau"],
                  _basic_guess({"tau": 1.0}), "TGA / chromatography"),
        PeakModel("logistic", "Logistic step", logistic_step,
                  ["height", "center", "width"], _step_guess,
                  "TGA / DSC"),
        PeakModel("exp_decay", "Exponential decay", exp_decay,
                  ["height", "center", "tau"], _decay_guess,
                  "AFM / relaxation"),
    ]
}


# ── Background models ───────────────────────────────────────────────

# Analytic backgrounds expose a polynomial degree (-1 = none).
BACKGROUNDS = [
    ("none", "None", -1),
    ("constant", "Constant", 0),
    ("linear", "Linear", 1),
    ("poly2", "Polynomial (2)", 2),
    ("poly3", "Polynomial (3)", 3),
    ("shirley", "Shirley (XPS)", None),
    ("tougaard", "Tougaard (XPS)", None),
]

BACKGROUND_LABELS = {k: label for k, label, _ in BACKGROUNDS}
_BG_DEGREE = {k: deg for k, _, deg in BACKGROUNDS}


def background_degree(key: str):
    """Polynomial degree for an analytic background, or None if the
    background is data-derived (Shirley/Tougaard) or absent."""
    return _BG_DEGREE.get(key, -1)


def is_data_background(key: str) -> bool:
    return key in ("shirley", "tougaard")


def shirley_background(x, y, max_iter: int = 50, tol: float = 1e-6):
    """Iterative Shirley background between the two range endpoints.

    Returns an array the same length as *y*. Robust to ascending or
    descending x (XPS binding-energy axes run high→low)."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 2:
        return np.zeros_like(y)
    # Work on an ascending-x copy so the cumulative integral is sane,
    # then map the result back.
    order = np.argsort(x)
    ys = y[order]
    y_lo, y_hi = ys[0], ys[-1]
    bg = np.linspace(y_lo, y_hi, n)
    for _ in range(max_iter):
        # Area above the current background, integrated from the left.
        above = np.clip(ys - bg, 0.0, None)
        cum = np.concatenate(([0.0], np.cumsum(
            (above[:-1] + above[1:]) / 2.0)))
        total = cum[-1]
        if total <= 0:
            break
        new_bg = y_lo + (y_hi - y_lo) * (1.0 - cum / total)
        # Shirley convention: background sits below the lower endpoint.
        new_bg = y_hi + (y_lo - y_hi) * (cum / total) \
            if y_lo < y_hi else new_bg
        if np.max(np.abs(new_bg - bg)) < tol * (abs(total) + 1e-12):
            bg = new_bg
            break
        bg = new_bg
    out = np.empty_like(bg)
    out[order] = bg
    return out


def tougaard_background(x, y, b: float = 2866.0, c: float = 1643.0):
    """Two-parameter universal Tougaard background (XPS).

    Uses the universal cross-section K(T) = B·T / (C + T²)² convolved
    with the spectrum above the high-kinetic-energy endpoint."""
    order = np.argsort(x)
    xs = np.asarray(x, dtype=float)[order]
    ys = np.asarray(y, dtype=float)[order]
    n = len(ys)
    if n < 2:
        return np.zeros_like(y)
    base = ys[-1]
    f = ys - base
    bg = np.zeros(n)
    for i in range(n):
        t = xs[i:] - xs[i]
        k = b * t / (c + t ** 2) ** 2
        bg[i] = np.trapz(k * f[i:], xs[i:])
    bg = bg + base
    out = np.empty(n)
    out[order] = bg
    return out
