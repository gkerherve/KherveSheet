"""Build the "Thermogravimetric Analysis" demo .ksheet example.

A rich example from the thermal analysis domain.  A sample is heated
from 30 to 700 °C and loses mass in two logistic (sigmoid) decomposition
steps.  All table rows are formula-driven; editing any input in the
parameter panel updates the table, the chart, and the summary in real
time.

Run:  python examples/build_tga.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Physics / defaults ────────────────────────────────────────────────

M0    = 10.0    # initial mass (mg)
T1    = 120.0   # step-1 midpoint (°C) — moisture / solvent loss
K1    = 15.0    # step-1 width (°C)
A1    = 8.0     # step-1 amplitude (%)
T2    = 400.0   # step-2 midpoint (°C) — polymer decomposition
K2    = 30.0    # step-2 width (°C)
RES   = 30.0    # residual char (%)
A2    = 100.0 - RES - A1   # = 62 %

T_ARR = np.arange(30, 701, 10, dtype=float)   # 68 temperature points
N     = len(T_ARR)                             # 68


def sigmoid(T, Ti, ki):
    """Decreasing logistic: ≈1 at low T, ≈0 at high T."""
    return 1.0 / (1.0 + np.exp((T - Ti) / ki))


wt = RES + A1 * sigmoid(T_ARR, T1, K1) + A2 * sigmoid(T_ARR, T2, K2)
mass_mg = M0 * wt / 100.0

# DTG: derivative of weight% wrt T (first row is 0)
dtg = np.zeros(N)
dtg[1:] = (wt[:-1] - wt[1:]) / (T_ARR[1:] - T_ARR[:-1])


def build() -> str:
    wb = Workbook(min_rows=90, min_cols=14)
    s = wb.add_sheet("TGA")

    # ── Column widths ────────────────────────────────────────────────
    s.col_width(0, 160)   # A — parameter label / T
    s.col_width(1, 110)   # B — value / weight%
    s.col_width(2, 110)   # C — mass (mg)
    s.col_width(3, 120)   # D — DTG
    s.col_width(4, 10)    # E — spacer
    s.col_width(5, 170)   # F — summary label
    s.col_width(6, 110)   # G — summary value

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Thermogravimetric Analysis (TGA)",
                  "Two-step sigmoid decomposition model — edit inputs to "
                  "recalculate the full thermogram",
                  span=7)

    # ── Input panel (rows 3-11, 0-based) ─────────────────────────────
    # Layout: col 0 = label, col 1 = editable value
    s.set(3, 0, "Model Inputs")
    s.fmt(3, 0, bold=True, font_size=11, font_color=PALETTE["accent"])

    inputs = [
        ("Initial mass  m₀  (mg)",           M0,  "0.000"),
        ("Step-1 midpoint  T₁  (°C)",         T1,  "0.0"),
        ("Step-1 width  k₁  (°C)",            K1,  "0.0"),
        ("Step-1 amplitude  A₁  (%)",         A1,  "0.0"),
        ("Step-2 midpoint  T₂  (°C)",         T2,  "0.0"),
        ("Step-2 width  k₂  (°C)",            K2,  "0.0"),
        ("Residual char  r  (%)",             RES, "0.0"),
    ]
    for i, (lbl, val, nfmt) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format=nfmt)

    # A2 is a formula (row 11 = index 7 → 4+7=11 is out of range for 7
    # inputs above; A2 occupies row 11, i.e. the 8th input row)
    A2_ROW = 11   # 0-based sheet row
    s.set(A2_ROW, 0, "Step-2 amplitude  A₂  (%)  [= 100 − r − A₁]")
    # B5=m0(row4), B6=T1, B7=k1, B8=A1, B9=T2, B10=k2, B11=residual
    # Sheet rows: row4→B5, row5→B6, ..., row10→B11
    # A2 = 100 - residual(B11) - A1(B8)
    s.formula(A2_ROW, 1, "=100-B11-B8")
    s.fmt(A2_ROW, 0, align="left")
    s.fmt(A2_ROW, 1, bg=PALETTE["band"], align="center", number_format="0.0",
          bold=True)

    s.box(4, 0, A2_ROW, 1, color=PALETTE["accent"], width=1.2)

    s.note(4, 1,
           "Edit m0, T1/T2, k1/k2, A1, residual here.\n"
           "A2 recalculates automatically so A1+A2+residual = 100 %.",
           kind="note")
    s.note(4, 0,
           "Step 1 (low T): moisture / solvent loss.\n"
           "Step 2 (high T): major polymer decomposition.",
           kind="note")

    # ── Data table (rows 13–81, 0-based: header row 13, data 14-81) ──
    # table() puts the header at start_row and data at start_row+1..+N
    TABLE_START = 13   # 0-based

    # Input cell addresses (1-based sheet rows):
    #   m0     → B5   (row 4 → sheet row 5)
    #   T1     → B6
    #   k1     → B7
    #   A1     → B8
    #   T2     → B9
    #   k2     → B10
    #   residual → B11
    #   A2     → B12  (row 11 → sheet row 12)
    # Table header at sheet row TABLE_START+1 = 14
    # First data row at sheet row TABLE_START+2 = 15

    FIRST_DATA_SHEET_ROW = TABLE_START + 2   # 1-based: 15

    rows = []
    for idx in range(N):
        rr = FIRST_DATA_SHEET_ROW + idx   # 1-based sheet row for this data row
        T_val = float(T_ARR[idx])

        # Weight% formula:
        #   =$B$11 + $B$8/(1+EXP((A{rr}-$B$6)/$B$7))
        #          + $B$12/(1+EXP((A{rr}-$B$9)/$B$10))
        wt_formula = (
            f"=$B$11"
            f"+$B$8/(1+EXP((A{rr}-$B$6)/$B$7))"
            f"+$B$12/(1+EXP((A{rr}-$B$9)/$B$10))"
        )

        # Mass formula: = m0 * weight% / 100
        mass_formula = f"=$B$5*B{rr}/100"

        # DTG formula: (prev_wt% - cur_wt%) / (cur_T - prev_T)
        # First row (idx==0): DTG = 0
        if idx == 0:
            dtg_formula = "=0"
        else:
            prev_rr = rr - 1
            dtg_formula = (
                f"=(B{prev_rr}-B{rr})/(A{rr}-A{prev_rr})"
            )

        rows.append([T_val, wt_formula, mass_formula, dtg_formula])

    s.set(TABLE_START - 1, 0, "Thermogram data  (30–700 °C, 10 °C steps)")
    s.fmt(TABLE_START - 1, 0, bold=True, font_color=PALETTE["header"])

    s.table(TABLE_START, 0,
            headers=["T (°C)", "Weight %", "Mass (mg)", "DTG (% °C⁻¹)"],
            rows=rows,
            banded=True)

    # Right-align all columns; apply number formats
    s.fmt_range(TABLE_START + 1, 0, TABLE_START + N, 0,
                align="right", number_format="0")
    s.fmt_range(TABLE_START + 1, 1, TABLE_START + N, 1,
                number_format="0.00")
    s.fmt_range(TABLE_START + 1, 2, TABLE_START + N, 2,
                number_format="0.000")
    s.fmt_range(TABLE_START + 1, 3, TABLE_START + N, 3,
                number_format="0.0000")

    # Designate columns
    s.designate(0, "X")   # T (°C)
    s.designate(1, "Y")   # weight %
    s.designate(2, "Y")   # mass
    s.designate(3, "Y")   # DTG

    # ── Summary panel (rows 3–11, cols 5–6) ──────────────────────────
    FIRST_1B = FIRST_DATA_SHEET_ROW       # 1-based first data row
    LAST_1B  = FIRST_DATA_SHEET_ROW + N - 1  # 1-based last data row

    s.set(3, 5, "Summary")
    s.fmt(3, 5, bold=True, font_size=11, font_color=PALETTE["header"])

    summ = [
        ("Initial mass (mg)",        f"=B5",                      PALETTE["band"]),
        ("Residual mass (mg)",       f"=MIN(C{FIRST_1B}:C{LAST_1B})", PALETTE["good"]),
        ("Total mass lost (mg)",     f"=B5-MIN(C{FIRST_1B}:C{LAST_1B})", PALETTE["bad"]),
        ("Wt% at step-1 midpt T₁",  f"=B11+B8/(1+EXP(0))+B12/(1+EXP((B6-B9)/B10))", PALETTE["band_alt"]),
        ("Wt% at step-2 midpt T₂",  f"=B11+B8/(1+EXP((B9-B6)/B7))+B12/(1+EXP(0))", PALETTE["band_alt"]),
        ("Peak DTG step-1 (% °C⁻¹)", f"=MAX(D{FIRST_1B}:D{LAST_1B})",   PALETTE["warn"]),
        ("Residual char (%)",        "=B11",                      PALETTE["good"]),
        ("A₁ + A₂ + residual (%)",   "=B8+B12+B11",               PALETTE["good"]),
    ]
    for i, (lbl, expr, col) in enumerate(summ):
        r = 4 + i
        s.set(r, 5, lbl)
        if expr.startswith("="):
            s.formula(r, 6, expr)
        else:
            s.set(r, 6, expr)
        s.fmt(r, 5, align="left")
        s.fmt(r, 6, bg=col, align="center", number_format="0.000", bold=True)

    s.box(4, 5, 4 + len(summ) - 1, 6, color=PALETTE["header"], width=1.2)
    s.col_width(5, 200)
    s.col_width(6, 100)

    # ── Note: DTG ─────────────────────────────────────────────────────
    s.note(TABLE_START, 3,
           "DTG = d(wt%)/dT from adjacent rows.\n"
           "Peaks in DTG locate each decomposition step temperature.",
           kind="note")

    # ── Note: residual ────────────────────────────────────────────────
    s.note(A2_ROW, 5,
           "Residual at 700 °C = inorganic char / ash.\n"
           "Increase 'Residual char %' to model more thermally stable fillers.",
           kind="note")

    # ── Chart 1: weight% vs T (live-bound) ───────────────────────────
    # Data rows in the sheet occupy 0-based rows TABLE_START+1 .. TABLE_START+N
    row0 = TABLE_START + 1
    row1 = TABLE_START + N

    s.chart(
        [
            Series(T_ARR, wt, "Weight %", "Line",
                   color="#4472c4", linewidth=2.0,
                   x_col=0, y_col=1, row_start=row0, row_end=row1),
            Series(T_ARR, dtg * 100, "DTG × 100", "Line",
                   color="#ed7d31", linewidth=1.5, linestyle="--",
                   x_col=0, y_col=3, row_start=row0, row_end=row1),
        ],
        at=(560, 20), size=(480, 310),
        title="TGA Thermogram", xlabel="Temperature (°C)",
        ylabel="Weight % / DTG×100 (% °C⁻¹)",
        grid=True, legend=True,
    )

    # ── Equation: weight%(T) ──────────────────────────────────────────
    # Mathtext: \frac, \mathrm, no \tfrac/\dfrac/\text
    s.equation(
        r"w(T) = r + \frac{A_1}{1+\mathrm{exp}\!\left(\frac{T-T_1}{k_1}\right)}"
        r" + \frac{A_2}{1+\mathrm{exp}\!\left(\frac{T-T_2}{k_2}\right)}",
        at=(560, 345), fontsize=16,
        color="#222222", bg_color="#ffffff",
        border_color=PALETTE["header"], border_width=1.2,
        size=(480, 68),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Thermogravimetric Analysis.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
