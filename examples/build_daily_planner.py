"""Build the "Daily Planner" template .ksheet file.

A fillable daily planner template — not a data-analysis example.
The sheet contains:
  - Title block with editable Date and Day fields.
  - Hourly schedule table (06:00–21:00) with Priority dropdowns.
  - Top 3 Priorities boxed section.
  - To-Do List with Status dropdowns.
  - Progress summary: Total tasks (COUNTA formula), Done (editable),
    Remaining (formula), % Complete (formula), plus a bound bar chart.
  - Notes area.
  - Yellow sticky notes with usage tips.

Run:  python examples/build_daily_planner.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402

# ── Column layout ────────────────────────────────────────────────────
# A=0  B=1   C=2          D=3       E=4      F=5   G=6   H=7
# The planner uses columns A–G for content; H onward for breathing room.
COL_A = 0  # labels / time labels
COL_B = 1  # main content / task text
COL_C = 2  # secondary (priority / status)
COL_D = 3  # gap / progress labels
COL_E = 4  # progress values / chart area
COL_F = 5  # (chart overhang)
COL_G = 6

# Accent colour for this template (softer teal rather than the default blue)
TEAL = "#2e75b6"
TEAL_LIGHT = "#dce6f1"
ORANGE = PALETTE["accent"]


def build() -> str:
    wb = Workbook(min_rows=72, min_cols=10)
    s = wb.add_sheet("Daily Planner")

    # ── Column widths ────────────────────────────────────────────────
    s.col_width(COL_A, 90)    # Time / label
    s.col_width(COL_B, 260)   # Plan / Task text
    s.col_width(COL_C, 110)   # Priority / Status
    s.col_width(COL_D, 160)   # Progress labels
    s.col_width(COL_E, 100)   # Progress values
    s.col_width(COL_F, 30)    # narrow spacer
    s.col_width(COL_G, 30)

    # ════════════════════════════════════════════════════════════════
    # 1. TITLE BLOCK
    # ════════════════════════════════════════════════════════════════
    # Title at row 0 spanning cols A-E
    s.set(0, COL_A, "Daily Planner")
    s.fmt(0, COL_A, bold=True, font_size=22, font_color=TEAL)
    s.merge(0, COL_A, 1, 5)

    # Subtitle at row 1
    s.set(1, COL_A, "Plan your day, focus on priorities, track your progress")
    s.fmt(1, COL_A, italic=True, font_color="#555555", font_size=10)
    s.merge(1, COL_A, 1, 5)

    # Row 2 blank separator

    # ── Date / Day row ───────────────────────────────────────────────
    s.set(3, COL_A, "Date:")
    s.fmt(3, COL_A, bold=True, font_color=TEAL, align="right")
    # Literal date — user edits this
    s.set(3, COL_B, "2026-06-15")
    s.fmt(3, COL_B, bold=True, bg=PALETTE["warn"], align="center",
          font_size=11)
    s.merge(3, COL_B, 1, 1)

    s.set(3, COL_C, "Day:")
    s.fmt(3, COL_C, bold=True, font_color=TEAL, align="right")
    # Day name — literal, user edits to match their date
    s.set(3, COL_D, "Monday")
    s.fmt(3, COL_D, bold=True, bg=TEAL_LIGHT, align="center", font_size=11)

    s.note(3, COL_B,
           "Type your date here (YYYY-MM-DD). Update 'Day' in D4 "
           "to match the weekday.", kind="note")

    # Row 4 blank

    # ════════════════════════════════════════════════════════════════
    # 2. HOURLY SCHEDULE TABLE  (rows 5–22)
    #    header=5, data rows 6..22 (17 hours: 06:00..21:00 = 16 slots +1)
    # ════════════════════════════════════════════════════════════════
    SCHED_HEADER_ROW = 5
    hours = [f"{h:02d}:00" for h in range(6, 22)]  # 06:00 to 21:00 = 16 rows

    # Section label above table
    s.set(4, COL_A, "SCHEDULE")
    s.fmt(4, COL_A, bold=True, font_size=9, font_color="#888888")

    # Header row
    for col, label in [(COL_A, "Time"), (COL_B, "Plan / Appointment"),
                       (COL_C, "Priority")]:
        s.set(SCHED_HEADER_ROW, col, label)
        s.fmt(SCHED_HEADER_ROW, col, bold=True, bg=TEAL,
              font_color="#ffffff", align="center")

    # Data rows
    for i, hour in enumerate(hours):
        r = SCHED_HEADER_ROW + 1 + i
        band = TEAL_LIGHT if (i % 2 == 0) else "#f7fbff"

        # Time label
        s.set(r, COL_A, hour)
        s.fmt(r, COL_A, bold=True, align="center", bg=band,
              font_color=TEAL)

        # Plan cell (blank — user fills in)
        s.set(r, COL_B, "")
        s.fmt(r, COL_B, align="left", bg=band, wrap=True)

        # Priority dropdown
        s.set(r, COL_C, "")
        s.fmt(r, COL_C, align="center", bg=band)
        s.dropdown(r, COL_C, ["", "High", "Medium", "Low"])

    SCHED_LAST_ROW = SCHED_HEADER_ROW + len(hours)  # = 21

    # Box around the schedule table
    s.box(SCHED_HEADER_ROW, COL_A, SCHED_LAST_ROW, COL_C,
          color=TEAL, width=1.2)

    s.note(SCHED_HEADER_ROW, COL_C,
           "Click a cell in the Priority column and pick from the "
           "dropdown: High / Medium / Low.", kind="note")

    # Row 22 blank after schedule

    # ════════════════════════════════════════════════════════════════
    # 3. TOP 3 PRIORITIES  (rows 23–27)
    # ════════════════════════════════════════════════════════════════
    PRIO_START = 23

    s.set(PRIO_START, COL_A, "TOP 3 PRIORITIES")
    s.fmt(PRIO_START, COL_A, bold=True, bg=ORANGE,
          font_color="#ffffff", align="center", font_size=10)
    s.merge(PRIO_START, COL_A, 1, 3)

    for i, label in enumerate(["1.", "2.", "3."]):
        r = PRIO_START + 1 + i
        s.set(r, COL_A, label)
        s.fmt(r, COL_A, bold=True, align="center", font_color=ORANGE,
              bg="#fff8f3")
        s.set(r, COL_B, "")
        s.fmt(r, COL_B, align="left", bg="#fff8f3", wrap=True)
        s.merge(r, COL_B, 1, 2)

    PRIO_LAST = PRIO_START + 3
    s.box(PRIO_START, COL_A, PRIO_LAST, COL_C,
          color=ORANGE, width=1.2)

    s.note(PRIO_START, COL_A,
           "List the three most important things to accomplish today. "
           "Focus here first.", kind="note")

    # Row 27 blank

    # ════════════════════════════════════════════════════════════════
    # 4. TO-DO LIST  (rows 28–39)
    #    header=28, 10 data rows 29..38, blank+summary rows 39..40
    # ════════════════════════════════════════════════════════════════
    TODO_HEADER_ROW = 28
    TODO_N = 10  # number of task rows

    s.set(27, COL_A, "TO-DO LIST")
    s.fmt(27, COL_A, bold=True, font_size=9, font_color="#888888")

    # Header
    for col, label in [(COL_A, "#"), (COL_B, "Task"),
                       (COL_C, "Status")]:
        s.set(TODO_HEADER_ROW, col, label)
        s.fmt(TODO_HEADER_ROW, col, bold=True, bg=TEAL,
              font_color="#ffffff", align="center")

    # Task rows
    for i in range(TODO_N):
        r = TODO_HEADER_ROW + 1 + i
        band = TEAL_LIGHT if (i % 2 == 0) else "#f7fbff"

        # Row number
        s.set(r, COL_A, str(i + 1))
        s.fmt(r, COL_A, align="center", bg=band,
              font_color="#888888", bold=True)

        # Task cell (blank)
        s.set(r, COL_B, "")
        s.fmt(r, COL_B, align="left", bg=band, wrap=True)

        # Status dropdown
        s.set(r, COL_C, "")
        s.fmt(r, COL_C, align="center", bg=band)
        s.dropdown(r, COL_C, ["", "To do", "In progress", "Done"])

    TODO_LAST_DATA = TODO_HEADER_ROW + TODO_N  # last data row = 38

    s.box(TODO_HEADER_ROW, COL_A, TODO_LAST_DATA, COL_C,
          color=TEAL, width=1.2)

    s.note(TODO_HEADER_ROW, COL_C,
           "Set status via dropdown: 'To do', 'In progress', or 'Done'. "
           "Update the Done count in the Progress section below.", kind="note")

    # ════════════════════════════════════════════════════════════════
    # 5. PROGRESS SUMMARY  (rows 40–44)
    #    Column D = labels, Column E = values (all in sheet rows 41–45)
    #
    #    Total (editable) — user enters how many tasks they planned.
    #    Done  (editable) — user enters how many tasks they completed.
    #    Remaining = Total - Done   [FORMULA, live]
    #    % Complete = Done / MAX(Total, 1) * 100  [FORMULA, live]
    #
    #    Note: COUNTA/COUNTIF on text cells is not supported by the
    #    engine (it filters text from ranges), so Total and Done are
    #    left as editable inputs; only Remaining and % Complete are
    #    live formulas.
    #
    #    0-based rows:
    #      PROG_START+0 = section label  (row 40)
    #      PROG_START+1 = Total           (row 41) → sheet row 42 → E42
    #      PROG_START+2 = Done            (row 42) → sheet row 43 → E43
    #      PROG_START+3 = Remaining       (row 43) → sheet row 44 → E44
    #      PROG_START+4 = % Complete      (row 44) → sheet row 45 → E45
    # ════════════════════════════════════════════════════════════════

    PROG_START = 40  # 0-based row for section label

    s.set(PROG_START, COL_A, "PROGRESS")
    s.fmt(PROG_START, COL_A, bold=True, font_size=9, font_color="#888888")
    s.merge(PROG_START, COL_A, 1, 2)

    # Row 41 (0-based): Total tasks — editable input
    # Sheet row 42, col E → "E42"
    total_ref = f"E{PROG_START + 2}"   # 1-based = PROG_START+1 +1 = 42
    s.set(PROG_START + 1, COL_D, "Total Tasks")
    s.fmt(PROG_START + 1, COL_D, bold=True, align="right",
          font_color=TEAL)
    s.set(PROG_START + 1, COL_E, "10")   # default: 10 tasks planned
    s.fmt(PROG_START + 1, COL_E, bold=True, align="center",
          bg=TEAL_LIGHT, number_format="0")

    # Row 42 (0-based): Done — editable input
    # Sheet row 43, col E → "E43"
    done_ref = f"E{PROG_START + 3}"    # 1-based = PROG_START+2 +1 = 43
    s.set(PROG_START + 2, COL_D, "Done")
    s.fmt(PROG_START + 2, COL_D, bold=True, align="right",
          font_color="#217346")
    s.set(PROG_START + 2, COL_E, "0")
    s.fmt(PROG_START + 2, COL_E, bold=True, align="center",
          bg=PALETTE["good"], number_format="0")

    # Row 43 (0-based): Remaining = Total - Done   [FORMULA]
    s.set(PROG_START + 3, COL_D, "Remaining")
    s.fmt(PROG_START + 3, COL_D, bold=True, align="right",
          font_color=ORANGE)
    s.formula(PROG_START + 3, COL_E, f"={total_ref}-{done_ref}")
    s.fmt(PROG_START + 3, COL_E, bold=True, align="center",
          bg=PALETTE["warn"], number_format="0")

    # Row 44 (0-based): % Complete = Done / MAX(Total, 1) * 100   [FORMULA]
    s.set(PROG_START + 4, COL_D, "% Complete")
    s.fmt(PROG_START + 4, COL_D, bold=True, align="right",
          font_color=TEAL)
    s.formula(PROG_START + 4, COL_E,
              f"={done_ref}/MAX({total_ref},1)*100")
    s.fmt(PROG_START + 4, COL_E, bold=True, align="center",
          bg=TEAL_LIGHT, number_format="0.0")

    PROG_LAST = PROG_START + 4
    s.box(PROG_START + 1, COL_D, PROG_LAST, COL_E,
          color=TEAL, width=1.2)

    s.note(PROG_START + 1, COL_E,
           "Edit 'Total Tasks' and 'Done'. "
           "Remaining and % Complete update automatically.", kind="note")

    # ── Progress bar chart ────────────────────────────────────────
    # Bind to the Done (row PROG_START+2) and Remaining (row PROG_START+3)
    # values in column E (COL_E = 4).
    # For a 2-bar chart we need x = category labels and y = values.
    # Use a Bar chart with two series: Done and Remaining,
    # each a single data point. We'll place them in a small helper area
    # in column F rows (PROG_START+2) and (PROG_START+3), hidden as narrow col.
    # Simpler: just show a static initial render + note that it reflects
    # the summary cells. The chart reads the Done/Remaining column.
    #
    # Actually: to make the chart data-bound, both series must use y_col.
    # Since Done and Remaining are single cells in column E consecutive rows,
    # we can bind Series 1 to col E rows PROG_START+2..PROG_START+2 (Done)
    # and Series 2 to col E rows PROG_START+3..PROG_START+3 (Remaining).
    # But the library requires ALL series be bound or none.
    # We'll use 1-row binding for each series.

    done_row_0based = PROG_START + 2     # 0-based
    remaining_row_0based = PROG_START + 3  # 0-based

    s.chart(
        [
            Series(
                x=[0], y=[0.0],
                label="Done", plot_type="Bar",
                color=PALETTE["good"],
                y_col=COL_E, x_col=None,
                row_start=done_row_0based,
                row_end=done_row_0based,
            ),
            Series(
                x=[1], y=[0.0],
                label="Remaining", plot_type="Bar",
                color=PALETTE["warn"],
                y_col=COL_E, x_col=None,
                row_start=remaining_row_0based,
                row_end=remaining_row_0based,
            ),
        ],
        at=(540, 330), size=(280, 200),
        title="Tasks Progress", xlabel="", ylabel="Tasks",
        grid=True, legend=True,
    )

    # ════════════════════════════════════════════════════════════════
    # 6. NOTES AREA  (rows 46–54)
    # ════════════════════════════════════════════════════════════════
    NOTES_START = 47

    s.set(NOTES_START, COL_A, "NOTES")
    s.fmt(NOTES_START, COL_A, bold=True, font_size=9, font_color="#888888")
    s.merge(NOTES_START, COL_A, 1, 3)

    # Header-style label
    s.set(NOTES_START + 1, COL_A, "Notes & Ideas")
    s.fmt(NOTES_START + 1, COL_A, bold=True, bg=TEAL,
          font_color="#ffffff", align="center")
    s.merge(NOTES_START + 1, COL_A, 1, 3)

    # 6 blank wrappable note rows
    for i in range(6):
        r = NOTES_START + 2 + i
        bg = PALETTE["note"] if (i % 2 == 0) else "#fffef0"
        s.set(r, COL_A, "")
        s.fmt(r, COL_A, bg=bg, wrap=True)
        s.merge(r, COL_A, 1, 3)

    NOTES_LAST = NOTES_START + 7
    s.box(NOTES_START + 1, COL_A, NOTES_LAST, COL_C,
          color=TEAL, width=1.2)

    # ════════════════════════════════════════════════════════════════
    # 7. GLOBAL STICKY NOTES (usage tips)
    # ════════════════════════════════════════════════════════════════
    s.note(0, COL_D,
           "DAILY PLANNER TEMPLATE\n"
           "1. Set your date in B4.\n"
           "2. Fill in the hourly schedule — choose a priority from the dropdown.\n"
           "3. Write your top 3 priorities for the day.\n"
           "4. Add tasks to the To-Do list and update status via dropdown.\n"
           "5. At the end of the day enter your 'Done' count in E43 to track progress.",
           kind="note")

    # ════════════════════════════════════════════════════════════════
    # 8. FINAL COLUMN-WIDTH TWEAKS & ROW HEIGHTS
    # ════════════════════════════════════════════════════════════════
    s.col_width(0, 90)
    s.col_width(1, 260)
    s.col_width(2, 110)
    s.col_width(3, 160)
    s.col_width(4, 100)

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Planners", "Daily Planner.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
