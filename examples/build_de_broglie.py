"""Build the "de Broglie Electron Wavelength" demo .ksheet example.

Fundamental non-relativistic de Broglie relation: lambda = h/p = h/sqrt(2mE).
For electrons with E in eV this simplifies to lambda (nm) = 1.2264 / sqrt(E).

Features: title block, styled/banded data table driven by formulas,
designated X/Y columns, a summary panel, three yellow notes,
an embedded log-scale chart, and a mathtext equation.

Run:  python examples/build_de_broglie.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Ensure the project root is importable.
_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_DIR)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# Physical constants (for annotation only — formulas use the simplified
# constant 1.2264 which folds h, m_e, and the eV→J conversion).
H_PLANCK_EV_NM = 1.2264   # nm · eV^(1/2)  (= h / sqrt(2 m_e e) in nm units)

# Input highlight energy (eV) — this is the editable literal.
E0_EV = 100.0

# Fixed kinetic-energy grid: 40 points from 1 to 1000 eV on a log scale.
# These are LITERALS in the sheet (the independent variable column).
N_PTS = 40
E_GRID = np.round(np.geomspace(1.0, 1000.0, N_PTS), 6)

# Pre-compute numpy arrays for chart initial render (must match formula output).
LAMBDA_NM = H_PLANCK_EV_NM / np.sqrt(E_GRID)      # lambda (nm)
INV_LAMBDA = 1.0 / LAMBDA_NM                       # 1/lambda (nm⁻¹), ∝ momentum


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=14)
    s = wb.add_sheet("de Broglie")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 160)   # A: label / E (eV)
    s.col_width(1, 130)   # B: value / lambda (nm)
    s.col_width(2, 150)   # C: 1/lambda (nm⁻¹)
    s.col_width(3, 20)    # D: spacer
    s.col_width(4, 200)   # E: summary labels
    s.col_width(5, 130)   # F: summary values

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "de Broglie Electron Wavelength",
        "Non-relativistic wavelength vs kinetic energy  λ(nm) = 1.2264 / √E(eV)",
        span=7,
    )

    # ── Input panel ───────────────────────────────────────────────────
    # Row 3 (0-based) = sheet row 4: section label
    s.set(3, 0, "Editable Input")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    # Row 4 (0-based) = sheet row 5 → cell B5 (col 1)
    s.set(4, 0, "Highlight energy E₀ (eV)")
    s.set(4, 1, E0_EV)   # LITERAL — the editable input cell
    s.fmt(4, 0, align="left")
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.00",
          bold=True)
    s.box(4, 0, 4, 1, color=PALETTE["accent"], width=1.5)

    # Note: what to edit
    s.note(4, 1,
           "Edit E₀ here (eV). The summary values below "
           "recompute instantly via formulas referencing this cell.",
           kind="note")

    # ── Summary panel ─────────────────────────────────────────────────
    # Placed at col E–F (cols 4–5), rows 3–7 (0-based).
    s.set(3, 4, "Summary at E₀")
    s.fmt(3, 4, bold=True, font_color=PALETTE["header"])

    # lambda at E0: =1.2264/SQRT($B$5)   [B5 = row 4, col 1]
    s.set(4, 4, "λ at E₀ (nm)")
    s.formula(4, 5, "=1.2264/SQRT($B$5)")
    s.fmt(4, 4, align="left")
    s.fmt(4, 5, bg=PALETTE["good"], align="center",
          number_format="0.0000", bold=True)

    # 1/lambda at E0: momentum-proportional (nm⁻¹)
    s.set(5, 4, "1/λ at E₀ (nm⁻¹)")
    s.formula(5, 5, "=SQRT($B$5)/1.2264")
    s.fmt(5, 4, align="left")
    s.fmt(5, 5, bg=PALETTE["band"], align="center",
          number_format="0.0000", bold=True)

    # Energy at which lambda = 0.1 nm: E = (1.2264/0.1)^2
    # = (12.264)^2 = 150.406 eV — formula: =(1.2264/0.1)^2
    s.set(6, 4, "E where λ = 0.1 nm (eV)")
    s.formula(6, 5, "=POWER(1.2264/0.1, 2)")
    s.fmt(6, 4, align="left")
    s.fmt(6, 5, bg=PALETTE["band"], align="center",
          number_format="0.00", bold=True)

    # Relativistic correction check: lambda_rel / lambda ≈ 1 - E/(2*511000)
    # at E0 eV (m_e c^2 = 511000 eV); small deviation means NR is valid.
    s.set(7, 4, "NR correction δ at E₀")
    s.formula(7, 5, "=$B$5/(2*511000)")
    s.fmt(7, 4, align="left")
    s.fmt(7, 5, bg=PALETTE["warn"], align="center",
          number_format="0.0000", bold=True)

    s.box(3, 4, 7, 5, color=PALETTE["header"], width=1.5)
    s.note(6, 5,
           "lambda = 0.1 nm is the atomic bond-length scale — "
           "electrons above ~150 eV can resolve crystal structure.",
           kind="note")

    # ── Data table ────────────────────────────────────────────────────
    # Table starts at row 9 (0-based) → header at sheet row 10,
    # first data row at sheet row 11, i.e. 1-based row = 11.
    TABLE_START = 9  # 0-based

    s.set(8, 0, "Kinetic Energy vs de Broglie Wavelength")
    s.fmt(8, 0, bold=True, font_color=PALETTE["header"])

    # Build table rows: col A = E literal, col B = lambda formula,
    # col C = 1/lambda formula (references the B cell in the same row).
    table_rows = []
    for k, e_val in enumerate(E_GRID):
        # 1-based sheet row of this data row:
        #   header is at sheet row TABLE_START+1 = 10,
        #   first data row is TABLE_START+2 = 11.
        sheet_r = TABLE_START + 2 + k
        table_rows.append([
            round(float(e_val), 6),                  # col A: E (eV) — literal
            f"=1.2264/SQRT(A{sheet_r})",             # col B: lambda (nm)
            f"=1/B{sheet_r}",                        # col C: 1/lambda (nm⁻¹)
        ])

    s.table(
        TABLE_START, 0,
        headers=["E (eV)", "λ (nm)", "1/λ (nm⁻¹)"],
        rows=table_rows,
        number_format="0.0000",
        banded=True,
    )

    # Right-align all numeric columns.
    for k in range(N_PTS):
        r = TABLE_START + 1 + k
        s.fmt(r, 0, align="right", number_format="0.000")
        s.fmt(r, 1, align="right", number_format="0.0000")
        s.fmt(r, 2, align="right", number_format="0.0000")

    # Designate axes for chart auto-detection.
    s.designate(0, "X")
    s.designate(1, "Y")
    s.designate(2, "Y")

    # ── Chart ─────────────────────────────────────────────────────────
    # Data rows (0-based, inclusive):
    #   row TABLE_START+1 through TABLE_START+N_PTS (i.e. 10 to 49).
    row_start = TABLE_START + 1
    row_end   = TABLE_START + N_PTS   # = 49

    s.chart(
        [
            Series(
                E_GRID, LAMBDA_NM,
                label="λ (nm)",
                plot_type="Line",
                color=PALETTE["header"],
                linewidth=2.0,
                x_col=0,   # column A: E (eV)
                y_col=1,   # column B: lambda (nm)
                row_start=row_start,
                row_end=row_end,
            ),
        ],
        at=(490, 30),
        size=(470, 340),
        title="de Broglie Wavelength vs Kinetic Energy",
        xlabel="Kinetic energy (eV)",
        ylabel="λ (nm)",
        xscale="log",
        yscale="log",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    s.equation(
        r"\lambda = \frac{h}{p} = \frac{h}{\sqrt{2 m_e E}}",
        at=(490, 390),
        fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(310, 60),
    )

    # ── Yellow sticky notes ───────────────────────────────────────────
    s.note(
        0, 8,
        "Wave–particle duality: every moving particle has a de Broglie "
        "wavelength λ = h/p. For electrons this reaches atomic scales "
        "(0.1–1 nm) at laboratory energies, enabling electron diffraction "
        "and microscopy.",
        kind="note",
    )
    s.note(
        2, 8,
        "Why electrons resolve finer than visible light: photons at 100 eV "
        "have λ ≈ 12 nm (EUV), but electrons at 100 eV have "
        "λ ≈ 0.12 nm — 100× shorter. TEM exploits this "
        "to image individual atoms.",
        kind="note",
    )
    s.note(
        4, 8,
        "Non-relativistic validity: this formula assumes E ≪ m_e c² "
        "= 511 keV. The relativistic correction is ~E/(2×511 000) "
        "— shown in the summary panel. Below 10 keV the error is <1%.",
        kind="note",
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(_DIR, "de Broglie Electron Wavelength.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    path = build()
    print("Wrote", path)
