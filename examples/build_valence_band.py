"""Build the "Valence Band Photoemission" demo .ksheet example.

A surface-science / semiconductor physics example showing how a valence-band
photoemission spectrum is modelled, how the Valence Band Maximum (VBM) is
located by linear extrapolation of the leading edge, and how changing the
input parameters shifts the spectrum in the live, formula-driven table.

Run:  python examples/build_valence_band.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Allow running from any directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Physical / display parameters (match what the formulas evaluate to) ──

VBM      = 2.0    # Valence Band Maximum (eV)  — editable, stored in B5
WIDTH    = 0.30   # edge-broadening width (eV) — editable, stored in B6
AMP      = 1000.0 # peak amplitude (counts)    — editable, stored in B7
BASELINE = 50.0   # background baseline        — editable, stored in B8

# Fixed BE grid: -1 to 8 eV inclusive in 0.1 eV steps = 91 points.
BE_START =  -1.0
BE_STOP  =   8.0
BE_STEP  =   0.1
be = np.round(np.arange(BE_START, BE_STOP + BE_STEP / 2, BE_STEP), 2)
N  = len(be)   # 91 points

# Logistic intensity:  I(BE) = baseline + amp / (1 + exp(-(BE-VBM)/width))
intensity = BASELINE + AMP / (1.0 + np.exp(-(be - VBM) / WIDTH))

# Leading-edge linear fit through the inflection point at BE = VBM:
#   slope = amp / (4 * width)   (derivative of logistic at inflection)
#   offset = baseline + amp/2   (logistic value at VBM)
#   L(BE)  = offset + slope * (BE - VBM)
slope_le  = AMP / (4.0 * WIDTH)
offset_le = BASELINE + AMP / 2.0
lin_edge  = offset_le + slope_le * (be - VBM)

# Clamp to [0, amp + baseline + small] so the line doesn't go huge above
# the spectrum; for chart aesthetics only — the sheet formulas are unclamped.
lin_edge_clamped = np.clip(lin_edge, 0.0, AMP + BASELINE + 50)


def build() -> str:
    wb = Workbook(min_rows=110, min_cols=14)
    s  = wb.add_sheet("Valence Band")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 190)   # label column
    s.col_width(1, 110)   # value column
    s.col_width(2, 60)    # spacer
    s.col_width(3, 130)   # BE (eV)
    s.col_width(4, 130)   # Intensity
    s.col_width(5, 160)   # Leading-edge fit
    s.col_width(6, 90)    # (spare)

    # ── Title block ──────────────────────────────────────────────────
    s.title_block(
        "Valence Band Photoemission",
        "Logistic edge model — locate the VBM by leading-edge extrapolation",
        row=0, col=0, span=8,
    )

    # ── Input panel ──────────────────────────────────────────────────
    # 0-based rows 3-8; literal inputs in column B (col 1) = 1-based B4..B9
    s.set(3, 0, "Editable Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"], font_size=11)

    input_rows = [
        ("VBM — Valence Band Maximum (eV)", VBM),
        ("Edge width  σ  (eV)",         WIDTH),
        ("Amplitude  A  (counts)",           AMP),
        ("Baseline  B₀ (counts)",        BASELINE),
    ]
    for i, (lbl, val) in enumerate(input_rows):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center",
              number_format="0.00")
    s.box(4, 0, 7, 1, color=PALETTE["accent"], width=1.5)

    # Friendly notes for the user.
    # Input cells (1-based): B5=VBM, B6=width, B7=amplitude, B8=baseline
    s.note(4, 1,
           "VBM (eV): the binding energy at the leading-edge midpoint.\n"
           "Change this and the spectrum shifts horizontally.",
           kind="note")
    s.note(5, 1,
           "Edge width σ: broadening from thermal smearing + instrument "
           "resolution. Smaller σ = sharper edge.",
           kind="note")

    # ── Derived summary panel ─────────────────────────────────────────
    # Analytically: extrapolated VBM intercept with zero baseline at
    #   BE_intercept = VBM - 2*width - 4*width*baseline/amplitude
    # (where the leading-edge line L = baseline).
    # All live formulas referencing $B$5..$B$8.
    s.set(3, 3, "Derived Quantities")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"], font_size=11)
    s.merge(3, 3, 1, 2)

    derived = [
        ("Leading-edge slope (counts/eV)", "=$B$7/(4*$B$6)"),
        ("Intensity at VBM (counts)",      "=$B$8+$B$7/2"),
        ("Extrapolated VBM (eV)",
         # x-intercept of L(BE)=baseline: BE = VBM - 2*width - 4*w*B0/A
         "=$B$5-2*$B$6-4*$B$6*$B$8/$B$7"),
        ("Intensity at BE=0 (counts)",
         "=$B$8+$B$7/(1+EXP(-(-$B$5)/$B$6))"),
    ]
    for i, (lbl, fml) in enumerate(derived):
        r = 4 + i
        s.set(r, 3, lbl)
        s.formula(r, 4, fml)
        s.fmt(r, 3, align="left")
        s.fmt(r, 4, bg=PALETTE["band"], align="center",
              number_format="0.000", bold=True)
    s.box(4, 3, 7, 4, color=PALETTE["header"], width=1.0)
    s.col_width(4, 130)

    s.note(6, 4,
           "Extrapolated VBM: the binding energy where the tangent line "
           "through the leading-edge inflection point crosses the baseline. "
           "This is the standard experimental VBM determination method.",
           kind="note")

    # ── Data table ────────────────────────────────────────────────────
    # Layout: header at 0-based row 9 (sheet row 10),
    #         first data row at 0-based row 10 (sheet row 11).
    # Column mapping (0-based):  col 0 = label, col 1 = value, col 2 = spacer
    #   col 3 = BE (eV)       → sheet col D → "X"
    #   col 4 = Intensity     → sheet col E → "Y"
    #   col 5 = Leading edge  → sheet col F → "Y"
    TABLE_START = 9   # 0-based row of header row

    s.set(8, 0, "Photoemission Data Table")
    s.fmt(8, 0, bold=True, font_color=PALETTE["header"], font_size=11)

    rows = []
    for k, be_val in enumerate(be):
        # 1-based sheet row of this data row (header is TABLE_START+1=10,
        # so first data row is TABLE_START+2=11, i.e. sheet row 11+k).
        rr = TABLE_START + 2 + k   # 1-based

        # Intensity logistic: =B8 + B7/(1+EXP(-(D<rr>-$B$5)/$B$6))
        intensity_fml = (
            f"=$B$8+$B$7/(1+EXP(-(D{rr}-$B$5)/$B$6))"
        )
        # Leading-edge tangent: =$B$8+$B$7/2+$B$7/(4*$B$6)*(D<rr>-$B$5)
        edge_fml = (
            f"=$B$8+$B$7/2+$B$7/(4*$B$6)*(D{rr}-$B$5)"
        )
        rows.append([
            round(float(be_val), 2),   # BE literal (fixed grid)
            intensity_fml,
            edge_fml,
        ])

    s.table(
        TABLE_START, 3,
        headers=["BE (eV)", "Intensity (counts)", "Leading-edge fit"],
        rows=rows,
        number_format="0.00",
        banded=True,
    )
    # First column (BE) right-aligned with two decimals.
    for k in range(N):
        r = TABLE_START + 1 + k
        s.fmt(r, 3, align="right", number_format="0.00")

    # Designate axes for the chart engine.
    s.designate(3, "X")
    s.designate(4, "Y")
    s.designate(5, "Y")

    # ── Embedded chart ────────────────────────────────────────────────
    # Bind to the table columns: col 3 (BE), col 4 (Intensity), col 5 (edge).
    # 0-based data rows: TABLE_START+1 .. TABLE_START+N  (10 .. 100)
    r0 = TABLE_START + 1
    r1 = TABLE_START + N    # inclusive

    s.chart(
        [
            Series(
                be, intensity,
                label="Photoemission intensity",
                plot_type="Line",
                color=PALETTE["header"],
                linewidth=2.2,
                x_col=3, y_col=4,
                row_start=r0, row_end=r1,
            ),
            Series(
                be, lin_edge_clamped,
                label="Leading-edge tangent",
                plot_type="Line",
                color=PALETTE["accent"],
                linewidth=1.5,
                linestyle="--",
                x_col=3, y_col=5,
                row_start=r0, row_end=r1,
            ),
        ],
        at=(530, 30),
        size=(460, 330),
        title="Valence Band Photoemission Spectrum",
        xlabel="Binding Energy (eV)",
        ylabel="Intensity (counts)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation (mathtext) ─────────────────────────────────────
    # Logistic edge model.
    s.equation(
        r"I(E) = B_0 + \frac{A}{1 + \exp\left(-\frac{E - E_{VBM}}{\sigma}\right)}",
        at=(530, 380),
        fontsize=17,
        color="#1a1a2e",
        bg_color="#f8f8ff",
        border_color=PALETTE["header"],
        border_width=1.3,
        size=(390, 58),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(_HERE, "Valence Band Photoemission.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    path = build()
    print("Wrote", path)
