"""Build "Pendulum Period.ksheet" — a Python-cell physics example.

A column of pendulum lengths L (m) is in cells B4:B23.
=PY plots T = 2π√(L/g) vs L, and a second =PY cell spills
the corresponding T values into column C.

Run:  python examples/build_py_pendulum.py

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
    N = 20          # number of length values
    L_vals = np.linspace(0.1, 2.5, N)

    wb = Workbook(min_rows=35, min_cols=12)
    s = wb.add_sheet("Pendulum")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Pendulum Period",
                  "T = 2π√(L/g)  —  edit the lengths in column B "
                  "and press Ctrl+Enter to recompute")

    # ── Column headers ─────────────────────────────────────────────────
    s.set(3, 0, "L  (m)")
    s.set(3, 1, "T  (s)  [spilled by =PY]")
    s.fmt(3, 0, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.fmt(3, 1, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.col_width(0, 90)
    s.col_width(1, 180)

    # ── Length data (editable) in B4:B23 → 0-based rows 4..23, col 1 ──
    # (col 0 = A = label, col 1 = B = L values)
    # Wait — headers at row 3, data starts row 4
    # B4 corresponds to 0-based (row=4, col=1) → sheet cell B5 ... no.
    # 0-based row 3 → sheet row 4 (headers).
    # 0-based row 4..23 → sheet rows 5..24 → cells B5:B24.
    # We want ks('B4:B23') to get N=20 values.
    # So put the header at 0-based row 2 (sheet row 3) and data at rows 3..22.
    # Let me redo: header at row 2 (sheet row 3), data rows 3..22 (sheet B4:B23).

    wb2 = Workbook(min_rows=35, min_cols=12)
    s2 = wb2.add_sheet("Pendulum")

    s2.title_block("Pendulum Period",
                   "T = 2π√(L/g)  —  edit lengths in column B, "
                   "press Ctrl+Enter on the =PY cells to recompute")

    # Column headers at 0-based row 2 (sheet row 3)
    s2.set(2, 0, "L  (m)")
    s2.set(2, 1, "T  (s)  ← spilled by =PY below")
    s2.fmt(2, 0, bold=True, bg=PALETTE["header"],
           font_color=PALETTE["header_text"], align="center")
    s2.fmt(2, 1, bold=True, bg=PALETTE["header"],
           font_color=PALETTE["header_text"], align="center")
    s2.col_width(0, 90)
    s2.col_width(1, 210)

    # Length values at 0-based rows 3..22, col 0 → sheet A4:A23
    for i, L in enumerate(L_vals):
        r = 3 + i
        s2.set(r, 0, round(float(L), 3))
        s2.fmt(r, 0, number_format="0.000", align="right",
               bg=(PALETTE["band_alt"] if i % 2 else None))

    s2.note(3, 0,
            "These are the pendulum lengths (m).  Edit any value "
            "and press Ctrl+Enter on the =PY cells (rows 25–26) "
            "to recompute T and replot.",
            kind="note")

    # ── =PY cell: spill T values into column B (next to L) ────────────
    # 0-based row 24 → sheet row 25
    # Spill into col 1 (B), rows 3..22 → but spill goes downward from the
    # cell itself.  Place the =PY cell at row 3, col 1 (B4) so it spills
    # T values right next to L values.
    py_spill = "\n".join([
        "=PY",
        "import numpy as np",
        "L = ks('A4:A23')",
        "g = 9.81",
        "T = 2 * np.pi * np.sqrt(L / g)",
        "list(np.round(T, 4))",
    ])
    s2.formula(3, 1, py_spill)
    s2.fmt(3, 1, number_format="0.0000", align="right")

    # ── =PY cell: plot T vs L ─────────────────────────────────────────
    # 0-based row 24 → sheet row 25
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "L = ks('A4:A23')",
        "g = 9.81",
        "T = 2 * np.pi * np.sqrt(L / g)",
        "L_fine = np.linspace(L.min(), L.max(), 300)",
        "T_fine = 2 * np.pi * np.sqrt(L_fine / g)",
        "fig, ax = plt.subplots(figsize=(5, 4))",
        "ax.plot(L_fine, T_fine, color='#4472c4', linewidth=2, label='T(L)')",
        "ax.scatter(L, T, color='#ed7d31', s=40, zorder=5, label='data points')",
        "ax.set_xlabel('Length  L  (m)')",
        "ax.set_ylabel('Period  T  (s)')",
        "ax.set_title('Pendulum period vs length')",
        "ax.legend(fontsize=9)",
        "ax.grid(True, alpha=0.4)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s2.formula(24, 0, py_plot)

    s2.note(24, 0,
            "=PY plot cell — shows T vs L curve.  "
            "Press Ctrl+Enter here after editing the lengths above.",
            kind="note")

    out = os.path.join(_REPO, "examples", "python", "Physics",
                       "Pendulum Period.ksheet")
    wb2.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
