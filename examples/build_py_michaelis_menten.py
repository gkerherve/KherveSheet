"""Build "Michaelis-Menten Kinetics" Python-cell example for KherveSheet.

Demonstrates =PY cells: reads Vmax and Km from the grid and plots
reaction velocity v = Vmax·[S] / (Km + [S]) vs substrate concentration.

Run:  python examples/build_py_michaelis_menten.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ksheet_author import Workbook, PALETTE

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "examples", "python", "Biology",
                   "Michaelis-Menten Kinetics.ksheet")


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=12)
    s = wb.add_sheet("MM Kinetics")

    # Title
    s.title_block("Michaelis-Menten Kinetics",
                  "v = Vmax·[S] / (Km + [S])  —  enzyme reaction velocity")

    # Input parameters
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Vmax (µmol/min)", 10.0),
        ("Km (µM)", 2.5),
        ("Max [S] to plot (µM)", 20.0),
    ]
    for i, (label, value) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, label)
        s.fmt(r, 0, align="left")
        s.set(r, 1, value)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 200)
    s.col_width(1, 100)

    s.note(4, 1,
           "Edit Vmax (maximum velocity), Km (Michaelis constant) or the "
           "substrate range, then press Ctrl+Enter on the =PY cell below "
           "to replot.", kind="note")

    # Summary panel: v at [S]=Km (should be Vmax/2), and at [S]=10*Km
    s.set(3, 3, "Key values")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"])

    py_half = (
        "=PY\n"
        "Vmax = ks('B5')\n"
        "Km = ks('B6')\n"
        "# At [S]=Km, v = Vmax/2\n"
        "round(Vmax / 2, 4)"
    )
    s.set(4, 3, "v at [S]=Km  (= Vmax/2):")
    s.fmt(4, 3, align="left")
    s.formula(4, 4, py_half)
    s.fmt(4, 4, bg=PALETTE["good"], align="center", bold=True,
          number_format="0.0000")

    py_sat = (
        "=PY\n"
        "Vmax = ks('B5')\n"
        "Km = ks('B6')\n"
        "import numpy as np\n"
        "S_sat = 10 * Km\n"
        "v_sat = Vmax * S_sat / (Km + S_sat)\n"
        "round(v_sat, 4)"
    )
    s.set(5, 3, "v at [S]=10·Km:")
    s.fmt(5, 3, align="left")
    s.formula(5, 4, py_sat)
    s.fmt(5, 4, bg=PALETTE["band"], align="center", bold=True,
          number_format="0.0000")

    s.box(4, 3, 5, 4, color=PALETTE["header"], width=1.0)
    s.col_width(3, 180)
    s.col_width(4, 100)

    # Main =PY plot cell
    py_plot = (
        "=PY\n"
        "import numpy as np\n"
        "import matplotlib.pyplot as plt\n"
        "Vmax = ks('B5')\n"
        "Km = ks('B6')\n"
        "S_max = ks('B7')\n"
        "S = np.linspace(0, S_max, 500)\n"
        "v = Vmax * S / (Km + S)\n"
        "# Lineweaver-Burk points for annotation\n"
        "S_lw = np.linspace(S_max / 20, S_max, 200)\n"
        "fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))\n"
        "# Left: MM curve\n"
        "ax = axes[0]\n"
        "ax.plot(S, v, color='#4472c4', linewidth=2.5, label='v([S])')\n"
        "ax.axhline(Vmax, color='#ed7d31', linestyle='--', linewidth=1.5,\n"
        "           label=f'Vmax = {Vmax:.2f}')\n"
        "ax.axhline(Vmax / 2, color='#70ad47', linestyle=':', linewidth=1.2,\n"
        "           label=f'Vmax/2 = {Vmax/2:.2f}')\n"
        "ax.axvline(Km, color='#70ad47', linestyle=':', linewidth=1.2,\n"
        "           label=f'Km = {Km:.2f} µM')\n"
        "ax.set_xlabel('[S] (µM)', fontsize=11)\n"
        "ax.set_ylabel('v (µmol/min)', fontsize=11)\n"
        "ax.set_title('Michaelis-Menten', fontsize=12)\n"
        "ax.legend(fontsize=8)\n"
        "ax.grid(True, alpha=0.3)\n"
        "# Right: Lineweaver-Burk (double-reciprocal)\n"
        "ax2 = axes[1]\n"
        "inv_S = 1 / S_lw\n"
        "inv_v = (Km + S_lw) / (Vmax * S_lw)\n"
        "ax2.plot(inv_S, inv_v, color='#c00000', linewidth=2.0,\n"
        "         label='Lineweaver-Burk')\n"
        "ax2.set_xlabel('1/[S]  (µM⁻¹)', fontsize=11)\n"
        "ax2.set_ylabel('1/v  (min/µmol)', fontsize=11)\n"
        "ax2.set_title('Lineweaver-Burk', fontsize=12)\n"
        "ax2.legend(fontsize=8)\n"
        "ax2.grid(True, alpha=0.3)\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )

    s.set(9, 0, "Python cell below")
    s.fmt(9, 0, bold=True, font_color=PALETTE["header"])
    s.formula(10, 0, py_plot)
    s.fmt(10, 0, bg=PALETTE["band"], bold=True, align="center")
    s.set(10, 1, "← Python cell: shows MM curve + Lineweaver-Burk plot")
    s.fmt(10, 1, italic=True, font_color="#555555")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb.save(OUT)
    return OUT


if __name__ == "__main__":
    print("Wrote", build())
