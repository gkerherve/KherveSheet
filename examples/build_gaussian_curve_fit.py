"""Build "Gaussian Curve Fit" Python-cell example .ksheet.

Input data: columns x and noisy y with a Gaussian peak in cells.
=PY fits a Gaussian with scipy.optimize.curve_fit, plots data + fitted curve,
and a second =PY cell returns the fitted amplitude, centre, and width.

Run:  python examples/build_gaussian_curve_fit.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ksheet_author import Workbook, PALETTE


def build() -> str:
    rng = np.random.default_rng(55)
    # Ground truth: amplitude=3.0, centre=5.0, width=1.2
    x_data = np.linspace(0, 10, 30)
    y_data = 3.0 * np.exp(-0.5 * ((x_data - 5.0) / 1.2) ** 2) + rng.normal(0, 0.15, len(x_data))

    wb = Workbook(min_rows=44, min_cols=14)
    s = wb.add_sheet("Gaussian Fit")

    # Title
    s.title_block(
        "Gaussian Curve Fit",
        "Fit  A * exp(-0.5 * ((x - x0) / sigma)^2)  to noisy peak data",
    )

    # Instructions
    s.set(3, 0, "Data  (x and y columns -- edit values to refit)")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    s.col_width(0, 110)
    s.col_width(1, 110)
    s.col_width(2, 110)

    # Data table header
    s.set(4, 0, "x")
    s.set(4, 1, "y (noisy)")
    s.fmt(4, 0, bold=True, bg=PALETTE["header"], font_color=PALETTE["header_text"], align="center")
    s.fmt(4, 1, bold=True, bg=PALETTE["header"], font_color=PALETTE["header_text"], align="center")

    n = len(x_data)
    for i in range(n):
        r = 5 + i
        s.set(r, 0, round(float(x_data[i]), 3))
        s.set(r, 1, round(float(y_data[i]), 4))
        if i % 2 == 1:
            s.fmt(r, 0, bg=PALETTE["band_alt"])
            s.fmt(r, 1, bg=PALETTE["band_alt"])
        s.fmt(r, 0, align="right", number_format="0.000")
        s.fmt(r, 1, align="right", number_format="0.0000")

    s.box(4, 0, 4 + n, 1, color=PALETTE["header"], width=1.0)

    row_start_a1 = 6
    row_end_a1 = 5 + n

    s.note(
        4, 0,
        f"Data lives in A{row_start_a1}:B{row_end_a1}. "
        "Edit y values then Ctrl+Enter the Python cells (D5, D8) to refit.",
        kind="note",
    )

    # Python cell: fit and plot
    plot_code = "\n".join([
        "=PY",
        "import numpy as np",
        "from scipy.optimize import curve_fit",
        "import matplotlib.pyplot as plt",
        f"x = ks('A{row_start_a1}:A{row_end_a1}')",
        f"y = ks('B{row_start_a1}:B{row_end_a1}')",
        "def gaussian(x, A, x0, sigma):",
        "    return A * np.exp(-0.5 * ((x - x0) / sigma)**2)",
        "# Initial guess: A from max, centre from argmax, width=1",
        "p0 = [float(y.max()), float(x[y.argmax()]), 1.0]",
        "popt, _ = curve_fit(gaussian, x, y, p0=p0)",
        "A_fit, x0_fit, sigma_fit = popt",
        "x_fine = np.linspace(float(x.min()), float(x.max()), 300)",
        "y_fit  = gaussian(x_fine, A_fit, x0_fit, sigma_fit)",
        "fig, ax = plt.subplots(figsize=(6, 4))",
        "ax.scatter(x, y, color='#4472c4', s=30, zorder=3, label='Data')",
        "ax.plot(x_fine, y_fit, 'r-', linewidth=2,",
        "        label=f'Fit: A={A_fit:.3f}, x0={x0_fit:.3f}, s={sigma_fit:.3f}')",
        "ax.set_xlabel('x')",
        "ax.set_ylabel('y')",
        "ax.set_title('Gaussian Curve Fit')",
        "ax.legend()",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(4, 3, plot_code)
    s.set(4, 5, "<-- Plot (Ctrl+Enter to rerun)")
    s.fmt(4, 5, italic=True, font_color="#777777")

    # Python cell: return fit parameters
    params_code = "\n".join([
        "=PY",
        "import numpy as np",
        "from scipy.optimize import curve_fit",
        f"x = ks('A{row_start_a1}:A{row_end_a1}')",
        f"y = ks('B{row_start_a1}:B{row_end_a1}')",
        "def gaussian(x, A, x0, sigma):",
        "    return A * np.exp(-0.5 * ((x - x0) / sigma)**2)",
        "p0 = [float(y.max()), float(x[y.argmax()]), 1.0]",
        "popt, pcov = curve_fit(gaussian, x, y, p0=p0)",
        "A_fit, x0_fit, sigma_fit = popt",
        "perr = np.sqrt(np.diag(pcov))",
        "y_pred = gaussian(x, *popt)",
        "ss_res = float(np.sum((y - y_pred)**2))",
        "ss_tot = float(np.sum((y - np.mean(y))**2))",
        "r2 = 1.0 - ss_res / ss_tot",
        "[",
        "    ['Parameter', 'Fitted value', 'Std error'],",
        "    ['Amplitude  A',  round(float(A_fit), 5),     round(float(perr[0]), 5)],",
        "    ['Centre  x0',    round(float(x0_fit), 5),    round(float(perr[1]), 5)],",
        "    ['Width  sigma',  round(float(sigma_fit), 5), round(float(perr[2]), 5)],",
        "    ['R-squared',     round(r2, 5),               ''],",
        "]",
    ])
    s.formula(10, 3, params_code)
    s.note(
        10, 3,
        "Spills: fitted amplitude, centre, width, and R-squared.",
        kind="note",
    )

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "python", "Statistics", "Gaussian Curve Fit.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())