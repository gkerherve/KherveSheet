"""Build the "Raman Spectrum Processing" template .ksheet file.

Demonstrates the standard Raman data-reduction workflow step by step,
with all processed columns as live per-row scalar formulas:

  Col A  Raman Shift (cm⁻¹)          — fixed literal grid, 200–1800 cm⁻¹
  Col B  Raw Intensity (counts)       — synthetic data with D/G bands
  Col C  Baseline (linear)            — linear interpolation between anchors
  Col D  Baseline-Corrected           — Raw − Baseline
  Col E  Smoothed (5-pt MA)           — AVERAGE of 5 explicit cell refs
  Col F  Normalised 0–1               — (corr − MIN)/(MAX − MIN)

All formula cells reference editable input cells ($B$5 = anchor start,
$B$6 = anchor end) so changing the anchors immediately re-draws the
baseline, the corrected spectrum, the smoothing, and the normalised
output.

Run:  python examples/build_tpl_raman.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys
import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Synthetic Raman data ──────────────────────────────────────────────────────
# Shift grid: 200 – 1800 cm⁻¹ in 40 cm⁻¹ steps → 41 points.
SHIFT = np.arange(200, 1841, 40, dtype=float)   # 41 rows
N = len(SHIFT)                                    # 41


def lorentz(x, x0, fwhm, amp):
    """Lorentzian peak."""
    gamma = fwhm / 2.0
    return amp * gamma**2 / ((x - x0)**2 + gamma**2)


# Gently sloping fluorescence baseline (counts)
BG_A = 150.0     # intensity at first point (200 cm⁻¹)
BG_B = 420.0     # intensity at last point  (1800 cm⁻¹)
bg_slope = (BG_B - BG_A) / (SHIFT[-1] - SHIFT[0])

bg_true = BG_A + bg_slope * (SHIFT - SHIFT[0])

# Three peaks: Si (~520), D band (~1350), G band (~1580)
peaks = lorentz(SHIFT, 520, 30, 2800) + \
        lorentz(SHIFT, 1350, 60, 1800) + \
        lorentz(SHIFT, 1580, 40, 3200)

RAW = np.round(bg_true + peaks).astype(float)

# Anchor values (intensity of the first and last raw data rows)
ANCHOR_START = float(RAW[0])    # ~150 counts at 200 cm⁻¹
ANCHOR_END   = float(RAW[-1])   # ~420 counts at 1800 cm⁻¹

# Pre-compute numpy arrays that MATCH what the formulas will produce.
# These are used for the chart initial render only.
# Linear baseline between first and last row:
baseline = ANCHOR_START + (ANCHOR_END - ANCHOR_START) * (
    (SHIFT - SHIFT[0]) / (SHIFT[-1] - SHIFT[0])
)
corrected = RAW - baseline

# 5-point moving average (edge-clamped to match formula behaviour):
smoothed = np.empty(N)
for k in range(N):
    lo = max(0, k - 2)
    hi = min(N - 1, k + 2)
    smoothed[k] = corrected[lo:hi+1].mean()

corr_min = corrected.min()
corr_max = corrected.max()
normalised = (corrected - corr_min) / (corr_max - corr_min)

# ── Sheet layout constants (0-based rows) ─────────────────────────────────────
#
#  Row 0  : Title
#  Row 1  : Subtitle
#  Row 3  : "Baseline Anchor Points" label
#  Row 4  : "Anchor start intensity (counts)"  | B5 = ANCHOR_START  ← $B$5
#  Row 5  : "Anchor end intensity (counts)"    | B6 = ANCHOR_END    ← $B$6
#  Row 7  : "Processing Parameters" label
#  Row 8  : "First data row (1-based)"         | B9 = literal note
#  Row 9  : "Last data row (1-based)"          | B10= literal note
#  Row 11 : Section heading
#  Row 12 : Table header  (TABLE_START = 12)
#  Row 13 : First data row (TABLE_ROW0 = 13, 1-based = 14)
#  ...
#  Row 53 : Last data row  (TABLE_ROW0 + N - 1 = 53, 1-based = 54)

TABLE_START = 12
TABLE_ROW0  = TABLE_START + 1        # 0-based first data row = 13
TABLE_ROW0_1 = TABLE_ROW0 + 1       # 1-based first data row = 14
TABLE_LAST_1 = TABLE_ROW0_1 + N - 1 # 1-based last  data row = 54

# Column assignments (0-based):
COL_SHIFT  = 0   # A  Raman Shift
COL_RAW    = 1   # B  Raw Intensity
COL_BASE   = 2   # C  Baseline
COL_CORR   = 3   # D  Baseline-Corrected
COL_SMOOTH = 4   # E  Smoothed
COL_NORM   = 5   # F  Normalised

# Column letter names (1-based A1 notation):
L_SHIFT  = "A"
L_RAW    = "B"
L_BASE   = "C"
L_CORR   = "D"
L_SMOOTH = "E"
L_NORM   = "F"

# Absolute refs for anchor inputs:
REF_ANCH_START = "$B$5"   # Anchor start intensity (row 4 col 1 → 1-based B5)
REF_ANCH_END   = "$B$6"   # Anchor end intensity   (row 5 col 1 → 1-based B6)
REF_SHIFT_FIRST = "$A$14" # first shift cell (literal, 1-based row 14)
REF_SHIFT_LAST  = "$A$54" # last  shift cell (literal, 1-based row 54)

# MIN/MAX ranges over the baseline-corrected column D:
CORR_RANGE = f"$D$14:$D$54"


def build() -> str:
    wb = Workbook(min_rows=max(N + TABLE_START + 10, 60), min_cols=14)
    s = wb.add_sheet("Raman Processing")

    # ── Column widths ─────────────────────────────────────────────────────
    s.col_width(COL_SHIFT,  110)  # Raman Shift
    s.col_width(COL_RAW,    100)  # Raw
    s.col_width(COL_BASE,   110)  # Baseline
    s.col_width(COL_CORR,   120)  # Corrected
    s.col_width(COL_SMOOTH, 110)  # Smoothed
    s.col_width(COL_NORM,   110)  # Normalised
    s.col_width(6,           18)  # spacer
    s.col_width(7,          170)  # summary labels
    s.col_width(8,          110)  # summary values

    # ── Title block ───────────────────────────────────────────────────────
    s.title_block(
        "Raman Spectrum Processing",
        "Step-by-step baseline correction, smoothing, and normalisation "
        "— edit anchors in B5:B6 to re-process the full spectrum",
        row=0, col=0, span=8,
    )

    # ── Input panel: baseline anchor points ───────────────────────────────
    # Editable values sit at (row 4, col 1) → B5 and (row 5, col 1) → B6.
    s.set(3, 0, "Baseline Anchor Points  (edit these to move the baseline)")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    s.merge(3, 0, 1, 4)

    anchor_inputs = [
        ("Anchor start — intensity at 200 cm⁻¹ (counts)", ANCHOR_START),  # → $B$5
        ("Anchor end   — intensity at 1800 cm⁻¹ (counts)", ANCHOR_END),   # → $B$6
    ]
    for i, (lbl, val) in enumerate(anchor_inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.fmt(r, 0, align="left")
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0")

    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.5)

    # ── Notes for the input panel ──────────────────────────────────────────
    s.note(
        4, 1,
        "Change either anchor intensity here and ALL columns "
        "(Baseline, Corrected, Smoothed, Normalised) recalculate instantly. "
        "The anchor points are the spectrum intensity at the first and last "
        "Raman shift values (200 and 1800 cm⁻¹).",
        kind="note",
    )
    s.note(
        5, 1,
        "Linear baseline: C_n = AnchorStart + (AnchorEnd − AnchorStart) "
        "× (Shift_n − Shift_first) / (Shift_last − Shift_first).\n"
        "Replacing with a polynomial or spline baseline is the most common "
        "upgrade for real Raman data with strong fluorescence.",
        kind="note",
    )

    # ── Summary panel ─────────────────────────────────────────────────────
    # Placed at cols 7–8 (H-I), rows 3–10.
    s.set(3, 7, "Spectrum Summary")
    s.fmt(3, 7, bold=True, font_color=PALETTE["header"], font_size=12)
    s.merge(3, 7, 1, 2)

    summary_items = [
        ("Peak raw intensity (cts)",
         f"=MAX({L_RAW}${TABLE_ROW0_1}:{L_RAW}${TABLE_LAST_1})",
         PALETTE["good"]),
        ("Peak corrected intensity (cts)",
         f"=MAX({CORR_RANGE})",
         PALETTE["good"]),
        ("D-band peak (corr, cts)",
         # D band is near 1350 cm⁻¹ — find the max in the central section
         # Rows 14..54; D band sits roughly at shift ~1340 cm⁻¹.
         # Use the max over the full corrected column (serves as the highest peak).
         # Actually use a direct formula reference to the peak row (row 37 ≈ 1320 cm⁻¹).
         # shift[k] = 200 + 40*k  → k = (1350-200)/40 = 28.75 → row index 29
         # → sheet row 14 + 29 = 43 (1-based) → D43
         "=$D$43",
         PALETTE["band"]),
        ("G-band peak (corr, cts)",
         # G band near 1580 cm⁻¹ → k = (1580-200)/40 = 34.5 → row 35
         # → sheet row 14 + 35 = 49 → D49 (but 34.5→round → k=35 → row=49)
         # Actually 1580 is between 1560 (k=34) and 1600 (k=35).
         # k=34 → shift 200+40*34=1560, k=35 → 1600.
         # G band peak amplitude is at k=34 (1560 cm⁻¹): sheet row 14+34=48.
         # Let's use AVERAGE of neighbours for robustness: D48+D49 max
         "=MAX($D$48,$D$49)",
         PALETTE["band"]),
        ("I(D)/I(G) ratio",
         "=IFERROR($D$43/MAX($D$48,$D$49),0)",
         PALETTE["warn"]),
        ("Min corrected (cts)",
         f"=MIN({CORR_RANGE})",
         PALETTE["band_alt"]),
        ("Baseline slope (cts/cm⁻¹)",
         f"=({REF_ANCH_END}-{REF_ANCH_START})/({REF_SHIFT_LAST}-{REF_SHIFT_FIRST})",
         PALETTE["band_alt"]),
    ]

    for i, (lbl, expr, col) in enumerate(summary_items):
        r = 4 + i
        s.set(r, 7, lbl)
        s.fmt(r, 7, align="left")
        s.formula(r, 8, expr)
        s.fmt(r, 8, bg=col, align="center", number_format="0.00", bold=True)

    s.box(4, 7, 4 + len(summary_items) - 1, 8,
          color=PALETTE["header"], width=1.2)

    # ── Section heading ───────────────────────────────────────────────────
    s.set(11, 0,
          "Raman Spectrum Data  "
          "(200–1800 cm⁻¹, 40 cm⁻¹ step — edit anchors in B5:B6)")
    s.fmt(11, 0, bold=True, font_color=PALETTE["header"])
    s.merge(11, 0, 1, 6)

    # ── Data table ────────────────────────────────────────────────────────
    # Header at TABLE_START=12 (0-based) → sheet row 13.
    # First data row: TABLE_ROW0=13 (0-based) → sheet row 14 = TABLE_ROW0_1=14.
    # Last  data row: TABLE_ROW0_1+N-1 = 14+40 = 54 = TABLE_LAST_1.
    #
    # Column mapping (0-based → 1-based letter):
    #   0=A Raman Shift  (literal)
    #   1=B Raw          (literal)
    #   2=C Baseline     (formula)
    #   3=D Corrected    (formula)
    #   4=E Smoothed     (formula)
    #   5=F Normalised   (formula)
    #
    # Baseline formula for row rr (1-based):
    #   = $B$5 + ($B$6 - $B$5) * (A{rr} - $A$14) / ($A$54 - $A$14)
    #
    # Corrected:
    #   = B{rr} - C{rr}
    #
    # Smoothed (5-pt moving average, edge-clamped explicit refs):
    #   General: AVERAGE(D{rr-2}, D{rr-1}, D{rr}, D{rr+1}, D{rr+2})
    #   Top edge (rr==14):       AVERAGE(D14, D15, D16)   (3-pt)
    #   Second row (rr==15):     AVERAGE(D14, D15, D16, D17)  (4-pt)
    #   Second-to-last (rr==53): AVERAGE(D51, D52, D53, D54)  (4-pt)
    #   Bottom edge (rr==54):    AVERAGE(D52, D53, D54)   (3-pt)
    #
    # Normalised:
    #   = (D{rr} - MIN($D$14:$D$54)) / (MAX($D$14:$D$54) - MIN($D$14:$D$54))

    table_rows = []
    for k in range(N):
        rr = TABLE_ROW0_1 + k    # 1-based sheet row of this data row

        # Literal columns
        shift_val = float(SHIFT[k])
        raw_val   = float(RAW[k])

        # Baseline formula (linear interpolation between anchors)
        base_f = (
            f"={REF_ANCH_START}"
            f"+({REF_ANCH_END}-{REF_ANCH_START})"
            f"*(A{rr}-{REF_SHIFT_FIRST})"
            f"/({REF_SHIFT_LAST}-{REF_SHIFT_FIRST})"
        )

        # Corrected = Raw - Baseline
        corr_f = f"={L_RAW}{rr}-{L_BASE}{rr}"

        # Smoothed — 5-point MA with explicit edge-clamped cell refs
        # Determine available neighbour rows
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
        refs = ",".join(f"{L_CORR}{rv}" for rv in seen)
        smooth_f = f"=AVERAGE({refs})"

        # Normalised
        norm_f = (
            f"=({L_CORR}{rr}-MIN({CORR_RANGE}))"
            f"/(MAX({CORR_RANGE})-MIN({CORR_RANGE}))"
        )

        table_rows.append([
            shift_val,
            raw_val,
            base_f,
            corr_f,
            smooth_f,
            norm_f,
        ])

    s.table(
        TABLE_START, 0,
        headers=[
            "Raman Shift (cm⁻¹)",
            "Raw Intensity (counts)",
            "Baseline (linear)",
            "Corrected (counts)",
            "Smoothed 5-pt (counts)",
            "Normalised (0–1)",
        ],
        rows=table_rows,
        number_format="0.00",
        banded=True,
    )

    # Left-align the shift column (it's a label-like number)
    for i in range(N):
        s.fmt(TABLE_ROW0 + i, COL_SHIFT, align="right",
              number_format="0")

    # The Raw column is also integer-like
    for i in range(N):
        s.fmt(TABLE_ROW0 + i, COL_RAW, align="right",
              number_format="0")

    # Designate axes for chart hints
    s.designate(COL_SHIFT,  "X")
    s.designate(COL_RAW,    "Y")
    s.designate(COL_CORR,   "Y")
    s.designate(COL_SMOOTH, "Y")
    s.designate(COL_NORM,   "Y")

    # ── Sticky notes explaining each processing step ───────────────────────
    # Note at the Baseline column header
    s.note(
        TABLE_START, COL_BASE,
        "BASELINE SUBTRACTION\n"
        "A straight-line background is drawn between the anchor intensities "
        "at 200 cm⁻¹ (B5) and 1800 cm⁻¹ (B6). This removes slowly-varying "
        "fluorescence. Edit B5 or B6 to drag the baseline up or down.",
        kind="note",
    )
    # Note at the Smoothed column header
    s.note(
        TABLE_START, COL_SMOOTH,
        "5-POINT MOVING AVERAGE\n"
        "Each cell averages the corrected intensity of the two rows above, "
        "the current row, and the two rows below (3 pts at the edges). "
        "This suppresses shot-noise without shifting peak positions. "
        "A Savitzky-Golay filter gives better peak preservation for real data.",
        kind="note",
    )
    # Note at the Normalised column header
    s.note(
        TABLE_START, COL_NORM,
        "MIN-MAX NORMALISATION\n"
        "Each cell = (D_row − MIN(D)) / (MAX(D) − MIN(D)).\n"
        "The result spans exactly 0 to 1. Useful for comparing spectra "
        "measured with different acquisition times or laser powers.\n"
        "The D and G band peaks (~1350 and ~1580 cm⁻¹) are the "
        "characteristic fingerprints of carbon materials. "
        "The I(D)/I(G) ratio in the summary panel reports the disorder level.",
        kind="note",
    )
    # Note at the D-band row
    # k for ~1340 cm⁻¹: (1340-200)/40 = 28.5 → k=29 → 0-based row TABLE_ROW0+29
    k_d = 29
    s.note(
        TABLE_ROW0 + k_d, COL_SHIFT,
        "D BAND (~1350 cm⁻¹)\n"
        "Activated by defects and disorder in graphitic carbon. "
        "A breathing mode of six-membered rings, forbidden in perfect graphene. "
        "I(D)/I(G) is widely used to quantify sp³ / defect density.",
        kind="note",
    )
    # Note at the G-band row
    k_g = 34
    s.note(
        TABLE_ROW0 + k_g, COL_SHIFT,
        "G BAND (~1580 cm⁻¹)\n"
        "The primary first-order Raman peak of all sp² carbon — "
        "E₂g in-plane C–C stretching. Present in graphene, graphite, "
        "diamond-like carbon, and carbon nanotubes. "
        "Its width (FWHM) reports the degree of graphitisation.",
        kind="note",
    )

    # ── Charts ────────────────────────────────────────────────────────────
    # Chart 1: Raw vs Corrected Intensity (overlay on one plot)
    # Data rows: 0-based TABLE_ROW0 (13) .. TABLE_ROW0+N-1 (53)
    r0 = TABLE_ROW0
    r1 = TABLE_ROW0 + N - 1

    s.chart(
        [
            Series(
                SHIFT, RAW,
                label="Raw Intensity",
                plot_type="Line",
                color="#4472c4",
                linewidth=1.8,
                x_col=COL_SHIFT, y_col=COL_RAW,
                row_start=r0, row_end=r1,
            ),
            Series(
                SHIFT, corrected,
                label="Baseline-Corrected",
                plot_type="Line",
                color="#ed7d31",
                linewidth=2.2,
                x_col=COL_SHIFT, y_col=COL_CORR,
                row_start=r0, row_end=r1,
            ),
        ],
        at=(730, 20),
        size=(480, 300),
        title="Raman Spectrum — Raw vs Corrected",
        xlabel="Raman Shift (cm⁻¹)",
        ylabel="Intensity (counts)",
        grid=True, legend=True,
    )

    # Chart 2: Smoothed and Normalised
    s.chart(
        [
            Series(
                SHIFT, smoothed,
                label="Smoothed (5-pt MA)",
                plot_type="Line+Symbol",
                color="#70ad47",
                linewidth=2.0,
                marker="o",
                markersize=3.5,
                x_col=COL_SHIFT, y_col=COL_SMOOTH,
                row_start=r0, row_end=r1,
            ),
            Series(
                SHIFT, normalised,
                label="Normalised (0–1)",
                plot_type="Line",
                color="#a040a0",
                linewidth=1.6,
                linestyle="--",
                x_col=COL_SHIFT, y_col=COL_NORM,
                row_start=r0, row_end=r1,
            ),
        ],
        at=(730, 340),
        size=(480, 300),
        title="Raman — Smoothed & Normalised",
        xlabel="Raman Shift (cm⁻¹)",
        ylabel="Intensity (a.u.)",
        grid=True, legend=True,
    )

    # ── LaTeX equation — linear baseline ─────────────────────────────────
    s.equation(
        r"B_n = I_{start} + (I_{end}-I_{start})\,"
        r"\frac{\nu_n - \nu_{first}}{\nu_{last}-\nu_{first}}",
        at=(730, 658),
        fontsize=15,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.5,
        size=(480, 60),
    )

    # ── LaTeX equation — normalisation ───────────────────────────────────
    s.equation(
        r"I_{norm} = \frac{I_{corr} - \min(I_{corr})}{\max(I_{corr}) - \min(I_{corr})}",
        at=(730, 734),
        fontsize=15,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(480, 60),
    )

    # ── Save ──────────────────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates",
        "Data Processing",
    )
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Raman Spectrum Processing.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
