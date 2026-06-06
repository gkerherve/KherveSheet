"""Build "Remove Outliers.ksheet" — a data-processing Python-cell example.

Embeds a column with a few injected spikes and an IQR-factor threshold cell.
The =PY cell flags outliers, writes a cleaned column (outliers → NaN),
reports how many were removed, and plots original vs cleaned.

Run:  python examples/build_dp_remove_outliers.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

import numpy as np
from ksheet_author import Workbook, PALETTE

N = 60
SEED = 99
SPIKE_INDICES = [5, 18, 31, 47, 55]   # rows that get injected spikes
DATA_ROW_START = 8   # 0-based; sheet row 9
PY_COL = 5           # column F — clear of A..D


def build() -> str:
    rng = np.random.default_rng(SEED)
    t = np.linspace(0, 4 * np.pi, N)
    clean = 2.0 * np.sin(t) + 0.5 * np.cos(2 * t)
    raw = clean + 0.2 * rng.standard_normal(N)
    # Inject spikes
    for idx in SPIKE_INDICES:
        raw[idx] += rng.choice([-1, 1]) * rng.uniform(6.0, 9.0)

    wb = Workbook(min_rows=N + 15, min_cols=12)
    s = wb.add_sheet("Remove Outliers")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block(
        "Remove Outliers",
        "IQR-based outlier detection and removal with editable threshold",
    )

    # ── Parameter block ───────────────────────────────────────────────
    s.set(2, 0, "Parameters")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("IQR factor threshold",  2.5),
        ("Noise seed",           SEED),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.0")

    s.box(3, 0, 4, 1, color=PALETTE["accent"], width=1.0)

    # Summary cells (filled by =PY via ks_set)
    s.set(6, 0, "Outliers removed:")
    s.fmt(6, 0, bold=True)
    s.set(6, 1, "")
    s.fmt(6, 1, bg=PALETTE["bad"], bold=True, align="center", number_format="0")

    s.col_width(0, 200)
    s.col_width(1, 100)
    s.col_width(PY_COL, 460)

    s.note(3, 1,
           "Edit the IQR factor (B4).  Smaller values flag more points "
           "as outliers; typical range 1.5–3.0.  "
           "Press Ctrl+Enter on the =PY cell in column F.",
           kind="note")

    # ── Data table header ─────────────────────────────────────────────
    hdr_row = DATA_ROW_START - 1
    for c, label in enumerate(["Index", "Raw", "Cleaned", "Outlier?"]):
        s.set(hdr_row, c, label)
        s.fmt(hdr_row, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    s.col_width(0, 70)
    s.col_width(2, 100)
    s.col_width(3, 90)

    # ── Data rows ─────────────────────────────────────────────────────
    for i in range(N):
        r = DATA_ROW_START + i
        band = PALETTE["band_alt"] if i % 2 else None
        s.set(r, 0, i + 1)
        s.set(r, 1, round(float(raw[i]), 5))
        s.fmt(r, 1, number_format="0.00000",
              bg=band if band else None)
        s.set(r, 2, "")
        s.set(r, 3, "")

    s.box(hdr_row, 0, DATA_ROW_START + N - 1, 3,
          color=PALETTE["header"], width=1.0)

    s.note(hdr_row, 1,
           "Column B = raw signal (spikes injected at rows "
           + ", ".join(str(DATA_ROW_START + 1 + k) for k in SPIKE_INDICES)
           + ").  Columns C and D are filled by the =PY cell.",
           kind="note")

    # ── =PY cell ──────────────────────────────────────────────────────
    first_data = DATA_ROW_START + 1   # 1-based = 9
    last_data  = DATA_ROW_START + N   # 1-based = 68
    # B4=IQR factor  (B7=summary cell for count)
    py_code = f"""\
=PY
import numpy as np
import matplotlib.pyplot as plt

factor = float(ks("B4"))
y = np.asarray(ks("B{first_data}:B{last_data}"), dtype=float)

# IQR-based outlier detection
q1, q3 = np.percentile(y, 25), np.percentile(y, 75)
iqr = q3 - q1
lo  = q1 - factor * iqr
hi  = q3 + factor * iqr
is_outlier = (y < lo) | (y > hi)

cleaned = y.copy()
cleaned[is_outlier] = np.nan
n_removed = int(is_outlier.sum())

# Flag column: 1 = outlier, 0 = ok
flags = is_outlier.astype(float)

# ks_set cannot handle NaN — replace with empty string
cleaned_list = ["" if np.isnan(v) else float(v) for v in cleaned]
ks_set("C{first_data}", cleaned_list)
ks_set("D{first_data}", flags.tolist())
ks_set("B7",  n_removed)

# Plot
idx = np.arange(1, len(y) + 1)
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(idx, y, color="#bfbfbf", linewidth=1.0, label="Raw")
ax.plot(idx, cleaned, color="#4472c4", linewidth=1.8, label="Cleaned")
spike_idx = np.where(is_outlier)[0]
ax.scatter(spike_idx + 1, y[spike_idx], color="#c00000", zorder=5,
           s=60, label="Outliers (%d)" % n_removed)
ax.axhline(hi, color="#ed7d31", linestyle="--", linewidth=1.0,
           label="Upper fence (%.2f)" % hi)
ax.axhline(lo, color="#ed7d31", linestyle=":",  linewidth=1.0,
           label="Lower fence (%.2f)" % lo)
ax.set_xlabel("Sample index", fontsize=11)
ax.set_ylabel("Value", fontsize=11)
ax.set_title("Outlier Removal (IQR factor = %.1f)" % factor,
             fontsize=12, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.35)
fig.tight_layout()
plt.gcf()
"""

    s.formula(DATA_ROW_START - 1, PY_COL, py_code)
    s.fmt(DATA_ROW_START - 1, PY_COL,
          font_family="Consolas", font_size=9, wrap=True)

    s.note(DATA_ROW_START - 1, PY_COL,
           "=PY cell: IQR outlier detection; writes cleaned column "
           "to C, outlier flags to D, and count to B7.",
           kind="note")

    # ── Equation ──────────────────────────────────────────────────────
    s.equation(
        r"x_i \text{ is outlier if } x_i < Q_1 - k \cdot IQR"
        r" \text{ or } x_i > Q_3 + k \cdot IQR",
        at=(560, 30), fontsize=14, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(390, 46),
    )

    out = os.path.join(
        _REPO, "examples", "python", "Data Processing",
        "Remove Outliers.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
