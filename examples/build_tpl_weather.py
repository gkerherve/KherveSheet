"""Build the "Weather Data" Daily Life template .ksheet.

A polished, fully live daily weather log workbook for 21 days:
  - Title block and editable introduction note
  - Daily table: Date | High (°C) | Low (°C) | Mean = (High+Low)/2
    | Rainfall (mm) | Condition (editable dropdown)
  - All Mean cells are live formulas referencing their row's High/Low
  - Summary panel: Average High, Average Low, Average Mean, Max High,
    Min Low, Total Rainfall — all live AVERAGE/MAX/MIN/SUM formulas
  - Line chart of High and Low temperatures (two live-bound series)
  - Bar chart of daily Rainfall (one live-bound series)
  - LaTeX equation for mean temperature
  - Instructive sticky notes

Run:  python examples/build_tpl_weather.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Sample weather data (21 days) ─────────────────────────────────────
# These literal values seed the editable input cells.
# The Mean column is always a formula, never a literal.

DATES = [
    "01 Jul", "02 Jul", "03 Jul", "04 Jul", "05 Jul",
    "06 Jul", "07 Jul", "08 Jul", "09 Jul", "10 Jul",
    "11 Jul", "12 Jul", "13 Jul", "14 Jul", "15 Jul",
    "16 Jul", "17 Jul", "18 Jul", "19 Jul", "20 Jul",
    "21 Jul",
]

HIGHS = [24.2, 26.1, 27.5, 25.8, 23.4,
         22.1, 28.3, 30.0, 29.6, 27.8,
         26.4, 24.9, 23.7, 22.5, 25.0,
         27.2, 28.8, 29.3, 26.7, 24.5,
         23.1]

LOWS  = [14.5, 15.2, 16.8, 15.0, 13.2,
         12.8, 17.1, 18.5, 18.9, 17.3,
         16.0, 14.7, 13.5, 12.2, 14.8,
         16.5, 17.8, 18.0, 16.2, 14.0,
         12.5]

RAINFALL = [0.0, 0.0, 2.4, 8.1, 12.3,
            5.6, 0.0, 0.0, 0.0, 1.2,
            0.0, 3.8, 6.5, 9.2, 0.0,
            0.0, 0.0, 0.4, 2.1, 4.7,
            7.0]

CONDITIONS = [
    "Sunny", "Sunny", "Partly Cloudy", "Rainy", "Heavy Rain",
    "Cloudy", "Sunny", "Sunny", "Sunny", "Partly Cloudy",
    "Sunny", "Cloudy", "Rainy", "Rainy", "Sunny",
    "Sunny", "Sunny", "Partly Cloudy", "Cloudy", "Rainy",
    "Rainy",
]

CONDITION_OPTIONS = ["Sunny", "Partly Cloudy", "Cloudy", "Rainy",
                     "Heavy Rain", "Stormy", "Foggy", "Windy"]

N_DAYS = len(DATES)

# Column layout (0-based)
COL_DATE      = 0   # A  Date (literal, editable)
COL_HIGH      = 1   # B  High °C (literal, editable)
COL_LOW       = 2   # C  Low °C  (literal, editable)
COL_MEAN      = 3   # D  Mean °C (FORMULA)
COL_RAIN      = 4   # E  Rainfall mm (literal, editable)
COL_COND      = 5   # F  Condition (text, editable)

# Table starts at row 3 (0-based); header at row 3; first data row at row 4.
TABLE_START    = 3
DATA_ROW_FIRST = TABLE_START + 1          # 0-based
DATA_ROW_LAST  = DATA_ROW_FIRST + N_DAYS - 1  # 0-based inclusive

# 1-based sheet rows (for formula strings)
SR_FIRST = DATA_ROW_FIRST + 1   # = 5
SR_LAST  = DATA_ROW_LAST  + 1   # = 25

# Summary panel: right side, starting at column 8 (I)
COL_SUM_L = 8    # I — label
COL_SUM_V = 9    # J — value

# Chart placement
CHART_TEMP_X = 720
CHART_TEMP_Y = 30
CHART_TEMP_W = 480
CHART_TEMP_H = 300

CHART_RAIN_X = 720
CHART_RAIN_Y = 350
CHART_RAIN_W = 480
CHART_RAIN_H = 270


def col_letter(c: int) -> str:
    """0-based column index → spreadsheet letter (A…Z, AA…)."""
    letters = ""
    c += 1
    while c > 0:
        c, rem = divmod(c - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Weather Data")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(COL_DATE, 90)
    s.col_width(COL_HIGH, 80)
    s.col_width(COL_LOW,  80)
    s.col_width(COL_MEAN, 80)
    s.col_width(COL_RAIN, 90)
    s.col_width(COL_COND, 120)
    s.col_width(6, 40)           # G — spacer
    s.col_width(COL_SUM_L, 170)
    s.col_width(COL_SUM_V, 90)

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Daily Weather Log",
        "Record and analyse daily temperature and rainfall — "
        "edit the highlighted cells to enter your own data",
        row=0, col=0, span=7,
    )
    s.note(0, 0,
           "TEMPLATE: Edit the Date, High, Low, Rainfall and Condition "
           "columns (rows 5–25). Mean temperature, all summaries and "
           "both charts update automatically.",
           kind="note")

    # ── Table ─────────────────────────────────────────────────────────
    # Build the rows list for table().  Mean is a formula string.
    rows = []
    for k in range(N_DAYS):
        sr = SR_FIRST + k          # 1-based sheet row of this data row
        rows.append([
            DATES[k],              # A: Date (literal)
            HIGHS[k],              # B: High °C (literal)
            LOWS[k],               # C: Low °C  (literal)
            f"=(B{sr}+C{sr})/2",   # D: Mean (formula)
            RAINFALL[k],           # E: Rainfall mm (literal)
            CONDITIONS[k],         # F: Condition (literal text)
        ])

    s.table(
        TABLE_START, COL_DATE,
        headers=["Date", "High (°C)", "Low (°C)",
                 "Mean (°C)", "Rainfall (mm)", "Condition"],
        rows=rows,
        number_format="0.0",
        banded=True,
    )

    # Override: Date and Condition columns should be left-aligned text
    for k in range(N_DAYS):
        r = DATA_ROW_FIRST + k
        s.fmt(r, COL_DATE, align="left", number_format="")
        s.fmt(r, COL_COND, align="left", number_format="")

    # Dropdowns for Condition column
    for k in range(N_DAYS):
        r = DATA_ROW_FIRST + k
        s.dropdown(r, COL_COND, CONDITION_OPTIONS)

    # Highlight editable numeric columns (High, Low, Rainfall) in warm amber
    for k in range(N_DAYS):
        r = DATA_ROW_FIRST + k
        s.fmt(r, COL_HIGH, bg=PALETTE["warn"])
        s.fmt(r, COL_LOW,  bg=PALETTE["warn"])
        s.fmt(r, COL_RAIN, bg=PALETTE["warn"])

    # ── Input hints ───────────────────────────────────────────────────
    s.note(DATA_ROW_FIRST, COL_HIGH,
           "Edit High and Low temperatures (°C). "
           "Mean column recalculates automatically.",
           kind="note")
    s.note(DATA_ROW_FIRST, COL_RAIN,
           "Enter daily rainfall in millimetres. "
           "Total Rainfall in the summary panel updates live.",
           kind="note")

    # Designate for chart binding
    s.designate(COL_HIGH, "Y")
    s.designate(COL_LOW,  "Y")
    s.designate(COL_RAIN, "Y")

    # ── Summary panel ─────────────────────────────────────────────────
    s.set(TABLE_START, COL_SUM_L, "Summary")
    s.fmt(TABLE_START, COL_SUM_L,
          bold=True, font_size=12, font_color=PALETTE["header"])
    s.merge(TABLE_START, COL_SUM_L, 1, 2)

    B_RANGE = f"B{SR_FIRST}:B{SR_LAST}"
    C_RANGE = f"C{SR_FIRST}:C{SR_LAST}"
    D_RANGE = f"D{SR_FIRST}:D{SR_LAST}"
    E_RANGE = f"E{SR_FIRST}:E{SR_LAST}"

    summary_items = [
        ("Average High (°C)",   f"=AVERAGE({B_RANGE})", PALETTE["bad"],   "0.0"),
        ("Average Low (°C)",    f"=AVERAGE({C_RANGE})", PALETTE["band"],   "0.0"),
        ("Average Mean (°C)",   f"=AVERAGE({D_RANGE})", PALETTE["band_alt"], "0.0"),
        ("Max High (°C)",       f"=MAX({B_RANGE})",     PALETTE["bad"],   "0.0"),
        ("Min Low (°C)",        f"=MIN({C_RANGE})",     PALETTE["good"],  "0.0"),
        ("Total Rainfall (mm)", f"=SUM({E_RANGE})",     PALETTE["header"],"0.0"),
    ]

    for i, (lbl, expr, bg, nf) in enumerate(summary_items):
        r = TABLE_START + 1 + i
        s.set(r, COL_SUM_L, lbl)
        s.fmt(r, COL_SUM_L, align="left")
        s.formula(r, COL_SUM_V, expr)
        fc = "#ffffff" if bg == PALETTE["header"] else "#000000"
        s.fmt(r, COL_SUM_V, bold=True, bg=bg, align="right",
              number_format=nf, font_color=fc)

    s.box(TABLE_START + 1, COL_SUM_L,
          TABLE_START + len(summary_items), COL_SUM_V,
          color=PALETTE["header"], width=1.2)

    s.note(TABLE_START + 1, COL_SUM_L,
           "All summary values update automatically when you "
           "edit any High, Low, or Rainfall cell.",
           kind="note")

    # ── Temperature Line chart (High + Low, data-bound) ───────────────
    # X axis: day index 0..20  (no x_col — row-index X)
    # Y cols: COL_HIGH (1) and COL_LOW (2)
    # Rows: DATA_ROW_FIRST .. DATA_ROW_LAST  (0-based inclusive)
    highs_np = np.array(HIGHS, dtype=float)
    lows_np  = np.array(LOWS,  dtype=float)
    day_idx  = np.arange(N_DAYS, dtype=float)

    s.chart(
        [
            Series(
                x=day_idx, y=highs_np,
                label="High (°C)",
                plot_type="Line+Symbol",
                color="#c0392b",
                linewidth=2.0,
                marker="o", markersize=4.0,
                y_col=COL_HIGH,
                row_start=DATA_ROW_FIRST,
                row_end=DATA_ROW_LAST,
            ),
            Series(
                x=day_idx, y=lows_np,
                label="Low (°C)",
                plot_type="Line+Symbol",
                color="#2980b9",
                linewidth=2.0,
                marker="o", markersize=4.0,
                y_col=COL_LOW,
                row_start=DATA_ROW_FIRST,
                row_end=DATA_ROW_LAST,
            ),
        ],
        at=(CHART_TEMP_X, CHART_TEMP_Y),
        size=(CHART_TEMP_W, CHART_TEMP_H),
        title="Daily High & Low Temperatures",
        xlabel="Day",
        ylabel="Temperature (°C)",
        grid=True,
        legend=True,
    )

    # ── Rainfall Bar chart (data-bound) ──────────────────────────────
    rain_np = np.array(RAINFALL, dtype=float)

    s.chart(
        [
            Series(
                x=day_idx, y=rain_np,
                label="Rainfall (mm)",
                plot_type="Bar",
                color="#2980b9",
                y_col=COL_RAIN,
                row_start=DATA_ROW_FIRST,
                row_end=DATA_ROW_LAST,
            ),
        ],
        at=(CHART_RAIN_X, CHART_RAIN_Y),
        size=(CHART_RAIN_W, CHART_RAIN_H),
        title="Daily Rainfall",
        xlabel="Day",
        ylabel="Rainfall (mm)",
        grid=True,
        legend=False,
    )

    # ── LaTeX equation ─────────────────────────────────────────────────
    s.equation(
        r"\bar{T} = \frac{T_{high} + T_{low}}{2}",
        at=(CHART_TEMP_X, CHART_TEMP_Y + CHART_TEMP_H + 10),
        fontsize=18,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(340, 52),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Daily Life", "Weather Data.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    path = build()
    print(f"Saved: {path}")
