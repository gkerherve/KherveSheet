"""Build the "Workout Log" Daily Life template .ksheet.

A polished, fully live workout tracking workbook with:
  - Title block and instructions
  - Log table: Date | Exercise | Sets | Reps | Weight (kg) | Volume
    (Volume = Sets × Reps × Weight as a live formula per row)
  - 12 pre-filled sample rows covering three training days (editable)
  - Summary panel: Total Volume (=SUM), Sessions (=COUNTA on dates),
    Heaviest Lift (=MAX on weight column) — all live formulas
  - Bar chart of training volume per row, data-bound to Volume column
  - LaTeX equation for Volume
  - 3 instructive sticky notes

Run:  python examples/build_tpl_workout.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Sample workout data ───────────────────────────────────────────────
# Three training sessions.  Weights are editable literals; Volume is a
# live formula.  Sets/Reps are also editable literals.
WORKOUTS = [
    # (Date,        Exercise,           Sets, Reps, Weight_kg)
    ("2026-05-19", "Squat",             4,    8,    100),
    ("2026-05-19", "Bench Press",       4,    10,    80),
    ("2026-05-19", "Deadlift",          3,     5,   140),
    ("2026-05-21", "Overhead Press",    4,     8,    50),
    ("2026-05-21", "Barbell Row",       4,     8,    70),
    ("2026-05-21", "Pull-ups",          3,    10,     0),
    ("2026-05-23", "Squat",             5,     5,   110),
    ("2026-05-23", "Bench Press",       5,     5,    90),
    ("2026-05-23", "Romanian DL",       3,    10,    80),
    ("2026-05-26", "Overhead Press",    4,     6,    55),
    ("2026-05-26", "Barbell Row",       4,     6,    75),
    ("2026-05-26", "Deadlift",          3,     3,   150),
]

N_ROWS = len(WORKOUTS)

# Column indices (0-based)
COL_DATE   = 0   # A
COL_EXER   = 1   # B
COL_SETS   = 2   # C
COL_REPS   = 3   # D
COL_WGHT   = 4   # E
COL_VOL    = 5   # F

# Layout rows (0-based)
ROW_TITLE   = 0
ROW_SUBTITLE = 1
ROW_TABLE   = 3   # table() header goes here; first data row = ROW_TABLE+1
ROW_DATA_0  = ROW_TABLE + 1          # first data row (0-based)
ROW_DATA_N  = ROW_TABLE + N_ROWS     # last data row (0-based, inclusive)

# 1-based sheet rows for formula references
SR_DATA_0  = ROW_DATA_0 + 1         # first data row (1-based)
SR_DATA_N  = ROW_DATA_N + 1         # last data row (1-based)

# Summary panel column offsets (right of log table)
COL_SUM_L  = 7   # H — label
COL_SUM_V  = 8   # I — value


def build() -> str:
    wb = Workbook(min_rows=30, min_cols=10)
    s = wb.add_sheet("Workout Log")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(COL_DATE, 105)
    s.col_width(COL_EXER, 160)
    s.col_width(COL_SETS,  60)
    s.col_width(COL_REPS,  60)
    s.col_width(COL_WGHT,  90)
    s.col_width(COL_VOL,   90)
    s.col_width(6, 20)             # G — spacer
    s.col_width(COL_SUM_L, 180)
    s.col_width(COL_SUM_V, 110)

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Workout Log",
        "Track your training sets, reps and weight — Volume recalculates automatically",
        span=6,
    )

    # ── Log table ─────────────────────────────────────────────────────
    # Build table rows: Date/Exercise/Sets/Reps/Weight are literals;
    # Volume is a live formula =C{r}*D{r}*E{r}.
    table_rows = []
    for i, (date, exer, sets, reps, wgt) in enumerate(WORKOUTS):
        # 1-based sheet row of this data row:
        sr = SR_DATA_0 + i
        vol_formula = f"=C{sr}*D{sr}*E{sr}"
        table_rows.append([date, exer, sets, reps, wgt, vol_formula])

    s.table(
        ROW_TABLE, COL_DATE,
        headers=["Date", "Exercise", "Sets", "Reps", "Weight (kg)", "Volume (kg)"],
        rows=table_rows,
        number_format="0",
        banded=True,
        align_data="right",
    )

    # Override first two columns to left-align (date and exercise label)
    for i in range(N_ROWS):
        r = ROW_DATA_0 + i
        s.fmt(r, COL_DATE, align="left")
        s.fmt(r, COL_EXER, align="left")

    # Designate Volume column as Y for chart axis
    s.designate(COL_VOL, "Y")

    # ── Summary panel ─────────────────────────────────────────────────
    s.set(ROW_TABLE, COL_SUM_L, "Summary")
    s.fmt(ROW_TABLE, COL_SUM_L,
          bold=True, font_size=12, font_color=PALETTE["header"])
    s.merge(ROW_TABLE, COL_SUM_L, 1, 2)

    # Volume column range string
    vol_range  = f"F{SR_DATA_0}:F{SR_DATA_N}"
    wgt_range  = f"E{SR_DATA_0}:E{SR_DATA_N}"
    date_range = f"A{SR_DATA_0}:A{SR_DATA_N}"

    summary_items = [
        ("Total Volume (kg)",   f"=SUM({vol_range})",         PALETTE["good"]),
        ("Total Sets",          f"=SUM(C{SR_DATA_0}:C{SR_DATA_N})", PALETTE["band"]),
        ("Total Reps",          f"=SUM(D{SR_DATA_0}:D{SR_DATA_N})", PALETTE["band_alt"]),
        ("Heaviest Lift (kg)",  f"=MAX({wgt_range})",          PALETTE["warn"]),
        ("Entries Logged",      f"=COUNT({wgt_range})",        PALETTE["band"]),
        ("Avg Volume / Entry",
         f"=IFERROR(SUM({vol_range})/COUNT({wgt_range}),0)",
         PALETTE["band_alt"]),
    ]

    for i, (lbl, expr, fill) in enumerate(summary_items):
        r = ROW_DATA_0 + i
        s.set(r, COL_SUM_L, lbl)
        s.fmt(r, COL_SUM_L, align="left")
        s.formula(r, COL_SUM_V, expr)
        s.fmt(r, COL_SUM_V, bold=True, bg=fill,
              align="right", number_format="0")

    s.box(ROW_DATA_0, COL_SUM_L,
          ROW_DATA_0 + len(summary_items) - 1, COL_SUM_V,
          color=PALETTE["header"], width=1.2)

    # ── Sticky notes ──────────────────────────────────────────────────
    s.note(ROW_TITLE, COL_SUM_L,
           "TEMPLATE: Edit Sets, Reps, and Weight (kg) in the blue log table. "
           "Volume and all summary values recalculate automatically.",
           kind="note")

    s.note(ROW_TABLE, COL_SETS,
           "Sets, Reps, and Weight (kg) are editable. "
           "Volume = Sets × Reps × Weight is a live formula.",
           kind="note")

    s.note(ROW_DATA_0, COL_SUM_L,
           "Summary formulas reference the entire log table. "
           "Add or edit rows and all totals update instantly.",
           kind="note")

    # ── Bar chart — Volume per entry, data-bound ──────────────────────
    # X: row index (0..N_ROWS-1), Y: Volume column (COL_VOL = 5)
    # The initial y values match what F{sr} = C*D*E evaluates to.
    vol_initial = np.array(
        [s * r * w for (_, _, s, r, w) in WORKOUTS], dtype=float
    )
    x_initial = np.arange(N_ROWS, dtype=float)

    s.chart(
        [Series(
            x=x_initial,
            y=vol_initial,
            label="Volume (kg)",
            plot_type="Bar",
            color=PALETTE["header"],
            y_col=COL_VOL,
            row_start=ROW_DATA_0,
            row_end=ROW_DATA_N,
        )],
        at=(660, 30),
        size=(430, 310),
        title="Training Volume per Exercise",
        xlabel="Exercise (entry #)",
        ylabel="Volume (kg)",
        grid=True,
        legend=False,
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    s.equation(
        r"\mathrm{Volume} = \mathrm{Sets} \times \mathrm{Reps} \times \mathrm{Weight}",
        at=(660, 360),
        fontsize=16,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(430, 44),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Daily Life", "Workout Log.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    path = build()
    print(f"Saved: {path}")
