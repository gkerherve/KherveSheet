"""Build the "Statistical Process Control" template .ksheet file.

A Shewhart X-bar control chart workbook demonstrating:
  1. ~28 sample measurements with realistic process variation
  2. Centre Line (CL) = AVERAGE of all measurements — live formula per row
  3. Process Std Dev (sigma) = STDEV of all measurements — live formula
  4. UCL = CL + 3*sigma, LCL = CL - 3*sigma — flat lines across all rows
  5. Out-of-control flag per row: IF(OR(meas > UCL, meas < LCL), "OUT", "OK")
  6. Capability block: editable USL/LSL, then Cp and Cpk formulas
  7. Control chart: Measurement + CL/UCL/LCL overlaid flat lines vs Sample #

All processed columns are per-row scalar formulas referencing absolute
summary cells ($I$10 for CL, $I$11 for sigma, etc.) — editing USL/LSL
instantly recalculates the Cp/Cpk block.

Run:  python examples/build_tpl_spc.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Realistic process data ────────────────────────────────────────────────────
# 28 samples, nominal target 50.0, natural sigma ~1.8.
# Points 8 and 20 (1-indexed) are near the control limits to demonstrate
# how the "OUT" flag lights up.
MEASUREMENTS = [
    50.89, 49.75, 51.17, 52.74, 49.58, 49.58, 52.84, 54.80,
    49.15, 50.98, 49.17, 49.16, 50.44, 46.56, 46.90, 48.99,
    48.18, 50.57, 48.37, 45.10, 52.64, 49.59, 50.12, 47.44,
    49.02, 50.20, 47.93, 50.68,
]
N = len(MEASUREMENTS)   # 28

# Pre-compute for chart initial render — must match what the formulas return.
MEAS = np.array(MEASUREMENTS)
CL_val   = float(np.mean(MEAS))
SIG_val  = float(np.std(MEAS, ddof=1))
UCL_val  = CL_val + 3.0 * SIG_val
LCL_val  = CL_val - 3.0 * SIG_val

# Default specification limits (editable by the user)
USL_default = 57.0
LSL_default = 43.0

# ── Sheet layout constants ────────────────────────────────────────────────────
#
#  Row 0  : Title
#  Row 1  : Subtitle
#  Row 3  : "Specification Limits (editable)" label  — cols H/I
#  Row 4  : USL  → $I$5  (0-based row 4, col 8)
#  Row 5  : LSL  → $I$6
#  Row 7  : "Process Summary" label  — cols H/I
#  Row 8  : separator
#  Row 9  : CL   → $I$10  (0-based row 9, col 8)
#  Row 10 : sigma → $I$11
#  Row 11 : UCL  → $I$12
#  Row 12 : LCL  → $I$13
#  Row 13 : Cp   → $I$14
#  Row 14 : Cpk  → $I$15
#
#  Row 16 : section heading for table
#  Row 17 : table header  (TABLE_START = 17)
#  Row 18 : first data row  (FIRST_DATA_0B = 18;  FIRST_DATA_SR = 19)
#  ...
#  Row 45 : last data row   (LAST_DATA_0B  = 45;  LAST_DATA_SR  = 46)

TABLE_START   = 17              # 0-based row of table header
FIRST_DATA_0B = TABLE_START + 1 # 0-based first data row = 18
FIRST_DATA_SR = FIRST_DATA_0B + 1  # 1-based first data row = 19
LAST_DATA_SR  = FIRST_DATA_SR + N - 1  # 1-based last data row  = 46

# Summary cell absolute refs (1-based A1 notation):
REF_USL = "$I$5"   # User Specification Upper Limit
REF_LSL = "$I$6"   # User Specification Lower Limit
REF_CL  = "$I$10"  # Centre Line = AVERAGE of all measurements
REF_SIG = "$I$11"  # Process std dev = STDEV of all measurements
REF_UCL = "$I$12"  # Upper Control Limit = CL + 3*sigma
REF_LCL = "$I$13"  # Lower Control Limit = CL - 3*sigma
REF_CP  = "$I$14"  # Process capability index Cp
REF_CPK = "$I$15"  # Process capability index Cpk

# Measurement data range (for AVERAGE/STDEV):
MEAS_RANGE = f"$B${FIRST_DATA_SR}:$B${LAST_DATA_SR}"

# Column assignments (0-based):
COL_SAMPLE = 0  # A  Sample #
COL_MEAS   = 1  # B  Measurement
COL_CL     = 2  # C  Centre Line (formula = CL)
COL_UCL    = 3  # D  UCL
COL_LCL    = 4  # E  LCL
COL_FLAG   = 5  # F  Out-of-control flag
#              6  G  spacer
COL_LPAR   = 7  # H  summary label
COL_VPAR   = 8  # I  summary value

# 1-based column letters:
L_MEAS = "B"
L_CL   = "C"
L_UCL  = "D"
L_LCL  = "E"


def build() -> str:
    wb = Workbook(min_rows=max(N + TABLE_START + 12, 55), min_cols=14)
    s = wb.add_sheet("Control Chart")

    # ── Column widths ─────────────────────────────────────────────────────────
    s.col_width(COL_SAMPLE, 90)   # A  Sample #
    s.col_width(COL_MEAS,   110)  # B  Measurement
    s.col_width(COL_CL,     100)  # C  CL
    s.col_width(COL_UCL,    100)  # D  UCL
    s.col_width(COL_LCL,    100)  # E  LCL
    s.col_width(COL_FLAG,    90)  # F  Flag
    s.col_width(6,           14)  # G  spacer
    s.col_width(COL_LPAR,   210)  # H  label
    s.col_width(COL_VPAR,   120)  # I  value

    # ── Title block ───────────────────────────────────────────────────────────
    s.title_block(
        "Statistical Process Control — Shewhart X-bar Chart",
        "Edit USL / LSL spec limits (H–I panel) to update Cp & Cpk  ·  "
        "Replace column B measurements with your own data  ·  "
        "OUT flags, control limits, and the chart recalculate automatically",
        row=0, col=0, span=8,
    )

    # ── Spec limits panel (rows 3-5, cols H-I) ────────────────────────────────
    s.set(3, COL_LPAR, "Specification Limits  (editable)")
    s.fmt(3, COL_LPAR, bold=True, font_color=PALETTE["accent"], font_size=11)
    s.merge(3, COL_LPAR, 1, 2)

    spec_inputs = [
        ("Upper Specification Limit  USL", USL_default),  # row 4 → $I$5
        ("Lower Specification Limit  LSL", LSL_default),  # row 5 → $I$6
    ]
    for i, (lbl, val) in enumerate(spec_inputs):
        r = 4 + i
        s.set(r, COL_LPAR, lbl)
        s.fmt(r, COL_LPAR, align="left")
        s.set(r, COL_VPAR, val)
        s.fmt(r, COL_VPAR, bg=PALETTE["warn"], align="center",
              number_format="0.00", bold=True)

    s.box(4, COL_LPAR, 5, COL_VPAR, color=PALETTE["accent"], width=1.5)

    # ── Process summary panel (rows 9-15, cols H-I) ───────────────────────────
    s.set(7, COL_LPAR, "Process Summary  (live — recalculates with data)")
    s.fmt(7, COL_LPAR, bold=True, font_color=PALETTE["header"], font_size=11)
    s.merge(7, COL_LPAR, 1, 2)

    # Summary row definitions:
    #   (row_0based, label, formula, bg_color, number_format)
    #
    # CL/sigma/UCL/LCL: reference MEAS_RANGE for AVERAGE/STDEV.
    # Cp  = (USL - LSL) / (6 * sigma)  — guard sigma with MAX(...,0.0001) to
    #       avoid /0 if all measurements are identical.
    # Cpk = MIN((USL - CL), (CL - LSL)) / (3 * sigma) — same guard.
    #       MIN with two scalar arguments works correctly in the engine.

    summary_rows = [
        (9,  "Centre Line  CL = AVERAGE(B)",
         f"=AVERAGE({MEAS_RANGE})",
         PALETTE["band"], "0.0000"),
        (10, "Process Std Dev  σ = STDEV(B)",
         f"=STDEV({MEAS_RANGE})",
         PALETTE["band_alt"], "0.0000"),
        (11, "Upper Control Limit  UCL = CL + 3σ",
         f"=AVERAGE({MEAS_RANGE})+3*STDEV({MEAS_RANGE})",
         PALETTE["bad"], "0.0000"),
        (12, "Lower Control Limit  LCL = CL − 3σ",
         f"=AVERAGE({MEAS_RANGE})-3*STDEV({MEAS_RANGE})",
         PALETTE["bad"], "0.0000"),
        (13, "Capability Index  Cp = (USL−LSL)/(6σ)",
         f"=({REF_USL}-{REF_LSL})/(6*MAX(STDEV({MEAS_RANGE}),0.0001))",
         PALETTE["good"], "0.0000"),
        (14, "Capability Index  Cpk = MIN((USL−CL),(CL−LSL))/(3σ)",
         f"=MIN({REF_USL}-AVERAGE({MEAS_RANGE}),AVERAGE({MEAS_RANGE})-{REF_LSL})"
         f"/(3*MAX(STDEV({MEAS_RANGE}),0.0001))",
         PALETTE["good"], "0.0000"),
    ]

    for r0b, lbl, expr, bg, nfmt in summary_rows:
        s.set(r0b, COL_LPAR, lbl)
        s.fmt(r0b, COL_LPAR, align="left")
        s.formula(r0b, COL_VPAR, expr)
        s.fmt(r0b, COL_VPAR, bg=bg, align="center",
              number_format=nfmt, bold=True)

    s.box(9, COL_LPAR, 14, COL_VPAR, color=PALETTE["header"], width=1.2)

    # ── Section heading ───────────────────────────────────────────────────────
    s.set(TABLE_START - 1, 0,
          f"Process Data  ({N} samples  |  replace column B with your measurements)")
    s.fmt(TABLE_START - 1, 0, bold=True, font_color=PALETTE["header"])
    s.merge(TABLE_START - 1, 0, 1, 6)

    # ── Data table ────────────────────────────────────────────────────────────
    #
    # Column formulas (1-based sheet row rr):
    #   A (0) = sample number           — literal integer
    #   B (1) = measurement             — literal (replace with own data)
    #   C (2) = CL per row              — =AVERAGE($B$19:$B$46)   (flat line)
    #   D (3) = UCL per row             — =AVERAGE($B$19:$B$46)+3*STDEV($B$19:$B$46)
    #   E (4) = LCL per row             — =AVERAGE($B$19:$B$46)-3*STDEV($B$19:$B$46)
    #   F (5) = out-of-control flag     — =IF(OR(B{rr}>D{rr},B{rr}<E{rr}),"OUT","OK")
    #
    # NOTE: the CL/UCL/LCL columns use the absolute MEAS_RANGE directly (not
    # the summary cells) so that STDEV/AVERAGE are re-evaluated for every row
    # and the formula chain is transparent.  The summary cells use identical
    # formulas, so all values agree.

    table_rows = []
    cl_arr   = np.full(N, CL_val)
    ucl_arr  = np.full(N, UCL_val)
    lcl_arr  = np.full(N, LCL_val)

    for k in range(N):
        rr = FIRST_DATA_SR + k   # 1-based sheet row

        sample_num = k + 1
        meas_val   = float(MEASUREMENTS[k])

        cl_f  = f"=AVERAGE({MEAS_RANGE})"
        ucl_f = f"=AVERAGE({MEAS_RANGE})+3*STDEV({MEAS_RANGE})"
        lcl_f = f"=AVERAGE({MEAS_RANGE})-3*STDEV({MEAS_RANGE})"

        # Out-of-control flag.
        # IF evaluates both branches, but neither contains a domain error,
        # so this is safe.
        flag_f = (
            f"=IF(OR({L_MEAS}{rr}>{L_UCL}{rr},{L_MEAS}{rr}<{L_LCL}{rr}),"
            f"\"OUT\",\"OK\")"
        )

        table_rows.append([sample_num, meas_val, cl_f, ucl_f, lcl_f, flag_f])

    s.table(
        TABLE_START, 0,
        headers=[
            "Sample #",
            "Measurement",
            "CL",
            "UCL  (+3σ)",
            "LCL  (−3σ)",
            "Status",
        ],
        rows=table_rows,
        banded=True,
        align_data="right",
    )

    # Override: Sample # left-aligned, Status centre-aligned, numbers right
    for k in range(N):
        r0b = FIRST_DATA_0B + k
        s.fmt(r0b, COL_SAMPLE, align="right", number_format="0")
        s.fmt(r0b, COL_MEAS,   number_format="0.00",  align="right")
        s.fmt(r0b, COL_CL,     number_format="0.0000", align="right")
        s.fmt(r0b, COL_UCL,    number_format="0.0000", align="right")
        s.fmt(r0b, COL_LCL,    number_format="0.0000", align="right")
        s.fmt(r0b, COL_FLAG,   align="center")
        # Colour-code the flag cell
        meas = MEASUREMENTS[k]
        if meas > UCL_val or meas < LCL_val:
            s.fmt(r0b, COL_FLAG, bg=PALETTE["bad"],
                  font_color="#9c0006", bold=True)
        else:
            s.fmt(r0b, COL_FLAG, bg=PALETTE["good"],
                  font_color="#276221")

    # ── Column designations ───────────────────────────────────────────────────
    s.designate(COL_SAMPLE, "X")
    s.designate(COL_MEAS,   "Y")
    s.designate(COL_CL,     "Y")
    s.designate(COL_UCL,    "Y")
    s.designate(COL_LCL,    "Y")

    # ── Sticky notes ──────────────────────────────────────────────────────────
    s.note(
        TABLE_START, COL_MEAS,
        "MEASUREMENTS (column B)\n"
        "Replace these with your own process data — one measurement (or\n"
        "subgroup mean) per row.  All columns C–F, the summary panel,\n"
        "and the chart recalculate automatically.\n\n"
        "Keep the same number of rows, or extend the MEAS_RANGE in the\n"
        "formula bar if you add/remove rows.",
        kind="note",
    )
    s.note(
        TABLE_START, COL_UCL,
        "CONTROL LIMITS — 3-SIGMA RULE\n"
        "Shewhart's rule: a point is out of control if it falls\n"
        "outside UCL = CL + 3σ  or  LCL = CL − 3σ.\n\n"
        "Control limits are estimated from the process data itself\n"
        "(not from customer spec limits).  They represent the\n"
        "natural voice of the process.\n\n"
        "A process can be in statistical control yet still fail\n"
        "to meet specifications — that is what Cp and Cpk measure.",
        kind="note",
    )
    s.note(
        4, COL_VPAR,
        "SPECIFICATION LIMITS (editable)\n"
        "USL and LSL are engineering or customer tolerances —\n"
        "they define what the product must achieve, not what the\n"
        "process naturally produces.\n\n"
        "Edit I5 (USL) and I6 (LSL) here to see Cp and Cpk update.",
        kind="note",
    )
    s.note(
        13, COL_VPAR,
        "PROCESS CAPABILITY INDICES\n"
        "Cp  = (USL − LSL) / (6σ)\n"
        "    Measures potential capability (assumes centred process).\n"
        "    Cp >= 1.33 is typically required for a capable process.\n\n"
        "Cpk = MIN(USL − CL, CL − LSL) / (3σ)\n"
        "    Accounts for process centering.  Cpk < Cp means the\n"
        "    process is off-centre.  Target Cpk >= 1.33.",
        kind="note",
    )

    # ── Chart: control chart ──────────────────────────────────────────────────
    # Data row bounds (0-based, inclusive)
    r0 = FIRST_DATA_0B
    r1 = FIRST_DATA_0B + N - 1

    sample_nums = np.arange(1, N + 1, dtype=float)

    s.chart(
        [
            Series(
                sample_nums, MEAS,
                label="Measurement",
                plot_type="Line+Symbol",
                color="#4472c4",
                linewidth=1.8,
                marker="o",
                markersize=5,
                markerfacecolor="#4472c4",
                markeredgecolor="#1f3864",
                x_col=COL_SAMPLE, y_col=COL_MEAS,
                row_start=r0, row_end=r1,
            ),
            Series(
                sample_nums, cl_arr,
                label="CL (centre line)",
                plot_type="Line",
                color="#70ad47",
                linewidth=2.0,
                linestyle="-",
                x_col=COL_SAMPLE, y_col=COL_CL,
                row_start=r0, row_end=r1,
            ),
            Series(
                sample_nums, ucl_arr,
                label="UCL (+3σ)",
                plot_type="Line",
                color="#ff0000",
                linewidth=1.8,
                linestyle="--",
                x_col=COL_SAMPLE, y_col=COL_UCL,
                row_start=r0, row_end=r1,
            ),
            Series(
                sample_nums, lcl_arr,
                label="LCL (−3σ)",
                plot_type="Line",
                color="#ff0000",
                linewidth=1.8,
                linestyle="--",
                x_col=COL_SAMPLE, y_col=COL_LCL,
                row_start=r0, row_end=r1,
            ),
        ],
        at=(760, 20),
        size=(530, 380),
        title="Shewhart X-bar Control Chart",
        xlabel="Sample #",
        ylabel="Measurement",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation: control limits ────────────────────────────────────────
    s.equation(
        r"\mathrm{UCL} = \bar{x} + 3\hat{\sigma} \quad"
        r"\mathrm{CL} = \bar{x} \quad"
        r"\mathrm{LCL} = \bar{x} - 3\hat{\sigma}",
        at=(760, 420),
        fontsize=14,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(530, 50),
    )

    # ── LaTeX equation: capability ────────────────────────────────────────────
    s.equation(
        r"C_p = \frac{USL - LSL}{6\hat{\sigma}} \qquad"
        r"C_{pk} = \frac{\min(USL-\bar{x},\,\bar{x}-LSL)}{3\hat{\sigma}}",
        at=(760, 484),
        fontsize=14,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.2,
        size=(530, 54),
    )

    # ── Save ──────────────────────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Analysis",
    )
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Statistical Process Control.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
