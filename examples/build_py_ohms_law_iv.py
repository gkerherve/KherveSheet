"""Build "Ohms Law IV.ksheet" — a Python-cell physics example.

The sheet has a column of user-editable voltages (V) and a resistance R.
A =PY cell computes I = V/R and spills the current values into column B.
A second =PY cell reads V and R, recomputes I, and plots the I–V curve.

Run:  python examples/build_py_ohms_law_iv.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE  # noqa: E402

OUT_PATH = os.path.join(
    _REPO, "examples", "python", "Physics", "Ohms Law IV.ksheet"
)

# Default voltages (user can edit any of these in the sheet)
VOLTAGES = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
R_DEFAULT = 47.0   # Ω


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("IV Curve")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Ohm's Law — I–V Characteristic",
        "Current I = V / R  for a resistor; edit any voltage or R to update the plot",
    )

    # ── Resistance input ──────────────────────────────────────────────
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    s.set(4, 0, "Resistance R (Ohms)")
    s.set(4, 1, R_DEFAULT)
    s.fmt(4, 0, bold=True)
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.0")
    s.box(4, 0, 4, 1, color=PALETTE["accent"], width=1.0)

    s.col_width(0, 175)
    s.col_width(1, 120)

    # ── Sticky note ───────────────────────────────────────────────────
    s.note(
        4, 1,
        "Edit R (B5) or any voltage in column A below.\n"
        "Press Ctrl+Enter on the PY-compute cell (C9) to recalculate I,\n"
        "then Ctrl+Enter on the PY-plot cell (D9) to refresh the chart.",
        kind="note",
    )

    # ── Voltage data column ───────────────────────────────────────────
    s.set(6, 0, "Voltage data  (edit freely)")
    s.fmt(6, 0, bold=True, font_color=PALETTE["header"])

    # Column headers (row index 7 = sheet row 8)
    s.set(7, 0, "V (volts)")
    s.fmt(7, 0, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.set(7, 1, "I (mA)  — spilled by Python")
    s.fmt(7, 1, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.col_width(1, 210)

    n = len(VOLTAGES)
    for i, v in enumerate(VOLTAGES):
        r = 8 + i
        s.set(r, 0, v)
        s.fmt(r, 0, align="center", number_format="0.0",
              bg=(PALETTE["band_alt"] if i % 2 else None))
        s.fmt(r, 1, align="center", number_format="0.000",
              bg=(PALETTE["band_alt"] if i % 2 else None))

    s.box(7, 0, 7 + n, 1, color=PALETTE["header"], width=1.0)

    # 1-based A1 range for the voltage column
    # Voltages start at row index 8 (sheet row 9) and end at row index 8+n-1
    v_range = f"A9:A{8 + n}"      # sheet rows 9 .. 8+n

    # ── PY compute cell: spill I values into column B ─────────────────
    # Place this cell at row index 8, col index 2  (=C9 in sheet)
    # It spills results downward; the first spill cell is B9 (col 1 row 8)
    # NOTE: we put the compute cell in column C so its spill goes into B.
    py_compute = f"""\
=PY
import numpy as np

R    = float(ks("B5"))          # resistance in Ohms
V    = np.atleast_1d(np.array(ks("{v_range}"), dtype=float))

I_mA = (V / R * 1000).tolist()  # current in mA; spill as list into B9:B{8+n}
I_mA
"""
    s.set(6, 2, "PY-compute: spills I into B9:B{}".format(8 + n))
    s.fmt(6, 2, italic=True, font_color="#555555")
    s.formula(8, 2, py_compute)
    s.fmt(8, 2, bg=PALETTE["band"], font_family="Courier New", font_size=9)
    s.col_width(2, 230)

    # ── PY plot cell: reads V from column A, recomputes I ─────────────
    # Place at row index 8, col index 3 (=D9 in sheet)
    py_plot = f"""\
=PY
import numpy as np
import matplotlib.pyplot as plt

R = float(ks("B5"))
V = np.atleast_1d(np.array(ks("{v_range}"), dtype=float))
I = V / R * 1000     # mA — recomputed directly from inputs

fig, ax = plt.subplots(figsize=(5.5, 4))
ax.plot(V, I, "o-", color="#4472c4", linewidth=2.0,
        markersize=7, markerfacecolor="#ffffff",
        markeredgecolor="#4472c4", markeredgewidth=1.8,
        label=f"R = {{R:.1f}} Ohm")

# Overlay the ideal Ohm's law line
V_line = np.linspace(float(V.min()), float(V.max()), 200)
ax.plot(V_line, V_line / R * 1000, "--", color="#ed7d31",
        linewidth=1.4, alpha=0.75, label="Ideal V/R")

ax.set_xlabel("Voltage  V  (volts)", fontsize=11)
ax.set_ylabel("Current  I  (mA)", fontsize=11)
ax.set_title(f"Ohm's Law — I–V Characteristic  (R = {{R:.1f}} Ohm)", fontsize=12)
ax.legend(fontsize=9)
ax.grid(True, alpha=0.35)
plt.tight_layout()
plt.gcf()
"""
    s.set(6, 3, "PY-plot: I–V characteristic")
    s.fmt(6, 3, italic=True, font_color="#555555")
    s.formula(8, 3, py_plot)
    s.fmt(8, 3, bg=PALETTE["band"], font_family="Courier New", font_size=9)
    s.col_width(3, 210)

    wb.save(OUT_PATH)
    return OUT_PATH


if __name__ == "__main__":
    print("Wrote", build())
