"""Build "Baseline Correction.ksheet" — data-processing example.

A spectrum-like y column with a sloping/curved baseline plus an x column
and a polynomial-degree input. The =PY cell fits a polynomial baseline,
writes the baseline and corrected columns back, and plots raw, baseline,
and corrected on the same axes.

Run:  python examples/build_dp_baseline_correction.py

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
    rng = np.random.default_rng(17)
    N = 80

    x = np.linspace(200, 800, N)
    # Baseline: sloping + gentle quadratic drift
    baseline_true = 0.004 * x + 0.000003 * (x - 500) ** 2 + 0.5
    # Peak: Gaussian at 450 and 620
    peak = (
        2.5 * np.exp(-((x - 450) ** 2) / (2 * 30 ** 2))
        + 1.8 * np.exp(-((x - 620) ** 2) / (2 * 25 ** 2))
    )
    y_raw = peak + baseline_true + 0.05 * rng.standard_normal(N)

    wb = Workbook(min_rows=N + 10, min_cols=16)
    s = wb.add_sheet("Baseline Correction")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block(
        "Baseline Correction",
        "Polynomial background subtraction — edit degree, then Ctrl+Enter",
    )

    # ── Input parameters ───────────────────────────────────────────────
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Polynomial degree", 2),
        ("Noise seed",        17),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0")

    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 170)
    s.col_width(1, 80)

    s.note(
        4, 1,
        "Change the polynomial degree (1=linear, 2=quadratic, 3=cubic) "
        "and press Ctrl+Enter on the =PY cell. "
        "Columns C and D update with baseline and corrected signal.",
        kind="note",
    )

    # ── Data columns: A (x), B (y raw) ────────────────────────────────
    # Header row at row index 7 (sheet row 8)
    data_header_row = 7
    data_start = 8  # first data row index (0-based)

    s.set(data_header_row, 0, "x")
    s.set(data_header_row, 1, "y_raw")
    s.set(data_header_row, 2, "baseline")
    s.set(data_header_row, 3, "corrected")
    for c in range(4):
        s.fmt(
            data_header_row, c,
            bold=True, bg=PALETTE["header"],
            font_color=PALETTE["header_text"], align="center",
        )
    s.col_width(0, 75)
    s.col_width(1, 80)
    s.col_width(2, 85)
    s.col_width(3, 90)

    for i in range(N):
        r = data_start + i
        s.set(r, 0, round(float(x[i]), 3))
        s.set(r, 1, round(float(y_raw[i]), 5))
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

    # ── =PY cell (placed in column F, clear of A-D) ────────────────────
    # data_start (0-based) = 8 → sheet row 9 → "A9"
    # last data row (0-based) = data_start + N - 1 = 87 → sheet row 88 → "A88"
    sheet_data_first = data_start + 1       # 1-based: 9
    sheet_data_last  = data_start + N       # 1-based: 88 (= data_start + N)
    # baseline writes to C9:C88, corrected to D9:D88

    py_code = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        f"deg = int(ks('B5'))",
        f"x   = ks('A{sheet_data_first}:A{sheet_data_last}')",
        f"y   = ks('B{sheet_data_first}:B{sheet_data_last}')",
        "x = x[np.isfinite(x)]",
        "y = y[np.isfinite(y)]",
        "n = min(len(x), len(y))",
        "x, y = x[:n], y[:n]",
        "# Fit polynomial baseline to the signal ends (first + last 10%)",
        "mask = np.zeros(n, dtype=bool)",
        "edge = max(1, n // 10)",
        "mask[:edge] = True",
        "mask[-edge:] = True",
        "coeffs = np.polyfit(x[mask], y[mask], deg)",
        "bl = np.polyval(coeffs, x)",
        "corr = y - bl",
        f"ks_set('C{sheet_data_first}', bl.tolist())",
        f"ks_set('D{sheet_data_first}', corr.tolist())",
        "fig, ax = plt.subplots(figsize=(8, 5))",
        "ax.plot(x, y,    color='#bfbfbf', linewidth=1.0, label='Raw')",
        "ax.plot(x, bl,   color='#ed7d31', linewidth=2.0, linestyle='--', label=f'Baseline (deg {deg})')",
        "ax.plot(x, corr, color='#4472c4', linewidth=2.0, label='Corrected')",
        "ax.axhline(0, color='#888888', linewidth=0.7, linestyle=':')",
        "ax.set_xlabel('x', fontsize=11)",
        "ax.set_ylabel('Intensity', fontsize=11)",
        "ax.set_title('Polynomial Baseline Correction', fontsize=12, fontweight='bold')",
        "ax.legend(fontsize=10)",
        "ax.grid(True, alpha=0.3)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])

    py_row = 4   # place =PY at row index 4, col 5 (column F)
    s.formula(py_row, 5, py_code)
    s.fmt(py_row, 5, font_family="Consolas", font_size=9, wrap=True)
    s.col_width(5, 50)

    s.note(
        py_row, 5,
        "=PY cell: reads x (col A) and y_raw (col B), "
        "fits a polynomial to the spectrum edges, writes "
        "baseline to col C and corrected signal to col D.",
        kind="note",
    )

    # ── Save ──────────────────────────────────────────────────────────
    out_dir = os.path.join(_REPO, "examples", "python", "Data Processing")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Baseline Correction.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
