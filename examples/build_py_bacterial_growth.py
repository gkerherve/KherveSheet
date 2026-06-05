"""Build "Bacterial Growth" Python-cell example for KherveSheet.

Demonstrates =PY cells: reads N0 and doubling time from the grid and
plots exponential growth N(t) = N0 * 2^(t/t_d). A second =PY cell
spills a population-at-time table into the sheet.

Run:  python examples/build_py_bacterial_growth.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ksheet_author import Workbook, PALETTE

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "examples", "python", "Biology",
                   "Bacterial Growth.ksheet")


def build() -> str:
    wb = Workbook(min_rows=45, min_cols=14)
    s = wb.add_sheet("Bacterial Growth")

    # Title
    s.title_block("Bacterial Growth",
                  "N(t) = N₀ · 2^(t / t_d)  —  exponential growth model")

    # Input parameters
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Initial count N₀ (cells)", 100),
        ("Doubling time t_d (hours)", 0.5),
        ("Time span (hours)", 8.0),
    ]
    for i, (label, value) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, label)
        s.fmt(r, 0, align="left")
        s.set(r, 1, value)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 210)
    s.col_width(1, 100)

    s.note(4, 1,
           "Edit N0 (starting cells), doubling time (hours), or time span, "
           "then press Ctrl+Enter on the =PY cells to recompute.",
           kind="note")

    # Summary: number of doublings and final count
    s.set(3, 3, "Summary")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"])

    py_doublings = (
        "=PY\n"
        "t_d = ks('B6')\n"
        "T_max = ks('B7')\n"
        "doublings = T_max / t_d if t_d > 0 else float('nan')\n"
        "round(doublings, 2)"
    )
    s.set(4, 3, "Number of doublings:")
    s.fmt(4, 3, align="left")
    s.formula(4, 4, py_doublings)
    s.fmt(4, 4, bg=PALETTE["good"], align="center", bold=True,
          number_format="0.00")

    py_final = (
        "=PY\n"
        "import numpy as np\n"
        "N0 = ks('B5')\n"
        "t_d = ks('B6')\n"
        "T_max = ks('B7')\n"
        "N_final = N0 * 2 ** (T_max / t_d) if t_d > 0 else float('nan')\n"
        "round(N_final, 0)"
    )
    s.set(5, 3, "Final population N(T_max):")
    s.fmt(5, 3, align="left")
    s.formula(5, 4, py_final)
    s.fmt(5, 4, bg=PALETTE["band"], align="center", bold=True,
          number_format="0")

    s.box(4, 3, 5, 4, color=PALETTE["header"], width=1.0)
    s.col_width(3, 200)
    s.col_width(4, 120)

    # Main =PY plot cell
    py_plot = (
        "=PY\n"
        "import numpy as np\n"
        "import matplotlib.pyplot as plt\n"
        "N0 = ks('B5')\n"
        "t_d = ks('B6')\n"
        "T_max = ks('B7')\n"
        "t = np.linspace(0, T_max, 500)\n"
        "N = N0 * 2 ** (t / t_d)\n"
        "fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))\n"
        "# Linear scale\n"
        "ax1 = axes[0]\n"
        "ax1.plot(t, N, color='#4472c4', linewidth=2.5)\n"
        "ax1.set_xlabel('Time (hours)', fontsize=11)\n"
        "ax1.set_ylabel('Cell count N(t)', fontsize=11)\n"
        "ax1.set_title('Exponential growth (linear)', fontsize=12)\n"
        "ax1.grid(True, alpha=0.3)\n"
        "# Log scale\n"
        "ax2 = axes[1]\n"
        "ax2.semilogy(t, N, color='#c00000', linewidth=2.5)\n"
        "ax2.set_xlabel('Time (hours)', fontsize=11)\n"
        "ax2.set_ylabel('Cell count N(t)  [log scale]', fontsize=11)\n"
        "ax2.set_title('Exponential growth (log scale)', fontsize=12)\n"
        "ax2.grid(True, alpha=0.3, which='both')\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )

    s.set(8, 0, "Python cell below")
    s.fmt(8, 0, bold=True, font_color=PALETTE["header"])
    s.formula(9, 0, py_plot)
    s.fmt(9, 0, bg=PALETTE["band"], bold=True, align="center")
    s.set(9, 1, "← Python cell: linear and log-scale growth curves")
    s.fmt(9, 1, italic=True, font_color="#555555")

    # Second =PY cell: spills a time/population table (hourly snapshots)
    py_table = (
        "=PY\n"
        "import numpy as np\n"
        "N0 = ks('B5')\n"
        "t_d = ks('B6')\n"
        "T_max = ks('B7')\n"
        "# Hourly snapshots (or fewer if T_max < 1)\n"
        "n_pts = max(2, min(20, int(T_max) + 1))\n"
        "times = np.linspace(0, T_max, n_pts)\n"
        "pops  = N0 * 2 ** (times / t_d)\n"
        "# Return as a list of [t, N] pairs — spills downward\n"
        "[[round(float(ti), 3), round(float(ni), 1)] for ti, ni in zip(times, pops)]"
    )

    s.set(8, 6, "Time snapshot table")
    s.fmt(8, 6, bold=True, font_color=PALETTE["header"])
    s.set(9, 6, "t (h)")
    s.set(9, 7, "N(t)")
    s.fmt(9, 6, bold=True, bg=PALETTE["header"], font_color="#ffffff",
          align="center")
    s.fmt(9, 7, bold=True, bg=PALETTE["header"], font_color="#ffffff",
          align="center")
    s.formula(10, 6, py_table)
    s.fmt(10, 6, bg=PALETTE["band_alt"], align="center")
    s.set(10, 8, "← spills t and N(t) values")
    s.fmt(10, 8, italic=True, font_color="#555555")
    s.col_width(6, 80)
    s.col_width(7, 100)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb.save(OUT)
    return OUT


if __name__ == "__main__":
    print("Wrote", build())
