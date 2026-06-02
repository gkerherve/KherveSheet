"""Build the "UV-Vis Absorption" demo .ksheet example.

A spectroscopy example demonstrating Beer-Lambert law: A = epsilon * c * l,
Gaussian absorption band modelling, and the %T = 100 * 10^(-A) relationship.
All output cells are live formulas — editing any input rescales the
absorbance spectrum and transmittance curve instantly.

Concentration is stored in mM (millimolar) to avoid sub-milli values that
would round to zero in the 3-decimal display.  Formulas convert mM → mol/L
with the factor /1000.

Run:  python examples/build_uvvis.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import numpy as np

from ksheet_author import Workbook, Series, PALETTE

# ── Physics parameters (initial values) ──────────────────────────────
EPS   = 25000.0   # molar absorptivity  ε  (L/mol/cm)
C_MM  = 0.1       # concentration           (mM = mmol/L)
C_MOL = C_MM / 1000.0   # in mol/L for numpy
L     = 1.0       # path length             (cm)
LAM0  = 450.0     # band centre   λ₀        (nm)
FWHM  = 60.0      # band FWHM               (nm)

# Spectrum wavelength grid: 200–800 nm in 5 nm steps → 121 points
LAMBDA = np.arange(200, 805, 5, dtype=float)
N = len(LAMBDA)   # 121

# Pre-compute spectrum for the initial render (numpy) — these values
# must agree exactly with what the formula cells will evaluate to.
# A_peak = eps * c_mol * l  = 25000 * 0.0001 * 1 = 2.5
A_PEAK = EPS * C_MOL * L
A_SPEC = A_PEAK * np.exp(
    -4 * np.log(2) * ((LAMBDA - LAM0) / FWHM) ** 2
)
T_SPEC = 100.0 * 10.0 ** (-A_SPEC)


def build() -> str:
    wb = Workbook(min_rows=135, min_cols=14)
    s  = wb.add_sheet("UV-Vis")

    # ── Column widths ────────────────────────────────────────────────
    s.col_width(0, 210)   # label column
    s.col_width(1, 110)   # value column
    s.col_width(2, 18)    # spacer
    s.col_width(3, 90)    # λ (nm)
    s.col_width(4, 110)   # Absorbance
    s.col_width(5, 120)   # %Transmittance
    s.col_width(6, 18)    # spacer
    s.col_width(7, 160)   # summary label
    s.col_width(8, 110)   # summary value

    # ── Title block ──────────────────────────────────────────────────
    s.title_block("UV-Vis Absorption Spectroscopy",
                  "Beer-Lambert law: A = ε c l  —  "
                  "Gaussian single-band model",
                  row=0, col=0, span=8)

    # ── Input panel ─────────────────────────────────────────────────
    # Inputs occupy rows 4..8 (0-based), column 1.
    # Absolute refs in formulas:
    #   $B$5 = ε (L/mol/cm)
    #   $B$6 = c (mM)            ← formula uses $B$6/1000 to get mol/L
    #   $B$7 = l (cm)
    #   $B$8 = λ₀ (nm)
    #   $B$9 = FWHM (nm)
    s.set(3, 0, "Editable Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Molar absorptivity ε (L/mol/cm)", EPS),    # B5  row=4
        ("Concentration c (mM)",                 C_MM),   # B6  row=5
        ("Path length l (cm)",                   L),      # B7  row=6
        ("Band centre λ₀ (nm)",         LAM0),  # B8  row=7
        ("Band FWHM (nm)",                       FWHM),   # B9  row=8
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.000")

    s.box(4, 0, 8, 1, color=PALETTE["accent"], width=1.5)

    # ── Notes ────────────────────────────────────────────────────────
    s.note(4, 1,
           "Beer-Lambert law (A = ε c l) is linear: doubling any of "
           "ε, c, or l doubles A at every wavelength. Try it!",
           kind="note")
    s.note(5, 1,
           "Change concentration c here (e.g. 0.2 mM) to see the full "
           "spectrum scale: absorbance doubles, transmittance halves on "
           "a log scale.",
           kind="note")
    s.note(7, 1,
           "%T = 100 × 10^(−A). At A=1, %T=10%; at A=2, %T=1%."
           " This non-linear relationship is why A is preferred for "
           "quantitative work.",
           kind="note")

    # ── Summary panel ───────────────────────────────────────────────
    # All four cells are live formulas.
    # A_peak = eps * (c_mM / 1000) * l  = $B$5 * ($B$6/1000) * $B$7
    s.set(3, 7, "Summary")
    s.fmt(3, 7, bold=True, font_color=PALETTE["header"])

    summ_rows = [
        ("Peak absorbance A",
         "=$B$5*($B$6/1000)*$B$7",
         PALETTE["good"]),
        ("%T at peak (%)",
         "=100*POWER(10,-$B$5*($B$6/1000)*$B$7)",
         PALETTE["band"]),
        ("Band centre λ₀ (nm)",
         "=$B$8",
         PALETTE["band_alt"]),
        ("Band FWHM (nm)",
         "=$B$9",
         PALETTE["band_alt"]),
    ]
    for i, (lbl, expr, col) in enumerate(summ_rows):
        r = 4 + i
        s.set(r, 7, lbl)
        s.formula(r, 8, expr)
        s.fmt(r, 7, align="left")
        s.fmt(r, 8, bg=col, align="center", number_format="0.000", bold=True)

    s.box(4, 7, 7, 8, color=PALETTE["header"], width=1.5)

    # ── Data table ─────────────────────────────────────────────────
    # Header at TABLE_START (row 10, 0-based) → sheet row 11.
    # First data row: 0-based row 11 → sheet row 12.
    # Wavelength in column D (col index 3).
    # Absorbance in column E (col index 4).
    # %T in column F (col index 5).
    # A(lambda) = A_peak * EXP(-4*LN(2)*((lambda-lambda0)/FWHM)^2)
    #           = $B$5*($B$6/1000)*$B$7 * EXP(...)
    # %T        = 100 * POWER(10, -A_cell)
    TABLE_START = 10

    s.set(9, 3, "Absorption Spectrum  (200–800 nm, step 5 nm)")
    s.fmt(9, 3, bold=True, font_color=PALETTE["header"])

    rows = []
    for k, lam in enumerate(LAMBDA):
        # 1-based sheet row of this data cell:
        # header at sheet row TABLE_START+1=11, first data at sheet row 12
        sr = TABLE_START + 2 + k   # 1-based
        lam_ref = f"D{sr}"
        absorbance_formula = (
            f"=$B$5*($B$6/1000)*$B$7"
            f"*EXP(-4*LN(2)*(({lam_ref}-$B$8)/$B$9)^2)"
        )
        transmittance_formula = f"=100*POWER(10,-E{sr})"
        rows.append([
            float(lam),
            absorbance_formula,
            transmittance_formula,
        ])

    s.table(TABLE_START, 3,
            headers=["λ (nm)", "Absorbance A", "%Transmittance"],
            rows=rows,
            number_format="0.000",
            banded=True)

    # Mark columns for axis hints
    s.designate(3, "X")   # lambda
    s.designate(4, "Y")   # absorbance
    s.designate(5, "Y")   # %T

    # ── Chart: Absorbance vs wavelength ─────────────────────────────
    # Data occupies 0-based rows TABLE_START+1 .. TABLE_START+N (inclusive).
    r0 = TABLE_START + 1
    r1 = TABLE_START + N   # = 10 + 121 = 131 (inclusive, 0-based)

    s.chart(
        [
            Series(
                LAMBDA, A_SPEC,
                label="Absorbance A",
                plot_type="Line",
                color="#4472c4",
                linewidth=2.5,
                x_col=3,     # column D (0-based)
                y_col=4,     # column E (0-based)
                row_start=r0,
                row_end=r1,
            ),
        ],
        at=(820, 20),
        size=(480, 300),
        title="UV-Vis Absorbance Spectrum",
        xlabel="λ (nm)",
        ylabel="Absorbance A",
        grid=True,
        legend=True,
    )

    # ── Chart: %Transmittance vs wavelength ──────────────────────────
    s.chart(
        [
            Series(
                LAMBDA, T_SPEC,
                label="%Transmittance",
                plot_type="Line",
                color="#ed7d31",
                linewidth=2.5,
                x_col=3,     # column D (0-based)
                y_col=5,     # column F (0-based)
                row_start=r0,
                row_end=r1,
            ),
        ],
        at=(820, 340),
        size=(480, 300),
        title="UV-Vis %Transmittance Spectrum",
        xlabel="λ (nm)",
        ylabel="%T",
        grid=True,
        legend=True,
    )

    # ── LaTeX equations ──────────────────────────────────────────────
    # Gaussian Beer-Lambert equation in mathtext.
    s.equation(
        r"A(\lambda) = \epsilon\,c\,l\;\exp\!\left("
        r"-4\ln 2\left(\frac{\lambda-\lambda_0}{\Delta\lambda}\right)^{\!2}"
        r"\right)",
        at=(820, 658),
        fontsize=15,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(480, 62),
    )
    s.equation(
        r"\%T = 100 \times 10^{-A}",
        at=(820, 732),
        fontsize=16,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.2,
        size=(280, 50),
    )

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "UV-Vis Absorption.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
