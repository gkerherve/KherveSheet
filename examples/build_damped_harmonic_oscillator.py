"""Build "Damped Harmonic Oscillator" -- a Year-2 undergraduate physics exercise.

Two-sheet workbook:
  - Sheet 1 "Problem": problem statement, editable amber inputs, numbered tasks
    with blank answer cells (students fill these in).
  - Sheet 2 "Solution": self-contained copy of inputs, all derived quantities
    as live formulas, a banded time-displacement table, data-bound chart of
    x(t) and the decay envelope, and a mathtext equation panel.

Row/column mapping (0-based Python -> 1-based A1):
  Solution inputs at col 2 (C):
    C5 = m  (0-based row 4)
    C6 = k  (0-based row 5)
    C7 = b  (0-based row 6)
    C8 = A0 (0-based row 7)
  Derived at col 2 (C):
    C11 = omega0  (0-based row 10)
    C12 = gamma   (0-based row 11)
    C13 = zeta    (0-based row 12)
    C14 = omega_d (0-based row 13)
    C15 = Td      (0-based row 14)  <- references C14

Run:  python examples/build_damped_harmonic_oscillator.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Make the project importable.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, Series, PALETTE   # noqa: E402


# ---------------------------------------------------------------------------
# Physical parameters (match the editable input cells exactly).
# ---------------------------------------------------------------------------
M   = 0.5    # kg
K   = 50.0   # N/m
B   = 0.7    # kg/s
A0  = 0.1    # m

omega0  = np.sqrt(K / M)
gamma   = B / (2 * M)
zeta    = B / (2 * np.sqrt(K * M))
omega_d = np.sqrt(K / M - (B / (2 * M)) ** 2)
Td      = 2 * np.pi / omega_d

N_POINTS = 60
t_max = 4 * Td
t_arr = np.linspace(0.0, t_max, N_POINTS)
x_arr = A0 * np.exp(-gamma * t_arr) * np.cos(omega_d * t_arr)
env_p = A0 * np.exp(-gamma * t_arr)
env_n = -env_p


def build() -> str:
    wb = Workbook(min_rows=85, min_cols=16)

    # ====================================================================
    # SHEET 1: Problem
    # ====================================================================
    p = wb.add_sheet("Problem")

    # --- Title block ---
    p.title_block(
        "Damped Harmonic Oscillator",
        "Year 2 Physics -- Classical Mechanics & Oscillations",
        span=10,
    )

    # --- Problem statement (row 2, merged) ---
    statement = (
        "A mass m is attached to a spring of stiffness k and subject to "
        "linear damping with coefficient b. It is released from rest at "
        "displacement A0 at t = 0. Neglect all other forces."
    )
    p.set(2, 0, statement)
    p.fmt(2, 0, italic=True, wrap=True, font_color="#333333")
    p.merge(2, 0, 1, 10)
    p.col_width(0, 220)

    # --- Given (reference inputs, amber) ---
    p.set(4, 0, "Given")
    p.fmt(4, 0, bold=True, font_size=13, font_color=PALETTE["accent"])

    given = [
        ("m",   "Mass",                   M,   "kg"),
        ("k",   "Spring stiffness",       K,   "N/m"),
        ("b",   "Damping coefficient",    B,   "kg/s"),
        ("A0",  "Initial amplitude",      A0,  "m"),
    ]
    for j, h in enumerate(["Symbol", "Description", "Value", "Units"]):
        p.set(5, j, h)
        p.fmt(5, j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    for i, (sym, desc, val, unit) in enumerate(given):
        r = 6 + i
        p.set(r, 0, sym)
        p.set(r, 1, desc)
        p.set(r, 2, val)
        p.set(r, 3, unit)
        p.fmt(r, 0, align="center", bold=True)
        p.fmt(r, 1, align="left")
        p.fmt(r, 2, bg=PALETTE["warn"], align="center",
              number_format="0.000", bold=True)
        p.fmt(r, 3, align="center")
        if i % 2:
            p.fmt(r, 0, bg=PALETTE["band_alt"])
            p.fmt(r, 1, bg=PALETTE["band_alt"])
            p.fmt(r, 3, bg=PALETTE["band_alt"])

    p.box(5, 0, 9, 3, color=PALETTE["header"], width=1.2)
    p.note(6, 2,
           "These values are for reference. Enter your answers in the table below.",
           kind="note")

    # --- Tasks table ---
    p.set(11, 0, "Tasks")
    p.fmt(11, 0, bold=True, font_size=13, font_color=PALETTE["accent"])

    tasks = [
        ("1", "Undamped natural frequency omega0",
         "omega0 = sqrt(k/m)",   "rad/s"),
        ("2", "Damping ratio zeta",
         "zeta = b / (2*sqrt(k*m))",      "--"),
        ("3", "Damped angular frequency omega_d",
         "omega_d = sqrt(omega0^2 - gamma^2)",  "rad/s"),
        ("4", "Damped period Td",
         "Td = 2*pi / omega_d",    "s"),
        ("5", "Displacement x(t) at t = 0.5 s",
         "x(t) = A0 * exp(-gamma*t) * cos(omega_d*t)", "m"),
        ("6", "Classify: under / critical / over-damped",
         "Compare zeta to 1",           "--"),
    ]

    for j, h in enumerate(["#", "Quantity", "Formula / hint", "Units", "Your Answer"]):
        p.set(12, j, h)
        p.fmt(12, j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    for i, (num, qty, hint, units) in enumerate(tasks):
        r = 13 + i
        p.set(r, 0, num)
        p.set(r, 1, qty)
        p.set(r, 2, hint)
        p.set(r, 3, units)
        p.set(r, 4, "")   # blank answer cell
        p.fmt(r, 0, align="center", bold=True)
        p.fmt(r, 1, align="left")
        p.fmt(r, 2, align="left", italic=True, font_color="#555555")
        p.fmt(r, 3, align="center")
        p.fmt(r, 4, bg="#ffffff", align="center")
        if i % 2:
            p.fmt(r, 0, bg=PALETTE["band_alt"])
            p.fmt(r, 1, bg=PALETTE["band_alt"])
            p.fmt(r, 2, bg=PALETTE["band_alt"])
            p.fmt(r, 3, bg=PALETTE["band_alt"])

    p.box(12, 0, 18, 4, color=PALETTE["header"], width=1.2)
    p.col_width(1, 210)
    p.col_width(2, 230)
    p.col_width(3, 70)
    p.col_width(4, 120)
    p.note(12, 4,
           "Enter your numerical answers in column E. "
           "Then open the Solution sheet to verify.",
           kind="note")

    # --- Regime hint ---
    p.set(20, 0, "Hint -- Damping Regimes")
    p.fmt(20, 0, bold=True, font_color=PALETTE["accent"])
    p.merge(20, 0, 1, 6)
    regime_text = (
        "zeta < 1 : Under-damped -- oscillates with decaying amplitude.  "
        "zeta = 1 : Critically damped -- fastest non-oscillatory return.  "
        "zeta > 1 : Over-damped -- pure exponential decay."
    )
    p.set(21, 0, regime_text)
    p.fmt(21, 0, italic=True, wrap=True, font_color="#444444",
          bg=PALETTE["band_alt"])
    p.merge(21, 0, 2, 7)
    p.box(20, 0, 22, 7, color=PALETTE["accent"], width=1.0, style="dash")

    # ====================================================================
    # SHEET 2: Solution
    # ====================================================================
    s = wb.add_sheet("Solution")

    # --- Title block ---
    s.title_block(
        "Damped Harmonic Oscillator -- Solution",
        "Edit any amber input cell -- all results, table and chart update automatically.",
        span=10,
    )

    # --- Self-contained input block ---
    # 0-based rows 4-7, col 2 (C) -> 1-based C5, C6, C7, C8
    s.set(3, 0, "Inputs (editable)")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    sol_inputs = [
        ("m",   "Mass",                M,   "kg"),
        ("k",   "Spring stiffness",    K,   "N/m"),
        ("b",   "Damping coefficient", B,   "kg/s"),
        ("A0",  "Initial amplitude",   A0,  "m"),
    ]
    # headers
    for j, h in enumerate(["Symbol", "Description", "Value", "Units"]):
        s.set(3, j, h)
        s.fmt(3, j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    # data rows: 0-based rows 4-7
    for i, (sym, desc, val, unit) in enumerate(sol_inputs):
        r = 4 + i
        s.set(r, 0, sym)
        s.set(r, 1, desc)
        s.set(r, 2, val)   # editable literal at C(r+1)
        s.set(r, 3, unit)
        s.fmt(r, 0, align="center", bold=True)
        s.fmt(r, 1, align="left")
        s.fmt(r, 2, bg=PALETTE["warn"], align="center",
              number_format="0.000", bold=True)
        s.fmt(r, 3, align="center")
        if i % 2:
            s.fmt(r, 0, bg=PALETTE["band_alt"])
            s.fmt(r, 1, bg=PALETTE["band_alt"])
            s.fmt(r, 3, bg=PALETTE["band_alt"])

    s.box(3, 0, 7, 3, color=PALETTE["accent"], width=1.2)
    s.note(4, 2,
           "Edit C5=m, C6=k, C7=b, C8=A0 here. "
           "Every derived quantity, the table, and the chart update instantly.",
           kind="note")

    # --- Derived quantities ---
    # 0-based rows 9-13, col 2 (C) -> C10..C14... wait:
    # 0-based row 9  -> 1-based row 10 -> column C -> C10  (header row)
    # 0-based row 10 -> 1-based row 11 -> C11 = omega0
    # 0-based row 11 -> 1-based row 12 -> C12 = gamma
    # 0-based row 12 -> 1-based row 13 -> C13 = zeta
    # 0-based row 13 -> 1-based row 14 -> C14 = omega_d
    # 0-based row 14 -> 1-based row 15 -> C15 = Td (uses C14)
    s.set(8, 0, "Derived Quantities")
    s.fmt(8, 0, bold=True, font_color=PALETTE["accent"])

    for j, h in enumerate(["Symbol", "Expression", "Value", "Units"]):
        s.set(9, j, h)
        s.fmt(9, j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    # C5=m, C6=k, C7=b, C8=A0
    derived = [
        ("omega0", "sqrt(k/m)",
         "=SQRT($C$6/$C$5)",
         "rad/s"),
        ("gamma",  "b/(2m)",
         "=$C$7/(2*$C$5)",
         "1/s"),
        ("zeta",   "b/(2*sqrt(k*m))",
         "=$C$7/(2*SQRT($C$6*$C$5))",
         "--"),
        ("omega_d", "sqrt(k/m-(b/(2m))^2)",
         "=SQRT($C$6/$C$5-($C$7/(2*$C$5))^2)",
         "rad/s"),
        ("Td",     "2*pi/omega_d",
         "=2*PI/$C$14",   # C14 = omega_d (0-based row 13, col 2, 1-based C14)
         "s"),
    ]

    for i, (sym, expr_hint, formula, units) in enumerate(derived):
        r = 10 + i    # 0-based rows 10..14
        s.set(r, 0, sym)
        s.set(r, 1, expr_hint)
        s.formula(r, 2, formula)
        s.set(r, 3, units)
        s.fmt(r, 0, align="center", bold=True)
        s.fmt(r, 1, align="left", italic=True, font_color="#555555")
        s.fmt(r, 2, align="center", number_format="0.0000",
              bg=PALETTE["good"], bold=True)
        s.fmt(r, 3, align="center")
        if i % 2:
            s.fmt(r, 0, bg=PALETTE["band_alt"])
            s.fmt(r, 1, bg=PALETTE["band_alt"])
            s.fmt(r, 3, bg=PALETTE["band_alt"])

    s.box(9, 0, 14, 3, color=PALETTE["header"], width=1.2)

    # --- Regime identification (0-based row 16) ---
    # zeta is at 0-based row 12, col 2 -> C13
    s.set(16, 0, "Damping regime:")
    s.fmt(16, 0, bold=True)
    s.formula(16, 2,
              '=IF($C$13<1,"Under-damped",IF($C$13>1,"Over-damped","Critically damped"))')
    s.fmt(16, 2, bold=True, align="center", bg=PALETTE["band"])
    s.merge(16, 2, 1, 3)
    s.note(16, 2,
           "Regime set by zeta (C13). "
           "Under-damped: zeta < 1 (oscillatory). "
           "With defaults zeta ~ 0.22.",
           kind="note")

    # --- Logarithmic decrement (0-based row 17) ---
    # Lambda = gamma * Td = C12 * C15
    s.set(17, 0, "Log. decrement:")
    s.fmt(17, 0, italic=True, font_color="#555555")
    s.formula(17, 2, "=$C$12*$C$15")
    s.fmt(17, 2, align="center", number_format="0.0000",
          bg=PALETTE["band_alt"])
    s.set(17, 3, "gamma * Td")
    s.fmt(17, 3, italic=True, font_color="#777777")

    # --- Time-displacement table ---
    # TABLE_START = 19 (0-based): header at 0-based 19 -> 1-based row 20
    # First data row: 0-based 20 -> 1-based 21
    TABLE_START = 19
    DATA_ROW_0  = TABLE_START + 1    # 0-based first data row = 20
    DATA_ROW_1B = DATA_ROW_0 + 1    # 1-based first data row = 21

    s.set(TABLE_START - 1, 0, "Time-Domain Response x(t)")
    s.fmt(TABLE_START - 1, 0, bold=True, font_color=PALETTE["header"])

    # Cols: A=time(0), B=x(t)(1), C=+env(2), D=-env(3)
    # Input refs: C5=m, C6=k, C7=b, C8=A0, C12=gamma, C14=omega_d
    table_rows = []
    for idx, t_val in enumerate(t_arr):
        rr = DATA_ROW_1B + idx    # 1-based sheet row for this data row
        table_rows.append([
            round(float(t_val), 5),
            f"=$C$8*EXP(-$C$12*A{rr})*COS($C$14*A{rr})",
            f"=$C$8*EXP(-$C$12*A{rr})",
            f"=-$C$8*EXP(-$C$12*A{rr})",
        ])

    s.table(TABLE_START, 0,
            headers=["t (s)", "x(t) (m)", "+Envelope (m)", "-Envelope (m)"],
            rows=table_rows,
            number_format="0.00000",
            banded=True)

    s.designate(0, "X")
    s.designate(1, "Y")
    s.designate(2, "Y")
    s.designate(3, "Y")

    s.col_width(0, 90)
    s.col_width(1, 115)
    s.col_width(2, 125)
    s.col_width(3, 125)

    # 0-based row range for live binding
    r0_bind = DATA_ROW_0
    r1_bind = DATA_ROW_0 + N_POINTS - 1

    # --- Chart (live-bound to table columns) ---
    s.chart(
        [
            Series(t_arr, x_arr, "x(t)", "Line",
                   color="#4472c4", linewidth=2.0,
                   x_col=0, y_col=1, row_start=r0_bind, row_end=r1_bind),
            Series(t_arr, env_p, "+A0*exp(-gamma*t)", "Line",
                   color="#ed7d31", linewidth=1.2, linestyle="--",
                   x_col=0, y_col=2, row_start=r0_bind, row_end=r1_bind),
            Series(t_arr, env_n, "-A0*exp(-gamma*t)", "Line",
                   color="#ed7d31", linewidth=1.2, linestyle="--",
                   x_col=0, y_col=3, row_start=r0_bind, row_end=r1_bind),
        ],
        at=(540, 30), size=(460, 320),
        title="Damped Oscillation: x(t) and Envelope",
        xlabel="Time t (s)", ylabel="Displacement x (m)",
        grid=True, legend=True,
    )

    # --- LaTeX equations (mathtext) ---
    s.equation(
        r"x(t) = A_0 \, e^{-\gamma t} \cos(\omega_d \, t)",
        at=(540, 370), fontsize=18, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(310, 50),
    )
    s.equation(
        r"\omega_d = \sqrt{\omega_0^2 - \gamma^2}",
        at=(540, 436), fontsize=18, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(260, 50),
    )
    s.equation(
        r"\zeta = \frac{b}{2\sqrt{km}}",
        at=(540, 500), fontsize=18, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(185, 54),
    )

    # --- Summary panel (right of derived table) ---
    s.set(8, 5, "Summary")
    s.fmt(8, 5, bold=True, font_color=PALETTE["header"])

    # omega0 -> C11 (0-based row 10, col 2)
    # zeta   -> C13 (0-based row 12, col 2)
    # omega_d-> C14 (0-based row 13, col 2)
    # Td     -> C15 (0-based row 14, col 2)
    # A0     -> C8  (0-based row 7, col 2)
    summ = [
        ("omega0 (rad/s)", "=C11"),
        ("zeta",           "=C13"),
        ("omega_d (rad/s)","=C14"),
        ("Td (s)",         "=C15"),
        ("A0 (m)",         "=C8"),
    ]
    for i, (lbl, fml) in enumerate(summ):
        r = 9 + i
        s.set(r, 5, lbl)
        s.formula(r, 6, fml)
        s.fmt(r, 5, align="left")
        s.fmt(r, 6, bg=PALETTE["band"], align="center",
              number_format="0.0000", bold=True)

    s.box(8, 5, 14, 6, color=PALETTE["header"], width=1.2)
    s.col_width(5, 145)
    s.col_width(6, 105)

    # Instructive notes
    s.note(TABLE_START, 1,
           "x(t) = A0 * exp(-gamma*t) * cos(omega_d*t). "
           "Changing b in C7 changes gamma and omega_d -- "
           "the curve and envelope update instantly.",
           kind="note")
    s.note(TABLE_START, 2,
           "Orange dashed lines are the exponential decay envelope "
           "+/- A0 * exp(-gamma*t). "
           "Every peak of x(t) touches this envelope.",
           kind="note")

    # ====================================================================
    # Save
    # ====================================================================
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "exercises", "Year 2",
    )
    out_path = os.path.join(out_dir, "Damped Harmonic Oscillator.ksheet")
    wb.save(out_path)
    return out_path


if __name__ == "__main__":
    print("Wrote", build())
