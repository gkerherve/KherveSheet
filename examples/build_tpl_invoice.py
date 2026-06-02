"""Build the "Invoice Template" Finance template .ksheet.

A professional, fully-formula-driven invoice: editable company info,
client details, invoice metadata (number, date, due date, tax rate),
a line-items table where every Line Total = Qty * Unit Price as a live
formula, and a totals panel (Subtotal / Tax / Grand Total) all wired
to the data above.  No chart — this is a document template.

Run:  python examples/build_tpl_invoice.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

from __future__ import annotations

import os
import sys

# Make the project importable when run from anywhere.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from examples.ksheet_author import Workbook, PALETTE  # noqa: E402


# ─────────────────────────────────────────────────────────────────────
# Layout constants (all 0-based row/col indices)
# ─────────────────────────────────────────────────────────────────────

# Columns (0-based):
#   A(0) — "FROM" label column
#   B(1) — "FROM" value column  (spans into C if needed)
#   C(2) — "BILL TO" label column
#   D(3) — "BILL TO" value column
#   E(4) — meta label  (Invoice #, Date, …)
#   F(5) — meta value
# Items table starts at col A(0):
#   A(0) Description | B(1) Qty | C(2) Unit Price | D(3) Line Total

COL_DESC      = 0   # A
COL_QTY       = 1   # B
COL_UNIT      = 2   # C
COL_TOTAL     = 3   # D

COL_META_LBL  = 4   # E  — invoice #, date, due date, tax rate
COL_META_VAL  = 5   # F

# Rows
ROW_TITLE     = 0   # "INVOICE"
ROW_FROM_HDR  = 2   # "FROM" label
ROW_FROM_NAME = 3   # editable company name
ROW_FROM_ADDR = 4
ROW_FROM_CITY = 5
ROW_FROM_EMAIL= 6
ROW_BILL_HDR  = 2   # "BILL TO" — same row, different cols
ROW_BILL_NAME = 3
ROW_BILL_ADDR = 4
ROW_BILL_CITY = 5
ROW_BILL_EMAIL= 6

# Invoice metadata uses same rows but cols E/F
ROW_INV_NUM   = 2
ROW_DATE      = 3
ROW_DUE       = 4
ROW_TAX_RATE  = 5   # editable tax rate → 0-based row 5, col F → sheet F6

TABLE_START   = 9   # 0-based row where line-items table header sits
                    # header is at sheet row TABLE_START+1 = row 10 (1-based)
                    # first data row is TABLE_START+2 = row 11 (1-based)

# 10 line-item rows + 2 blank user rows
N_ITEMS       = 10
N_BLANK       = 2
N_DATA        = N_ITEMS + N_BLANK

# Rows for totals panel (0-based)
TOTALS_START  = TABLE_START + 1 + N_DATA + 1   # one gap row after data
ROW_SUBTOTAL  = TOTALS_START
ROW_TAX       = TOTALS_START + 1
ROW_GRAND     = TOTALS_START + 2

# Fixed number format for currency
CUR = "0.00"

# ─────────────────────────────────────────────────────────────────────
# Default line items (description, qty, unit_price)
# ─────────────────────────────────────────────────────────────────────
LINE_ITEMS = [
    ("Web Design — Homepage redesign",  1,  2500.00),
    ("Annual Hosting Plan",            12,    29.99),
    ("Domain Renewal",                  1,    14.99),
    ("Wildcard SSL Certificate",        1,    89.00),
    ("SEO Audit — Full site analysis",  1,   750.00),
    ("Logo & Brand Identity pack",      1,   420.00),
    ("Email Marketing setup",           3,   149.00),
    ("Monthly Maintenance retainer",    1,   299.00),
    ("Copywriting — 5 pages",           5,    95.00),
    ("Project Management",             20,    75.00),
]


def col_letter(c: int) -> str:
    """0-based column index → Excel letter (A, B, …, Z, AA, …)."""
    result = ""
    c += 1
    while c > 0:
        c, rem = divmod(c - 1, 26)
        result = chr(65 + rem) + result
    return result


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=10)
    s = wb.add_sheet("Invoice")

    # ── Column widths ────────────────────────────────────────────────
    s.col_width(COL_DESC,     280)   # A — Description
    s.col_width(COL_QTY,       70)   # B — Qty
    s.col_width(COL_UNIT,     110)   # C — Unit Price
    s.col_width(COL_TOTAL,    120)   # D — Line Total
    s.col_width(COL_META_LBL, 130)   # E — Meta label
    s.col_width(COL_META_VAL, 130)   # F — Meta value

    # ── Title bar ────────────────────────────────────────────────────
    # Big "INVOICE" across columns A-D, accent colour
    s.set(ROW_TITLE, 0, "INVOICE")
    s.fmt(ROW_TITLE, 0,
          bold=True, font_size=28, font_color="#ffffff",
          bg=PALETTE["accent"], align="center")
    s.merge(ROW_TITLE, 0, 1, 4)

    # "Professional Invoice Template" subtitle in meta area
    s.set(ROW_TITLE, COL_META_LBL, "Professional Invoice Template")
    s.fmt(ROW_TITLE, COL_META_LBL,
          italic=True, font_color="#555555", align="right")
    s.merge(ROW_TITLE, COL_META_LBL, 1, 2)

    # Thin accent stripe below title
    s.set(1, 0, "")
    s.fmt_range(1, 0, 1, 5, bg=PALETTE["accent"])

    # ── FROM block (cols A-B) ────────────────────────────────────────
    s.set(ROW_FROM_HDR, 0, "FROM")
    s.fmt(ROW_FROM_HDR, 0,
          bold=True, bg=PALETTE["header"], font_color="#ffffff",
          align="center")
    s.merge(ROW_FROM_HDR, 0, 1, 2)

    from_defaults = [
        "Your Company Name",
        "123 Business Street",
        "City, State 00000",
        "hello@yourcompany.com",
    ]
    for i, val in enumerate(from_defaults):
        r = ROW_FROM_NAME + i
        s.set(r, 0, val)
        s.fmt(r, 0, bg=PALETTE["warn"], align="left")
        s.merge(r, 0, 1, 2)

    s.box(ROW_FROM_HDR, 0, ROW_FROM_EMAIL, 1,
          color=PALETTE["header"], width=1.2)

    # ── BILL TO block (cols C-D) ─────────────────────────────────────
    s.set(ROW_BILL_HDR, 2, "BILL TO")
    s.fmt(ROW_BILL_HDR, 2,
          bold=True, bg=PALETTE["header"], font_color="#ffffff",
          align="center")
    s.merge(ROW_BILL_HDR, 2, 1, 2)

    bill_defaults = [
        "Client Company Name",
        "456 Client Avenue",
        "Client City, State 00000",
        "billing@clientco.com",
    ]
    for i, val in enumerate(bill_defaults):
        r = ROW_BILL_NAME + i
        s.set(r, 2, val)
        s.fmt(r, 2, bg=PALETTE["band_alt"], align="left")
        s.merge(r, 2, 1, 2)

    s.box(ROW_BILL_HDR, 2, ROW_BILL_EMAIL, 3,
          color=PALETTE["header"], width=1.2)

    # ── Invoice metadata (cols E-F) ──────────────────────────────────
    meta_labels = [
        (ROW_INV_NUM,  "Invoice #:",    "INV-2026-001"),
        (ROW_DATE,     "Invoice Date:", "2026-06-02"),
        (ROW_DUE,      "Due Date:",     "2026-07-02"),
    ]
    for row, lbl, val in meta_labels:
        s.set(row, COL_META_LBL, lbl)
        s.fmt(row, COL_META_LBL, bold=True, align="right",
              bg=PALETTE["band"])
        s.set(row, COL_META_VAL, val)
        s.fmt(row, COL_META_VAL, bg=PALETTE["warn"], align="left")

    # Tax rate — editable cell at F6 (0-based: row 5, col 5)
    # Cell reference used in formulas: $F$6
    s.set(ROW_TAX_RATE, COL_META_LBL, "Tax Rate (%):")
    s.fmt(ROW_TAX_RATE, COL_META_LBL,
          bold=True, align="right", bg=PALETTE["band"])
    s.set(ROW_TAX_RATE, COL_META_VAL, 20)   # default 20 %
    s.fmt(ROW_TAX_RATE, COL_META_VAL,
          bg=PALETTE["warn"], align="center", number_format="0.00")

    s.note(ROW_TAX_RATE, COL_META_VAL,
           "Edit this cell to change the tax rate (%). "
           "Tax and Grand Total update automatically.",
           kind="note")

    s.box(ROW_INV_NUM, COL_META_LBL, ROW_TAX_RATE, COL_META_VAL,
          color=PALETTE["header"], width=1.2)

    # ── Separator row ────────────────────────────────────────────────
    s.fmt_range(8, 0, 8, 5, bg=PALETTE["header"])

    # ── Line-items table ─────────────────────────────────────────────
    # TABLE_START = 9  (0-based)
    # Header at 0-based row 9  → sheet row 10 (1-based)
    # First data row at 0-based row 10 → sheet row 11 (1-based)
    # So data row k (0-based from TABLE_START+1) has 1-based ref:
    #   TABLE_START + 1 + k + 1  =  TABLE_START + 2 + k

    headers = ["Description", "Qty", "Unit Price", "Line Total"]

    rows = []
    for k in range(N_DATA):
        # 1-based sheet row of this data row:
        sheet_row = TABLE_START + 2 + k   # = 11, 12, … for k=0,1,…

        B = col_letter(COL_QTY)    # "B"
        C = col_letter(COL_UNIT)   # "C"

        if k < N_ITEMS:
            desc, qty, unit = LINE_ITEMS[k]
            line_total_formula = f"={B}{sheet_row}*{C}{sheet_row}"
            rows.append([desc, qty, unit, line_total_formula])
        else:
            # Blank rows for user — Line Total only fires when Qty & Unit filled
            line_total_formula = f"={B}{sheet_row}*{C}{sheet_row}"
            rows.append(["", "", "", line_total_formula])

    s.table(TABLE_START, 0,
            headers=headers,
            rows=rows,
            banded=True)

    # Override number formats: Qty integer, Unit Price & Line Total currency
    # Data rows span from (TABLE_START+1) to (TABLE_START+N_DATA) 0-based
    for k in range(N_DATA):
        r = TABLE_START + 1 + k
        s.fmt(r, COL_QTY,   align="center", number_format="0")
        s.fmt(r, COL_UNIT,  align="right",  number_format=CUR)
        s.fmt(r, COL_TOTAL, align="right",  number_format=CUR)

    # ── Notes ────────────────────────────────────────────────────────
    s.note(TABLE_START + 1, COL_DESC,
           "Add or edit line items below. "
           "Line Total = Qty × Unit Price (live formula).",
           kind="note")
    s.note(TABLE_START + 1, COL_TOTAL,
           "Edit Qty or Unit Price — this column recalculates instantly.",
           kind="note")

    # ── Totals panel ─────────────────────────────────────────────────
    # Data rows live at 0-based rows TABLE_START+1 .. TABLE_START+N_DATA
    # Their 1-based sheet rows: (TABLE_START+2) .. (TABLE_START+1+N_DATA)
    first_data_sheet_row = TABLE_START + 2
    last_data_sheet_row  = TABLE_START + 1 + N_DATA

    D = col_letter(COL_TOTAL)   # "D"
    F = col_letter(COL_META_VAL)  # "F"

    subtotal_ref = f"D{ROW_SUBTOTAL + 1}"   # 1-based ref to subtotal cell
    tax_ref      = f"D{ROW_TAX + 1}"
    grand_ref    = f"D{ROW_GRAND + 1}"
    tax_rate_ref = f"$F$6"                  # absolute ref to tax-rate cell

    subtotal_formula = f"=SUM({D}{first_data_sheet_row}:{D}{last_data_sheet_row})"
    tax_formula      = f"={subtotal_ref}*{tax_rate_ref}/100"
    grand_formula    = f"={subtotal_ref}+{tax_ref}"

    totals = [
        (ROW_SUBTOTAL, "Subtotal",   subtotal_formula, PALETTE["band"]),
        (ROW_TAX,      "Tax",        tax_formula,      PALETTE["warn"]),
        (ROW_GRAND,    "TOTAL DUE",  grand_formula,    PALETTE["accent"]),
    ]

    for row, lbl, expr, bg in totals:
        # Label spans cols A-C (merged)
        s.set(row, 0, lbl)
        s.merge(row, 0, 1, 3)
        if lbl == "TOTAL DUE":
            s.fmt(row, 0, bold=True, font_size=13,
                  bg=bg, font_color="#ffffff", align="right")
        else:
            s.fmt(row, 0, bold=True, bg=bg, align="right")

        # Value in col D
        s.formula(row, COL_TOTAL, expr)
        if lbl == "TOTAL DUE":
            s.fmt(row, COL_TOTAL, bold=True, font_size=13,
                  bg=bg, font_color="#ffffff", align="right",
                  number_format=CUR)
        else:
            s.fmt(row, COL_TOTAL, bold=True, bg=bg,
                  align="right", number_format=CUR)

    # Box around the totals panel
    s.box(ROW_SUBTOTAL, 0, ROW_GRAND, COL_TOTAL,
          color=PALETTE["header"], width=1.5)
    # Inner horizontal borders between subtotal / tax / grand
    s.box(ROW_SUBTOTAL, 0, ROW_SUBTOTAL, COL_TOTAL,
          color=PALETTE["header"], width=1.0)
    s.box(ROW_TAX, 0, ROW_TAX, COL_TOTAL,
          color=PALETTE["header"], width=1.0)

    # ── Footer notes ─────────────────────────────────────────────────
    footer_row = ROW_GRAND + 2
    s.set(footer_row, 0,
          "Payment terms: 30 days net.  "
          "Please include the Invoice # on your remittance.")
    s.fmt(footer_row, 0, italic=True, font_color="#777777", align="left")
    s.merge(footer_row, 0, 1, 6)

    thank_row = footer_row + 1
    s.set(thank_row, 0, "Thank you for your business!")
    s.fmt(thank_row, 0,
          bold=True, font_color=PALETTE["accent"],
          align="center", font_size=13)
    s.merge(thank_row, 0, 1, 6)

    s.note(ROW_FROM_NAME, 0,
           "Fill in your company details here (name, address, email).",
           kind="note")

    # ── Save ─────────────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Finance",
    )
    out = os.path.join(out_dir, "Invoice Template.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
