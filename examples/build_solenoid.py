"""Build the "Solenoid Magnetic Field" demo .ksheet example.

Physics: B = mu0 * mu_r * n * I  (magnetic flux density inside a long solenoid)
  mu0 = 4*pi*1e-7 T·m/A (stored as cell value 0.0000012566)
  mu_r = relative permeability (1 for air, ~200 for iron)
  n    = turns per metre
  I    = current in amps (independent variable, 0..10 A, fixed grid)
  B    = flux density in Tesla

Run:  python examples/build_solenoid.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import numpy as np
from ksheet_author import Workbook, Series, PALETTE


def build() -> str:
    # ── Physics constants (for numpy pre-computation only) ─────────────
    MU0   = 4 * np.pi * 1e-7   # T·m/A
    MU_R  = 1.0                 # air
    N     = 1000.0              # turns per metre
    I_MAX = 10.0
    N_PTS = 21

    # Independent variable: fixed literal current grid (A)
    currents = np.linspace(0.0, I_MAX, N_PTS)

    # Pre-compute B arrays for initial chart render (must match formulas)
    B_T  = MU0 * MU_R * N * currents          # Tesla
    B_mT = B_T * 1000.0                        # milli-Tesla

    # ── Workbook / sheet ───────────────────────────────────────────────
    wb = Workbook(min_rows=44, min_cols=14)
    s  = wb.add_sheet("Solenoid B-Field")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Solenoid Magnetic Field",
        "B = μ₀ · μ_r · n · I  inside a long solenoid",
        span=7,
    )

    # ── Editable inputs ───────────────────────────────────────────────
    # Layout: rows 3-6, cols 0-1
    #   B3  = "Inputs" label
    #   B4  = mu0 value  → cell B4  (0-based: row=3, col=1)
    #   B5  = mu_r value → cell B5  (0-based: row=4, col=1)
    #   B6  = n value    → cell B6  (0-based: row=5, col=1)
    #
    # 1-based refs:  mu0 = $B$4,  mu_r = $B$5,  n = $B$6

    s.set(2, 0, "Inputs")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    input_rows = [
        ("mu0 = 4π × 10⁻⁷ (T·m/A)", 0.0000012566),
        ("mu_r — relative permeability",                       1.0),
        ("n — turns per metre (m⁻¹)",                1000.0),
    ]
    for i, (lbl, val) in enumerate(input_rows):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.0000000000")

    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 240)
    s.col_width(1, 130)

    # Notes teaching users what to edit
    s.note(3, 1,
           "mu0 is a physical constant: 4π×10⁻⁷ T·m/A.\n"
           "Stored as a plain decimal cell value (0.0000012566).",
           kind="note")
    s.note(4, 1,
           "Change mu_r to model a core:\n"
           "  Air     →  mu_r = 1\n"
           "  Iron    →  mu_r ≈ 200\n"
           "  Ferrite →  mu_r ≈ 1000\n"
           "B scales linearly with mu_r.",
           kind="note")
    s.note(5, 1,
           "n = N_turns / length.\n"
           "More turns per metre → stronger field.\n"
           "Try n = 5000 for a typical MRI-grade coil.",
           kind="note")

    # ── Summary panel ─────────────────────────────────────────────────
    # Placed at rows 3-6, cols 3-5
    # dB/dI = mu0 * mu_r * n  (slope, T/A)
    # B at I=5 A = mu0 * mu_r * n * 5
    # B with iron core (mu_r=200) at I=5 A = mu0 * 200 * n * 5

    s.set(2, 3, "Summary")
    s.fmt(2, 3, bold=True, font_color=PALETTE["header"])

    summ = [
        ("dB/dI = μ₀μ_r n  (T/A)",
         "=$B$4*$B$5*$B$6",
         PALETTE["band"]),
        ("B at I = 5 A  (T)",
         "=$B$4*$B$5*$B$6*5",
         PALETTE["good"]),
        ("B at I = 5 A  (mT)",
         "=$B$4*$B$5*$B$6*5*1000",
         PALETTE["good"]),
        ("Iron-core B at I=5 A, mu_r=200  (mT)",
         "=$B$4*200*$B$6*5*1000",
         PALETTE["warn"]),
    ]
    for i, (lbl, expr, col) in enumerate(summ):
        r = 3 + i
        s.set(r, 3, lbl)
        s.formula(r, 4, expr)
        s.fmt(r, 3, align="left")
        s.fmt(r, 4, bg=col, align="center", number_format="0.000000", bold=True)

    s.box(3, 3, 6, 4, color=PALETTE["header"], width=1.0)
    s.col_width(3, 260)
    s.col_width(4, 110)

    # ── Data table ────────────────────────────────────────────────────
    # Columns: I (A) | B (T) | B (mT)
    # table starts at row 9 (0-based) → header at sheet row 10 (1-based)
    # First data row: sheet row 11, i.e. row=10 (0-based)
    TABLE_START = 9
    DATA_ROW_0  = TABLE_START + 2   # 1-based sheet row of first data row

    s.set(8, 0, "Magnetic Field vs Current")
    s.fmt(8, 0, bold=True, font_color=PALETTE["header"])

    rows = []
    for k, I_val in enumerate(currents):
        rr = DATA_ROW_0 + k           # 1-based sheet row for this data row
        col_I  = f"A{rr}"             # current cell (literal)
        col_BT = f"B{rr}"             # B in Tesla formula result
        rows.append([
            round(float(I_val), 2),   # I (A) — literal independent variable
            f"=$B$4*$B$5*$B$6*{col_I}",    # B (T)  = mu0*mu_r*n*I
            f"=B{rr}*1000",                 # B (mT) = B(T) * 1000
        ])

    s.table(
        TABLE_START, 0,
        headers=["I (A)", "B (T)", "B (mT)"],
        rows=rows,
        number_format="0.000000",
        banded=True,
    )

    # Designate X and Y columns for chart axis hints
    s.designate(0, "X")
    s.designate(1, "Y")
    s.designate(2, "Y")

    # ── Chart ─────────────────────────────────────────────────────────
    # Bind to data columns A (col 0) and C (col 2, B in mT)
    # Data rows are 0-based: TABLE_START+1 .. TABLE_START+N_PTS
    r0 = TABLE_START + 1
    r1 = TABLE_START + N_PTS

    s.chart(
        [Series(
            currents, B_mT,
            label="B (mT)",
            plot_type="Line+Symbol",
            color="#4472c4",
            linewidth=2.0,
            marker="o",
            markersize=5.0,
            x_col=0,
            y_col=2,
            row_start=r0,
            row_end=r1,
        )],
        at=(560, 30),
        size=(440, 310),
        title="Solenoid Field vs Current",
        xlabel="Current I (A)",
        ylabel="Flux Density B (mT)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    # mathtext: \mu is valid, \frac is valid, \mathrm is valid
    s.equation(
        r"B = \mu_0 \, \mu_r \, n \, I",
        at=(560, 360),
        fontsize=22,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(260, 50),
    )

    # Instructive note near the equation
    s.note(0, 7,
           "B is linear in I: doubling the current doubles the field.\n"
           "The slope dB/dI = μ₀μ_r n is constant for a given core.",
           kind="note")

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Solenoid Magnetic Field.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
