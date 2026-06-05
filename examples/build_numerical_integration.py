"""Build "Numerical Integration.ksheet" — a =PY science example.

Demonstrates trapezoidal and Simpson's rule integration on user-supplied
x/y data.  The Python cell reads the data from the grid via ks(), computes
both integrals, and plots the curve with the area shaded.

Run:  python examples/build_numerical_integration.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

from ksheet_author import Workbook, PALETTE  # noqa: E402


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=14)
    s = wb.add_sheet("Integration")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block(
        "Numerical Integration",
        "Trapezoidal and Simpson's rule on sampled (x, y) data",
    )

    # ── Instructions label ─────────────────────────────────────────────
    s.set(2, 0, "Data table  (edit x and y values — Python reads them via ks)")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    # ── Input data: x and y columns ────────────────────────────────────
    # 20 evenly-spaced points of sin(x) over [0, 2π].  User may replace.
    n = 20
    x_vals = np.linspace(0, 2 * np.pi, n)
    y_vals = np.sin(x_vals)

    # Table header at row 3 (0-based) = A4:B4 in 1-based.
    # Data rows 4..23 (0-based) = A5:B24 in 1-based.
    s.set(3, 0, "x")
    s.set(3, 1, "y = sin(x)")
    s.fmt(3, 0, bold=True, bg=PALETTE["header"], font_color=PALETTE["header_text"], align="center")
    s.fmt(3, 1, bold=True, bg=PALETTE["header"], font_color=PALETTE["header_text"], align="center")

    for i, (xv, yv) in enumerate(zip(x_vals, y_vals)):
        r = 4 + i   # 0-based row 4..23 → 1-based A5..A24
        s.set(r, 0, round(float(xv), 5))
        s.set(r, 1, round(float(yv), 6))
        band = PALETTE["band_alt"] if i % 2 else None
        s.fmt(r, 0, align="right", number_format="0.00000", bg=band or "")
        s.fmt(r, 1, align="right", number_format="0.000000", bg=band or "")

    s.box(3, 0, 3 + n, 1, color=PALETTE["header"], width=1.0)
    s.col_width(0, 90)
    s.col_width(1, 110)

    # ── Result labels (Python cell spills into E4:E5 = col 4, rows 3:4) ─
    # Labels at D5:D6 (0-based rows 4:5, col 3)
    s.set(3, 3, "Results")
    s.fmt(3, 3, bold=True, font_color=PALETTE["accent"])
    s.set(4, 3, "Trapezoidal integral")
    s.set(5, 3, "Simpson's integral")
    s.fmt(4, 3, bold=True)
    s.fmt(5, 3, bold=True)
    s.col_width(3, 160)
    s.col_width(4, 120)

    # ── Python cell: compute integrals ─────────────────────────────────
    # Placed at row 3, col 4 (0-based) = E4 in 1-based.
    # Data is at A5:A24, B5:B24 (0-based rows 4..23).
    py_integrals = (
        "=PY\n"
        "import numpy as np\n"
        "from scipy.integrate import simpson\n"
        "x = ks('A5:A24')\n"
        "y = ks('B5:B24')\n"
        "x = np.array(x, dtype=float)\n"
        "y = np.array(y, dtype=float)\n"
        "trap = float(np.trapezoid(y, x))\n"
        "simp = float(simpson(y, x=x))\n"
        "[round(trap, 8), round(simp, 8)]"
    )
    s.formula(3, 4, py_integrals)
    s.fmt(3, 4, bg=PALETTE["warn"], bold=True, align="right", number_format="0.00000000")
    s.fmt(4, 4, bg=PALETTE["good"], bold=True, align="right", number_format="0.00000000")

    # ── Python cell: plot ──────────────────────────────────────────────
    # Placed at row 7, col 3 (0-based) = D8 in 1-based.
    py_plot = (
        "=PY\n"
        "import numpy as np, matplotlib.pyplot as plt\n"
        "x = ks('A5:A24')\n"
        "y = ks('B5:B24')\n"
        "x = np.array(x, dtype=float)\n"
        "y = np.array(y, dtype=float)\n"
        "fig, ax = plt.subplots(figsize=(6, 4))\n"
        "ax.plot(x, y, 'o-', color='#4472c4', linewidth=2, markersize=5, label='y data')\n"
        "ax.fill_between(x, y, alpha=0.25, color='#4472c4', label='Shaded area')\n"
        "ax.axhline(0, color='#333333', linewidth=0.8, linestyle='--')\n"
        "ax.set_xlabel('x'); ax.set_ylabel('y')\n"
        "ax.set_title('Numerical Integration — area under the curve')\n"
        "ax.legend(fontsize=9)\n"
        "ax.grid(True, alpha=0.3)\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )
    s.formula(7, 3, py_plot)

    # ── Sticky notes ───────────────────────────────────────────────────
    s.note(
        4, 0,
        "Edit any x or y value in columns A/B (rows 5-24), then press "
        "Ctrl+Enter on the Python cell in E4 to recompute the integrals "
        "and on D8 to redraw the plot.",
        kind="note",
    )
    s.note(
        3, 4,
        "E4 (top of spill): trapezoidal result.  E5: Simpson's result.  "
        "For smooth functions, Simpson's rule is significantly more accurate.",
        kind="note",
    )
    s.note(
        7, 3,
        "The shaded area is the integral.  The exact value of "
        "integral(sin x, 0, 2pi) = 0.",
        kind="note",
    )

    out = os.path.join(
        _ROOT, "examples", "python", "Numerical Methods",
        "Numerical Integration.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
