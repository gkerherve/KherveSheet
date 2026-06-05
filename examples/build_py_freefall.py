"""Build "Free Fall.ksheet" — a Python-cell physics example.

A column of times t (s) in A4:A23.
One =PY cell spills d = ½ g t² values into column B.
A second =PY cell plots d vs t with the parabolic curve.

Run:  python examples/build_py_freefall.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE


def build() -> str:
    N = 20
    t_vals = np.linspace(0.0, 4.5, N)

    wb = Workbook(min_rows=35, min_cols=12)
    s = wb.add_sheet("FreeFall")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Free Fall",
                  "d = ½ g t²  —  edit the time values in column A, "
                  "press Ctrl+Enter to recompute")

    # ── Column headers at 0-based row 2 (sheet row 3) ─────────────────
    s.set(2, 0, "t  (s)")
    s.set(2, 1, "d  (m)  ← spilled by =PY")
    s.fmt(2, 0, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.fmt(2, 1, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.col_width(0, 90)
    s.col_width(1, 200)

    # ── Time values at 0-based rows 3..22, col 0 → sheet A4:A23 ───────
    for i, t in enumerate(t_vals):
        r = 3 + i
        s.set(r, 0, round(float(t), 3))
        s.fmt(r, 0, number_format="0.000", align="right",
              bg=(PALETTE["band_alt"] if i % 2 else None))

    s.note(3, 0,
           "These are the fall times (s).  Edit any value and press "
           "Ctrl+Enter on the =PY cells (rows 25–26) to recompute d and replot.",
           kind="note")

    # ── =PY cell: spill d values into column B, starting at B4 ────────
    py_spill = "\n".join([
        "=PY",
        "import numpy as np",
        "t = ks('A4:A23')",
        "g = 9.81",
        "d = 0.5 * g * t**2",
        "list(np.round(d, 4))",
    ])
    s.formula(3, 1, py_spill)
    s.fmt(3, 1, number_format="0.0000", align="right")

    # ── =PY cell: plot d vs t ─────────────────────────────────────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "t = ks('A4:A23')",
        "g = 9.81",
        "d = 0.5 * g * t**2",
        "t_fine = np.linspace(0, t.max(), 300)",
        "d_fine = 0.5 * g * t_fine**2",
        "fig, ax = plt.subplots(figsize=(5, 4))",
        "ax.plot(t_fine, d_fine, color='#4472c4', linewidth=2, label='d(t)')",
        "ax.scatter(t, d, color='#ed7d31', s=40, zorder=5, label='data points')",
        "ax.set_xlabel('Time  t (s)')",
        "ax.set_ylabel('Distance fallen  d (m)')",
        "ax.set_title('Free-fall distance vs time')",
        "ax.legend(fontsize=9)",
        "ax.grid(True, alpha=0.4)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(24, 0, py_plot)

    s.note(24, 0,
           "=PY plot cell — parabolic d vs t curve.  "
           "Press Ctrl+Enter here after editing the time column above.",
           kind="note")

    out = os.path.join(_REPO, "examples", "python", "Physics",
                       "Free Fall.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
