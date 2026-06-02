"""Build the "EDX Spectrum" demo .ksheet example.

Energy-Dispersive X-ray Spectroscopy (EDX/EDS) — a worked materials-
analysis example showing a synthetic spectrum of detector counts vs
X-ray energy (keV).  The spectrum is modelled as a flat continuum
(bremsstrahlung background) plus Gaussian characteristic-line peaks for
four elements (C, O, Al, Fe).  All derived columns are live formulas
so editing any amplitude, peak energy, FWHM or background level
immediately updates the table, summary panel and chart.

Run:  python examples/build_edx.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Make the project importable from any cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Physical / detector parameters ───────────────────────────────────
# Realistic Kα energies (keV):
#   C=0.277  O=0.525  Al=1.486  Fe=6.40
# Four elements chosen so both light-element overlap (C/O) and the
# heavier Fe peak are visible on a 0–10 keV axis.

ELEMENTS = [
    ("C",  0.277,  8000),   # name, E_Kα (keV), amplitude (counts)
    ("O",  0.525,  5000),
    ("Al", 1.486,  3500),
    ("Fe", 6.40,   2000),
]
FWHM_DEFAULT  = 0.13        # keV  (typical Si-drift detector resolution)
BG_DEFAULT    = 150         # counts (flat bremsstrahlung background)

# Energy grid: 0.00 → 10.00 keV, step 0.05 keV → 201 points.
E_MIN, E_MAX, E_STEP = 0.00, 10.00, 0.05
energies = np.arange(E_MIN, E_MAX + E_STEP * 0.5, E_STEP)
N = len(energies)   # 201


def _gaussian(E: np.ndarray, E0: float, A: float, fwhm: float) -> np.ndarray:
    """Gaussian peak: A * exp(-4 ln2 * ((E - E0)/fwhm)^2)."""
    return A * np.exp(-4 * np.log(2) * ((E - E0) / fwhm) ** 2)


def build() -> str:
    wb = Workbook(min_rows=220, min_cols=14)
    s = wb.add_sheet("EDX Spectrum")

    # ── Column layout ─────────────────────────────────────────────
    # col 0 = A: Energy (keV)   [literal grid]
    # col 1 = B: Peak C         [formula]
    # col 2 = C: Peak O         [formula]
    # col 3 = D: Peak Al        [formula]
    # col 4 = E: Peak Fe        [formula]
    # col 5 = F: Total counts   [formula]
    # col 6 = G: Background     [formula]
    # col 9..10: input panel
    # col 8: summary panel labels / values

    # ── Column widths ─────────────────────────────────────────────
    s.col_width(0, 90)   # Energy
    s.col_width(1, 80)   # Peak C
    s.col_width(2, 80)   # Peak O
    s.col_width(3, 80)   # Peak Al
    s.col_width(4, 80)   # Peak Fe
    s.col_width(5, 90)   # Total
    s.col_width(6, 90)   # Background
    s.col_width(7, 20)   # spacer
    s.col_width(8, 160)  # labels
    s.col_width(9, 110)  # values
    s.col_width(10, 20)  # spacer

    # ── Title block ───────────────────────────────────────────────
    s.title_block(
        "EDX Spectrum — Materials Analysis",
        "Synthetic energy-dispersive X-ray spectrum: C, O, Al, Fe Kα lines",
        row=0, col=0, span=10,
    )

    # ── Input panel (rows 2–12, cols 8–9) ─────────────────────────
    # Inputs are stored as absolute references so table formulas
    # use $J$... notation.
    #
    # Layout (0-based rows, col 8 = label, col 9 = value):
    #   row 2  : section header "Inputs"
    #   row 3  : FWHM
    #   row 4  : Background
    #   row 5  : --- element block header
    #   row 6  : E_C  (keV)
    #   row 7  : A_C  (counts)
    #   row 8  : E_O  (keV)
    #   row 9  : A_O  (counts)
    #   row 10 : E_Al (keV)
    #   row 11 : A_Al (counts)
    #   row 12 : E_Fe (keV)
    #   row 13 : A_Fe (counts)
    #
    # Cell refs (1-based sheet row = 0-based row + 1, col J = col 9):
    #   FWHM   → J4
    #   BG     → J5
    #   E_C    → J7    A_C  → J8
    #   E_O    → J9    A_O  → J10
    #   E_Al   → J11   A_Al → J12
    #   E_Fe   → J13   A_Fe → J14

    s.set(2, 8, "Editable Inputs")
    s.fmt(2, 8, bold=True, font_color=PALETTE["accent"], font_size=12)

    s.set(3, 8, "Detector FWHM (keV)")
    s.set(3, 9, FWHM_DEFAULT)
    s.fmt(3, 9, bg=PALETTE["warn"], align="center", number_format="0.000")

    s.set(4, 8, "Background level (counts)")
    s.set(4, 9, BG_DEFAULT)
    s.fmt(4, 9, bg=PALETTE["warn"], align="center", number_format="0.0")

    s.set(5, 8, "Element peaks")
    s.fmt(5, 8, bold=True, italic=True, font_color=PALETTE["header"])

    element_rows = []   # (label_row, value_row for E, label_row for A, value_row for A)
    for k, (el, e0, amp) in enumerate(ELEMENTS):
        re = 6 + k * 2      # row for peak energy  (0-based)
        ra = 7 + k * 2      # row for amplitude    (0-based)
        s.set(re, 8, f"E_{el}  Kα energy (keV)")
        s.set(re, 9, e0)
        s.fmt(re, 9, bg=PALETTE["warn"], align="center", number_format="0.000")
        s.set(ra, 8, f"A_{el}  amplitude (counts)")
        s.set(ra, 9, amp)
        s.fmt(ra, 9, bg=PALETTE["warn"], align="center", number_format="0")
        element_rows.append((re, ra))

    # 0-based rows → 1-based sheet rows for the formula refs:
    # FWHM  = row 3  → sheet row 4  → J4
    # BG    = row 4  → sheet row 5  → J5
    # E_C   = row 6  → sheet row 7  → J7
    # A_C   = row 7  → sheet row 8  → J8
    # E_O   = row 8  → sheet row 9  → J9
    # A_O   = row 9  → sheet row 10 → J10
    # E_Al  = row 10 → sheet row 11 → J11
    # A_Al  = row 11 → sheet row 12 → J12
    # E_Fe  = row 12 → sheet row 13 → J13
    # A_Fe  = row 13 → sheet row 14 → J14

    REF_FWHM = "$J$4"
    REF_BG   = "$J$5"
    # (E_ref, A_ref) for each element, 1-based:
    ELEM_REFS = [
        ("$J$7",  "$J$8"),   # C
        ("$J$9",  "$J$10"),  # O
        ("$J$11", "$J$12"),  # Al
        ("$J$13", "$J$14"),  # Fe
    ]

    s.box(3, 8, 13, 9, color=PALETTE["accent"], width=1.2)
    s.note(3, 9,
           "Edit FWHM, background, peak energies or amplitudes — "
           "all table columns and the chart update automatically.",
           kind="note")

    # ── Designate axes ────────────────────────────────────────────
    s.designate(0, "X")   # col A = Energy
    s.designate(5, "Y")   # col F = Total counts

    # ── Data table ────────────────────────────────────────────────
    # Table header at 0-based row 14; first data row at 0-based row 15
    # → sheet row 16.  Energy column is a literal; everything else is a
    # formula referencing the input cells above.
    TABLE_START = 14
    DATA_ROW0   = TABLE_START + 1   # 0-based, first data row

    # Pre-compute numpy arrays for chart render & formula verification.
    fwhm = FWHM_DEFAULT
    peaks_np = [_gaussian(energies, e0, amp, fwhm)
                for (_, e0, amp) in ELEMENTS]
    bg_np    = np.full(N, float(BG_DEFAULT))
    total_np = bg_np + sum(peaks_np)

    # Build the row list for table().
    # Each row: [energy_literal, formula_C, formula_O, formula_Al, formula_Fe,
    #            formula_Total, formula_BG]
    # The data row's sheet row (1-based) = DATA_ROW0 + 1 + i
    # But table() constructs it as start_row + 1 + i (0-based), so
    # sheet row = TABLE_START + 1 + 1 + i = TABLE_START + 2 + i.
    # With TABLE_START=14 → sheet row 16 for i=0, matching A16 for col 0.

    rows = []
    for i, E in enumerate(energies):
        sr = TABLE_START + 2 + i   # 1-based sheet row of this data row
        AE = f"A{sr}"              # the energy cell reference
        # Gaussian for each element:
        peak_formulas = []
        for (eref, aref) in ELEM_REFS:
            # A_i * EXP(-4*LN(2)*((E - E_i)/FWHM)^2)
            f = (f"={aref}*EXP(-4*LN(2)*"
                 f"(({AE}-{eref})/{REF_FWHM})^2)")
            peak_formulas.append(f)
        # Total = BG + sum of peaks (each already a formula; here we sum cells)
        # Columns B..E hold peaks, so col letters: B=1, C=2, D=3, E=4
        # Use individual cell refs B{sr}+C{sr}+D{sr}+E{sr} for clarity.
        f_total = (f"={REF_BG}+B{sr}+C{sr}+D{sr}+E{sr}")
        f_bg    = f"={REF_BG}"
        rows.append([
            round(float(E), 2),   # literal energy
            peak_formulas[0],     # =formula for C
            peak_formulas[1],     # =formula for O
            peak_formulas[2],     # =formula for Al
            peak_formulas[3],     # =formula for Fe
            f_total,              # =formula for Total
            f_bg,                 # =formula for BG
        ])

    s.table(
        TABLE_START, 0,
        headers=["E (keV)", "Peak C", "Peak O", "Peak Al", "Peak Fe",
                 "Total", "Background"],
        rows=rows,
        number_format="0.0",
        banded=True,
    )
    # Override first column (Energy) to show 3 decimal places.
    for i in range(N):
        s.fmt(DATA_ROW0 + i, 0,
              align="right", number_format="0.00")

    s.note(TABLE_START, 0,
           "Energy column is a fixed 0–10 keV grid (0.05 keV step). "
           "Derived columns B–G are live formulas — never literals.",
           kind="note")

    # ── Summary panel (rows 16–24, cols 8–9) ─────────────────────
    # Show the Total counts at each characteristic line energy.
    # Each value is a formula referencing the appropriate data row.
    # Peak energies (keV): C=0.277, O=0.525, Al=1.486, Fe=6.40
    # Nearest grid indices (0.05 step): C→5, O→10, Al→29, Fe→128
    # (index = round(E / 0.05))
    peak_indices = [round(e0 / E_STEP) for (_, e0, _) in ELEMENTS]
    # The sheet row for data index i is TABLE_START + 2 + i (1-based).
    peak_sheet_rows = [TABLE_START + 2 + idx for idx in peak_indices]

    SUMM_START = 16
    s.set(SUMM_START, 8, "Peak Summary")
    s.fmt(SUMM_START, 8, bold=True, font_size=12,
          font_color=PALETTE["header"])

    elem_colors = {
        "C":  PALETTE["good"],
        "O":  PALETTE["band"],
        "Al": PALETTE["warn"],
        "Fe": PALETTE["bad"],
    }
    for k, (el, e0, _) in enumerate(ELEMENTS):
        r = SUMM_START + 1 + k
        psr = peak_sheet_rows[k]
        s.set(r, 8, f"{el} Kα at {e0:.3f} keV (counts)")
        # Total counts in col F (index 5) at the peak row:
        s.formula(r, 9, f"=F{psr}")
        s.fmt(r, 8, align="left")
        s.fmt(r, 9, bg=elem_colors[el], align="center",
              number_format="0", bold=True)

    # Max total counts (formula):
    first_data_sheet = TABLE_START + 2
    last_data_sheet  = TABLE_START + 1 + N
    s.set(SUMM_START + 5, 8, "Max total (counts)")
    s.formula(SUMM_START + 5, 9,
              f"=MAX(F{first_data_sheet}:F{last_data_sheet})")
    s.fmt(SUMM_START + 5, 9,
          bg=PALETTE["header"], font_color="#ffffff",
          align="center", number_format="0", bold=True)

    s.set(SUMM_START + 6, 8, "Background level (counts)")
    s.formula(SUMM_START + 6, 9, f"={REF_BG}")
    s.fmt(SUMM_START + 6, 9,
          bg=PALETTE["band_alt"], align="center",
          number_format="0", bold=True)

    s.box(SUMM_START, 8, SUMM_START + 6, 9,
          color=PALETTE["header"], width=1.2)
    s.note(SUMM_START, 9,
           "Summary recalculates automatically. "
           "Peak heights depend on amplitude, FWHM and background.",
           kind="note")

    # ── Yellow notes ──────────────────────────────────────────────
    s.note(4, 8,
           "Continuum background: in real EDX this is bremsstrahlung "
           "(X-ray braking radiation). Here it is a flat baseline — "
           "characteristic peaks sit on top of it.",
           kind="note")
    s.note(6, 8,
           "Detector resolution (FWHM) controls peak width. "
           "C and O peaks overlap at low energy (try FWHM > 0.2 keV). "
           "Quantification uses peak area (integral), not peak height.",
           kind="note")

    # ── Chart ─────────────────────────────────────────────────────
    # Bound series: x_col=0 (Energy), y_col=5 (Total), y_col=6 (BG).
    # 0-based data rows: DATA_ROW0 .. DATA_ROW0 + N - 1
    r0_chart = DATA_ROW0        # first data row (0-based)
    r1_chart = DATA_ROW0 + N - 1   # last  data row (0-based)

    s.chart(
        [
            Series(
                energies, total_np,
                label="Total counts",
                plot_type="Line",
                color="#4472c4",
                linewidth=1.8,
                x_col=0, y_col=5,
                row_start=r0_chart, row_end=r1_chart,
            ),
            Series(
                energies, bg_np,
                label="Background",
                plot_type="Line",
                color="#a5a5a5",
                linewidth=1.0,
                linestyle="--",
                x_col=0, y_col=6,
                row_start=r0_chart, row_end=r1_chart,
            ),
        ],
        at=(560, 30),
        size=(460, 310),
        title="EDX Spectrum — Counts vs Energy",
        xlabel="Energy (keV)",
        ylabel="Counts",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ────────────────────────────────────────────
    # Gaussian line shape.
    s.equation(
        r"I_i(E)= A_i \exp\!\left(-\frac{4\ln 2\,(E-E_i)^2}{\mathrm{FWHM}^2}\right)",
        at=(560, 360),
        fontsize=17,
        color="#1a1a2e",
        bg_color="#f8f8ff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(380, 56),
    )

    # ── Save ──────────────────────────────────────────────────────
    out = os.path.join(_HERE, "EDX Spectrum.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
