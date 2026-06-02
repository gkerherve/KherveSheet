"""Build the "Loan Amortization" demo .ksheet example.

A finance example demonstrating a fixed-rate loan amortization schedule:
editable inputs (amount, rate, term, payments/year), a period-by-period
table driven by the closed-form payment formula (POWER), a summary
panel, a chart of remaining balance vs period (live-bound to table columns),
and a LaTeX equation for the amortized-payment formula.

Run:  python examples/build_loan_amortization.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os

import numpy as np

from ksheet_author import Workbook, Series, PALETTE

# ── Loan parameters (must match what the formulas compute) ─────────────
LOAN_AMOUNT    = 15_000.0   # principal ($)
ANNUAL_RATE    = 6.0        # annual interest rate (%) — chosen so r = 0.005 exactly
TERM_YEARS     = 2          # loan term (years)
PERIODS_YEAR   = 12         # payments per year (monthly)

n_periods   = TERM_YEARS * PERIODS_YEAR          # 24
r_periodic  = (ANNUAL_RATE / 100) / PERIODS_YEAR  # 0.005 exactly

# Amortized periodic payment: P = L*r / (1 - (1+r)^(-n))
pmt = LOAN_AMOUNT * r_periodic / (1 - (1 + r_periodic) ** (-n_periods))

# Build amortization schedule in Python (matches formula results)
balance     = np.zeros(n_periods + 1)
interest_v  = np.zeros(n_periods)
principal_v = np.zeros(n_periods)

balance[0] = LOAN_AMOUNT
for k in range(n_periods):
    interest_v[k]   = balance[k] * r_periodic
    principal_v[k]  = pmt - interest_v[k]
    balance[k+1]    = balance[k] - principal_v[k]

# Arrays for chart (end-of-period values)
periods_arr = np.arange(1, n_periods + 1, dtype=float)
balance_end = balance[1:]


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=14)
    s = wb.add_sheet("Amortization")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 85)    # A: Period
    s.col_width(1, 115)   # B: Payment
    s.col_width(2, 115)   # C: Interest
    s.col_width(3, 115)   # D: Principal
    s.col_width(4, 130)   # E: Balance
    s.col_width(5, 18)    # F: spacer
    s.col_width(6, 190)   # G: label column
    s.col_width(7, 120)   # H: value column

    # ── Title block (rows 0–1) ────────────────────────────────────────
    s.title_block(
        "Loan Amortization Schedule",
        "Fixed-rate loan — edit the yellow input cells; table, chart and "
        "summary recalculate automatically",
        span=8,
    )

    # ── Editable inputs at A4:B7 (0-based rows 3–6, cols 0–1) ─────────
    # Row index → 1-based sheet row:  3→4, 4→5, 5→6, 6→7
    # Col index 0 = A (label), col index 1 = B (value)
    #
    # Canonical input cells:
    #   B4 = Loan Amount     (row 3, col 1)
    #   B5 = Annual Rate %   (row 4, col 1)
    #   B6 = Term years      (row 5, col 1)
    #   B7 = Payments/yr     (row 6, col 1)

    s.set(2, 0, "Loan Inputs")
    s.fmt(2, 0, bold=True, font_size=11, font_color=PALETTE["accent"])

    input_defs = [
        (3, "Loan Amount ($)",           LOAN_AMOUNT,  "0.00"),
        (4, "Annual Interest Rate (%)",   ANNUAL_RATE,  "0.00"),
        (5, "Term (years)",               TERM_YEARS,   "0"),
        (6, "Payments per Year",          PERIODS_YEAR, "0"),
    ]
    for r, lbl, val, nf in input_defs:
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="right",
              number_format=nf, bold=True)

    s.box(3, 0, 6, 1, color=PALETTE["accent"], width=1.2)
    s.col_width(0, 200)

    s.note(3, 1,
           "Edit B4 (Loan Amount $), B5 (Annual Rate %), B6 (Term years), "
           "B7 (Payments per year) — the entire schedule, chart and "
           "summary recalculate automatically.",
           kind="note")

    # Absolute cell references for the four inputs
    R_AMT  = "$B$4"   # loan amount L
    R_RATE = "$B$5"   # annual rate % (not divided)
    R_TERM = "$B$6"   # term years
    R_PPYR = "$B$7"   # payments per year

    # Inline formulas for the two derived scalars (avoids rounding via helper cell)
    # Periodic rate r  = B5/100/B7
    # Total periods n  = B6*B7
    # Payment P        = B4*(B5/100/B7) / (1 - POWER(1 + B5/100/B7, -B6*B7))
    RATE_EXPR = f"{R_RATE}/100/{R_PPYR}"           # r inline
    NPER_EXPR = f"{R_TERM}*{R_PPYR}"               # n inline
    PAY_EXPR  = (f"{R_AMT}*({RATE_EXPR})/"
                 f"(1-POWER(1+({RATE_EXPR}),-({NPER_EXPR})))")

    # ── Helper display cells (rows 8–10, cols G/H = indices 6/7) ──────
    # These are DISPLAY ONLY — not referenced by table formulas.
    # They show the user the computed scalars for transparency.
    TBL_START   = 14
    data_row1   = TBL_START + 2           # 1-based sheet row of first data row
    data_row_n  = TBL_START + 1 + n_periods

    s.set(7, 6, "Derived Values (read-only)")
    s.fmt(7, 6, bold=True, font_color=PALETTE["header"])

    s.set(8, 6, "Periodic Rate  r")
    s.formula(8, 7, f"={RATE_EXPR}")
    s.fmt(8, 6, align="left", italic=True, font_color="#555555")
    s.fmt(8, 7, align="right", number_format="0.000000", font_color="#555555")

    s.set(9, 6, "Total Periods  n")
    s.formula(9, 7, f"={NPER_EXPR}")
    s.fmt(9, 6, align="left", italic=True, font_color="#555555")
    s.fmt(9, 7, align="right", number_format="0", font_color="#555555")

    s.set(10, 6, "Periodic Payment  P ($)")
    s.formula(10, 7, f"={PAY_EXPR}")
    s.fmt(10, 6, align="left", italic=True, bold=True,
          font_color=PALETTE["header"])
    s.fmt(10, 7, align="right", number_format="0.00",
          font_color=PALETTE["header"], bold=True)
    s.box(7, 6, 10, 7, color=PALETTE["header"], width=1.0)

    # ── Summary panel (rows 12–14, cols G/H) ─────────────────────────
    s.set(11, 6, "Summary")
    s.fmt(11, 6, bold=True, font_size=11, font_color=PALETTE["header"])

    summ = [
        ("Monthly Payment ($)",
         f"={PAY_EXPR}",
         PALETTE["good"]),
        ("Total Paid ($)",
         f"={PAY_EXPR}*({NPER_EXPR})",
         PALETTE["band"]),
        ("Total Interest ($)",
         f"=SUM(C{data_row1}:C{data_row_n})",
         PALETTE["bad"]),
    ]
    for i, (lbl, expr, fill) in enumerate(summ):
        r = 12 + i
        s.set(r, 6, lbl)
        s.formula(r, 7, expr)
        s.fmt(r, 6, align="left")
        s.fmt(r, 7, bg=fill, align="right", number_format="0.00", bold=True)

    s.box(11, 6, 14, 7, color=PALETTE["header"], width=1.2)

    s.note(14, 7,
           "Total Interest is the real cost of borrowing. Try raising B5 "
           "(rate) or B6 (term) — the interest bill grows quickly.",
           kind="note")

    # ── Schedule section heading (row 13, cols A–E) ───────────────────
    s.set(13, 0, "Period-by-Period Amortization Schedule")
    s.fmt(13, 0, bold=True, font_size=11, font_color=PALETTE["header"])
    s.merge(13, 0, 1, 5)

    # ── Amortization table ────────────────────────────────────────────
    # Columns (0-based): 0=Period  1=Payment  2=Interest  3=Principal  4=Balance
    # Header at row index TBL_START → sheet row TBL_START+1.
    # First data row at index TBL_START+1 → sheet row TBL_START+2 = data_row1.
    #
    # All formula rows compute inline (no helper-cell refs) so there is
    # no cascading rounding issue.
    #
    # Payment:    = L*r/(1-(1+r)^(-n))   [same every row]
    # Interest_k: = opening_balance * r
    # Principal_k = Payment - Interest_k
    # Balance_k   = opening_balance - Principal_k
    #
    # Opening balance for period 1 = B4; for period k>1 = E{prev_sheet_row}

    table_rows = []
    for k in range(n_periods):
        sheet_row = TBL_START + 2 + k   # 1-based sheet row

        if k == 0:
            bal_open = R_AMT
        else:
            bal_open = f"E{sheet_row - 1}"

        r_expr = RATE_EXPR   # inline rate expression
        pay_e  = PAY_EXPR    # inline payment expression

        interest_f  = f"={bal_open}*({r_expr})"
        principal_f = f"=({pay_e})-{bal_open}*({r_expr})"
        balance_f   = f"={bal_open}-(({pay_e})-{bal_open}*({r_expr}))"

        table_rows.append([
            k + 1,
            f"={pay_e}",
            interest_f,
            principal_f,
            balance_f,
        ])

    s.table(
        TBL_START, 0,
        headers=["Period", "Payment ($)", "Interest ($)",
                 "Principal ($)", "Balance ($)"],
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
          TBL_START + n_periods, 4,
          color=PALETTE["header"], width=1.0)

    # Designate columns for axis hints
    s.designate(0, "X")
    s.designate(4, "Y")

    # Note on interest front-loading
    s.note(TBL_START + 2, 2,
           "Interest is front-loaded: it is highest in period 1 and falls "
           "each month. In early periods most of each payment goes to the "
           "lender — only a small portion reduces the outstanding principal.",
           kind="note")

    # ── Chart: Balance & Interest per Period (live-bound) ─────────────
    r0 = TBL_START + 1
    r1 = TBL_START + n_periods

    s.chart(
        [
            Series(
                x=periods_arr,
                y=balance_end,
                label="Remaining Balance",
                plot_type="Line+Symbol",
                color="#4472c4",
                linewidth=2.2,
                marker="o",
                markersize=4.5,
                x_col=0,    # A = Period
                y_col=4,    # E = Balance
                row_start=r0,
                row_end=r1,
            ),
            Series(
                x=periods_arr,
                y=interest_v,
                label="Interest Paid",
                plot_type="Bar",
                color="#ed7d31",
                x_col=0,    # A = Period
                y_col=2,    # C = Interest
                row_start=r0,
                row_end=r1,
            ),
        ],
        at=(560, 20),
        size=(450, 330),
        title="Loan Balance & Interest per Period",
        xlabel="Period",
        ylabel="Amount ($)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation for the amortized payment formula ──────────────
    s.equation(
        r"P = \frac{L \cdot r}{1 - (1+r)^{-n}}",
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
        "P = periodic payment ($)",
        "L = loan amount ($)   |   r = annual rate / payments per year",
        "n = total periods = term (years) × payments per year",
    ]
    for i, txt in enumerate(legend_items):
        s.set(leg_start + i, 6, txt)
        s.fmt(leg_start + i, 6, italic=True, font_color="#555555")
        s.merge(leg_start + i, 6, 1, 2)

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Loan Amortization.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
