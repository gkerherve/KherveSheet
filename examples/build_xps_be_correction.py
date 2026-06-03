"""Build the "XPS Binding Energy Correction" data-processing template.

A step-by-step XPS data-manipulation template demonstrating:
  1. Charge correction of binding energy (C 1s reference method)
  2. Linear background subtraction with user-defined endpoint anchors
  3. Normalisation (0–1 and 0–1000 scales)
  4. Reconstruction: normalised signal + background

All processed columns are live formulas referencing the parameter cells
and independent-variable column, so editing any parameter recalculates
the entire table and chart.

Run:  python examples/build_xps_be_correction.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


def build() -> str:
    # ── Synthetic XPS data: C 1s / C-O region 280–300 eV ──────────────
    # Two peaks on a sloping background — physically plausible Fe 2p-like
    # intensity scale but region is C 1s for easy charge-referencing.
    #
    # True (uncharged) positions:
    #   C 1s hydrocarbon : 284.8 eV
    #   C-O shoulder     : 286.4 eV
    # We simulate a +0.5 eV charge shift so the *measured* positions are
    #   C 1s: 285.3 eV,  C-O: 286.9 eV
    # The template corrects back to the true positions.

    BE_RAW_MIN, BE_RAW_MAX, BE_STEP = 280.0, 300.0, 0.5
    be_raw = np.round(np.arange(BE_RAW_MIN, BE_RAW_MAX + BE_STEP * 0.5, BE_STEP), 1)
    N = len(be_raw)   # 41 rows

    # Parameters
    C1S_REF      = 284.8   # reference C 1s (eV)
    C1S_MEASURED = 285.3   # measured C 1s (with +0.5 eV charge shift)
    SHIFT        = C1S_REF - C1S_MEASURED   # -0.5 eV  (correction to subtract)

    # Linear background (sloping upwards toward low BE for Shirley-like shape)
    BG_SLOPE = -8.0        # counts / eV  (negative: more BG at low BE)
    BG_AT_FIRST = 1200.0   # background at BE = 280.0 eV

    # Gaussian peaks (on measured/raw BE axis)
    def gauss(be, be0, fwhm, amp):
        return amp * np.exp(-4.0 * np.log(2.0) * ((be - be0) / fwhm) ** 2)

    bg      = BG_AT_FIRST + BG_SLOPE * (be_raw - BE_RAW_MIN)
    peak1   = gauss(be_raw, 285.3, 1.4, 8500.0)   # C 1s (shifted)
    peak2   = gauss(be_raw, 286.9, 1.6, 2200.0)   # C-O (shifted)
    raw_int = bg + peak1 + peak2

    # Post-correction (shifted back to true positions)
    be_corr = be_raw + SHIFT
    bg_sub  = raw_int - bg
    bg_sub  = np.maximum(bg_sub, 0.0)
    bg_min  = bg_sub.min()
    bg_max  = bg_sub.max()
    norm01  = (bg_sub - bg_min) / (bg_max - bg_min)
    norm1k  = norm01 * 1000.0
    recon   = norm1k + bg          # normalised + background

    # ── Sheet layout (0-based rows) ──────────────────────────────────────
    #
    # Row 0:  Title
    # Row 1:  Subtitle
    # Row 3:  "Charge Correction Parameters" label
    # Row 4:  C 1s reference BE (eV)   B5 ← $B$5
    # Row 5:  Measured C 1s BE (eV)    B6 ← $B$6
    # Row 6:  Calculated shift (eV)    B7 ← formula =$B$5-$B$6
    # Row 8:  "Background Anchors" label
    # Row 9:  BG intensity @ first pt  B10 ← $B$10
    # Row 10: BG intensity @ last pt   B11 ← $B$11
    # Row 12: Section label
    # Row 13: Table header   (DATA_START = 13)
    # Row 14: First data row (DATA_ROW0 = 14;  1-based = 15)
    # ...
    # Row 14+N-1 = 54: Last data row
    #
    # Columns (0-based → 1-based letter):
    #   0=A Raw BE (eV)          — literal independent variable
    #   1=B Raw Intensity (cts)  — literal (paste your data here)
    #   2=C BE Corrected (eV)    — =A_rr + $B$7
    #   3=D Linear Background    — linear interp between $B$10 and $B$11
    #   4=E BG Subtracted        — =B_rr - D_rr
    #   5=F Norm 0–1             — =(E_rr - MIN(E_first:E_last)) /
    #                               (MAX(E_range) - MIN(E_range))
    #   6=G Norm 0–1000          — =F_rr * 1000
    #   7=H Reconstructed        — =G_rr + D_rr

    DATA_START  = 13
    DATA_ROW0   = DATA_START + 1      # 0-based first data row = 14
    DATA_ROW0_1 = DATA_ROW0 + 1      # 1-based first data row = 15
    DATA_LAST_1 = DATA_ROW0_1 + N - 1  # 1-based last data row = 15+40 = 55

    # E column range for MIN/MAX in normalisation
    E_RANGE = f"E{DATA_ROW0_1}:E{DATA_LAST_1}"

    # ── Workbook ─────────────────────────────────────────────────────────
    wb = Workbook(min_rows=max(DATA_LAST_1 + 5, 60), min_cols=16)
    s = wb.add_sheet("XPS Processing")

    # ── Column widths ─────────────────────────────────────────────────────
    s.col_width(0, 120)   # A: Raw BE
    s.col_width(1, 130)   # B: Raw Intensity
    s.col_width(2, 140)   # C: BE Corrected
    s.col_width(3, 140)   # D: Background
    s.col_width(4, 140)   # E: BG Subtracted
    s.col_width(5, 110)   # F: Norm 0-1
    s.col_width(6, 120)   # G: Norm 0-1000
    s.col_width(7, 140)   # H: Reconstructed
    s.col_width(8, 20)    # spacer
    s.col_width(9, 200)   # summary labels
    s.col_width(10, 110)  # summary values

    # ── Title block ───────────────────────────────────────────────────────
    s.title_block(
        "XPS Binding Energy Correction & Processing",
        "Step-by-step: charge correction → background subtraction → "
        "normalisation → reconstruction",
        span=10,
    )

    # ── Step 1: Charge correction parameters ─────────────────────────────
    # Row 3: section label
    # Row 4: C 1s ref      → 0-based (4,1) → B5  ← $B$5
    # Row 5: measured C 1s → 0-based (5,1) → B6  ← $B$6
    # Row 6: shift formula → 0-based (6,1) → B7  (formula, not input)
    s.set(3, 0, "Step 1 — Charge Correction")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"], font_size=11)
    s.merge(3, 0, 1, 4)

    s.set(4, 0, "C 1s reference BE (eV)")
    s.set(4, 1, C1S_REF)
    s.fmt(4, 0, align="left")
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.0",
          bold=True)

    s.set(5, 0, "Measured C 1s BE (eV)")
    s.set(5, 1, C1S_MEASURED)
    s.fmt(5, 0, align="left")
    s.fmt(5, 1, bg=PALETTE["warn"], align="center", number_format="0.0",
          bold=True)

    s.set(6, 0, "Calculated shift (eV)  [= ref - measured]")
    s.formula(6, 1, "=$B$5-$B$6")
    s.fmt(6, 0, align="left", italic=True)
    s.fmt(6, 1, bg=PALETTE["good"], align="center", number_format="0.00",
          bold=True)

    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.2)

    s.note(4, 1,
           "Edit this cell to the standard C 1s reference BE.\n"
           "The most widely used value is 284.8 eV (hydrocarbon C 1s).\n"
           "Some labs use 285.0 eV — check your instrument's convention.",
           kind="note")
    s.note(5, 1,
           "Enter the MEASURED position of the C 1s peak for your sample.\n"
           "The template automatically computes the electrostatic shift\n"
           "and applies it to every point in the BE Corrected column.",
           kind="note")

    # ── Step 2: Background anchors ────────────────────────────────────────
    # Row 8: section label
    # Row 9:  BG at first point → 0-based (9,1)  → B10 ← $B$10
    # Row 10: BG at last point  → 0-based (10,1) → B11 ← $B$11
    s.set(8, 0, "Step 2 — Linear Background Anchors")
    s.fmt(8, 0, bold=True, font_color=PALETTE["accent"], font_size=11)
    s.merge(8, 0, 1, 4)

    s.set(9, 0, "Background at first BE point (counts)")
    s.set(9, 1, round(float(bg[0]), 0))
    s.fmt(9, 0, align="left")
    s.fmt(9, 1, bg=PALETTE["warn"], align="center", number_format="0",
          bold=True)

    s.set(10, 0, "Background at last BE point (counts)")
    s.set(10, 1, round(float(bg[-1]), 0))
    s.fmt(10, 0, align="left")
    s.fmt(10, 1, bg=PALETTE["warn"], align="center", number_format="0",
          bold=True)

    s.box(9, 0, 10, 1, color=PALETTE["accent"], width=1.2)

    s.note(9, 1,
           "Set this to the raw intensity at the LOW-BE end of your spectrum\n"
           "(away from any peaks). Together with the last-point intensity,\n"
           "this defines the two-point linear baseline.",
           kind="note")
    s.note(10, 1,
           "Set this to the raw intensity at the HIGH-BE end of the spectrum\n"
           "(the other baseline anchor). A sloping baseline is common in XPS\n"
           "due to inelastic scattering adding a step-like background.",
           kind="note")

    # ── Section divider ────────────────────────────────────────────────────
    s.set(12, 0,
          "Spectrum data  (paste your Raw BE / Raw Intensity here — "
          "all processed columns update automatically)")
    s.fmt(12, 0, bold=True, font_color=PALETTE["header"])
    s.merge(12, 0, 1, 8)

    # ── Data table ─────────────────────────────────────────────────────────
    # Columns:
    #   A = Raw BE (eV)        — literal
    #   B = Raw Intensity      — literal
    #   C = BE Corrected       — =A_rr + $B$7
    #   D = Background (lin.)  — linear interp: $B$10 + ($B$11-$B$10)*(A_rr-$A$first)
    #                                             / ($A$last - $A$first)
    #   E = BG Subtracted      — =MAX(B_rr - D_rr, 0)  (clamp to 0)
    #   F = Norm 0–1           — =(E_rr - MIN(E_range)) / (MAX(E_range) - MIN(E_range))
    #   G = Norm 0–1000        — =F_rr * 1000
    #   H = Reconstructed      — =G_rr + D_rr

    # Absolute refs for fixed row anchors
    A_FIRST_1 = f"$A${DATA_ROW0_1}"    # BE at first data row (1-based)
    A_LAST_1  = f"$A${DATA_LAST_1}"    # BE at last data row (1-based)

    table_rows = []
    for k in range(N):
        rr = DATA_ROW0_1 + k     # 1-based sheet row
        Acell = f"A{rr}"
        Bcell = f"B{rr}"
        Dcell = f"D{rr}"
        Ecell = f"E{rr}"
        Fcell = f"F{rr}"

        # Column C: charge-corrected BE
        c_form = f"={Acell}+$B$7"

        # Column D: linear background interpolated between the two anchors
        # bg(A) = $B$10 + ($B$11 - $B$10) * (A - A_first) / (A_last - A_first)
        d_form = (
            f"=$B$10+($B$11-$B$10)*({Acell}-{A_FIRST_1})"
            f"/({A_LAST_1}-{A_FIRST_1})"
        )

        # Column E: background-subtracted, clamped to 0
        e_form = f"=MAX({Bcell}-{Dcell},0)"

        # Column F: normalised 0-1
        # =(E - MIN(range)) / (MAX(range) - MIN(range))
        f_form = (
            f"=({Ecell}-MIN({E_RANGE}))"
            f"/(MAX({E_RANGE})-MIN({E_RANGE}))"
        )

        # Column G: normalised 0-1000
        g_form = f"={Fcell}*1000"

        # Column H: reconstructed = normalised + background
        h_form = f"=F{rr}*1000+{Dcell}"

        table_rows.append([
            round(float(be_raw[k]), 1),        # A: raw BE literal
            round(float(raw_int[k]), 0),       # B: raw intensity literal
            c_form,
            d_form,
            e_form,
            f_form,
            g_form,
            h_form,
        ])

    s.table(
        DATA_START, 0,
        headers=[
            "Raw BE (eV)",
            "Raw Intensity (counts)",
            "BE Corrected (eV)",
            "Background (counts)",
            "BG Subtracted (counts)",
            "Norm 0-1",
            "Norm 0-1000",
            "Reconstructed (counts)",
        ],
        rows=table_rows,
        number_format="0.0",
        banded=True,
    )

    # Override number format for Norm 0-1 column (needs more decimals)
    for k in range(N):
        r = DATA_ROW0 + k
        s.fmt(r, 5, number_format="0.000", align="right")

    # Designate X/Y for chart axis hints
    s.designate(2, "X")   # BE corrected = X axis
    s.designate(1, "Y")   # Raw intensity = Y
    s.designate(4, "Y")   # BG subtracted = Y

    # ── Summary panel (right of parameters, cols 9-10) ─────────────────
    s.set(3, 9, "Summary")
    s.fmt(3, 9, bold=True, font_color=PALETTE["header"], font_size=12)
    s.merge(3, 9, 1, 2)

    summ = [
        ("Charge shift (eV)",
         "=$B$5-$B$6",
         PALETTE["good"]),
        ("BE range corrected: min (eV)",
         f"=MIN(C{DATA_ROW0_1}:C{DATA_LAST_1})",
         PALETTE["band"]),
        ("BE range corrected: max (eV)",
         f"=MAX(C{DATA_ROW0_1}:C{DATA_LAST_1})",
         PALETTE["band"]),
        ("Background span (counts)",
         "=$B$11-$B$10",
         PALETTE["band"]),
        ("Peak max BG-subtracted (counts)",
         f"=MAX(E{DATA_ROW0_1}:E{DATA_LAST_1})",
         PALETTE["good"]),
        ("Peak max normalised (0-1000)",
         f"=MAX(G{DATA_ROW0_1}:G{DATA_LAST_1})",
         PALETTE["good"]),
    ]
    for i, (lbl, expr, col) in enumerate(summ):
        r = 4 + i
        s.set(r, 9, lbl)
        s.formula(r, 10, expr)
        s.fmt(r, 9, align="left")
        s.fmt(r, 10, bg=col, align="center", number_format="0.00", bold=True)
    s.box(4, 9, 4 + len(summ) - 1, 10,
          color=PALETTE["header"], width=1.2)

    s.note(6, 9,
           "The corrected BE range shifts rigidly with the charge correction.\n"
           "Verify the C 1s peak in column C is centred near 284.8 eV\n"
           "after applying the shift.",
           kind="note")

    # ── Chart: raw intensity and BG-subtracted vs corrected BE ─────────
    # Data rows: 0-based DATA_ROW0 (14) .. DATA_ROW0+N-1 (54)
    r0 = DATA_ROW0
    r1 = DATA_ROW0 + N - 1

    s.chart(
        [
            Series(
                be_corr, raw_int,
                "Raw Intensity", "Line",
                color="#4472c4", linewidth=1.8,
                x_col=2, y_col=1, row_start=r0, row_end=r1,
            ),
            Series(
                be_corr, bg_sub,
                "BG Subtracted", "Line",
                color="#ed7d31", linewidth=2.0,
                x_col=2, y_col=4, row_start=r0, row_end=r1,
            ),
        ],
        at=(0, 370), size=(560, 330),
        title="XPS — Charge-Corrected Spectrum",
        xlabel="Binding Energy (eV, corrected)",
        ylabel="Intensity (counts)",
        grid=True, legend=True,
    )

    # Second chart: normalised signal
    s.chart(
        [
            Series(
                be_corr, norm1k,
                "Norm 0–1000", "Line",
                color="#70ad47", linewidth=2.0,
                x_col=2, y_col=6, row_start=r0, row_end=r1,
            ),
        ],
        at=(580, 370), size=(480, 330),
        title="XPS — Normalised Spectrum (0–1000)",
        xlabel="Binding Energy (eV, corrected)",
        ylabel="Normalised Intensity",
        grid=True, legend=True,
    )

    # ── LaTeX equations ────────────────────────────────────────────────
    # Charge correction
    s.equation(
        r"BE_{corr} = BE_{raw} + (BE_{ref} - BE_{meas})",
        at=(0, 720), fontsize=17,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(440, 52),
    )

    # Linear background
    s.equation(
        r"BG(BE) = I_{1} + \frac{(I_{N}-I_{1})(BE-BE_{1})}{BE_{N}-BE_{1}}",
        at=(460, 720), fontsize=17,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.5,
        size=(450, 60),
    )

    # Normalisation
    s.equation(
        r"I_{norm} = \frac{I - I_{min}}{I_{max} - I_{min}}",
        at=(930, 720), fontsize=17,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["good"],
        border_width=1.5,
        size=(290, 60),
    )

    # ── Save ──────────────────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Data Processing",
    )
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "XPS Binding Energy Correction.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
