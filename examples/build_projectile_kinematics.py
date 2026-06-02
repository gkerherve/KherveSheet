"""Build the "Projectile Kinematics" Year-1 undergraduate EXERCISE.

Two-sheet workbook:
  Sheet 1 "Problem"  — problem statement, given values, numbered tasks,
                       empty answer cells for the student.
  Sheet 2 "Solution" — self-contained editable inputs, live formulas for
                       every answer, a trajectory table, a bound chart,
                       a mathtext equation panel and brief step notes.

Run:  python examples/build_projectile_kinematics.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402

# ── Physical constants used for numpy pre-compute only ───────────────
U_DEF = 20.0      # launch speed (m/s)
TH_DEF = 35.0     # launch angle (degrees)
G_DEF = 9.81      # gravity (m/s^2)

N_TRAJ = 25       # number of trajectory samples


def _col(c: int) -> str:
    """0-based column index → A1 letter (A..Z only, sufficient here)."""
    return chr(ord("A") + c)


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=16)

    # =================================================================
    # SHEET 1 — PROBLEM
    # =================================================================
    prob = wb.add_sheet("Problem")

    # Column widths
    prob.col_width(0, 40)   # narrow indent
    prob.col_width(1, 240)  # label / question text
    prob.col_width(2, 120)  # answer cell
    prob.col_width(3, 80)   # units
    prob.col_width(4, 200)  # extra info

    # --- Title block -------------------------------------------------
    prob.title_block(
        "Projectile Kinematics",
        "Year 1 Undergraduate Physics  |  Exercise Sheet",
        row=0, col=0, span=5,
    )

    # --- Problem statement -------------------------------------------
    prob.set(2, 0, "Problem Statement")
    prob.fmt(2, 0, bold=True, font_size=12, font_color=PALETTE["header"])
    prob.merge(2, 0, 1, 5)

    statement_lines = [
        "A ball is launched from the ground with initial speed u at angle"
        " θ above the horizontal.",
        "The ground is flat and air resistance may be neglected.",
        "Take the launch point as the origin (x = 0, y = 0).",
        "Use g = 9.81 m s⁻² directed vertically downward.",
    ]
    for i, line in enumerate(statement_lines):
        prob.set(3 + i, 1, line)
        prob.fmt(3 + i, 1, italic=(i == 0), wrap=True)
        prob.merge(3 + i, 1, 1, 4)

    # --- Given block -------------------------------------------------
    prob.set(8, 0, "Given")
    prob.fmt(8, 0, bold=True, font_size=11, font_color=PALETTE["accent"])
    prob.merge(8, 0, 1, 5)

    given_header = ["Symbol", "Value", "Unit", "Description"]
    for j, h in enumerate(given_header):
        prob.set(9, j + 1, h)
        prob.fmt(9, j + 1, bold=True, bg=PALETTE["header"],
                 font_color="#ffffff", align="center")

    given_data = [
        ("u",  U_DEF,  "m/s",   "Initial speed"),
        ("θ", TH_DEF, "deg", "Launch angle above horizontal"),
        ("g",  G_DEF,  "m/s²", "Gravitational acceleration"),
    ]
    for i, (sym, val, unit, desc) in enumerate(given_data):
        r = 10 + i
        band = PALETTE["band_alt"] if i % 2 else None
        prob.set(r, 1, sym)
        prob.fmt(r, 1, bold=True, italic=True,
                 align="center", bg=band or "")
        prob.set(r, 2, val)
        prob.fmt(r, 2, bg=PALETTE["warn"], align="center",
                 number_format="0.00")
        prob.set(r, 3, unit)
        prob.fmt(r, 3, align="center", bg=band or "")
        prob.set(r, 4, desc)
        prob.fmt(r, 4, align="left", bg=band or "")
    prob.box(9, 1, 12, 4, color=PALETTE["accent"], width=1.2)

    prob.note(10, 2,
              "These are the given values. Do not change them here — "
              "work through the tasks below using these numbers.",
              kind="note")

    # --- Tasks -------------------------------------------------------
    prob.set(14, 0, "Tasks")
    prob.fmt(14, 0, bold=True, font_size=12, font_color=PALETTE["header"])
    prob.merge(14, 0, 1, 5)

    tasks = [
        ("1.", "Find the horizontal component of the initial velocity.",
         "uₓ =", "m/s"),
        ("2.", "Find the vertical component of the initial velocity.",
         "uᵧ =", "m/s"),
        ("3.", "Calculate the total time of flight T.",
         "T =", "s"),
        ("4.", "Calculate the maximum height H reached by the ball.",
         "H =", "m"),
        ("5.", "Calculate the horizontal range R.",
         "R =", "m"),
        ("6.", "Sketch the trajectory (height y vs horizontal distance x) "
              "on the axes below. Label the key points: launch, apex, landing.",
         "", ""),
    ]

    task_start = 15
    for i, (num, question, ans_label, unit) in enumerate(tasks):
        r = task_start + i * 3
        # Task number + question
        prob.set(r, 1, f"{num}  {question}")
        prob.fmt(r, 1, bold=(i < 5), wrap=True)
        prob.merge(r, 1, 1, 4)

        if ans_label:
            # Answer label
            prob.set(r + 1, 2, ans_label)
            prob.fmt(r + 1, 2, align="right", italic=True)
            # Empty answer cell (student fills this in)
            prob.fmt(r + 1, 3, bg="#ffffff", align="center",
                     number_format="0.000")
            prob.box(r + 1, 3, r + 1, 3,
                     color=PALETTE["accent"], width=1.0)
            # Unit label
            prob.set(r + 1, 4, unit)
            prob.fmt(r + 1, 4, align="left")

    # Sketch area placeholder
    sketch_row = task_start + 5 * 3 + 1
    prob.set(sketch_row, 1,
             "Sketch area — use graph paper or draw below:")
    prob.fmt(sketch_row, 1, italic=True)
    prob.merge(sketch_row, 1, 1, 4)
    # Draw a blank bordered box for the sketch
    for rr in range(sketch_row + 1, sketch_row + 8):
        for cc in range(1, 5):
            prob.fmt(rr, cc, bg="#f8f8f8")
    prob.box(sketch_row + 1, 1, sketch_row + 7, 4,
             color="#888888", width=1.0, style="solid")

    prob.note(task_start, 1,
              "Work through tasks 1-5 analytically using SUVAT equations, "
              "then compare your answers with the Solution sheet.",
              kind="note")
    prob.note(task_start + 5 * 3, 1,
              "Sketch the parabolic arc. Mark: O (launch), A (apex), "
              "B (landing). The Solution sheet has a live chart to check "
              "your sketch against.",
              kind="note")

    # =================================================================
    # SHEET 2 — SOLUTION
    # =================================================================
    sol = wb.add_sheet("Solution")

    # Column widths
    sol.col_width(0, 200)   # label
    sol.col_width(1, 100)   # value / formula
    sol.col_width(2, 70)    # unit
    sol.col_width(3, 30)    # spacer
    sol.col_width(4, 100)   # summary value
    sol.col_width(5, 70)    # summary unit

    # --- Title -------------------------------------------------------
    sol.title_block(
        "Projectile Kinematics — Solution",
        "All answers are live formulas. Edit u, θ or g to see "
        "everything recalculate.",
        row=0, col=0, span=6,
    )

    # --- Input panel (editable — self-contained) ---------------------
    # Inputs stored at rows 3,4,5 (0-based), cols 0/1/2
    # B4 = u (sheet row 4),  B5 = theta,  B6 = g   [1-based]
    sol.set(3, 0, "Inputs")
    sol.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    sol_inputs = [
        ("Launch speed  u  (m/s)", U_DEF,  "m/s"),
        ("Launch angle  θ  (deg)", TH_DEF, "deg"),
        ("Gravity  g  (m/s²)",    G_DEF,  "m/s²"),
    ]
    # 0-based rows: 4, 5, 6   →  A1 refs:  A5, A6, A7 for labels
    #                               B5, B6, B7 for values
    for i, (lbl, val, unit) in enumerate(sol_inputs):
        r = 4 + i
        sol.set(r, 0, lbl)
        sol.set(r, 1, val)
        sol.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
        sol.set(r, 2, unit)
        sol.fmt(r, 2, align="left")
    sol.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.2)

    sol.note(4, 1,
             "Edit u, theta or g here — every answer, the trajectory "
             "table, and the chart all update automatically.",
             kind="note")

    # Convenience: input cells in A1 notation (1-based)
    # u -> B5,  theta -> B6,  g -> B7
    REF_U = "$B$5"
    REF_TH = "$B$6"
    REF_G = "$B$7"

    # --- Derived components ------------------------------------------
    # Rows 8,9,10,11,12  (0-based) → sheet rows 9..13
    sol.set(8, 0, "Step-by-step Solution")
    sol.fmt(8, 0, bold=True, font_size=12, font_color=PALETTE["header"])
    sol.merge(8, 0, 1, 6)

    # Step 1: horizontal component  ux = u cos(theta)
    # 0-based row 9 → sheet row 10  → value in B10
    sol.set(9, 0, "Step 1:  ux = u cos(θ)")
    sol.fmt(9, 0, bold=True)
    sol.formula(9, 1, f"={REF_U}*COS(RADIANS({REF_TH}))")
    sol.set(9, 2, "m/s")
    sol.fmt(9, 1, bg=PALETTE["band"], align="center", number_format="0.000",
            bold=True)
    sol.note(9, 0,
             "Horizontal component is constant throughout the flight "
             "(no air resistance).",
             kind="note")

    # Step 2: vertical component  uy = u sin(theta)
    # 0-based row 10 → sheet row 11 → value in B11
    sol.set(10, 0, "Step 2:  uy = u sin(θ)")
    sol.fmt(10, 0, bold=True)
    sol.formula(10, 1, f"={REF_U}*SIN(RADIANS({REF_TH}))")
    sol.set(10, 2, "m/s")
    sol.fmt(10, 1, bg=PALETTE["band"], align="center", number_format="0.000",
            bold=True)

    # Step 3: time of flight  T = 2 uy / g
    # 0-based row 11 → sheet row 12 → B12
    # uy lives at B11 (0-based row 10 → sheet col 1 = B, row = 11)
    REF_UY = "$B$11"
    sol.set(11, 0, "Step 3:  T = 2 × uy / g")
    sol.fmt(11, 0, bold=True)
    sol.formula(11, 1, f"=2*{REF_UY}/{REF_G}")
    sol.set(11, 2, "s")
    sol.fmt(11, 1, bg=PALETTE["good"], align="center", number_format="0.000",
            bold=True)
    sol.note(11, 0,
             "Time of flight: ball returns to y=0 when uy*t = 0.5*g*t^2, "
             "giving t = 2*uy/g.",
             kind="note")

    # Step 4: maximum height  H = uy^2 / (2g)
    # 0-based row 12 → sheet row 13 → B13
    sol.set(12, 0, "Step 4:  H = uy² / (2g)")
    sol.fmt(12, 0, bold=True)
    sol.formula(12, 1, f"={REF_UY}*{REF_UY}/(2*{REF_G})")
    sol.set(12, 2, "m")
    sol.fmt(12, 1, bg=PALETTE["good"], align="center", number_format="0.000",
            bold=True)
    sol.note(12, 0,
             "Apex: vertical velocity = 0. Use v^2 = uy^2 - 2gH "
             "with v=0 to get H = uy^2/(2g).",
             kind="note")

    # Step 5: horizontal range  R = u^2 * sin(2*theta) / g
    # 0-based row 13 → sheet row 14 → B14
    sol.set(13, 0, "Step 5:  R = u² sin(2θ) / g")
    sol.fmt(13, 0, bold=True)
    sol.formula(13, 1,
                f"={REF_U}*{REF_U}*SIN(RADIANS(2*{REF_TH}))/{REF_G}")
    sol.set(13, 2, "m")
    sol.fmt(13, 1, bg=PALETTE["good"], align="center", number_format="0.000",
            bold=True)

    sol.box(9, 0, 13, 2, color=PALETTE["header"], width=1.0)

    # --- Trajectory table --------------------------------------------
    # Table starts at row 16 (0-based header), data from row 17 onward.
    # x in col 0, y in col 1 of the table → absolute cols 0,1.
    # Within the table helper, start_row=16 → header at sheet row 17,
    # first data row at sheet row 18.
    TABLE_START = 16
    # T at 0-based row 11, col 1 → sheet cell B12
    REF_T = "$B$12"
    # ux at 0-based row 9, col 1 → sheet cell B10
    REF_UX = "$B$10"

    # Independent variable: time fractions (fixed literals)
    T_computed = 2.0 * U_DEF * np.sin(np.radians(TH_DEF)) / G_DEF
    t_vals = np.linspace(0.0, T_computed, N_TRAJ)

    # For numpy pre-compute (chart render only)
    ux_np = U_DEF * np.cos(np.radians(TH_DEF))
    uy_np = U_DEF * np.sin(np.radians(TH_DEF))
    x_np = ux_np * t_vals
    y_np = uy_np * t_vals - 0.5 * G_DEF * t_vals ** 2
    # clip tiny negatives at the last point
    y_np = np.maximum(y_np, 0.0)

    sol.set(15, 0, "Trajectory (25 sample points)")
    sol.fmt(15, 0, bold=True, font_color=PALETTE["header"])
    sol.merge(15, 0, 1, 3)

    # Build rows: t is a literal, x and y are formulas.
    # Data row i (0-indexed) sits at sheet row TABLE_START+2+i (1-based).
    traj_rows = []
    for k, t in enumerate(t_vals):
        sheet_row = TABLE_START + 2 + k  # 1-based sheet row for this data row
        traj_rows.append([
            round(float(t), 6),                         # t — independent literal
            f"={REF_UX}*A{sheet_row}",                  # x = ux * t
            f"={REF_UY}*A{sheet_row}-0.5*{REF_G}*A{sheet_row}*A{sheet_row}",  # y
        ])

    sol.table(TABLE_START, 0,
              headers=["t (s)", "x (m)", "y (m)"],
              rows=traj_rows,
              number_format="0.000",
              banded=True)

    # Designate columns so the app knows the axes
    sol.designate(0, "X")   # col A = time (not really X for the chart)
    sol.designate(1, "X")   # col B = horizontal distance → chart X
    sol.designate(2, "Y")   # col C = height → chart Y

    # --- Chart (live-bound to cols B and C) --------------------------
    # Data rows: 0-based TABLE_START+1 .. TABLE_START+N_TRAJ
    r0 = TABLE_START + 1
    r1 = TABLE_START + N_TRAJ

    sol.chart(
        [Series(
            x_np, y_np,
            label="Trajectory",
            plot_type="Line+Symbol",
            color="#4472c4",
            linewidth=2.0,
            marker="o",
            markersize=4.0,
            x_col=1,          # col B (0-based) = x (m)
            y_col=2,          # col C (0-based) = y (m)
            row_start=r0,
            row_end=r1,
        )],
        at=(520, 30), size=(450, 310),
        title="Projectile Trajectory",
        xlabel="Horizontal distance x (m)",
        ylabel="Height y (m)",
        grid=True,
        legend=False,
    )

    # --- SUVAT / projectile equations (mathtext) ---------------------
    sol.equation(
        r"u_x = u\cos\theta \quad u_y = u\sin\theta",
        at=(520, 360), fontsize=16,
        color="#222222", bg_color="#ffffff",
        border_color=PALETTE["header"], border_width=1.2,
        size=(360, 44),
    )
    sol.equation(
        r"T = \frac{2u_y}{g} \quad H = \frac{u_y^2}{2g} "
        r"\quad R = \frac{u^2\sin 2\theta}{g}",
        at=(520, 415), fontsize=16,
        color="#222222", bg_color="#ffffff",
        border_color=PALETTE["header"], border_width=1.2,
        size=(450, 44),
    )
    sol.equation(
        r"y(t)=u_y t - \frac{1}{2}g t^2 \quad x(t)=u_x t",
        at=(520, 470), fontsize=16,
        color="#222222", bg_color="#ffffff",
        border_color=PALETTE["header"], border_width=1.2,
        size=(380, 44),
    )

    # --- Summary panel -----------------------------------------------
    # Placed to the right of the step-by-step block, rows 9-13
    sol.set(8, 4, "Summary")
    sol.fmt(8, 4, bold=True, font_color=PALETTE["header"])
    sol.merge(8, 4, 1, 2)

    # REF_UX = B10, REF_UY = B11, REF_T = B12
    # H = B13, R = B14
    REF_H = "$B$13"
    REF_R = "$B$14"

    summary = [
        ("ux (m/s)", f"={REF_UX}", PALETTE["band"]),
        ("uy (m/s)", f"={REF_UY}", PALETTE["band_alt"]),
        ("T (s)",    f"={REF_T}",  PALETTE["good"]),
        ("H (m)",    f"={REF_H}",  PALETTE["good"]),
        ("R (m)",    f"={REF_R}",  PALETTE["band"]),
    ]
    for i, (lbl, expr, bg) in enumerate(summary):
        r = 9 + i
        sol.set(r, 4, lbl)
        sol.fmt(r, 4, align="right")
        sol.formula(r, 5, expr)
        sol.fmt(r, 5, bg=bg, align="center", number_format="0.000", bold=True)
    sol.box(9, 4, 13, 5, color=PALETTE["header"], width=1.2)

    # --- Save --------------------------------------------------------
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "exercises", "Year 1",
    )
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "Projectile Kinematics.ksheet")
    wb.save(out_path)
    return out_path


if __name__ == "__main__":
    path = build()
    print(f"Saved: {path}")
