"""Build "Bin and Aggregate.ksheet" — data-processing example.

A raw-values column plus a bin-count input. The =PY cell computes a
histogram (bin centres and counts), writes them to result columns, and
draws a bar chart.

Run:  python examples/build_dp_bin_aggregate.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE


def build() -> str:
    rng = np.random.default_rng(42)
    N = 120  # raw data points

    # Bimodal distribution
    raw = np.concatenate([
        rng.normal(40, 8, 70),
        rng.normal(75, 6, 50),
    ])
    raw = np.sort(raw)

    wb = Workbook(min_rows=N + 15, min_cols=14)
    s = wb.add_sheet("Bin and Aggregate")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block(
        "Bin and Aggregate",
        "Histogram from raw values — edit bin count, then Ctrl+Enter",
    )

    # ── Input parameters ───────────────────────────────────────────────
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Number of bins",  15),
        ("Noise seed",      42),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0")

    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 160)
    s.col_width(1, 80)

    s.note(
        4, 1,
        "Change the number of bins (e.g. 5, 10, 20, 30) and press "
        "Ctrl+Enter on the =PY cell. "
        "Columns C (bin centres) and D (counts) update automatically.",
        kind="note",
    )

    # ── Raw data column A ──────────────────────────────────────────────
    data_header_row = 7
    data_start = 8  # 0-based row index of first data row

    s.set(data_header_row, 0, "value")
    s.fmt(data_header_row, 0, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")

    for i, v in enumerate(raw):
        r = data_start + i
        s.set(r, 0, round(float(v), 4))
        if i % 2:
            s.fmt(r, 0, bg=PALETTE["band_alt"], align="right",
                  number_format="0.00")
        else:
            s.fmt(r, 0, align="right", number_format="0.00")

    s.box(data_header_row, 0, data_start + N - 1, 0,
          color=PALETTE["header"], width=1.0)
    s.col_width(0, 90)

    # ── Result columns: C = bin_centre, D = count ──────────────────────
    # Reserve headers at row 7 (same header row)
    s.set(data_header_row, 2, "bin_centre")
    s.set(data_header_row, 3, "count")
    for c in (2, 3):
        s.fmt(data_header_row, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    s.col_width(2, 95)
    s.col_width(3, 75)

    # ── =PY cell in column F, row 4 (clear of data/result cols A-D) ────
    sheet_data_first = data_start + 1   # 1-based: 9
    sheet_data_last  = data_start + N   # 1-based: 128
    result_first     = data_header_row + 2  # 1-based: 10 (row after header, 1-based)

    py_code = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        f"n_bins = int(ks('B5'))",
        f"raw    = ks('A{sheet_data_first}:A{sheet_data_last}')",
        "raw = raw[np.isfinite(raw)]",
        "counts, edges = np.histogram(raw, bins=n_bins)",
        "centres = 0.5 * (edges[:-1] + edges[1:])",
        f"ks_set('C{result_first}', centres.tolist())",
        f"ks_set('D{result_first}', counts.tolist())",
        "fig, axes = plt.subplots(1, 2, figsize=(10, 4))",
        "# Left: strip plot of raw values",
        "ax0 = axes[0]",
        "ax0.scatter(raw, np.zeros_like(raw), s=12, alpha=0.45,",
        "            color='#4472c4', marker='|', linewidths=1.2)",
        "ax0.set_xlabel('Value', fontsize=10)",
        "ax0.set_yticks([])",
        "ax0.set_title('Raw data strip', fontsize=10)",
        "ax0.grid(True, axis='x', alpha=0.3)",
        "# Right: histogram bars",
        "ax1 = axes[1]",
        "width = centres[1] - centres[0] if len(centres) > 1 else 1.0",
        "ax1.bar(centres, counts, width=width * 0.85,",
        "        color='#4472c4', edgecolor='white', linewidth=0.5)",
        "ax1.set_xlabel('Bin centre', fontsize=10)",
        "ax1.set_ylabel('Count', fontsize=10)",
        "ax1.set_title(f'Histogram  ({n_bins} bins)', fontsize=10)",
        "ax1.grid(True, axis='y', alpha=0.3)",
        "plt.suptitle('Bin and Aggregate', fontsize=12, fontweight='bold')",
        "plt.tight_layout()",
        "plt.gcf()",
    ])

    py_row = 4
    s.formula(py_row, 5, py_code)
    s.fmt(py_row, 5, font_family="Consolas", font_size=9, wrap=True)
    s.col_width(5, 50)

    s.note(
        py_row, 5,
        "=PY cell: reads raw values from col A, bins them with "
        "np.histogram, writes bin centres to col C and counts to col D, "
        "then renders a histogram bar chart.",
        kind="note",
    )

    # ── Save ──────────────────────────────────────────────────────────
    out_dir = os.path.join(_REPO, "examples", "python", "Data Processing")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Bin and Aggregate.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
