"""Build the "Drude Free-Electron Model" demo .ksheet example.

Solid-state physics: the classical Drude model of metallic conduction.
Editable inputs (carrier density n, electron charge e, mass m, eps0) drive
formula columns for conductivity sigma and resistivity rho as a function of
the relaxation time tau.  A chart shows sigma(tau) live-bound to the sheet
columns.  A LaTeX equation and three sticky notes complete the workbook.

Run:  python examples/build_drude.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import numpy as np
from ksheet_author import Workbook, Series, PALETTE

# ---------------------------------------------------------------------------
# Physical constants / default inputs
# ---------------------------------------------------------------------------
n_val   = 8.5e28      # carrier density  (m^-3)  copper
e_val   = 1.602e-19   # electron charge  (C)
m_val   = 9.109e-31   # electron mass    (kg)
eps0_val = 8.854e-12  # vacuum permittivity (F/m)

# Independent variable grid: tau from 1e-15 to 4e-14 s (40 points).
# We write plain Python floats as literal cell values -- that is correct
# (rule 0: literals for the independent variable grid are allowed).
N_TAU = 40
tau_vals = np.linspace(1e-15, 4e-14, N_TAU)  # seconds

# Pre-compute sigma for chart render and sanity checks (numpy only -- these
# numbers are NOT written into output cells).
sigma_arr = n_val * e_val**2 * tau_vals / m_val   # S/m


def col_letter(c: int) -> str:
    """0-based column index → spreadsheet letter (A, B, ..., Z, AA, ...)."""
    result = ""
    c += 1
    while c:
        c, rem = divmod(c - 1, 26)
        result = chr(65 + rem) + result
    return result


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=12)
    s  = wb.add_sheet("Drude Model")

    # ── Column layout ───────────────────────────────────────────────────
    # A(0)  label / tau (s)
    # B(1)  sigma (S/m)   ← formula
    # C(2)  rho (Ω·m)     ← formula
    # E(4)  input labels
    # F(5)  input values  ← editable literals
    # H(7)  summary labels
    # I(8)  summary values ← formulas

    # Absolute cell refs for the four input cells (all in column F = col 5).
    # Row 0-based → 1-based sheet row.
    ROW_N    = 4   # 0-based → sheet row 5  → $F$5
    ROW_E    = 5   # 0-based → sheet row 6  → $F$6
    ROW_M    = 6   # 0-based → sheet row 7  → $F$7
    ROW_EPS0 = 7   # 0-based → sheet row 8  → $F$8
    IN_COL   = 5   # column F (0-based)

    ref_n    = f"$F${ROW_N    + 1}"  # $F$5
    ref_e    = f"$F${ROW_E    + 1}"  # $F$6
    ref_m    = f"$F${ROW_M    + 1}"  # $F$7
    ref_eps0 = f"$F${ROW_EPS0 + 1}"  # $F$8

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block("Drude Free-Electron Model",
                  "Classical electron transport in metals — "
                  "conductivity and resistivity vs. relaxation time")
    s.col_width(0, 175)
    s.col_width(1, 130)
    s.col_width(2, 130)
    s.col_width(3, 20)   # spacer
    s.col_width(4, 200)
    s.col_width(5, 140)
    s.col_width(6, 20)   # spacer
    s.col_width(7, 170)
    s.col_width(8, 140)

    # ── Input panel ────────────────────────────────────────────────────
    s.set(3, 4, "Input Parameters")
    s.fmt(3, 4, bold=True, font_color=PALETTE["accent"], font_size=11)

    inputs = [
        ("n  — carrier density (m⁻³)", n_val),
        ("e  — electron charge (C)",    e_val),
        ("m  — electron mass (kg)",     m_val),
        ("ε₀ — vacuum permittivity (F/m)", eps0_val),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = ROW_N + i
        s.set(r, 4, lbl)
        s.set(r, IN_COL, val)
        s.fmt(r, 4, align="left")
        s.fmt(r, IN_COL, bg=PALETTE["warn"], align="right", bold=True)

    s.box(ROW_N, 4, ROW_EPS0, IN_COL,
          color=PALETTE["accent"], width=1.5)

    s.note(ROW_N, IN_COL,
           "Edit n, e, m, or ε₀ here — sigma and rho columns recalculate "
           "immediately (copper default: n ≈ 8.5 × 10²⁸ m⁻³).",
           kind="note")

    # ── Data table header ──────────────────────────────────────────────
    TABLE_START = 10   # 0-based: header row; data rows = 11 .. 50
    s.set(TABLE_START - 1, 0, "Transport Properties vs. Relaxation Time")
    s.fmt(TABLE_START - 1, 0, bold=True, font_color=PALETTE["header"])

    headers = [
        "τ (s)",          # τ (s)
        "σ (S/m)",        # σ (S/m)
        "ρ (Ω·m)",  # ρ (Ω·m)
    ]
    # Write header row manually (TABLE_START is 0-based header row).
    for j, h in enumerate(headers):
        s.set(TABLE_START, j, h)
        s.fmt(TABLE_START, j, bold=True,
              bg=PALETTE["header"], font_color=PALETTE["header_text"],
              align="center")

    # ── Data rows ──────────────────────────────────────────────────────
    # col A (0): tau literal (s)  — independent variable, plain decimal float
    # col B (1): sigma formula referencing $F$5..$F$7 and the tau cell
    # col C (2): rho formula = 1 / sigma cell in same row
    for i, tau in enumerate(tau_vals):
        r = TABLE_START + 1 + i   # 0-based data row
        # 1-based sheet row for formula strings
        sr = r + 1
        # Column letters for this data row
        col_tau   = col_letter(0)   # A
        col_sigma = col_letter(1)   # B
        col_rho   = col_letter(2)   # C

        # Tau as a plain decimal (Python float → str avoids scientific notation).
        s.set(r, 0, tau)

        # sigma = n * e^2 * tau / m
        # Use e*e instead of e^2 (no POWER call needed; avoids any ambiguity).
        f_sigma = (f"={ref_n}*{ref_e}*{ref_e}*{col_tau}{sr}/{ref_m}")
        s.formula(r, 1, f_sigma)

        # rho = 1 / sigma
        f_rho = f"=1/{col_sigma}{sr}"
        s.formula(r, 2, f_rho)

        # Formatting: banded rows
        band = PALETTE["band_alt"] if (i % 2) else None
        s.fmt(r, 0, align="right", number_format="0.00E+00",
              bg=band if band else None)
        s.fmt(r, 1, align="right", number_format="0.00E+00",
              bg=band if band else None)
        s.fmt(r, 2, align="right", number_format="0.00E+00",
              bg=band if band else None)

    # Outer border around table
    s.box(TABLE_START, 0,
          TABLE_START + N_TAU, 2,
          color=PALETTE["header"], width=1.0)

    # Designate columns for axis hints
    s.designate(0, "X")
    s.designate(1, "Y")
    s.designate(2, "Y")

    # ── Summary panel ──────────────────────────────────────────────────
    # Reference the last data row (largest tau = copper-ish) and mid-range.
    FIRST_DATA_SR = TABLE_START + 2   # 1-based sheet row of row i=0
    LAST_DATA_SR  = TABLE_START + 1 + N_TAU  # 1-based sheet row of row i=N_TAU-1
    # Mid-table row: index 9 (tau ~ 1e-14 s, near typical metals)
    MID_DATA_SR   = TABLE_START + 2 + 9

    s.set(3, 7, "Summary")
    s.fmt(3, 7, bold=True, font_color=PALETTE["header"], font_size=11)

    SUMM_ROW = 4

    # sigma at mid tau (reference point ~ 1e-14 s)
    s.set(SUMM_ROW, 7, "σ at τ≈ 1×10⁻¹⁴ s (S/m)")
    s.formula(SUMM_ROW, 8, f"=B{MID_DATA_SR}")
    s.fmt(SUMM_ROW, 7, align="left")
    s.fmt(SUMM_ROW, 8, bg=PALETTE["good"], align="right", bold=True,
          number_format="0.00E+00")

    # sigma max (last row, largest tau)
    s.set(SUMM_ROW + 1, 7, "σ max in table (S/m)")
    s.formula(SUMM_ROW + 1, 8, f"=MAX(B{FIRST_DATA_SR}:B{LAST_DATA_SR})")
    s.fmt(SUMM_ROW + 1, 7, align="left")
    s.fmt(SUMM_ROW + 1, 8, bg=PALETTE["band"], align="right", bold=True,
          number_format="0.00E+00")

    # rho at mid tau
    s.set(SUMM_ROW + 2, 7, "ρ at τ≈ 1×10⁻¹⁴ s (Ω·m)")
    s.formula(SUMM_ROW + 2, 8, f"=C{MID_DATA_SR}")
    s.fmt(SUMM_ROW + 2, 7, align="left")
    s.fmt(SUMM_ROW + 2, 8, bg=PALETTE["band_alt"], align="right", bold=True,
          number_format="0.00E+00")

    # Plasma angular frequency (formula: SQRT(n*e*e/(eps0*m)))
    s.set(SUMM_ROW + 3, 7, "ωₚ — plasma frequency (rad/s)")
    s.formula(SUMM_ROW + 3, 8,
              f"=SQRT({ref_n}*{ref_e}*{ref_e}/({ref_eps0}*{ref_m}))")
    s.fmt(SUMM_ROW + 3, 7, align="left")
    s.fmt(SUMM_ROW + 3, 8, bg=PALETTE["accent"], font_color="#ffffff",
          align="right", bold=True, number_format="0.00E+00")

    s.box(SUMM_ROW, 7, SUMM_ROW + 3, 8,
          color=PALETTE["header"], width=1.5)
    s.col_width(8, 140)

    # ── Notes ──────────────────────────────────────────────────────────
    s.note(TABLE_START, 1,
           "sigma is LINEAR in tau (Drude model): doubling tau doubles "
           "conductivity.  Edit tau values in column A to explore.",
           kind="note")
    s.note(SUMM_ROW + 3, 8,
           "The plasma frequency omega_p depends only on n, e, m, eps0 — "
           "NOT on tau.  Metals are reflective below omega_p (UV range).",
           kind="note")
    s.note(TABLE_START, 2,
           "rho = 1 / sigma (Drude model neglects electron-electron "
           "and electron-phonon scattering details).",
           kind="note")

    # ── Chart: sigma vs tau (live-bound) ───────────────────────────────
    # Data rows in 0-based coords: TABLE_START+1 .. TABLE_START+N_TAU
    r0 = TABLE_START + 1
    r1 = TABLE_START + N_TAU

    s.chart(
        [Series(
            tau_vals, sigma_arr,
            label="σ (S/m)",
            plot_type="Line+Symbol",
            color=PALETTE["header"],
            linewidth=2.0,
            marker="o", markersize=4.0,
            x_col=0, y_col=1,
            row_start=r0, row_end=r1,
        )],
        at=(680, 20), size=(460, 320),
        title="Drude Conductivity σ vs. τ",
        xlabel="τ (s)",
        ylabel="σ (S/m)",
        grid=True, legend=True,
    )

    # ── LaTeX equation (mathtext) ───────────────────────────────────────
    # sigma = n e^2 tau / m   and   omega_p = sqrt(n e^2 / eps0 m)
    eq_str = (
        r"\sigma = \frac{n e^{2} \tau}{m} \quad , \quad"
        r"\omega_{p} = \sqrt{\frac{n e^{2}}{\epsilon_{0} m}}"
    )
    s.equation(eq_str,
               at=(680, 360), fontsize=18,
               color="#1a1a2e",
               bg_color="#f0f4ff",
               border_color=PALETTE["header"],
               border_width=1.5,
               size=(460, 60))

    # ── Save ────────────────────────────────────────────────────────────
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Drude Free-Electron Model.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
