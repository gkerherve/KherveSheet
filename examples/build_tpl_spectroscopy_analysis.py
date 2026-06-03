"""Build the "Spectroscopy Analysis" template .ksheet file.

A polished UV-Vis analysis workflow template demonstrating:
  1. Wavelength (nm) and raw Absorbance — example data with two peaks
  2. Transmittance (%T) = 10^(−A) × 100, showing the A ↔ %T relationship
  3. Linear baseline between two user-editable anchor absorbance cells
  4. Baseline-corrected Absorbance = Absorbance − Baseline
  5. Single-Gaussian peak-fit model = Amp · EXP(−(λ−μ)²/(2σ²))
     with editable Amp, μ (centre), σ (width) parameter cells

All processed columns are per-row scalar formulas referencing absolute
input cells ($B$5…$B$11) — editing any parameter instantly recalculates
the full table, the summary panel, and all three chart curves.

Run:  python examples/build_tpl_spectroscopy_analysis.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Realistic UV-Vis spectrum: two overlapping absorption peaks ───────────────
# Wavelength axis: 300 – 700 nm, step 12 nm → 34 points.
LAM = np.arange(300, 708, 12, dtype=float)
N = len(LAM)   # 34


def gaussian(lam, centre, sigma, amp):
    """Gaussian peak in absorbance units."""
    return amp * np.exp(-0.5 * ((lam - centre) / sigma) ** 2)


# Gentle sloping baseline (simulates detector drift / solvent background)
# A_base ~ 0.05 at 300 nm, rising to 0.10 at 700 nm
A_BASE_SLOPE = (0.10 - 0.05) / (700.0 - 300.0)
A_baseline_true = 0.05 + A_BASE_SLOPE * (LAM - 300.0)

# Two absorption peaks:
#   Peak 1: λ=410 nm  σ=25 nm  A=1.2  (strongest)
#   Peak 2: λ=600 nm  σ=30 nm  A=0.65 (secondary)
A_PEAKS = (gaussian(LAM, 410, 25, 1.2) +
           gaussian(LAM, 600, 30, 0.65))

A_raw = np.clip(A_baseline_true + A_PEAKS, 0.001, 3.5)

# Transmittance
T_raw = 100.0 * 10.0 ** (-A_raw)

# Linear baseline between endpoints (row 0 and row N-1)
A_BL1 = float(A_raw[0])   # absorbance at 300 nm
A_BL2 = float(A_raw[-1])  # absorbance at 700 nm
BL_VEC = A_BL1 + (A_BL2 - A_BL1) * (LAM - LAM[0]) / (LAM[-1] - LAM[0])
A_corr = A_raw - BL_VEC

# Initial Gaussian model: fit to the dominant peak 1
GAUSS_AMP   = 1.20   # peak amplitude
GAUSS_MU    = 410.0  # centre (nm)
GAUSS_SIGMA = 25.0   # width (nm)
A_gauss = gaussian(LAM, GAUSS_MU, GAUSS_MU * 0 + GAUSS_MU,
                   GAUSS_AMP)
# Recompute properly
A_gauss = GAUSS_AMP * np.exp(
    -0.5 * ((LAM - GAUSS_MU) / GAUSS_SIGMA) ** 2
)

# ── Sheet layout constants ────────────────────────────────────────────────────
#
#  Row 0  : Title
#  Row 1  : Subtitle
#  Row 3  : "Editable Parameters" label
#  Row 4  : Baseline anchor 1 absorbance   → B5  ($B$5)
#  Row 5  : Baseline anchor 2 absorbance   → B6  ($B$6)
#  Row 6  : Gaussian amplitude Amp         → B7  ($B$7)
#  Row 7  : Gaussian centre μ (nm)         → B8  ($B$8)
#  Row 8  : Gaussian width σ (nm)          → B9  ($B$9)
#  Row 9  : spacer / notes
#  Row 10 : Summary header
#  Row 11 : summary row 1
#  Row 12 : summary row 2
#  Row 13 : summary row 3
#  Row 14 : summary row 4
#  Row 15 : section heading for table
#  Row 16 : table header  (TABLE_START=16)
#  Row 17 : first data row (0-based 17, 1-based = 18)
#  ...
#  Row 50 : last data row (0-based 17+33=50, 1-based = 51)

TABLE_START    = 16              # 0-based row of table header
FIRST_DATA_0B  = TABLE_START + 1 # 0-based first data row  = 17
FIRST_DATA_SR  = FIRST_DATA_0B + 1  # 1-based first data row = 18
LAST_DATA_SR   = FIRST_DATA_SR + N - 1  # 1-based last data row  = 51

# Absolute refs for editable inputs (1-based A1 notation):
REF_BL1 = "$B$5"   # baseline anchor absorbance at λ_start
REF_BL2 = "$B$6"   # baseline anchor absorbance at λ_end
REF_AMP = "$B$7"   # Gaussian amplitude
REF_MU  = "$B$8"   # Gaussian centre (nm)
REF_SIG = "$B$9"   # Gaussian sigma  (nm)

# Column assignments (0-based):
COL_LAM   = 0   # A  Wavelength (nm)
COL_ABS   = 1   # B  Absorbance
COL_TRANS = 2   # C  Transmittance (%T)
COL_BL    = 3   # D  Baseline
COL_CORR  = 4   # E  Baseline-corrected
COL_GAUSS = 5   # F  Gaussian model
#              6   G  spacer
COL_LPAR  = 7   # H  parameter label
COL_VPAR  = 8   # I  parameter value / summary

# 1-based column letters:
L_LAM   = "A"
L_ABS   = "B"
L_TRANS = "C"
L_BL    = "D"
L_CORR  = "E"
L_GAUSS = "F"

# Absolute range refs over the full data:
CORR_RANGE = f"$E${FIRST_DATA_SR}:$E${LAST_DATA_SR}"
ABS_RANGE  = f"$B${FIRST_DATA_SR}:$B${LAST_DATA_SR}"
LAM_FIRST  = f"$A${FIRST_DATA_SR}"
LAM_LAST   = f"$A${LAST_DATA_SR}"

LAM_START = float(LAM[0])   # 300.0
LAM_END   = float(LAM[-1])  # 696.0
LAM_SPAN  = LAM_END - LAM_START   # 396.0


def build() -> str:
    wb = Workbook(min_rows=max(N + TABLE_START + 10, 60), min_cols=14)
    s = wb.add_sheet("Spectroscopy Analysis")

    # ── Column widths ─────────────────────────────────────────────────────────
    s.col_width(COL_LAM,   115)  # A  Wavelength
    s.col_width(COL_ABS,   110)  # B  Absorbance
    s.col_width(COL_TRANS, 130)  # C  Transmittance
    s.col_width(COL_BL,    120)  # D  Baseline
    s.col_width(COL_CORR,  140)  # E  Baseline-corrected
    s.col_width(COL_GAUSS, 135)  # F  Gaussian model
    s.col_width(6,          14)  # G  spacer
    s.col_width(COL_LPAR,  195)  # H  label
    s.col_width(COL_VPAR,  120)  # I  value

    # ── Title block ───────────────────────────────────────────────────────────
    s.title_block(
        "Spectroscopy Data Analysis",
        "UV-Vis: A  ↔  %T  ·  linear baseline correction  "
        "·  Gaussian peak-fit model  —  edit parameters to recalculate",
        row=0, col=0, span=8,
    )

    # ── Parameter / input panel (rows 3–8) ───────────────────────────────────
    #
    # Layout:
    #   Row 3: section label
    #   Row 4: Anchor 1 absorbance (at λ_start)   → $B$5
    #   Row 5: Anchor 2 absorbance (at λ_end)     → $B$6
    #   Row 6: Gaussian Amp                        → $B$7
    #   Row 7: Gaussian centre μ (nm)              → $B$8
    #   Row 8: Gaussian width σ (nm)               → $B$9

    s.set(3, 0, "Editable Parameters  (change any value to recalculate all columns and the chart)")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    s.merge(3, 0, 1, 5)

    inputs = [
        ("Baseline anchor 1 — A at λ₁ = 300 nm",
         round(float(A_raw[0]), 4)),          # $B$5  row 4
        ("Baseline anchor 2 — A at λ₂ = 696 nm",
         round(float(A_raw[-1]), 4)),          # $B$6  row 5
        ("Gaussian Amp (peak height, A.U.)",
         float(GAUSS_AMP)),                    # $B$7  row 6
        ("Gaussian μ — peak centre (nm)",
         float(GAUSS_MU)),                     # $B$8  row 7
        ("Gaussian σ — peak width (nm)",
         float(GAUSS_SIGMA)),                  # $B$9  row 8
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.fmt(r, 0, align="left")
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.0000")

    s.box(4, 0, 8, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 275)

    # ── Sticky notes — parameter panel ───────────────────────────────────────
    s.note(
        4, 1,
        "BASELINE ANCHORS\n"
        "The linear baseline is drawn between the absorbance values you set "
        "here for λ₁ = 300 nm (B5) and λ₂ = 696 nm (B6).\n"
        "Change B5 or B6 to tilt the baseline and watch column D, "
        "column E, and the chart update instantly.\n"
        "These default values match the raw data at the spectrum endpoints.",
        kind="note",
    )
    s.note(
        6, 1,
        "GAUSSIAN PEAK-FIT PARAMETERS\n"
        "B7 = Amp  (peak height in absorbance units)\n"
        "B8 = μ  (peak centre in nm)\n"
        "B9 = σ  (Gaussian half-width; FWHM = 2.355 × σ)\n\n"
        "Adjust these to hand-fit the model (column F) to the "
        "baseline-corrected data (column E).\n"
        "For automated fitting, use Tools → Curve Fitting.",
        kind="note",
    )

    # ── Summary panel (rows 10–14, cols H–I) ─────────────────────────────────
    s.set(10, COL_LPAR, "Spectrum Summary")
    s.fmt(10, COL_LPAR, bold=True, font_color=PALETTE["header"], font_size=12)
    s.merge(10, COL_LPAR, 1, 2)

    summary_items = [
        ("Peak absorbance (raw)",
         f"=MAX({ABS_RANGE})",
         PALETTE["good"]),
        ("Min %T (most absorbing)",
         f"=MIN($C${FIRST_DATA_SR}:$C${LAST_DATA_SR})",
         PALETTE["bad"]),
        ("Max baseline-corrected A",
         f"=MAX({CORR_RANGE})",
         PALETTE["good"]),
        ("Gaussian peak predicted A",
         f"={REF_AMP}",
         PALETTE["band"]),
        ("FWHM of Gaussian model (nm)",
         f"=2.355*{REF_SIG}",
         PALETTE["band_alt"]),
    ]
    for i, (lbl, expr, col) in enumerate(summary_items):
        r = 11 + i
        s.set(r, COL_LPAR, lbl)
        s.fmt(r, COL_LPAR, align="left")
        s.formula(r, COL_VPAR, expr)
        s.fmt(r, COL_VPAR, bg=col, align="center",
              number_format="0.0000", bold=True)

    s.box(11, COL_LPAR, 11 + len(summary_items) - 1, COL_VPAR,
          color=PALETTE["header"], width=1.2)

    # ── Section heading ───────────────────────────────────────────────────────
    s.set(TABLE_START - 1, 0,
          "Spectral Data  (300–696 nm, step 12 nm, 34 points  |  "
          "paste your own data in columns A and B, then adjust parameters)")
    s.fmt(TABLE_START - 1, 0, bold=True, font_color=PALETTE["header"])
    s.merge(TABLE_START - 1, 0, 1, 6)

    # ── Data table ────────────────────────────────────────────────────────────
    #
    # Column mapping (0-based → letter):
    #   A (0)  Wavelength (nm)          — literal
    #   B (1)  Absorbance               — literal (raw data)
    #   C (2)  Transmittance (%T)       — formula: =100*POWER(10,-B{sr})
    #   D (3)  Baseline (linear)        — formula: interpol. B5..B6 vs A{sr}
    #   E (4)  Baseline-corrected A     — formula: =B{sr}-D{sr}
    #   F (5)  Gaussian model           — formula: =$B$7*EXP(-0.5*((A{sr}-$B$8)/$B$9)^2)
    #
    # Baseline formula for row rr (1-based):
    #   = $B$5 + ($B$6 - $B$5) * (A{rr} - LAM_FIRST) / (LAM_LAST - LAM_FIRST)
    # (uses the anchor absorbance values from B5/B6 plus the wavelength cells)

    table_rows = []
    for k in range(N):
        rr = FIRST_DATA_SR + k   # 1-based sheet row

        lam_val = float(LAM[k])
        abs_val = round(float(A_raw[k]), 4)

        # Transmittance
        trans_f = f"=100*POWER(10,-{L_ABS}{rr})"

        # Linear baseline between anchor absorbances $B$5 and $B$6,
        # interpolated by the wavelength in this row's A cell.
        # bl = $B$5 + ($B$6 - $B$5) * (A{rr} - LAM_FIRST) / (LAM_LAST - LAM_FIRST)
        bl_f = (
            f"={REF_BL1}+({REF_BL2}-{REF_BL1})"
            f"*({L_LAM}{rr}-{LAM_FIRST})"
            f"/({LAM_LAST}-{LAM_FIRST})"
        )

        # Baseline-corrected absorbance
        corr_f = f"={L_ABS}{rr}-{L_BL}{rr}"

        # Gaussian model = Amp * EXP(-0.5 * ((A{rr} - mu)/sigma)^2)
        # Guard sigma: use MAX($B$9, 1) to avoid /0
        gauss_f = (
            f"={REF_AMP}*EXP(-0.5*"
            f"(({L_LAM}{rr}-{REF_MU})/MAX({REF_SIG},1))^2)"
        )

        table_rows.append([
            lam_val,
            abs_val,
            trans_f,
            bl_f,
            corr_f,
            gauss_f,
        ])

    s.table(
        TABLE_START, 0,
        headers=[
            "Wavelength (nm)",
            "Absorbance (A.U.)",
            "Transmittance (%T)",
            "Baseline",
            "Corrected (A.U.)",
            "Gaussian Model",
        ],
        rows=table_rows,
        banded=True,
    )

    # Apply per-column number formats to data rows
    for k in range(N):
        r0b = FIRST_DATA_0B + k
        s.fmt(r0b, COL_LAM,   number_format="0",      align="right")
        s.fmt(r0b, COL_ABS,   number_format="0.0000",  align="right")
        s.fmt(r0b, COL_TRANS, number_format="0.00",    align="right")
        s.fmt(r0b, COL_BL,    number_format="0.0000",  align="right")
        s.fmt(r0b, COL_CORR,  number_format="0.0000",  align="right")
        s.fmt(r0b, COL_GAUSS, number_format="0.0000",  align="right")

    # ── Column designations ───────────────────────────────────────────────────
    s.designate(COL_LAM,   "X")
    s.designate(COL_ABS,   "Y")
    s.designate(COL_CORR,  "Y")
    s.designate(COL_GAUSS, "Y")

    # ── Sticky notes — processing columns ────────────────────────────────────
    s.note(
        TABLE_START, COL_TRANS,
        "TRANSMITTANCE vs ABSORBANCE\n"
        "%T = 10^(−A) × 100 = 100 / 10^A\n"
        "Equivalently: A = 2 − log₁₀(%T)\n\n"
        "At A = 0.0: %T = 100%  (no absorption)\n"
        "At A = 1.0: %T = 10%\n"
        "At A = 2.0: %T = 1%\n\n"
        "Absorbance is preferred for quantitative work because it is "
        "directly proportional to concentration (Beer–Lambert law: A = ε cl).",
        kind="note",
    )
    s.note(
        TABLE_START, COL_BL,
        "LINEAR BASELINE CORRECTION\n"
        "Column D draws a straight-line background between the absorbance "
        "values B5 (at 300 nm) and B6 (at 696 nm).\n\n"
        "Formula: D(λ) = B5 + (B6 − B5) × (λ − λ₁) / (λ₂ − λ₁)\n\n"
        "This removes slowly-varying background (solvent, scatter, source drift). "
        "Edit B5 or B6 to move the baseline up/down at each end.",
        kind="note",
    )
    s.note(
        TABLE_START, COL_CORR,
        "BASELINE-CORRECTED ABSORBANCE\n"
        "Column E = Column B − Column D.\n"
        "The baseline is subtracted point-by-point so the spectrum "
        "sits on a flat zero baseline.\n\n"
        "After correction, peak areas and heights are quantitative. "
        "Column E feeds into the Gaussian model comparison in column F.",
        kind="note",
    )
    s.note(
        TABLE_START, COL_GAUSS,
        "GAUSSIAN PEAK-FIT MODEL\n"
        "Column F = Amp × exp(−(λ−μ)² / (2σ²))\n\n"
        "Adjust B7 (Amp), B8 (μ), B9 (σ) to fit this curve to "
        "column E by eye.\n\n"
        "KherveSheet also provides:\n"
        "  • Tools → Curve Fitting  for automated lmfit / scipy fitting\n"
        "  • SAVGOL() function (Data Analysis menu) for Savitzky–Golay smoothing\n"
        "  • BASELINE.ALS() for asymmetric least-squares baseline removal",
        kind="note",
    )

    # ── Charts ────────────────────────────────────────────────────────────────
    # Data row bounds (0-based, inclusive)
    r0 = FIRST_DATA_0B
    r1 = FIRST_DATA_0B + N - 1

    # Pre-compute arrays for the initial render — must agree with formulas
    T_render    = 100.0 * 10.0 ** (-A_raw)
    BL_render   = A_raw[0] + (A_raw[-1] - A_raw[0]) * (LAM - LAM[0]) / (LAM[-1] - LAM[0])
    CORR_render = A_raw - BL_render
    GAUSS_render = GAUSS_AMP * np.exp(-0.5 * ((LAM - GAUSS_MU) / GAUSS_SIGMA) ** 2)

    # Chart 1: Raw Absorbance + Baseline + Corrected
    s.chart(
        [
            Series(
                LAM, A_raw,
                label="Absorbance",
                plot_type="Line",
                color="#4472c4",
                linewidth=2.2,
                x_col=COL_LAM, y_col=COL_ABS,
                row_start=r0, row_end=r1,
            ),
            Series(
                LAM, BL_render,
                label="Baseline",
                plot_type="Line",
                color="#ed7d31",
                linewidth=1.5,
                linestyle="--",
                x_col=COL_LAM, y_col=COL_BL,
                row_start=r0, row_end=r1,
            ),
            Series(
                LAM, CORR_render,
                label="Corrected A",
                plot_type="Line",
                color="#70ad47",
                linewidth=2.0,
                x_col=COL_LAM, y_col=COL_CORR,
                row_start=r0, row_end=r1,
            ),
        ],
        at=(830, 20),
        size=(520, 310),
        title="UV-Vis: Absorbance, Baseline & Corrected",
        xlabel="λ (nm)",
        ylabel="Absorbance (A.U.)",
        grid=True,
        legend=True,
    )

    # Chart 2: Corrected data vs Gaussian model
    s.chart(
        [
            Series(
                LAM, CORR_render,
                label="Corrected A",
                plot_type="Line+Symbol",
                color="#4472c4",
                linewidth=1.8,
                marker="o",
                markersize=3.5,
                x_col=COL_LAM, y_col=COL_CORR,
                row_start=r0, row_end=r1,
            ),
            Series(
                LAM, GAUSS_render,
                label="Gaussian model",
                plot_type="Line",
                color="#ff4444",
                linewidth=2.5,
                linestyle="--",
                x_col=COL_LAM, y_col=COL_GAUSS,
                row_start=r0, row_end=r1,
            ),
        ],
        at=(830, 350),
        size=(520, 310),
        title="Corrected Spectrum vs Gaussian Peak-Fit",
        xlabel="λ (nm)",
        ylabel="Absorbance (A.U.)",
        grid=True,
        legend=True,
    )

    # Chart 3: Transmittance spectrum
    s.chart(
        [
            Series(
                LAM, T_render,
                label="%Transmittance",
                plot_type="Line",
                color="#9932cc",
                linewidth=2.2,
                x_col=COL_LAM, y_col=COL_TRANS,
                row_start=r0, row_end=r1,
            ),
        ],
        at=(830, 680),
        size=(520, 280),
        title="Transmittance Spectrum",
        xlabel="λ (nm)",
        ylabel="%T",
        grid=True,
        legend=True,
    )

    # ── LaTeX equations ───────────────────────────────────────────────────────
    # Equation 1: Beer-Lambert & A ↔ %T relationship
    s.equation(
        r"\%T = 100 \times 10^{-A} \quad\Leftrightarrow\quad"
        r" A = 2 - \log_{10}(\%T) = \varepsilon\,c\,l",
        at=(830, 978),
        fontsize=14,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(520, 48),
    )

    # Equation 2: Linear baseline
    s.equation(
        r"D(\lambda) = A_1 + (A_2 - A_1)\,"
        r"\frac{\lambda - \lambda_1}{\lambda_2 - \lambda_1}",
        at=(830, 1040),
        fontsize=14,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.2,
        size=(520, 52),
    )

    # Equation 3: Gaussian model
    s.equation(
        r"G(\lambda) = A_{mp}\,\exp\!\left("
        r"-\frac{(\lambda - \mu)^{2}}{2\sigma^{2}}\right)",
        at=(830, 1106),
        fontsize=14,
        color="#222222",
        bg_color="#ffffff",
        border_color="#ff4444",
        border_width=1.2,
        size=(520, 52),
    )

    # ── Save ──────────────────────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Analysis",
    )
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Spectroscopy Analysis.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
