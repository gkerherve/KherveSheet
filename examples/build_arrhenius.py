"""Build the "Arrhenius Plot" demo .ksheet example.

Chemical kinetics: temperature dependence of the rate constant
    k = A * exp(-Ea / (R*T))
and the linear Arrhenius plot  ln(k)  vs  1000/T.

Editable inputs: pre-exponential factor A, activation energy Ea, gas
constant R.  A styled data table covers 300–500 K; a live-bound chart
plots the straight Arrhenius line; two LaTeX equations explain the
theory; three yellow sticky notes guide the user.

Run:  python examples/build_arrhenius.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Physical constants and default inputs ─────────────────────────────
R_GAS   = 8.314          # J mol-1 K-1
A_PRE   = 1.0e13         # pre-exponential factor (s-1)
EA_DEF  = 50_000.0       # activation energy (J/mol)

# Temperature range
T_MIN, T_MAX, N_ROWS = 300.0, 500.0, 21

# 0-based column layout for the data table
COL_T      = 0   # T (K)
COL_INV_T  = 1   # 1000/T (K-1)
COL_K      = 2   # k (s-1)
COL_LNK    = 3   # ln(k)

# 0-based row where table() header sits
TABLE_START_ROW = 9


def build() -> str:
    wb = Workbook(min_rows=45, min_cols=16)
    s  = wb.add_sheet("Arrhenius")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Arrhenius Plot",
        "Temperature dependence of a reaction rate constant  "
        "(k = A·exp(−Eₐ/RT))",
        span=8,
    )

    # ── Input panel (cells B5, B6, B7 = 1-based) ─────────────────────
    # 0-based: row 3 = section label, rows 4-6 = values
    s.set(3, 0, "Editable Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Pre-exponential factor A (s⁻¹)", A_PRE),
        ("Activation energy Eₐ (J/mol)",   EA_DEF),
        ("Gas constant R (J mol⁻¹ K⁻¹)",   R_GAS),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.0000")
    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.5)

    s.col_width(0, 230)
    s.col_width(1, 120)
    s.col_width(2, 120)
    s.col_width(3, 110)
    s.col_width(4, 110)
    s.col_width(5, 180)
    s.col_width(6, 130)

    # ── Data table: T, 1000/T, k, ln(k) ──────────────────────────────
    T_vals  = np.linspace(T_MIN, T_MAX, N_ROWS)
    inv_T   = 1000.0 / T_vals
    k_vals  = A_PRE  * np.exp(-EA_DEF / (R_GAS * T_vals))
    lnk     = np.log(k_vals)

    # Header is at 1-based sheet row TABLE_START_ROW+1 = 10.
    # First data row is TABLE_START_ROW+2 = 11  (1-based).
    first_data_sheet_row = TABLE_START_ROW + 2   # 1-based, = 11
    last_data_sheet_row  = first_data_sheet_row + N_ROWS - 1  # = 31

    rows = []
    for idx, T_v in enumerate(T_vals):
        sr = first_data_sheet_row + idx          # 1-based sheet row
        col_T_letter   = "A"                     # column 0  → A
        col_inv_T_ltr  = "B"                     # column 1  → B
        rows.append([
            round(float(T_v), 2),                              # T (K)  — literal
            f"=1000/{col_T_letter}{sr}",                       # 1000/T
            f"=$B$5*EXP(-$B$6/($B$7*{col_T_letter}{sr}))",    # k
            f"=LN(C{sr})",                                     # ln(k)
        ])

    s.set(8, 0, "Arrhenius data table")
    s.fmt(8, 0, bold=True, font_color=PALETTE["header"])

    s.table(
        TABLE_START_ROW, 0,
        headers=["T (K)", "1000/T (K⁻¹)", "k (s⁻¹)", "ln(k)"],
        rows=rows,
        number_format="0.0000",
        banded=True,
    )

    # Column 0 (T values) right-aligned with number format too
    for i in range(N_ROWS):
        s.fmt(TABLE_START_ROW + 1 + i, COL_T,
              align="right", number_format="0.00")

    # Designate X/Y columns for chart hints
    s.designate(COL_INV_T, "X")   # col 1: 1000/T
    s.designate(COL_LNK,   "Y")   # col 3: ln(k)

    # ── Summary panel ─────────────────────────────────────────────────
    # Located at columns 5-6, rows 3-7 (0-based)
    # References:
    #   -Ea/R       = -B6/B7
    #   k at 298 K  = B5*EXP(-B6/(B7*298))
    #   k at 500 K  = B5*EXP(-B6/(B7*500))
    #   ratio       = k500/k298

    s.set(3, 5, "Summary")
    s.fmt(3, 5, bold=True, font_color=PALETTE["header"])

    summ_items = [
        ("Theoretical slope  −Eₐ/R",
         "=-$B$6/$B$7",            PALETTE["band"]),
        ("k at 298 K (s⁻¹)",
         "=$B$5*EXP(-$B$6/($B$7*298))",  PALETTE["good"]),
        ("k at 500 K (s⁻¹)",
         "=$B$5*EXP(-$B$6/($B$7*500))",  PALETTE["good"]),
        ("Ratio k(500 K)/k(298 K)",
         "=($B$5*EXP(-$B$6/($B$7*500)))/($B$5*EXP(-$B$6/($B$7*298)))",
         PALETTE["accent"]),
    ]
    for i, (lbl, expr, bg) in enumerate(summ_items):
        r = 4 + i
        s.set(r, 5, lbl)
        s.formula(r, 6, expr)
        s.fmt(r, 5, align="left")
        s.fmt(r, 6, bg=bg, align="center",
              number_format="0.00e+00", bold=True,
              font_color="#ffffff" if bg == PALETTE["accent"] else "#000000")
    s.box(4, 5, 7, 6, color=PALETTE["header"], width=1.5)

    # ── Live chart: ln(k) vs 1000/T ──────────────────────────────────
    # 0-based data rows: header = TABLE_START_ROW (row 9),
    # first data = TABLE_START_ROW+1 (row 10), last = TABLE_START_ROW+N_ROWS (row 30).
    r0_bind = TABLE_START_ROW + 1          # 0-based, inclusive
    r1_bind = TABLE_START_ROW + N_ROWS     # 0-based, inclusive

    s.chart(
        [Series(
            x       = list(inv_T),
            y       = list(lnk),
            label   = "ln(k)",
            plot_type = "Line+Symbol",
            color   = PALETTE["header"],
            linewidth = 2.0,
            marker  = "o",
            markersize = 5.0,
            markerfacecolor = PALETTE["header"],
            markeredgecolor = "#ffffff",
            x_col     = COL_INV_T,   # 0-based col 1
            y_col     = COL_LNK,     # 0-based col 3
            row_start = r0_bind,
            row_end   = r1_bind,
        )],
        at=(540, 30), size=(450, 300),
        title="Arrhenius Plot  (linear region confirms Arrhenius behaviour)",
        xlabel="1000/T  (K⁻¹)",
        ylabel="ln(k)",
        grid=True, legend=True,
    )

    # ── LaTeX equations ───────────────────────────────────────────────
    # Equation 1: k = A e^{-Ea/RT}
    s.equation(
        r"k = A \, e^{-E_a / (RT)}",
        at=(540, 345), fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(240, 52),
    )

    # Equation 2: ln k = ln A - (Ea/R)(1/T)
    s.equation(
        r"\ln k = \ln A - \frac{E_a}{R} \cdot \frac{1}{T}",
        at=(540, 410), fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.2,
        size=(300, 52),
    )

    # ── Yellow notes ──────────────────────────────────────────────────
    # Note 1: why the plot is linear (next to the input cells)
    s.note(4, 0,
           "The Arrhenius equation k = A·exp(−Eₐ/RT) becomes linear when\n"
           "ln(k) is plotted against 1/T.  Edit A or Eₐ and the whole\n"
           "table, summary and chart update instantly.",
           kind="note")

    # Note 2: what the slope means (next to the summary panel)
    s.note(4, 5,
           "Slope of ln(k) vs 1/T  =  −Eₐ/R.\n"
           "Measuring this slope from an experiment lets you extract Eₐ\n"
           "without knowing A.",
           kind="note")

    # Note 3: higher T means faster reaction (next to last data rows)
    last_note_row = TABLE_START_ROW + N_ROWS   # 0-based
    s.note(last_note_row, 0,
           "Higher temperature → larger k → faster reaction.\n"
           "Even a moderate rise in T can double or triple the rate\n"
           "because k depends *exponentially* on 1/T.",
           kind="note")

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Arrhenius Plot.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
