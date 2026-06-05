"""Build "Projectile Motion.ksheet" — a Python-cell physics example.

=PY cells read v0 and angle from the grid, compute the trajectory,
plot y vs x, and return the horizontal range as a number.

Run:  python examples/build_py_projectile.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=12)
    s = wb.add_sheet("Projectile")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Projectile Motion",
                  "Python computes the trajectory — edit v₀ and angle, "
                  "press Ctrl+Enter to replot")

    # ── Input parameters  (B4 = v0, B5 = angle) ───────────────────────
    s.set(3, 0, "v₀  (m/s)")
    s.set(3, 1, 30.0)
    s.set(4, 0, "Launch angle  (°)")
    s.set(4, 1, 45.0)
    s.fmt(3, 0, bold=True)
    s.fmt(4, 0, bold=True)
    s.fmt(3, 1, bg=PALETTE["warn"], align="center", number_format="0.0")
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.0")
    s.box(3, 0, 4, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 190)
    s.col_width(1, 90)

    s.note(3, 1,
           "Change v₀ here (e.g. 20, 40) or the angle below (e.g. 30, 60), "
           "then press Ctrl+Enter on the =PY plot cell in row 7.",
           kind="note")

    # ── =PY cell: plot trajectory ──────────────────────────────────────
    # 0-based row 6 → sheet row 7 (A7)
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "v0    = ks('B4')",
        "angle = ks('B5')",
        "g     = 9.81",
        "a_rad = np.radians(angle)",
        "T     = 2 * v0 * np.sin(a_rad) / g",
        "t     = np.linspace(0, T, 300)",
        "x     = v0 * np.cos(a_rad) * t",
        "y     = v0 * np.sin(a_rad) * t - 0.5 * g * t**2",
        "fig, ax = plt.subplots(figsize=(6, 4))",
        "ax.plot(x, y, color='#4472c4', linewidth=2.5)",
        "ax.fill_between(x, y, alpha=0.15, color='#4472c4')",
        "ax.set_xlabel('Horizontal distance  x (m)')",
        "ax.set_ylabel('Height  y (m)')",
        "ax.set_title(f'Trajectory  (v\\u2080={v0} m/s, \\u03b8={angle}\\u00b0)')",
        "ax.set_ylim(bottom=0)",
        "ax.grid(True, alpha=0.4)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(6, 0, py_plot)

    # ── =PY cell: return horizontal range ─────────────────────────────
    # 0-based row 6, col 3 → sheet E7
    s.set(6, 3, "Horizontal range (m):")
    s.fmt(6, 3, bold=True, align="right")
    py_range = "\n".join([
        "=PY",
        "import numpy as np",
        "v0    = ks('B4')",
        "angle = ks('B5')",
        "g     = 9.81",
        "a_rad = np.radians(angle)",
        "round(v0**2 * np.sin(2 * a_rad) / g, 3)",
    ])
    s.formula(6, 4, py_range)
    s.fmt(6, 4, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.00")
    s.col_width(3, 180)
    s.col_width(4, 100)

    out = os.path.join(_REPO, "examples", "python", "Physics",
                       "Projectile Motion.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
