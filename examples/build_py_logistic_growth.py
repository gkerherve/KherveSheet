"""Build "Logistic Population Growth" Python-cell example for KherveSheet.

Demonstrates =PY cells: reads r, K, N0 from the grid and plots the
logistic curve N(t) = K / (1 + ((K-N0)/N0) * exp(-r*t)).

Run:  python examples/build_py_logistic_growth.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ksheet_author import Workbook, PALETTE

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "examples", "python", "Biology",
                   "Logistic Population Growth.ksheet")


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=12)
    s = wb.add_sheet("Logistic Growth")

    # Title
    s.title_block("Logistic Population Growth",
                  "N(t) = K / (1 + ((K−N₀)/N₀) · exp(−r·t))")

    # Input parameters
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Growth rate r (per year)", "r", 0.4),
        ("Carrying capacity K", "K", 1000),
        ("Initial population N₀", "N0", 50),
        ("Time span (years)", "T_max", 30),
    ]
    for i, (label, _, value) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, label)
        s.fmt(r, 0, align="left", bold=False)
        s.set(r, 1, value)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.box(4, 0, 7, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 220)
    s.col_width(1, 100)

    s.note(4, 1,
           "Edit r (growth rate), K (carrying capacity), N0 (initial "
           "population) or T_max, then press Ctrl+Enter on the =PY cell "
           "in A10 to recompute the plot.", kind="note")

    # Summary =PY cell: carrying capacity utilisation text
    py_summary = (
        "=PY\n"
        "r_val = ks('B5')\n"
        "K_val = ks('B6')\n"
        "N0_val = ks('B7')\n"
        "T_max = ks('B8')\n"
        "import numpy as np\n"
        "# Time to reach 50% of K\n"
        "if r_val > 0 and K_val > N0_val:\n"
        "    t_half = np.log((K_val - N0_val) / N0_val) / r_val\n"
        "else:\n"
        "    t_half = float('nan')\n"
        "round(t_half, 2)"
    )
    s.set(3, 3, "Time to 50% K (years):")
    s.fmt(3, 3, bold=True, align="left")
    s.formula(3, 4, py_summary)
    s.fmt(3, 4, bg=PALETTE["good"], align="center", bold=True,
          number_format="0.00")
    s.col_width(3, 180)
    s.col_width(4, 100)
    s.box(3, 3, 3, 4, color=PALETTE["header"], width=1.0)

    # Main =PY plot cell
    py_plot = (
        "=PY\n"
        "import numpy as np\n"
        "import matplotlib.pyplot as plt\n"
        "r_val = ks('B5')\n"
        "K_val = ks('B6')\n"
        "N0_val = ks('B7')\n"
        "T_max = ks('B8')\n"
        "t = np.linspace(0, T_max, 500)\n"
        "N = K_val / (1 + ((K_val - N0_val) / N0_val) * np.exp(-r_val * t))\n"
        "fig, ax = plt.subplots(figsize=(7, 4.5))\n"
        "ax.plot(t, N, color='#4472c4', linewidth=2.5, label='N(t)')\n"
        "ax.axhline(K_val, color='#ed7d31', linestyle='--', linewidth=1.5,\n"
        "           label=f'K = {K_val:.0f}')\n"
        "ax.axhline(K_val / 2, color='#70ad47', linestyle=':', linewidth=1.2,\n"
        "           label=f'K/2 = {K_val/2:.0f}')\n"
        "ax.set_xlabel('Time (years)', fontsize=11)\n"
        "ax.set_ylabel('Population N(t)', fontsize=11)\n"
        "ax.set_title('Logistic Population Growth', fontsize=13)\n"
        "ax.legend(fontsize=9)\n"
        "ax.grid(True, alpha=0.3)\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )
    s.set(9, 0, "Python cell below")
    s.fmt(9, 0, bold=True, font_color=PALETTE["header"])
    s.formula(10, 0, py_plot)
    s.fmt(10, 0, bg=PALETTE["band"], bold=True, align="center")
    s.set(10, 1, "← Python cell: edit inputs above, then Ctrl+Enter here")
    s.fmt(10, 1, italic=True, font_color="#555555")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb.save(OUT)
    return OUT


if __name__ == "__main__":
    print("Wrote", build())
