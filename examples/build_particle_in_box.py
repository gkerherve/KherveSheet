"""Build the "Particle in a 1D Box" Year-3 undergraduate exercise.

An electron confined to a 1D infinite potential well: quantised energies
E_n = n^2 h^2 / (8 m L^2).  Two-sheet workbook:

  Problem  — title, physics statement, editable inputs, numbered tasks
             with blank "Your answer" cells for students to fill.
  Solution — self-contained constants, live formula table E_1..E_6 (eV),
             transition energy and photon wavelength formulas, data-bound
             parabolic chart, mathtext equation, pedagogic notes.

Run:  python examples/build_particle_in_box.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import numpy as np
from ksheet_author import Workbook, Series, PALETTE


# ── Physical constants (also written as cell values in both sheets) ────
H_SI    = 6.626e-34    # Planck constant  J·s
M_SI    = 9.109e-31    # electron mass    kg
E_C     = 1.602e-19    # electron charge  C  (used to convert J → eV)
L_NM    = 0.5          # default box width nm

# ── Helper: compute E_n (eV) in Python for chart / verify ─────────────
def energy_eV(n, L_nm):
    L_m = L_nm * 1e-9
    return n**2 * H_SI**2 / (8 * M_SI * L_m**2 * E_C)


def build() -> str:
    wb = Workbook(min_rows=44, min_cols=14)

    # ================================================================
    # SHEET 1 — Problem
    # ================================================================
    prob = wb.add_sheet("Problem")

    # --- Title block -------------------------------------------------
    prob.title_block(
        "Particle in a 1D Box",
        "Year 3 Undergraduate Exercise  ·  Quantum Mechanics",
        span=8,
    )

    # --- Physics statement -------------------------------------------
    prob.set(2, 0, "Background")
    prob.fmt(2, 0, bold=True, font_size=12, font_color=PALETTE["header"])
    prob.merge(2, 0, 1, 8)

    statement_lines = [
        ("An electron is confined inside an infinitely deep potential well of width L "
         "(the '1D particle-in-a-box' model).  The allowed stationary-state energies are:"),
        "    E_n  =  n² h² / (8 m L²)",
        ("where n = 1, 2, 3, … is the principal quantum number, h is Planck’s constant, "
         "and m is the electron mass.  Energy levels are quantised: only discrete values are "
         "permitted, and the lowest (n=1) ground-state energy is non-zero (zero-point energy)."),
    ]
    for i, line in enumerate(statement_lines):
        prob.set(3 + i, 0, line)
        prob.fmt(3 + i, 0, italic=(i == 1), font_color="#333333")
        prob.merge(3 + i, 0, 1, 8)

    prob.set(6, 0, "The energy difference ΔE = E_n′ − E_n drives photon emission/absorption: "
             "λ = hc / ΔE.  Use c = 2.998 × 10⁸ m/s.")
    prob.fmt(6, 0, font_color="#333333")
    prob.merge(6, 0, 1, 8)

    # --- Given: editable inputs / constants --------------------------
    prob.set(8, 0, "Given")
    prob.fmt(8, 0, bold=True, font_size=12, font_color=PALETTE["accent"])
    prob.merge(8, 0, 1, 2)

    given_labels = [
        ("Box width  L",           L_NM,        "nm",    True),   # editable
        ("Planck constant  h",     6.626e-34,   "J·s",  False),
        ("Electron mass  m_e",     9.109e-31,   "kg",    False),
        ("Electron charge  e",     1.602e-19,   "C",     False),
        ("Speed of light  c",      2.998e8,     "m/s",   False),
    ]
    for i, (lbl, val, unit, editable) in enumerate(given_labels):
        r = 9 + i
        prob.set(r, 0, lbl)
        prob.set(r, 1, val)
        prob.set(r, 2, unit)
        prob.fmt(r, 0, align="left")
        bg = PALETTE["warn"] if editable else PALETTE["band_alt"]
        prob.fmt(r, 1, bg=bg, align="center")
        prob.fmt(r, 2, align="left", italic=True, font_color="#555555")
        prob.col_width(0, 200)
        prob.col_width(1, 130)
        prob.col_width(2, 80)

    prob.box(9, 0, 13, 2, color=PALETTE["accent"], width=1.2)
    prob.note(9, 1,
              "Edit the box width L here (in nm). "
              "See the Solution sheet to watch E_n recalculate.",
              kind="note")

    # --- Tasks -------------------------------------------------------
    prob.set(15, 0, "Tasks")
    prob.fmt(15, 0, bold=True, font_size=12, font_color=PALETTE["header"])
    prob.merge(15, 0, 1, 8)

    tasks = [
        ("1", "Calculate the energy levels E₁ through E₅ in electron-volts (eV)."),
        ("2", "Find the energy spacing ΔE = E₂ − E₁."),
        ("3", "Determine the wavelength λ of the photon emitted in the n = 2 → 1 transition."),
        ("4", "If L is doubled to 1.0 nm, by what factor do all energy levels scale?  "
              "Explain the physical origin of this scaling."),
        ("5", "Sketch (or describe) the probability density |ψ_n(x)|² for n = 1, 2, 3.  "
              "How many nodes does each have?"),
    ]
    # Header row for tasks table
    prob.set(16, 0, "#")
    prob.set(16, 1, "Task")
    prob.set(16, 3, "Your answer")
    prob.set(16, 5, "Units")
    for c in range(6):
        prob.fmt(16, c, bold=True, bg=PALETTE["header"],
                 font_color=PALETTE["header_text"], align="center")
    prob.merge(16, 1, 1, 2)
    prob.merge(16, 3, 1, 2)
    prob.col_width(1, 340)
    prob.col_width(3, 160)
    prob.col_width(5, 80)

    answer_units = ["eV each", "eV", "nm", "dimensionless", "—"]
    for i, (num, text) in enumerate(tasks):
        r = 17 + i
        band = PALETTE["band_alt"] if i % 2 else None
        prob.set(r, 0, num)
        prob.set(r, 1, text)
        # blank answer cell
        prob.set(r, 3, "")
        prob.set(r, 5, answer_units[i])
        for c in [0, 1, 3, 5]:
            kw = dict(align="center" if c in (0, 5) else "left",
                      wrap=True)
            if band:
                kw["bg"] = band
            prob.fmt(r, c, **kw)
        prob.merge(r, 1, 1, 2)
        prob.merge(r, 3, 1, 2)
        # amber highlight on the "Your answer" cell
        prob.fmt(r, 3, bg=PALETTE["warn"])

    prob.box(16, 0, 21, 5, color=PALETTE["header"], width=1.2)
    prob.note(16, 3, "Fill your answers in the amber cells.", kind="note")

    # --- Hint --------------------------------------------------------
    prob.set(23, 0, "Hint: check your answers on the Solution sheet.")
    prob.fmt(23, 0, italic=True, font_color="#888888")
    prob.merge(23, 0, 1, 6)

    # ================================================================
    # SHEET 2 — Solution
    # ================================================================
    sol = wb.add_sheet("Solution")

    # --- Title block -------------------------------------------------
    sol.title_block(
        "Particle in a 1D Box — Solution",
        "Year 3 Undergraduate Exercise  ·  Quantum Mechanics",
        span=8,
    )

    # --- Self-contained constants ------------------------------------
    # Layout (0-based rows):
    #   Row 1: "Constants" heading
    #   Row 2: h   → B3  (col 1)
    #   Row 3: m   → B4  (col 1)
    #   Row 4: e   → B5  (col 1)
    #   Row 5: L   → B6  (col 1)   ← editable
    #   Row 6: c   → B7  (col 1)
    # All are cell literals so formula refs like $B$3 work correctly.
    # 1-based sheet rows = 0-based index + 1:
    #   (1,1)→B2, (2,1)→B3, (3,1)→B4, (4,1)→B5, (5,1)→B6, (6,1)→B7

    sol.set(1, 0, "Constants & Inputs")
    sol.fmt(1, 0, bold=True, font_size=11, font_color=PALETTE["accent"])
    sol.merge(1, 0, 1, 4)

    const_data = [
        # (label, col-A text,   value,        unit,   0-based row)
        ("h",  "Planck constant  h",  H_SI,    "J·s",  2),
        ("m",  "Electron mass  m_e",  M_SI,    "kg",         3),
        ("e",  "Electron charge  e",  E_C,     "C",          4),
        ("L",  "Box width  L",        L_NM,    "nm",         5),
        ("c",  "Speed of light  c",   2.998e8, "m/s",        6),
    ]
    for sym, lbl, val, unit, r in const_data:
        sol.set(r, 0, lbl)
        sol.set(r, 1, val)
        sol.set(r, 2, unit)
        bg = PALETTE["warn"] if sym == "L" else PALETTE["band_alt"]
        sol.fmt(r, 0, align="left")
        sol.fmt(r, 1, bg=bg, align="center")
        sol.fmt(r, 2, italic=True, font_color="#555555")

    sol.box(2, 0, 6, 2, color=PALETTE["accent"], width=1.2)
    sol.col_width(0, 200)
    sol.col_width(1, 130)
    sol.col_width(2, 80)
    sol.note(5, 1,
             "Edit L here (nm) — all energies and the chart update instantly.",
             kind="note")

    # Constants are now at (0-based row, col 1):
    #   h → row 2, col 1  → sheet cell B3
    #   m → row 3, col 1  → sheet cell B4
    #   e → row 4, col 1  → sheet cell B5
    #   L → row 5, col 1  → sheet cell B6
    #   c → row 6, col 1  → sheet cell B7

    # Formula for E_n (eV):
    #   E_n = n^2 * h^2 / (8 * m * (L*0.000000001)^2 * e)
    # Sheet refs: h=$B$3, m=$B$4, e=$B$5, L=$B$6, c=$B$7
    # The n column will be column A (col 0).
    # table() places header at row table_start (0-based), data starts table_start+1.

    # --- Energy table ------------------------------------------------
    # table_start = 9  → header at 0-based row 9 → sheet row 10
    # first data row = 0-based row 10 → sheet row 11  (rr=11 for n=1)

    N_LEVELS = 6
    table_start = 9

    ns = np.arange(1, N_LEVELS + 1)
    E_eV_vals = np.array([energy_eV(n, L_NM) for n in ns])

    # Build formula rows. For row i (0-based within data), the 0-based
    # sheet row is table_start + 1 + i.  The 1-based sheet row (used in
    # A1-notation) is table_start + 2 + i.
    table_rows = []
    for i, n in enumerate(ns):
        rr = table_start + 2 + i     # 1-based sheet row
        # A{rr} holds n (literal integer).
        # Formula: n^2 * h^2 / (8 * m * (L*nm_to_m)^2 * e)
        # nm_to_m = 0.000000001  (plain decimal — no sci-notation in formula)
        formula = (
            f"=A{rr}*A{rr}*$B$3*$B$3"
            f"/(8*$B$4*($B$6*0.000000001)*($B$6*0.000000001)*$B$5)"
        )
        table_rows.append([int(n), formula])

    sol.set(8, 0, "Energy Levels")
    sol.fmt(8, 0, bold=True, font_color=PALETTE["header"])
    sol.merge(8, 0, 1, 3)

    sol.table(
        table_start, 0,
        headers=["n", "E_n (eV)"],
        rows=table_rows,
        number_format="0.0000",
        banded=True,
    )

    # Designate columns: n is X, E_n is Y.
    sol.designate(0, "X")
    sol.designate(1, "Y")
    sol.col_width(0, 60)
    sol.col_width(1, 120)

    # --- Transition / wavelength panel --------------------------------
    # Sheet rows of E_1 and E_2 data cells (1-based):
    #   E_1 is at table_start+2+0 = 11  → col B (col 1) → B11
    #   E_2 is at table_start+2+1 = 12  → col B (col 1) → B12
    r_E1 = table_start + 2           # = 11
    r_E2 = table_start + 2 + 1       # = 12

    panel_top = table_start + N_LEVELS + 2  # row below the table (0-based)
    sol.set(panel_top - 1, 0, "Transition  n = 2 → 1")
    sol.fmt(panel_top - 1, 0, bold=True, font_color=PALETTE["header"])
    sol.merge(panel_top - 1, 0, 1, 4)

    # delta_E in eV
    sol.set(panel_top, 0, "ΔE = E₂ − E₁ (eV)")
    sol.formula(panel_top, 1, f"=B{r_E2}-B{r_E1}")
    sol.fmt(panel_top, 1, bg=PALETTE["good"], bold=True,
            align="center", number_format="0.0000")

    # delta_E in Joules (multiply by e stored in B5)
    sol.set(panel_top + 1, 0, "ΔE (J)")
    sol.formula(panel_top + 1, 1, f"=(B{r_E2}-B{r_E1})*$B$5")
    sol.fmt(panel_top + 1, 1, bg=PALETTE["band"], bold=False,
            align="center", number_format="0.0000000000000000000")

    # wavelength in nm: lambda = h*c / delta_E_J
    # delta_E_J = (B12-B11)*B5
    # h*c in J·m: $B$3 * $B$7
    # convert to nm: multiply by 1000000000
    sol.set(panel_top + 2, 0, "λ = hc/ΔE (nm)")
    sol.formula(
        panel_top + 2, 1,
        f"=$B$3*$B$7/((B{r_E2}-B{r_E1})*$B$5)*1000000000"
    )
    sol.fmt(panel_top + 2, 1, bg=PALETTE["good"], bold=True,
            align="center", number_format="0.00")

    sol.box(panel_top, 0, panel_top + 2, 1,
            color=PALETTE["header"], width=1.2)
    sol.col_width(0, 200)
    sol.col_width(1, 130)

    # -------  Numerical values for chart / verify  -------------------
    r0_chart = table_start + 1    # 0-based first data row
    r1_chart = table_start + N_LEVELS  # 0-based last data row

    # --- Chart (data-bound, parabolic E vs n) -------------------------
    sol.chart(
        [Series(
            x=ns.tolist(),
            y=E_eV_vals.tolist(),
            label="E_n (eV)",
            plot_type="Line+Symbol",
            color=PALETTE["header"],
            linewidth=2.0,
            marker="o",
            markersize=7.0,
            markerfacecolor=PALETTE["warn"],
            markeredgecolor=PALETTE["header"],
            x_col=0,
            y_col=1,
            row_start=r0_chart,
            row_end=r1_chart,
        )],
        at=(350, 30),
        size=(430, 300),
        title="Energy Levels: Particle in a 1D Box",
        xlabel="Quantum number  n",
        ylabel="Energy  E_n  (eV)",
        grid=True,
        legend=True,
    )

    # --- LaTeX equation -----------------------------------------------
    sol.equation(
        r"E_n = \frac{n^2 h^2}{8 m L^2}",
        at=(350, 345),
        fontsize=22,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(280, 58),
    )

    # --- Pedagogic notes ---------------------------------------------
    sol.note(8, 0,
             "Energy levels scale as n^2 (parabolic). "
             "Only the box width L determines the scale.",
             kind="note")
    sol.note(5, 1,
             "E scales as 1/L^2: doubling L reduces all energies by a factor of 4.",
             kind="note")
    sol.note(table_start + 2, 0,
             "n=1 is the zero-point energy — the particle can never be "
             "at rest (uncertainty principle).",
             kind="note")

    # ── Save ──────────────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "exercises", "Year 3",
    )
    out_path = os.path.join(out_dir, "Particle in a 1D Box.ksheet")
    wb.save(out_path)
    return out_path


if __name__ == "__main__":
    print("Wrote", build())
