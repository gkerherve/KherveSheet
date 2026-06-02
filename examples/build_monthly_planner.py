"""Build the "Monthly Planner" template .ksheet file.

A beautifully formatted, fillable monthly planner template with:
- Editable Month / Year input cells
- A 6-week calendar grid with computed day numbers (Mon-start)
- Shaded weekend columns
- Monthly Goals, Key Dates, and Habit Tracker sections
- A Per-Week Events summary table (user fills in counts)
- A data-bound Bar chart of events per week

Run:  python examples/build_monthly_planner.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Ensure repo root is on the path.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Palette extensions for the planner ───────────────────────────────

ACCENT       = PALETTE["header"]        # #4472c4  — blue
ACCENT_LIGHT = PALETTE["band"]          # #d9e1f2  — light blue banding
WEEKEND_BG   = "#dce6f1"               # muted blue-grey for Sat/Sun cols
GOAL_BG      = "#e2efda"               # soft green for goals panel
HABIT_BG     = "#fce4d6"              # soft orange for habit tracker
KEY_BG       = "#fff2cc"              # soft yellow for key dates
TITLE_COL    = PALETTE["header"]
WHITE        = "#ffffff"
DARK_TEXT    = "#1f3864"
GREY_TEXT    = "#595959"
BORDER_COL   = "#8eaadb"              # medium blue border


# ── Layout constants ──────────────────────────────────────────────────

# Input cells (0-based row/col)
MONTH_ROW, MONTH_COL = 3, 2   # B4 in 1-based → (3, 1)... we'll use col 2
YEAR_ROW,  YEAR_COL  = 3, 5   # adjacent
# After rethink: put Month in col 2 (C4), Year in col 5 (F4)
# Row 0 = title, Row 1 = subtitle, Row 2 = blank, Row 3 = month/year bar
# Row 4 = blank, Row 5 = day-name headers
# Rows 6..17 = 6 week blocks (2 rows each: day-number row + notes row)
# Row 18 = blank, Row 19+ = side sections

CAL_START_ROW = 5   # 0-based; row 5 = day headers
# Day columns: Mon=col1, Tue=col2, ..., Sun=col7  (col0 = week label)
DAY_COLS = list(range(1, 8))   # cols 1..7
WEEK_ROWS = 6                  # 6 week blocks
ROWS_PER_WEEK = 2              # 2 rows per week block (day# + notes)

# Sides panel starts at col 9
SIDE_COL = 9

# Week summary table row (below calendar)
SUMMARY_START = CAL_START_ROW + 1 + WEEK_ROWS * ROWS_PER_WEEK + 2  # row 20

# ── Month-name helper (Python, for the equation/label only) ──────────
MONTH_NAMES = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]


def _days_in_month_formula(month_cell: str, year_cell: str) -> str:
    """Return a formula string that evaluates to the number of days in
    the given month/year.  Uses nested IF chains (no EOMONTH available).

    CRITICAL: KherveSheet's formula engine does NOT convert Excel's single
    '=' to Python '==' — use '==' for equality comparisons, '>='/'<=' for
    inequalities (these are fine), and NOT(x==y) instead of x<>y.
    """
    # Leap: year%4==0 and (NOT(year%100==0) or year%400==0)
    y = year_cell
    leap = (f"IF(AND(MOD({y},4)==0,"
            f"OR(NOT(MOD({y},100)==0),MOD({y},400)==0)),29,28)")
    # 30-day months: 4,6,9,11
    # 31-day months: 1,3,5,7,8,10,12
    m = month_cell
    return (
        f"=IF(OR({m}==1,{m}==3,{m}==5,{m}==7,{m}==8,{m}==10,{m}==12),31,"
        f"IF(OR({m}==4,{m}==6,{m}==9,{m}==11),30,{leap}))"
    )


def _calendar_day_formula(week: int, dow: int,
                           month_cell: str, year_cell: str,
                           days_cell: str) -> str:
    """Return the formula for a calendar day cell.

    ``week`` is 0-based week index (0..5).
    ``dow``  is 0-based day-of-week (0=Mon..6=Sun).

    WEEKDAY(DATE(year,month,1)) returns 1=Mon..7=Sun (isoweekday).
    The 1st of the month lands on column (weekday-1).
    Position number = week*7 + dow.
    Day number      = position - (start_dow - 1) + 1
                    = position - start_dow + 2
                    where start_dow = WEEKDAY(DATE(year,month,1)).

    Show "" if day < 1 or day > days_in_month.
    """
    pos = week * 7 + dow   # 0-based position in the 6-week grid
    wd  = f"WEEKDAY(DATE({year_cell},{month_cell},1))"
    day = f"{pos}-{wd}+2"
    return (
        f"=IF(AND({day}>=1,{day}<={days_cell}),{day},\"\")"
    )


def build() -> str:
    default_month = 6
    default_year  = 2026

    # Absolute cell references for inputs (1-based A1 notation)
    # Month will be at row=3 (0-based) col=2 → C4
    # Year  will be at row=3 (0-based) col=5 → F4
    # Days  will be at row=3 (0-based) col=8 → I4  (hidden helper cell)
    month_ref = "C4"
    year_ref  = "F4"
    days_ref  = "I4"   # computed days-in-month helper

    wb = Workbook(min_rows=60, min_cols=20)
    s  = wb.add_sheet("Planner")

    # ── Column widths ────────────────────────────────────────────────
    s.col_width(0, 72)    # week label
    for c in range(1, 8):
        s.col_width(c, 108)   # Mon-Sun
    s.col_width(8, 24)    # gap / helper
    s.col_width(9, 30)    # side margin
    s.col_width(10, 170)  # goal/date text
    s.col_width(11, 90)   # value col
    s.col_width(12, 90)
    s.col_width(13, 90)
    s.col_width(14, 90)

    # ── Title block ──────────────────────────────────────────────────
    s.title_block("Monthly Planner",
                  "Fill in Month & Year  ·  Enter events in each day cell  ·  "
                  "Track habits and goals on the right",
                  span=8)

    # ── Month / Year input bar ───────────────────────────────────────
    # Row 3 (0-based) = sheet row 4
    s.set(3, 0, "Month:")
    s.fmt(3, 0, bold=True, font_color=DARK_TEXT, align="right")
    s.set(3, MONTH_COL, default_month)           # C4 — editable
    s.fmt(3, MONTH_COL, bold=True, font_size=13,
          bg=PALETTE["warn"], align="center", number_format="0")

    s.set(3, 3, "Year:")
    s.fmt(3, 3, bold=True, font_color=DARK_TEXT, align="right")
    s.set(3, YEAR_COL, default_year)             # F4 — editable
    s.fmt(3, YEAR_COL, bold=True, font_size=13,
          bg=PALETTE["warn"], align="center", number_format="0")

    # Month name display (G4 = col 6) — nested IF since CHOOSE is unimplemented
    # Note: use == for equality (formula engine does not convert = to ==)
    m = month_ref
    s.formula(3, 6,
              f'=IF({m}==1,"January",IF({m}==2,"February",IF({m}==3,"March",'
              f'IF({m}==4,"April",IF({m}==5,"May",IF({m}==6,"June",'
              f'IF({m}==7,"July",IF({m}==8,"August",IF({m}==9,"September",'
              f'IF({m}==10,"October",IF({m}==11,"November","December")))'
              f'))))))))')
    s.fmt(3, 6, bold=True, font_size=14,
          font_color=ACCENT, align="left", italic=True)
    s.merge(3, 6, 1, 2)

    # Hidden helper: days in month (col 8 = I4)
    s.formula(3, 8, _days_in_month_formula(month_ref, year_ref))
    s.fmt(3, 8, font_color="#ffffff", bg="#ffffff")  # hide it visually

    s.note(3, MONTH_COL,
           "Edit the Month (1-12) and Year here.\n"
           "The calendar day numbers update automatically.",
           kind="note")

    # ── Day-name header row ──────────────────────────────────────────
    # Row 5 (0-based) = sheet row 6
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    s.set(CAL_START_ROW, 0, "Week")
    s.fmt(CAL_START_ROW, 0, bold=True, bg=ACCENT,
          font_color=WHITE, align="center")
    for i, name in enumerate(day_names):
        c = DAY_COLS[i]
        s.set(CAL_START_ROW, c, name)
        s.fmt(CAL_START_ROW, c, bold=True, bg=ACCENT,
              font_color=WHITE, align="center")
    s.box(CAL_START_ROW, 0, CAL_START_ROW, 7,
          color=ACCENT, width=1.5, inner=True)

    # ── 6-week calendar grid ─────────────────────────────────────────
    # Two rows per week: top row has the day number, second row is blank
    # (for user text). Weekends (Sat=col6, Sun=col7 → indices 5,6) shaded.
    week_labels = ["Wk 1", "Wk 2", "Wk 3", "Wk 4", "Wk 5", "Wk 6"]
    for w in range(WEEK_ROWS):
        r_num  = CAL_START_ROW + 1 + w * ROWS_PER_WEEK   # day-number row
        r_note = r_num + 1                                # notes row

        # Week label (spans both rows)
        s.set(r_num, 0, week_labels[w])
        s.fmt(r_num, 0, bold=True, font_size=9,
              font_color=GREY_TEXT, align="center", bg="#f2f2f2")
        s.fmt(r_note, 0, bg="#f2f2f2")
        s.merge(r_num, 0, 2, 1)

        for d in range(7):
            c = DAY_COLS[d]
            is_weekend = (d >= 5)
            bg_num  = WEEKEND_BG if is_weekend else WHITE
            bg_note = "#eff3fb" if is_weekend else "#fafafa"

            # Day-number cell: formula
            formula = _calendar_day_formula(
                w, d, month_ref, year_ref, days_ref)
            s.formula(r_num, c, formula)
            s.fmt(r_num, c, bold=True, font_size=10,
                  font_color=DARK_TEXT if not is_weekend else "#4472c4",
                  align="left", bg=bg_num)

            # Notes row: blank, user fills in events
            s.set(r_note, c, "")
            s.fmt(r_note, c, bg=bg_note, align="left",
                  font_size=8, wrap=True)

        # Border around the week block
        s.box(r_num, 1, r_note, 7,
              color=BORDER_COL, width=0.8, inner=False)
        s.box(r_num, 0, r_note, 7,
              color=BORDER_COL, width=0.8, inner=False)

    # Inner vertical lines between days (thin separators across all 12 rows)
    cal_r1 = CAL_START_ROW + 1
    cal_r2 = CAL_START_ROW + WEEK_ROWS * ROWS_PER_WEEK
    s.box(cal_r1, 1, cal_r2, 7, color="#c0c0c0", width=0.5, inner=True)
    # Outer border around whole calendar grid
    s.box(CAL_START_ROW, 0, cal_r2, 7,
          color=ACCENT, width=1.8)

    s.note(CAL_START_ROW + 1, 1,
           "Day numbers are computed from Month & Year above.\n"
           "Type your events in the blank row beneath each number.",
           kind="note")

    # ── Per-week events summary table ────────────────────────────────
    # Below the calendar — user fills in event counts; chart is bound here.
    # SUMMARY_START = row 20 (0-based)
    s.set(SUMMARY_START - 1, 0, "Weekly Event Count")
    s.fmt(SUMMARY_START - 1, 0, bold=True,
          font_color=ACCENT, font_size=11)
    s.merge(SUMMARY_START - 1, 0, 1, 4)

    week_count_rows = []
    for w in range(5):
        week_count_rows.append([f"Week {w+1}", 0])  # default 0 events
    s.table(SUMMARY_START, 0,
            headers=["Week", "Events / Tasks"],
            rows=week_count_rows,
            number_format="0",
            banded=True)
    # Make the count cells editable-looking (warm fill)
    for w in range(5):
        r = SUMMARY_START + 1 + w
        s.fmt(r, 1, bg=PALETTE["warn"], align="center")

    s.box(SUMMARY_START, 0, SUMMARY_START + 5, 1,
          color=ACCENT, width=1.2)
    s.note(SUMMARY_START + 1, 1,
           "Enter the number of events/tasks planned for each week.\n"
           "The bar chart on the right updates automatically.",
           kind="note")

    # Designate columns for axis hints
    s.designate(0, "X")
    s.designate(1, "Y")

    # ── Side panel — Monthly Goals ───────────────────────────────────
    goals_row = 5   # start at day-header row level
    s.set(goals_row, SIDE_COL, "Monthly Goals")
    s.fmt(goals_row, SIDE_COL, bold=True, font_size=12,
          bg=ACCENT, font_color=WHITE, align="center")
    s.merge(goals_row, SIDE_COL, 1, 5)

    for i in range(8):
        r = goals_row + 1 + i
        s.set(r, SIDE_COL, f"{i+1}.")
        s.fmt(r, SIDE_COL, bold=True, font_color=GREY_TEXT,
              align="right", font_size=9)
        s.fmt(r, SIDE_COL + 1, bg="#f7fbf0", wrap=True)
        s.merge(r, SIDE_COL + 1, 1, 4)

    s.box(goals_row, SIDE_COL, goals_row + 8, SIDE_COL + 4,
          color="#70ad47", width=1.5, inner=False)
    s.box(goals_row + 1, SIDE_COL + 1, goals_row + 8, SIDE_COL + 4,
          color="#a9d18e", width=0.5, inner=True)

    # ── Side panel — Key Dates / Deadlines ───────────────────────────
    key_row = goals_row + 10
    s.set(key_row, SIDE_COL, "Key Dates & Deadlines")
    s.fmt(key_row, SIDE_COL, bold=True, font_size=12,
          bg="#ed7d31", font_color=WHITE, align="center")
    s.merge(key_row, SIDE_COL, 1, 5)

    kd_headers = ["Date", "Description", "Priority"]
    for j, h in enumerate(kd_headers):
        s.set(key_row + 1, SIDE_COL + j * 2, h)
        s.fmt(key_row + 1, SIDE_COL + j * 2,
              bold=True, bg=PALETTE["band"],
              font_color=DARK_TEXT, align="center")
    # Adjust merges for the description column
    s.merge(key_row + 1, SIDE_COL + 2, 1, 2)

    for i in range(6):
        r = key_row + 2 + i
        for j in range(3):
            c = SIDE_COL + j * 2
            bg = PALETTE["band_alt"] if i % 2 else WHITE
            s.fmt(r, c, bg=bg, align="center", font_size=9)
        s.merge(r, SIDE_COL + 2, 1, 2)   # merge description cols
        # Priority dropdown
        s.dropdown(r, SIDE_COL + 4, ["High", "Medium", "Low"])
        s.fmt(r, SIDE_COL + 4, align="center", font_size=9,
              bg=PALETTE["band_alt"] if i % 2 else WHITE)

    s.box(key_row, SIDE_COL, key_row + 7, SIDE_COL + 4,
          color="#ed7d31", width=1.5)
    s.box(key_row + 2, SIDE_COL, key_row + 7, SIDE_COL + 4,
          color="#f4b183", width=0.5, inner=True)

    # ── Side panel — Habit Tracker ────────────────────────────────────
    habit_row = key_row + 9
    s.set(habit_row, SIDE_COL, "Habit Tracker")
    s.fmt(habit_row, SIDE_COL, bold=True, font_size=12,
          bg="#7030a0", font_color=WHITE, align="center")
    s.merge(habit_row, SIDE_COL, 1, 5)

    # Headers: Habit | Wk1 | Wk2 | Wk3 | Wk4 | Wk5
    habit_headers = ["Habit", "Wk 1", "Wk 2", "Wk 3", "Wk 4", "Wk 5"]
    for j, h in enumerate(habit_headers[:6]):
        c = SIDE_COL + j
        s.set(habit_row + 1, c, h)
        s.fmt(habit_row + 1, c, bold=True, bg="#c5a5d4",
              font_color=DARK_TEXT, align="center", font_size=9)

    default_habits = ["Exercise", "Read", "Meditate", "Sleep 8h", "Journaling"]
    for i, habit in enumerate(default_habits):
        r = habit_row + 2 + i
        s.set(r, SIDE_COL, habit)
        s.fmt(r, SIDE_COL, italic=True, font_size=9,
              bg="#f3eef7", align="left")
        for j in range(1, 6):
            c = SIDE_COL + j
            s.fmt(r, c, bg="#faf5fc" if i % 2 else "#f3eef7",
                  align="center", font_size=9)

    s.box(habit_row, SIDE_COL, habit_row + 6, SIDE_COL + 5,
          color="#7030a0", width=1.5)
    s.box(habit_row + 2, SIDE_COL, habit_row + 6, SIDE_COL + 5,
          color="#c5a5d4", width=0.5, inner=True)

    s.note(habit_row + 2, SIDE_COL,
           "Enter a tick mark, number of days completed,\n"
           "or any count in each week cell.",
           kind="note")

    # ── Bar chart — Events per week (data-bound) ──────────────────────
    # The editable event-count cells are at (SUMMARY_START+1)..(SUMMARY_START+5)
    # in column 1 (0-based = col B).
    # row_start/row_end are 0-based inclusive.
    row_start_chart = SUMMARY_START + 1
    row_end_chart   = SUMMARY_START + 5

    # Initial Y data matches the default zeros in the table
    y_data = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
    x_data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

    s.chart(
        [Series(
            x_data, y_data,
            label="Events / Tasks",
            plot_type="Bar",
            color="#4472c4",
            y_col=1,       # column B (0-based)
            row_start=row_start_chart,
            row_end=row_end_chart,
        )],
        at=(0, 780),
        size=(480, 260),
        title="Events per Week",
        xlabel="Week",
        ylabel="Events / Tasks",
        grid=True,
        legend=False,
    )

    # ── LaTeX equation ───────────────────────────────────────────────
    # A small calendar-formula reminder
    s.equation(
        r"\mathrm{Day\,} n = \mathrm{pos} - \mathrm{weekday}(1^{st}) + 2",
        at=(490, 780),
        fontsize=15,
        color="#1f3864",
        bg_color="#f2f7ff",
        border_color=ACCENT,
        border_width=1.2,
        size=(340, 50),
    )

    # ── Output ───────────────────────────────────────────────────────
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "templates", "Planners")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Monthly Planner.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    path = build()
    print("Wrote", path)
