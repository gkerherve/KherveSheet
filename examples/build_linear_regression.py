"""Build "Linear Regression" Python-cell example .ksheet.

Input data: columns of x and y values in cells.
=PY fits a straight line (np.polyfit), plots data + fit line.
Second =PY cell returns slope, intercept and R-squared.

Run:  python examples/build_linear_regression.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ksheet_author import Workbook, PALETTE


def build() -> str:
    rng = np.random.default_rng(7)
    # Ground truth: y = 2.5x + 1.0 + noise
    x_data = np.linspace(0, 10, 20)
    y_data = 2.5 * x_data + 1.0 + rng.normal(0, 1.5, len(x_data))

    wb = Workbook(min_rows=44, min_cols=14)
    s = wb.add_sheet("Linear Regression")

    # Title
    s.title_block(
        "Linear Regression",
        "Fit a straight line y = mx + b to data using least squares",
    )

    # Instructions
    s.set(3, 0, "Data  (x and y columns -- edit values to update the fit)")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    s.col_width(0, 120)
    s.col_width(1, 120)
    s.col_width(2, 120)

    # Data table header
    s.set(4, 0, "x")
    s.set(4, 1, "y")
    s.fmt(4, 0, bold=True, bg=PALETTE["header"], font_color=PALETTE["header_text"], align="center")
    s.fmt(4, 1, bold=True, bg=PALETTE["header"], font_color=PALETTE["header_text"], align="center")

    n = len(x_data)
    for i in range(n):
        r = 5 + i
        s.set(r, 0, round(float(x_data[i]), 3))
        s.set(r, 1, round(float(y_data[i]), 3))
        if i % 2 == 1:
            s.fmt(r, 0, bg=PALETTE["band_alt"])
            s.fmt(r, 1, bg=PALETTE["band_alt"])
        s.fmt(r, 0, align="right", number_format="0.000")
        s.fmt(r, 1, align="right", number_format="0.000")

    s.box(4, 0, 4 + n, 1, color=PALETTE["header"], width=1.0)

    # Row bounds in A1 notation: data is rows 6 to (5+n)
    row_start_a1 = 6
    row_end_a1 = 5 + n

    s.note(
        4, 0,
        f"Data lives in A{row_start_a1}:B{row_end_a1}. "
        "Edit x/y values then Ctrl+Enter the Python cells (D5, D7) to refit.",
        kind="note",
    )

    # Python cell: plot (col D = col index 3, row 4 = 0-based)
    plot_code = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        f"x = ks('A{row_start_a1}:A{row_end_a1}')",
        f"y = ks('B{row_start_a1}:B{row_end_a1}')",
        "coeffs = np.polyfit(x, y, 1)",
        "m, b = float(coeffs[0]), float(coeffs[1])",
        "x_fit = np.linspace(float(x.min()), float(x.max()), 200)",
        "y_fit = m * x_fit + b",
        "fig, ax = plt.subplots(figsize=(6, 4))",
        "ax.scatter(x, y, color='#4472c4', s=40, zorder=3, label='Data')",
        "ax.plot(x_fit, y_fit, 'r-', linewidth=2, label=f'Fit: y = {m:.3f}x + {b:.3f}')",
        "ax.set_xlabel('x')",
        "ax.set_ylabel('y')",
        "ax.set_title('Linear Regression')",
        "ax.legend()",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(4, 3, plot_code)
    s.set(4, 5, "<-- Plot (Ctrl+Enter to rerun)")
    s.fmt(4, 5, italic=True, font_color="#777777")

    # Python cell: return slope, intercept, R^2
    stats_code = "\n".join([
        "=PY",
        "import numpy as np",
        f"x = ks('A{row_start_a1}:A{row_end_a1}')",
        f"y = ks('B{row_start_a1}:B{row_end_a1}')",
        "coeffs = np.polyfit(x, y, 1)",
        "m, b = float(coeffs[0]), float(coeffs[1])",
        "y_pred = m * x + b",
        "ss_res = float(np.sum((y - y_pred)**2))",
        "ss_tot = float(np.sum((y - np.mean(y))**2))",
        "r2 = 1.0 - ss_res / ss_tot",
        "[",
        "    ['Parameter', 'Value'],",
        "    ['Slope  m',       round(m,  5)],",
        "    ['Intercept  b',   round(b,  5)],",
        "    ['R-squared  R2',  round(r2, 5)],",
        "]",
    ])
    s.formula(10, 3, stats_code)
    s.note(
        10, 3,
        "Spills: slope, intercept, and R-squared of the fit.",
        kind="note",
    )

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "python", "Statistics", "Linear Regression.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())