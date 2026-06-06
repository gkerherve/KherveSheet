"""Build "Normalize Column.ksheet" — a data-processing Python-cell example.

Embeds a raw numeric column of 50 seeded values.  The =PY cell reads the
column, computes min-max scaling (0..1) and z-score normalisation, writes
both back with ks_set into adjacent columns, and plots all three series.

Run:  python examples/build_dp_normalize_column.py

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
SEED = 42
DATA_ROW_START = 5   # 0-based row of first data row (sheet row 6)
PY_COL = 4           # column E — clear of A, B, C (data+results)


def build() -> str:
    rng = np.random.default_rng(SEED)
    raw = rng.normal(loc=50.0, scale=15.0, size=N)

    wb = Workbook(min_rows=N + 10, min_cols=10)
    s = wb.add_sheet("Normalize")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block(
        "Normalize Column",
        "Min-max scaling (0–1) and z-score normalisation of a raw column",
    )

    # ── Data table header ─────────────────────────────────────────────
    # Columns: A=raw, B=min-max, C=z-score  (0-based: 0, 1, 2)
    hdr_row = DATA_ROW_START - 1  # row 4 (0-based), sheet row 5
    for c, label in enumerate(["Raw value", "Min-max (0–1)", "Z-score"]):
        s.set(hdr_row, c, label)
        s.fmt(hdr_row, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    s.col_width(0, 120)
    s.col_width(1, 130)
    s.col_width(2, 120)
    s.col_width(PY_COL, 460)

    # ── Raw data column ───────────────────────────────────────────────
    for i, v in enumerate(raw):
        r = DATA_ROW_START + i
        s.set(r, 0, round(float(v), 4))
        s.fmt(r, 0, number_format="0.0000",
              bg=(PALETTE["band_alt"] if i % 2 else None))
        # result cells start blank; =PY will fill them
        s.set(r, 1, "")
        s.set(r, 2, "")

    s.box(hdr_row, 0, DATA_ROW_START + N - 1, 2,
          color=PALETTE["header"], width=1.0)

    # ── Instruction note ──────────────────────────────────────────────
    s.note(hdr_row, 0,
           "Column A holds the raw data (edit any value, then "
           "press Ctrl+Enter on the =PY cell in column E to update "
           "the normalised columns and chart).",
           kind="note")

    # ── =PY cell — placed in column E, clear of A/B/C ─────────────────
    # 1-based refs: A6:A55 = raw data (rows 6..55)
    first_data = DATA_ROW_START + 1          # 1-based = 6
    last_data  = DATA_ROW_START + N          # 1-based = 55
    py_code = f"""\
=PY
import numpy as np
import matplotlib.pyplot as plt

# Read the raw column (NaN for blanks, filter to be safe)
raw = ks("A{first_data}:A{last_data}")
raw = np.asarray(raw, dtype=float)
finite = np.isfinite(raw)
r = raw.copy()

# Min-max normalisation
mn, mx = r[finite].min(), r[finite].max()
mm = np.where(finite, (r - mn) / (mx - mn), 0.0)

# Z-score
mu, sd = r[finite].mean(), r[finite].std()
zs = np.where(finite, (r - mu) / sd, 0.0)

# Write results back (round to avoid tiny floating point noise)
ks_set("B{first_data}", [round(float(v), 6) for v in mm])
ks_set("C{first_data}", [round(float(v), 6) for v in zs])

# Plot
fig, axes = plt.subplots(1, 3, figsize=(10, 4), constrained_layout=True)
idx = np.arange(1, len(r) + 1)
axes[0].bar(idx, r,  color="#4472c4", width=0.8, alpha=0.85)
axes[0].set_title("Raw", fontsize=11)
axes[0].set_xlabel("Row index"); axes[0].set_ylabel("Value")
axes[0].grid(axis="y", alpha=0.35)

axes[1].bar(idx, mm, color="#70ad47", width=0.8, alpha=0.85)
axes[1].set_title("Min-max normalised (0–1)", fontsize=11)
axes[1].set_xlabel("Row index")
axes[1].axhline(0.5, color="#ed7d31", linestyle="--", linewidth=1.0)
axes[1].grid(axis="y", alpha=0.35)

axes[2].bar(idx, zs, color="#ed7d31", width=0.8, alpha=0.85)
axes[2].set_title("Z-score", fontsize=11)
axes[2].set_xlabel("Row index")
axes[2].axhline(0, color="#000000", linestyle="-", linewidth=0.8)
axes[2].grid(axis="y", alpha=0.35)

fig.suptitle("Column Normalisation", fontsize=13, fontweight="bold")
plt.gcf()
"""

    s.formula(DATA_ROW_START - 1, PY_COL, py_code)
    s.fmt(DATA_ROW_START - 1, PY_COL,
          font_family="Consolas", font_size=9, wrap=True)

    s.note(DATA_ROW_START - 1, PY_COL,
           "=PY cell: reads A6:A55, writes min-max into B6:B55 and "
           "z-score into C6:C55 via ks_set, then plots all three.",
           kind="note")

    # ── Equation ──────────────────────────────────────────────────────
    s.equation(
        r"\hat{x} = \frac{x - x_{min}}{x_{max} - x_{min}}, \quad"
        r" z = \frac{x - \mu}{\sigma}",
        at=(580, 30), fontsize=16, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(330, 50),
    )

    out = os.path.join(
        _REPO, "examples", "python", "Data Processing",
        "Normalize Column.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
