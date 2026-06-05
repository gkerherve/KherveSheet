"""Build "Taylor Series.ksheet" — a =PY science example.

Shows the N-term Taylor approximation of sin(x) and e^x side-by-side.
Inputs: number of terms N and M, x range (read from cells).
The plot overlays the exact function and its truncated Taylor series.

Run:  python examples/build_taylor_series.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

from ksheet_author import Workbook, PALETTE  # noqa: E402


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=14)
    s = wb.add_sheet("Taylor Series")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block(
        "Taylor Series Approximations",
        "Compare sin(x) and e^x to their N-term Taylor polynomials",
    )

    # ── Input parameters ───────────────────────────────────────────────
    # Labels at col 0, values at col 1.
    # Row 3 (0-based) = B4 in 1-based, row 4 = B5, row 5 = B6.
    s.set(2, 0, "Inputs")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Terms N (sin series)",  6),
        ("Terms M (exp series)",  8),
        ("x range half-width",    6.28),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i  # 0-based rows 3,4,5 → 1-based B4,B5,B6
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 190)
    s.col_width(1, 100)

    # ── Coefficient table header at row 7 (0-based) = row 8 in 1-based ─
    s.set(7, 0, "sin(x) Taylor coefficients  (up to N terms)")
    s.fmt(7, 0, bold=True, font_color=PALETTE["header"])
    s.set(8, 0, "Term k")
    s.set(8, 1, "Power")
    s.set(8, 2, "Coefficient  (-1)^k / (2k+1)!")
    for c in range(3):
        s.fmt(8, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    s.col_width(2, 180)

    # ── Python cell: spill sin Taylor coefficients ─────────────────────
    # Placed at row 8, col 0 (0-based) = A9 in 1-based.
    # N is at B4 (0-based row 3, col 1 → 1-based B4).
    py_coeffs = (
        "=PY\n"
        "import math\n"
        "N = int(ks('B4'))\n"
        "rows = []\n"
        "for k in range(N):\n"
        "    power = 2*k + 1\n"
        "    coeff = ((-1)**k) / math.factorial(power)\n"
        "    rows.append([k, power, round(coeff, 12)])\n"
        "rows"
    )
    s.formula(8, 0, py_coeffs)

    # ── Python cell: main comparison plot ─────────────────────────────
    # Placed at row 2, col 3 (0-based) = D3 in 1-based.
    # N=B4, M=B5, half=B6.
    py_plot = (
        "=PY\n"
        "import numpy as np, matplotlib.pyplot as plt, math\n"
        "N = int(ks('B4'))\n"
        "M = int(ks('B5'))\n"
        "half = float(ks('B6'))\n"
        "x_sin = np.linspace(-half, half, 500)\n"
        "x_exp = np.linspace(-2.0, 2.0, 500)\n"
        "sin_taylor = np.zeros_like(x_sin)\n"
        "for k in range(N):\n"
        "    sin_taylor += ((-1)**k / math.factorial(2*k+1)) * x_sin**(2*k+1)\n"
        "exp_taylor = np.zeros_like(x_exp)\n"
        "for k in range(M):\n"
        "    exp_taylor += x_exp**k / math.factorial(k)\n"
        "fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))\n"
        "ax1.plot(x_sin, np.sin(x_sin), color='#4472c4', linewidth=2.5, label='sin(x) exact')\n"
        "ax1.plot(x_sin, np.clip(sin_taylor, -4, 4), '--', color='#ed7d31', linewidth=2, label=f'Taylor N={N}')\n"
        "ax1.set_ylim(-2.5, 2.5); ax1.axhline(0, color='#aaaaaa', linewidth=0.7)\n"
        "ax1.set_xlabel('x'); ax1.set_ylabel('sin(x)')\n"
        "ax1.set_title(f'sin(x)  N={N} terms'); ax1.legend(fontsize=9); ax1.grid(True, alpha=0.3)\n"
        "ax2.plot(x_exp, np.exp(x_exp), color='#4472c4', linewidth=2.5, label='e^x exact')\n"
        "ax2.plot(x_exp, np.clip(exp_taylor, -1, 30), '--', color='#ed7d31', linewidth=2, label=f'Taylor M={M}')\n"
        "ax2.set_ylim(-0.5, 9); ax2.axhline(0, color='#aaaaaa', linewidth=0.7)\n"
        "ax2.set_xlabel('x'); ax2.set_ylabel('e^x')\n"
        "ax2.set_title(f'e^x  M={M} terms'); ax2.legend(fontsize=9); ax2.grid(True, alpha=0.3)\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )
    s.formula(2, 3, py_plot)

    # ── Sticky notes ───────────────────────────────────────────────────
    s.note(
        3, 1,
        "Change N (sin terms in B4) or M (exp terms in B5), then press "
        "Ctrl+Enter on D3 (plot) and A9 (coefficients).  "
        "Try N=1, 3, 5, 11 for sin(x).",
        kind="note",
    )
    s.note(
        7, 0,
        "The coefficient table spills downward from A9.  "
        "It shows the alternating-sign odd-power terms that build sin(x).",
        kind="note",
    )
    s.note(
        2, 3,
        "Blue = exact function.  Orange dashed = N-term Taylor polynomial.  "
        "The series diverges far from x=0 until enough terms are added.",
        kind="note",
    )

    out = os.path.join(
        _ROOT, "examples", "python", "Numerical Methods",
        "Taylor Series.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
