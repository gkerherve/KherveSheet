"""Build "Wave Interference.ksheet" — a Python-cell physics example.

Two sinusoidal waves with independent amplitudes, wavelengths, and phase
offsets are plotted together with their superposition.  Inputs are
labelled cells; the =PY cell reads them via ks() and builds the figure.

Run:  python examples/build_py_wave_interference.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE  # noqa: E402

OUT_PATH = os.path.join(
    _REPO, "examples", "python", "Physics", "Wave Interference.ksheet"
)


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Interference")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Wave Interference",
        "y(x) = A₁ sin(2π x/λ₁ + φ₁)  +  A₂ sin(2π x/λ₂ + φ₂)",
    )

    # ── Input parameters ──────────────────────────────────────────────
    s.set(3, 0, "Wave 1")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    s.set(3, 2, "Wave 2")
    s.fmt(3, 2, bold=True, font_color="#4472c4")

    # Wave 1 (column A/B, rows 5–7)
    wave1 = [
        ("Amplitude A₁",       1.0),   # B5
        ("Wavelength λ₁ (m)",  1.0),   # B6
        ("Phase φ₁ (degrees)", 0.0),   # B7
    ]
    for i, (lbl, val) in enumerate(wave1):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.0)

    # Wave 2 (column C/D, rows 5–7)
    wave2 = [
        ("Amplitude A₂",       0.8),   # D5
        ("Wavelength λ₂ (m)",  1.2),   # D6
        ("Phase φ₂ (degrees)", 45.0),  # D7
    ]
    for i, (lbl, val) in enumerate(wave2):
        r = 4 + i
        s.set(r, 2, lbl)
        s.set(r, 3, val)
        s.fmt(r, 2, bold=True)
        s.fmt(r, 3, bg=PALETTE["band"], align="center", number_format="0.00")
    s.box(4, 2, 6, 3, color="#4472c4", width=1.0)

    # x-axis control
    s.set(7, 0, "x range: 0 to (m)")
    s.set(7, 1, 6.0)           # B8
    s.fmt(7, 0, bold=True)
    s.fmt(7, 1, bg=PALETTE["warn"], align="center", number_format="0.0")

    s.col_width(0, 190)
    s.col_width(1, 110)
    s.col_width(2, 190)
    s.col_width(3, 110)

    # ── Sticky note ───────────────────────────────────────────────────
    s.note(
        4, 1,
        "Set λ₁ = λ₂ for pure constructive/destructive interference.\n"
        "Try A₁=1, λ₁=1, φ₁=0  vs  A₂=1, λ₂=1, φ₂=180 → complete cancellation.\n"
        "Or λ₁=1, λ₂=1.1 to see beating.\n"
        "Press Ctrl+Enter on the Python cell (A10) to replot.",
        kind="note",
    )

    # ── Python cell: plot both waves + sum ────────────────────────────
    py_plot = """\
=PY
import numpy as np
import matplotlib.pyplot as plt

# Wave 1
A1  = float(ks("B5"))
lam1 = float(ks("B6"))
phi1 = np.radians(float(ks("B7")))

# Wave 2
A2  = float(ks("D5"))
lam2 = float(ks("D6"))
phi2 = np.radians(float(ks("D7")))

x_max = float(ks("B8"))
x = np.linspace(0, x_max, 1000)

y1  = A1 * np.sin(2 * np.pi * x / lam1 + phi1)
y2  = A2 * np.sin(2 * np.pi * x / lam2 + phi2)
y12 = y1 + y2

fig, axes = plt.subplots(3, 1, figsize=(7, 6), sharex=True)

axes[0].plot(x, y1, color="#e05c00", linewidth=1.8)
axes[0].set_ylabel(r"$y_1$", fontsize=11)
axes[0].set_title(
    f"Wave 1:  A={A1:.2f}, λ={lam1:.2f} m, φ={np.degrees(phi1):.1f}°",
    fontsize=10)
axes[0].axhline(0, color="#888", linewidth=0.6)
axes[0].grid(True, alpha=0.3)

axes[1].plot(x, y2, color="#4472c4", linewidth=1.8)
axes[1].set_ylabel(r"$y_2$", fontsize=11)
axes[1].set_title(
    f"Wave 2:  A={A2:.2f}, λ={lam2:.2f} m, φ={np.degrees(phi2):.1f}°",
    fontsize=10)
axes[1].axhline(0, color="#888", linewidth=0.6)
axes[1].grid(True, alpha=0.3)

axes[2].plot(x, y12, color="#2e8b57", linewidth=2.2, label="Sum")
axes[2].fill_between(x, y12, alpha=0.13, color="#2e8b57")
axes[2].axhline(0, color="#888", linewidth=0.6)
axes[2].set_ylabel(r"$y_1 + y_2$", fontsize=11)
axes[2].set_xlabel("x  (m)", fontsize=11)
axes[2].set_title("Superposition", fontsize=10)
axes[2].grid(True, alpha=0.3)

fig.suptitle("Wave Interference", fontsize=13, fontweight="bold", y=1.01)
plt.tight_layout()
plt.gcf()
"""
    s.set(9, 0, "Python cell — interference plot")
    s.fmt(9, 0, bold=True, font_color=PALETTE["header"])
    s.formula(10, 0, py_plot)
    s.fmt(10, 0, bg=PALETTE["band"], font_family="Courier New", font_size=9)

    # ── Python cell 2: summary (max amplitude, beat period if near) ───
    py_summary = """\
=PY
import numpy as np

A1   = float(ks("B5"));  lam1 = float(ks("B6"))
A2   = float(ks("D5"));  lam2 = float(ks("D6"))

max_constructive = A1 + A2
max_destructive  = abs(A1 - A2)

# Beat wavelength (only meaningful when lambdas are close)
if abs(lam1 - lam2) > 1e-9:
    lam_beat = (lam1 * lam2) / abs(lam1 - lam2)
else:
    lam_beat = float("inf")

[
    ["Max constructive amplitude",  round(max_constructive, 4)],
    ["Max destructive amplitude",   round(max_destructive,  4)],
    ["Beat wavelength (m)",         round(lam_beat, 4) if lam_beat < 1e6 else "inf"],
]
"""
    s.set(9, 5, "Summary")
    s.fmt(9, 5, bold=True, font_color=PALETTE["header"])
    s.formula(10, 5, py_summary)
    s.fmt(10, 5, bg=PALETTE["band_alt"], font_family="Courier New", font_size=9)
    s.col_width(5, 230)
    s.col_width(6, 130)

    wb.save(OUT_PATH)
    return OUT_PATH


if __name__ == "__main__":
    print("Wrote", build())
