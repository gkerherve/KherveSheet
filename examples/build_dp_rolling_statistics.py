"""Build "Rolling Statistics.ksheet" — data-processing example.

A time-series column plus a window-size input. The =PY cell uses pandas
rolling to compute rolling mean and rolling std, writes them back, and
plots the series with a mean±std band.

Run:  python examples/build_dp_rolling_statistics.py

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
    rng = np.random.default_rng(99)
    N = 150

    t = np.arange(N)
    trend = 0.05 * t
    seasonal = 3.0 * np.sin(2 * np.pi * t / 30)
    noise = rng.normal(0, 1.2, N)
    y = 20.0 + trend + seasonal + noise

    wb = Workbook(min_rows=N + 12, min_cols=14)
    s = wb.add_sheet("Rolling Statistics")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block(
        "Rolling Statistics",
        "Pandas rolling mean and std — edit window size, then Ctrl+Enter",
    )

    # ── Input parameters ───────────────────────────────────────────────
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Window size",  20),
        ("Noise seed",   99),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0")

    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 150)
    s.col_width(1, 80)

    s.note(
        4, 1,
        "Edit the window size (e.g. 5, 10, 20, 50) and press Ctrl+Enter "
        "on the =PY cell. Columns C (rolling mean) and D (rolling std) "
        "update, and the shaded band widens or narrows.",
        kind="note",
    )

    # ── Data columns A (t) and B (y) ───────────────────────────────────
    data_header_row = 7
    data_start = 8  # 0-based row index of first data row

    headers = ["t", "y", "roll_mean", "roll_std"]
    for j, h in enumerate(headers):
        s.set(data_header_row, j, h)
        s.fmt(data_header_row, j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    for c in range(4):
        s.col_width(c, 90)

    for i in range(N):
        r = data_start + i
        s.set(r, 0, int(t[i]))
        s.set(r, 1, round(float(y[i]), 4))
        band = PALETTE["band_alt"] if i % 2 else None
        for c in range(2):
            kw = dict(align="right", number_format="0.000")
            if band:
                kw["bg"] = band
            s.fmt(r, c, **kw)

    s.box(data_header_row, 0, data_start + N - 1, 3,
          color=PALETTE["header"], width=1.0)
    s.designate(0, "X")
    s.designate(1, "Y")
    s.designate(2, "Y")
    s.designate(3, "Y")

    # ── =PY cell in column F, row 4 ────────────────────────────────────
    sheet_data_first = data_start + 1   # 1-based: 9
    sheet_data_last  = data_start + N   # 1-based: 158

    py_code = "\n".join([
        "=PY",
        "import numpy as np",
        "import pandas as pd",
        "import matplotlib.pyplot as plt",
        f"window = int(ks('B5'))",
        f"t_arr  = ks('A{sheet_data_first}:A{sheet_data_last}')",
        f"y_arr  = ks('B{sheet_data_first}:B{sheet_data_last}')",
        "t_arr = t_arr[np.isfinite(t_arr)]",
        "y_arr = y_arr[np.isfinite(y_arr)]",
        "n = min(len(t_arr), len(y_arr))",
        "t_arr, y_arr = t_arr[:n], y_arr[:n]",
        "s_y = pd.Series(y_arr)",
        "roll_mean = s_y.rolling(window, min_periods=1).mean().to_numpy()",
        "roll_std  = s_y.rolling(window, min_periods=1).std().fillna(0).to_numpy()",
        f"ks_set('C{sheet_data_first}', roll_mean.tolist())",
        f"ks_set('D{sheet_data_first}', roll_std.tolist())",
        "fig, ax = plt.subplots(figsize=(9, 5))",
        "ax.plot(t_arr, y_arr, color='#bfbfbf', linewidth=1.0, alpha=0.8, label='Raw')",
        "ax.plot(t_arr, roll_mean, color='#4472c4', linewidth=2.5, label=f'Rolling mean (w={window})')",
        "ax.fill_between(t_arr, roll_mean - roll_std, roll_mean + roll_std,",
        "                color='#4472c4', alpha=0.18, label='±1 std')",
        "ax.set_xlabel('Time step', fontsize=11)",
        "ax.set_ylabel('Value', fontsize=11)",
        "ax.set_title('Rolling Mean ± Std Band', fontsize=12, fontweight='bold')",
        "ax.legend(fontsize=10)",
        "ax.grid(True, alpha=0.3)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])

    py_row = 4
    s.formula(py_row, 5, py_code)
    s.fmt(py_row, 5, font_family="Consolas", font_size=9, wrap=True)
    s.col_width(5, 50)

    s.note(
        py_row, 5,
        "=PY cell: uses pd.Series.rolling() to compute mean and std, "
        "writes them to cols C and D, then plots the raw series "
        "with a shaded ±1 std band.",
        kind="note",
    )

    # ── Save ──────────────────────────────────────────────────────────
    out_dir = os.path.join(_REPO, "examples", "python", "Data Processing")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Rolling Statistics.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
