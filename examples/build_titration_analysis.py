"""Build the "Titration Curve Analysis" template .ksheet file.

Data-analysis workflow for a strong-acid / strong-base titration:
columns Volume Added (mL), pH, first derivative d(pH)/dV, second
derivative d²(pH)/dV², and a helper |d(pH)/dV| column used to locate the
equivalence point automatically.

Derivative formulas use per-row scalar cell references (no array
functions):
  - central difference for interior rows
  - forward difference for the first row
  - backward difference for the last row

Two live-bound charts: (a) the sigmoidal pH curve, (b) the first
derivative curve whose peak marks the equivalence point.

Run:  python examples/build_titration_analysis.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import numpy as np

from ksheet_author import Workbook, Series, PALETTE

# ── Physical setup ───────────────────────────────────────────────────
# 35 equally-spaced titrant volumes from 0 to ~50 mL.
# Strong acid: 25 mL of 0.10 mol/L HCl.
# Strong base: 0.10 mol/L NaOH.
# Equivalence at 25.0 mL NaOH added.

Ca = 0.10
Va = 25.0
Cb = 0.10

n = 35
Vb_arr = np.linspace(0.0, 50.0, n)  # mL NaOH added

# Pre-compute pH array (mirrors the sheet formulas for initial render)
pH_arr = np.empty(n)
for i, Vb in enumerate(Vb_arr):
    Va_L  = Va  / 1000.0
    Vb_L  = Vb  / 1000.0
    Vtot  = Va_L + Vb_L
    net   = Ca * Va_L - Cb * Vb_L   # positive = excess H+
    conc  = max(abs(net) / Vtot, 1e-7)
    if net > 0:
        pH_arr[i] = -np.log10(conc)
    else:
        pH_arr[i] = 14.0 + np.log10(conc)

# First derivative via finite differences (matching per-row formulas)
d1_arr = np.empty(n)
d1_arr[0]    = (pH_arr[1]  - pH_arr[0])   / (Vb_arr[1]  - Vb_arr[0])
d1_arr[-1]   = (pH_arr[-1] - pH_arr[-2])  / (Vb_arr[-1] - Vb_arr[-2])
for i in range(1, n - 1):
    d1_arr[i] = (pH_arr[i + 1] - pH_arr[i - 1]) / (Vb_arr[i + 1] - Vb_arr[i - 1])

# Second derivative
d2_arr = np.empty(n)
d2_arr[0]  = (d1_arr[1]  - d1_arr[0])   / (Vb_arr[1]  - Vb_arr[0])
d2_arr[-1] = (d1_arr[-1] - d1_arr[-2])  / (Vb_arr[-1] - Vb_arr[-2])
for i in range(1, n - 1):
    d2_arr[i] = (d1_arr[i + 1] - d1_arr[i - 1]) / (Vb_arr[i + 1] - Vb_arr[i - 1])

abs_d1 = np.abs(d1_arr)

# ── Layout constants ──────────────────────────────────────────────────
# Columns (0-based): A=0 Volume, B=1 pH, C=2 d1, D=3 d2, E=4 |d1| helper
# F=5 Veq-helper (V if |d1|==MAX else 0), G=6 pH-eq-helper
COL_V     = 0  # A
COL_PH    = 1  # B
COL_D1    = 2  # C
COL_D2    = 3  # D
COL_ABSD1 = 4  # E  – |d(pH)/dV|, helper for equivalence detection
COL_VH    = 5  # F  – V when |d1| is maximum, else 0
COL_PHH   = 6  # G  – pH when |d1| is maximum, else 0

# Data table layout
TABLE_START   = 3     # 0-based row of table header row
FIRST_DATA_R  = TABLE_START + 1      # 0-based first data row = 4
LAST_DATA_R   = TABLE_START + n      # 0-based last data row (inclusive) = 38

# 1-based sheet row equivalents
FIRST_DATA_SR = FIRST_DATA_R + 1     # = 5
LAST_DATA_SR  = LAST_DATA_R  + 1     # = 39

# Summary placed BELOW the data table so it evaluates after F/G columns
# in row-major order (critical for the two-pass evaluator).
SUM_HEADER_R  = LAST_DATA_R + 2      # 0-based row of summary section header = 41
SUM_LBL_C     = 0    # A (same column as data, below table)
SUM_VAL_C     = 1    # B


def build() -> str:
    wb = Workbook(min_rows=55, min_cols=14)
    s  = wb.add_sheet("Titration Analysis")

    # ── Column widths ────────────────────────────────────────────────
    s.col_width(COL_V,     120)   # Volume (mL)
    s.col_width(COL_PH,     90)   # pH
    s.col_width(COL_D1,    120)   # d(pH)/dV
    s.col_width(COL_D2,    130)   # d²(pH)/dV²
    s.col_width(COL_ABSD1, 110)   # |d(pH)/dV|
    s.col_width(COL_VH,    100)   # Veq helper
    s.col_width(COL_PHH,   100)   # pH helper
    s.col_width(8,         200)   # chart area spacer / context

    # ── Title block (rows 0-1) ───────────────────────────────────────
    s.title_block(
        "Titration Curve Analysis",
        "Derivatives and equivalence-point detection "
        "— replace columns A and B with your own V/pH data",
        span=8,
    )

    # ── Info note near title ─────────────────────────────────────────
    s.note(0, 9,
           "Replace the Volume (A) and pH (B) data with your own\n"
           "measurements. All derivative and summary cells update.",
           kind="note")

    # ── Data table header row ────────────────────────────────────────
    # TABLE_START = 3 (0-based), so header is at sheet row 4.
    col_labels = [
        "Volume Added (mL)",
        "pH",
        "d(pH)/dV  (mL⁻\xb9)",
        "d\xb2(pH)/dV\xb2  (mL⁻\xb2)",
        "|d(pH)/dV|",
        "Veq helper",
        "pHₐq helper",
    ]
    for j, h in enumerate(col_labels):
        s.set(TABLE_START, j, h)
        s.fmt(TABLE_START, j,
              bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"],
              align="center", wrap=True)

    # ── Equivalence detection range references ───────────────────────
    abs_d1_range = f"$E${FIRST_DATA_SR}:$E${LAST_DATA_SR}"
    max_abs_d1   = f"MAX({abs_d1_range})"

    # ── Data rows ────────────────────────────────────────────────────
    for i in range(n):
        r0 = FIRST_DATA_R + i        # 0-based row
        rr = FIRST_DATA_SR + i       # 1-based sheet row

        # Banding
        band = (PALETTE["band_alt"] if i % 2 else None)

        # Column A: Volume (literal — independent variable grid)
        s.set(r0, COL_V, round(float(Vb_arr[i]), 4))
        s.fmt(r0, COL_V, align="right", number_format="0.00")
        if band:
            s.fmt(r0, COL_V, bg=band)

        # Column B: pH (literal — user-entered measured data)
        s.set(r0, COL_PH, round(float(pH_arr[i]), 4))
        s.fmt(r0, COL_PH, align="right", number_format="0.000")
        if band:
            s.fmt(r0, COL_PH, bg=band)

        # Column C: first derivative d(pH)/dV
        if i == 0:
            rr_next = rr + 1
            d1_formula = f"=(B{rr_next}-B{rr})/(A{rr_next}-A{rr})"
        elif i == n - 1:
            rr_prev = rr - 1
            d1_formula = f"=(B{rr}-B{rr_prev})/(A{rr}-A{rr_prev})"
        else:
            rr_prev = rr - 1
            rr_next = rr + 1
            d1_formula = f"=(B{rr_next}-B{rr_prev})/(A{rr_next}-A{rr_prev})"

        s.formula(r0, COL_D1, d1_formula)
        s.fmt(r0, COL_D1, align="right", number_format="0.000")
        if band:
            s.fmt(r0, COL_D1, bg=band)

        # Column D: second derivative d²(pH)/dV²
        if i == 0:
            rr_next = rr + 1
            d2_formula = f"=(C{rr_next}-C{rr})/(A{rr_next}-A{rr})"
        elif i == n - 1:
            rr_prev = rr - 1
            d2_formula = f"=(C{rr}-C{rr_prev})/(A{rr}-A{rr_prev})"
        else:
            rr_prev = rr - 1
            rr_next = rr + 1
            d2_formula = f"=(C{rr_next}-C{rr_prev})/(A{rr_next}-A{rr_prev})"

        s.formula(r0, COL_D2, d2_formula)
        s.fmt(r0, COL_D2, align="right", number_format="0.000")
        if band:
            s.fmt(r0, COL_D2, bg=band)

        # Column E: |d(pH)/dV|  (helper for equivalence detection)
        s.formula(r0, COL_ABSD1, f"=ABS(C{rr})")
        s.fmt(r0, COL_ABSD1, align="right", number_format="0.000")
        if band:
            s.fmt(r0, COL_ABSD1, bg=band)

        # Column F: V if this row has the maximum |d1|, else 0
        # The summary SUM(F) is placed BELOW the table so it evaluates
        # after F column in both passes of the two-pass evaluator.
        s.formula(r0, COL_VH,
                  f"=IF(E{rr}=={max_abs_d1},A{rr},0)")
        s.fmt(r0, COL_VH, align="right", number_format="0.00")
        if band:
            s.fmt(r0, COL_VH, bg=band)

        # Column G: pH if this row has the maximum |d1|, else 0
        s.formula(r0, COL_PHH,
                  f"=IF(E{rr}=={max_abs_d1},B{rr},0)")
        s.fmt(r0, COL_PHH, align="right", number_format="0.000")
        if band:
            s.fmt(r0, COL_PHH, bg=band)

    # ── Borders around data table ────────────────────────────────────
    s.box(TABLE_START, 0, LAST_DATA_R, 6,
          color=PALETTE["header"], width=1.0)

    # ── Column designations for chart axis hints ─────────────────────
    s.designate(COL_V,  "X")
    s.designate(COL_PH, "Y")
    s.designate(COL_D1, "Y")
    s.designate(COL_D2, "Y")

    # ── Summary panel — placed BELOW data table ───────────────────────
    # By placing these rows after the data table, the two-pass evaluator
    # guarantees they are computed after F and G columns are ready.
    s.set(SUM_HEADER_R, SUM_LBL_C, "Equivalence Point Summary")
    s.fmt(SUM_HEADER_R, SUM_LBL_C,
          bold=True, font_color=PALETTE["header"], font_size=12)
    s.merge(SUM_HEADER_R, SUM_LBL_C, 1, 3)

    summary = [
        # (row_offset, label, formula, bg, number_format)
        (1, "Equivalence Volume (mL)",
         f"=SUM($F${FIRST_DATA_SR}:$F${LAST_DATA_SR})",
         PALETTE["good"], "0.00"),
        (2, "pH at Equivalence",
         f"=SUM($G${FIRST_DATA_SR}:$G${LAST_DATA_SR})",
         PALETTE["good"], "0.000"),
        (3, "Max |d(pH)/dV|  (peak height)",
         f"=MAX($E${FIRST_DATA_SR}:$E${LAST_DATA_SR})",
         PALETTE["band"], "0.000"),
        (4, "Max d\xb2(pH)/dV\xb2  (inflection)",
         f"=MAX($D${FIRST_DATA_SR}:$D${LAST_DATA_SR})",
         PALETTE["band"], "0.000"),
        (5, "pH at start  (V = 0 mL)",
         f"=B{FIRST_DATA_SR}",
         PALETTE["band_alt"], "0.000"),
        (6, "pH at end",
         f"=B{LAST_DATA_SR}",
         PALETTE["band_alt"], "0.000"),
    ]
    col_w_lbl = 200
    col_w_val = 110
    s.col_width(SUM_LBL_C, col_w_lbl)  # already set but reaffirm
    s.col_width(SUM_VAL_C, col_w_val)

    for (off, lbl, expr, bg, nf) in summary:
        r = SUM_HEADER_R + off
        s.set(r, SUM_LBL_C, lbl)
        s.formula(r, SUM_VAL_C, expr)
        s.fmt(r, SUM_LBL_C, align="left", bold=False)
        s.fmt(r, SUM_VAL_C,
              bg=bg, align="center", number_format=nf, bold=True)

    s.box(SUM_HEADER_R + 1, SUM_LBL_C,
          SUM_HEADER_R + 6, SUM_VAL_C,
          color=PALETTE["header"], width=1.2)

    # ── Notes ────────────────────────────────────────────────────────
    # Note 1: derivative method
    s.note(TABLE_START, COL_D1,
           "Central difference (interior rows):\n"
           "  d(pH)/dV ≈ (pH[i+1] − pH[i-1]) / (V[i+1] − V[i-1])\n"
           "Forward difference (first row):\n"
           "  d(pH)/dV ≈ (pH[2] − pH[1]) / (V[2] − V[1])\n"
           "Backward difference (last row):\n"
           "  d(pH)/dV ≈ (pH[n] − pH[n-1]) / (V[n] − V[n-1])\n"
           "Each formula is a live scalar cell reference.\n"
           "\n"
           "Tip: KherveSheet also has a DERIV formula (Data Analysis\n"
           "category) and a Find Peaks tool in the Science menu.",
           kind="note")

    # Note 2: equivalence point detection
    s.note(SUM_HEADER_R, SUM_LBL_C,
           "Equivalence volume = V at max |d(pH)/dV| (column E).\n"
           "Columns F and G mark that row's V and pH;\n"
           "SUM(F) and SUM(G) extract the unique non-zero values.\n"
           "\n"
           "The summary is placed BELOW the data table so the\n"
           "formula evaluator computes it after columns E/F/G.",
           kind="note")

    # Note 3: paste-your-data reminder
    s.note(FIRST_DATA_R, COL_V,
           "Paste your own measured Volume (mL) here (col A)\n"
           "and pH measurements here (col B).\n"
           "All derivative and summary cells recalculate.",
           kind="note")

    # ── Chart 1: pH vs Volume ────────────────────────────────────────
    r0_chart = FIRST_DATA_R    # 0-based inclusive
    r1_chart = LAST_DATA_R     # 0-based inclusive

    s.chart(
        [Series(
            x=Vb_arr,
            y=pH_arr,
            label="pH",
            plot_type="Line+Symbol",
            color="#4472c4",
            linewidth=2.0,
            marker="o",
            markersize=4.0,
            x_col=COL_V,
            y_col=COL_PH,
            row_start=r0_chart,
            row_end=r1_chart,
        )],
        at=(890, 30),
        size=(450, 310),
        title="Titration Curve",
        xlabel="Volume NaOH added (mL)",
        ylabel="pH",
        grid=True,
        legend=True,
    )

    # ── Chart 2: first derivative vs Volume ─────────────────────────
    s.chart(
        [Series(
            x=Vb_arr,
            y=d1_arr,
            label="d(pH)/dV",
            plot_type="Line+Symbol",
            color="#ed7d31",
            linewidth=2.0,
            marker="^",
            markersize=5.0,
            x_col=COL_V,
            y_col=COL_D1,
            row_start=r0_chart,
            row_end=r1_chart,
        )],
        at=(890, 360),
        size=(450, 290),
        title="First Derivative — Peak = Equivalence Point",
        xlabel="Volume NaOH added (mL)",
        ylabel="d(pH)/dV  (mL⁻\xb9)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation: central difference formula ───────────────────
    s.equation(
        r"\frac{d(\mathrm{pH})}{dV}\approx"
        r"\frac{\mathrm{pH}_{i+1}-\mathrm{pH}_{i-1}}{V_{i+1}-V_{i-1}}",
        at=(890, 670),
        fontsize=17,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(370, 58),
    )

    # ── Save ─────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Analysis",
        "Titration Curve Analysis.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
