"""Build "Maxwell-Boltzmann Speeds.ksheet" — a Python-cell physics example.

Plots the Maxwell–Boltzmann speed distribution for a gas at temperature T
with particle mass m.  Three characteristic speeds (v_p, v_avg, v_rms) are
marked and returned as a spilled list by a second =PY cell.

Run:  python examples/build_py_maxwell_boltzmann.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE  # noqa: E402

OUT_PATH = os.path.join(
    _REPO, "examples", "python", "Physics", "Maxwell-Boltzmann Speeds.ksheet"
)


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("MB Distribution")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Maxwell–Boltzmann Speed Distribution",
        "f(v) = 4π n (m/2πkT)^(3/2) v² exp(-mv²/2kT)  —  edit T and m below",
    )

    # ── Input parameters ──────────────────────────────────────────────
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    s.set(4, 0, "Temperature T (K)")
    s.set(4, 1, 300.0)        # B5: room temperature
    s.fmt(4, 0, bold=True)
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.0")

    # Particle mass as atomic mass units for user friendliness
    s.set(5, 0, "Particle mass (u, e.g. 4 for He)")
    s.set(5, 1, 4.0)          # B6: helium
    s.fmt(5, 0, bold=True)
    s.fmt(5, 1, bg=PALETTE["warn"], align="center", number_format="0.000")

    s.set(6, 0, "v_max for plot (m/s)")
    s.set(6, 1, 4000.0)       # B7
    s.fmt(6, 0, bold=True)
    s.fmt(6, 1, bg=PALETTE["warn"], align="center", number_format="0.0")

    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 220)
    s.col_width(1, 120)

    # ── Sticky note ───────────────────────────────────────────────────
    s.note(
        4, 1,
        "Try different gases:\n"
        "  He  → m = 4 u\n"
        "  N₂  → m = 28 u\n"
        "  Ar  → m = 40 u\n"
        "Change T to see the distribution widen at higher temperatures.\n"
        "Press Ctrl+Enter on the Python cells (A10, E10) to recompute.",
        kind="note",
    )

    # ── Python cell 1: plot ───────────────────────────────────────────
    py_plot = """\
=PY
import numpy as np
import matplotlib.pyplot as plt

kB  = 1.380649e-23    # Boltzmann constant (J/K)
u   = 1.66053906660e-27  # atomic mass unit (kg)

T     = float(ks("B5"))
m_u   = float(ks("B6"))          # mass in atomic mass units
v_max = float(ks("B7"))

m = m_u * u                      # convert to kg

v = np.linspace(0.0, v_max, 800)

# Maxwell-Boltzmann speed distribution (probability density, 1/m·s^-1)
fv = (4 * np.pi * (m / (2 * np.pi * kB * T))**1.5
      * v**2 * np.exp(-m * v**2 / (2 * kB * T)))

# Characteristic speeds
v_p   = np.sqrt(2 * kB * T / m)            # most probable
v_avg = np.sqrt(8 * kB * T / (np.pi * m))  # mean
v_rms = np.sqrt(3 * kB * T / m)            # root-mean-square

fig, ax = plt.subplots(figsize=(6.5, 4.2))
ax.plot(v, fv, color="#4472c4", linewidth=2.4, label=f"T={T:.0f} K, m={m_u:.1f} u")
ax.fill_between(v, fv, alpha=0.13, color="#4472c4")

for speed, lbl, col in [
    (v_p,   "v_p",   "#e05c00"),
    (v_avg, "v_avg", "#2e8b57"),
    (v_rms, "v_rms", "#9932cc"),
]:
    if speed <= v_max:
        fv_s = (4 * np.pi * (m / (2 * np.pi * kB * T))**1.5
                * speed**2 * np.exp(-m * speed**2 / (2 * kB * T)))
        ax.axvline(speed, color=col, linestyle="--", linewidth=1.5, alpha=0.8)
        ax.text(speed, fv_s * 1.04, f" {lbl}\\n {speed:.0f} m/s",
                color=col, fontsize=8.5, va="bottom")

ax.set_xlabel("Speed  v  (m/s)", fontsize=11)
ax.set_ylabel(r"$f(v)$  (s m$^{-1}$)", fontsize=11)
ax.set_title("Maxwell–Boltzmann Speed Distribution", fontsize=12)
ax.legend(fontsize=9)
ax.grid(True, alpha=0.35)
plt.tight_layout()
plt.gcf()
"""
    s.set(9, 0, "Plot cell")
    s.fmt(9, 0, bold=True, font_color=PALETTE["header"])
    s.formula(10, 0, py_plot)
    s.fmt(10, 0, bg=PALETTE["band"], font_family="Courier New", font_size=9)

    # ── Python cell 2: return characteristic speeds ───────────────────
    py_speeds = """\
=PY
import numpy as np

kB = 1.380649e-23
u  = 1.66053906660e-27

T   = float(ks("B5"))
m_u = float(ks("B6"))
m   = m_u * u

v_p   = np.sqrt(2 * kB * T / m)
v_avg = np.sqrt(8 * kB * T / (np.pi * m))
v_rms = np.sqrt(3 * kB * T / m)

[
    ["v_p   (most probable, m/s)", round(v_p,   2)],
    ["v_avg (mean speed, m/s)",    round(v_avg, 2)],
    ["v_rms (RMS speed, m/s)",     round(v_rms, 2)],
]
"""
    s.set(9, 4, "Characteristic speeds")
    s.fmt(9, 4, bold=True, font_color=PALETTE["header"])
    s.formula(10, 4, py_speeds)
    s.fmt(10, 4, bg=PALETTE["band_alt"], font_family="Courier New", font_size=9)
    s.col_width(4, 220)
    s.col_width(5, 130)

    wb.save(OUT_PATH)
    return OUT_PATH


if __name__ == "__main__":
    print("Wrote", build())
