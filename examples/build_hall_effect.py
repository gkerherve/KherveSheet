"""Build the "Hall Effect" demo .ksheet example.

A semiconductor-transport physics example covering the Hall effect:
the transverse voltage V_H = I*B / (n*e*t) that develops across a
current-carrying conductor in a perpendicular magnetic field.

Features:
  - Editable input panel (I, n, t, e as literal values).
  - Fixed B-field grid (0 to 1 T) as independent-variable literals.
  - V_H and V_H(mV) as live formula columns referencing inputs.
  - Summary panel: Hall coefficient R_H, V_H at B=0.5 T, slope dV/dB.
  - Live-bound Line chart (V_H vs B).
  - Mathtext equation for V_H and R_H.
  - Three instructive yellow sticky notes.

Run:  python examples/build_hall_effect.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import numpy as np
from ksheet_author import Workbook, Series, PALETTE


def build() -> str:
    # ── Physics constants / default inputs ───────────────────────────
    I_val   = 0.01          # current  (A)
    n_val   = 1e22          # carrier density (m^-3)  — stored as literal 1e22
    t_val   = 0.001         # thickness (m)
    e_val   = 1.602e-19     # electron charge (C)     — stored as literal 1.602e-19

    # Independent variable: B field from 0 to 1 T in 21 steps
    n_pts = 21
    B_arr = np.linspace(0.0, 1.0, n_pts)

    # Pre-compute V_H for chart initial render (matches what formulas give)
    VH_arr  = I_val * B_arr / (n_val * e_val * t_val)   # volts
    VH_mV   = VH_arr * 1000.0                            # millivolts

    # ── Layout constants (0-based) ────────────────────────────────────
    # Inputs: rows 4..7, cols 0-1
    #   row 4 → I   in B5
    #   row 5 → n   in B6
    #   row 6 → t   in B7
    #   row 7 → e   in B8
    # Table header at row 10, data rows 11..(11+n_pts-1)
    TABLE_HDR = 10
    DATA_START = TABLE_HDR + 1          # 0-based first data row
    DATA_END   = TABLE_HDR + n_pts      # 0-based last data row (inclusive)

    # Sheet-row numbers (1-based) for formula strings
    # header is at sheet row TABLE_HDR+1 = 11 (1-based)
    # data rows: TABLE_HDR+2 .. TABLE_HDR+1+n_pts  (1-based)

    wb = Workbook(min_rows=44, min_cols=14)
    s  = wb.add_sheet("Hall Effect")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block("Hall Effect",
                  "Transverse voltage in a magnetised semiconductor conductor",
                  span=8)

    # ── Input panel ───────────────────────────────────────────────────
    s.set(3, 0, "Editable Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    input_rows = [
        ("Current  I  (A)",             I_val),
        ("Carrier density  n  (m⁻³)",   n_val),
        ("Thickness  t  (m)",           t_val),
        ("Electron charge  e  (C)",     e_val),
    ]
    for i, (lbl, val) in enumerate(input_rows):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)          # stored as a plain numeric literal
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center",
              number_format="0.0000E+00")

    s.box(4, 0, 7, 1, color=PALETTE["accent"], width=1.2)
    s.col_width(0, 210)
    s.col_width(1, 130)

    s.note(4, 1,
           "Edit I, n, t or e here — the entire table and chart "
           "recalculate automatically on open.", kind="note")

    # ── Data table ────────────────────────────────────────────────────
    # Column layout:
    #   col 0 (A) — B field (T)   [X, literal]
    #   col 1 (B) — inputs …      (already used)
    #   We place the table at col 3 so it doesn't collide with inputs.
    # Re-layout: put table starting at col 0 for columns A(B), C(V_H), D(V_H mV).
    # Input panel uses cols 0-1 rows 4-7 only. Table will use same cols but
    # different rows (10+), which is fine — no collision.
    # Col mapping inside table (start_col=0):
    #   table col 0 → sheet col A (col index 0)  B field literal
    #   table col 1 → sheet col B (col index 1)  V_H (V)  — BUT col B is already
    #                 used for inputs rows 4-7.  Rows 11+ are safe.
    #   table col 2 → sheet col C (col index 2)  V_H (mV)
    #
    # Input cell addresses:
    #   I  → B5  ($B$5, 0-based row 4 col 1)
    #   n  → B6  ($B$6, 0-based row 5 col 1)
    #   t  → B7  ($B$7, 0-based row 6 col 1)
    #   e  → B8  ($B$8, 0-based row 7 col 1)
    #
    # V_H formula: = $B$5 * A{rr} / ($B$6 * $B$8 * $B$7)
    #   where rr = 1-based sheet row of the data row.
    # Table header is at 0-based row 10 → sheet row 11 (1-based).
    # First data 0-based row 11 → sheet row 12 (1-based).

    table_rows = []
    for k, B in enumerate(B_arr):
        rr = TABLE_HDR + 2 + k     # 1-based sheet row of this data row
        vh_formula = f"=$B$5*A{rr}/($B$6*$B$8*$B$7)"
        mv_formula = f"=B{rr}*1000"
        table_rows.append([
            round(float(B), 2),    # B field literal (independent var)
            vh_formula,
            mv_formula,
        ])

    s.set(9, 0, "Hall Voltage vs Magnetic Field")
    s.fmt(9, 0, bold=True, font_color=PALETTE["header"])
    s.merge(9, 0, 1, 3)

    s.table(TABLE_HDR, 0,
            headers=["B (T)", "V_H (V)", "V_H (mV)"],
            rows=table_rows,
            number_format="0.0000",
            banded=True)

    s.col_width(0, 80)
    s.col_width(1, 120)
    s.col_width(2, 120)

    # Designate axes for the app
    s.designate(0, "X")
    s.designate(1, "Y")
    s.designate(2, "Y")

    s.note(DATA_START + 10, 0,
           "Column A (B field) is the FIXED independent variable. "
           "V_H values are live formulas — change any input above to "
           "see this column update.", kind="note")

    # ── Summary panel (formulas referencing inputs and table) ─────────
    # Place to the right: cols 4-6, rows 4-9
    s.set(3, 4, "Summary")
    s.fmt(3, 4, bold=True, font_color=PALETTE["header"])
    s.merge(3, 4, 1, 2)

    # 1-based rows of V_H column (col B = col index 1)
    # B=0 is at rr = TABLE_HDR+2 = 12,  B=1 at rr = TABLE_HDR+1+n_pts = 32
    first_data_sr = TABLE_HDR + 2          # 12 (1-based)
    last_data_sr  = TABLE_HDR + 1 + n_pts  # 32 (1-based)

    # V_H at B=0.5 T — 0.5 T is at index 10 of a 0..1 T uniform grid with 21 pts
    # (indices 0..20, step 0.05; index 10 → B=0.5 T)
    midpoint_rr = TABLE_HDR + 2 + 10       # 1-based sheet row for B=0.5 T = 22

    # R_H = 1/(n*e)
    # slope dV/dB = I/(n*e*t)
    # V_H at B=0.5 T = B{midpoint_rr} (direct formula reference)
    summary_items = [
        ("Hall coeff R_H (m³/C)",
         "=1/($B$6*$B$8)",
         PALETTE["band"]),
        ("V_H at B = 0.5 T  (V)",
         f"=B{midpoint_rr}",
         PALETTE["good"]),
        ("Slope dV/dB  (V/T)",
         "=$B$5/($B$6*$B$8*$B$7)",
         PALETTE["band"]),
        ("Max V_H  (V)",
         f"=MAX(B{first_data_sr}:B{last_data_sr})",
         PALETTE["band_alt"]),
        ("Min V_H  (V)",
         f"=MIN(B{first_data_sr}:B{last_data_sr})",
         PALETTE["band_alt"]),
    ]

    for i, (lbl, expr, col) in enumerate(summary_items):
        r = 4 + i
        s.set(r, 4, lbl)
        s.formula(r, 5, expr)
        s.fmt(r, 4, align="left")
        s.fmt(r, 5, bg=col, align="center",
              number_format="0.000E+00", bold=True)

    s.box(4, 4, 4 + len(summary_items) - 1, 5,
          color=PALETTE["header"], width=1.2)
    s.col_width(4, 200)
    s.col_width(5, 130)

    s.note(4, 4,
           "R_H = 1/(n·e). The sign of V_H (positive or negative) "
           "tells you whether carriers are electrons (n-type) or "
           "holes (p-type) — this is how Hall sensors identify carrier "
           "type.", kind="note")

    s.note(6, 4,
           "Slope dV_H/dB = I/(n·e·t). Measuring the slope from a "
           "V_H vs B graph directly gives the carrier density n — "
           "the basis of Hall-effect magnetometers and current sensors.",
           kind="note")

    # ── Chart: V_H vs B (live-bound) ──────────────────────────────────
    # Data-binding: B col = col index 0, V_H col = col index 1
    # 0-based row range: DATA_START .. DATA_END
    s.chart(
        [Series(
            B_arr, VH_arr,
            label="V_H (V)",
            plot_type="Line+Symbol",
            color="#4472c4",
            linewidth=2.0,
            marker="o",
            markersize=4.0,
            x_col=0,
            y_col=1,
            row_start=DATA_START,
            row_end=DATA_END,
        )],
        at=(530, 30),
        size=(430, 300),
        title="Hall Voltage vs Magnetic Field",
        xlabel="B (T)",
        ylabel="V_H (V)",
        grid=True,
        legend=True,
    )

    # ── Mathtext equation ─────────────────────────────────────────────
    s.equation(
        r"V_H = \frac{I \, B}{n \, e \, t} \qquad R_H = \frac{1}{n \, e}",
        at=(530, 350),
        fontsize=18,
        color="#1a1a2e",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(430, 60),
    )

    # ── Output path ───────────────────────────────────────────────────
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Hall Effect.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
