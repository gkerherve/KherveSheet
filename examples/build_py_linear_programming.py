"""Build the "Linear Programming" Python-cell example .ksheet.

A classic Solver problem — maximize profit for a product mix subject to
resource limits — solved with scipy.optimize.linprog inside a =PY cell,
writing the optimal quantities back to the grid with ks_set().

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from ksheet_author import Workbook, PALETTE  # noqa: E402


def build():
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Product Mix")
    s.title_block(
        "Linear Programming Solver",
        "Maximize profit for a product mix (scipy.optimize.linprog)")

    # Objective coefficients (profit per unit).
    s.set(3, 0, "Profit / unit — Product A")
    s.set(3, 1, 30.0)
    s.set(4, 0, "Profit / unit — Product B")
    s.set(4, 1, 40.0)
    for r in (3, 4):
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center",
              number_format="0.00")

    # Constraint table: each resource's usage per unit and its limit.
    s.set(6, 0, "Resource")
    s.set(6, 1, "A uses /unit")
    s.set(6, 2, "B uses /unit")
    s.set(6, 3, "Available")
    for c in range(4):
        s.fmt(6, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    constraints = [
        ("Labour (hr)", 1.0, 2.0, 40.0),
        ("Material (kg)", 3.0, 2.0, 60.0),
    ]
    for i, (name, a, b, lim) in enumerate(constraints):
        r = 7 + i
        s.set(r, 0, name)
        s.set(r, 1, a)
        s.set(r, 2, b)
        s.set(r, 3, lim)
        s.fmt(r, 0, bold=True)
        for c in (1, 2, 3):
            s.fmt(r, c, align="center", number_format="0.0")
    s.box(6, 0, 8, 3, color=PALETTE["header"], width=1.0)

    # Result cells (the "changing variable cells" + objective).
    outs = [("Optimal units — A", 10), ("Optimal units — B", 11),
            ("Maximum profit", 12)]
    for label, r in outs:
        s.set(r, 0, label)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["good"], align="center",
              number_format="0.00")
    s.box(10, 0, 12, 1, color=PALETTE["header"], width=1.0)

    code = "\n".join([
        "=PY",
        "import numpy as np, matplotlib.pyplot as plt",
        "from scipy.optimize import linprog",
        "pA = ks('B4'); pB = ks('B5')          # profit per unit",
        "a1 = ks('B8'); b1 = ks('C8'); L = ks('D8')   # labour",
        "a2 = ks('B9'); b2 = ks('C9'); M = ks('D9')   # material",
        "# Maximize pA*A + pB*B  ->  minimize the negatives.",
        "res = linprog(c=[-pA, -pB],",
        "              A_ub=[[a1, b1], [a2, b2]], b_ub=[L, M],",
        "              bounds=[(0, None), (0, None)])",
        "A, B = res.x",
        "ks_set('B11', round(float(A), 2))    # optimal A",
        "ks_set('B12', round(float(B), 2))    # optimal B",
        "ks_set('B13', round(float(-res.fun), 2))   # max profit",
        "",
        "# Draw the feasible region and the optimum.",
        "xm = max(L/a1 if a1 else 0, M/a2 if a2 else 0, A) * 1.25 + 1",
        "ym = max(L/b1 if b1 else 0, M/b2 if b2 else 0, B) * 1.25 + 1",
        "gx = np.linspace(0, xm, 300); gy = np.linspace(0, ym, 300)",
        "X, Y = np.meshgrid(gx, gy)",
        "feas = (a1*X + b1*Y <= L) & (a2*X + b2*Y <= M)",
        "fig, ax = plt.subplots()",
        "ax.contourf(X, Y, feas, levels=[0.5, 1],",
        "            colors=['#cfe2f3'], alpha=0.8)",
        "if b1:",
        "    ax.plot(gx, (L - a1*gx)/b1, color='#4472c4', label='Labour')",
        "if b2:",
        "    ax.plot(gx, (M - a2*gx)/b2, color='#70ad47',"
        " label='Material')",
        "ax.plot([A], [B], 'o', color='#ed7d31', ms=9, label='optimum')",
        "ax.set_xlim(0, xm); ax.set_ylim(0, ym)",
        "ax.set_xlabel('units of A'); ax.set_ylabel('units of B')",
        "ax.set_title(f'max profit {-res.fun:.0f} at "
        "A={A:.1f}, B={B:.1f}')",
        "ax.legend(); ax.grid(True, alpha=0.3)",
        "plt.gcf()",
    ])
    s.formula(14, 0, code)
    s.note(
        15, 0,
        "Solver-style: B4/B5 are the objective coefficients, B8:D9 the "
        "constraints, and B11:B13 the changing variable / result cells. "
        "Edit any profit, usage or limit and press Ctrl+Enter — the "
        "optimal product mix is written back and the feasible region "
        "redrawn.")
    s.col_width(0, 190)

    out = os.path.join(os.path.dirname(__file__), "python", "Solver",
                       "Linear Programming.ksheet")
    wb.save(out)
    print("Wrote", out)


if __name__ == "__main__":
    build()
