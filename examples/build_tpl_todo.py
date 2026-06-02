"""Build the "Todo List" Daily Life template .ksheet.

A polished task tracker with Priority and Status dropdowns, a 1/0 Done
flag column, live progress summary (Total / Done / Remaining / % Complete),
and a bound bar chart showing Done vs Remaining that updates whenever the
Done flags change.

Run:  python examples/build_tpl_todo.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Make the project importable from any working directory.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Sample tasks (users will replace / extend these) ──────────────────────
# (Task, Priority, DueDate, Status, DoneFlag)
TASKS = [
    ("Buy groceries",           "High",   "2026-06-03", "Done",        1),
    ("Call the dentist",        "Medium", "2026-06-05", "To do",       0),
    ("Submit expense report",   "High",   "2026-06-04", "In progress", 0),
    ("Read chapter 3",          "Low",    "2026-06-10", "To do",       0),
    ("Pay electricity bill",    "High",   "2026-06-06", "Done",        1),
    ("Book train tickets",      "Medium", "2026-06-07", "In progress", 0),
    ("Water the plants",        "Low",    "2026-06-03", "Done",        1),
    ("Backup laptop",           "Medium", "2026-06-08", "To do",       0),
    ("Plan weekend trip",       "Low",    "2026-06-12", "To do",       0),
    ("Reply to emails",         "High",   "2026-06-03", "Done",        1),
    ("Fix leaky tap",           "Medium", "2026-06-09", "In progress", 0),
    ("Renew car insurance",     "High",   "2026-06-15", "To do",       0),
]

N = len(TASKS)


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=16)
    s = wb.add_sheet("Todo List")

    # ── Column widths ─────────────────────────────────────────────────
    # Col 0=#  1=Task  2=Priority  3=Due Date  4=Status  5=Done(0/1)
    s.col_width(0, 45)    # #
    s.col_width(1, 220)   # Task
    s.col_width(2, 100)   # Priority
    s.col_width(3, 110)   # Due Date
    s.col_width(4, 110)   # Status
    s.col_width(5, 80)    # Done flag

    # ── Table layout constants ────────────────────────────────────────
    # table() writes:
    #   Header row  at 0-based row TABLE_START     → sheet row TABLE_START+1
    #   Data row k  at 0-based row TABLE_START+1+k → sheet row TABLE_START+2+k
    TABLE_START    = 5
    DATA_1B_FIRST  = TABLE_START + 2          # first data row, 1-based = 7
    DATA_1B_LAST   = TABLE_START + 1 + N      # last  data row, 1-based = 18

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Daily Todo List",
        "Track your tasks — set Done = 1 when complete and watch the "
        "progress bar update automatically.",
        span=6,
    )

    # ── Input note ────────────────────────────────────────────────────
    s.note(0, 7,
           "Edit any cell in the Task, Priority, Due Date, Status or Done "
           "columns. Set Done = 1 to mark a task complete; the summary and "
           "chart update instantly.",
           kind="note")

    # ── Summary panel ─────────────────────────────────────────────────
    # We put the summary to the right of the table, starting at col 8.
    # The summary also feeds two chart-binding cells (col 10 = "Y" column).
    #
    # Layout (0-based cols):
    #   Col 8  = label
    #   Col 9  = value (formula)
    #   Col 10 = chart data (Done / Remaining) — bound Y column
    #   Col 11 = chart label strings
    SUMM_COL   = 8
    CHART_Y    = 10   # 0-based column for chart Y data (Done, Remaining)

    # Total tasks is a fixed literal (the number of rows we wrote).
    # Done = SUM of the Done flag column (F = col 5, 1-based).
    # Remaining and % are formulas referencing the summary cells.
    #
    # Summary cell addresses (1-based):
    #   Total      → J4  (row 3, col 9)  = 0-based row 3, col 9
    #   Done       → J5  (row 4, col 9)
    #   Remaining  → J6  (row 5, col 9)
    #   % Complete → J7  (row 6, col 9)
    #
    # Use absolute $J$4 / $J$5 etc. so they can be referenced from chart cells.

    SUMM_ROW_0 = 3   # 0-based row of first summary label (Total)

    # 1-based sheet row of summary values
    TOTAL_1B    = SUMM_ROW_0 + 1       # = 4  → J4
    DONE_1B     = SUMM_ROW_0 + 2       # = 5  → J5
    REMAIN_1B   = SUMM_ROW_0 + 3       # = 6  → J6
    PCT_1B      = SUMM_ROW_0 + 4       # = 7  → J7

    # Value column letter (col 9 = J, 0-based → 1-based = col J)
    VAL_COL_LETTER = "J"

    s.set(SUMM_ROW_0 - 1, SUMM_COL, "Progress Summary")
    s.fmt(SUMM_ROW_0 - 1, SUMM_COL, bold=True, font_size=13,
          font_color=PALETTE["header"])
    s.merge(SUMM_ROW_0 - 1, SUMM_COL, 1, 3)

    flag_col_letter = "F"   # Done flag column (col 5 → F in 1-based A1)

    summary_rows = [
        # (label, formula_or_literal, bg_color, number_format)
        ("Total Tasks",
         str(N),
         PALETTE["band"],
         "0"),
        ("Done",
         f"=SUM({flag_col_letter}{DATA_1B_FIRST}:{flag_col_letter}{DATA_1B_LAST})",
         PALETTE["good"],
         "0"),
        ("Remaining",
         f"={VAL_COL_LETTER}{TOTAL_1B}-{VAL_COL_LETTER}{DONE_1B}",
         PALETTE["bad"],
         "0"),
        ("% Complete",
         f"=IFERROR({VAL_COL_LETTER}{DONE_1B}/{VAL_COL_LETTER}{TOTAL_1B}*100, 0)",
         PALETTE["warn"],
         "0.0"),
    ]

    for i, (lbl, expr, bg, nf) in enumerate(summary_rows):
        r = SUMM_ROW_0 + i
        s.set(r, SUMM_COL, lbl)
        s.fmt(r, SUMM_COL, align="left")
        if expr.startswith("="):
            s.formula(r, SUMM_COL + 1, expr)
        else:
            s.set(r, SUMM_COL + 1, expr)
        s.fmt(r, SUMM_COL + 1, bg=bg, align="right", bold=True,
              number_format=nf)

    s.box(SUMM_ROW_0, SUMM_COL, SUMM_ROW_0 + len(summary_rows) - 1,
          SUMM_COL + 1, color=PALETTE["header"], width=1.0)
    s.col_width(SUMM_COL, 140)
    s.col_width(SUMM_COL + 1, 80)

    # ── Chart data cells (col 10 = K, bound Y-axis) ───────────────────
    # Two rows: row SUMM_ROW_0 = Done, row SUMM_ROW_0+1 = Remaining.
    # These reference the summary column so they stay live.
    #
    # 0-based rows: SUMM_ROW_0, SUMM_ROW_0+1
    # 1-based sheet rows: SUMM_ROW_0+1, SUMM_ROW_0+2
    CHART_ROW_0 = SUMM_ROW_0          # 0-based first chart data row
    CHART_ROW_1 = SUMM_ROW_0 + 1      # 0-based second chart data row
    CHART_1B_0  = CHART_ROW_0 + 1     # 1-based = 4
    CHART_1B_1  = CHART_ROW_1 + 1     # 1-based = 5

    # Chart labels (col 11 = L)
    s.set(CHART_ROW_0, CHART_Y + 1, "Done")
    s.set(CHART_ROW_1, CHART_Y + 1, "Remaining")
    s.fmt(CHART_ROW_0, CHART_Y + 1, align="center", bold=True)
    s.fmt(CHART_ROW_1, CHART_Y + 1, align="center", bold=True)

    # Chart Y values (column K = col 10), referencing summary
    # J4 = Total(1-based 4), J5 = Done(1-based 5), J6 = Remain(1-based 6)
    s.formula(CHART_ROW_0, CHART_Y, f"={VAL_COL_LETTER}{DONE_1B}")
    s.formula(CHART_ROW_1, CHART_Y, f"={VAL_COL_LETTER}{REMAIN_1B}")
    s.fmt(CHART_ROW_0, CHART_Y, align="right", number_format="0",
          bg=PALETTE["good"])
    s.fmt(CHART_ROW_1, CHART_Y, align="right", number_format="0",
          bg=PALETTE["bad"])

    # Designate for chart axis binding
    s.designate(CHART_Y, "Y")

    s.col_width(CHART_Y, 70)
    s.col_width(CHART_Y + 1, 90)

    # ── Task table ────────────────────────────────────────────────────
    headers = ["#", "Task", "Priority", "Due Date", "Status", "Done (1/0)"]

    rows = []
    for k, (task, priority, due, status, done) in enumerate(TASKS):
        rr = TABLE_START + 2 + k   # 1-based sheet row of this data row
        rows.append([
            k + 1,          # # (literal row number)
            task,           # Task (editable text)
            priority,       # Priority (dropdown)
            due,            # Due Date (editable)
            status,         # Status (dropdown)
            done,           # Done flag 0 or 1 (editable integer)
        ])

    s.table(
        TABLE_START, 0,
        headers=headers,
        rows=rows,
        banded=True,
        align_data="left",
    )

    # Per-cell format overrides
    for k in range(N):
        r0 = TABLE_START + 1 + k   # 0-based data row
        band = (k % 2 == 1)
        bg_band = PALETTE["band_alt"] if band else None

        # # column: center, light
        s.fmt(r0, 0, align="center", number_format="0")
        # Task: left, highlight editable
        s.fmt(r0, 1, align="left", bg=PALETTE["band"] if not band else PALETTE["band_alt"])
        # Priority: center
        s.fmt(r0, 2, align="center")
        # Due Date: center
        s.fmt(r0, 3, align="center")
        # Status: center
        s.fmt(r0, 4, align="center")
        # Done flag: center, accent
        done_val = TASKS[k][4]
        done_bg = PALETTE["good"] if done_val else PALETTE["bad"]
        s.fmt(r0, 5, align="center", bg=done_bg, bold=True, number_format="0")

    # Outer table border
    s.box(TABLE_START, 0, TABLE_START + N, 5,
          color=PALETTE["header"], width=1.5)

    # ── Dropdowns ─────────────────────────────────────────────────────
    PRIORITY_OPTS = ["High", "Medium", "Low"]
    STATUS_OPTS   = ["To do", "In progress", "Done"]

    for k in range(N):
        r0 = TABLE_START + 1 + k
        s.dropdown(r0, 2, PRIORITY_OPTS)   # Priority
        s.dropdown(r0, 4, STATUS_OPTS)     # Status

    # ── Notes ─────────────────────────────────────────────────────────
    s.note(TABLE_START, 5,
           "Set to 1 when a task is complete, 0 otherwise. "
           "Done count and % Complete update immediately.",
           kind="note")
    s.note(TABLE_START, 2,
           "Click a Priority cell and use the dropdown arrow to choose "
           "High / Medium / Low.",
           kind="note")
    s.note(SUMM_ROW_0 + 3, SUMM_COL,
           "% Complete = Done / Total × 100. "
           "The bar chart on the right reflects this split.",
           kind="note")

    # ── Chart ─────────────────────────────────────────────────────────
    # Initial render values must match what the formula cells evaluate to.
    done_count      = sum(t[4] for t in TASKS)
    remaining_count = N - done_count

    init_x = np.array([0.0, 1.0])
    init_y = np.array([float(done_count), float(remaining_count)])

    s.chart(
        [
            Series(
                init_x, init_y,
                label="Tasks",
                plot_type="Bar",
                color="#70ad47",   # green for Done
                y_col=CHART_Y,     # column K (0-based = 10)
                row_start=CHART_ROW_0,
                row_end=CHART_ROW_1,
            ),
        ],
        at=(10, 480),
        size=(480, 280),
        title="Done vs Remaining",
        xlabel="",
        ylabel="Number of Tasks",
        grid=True,
        legend=False,
    )

    # ── Equation ──────────────────────────────────────────────────────
    s.equation(
        r"\mathrm{\%\ Complete} = \frac{\mathrm{Done}}{\mathrm{Total}} \times 100",
        at=(510, 480),
        fontsize=17,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(340, 54),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Daily Life", "Todo List.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
