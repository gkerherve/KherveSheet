"""Build "Planck Blackbody.ksheet" — a Python-cell physics example.

The sheet lets the user edit a blackbody temperature (K) and see the
Planck spectral-radiance curve recomputed and plotted by a =PY cell.

Run:  python examples/build_py_planck_blackbody.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE  # noqa: E402

OUT_PATH = os.path.join(
    _REPO, "examples", "python", "Physics", "Planck Blackbody.ksheet"
)


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Blackbody")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Planck Blackbody Radiation",
        "Spectral radiance B_lambda vs wavelength for a blackbody at temperature T",
    )

    # ── Input parameters ──────────────────────────────────────────────
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    s.set(4, 0, "Temperature T (K)")
    s.set(4, 1, 5778)          # default: surface temperature of the Sun
    s.fmt(4, 0, bold=True)
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0")

    s.set(5, 0, "lambda_min (nm)")
    s.set(5, 1, 100)
    s.fmt(5, 0, bold=True)
    s.fmt(5, 1, bg=PALETTE["warn"], align="center", number_format="0")

    s.set(6, 0, "lambda_max (nm)")
    s.set(6, 1, 3000)
    s.fmt(6, 0, bold=True)
    s.fmt(6, 1, bg=PALETTE["warn"], align="center", number_format="0")

    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 180)
    s.col_width(1, 110)

    # ── Sticky note ───────────────────────────────────────────────────
    s.note(
        4, 1,
        "Edit T (B5) — try 3000 K (red dwarf) or 10000 K (blue star).\n"
        "Also change the wavelength window (B6, B7).\n"
        "Press Ctrl+Enter on the Python cell (A10) to replot.",
        kind="note",
    )

    # ── Python cell: plot ─────────────────────────────────────────────
    py_code = """\
=PY
import numpy as np
import matplotlib.pyplot as plt

# Physical constants (SI)
h  = 6.62607015e-34   # Planck constant  (J·s)
c  = 2.99792458e8     # Speed of light   (m/s)
kB = 1.380649e-23     # Boltzmann constant (J/K)

# Read inputs from the sheet
T       = float(ks("B5"))          # temperature (K)
lam_min = float(ks("B6")) * 1e-9  # convert nm → m
lam_max = float(ks("B7")) * 1e-9

lam = np.linspace(lam_min, lam_max, 600)

# Planck spectral radiance  B_lambda  (W sr^-1 m^-3)
B = (2 * h * c**2 / lam**5) / (np.exp(h * c / (lam * kB * T)) - 1)

# Scale to MW sr^-1 m^-3 for readable y-axis
B_scaled = B * 1e-6   # → MW sr^-1 m^-3
lam_nm   = lam * 1e9  # → nm for x-axis

fig, ax = plt.subplots(figsize=(6.5, 4))
ax.plot(lam_nm, B_scaled, color="#e05c00", linewidth=2.2,
        label=f"T = {T:.0f} K")
ax.fill_between(lam_nm, B_scaled, alpha=0.15, color="#e05c00")

# Mark the peak wavelength (Wien's displacement law)
lam_peak = 2.897755e-3 / T        # metres
if lam_min < lam_peak < lam_max:
    B_peak = (2 * h * c**2 / lam_peak**5) / (
        np.exp(h * c / (lam_peak * kB * T)) - 1) * 1e-6
    ax.axvline(lam_peak * 1e9, color="#4472c4", linestyle="--", linewidth=1.4,
               label=f"Peak {lam_peak*1e9:.0f} nm")
    ax.annotate(f"  {lam_peak*1e9:.0f} nm",
                xy=(lam_peak*1e9, B_peak), fontsize=9, color="#4472c4")

ax.set_xlabel("Wavelength (nm)", fontsize=11)
ax.set_ylabel("Spectral radiance (MW / sr / m^3)", fontsize=11)
ax.set_title(f"Planck Blackbody Spectrum  —  T = {T:.0f} K", fontsize=12)
ax.legend(fontsize=9)
ax.grid(True, alpha=0.35)
plt.tight_layout()
plt.gcf()
"""
    s.set(9, 0, "Python cell — plot")
    s.fmt(9, 0, bold=True, font_color=PALETTE["header"])
    s.formula(10, 0, py_code)
    s.fmt(10, 0, bg=PALETTE["band"], font_family="Courier New", font_size=9)

    # ── Second Python cell: Wien peak & total power ───────────────────
    py_summary = """\
=PY
import numpy as np

h  = 6.62607015e-34
c  = 2.99792458e8
kB = 1.380649e-23
sigma = 5.670374419e-8   # Stefan-Boltzmann constant

T = float(ks("B5"))

lam_peak_nm = (2.897755e-3 / T) * 1e9          # Wien peak (nm)
total_power = sigma * T**4                       # Stefan-Boltzmann (W/m^2)

# Spill two labelled results downward
[
    ["Wien peak wavelength (nm)", round(lam_peak_nm, 2)],
    ["Total irradiance (W/m^2)",  round(total_power, 1)],
]
"""
    s.set(9, 3, "Summary (spilled by Python)")
    s.fmt(9, 3, bold=True, font_color=PALETTE["header"])
    s.formula(10, 3, py_summary)
    s.fmt(10, 3, bg=PALETTE["band_alt"], font_family="Courier New", font_size=9)
    s.col_width(3, 240)
    s.col_width(4, 140)

    wb.save(OUT_PATH)
    return OUT_PATH


if __name__ == "__main__":
    print("Wrote", build())
