"""Build the "Periodic Payments" Finance template .ksheet.

A savings / annuity future-value schedule: the user enters a regular
payment, an annual interest rate, the number of payments per year, and
the savings horizon in years.  The sheet builds a full period-by-period
schedule (Payment | Interest earned | Running Balance) driven entirely by
live formulas.  A summary panel shows the future value (final balance),
total paid in, and total interest earned.  An embedded line chart plots
balance growth vs period — data-bound so it updates with every input edit.

Run:  python examples/build_tpl_periodic_payments.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os

import numpy as np

from ksheet_author import Workbook, Series, PALETTE

# ── Default parameters (must match formula results) ────────────────────
PMT        = 200.0   # regular payment ($)
RATE_PCT   = 5.0     # annual interest rate (%)
PPY        = 12      # payments per year (monthly)
YEARS      = 5       # savings horizon (years)

n_periods = int(YEARS * PPY)               # 60
r_per     = (RATE_PCT / 100.0) / PPY      # 0.004166...

# Build the schedule in Python (matches formula column values exactly)
balances   = np.zeros(n_periods)
interests  = np.zeros(n_periods)
payments   = np.full(n_periods, PMT)

for k in range(n_periods):
    prev = balances[k - 1] if k > 0 else 0.0
    interests[k] = prev * r_per
    balances[k]  = prev + PMT + interests[k]

periods_arr = np.arange(1, n_periods + 1, dtype=float)
future_value = float(balances[-1])
total_paid   = PMT * n_periods
total_interest = future_value - total_paid


def build() -> str:
    wb = Workbook(min_rows=72, min_cols=14)
    s = wb.add_sheet("Savings Schedule")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 75)    # A: Period
    s.col_width(1, 115)   # B: Payment
    s.col_width(2, 130)   # C: Interest earned
    s.col_width(3, 20)    # D: spacer col (unused in table, used as visual gap)
    s.col_width(4, 130)   # E: Balance
    s.col_width(5, 20)    # F: spacer
    s.col_width(6, 200)   # G: label column (summary / inputs)
    s.col_width(7, 130)   # H: value column

    # ── Title block (rows 0–1) ────────────────────────────────────────
    s.title_block(
        "Periodic Payments — Savings Schedule",
        "Regular contributions with compound interest — edit the amber "
        "cells; the table, chart and summary all recalculate.",
        span=8,
    )

    # ── Editable inputs (amber) at rows 3–6, cols A/B (0-based) ──────
    # 0-based row → 1-based ref:  3→B4, 4→B5, 5→B6, 6→B7
    s.set(2, 0, "Savings Inputs")
    s.fmt(2, 0, bold=True, font_size=11, font_color=PALETTE["accent"])

    input_defs = [
        (3, "Regular Payment ($ / period)",  PMT,    "0.00"),
        (4, "Annual Interest Rate (%)",       RATE_PCT, "0.00"),
        (5, "Payments per Year",              PPY,    "0"),
        (6, "Number of Years",               YEARS,  "0"),
    ]
    for r, lbl, val, nf in input_defs:
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="right",
              number_format=nf, bold=True)

    s.box(3, 0, 6, 1, color=PALETTE["accent"], width=1.2)

    s.note(3, 1,
           "Edit B4 (payment $), B5 (annual rate %), B6 (payments/yr), "
           "B7 (years) — the schedule, chart and summary all update.",
           kind="note")

    # ── Derived read-only display cells (rows 8–10, cols G/H) ─────────
    # Periodic rate  r = B5/100/B6
    # Total periods  n = B7*B6
    # Future value (FV) = closed-form: PMT * ((1+r)^n - 1) / r
    RATE_EXPR = "$B$5/100/$B$6"
    NPER_EXPR = "$B$7*$B$6"
    # FV formula: uses POWER, avoids sci-notation literals
    FV_EXPR = (
        f"$B$4*(POWER(1+({RATE_EXPR}),{NPER_EXPR})-1)/({RATE_EXPR})"
    )

    s.set(7, 6, "Derived Values (read-only)")
    s.fmt(7, 6, bold=True, font_color=PALETTE["header"])

    s.set(8, 6, "Periodic Rate  r")
    s.formula(8, 7, f"={RATE_EXPR}")
    s.fmt(8, 6, align="left", italic=True, font_color="#555555")
    s.fmt(8, 7, align="right", number_format="0.0000000", font_color="#555555")

    s.set(9, 6, "Total Periods  n")
    s.formula(9, 7, f"={NPER_EXPR}")
    s.fmt(9, 6, align="left", italic=True, font_color="#555555")
    s.fmt(9, 7, align="right", number_format="0", font_color="#555555")

    s.set(10, 6, "Future Value (analytic)")
    s.formula(10, 7, f"={FV_EXPR}")
    s.fmt(10, 6, align="left", bold=True, italic=True,
          font_color=PALETTE["header"])
    s.fmt(10, 7, align="right", number_format="0.00",
          font_color=PALETTE["header"], bold=True)
    s.box(7, 6, 10, 7, color=PALETTE["header"], width=1.0)

    # ── Summary panel (rows 12–14, cols G/H) ─────────────────────────
    # The table occupies rows TBL_START .. TBL_START + n_periods (0-based).
    TBL_START  = 16
    data_row1  = TBL_START + 2      # 1-based sheet row of first data row
    data_row_n = TBL_START + 1 + n_periods  # 1-based last data row

    s.set(11, 6, "Summary")
    s.fmt(11, 6, bold=True, font_size=11, font_color=PALETTE["header"])

    # Balance column is E (0-based col 4), which is the 5th column.
    # In the table layout: col 0=Period, col 1=Payment, col 2=Interest,
    # col 3=spacer (not in table), col 4=Balance.
    # But the table uses consecutive columns starting at start_col=0:
    #   table col 0 → sheet col A (0)
    #   table col 1 → sheet col B (1)
    #   table col 2 → sheet col C (2)
    #   table col 3 → sheet col D (3)  ← Balance
    # See table() call below — 4 columns: Period/Payment/Interest/Balance
    # So Balance is at sheet col D (index 3, 1-based "D").
    # Redefine for clarity:
    BAL_COL = "D"   # 1-based letter for Balance column

    summ = [
        ("Future Value (final balance)",
         f"={BAL_COL}{data_row_n}",
         PALETTE["good"]),
        ("Total Paid In",
         f"=SUM(B{data_row1}:B{data_row_n})",
         PALETTE["band"]),
        ("Total Interest Earned",
         f"={BAL_COL}{data_row_n}-SUM(B{data_row1}:B{data_row_n})",
         PALETTE["good"]),
    ]
    for i, (lbl, expr, fill) in enumerate(summ):
        r = 12 + i
        s.set(r, 6, lbl)
        s.formula(r, 7, expr)
        s.fmt(r, 6, align="left")
        s.fmt(r, 7, bg=fill, align="right", number_format="0.00", bold=True)

    s.box(11, 6, 14, 7, color=PALETTE["header"], width=1.2)

    s.note(14, 7,
           "Try raising B5 (rate) or B6 (payments/yr) — compound interest "
           "accelerates the balance growth non-linearly.",
           kind="note")

    # ── Schedule section heading ──────────────────────────────────────
    s.set(15, 0, "Period-by-Period Savings Schedule")
    s.fmt(15, 0, bold=True, font_size=11, font_color=PALETTE["header"])
    s.merge(15, 0, 1, 4)

    # ── Schedule table ────────────────────────────────────────────────
    # Columns (0-based from start_col=0):
    #   0 → A  Period (literal integer label)
    #   1 → B  Payment ($)       = $B$4 every row
    #   2 → C  Interest earned   = prev_balance * ($B$5/100/$B$6)
    #   3 → D  Balance           = prev_balance + payment + interest
    #
    # Table header at 0-based row TBL_START (16) → 1-based sheet row 17.
    # First data row at 0-based row TBL_START+1 (17) → 1-based row 18.
    # BUT: table() puts data starting at start_row+1 (0-based),
    #      which is 1-based sheet row start_row+2.
    # So data_row1 (1-based) = TBL_START + 2 = 18.

    table_rows = []
    for k in range(n_periods):
        sheet_row = data_row1 + k   # 1-based sheet row for this period

        B_f = "=$B$4"               # Payment = input cell, same every row

        if k == 0:
            # No previous balance; first period has no interest accrued
            C_f = "=0"
            D_f = f"=$B$4+C{sheet_row}"   # = PMT + 0
        else:
            prev = sheet_row - 1           # previous row (1-based)
            C_f = f"=D{prev}*($B$5/100/$B$6)"
            D_f = f"=D{prev}+$B$4+C{sheet_row}"

        table_rows.append([
            k + 1,   # Period (literal integer)
            B_f,
            C_f,
            D_f,
        ])

    s.table(
        TBL_START, 0,
        headers=["Period", "Payment ($)", "Interest ($)", "Balance ($)"],
        rows=table_rows,
        number_format="0.00",
        banded=True,
        align_data="right",
    )

    # Period column: centre-aligned integers
    for k in range(n_periods):
        s.fmt(TBL_START + 1 + k, 0, align="center", number_format="0")

    # Outer border
    s.box(TBL_START, 0,
          TBL_START + n_periods, 3,
          color=PALETTE["header"], width=1.0)

    # Designate columns for axis hints
    s.designate(0, "X")
    s.designate(3, "Y")

    s.note(TBL_START + 1, 2,
           "Period 1 earns no interest — the deposit has just been made. "
           "From period 2 onward each balance accrues interest before the "
           "next deposit, so the curve accelerates.",
           kind="note")

    # ── Chart: Balance growth vs Period (live-bound) ──────────────────
    # 0-based row bounds: first data row = TBL_START+1, last = TBL_START+n_periods
    r0 = TBL_START + 1
    r1 = TBL_START + n_periods

    s.chart(
        [
            Series(
                x=periods_arr,
                y=balances,
                label="Account Balance",
                plot_type="Line+Symbol",
                color="#4472c4",
                linewidth=2.2,
                marker="o",
                markersize=3.5,
                x_col=0,    # A = Period
                y_col=3,    # D = Balance
                row_start=r0,
                row_end=r1,
            ),
        ],
        at=(560, 20),
        size=(450, 330),
        title="Savings Balance Growth",
        xlabel="Period",
        ylabel="Balance ($)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation for the future-value annuity formula ──────────
    s.equation(
        r"FV = PMT \cdot \frac{(1+r)^{n}-1}{r}",
        at=(560, 370),
        fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.4,
        size=(310, 62),
    )

    # ── Symbol legend ─────────────────────────────────────────────────
    leg_start = TBL_START + n_periods + 3
    legend_items = [
        "FV = future value ($)   |   PMT = regular payment ($)",
        "r = annual rate % / payments per year   |   n = total periods",
        "Balance grows as a geometric series — each period: balance = balance_prev×(1+r) + PMT",
    ]
    for i, txt in enumerate(legend_items):
        s.set(leg_start + i, 6, txt)
        s.fmt(leg_start + i, 6, italic=True, font_color="#555555")
        s.merge(leg_start + i, 6, 1, 2)

    # ── Output path ───────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Finance", "Periodic Payments.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
