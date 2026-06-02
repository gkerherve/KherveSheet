"""Build the "Calorie Tracker" Daily Life template .ksheet.

A practical weekly food-log workbook:
  - Editable daily calorie goal + 7-day food log (Day / Meal / Food /
    Calories / Protein / Carbs / Fat).
  - Per-day totals via =SUM() formula rows.
  - Weekly summary panel: total, average, remaining-vs-goal.
  - Live-bound bar chart of daily calorie totals.
  - LaTeX equation for energy balance.
  - Instructive yellow sticky notes.

Run:  python examples/build_tpl_calorie.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Make the project importable when run from any cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Default sample data ───────────────────────────────────────────────
DAILY_GOAL = 2000  # kcal

# 7 days x 4 meals.  Columns: Food, Calories, Protein(g), Carbs(g), Fat(g)
# These are the LITERAL editable values the user will overwrite.
SAMPLE = [
    # Day 1
    ("Porridge with berries",      350, 10, 60, 7),
    ("Chicken & rice bowl",        520, 38, 55, 10),
    ("Salmon with vegetables",     490, 35, 30, 18),
    ("Greek yoghurt & almonds",    210,  9, 14, 13),
    # Day 2
    ("Scrambled eggs on toast",    380, 22, 35, 14),
    ("Tuna salad wrap",            430, 30, 42,  9),
    ("Beef stir-fry with noodles", 570, 32, 60, 16),
    ("Apple & peanut butter",      190,  5, 22,  8),
    # Day 3
    ("Smoothie bowl",              320,  8, 52,  7),
    ("Lentil soup & bread",        450, 20, 68, 10),
    ("Grilled chicken & quinoa",   510, 42, 45, 12),
    ("Cheese & crackers",          240,  8, 22, 13),
    # Day 4
    ("Avocado toast with eggs",    420, 18, 40, 18),
    ("Caesar salad with chicken",  480, 34, 22, 26),
    ("Pasta with tomato sauce",    540, 18, 82, 12),
    ("Fruit salad",                150,  2, 35,  1),
    # Day 5
    ("Granola with milk",          390, 12, 58, 11),
    ("Turkey & avocado sandwich",  460, 28, 48, 14),
    ("Vegetable curry & rice",     520, 14, 78, 14),
    ("Dark chocolate (30 g)",      160,  2, 18, 10),
    # Day 6
    ("French toast",               400, 14, 52, 14),
    ("Minestrone soup",            340, 12, 52,  8),
    ("Steak with sweet potato",    580, 44, 38, 18),
    ("Mixed nuts",                 200,  5, 10, 16),
    # Day 7
    ("Pancakes with maple syrup",  450, 10, 70, 14),
    ("BLT sandwich",               480, 22, 42, 22),
    ("Roast chicken & potatoes",   560, 40, 45, 16),
    ("Hummus & vegetable sticks",  180,  6, 20,  8),
]

MEALS   = ["Breakfast", "Lunch", "Dinner", "Snack"]
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def build() -> str:
    wb = Workbook(min_rows=56, min_cols=16)
    s = wb.add_sheet("Calorie Tracker")

    # ── Column widths ────────────────────────────────────────────────
    # Col layout (0-based):
    #  A(0)=Day  B(1)=Meal  C(2)=Food  D(3)=Cal  E(4)=Prot  F(5)=Carbs  G(6)=Fat
    #  [gap H(7)]
    #  I(8)=Day-label  J(9)=Daily Cal  K(10)=Prot  L(11)=Carbs  M(12)=Fat
    #  [gap N(13)]
    #  O(14)=Summary label  P(15)=Summary value
    s.col_width(0,  48)   # Day
    s.col_width(1,  90)   # Meal
    s.col_width(2, 200)   # Food name
    s.col_width(3,  80)   # Calories
    s.col_width(4,  75)   # Protein
    s.col_width(5,  70)   # Carbs
    s.col_width(6,  60)   # Fat
    s.col_width(7,  18)   # spacer
    s.col_width(8,  55)   # Day label
    s.col_width(9,  80)   # Daily Cal total
    s.col_width(10, 75)   # Prot total
    s.col_width(11, 70)   # Carbs total
    s.col_width(12, 60)   # Fat total
    s.col_width(13, 18)   # spacer
    s.col_width(14, 175)  # Summary label
    s.col_width(15, 100)  # Summary value

    # ── Title block ──────────────────────────────────────────────────
    s.title_block("Weekly Calorie Tracker",
                  "Log meals for 7 days — totals, averages and goal tracking "
                  "update automatically",
                  span=8)

    # ── Goal input ───────────────────────────────────────────────────
    # Row 3 (0-based) → sheet row 4.  Goal value at B4 → 1-based = B4.
    s.set(3, 0, "Daily Calorie Goal (kcal)")
    s.set(3, 1, DAILY_GOAL)
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"], align="left")
    s.fmt(3, 1, bg=PALETTE["warn"], bold=True, align="center",
          number_format="0")
    s.box(3, 0, 3, 1, color=PALETTE["accent"], width=1.5)
    s.note(3, 1,
           "Edit B4 to set your daily calorie goal.\n"
           "The 'Remaining' rows and weekly summary update instantly.",
           kind="note")

    # ── Food log table ───────────────────────────────────────────────
    # Header at 0-based row 5 → sheet row 6.
    # First data row at 0-based row 6 → sheet row 7.
    LOG_START = 5   # 0-based row of table header
    FIRST_DATA_SHEET = LOG_START + 2   # = 7  (1-based sheet row of row 0)

    s.set(4, 0, "Daily Food Log")
    s.fmt(4, 0, bold=True, font_color=PALETTE["header"], font_size=11)

    log_headers = ["Day", "Meal", "Food / Description",
                   "Calories", "Protein (g)", "Carbs (g)", "Fat (g)"]
    # Write header row manually (table() would reset banding logic).
    for j, h in enumerate(log_headers):
        s.set(LOG_START, j, h)
        s.fmt(LOG_START, j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    # Data rows: 28 rows (7 days x 4 meals).
    for i, (food, cal, prot, carb, fat) in enumerate(SAMPLE):
        day_idx  = i // 4       # 0..6
        meal_idx = i % 4        # 0..3
        r = LOG_START + 1 + i  # 0-based row
        band = PALETTE["band_alt"] if (day_idx % 2 == 1) else None

        s.set(r, 0, DAY_NAMES[day_idx])
        s.set(r, 1, MEALS[meal_idx])
        s.set(r, 2, food)
        s.set(r, 3, cal)
        s.set(r, 4, prot)
        s.set(r, 5, carb)
        s.set(r, 6, fat)

        s.fmt(r, 0, align="center", bold=(meal_idx == 0))
        s.fmt(r, 1, align="left")
        s.fmt(r, 2, align="left")
        if band:
            s.fmt_range(r, 0, r, 6, bg=band)
        s.fmt(r, 3, align="right", number_format="0")
        s.fmt(r, 4, align="right", number_format="0")
        s.fmt(r, 5, align="right", number_format="0")
        s.fmt(r, 6, align="right", number_format="0")

    # Outer border around the entire log (header + 28 data rows).
    s.box(LOG_START, 0, LOG_START + 28, 6,
          color=PALETTE["header"], width=1.2)
    # Inner horizontal lines between days (every 4 rows).
    for day_idx in range(1, 7):
        sep_r = LOG_START + day_idx * 4  # 0-based row of separator
        for c in range(7):
            s.fmt(sep_r, c, bg=None)   # just touch the cell
        s.box(sep_r, 0, sep_r, 6,
              color=PALETTE["grid"], width=0.8, style="solid")

    s.note(LOG_START, 2,
           "Edit any Food, Calories, Protein, Carbs or Fat cell.\n"
           "The daily totals and weekly summary recompute automatically.",
           kind="note")

    # ── Daily totals table ───────────────────────────────────────────
    # Header at 0-based row TOTALS_START.
    # Data rows at TOTALS_START+1 .. TOTALS_START+7.
    # Each row: SUM of 4 log rows for that day.
    #
    # Log data occupies 1-based sheet rows FIRST_DATA_SHEET .. FIRST_DATA_SHEET+27
    # i.e. sheet rows 7..34  (0-based 6..33).
    #
    # For day k (0-based 0..6):
    #   First log row (1-based) = FIRST_DATA_SHEET + 4*k
    #   Last  log row (1-based) = FIRST_DATA_SHEET + 4*k + 3

    TOTALS_START = LOG_START + 30   # 0-based row 35, sheet row 36

    s.set(TOTALS_START - 1, 8, "Daily Totals")
    s.fmt(TOTALS_START - 1, 8, bold=True, font_color=PALETTE["header"],
          font_size=11)

    tot_headers = ["Day", "Calories", "Protein (g)", "Carbs (g)", "Fat (g)",
                   "Remaining (kcal)"]
    for j, h in enumerate(tot_headers):
        c = 8 + j
        s.set(TOTALS_START, c, h)
        s.fmt(TOTALS_START, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    # Numpy arrays for chart render (pre-computed to match formulas).
    daily_cal_np = np.zeros(7, dtype=float)
    for day_idx in range(7):
        cal_sum = sum(SAMPLE[day_idx * 4 + m][1] for m in range(4))
        daily_cal_np[day_idx] = cal_sum

    day_x_np = np.arange(1, 8, dtype=float)

    for day_idx in range(7):
        r = TOTALS_START + 1 + day_idx  # 0-based

        # 1-based sheet rows of the 4 log rows for this day.
        log_first = FIRST_DATA_SHEET + 4 * day_idx      # 1-based
        log_last  = FIRST_DATA_SHEET + 4 * day_idx + 3  # 1-based

        band = PALETTE["band_alt"] if (day_idx % 2 == 1) else None

        s.set(r, 8, DAY_NAMES[day_idx])
        s.formula(r, 9,  f"=SUM(D{log_first}:D{log_last})")  # Calories
        s.formula(r, 10, f"=SUM(E{log_first}:E{log_last})")  # Protein
        s.formula(r, 11, f"=SUM(F{log_first}:F{log_last})")  # Carbs
        s.formula(r, 12, f"=SUM(G{log_first}:G{log_last})")  # Fat
        # Remaining = goal - daily cal total; clamp at 0 minimum display.
        s.formula(r, 13, f"=$B$4-J{r + 1}")                   # 1-based ref to J col

        s.fmt(r, 8,  align="center", bold=True)
        s.fmt(r, 9,  align="right", number_format="0")
        s.fmt(r, 10, align="right", number_format="0")
        s.fmt(r, 11, align="right", number_format="0")
        s.fmt(r, 12, align="right", number_format="0")
        s.fmt(r, 13, align="right", number_format="0",
              bg=PALETTE["good"] if (DAILY_GOAL - daily_cal_np[day_idx]) >= 0
              else PALETTE["bad"])
        if band:
            s.fmt_range(r, 8, r, 13, bg=band)
            # Re-apply number formats after band overwrite.
            s.fmt(r, 9,  align="right", number_format="0")
            s.fmt(r, 10, align="right", number_format="0")
            s.fmt(r, 11, align="right", number_format="0")
            s.fmt(r, 12, align="right", number_format="0")
            s.fmt(r, 13, align="right", number_format="0")

    s.box(TOTALS_START, 8, TOTALS_START + 7, 13,
          color=PALETTE["header"], width=1.2)

    s.note(TOTALS_START, 13,
           "Remaining = Goal - Daily Calories.\n"
           "Positive = under target; negative = over target.\n"
           "Edit the goal in B4 to update all values.",
           kind="note")

    # ── Weekly summary panel ─────────────────────────────────────────
    # Placed at 0-based rows TOTALS_START..TOTALS_START+6, cols 14..15.
    # 1-based refs to the daily totals column J (col index 9, 0-based).
    # Total rows (1-based): TOTALS_START+2 .. TOTALS_START+8

    first_tot_sheet = TOTALS_START + 2   # 1-based sheet row of day-1 total
    last_tot_sheet  = TOTALS_START + 8   # 1-based sheet row of day-7 total

    s.set(TOTALS_START - 1, 14, "Weekly Summary")
    s.fmt(TOTALS_START - 1, 14, bold=True, font_color=PALETTE["header"],
          font_size=11)

    summary_items = [
        ("Weekly Calorie Total",
         f"=SUM(J{first_tot_sheet}:J{last_tot_sheet})",
         PALETTE["band"]),
        ("Daily Average (kcal)",
         f"=AVERAGE(J{first_tot_sheet}:J{last_tot_sheet})",
         PALETTE["band_alt"]),
        ("Daily Goal (kcal)",
         "=$B$4",
         PALETTE["warn"]),
        ("Weekly Goal (kcal)",
         "=$B$4*7",
         PALETTE["warn"]),
        ("Total Protein (g)",
         f"=SUM(K{first_tot_sheet}:K{last_tot_sheet})",
         PALETTE["band_alt"]),
        ("Total Carbs (g)",
         f"=SUM(L{first_tot_sheet}:L{last_tot_sheet})",
         PALETTE["band_alt"]),
        ("Total Fat (g)",
         f"=SUM(M{first_tot_sheet}:M{last_tot_sheet})",
         PALETTE["band_alt"]),
    ]

    for i, (lbl, expr, fill) in enumerate(summary_items):
        r = TOTALS_START + i
        s.set(r, 14, lbl)
        s.formula(r, 15, expr)
        s.fmt(r, 14, align="left")
        s.fmt(r, 15, bg=fill, align="right", number_format="0", bold=True)

    s.box(TOTALS_START, 14, TOTALS_START + len(summary_items) - 1, 15,
          color=PALETTE["header"], width=1.5)

    s.note(TOTALS_START, 15,
           "Weekly summary references all 7 daily totals.\n"
           "Edit any food entry and these values recalculate.",
           kind="note")

    # ── Designations for chart binding ───────────────────────────────
    # Col I (8) = X axis (day index), Col J (9) = Y axis (daily calories).
    s.designate(8, "X")
    s.designate(9, "Y")

    # ── Bar chart: daily calorie totals ──────────────────────────────
    # 0-based data rows: TOTALS_START+1 .. TOTALS_START+7
    r0_chart = TOTALS_START + 1
    r1_chart = TOTALS_START + 7

    s.chart(
        [Series(
            day_x_np,
            daily_cal_np,
            label="Daily Calories",
            plot_type="Bar",
            color=PALETTE["header"],
            x_col=8,       # 0-based col I (Day label col — numeric index)
            y_col=9,       # 0-based col J (Daily Cal total)
            row_start=r0_chart,
            row_end=r1_chart,
        )],
        at=(10, 380),
        size=(500, 280),
        title="Daily Calorie Totals vs Goal",
        xlabel="Day",
        ylabel="Calories (kcal)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    # Simple energy balance equation.
    s.equation(
        r"\Delta E = E_{\mathrm{in}} - E_{\mathrm{out}}",
        at=(520, 380),
        fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.2,
        size=(260, 54),
    )

    # ── Save ─────────────────────────────────────────────────────────
    out_dir = os.path.join(_HERE, "templates", "Daily Life")
    out = os.path.join(out_dir, "Calorie Tracker.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
