"""Build the "Compound Interest" TEMPLATE .ksheet file.

A reusable calculator template (distinct from the worked example in
build_compound_interest.py) that handles per-period compounding and
an optional monthly contribution.

Features:
  - Amber input cells: Principal, Annual rate %, Investment years,
    Compounding periods/year, Monthly contribution.
  - Year-by-year table (all live formulas): Starting Balance, Interest
    Earned, Annual Contribution, Ending Balance.
    Compounding formula: E = B * POWER(1 + r/n, n) + 12*C
    where r = rate/100, n = periods/year, C = monthly contribution.
    Interest = B * (POWER(1 + r/n, n) - 1)  [always safe; =0 when r=0]
  - Summary panel: Final Balance, Total Interest, Total Contributions,
    Effective Annual Yield (POWER formula).
  - Live-bound Line+Symbol chart: Ending Balance vs Year.
  - LaTeX equation for the compound-interest formula.
  - Three instructive yellow notes.

Output: examples/templates/Finance/Compound Interest.ksheet

Run:   python examples/build_tpl_compound_interest.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Ensure project root is importable regardless of working directory.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402

# ── Default parameter values ─────────────────────────────────────────
PRINCIPAL        = 10_000.0   # £
RATE_PCT         = 5.0        # annual interest rate (%)
YEARS            = 25         # investment horizon
N_PERIODS        = 12         # compounding periods per year (monthly)
MONTHLY_CONTRIB  = 200.0      # £ per month


def _compute_table(principal, rate_pct, years, n_periods, monthly_contrib):
    """Compute year-by-year arrays matching the cell formula semantics.

    Ending balance per year:
        E = B * POWER(1 + r_p, n)  +  12 * C
    where  r_p = rate_pct / (100 * n_periods)
           n   = n_periods
           C   = monthly_contrib
    Interest = B * (POWER(1 + r_p, n) - 1)
    Annual contribution = 12 * C
    """
    r_p = rate_pct / (100.0 * n_periods)
    growth = (1.0 + r_p) ** n_periods   # annual growth factor

    balance = principal
    years_arr, start_arr, int_arr, contrib_arr, end_arr = [], [], [], [], []

    for yr in range(1, years + 1):
        start    = balance
        interest = start * (growth - 1.0)
        contrib  = 12.0 * monthly_contrib
        end      = start * growth + contrib
        balance  = end

        years_arr.append(float(yr))
        start_arr.append(start)
        int_arr.append(interest)
        contrib_arr.append(contrib)
        end_arr.append(end)

    return (np.array(years_arr),  np.array(start_arr),
            np.array(int_arr),    np.array(contrib_arr),
            np.array(end_arr))


def build() -> str:
    years_arr, start_arr, int_arr, contrib_arr, end_arr = _compute_table(
        PRINCIPAL, RATE_PCT, YEARS, N_PERIODS, MONTHLY_CONTRIB)

    wb = Workbook(min_rows=50, min_cols=15)
    s  = wb.add_sheet("Compound Interest")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Compound Interest Calculator",
        "Per-period compounding with optional monthly contributions — "
        "edit the amber cells to update everything",
        span=8,
    )

    # ── Input panel ──────────────────────────────────────────────────
    # Labels in col A (0), values in col B (1).
    # 0-based rows 4..8  →  1-based sheet refs B5, B6, B7, B8, B9.
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"], font_size=11)

    inputs = [
        ("Principal (£)",                  PRINCIPAL,       "£#,##0.00"),
        ("Annual interest rate (%)",        RATE_PCT,        "0.00"),
        ("Investment period (years)",       YEARS,           "0"),
        ("Compounding periods / year",      N_PERIODS,       "0"),
        ("Monthly contribution (£)",        MONTHLY_CONTRIB, "£#,##0.00"),
    ]
    for i, (lbl, val, nfmt) in enumerate(inputs):
        r = 4 + i   # 0-based: rows 4, 5, 6, 7, 8
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center",
              number_format=nfmt, bold=True)

    s.box(4, 0, 8, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 230)  # label column wide enough to avoid clipping
    s.col_width(1, 130)

    # Note 1: tell the user what to edit.
    s.note(4, 1,
           "Edit any amber cell — Principal (B5), Rate (B6), Years (B7),\n"
           "Periods/year (B8) or Monthly contribution (B9).\n"
           "The table, summary panel, and chart all update instantly.",
           kind="note")

    # ── Derived helper: effective annual yield ────────────────────────
    # Placed in col D/E rows 4..5 as a visual reference (not used by table).
    # 0-based col 3 = D, col 4 = E.
    s.set(3, 3, "Derived")
    s.fmt(3, 3, bold=True, font_color=PALETTE["accent"])

    s.set(4, 3, "Period rate (r/n)")
    # r_p = B6 / (100 * B8)  — no sci-notation, plain division
    s.formula(4, 4, "=$B$6/(100*$B$8)")
    s.fmt(4, 4, number_format="0.0000%", bg=PALETTE["band"], align="center")

    s.set(5, 3, "Annual growth factor")
    # f = POWER(1 + r_p, n) = POWER(1 + B6/(100*B8), B8)
    s.formula(5, 4, "=POWER(1+$B$6/(100*$B$8),$B$8)")
    s.fmt(5, 4, number_format="0.000000", bg=PALETTE["band"], align="center")

    s.set(6, 3, "Effective annual yield (%)")
    # EAY = (POWER(1 + r_p, n) - 1) * 100
    s.formula(6, 4, "=(POWER(1+$B$6/(100*$B$8),$B$8)-1)*100")
    s.fmt(6, 4, number_format="0.0000", bg=PALETTE["good"], align="center",
          bold=True)

    s.col_width(3, 200)
    s.col_width(4, 120)
    s.box(4, 3, 6, 4, color=PALETTE["accent"], width=1.0)

    # ── Year-by-year data table ───────────────────────────────────────
    # Table header at 0-based row 11  → sheet row 12.
    # First data row at 0-based row 12 → sheet row 13.
    # Last data row at 0-based row (11 + YEARS) → sheet row (12 + YEARS).
    #
    # Column layout (0-based cols 0..4 = A..E):
    #   A  Year                (literal integer)
    #   B  Starting Balance    (formula, = Principal for yr1 or prev Ending)
    #   C  Interest Earned     (formula = B{r} * (POWER(1+$B$6/(100*$B$8),$B$8) - 1))
    #   D  Annual Contribution (formula = 12 * $B$9)
    #   E  Ending Balance      (formula = B{r}*POWER(1+$B$6/(100*$B$8),$B$8) + 12*$B$9)

    TABLE_START = 11   # 0-based row of table header

    s.set(10, 0, "Year-by-Year Growth")
    s.fmt(10, 0, bold=True, font_color=PALETTE["header"], font_size=11)

    # Growth-factor sub-expression (reused in every row formula).
    # POWER(1 + $B$6/(100*$B$8), $B$8)
    GF = "POWER(1+$B$6/(100*$B$8),$B$8)"

    table_rows = []
    for k in range(YEARS):
        # 1-based sheet row of this data row.
        # Header sits at sheet row TABLE_START+1 = 12,
        # so the first data row is sheet row 13 (k=0 → rr=13).
        rr = TABLE_START + 2 + k   # 13, 14, …, 37  (for YEARS=25)

        if k == 0:
            # Year 1: starting balance is the Principal input.
            b_formula = "=$B$5"
        else:
            # Year k>1: starting balance is the previous row's ending balance.
            prev_rr = TABLE_START + 2 + (k - 1)
            b_formula = f"=E{prev_rr}"

        # Interest: B * (growth_factor - 1)
        c_formula = f"=B{rr}*({GF}-1)"

        # Annual contribution: 12 monthly payments
        d_formula = "=12*$B$9"

        # Ending balance: B * growth_factor + 12 * monthly_contrib
        e_formula = f"=B{rr}*{GF}+12*$B$9"

        table_rows.append([
            k + 1,      # Year — literal integer
            b_formula,
            c_formula,
            d_formula,
            e_formula,
        ])

    s.table(TABLE_START, 0,
            headers=[
                "Year",
                "Starting Balance (£)",
                "Interest Earned (£)",
                "Annual Contribution (£)",
                "Ending Balance (£)",
            ],
            rows=table_rows,
            number_format="£#,##0.00",
            banded=True)

    # Column widths for the table.
    s.col_width(0, 55)    # Year
    s.col_width(1, 160)   # Starting Balance
    s.col_width(2, 165)   # Interest Earned
    s.col_width(3, 175)   # Annual Contribution
    s.col_width(4, 155)   # Ending Balance

    # Designate X / Y columns so chart binding and axis hints are correct.
    s.designate(0, "X")   # Year
    s.designate(4, "Y")   # Ending Balance

    # Note 2: explain contribution timing and compounding model.
    s.note(TABLE_START, 3,
           "Compounding: interest applied n times per year.\n"
           "Annual contribution = 12 × monthly input (added end-of-year).\n"
           "Increase periods/year (B8) to model daily/quarterly compounding.",
           kind="note")

    # ── Summary panel ────────────────────────────────────────────────
    # Placed in cols 6..7 (G..H), rows 11..16 (0-based).
    # 1-based data range: sheet row 13 (first) to sheet row 12+YEARS (last).
    first_data = TABLE_START + 2          # sheet row 13
    last_data  = TABLE_START + 1 + YEARS  # sheet row 12 + YEARS = 37

    s.set(10, 6, "Summary")
    s.fmt(10, 6, bold=True, font_color=PALETTE["header"], font_size=11)

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
        ("Effective Annual Yield (%)",
         "=(POWER(1+$B$6/(100*$B$8),$B$8)-1)*100",
         PALETTE["warn"]),
        ("Return on Total Invested (%)",
         f"=(E{last_data}-$B$5-SUM(D{first_data}:D{last_data}))"
         f"/($B$5+SUM(D{first_data}:D{last_data}))*100",
         PALETTE["warn"]),
    ]

    for i, (lbl, expr, fill) in enumerate(summary_items):
        r = 11 + i   # 0-based rows 11..16
        s.set(r, 6, lbl)
        s.formula(r, 7, expr)
        s.fmt(r, 6, align="left")
        nfmt = "0.0000" if "%" in lbl else "£#,##0.00"
        s.fmt(r, 7, bg=fill, align="right", number_format=nfmt, bold=True)

    s.box(11, 6, 16, 7, color=PALETTE["header"], width=1.5)
    s.col_width(6, 210)
    s.col_width(7, 130)

    # Note 3: power of compounding.
    s.note(11, 7,
           "Final Balance = Interest + Contributions + Principal.\n"
           "The larger the compounding frequency (B8), the higher\n"
           "the effective annual yield — compare monthly vs annual.",
           kind="note")

    # ── Chart (live-bound to Year col A and Ending Balance col E) ─────
    # 0-based data rows: TABLE_START+1 .. TABLE_START+YEARS
    r0 = TABLE_START + 1          # 0-based first data row (= 12)
    r1 = TABLE_START + YEARS      # 0-based last data row  (= 36)

    s.chart(
        [Series(
            years_arr,
            end_arr,
            label="Ending Balance",
            plot_type="Line+Symbol",
            color="#4472c4",
            linewidth=2.0,
            marker="o",
            markersize=5.0,
            x_col=0,   # 0-based column A (Year)
            y_col=4,   # 0-based column E (Ending Balance)
            row_start=r0,
            row_end=r1,
        )],
        at=(560, 20),
        size=(460, 320),
        title="Portfolio Growth Over Time",
        xlabel="Year",
        ylabel="Balance (£)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    # E_n = B * (1 + r/n)^n + 12*C
    # with growth factor f = (1 + r/n)^n
    s.equation(
        r"E = B \cdot \left(1 + \frac{r}{n}\right)^{n} + 12C",
        at=(560, 360),
        fontsize=18,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(320, 56),
    )

    # ── Save ─────────────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Finance",
    )
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Compound Interest.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
