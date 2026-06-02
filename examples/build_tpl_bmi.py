"""Build the "BMI Calculator" daily-life template .ksheet file.

A polished, fully formula-driven Body Mass Index calculator with:
  - Editable metric inputs (weight kg, height m)
  - Optional imperial inputs (lbs, ft + in) with auto-conversion formulas
  - Live BMI result cell driven by =weight/height^2
  - Category via nested IF (Underweight/Normal/Overweight/Obese)
  - WHO reference table with banded colour coding
  - Live bar chart of category upper boundaries
  - LaTeX equation and instructive sticky notes

Run:  python examples/build_tpl_bmi.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ---------------------------------------------------------------------------
# Colour constants
# ---------------------------------------------------------------------------
UNDERWEIGHT_CLR = "#bdd7ee"   # light blue
NORMAL_CLR      = "#c6efce"   # green
OVERWEIGHT_CLR  = "#ffeb9c"   # amber
OBESE_CLR       = "#ffc7ce"   # red/pink
AMBER_INPUT     = "#fff2cc"   # amber input fill


def build() -> str:
    wb = Workbook(min_rows=46, min_cols=14)
    s = wb.add_sheet("BMI Calculator")

    # ------------------------------------------------------------------ #
    # Column widths                                                        #
    # ------------------------------------------------------------------ #
    s.col_width(0, 180)   # labels
    s.col_width(1, 110)   # metric values
    s.col_width(2, 80)    # units
    s.col_width(3, 30)    # spacer
    s.col_width(4, 160)   # summary labels
    s.col_width(5, 120)   # summary values

    # ------------------------------------------------------------------ #
    # Title block                                                          #
    # ------------------------------------------------------------------ #
    s.title_block(
        "BMI Calculator",
        "Body Mass Index — WHO Classification (adults 18+)",
        row=0, col=0, span=6,
    )

    # ------------------------------------------------------------------ #
    # INPUT PANEL  (rows 3–9, cols 0–2)                                   #
    # ------------------------------------------------------------------ #
    # Section heading
    s.set(3, 0, "Metric Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"], font_size=11)

    # Weight row  (row=4, col=1 => sheet B5)
    s.set(4, 0, "Body weight")
    s.set(4, 1, 70.0)                      # default: 70 kg
    s.set(4, 2, "kg")
    s.fmt(4, 1, bg=AMBER_INPUT, align="center", number_format="0.0")
    s.fmt(4, 0, align="left")
    s.fmt(4, 2, align="left", italic=True, font_color="#555555")

    # Height row  (row=5, col=1 => sheet B6)
    s.set(5, 0, "Height")
    s.set(5, 1, 1.75)                      # default: 1.75 m
    s.set(5, 2, "m")
    s.fmt(5, 1, bg=AMBER_INPUT, align="center", number_format="0.00")
    s.fmt(5, 0, align="left")
    s.fmt(5, 2, align="left", italic=True, font_color="#555555")

    # Box around metric inputs
    s.box(4, 0, 5, 2, color=PALETTE["accent"], width=1.5)
    s.note(4, 1,
           "Edit weight (kg) here.\n"
           "BMI, category and chart all update automatically.",
           kind="note")
    s.note(5, 1,
           "Edit height (m) here (e.g. 1.75 for 175 cm).",
           kind="note")

    # Imperial inputs section  (rows 7–9)
    s.set(7, 0, "Imperial Inputs (optional)")
    s.fmt(7, 0, bold=True, font_color=PALETTE["accent"], font_size=11)

    s.set(8, 0, "Weight (lbs)")
    s.set(8, 1, 154.0)                     # 70 kg ≈ 154 lbs default
    s.set(8, 2, "lbs")
    s.fmt(8, 1, bg=AMBER_INPUT, align="center", number_format="0.0")
    s.fmt(8, 2, align="left", italic=True, font_color="#555555")

    s.set(9, 0, "Height (ft)")
    s.set(9, 1, 5.0)                       # 5 ft
    s.set(9, 2, "ft")
    s.fmt(9, 1, bg=AMBER_INPUT, align="center", number_format="0.0")
    s.fmt(9, 2, align="left", italic=True, font_color="#555555")

    s.set(10, 0, "Height (in)")
    s.set(10, 1, 9.0)                      # 9 in => 5'9" = 1.753 m
    s.set(10, 2, "in")
    s.fmt(10, 1, bg=AMBER_INPUT, align="center", number_format="0.0")
    s.fmt(10, 2, align="left", italic=True, font_color="#555555")

    # Imperial → metric conversion formulas
    # weight_kg from lbs: =B9/2.20462   (B9 = row 8, col 1)
    # height_m from ft+in: =(B10*12+B11)*0.0254  (B10=row9,col1; B11=row10,col1)
    s.set(11, 0, "  ↳ kg (from lbs)")
    s.formula(11, 1, "=B9/2.20462")
    s.fmt(11, 1, bg=PALETTE["band"], align="center", number_format="0.00")
    s.fmt(11, 0, italic=True, font_color="#555555")

    s.set(12, 0, "  ↳ m (from ft + in)")
    s.formula(12, 1, "=(B10*12+B11)*0.0254")
    s.fmt(12, 1, bg=PALETTE["band"], align="center", number_format="0.00")
    s.fmt(12, 0, italic=True, font_color="#555555")

    s.box(8, 0, 12, 2, color="#999999", width=1.0)
    s.note(8, 0,
           "Optional: enter imperial values here.\n"
           "The converted kg/m values appear below.\n"
           "Copy them manually to B5/B6 if you prefer imperial.",
           kind="note")

    # ------------------------------------------------------------------ #
    # RESULT PANEL  (rows 14–18, cols 0–5)                                #
    # ------------------------------------------------------------------ #
    # Section heading
    s.set(14, 0, "Result")
    s.fmt(14, 0, bold=True, font_color=PALETTE["header"], font_size=12)

    # BMI value — big cell
    # BMI = weight / height^2  => =B5/(B6^2)
    # B5 = row4,col1; B6 = row5,col1
    s.formula(15, 1, "=B5/(B6*B6)")
    s.fmt(15, 1, bold=True, font_size=28, align="center",
          number_format="0.00", bg=PALETTE["band"])
    s.merge(15, 1, 2, 2)
    s.set(15, 0, "BMI")
    s.fmt(15, 0, bold=True, font_size=18, align="right",
          font_color=PALETTE["header"])
    s.merge(15, 0, 2, 1)

    # Category via nested IF
    # Thresholds: <18.5 Underweight, <25 Normal, <30 Overweight, else Obese
    # Reference cell: C16 (row=15, col=2) holds the BMI formula above in merged
    # Actually BMI is in B16 (row=15, col=1).  Nested IF:
    cat_formula = (
        '=IF(B16<18.5,"Underweight",'
        'IF(B16<25,"Normal weight",'
        'IF(B16<30,"Overweight","Obese")))'
    )
    s.formula(17, 1, cat_formula)
    s.fmt(17, 1, bold=True, font_size=16, align="center",
          bg=NORMAL_CLR)
    s.merge(17, 1, 1, 2)
    s.set(17, 0, "Category")
    s.fmt(17, 0, bold=True, font_size=13, align="right",
          font_color=PALETTE["header"])

    # Box around result block
    s.box(15, 0, 18, 3, color=PALETTE["header"], width=2.0)

    # ------------------------------------------------------------------ #
    # QUICK STATS panel  (rows 14–18, cols 4–5)                           #
    # ------------------------------------------------------------------ #
    s.set(14, 4, "Quick Reference")
    s.fmt(14, 4, bold=True, font_color=PALETTE["header"], font_size=11)

    stats = [
        ("Healthy BMI range", "18.5 – 24.9"),
        ("Your weight (kg)", "=B5"),
        ("Your height (m)", "=B6"),
        ("BMI (kg/m²)", "=B16"),
        ("Healthy weight min (kg)", "=ROUND(18.5*B6*B6,1)"),
        ("Healthy weight max (kg)", "=ROUND(24.9*B6*B6,1)"),
    ]
    for i, (lbl, val) in enumerate(stats):
        r = 15 + i
        s.set(r, 4, lbl)
        s.fmt(r, 4, align="left", font_size=10)
        if isinstance(val, str) and val.startswith("="):
            s.formula(r, 5, val)
        else:
            s.set(r, 5, val)
        s.fmt(r, 5, bold=True, align="center", font_size=10,
              bg=PALETTE["band_alt"])

    s.box(15, 4, 20, 5, color=PALETTE["header"], width=1.0)
    s.col_width(4, 200)
    s.col_width(5, 160)

    # ------------------------------------------------------------------ #
    # WHO REFERENCE TABLE  (rows 21–26, cols 0–3)                         #
    # Header at row 21 (0-based), data rows 22–26                         #
    # ------------------------------------------------------------------ #
    s.set(20, 0, "WHO BMI Classification (Adults 18+)")
    s.fmt(20, 0, bold=True, font_color=PALETTE["header"], font_size=11)
    s.merge(20, 0, 1, 4)

    who_headers = ["Category", "BMI Range", "Upper Limit", "Risk Level"]
    who_rows = [
        # col0: label, col1: range string, col2: upper limit (numeric), col3: risk
        ["Underweight",   "< 18.5",   18.5,  "Increased"],
        ["Normal weight", "18.5 – 24.9", 24.9, "Minimal"],
        ["Overweight",    "25.0 – 29.9", 29.9, "Increased"],
        ["Obese class I", "30.0 – 34.9", 34.9, "High"],
        ["Obese class II","35.0 – 39.9", 39.9, "Very high"],
        ["Obese class III","≥ 40",       45.0, "Extremely high"],
    ]

    # Write the table manually for full colour control
    tbl_start = 21
    for j, h in enumerate(who_headers):
        s.set(tbl_start, j, h)
        s.fmt(tbl_start, j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    # Category colour map
    row_colours = [
        UNDERWEIGHT_CLR,
        NORMAL_CLR,
        OVERWEIGHT_CLR,
        "#ffc7ce",   # red-ish for obese I
        "#ff9999",   # stronger red for obese II
        "#ff6666",   # darkest red for obese III
    ]
    for i, (row_data, bg) in enumerate(zip(who_rows, row_colours)):
        r = tbl_start + 1 + i
        for j, v in enumerate(row_data):
            if isinstance(v, float):
                s.set(r, j, v)
                s.fmt(r, j, bg=bg, align="center", number_format="0.0")
            else:
                s.set(r, j, v)
                s.fmt(r, j, bg=bg, align="left" if j == 0 else "center")

    s.box(tbl_start, 0, tbl_start + len(who_rows), 3,
          color=PALETTE["header"], width=1.0, inner=True)
    s.col_width(1, 110)
    s.col_width(2, 90)
    s.col_width(3, 110)

    # Designate cols for chart: col 0=category labels (X), col 2=upper limit (Y)
    s.designate(0, "X")
    s.designate(2, "Y")

    # ------------------------------------------------------------------ #
    # BAR CHART of category upper-limit boundaries                         #
    # Live-bound to col 2 (upper limit), rows 22–27 (0-based 22..27)      #
    # ------------------------------------------------------------------ #
    cat_labels = [r[0] for r in who_rows]
    upper_limits = np.array([r[2] for r in who_rows], dtype=float)
    # x is just the category index for a bar chart
    x_idx = np.arange(len(upper_limits), dtype=float)

    # Data rows in 0-based: tbl_start+1 .. tbl_start+len(who_rows)
    row_s = tbl_start + 1
    row_e = tbl_start + len(who_rows)

    s.chart(
        [Series(
            x=x_idx,
            y=upper_limits,
            label="Upper BMI limit",
            plot_type="Bar",
            color=PALETTE["header"],
            y_col=2,          # 0-based col 2 = "Upper Limit"
            row_start=row_s,
            row_end=row_e,
        )],
        at=(500, 240),
        size=(430, 280),
        title="WHO BMI Category Boundaries",
        xlabel="Category",
        ylabel="BMI (kg/m²)",
        grid=True,
        legend=False,
    )

    # ------------------------------------------------------------------ #
    # LaTeX equation                                                       #
    # ------------------------------------------------------------------ #
    s.equation(
        r"BMI = \frac{m \; [\mathrm{kg}]}{h^{2} \; [\mathrm{m}^{2}]}",
        at=(500, 140),
        fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(320, 60),
    )

    # ------------------------------------------------------------------ #
    # Extra instructive note                                               #
    # ------------------------------------------------------------------ #
    s.note(14, 4,
           "Healthy weight range is calculated from your height.\n"
           "Edit B5 (weight) or B6 (height) to see all values update.",
           kind="note")

    # ------------------------------------------------------------------ #
    # Save                                                                 #
    # ------------------------------------------------------------------ #
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Daily Life",
    )
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "BMI Calculator.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
