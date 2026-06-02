"""Build the "Loan Comparison" Finance template .ksheet.

Compare three loan options side by side (Loan A / B / C) with editable
inputs per loan (amount, annual rate, term) and live formula-driven
outputs (monthly payment via closed-form PMT, total paid, total interest).
The cheapest loan is highlighted in green.  A data-bound bar chart shows
total interest across the three options.

Run:  python examples/build_tpl_loan_comparison.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Default input values (used to pre-populate editable cells and to
#    compute the initial chart render data — formulas re-evaluate on open).
LOANS = [
    {"label": "Loan A", "amount": 20000.0, "rate": 5.5,  "term": 5},
    {"label": "Loan B", "amount": 20000.0, "rate": 7.25, "term": 3},
    {"label": "Loan C", "amount": 20000.0, "rate": 4.0,  "term": 7},
]


def _pmt(amount: float, annual_rate_pct: float, term_years: int) -> float:
    """Closed-form monthly payment (matches the sheet formula)."""
    r = annual_rate_pct / 100.0 / 12.0
    n = term_years * 12
    if r == 0:
        return amount / n
    return amount * r / (1.0 - (1.0 + r) ** (-n))


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=12)
    s = wb.add_sheet("Loan Comparison")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 200)   # label column
    s.col_width(1, 130)   # Loan A
    s.col_width(2, 130)   # Loan B
    s.col_width(3, 130)   # Loan C
    s.col_width(5, 160)   # summary labels
    s.col_width(6, 130)   # summary values

    # ── Title block ──────────────────────────────────────────────────
    s.title_block("Loan Comparison",
                  "Compare three financing options — edit any input and "
                  "all outputs recalculate instantly",
                  row=0, col=0, span=7)

    # ── Column headers (row 3, 0-based) ──────────────────────────────
    #    Sheet row 4 (A4 = blank label, B4 = Loan A, C4 = Loan B, D4 = Loan C)
    HEADER_ROW = 3
    s.set(HEADER_ROW, 0, "")
    for j, loan in enumerate(LOANS):
        c = 1 + j
        s.set(HEADER_ROW, c, loan["label"])
        s.fmt(HEADER_ROW, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center",
              font_size=12)
    s.fmt(HEADER_ROW, 0, bg=PALETTE["header"], font_color=PALETTE["header_text"])

    # ── Input rows (editable cells) ───────────────────────────────────
    #    Row 4 (0-based) → sheet row 5  → B5, C5, D5 = amounts
    #    Row 5 (0-based) → sheet row 6  → B6, C6, D6 = annual rates (%)
    #    Row 6 (0-based) → sheet row 7  → B7, C7, D7 = term (years)
    INPUT_LABELS = [
        ("Loan Amount ($)",     "amount",  "0.00"),
        ("Annual Rate (%)",     "rate",    "0.00"),
        ("Term (years)",        "term",    "0"),
    ]
    INPUT_START = 4   # 0-based row index of first input row
    COL_LETTERS = ["B", "C", "D"]   # columns for Loan A/B/C

    for i, (lbl, key, nfmt) in enumerate(INPUT_LABELS):
        r = INPUT_START + i
        s.set(r, 0, lbl)
        s.fmt(r, 0, bold=True, align="left")
        for j, loan in enumerate(LOANS):
            c = 1 + j
            s.set(r, c, loan[key])
            s.fmt(r, c, bg=PALETTE["warn"], align="center",
                  number_format=nfmt, bold=False)
    # Box around the editable input block
    s.box(INPUT_START, 0, INPUT_START + 2, 3,
          color=PALETTE["accent"], width=1.5)

    # ── Formula rows ─────────────────────────────────────────────────
    #    Sheet rows (1-based):
    #      Amount  = row 5 → B5/C5/D5
    #      Rate    = row 6 → B6/C6/D6
    #      Term    = row 7 → B7/C7/D7
    #    Computed:
    #      Monthly payment = row 8  → B8/C8/D8
    #      Total paid      = row 9  → B9/C9/D9
    #      Total interest  = row 10 → B10/C10/D10

    FORMULA_LABELS = [
        "Monthly Payment ($)",
        "Total Paid ($)",
        "Total Interest ($)",
    ]
    FORMULA_START = INPUT_START + 3   # 0-based = 7 → sheet row 8

    s.set(FORMULA_START - 1, 0, "Computed Results")
    s.fmt(FORMULA_START - 1, 0, bold=True, italic=True,
          font_color=PALETTE["header"])

    for i, lbl in enumerate(FORMULA_LABELS):
        r = FORMULA_START + i
        s.set(r, 0, lbl)
        s.fmt(r, 0, bold=True, align="left")

    # Write PMT / Total Paid / Total Interest formulas for each loan.
    # Monthly payment PMT: L*r/(1-POWER(1+r,-n)) with r=rate/100/12, n=term*12
    # Guard zero-rate with IFERROR: fallback = amount / (term*12)
    #   Loan A: amount=B5, rate=B6, term=B7 → sheet col B (1-based)
    #   Loan B: amount=C5, rate=C6, term=C7 → sheet col C
    #   Loan C: amount=D5, rate=D6, term=D7 → sheet col D

    for j, cl in enumerate(COL_LETTERS):
        c = 1 + j
        # Sheet row refs (1-based): amount=row5, rate=row6, term=row7
        amount_ref = f"${cl}$5"
        rate_ref   = f"${cl}$6"
        term_ref   = f"${cl}$7"

        pmt_row   = FORMULA_START       # 0-based row 7  → sheet row 8
        total_row = FORMULA_START + 1   # 0-based row 8  → sheet row 9
        int_row   = FORMULA_START + 2   # 0-based row 9  → sheet row 10

        # Sheet row numbers (1-based) for formula self-references
        pmt_sr   = pmt_row   + 1   # = 8
        total_sr = total_row + 1   # = 9

        # PMT = amount * r / (1 - POWER(1+r, -n))
        # with r = rate/100/12, n = term*12
        # IFERROR fallback: amount/(term*12) for zero-rate loans
        pmt_formula = (
            f"=IFERROR("
            f"{amount_ref}*({rate_ref}/100/12)"
            f"/(1-POWER(1+{rate_ref}/100/12,-{term_ref}*12)),"
            f"{amount_ref}/({term_ref}*12)"
            f")"
        )

        total_formula = f"={cl}{pmt_sr}*{term_ref}*12"
        interest_formula = f"={cl}{total_sr}-{amount_ref}"

        s.formula(pmt_row,   c, pmt_formula)
        s.formula(total_row, c, total_formula)
        s.formula(int_row,   c, interest_formula)

    # Format computed rows
    for i in range(3):
        r = FORMULA_START + i
        for j in range(3):
            c = 1 + j
            band = PALETTE["band"] if i % 2 == 0 else PALETTE["band_alt"]
            s.fmt(r, c, bg=band, align="center", number_format="0.00")

    # ── Cheapest-loan highlighting ────────────────────────────────────
    # Cheapest = lowest total interest (row 10 in sheet, 0-based row 9).
    # Use IF(value==MIN(...), green, existing band) for each cell.
    # We highlight both total paid and total interest rows.
    int_r = FORMULA_START + 2   # 0-based row of total interest
    # Sheet row 10: total interest in B10, C10, D10
    int_sr = int_r + 1

    # Also highlight the monthly payment row for cheapest loan
    pmt_r = FORMULA_START       # 0-based row of monthly payment (row 8)
    pmt_sr_val = pmt_r + 1

    # We do highlight highlighting by overwriting bg based on MIN check —
    # since ksheet doesn't support conditional formatting, we rely on the
    # IF formula to pick the cheapest LABEL row and a note to explain.
    # The green fill is applied statically to match the default inputs,
    # and a note explains which loan wins initially.
    # Compute which loan has lowest total interest with default inputs:
    interests = []
    for loan in LOANS:
        p = _pmt(loan["amount"], loan["rate"], loan["term"])
        n = loan["term"] * 12
        interests.append(p * n - loan["amount"])

    cheapest_j = int(np.argmin(interests))
    cheapest_col = 1 + cheapest_j

    # Apply green highlight to cheapest loan column in computed rows
    for i in range(3):
        r = FORMULA_START + i
        c = cheapest_col
        s.fmt(r, c, bg=PALETTE["good"], align="center",
              number_format="0.00", bold=True)

    # Also add a "Cheapest" indicator row
    BEST_ROW = FORMULA_START + 3   # 0-based row 10 → sheet row 11
    s.set(BEST_ROW, 0, "Lowest Interest?")
    s.fmt(BEST_ROW, 0, bold=True, italic=True, align="left")
    for j, cl in enumerate(COL_LETTERS):
        c = 1 + j
        # IF this loan's interest == MIN of all three → "YES" else "—"
        s.formula(BEST_ROW, c,
                  f"=IF({cl}{int_sr}==MIN(B{int_sr},C{int_sr},D{int_sr}),"
                  f'"YES","-")')
        s.fmt(BEST_ROW, c, align="center", bold=True,
              bg=PALETTE["band_alt"])

    # Outer border around the entire inputs+computed block
    s.box(HEADER_ROW, 0, BEST_ROW, 3,
          color=PALETTE["header"], width=1.5)
    # Inner borders (separator between input and computed)
    s.box(FORMULA_START, 0, BEST_ROW, 3,
          color=PALETTE["header"], width=1.0)

    # ── Summary panel (right side) ────────────────────────────────────
    # Sheet rows for computed values (1-based):
    pmt_sr_1   = FORMULA_START + 1        # sheet row = FORMULA_START+1
    total_sr_1 = FORMULA_START + 2        # sheet row = FORMULA_START+2
    int_sr_1   = FORMULA_START + 3        # sheet row = FORMULA_START+3

    SUMM_COL  = 5   # label column (F)
    SUMM_VAL  = 6   # value column (G)
    SUMM_START = HEADER_ROW   # align with headers row

    s.set(SUMM_START, SUMM_COL, "Summary")
    s.fmt(SUMM_START, SUMM_COL, bold=True, font_size=12,
          bg=PALETTE["header"], font_color=PALETTE["header_text"],
          align="center")
    s.fmt(SUMM_START, SUMM_VAL, bg=PALETTE["header"],
          font_color=PALETTE["header_text"])

    # Summary rows: min payment, min total interest, cheapest loan label
    summ_rows = [
        ("Lowest Monthly Pmt ($)",
         f"=MIN(B{FORMULA_START+1},C{FORMULA_START+1},D{FORMULA_START+1})",
         PALETTE["good"]),
        ("Lowest Total Interest ($)",
         f"=MIN(B{int_sr},C{int_sr},D{int_sr})",
         PALETTE["good"]),
        ("Cheapest Loan",
         f'=IF(B{int_sr}==MIN(B{int_sr},C{int_sr},D{int_sr}),"Loan A",'
         f'IF(C{int_sr}==MIN(B{int_sr},C{int_sr},D{int_sr}),"Loan B","Loan C"))',
         PALETTE["warn"]),
    ]
    for i, (lbl, expr, col) in enumerate(summ_rows):
        r = SUMM_START + 1 + i
        s.set(r, SUMM_COL, lbl)
        s.formula(r, SUMM_VAL, expr)
        s.fmt(r, SUMM_COL, align="left", bold=False)
        nfmt = "0.00" if i < 2 else None
        kw = dict(bg=col, align="center", bold=True)
        if nfmt:
            kw["number_format"] = nfmt
        s.fmt(r, SUMM_VAL, **kw)

    s.box(SUMM_START, SUMM_COL, SUMM_START + len(summ_rows), SUMM_VAL,
          color=PALETTE["header"], width=1.5)

    # ── Sticky notes ──────────────────────────────────────────────────
    s.note(INPUT_START, 1,
           "Edit Loan Amount, Rate, or Term for any column — all payment "
           "and interest rows recalculate automatically.",
           kind="note")
    s.note(BEST_ROW, 0,
           "The YES/NO row uses IF(value==MIN(...)) to flag the cheapest loan. "
           "Green cells show the winning column.",
           kind="note")
    s.note(SUMM_START + 3, SUMM_COL,
           "Summary panel shows the best values across all three loans.",
           kind="note")

    # ── PMT equation (mathtext) ───────────────────────────────────────
    s.equation(
        r"M = \frac{L \cdot r}{1 - (1+r)^{-n}}",
        at=(540, 310), fontsize=20,
        color="#222222", bg_color="#ffffff",
        border_color=PALETTE["header"], border_width=1.5,
        size=(280, 60),
    )
    # Label beneath equation
    s.set(BEST_ROW + 2, 5,
          "M=monthly pmt, L=loan amount, r=rate/12, n=term×12")
    s.fmt(BEST_ROW + 2, 5, italic=True, font_color="#555555",
          font_size=9)

    # ── Bar chart: Total Interest by Loan ─────────────────────────────
    # Each loan is one Series with x=[loan_index], y=[total_interest].
    # Data-bound: y_col=1/2/3, row_start=row_end=int_r (0-based).
    bar_colors = [PALETTE["header"], PALETTE["accent"], PALETTE["good"]]

    chart_series = []
    for j, loan in enumerate(LOANS):
        p = _pmt(loan["amount"], loan["rate"], loan["term"])
        n = loan["term"] * 12
        total_interest = p * n - loan["amount"]
        chart_series.append(
            Series(
                x=[float(j)],
                y=[total_interest],
                label=loan["label"],
                plot_type="Bar",
                color=bar_colors[j],
                y_col=1 + j,
                row_start=int_r,
                row_end=int_r,
            )
        )

    s.chart(
        chart_series,
        at=(540, 30), size=(420, 270),
        title="Total Interest by Loan",
        xlabel="Loan Option",
        ylabel="Total Interest ($)",
        grid=True, legend=True,
    )

    # ── Output path ───────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Finance",
    )
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Loan Comparison.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
