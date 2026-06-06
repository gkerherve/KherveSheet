"""Build "EPR Spectrum.ksheet" — a Python-cell materials science example.

Electron Paramagnetic Resonance (EPR): magnetic field (Gauss) vs first-
derivative absorption signal.  The =PY cell finds the resonance field at
the derivative zero-crossing, computes the g-factor
    g = h*nu / (mu_B * B_res)
integrates the derivative to get the absorption line, reports g and B_res,
and plots the derivative and integrated absorption on twin axes.

Data layout:
  col 0 = A : B-field (Gauss)     [literal, header in A1, data A2 onward]
  col 1 = B : dI/dB signal        [literal, header in B1, data B2 onward]
  Parameters: D2 = microwave frequency (GHz)
  Results: written to F2:F3 by =PY via ks_set
  =PY cell: col 8 (I), row 9 — well clear of A-B data and D-F results

Physics constants:
  h   = 6.62607015e-34 J·s
  mu_B = 9.2740100783e-24 J/T
  g = h * nu / (mu_B * B_res)  with B_res in Tesla (1 G = 1e-4 T)

Run:  python examples/build_py_epr_spectrum.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE  # noqa: E402


# ── Physical constants ────────────────────────────────────────────────
h_PLANCK = 6.62607015e-34   # J·s
MU_B = 9.2740100783e-24     # J/T

# ── EPR spectrum parameters ───────────────────────────────────────────
# Simulate an organic radical with g ≈ 2.0023 at X-band (9.45 GHz)
NU_GHZ = 9.45                   # microwave frequency (GHz)
G_TRUE = 2.0023                 # true g-factor (organic radical)

# Resonance field from g = h*nu / (mu_B * B_res)
# B_res in Tesla, then convert to Gauss for the sweep
B_res_T = (h_PLANCK * NU_GHZ * 1e9) / (MU_B * G_TRUE)
B_res_G = B_res_T * 1e4   # Gauss

# Field sweep: ±200 G around resonance, 401 points
B_HALF_WIDTH = 200.0   # Gauss
N_POINTS = 401
B_arr = np.linspace(B_res_G - B_HALF_WIDTH, B_res_G + B_HALF_WIDTH, N_POINTS)
dB = B_arr[1] - B_arr[0]

# Derivative-Gaussian signal (Gaussian absorption → its derivative)
# Linewidth (peak-to-peak) 5 Gauss (typical for organic radical)
LINEWIDTH_PP = 5.0   # Gauss (peak-to-peak)
SIGMA_G = LINEWIDTH_PP / (2.0 * np.sqrt(2.0))   # Gaussian sigma
AMPLITUDE = 1.0   # normalised

# Derivative of Gaussian: dA/dB = -(B - B_res)/sigma^2 * A * exp(...)
absorb_gauss = AMPLITUDE * np.exp(-0.5 * ((B_arr - B_res_G) / SIGMA_G) ** 2)
deriv_signal = -(B_arr - B_res_G) / SIGMA_G ** 2 * absorb_gauss

# Add a small Lorentzian contribution (mixed lineshape, typical EPR)
SIGMA_L = SIGMA_G * 1.2
lorentz_absorb = AMPLITUDE * 0.15 * SIGMA_L ** 2 / ((B_arr - B_res_G) ** 2 + SIGMA_L ** 2)
lorentz_deriv = -0.30 * SIGMA_L ** 2 * 2.0 * (B_arr - B_res_G) / ((B_arr - B_res_G) ** 2 + SIGMA_L ** 2) ** 2

deriv_signal = deriv_signal + lorentz_deriv

# Add noise
rng = np.random.default_rng(7)
noise = rng.normal(0, 0.005, N_POINTS)
deriv_signal = deriv_signal + noise
deriv_signal = np.round(deriv_signal, 6)


# ── =PY cell body ─────────────────────────────────────────────────────
PY_BODY = r"""import numpy as np, matplotlib.pyplot as plt

# Physical constants (exact CODATA 2018)
H_PLANCK = 6.62607015e-34    # J·s
MU_B     = 9.2740100783e-24  # J/T

# --- read data from cells ------------------------------------------
B_raw  = ks('A2:A2000')
dI_raw = ks('B2:B2000')
B_raw  = np.asarray(B_raw, dtype=float)
dI_raw = np.asarray(dI_raw, dtype=float)
mask = np.isfinite(B_raw) & np.isfinite(dI_raw)
B_G  = B_raw[mask]   # Gauss
dI   = dI_raw[mask]

# --- read microwave frequency (GHz) from D2 -----------------------
nu_GHz = float(ks('D2'))
nu_Hz  = nu_GHz * 1.0e9

# --- find resonance field: zero-crossing of derivative ------------
# Sign change: pick zero crossing nearest to centre of sweep
n = len(B_G)
zero_crossings = np.where(np.diff(np.sign(dI)))[0]  # indices before crossing
if len(zero_crossings) == 0:
    B_res_G = float(B_G[np.argmin(np.abs(dI))])
