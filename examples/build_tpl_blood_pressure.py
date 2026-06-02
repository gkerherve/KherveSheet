"""Build the "Blood Pressure Log" template .ksheet file.

A daily-life health tracker that records blood pressure and pulse readings
and classifies them according to the ACC/AHA 2017 guidelines:

  Systolic < 120  AND  Diastolic < 80              → Normal
  Systolic 120-129 AND  Diastolic < 80              → Elevated
  Systolic 130-139 OR   Diastolic 80-89             → Stage 1
  Systolic >= 140  OR   Diastolic >= 90             → Stage 2

Features
--------
* Title block + subtitle
* Editable log table: Date | Time | Systolic | Diastolic | Pulse | Category | Notes
  (15 sample rows; category column = live nested-IF formula)
* Summary panel: AVERAGE / MAX / MIN for systolic, diastolic, pulse
* Live-bound LINE chart: systolic + diastolic over readings
* LaTeX equation for MAP (mean arterial pressure)
* 3 instructive yellow sticky notes

Run:  python examples/build_tpl_blood_pressure.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Make repo importable when run from anywhere.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Sample data (15 readings) ─────────────────────────────────────────
# Each row: (date_str, time_str, systolic, diastolic, pulse, notes)
READINGS = [
    ("2026-06-01", "07:30", 118, 76, 68, "Morning, before coffee"),
    ("2026-06-01", "19:45", 122, 78, 72, "Evening after walk"),
    ("2026-06-02", "07:20", 125, 79, 70, ""),
    ("2026-06-02", "12:15", 128, 81, 75, "Post lunch"),
    ("2026-06-03", "07:35", 132, 84, 74, "Slightly elevated"),
    ("2026-06-03", "20:00", 135, 86, 78, "Stressful day"),
    ("2026-06-04", "07:25", 119, 77, 67, ""),
    ("2026-06-04", "19:50", 121, 79, 71, ""),
    ("2026-06-05", "07:40", 141, 91, 82, "High — rest and monitor"),
    ("2026-06-05", "20:10", 138, 89, 80, ""),
    ("2026-06-06", "07:30", 126, 80, 73, ""),
    ("2026-06-06", "19:55", 129, 82, 76, ""),
    ("2026-06-07", "07:20", 117, 75, 65, "After 8 h sleep"),
    ("2026-06-07", "12:30", 120, 78, 69, ""),
    ("2026-06-07", "20:05", 124, 80, 72, ""),
]

N = len(READINGS)  # 15


def _category(sys_val, dia_val):
    """Python copy of the formula logic — used only for chart render data."""
    if sys_val >= 140 or dia_val >= 90:
        return "Stage 2"
    if sys_val >= 130 or dia_val >= 80:
        return "Stage 1"
    if sys_val >= 120 and dia_val < 80:
        return "Elevated"
    return "Normal"


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=16)
    s = wb.add_sheet("BP Log")

    # ── Column layout ────────────────────────────────────────────────
    # col 0: #  (reading index)
    # col 1: Date
    # col 2: Time
    # col 3: Systolic (mmHg)
    # col 4: Diastolic (mmHg)
    # col 5: Pulse (bpm)
    # col 6: Category (formula)
    # col 7: Notes (text)
    # col 9-10: Summary labels / values

    s.col_width(0, 45)   # #
    s.col_width(1, 100)  # Date
    s.col_width(2, 70)   # Time
    s.col_width(3, 95)   # Systolic
    s.col_width(4, 95)   # Diastolic
    s.col_width(5, 75)   # Pulse
    s.col_width(6, 110)  # Category
    s.col_width(7, 200)  # Notes
    s.col_width(8, 20)   # spacer
    s.col_width(9, 160)  # Summary label
    s.col_width(10, 100) # Summary value

    # ── Title ────────────────────────────────────────────────────────
    s.title_block(
        "Blood Pressure Log",
        "Daily readings tracker — ACC/AHA 2017 classification",
        row=0, col=0, span=8,
    )

    # ── Reference guide (cols 9-10, rows 0-5) ───────────────────────
    s.set(0, 9, "ACC/AHA Classification")
    s.fmt(0, 9, bold=True, font_size=11, font_color=PALETTE["header"])
    s.merge(0, 9, 1, 2)

    guide = [
        ("Normal",   "SYS < 120  AND  DIA < 80",  PALETTE["good"]),
        ("Elevated",  "SYS 120-129 AND DIA < 80",  PALETTE["warn"]),
        ("Stage 1",   "SYS 130-139 OR  DIA 80-89", "#ffd966"),
        ("Stage 2",   "SYS ≥ 140   OR  DIA ≥ 90",  PALETTE["bad"]),
    ]
    for i, (cat, criteria, col) in enumerate(guide):
        r = 1 + i
        s.set(r, 9, cat)
        s.set(r, 10, criteria)
        s.fmt(r, 9, bold=True, bg=col, align="center")
        s.fmt(r, 10, bg=col, align="left", font_size=9)
    s.box(1, 9, 4, 10, color=PALETTE["header"], width=1.2)

    # ── Log table ────────────────────────────────────────────────────
    # table() header is at sheet row (TABLE_START + 1) [1-based],
    # first data row is at sheet row (TABLE_START + 2) [1-based].
    TABLE_START = 3   # 0-based row for the header row
    # first data row 0-based = TABLE_START + 1 = 4
    # sheet row (1-based) of first data row = TABLE_START + 2 = 5

    headers = ["#", "Date", "Time", "Systolic (mmHg)",
               "Diastolic (mmHg)", "Pulse (bpm)", "Category", "Notes"]

    rows = []
    for k, (date, time, sys_v, dia_v, pulse, notes) in enumerate(READINGS):
        # 1-based sheet row of this data row
        rr = TABLE_START + 2 + k   # = 5, 6, 7, …
        # Designate D col (col 3, "D") = Systolic, E col (col 4) = Diastolic
        # Nested IF classification formula (uses == not <>):
        # Stage 2: sys>=140 OR dia>=90
        # Stage 1: sys>=130 OR dia>=80
        # Elevated: sys>=120 (sys<130 implied from ordering) AND dia<80
        # Normal: otherwise
        cat_formula = (
            f"=IF(D{rr}>=140,\"Stage 2\","
            f"IF(E{rr}>=90,\"Stage 2\","
            f"IF(D{rr}>=130,\"Stage 1\","
            f"IF(E{rr}>=80,\"Stage 1\","
            f"IF(D{rr}>=120,\"Elevated\",\"Normal\")))))"
        )
        rows.append([
            k + 1,       # reading number (literal independent index)
            date,        # literal date string
            time,        # literal time string
            sys_v,       # editable systolic
            dia_v,       # editable diastolic
            pulse,       # editable pulse
            cat_formula, # live category
            notes,       # notes text
        ])

    s.table(TABLE_START, 0,
            headers=headers,
            rows=rows,
            banded=True,
            align_data="center")

    # Override column alignments for better readability
    for k in range(N):
        r = TABLE_START + 1 + k
        s.fmt(r, 1, align="center")  # Date
        s.fmt(r, 2, align="center")  # Time
        s.fmt(r, 7, align="left")    # Notes

    # Colour the Category cells based on their content
    # (we apply to each data row based on sample data; on reload the formula
    #  re-runs and the colour follows the banding set by table(), which is
    #  fine — the formula text is what matters for live recalculation)
    CAT_COLORS = {
        "Normal":  PALETTE["good"],
        "Elevated": PALETTE["warn"],
        "Stage 1": "#ffd966",
        "Stage 2": PALETTE["bad"],
    }
    for k, (_, _, sys_v, dia_v, _, _) in enumerate(READINGS):
        cat = _category(sys_v, dia_v)
        r = TABLE_START + 1 + k
        s.fmt(r, 6, bg=CAT_COLORS[cat], bold=True, align="center")

    # Designate Systolic (col 3) as Y and Diastolic (col 4) as Y
    s.designate(3, "Y")
    s.designate(4, "Y")
    s.designate(0, "X")  # reading index as X axis

    # ── Summary panel ────────────────────────────────────────────────
    # Data range (1-based sheet rows): first=TABLE_START+2, last=TABLE_START+1+N
    FIRST_ROW_1 = TABLE_START + 2       # = 5
    LAST_ROW_1  = TABLE_START + 1 + N   # = 19

    SUMM_START_ROW = TABLE_START + N + 3   # 0-based, leave gap after table
    s.set(SUMM_START_ROW, 0, "Summary")
    s.fmt(SUMM_START_ROW, 0, bold=True, font_size=12,
          font_color=PALETTE["header"])
    s.merge(SUMM_START_ROW, 0, 1, 3)

    summary_items = [
        # (label, systolic formula, diastolic formula, pulse formula, fill)
        ("Average",
         f"=AVERAGE(D{FIRST_ROW_1}:D{LAST_ROW_1})",
         f"=AVERAGE(E{FIRST_ROW_1}:E{LAST_ROW_1})",
         f"=AVERAGE(F{FIRST_ROW_1}:F{LAST_ROW_1})",
         PALETTE["band"]),
        ("Maximum",
         f"=MAX(D{FIRST_ROW_1}:D{LAST_ROW_1})",
         f"=MAX(E{FIRST_ROW_1}:E{LAST_ROW_1})",
         f"=MAX(F{FIRST_ROW_1}:F{LAST_ROW_1})",
         PALETTE["bad"]),
        ("Minimum",
         f"=MIN(D{FIRST_ROW_1}:D{LAST_ROW_1})",
         f"=MIN(E{FIRST_ROW_1}:E{LAST_ROW_1})",
         f"=MIN(F{FIRST_ROW_1}:F{LAST_ROW_1})",
         PALETTE["good"]),
    ]

    # Sub-header row
    r_subhdr = SUMM_START_ROW + 1
    for j, hdr in enumerate(["Metric", "Systolic (mmHg)",
                              "Diastolic (mmHg)", "Pulse (bpm)"]):
        s.set(r_subhdr, j, hdr)
        s.fmt(r_subhdr, j, bold=True, bg=PALETTE["header"],
              font_color="#ffffff", align="center")

    for i, (lbl, sys_f, dia_f, pul_f, fill) in enumerate(summary_items):
        r = r_subhdr + 1 + i
        s.set(r, 0, lbl)
        s.formula(r, 1, sys_f)
        s.formula(r, 2, dia_f)
        s.formula(r, 3, pul_f)
        s.fmt(r, 0, bold=True, align="left", bg=fill)
        for c in range(1, 4):
            s.fmt(r, c, align="center", bg=fill, number_format="0.0")

    s.box(r_subhdr, 0, r_subhdr + len(summary_items), 3,
          color=PALETTE["header"], width=1.5)

    # ── Chart: Systolic + Diastolic over readings ────────────────────
    # X: reading index column (col 0), Y: systolic (col 3), diastolic (col 4)
    # 0-based data rows: TABLE_START+1 .. TABLE_START+N
    row_start_0 = TABLE_START + 1   # 0-based inclusive
    row_end_0   = TABLE_START + N   # 0-based inclusive  (= TABLE_START+15)

    x_arr  = np.arange(1, N + 1, dtype=float)
    sys_arr = np.array([r[3] for r in READINGS], dtype=float)
    dia_arr = np.array([r[4] for r in READINGS], dtype=float)

    # ACC/AHA threshold lines baked into initial render data
    # (static horizontal reference — not live-bound)
    sys_series = Series(
        x_arr, sys_arr, "Systolic", "Line+Symbol",
        color="#c00000", linewidth=2.0, marker="o", markersize=5.0,
        x_col=0, y_col=3,
        row_start=row_start_0, row_end=row_end_0,
    )
    dia_series = Series(
        x_arr, dia_arr, "Diastolic", "Line+Symbol",
        color="#4472c4", linewidth=2.0, marker="s", markersize=5.0,
        x_col=0, y_col=4,
        row_start=row_start_0, row_end=row_end_0,
    )

    s.chart(
        [sys_series, dia_series],
        at=(560, 20), size=(450, 300),
        title="Blood Pressure Over Time",
        xlabel="Reading #", ylabel="Pressure (mmHg)",
        grid=True, legend=True,
    )

    # ── MAP equation (Mean Arterial Pressure) ────────────────────────
    # MAP = diastolic + 1/3 * (systolic - diastolic)
    s.equation(
        r"\mathrm{MAP} = P_{dia} + \frac{1}{3}(P_{sys} - P_{dia})",
        at=(560, 340), fontsize=17, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(320, 52),
    )

    # ── Sticky notes ─────────────────────────────────────────────────
    s.note(TABLE_START, 3,
           "Edit Systolic / Diastolic / Pulse values directly. "
           "The Category column and Summary recalculate instantly.",
           kind="note")
    s.note(TABLE_START, 6,
           "Category uses ACC/AHA 2017 thresholds: "
           "Stage 2 if SYS>=140 OR DIA>=90; Stage 1 if SYS>=130 OR DIA>=80; "
           "Elevated if SYS 120-129 AND DIA<80; Normal otherwise.",
           kind="note")
    s.note(SUMM_START_ROW, 0,
           "Summary recalculates over all 15 readings. "
           "Add more rows by copying the formula in column G.",
           kind="note")

    # ── Save ─────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Daily Life", "Blood Pressure Log.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
