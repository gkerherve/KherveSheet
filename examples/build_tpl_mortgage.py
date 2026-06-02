"""Build the "Mortgage Amortization" Finance template .ksheet file.

A polished, richly-formatted mortgage calculator template:
- Editable amber inputs: loan amount, annual rate %, term (years),
  payments/year (default: monthly = 12).
- Closed-form level payment via PMT = L*r/(1-POWER(1+r,-n))
  (PMT() built-in is unimplemented — closed-form is used throughout).
- 36-period amortization schedule (3-year view) with all live formulas
  chaining the running balance.
- Summary panel: periodic payment, total paid, total interest, LTV ratio.
- Two live-bound charts: (1) remaining balance vs period, (2) interest
  vs principal per period as stacked bars.
- LaTeX equation for the payment formula.
- Three yellow sticky notes guiding the user.

Run:  python examples/build_tpl_mortgage.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Make the project importable when run from anywhere.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402

# ── Default loan parameters (must match formula output exactly) ──────────
LOAN_AMOUNT  = 300_000.0   # $
ANNUAL_RATE  =       4.5   # %
TERM_YEARS   =        30   # full loan term for payment calculation
PERIODS_YEAR =        12   # monthly payments

# Derived constants matching formula cells
r = (ANNUAL_RATE / 100) / PERIODS_YEAR   # periodic rate
n_total = TERM_YEARS * PERIODS_YEAR      # total periods for payment

# Closed-form payment
pmt = LOAN_AMOUNT * r / (1 - (1 + r) ** (-n_total))

# We show only 36 periods in the schedule (3-year slice)
N_SHOWN = 36

# Build amortization for the first N_SHOWN periods
balance_arr  = np.zeros(N_SHOWN + 1)
interest_arr = np.zeros(N_SHOWN)
principal_arr= np.zeros(N_SHOWN)

balance_arr[0] = LOAN_AMOUNT
for k in range(N_SHOWN):
    interest_arr[k]  = balance_arr[k] * r
    principal_arr[k] = pmt - interest_arr[k]
    balance_arr[k+1] = balance_arr[k] - principal_arr[k]

periods_arr  = np.arange(1, N_SHOWN + 1, dtype=float)
balance_end  = balance_arr[1:]


def build() -> str:
    wb = Workbook(min_rows=60, min_cols=16)
    s = wb.add_sheet("Amortization")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 80)    # A: Period
    s.col_width(1, 125)   # B: Payment
    s.col_width(2, 125)   # C: Interest
    s.col_width(3, 125)   # D: Principal
    s.col_width(4, 140)   # E: Balance
    s.col_width(5, 20)    # F: spacer
    s.col_width(6, 210)   # G: label / summary
    s.col_width(7, 130)   # H: value / summary

    # ── Title block (rows 0–1) ────────────────────────────────────────
    s.title_block(
        "Mortgage Amortization Schedule",
        "Fixed-rate mortgage — edit the amber input cells; "
        "table, summary and chart recalculate automatically",
        span=8,
    )

    # ── Input panel (rows 3–6, cols A/B = indices 0/1) ───────────────
    #   1-based sheet refs:
    #     B4 = Loan Amount       (row 3, col 1)
    #     B5 = Annual Rate %     (row 4, col 1)
    #     B6 = Term (years)      (row 5, col 1)
    #     B7 = Payments per year (row 6, col 1)

    s.set(2, 0, "Loan Inputs")
    s.fmt(2, 0, bold=True, font_size=11, font_color=PALETTE["accent"])

    input_defs = [
        (3, "Loan Amount ($)",          LOAN_AMOUNT,  "0.00"),
        (4, "Annual Interest Rate (%)", ANNUAL_RATE,  "0.00"),
        (5, "Loan Term (years)",        TERM_YEARS,   "0"),
        (6, "Payments per Year",        PERIODS_YEAR, "0"),
    ]
    for row_idx, lbl, val, nf in input_defs:
        s.set(row_idx, 0, lbl)
        s.set(row_idx, 1, val)
        s.fmt(row_idx, 0, align="left")
        s.fmt(row_idx, 1, bg=PALETTE["warn"], align="right",
              number_format=nf, bold=True)

    s.box(3, 0, 6, 1, color=PALETTE["accent"], width=1.4)

    s.note(3, 1,
           "Edit B4 (Loan Amount), B5 (Annual Rate %), B6 (Term years), "
           "B7 (Payments per year). All schedule rows, summary and chart "
           "recalculate automatically via live formulas.",
           kind="note")

    # ── Payment formula building blocks ──────────────────────────────
    # Periodic rate  r  =  B5/100/B7
    # Total periods  n  =  B6*B7
    # Payment        P  =  B4*(r)/(1-POWER(1+r,-n))
    RATE_EXPR = "$B$5/100/$B$7"
    NPER_EXPR = "$B$6*$B$7"
    PAY_EXPR  = (
        f"$B$4*({RATE_EXPR})/"
        f"(1-POWER(1+({RATE_EXPR}),-({NPER_EXPR})))"
    )

    # ── Derived-value display (rows 8–11, cols G/H = indices 6/7) ────
    s.set(7, 6, "Derived Values (read-only)")
    s.fmt(7, 6, bold=True, font_color=PALETTE["header"])

    derived = [
        (8,  "Periodic Rate  r",       f"={RATE_EXPR}",    "0.000000"),
        (9,  "Total Periods  n",       f"={NPER_EXPR}",    "0"),
        (10, "Periodic Payment  P ($)", f"={PAY_EXPR}",     "0.00"),
    ]
    for row_idx, lbl, expr, nf in derived:
        s.set(row_idx, 6, lbl)
        s.formula(row_idx, 7, expr)
        s.fmt(row_idx, 6, align="left", italic=True, font_color="#555555")
        s.fmt(row_idx, 7, align="right", number_format=nf,
              font_color="#555555")

    # Highlight the payment row
    s.fmt(10, 6, bold=True, font_color=PALETTE["header"], italic=False)
    s.fmt(10, 7, bold=True, font_color=PALETTE["header"], number_format="0.00")
    s.box(7, 6, 10, 7, color=PALETTE["header"], width=1.0)

    # ── Summary panel (rows 12–16, cols G/H) ─────────────────────────
    # Table data rows span from sheet row data_row1 to data_row1+N_SHOWN-1.
    TBL_START  = 19                    # 0-based row of the table header
    data_row1  = TBL_START + 2        # 1-based first data row  = 21
    data_row_n = TBL_START + 1 + N_SHOWN  # 1-based last data row = 56

    s.set(11, 6, "Summary")
    s.fmt(11, 6, bold=True, font_size=11, font_color=PALETTE["header"])

    summary_rows = [
        ("Periodic Payment ($)",
         f"={PAY_EXPR}",
         "0.00",
         PALETTE["good"]),
        ("Total Paid — first 36 periods ($)",
         f"=SUM(B{data_row1}:B{data_row_n})",
         "0.00",
         PALETTE["band"]),
        ("Total Interest — first 36 periods ($)",
         f"=SUM(C{data_row1}:C{data_row_n})",
         "0.00",
         PALETTE["bad"]),
        ("Balance after 36 periods ($)",
         f"=E{data_row_n}",
         "0.00",
         PALETTE["band_alt"]),
        ("% of Loan Remaining",
         f"=E{data_row_n}/$B$4*100",
         "0.00",
         PALETTE["warn"]),
    ]
    for i, (lbl, expr, nf, fill) in enumerate(summary_rows):
        r_idx = 12 + i
        s.set(r_idx, 6, lbl)
        s.formula(r_idx, 7, expr)
        s.fmt(r_idx, 6, align="left")
        s.fmt(r_idx, 7, bg=fill, align="right", number_format=nf, bold=True)

    s.box(11, 6, 17, 7, color=PALETTE["header"], width=1.2)

    s.note(17, 7,
           "The schedule shows the first 36 periods (3 years). "
           "Total Paid and Total Interest reflect only these periods. "
           "Balance after 36 periods shows how much principal remains.",
           kind="note")

    # ── Early repayment note ──────────────────────────────────────────
    s.note(12, 6,
           "Tip: Try reducing B6 (term years) — a shorter term means "
           "a higher payment but far less total interest paid over the life "
           "of the loan.",
           kind="note")

    # ── Schedule section heading (row 18, cols A–E) ───────────────────
    s.set(18, 0, "Amortization Schedule — First 36 Periods")
    s.fmt(18, 0, bold=True, font_size=11, font_color=PALETTE["header"])
    s.merge(18, 0, 1, 5)

    # ── Amortization table ────────────────────────────────────────────
    # Header at 0-based row TBL_START=19 → 1-based sheet row 20.
    # First data row at 0-based row TBL_START+1=20 → 1-based sheet row 21.
    #
    # Columns: 0=Period  1=Payment  2=Interest  3=Principal  4=Balance
    #
    # Formula layout:
    #   B_f  = PMT closed-form (same every row)
    #   C_f  = interest on previous balance
    #          period 1: $B$4 * (rate)
    #          period k: E{prev} * (rate)
    #   D_f  = B_f - C_f   (principal repaid)
    #   E_f  = previous_balance - D_f
    #          period 1: $B$4 - D{r}
    #          period k: E{prev} - D{r}

    table_rows = []
    for k in range(N_SHOWN):
        sheet_row = data_row1 + k    # 21, 22, ..., 56

        B_f = f"={PAY_EXPR}"

        if k == 0:
            C_f = f"=$B$4*({RATE_EXPR})"
            D_f = f"=B{sheet_row}-C{sheet_row}"
            E_f = f"=$B$4-D{sheet_row}"
        else:
            prev = sheet_row - 1
            C_f = f"=E{prev}*({RATE_EXPR})"
            D_f = f"=B{sheet_row}-C{sheet_row}"
            E_f = f"=E{prev}-D{sheet_row}"

        table_rows.append([
            k + 1,   # Period — literal integer
            B_f,
            C_f,
            D_f,
            E_f,
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
    for k in range(N_SHOWN):
        s.fmt(TBL_START + 1 + k, 0, align="center", number_format="0")

    # Outer border around table
    s.box(TBL_START, 0,
          TBL_START + N_SHOWN, 4,
          color=PALETTE["header"], width=1.0)

    # Designate axes for app axis hints
    s.designate(0, "X")   # A = Period
    s.designate(4, "Y")   # E = Balance

    # Annotate interest front-loading
    s.note(TBL_START + 2, 2,
           "Interest is front-loaded: the first payment goes mostly to "
           "interest, with only a small slice reducing the principal. "
           "The ratio flips gradually over the loan term.",
           kind="note")

    # ── Charts (live-bound to table columns) ──────────────────────────
    # 0-based row bounds matching the table data
    r0 = TBL_START + 1           # first data row (0-based)
    r1 = TBL_START + N_SHOWN     # last  data row (0-based)

    # Chart 1: Remaining balance vs period
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
                markersize=4.0,
                x_col=0,   # A = Period
                y_col=4,   # E = Balance
                row_start=r0,
                row_end=r1,
            ),
        ],
        at=(560, 20),
        size=(450, 280),
        title="Remaining Balance vs Period",
        xlabel="Period",
        ylabel="Balance ($)",
        grid=True,
        legend=True,
    )

    # Chart 2: Interest vs principal per period (Bar)
    s.chart(
        [
            Series(
                x=periods_arr,
                y=interest_arr,
                label="Interest",
                plot_type="Bar",
                color="#ed7d31",
                x_col=0,   # A = Period
                y_col=2,   # C = Interest
                row_start=r0,
                row_end=r1,
            ),
            Series(
                x=periods_arr,
                y=principal_arr,
                label="Principal",
                plot_type="Bar",
                color="#70ad47",
                x_col=0,   # A = Period
                y_col=3,   # D = Principal
                row_start=r0,
                row_end=r1,
            ),
        ],
        at=(560, 320),
        size=(450, 280),
        title="Interest vs Principal per Period",
        xlabel="Period",
        ylabel="Amount ($)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation for the payment formula ────────────────────────
    s.equation(
        r"P = \frac{L \cdot r}{1 - (1+r)^{-n}},\quad r = \frac{R}{m},\quad n = T \cdot m",
        at=(560, 620),
        fontsize=17,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.4,
        size=(450, 62),
    )

    # ── Symbol legend ─────────────────────────────────────────────────
    leg_start = TBL_START + N_SHOWN + 3
    legend_items = [
        "P = periodic payment ($)   |   L = loan amount ($)",
        "r = periodic rate = R / m   |   R = annual rate (%)   |   m = payments per year",
        "n = total periods = T × m   |   T = loan term (years)",
    ]
    for i, txt in enumerate(legend_items):
        s.set(leg_start + i, 0, txt)
        s.fmt(leg_start + i, 0, italic=True, font_color="#555555")
        s.merge(leg_start + i, 0, 1, 5)

    # ── Output path ───────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Finance", "Mortgage Amortization.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
