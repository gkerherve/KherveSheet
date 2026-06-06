"""Build the "Optimization Solver" Python-cell example .ksheet.

Mirrors KherveSheet's Solver dialog (objective + changing variable cells +
constraint) but driven by scipy.optimize.minimize inside a =PY cell, which
writes the optimal variables back into the grid with ks_set().

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
    s = wb.add_sheet("Solver")
    s.title_block(
        "Optimization Solver",
        "Minimize a can's surface area for a fixed volume "
        "(scipy.optimize.minimize)")

    # ── Problem set-up (mirrors the Solver dialog) ───────────────────
    s.set(3, 0, "Objective (minimize)")
    s.set(3, 1, "surface area")
    s.set(4, 0, "Constraint")
    s.set(4, 1, "π·r²·h = V")
    for r in (3, 4):
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, italic=True, font_color="#555555")

    # Inputs / changing variable cells.
    rows = [
        ("Target volume V (cm³)", 500.0),
        ("radius r (start → optimal)", 3.0),
        ("height h (start → optimal)", 8.0),
        ("min surface area (cm²)", ""),
    ]
    for i, (label, val) in enumerate(rows):
        r = 6 + i
        s.set(r, 0, label)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center",
              number_format="0.000")
    # Highlight the result cell differently.
    s.fmt(9, 1, bg=PALETTE["good"], align="center", number_format="0.00")
    s.box(6, 0, 9, 1, color=PALETTE["header"], width=1.0)

    code = "\n".join([
        "=PY",
        "import numpy as np, matplotlib.pyplot as plt",
        "from scipy.optimize import minimize",
        "V  = ks('B7')           # fixed volume (the constraint)",
        "r0 = ks('B8'); h0 = ks('B9')   # starting guess",
        "",
        "def area(x):",
        "    r, h = x",
        "    return 2*np.pi*r**2 + 2*np.pi*r*h",
        "",
        "cons = ({'type': 'eq',",
        "         'fun': lambda x: np.pi*x[0]**2*x[1] - V},)",
        "res = minimize(area, [r0, h0], method='SLSQP',",
        "               bounds=[(0.05, None), (0.05, None)],",
        "               constraints=cons)",
        "r, h = res.x",
        "# Write the optimum back into the variable cells (like Solver).",
        "ks_set('B8', round(float(r), 4))",
        "ks_set('B9', round(float(h), 4))",
        "ks_set('B10', round(float(res.fun), 3))",
        "",
        "# Show the objective vs radius with the optimum marked.",
        "rr = np.linspace(max(0.3, r*0.3), r*2.2, 300)",
        "hh = V / (np.pi*rr**2)",
        "aa = 2*np.pi*rr**2 + 2*np.pi*rr*hh",
        "fig, ax = plt.subplots()",
        "ax.plot(rr, aa, color='#4472c4', label='surface area')",
        "ax.plot([r], [res.fun], 'o', color='#ed7d31', ms=8,",
        "        label='optimum')",
        "ax.set_xlabel('radius r (cm)'); ax.set_ylabel('area (cm²)')",
        "ax.set_title(f'min area {res.fun:.1f} cm² at "
        "r={r:.3f}, h={h:.3f}')",
        "ax.legend(); ax.grid(True, alpha=0.4)",
        "plt.gcf()",
    ])
    s.formula(12, 0, code)
    s.note(
        13, 0,
        "This is the Solver workflow in Python: B7 is the constraint, "
        "B8/B9 are the changing variable cells, B10 is the objective. "
        "Edit V (B7) or the starting guess, then press Ctrl+Enter — the "
        "optimal r and h are written back into B8/B9.")
    s.col_width(0, 200)

    out = os.path.join(os.path.dirname(__file__), "python", "Solver",
                       "Optimization Solver.ksheet")
    wb.save(out)
    print("Wrote", out)


if __name__ == "__main__":
    build()
