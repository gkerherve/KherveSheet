"""Capability catalogue for the AI assistant.

Rather than pour every formula function and analysis feature into the
system prompt (which would be huge and mostly irrelevant per turn), the
assistant queries this catalogue on demand — like a small searchable
database — through the ``search_functions`` and ``get_function_details``
tools.

The formula half is built directly from the live registries in
``formulas.py`` so it never drifts.  The science/analysis half is a
curated list of higher-level features (fitting models, solver, trendline,
baseline methods, chart types) with a short note on how to reach each.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, List


# ── Curated higher-level capabilities ──────────────────────────────
# These are app features reached through dialogs/menus rather than cell
# formulas.  The assistant can describe them to the user and, where a
# formula equivalent exists (e.g. the "Data Analysis" functions), use
# that directly via set_formula/write_cells.

_CAPABILITIES: List[dict] = [
    # ── Curve fitting (Tools ▸ Curve Fitting) ───────────────────────
    {"name": "Curve Fitting", "category": "Analysis",
     "summary": "lmfit peak fitting: add Gaussian/Lorentzian/Voigt/etc., "
                "per-peak parameter editor, pick a background, live fit "
                "report, write components back to the sheet.",
     "access": "Tools ▸ Curve Fitting"},
    {"name": "Fitting Models", "category": "Analysis",
     "summary": "Available peak shapes: Gaussian, Lorentzian, Voigt, "
                "Pseudo-Voigt, Pearson VII, Pearson IV, Split Lorentzian, "
                "Doniach-Sunjic, Skewed Gaussian, Skewed Voigt, "
                "Breit-Wigner-Fano, Log-normal, Moffat, Student's-t, "
                "Damped oscillator, Thermal/Bose-Einstein/Fermi-Dirac, "
                "Step, Rectangle, plus custom expression models.",
     "access": "Tools ▸ Curve Fitting ▸ Add Function"},
    {"name": "Fitting Backgrounds", "category": "Analysis",
     "summary": "Background choices for fitting: None, Constant, Linear, "
                "Polynomial (2nd/3rd), Shirley, Reversed Shirley, "
                "Active Shirley, ALS.",
     "access": "Tools ▸ Curve Fitting ▸ Background"},
    # ── Trendlines ──────────────────────────────────────────────────
    {"name": "Trendline", "category": "Analysis",
     "summary": "Fit a curve to a series with goodness-of-fit (R², adj-R², "
                "RMSE, reduced chi-sq, AIC, BIC). Models: Linear, "
                "Quadratic, Cubic, Polynomial, Exponential, Exponential "
                "Decay, Double/Stretched Exponential, Logarithmic, Power, "
                "Allometric, Square Root, Inverse, Hyperbolic, Logistic, "
                "Boltzmann, Gaussian, Lorentzian, Sine, Hill, "
                "Michaelis-Menten, erf.",
     "access": "right-click a chart ▸ Add Trendline"},
    # ── Solver ──────────────────────────────────────────────────────
    {"name": "Solver", "category": "Optimisation",
     "summary": "Excel-style optimisation: minimise, maximise, or hit a "
                "target value of a cell by changing other cells, subject "
                "to constraints. Methods: GRG Nonlinear (SLSQP), LP "
                "Simplex (HiGHS), Evolutionary (differential evolution).",
     "access": "Tools ▸ Solver"},
    # ── Science tools (Science menu) ────────────────────────────────
    {"name": "Normalisation", "category": "Science",
     "summary": "Scale a column to a custom [min, max] range. Formula "
                "equivalents: NORM.MAX, NORM.AREA, NORM.MINMAX, "
                "NORM.ZSCORE, NORM.PEAK, NORM.RANGE.",
     "access": "Science ▸ Normalisation (or NORM.* formulas)"},
    {"name": "Integration", "category": "Science",
     "summary": "Cumulative or definite trapezoidal/Simpson integration. "
                "Formula equivalents: TRAPZ, CUMTRAPZ, SIMPS.",
     "access": "Science ▸ Integration (or TRAPZ/CUMTRAPZ/SIMPS)"},
    {"name": "Derivative", "category": "Science",
     "summary": "First/second numerical derivative via gradient. "
                "Formula equivalents: DERIV, DERIV2, DERIV.SMOOTH.",
     "access": "Science ▸ Derivative (or DERIV/DERIV2)"},
    {"name": "Smoothing", "category": "Science",
     "summary": "Moving-average or Savitzky-Golay smoothing. Formula "
                "equivalents: MOVAVG, SAVGOL, EWMA, MEDIAN.FILTER.",
     "access": "Science ▸ Smooth (or SAVGOL/MOVAVG)"},
    {"name": "FFT", "category": "Science",
     "summary": "Discrete Fourier transform (Magnitude/Power/Amplitude). "
                "Formula equivalents: FFT.MAG, FFT.PHASE, FFT.FREQ, "
                "FFT.REAL, FFT.IMAG, FFT.POWER, IFFT.",
     "access": "Science ▸ FFT (or FFT.* formulas)"},
    {"name": "Interpolation", "category": "Science",
     "summary": "Resample to N points (linear/cubic/quadratic/nearest/"
                "spline/Akima). Formula equivalents: INTERP.LINEAR, "
                "INTERP.SPLINE, INTERP.AKIMA, RESAMPLE.",
     "access": "Science ▸ Interpolation (or INTERP.* formulas)"},
    {"name": "Find Peaks", "category": "Science",
     "summary": "Detect peaks with height/prominence/distance thresholds. "
                "Formula equivalents: FIND.PEAKS, FIND.PEAKS.X, "
                "FIND.PEAKS.Y.",
     "access": "Science ▸ Find Peaks (or FIND.PEAKS)"},
    {"name": "Baseline Subtraction", "category": "Science",
     "summary": "Remove a baseline with 11 methods: Polynomial, Linear, "
                "ALS, SNIP, Rubberband, Rolling Ball, LOWESS, Median, "
                "Shirley, Tougaard, Spline. Formula: BASELINE.POLY, "
                "BASELINE.ALS.",
     "access": "Science ▸ Baseline Subtraction"},
    {"name": "Band-pass Filter", "category": "Science",
     "summary": "Butterworth band-pass with low/high cutoffs. Formula "
                "equivalents: LOWPASS, HIGHPASS, BANDPASS.",
     "access": "Science ▸ Band-pass Filter (or BANDPASS)"},
    {"name": "Cross-Correlation", "category": "Science",
     "summary": "Cross-correlate two signals with optional lag.",
     "access": "Science ▸ Cross-Correlation"},
    {"name": "Signal-to-Noise", "category": "Science",
     "summary": "Estimate SNR from signal and noise regions.",
     "access": "Science ▸ Signal-to-Noise"},
    {"name": "Envelope", "category": "Science",
     "summary": "Analytic-signal envelope via the Hilbert transform.",
     "access": "Science ▸ Envelope"},
    {"name": "Kramers-Kronig", "category": "Science",
     "summary": "Recover the real part from the imaginary part "
                "(dispersion relations).",
     "access": "Science ▸ Kramers-Kronig"},
    {"name": "Deconvolution", "category": "Science",
     "summary": "Richardson-Lucy iterative deconvolution with a known PSF.",
     "access": "Science ▸ Deconvolution"},
    {"name": "Calibration", "category": "Science",
     "summary": "Linear calibration y' = y·slope + intercept.",
     "access": "Science ▸ Calibration"},
    {"name": "Statistics on Selection", "category": "Analysis",
     "summary": "Quick descriptive stats (count, mean, stdev, min, max, "
                "sum) for the current selection.",
     "access": "Tools ▸ Statistics on Selection"},
    # ── Charts ──────────────────────────────────────────────────────
    {"name": "Chart Types", "category": "Charts",
     "summary": "Embedded chart types: Line, Scatter, Line+Symbol, Bar, "
                "Step, Stem, Histogram, Box, Heatmap, 3D Surface. Use the "
                "insert_chart tool to create one.",
     "access": "Insert ▸ Chart (or the insert_chart tool)"},
    # ── Insert decorations ──────────────────────────────────────────
    {"name": "Insert Decorations", "category": "Insert",
     "summary": "Cell extras: checkbox, dropdown (data validation), "
                "hyperlink, comment, sticky note, emoji, sparkline "
                "(Line/Bar/Win-Loss), transpose.",
     "access": "Insert menu"},
]


# ── Index building (cached) ────────────────────────────────────────

@lru_cache(maxsize=1)
def _build_index() -> Dict[str, dict]:
    """Return name(upper) → entry dict for everything searchable.

    Entry fields: name, category, summary, signature (formulas only),
    access (capabilities only).
    """
    index: Dict[str, dict] = {}
    # Formula functions from the live registry.
    try:
        from .formulas import FUNCTION_CATEGORIES, FUNCTION_HELP
    except Exception:
        FUNCTION_CATEGORIES, FUNCTION_HELP = {}, {}
    name_to_cat: Dict[str, str] = {}
    for cat, names in FUNCTION_CATEGORIES.items():
        clean_cat = cat.replace("&&", "&")
        for nm in names:
            name_to_cat[nm] = clean_cat
    for nm, help_text in FUNCTION_HELP.items():
        sig, _, desc = help_text.partition("\n")
        index[nm.upper()] = {
            "name": nm,
            "category": name_to_cat.get(nm, "Function"),
            "signature": sig.strip(),
            "summary": desc.strip() or sig.strip(),
            "kind": "formula",
        }
    # Also index any function that has a category but no help text.
    for nm, cat in name_to_cat.items():
        if nm.upper() not in index:
            index[nm.upper()] = {
                "name": nm, "category": cat,
                "signature": f"{nm}(...)", "summary": "",
                "kind": "formula",
            }
    # Curated capabilities.
    for cap in _CAPABILITIES:
        key = cap["name"].upper()
        index[key] = {**cap, "kind": "capability"}
    return index


# ── Public search API ──────────────────────────────────────────────

def all_categories() -> List[str]:
    cats = {e["category"] for e in _build_index().values()}
    return sorted(cats)


def search(query: str, category: str = "", limit: int = 25) -> List[dict]:
    """Search the catalogue by substring over name + summary.

    Returns lightweight hits: {name, category, summary, signature?}.
    Exact and prefix name matches are ranked first.
    """
    index = _build_index()
    q = (query or "").strip().lower()
    cat = (category or "").strip().lower()
    hits = []
    for entry in index.values():
        if cat and entry["category"].lower() != cat:
            continue
        name_l = entry["name"].lower()
        summ_l = entry.get("summary", "").lower()
        sig_l = entry.get("signature", "").lower()
        if not q:
            score = 5
        elif name_l == q:
            score = 0
        elif name_l.startswith(q):
            score = 1
        elif q in name_l:
            score = 2
        elif q in summ_l or q in sig_l:
            score = 3
        else:
            continue
        hit = {
            "name": entry["name"],
            "category": entry["category"],
            "summary": entry.get("summary", ""),
        }
        if entry.get("signature"):
            hit["signature"] = entry["signature"]
        hits.append((score, entry["name"].lower(), hit))
    hits.sort(key=lambda t: (t[0], t[1]))
    return [h for _s, _n, h in hits[:max(1, limit)]]


def details(names: List[str]) -> List[dict]:
    """Return full entries for the given names (case-insensitive)."""
    index = _build_index()
    out = []
    for nm in names:
        entry = index.get((nm or "").strip().upper())
        if entry is None:
            out.append({"name": nm, "error": "not found"})
        else:
            out.append(dict(entry))
    return out
