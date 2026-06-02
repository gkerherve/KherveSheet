"""Build the "Peak Shapes" demo .ksheet example.

Spectroscopy comparison of Gaussian, Lorentzian and Pseudo-Voigt line
shapes.  Shared editable inputs (amplitude A, centre x0, FWHM, and the
Pseudo-Voigt mixing fraction eta) drive a computed x-grid table and a
live-bound chart with three distinct series.  LaTeX equations, a summary
panel, and instructional yellow notes complete the workbook.

Run:  python examples/build_peak_shapes.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import numpy as np

from ksheet_author import Workbook, Series, PALETTE

# ── Physical / aesthetic constants ──────────────────────────────────────
A        = 1.0          # peak amplitude (a.u.)
X0       = 0.0          # peak centre (eV)
FWHM     = 1.0          # full-width at half-maximum (eV)
ETA      = 0.5          # Pseudo-Voigt mixing fraction  (0 = Gauss, 1 = Lor)
X_MIN    = -4.0
X_MAX    =  4.0
N_POINTS = 81           # odd so x=0 is exactly included

GAUSS_COLOR  = "#4472c4"   # blue
LOR_COLOR    = "#ed7d31"   # orange
PV_COLOR     = "#70ad47"   # green

# ── Row layout constants (0-based) ───────────────────────────────────────
ROW_TITLE        = 0
ROW_SUBTITLE     = 1
ROW_INPUT_LABEL  = 3
ROW_A            = 4   # cell B5  (1-based)
ROW_X0           = 5   # cell B6
ROW_FWHM         = 6   # cell B7
ROW_ETA          = 7   # cell B8
ROW_SECTION_DATA = 9
TABLE_START      = 10  # header row; data starts at TABLE_START+1  (row 12 1-based)

# Column layout
COL_LBL  = 0   # A — label / x-value
COL_VAL  = 1   # B — input values
COL_X    = 0   # A — x column in table
COL_G    = 1   # B — Gaussian
COL_L    = 2   # C — Lorentzian
COL_PV   = 3   # D — Pseudo-Voigt
COL_SUMM = 6   # G — summary labels
COL_SVAL = 7   # H — summary values


def build() -> str:
    wb = Workbook(min_rows=96, min_cols=14)
    s = wb.add_sheet("Peak Shapes")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block("Peak Shapes",
                  "Gaussian, Lorentzian and Pseudo-Voigt line shapes — "
                  "edit the inputs and watch the chart update",
                  span=8)

    # ── Input panel ───────────────────────────────────────────────────
    s.set(ROW_INPUT_LABEL, COL_LBL, "Inputs")
    s.fmt(ROW_INPUT_LABEL, COL_LBL, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Amplitude  A (a.u.)",      A,    "0.000"),
        ("Centre  x₀ (eV)",     X0,   "0.000"),
        ("FWHM (eV)",                FWHM, "0.000"),
        ("Pseudo-Voigt  η",     ETA,  "0.000"),
    ]
    for i, (lbl, val, nf) in enumerate(inputs):
        r = ROW_A + i
        s.set(r, COL_LBL, lbl)
        s.set(r, COL_VAL, val)
        s.fmt(r, COL_VAL, bg=PALETTE["warn"], align="center",
              number_format=nf)

    s.box(ROW_A, COL_LBL, ROW_ETA, COL_VAL,
          color=PALETTE["accent"], width=1.2)
    s.col_width(COL_LBL, 200)
    s.col_width(COL_VAL, 90)

    # Notes on inputs
    s.note(ROW_FWHM, COL_VAL,
           "FWHM = Full Width at Half Maximum. "
           "All three shapes have exactly this width at half the peak height.",
           kind="note")
    s.note(ROW_ETA, COL_VAL,
           "eta = 0  →  pure Gaussian; "
           "eta = 1  →  pure Lorentzian. "
           "Any value in [0, 1] blends the two.",
           kind="note")

    # ── Data table ───────────────────────────────────────────────────
    # Absolute references:
    #   $B$5 = A, $B$6 = x0, $B$7 = FWHM, $B$8 = eta
    # Header at TABLE_START (0-based row 10) → sheet row 11.
    # First data row at TABLE_START+1 (0-based row 11) → sheet row 12.

    xs = np.linspace(X_MIN, X_MAX, N_POINTS)

    def gauss(x):
        return A * np.exp(-4 * np.log(2) * ((x - X0) / FWHM) ** 2)

    def lorentz(x):
        return A / (1.0 + 4.0 * ((x - X0) / FWHM) ** 2)

    def pseudovoigt(x):
        return ETA * lorentz(x) + (1.0 - ETA) * gauss(x)

    g_arr  = gauss(xs)
    l_arr  = lorentz(xs)
    pv_arr = pseudovoigt(xs)

    table_rows = []
    for k, xv in enumerate(xs):
        # Sheet row of this data row (1-based): TABLE_START + 1 (header) + 1 (first data) + k
        rr = TABLE_START + 2 + k   # 1-based
        x_ref  = f"A{rr}"
        # Gaussian: A*EXP(-4*LN(2)*((x-x0)/FWHM)^2)
        g_expr  = (f"=$B$5*EXP(-4*LN(2)*(({x_ref}-$B$6)/$B$7)^2)")
        # Lorentzian: A / (1 + 4*((x-x0)/FWHM)^2)
        l_expr  = (f"=$B$5/(1+4*(({x_ref}-$B$6)/$B$7)^2)")
        # Pseudo-Voigt: eta*L + (1-eta)*G
        pv_expr = (f"=$B$8*C{rr}+(1-$B$8)*B{rr}")
        table_rows.append([round(float(xv), 4), g_expr, l_expr, pv_expr])

    s.set(ROW_SECTION_DATA, COL_LBL, "Computed line shapes")
    s.fmt(ROW_SECTION_DATA, COL_LBL,
          bold=True, font_color=PALETTE["header"])

    s.table(TABLE_START, COL_LBL,
            headers=["x (eV)", "Gaussian", "Lorentzian", "Pseudo-Voigt"],
            rows=table_rows,
            number_format="0.00000",
            banded=True)

    # Column widths for data columns
    s.col_width(COL_X,  80)
    s.col_width(COL_G,  90)
    s.col_width(COL_L,  90)
    s.col_width(COL_PV, 100)

    # Designate axes so the app knows which column is X
    s.designate(COL_X,  "X")
    s.designate(COL_G,  "Y")
    s.designate(COL_L,  "Y")
    s.designate(COL_PV, "Y")

    # ── Summary panel ────────────────────────────────────────────────
    # 0-based first/last data rows of the table for use in formula ranges
    data_row0 = TABLE_START + 1   # 0-based
    data_row1 = TABLE_START + N_POINTS   # 0-based (inclusive)
    # 1-based sheet rows
    first_1 = TABLE_START + 2
    last_1  = TABLE_START + 1 + N_POINTS

    s.set(ROW_INPUT_LABEL, COL_SUMM, "Summary")
    s.fmt(ROW_INPUT_LABEL, COL_SUMM,
          bold=True, font_color=PALETTE["header"])

    # Gaussian area = A * FWHM * sqrt(pi / (4 ln 2))
    # We display as a formula: =$B$5*$B$7*SQRT(PI()/(4*LN(2)))
    summary = [
        ("Peak height (A)",
         "=$B$5",
         PALETTE["good"]),
        ("FWHM (eV)",
         "=$B$7",
         PALETTE["band"]),
        ("Gaussian area (a.u. eV)",
         "=$B$5*$B$7*SQRT(PI/(4*LN(2)))",
         PALETTE["band_alt"]),
        ("Lorentz max col",
         f"=MAX(C{first_1}:C{last_1})",
         PALETTE["band"]),
        ("Pseudo-Voigt max col",
         f"=MAX(D{first_1}:D{last_1})",
         PALETTE["band_alt"]),
    ]
    summ_start = ROW_A
    for i, (lbl, expr, bg) in enumerate(summary):
        r = summ_start + i
        s.set(r, COL_SUMM, lbl)
        s.formula(r, COL_SVAL, expr)
        s.fmt(r, COL_SUMM, align="left")
        s.fmt(r, COL_SVAL, bg=bg, align="center",
              number_format="0.00000", bold=True)

    s.box(summ_start, COL_SUMM, summ_start + len(summary) - 1, COL_SVAL,
          color=PALETTE["header"], width=1.2)
    s.col_width(COL_SUMM, 190)
    s.col_width(COL_SVAL, 110)

    s.note(summ_start + 2, COL_SVAL,
           "Gaussian analytical area = A × FWHM × "
           "√(π / (4 ln 2)) ≈ A × FWHM × 1.0645. "
           "The Lorentzian area diverges (infinite tails).",
           kind="note")

    # ── Chart: three live-bound series ───────────────────────────────
    # 0-based inclusive data rows for binding
    r0 = data_row0
    r1 = data_row1

    series = [
        Series(xs, g_arr,  "Gaussian",     "Line",
               color=GAUSS_COLOR, linewidth=2.0,
               x_col=COL_X, y_col=COL_G, row_start=r0, row_end=r1),
        Series(xs, l_arr,  "Lorentzian",   "Line",
               color=LOR_COLOR,  linewidth=2.0, linestyle="--",
               x_col=COL_X, y_col=COL_L, row_start=r0, row_end=r1),
        Series(xs, pv_arr, "Pseudo-Voigt", "Line",
               color=PV_COLOR,   linewidth=2.0, linestyle="-.",
               x_col=COL_X, y_col=COL_PV, row_start=r0, row_end=r1),
    ]

    s.chart(series,
            at=(480, 30), size=(460, 330),
            title="Line-shape comparison",
            xlabel="x (eV)", ylabel="Intensity (a.u.)",
            grid=True, legend=True)

    # ── LaTeX equations ──────────────────────────────────────────────
    eq_x = 480
    eq_y_start = 375

    # Gaussian
    s.equation(
        r"G(x) = A \exp\!\left(-4\ln 2 \cdot "
        r"\frac{(x - x_0)^2}{\mathrm{FWHM}^2}\right)",
        at=(eq_x, eq_y_start), fontsize=15,
        color="#222222", bg_color="#ffffff",
        border_color=GAUSS_COLOR, border_width=1.5,
        size=(460, 52))

    # Lorentzian
    s.equation(
        r"L(x) = \frac{A}{1 + 4\,(x - x_0)^2 / \mathrm{FWHM}^2}",
        at=(eq_x, eq_y_start + 65), fontsize=15,
        color="#222222", bg_color="#ffffff",
        border_color=LOR_COLOR, border_width=1.5,
        size=(460, 52))

    # Pseudo-Voigt combination
    s.equation(
        r"PV(x) = \eta\,L(x) + (1-\eta)\,G(x),\quad \eta \in [0,\,1]",
        at=(eq_x, eq_y_start + 130), fontsize=15,
        color="#222222", bg_color="#ffffff",
        border_color=PV_COLOR, border_width=1.5,
        size=(460, 52))

    # Note about Lorentzian tails
    s.note(ROW_X0, COL_SUMM,
           "Lorentzian has much heavier tails than Gaussian "
           "(power-law ∼ 1/x² vs. exponential decay). "
           "In spectroscopy this broadening is called natural or "
           "lifetime broadening.",
           kind="note")

    # ── Save ─────────────────────────────────────────────────────────
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Peak Shapes.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
