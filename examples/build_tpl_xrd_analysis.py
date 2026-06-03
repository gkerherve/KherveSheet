"""Build the "XRD Pattern Analysis" template .ksheet file.

A realistic powder-XRD data-reduction worksheet showing:

  Col A  2theta (°)               — fixed literal grid, 20–80.75°, step 1.25°
  Col B  Intensity (a.u.)         — synthetic diffractogram with 4 Bragg peaks
  Col C  Smoothed Intensity       — 5-point moving average (explicit cell refs)

Below the diffractogram table, a small peak table lets the user fill in
the 2theta and FWHM for each peak; d-spacing and Scherrer crystallite size
are computed as live formulas referencing the editable wavelength (B5) and
shape factor (B6) input cells.

Editable inputs (change these; the whole sheet recomputes):
  B5  — X-ray wavelength λ (Å), default Cu Kα = 1.5406
  B6  — Scherrer shape factor K, default 0.9

Run:  python examples/build_tpl_xrd_analysis.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys
import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Synthetic diffractogram ───────────────────────────────────────────────────
# 2theta grid: 20.0 – 80.75° in 1.25° steps → 49 points
TWO_THETA = np.arange(20.0, 81.0, 1.25)   # 49 values
N = len(TWO_THETA)                          # 49


def pseudo_voigt(x, x0, fwhm, amp, eta=0.5):
    """Pseudo-Voigt peak (linear mix of Lorentzian and Gaussian)."""
    sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    gauss = np.exp(-0.5 * ((x - x0) / sigma) ** 2)
    lorentz = (fwhm / 2.0) ** 2 / ((x - x0) ** 2 + (fwhm / 2.0) ** 2)
    return amp * (eta * lorentz + (1.0 - eta) * gauss)


# Four realistic Bragg peaks (2theta positions for a typical oxide/metal)
#   Peak 1: ~28.4° (Si 111-like)   FWHM 0.35°
#   Peak 2: ~38.1° (Au 111-like)   FWHM 0.28°
#   Peak 3: ~47.3° (broad)         FWHM 0.50°
#   Peak 4: ~64.6° (weak)          FWHM 0.32°
PEAKS = [
    {"x0": 28.4,  "fwhm": 0.35, "amp": 3500},
    {"x0": 38.1,  "fwhm": 0.28, "amp": 5200},
    {"x0": 47.3,  "fwhm": 0.50, "amp": 1800},
    {"x0": 64.6,  "fwhm": 0.32, "amp": 2700},
]

# Low sloping background (~100 at start, ~250 at end)
BG = 100.0 + 150.0 * (TWO_THETA - TWO_THETA[0]) / (TWO_THETA[-1] - TWO_THETA[0])

# Build intensity array
raw_intensity = BG.copy()
for p in PEAKS:
    raw_intensity += pseudo_voigt(TWO_THETA, p["x0"], p["fwhm"], p["amp"])

# Round to integers (diffractometers give integer counts)
INTENSITY = np.round(raw_intensity).astype(float)

# 5-point moving average (edge-clamped, must match the formulas we write)
SMOOTHED = np.empty(N)
for k in range(N):
    lo = max(0, k - 2)
    hi = min(N - 1, k + 2)
    SMOOTHED[k] = INTENSITY[lo:hi + 1].mean()

# ── Physical constants ────────────────────────────────────────────────────────
LAMBDA_DEFAULT = 1.5406   # Cu Kα wavelength (Å)
K_DEFAULT      = 0.9      # Scherrer shape factor

# ── Sheet layout (0-based rows) ───────────────────────────────────────────────
#
#  Row  0 : Title
#  Row  1 : Subtitle
#  Row  3 : "Instrument Parameters" section label
#  Row  4 : λ label | B5 = 1.5406     ← $B$5
#  Row  5 : K label | B6 = 0.9        ← $B$6
#  Row  7 : "Diffractogram Data" section heading
#  Row  8 : Table header (TABLE_START = 8)
#  Row  9 : First data row (TABLE_ROW0 = 9, 1-based = 10)
#  Row 57 : Last data row  (TABLE_ROW0 + N - 1 = 57, 1-based = 58)
#
#  PEAK TABLE (after 2 blank rows):
#  Row 60 : "Peak Summary" heading
#  Row 61 : Peak table header  (PEAK_TABLE_START = 61)
#  Row 62 : Peak 1 data row    (1-based = 63)
#  Row 63 : Peak 2 data row    (1-based = 64)
#  Row 64 : Peak 3 data row    (1-based = 65)
#  Row 65 : Peak 4 data row    (1-based = 66)

TABLE_START   = 8
TABLE_ROW0    = TABLE_START + 1          # 0-based first data row = 9
TABLE_ROW0_1  = TABLE_ROW0 + 1          # 1-based first data row = 10
TABLE_LAST_1  = TABLE_ROW0_1 + N - 1    # 1-based last  data row = 58  (10+48)

PEAK_TABLE_START = 61                    # 0-based header row
PEAK_DATA_ROW0   = PEAK_TABLE_START + 1 # 0-based first peak data row = 62
# 1-based first peak data row = 63

# Column assignments (0-based):
COL_2THETA  = 0   # A  2θ (°)
COL_INTEN   = 1   # B  Intensity
COL_SMOOTH  = 2   # C  Smoothed

# Peak table columns (0-based):
COL_PK_NUM   = 0   # A  Peak #
COL_PK_2T    = 1   # B  2θ position (editable)
COL_PK_FWHM  = 2   # C  FWHM (°) (editable)
COL_PK_D     = 3   # D  d-spacing (Å) — formula
COL_PK_SIZE  = 4   # E  Crystallite size D (nm) — formula

# Column letters for formula strings:
L_2THETA = "A"
L_INTEN  = "B"
L_SMOOTH = "C"

L_PK_2T   = "B"
L_PK_FWHM = "C"
L_PK_D    = "D"
L_PK_SIZE = "E"


def build() -> str:
    wb = Workbook(min_rows=max(N + TABLE_START + 20, 70), min_cols=14)
    s = wb.add_sheet("XRD Analysis")

    # ── Column widths ─────────────────────────────────────────────────────────
    s.col_width(COL_2THETA, 100)   # 2θ
    s.col_width(COL_INTEN,  110)   # Intensity
    s.col_width(COL_SMOOTH, 130)   # Smoothed
    s.col_width(3,           18)   # spacer
    s.col_width(4,          160)   # summary labels
    s.col_width(5,          110)   # summary values
    s.col_width(6,           18)   # spacer 2

    # ── Title block ───────────────────────────────────────────────────────────
    s.title_block(
        "XRD Pattern Analysis",
        "Powder diffraction: smoothing, d-spacing (Bragg) and Scherrer "
        "crystallite size — edit λ and K to update all results",
        row=0, col=0, span=6,
    )

    # ── Instrument parameters (editable inputs) ───────────────────────────────
    # Row 3 label, row 4 → $B$5, row 5 → $B$6
    s.set(3, 0, "Instrument Parameters  (edit these cells)")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    s.merge(3, 0, 1, 4)

    param_rows = [
        ("X-ray wavelength  λ (Å)  — Cu Kα default", LAMBDA_DEFAULT),  # → B5
        ("Scherrer shape factor  K (dimensionless)", K_DEFAULT),         # → B6
    ]
    for i, (lbl, val) in enumerate(param_rows):
        r = 4 + i
        s.set(r, 0, lbl)
        s.fmt(r, 0, align="left")
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.0000")

    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.5)

    s.note(
        4, 1,
        "WAVELENGTH INPUT\n"
        "Default Cu Kα = 1.5406 Å. Change to Mo Kα (0.7107 Å), "
        "Co Kα (1.7902 Å), or any monochromatic line. "
        "The d-spacing and crystallite-size columns in the peak "
        "table recalculate immediately.",
        kind="note",
    )
    s.note(
        5, 1,
        "SCHERRER SHAPE FACTOR K\n"
        "K ≈ 0.89–0.94 for spherical crystallites (FWHM definition). "
        "Use K = 0.9 as the default. The exact value depends on "
        "crystallite shape and the peak-width definition (FWHM vs. β).",
        kind="note",
    )

    # ── Summary panel (cols 4–5, rows 3–9) ───────────────────────────────────
    s.set(3, 4, "Pattern Summary")
    s.fmt(3, 4, bold=True, font_color=PALETTE["header"], font_size=12)
    s.merge(3, 4, 1, 2)

    summary_items = [
        ("Peak intensity (a.u.)",
         f"=MAX({L_INTEN}${TABLE_ROW0_1}:{L_INTEN}${TABLE_LAST_1})",
         PALETTE["good"]),
        ("Background (min)",
         f"=MIN({L_INTEN}${TABLE_ROW0_1}:{L_INTEN}${TABLE_LAST_1})",
         PALETTE["band_alt"]),
        ("Peak-to-background",
         f"=MAX({L_INTEN}${TABLE_ROW0_1}:{L_INTEN}${TABLE_LAST_1})"
         f"/MIN({L_INTEN}${TABLE_ROW0_1}:{L_INTEN}${TABLE_LAST_1})",
         PALETTE["warn"]),
        ("Max smoothed (a.u.)",
         f"=MAX({L_SMOOTH}${TABLE_ROW0_1}:{L_SMOOTH}${TABLE_LAST_1})",
         PALETTE["band"]),
        ("2θ range (°)",
         f"=MAX({L_2THETA}${TABLE_ROW0_1}:{L_2THETA}${TABLE_LAST_1})"
         f"-MIN({L_2THETA}${TABLE_ROW0_1}:{L_2THETA}${TABLE_LAST_1})",
         PALETTE["band_alt"]),
    ]
    for i, (lbl, expr, bg) in enumerate(summary_items):
        r = 4 + i
        s.set(r, 4, lbl)
        s.fmt(r, 4, align="left")
        s.formula(r, 5, expr)
        s.fmt(r, 5, bg=bg, align="center", number_format="0.00", bold=True)

    s.box(4, 4, 4 + len(summary_items) - 1, 5,
          color=PALETTE["header"], width=1.2)

    # ── Section heading for diffractogram table ───────────────────────────────
    s.set(7, 0,
          "Diffractogram Data  "
          "(20–80.75°, 1.25° step — edit Intensity column B for your data)")
    s.fmt(7, 0, bold=True, font_color=PALETTE["header"])
    s.merge(7, 0, 1, 4)

    # ── Data table ────────────────────────────────────────────────────────────
    # Header at TABLE_START=8 (0-based) → sheet row 9 (1-based).
    # First data row: TABLE_ROW0=9 (0-based) → sheet row 10 (1-based) = TABLE_ROW0_1.
    # Last  data row: TABLE_LAST_1 = 58 (1-based).
    #
    # Column layout (0-based → 1-based letter):
    #   0=A  2θ literal
    #   1=B  Raw intensity literal (user can overwrite with own data)
    #   2=C  Smoothed 5-pt MA formula
    #
    # Smoothed formula — 5-point moving average with explicit edge-clamped refs:
    #   General row rr:
    #     =AVERAGE(B{rr-2}, B{rr-1}, B{rr}, B{rr+1}, B{rr+2})
    #   Edge rows (TABLE_ROW0_1 = 10, TABLE_LAST_1 = 58):
    #     rr==10:  =AVERAGE(B10, B11, B12)
    #     rr==11:  =AVERAGE(B10, B11, B12, B13)
    #     rr==57:  =AVERAGE(B55, B56, B57, B58)
    #     rr==58:  =AVERAGE(B56, B57, B58)

    table_rows = []
    for k in range(N):
        rr = TABLE_ROW0_1 + k    # 1-based sheet row for this data row

        two_theta_val = float(TWO_THETA[k])
        intensity_val = float(INTENSITY[k])

        # Smoothed — 5-point MA with explicit edge-clamped cell refs
        rows_avail = [
            max(TABLE_ROW0_1, rr - 2),
            max(TABLE_ROW0_1, rr - 1),
            rr,
            min(TABLE_LAST_1, rr + 1),
            min(TABLE_LAST_1, rr + 2),
        ]
        # Deduplicate while preserving order
        seen = []
        for rv in rows_avail:
            if rv not in seen:
                seen.append(rv)
        refs = ",".join(f"{L_INTEN}{rv}" for rv in seen)
        smooth_f = f"=AVERAGE({refs})"

        table_rows.append([
            two_theta_val,
            intensity_val,
            smooth_f,
        ])

    s.table(
        TABLE_START, 0,
        headers=[
            "2θ (°)",
            "Intensity (a.u.)",
            "Smoothed Intensity (5-pt MA)",
        ],
        rows=table_rows,
        number_format="0.00",
        banded=True,
    )

    # Format the 2θ column as 2 decimals
    for i in range(N):
        s.fmt(TABLE_ROW0 + i, COL_2THETA, align="right", number_format="0.00")
        s.fmt(TABLE_ROW0 + i, COL_INTEN,  align="right", number_format="0")

    # Designate axes for chart hints
    s.designate(COL_2THETA, "X")
    s.designate(COL_INTEN,  "Y")
    s.designate(COL_SMOOTH, "Y")

    # ── Note on the Smoothed column header ────────────────────────────────────
    s.note(
        TABLE_START, COL_SMOOTH,
        "5-POINT MOVING AVERAGE SMOOTHING\n"
        "Each cell = AVERAGE of the two rows above, this row, and the "
        "two rows below (3 pts at the edges). This suppresses counting "
        "noise without shifting peak positions.\n"
        "For real data, a Savitzky-Golay filter (KherveSheet: "
        "Data Analysis → SAVGOL) preserves peak shape better.",
        kind="note",
    )

    # ── Peak Summary table ────────────────────────────────────────────────────
    # Rows 60–65 (0-based: 60=heading, 61=header, 62..65=data)
    # Sheet rows (1-based): heading=61, header=62, data=63..66
    #
    # 2θ and FWHM are *editable* — user types them in.
    # d-spacing and crystallite size are live formulas.
    #
    # d = λ / (2 * SIN(RADIANS(2θ/2)))
    #   = $B$5 / (2 * SIN(RADIANS(B{rr}/2)))
    #
    # D_scherrer = K * λ / (FWHM_rad * COS(RADIANS(θ)))
    #            = $B$6 * $B$5 / (RADIANS(C{rr}) * COS(RADIANS(B{rr}/2)))
    #
    # Note: we store D in Angstroms and divide by 10 to display nm.
    # D(Å) = K*λ(Å) / (RADIANS(FWHM°) * COS(RADIANS(θ)))
    # D(nm) = D(Å) / 10

    s.set(60, 0, "Peak Summary Table  "
                 "(enter 2θ and FWHM for your peaks — d and D recalculate)")
    s.fmt(60, 0, bold=True, font_color=PALETTE["header"])
    s.merge(60, 0, 1, 6)

    # Peak table header at row 61 (0-based) → sheet row 62 (1-based)
    peak_headers = [
        "Peak #",
        "2θ (°)",
        "FWHM (°)",
        "d-spacing (Å)",
        "Crystallite size D (nm)",
    ]

    # Default peak data (editable 2θ and FWHM from our synthetic peaks)
    peak_data_defaults = [
        (1, PEAKS[0]["x0"], PEAKS[0]["fwhm"]),
        (2, PEAKS[1]["x0"], PEAKS[1]["fwhm"]),
        (3, PEAKS[2]["x0"], PEAKS[2]["fwhm"]),
        (4, PEAKS[3]["x0"], PEAKS[3]["fwhm"]),
    ]

    peak_rows = []
    for pk_idx, (pk_num, pk_2t, pk_fwhm) in enumerate(peak_data_defaults):
        # 1-based sheet row for this peak row:  header at 62, first data at 63
        rr = PEAK_DATA_ROW0 + 1 + pk_idx  # 1-based: 63, 64, 65, 66

        # d-spacing formula: d = λ / (2 · sin(θ)) where θ = 2θ/2
        # B{rr} = 2θ, so θ = B{rr}/2
        d_formula = (
            f"=$B$5/(2*SIN(RADIANS({L_PK_2T}{rr}/2)))"
        )

        # Scherrer crystallite size (in nm):
        # D(nm) = K * λ(Å) / (RADIANS(FWHM°) * COS(RADIANS(θ))) / 10
        # = $B$6 * $B$5 / (RADIANS(C{rr}) * COS(RADIANS(B{rr}/2))) / 10
        size_formula = (
            f"=$B$6*$B$5/(RADIANS({L_PK_FWHM}{rr})*COS(RADIANS({L_PK_2T}{rr}/2)))/10"
        )

        peak_rows.append([
            pk_num,
            pk_2t,
            pk_fwhm,
            d_formula,
            size_formula,
        ])

    s.table(
        PEAK_TABLE_START, 0,
        headers=peak_headers,
        rows=peak_rows,
        number_format="0.0000",
        banded=True,
    )

    # Format peak # as integer, 2θ and FWHM as 4 decimals, D as 2 decimals
    for pk_idx in range(4):
        r = PEAK_DATA_ROW0 + pk_idx   # 0-based row
        s.fmt(r, COL_PK_NUM,  align="center", number_format="0")
        s.fmt(r, COL_PK_2T,   align="right",  number_format="0.0000")
        s.fmt(r, COL_PK_FWHM, align="right",  number_format="0.0000")
        s.fmt(r, COL_PK_D,    align="right",  number_format="0.0000")
        s.fmt(r, COL_PK_SIZE, align="right",  number_format="0.00")

    # Amber fill on the editable peak columns (2θ and FWHM)
    for pk_idx in range(4):
        r = PEAK_DATA_ROW0 + pk_idx
        s.fmt(r, COL_PK_2T,   bg=PALETTE["warn"])
        s.fmt(r, COL_PK_FWHM, bg=PALETTE["warn"])

    # Wider columns for the peak table
    s.col_width(COL_PK_NUM,  60)
    s.col_width(COL_PK_2T,   100)
    s.col_width(COL_PK_FWHM, 100)
    s.col_width(COL_PK_D,    120)
    s.col_width(COL_PK_SIZE, 175)

    # ── Notes on peak table ───────────────────────────────────────────────────
    s.note(
        PEAK_TABLE_START, COL_PK_2T,
        "EDITABLE PEAK POSITIONS\n"
        "Type the 2θ position (in degrees) for each of your Bragg peaks. "
        "The d-spacing and crystallite size columns update immediately. "
        "Add or overwrite rows for as many peaks as needed.",
        kind="note",
    )
    s.note(
        PEAK_TABLE_START, COL_PK_D,
        "BRAGG'S LAW: d = λ / (2 sin θ)\n"
        "d-spacing (Å) is the interplanar spacing for the reflecting planes. "
        "Combined with Miller indices, it identifies the crystal phase. "
        "Compare with ICDD PDF card values for phase identification.\n"
        "Formula: =$B$5 / (2·SIN(RADIANS(2θ/2)))",
        kind="note",
    )
    s.note(
        PEAK_TABLE_START, COL_PK_SIZE,
        "SCHERRER EQUATION: D = Kλ / (β cos θ)\n"
        "D = crystallite size (nm); K = shape factor (B6); "
        "λ = wavelength (B5); β = FWHM in radians; θ = Bragg angle.\n"
        "Valid when D < ~120 nm; for larger crystallites use Warren-Averbach. "
        "Microstrain broadening is NOT included — use Williamson-Hall if "
        "strain is significant.\n"
        "TIP: Use KherveSheet's Curve Fitting tool (Pseudo-Voigt model) "
        "for accurate FWHM extraction from overlapping peaks.",
        kind="note",
    )

    # ── Chart: Intensity and Smoothed vs 2θ ──────────────────────────────────
    # Data rows: 0-based TABLE_ROW0 (9) .. TABLE_ROW0+N-1 (57)
    r0 = TABLE_ROW0
    r1 = TABLE_ROW0 + N - 1

    s.chart(
        [
            Series(
                TWO_THETA, INTENSITY,
                label="Intensity (raw)",
                plot_type="Line",
                color="#4472c4",
                linewidth=1.5,
                x_col=COL_2THETA, y_col=COL_INTEN,
                row_start=r0, row_end=r1,
            ),
            Series(
                TWO_THETA, SMOOTHED,
                label="Smoothed (5-pt MA)",
                plot_type="Line",
                color="#ed7d31",
                linewidth=2.2,
                x_col=COL_2THETA, y_col=COL_SMOOTH,
                row_start=r0, row_end=r1,
            ),
        ],
        at=(730, 20),
        size=(500, 340),
        title="XRD Pattern — Intensity vs 2θ",
        xlabel="2θ (°)",
        ylabel="Intensity (a.u.)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equations ───────────────────────────────────────────────────────
    # Bragg's law
    s.equation(
        r"n\lambda = 2\,d\sin\theta \quad\Rightarrow\quad "
        r"d = \frac{\lambda}{2\sin\theta}",
        at=(730, 380),
        fontsize=16,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(500, 60),
    )

    # Scherrer equation
    s.equation(
        r"D = \frac{K\,\lambda}{\beta\cos\theta}",
        at=(730, 456),
        fontsize=18,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.5,
        size=(240, 62),
    )

    # ── Save ──────────────────────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates",
        "Analysis",
    )
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "XRD Pattern Analysis.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
