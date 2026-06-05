"""Build "Euler ODE Solver.ksheet" — a =PY science example.

Solves dy/dx = -k*y (exponential decay) using Euler's method.
Inputs: decay constant k, initial value y0, step size h, x end (read from cells).
A spill cell gives the solution table; a plot overlays Euler vs analytic.

Run:  python examples/build_euler_ode_solver.py

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
    wb = Workbook(min_rows=60, min_cols=14)
    s = wb.add_sheet("Euler ODE")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block(
        "Euler ODE Solver",
        "dy/dx = -k*y  solved step by step with Euler's forward method",
    )

    # ── Input parameters ───────────────────────────────────────────────
    # Labels at col 0, values at col 1.
    # Row 3 (0-based) → B4, row 4 → B5, row 5 → B6, row 6 → B7.
    s.set(2, 0, "Inputs")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Decay constant k",     1.0),
        ("Initial value y0",     1.0),
        ("Step size h",          0.25),
        ("End of range x_end",   5.0),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i  # 0-based rows 3..6 → 1-based B4..B7
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.000")
    s.box(3, 0, 6, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 180)
    s.col_width(1, 100)

    # ── Solution table header at row 8 (0-based) = row 9 in 1-based ───
    s.set(8, 0, "Euler solution table  (spilled by Python)")
    s.fmt(8, 0, bold=True, font_color=PALETTE["header"])
    s.set(9, 0, "Step")
    s.set(9, 1, "x")
    s.set(9, 2, "y_Euler")
    s.set(9, 3, "y_analytic")
    s.set(9, 4, "|error|")
    for c in range(5):
        s.fmt(9, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    s.col_width(1, 90)
    s.col_width(2, 100)
    s.col_width(3, 110)
    s.col_width(4, 90)

    # ── Python cell: run Euler's method, spill table ───────────────────
    # Placed at row 9, col 0 (0-based) = A10 in 1-based.
    # k=B4, y0=B5, h=B6, x_end=B7.
    py_euler = (
        "=PY\n"
        "import numpy as np\n"
        "k = ks('B4'); y0 = ks('B5'); h = ks('B6'); x_end = ks('B7')\n"
        "x = 0.0; y = y0\n"
        "rows = [[0, round(x, 6), round(y, 8), round(y0, 8), 0.0]]\n"
        "step = 1\n"
        "while x + h <= x_end + 1e-12:\n"
        "    dy = -k * y * h\n"
        "    x = round(x + h, 10)\n"
        "    y = y + dy\n"
        "    exact = y0 * np.exp(-k * x)\n"
        "    err = abs(y - exact)\n"
        "    rows.append([step, round(x, 6), round(y, 8), round(exact, 8), round(err, 8)])\n"
        "    step += 1\n"
        "rows"
    )
    s.formula(9, 0, py_euler)

    # ── Python cell: comparison plot ───────────────────────────────────
    # Placed at row 2, col 3 (0-based) = D3 in 1-based.
    py_plot = (
        "=PY\n"
        "import numpy as np, matplotlib.pyplot as plt\n"
        "k = ks('B4'); y0 = ks('B5'); h = ks('B6'); x_end = ks('B7')\n"
        "x_euler = [0.0]; y_euler = [y0]\n"
        "x_cur = 0.0; y_cur = y0\n"
        "while x_cur + h <= x_end + 1e-12:\n"
        "    y_cur = y_cur + (-k * y_cur) * h\n"
        "    x_cur = round(x_cur + h, 10)\n"
        "    x_euler.append(x_cur); y_euler.append(y_cur)\n"
        "x_euler = np.array(x_euler); y_euler = np.array(y_euler)\n"
        "x_fine = np.linspace(0, x_end, 400)\n"
        "y_fine = y0 * np.exp(-k * x_fine)\n"
        "y_exact_steps = y0 * np.exp(-k * x_euler)\n"
        "errors = np.abs(y_euler - y_exact_steps)\n"
        "fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))\n"
        "ax1.plot(x_fine, y_fine, color='#4472c4', linewidth=2.5, label='Analytic y=y0*e^(-kx)')\n"
        "ax1.step(x_euler, y_euler, where='post', color='#ed7d31',\n"
        "         linewidth=1.5, linestyle='--', label=f'Euler h={h}')\n"
        "ax1.scatter(x_euler, y_euler, color='#ed7d31', s=25, zorder=4)\n"
        "ax1.set_xlabel('x'); ax1.set_ylabel('y')\n"
        "ax1.set_title(f'Euler vs Analytic  k={k} y0={y0}')\n"
        "ax1.legend(fontsize=9); ax1.grid(True, alpha=0.3)\n"
        "valid = errors[1:] > 0\n"
        "if valid.any():\n"
        "    ax2.semilogy(x_euler[1:][valid], errors[1:][valid], 'o-', color='#c6efce',\n"
        "                 markeredgecolor='#333333', linewidth=2, markersize=5)\n"
        "ax2.set_xlabel('x'); ax2.set_ylabel('|error|')\n"
        "ax2.set_title('Absolute error  (log scale)'); ax2.grid(True, alpha=0.3)\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )
    s.formula(2, 3, py_plot)

    # ── Sticky notes ───────────────────────────────────────────────────
    s.note(
        3, 1,
        "Edit k (B4), y0 (B5), h (B6), x_end (B7).  "
        "Larger h = fewer steps but more error.  Try h=0.5 vs h=0.1.",
        kind="note",
    )
    s.note(
        8, 0,
        "The table spills one row per Euler step from A10.  "
        "Columns: step, x, y_Euler, y_analytic, |error|.",
        kind="note",
    )
    s.note(
        2, 3,
        "Left: Euler steps (orange) vs exact curve (blue).  "
        "Right: absolute error on a log scale — note it grows with x.",
        kind="note",
    )

    out = os.path.join(
        _ROOT, "examples", "python", "Numerical Methods",
        "Euler ODE Solver.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
