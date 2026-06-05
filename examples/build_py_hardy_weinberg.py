"""Build "Hardy-Weinberg Equilibrium" Python-cell example for KherveSheet.

Demonstrates =PY cells: reads allele frequency p from the grid and
plots genotype frequencies p², 2pq, q² as a function of p (0..1).
Also shows the frequency at the user's chosen p in a summary panel.

Run:  python examples/build_py_hardy_weinberg.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ksheet_author import Workbook, PALETTE

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "examples", "python", "Biology",
                   "Hardy-Weinberg.ksheet")


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=12)
    s = wb.add_sheet("Hardy-Weinberg")

    # Title
    s.title_block("Hardy-Weinberg Equilibrium",
                  "Genotype frequencies: AA = p², Aa = 2pq, aa = q²  (q = 1−p)")

    # Input parameters
    s.set(3, 0, "Parameter")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    s.set(4, 0, "Allele frequency p  (0 < p < 1)")
    s.fmt(4, 0, align="left")
    s.set(4, 1, 0.3)
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.box(4, 0, 4, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 230)
    s.col_width(1, 100)

    s.note(4, 1,
           "Change p (between 0 and 1) and press Ctrl+Enter on the =PY "
           "cell below. q is computed automatically as 1−p.",
           kind="note")

    # Summary panel: genotype frequencies at user's p
    s.set(3, 3, "Frequencies at chosen p")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"])

    py_q = (
        "=PY\n"
        "p = ks('B5')\n"
        "round(1 - p, 4)"
    )
    s.set(4, 3, "q = 1 − p:")
    s.fmt(4, 3, align="left")
    s.formula(4, 4, py_q)
    s.fmt(4, 4, bg=PALETTE["band"], align="center", bold=True,
          number_format="0.0000")

    py_AA = (
        "=PY\n"
        "p = ks('B5')\n"
        "round(p ** 2, 4)"
    )
    s.set(5, 3, "f(AA) = p²:")
    s.fmt(5, 3, align="left")
    s.formula(5, 4, py_AA)
    s.fmt(5, 4, bg=PALETTE["good"], align="center", bold=True,
          number_format="0.0000")

    py_Aa = (
        "=PY\n"
        "p = ks('B5')\n"
        "q = 1 - p\n"
        "round(2 * p * q, 4)"
    )
    s.set(6, 3, "f(Aa) = 2pq:")
    s.fmt(6, 3, align="left")
    s.formula(6, 4, py_Aa)
    s.fmt(6, 4, bg=PALETTE["warn"], align="center", bold=True,
          number_format="0.0000")

    py_aa = (
        "=PY\n"
        "p = ks('B5')\n"
        "q = 1 - p\n"
        "round(q ** 2, 4)"
    )
    s.set(7, 3, "f(aa) = q²:")
    s.fmt(7, 3, align="left")
    s.formula(7, 4, py_aa)
    s.fmt(7, 4, bg=PALETTE["bad"], align="center", bold=True,
          number_format="0.0000")

    s.box(4, 3, 7, 4, color=PALETTE["header"], width=1.0)
    s.col_width(3, 170)
    s.col_width(4, 100)

    # Main =PY plot cell
    py_plot = (
        "=PY\n"
        "import numpy as np\n"
        "import matplotlib.pyplot as plt\n"
        "p_input = ks('B5')\n"
        "p = np.linspace(0, 1, 500)\n"
        "q = 1 - p\n"
        "f_AA = p ** 2\n"
        "f_Aa = 2 * p * q\n"
        "f_aa = q ** 2\n"
        "fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))\n"
        "# Left: frequency curves vs p\n"
        "ax1 = axes[0]\n"
        "ax1.plot(p, f_AA, color='#4472c4', linewidth=2.5, label='f(AA) = p²')\n"
        "ax1.plot(p, f_Aa, color='#ed7d31', linewidth=2.5, label='f(Aa) = 2pq')\n"
        "ax1.plot(p, f_aa, color='#c00000', linewidth=2.5, label='f(aa) = q²')\n"
        "p_val = float(p_input)\n"
        "q_val = 1 - p_val\n"
        "ax1.axvline(p_val, color='#70ad47', linestyle='--', linewidth=1.5,\n"
        "            label=f'p = {p_val:.2f}')\n"
        "ax1.set_xlabel('Allele frequency p', fontsize=11)\n"
        "ax1.set_ylabel('Genotype frequency', fontsize=11)\n"
        "ax1.set_title('Hardy-Weinberg genotype frequencies', fontsize=12)\n"
        "ax1.legend(fontsize=9)\n"
        "ax1.grid(True, alpha=0.3)\n"
        "# Right: stacked area at chosen p (bar chart)\n"
        "ax2 = axes[1]\n"
        "vals = [p_val**2, 2*p_val*q_val, q_val**2]\n"
        "labels = [f'AA = {p_val**2:.3f}', f'Aa = {2*p_val*q_val:.3f}',\n"
        "          f'aa = {q_val**2:.3f}']\n"
        "colors = ['#4472c4', '#ed7d31', '#c00000']\n"
        "bars = ax2.bar(labels, vals, color=colors, edgecolor='white', width=0.5)\n"
        "ax2.set_ylim(0, 1)\n"
        "ax2.set_ylabel('Frequency', fontsize=11)\n"
        "ax2.set_title(f'Genotypes at p = {p_val:.2f}', fontsize=12)\n"
        "for bar, v in zip(bars, vals):\n"
        "    ax2.text(bar.get_x() + bar.get_width()/2, v + 0.02, f'{v:.3f}',\n"
        "             ha='center', va='bottom', fontsize=10, fontweight='bold')\n"
        "ax2.grid(True, alpha=0.3, axis='y')\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )

    s.set(9, 0, "Python cell below")
    s.fmt(9, 0, bold=True, font_color=PALETTE["header"])
    s.formula(10, 0, py_plot)
    s.fmt(10, 0, bg=PALETTE["band"], bold=True, align="center")
    s.set(10, 1, "← Python cell: genotype frequency curves + bar chart at chosen p")
    s.fmt(10, 1, italic=True, font_color="#555555")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb.save(OUT)
    return OUT


if __name__ == "__main__":
    print("Wrote", build())
