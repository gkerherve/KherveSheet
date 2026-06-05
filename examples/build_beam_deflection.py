"""Build the "Beam Deflection" Python-cell example .ksheet.

Cantilever beam with a point load at the free end. Inputs are set in
cells; a =PY cell reads them via ks() and plots the deflection curve.

Run:  python examples/build_beam_deflection.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE

OUTPUT = os.path.join(
    _REPO, "examples", "python", "Engineering", "Beam Deflection.ksheet"
)


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Beam Deflection")

    # Title
    s.title_block(
        "Beam Deflection",
        "Cantilever beam with a point load P at the free end — edit inputs, press Ctrl+Enter",
    )

    # Input parameters
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Beam length  L (m)", 2.0),
        ("Point load   P (N)", 1000.0),
        ("Flexural rigidity  EI (N·m²)", 50000.0),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=False)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 220)
    s.col_width(1, 110)

    # Derived summary cell (=PY returns the max deflection)
    s.set(8, 0, "Max tip deflection δ_max (m)")
    s.fmt(8, 0, bold=True)
    s.formula(
        8, 1,
        "=PY\n"
        "L = ks('B5'); P = ks('B6'); EI = ks('B7')\n"
        "round(P * L**3 / (3 * EI), 6)\n"
    )
    s.fmt(8, 1, bg=PALETTE["good"], bold=True, align="center", number_format="0.000000")
    s.box(8, 0, 8, 1, color=PALETTE["header"], width=1.5)

    # Note
    s.note(4, 1,
           "Edit L, P or EI here, then press Ctrl+Enter on the =PY plot "
           "cell (row 11) to recompute the deflection curve.",
           kind="note")

    # Instruction row
    s.set(10, 0, "Deflection plot  (=PY cell below — press Ctrl+Enter to refresh)")
    s.fmt(10, 0, bold=True, font_color=PALETTE["header"])

    # =PY plot cell
    py_code = (
        "=PY\n"
        "import numpy as np, matplotlib.pyplot as plt\n"
        "L  = ks('B5')\n"
        "P  = ks('B6')\n"
        "EI = ks('B7')\n"
        "x  = np.linspace(0, L, 300)\n"
        "# Cantilever deflection: y(x) = P/(6EI) * (3L x^2 - x^3)\n"
        "y  = (P / (6 * EI)) * (3 * L * x**2 - x**3)\n"
        "fig, ax = plt.subplots(figsize=(6, 4))\n"
        "ax.plot(x, y * 1000, color='#4472c4', linewidth=2.5, label='Deflection')\n"
        "ax.fill_between(x, y * 1000, alpha=0.15, color='#4472c4')\n"
        "ax.set_xlabel('Position along beam  x (m)')\n"
        "ax.set_ylabel('Deflection  y (mm)')\n"
        "ax.set_title('Cantilever Beam Deflection')\n"
        "ax.legend()\n"
        "ax.grid(True, linestyle='--', alpha=0.5)\n"
        "ax.invert_yaxis()\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )
    s.formula(11, 0, py_code)
    s.fmt(11, 0, bg="#f0f4ff", font_family="Consolas", font_size=9)

    # Second note
    s.note(11, 0,
           "The curve shows deflection in mm (positive = downward). "
           "δ(x) = P(3Lx² − x³) / (6EI).",
           kind="note")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    wb.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print("Wrote", build())
