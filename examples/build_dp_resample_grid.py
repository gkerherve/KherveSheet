"""Build "Resample to Grid.ksheet" — a data-processing Python-cell example.

Embeds irregular x and y columns (45 samples drawn from a non-uniform
distribution) and a target-count parameter cell.  The =PY cell interpolates
onto an evenly spaced grid spanning [x_min, x_max], writes the new x and y
back with ks_set, and plots original scatter vs the resampled line.

Run:  python examples/build_dp_resample_grid.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

import numpy as np
from ksheet_author import Workbook, PALETTE

N_ORIG = 45          # irregular sample count
N_TARGET = 100       # default resample count
SEED = 31
DATA_ROW_START = 8   # 0-based; sheet row 9
# irregular data: cols A(0) and B(1)
# resampled:      cols C(2) and D(3)
PY_COL = 6           # column G — clear of A..D


def build() -> str:
    rng = np.random.default_rng(SEED)
    # Generate irregular x (clustered towards edges)
    u = rng.uniform(0, 1, N_ORIG)
    x_irr = np.sort(10.0 * (u ** 2 + 0.1 * rng.standard_normal(N_ORIG).clip(-0.5, 0.5)))
    x_irr = np.clip(x_irr, 0, 10)
    y_irr = np.sin(x_irr) * np.exp(-0.1 * x_irr) + 0.15 * rng.standard_normal(N_ORIG)

    # Pre-compute what the resampled grid looks like (for display only)
    x_grid = np.linspace(x_irr[0], x_irr[-1], N_TARGET)
    y_grid = np.interp(x_grid, x_irr, y_irr)

    wb = Workbook(min_rows=max(N_ORIG, N_TARGET) + 15, min_cols=12)
    s = wb.add_sheet("Resample")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block(
        "Resample to Grid",
        "Interpolate irregular (x, y) data onto an evenly spaced grid",
    )

    # ── Parameter block ───────────────────────────────────────────────
    s.set(2, 0, "Parameters")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Target grid points M",  N_TARGET),
        ("Noise seed",            SEED),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0")

    s.box(3, 0, 4, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 200)
    s.col_width(1, 90)
    s.col_width(PY_COL, 460)

    s.note(3, 1,
           "Edit the target grid point count M (B4).  "
           "Press Ctrl+Enter on the =PY cell in column G to update "
           "columns C and D with the resampled x and y.",
           kind="note")

    # ── Data table headers ────────────────────────────────────────────
    hdr_row = DATA_ROW_START - 1
    for c, label in enumerate(["x (irregular)", "y (irregular)",
                                "x (resampled)", "y (resampled)"]):
        s.set(hdr_row, c, label)
        s.fmt(hdr_row, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    for c in range(4):
        s.col_width(c, 120)

    # ── Data rows — irregular data in A/B; C/D seeded from resample ───
    max_rows = max(N_ORIG, N_TARGET)
    for i in range(max_rows):
        r = DATA_ROW_START + i
        band = PALETTE["band_alt"] if i % 2 else None

        if i < N_ORIG:
            s.set(r, 0, round(float(x_irr[i]), 5))
            s.set(r, 1, round(float(y_irr[i]), 5))
            s.fmt(r, 0, number_format="0.00000", bg=band if band else None)
            s.fmt(r, 1, number_format="0.00000", bg=band if band else None)
        else:
            s.set(r, 0, "")
            s.set(r, 1, "")

        # C and D filled by =PY
        s.set(r, 2, "")
        s.set(r, 3, "")

    s.box(hdr_row, 0, DATA_ROW_START + max_rows - 1, 3,
          color=PALETTE["header"], width=1.0)

    s.note(hdr_row, 0,
           "Columns A and B = irregularly sampled data (edit freely).  "
           "Columns C and D = evenly spaced grid, computed by the =PY cell.",
           kind="note")

    # ── =PY cell ──────────────────────────────────────────────────────
    first_irr = DATA_ROW_START + 1        # 1-based = 9
    last_irr  = DATA_ROW_START + N_ORIG   # 1-based = 53
    first_out = DATA_ROW_START + 1        # 1-based = 9 (C9 and D9)

    py_code = f"""\
=PY
import numpy as np
import matplotlib.pyplot as plt

M = max(2, int(ks("B4")))

# Read irregular data (filter out NaN / blank rows)
x_all = np.asarray(ks("A{first_irr}:A{last_irr}"), dtype=float)
y_all = np.asarray(ks("B{first_irr}:B{last_irr}"), dtype=float)
ok    = np.isfinite(x_all) & np.isfinite(y_all)
x_irr = x_all[ok]
y_irr = y_all[ok]

# Sort by x (required for np.interp)
order = np.argsort(x_irr)
x_irr = x_irr[order]
y_irr = y_irr[order]

# Build even grid and interpolate
x_grid = np.linspace(x_irr[0], x_irr[-1], M)
y_grid = np.interp(x_grid, x_irr, y_irr)

# Pad with NaN to fill any leftover rows from a previous run
pad = [""] * max(0, {N_ORIG} - M)
ks_set("C{first_out}", x_grid.tolist() + pad)
ks_set("D{first_out}", y_grid.tolist() + pad)

# Plot
fig, ax = plt.subplots(figsize=(8, 4))
ax.scatter(x_irr, y_irr, color="#bfbfbf", s=40, zorder=3,
           label=f"Irregular ({{len(x_irr)}} pts)")
ax.plot(x_grid, y_grid, color="#4472c4", linewidth=2.0, zorder=2,
        label=f"Resampled grid (M={{M}})")
ax.set_xlabel("x", fontsize=11)
ax.set_ylabel("y", fontsize=11)
ax.set_title("Resample Irregular Data onto an Even Grid",
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
           "=PY cell: reads A9:A53 and B9:B53, builds a uniform grid "
           "of M points, writes resampled x → C9 and y → D9 (downward).",
           kind="note")

    # ── Equation ──────────────────────────────────────────────────────
    s.equation(
        r"x_i^{\mathrm{grid}} = x_{\min} + \frac{i}{M-1}(x_{\max}-x_{\min}),\;"
        r"\quad i=0,\ldots,M-1",
        at=(560, 30), fontsize=14, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(400, 50),
    )

    out = os.path.join(
        _REPO, "examples", "python", "Data Processing",
        "Resample to Grid.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