else:
    # Pick crossing closest to spectrum centre
    centre = B_G[n // 2]
    ic = zero_crossings[np.argmin(np.abs(B_G[zero_crossings] - centre))]
    # Linear interpolation for sub-point accuracy
    frac = -dI[ic] / (dI[ic + 1] - dI[ic]) if (dI[ic + 1] - dI[ic]) != 0 else 0.5
    B_res_G = float(B_G[ic] + frac * (B_G[ic + 1] - B_G[ic]))

# --- compute g-factor ----------------------------------------------
B_res_T = B_res_G * 1.0e-4   # convert Gauss → Tesla
g_factor = (H_PLANCK * nu_Hz) / (MU_B * B_res_T)

# --- write results -------------------------------------------------
ks_set('F2', round(B_res_G, 3))
ks_set('F3', round(g_factor, 5))

# --- integrate derivative to obtain absorption line ---------------
# numerical integration (cumulative trapezoidal)
dB_arr = np.diff(B_G)
dB_arr = np.append(dB_arr, dB_arr[-1])
absorption = np.cumsum(dI * dB_arr)
# baseline-correct: subtract linear trend
absorption -= np.linspace(absorption[0], absorption[-1], len(absorption))
# Normalise so max = 1
amax = np.max(np.abs(absorption))
if amax > 0:
    absorption = absorption / amax

# --- plot: twin axes -----------------------------------------------
fig, ax1 = plt.subplots(figsize=(7.5, 4.8))
ax2 = ax1.twinx()

# Derivative signal (left axis)
l1, = ax1.plot(B_G, dI, '-', lw=1.5, color='#1f4e79',
               label='dI/dB (derivative)')
ax1.axhline(0, color='#888888', lw=0.7, linestyle='--')
ax1.axvline(B_res_G, color='#c00000', lw=1.2, linestyle=':',
            label=f'B$_{{res}}$ = {B_res_G:.1f} G')
ax1.set_xlabel('Magnetic field B (Gauss)')
ax1.set_ylabel('dI/dB (arb. units)', color='#1f4e79')
ax1.tick_params(axis='y', labelcolor='#1f4e79')

# Integrated absorption (right axis)
l2, = ax2.plot(B_G, absorption, '-', lw=1.5, color='#ed7d31',
               alpha=0.85, label='Absorption (integrated)')
ax2.set_ylabel('Absorption (normalised)', color='#ed7d31')
ax2.tick_params(axis='y', labelcolor='#ed7d31')
ax2.set_ylim(-0.1, 1.3)

ax1.set_title(
    f'EPR Spectrum  —  g = {g_factor:.5f},  '
    f'B$_{{res}}$ = {B_res_G:.1f} G  '
    f'(ν = {nu_GHz} GHz)')

lines = [l1, l2]
labels = [l.get_label() for l in lines]
ax1.legend(lines, labels, fontsize=9, loc='upper left')
ax1.grid(True, alpha=0.25)
plt.tight_layout()
plt.gcf()"""


def build() -> str:
    wb = Workbook(min_rows=max(N_POINTS + 10, 60), min_cols=14)
    s = wb.add_sheet("EPR Spectrum")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 110)   # A: B-field
    s.col_width(1, 110)   # B: dI/dB
    s.col_width(2, 20)    # C: spacer
    s.col_width(3, 180)   # D: label
    s.col_width(4, 20)    # E: spacer
    s.col_width(5, 120)   # F: result values
    s.col_width(6, 20)    # G: spacer
    s.col_width(7, 20)    # H: spacer
    s.col_width(8, 20)    # I: =PY cell col

    # ── Title in cols 3-8 (rows 0-1) ─────────────────────────────────
    s.set(0, 3, "EPR Spectrum Analysis")
    s.fmt(0, 3, bold=True, font_size=16, font_color=PALETTE["header"])
    s.merge(0, 3, 1, 5)
    s.set(1, 3, "First-derivative EPR signal: g-factor, resonance field, absorption integration")
    s.fmt(1, 3, italic=True, font_color="#555555")
    s.merge(1, 3, 1, 5)

    # ── Data column headers (row 0, cols 0-1 = A1, B1) ───────────────
    # =PY reads A2:A2000 and B2:B2000, so header at row 0, data from row 1
    s.set(0, 0, "B-field (Gauss)")
    s.fmt(0, 0, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.set(0, 1, "dI/dB (arb.)")
    s.fmt(0, 1, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")

    # ── Write spectrum data ───────────────────────────────────────────
    for i, (B, dI) in enumerate(zip(B_arr, deriv_signal)):
        r = i + 1
        s.set(r, 0, round(float(B), 3))
        s.set(r, 1, round(float(dI), 6))
        s.fmt(r, 0, align="right", number_format="0.0")
        s.fmt(r, 1, align="right", number_format="0.000000")
        if i % 2 == 1:
            s.fmt(r, 0, bg=PALETTE["band_alt"])
            s.fmt(r, 1, bg=PALETTE["band_alt"])

    s.box(0, 0, N_POINTS, 1, color=PALETTE["header"], width=1.0)

    # ── Parameter panel (row 2, cols 3-5) ────────────────────────────
    # Microwave frequency input: D2 (0-based row 1, col 3 → sheet row 2, col D)
    s.set(2, 3, "Parameters")
    s.fmt(2, 3, bold=True, font_color=PALETTE["accent"], font_size=11)

    s.set(3, 3, "Microwave frequency (GHz)")
    s.set(3, 3, "Microwave frequency (GHz)")
    # 0-based row 1, col 3 = D2 in sheet notation
    s.set(1, 3, "Microwave frequency (GHz)")
    s.fmt(1, 3, bold=True)
    s.set(1, 5, NU_GHZ)   # col 5 = F; but =PY reads D2...
    # Actually the guide says D2: col 3 (D), row 1 (row 1+1=row 2 in 1-based)
    # set(1, 3, ...) → D2 in sheet. So put the value there.
    # Let's fix: parameter label in col 3 (D), value in col 4 (E)?
    # No, the guide snippet says ks('D2') — that's col D (index 3), row 2 (1-based) = row 1 (0-based)
    # So: s.set(1, 3, label) puts label in D2, and s.set(1, 4, value) puts value in E2.
    # But the =PY reads ks('D2')... that would return the label text, not the value.
    # Correct: put the value in D2 itself (col 3, row 1):
    s.set(1, 3, NU_GHZ)
    s.fmt(1, 3, bg=PALETTE["warn"], align="center", number_format="0.00")

    # Put label in col 2 (C), row 1:
    s.set(1, 2, "Microwave frequency (GHz)")
    s.fmt(1, 2, bold=True)

    # ── Results panel (rows 1-3, cols 4-5) ───────────────────────────
    # ks_set('F2', B_res_G) → col F = col 5, sheet row 2 = 0-based row 1
    # ks_set('F3', g_factor) → col F = col 5, sheet row 3 = 0-based row 2
    s.set(0, 4, "Results")
    s.fmt(0, 4, bold=True, font_color=PALETTE["accent"], font_size=11)

    s.set(1, 4, "B_res (Gauss)")
    s.fmt(1, 4, bold=True)
    s.set(1, 5, "")   # filled by ks_set('F2', ...)
    s.fmt(1, 5, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.000")

    s.set(2, 4, "g-factor")
    s.fmt(2, 4, bold=True)
    s.set(2, 5, "")   # filled by ks_set('F3', ...)
    s.fmt(2, 5, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.00000")

    s.box(1, 4, 2, 5, color=PALETTE["header"], width=1.2)

    s.note(
        1, 5,
        "B_res and g-factor are written by the =PY cell (I10). "
        "g = h·ν / (μ_B · B_res).  For a free electron g = 2.00232.",
        kind="note",
    )

    # ── =PY cell (row 9 = sheet row 10, col 8 = I) ────────────────────
    s.set(8, 3, "Analysis cell (I10) ▼")
    s.fmt(8, 3, bold=True, font_color=PALETTE["header"])
    s.formula(9, 8, "=PY\n" + PY_BODY)

    s.note(
        9, 8,
        "=PY cell: reads B-field and dI/dB signal from A/B columns. "
        "Finds resonance at the derivative zero-crossing. "
        "Computes g = h·ν/(μ_B·B_res). Integrates the derivative "
        "to get the absorption line. Plots both on twin axes.",
        kind="note",
    )

    # ── Additional notes ──────────────────────────────────────────────
    s.note(
        0, 0,
        f"Column A: B-field sweep from {B_arr[0]:.0f} to {B_arr[-1]:.0f} Gauss "
        f"({N_POINTS} points, step {dB:.2f} G).  "
        "Column B: first-derivative EPR signal (mixed Gaussian/Lorentzian "
        f"lineshape, linewidth ≈ {LINEWIDTH_PP} G, g = {G_TRUE}).  "
        "Seed: np.random.default_rng(7).",
        kind="note",
    )

    s.note(
        1, 2,
        "Edit the microwave frequency (GHz) to simulate different EPR bands: "
        "X-band ≈ 9.45, Q-band ≈ 35, W-band ≈ 95. "
        "Press Ctrl+Enter on I10 to recompute g.",
        kind="note",
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    s.equation(
        r"g = \frac{h \nu}{\mu_B B_{res}}",
        at=(560, 40), fontsize=20, color="#1a1a2e",
        bg_color="#f8f8ff", border_color=PALETTE["header"],
        border_width=1.2, size=(200, 60),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        _REPO, "examples", "python", "Materials Science",
        "EPR Spectrum.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
