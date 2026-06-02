"""Build the "Stock Portfolio" Finance template .ksheet.

A holdings tracker: enter your tickers, shares, buy and current prices,
and every derived column — cost basis, market value, gain/loss, gain %
and portfolio weight — updates automatically.  An embedded bar chart
shows market value by holding.

Run:  python examples/build_tpl_stock_portfolio.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Make project importable from any cwd.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Hard-coded sample holdings (users edit these in the sheet) ─────────
HOLDINGS = [
    # (Ticker, Shares, BuyPrice, CurrentPrice)
    ("AAPL",  50,  155.00, 189.50),
    ("MSFT",  30,  250.00, 415.00),
    ("GOOGL", 10,  120.00, 178.50),
    ("AMZN",  20,  130.00, 195.00),
    ("NVDA",  15,  420.00, 875.00),
    ("TSLA",  25,   80.00, 175.50),
    ("META",  40,  180.00, 530.00),
    ("BRK.B", 12,  310.00, 410.00),
]

N = len(HOLDINGS)


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=16)
    s = wb.add_sheet("Portfolio")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 80)   # Ticker
    s.col_width(1, 80)   # Shares
    s.col_width(2, 110)  # Buy Price
    s.col_width(3, 120)  # Current Price
    s.col_width(4, 110)  # Cost Basis
    s.col_width(5, 120)  # Market Value
    s.col_width(6, 110)  # Gain / Loss
    s.col_width(7, 90)   # Gain %
    s.col_width(8, 110)  # % of Portfolio

    # ── Table layout constants ────────────────────────────────────────
    # The table() helper writes:
    #   Header  at 0-based row TABLE_START     → 1-based row TABLE_START+1
    #   Data[k] at 0-based row TABLE_START+1+k → 1-based row TABLE_START+2+k
    #
    # For k in 0..N-1:
    #   0-based data row k : TABLE_START + 1 + k
    #   1-based sheet ref  : TABLE_START + 2 + k  (this is what goes in formulas)
    #
    # Totals row sits immediately after the last data row:
    #   0-based: TABLE_START + 1 + N = TABLE_START + N + 1
    #   1-based: TABLE_START + N + 2

    TABLE_START = 6          # 0-based row of table header
    # 1-based row of totals (for SUM formulas and % Portfolio absolute ref)
    TOTALS_1B   = TABLE_START + N + 2    # = 6 + 8 + 2 = 16
    # 1-based range of data rows (for SUM ranges)
    DATA_1B_FIRST = TABLE_START + 2      # = 8
    DATA_1B_LAST  = TABLE_START + 1 + N  # = 15

    # ── Title block ──────────────────────────────────────────────────
    s.title_block(
        "Stock Portfolio Tracker",
        "Edit Ticker, Shares, Buy Price and Current Price — all other "
        "columns update automatically.",
        span=9,
    )

    # ── Instruction note ─────────────────────────────────────────────
    s.note(0, 9,
           "Blue/yellow cells are editable inputs. "
           "All formula columns recalculate when you change any value.",
           kind="note")

    # ── Summary panel (positioned to the right of the table) ─────────
    # References the totals row column F (Market Value total = col 5).
    SUMM_COL = 11

    s.set(3, SUMM_COL, "Portfolio Summary")
    s.fmt(3, SUMM_COL, bold=True, font_size=13, font_color=PALETTE["header"])
    s.merge(3, SUMM_COL, 1, 3)

    # Summary rows: label | formula value
    labels = [
        ("Total Cost Basis",  f"=E{TOTALS_1B}",                   PALETTE["band"],  "$#,##0.00"),
        ("Total Market Value",f"=F{TOTALS_1B}",                   PALETTE["good"],  "$#,##0.00"),
        ("Total Gain / Loss", f"=G{TOTALS_1B}",                   PALETTE["warn"],  "$#,##0.00"),
        ("Overall Gain %",
         f"=IFERROR((F{TOTALS_1B}-E{TOTALS_1B})/E{TOTALS_1B}*100, 0)",
         PALETTE["warn"],  "0.00"),
        ("# Holdings",
         f"=COUNTA(A{DATA_1B_FIRST}:A{DATA_1B_LAST})",
         PALETTE["band"],  "0"),
    ]

    for i, (lbl, expr, bg, nf) in enumerate(labels):
        r = 4 + i
        s.set(r, SUMM_COL, lbl)
        s.formula(r, SUMM_COL + 1, expr)
        s.fmt(r, SUMM_COL, align="left")
        s.fmt(r, SUMM_COL + 1, bg=bg, align="right", bold=True, number_format=nf)

    s.box(4, SUMM_COL, 4 + len(labels) - 1, SUMM_COL + 1,
          color=PALETTE["header"], width=1.0)
    s.col_width(SUMM_COL, 160)
    s.col_width(SUMM_COL + 1, 120)

    # ── Holdings table ────────────────────────────────────────────────
    # Columns (0-based):
    #   0=Ticker  1=Shares  2=BuyPrice  3=CurPrice
    #   4=Cost    5=MktVal  6=G/L       7=G%       8=%Portfolio

    headers = [
        "Ticker", "Shares", "Buy Price ($)", "Current Price ($)",
        "Cost Basis ($)", "Market Value ($)", "Gain / Loss ($)",
        "Gain %", "% of Portfolio",
    ]

    rows = []
    for k in range(N):
        ticker, shares, buy_px, cur_px = HOLDINGS[k]
        # 1-based sheet row of this data row
        rr = TABLE_START + 2 + k   # 8, 9, 10, ... 15
        rows.append([
            ticker,
            shares,
            buy_px,
            cur_px,
            f"=B{rr}*C{rr}",                           # Cost Basis
            f"=B{rr}*D{rr}",                            # Market Value
            f"=F{rr}-E{rr}",                            # Gain / Loss
            f"=IFERROR((F{rr}-E{rr})/E{rr}*100, 0)",   # Gain %
            f"=IFERROR(F{rr}/$F${TOTALS_1B}*100, 0)",  # % of Portfolio
        ])

    s.table(
        TABLE_START, 0,
        headers=headers,
        rows=rows,
        number_format="0.00",
        banded=True,
        align_data="right",
    )

    # Per-cell format overrides after table() has painted everything.
    for k in range(N):
        r = TABLE_START + 1 + k    # 0-based data row
        s.fmt(r, 0, align="left")                                   # Ticker left
        s.fmt(r, 1, bg=PALETTE["band"],  number_format="0")         # Shares (editable)
        s.fmt(r, 2, bg=PALETTE["band"],  number_format="$#,##0.00") # BuyPx (editable)
        s.fmt(r, 3, bg=PALETTE["warn"],  number_format="$#,##0.00") # CurPx (editable)
        s.fmt(r, 4, number_format="$#,##0.00")                      # Cost
        s.fmt(r, 5, number_format="$#,##0.00")                      # MktVal
        s.fmt(r, 6, number_format="$#,##0.00")                      # G/L
        s.fmt(r, 7, number_format="0.00")                           # Gain%
        s.fmt(r, 8, number_format="0.00")                           # %Portfolio

    # ── Totals row ────────────────────────────────────────────────────
    TOTALS_ROW = TABLE_START + 1 + N   # 0-based = 15

    s.set(TOTALS_ROW, 0, "TOTAL")
    s.fmt(TOTALS_ROW, 0, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")

    # SUM for Shares (col B=1), Cost (E=4), MktVal (F=5), G/L (G=6)
    for col_idx, col_letter, nf in (
        (1, "B", "0"),
        (4, "E", "$#,##0.00"),
        (5, "F", "$#,##0.00"),
        (6, "G", "$#,##0.00"),
    ):
        s.formula(TOTALS_ROW, col_idx,
                  f"=SUM({col_letter}{DATA_1B_FIRST}:{col_letter}{DATA_1B_LAST})")
        s.fmt(TOTALS_ROW, col_idx, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="right",
              number_format=nf)

    # % Portfolio SUM (should be 100) — col I = 8
    s.formula(TOTALS_ROW, 8,
              f"=SUM(I{DATA_1B_FIRST}:I{DATA_1B_LAST})")
    s.fmt(TOTALS_ROW, 8, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="right",
          number_format="0.00")

    # Empty/header-coloured cells for columns that have no aggregate
    for col_idx in (2, 3, 7):
        s.set(TOTALS_ROW, col_idx, "")
        s.fmt(TOTALS_ROW, col_idx, bg=PALETTE["header"],
              font_color=PALETTE["header_text"])

    # Outer border around the whole table + totals row
    s.box(TABLE_START, 0, TOTALS_ROW, 8,
          color=PALETTE["header"], width=1.5)

    # ── Notes ─────────────────────────────────────────────────────────
    s.note(TABLE_START + 1, 3,
           "Edit Current Price cells (yellow) — gains, totals and the "
           "chart update instantly.",
           kind="note")
    s.note(TABLE_START, 8,
           "% of Portfolio sums to ≈100 in the TOTAL row (formula sanity check).",
           kind="note")

    # ── Column designations ───────────────────────────────────────────
    s.designate(5, "Y")   # Market Value is the primary Y axis

    # ── Charts ───────────────────────────────────────────────────────
    # Data rows occupy 0-based rows TABLE_START+1 .. TABLE_START+N  (7..14).
    chart_row_start = TABLE_START + 1   # 0-based first data row = 7
    chart_row_end   = TABLE_START + N   # 0-based last  data row = 14

    init_x  = np.arange(N, dtype=float)
    init_mv = np.array([sh * cp for (_, sh, _, cp) in HOLDINGS], dtype=float)
    init_gl = np.array([sh * (cp - bp) for (_, sh, bp, cp) in HOLDINGS],
                       dtype=float)

    # Chart 1: Market Value by holding (Bar)
    s.chart(
        [
            Series(
                init_x, init_mv,
                label="Market Value ($)",
                plot_type="Bar",
                color="#4472c4",
                y_col=5,                   # column F (0-based)
                row_start=chart_row_start,
                row_end=chart_row_end,
            ),
        ],
        at=(10, 440),
        size=(500, 280),
        title="Market Value by Holding",
        xlabel="Holding",
        ylabel="Market Value ($)",
        grid=True,
        legend=True,
    )

    # Chart 2: Gain / Loss by holding (Bar)
    s.chart(
        [
            Series(
                init_x, init_gl,
                label="Gain / Loss ($)",
                plot_type="Bar",
                color="#70ad47",
                y_col=6,                   # column G (0-based)
                row_start=chart_row_start,
                row_end=chart_row_end,
            ),
        ],
        at=(530, 440),
        size=(500, 280),
        title="Gain / Loss by Holding",
        xlabel="Holding",
        ylabel="Gain / Loss ($)",
        grid=True,
        legend=True,
    )

    # ── Equation ──────────────────────────────────────────────────────
    s.equation(
        r"\mathrm{Gain\%} = \frac{V_{market} - V_{cost}}{V_{cost}} \times 100",
        at=(10, 730),
        fontsize=16,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(380, 52),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Finance", "Stock Portfolio.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
