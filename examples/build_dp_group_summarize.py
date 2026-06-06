"""Build "Group and Summarize.ksheet" — data-processing example.

A small table with a category column and a value column. The =PY cell
uses pandas groupby to compute per-category count/mean/sum, writes the
summary table back to a results area, and draws a bar chart of per-category
mean.

Run:  python examples/build_dp_group_summarize.py

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
    rng = np.random.default_rng(7)

    categories = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
    n_per = 12  # rows per category
    N = len(categories) * n_per  # 60 rows total

    cats = []
    vals = []
    base_means = [42.0, 67.0, 55.0, 81.0, 33.0]
    for i, (cat, mean) in enumerate(zip(categories, base_means)):
        cats.extend([cat] * n_per)
        vals.extend(rng.normal(mean, 8.0, n_per).tolist())

    # Shuffle together
    idx = rng.permutation(N)
    cats = [cats[i] for i in idx]
    vals = [vals[i] for i in idx]

    wb = Workbook(min_rows=N + 20, min_cols=16)
    s = wb.add_sheet("Group and Summarize")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block(
        "Group and Summarize",
        "Pandas groupby — per-category count, mean, sum — press Ctrl+Enter",
    )

    # ── Input parameters (just a note; data is fixed) ──────────────────
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    s.set(4, 0, "Noise seed")
    s.set(4, 1, 7)
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0")
    s.box(4, 0, 4, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 120)
    s.col_width(1, 80)

    s.note(
        4, 1,
        "The raw data table (cols A–B) is fixed at generation time. "
        "Press Ctrl+Enter on the =PY cell to (re-)compute the groupby "
        "summary in cols D–G and refresh the bar chart.",
        kind="note",
    )

    # ── Raw data table: col A (category), col B (value) ────────────────
    data_header_row = 6
    data_start = 7  # 0-based row index of first data row

    s.set(data_header_row, 0, "category")
    s.set(data_header_row, 1, "value")
    for c in range(2):
        s.fmt(data_header_row, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    s.col_width(0, 90)
    s.col_width(1, 80)

    for i in range(N):
        r = data_start + i
        s.set(r, 0, cats[i])
        s.set(r, 1, round(float(vals[i]), 3))
        band = PALETTE["band_alt"] if i % 2 else None
        s.fmt(r, 0, align="left", **({"bg": band} if band else {}))
        s.fmt(r, 1, align="right", number_format="0.00",
              **({"bg": band} if band else {}))

    s.box(data_header_row, 0, data_start + N - 1, 1,
          color=PALETTE["header"], width=1.0)

    # ── Results area: cols D–G, headers at row 6 ───────────────────────
    result_col_start = 3  # col D
    res_headers = ["category", "count", "mean", "sum"]
    for j, h in enumerate(res_headers):
        c = result_col_start + j
        s.set(data_header_row, c, h)
        s.fmt(data_header_row, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    for j in range(4):
        s.col_width(result_col_start + j, 85)

    # ── =PY cell in column I, row 4 (clear of A-G) ────────────────────
    sheet_data_first = data_start + 1   # 1-based: 8
    sheet_data_last  = data_start + N   # 1-based: 67
    result_first_1b  = data_header_row + 2  # 1-based: 9 (row after header)
    # result columns: D=4th col (E in 1-based?), let's map:
    # col index 3 (D) → "D", 4 → "E", 5 → "F", 6 → "G"

    py_code = "\n".join([
        "=PY",
        "import numpy as np",
        "import pandas as pd",
        "import matplotlib.pyplot as plt",
        f"cats_raw = ks('A{sheet_data_first}:A{sheet_data_last}')",
        f"vals_raw = ks('B{sheet_data_first}:B{sheet_data_last}')",
        "# ks returns a list for text columns, ndarray for numeric columns",
        "cats = [str(c) if c is not None else '' for c in cats_raw]",
        "vals_arr = np.array([v if v is not None else float('nan')",
        "                     for v in (vals_raw.tolist() if hasattr(vals_raw, 'tolist') else vals_raw)],",
        "                    dtype=float)",
        "df = pd.DataFrame({'cat': cats, 'val': vals_arr})",
        "df = df[df['cat'].str.strip() != '']",
        "grp = df.groupby('cat')['val'].agg(['count', 'mean', 'sum']).reset_index()",
        "grp.columns = ['category', 'count', 'mean', 'sum']",
        "grp = grp.sort_values('category').reset_index(drop=True)",
        "n_grp = len(grp)",
        f"ks_set('D{result_first_1b}', grp['category'].tolist())",
        f"ks_set('E{result_first_1b}', grp['count'].tolist())",
        f"ks_set('F{result_first_1b}', grp['mean'].round(3).tolist())",
        f"ks_set('G{result_first_1b}', grp['sum'].round(3).tolist())",
        "colors = ['#4472c4', '#ed7d31', '#70ad47', '#a5a5a5', '#ffc000']",
        "fig, axes = plt.subplots(1, 2, figsize=(10, 4))",
        "ax0 = axes[0]",
        "ax0.bar(grp['category'], grp['mean'],",
        "        color=colors[:n_grp], edgecolor='white', linewidth=0.5)",
        "ax0.set_xlabel('Category', fontsize=10)",
        "ax0.set_ylabel('Mean value', fontsize=10)",
        "ax0.set_title('Mean per Category', fontsize=10, fontweight='bold')",
        "ax0.grid(True, axis='y', alpha=0.3)",
        "ax1 = axes[1]",
        "ax1.bar(grp['category'], grp['count'],",
        "        color=colors[:n_grp], edgecolor='white', linewidth=0.5)",
        "ax1.set_xlabel('Category', fontsize=10)",
        "ax1.set_ylabel('Count', fontsize=10)",
        "ax1.set_title('Count per Category', fontsize=10, fontweight='bold')",
        "ax1.grid(True, axis='y', alpha=0.3)",
        "plt.suptitle('Group and Summarize', fontsize=12, fontweight='bold')",
        "plt.tight_layout()",
        "plt.gcf()",
    ])

    py_row = 4
    s.formula(py_row, 8, py_code)   # column I (index 8)
    s.fmt(py_row, 8, font_family="Consolas", font_size=9, wrap=True)
    s.col_width(8, 50)

    s.note(
        py_row, 8,
        "=PY cell: reads category (col A) and value (col B) with ks(), "
        "runs pd.DataFrame.groupby, writes count/mean/sum to cols D-G, "
        "then plots per-category mean and count as bar charts.",
        kind="note",
    )

    # ── Save ──────────────────────────────────────────────────────────
    out_dir = os.path.join(_REPO, "examples", "python", "Data Processing")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Group and Summarize.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
