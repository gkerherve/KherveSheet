"""Build the "Currency Converter" Finance template .ksheet.

A polished, live-formula spreadsheet for converting a base amount into
multiple target currencies.  The user edits:
  - B4  : Amount (in base currency)
  - D7:D18 : Exchange rate for each currency (units per 1 base unit)

All "Converted" and "Reverse" cells are live formulas referencing those
inputs.  A data-bound bar chart visualises the converted amounts.

Run:  python examples/build_tpl_currency_converter.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Make the repo importable when called from any cwd.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Default rates (1 USD → target) used for initial render only ──────
CURRENCIES = [
    # (code,  full name,             rate per 1 USD)
    ("EUR", "Euro",                   0.92),
    ("GBP", "British Pound",          0.79),
    ("JPY", "Japanese Yen",         157.20),
    ("CHF", "Swiss Franc",            0.90),
    ("CAD", "Canadian Dollar",        1.37),
    ("AUD", "Australian Dollar",      1.54),
    ("CNY", "Chinese Yuan",           7.26),
    ("INR", "Indian Rupee",          83.50),
    ("MXN", "Mexican Peso",          17.15),
    ("BRL", "Brazilian Real",         5.10),
    ("SGD", "Singapore Dollar",       1.35),
    ("HKD", "Hong Kong Dollar",       7.82),
]

AMOUNT = 1000.0   # default editable amount in base currency


def build() -> str:
    wb = Workbook(min_rows=44, min_cols=14)
    s = wb.add_sheet("Currency Converter")

    # ── Column widths ────────────────────────────────────────────────
    s.col_width(0, 60)    # A  row spacer / index
    s.col_width(1, 60)    # B  currency code
    s.col_width(2, 160)   # C  full name
    s.col_width(3, 130)   # D  rate (editable)
    s.col_width(4, 140)   # E  converted
    s.col_width(5, 140)   # F  reverse (1 unit of target → base)
    s.col_width(6, 30)    # G  spacer
    s.col_width(7, 160)   # H  summary labels
    s.col_width(8, 120)   # I  summary values

    # ── Title block ──────────────────────────────────────────────────
    s.title_block("Currency Converter",
                  "Enter an amount and base currency; edit rates to update all conversions",
                  row=0, col=0, span=9)

    # ── Input panel: Amount ──────────────────────────────────────────
    # Row 2: section label
    s.set(2, 0, "Base Currency")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"], font_size=11)
    s.merge(2, 0, 1, 5)

    # Row 3: "Amount" label + editable cell (B4 = row 3, col 1)
    s.set(3, 0, "Amount")
    s.fmt(3, 0, bold=True, align="right")
    s.set(3, 1, AMOUNT)
    s.fmt(3, 1, bold=True, bg=PALETTE["warn"], align="center",
          number_format="0.00", font_size=12)
    s.merge(3, 1, 1, 2)   # span B4:C4

    s.set(3, 3, "Base currency label")
    s.fmt(3, 3, bold=False, italic=True, align="left",
          font_color="#555555")
    s.set(3, 3, "USD (editable)")
    s.fmt(3, 3, italic=True, font_color="#555555", align="left")

    s.box(3, 0, 3, 4, color=PALETTE["accent"], width=1.5)

    # Yellow sticky: guide the user
    s.note(3, 1,
           "Edit this cell to change the amount — all Converted and "
           "Reverse values update instantly.",
           kind="note")

    # ── Table: currency conversion ────────────────────────────────────
    # Header at row 5 (0-based), data rows 6..17 (12 currencies).
    # Spreadsheet sheet rows: header = row 6 (1-based), data = 7..18.
    # Amount is at B4  → absolute ref  $B$4
    # Rate   is at D7..D18 → per-row ref D<rr>

    TABLE_START = 5   # 0-based row of header
    N = len(CURRENCIES)

    headers = ["Code", "Currency", "Rate (per USD)", "Converted (USD→target)",
               "Reverse (1 target→USD)"]

    rows = []
    for i, (code, name, rate) in enumerate(CURRENCIES):
        # 1-based sheet row of this data row:  header is at TABLE_START+1,
        # so first data row is TABLE_START+2.
        rr = TABLE_START + 2 + i     # 1-based sheet row
        dr = f"D{rr}"                 # rate cell in this row (col D = col 3)
        rows.append([
            code,
            name,
            rate,                              # editable literal
            f"=$B$4*{dr}",                     # Converted = Amount × Rate
            f"=1/{dr}",                        # Reverse   = 1 / Rate (how many USD per 1 target)
        ])

    s.table(TABLE_START, 1,
            headers=headers,
            rows=rows,
            number_format="0.0000",
            banded=True,
            align_data="right")

    # Override: Code column (B) = left aligned, name column (C) = left aligned.
    for i in range(N):
        r = TABLE_START + 1 + i
        s.fmt(r, 1, align="left")   # code
        s.fmt(r, 2, align="left")   # name

    # Make rate column look editable (warm yellow bg so users know to edit it).
    for i in range(N):
        r = TABLE_START + 1 + i
        # Only change bg, keep banding for alternates; apply a light amber
        bg = PALETTE["warn"] if (i % 2 == 0) else "#fff3c0"
        s.fmt(r, 3, bg=bg, align="center", number_format="0.0000")

    # Override converted column: currency number format (2 dp).
    for i in range(N):
        r = TABLE_START + 1 + i
        s.fmt(r, 4, number_format="0.00")
        s.fmt(r, 5, number_format="0.0000")

    # Yellow note on rate column header.
    s.note(TABLE_START, 3,
           "These rates are USER-EDITABLE — they are NOT live FX rates. "
           "Update them manually from any reliable source (e.g. xe.com).",
           kind="note")

    # Note on reverse column.
    s.note(TABLE_START, 5,
           "Reverse: how many USD you get for 1 unit of the target currency "
           "(= 1 / Rate). Useful for back-of-envelope checks.",
           kind="note")

    # ── Designate columns for chart axis hints ────────────────────────
    # Col 1 (B) = currency codes (X labels), col 4 (E) = converted (Y).
    s.designate(1, "X")
    s.designate(4, "Y")

    # ── Summary panel ────────────────────────────────────────────────
    # Positioned to the right of the table (columns H=7, I=8).
    SUMM_ROW = TABLE_START     # 0-based; aligns with table header

    s.set(SUMM_ROW, 7, "Summary")
    s.fmt(SUMM_ROW, 7, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.fmt(SUMM_ROW, 8, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.set(SUMM_ROW, 8, "Value")
    s.fmt(SUMM_ROW, 8, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")

    # 1-based rows for the converted column (E).
    conv_first = TABLE_START + 2      # 1-based
    conv_last  = TABLE_START + 1 + N  # 1-based

    summary_items = [
        ("Amount (USD)",        "=$B$4",                         PALETTE["warn"],  "0.00"),
        ("Highest converted",   f"=MAX(E{conv_first}:E{conv_last})", PALETTE["good"],  "0.00"),
        ("Lowest converted",    f"=MIN(E{conv_first}:E{conv_last})", PALETTE["bad"],   "0.00"),
        ("Average converted",   f"=AVERAGE(E{conv_first}:E{conv_last})", PALETTE["band"], "0.00"),
    ]

    for i, (lbl, expr, bg, nfmt) in enumerate(summary_items):
        r = SUMM_ROW + 1 + i
        s.set(r, 7, lbl)
        s.fmt(r, 7, align="left", bold=False)
        s.formula(r, 8, expr)
        s.fmt(r, 8, bg=bg, align="center", bold=True, number_format=nfmt)

    s.box(SUMM_ROW, 7, SUMM_ROW + len(summary_items), 8,
          color=PALETTE["header"], width=1.5)

    # ── Bar chart: converted amounts ─────────────────────────────────
    # X axis: currency index (0..N-1), Y axis: converted amount.
    # Bound to col E (index 4), rows TABLE_START+1 .. TABLE_START+N.
    row_start_0 = TABLE_START + 1   # 0-based first data row
    row_end_0   = TABLE_START + N   # 0-based last data row  (inclusive)

    # Initial render data (numpy arrays matching formula results).
    rates = np.array([r for _, _, r in CURRENCIES])
    x_idx = np.arange(N, dtype=float)
    y_conv = AMOUNT * rates

    s.chart(
        [Series(x_idx, y_conv, "Converted amount", "Bar",
                color=PALETTE["header"],
                y_col=4,
                row_start=row_start_0,
                row_end=row_end_0)],
        at=(510, 160),
        size=(480, 320),
        title=f"Converted amounts from {AMOUNT:.0f} USD",
        xlabel="Currency index",
        ylabel="Converted amount (target units)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    s.equation(
        r"\mathrm{Converted} = \mathrm{Amount} \times \mathrm{Rate}",
        at=(510, 495),
        fontsize=16,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(360, 44),
    )

    # ── Save ─────────────────────────────────────────────────────────
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "templates", "Finance")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Currency Converter.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
