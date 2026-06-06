"""Build "Fill Missing Values.ksheet" — a data-processing Python-cell example.

Embeds an x column and a y column with deliberate gaps (blank cells at
known indices).  The =PY cell linearly interpolates the gaps, writes the
filled column back, reports how many were filled, and plots original points
vs the filled curve highlighting the filled positions.

Run:  python examples/build_dp_fill_missing.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

import numpy as np
from ksheet_author import Workbook, PALETTE

N = 50
SEED = 17
# Indices (0-based within the data) that will be left blank
GAP_INDICES = [4, 5, 14, 22, 23, 24, 35, 42]
DATA_ROW_START = 8   # 0-based; sheet row 9
PY_COL = 5           # column F — clear of A..D


def build() -> str:
    rng = np.random.default_rng(SEED)
    x_full = np.linspace(0, 10, N)
    y_full = np.sin(x_full) + 0.3 * rng.standard_normal(N)

    wb = Workbook(min_rows=N + 15, min_cols=12)
    s = wb.add_sheet("Fill Missing")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block(
        "Fill Missing Values",
        "Linear interpolation of blank cells; editable x and y columns",
    )

    # ── Summary cells (filled by =PY) ─────────────────────────────────
    s.set(2, 0, "Parameters / Summary")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    s.set(3, 0, "Values filled:")
    s.fmt(3, 0, bold=True)
    s.set(3, 1, "")
    s.fmt(3, 1, bg=PALETTE["good"], bold=True, align="center", number_format="0")

    s.set(4, 0, "Total data points:")
    s.fmt(4, 0, bold=True)
    s.set(4, 1, N)
    s.fmt(4, 1, align="center", number_format="0")

    s.box(3, 0, 4, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 180)
    s.col_width(1, 90)
    s.col_width(PY_COL, 460)

    s.note(3, 1,
           "This cell is written by the =PY cell via ks_set.  "
           "To add more gaps: clear any cell in column B, then "
           "press Ctrl+Enter on the =PY cell in column F.",
           kind="note")

    # ── Data table header ─────────────────────────────────────────────
    hdr_row = DATA_ROW_START - 1
    for c, label in enumerate(["x", "y (with gaps)", "y (filled)", "Was gap?"]):
        s.set(hdr_row, c, label)
        s.fmt(hdr_row, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    s.col_width(2, 110)
    s.col_width(3, 90)

    # ── Data rows — leave GAP_INDICES blank in y ──────────────────────
    for i in range(N):
        r = DATA_ROW_START + i
        band = PALETTE["band_alt"] if i % 2 else None
        s.set(r, 0, round(float(x_full[i]), 4))
        s.fmt(r, 0, number_format="0.0000", bg=band if band else None)
        if i in GAP_INDICES:
            s.set(r, 1, "")   # deliberate gap
        else:
            s.set(r, 1, round(float(y_full[i]), 5))
            s.fmt(r, 1, number_format="0.00000", bg=band if band else None)
        s.set(r, 2, "")
        s.set(r, 3, "")

    s.box(hdr_row, 0, DATA_ROW_START + N - 1, 3,
          color=PALETTE["header"], width=1.0)

    s.note(hdr_row, 1,
           "Blank cells in column B are the gaps to fill.  "
           "Column A must be monotonically increasing for linear "
           "interpolation to work correctly.",
           kind="note")

    # ── =PY cell ──────────────────────────────────────────────────────
    first_data = DATA_ROW_START + 1   # 1-based = 9
    last_data  = DATA_ROW_START + N   # 1-based = 58
    py_code = f"""\
=PY
import numpy as np
import matplotlib.pyplot as plt

x_all = np.asarray(ks("A{first_data}:A{last_data}"), dtype=float)
y_raw = np.asarray(ks("B{first_data}:B{last_data}"), dtype=float)
# NaN = blank cells (the gaps)
is_gap = ~np.isfinite(y_raw)
n_filled = int(is_gap.sum())

# Linear interpolation: use known points to fill gaps
x_known = x_all[~is_gap]
y_known = y_raw[~is_gap]
y_filled = np.interp(x_all, x_known, y_known)

# Flag column: 1 = was gap, 0 = original
flags = is_gap.astype(float)

ks_set("C{first_data}", y_filled.tolist())
ks_set("D{first_data}", flags.tolist())
ks_set("B4",  n_filled)

# Plot
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(x_all, y_filled, color="#4472c4", linewidth=1.5, label="Filled curve")
ax.scatter(x_all[~is_gap], y_raw[~is_gap], color="#4472c4", s=30, zorder=4,
           label="Original points")
ax.scatter(x_all[is_gap], y_filled[is_gap], color="#ed7d31", s=60, zorder=5,
           marker="^", label=f"Filled ({{n_filled}} points)")
ax.set_xlabel("x", fontsize=11)
ax.set_ylabel("y", fontsize=11)
ax.set_title("Fill Missing Values — Linear Interpolation",
             fontsize=12, fontweight="bold")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.35)
fig.tight_layout()
plt.gcf()
"""

    s.formula(DATA_ROW_START - 1, PY_COL, py_code)
    s.fmt(DATA_ROW_START - 1, PY_COL,
          font_family="Consolas", font_size=9, wrap=True)

    s.note(DATA_ROW_START - 1, PY_COL,
           "=PY cell: reads A/B columns, linearly interpolates gaps, "
           "writes filled y → C, flags → D, count → B4.",
           kind="note")

    # ── Equation ──────────────────────────────────────────────────────
    s.equation(
        r"y_i = y_a + \frac{x_i - x_a}{x_b - x_a}(y_b - y_a)",
        at=(570, 30), fontsize=17, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(310, 52),
    )

    out = os.path.join(
        _REPO, "examples", "python", "Data Processing",
        "Fill Missing Values.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
