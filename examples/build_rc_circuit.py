"""Build the "RC Circuit" demo .ksheet example.

Demonstrates the charging and discharging of a capacitor through a
resistor.  The sheet has editable inputs (V0, R, C, N steps), computes
the time constant tau = R*C in a formula cell, and builds a live data
table with columns: time t, charging voltage Vc, discharging voltage Vd,
and charging current i.  A live-bound chart shows both voltage curves.
Two mathtext equations annotate the physics.

Run:  python examples/build_rc_circuit.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os

import numpy as np

from ksheet_author import Workbook, Series, PALETTE

# ── Physical defaults (also hard-coded in the numpy arrays for first render)
V0    = 5.0       # supply voltage, V
R     = 1000.0    # resistance, Ohm
C     = 100e-6    # capacitance, F  (100 µF)
N     = 30        # number of time steps
TAU   = R * C     # time constant, s  (0.1 s)
T_MAX = 5 * TAU   # simulate to 5 tau (99 % charge)


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=14)
    s = wb.add_sheet("RC Circuit")

    # ------------------------------------------------------------------ #
    # Title                                                               #
    # ------------------------------------------------------------------ #
    s.title_block(
        "RC Circuit — Capacitor Charge / Discharge",
        "Edit V0, R, C or N steps; the table, summary and chart all update.",
        span=8,
    )

    # ------------------------------------------------------------------ #
    # Input panel  (rows 3-7, cols 0-1)                                  #
    # B5 = V0, B6 = R, B7 = C, B8 = N                                   #
    # ------------------------------------------------------------------ #
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Supply voltage V₀ (V)",       V0),
        ("Resistance R (Ω)",            R),
        ("Capacitance C (F)",                C),
        ("Number of time steps N",           N),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.0000")

    s.col_width(0, 200)
    s.col_width(1, 100)
    s.box(4, 0, 7, 1, color=PALETTE["accent"], width=1.5)

    # tau derived value  (row 9, col 0-1)
    s.set(9, 0, "Time constant τ = R×C (s)")
    s.formula(9, 1, "=B6*B7")
    s.fmt(9, 0, bold=True, italic=True, font_color=PALETTE["header"])
    s.fmt(9, 1, bold=True, bg=PALETTE["good"], align="center",
          number_format="0.0000")
    s.box(9, 0, 9, 1, color=PALETTE["header"], width=1.2)

    s.note(4, 1,
           "Edit V₀, R or C here.\n"
           "The table columns and chart update automatically.",
           kind="note")

    # ------------------------------------------------------------------ #
    # Summary panel  (rows 3-7, cols 4-6)                                #
    # ------------------------------------------------------------------ #
    s.set(3, 4, "Summary")
    s.fmt(3, 4, bold=True, font_color=PALETTE["header"])

    # We will define the table_start before this section, so we can
    # reference data rows.  Table starts at row 13 (0-based).
    # Header is at sheet row 14, first data row at sheet row 15.
    TABLE_START  = 13
    FIRST_DATA_R = TABLE_START + 2          # 1-based sheet row of first data row
    LAST_DATA_R  = TABLE_START + 1 + N      # 1-based sheet row of last data row

    summary_items = [
        # label, formula, bg
        ("Time constant τ (s)",
         "=B6*B7",
         PALETTE["band"]),
        ("Time to 99% charge (~5τ) (s)",
         "=5*B6*B7",
         PALETTE["band"]),
        ("Vc at t=τ (V)  [≈0.632×V₀]",
         f"=B5*(1-EXP(-($B$6*$B$7)/($B$6*$B$7)))",
         PALETTE["good"]),
        ("Max charging current (A)  [V₀/R]",
         "=B5/B6",
         PALETTE["band"]),
        (f"Vc at final step (V)",
         f"=C{LAST_DATA_R}",
         PALETTE["good"]),
        (f"Vd at final step (V)",
         f"=D{LAST_DATA_R}",
         PALETTE["band_alt"]),
    ]
    for i, (lbl, expr, bg) in enumerate(summary_items):
        r = 4 + i
        s.set(r, 4, lbl)
        s.formula(r, 5, expr)
        s.fmt(r, 4, align="left")
        s.fmt(r, 5, bg=bg, align="center", number_format="0.00000", bold=True)
    s.col_width(4, 230)
    s.col_width(5, 110)
    s.box(4, 4, 9, 5, color=PALETTE["header"], width=1.0)

    s.note(4, 5,
           "The summary re-computes from formulas.\n"
           "Vc at t=τ is always ≈0.6321×V₀ regardless of R or C.",
           kind="note")

    # ------------------------------------------------------------------ #
    # Data table  (starts at TABLE_START = row 13)                       #
    # Columns: A=t, B=step#(hidden label), C=Vc, D=Vd, E=i_charge       #
    # Layout cols: 0=t, 1=Vc, 2=Vd, 3=i_charge                          #
    # ------------------------------------------------------------------ #
    s.set(12, 0, "RC Circuit Data Table")
    s.fmt(12, 0, bold=True, font_color=PALETTE["header"])
    s.merge(12, 0, 1, 4)

    # Build numpy arrays (must exactly match what the formulas compute).
    t_arr  = np.linspace(0.0, T_MAX, N + 1)
    Vc_arr = V0 * (1.0 - np.exp(-t_arr / TAU))
    Vd_arr = V0 * np.exp(-t_arr / TAU)
    i_arr  = (V0 / R) * np.exp(-t_arr / TAU)

    table_rows = []
    for k in range(N + 1):
        rr = TABLE_START + 2 + k   # 1-based sheet row of this data row
        table_rows.append([
            round(float(t_arr[k]), 6),
            f"=$B$5*(1-EXP(-A{rr}/($B$6*$B$7)))",          # Vc
            f"=$B$5*EXP(-A{rr}/($B$6*$B$7))",              # Vd
            f"=($B$5/$B$6)*EXP(-A{rr}/($B$6*$B$7))",       # i_charge
        ])

    s.table(
        TABLE_START, 0,
        headers=["t (s)", "Vc — Charging (V)", "Vd — Discharging (V)",
                 "i — Charging (A)"],
        rows=table_rows,
        number_format="0.000000",
        banded=True,
    )

    # Column widths for table
    s.col_width(0, 110)
    s.col_width(1, 160)
    s.col_width(2, 175)
    s.col_width(3, 160)

    # Designate axes
    s.designate(0, "X")
    s.designate(1, "Y")
    s.designate(2, "Y")
    s.designate(3, "Y")

    # ------------------------------------------------------------------ #
    # Live-bound chart                                                    #
    # Both series bound: x_col=0 (time), y_col=1 (Vc) and y_col=2 (Vd)  #
    # row_start / row_end are 0-based inclusive data row indices.        #
    # ------------------------------------------------------------------ #
    r0 = TABLE_START + 1          # 0-based first data row
    r1 = TABLE_START + 1 + N      # 0-based last data row

    s.chart(
        [
            Series(
                t_arr, Vc_arr,
                label="Vc — Charging",
                plot_type="Line",
                color="#4472c4",
                linewidth=2.2,
                x_col=0, y_col=1,
                row_start=r0, row_end=r1,
            ),
            Series(
                t_arr, Vd_arr,
                label="Vd — Discharging",
                plot_type="Line",
                color="#ed7d31",
                linewidth=2.2,
                linestyle="--",
                x_col=0, y_col=2,
                row_start=r0, row_end=r1,
            ),
        ],
        at=(560, 20),
        size=(450, 310),
        title="RC Capacitor Voltage vs. Time",
        xlabel="Time t (s)",
        ylabel="Voltage (V)",
        grid=True,
        legend=True,
    )

    # ------------------------------------------------------------------ #
    # LaTeX equations (mathtext — use \frac, not \tfrac/\dfrac)          #
    # ------------------------------------------------------------------ #
    s.equation(
        r"V_c(t) = V_0 \left(1 - e^{-t/RC}\right)",
        at=(560, 345),
        fontsize=18,
        color="#1a3a6b",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(320, 52),
    )
    s.equation(
        r"V_d(t) = V_0 \, e^{-t/RC}",
        at=(560, 410),
        fontsize=18,
        color="#8b3a0f",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.2,
        size=(240, 52),
    )

    # ------------------------------------------------------------------ #
    # Note near tau cell                                                  #
    # ------------------------------------------------------------------ #
    s.note(9, 1,
           "τ = R×C is the time constant.\n"
           "At t=τ, Vc reaches ~63.2% of V₀.\n"
           "At t=5τ, Vc is >99% charged.",
           kind="note")

    # ------------------------------------------------------------------ #
    # Save                                                                #
    # ------------------------------------------------------------------ #
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "RC Circuit.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
