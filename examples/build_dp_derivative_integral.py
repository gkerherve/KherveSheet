"""Build "Derivative and Integral.ksheet" — data-processing example.

x and y columns. The =PY cell computes the numerical first derivative
(np.gradient) and the cumulative integral (scipy.integrate.cumulative_trapezoid),
writes both back, and plots all three on stacked subplots.

Run:  python examples/build_dp_derivative_integral.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE


def build() -> str:
    N = 100

    x = np.linspace(0, 4 * np.pi, N)
    y = np.sin(x) + 0.4 * np.sin(3 * x)

    wb = Workbook(min_rows=N + 12, min_cols=14)
    s = wb.add_sheet("Deriv and Integral")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block(
        "Derivative and Integral",
        "Numerical dy/dx (np.gradient) and cumulative integral (cumulative_trapezoid)",
    )

    # ── Input parameters ───────────────────────────────────────────────
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    s.set(4, 0, "Number of points N")
    s.set(4, 1, N)
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0")
    s.box(4, 0, 4, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 180)
    s.col_width(1, 80)

    s.note(
        4, 1,
        "N controls how many sample points are used. "
        "Press Ctrl+Enter on the =PY cell to recompute derivative "
        "and integral — written to columns C and D.",
        kind="note",
    )

    # ── Data columns A (x) and B (y) ───────────────────────────────────
    data_header_row = 6
    data_start = 7  # 0-based row of first data row

    headers = ["x", "y", "dy_dx", "cum_integral"]
    for j, h in enumerate(headers):
        s.set(data_header_row, j, h)
        s.fmt(data_header_row, j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    for c in range(4):
        s.col_width(c, 95)

    for i in range(N):
        r = data_start + i
        s.set(r, 0, round(float(x[i]), 5))
        s.set(r, 1, round(float(y[i]), 5))
        band = PALETTE["band_alt"] if i % 2 else None
        for c in range(2):
            kw = dict(align="right", number_format="0.0000")
            if band:
                kw["bg"] = band
            s.fmt(r, c, **kw)

    s.box(data_header_row, 0, data_start + N - 1, 3,
          color=PALETTE["header"], width=1.0)
    s.designate(0, "X")
    s.designate(1, "Y")
    s.designate(2, "Y")
    s.designate(3, "Y")

    # ── =PY cell in column F, row 4 ────────────────────────────────────
    sheet_data_first = data_start + 1   # 1-based: 8
    sheet_data_last  = data_start + N   # 1-based: 107

    py_code = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "from scipy.integrate import cumulative_trapezoid",
        f"x = ks('A{sheet_data_first}:A{sheet_data_last}')",
        f"y = ks('B{sheet_data_first}:B{sheet_data_last}')",
        "x = x[np.isfinite(x)]",
        "y = y[np.isfinite(y)]",
        "n = min(len(x), len(y))",
        "x, y = x[:n], y[:n]",
        "# Numerical derivative",
        "dydx = np.gradient(y, x)",
        "# Cumulative integral; prepend 0 so length matches",
        "integral = np.concatenate([[0.0], cumulative_trapezoid(y, x)])",
        f"ks_set('C{sheet_data_first}', dydx.tolist())",
        f"ks_set('D{sheet_data_first}', integral.tolist())",
        "fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 8), sharex=True)",
        "ax1.plot(x, y,        color='#4472c4', linewidth=2.0, label='y(x)')",
        "ax1.set_ylabel('y', fontsize=10)",
        "ax1.legend(fontsize=9)",
        "ax1.grid(True, alpha=0.3)",
        "ax2.plot(x, dydx,    color='#ed7d31', linewidth=2.0, label='dy/dx')",
        "ax2.axhline(0, color='#888', linewidth=0.6, linestyle=':')",
        "ax2.set_ylabel('dy/dx', fontsize=10)",
        "ax2.legend(fontsize=9)",
        "ax2.grid(True, alpha=0.3)",
        "ax3.plot(x, integral, color='#70ad47', linewidth=2.0, label=r'$\\int y\\,dx$')",
        "ax3.set_xlabel('x', fontsize=10)",
        "ax3.set_ylabel('Integral', fontsize=10)",
        "ax3.legend(fontsize=9)",
        "ax3.grid(True, alpha=0.3)",
        "plt.suptitle('Derivative and Integral', fontsize=12, fontweight='bold')",
        "plt.tight_layout()",
        "plt.gcf()",
    ])

    py_row = 4
    s.formula(py_row, 5, py_code)
    s.fmt(py_row, 5, font_family="Consolas", font_size=9, wrap=True)
    s.col_width(5, 50)

    s.note(
        py_row, 5,
        "=PY cell: computes np.gradient for dy/dx and "
        "cumulative_trapezoid for the integral; writes results "
        "to columns C and D, then plots all three.",
        kind="note",
    )

    # ── LaTeX equation ─────────────────────────────────────────────────
    s.equation(
        r"\frac{dy}{dx} \approx \frac{y_{i+1} - y_{i-1}}{x_{i+1} - x_{i-1}}",
        at=(520, 10), fontsize=16, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(310, 48),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out_dir = os.path.join(_REPO, "examples", "python", "Data Processing")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Derivative and Integral.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
