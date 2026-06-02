"""Build the "Electricity Bill" Finance template .ksheet file.

A monthly electricity bill tracker with a live unit-rate input, formula-
driven energy costs, standing charge, and monthly totals for all 12
months.  A bar chart of monthly cost updates whenever the unit rate or
standing charge inputs are edited.

Run:  python examples/build_tpl_electricity_bill.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import numpy as np
from ksheet_author import Workbook, Series, PALETTE

# Typical UK domestic electricity figures (2024 Ofgem price cap).
UNIT_RATE_P   = 24.50   # pence per kWh
STANDING_P    = 61.64   # pence per day (quarterly standing charge)
DAYS_PER_MONTH = 30.4   # average days per month

MONTHS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December",
]

# Realistic UK seasonal consumption data (kWh per month).
UNITS_KWH = [
    410, 360, 320, 260, 200, 170,
    160, 165, 210, 290, 355, 405,
]


def build() -> str:
    wb = Workbook(min_rows=45, min_cols=14)
    s = wb.add_sheet("Electricity Bill")

    # ── Column widths ────────────────────────────────────────────────
    s.col_width(0, 130)   # Month label
    s.col_width(1, 130)   # Units used (kWh)
    s.col_width(2, 130)   # Energy cost (£)
    s.col_width(3, 140)   # Standing charge (£)
    s.col_width(4, 120)   # Total (£)
    s.col_width(6, 160)   # Summary label
    s.col_width(7, 120)   # Summary value

    # ── Title block ──────────────────────────────────────────────────
    s.title_block(
        "Electricity Bill Tracker",
        "Monthly energy costs — edit the unit rate or standing charge "
        "to see all values update instantly",
        span=8,
    )

    # ── Inputs panel ─────────────────────────────────────────────────
    # 0-based rows: inputs at rows 3–5; sheet cells B4, B5, B6.
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    s.set(4, 0, "Unit rate (p/kWh)")
    s.set(4, 1, UNIT_RATE_P)
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.set(5, 0, "Standing charge (p/day)")
    s.set(5, 1, STANDING_P)
    s.fmt(5, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.set(6, 0, "Avg days per month")
    s.set(6, 1, DAYS_PER_MONTH)
    s.fmt(6, 1, bg=PALETTE["warn"], align="center", number_format="0.0")

    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.5)

    # Notes explaining editable inputs.
    s.note(4, 1,
           "Edit this cell — unit rate in pence per kWh.\n"
           "All energy cost cells update automatically.",
           kind="note")
    s.note(5, 1,
           "Standing charge in pence per day (from your tariff).\n"
           "The standing-charge column recomputes on change.",
           kind="note")

    # ── Monthly data table ───────────────────────────────────────────
    # table() places header at sheet row (table_start + 1).
    # First data row is sheet row (table_start + 2).
    # table_start = 8  →  header at sheet row 9  →  data rows 10..21
    # (0-based data rows 9..20).
    TABLE_START = 8

    headers = [
        "Month",
        "Units Used (kWh)",
        "Energy Cost (£)",
        "Standing Charge (£)",
        "Total (£)",
    ]

    # Build the 12-row data list.
    # Sheet row for data row k: TABLE_START + 2 + k  (1-based).
    rows = []
    for k, (month, kwh) in enumerate(zip(MONTHS, UNITS_KWH)):
        sr = TABLE_START + 2 + k   # 1-based sheet row for formulas
        col_b = f"B{sr}"           # Units used (kWh) — editable literal
        rows.append([
            month,
            kwh,                                    # literal kWh (editable)
            f"={col_b}*$B$5/100",                   # energy cost £
            f"=$B$6*$B$7/100",                      # standing charge £
            f"=C{sr}+D{sr}",                        # total £
        ])

    s.set(7, 0, "Monthly Consumption")
    s.fmt(7, 0, bold=True, font_color=PALETTE["header"])

    s.table(
        TABLE_START, 0,
        headers=headers,
        rows=rows,
        number_format="0.00",
        banded=True,
    )

    # Override column 0 alignment to left (table() already does this,
    # but reinforce it for the Month names).
    for k in range(12):
        s.fmt(TABLE_START + 1 + k, 0, align="left")

    # Designate columns so the chart knows X vs Y.
    s.designate(0, "X")   # Month (category)
    s.designate(4, "Y")   # Total cost

    # ── Summary panel ────────────────────────────────────────────────
    # Data spans sheet rows 10..21 (1-based).
    FIRST_SR = TABLE_START + 2          # = 10  (1-based)
    LAST_SR  = TABLE_START + 1 + 12    # = 21  (1-based)

    SUMM_ROW = TABLE_START + 1 + 12 + 2   # two blank rows below table (0-based)
    # That is 0-based row 23 → sheet row 24.

    s.set(SUMM_ROW - 1, 0, "Annual Summary")
    s.fmt(SUMM_ROW - 1, 0, bold=True, font_color=PALETTE["header"])

    total_kwh_formula    = f"=SUM(B{FIRST_SR}:B{LAST_SR})"
    total_cost_formula   = f"=SUM(E{FIRST_SR}:E{LAST_SR})"
    avg_cost_formula     = f"=AVERAGE(E{FIRST_SR}:E{LAST_SR})"
    max_cost_formula     = f"=MAX(E{FIRST_SR}:E{LAST_SR})"
    max_kwh_formula      = f"=MAX(B{FIRST_SR}:B{LAST_SR})"
    standing_annual_formula = f"=SUM(D{FIRST_SR}:D{LAST_SR})"

    summary_items = [
        ("Total consumption (kWh)", total_kwh_formula,     PALETTE["band"],  "0.0"),
        ("Total energy cost (£)",   total_cost_formula,    PALETTE["good"],  "0.00"),
        ("Total standing charges (£)", standing_annual_formula, PALETTE["band"], "0.00"),
        ("Average monthly bill (£)", avg_cost_formula,     PALETTE["band"],  "0.00"),
        ("Highest monthly bill (£)", max_cost_formula,     PALETTE["bad"],   "0.00"),
        ("Highest usage (kWh)",      max_kwh_formula,      PALETTE["band"],  "0.0"),
    ]

    for i, (lbl, expr, fill, nfmt) in enumerate(summary_items):
        r = SUMM_ROW + i
        s.set(r, 0, lbl)
        s.formula(r, 1, expr)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=fill, align="center", number_format=nfmt, bold=True)

    s.box(SUMM_ROW, 0, SUMM_ROW + len(summary_items) - 1, 1,
          color=PALETTE["header"], width=1.5)

    # Note on summary.
    s.note(SUMM_ROW, 1,
           "All summary figures recompute when you change the unit rate,\n"
           "standing charge, or any monthly kWh value above.",
           kind="note")

    # ── Equation ─────────────────────────────────────────────────────
    # Monthly Total = (kWh × rate/100) + (standing × days/100)
    s.equation(
        r"C_{month} = \frac{kWh \times r_{p}}{100} + \frac{c_{s} \times d}{100}",
        at=(540, 340), fontsize=17,
        color="#222222", bg_color="#ffffff",
        border_color=PALETTE["header"], border_width=1.2,
        size=(370, 54),
    )

    # ── Bar chart — monthly total bill ───────────────────────────────
    # Data rows: 0-based rows TABLE_START+1 .. TABLE_START+12
    # i.e.  9 .. 20  (inclusive).
    r0 = TABLE_START + 1
    r1 = TABLE_START + 12

    # Initial render values match formula evaluation with default inputs.
    unit_rate_frac    = UNIT_RATE_P / 100.0
    standing_frac     = STANDING_P / 100.0
    days              = DAYS_PER_MONTH
    month_x           = np.arange(1, 13, dtype=float)  # 1..12
    energy_cost       = np.array(UNITS_KWH, dtype=float) * unit_rate_frac
    standing_cost     = np.full(12, standing_frac * days)
    total_cost        = energy_cost + standing_cost

    # Bar chart of total monthly cost — bound to column E (index 4).
    s.chart(
        [Series(
            month_x, total_cost,
            label="Total Bill (£)",
            plot_type="Bar",
            color=PALETTE["header"],
            y_col=4,     # column E (0-based)
            row_start=r0,
            row_end=r1,
        )],
        at=(530, 30), size=(440, 300),
        title="Monthly Electricity Bill",
        xlabel="Month (1 = Jan)",
        ylabel="Total Cost (£)",
        grid=True,
        legend=True,
    )

    # ── Save ─────────────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Finance",
    )
    out = os.path.join(out_dir, "Electricity Bill.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
