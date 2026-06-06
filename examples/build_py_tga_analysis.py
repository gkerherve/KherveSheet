"""Build "TGA Analysis.ksheet" — a Python-cell materials-science example.

Simulates a thermogravimetric analysis (TGA) curve with two or three
mass-loss steps.  A =PY cell computes the DTG (derivative), reports
% mass loss per region, and plots weight (left axis) vs DTG (right axis).

Row/column mapping: set(r, c, v) -> sheet cell letter(c) + str(r+1).

Run:  python examples/build_py_tga_analysis.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

import numpy as np
from ksheet_author import Workbook, PALETTE


def build() -> str:
    # ── Synthetic TGA curve ────────────────────────────────────────────
    rng = np.random.default_rng(7)

    # Three decomposition steps: surface water ~100°C, organic ~300°C, carbonate ~600°C
    T = np.linspace(25, 900, 876)   # 1 °C / step

    def sigmoid_step(T, T50, width, delta):
        """Mass loss step: cumulative logistic from 0 to delta %."""
        return delta / (1.0 + np.exp(-(T - T50) / width))

    weight = (100.0
              - sigmoid_step(T, 105, 15, 3.2)    # free water
              - sigmoid_step(T, 310, 25, 18.5)   # organic decomp
              - sigmoid_step(T, 620, 30, 12.8))  # carbonate decomp
    noise = rng.normal(0, 0.05, len(T))
    weight = weight + noise

    N = len(T)  # 876 points

    # ── Workbook ──────────────────────────────────────────────────────
    wb = Workbook(min_rows=max(N + 10, 60), min_cols=16)
    s = wb.add_sheet("TGA")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block(
        "TGA Analysis",
        "Thermogravimetric analysis: weight loss steps and DTG.  Edit region bounds, press Ctrl+Enter.",
    )

    # ── Input parameters (rows 2-7 = sheet rows 3-8) ─────────────────
    s.set(2, 0, "Region bounds (°C)")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    regions = [
        ("Region 1  T_start (°C)", 50.0,  "0.0"),
        ("Region 1  T_end   (°C)", 180.0, "0.0"),
        ("Region 2  T_start (°C)", 220.0, "0.0"),
        ("Region 2  T_end   (°C)", 420.0, "0.0"),
        ("Region 3  T_start (°C)", 520.0, "0.0"),
        ("Region 3  T_end   (°C)", 750.0, "0.0"),
    ]
    for i, (lbl, val, nfmt) in enumerate(regions):
        r = 3 + i   # rows 3..8 -> sheet B4..B9
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format=nfmt)

    s.box(3, 0, 8, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 210)
    s.col_width(1, 110)

    s.note(
        3, 1,
        "Adjust the T_start / T_end pairs to bracket each mass-loss step. "
        "The =PY cell integrates the DTG in each region and reports % mass lost.",
        kind="note",
    )

    # ── Mass-loss result table (rows 2-5 in cols 3-5 = D-F) ──────────
    # Results header at row 9, data written by =PY to rows 10..12
    s.set(9, 3, "Region")
    s.set(9, 4, "T range (°C)")
    s.set(9, 5, "Mass loss (%)")
    s.set(9, 6, "T_peak DTG (°C)")
    for c in range(3, 7):
        s.fmt(9, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    s.col_width(3, 80)
    s.col_width(4, 120)
    s.col_width(5, 110)
    s.col_width(6, 120)

    # ── Data columns: T (col 8=I), weight (col 9=J) ──────────────────
    s.set(9, 8, "Temperature (°C)")
    s.set(9, 9, "Weight (%)")
    s.fmt(9, 8, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.fmt(9, 9, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.col_width(8, 140)
    s.col_width(9, 100)

    # Data rows start at row 10 (sheet row 11)
    for i in range(N):
        r = 10 + i
        s.set(r, 8, round(float(T[i]), 2))
        s.set(r, 9, round(float(weight[i]), 4))

    s.note(9, 8,
           "Temperature vs weight% data.  The =PY cell in column L "
           "computes the DTG and fills the result table above.",
           kind="note")

    # ── =PY cell: col 11 (L), row 10 (sheet row 11) ──────────────────
    # Reads: B4..B9 (region bounds), I11:I886 (T), J11:J886 (weight)
    # Writes region results to D10:G12
    last_row = 10 + N   # sheet row last_row+1

    py_code = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "",
        "# Region bounds",
        "r1s = float(ks('B4')); r1e = float(ks('B5'))",
        "r2s = float(ks('B6')); r2e = float(ks('B7'))",
        "r3s = float(ks('B8')); r3e = float(ks('B9'))",
        "",
        "# Read data",
        f"T_arr = ks('I11:I{last_row}')",
        f"W_arr = ks('J11:J{last_row}')",
        "m = np.isfinite(T_arr) & np.isfinite(W_arr)",
        "T_arr, W_arr = T_arr[m], W_arr[m]",
        "",
        "# DTG = -dW/dT  (positive for mass loss)",
        "dtg = -np.gradient(W_arr, T_arr)",
        "",
        "# Per-region: mass loss % and peak DTG temperature",
        "regions = [('Region 1', r1s, r1e),",
        "           ('Region 2', r2s, r2e),",
        "           ('Region 3', r3s, r3e)]",
        "result_rows = []",
        "for name, ts, te in regions:",
        "    mk = (T_arr >= ts) & (T_arr <= te)",
        "    if mk.sum() < 2:",
        "        result_rows.append([name, f'{ts:.0f}-{te:.0f}', 0.0, float('nan')])",
        "        continue",
        "    loss = W_arr[mk][0] - W_arr[mk][-1]",
        "    pk_i = np.argmax(dtg[mk])",
        "    t_peak = T_arr[mk][pk_i]",
        "    result_rows.append([name, f'{ts:.0f}-{te:.0f}',",
        "                        round(float(loss), 3), round(float(t_peak), 1)])",
        "",
        "# Write results: D10:G12 -> rows 9..11, cols 3..6",
        "for i, row in enumerate(result_rows):",
        "    base_row = f'{10 + i}'",
        "    ks_set(f'D{base_row}', row[0])",
        "    ks_set(f'E{base_row}', row[1])",
        "    ks_set(f'F{base_row}', row[2])",
        "    if not (row[3] != row[3]):  # nan check",
        "        ks_set(f'G{base_row}', row[3])",
        "",
        "# Plot: weight on left axis, DTG on right axis",
        "fig, ax1 = plt.subplots(figsize=(7, 4.5))",
        "ax2 = ax1.twinx()",
        "",
        "ax1.plot(T_arr, W_arr, color='#4472c4', linewidth=2.0, label='Weight %')",
        "ax2.plot(T_arr, dtg, color='#ed7d31', linewidth=1.5,",
        "         linestyle='--', label='DTG')",
        "",
        "# Mark step temperatures",
        "colors_reg = ['#70ad47', '#c00000', '#7030a0']",
        "for (name, ts, te), col in zip(regions, colors_reg):",
        "    mk = (T_arr >= ts) & (T_arr <= te)",
        "    if mk.sum() >= 2:",
        "        pk_i = np.argmax(dtg[mk])",
        "        t_pk = T_arr[mk][pk_i]",
        "        ax2.axvline(t_pk, color=col, linewidth=1.2,",
        "                    linestyle=':', alpha=0.7)",
        "        ax2.annotate(name, (t_pk, dtg[mk][pk_i]),",
        "                     textcoords='offset points', xytext=(4, 4),",
        "                     fontsize=7, color=col)",
        "",
        "ax1.set_xlabel('Temperature (°C)')",
        "ax1.set_ylabel('Weight (%)', color='#4472c4')",
        "ax2.set_ylabel('DTG (% / °C)', color='#ed7d31')",
        "ax1.set_title('Thermogravimetric Analysis (TGA/DTG)')",
        "h1, l1 = ax1.get_legend_handles_labels()",
        "h2, l2 = ax2.get_legend_handles_labels()",
        "ax1.legend(h1+h2, l1+l2, fontsize=9, loc='lower left')",
        "ax1.grid(True, alpha=0.3)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(10, 11, py_code)
    s.fmt(10, 11, italic=True, font_color="#555555")
    s.col_width(11, 280)
    s.set(10, 12, "Analysis cell (col L) — Ctrl+Enter to re-run")
    s.fmt(10, 12, italic=True, font_color="#888888")

    # ── Equation ──────────────────────────────────────────────────────
    s.equation(
        r"DTG = -\frac{dW}{dT}",
        at=(550, 50), fontsize=18, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(180, 52),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        _REPO, "examples", "python", "Materials Science",
        "TGA Analysis.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
