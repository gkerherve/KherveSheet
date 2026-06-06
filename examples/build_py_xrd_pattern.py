"""Build "XRD Pattern.ksheet" — a Python-cell materials-science example.

Simulates a powder XRD diffraction pattern (2theta vs intensity) for a
cubic phase with Cu K-alpha radiation.  A =PY cell finds the Bragg peaks,
computes d-spacings via Bragg's law and crystallite sizes via the Scherrer
equation, and plots the pattern with peaks marked.

Row/column mapping: set(r, c, v) -> sheet cell letter(c) + str(r+1).
  set(3, 1, v) -> B4,  set(4, 1, v) -> B5, etc.

Run:  python examples/build_py_xrd_pattern.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

import numpy as np
from ksheet_author import Workbook, PALETTE


def build() -> str:
    # ── Synthetic XRD pattern ─────────────────────────────────────────
    rng = np.random.default_rng(42)
    lam = 1.5406          # Cu K-alpha (Angstrom)
    K = 0.9               # Scherrer constant
    # Cubic phase peaks: (hkl, d in A, I_rel, FWHM_deg)
    # d = a/sqrt(h^2+k^2+l^2), a=4.21 A (e.g. SrTiO3-like)
    a = 4.21
    peaks_hkl = [(1,0,0),(1,1,0),(1,1,1),(2,0,0),(2,1,0),(2,1,1),(2,2,0)]
    # Only keep peaks where 2theta < 90
    peak_data = []
    for h,k,l in peaks_hkl:
        d = a / np.sqrt(h**2 + k**2 + l**2)
        sin_th = lam / (2*d)
        if sin_th > 0.999:
            continue
        tt = 2 * np.degrees(np.arcsin(sin_th))
        # Intensity ~ 1/d^2 with some variation
        I0 = 1000.0 / (h**2 + k**2 + l**2) * rng.uniform(0.7, 1.3)
        fwhm_deg = rng.uniform(0.18, 0.35)
        peak_data.append((tt, I0, fwhm_deg))

    # Build 2theta axis and pattern
    tt_axis = np.linspace(15, 85, 701)
    pattern = np.zeros_like(tt_axis)
    for (tt0, I0, fwhm_deg) in peak_data:
        sigma = fwhm_deg / (2 * np.sqrt(2 * np.log(2)))
        pattern += I0 * np.exp(-0.5 * ((tt_axis - tt0) / sigma)**2)
    # Add background + noise
    bkg = 15 + 5 * np.sin(np.radians(tt_axis * 0.8))
    noise = rng.normal(0, 4, len(tt_axis))
    pattern = np.maximum(pattern + bkg + noise, 0)

    N = len(tt_axis)  # 701 data points

    # ── Workbook ─────────────────────────────────────────────────────
    wb = Workbook(min_rows=max(N + 5, 60), min_cols=16)
    s = wb.add_sheet("XRD")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block(
        "XRD Pattern Analysis",
        "Bragg peak finding, d-spacing and Scherrer crystallite size.  Cu Kα radiation.",
    )

    # ── Input parameters (rows 2-5 = sheet rows 3-6) ─────────────────
    # set(r, c) -> sheet row r+1, col letter(c)
    s.set(2, 0, "Parameters")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    s.set(3, 0, "Wavelength λ (A)")
    s.set(3, 1, lam)
    s.fmt(3, 0, bold=True)
    s.fmt(3, 1, bg=PALETTE["warn"], align="center", number_format="0.0000")

    s.set(4, 0, "Scherrer K constant")
    s.set(4, 1, K)
    s.fmt(4, 0, bold=True)
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.000")

    s.set(5, 0, "Peak height threshold (%)")
    s.set(5, 1, 5.0)
    s.fmt(5, 0, bold=True)
    s.fmt(5, 1, bg=PALETTE["warn"], align="center", number_format="0.0")

    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 210)
    s.col_width(1, 110)

    s.note(
        3, 1,
        "Edit the wavelength (e.g. Mo Kα = 0.7107 A, Co Kα = 1.7902 A) "
        "and press Ctrl+Enter on the =PY cell to recompute d-spacings and Scherrer sizes.",
        kind="note",
    )

    # ── Data columns: 2theta (col 3=D), intensity (col 4=E) ──────────
    # Header at row 7 (set(7,...)-> sheet row 8)
    s.set(7, 3, "2theta (deg)")
    s.set(7, 4, "Intensity (arb)")
    s.fmt(7, 3, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.fmt(7, 4, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.col_width(3, 120)
    s.col_width(4, 120)

    for i, (tt_val, I_val) in enumerate(zip(tt_axis, pattern)):
        r = 8 + i   # data starts at row 8 (sheet row 9)
        s.set(r, 3, round(float(tt_val), 4))
        s.set(r, 4, round(float(I_val), 3))

    # ── Result table headers (col 6=G..9=J) — filled by =PY ──────────
    # Results start at row 7 (sheet row 8) for headers
    s.set(7, 6, "Peak 2θ (°)")
    s.set(7, 7, "d-spacing (Å)")
    s.set(7, 8, "FWHM (°)")
    s.set(7, 9, "Size (nm)")
    for c in range(6, 10):
        s.fmt(7, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    s.col_width(6, 110)
    s.col_width(7, 110)
    s.col_width(8, 100)
    s.col_width(9, 100)

    s.note(7, 6,
           "This table is written by the =PY cell in column L. "
           "Peaks are found by scipy.signal.find_peaks on the smoothed pattern.",
           kind="note")

    # ── =PY cell: col 11 (L), row 8 (sheet row 9) ────────────────────
    # Data is in D9:E709 (rows 8..708, cols 3..4)
    # Reads: B4=lambda, B5=K, B6=threshold%
    # Writes result table to G8:J<8+npeaks> (rows 7..7+npeaks, cols 6..9)
    # NOTE: =PY cell is at (8, 11) — column L, well clear of D/E (data) and G-J (results)
    n_data = N  # 701 points
    last_data_row = 8 + n_data - 1  # 708, sheet row 709

    py_code = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "from scipy.signal import find_peaks, savgol_filter",
        "from scipy.optimize import curve_fit",
        "",
        "# Read parameters",
        "lam = float(ks('B4'))   # wavelength in Angstrom",
        "Ksch = float(ks('B5'))  # Scherrer constant",
        "thr_pct = float(ks('B6'))  # peak threshold %",
        "",
        "# Read data",
        f"tt = ks('D9:D{8 + n_data}')   # 2theta array",
        f"II = ks('E9:E{8 + n_data}')   # intensity array",
        "m = np.isfinite(tt) & np.isfinite(II)",
        "tt, II = tt[m], II[m]",
        "",
        "# Smooth for peak finding",
        "II_sm = savgol_filter(II, window_length=11, polyorder=3)",
        "II_sm = np.maximum(II_sm, 0)",
        "",
        "# Find peaks above threshold",
        "thr = thr_pct / 100.0 * II_sm.max()",
        "pks, props = find_peaks(II_sm, height=thr, distance=8, prominence=thr*0.3)",
        "",
        "# For each peak: fit Gaussian to get FWHM and centre",
        "def gauss(x, A, x0, sig, bkg):",
        "    return A * np.exp(-0.5*((x-x0)/sig)**2) + bkg",
        "",
        "result_rows = []",
        "for pk in pks:",
        "    w = max(int(0.5 / (tt[1]-tt[0])), 5)",
        "    lo, hi = max(0, pk-w), min(len(tt)-1, pk+w)",
        "    try:",
        "        p0 = [II[pk]-II_sm[lo:hi].min(), tt[pk], 0.08, II_sm[lo:hi].min()]",
        "        popt, _ = curve_fit(gauss, tt[lo:hi+1], II[lo:hi+1],",
        "                            p0=p0, maxfev=2000)",
        "        tt0 = popt[1]; sig = abs(popt[2])",
        "        fwhm_deg = 2.355 * sig",
        "    except Exception:",
        "        tt0 = tt[pk]; fwhm_deg = 0.25",
        "    # Bragg's law: d = lam / (2 sin(theta))",
        "    sin_th = np.sin(np.radians(tt0 / 2.0))",
        "    if sin_th <= 0 or sin_th >= 1.0:",
        "        continue",
        "    d = lam / (2.0 * sin_th)",
        "    # Scherrer: t = K*lam / (beta_rad * cos(theta))",
        "    beta_rad = np.radians(fwhm_deg)",
        "    cos_th = np.cos(np.radians(tt0 / 2.0))",
        "    size_nm = (Ksch * lam / (beta_rad * cos_th)) / 10.0   # A -> nm",
        "    result_rows.append([round(tt0, 3), round(d, 4),",
        "                        round(fwhm_deg, 4), round(size_nm, 2)])",
        "",
        "# Write results to G8:J<8+n>",
        "if result_rows:",
        "    import numpy as _np2",
        "    arr = _np2.array(result_rows, dtype=float)",
        "    ks_set('G8', arr)",
        "",
        "# Plot",
        "fig, ax = plt.subplots(figsize=(7, 4))",
        "ax.plot(tt, II, color='#555555', linewidth=0.8, label='Pattern')",
        "ax.plot(tt, II_sm, color='#4472c4', linewidth=1.5, label='Smoothed')",
        "if len(pks):",
        "    ax.plot(tt[pks], II_sm[pks], 'v', color='#ed7d31',",
        "            markersize=8, label='Peaks', zorder=5)",
        "    for pk in pks:",
        "        ax.axvline(tt[pk], color='#ed7d31', linewidth=0.5,",
        "                   linestyle='--', alpha=0.4)",
        "ax.set_xlabel('2θ (degrees)')",
        "ax.set_ylabel('Intensity (arb. units)')",
        "ax.set_title('Powder XRD Pattern — Cu Kα')",
        "ax.legend(fontsize=9)",
        "ax.grid(True, alpha=0.3)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(8, 11, py_code)
    s.fmt(8, 11, italic=True, font_color="#555555")
    s.col_width(11, 280)
    s.set(8, 12, "Analysis cell (col L) — Ctrl+Enter to re-run")
    s.fmt(8, 12, italic=True, font_color="#888888")

    # ── Equation ─────────────────────────────────────────────────────
    s.equation(
        r"d = \frac{\lambda}{2\sin\theta},\quad "
        r"D = \frac{K\lambda}{\beta\cos\theta}",
        at=(550, 50), fontsize=16, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(320, 52),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        _REPO, "examples", "python", "Materials Science",
        "XRD Pattern.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
