"""Build the "Monthly Budget" Finance template .ksheet.

A polished, fully live monthly household budget workbook with:
  - Title block and instructions
  - Income section with monthly columns (Jan–Dec) + annual total
  - Expense categories (Housing, Food, Transport, Utilities, Personal,
    Recreation, Healthcare, Savings) with Budget vs Actual sub-rows
  - Totals, Difference, and % of Total as live formulas
  - Summary panel (Total Income, Total Expenses, Net, Savings Rate)
  - Bar chart of annual spending by expense category (data-bound)
  - Budget formula equation (LaTeX)
  - Instructive sticky notes

Run:  python examples/build_tpl_monthly_budget.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Layout constants ──────────────────────────────────────────────────
# Sheet uses columns:
#   A (0)  = Category label
#   B..M (1..12) = Jan..Dec amounts
#   N (13) = Annual Total  (=SUM formula)
#   O (14) = Budget Total  (=SUM formula, for Actual rows)
#   P (15) = Difference    (Actual − Budget)
#   Q (16) = % of Total    (Actual total / Grand total)
#
# The "Budget" sheet has one combined row per category (editable defaults
# for each month) plus a totals row.  Simpler than Budget/Actual pairs,
# which would need more rows — but we add a "Summary" mini-table on the
# right showing Budget vs Actual vs Difference for each category using
# a dedicated "Summary" sheet.
#
# Main sheet layout (0-based rows):
#   0   Title
#   1   Subtitle
#   2   (blank)
#   3   ── INCOME SECTION header
#   4   Headers row  (Category | Jan … Dec | Annual Total)
#   5   Salary / Wages
#   6   Freelance / Side Income
#   7   Investment Income
#   8   Other Income
#   9   TOTAL INCOME (formula row)
#  10   (blank)
#  11   ── EXPENSES SECTION header
#  12   Headers row
#  13+  Expense categories (one row each)
#  last Expense TOTAL row
#  ...  (blank)
#  Summary panel to the right

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Column letters for months (B=1..M=12), N=Annual Total, O=% of Grand
COL_LETTER = {i: chr(65 + i) for i in range(26)}   # 0=A..25=Z

# Income rows (editable defaults, £/month)
INCOME_CATS = [
    ("Salary / Wages",        [3500, 3500, 3500, 3500, 3500, 3500,
                               3500, 3500, 3500, 3500, 3500, 3500]),
    ("Freelance / Side",      [ 200,  150,  300,  250,  200,  400,
                                100,  200,  300,  150,  250,  200]),
    ("Investment Returns",    [  80,   80,   80,   80,   80,   80,
                                 80,   80,   80,   80,   80,   80]),
    ("Other Income",          [   0,    0,    0,  500,    0,    0,
                                  0,    0,    0,    0,    0,  200]),
]

# Expense categories (editable defaults, £/month)
EXPENSE_CATS = [
    ("Housing (Rent/Mortgage)", [1200, 1200, 1200, 1200, 1200, 1200,
                                 1200, 1200, 1200, 1200, 1200, 1200]),
    ("Groceries & Food",        [ 350,  320,  360,  340,  380,  400,
                                   350,  360,  340,  330,  370,  450]),
    ("Transport",               [ 120,  110,  130,  120,  115,  140,
                                   125,  120,  130,  120,  125,  130]),
    ("Utilities & Bills",       [ 180,  170,  160,  140,  120,  110,
                                   105,  110,  120,  140,  160,  180]),
    ("Healthcare",              [  50,   50,   50,   50,  100,   50,
                                    50,   50,   50,   50,   50,   50]),
    ("Personal & Clothing",     [  80,   60,  100,   80,  120,  150,
                                    60,   80,  100,   80,   60,  200]),
    ("Entertainment & Dining",  [ 150,  130,  160,  140,  180,  200,
                                   140,  160,  150,  130,  170,  250]),
    ("Savings & Investments",   [ 500,  500,  500,  500,  500,  500,
                                   500,  500,  500,  500,  500,  500]),
]


def col(c: int) -> str:
    """0-based column index → spreadsheet letter (A, B, …, Z, AA, …)."""
    letters = ""
    c += 1
    while c > 0:
        c, rem = divmod(c - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def build() -> str:
    n_income = len(INCOME_CATS)
    n_expense = len(EXPENSE_CATS)

    # Row layout (0-based)
    ROW_TITLE    = 0
    ROW_SUBTITLE = 1
    # Income block
    ROW_INC_HDR  = 3   # section label
    ROW_INC_HEAD = 4   # column headers
    ROW_INC_FIRST = 5  # first income data row
    ROW_INC_LAST  = ROW_INC_FIRST + n_income - 1
    ROW_INC_TOTAL = ROW_INC_LAST + 1
    # Expense block
    ROW_EXP_HDR   = ROW_INC_TOTAL + 2
    ROW_EXP_HEAD  = ROW_EXP_HDR + 1
    ROW_EXP_FIRST = ROW_EXP_HEAD + 1
    ROW_EXP_LAST  = ROW_EXP_FIRST + n_expense - 1
    ROW_EXP_TOTAL = ROW_EXP_LAST + 1

    # Columns (0-based)
    COL_CAT  = 0          # A  label
    COL_JAN  = 1          # B
    COL_DEC  = 12         # M
    COL_ANN  = 13         # N  Annual Total
    COL_PCT  = 14         # O  % of Grand Total (expense only)

    # 1-based sheet rows for formula refs
    INC_FIRST_SR = ROW_INC_FIRST + 1
    INC_LAST_SR  = ROW_INC_LAST  + 1
    INC_TOTAL_SR = ROW_INC_TOTAL + 1
    EXP_FIRST_SR = ROW_EXP_FIRST + 1
    EXP_LAST_SR  = ROW_EXP_LAST  + 1
    EXP_TOTAL_SR = ROW_EXP_TOTAL + 1

    # Annual-total column letter
    N = col(COL_ANN)   # "N"
    O = col(COL_PCT)   # "O"

    wb = Workbook(min_rows=50, min_cols=16)
    s = wb.add_sheet("Monthly Budget")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(COL_CAT, 200)
    for c in range(COL_JAN, COL_DEC + 1):
        s.col_width(c, 72)
    s.col_width(COL_ANN, 90)
    s.col_width(COL_PCT, 80)

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Monthly Household Budget",
        "Track income and expenses month-by-month — edit the blue cells to personalise",
        span=15,
    )

    # ── Instruction note ──────────────────────────────────────────────
    s.note(ROW_TITLE, COL_PCT,
           "TEMPLATE: Replace blue amounts with your own figures. "
           "All totals, differences, and the chart update automatically.",
           kind="note")

    # ── INCOME section ────────────────────────────────────────────────
    s.set(ROW_INC_HDR, COL_CAT, "INCOME")
    s.fmt(ROW_INC_HDR, COL_CAT,
          bold=True, font_size=12, font_color=PALETTE["header"])
    s.merge(ROW_INC_HDR, COL_CAT, 1, 4)

    # Header row
    _write_section_headers(s, ROW_INC_HEAD, COL_CAT, COL_PCT,
                           row_label="Category")

    # Income data rows
    for i, (cat, monthly) in enumerate(INCOME_CATS):
        r = ROW_INC_FIRST + i
        sr = r + 1
        s.set(r, COL_CAT, cat)
        s.fmt(r, COL_CAT, align="left")
        band = PALETTE["band_alt"] if (i % 2) else None
        for m, val in enumerate(monthly):
            c = COL_JAN + m
            s.set(r, c, val)
            kw = dict(align="right", number_format="0")
            if band:
                kw["bg"] = band
            s.fmt(r, c, **kw)
        # Annual total formula
        s.formula(r, COL_ANN,
                  f"=SUM({col(COL_JAN)}{sr}:{col(COL_DEC)}{sr})")
        kw = dict(align="right", number_format="0", bold=True)
        if band:
            kw["bg"] = PALETTE["band"]
        s.fmt(r, COL_ANN, **kw)
        # No % column for income rows (leave blank)

    # Income TOTAL row
    r = ROW_INC_TOTAL
    sr = r + 1
    s.set(r, COL_CAT, "TOTAL INCOME")
    s.fmt(r, COL_CAT, bold=True, bg=PALETTE["header"],
          font_color="#ffffff", align="left")
    for m in range(12):
        c = COL_JAN + m
        cl = col(c)
        s.formula(r, c,
                  f"=SUM({cl}{INC_FIRST_SR}:{cl}{INC_LAST_SR})")
        s.fmt(r, c, bold=True, bg=PALETTE["header"],
              font_color="#ffffff", align="right", number_format="0")
    # Annual total of totals
    s.formula(r, COL_ANN,
              f"=SUM({N}{INC_FIRST_SR}:{N}{INC_LAST_SR})")
    s.fmt(r, COL_ANN, bold=True, bg=PALETTE["header"],
          font_color="#ffffff", align="right", number_format="0")
    # Box around income block
    s.box(ROW_INC_HEAD, COL_CAT, ROW_INC_TOTAL, COL_ANN,
          color=PALETTE["header"], width=1.2)

    # ── EXPENSES section ──────────────────────────────────────────────
    s.set(ROW_EXP_HDR, COL_CAT, "EXPENSES")
    s.fmt(ROW_EXP_HDR, COL_CAT,
          bold=True, font_size=12, font_color=PALETTE["accent"])
    s.merge(ROW_EXP_HDR, COL_CAT, 1, 4)

    _write_section_headers(s, ROW_EXP_HEAD, COL_CAT, COL_PCT,
                           row_label="Category", show_pct=True)

    for i, (cat, monthly) in enumerate(EXPENSE_CATS):
        r = ROW_EXP_FIRST + i
        sr = r + 1
        s.set(r, COL_CAT, cat)
        s.fmt(r, COL_CAT, align="left")
        band = PALETTE["band_alt"] if (i % 2) else None
        for m, val in enumerate(monthly):
            c = COL_JAN + m
            s.set(r, c, val)
            kw = dict(align="right", number_format="0")
            if band:
                kw["bg"] = band
            s.fmt(r, c, **kw)
        # Annual total
        s.formula(r, COL_ANN,
                  f"=SUM({col(COL_JAN)}{sr}:{col(COL_DEC)}{sr})")
        kw = dict(align="right", number_format="0", bold=True)
        if band:
            kw["bg"] = PALETTE["band"]
        s.fmt(r, COL_ANN, **kw)
        # % of total expenses — uses IFERROR to guard division-by-zero
        s.formula(r, COL_PCT,
                  f"=IFERROR({N}{sr}/{N}{EXP_TOTAL_SR},0)")
        kw2 = dict(align="right", number_format="0%")
        if band:
            kw2["bg"] = PALETTE["band_alt"]
        s.fmt(r, COL_PCT, **kw2)

    # Expense TOTAL row
    r = ROW_EXP_TOTAL
    sr = r + 1
    s.set(r, COL_CAT, "TOTAL EXPENSES")
    s.fmt(r, COL_CAT, bold=True, bg=PALETTE["accent"],
          font_color="#ffffff", align="left")
    for m in range(12):
        c = COL_JAN + m
        cl = col(c)
        s.formula(r, c,
                  f"=SUM({cl}{EXP_FIRST_SR}:{cl}{EXP_LAST_SR})")
        s.fmt(r, c, bold=True, bg=PALETTE["accent"],
              font_color="#ffffff", align="right", number_format="0")
    s.formula(r, COL_ANN,
              f"=SUM({N}{EXP_FIRST_SR}:{N}{EXP_LAST_SR})")
    s.fmt(r, COL_ANN, bold=True, bg=PALETTE["accent"],
          font_color="#ffffff", align="right", number_format="0")
    # 100% marker
    s.set(r, COL_PCT, "100%")
    s.fmt(r, COL_PCT, bold=True, bg=PALETTE["accent"],
          font_color="#ffffff", align="right")

    # Box around expense block
    s.box(ROW_EXP_HEAD, COL_CAT, ROW_EXP_TOTAL, COL_PCT,
          color=PALETTE["accent"], width=1.2)

    # ── NET SUMMARY row ───────────────────────────────────────────────
    ROW_NET = ROW_EXP_TOTAL + 2
    s.set(ROW_NET, COL_CAT, "NET (Income − Expenses)")
    s.fmt(ROW_NET, COL_CAT, bold=True, italic=True, align="left")
    for m in range(12):
        c = COL_JAN + m
        cl = col(c)
        inc_r = INC_TOTAL_SR
        exp_r = EXP_TOTAL_SR
        s.formula(ROW_NET, c, f"={cl}{inc_r}-{cl}{exp_r}")
        s.fmt(ROW_NET, c, bold=True, align="right", number_format="0")
    s.formula(ROW_NET, COL_ANN,
              f"={N}{INC_TOTAL_SR}-{N}{EXP_TOTAL_SR}")
    s.fmt(ROW_NET, COL_ANN, bold=True, align="right", number_format="0")
    s.box(ROW_NET, COL_CAT, ROW_NET, COL_ANN,
          color=PALETTE["header"], width=1.2)

    # Conditional fill: we cannot do dynamic conditional formatting here,
    # so leave neutral; the formula will show positive or negative values.
    s.note(ROW_NET, COL_ANN,
           "Positive = surplus. Negative = deficit. "
           "Aim for at least 10% of income in savings each month.",
           kind="note")

    # ── SUMMARY PANEL (right of expense table) ────────────────────────
    # Placed starting at row 3, column 16 (Q)
    COL_SUM_L = 16   # Q — label
    COL_SUM_V = 17   # R — value

    s.col_width(COL_SUM_L, 180)
    s.col_width(COL_SUM_V, 100)

    s.set(ROW_INC_HDR, COL_SUM_L, "Annual Summary")
    s.fmt(ROW_INC_HDR, COL_SUM_L,
          bold=True, font_size=12, font_color=PALETTE["header"])
    s.merge(ROW_INC_HDR, COL_SUM_L, 1, 2)

    summary_items = [
        ("Total Income (£)",    f"={N}{INC_TOTAL_SR}", PALETTE["good"]),
        ("Total Expenses (£)",  f"={N}{EXP_TOTAL_SR}", PALETTE["bad"]),
        ("Net Savings (£)",     f"={N}{INC_TOTAL_SR}-{N}{EXP_TOTAL_SR}",
         PALETTE["band"]),
        ("Savings Rate",
         f"=IFERROR(({N}{INC_TOTAL_SR}-{N}{EXP_TOTAL_SR})/{N}{INC_TOTAL_SR},0)",
         PALETTE["warn"]),
        ("Avg Monthly Surplus",
         f"=IFERROR(({N}{INC_TOTAL_SR}-{N}{EXP_TOTAL_SR})/12,0)",
         PALETTE["band_alt"]),
    ]

    for i, (lbl, expr, col_bg) in enumerate(summary_items):
        r = ROW_INC_FIRST + i
        s.set(r, COL_SUM_L, lbl)
        s.fmt(r, COL_SUM_L, align="left")
        s.formula(r, COL_SUM_V, expr)
        nf = "0%" if "Rate" in lbl else "0"
        s.fmt(r, COL_SUM_V, bold=True, bg=col_bg,
              align="right", number_format=nf)

    s.box(ROW_INC_FIRST, COL_SUM_L,
          ROW_INC_FIRST + len(summary_items) - 1, COL_SUM_V,
          color=PALETTE["header"], width=1.2)

    s.note(ROW_INC_FIRST, COL_SUM_L,
           "Summary auto-updates when you change any monthly amount.",
           kind="note")

    # ── BAR CHART — spending by category ─────────────────────────────
    # X labels: expense categories (column A, rows EXP_FIRST..EXP_LAST)
    # Y values: annual totals (column N, same rows)
    # Designate for chart binding
    s.designate(COL_ANN, "Y")

    exp_annual = np.array([sum(m) for _, m in EXPENSE_CATS], dtype=float)
    cat_indices = np.arange(len(EXPENSE_CATS), dtype=float)  # x = row indices

    r0 = ROW_EXP_FIRST   # 0-based inclusive start
    r1 = ROW_EXP_LAST    # 0-based inclusive end

    s.chart(
        [Series(
            x=cat_indices,
            y=exp_annual,
            label="Annual Spend",
            plot_type="Bar",
            color=PALETTE["accent"],
            y_col=COL_ANN,
            row_start=r0,
            row_end=r1,
        )],
        at=(1480, 30),
        size=(420, 320),
        title="Annual Spending by Category",
        xlabel="Category",
        ylabel="Amount (£)",
        grid=True,
        legend=False,
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    s.equation(
        r"\mathrm{Net} = \sum_{m=1}^{12} (\mathrm{Income}_m - \mathrm{Expenses}_m)",
        at=(1480, 370),
        fontsize=16,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(420, 50),
    )

    # ── Output ────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Finance", "Monthly Budget.ksheet",
    )
    wb.save(out)
    return out


def _write_section_headers(sheet, row, col_cat, col_last,
                           row_label="Category", show_pct=False):
    """Write the column-header row for an income or expense block."""
    sheet.set(row, col_cat, row_label)
    sheet.fmt(row, col_cat, bold=True, bg=PALETTE["header"],
              font_color="#ffffff", align="center")
    for m, name in enumerate(MONTHS):
        c = col_cat + 1 + m
        sheet.set(row, c, name)
        sheet.fmt(row, c, bold=True, bg=PALETTE["header"],
                  font_color="#ffffff", align="center")
    # Annual total header
    sheet.set(row, col_last - (1 if show_pct else 0), "Annual Total")
    sheet.fmt(row, col_last - (1 if show_pct else 0),
              bold=True, bg=PALETTE["header"],
              font_color="#ffffff", align="center")
    if show_pct:
        sheet.set(row, col_last, "% of Total")
        sheet.fmt(row, col_last,
                  bold=True, bg=PALETTE["header"],
                  font_color="#ffffff", align="center")


if __name__ == "__main__":
    path = build()
    print(f"Saved: {path}")
