"""Build "Ohms Law and Resistor Networks" exercise .ksheet for Year-1 physics.

Two sheets:
  - "Problem"  : title block, problem statement, editable amber inputs,
                 numbered tasks (series + parallel), blank answer cells.
  - "Solution" : self-contained editable inputs, full live-formula solution
                 (series and parallel analysis), banded results tables,
                 a data-bound Bar chart (power per resistor), and validated
                 mathtext equations.

Run:  python examples/build_ohms_law_exercise.py

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
# Nominal values (used for chart initial render only -- cells are formulas)
# ---------------------------------------------------------------------------
V_NOM  = 12.0   # Supply voltage  (V)
R1_NOM = 100.0  # R1 (Ohm)
R2_NOM = 220.0  # R2 (Ohm)
R3_NOM = 330.0  # R3 (Ohm)

# Derived (series)
Rs_nom = R1_NOM + R2_NOM + R3_NOM
Is_nom = V_NOM / Rs_nom
Ps_nom = V_NOM ** 2 / Rs_nom
V1s_nom = Is_nom * R1_NOM
V2s_nom = Is_nom * R2_NOM
V3s_nom = Is_nom * R3_NOM
P1s_nom = Is_nom ** 2 * R1_NOM
P2s_nom = Is_nom ** 2 * R2_NOM
P3s_nom = Is_nom ** 2 * R3_NOM

# Derived (parallel)
Rp_nom = 1.0 / (1.0/R1_NOM + 1.0/R2_NOM + 1.0/R3_NOM)
Ip_nom = V_NOM / Rp_nom
I1p_nom = V_NOM / R1_NOM
I2p_nom = V_NOM / R2_NOM
I3p_nom = V_NOM / R3_NOM
P1p_nom = V_NOM ** 2 / R1_NOM
P2p_nom = V_NOM ** 2 / R2_NOM
P3p_nom = V_NOM ** 2 / R3_NOM


def _build_problem(wb: Workbook):
    """Sheet 1: Problem statement + blank answer cells."""
    s = wb.add_sheet("Problem")

    # ── Column widths ──────────────────────────────────────────────────
    s.col_width(0, 40)   # narrow left margin
    s.col_width(1, 220)  # task / label column
    s.col_width(2, 120)  # your answer
    s.col_width(3, 60)   # units

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block(
        "Ohm's Law and Resistor Networks",
        "Year 1 Physics Exercise  |  Series and Parallel DC Circuits",
        row=0, col=1, span=7,
    )

    # ── Problem statement ──────────────────────────────────────────────
    s.set(3, 1, "Problem Statement")
    s.fmt(3, 1, bold=True, font_size=12, font_color=PALETTE["header"])
    s.merge(3, 1, 1, 6)

    stmt_lines = [
        ("A DC power supply of voltage V is connected to three resistors "
         "R₁, R₂ and R₃."),
        ("You will analyse the circuit in two configurations:"),
        ("  (a) Series connection  —  all three resistors wired end-to-end "
         "between the supply terminals."),
        ("  (b) Parallel connection  —  all three resistors connected directly "
         "across the supply terminals."),
        ("Apply Ohm’s Law (V = IR) and the standard series / parallel rules "
         "to find the quantities listed in the Tasks section below."),
    ]
    for i, line in enumerate(stmt_lines):
        s.set(4 + i, 1, line)
        s.fmt(4 + i, 1, italic=(i in (0, 4)), wrap=True)
        s.merge(4 + i, 1, 1, 6)

    s.box(3, 1, 9, 7, color=PALETTE["grid"], width=1.0)

    # ── Given inputs (amber) ───────────────────────────────────────────
    s.set(11, 1, "Given Inputs")
    s.fmt(11, 1, bold=True, font_size=11, font_color=PALETTE["header"])
    s.merge(11, 1, 1, 5)

    inputs = [
        ("Supply voltage  V",    "V",    V_NOM),
        ("Resistance  R₁",  "Ω", R1_NOM),
        ("Resistance  R₂",  "Ω", R2_NOM),
        ("Resistance  R₃",  "Ω", R3_NOM),
    ]
    for i, (label, unit, val) in enumerate(inputs):
        r = 12 + i
        s.set(r, 1, label)
        s.fmt(r, 1, align="left")
        s.set(r, 2, val)
        s.fmt(r, 2, bg=PALETTE["warn"], align="center",
              number_format="0.0", bold=True)
        s.set(r, 3, unit)
        s.fmt(r, 3, align="left")

    s.box(12, 1, 15, 3, color=PALETTE["accent"], width=1.5)
    s.note(12, 2,
           "Edit these amber cells to change the circuit values.",
           kind="note")

    # ── Tasks ──────────────────────────────────────────────────────────
    s.set(17, 1, "Tasks")
    s.fmt(17, 1, bold=True, font_size=11, font_color=PALETTE["header"])
    s.merge(17, 1, 1, 6)

    # Header row for the answer table
    for c, hdr in enumerate(
            ["#", "Quantity to find", "Your Answer", "Unit"], start=1):
        s.set(18, c, hdr)
        s.fmt(18, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    tasks = [
        # (task_no, label, unit)
        ("1",  "SERIES: Total resistance  Rₛ",                "Ω"),
        ("2",  "SERIES: Total current     Iₛ",                "A"),
        ("3",  "SERIES: Total power       Pₛ",                "W"),
        ("4",  "SERIES: Voltage across R₁",                   "V"),
        ("5",  "SERIES: Voltage across R₂",                   "V"),
        ("6",  "SERIES: Voltage across R₃",                   "V"),
        ("",   "",                                                  ""),
        ("7",  "PARALLEL: Total resistance Rₚ",               "Ω"),
        ("8",  "PARALLEL: Total current   Iₚ",                "A"),
        ("9",  "PARALLEL: Branch current through R₁",         "A"),
        ("10", "PARALLEL: Branch current through R₂",         "A"),
        ("11", "PARALLEL: Branch current through R₃",         "A"),
    ]
    for i, (num, lbl, unit) in enumerate(tasks):
        r = 19 + i
        band = PALETTE["band_alt"] if (i % 2 == 0) else None
        s.set(r, 1, num)
        s.fmt(r, 1, bold=(num != ""), align="center",
              bg=(band if band else None))
        s.set(r, 2, lbl)
        s.fmt(r, 2, align="left",
              bg=(band if band else None))
        # Blank "Your Answer" cell — intentionally left empty
        s.fmt(r, 3, bg="#f5f5f5", align="center")
        s.set(r, 4, unit)
        s.fmt(r, 4, align="left",
              bg=(band if band else None))

    s.box(18, 1, 19 + len(tasks) - 1, 4,
          color=PALETTE["header"], width=1.0)

    # Separator row between series and parallel
    sep_r = 19 + 6  # the blank divider row
    s.fmt_range(sep_r, 1, sep_r, 4, bg="#d0d0d0")

    s.note(17, 2,
           "Fill in the 'Your Answer' column. "
           "Then open the Solution sheet to check your work.",
           kind="note")


def _build_solution(wb: Workbook):
    """Sheet 2: Self-contained solution with live formulas + chart."""
    s = wb.add_sheet("Solution")

    # ── Column widths ──────────────────────────────────────────────────
    s.col_width(0, 30)   # left margin
    s.col_width(1, 220)  # label
    s.col_width(2, 110)  # value
    s.col_width(3, 60)   # units
    s.col_width(4, 30)   # gap
    s.col_width(5, 180)  # summary label
    s.col_width(6, 110)  # summary value
    s.col_width(7, 60)   # summary units

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block(
        "Ohm's Law and Resistor Networks — Full Solution",
        "Series and Parallel DC Circuit Analysis",
        row=0, col=1, span=7,
    )

    # ── Inputs (self-contained editable amber cells) ───────────────────
    # Placed at rows 3-6 (0-based) => sheet rows 4-7 (1-based)
    # => absolute refs: $C$4, $C$5, $C$6, $C$7
    s.set(2, 1, "Given Inputs")
    s.fmt(2, 1, bold=True, font_color=PALETTE["accent"], font_size=11)

    inputs = [
        ("Supply voltage V",   V_NOM,  "V"),
        ("Resistance R₁", R1_NOM, "Ω"),
        ("Resistance R₂", R2_NOM, "Ω"),
        ("Resistance R₃", R3_NOM, "Ω"),
    ]
    # rows 3,4,5,6 (0-based) => sheet C4,C5,C6,C7
    for i, (lbl, val, unit) in enumerate(inputs):
        r = 3 + i
        s.set(r, 1, lbl)
        s.fmt(r, 1, align="left")
        s.set(r, 2, val)
        s.fmt(r, 2, bg=PALETTE["warn"], align="center",
              number_format="0.0", bold=True)
        s.set(r, 3, unit)
        s.fmt(r, 3, align="left")

    s.box(3, 1, 6, 3, color=PALETTE["accent"], width=1.5)
    s.note(3, 2,
           "Edit V, R1, R2, R3 here. All derived quantities "
           "below update automatically via live formulas.",
           kind="note")

    # Absolute refs for the four inputs (1-based: row 4-7, col C=3):
    #   V  => $C$4,  R1 => $C$5,  R2 => $C$6,  R3 => $C$7
    V_ref  = "$C$4"
    R1_ref = "$C$5"
    R2_ref = "$C$6"
    R3_ref = "$C$7"

    # ── SERIES ANALYSIS ────────────────────────────────────────────────
    s.set(8, 1, "Series Connection")
    s.fmt(8, 1, bold=True, font_size=12, font_color=PALETTE["header"])
    s.merge(8, 1, 1, 5)

    series_items = [
        # (label, formula, unit)
        ("Total resistance  Rₛ = R₁ + R₂ + R₃",
         f"={R1_ref}+{R2_ref}+{R3_ref}",
         "Ω"),
        # Rs is in row 10 (0-based), which is sheet row 11, col C => $C$11
        ("Series current  Iₛ = V / Rₛ",
         f"={V_ref}/$C$11",
         "A"),
        ("Total power  Pₛ = V² / Rₛ",
         f"={V_ref}*{V_ref}/$C$11",
         "W"),
        ("Voltage across R₁  V₁ = V·R₁/Rₛ",
         f"={V_ref}*{R1_ref}/$C$11",
         "V"),
        ("Voltage across R₂  V₂ = V·R₂/Rₛ",
         f"={V_ref}*{R2_ref}/$C$11",
         "V"),
        ("Voltage across R₃  V₃ = V·R₃/Rₛ",
         f"={V_ref}*{R3_ref}/$C$11",
         "V"),
        ("Power in R₁  P₁ = V²·R₁/Rₛ²",
         f"={V_ref}*{V_ref}*{R1_ref}/($C$11*$C$11)",
         "W"),
        ("Power in R₂  P₂ = V²·R₂/Rₛ²",
         f"={V_ref}*{V_ref}*{R2_ref}/($C$11*$C$11)",
         "W"),
        ("Power in R₃  P₃ = V²·R₃/Rₛ²",
         f"={V_ref}*{V_ref}*{R3_ref}/($C$11*$C$11)",
         "W"),
    ]
    # series_items[0] => row 9 (0-based) => sheet row 10 => BUT we said
    # Rs is at $C$11 (sheet row 11). Let's start at row 9 (0-based):
    #   row 9  => sheet row 10  => WRONG — we referenced $C$11 for Rs.
    # Re-check: start_row=9 (0-based), first data row = row 10 (0-based)
    # => sheet row 11 => $C$11 for Rs. Good.
    # Actually: we set items starting at row index 9 (0-based):
    #   i=0 => r=9  => sheet row 10 => C10 (not $C$11)
    # Need to reconcile. Let's start series at row 10 (0-based):
    #   i=0 => r=10 => sheet row 11 => $C$11  ✓ (Rs)
    #   i=1 => r=11 => sheet row 12 => $C$12  ✓ (Is)
    # This matches the $C$11/$C$12 refs above. Good.

    for i, (lbl, formula, unit) in enumerate(series_items):
        r = 10 + i
        band = PALETTE["band_alt"] if (i % 2 == 1) else None
        s.set(r, 1, lbl)
        s.fmt(r, 1, align="left", bg=(band if band else None))
        s.formula(r, 2, formula)
        s.fmt(r, 2, align="center", number_format="0.000",
              bg=(band if band else None))
        s.set(r, 3, unit)
        s.fmt(r, 3, align="left", bg=(band if band else None))

    s.box(9, 1, 10 + len(series_items) - 1, 3,
          color=PALETTE["header"], width=1.0)

    # ── PARALLEL ANALYSIS ──────────────────────────────────────────────
    par_start = 10 + len(series_items) + 2   # two blank rows gap
    s.set(par_start - 1, 1, "Parallel Connection")
    s.fmt(par_start - 1, 1, bold=True, font_size=12,
          font_color=PALETTE["header"])
    s.merge(par_start - 1, 1, 1, 5)

    # par_start (0-based) => sheet row par_start+1
    # Rp ref: $C${par_start+1}
    # Ip ref: $C${par_start+2}
    Rp_sheet_row = par_start + 1   # 1-based
    Ip_sheet_row = par_start + 2

    parallel_items = [
        (f"Total resistance  1/Rₚ = 1/R₁ + 1/R₂ + 1/R₃",
         f"=1/(1/{R1_ref}+1/{R2_ref}+1/{R3_ref})",
         "Ω"),
        (f"Total current  Iₚ = V / Rₚ",
         f"={V_ref}/$C${Rp_sheet_row}",
         "A"),
        (f"Branch current through R₁  I₁ = V / R₁",
         f"={V_ref}/{R1_ref}",
         "A"),
        (f"Branch current through R₂  I₂ = V / R₂",
         f"={V_ref}/{R2_ref}",
         "A"),
        (f"Branch current through R₃  I₃ = V / R₃",
         f"={V_ref}/{R3_ref}",
         "A"),
        (f"Power in R₁  P₁ = V² / R₁",
         f"={V_ref}*{V_ref}/{R1_ref}",
         "W"),
        (f"Power in R₂  P₂ = V² / R₂",
         f"={V_ref}*{V_ref}/{R2_ref}",
         "W"),
        (f"Power in R₃  P₃ = V² / R₃",
         f"={V_ref}*{V_ref}/{R3_ref}",
         "W"),
    ]

    for i, (lbl, formula, unit) in enumerate(parallel_items):
        r = par_start + i
        band = PALETTE["band_alt"] if (i % 2 == 1) else None
        s.set(r, 1, lbl)
        s.fmt(r, 1, align="left", bg=(band if band else None))
        s.formula(r, 2, formula)
        s.fmt(r, 2, align="center", number_format="0.000",
              bg=(band if band else None))
        s.set(r, 3, unit)
        s.fmt(r, 3, align="left", bg=(band if band else None))

    s.box(par_start, 1, par_start + len(parallel_items) - 1, 3,
          color=PALETTE["header"], width=1.0)

    # ── SUMMARY TABLE ──────────────────────────────────────────────────
    # A compact side-by-side comparison (right of the inputs)
    # Placed at columns 5-7 (0-based), rows 8 onwards
    # We'll use the already-computed formula cells via cross-refs.
    #
    # series row refs (0-based rows -> 1-based):
    # Rs: row10 C11,  Is: row11 C12,  Ps: row12 C13
    # V1s: row13 C14, V2s: row14 C15, V3s: row15 C16
    #
    # parallel row refs:
    # par_start = 10+9+2 = 21 (0-based), Rp: C22, Ip: C23
    # I1p: C24, I2p: C25, I3p: C26

    Rs_c  = "$C$11"
    Is_c  = "$C$12"
    Ps_c  = "$C$13"
    V1s_c = "$C$14"
    V2s_c = "$C$15"
    V3s_c = "$C$16"
    P1s_c = "$C$17"
    P2s_c = "$C$18"
    P3s_c = "$C$19"

    Rp_c  = f"$C${Rp_sheet_row}"
    Ip_c  = f"$C${Ip_sheet_row}"
    I1p_c = f"$C${Ip_sheet_row+1}"
    I2p_c = f"$C${Ip_sheet_row+2}"
    I3p_c = f"$C${Ip_sheet_row+3}"
    P1p_c = f"$C${Ip_sheet_row+4}"
    P2p_c = f"$C${Ip_sheet_row+5}"
    P3p_c = f"$C${Ip_sheet_row+6}"

    summ_start = 8
    s.set(summ_start, 5, "Summary")
    s.fmt(summ_start, 5, bold=True, font_size=12,
          font_color=PALETTE["header"])
    s.merge(summ_start, 5, 1, 3)

    summ_headers = ["Quantity", "Series", "Parallel"]
    for j, h in enumerate(summ_headers):
        s.set(summ_start + 1, 5 + j, h)
        s.fmt(summ_start + 1, 5 + j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    summ_rows = [
        # (label, series_formula, parallel_formula)
        ("R_total (Ω)",   f"={Rs_c[1:]}",       f"={Rp_c[1:]}"),
        ("I_total (A)",   f"={Is_c[1:]}",       f"={Ip_c[1:]}"),
        ("P_total (W)",   f"={Ps_c[1:]}",       f"={V_ref}*{V_ref}/{Rp_c[1:]}"),
        ("V across R₁ (V)", f"={V1s_c[1:]}",   f"={V_ref}"),
        ("I through R₁ (A)", f"={Is_c[1:]}",   f"={I1p_c[1:]}"),
        ("I through R₂ (A)", f"={Is_c[1:]}",   f"={I2p_c[1:]}"),
    ]
    for i, (lbl, s_ref, p_ref) in enumerate(summ_rows):
        r = summ_start + 2 + i
        band = PALETTE["band_alt"] if (i % 2 == 1) else None
        s.set(r, 5, lbl)
        s.fmt(r, 5, align="left", bg=(band if band else None))
        # Series value
        if s_ref.startswith("="):
            s.formula(r, 6, s_ref)
        else:
            s.formula(r, 6, f"={s_ref[1:]}")  # strip leading $, add =
        s.fmt(r, 6, align="center", number_format="0.000",
              bg=(band if band else None))
        # Parallel value
        if p_ref.startswith("="):
            s.formula(r, 7, p_ref)
        else:
            s.formula(r, 7, f"={p_ref[1:]}")
        s.fmt(r, 7, align="center", number_format="0.000",
              bg=(band if band else None))

    s.box(summ_start + 1, 5,
          summ_start + 1 + len(summ_rows), 7,
          color=PALETTE["header"], width=1.0)
    s.note(summ_start + 1, 5,
           "Side-by-side comparison. Note how Rp << Rs: "
           "parallel networks have lower resistance than any branch.",
           kind="note")

    # ── CHART: Power per resistor (series vs parallel) ─────────────────
    # We'll put a small data table for the chart at rows par_start+10..+12
    # (0-based), columns 5-7, then bind the chart to those columns.
    #
    # chart_data_start (0-based) such that rows are well below all content
    chart_data_start = par_start + len(parallel_items) + 3

    # X labels: R1, R2, R3 (stored as 1, 2, 3 for numeric x-axis)
    s.set(chart_data_start, 5, "Chart Data")
    s.fmt(chart_data_start, 5, bold=True, font_color=PALETTE["header"])

    chart_headers = ["Resistor #", "P series (W)", "P parallel (W)"]
    for j, h in enumerate(chart_headers):
        s.set(chart_data_start + 1, 5 + j, h)
        s.fmt(chart_data_start + 1, 5 + j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    # Three data rows (R1, R2, R3), 0-based rows chart_data_start+2/3/4
    chart_rows = [
        (1, P1s_c, P1p_c),
        (2, P2s_c, P2p_c),
        (3, P3s_c, P3p_c),
    ]
    for i, (res_num, ps_ref, pp_ref) in enumerate(chart_rows):
        r = chart_data_start + 2 + i
        s.set(r, 5, res_num)
        s.fmt(r, 5, align="center")
        s.formula(r, 6, f"={ps_ref[1:]}")
        s.fmt(r, 6, align="center", number_format="0.000")
        s.formula(r, 7, f"={pp_ref[1:]}")
        s.fmt(r, 7, align="center", number_format="0.000")

    s.box(chart_data_start + 1, 5,
          chart_data_start + 4, 7,
          color=PALETTE["header"], width=1.0)

    # Designate columns for the chart (0-based cols 5=X, 6=Y, 7=Y)
    s.designate(5, "X")
    s.designate(6, "Y")
    s.designate(7, "Y")

    # Live binding: x_col=5, y_col=6/7; rows chart_data_start+2 .. +4
    r0 = chart_data_start + 2
    r1 = chart_data_start + 4

    # Initial render arrays matching the formulas
    x_arr = np.array([1.0, 2.0, 3.0])
    y_series = np.array([P1s_nom, P2s_nom, P3s_nom])
    y_parallel = np.array([P1p_nom, P2p_nom, P3p_nom])

    s.chart(
        [
            Series(x_arr, y_series, "Series", "Bar",
                   color=PALETTE["header"],
                   x_col=5, y_col=6, row_start=r0, row_end=r1),
            Series(x_arr, y_parallel, "Parallel", "Bar",
                   color=PALETTE["accent"],
                   x_col=5, y_col=7, row_start=r0, row_end=r1),
        ],
        at=(530, 10), size=(430, 280),
        title="Power dissipated per resistor",
        xlabel="Resistor (1=R₁, 2=R₂, 3=R₃)",
        ylabel="Power (W)",
        grid=True, legend=True,
    )

    # ── Mathtext equations ─────────────────────────────────────────────
    # 1. Ohm's Law
    s.equation(
        r"V = I \, R",
        at=(530, 310), fontsize=20, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(120, 46),
    )

    # 2. Power dissipation
    s.equation(
        r"P = \frac{V^{2}}{R} = I^{2} R",
        at=(665, 310), fontsize=18, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["accent"],
        border_width=1.2, size=(215, 46),
    )

    # 3. Parallel resistance rule
    s.equation(
        r"\frac{1}{R_{p}} = \frac{1}{R_{1}} + \frac{1}{R_{2}} + \frac{1}{R_{3}}",
        at=(530, 372), fontsize=17, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(355, 50),
    )

    s.note(0, 0,
           "Solution sheet: change V, R1, R2, or R3 and every derived "
           "quantity updates. The chart also reflects the new powers.",
           kind="note")


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=14)
    _build_problem(wb)
    _build_solution(wb)

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "exercises", "Year 1",
        "Ohms Law and Resistor Networks.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
