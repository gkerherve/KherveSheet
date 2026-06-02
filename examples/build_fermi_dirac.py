"""Build the "Fermi-Dirac Distribution" demo .ksheet example.

Demonstrates the Fermi-Dirac occupation probability
    f(E) = 1 / (exp((E - EF) / (kB * T)) + 1)
as a richly formatted, fully live sheet: editing EF or T in the input
cells instantly reshapes the S-curve in both the table and the embedded
chart.

Run:  python examples/build_fermi_dirac.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os

import numpy as np

from ksheet_author import Workbook, Series, PALETTE

# ---------------------------------------------------------------------------
# Physical constants and default inputs
# ---------------------------------------------------------------------------
KB = 0.00008617       # Boltzmann constant in eV/K (plain decimal — NEVER 8.617e-5)
EF_DEFAULT = 5.0      # Fermi energy (eV)
T_DEFAULT = 300.0     # Temperature (K)

# Energy grid: 41 fixed literal points spanning EF-0.5 .. EF+0.5
N_POINTS = 41
E_MIN = 4.5
E_MAX = 5.5
energies = np.linspace(E_MIN, E_MAX, N_POINTS)

# Pre-compute f(E) at default inputs (matches what the bound columns will show)
kBT_default = KB * T_DEFAULT
f_values = 1.0 / (np.exp((energies - EF_DEFAULT) / kBT_default) + 1.0)


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=14)
    s = wb.add_sheet("Fermi-Dirac")

    # ── Column widths ────────────────────────────────────────────────────
    s.col_width(0, 160)   # E (eV) label / energy
    s.col_width(1, 140)   # f(E) / input values
    s.col_width(2, 20)    # spacer
    s.col_width(3, 220)   # summary labels
    s.col_width(4, 120)   # summary values

    # ── Title block ──────────────────────────────────────────────────────
    s.title_block(
        "Fermi-Dirac Distribution",
        "Electron occupation probability in a solid   f(E) = 1 / (exp((E−Eⁱ)/k₂T) + 1)",
        span=7,
    )

    # ── Input panel ──────────────────────────────────────────────────────
    # Inputs live at:  EF = B5 (row 4, col 1),  T = B6 (row 5, col 1)
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    s.set(4, 0, "Fermi energy  EF (eV)")
    s.set(4, 1, EF_DEFAULT)
    s.fmt(4, 0, align="left")
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.000")

    s.set(5, 0, "Temperature  T (K)")
    s.set(5, 1, T_DEFAULT)
    s.fmt(5, 0, align="left")
    s.fmt(5, 1, bg=PALETTE["warn"], align="center", number_format="0.0")

    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.2)

    s.note(4, 1,
           "Edit EF (eV) here — the table and chart recompute instantly.",
           kind="note")
    s.note(5, 1,
           "Raise T to broaden the S-curve; lower T (e.g. 30 K) to sharpen it "
           "toward a perfect step function.",
           kind="note")

    # ── Data table ───────────────────────────────────────────────────────
    # Table header at sheet row (table_start + 1) = row 8 (0-based 7).
    # First data row at sheet row 9, i.e. 0-based row 8.
    # Energy column A, f(E) column B.
    TABLE_START = 7   # 0-based; header occupies this row

    rows = []
    for k in range(N_POINTS):
        # 0-based data row index in the sheet
        r0 = TABLE_START + 1 + k
        # 1-based sheet row used in the formula string
        rr = r0 + 1
        e_val = round(float(energies[k]), 4)
        # Formula for f(E): use 0.00008617 (plain decimal) for kB
        formula = f"=1/(EXP((A{rr}-$B$5)/(0.00008617*$B$6))+1)"
        rows.append([e_val, formula])

    s.set(6, 0, "Occupation probability table")
    s.fmt(6, 0, bold=True, font_color=PALETTE["header"])

    s.table(
        TABLE_START, 0,
        headers=["E (eV)", "f(E)"],
        rows=rows,
        number_format="0.0000",
        banded=True,
    )

    # Designate columns for chart axis hints
    s.designate(0, "X")
    s.designate(1, "Y")

    # ── Summary panel ─────────────────────────────────────────────────────
    # Locate first/last data rows in 1-based sheet notation for AVERAGE/ranges.
    # We will compute specific summary values via formulas referencing inputs.
    #
    # f(EF) = 0.5 always (by definition of the Fermi level).
    # We compute it from the formula so the sheet proves it: at E = EF,
    # EXP(0) = 1, so 1/(1+1) = 0.5.  We reference $B$5 directly.
    # Thermal broadening width ~ kB * T.
    # f(EF + kBT) = 1/(exp(1)+1) ~ 0.269
    # f(EF - kBT) = 1/(exp(-1)+1) ~ 0.731

    SUMM_ROW = 3   # 0-based row for the summary header

    s.set(SUMM_ROW, 3, "Summary")
    s.fmt(SUMM_ROW, 3, bold=True, font_color=PALETTE["header"])

    # Row 4 (0-based) = sheet row 5: f at E=EF — should be exactly 0.5
    s.set(4, 3, "f(E = EF)")
    s.formula(4, 4, "=1/(EXP(($B$5-$B$5)/(0.00008617*$B$6))+1)")
    s.fmt(4, 3, align="left")
    s.fmt(4, 4, bg=PALETTE["good"], align="center", number_format="0.0000", bold=True)

    # Row 5 (0-based): thermal broadening kB*T (eV)
    s.set(5, 3, "Thermal broadening  kBT (eV)")
    s.formula(5, 4, "=0.00008617*$B$6")
    s.fmt(5, 3, align="left")
    s.fmt(5, 4, bg=PALETTE["band"], align="center", number_format="0.00000", bold=True)

    # Row 6 (0-based): f at EF + kBT  ~ 0.269
    s.set(6, 3, "f(EF + kBT)  (≈ 0.269 at any T)")
    s.formula(6, 4, "=1/(EXP(1)+1)")
    s.fmt(6, 3, align="left")
    s.fmt(6, 4, bg=PALETTE["band_alt"], align="center", number_format="0.0000", bold=True)

    # Row 7 (0-based): f at EF - kBT  ~ 0.731  (but table_start=7 so use col 3/4 safely)
    # Actually row 7 is the table header row — use col 3/4 which are free.
    # Let me shift summary rows down slightly to avoid collision.
    # Summary uses col 3 and col 4 which the table does NOT use (table is col 0-1).
    # Row 7 col 3 is fine since the table header is at row 7 col 0-1 only.
    s.set(7, 3, "f(EF − kBT)  (≈ 0.731 at any T)")
    s.formula(7, 4, "=1/(EXP(-1)+1)")
    s.fmt(7, 3, align="left")
    s.fmt(7, 4, bg=PALETTE["band_alt"], align="center", number_format="0.0000", bold=True)

    s.box(4, 3, 7, 4, color=PALETTE["header"], width=1.0)

    # Note on f(EF) = 0.5
    s.note(4, 3,
           "f(EF) = 1/2 at ALL temperatures — the Fermi energy is defined as "
           "the energy where occupation is exactly 50 %.",
           kind="note")

    # ── Chart: f(E) vs E (live-bound to table columns) ───────────────────
    # 0-based data rows: TABLE_START+1 .. TABLE_START+N_POINTS  (8..48)
    r_start = TABLE_START + 1
    r_end = TABLE_START + N_POINTS

    s.chart(
        [Series(
            x=energies,
            y=f_values,
            label="f(E)",
            plot_type="Line",
            color="#4472c4",
            linewidth=2.2,
            x_col=0,
            y_col=1,
            row_start=r_start,
            row_end=r_end,
        )],
        at=(540, 30),
        size=(430, 320),
        title="Fermi-Dirac Occupation Probability",
        xlabel="Energy E (eV)",
        ylabel="f(E)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ───────────────────────────────────────────────────
    # mathtext: use \frac (not \tfrac/\dfrac), \mathrm (not \text)
    s.equation(
        r"f(E) = \frac{1}{e^{(E - E_F) / k_B T} + 1}",
        at=(540, 370),
        fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.4,
        size=(310, 58),
    )

    # Third note — T→0 limit
    s.note(6, 3,
           "As T → 0 K, f(E) becomes a perfect step function: 1 below EF, "
           "0 above. At room temperature (300 K) the transition spans ~0.026 eV.",
           kind="note")

    # ── Save ─────────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Fermi-Dirac Distribution.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
