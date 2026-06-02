"""Build the "Weekly Planner" template .ksheet file.

A polished, fillable weekly planner template with:
- Title block and editable week-start date
- 7-day grid (Mon–Sun) with Morning / Afternoon / Evening / Tasks bands
- Weekend columns shaded differently
- "Tasks planned" per-day row with a live-bound bar chart
- Weekly Goals boxed section and a Notes area
- Yellow sticky notes with usage tips

Run:  python examples/build_weekly_planner.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Make the project importable from any working directory.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Colour constants ──────────────────────────────────────────────────

HEADER_BG    = PALETTE["header"]        # blue  – day-name header
HEADER_FG    = PALETTE["header_text"]   # white
BAND_LIGHT   = PALETTE["band_alt"]      # very light blue – weekday fill
WEEKEND_BG   = "#dce6f1"               # slightly darker blue-grey for Sat/Sun
TIME_BAND_A  = "#f2f2f2"               # light grey – time-block label cells
TIME_BAND_B  = "#ffffff"               # white – entry cells
GOALS_BG     = "#eaf4e8"               # pale green – goals section
NOTES_BG     = "#fffde7"               # pale yellow – notes section
SUMMARY_BG   = PALETTE["band"]         # light blue – summary row
ACCENT       = PALETTE["accent"]        # orange accent

# ── Column layout ─────────────────────────────────────────────────────
#   Col 0  : time-block label (e.g. "Morning")
#   Cols 1-7: Mon … Sun
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
        "Saturday", "Sunday"]
C_LABEL = 0          # label column index
C_MON   = 1          # first day column (Monday)
C_SUN   = 7          # last  day column (Sunday)

# Weekend columns (0-based)
WEEKEND_COLS = [6, 7]   # Saturday=6, Sunday=7

# ── Row layout constants ──────────────────────────────────────────────
R_TITLE        = 0
R_SUBTITLE     = 1
R_WEEK_LABEL   = 3    # "Week starting:" label
R_WEEK_DATE    = 3    # date cell is on same row (col 2)
R_DAYS_HEADER  = 5    # Day-name header row
R_DATE_SUB     = 6    # Row for short date sub-labels (user-editable)
R_MORN_START   = 8    # Morning block: rows 8-10
R_MORN_END     = 10
R_AFT_START    = 12   # Afternoon block: rows 12-14
R_AFT_END      = 14
R_EVE_START    = 16   # Evening block: rows 16-18
R_EVE_END      = 18
R_TASK_START   = 20   # Tasks/To-do block: rows 20-22
R_TASK_END     = 22
R_SUMMARY      = 24   # "Tasks planned" summary row
R_GOALS_TITLE  = 27   # Weekly Goals heading
R_GOALS_START  = 28   # Goals rows 28-32 (5 goals)
R_GOALS_END    = 32
R_NOTES_TITLE  = 34   # Notes heading
R_NOTES_START  = 35   # Notes rows 35-40
R_NOTES_END    = 40


def _apply_day_band(s, r, col_fill_weekend="#dce6f1", col_fill_weekday="#ffffff"):
    """Apply per-day fill to a single data row."""
    for c in range(C_MON, C_SUN + 1):
        bg = WEEKEND_BG if c in WEEKEND_COLS else col_fill_weekday
        s.fmt(r, c, bg=bg)


def build() -> str:
    wb = Workbook(min_rows=45, min_cols=10)
    s  = wb.add_sheet("Weekly Planner")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(C_LABEL, 120)   # time-block label
    for c in range(C_MON, C_SUN + 1):
        s.col_width(c, 110)

    # ── Title block ───────────────────────────────────────────────────
    s.title_block("Weekly Planner",
                  "Plan your week — edit cells, fill in tasks, track goals.",
                  row=R_TITLE, col=0, span=8)

    # "Week starting:" label + editable date cell
    s.set(R_WEEK_LABEL, 0, "Week starting:")
    s.fmt(R_WEEK_LABEL, 0, bold=True, font_size=11, align="right",
          font_color=ACCENT)
    s.set(R_WEEK_DATE, 1, "2026-06-15")        # editable literal
    s.fmt(R_WEEK_DATE, 1, bold=True, font_size=11, bg=PALETTE["warn"],
          align="center", number_format="Text")
    s.merge(R_WEEK_DATE, 1, 1, 2)
    s.box(R_WEEK_DATE, 1, R_WEEK_DATE, 2, color=ACCENT, width=1.5)

    s.note(R_WEEK_DATE, 1,
           "Edit the date (YYYY-MM-DD) to set the week. "
           "Update the date sub-row below manually to match.",
           kind="note")

    # ── Day-name header row ───────────────────────────────────────────
    s.set(R_DAYS_HEADER, C_LABEL, "")
    s.fmt(R_DAYS_HEADER, C_LABEL, bg=HEADER_BG)

    for i, day in enumerate(DAYS):
        c = C_MON + i
        s.set(R_DAYS_HEADER, c, day)
        bg = WEEKEND_BG if c in WEEKEND_COLS else HEADER_BG
        fg = "#333333" if c in WEEKEND_COLS else HEADER_FG
        s.fmt(R_DAYS_HEADER, c, bold=True, bg=bg, font_color=fg,
              align="center", font_size=10)

    s.box(R_DAYS_HEADER, C_LABEL, R_DAYS_HEADER, C_SUN,
          color=HEADER_BG, width=1.5)

    # ── Date sub-row (user fills in short dates, e.g. "15 Jun") ──────
    s.set(R_DATE_SUB, C_LABEL, "Date")
    s.fmt(R_DATE_SUB, C_LABEL, italic=True, bg=TIME_BAND_A,
          align="center", font_color="#555555", font_size=9)
    for i in range(7):
        c = C_MON + i
        s.set(R_DATE_SUB, c, "")               # user fills in
        bg = "#d6e4f0" if c in WEEKEND_COLS else "#eef3fb"
        s.fmt(R_DATE_SUB, c, italic=True, bg=bg, align="center",
              font_color="#444444", font_size=9)
    s.box(R_DATE_SUB, C_LABEL, R_DATE_SUB, C_SUN,
          color="#aaaaaa", width=0.8)
    s.note(R_DATE_SUB, 1,
           "Fill in short dates here, e.g. '15 Jun', '16 Jun' …",
           kind="note")

    # ── Helper: draw a time-block band ───────────────────────────────
    def time_block(label, r_start, r_end, label_bg, entry_bg, border_color):
        """Draw a labelled time-block band spanning r_start..r_end."""
        row_count = r_end - r_start + 1

        # Label cell: merged vertically, bold, centred
        s.set(r_start, C_LABEL, label)
        s.fmt(r_start, C_LABEL, bold=True, font_size=10,
              bg=label_bg, align="center", font_color="#333333",
              wrap=True)
        if row_count > 1:
            s.merge(r_start, C_LABEL, row_count, 1)

        # Entry cells
        for r in range(r_start, r_end + 1):
            for c in range(C_MON, C_SUN + 1):
                bg = "#eaf0f8" if c in WEEKEND_COLS else entry_bg
                s.fmt(r, c, bg=bg, wrap=True, align="left")

        # Inner grid lines (thin horizontal dividers between rows)
        s.box(r_start, C_LABEL, r_end, C_SUN,
              color=border_color, width=1.0, inner=True)

    # Separator helper (thin shaded row between bands)
    def separator_row(r):
        s.fmt_range(r, C_LABEL, r, C_SUN, bg="#d0d7e8")
        s.box(r, C_LABEL, r, C_SUN, color="#9aabcc", width=0.5)

    # ── Time-block bands ──────────────────────────────────────────────
    separator_row(R_MORN_START - 1)   # row 7
    time_block("Morning",   R_MORN_START, R_MORN_END,
               "#fff3cd", "#fffdf5", "#e0c060")

    separator_row(R_AFT_START - 1)    # row 11
    time_block("Afternoon", R_AFT_START, R_AFT_END,
               "#cce5ff", "#f0f7ff", "#5b9bd5")

    separator_row(R_EVE_START - 1)    # row 15
    time_block("Evening",   R_EVE_START, R_EVE_END,
               "#d4c5e2", "#f7f4fb", "#8064a2")

    separator_row(R_TASK_START - 1)   # row 19
    time_block("Tasks /\nTo-do", R_TASK_START, R_TASK_END,
               "#d9ead3", "#f4fbf2", "#6aa84f")

    # ── Outer border around the whole daily grid ──────────────────────
    s.box(R_DAYS_HEADER, C_LABEL, R_TASK_END, C_SUN,
          color=HEADER_BG, width=2.0)

    # ── Per-day summary row: "Tasks planned" ─────────────────────────
    separator_row(R_SUMMARY - 1)   # row 23

    s.set(R_SUMMARY, C_LABEL, "Tasks planned")
    s.fmt(R_SUMMARY, C_LABEL, bold=True, bg=SUMMARY_BG,
          align="left", font_size=10)

    # Editable task counts (the user updates these; start at 0)
    task_counts = [0] * 7
    for i in range(7):
        c = C_MON + i
        s.set(R_SUMMARY, c, task_counts[i])
        bg = "#c5d9f1" if c in WEEKEND_COLS else SUMMARY_BG
        s.fmt(R_SUMMARY, c, bg=bg, bold=True, align="center",
              font_size=11, number_format="0")

    s.box(R_SUMMARY, C_LABEL, R_SUMMARY, C_SUN,
          color=HEADER_BG, width=1.5)
    s.note(R_SUMMARY, C_MON,
           "Enter the number of tasks you plan each day. "
           "The bar chart updates automatically.",
           kind="note")

    # ── Bar chart: tasks planned per day ─────────────────────────────
    # Data binding: summary row R_SUMMARY (0-based) is the single data row.
    # x_col = C_LABEL (day names), y_col = each day column.
    # We use one Series per day for a grouped bar chart feel,
    # but the library needs one Series if we bind a single y_col.
    # Strategy: one bar Series with x = day indices, y = task counts,
    # bound to row R_SUMMARY, reading cols C_MON..C_SUN as y.
    # The library supports a single y_col; we expose the whole row as one
    # series (bar chart of 7 values at positions 0-6).

    day_indices = np.arange(7, dtype=float)
    task_y      = np.array(task_counts, dtype=float)

    # x_col binding: not appropriate here (x is day *names* from header).
    # We bind y to the C_MON column but row_start=row_end=R_SUMMARY —
    # the app reads a single row of that column. Instead we make 7 series,
    # one per day, each a single point, all bound.  That is rejected if
    # mixing bound/unbound, so we use a single series bound to the first
    # day and note the limitation.
    # Better: use a single Series with x=day_indices, y=task_counts,
    # y_col=C_MON (the chart engine reads y_cols=[C_MON] over row_start..
    # row_end, which is just one row = the summary row value for Mon).
    # This gives a single bar that tracks Mon only — not ideal.
    #
    # The cleanest data-bound approach for a single-row range is to
    # transpose: put the 7 counts in a column.  But that disrupts the
    # layout.  Instead we make the chart series span the summary row and
    # give x_col=C_LABEL, y_col=C_MON, row_start=R_SUMMARY,
    # row_end=R_SUMMARY so the engine at least tracks one live cell,
    # and place all 7 initial values in y.  Then to get 7 bars we pass
    # all 7 day values in x/y for the first render, but y_col only tracks
    # col C_MON.  This is the best we can do with the bar chart + row
    # layout without changing the template structure.
    #
    # Practical compromise: place a helper *column* (col 8) that lists
    # the 7 task-count cells as a column (rows R_SUMMARY_COL_START..+6)
    # via formulas referencing the summary row, then bind the chart to
    # that column.

    R_CHART_DATA_START = R_SUMMARY  # we'll place a hidden column
    R_CHART_DATA_END   = R_SUMMARY + 6

    # Col 9: day-name labels for the chart (literal text)
    # Col 8: per-day task counts as a column (formulas referencing row 24)
    C_CHART_LABELS = 9
    C_CHART_VALUES = 8

    # Sheet row of R_SUMMARY is R_SUMMARY+1 (1-based).
    # The 7 day cells are at columns C_MON..C_SUN in that row.
    day_col_letters = ["B", "C", "D", "E", "F", "G", "H"]  # cols 1-7
    summary_sheet_row = R_SUMMARY + 1   # 1-based

    for i, (day, col_letter) in enumerate(zip(DAYS, day_col_letters)):
        r = R_SUMMARY + i                       # 0-based row in helper col
        # Label column
        s.set(r, C_CHART_LABELS, day)
        s.fmt(r, C_CHART_LABELS, font_size=8, font_color="#888888")
        # Formula column: =B25, =C25, ... =H25
        s.formula(r, C_CHART_VALUES,
                  f"={col_letter}{summary_sheet_row}")
        s.fmt(r, C_CHART_VALUES, font_size=8, font_color="#888888",
              number_format="0")

    # Mark the helper columns small / unobtrusive
    s.col_width(C_CHART_VALUES, 60)
    s.col_width(C_CHART_LABELS, 80)

    # Designate columns for axis hints
    s.designate(C_CHART_LABELS, "X")
    s.designate(C_CHART_VALUES, "Y")

    # Build the bar chart bound to the helper column
    s.chart(
        [Series(
            x=day_indices,
            y=task_y,
            label="Tasks planned",
            plot_type="Bar",
            color=HEADER_BG,
            y_col=C_CHART_VALUES,
            row_start=R_CHART_DATA_START,
            row_end=R_CHART_DATA_END,
        )],
        at=(900, 180),
        size=(380, 260),
        title="Tasks Planned per Day",
        xlabel="Day",
        ylabel="Tasks",
        grid=True,
        legend=False,
    )

    # ── Weekly Goals section ──────────────────────────────────────────
    separator_row(R_GOALS_TITLE - 1)   # row 26

    s.set(R_GOALS_TITLE, 0, "Weekly Goals")
    s.fmt(R_GOALS_TITLE, 0, bold=True, font_size=12,
          font_color=HEADER_BG, bg=GOALS_BG)
    s.merge(R_GOALS_TITLE, 0, 1, 8)

    for i in range(5):
        r = R_GOALS_START + i
        s.set(r, 0, f"{i + 1}.")
        s.fmt(r, 0, bold=True, align="right", bg=GOALS_BG,
              font_color=HEADER_BG)
        s.set(r, 1, "")            # user fills in goal text
        s.fmt_range(r, 1, r, 7, bg=GOALS_BG, wrap=True)
        s.merge(r, 1, 1, 7)        # goal text spans all day columns
        s.box(r, 0, r, 7, color="#6aa84f", width=0.8, inner=False)

    s.box(R_GOALS_TITLE, 0, R_GOALS_END, 7,
          color="#6aa84f", width=1.5)

    s.note(R_GOALS_TITLE, 0,
           "Write your top 5 goals for the week here. "
           "Review them each morning.",
           kind="note")

    # ── Notes section ────────────────────────────────────────────────
    separator_row(R_NOTES_TITLE - 1)   # row 33

    s.set(R_NOTES_TITLE, 0, "Notes")
    s.fmt(R_NOTES_TITLE, 0, bold=True, font_size=12,
          font_color=ACCENT, bg=NOTES_BG)
    s.merge(R_NOTES_TITLE, 0, 1, 8)

    for r in range(R_NOTES_START, R_NOTES_END + 1):
        s.fmt_range(r, 0, r, 7, bg=NOTES_BG, wrap=True)
        s.merge(r, 0, 1, 8)

    s.box(R_NOTES_TITLE, 0, R_NOTES_END, 7,
          color="#f0a500", width=1.5)

    # ── Additional sticky notes ───────────────────────────────────────
    s.note(R_TASK_START, C_MON,
           "List your tasks here. Each row is a separate task slot.\n"
           "Tick off or cross out when done.",
           kind="note")

    s.note(R_MORN_START, C_MON,
           "Morning, Afternoon, Evening rows: "
           "type your scheduled activities directly into the cells.",
           kind="note")

    # ── Save ──────────────────────────────────────────────────────────
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "templates", "Planners")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Weekly Planner.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    path = build()
    print("Wrote", path)
