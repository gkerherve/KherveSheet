"""Build the "Compound Interest" demo .ksheet example.

A personal-finance example showing how a savings principal grows with
yearly compounding and optional annual contributions.  Demonstrates:
title block, editable input panel, a year-by-year formula-driven table,
a summary panel with accent fills, a live-bound chart, a LaTeX equation,
and instructive yellow sticky notes.

Run:  python examples/build_compound_interest.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os

import numpy as np

from ksheet_author import Workbook, Series, PALETTE

# ── Default input parameters ──────────────────────────────────────────
PRINCIPAL       = 10_000.0   # £ starting lump sum
RATE_PCT        = 6.0        # annual interest rate, %
YEARS           = 20         # investment horizon
ANNUAL_CONTRIB  = 1_200.0    # £ added at the start of each year


def _compute_table(principal, rate_pct, years, contrib):
    """Return (year_arr, start_arr, interest_arr, contrib_arr, end_arr)."""
    r = rate_pct / 100.0
    starts, interests, contribs, ends = [], [], [], []
    balance = principal
    for yr in range(1, years + 1):
        start = balance
        # Contribution added at the beginning of the year (before interest).
        balance += contrib
        interest = balance * r
        balance += interest
        starts.append(start)
        interests.append(interest)
        contribs.append(contrib)
        ends.append(balance)
    year_arr     = np.arange(1, years + 1, dtype=float)
    start_arr    = np.array(starts,    dtype=float)
    interest_arr = np.array(interests, dtype=float)
    contrib_arr  = np.array(contribs,  dtype=float)
    end_arr      = np.array(ends,      dtype=float)
    return year_arr, start_arr, interest_arr, contrib_arr, end_arr


def build() -> str:
    years_arr, start_arr, interest_arr, contrib_arr, end_arr = _compute_table(
        PRINCIPAL, RATE_PCT, YEARS, ANNUAL_CONTRIB)

    wb = Workbook(min_rows=44, min_cols=14)
    s  = wb.add_sheet("Compound Interest")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block("Compound Interest Calculator",
                  "Year-by-year growth of savings with regular contributions",
                  span=7)

    # ── Input panel ──────────────────────────────────────────────────
    # Labels in col A (0), values in col B (1).
    # 0-based rows 3..6; 1-based sheet refs B4..B7.
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"], font_size=11)

    inputs = [
        ("Principal (£)",              PRINCIPAL,      "£#,##0.00"),
        ("Annual interest rate (%)",   RATE_PCT,       "0.00"),
        ("Investment period (years)",  YEARS,          "0"),
        ("Annual contribution (£)",    ANNUAL_CONTRIB, "£#,##0.00"),
    ]
    for i, (lbl, val, nfmt) in enumerate(inputs):
        r = 4 + i   # 0-based rows 4..7
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center",
              number_format=nfmt, bold=True)

    s.box(4, 0, 7, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 210)   # label column
    s.col_width(1, 120)   # value column

    # Note 1: tell user what to edit.
    s.note(4, 1,
           "Edit B5, B6, B7 or B8 — the entire table,\n"
           "summary panel and chart all recalculate.",
           kind="note")

    # ── Year-by-year data table ───────────────────────────────────────
    # Table header at 0-based row 9  → sheet row 10.
    # First data row at 0-based row 10 → sheet row 11.
    # Inputs live at 1-based: B5=Principal, B6=Rate%, B7=Years, B8=Contrib.
    #
    # Column layout (0-based cols 0..4 = A..E):
    #   A  Year
    #   B  Starting Balance
    #   C  Interest Earned
    #   D  Annual Contribution
    #   E  Ending Balance
    #
    # Formulas use absolute refs $B$5..$B$8 for inputs.
    # Year 1 starting balance = $B$5 (principal).
    # Year k>1 starting balance = previous ending balance (E row above).
    # Interest = (starting + contribution) * rate / 100.
    # Ending   = starting + contribution + interest.

    TABLE_START = 9   # 0-based row of header

    s.set(8, 0, "Year-by-Year Growth")
    s.fmt(8, 0, bold=True, font_color=PALETTE["header"], font_size=11)

    table_rows = []
    for k in range(YEARS):
        rr = TABLE_START + 2 + k   # 1-based sheet row of this data row

        if k == 0:
            start_formula = "=$B$5"
        else:
            prev_e = TABLE_START + 2 + (k - 1)   # 1-based sheet row above
            start_formula = f"=E{prev_e}"

        interest_formula = f"=(B{rr}+$B$8)*$B$6/100"
        contrib_formula  = "=$B$8"
        end_formula      = f"=B{rr}+D{rr}+C{rr}"

        table_rows.append([
            k + 1,           # Year (literal integer — no formula needed)
            start_formula,
            interest_formula,
            contrib_formula,
            end_formula,
        ])

    s.table(TABLE_START, 0,
            headers=["Year", "Starting Balance (£)", "Interest Earned (£)",
                     "Annual Contribution (£)", "Ending Balance (£)"],
            rows=table_rows,
            number_format="£#,##0.00",
            banded=True)

    # Column widths for the table.
    s.col_width(0, 55)    # Year
    s.col_width(2, 165)   # Interest Earned
    s.col_width(3, 175)   # Annual Contribution
    s.col_width(4, 155)   # Ending Balance

    # Designate X and Y columns.
    s.designate(0, "X")   # Year
    s.designate(4, "Y")   # Ending Balance

    # Note 2: explain the contribution timing.
    s.note(TABLE_START, 3,
           "The annual contribution is added at the START\n"
           "of each year (before interest is applied),\n"
           "maximising compounding benefit.",
           kind="note")

    # ── Summary panel ────────────────────────────────────────────────
    # 0-based rows 9..13 on cols 6..7 (G..H).
    # 1-based data range runs from sheet row (TABLE_START+2) to
    # sheet row (TABLE_START+1+YEARS).
    first_data = TABLE_START + 2           # 1-based sheet row, first data
    last_data  = TABLE_START + 1 + YEARS   # 1-based sheet row, last data

    final_balance    = end_arr[-1]
    total_interest   = float(np.sum(interest_arr))
    total_contribs   = ANNUAL_CONTRIB * YEARS

    s.set(8, 6, "Summary")
    s.fmt(8, 6, bold=True, font_color=PALETTE["header"], font_size=11)

    summary_items = [
        ("Final Balance (£)",
         f"=E{last_data}",
         PALETTE["good"]),
        ("Total Interest Earned (£)",
         f"=SUM(C{first_data}:C{last_data})",
         PALETTE["band"]),
        ("Total Contributions (£)",
         f"=SUM(D{first_data}:D{last_data})",
         PALETTE["band_alt"]),
        ("Initial Principal (£)",
         "=$B$5",
         PALETTE["band_alt"]),
        ("Effective Return (%)",
         f"=(E{last_data}-$B$5)/($B$5)*100",
         PALETTE["warn"]),
    ]

    for i, (lbl, expr, fill) in enumerate(summary_items):
        r = 9 + i
        s.set(r, 6, lbl)
        s.formula(r, 7, expr)
        s.fmt(r, 6, align="left", bold=False)
        nfmt = "0.00" if "%" in lbl else "£#,##0.00"
        s.fmt(r, 7, bg=fill, align="right", number_format=nfmt, bold=True)

    s.box(9, 6, 13, 7, color=PALETTE["header"], width=1.5)
    s.col_width(6, 190)
    s.col_width(7, 120)

    # Note 3: highlight the power of compounding.
    s.note(9, 7,
           "The final balance exceeds principal + contributions\n"
           "because interest compounds on interest each year.",
           kind="note")

    # ── Chart (live-bound to Year col A and Ending Balance col E) ─────
    # 0-based data rows: TABLE_START+1 .. TABLE_START+YEARS
    r0 = TABLE_START + 1            # 0-based, first data row
    r1 = TABLE_START + YEARS        # 0-based, last data row

    s.chart(
        [Series(
            years_arr, end_arr,
            label="Ending Balance",
            plot_type="Line+Symbol",
            color="#4472c4",
            linewidth=2.0,
            marker="o",
            markersize=5.0,
            x_col=0,    # 0-based column A (Year)
            y_col=4,    # 0-based column E (Ending Balance)
            row_start=r0,
            row_end=r1,
        )],
        at=(540, 30),
        size=(450, 310),
        title="Savings Growth Over Time",
        xlabel="Year",
        ylabel="Balance (£)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    # A_n = (P + C) * (1+r)^n  +  C * [(1+r)^n - 1] / r  -  C
    # Simplified form: A_n = P(1+r)^n + C * [(1+r)^n - 1] / r
    s.equation(
        r"A_n = P\,(1+r)^n + C\,\frac{(1+r)^n - 1}{r}",
        at=(540, 360),
        fontsize=18,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(340, 56),
    )

    # ── Save ─────────────────────────────────────────────────────────
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Compound Interest.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
