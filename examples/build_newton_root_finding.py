"""Build "Newton Root Finding.ksheet" — a =PY science example.

Shows Newton's method applied to f(x) = x^3 + a*x^2 + b*x + c.
Inputs: coefficients a, b, c and an initial guess x0.
A spill cell lists the iteration values; a plot cell shows the convergence.

Run:  python examples/build_newton_root_finding.py

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
    s = wb.add_sheet("Newton")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block(
        "Newton's Root-Finding Method",
        "Iteratively solves f(x) = x^3 + a*x^2 + b*x + c = 0",
    )

    # ── Input parameters ───────────────────────────────────────────────
    # Labels at col 0, values at col 1.
    # s.set(row, col, val) → 1-based: row+1, col+1.
    # Rows 4..9 (0-based) = B5:B10 in 1-based.
    s.set(2, 0, "Function: f(x) = x^3 + a*x^2 + b*x + c")
    s.fmt(2, 0, italic=True, font_color="#555555")

    inputs = [
        ("a  (coefficient of x^2)", 0.0),
        ("b  (coefficient of x)",   0.0),
        ("c  (constant term)",      -2.0),
        ("x0  (initial guess)",     1.5),
        ("Max iterations",          20),
        ("Tolerance",               0.000001),
    ]
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    # Row 4 = 0-based → B5 in 1-based; row 9 → B10.
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.000000")
    s.box(4, 0, 9, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 210)
    s.col_width(1, 110)

    # ── Iteration table header at row 11 (0-based) = row 12 in 1-based ─
    s.set(11, 0, "Iteration trace  (spilled by Python)")
    s.fmt(11, 0, bold=True, font_color=PALETTE["header"])

    s.set(12, 0, "Iteration")
    s.set(12, 1, "x_n")
    s.set(12, 2, "f(x_n)")
    s.set(12, 3, "|error|")
    for c in range(4):
        s.fmt(12, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    s.col_width(1, 110)
    s.col_width(2, 110)
    s.col_width(3, 110)

    # ── Python cell: run Newton's method, spill iteration table ────────
    # Placed at row 12, col 0 (0-based) = A13 in 1-based.
    # Inputs: a=B5, b=B6, c=B7, x0=B8, max_iter=B9, tol=B10.
    py_newton = (
        "=PY\n"
        "import numpy as np\n"
        "a = ks('B5'); b = ks('B6'); c_val = ks('B7')\n"
        "x = ks('B8'); max_iter = int(ks('B9')); tol = ks('B10')\n"
        "def f(t):  return t**3 + a*t**2 + b*t + c_val\n"
        "def df(t): return 3*t**2 + 2*a*t + b\n"
        "rows = []\n"
        "for i in range(1, max_iter + 1):\n"
        "    fx = f(x); dfx = df(x)\n"
        "    if abs(dfx) < 1e-14: break\n"
        "    x_new = x - fx / dfx\n"
        "    err = abs(x_new - x)\n"
        "    rows.append([i, round(x_new, 10), round(fx, 10), round(err, 10)])\n"
        "    x = x_new\n"
        "    if err < tol: break\n"
        "rows"
    )
    s.formula(12, 0, py_newton)

    # ── Python cell: convergence plot ──────────────────────────────────
    # Placed at row 2, col 3 (0-based) = D3 in 1-based.
    py_plot = (
        "=PY\n"
        "import numpy as np, matplotlib.pyplot as plt\n"
        "a = ks('B5'); b = ks('B6'); c_val = ks('B7')\n"
        "x0 = ks('B8'); max_iter = int(ks('B9')); tol = ks('B10')\n"
        "def f(t):  return t**3 + a*t**2 + b*t + c_val\n"
        "def df(t): return 3*t**2 + 2*a*t + b\n"
        "xs = [x0]\n"
        "x = x0\n"
        "for i in range(max_iter):\n"
        "    fx = f(x); dfx = df(x)\n"
        "    if abs(dfx) < 1e-14: break\n"
        "    x_new = x - fx / dfx\n"
        "    xs.append(x_new)\n"
        "    if abs(x_new - x) < tol: break\n"
        "    x = x_new\n"
        "root = xs[-1]\n"
        "errors = [abs(xi - root) for xi in xs[:-1]]\n"
        "x_range = np.linspace(root - 3, root + 3, 400)\n"
        "y_range = x_range**3 + a*x_range**2 + b*x_range + c_val\n"
        "fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))\n"
        "ax1.plot(x_range, y_range, color='#4472c4', linewidth=2)\n"
        "ax1.axhline(0, color='#333333', linewidth=0.8, linestyle='--')\n"
        "ax1.axvline(root, color='#ed7d31', linewidth=1.5, linestyle=':', label=f'root={root:.6f}')\n"
        "ax1.scatter([xs[0]], [f(xs[0])], color='#ed7d31', zorder=5, s=60, label='x0')\n"
        "ax1.scatter([root], [0], color='#c6efce', edgecolors='#333333', zorder=6, s=80, label='root')\n"
        "ax1.set_xlabel('x'); ax1.set_ylabel('f(x)')\n"
        "ax1.set_title('f(x) and root'); ax1.legend(fontsize=8); ax1.grid(True, alpha=0.3)\n"
        "if errors:\n"
        "    ax2.semilogy(range(len(errors)), errors, 'o-', color='#4472c4', linewidth=2, markersize=5)\n"
        "    ax2.set_xlabel('Iteration'); ax2.set_ylabel('|error|')\n"
        "    ax2.set_title('Convergence'); ax2.grid(True, alpha=0.3)\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )
    s.formula(2, 3, py_plot)

    # ── Sticky notes ───────────────────────────────────────────────────
    s.note(
        4, 1,
        "Edit a, b, c and x0 in B5:B10, then press Ctrl+Enter on A13 "
        "(iteration table) and D3 (plot).",
        kind="note",
    )
    s.note(
        11, 0,
        "Default: f(x) = x^3 - 2 = 0.  The root is cube-root(2) ~ 1.2599210.  "
        "Change c to any value to find a different root.",
        kind="note",
    )
    s.note(
        2, 3,
        "Left: cubic curve with root marked (orange).  "
        "Right: convergence of |error| on a log scale.",
        kind="note",
    )

    out = os.path.join(
        _ROOT, "examples", "python", "Numerical Methods",
        "Newton Root Finding.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
