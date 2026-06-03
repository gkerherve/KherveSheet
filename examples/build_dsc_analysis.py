"""Build the "Thermal Analysis DSC" template.

Differential Scanning Calorimetry (DSC) analysis of a semicrystalline
polymer: glass transition (Tg), melting peak (Tm), and melting enthalpy
(ΔH) — all computed from live per-row formulas referencing editable inputs.

Layout
------
Cols A-E: Temperature (°C) | Heat Flow (W/g) | Baseline (W/g) |
          Corrected HF (W/g) | Trap. contribution (W/g·K)
Inputs (rows 4-11, cols A-B): scan rate, baseline anchors,
          Tg onset/end temperatures
Summary panel (rows 4-13, cols G-H): Tg midpoint, Tm, ΔH, max corrected HF

Convention: endothermic = positive heat flow (endo UP).

Output: examples/templates/Analysis/Thermal Analysis DSC.ksheet

Run:  python examples/build_dsc_analysis.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402

# ── Physical parameters ───────────────────────────────────────────────
# Semicrystalline polymer (nylon-6 like) DSC trace, endo UP convention.
# Heating scan: 10 °C/min, 40–200 °C in 4 °C steps → 41 data points.
SCAN_RATE    = 10.0    # °C/min
TEMPS        = list(range(40, 204, 4))   # 40, 44, 48, …, 200  (41 pts)
N            = len(TEMPS)                # 41

# Raw heat flow values (W/g) — pre-computed from a sigmoid Tg step
# centred at 80 °C and a Gaussian melting peak centred at 158 °C.
# These literals are the "raw experimental data" columns.
HEAT_FLOW = [
    -0.1185, -0.1194, -0.1161, -0.1124, -0.1167,
    -0.1156, -0.1090, -0.1096, -0.1095, -0.0969,
    -0.0814, -0.0629, -0.0512, -0.0538, -0.0515,
    -0.0468, -0.0471, -0.0421, -0.0447, -0.0452,
    -0.0356, -0.0396, -0.0374, -0.0390, -0.0274,
     0.0011,  0.0599,  0.1742,  0.3059,  0.4043,
     0.4043,  0.3162,  0.1780,  0.0671,  0.0123,
    -0.0184, -0.0211, -0.0285, -0.0259, -0.0204,
    -0.0178,
]
assert len(HEAT_FLOW) == N

# Baseline anchor values (stored as inputs in the sheet):
#   Anchor 1:  T=44 °C,  HF=-0.1194 W/g
#   Anchor 2:  T=180 °C, HF=-0.0184 W/g
BL1_T   = 44.0;    BL1_HF  = -0.1194
BL2_T   = 180.0;   BL2_HF  = -0.0184

# Pre-compute numpy arrays for initial chart render and for
# verifying formula results at authoring time (not stored as literals).
T_arr   = np.array(TEMPS, dtype=float)
HF_arr  = np.array(HEAT_FLOW, dtype=float)
BL_arr  = BL1_HF + (T_arr - BL1_T) / (BL2_T - BL1_T) * (BL2_HF - BL1_HF)
COR_arr = HF_arr - BL_arr                    # baseline-corrected heat flow
STEP    = 4.0                                # uniform temperature step (°C)
TRAP_arr = COR_arr * STEP                    # rectangle-rule strip contribution

# Peak range for enthalpy integration: 132 – 180 °C (indices 23–35)
PEAK_ONSET_I = 23;  PEAK_END_I = 35
DH_Wg_K = np.sum(TRAP_arr[PEAK_ONSET_I : PEAK_END_I + 1])   # (W/g)·K
DH_Jg   = DH_Wg_K * 60.0 / SCAN_RATE                        # J/g

# Tm: temperature at maximum corrected heat flow in the peak range.
Tm_i    = PEAK_ONSET_I + int(np.argmax(COR_arr[PEAK_ONSET_I : PEAK_END_I + 1]))
Tm_T    = TEMPS[Tm_i]   # 156 °C

# ── Table layout constants ────────────────────────────────────────────
# table() places header at 0-based row TABLE_START and the first data
# row at 0-based row TABLE_START + 1.
# Sheet row (1-based) = 0-based + 1.
# So data row i (0-based) lives at sheet row TABLE_START + 2 + i.
TABLE_START   = 11             # 0-based header row
FIRST_DATA_0B = TABLE_START + 1     # = 12
FIRST_DATA_SR = FIRST_DATA_0B + 1   # = 13   (1-based sheet row)
LAST_DATA_SR  = FIRST_DATA_SR + N - 1  # = 53

# Column letters (0-based col → 1-based letter):
#   col 0 = A  (Temperature)
#   col 1 = B  (Heat Flow — raw, literal)
#   col 2 = C  (Baseline — formula)
#   col 3 = D  (Corrected HF — formula)
#   col 4 = E  (Trap. contribution — formula)
T_COL   = "A"
HF_COL  = "B"
BL_COL  = "C"
COR_COL = "D"
TR_COL  = "E"

# Input cell references (absolute), 0-based rows 4–11 → SR 5–12:
# $B$5  = scan rate (°C/min)
# $B$6  = BL anchor T1 (°C)
# $B$7  = BL anchor HF1 (W/g)
# $B$8  = BL anchor T2 (°C)
# $B$9  = BL anchor HF2 (W/g)
# $B$10 = Tg onset T (°C)
# $B$11 = Tg end T (°C)
SR_SCAN  = "$B$5"
SR_BLT1  = "$B$6"
SR_BLHF1 = "$B$7"
SR_BLT2  = "$B$8"
SR_BLHF2 = "$B$9"
SR_TGON  = "$B$10"
SR_TGEND = "$B$11"

# Peak range for enthalpy SUM: T=132 (index 23) to T=180 (index 35)
SR_PEAK_ON = FIRST_DATA_SR + PEAK_ONSET_I   # 36
SR_PEAK_END = FIRST_DATA_SR + PEAK_END_I    # 48

# Tm sheet row (direct temperature ref for summary)
SR_TM_ROW = FIRST_DATA_SR + Tm_i           # 42

# Tg midpoint sheet rows (fixed from onset/end): midpoint via inputs.
# We reference them via the input cells $B$10 and $B$11.


def build() -> str:
    wb = Workbook(min_rows=60, min_cols=14)
    s = wb.add_sheet("DSC Analysis")

    # ── Column widths ────────────────────────────────────────────────
    s.col_width(0, 125)   # A — Temperature
    s.col_width(1, 115)   # B — Heat Flow
    s.col_width(2, 115)   # C — Baseline
    s.col_width(3, 135)   # D — Corrected HF
    s.col_width(4, 145)   # E — Trap. contribution
    s.col_width(5, 16)    # F — spacer
    s.col_width(6, 200)   # G — summary / input label
    s.col_width(7, 120)   # H — summary / input value

    # ── Title block ──────────────────────────────────────────────────
    s.title_block(
        "Thermal Analysis — DSC",
        "Differential Scanning Calorimetry: glass transition (Tg), "
        "melting (Tm) and enthalpy (ΔH) — semicrystalline polymer",
        span=8,
    )

    # ── Input panel (0-based rows 3–11, cols 0–1) ────────────────────
    # Row 3  = section heading
    # Rows 4–11 = editable inputs  →  1-based sheet rows 5–12
    s.set(3, 0, "Measurement Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        # (label, value, number_format)
        ("Scan rate  (°C/min)",           SCAN_RATE,  "0.0"),
        ("Baseline anchor  T1 (°C)",      BL1_T,      "0.0"),
        ("Baseline anchor  HF1 (W/g)",    BL1_HF,     "0.0000"),
        ("Baseline anchor  T2 (°C)",      BL2_T,      "0.0"),
        ("Baseline anchor  HF2 (W/g)",    BL2_HF,     "0.0000"),
        ("Tg onset temperature  (°C)",    72.0,       "0.0"),
        ("Tg end temperature  (°C)",      88.0,       "0.0"),
    ]
    for i, (lbl, val, nfmt) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center",
              number_format=nfmt, bold=True)

    s.box(4, 0, 10, 1, color=PALETTE["accent"], width=1.2)

    # Note 1: editable inputs
    s.note(
        4, 1,
        "Yellow cells are editable inputs.\n"
        "Scan rate affects ΔH (column E and the summary).\n"
        "Baseline anchors control columns C and D.\n"
        "Tg onset / end control the midpoint in the summary.",
        kind="note",
    )

    # ── Summary panel (0-based rows 3–12, cols 6–7) ──────────────────
    # 1-based refs: G column is col 6, H column is col 7.
    s.set(3, 6, "Analysis Summary")
    s.fmt(3, 6, bold=True, font_color=PALETTE["header"])

    # Tg midpoint = average of onset and end input cells
    tg_formula  = f"=({SR_TGON}+{SR_TGEND})/2"
    # Tm = temperature at the row with max corrected HF in peak range
    #   (identified as row {SR_TM_ROW} from the chart; change if your
    #    peak lies at a different row after editing the data)
    tm_formula  = f"={T_COL}{SR_TM_ROW}"
    # Max corrected HF (peak height, W/g) — useful for peak purity
    peak_hf_formula = f"=MAX({COR_COL}{SR_PEAK_ON}:{COR_COL}{SR_PEAK_END})"
    # ΔH = SUM(trap contributions in peak range) × 60 / scan_rate
    dh_formula  = (
        f"=SUM({TR_COL}{SR_PEAK_ON}:{TR_COL}{SR_PEAK_END})"
        f"*60/{SR_SCAN}"
    )
    # Corrected HF at Tg midpoint (from the midpoint row)
    # Tg midpoint T = (72+88)/2 = 80 °C = data index 10 → SR = 23
    SR_TG_MID_ROW = FIRST_DATA_SR + 10    # 23
    tg_hf_formula = f"={COR_COL}{SR_TG_MID_ROW}"
    # Heat-flow step at Tg (corrected HF at end minus at onset)
    SR_TGON_ROW  = FIRST_DATA_SR + 8    # 20  (T=72 °C, index 8)
    SR_TGEND_ROW = FIRST_DATA_SR + 12   # 25  (T=88 °C, index 12)
    tg_step_formula = (
        f"={COR_COL}{SR_TGEND_ROW}-{COR_COL}{SR_TGON_ROW}"
    )

    summ = [
        # (label, formula, bg, number_format, bold)
        ("Tg midpoint  (°C)",
         tg_formula,       PALETTE["good"],   "0.0",    True),
        ("Tg HF step  (W/g)",
         tg_step_formula,  PALETTE["band"],   "0.0000", True),
        ("Tm peak temp  (°C)",
         tm_formula,       PALETTE["bad"],    "0.0",    True),
        ("Peak corr. HF  (W/g)",
         peak_hf_formula,  PALETTE["band"],   "0.0000", True),
        ("ΔH melting  (J/g)",
         dh_formula,       PALETTE["accent"], "0.00",   True),
        ("Scan rate  (°C/min)",
         f"={SR_SCAN}",    PALETTE["band_alt"], "0.0",  False),
        ("Peak range onset  (°C)",
         f"={T_COL}{SR_PEAK_ON}",  PALETTE["band_alt"], "0",  False),
        ("Peak range end  (°C)",
         f"={T_COL}{SR_PEAK_END}", PALETTE["band_alt"], "0",  False),
    ]
    for i, (lbl, expr, bg, nfmt, bd) in enumerate(summ):
        r = 4 + i
        s.set(r, 6, lbl)
        s.formula(r, 7, expr)
        s.fmt(r, 6, align="left")
        s.fmt(r, 7, bg=bg, align="center", number_format=nfmt, bold=bd)

    s.box(4, 6, 4 + len(summ) - 1, 7,
          color=PALETTE["header"], width=1.2)

    # Note 2: Tg midpoint method
    s.note(
        4, 6,
        "Tg (midpoint) = (Tg_onset + Tg_end) / 2.\n"
        "Edit the onset/end inputs in column B to re-compute Tg.",
        kind="note",
    )

    # Note 3: Tm identification
    s.note(
        6, 6,
        "Tm is the temperature at the maximum baseline-corrected heat\n"
        "flow within the melting peak range (row reference formula).\n"
        "If you update the raw data, confirm which row holds the peak\n"
        "and update the Tm formula accordingly.",
        kind="note",
    )

    # Note 4: enthalpy by integration
    s.note(
        8, 6,
        "ΔH (J/g) = SUM(col E, peak range) × 60 / scan_rate\n"
        "Col E = D_i × 4  (rectangle rule, uniform 4 °C step).\n"
        "This equals integral(HF_corr dT) / (scan_rate in K/s).\n"
        "Edit scan rate in B5 to correct for a different experiment.",
        kind="note",
    )

    # ── Section label above table ────────────────────────────────────
    s.set(TABLE_START - 1, 0, "DSC Data Table (41 points, 40–200 °C, step 4 °C)")
    s.fmt(TABLE_START - 1, 0, bold=True, font_color=PALETTE["header"])
    s.merge(TABLE_START - 1, 0, 1, 5)

    # ── Data table ───────────────────────────────────────────────────
    # Formulas reference:
    #   $B$5  = scan rate
    #   $B$6  = BL anchor T1,  $B$7  = BL anchor HF1
    #   $B$8  = BL anchor T2,  $B$9  = BL anchor HF2
    # Baseline (linear):
    #   C{rr} = $B$7 + (A{rr} - $B$6) / ($B$8 - $B$6) * ($B$9 - $B$7)
    # Corrected HF:
    #   D{rr} = B{rr} - C{rr}
    # Trap contribution (rectangle rule, step 4 °C):
    #   E{rr} = D{rr} * 4

    rows = []
    for i in range(N):
        # 1-based sheet row for this data row
        rr = FIRST_DATA_SR + i

        bl_formula  = (
            f"={SR_BLHF1}+({T_COL}{rr}-{SR_BLT1})"
            f"/({SR_BLT2}-{SR_BLT1})"
            f"*({SR_BLHF2}-{SR_BLHF1})"
        )
        cor_formula = f"={HF_COL}{rr}-{BL_COL}{rr}"
        trap_formula = f"={COR_COL}{rr}*4"

        rows.append([
            float(TEMPS[i]),           # col A — temperature (literal, indep. variable)
            float(HEAT_FLOW[i]),       # col B — raw heat flow (literal, raw data)
            bl_formula,                # col C — baseline (formula)
            cor_formula,               # col D — corrected HF (formula)
            trap_formula,              # col E — trap. contribution (formula)
        ])

    s.table(
        TABLE_START, 0,
        headers=[
            "Temperature (°C)",
            "Heat Flow (W/g)",
            "Baseline (W/g)",
            "Corrected HF (W/g)",
            "Trap. contrib. (W/g·K)",
        ],
        rows=rows,
        banded=True,
    )

    # Per-column number formats and alignment overrides
    for i in range(N):
        r0 = FIRST_DATA_0B + i
        s.fmt(r0, 0, align="right", number_format="0")
        s.fmt(r0, 1, align="right", number_format="0.0000")
        s.fmt(r0, 2, align="right", number_format="0.0000")
        s.fmt(r0, 3, align="right", number_format="0.0000")
        s.fmt(r0, 4, align="right", number_format="0.0000")

    # Highlight the peak rows (T=132–180 °C, indices 23–35)
    for i in range(PEAK_ONSET_I, PEAK_END_I + 1):
        r0 = FIRST_DATA_0B + i
        for c in range(5):
            s.fmt(r0, c, bg="#fff0d0")   # warm highlight for melting region

    # Highlight Tg region (T=72–88 °C, indices 8–12)
    for i in range(8, 13):
        r0 = FIRST_DATA_0B + i
        for c in range(5):
            s.fmt(r0, c, bg="#e8f5e9")   # green tint for glass transition region

    # Designate axis columns
    s.designate(0, "X")   # Temperature
    s.designate(2, "Y")   # Baseline
    s.designate(3, "Y")   # Corrected HF

    # ── Table notes ──────────────────────────────────────────────────
    s.note(
        TABLE_START, 2,
        "Baseline (col C) = linear interpolation between the two\n"
        "anchor points (T1, HF1) and (T2, HF2) in the input panel.\n"
        "Changing any anchor input instantly updates every row.",
        kind="note",
    )
    s.note(
        TABLE_START, 3,
        "Baseline-corrected HF (col D) = Heat Flow − Baseline.\n"
        "The Tg step and melting peak are visible in this column.\n"
        "Endo UP convention: endothermic = positive.",
        kind="note",
    )
    s.note(
        TABLE_START, 4,
        "Trap. contribution (col E) = D_i × 4 (°C step).\n"
        "SUM over the highlighted peak rows (warm colour) gives the\n"
        "peak area in (W/g)·K; dividing by scan rate yields ΔH in J/g.",
        kind="note",
    )

    # ── Charts ───────────────────────────────────────────────────────
    # Chart data rows: 0-based FIRST_DATA_0B … FIRST_DATA_0B + N - 1
    r0_bind = FIRST_DATA_0B
    r1_bind = FIRST_DATA_0B + N - 1

    # Chart 1: Raw Heat Flow and Baseline vs Temperature
    s.chart(
        [
            Series(
                T_arr, HF_arr,
                label="Heat Flow",
                plot_type="Line+Symbol",
                color="#4472c4",
                linewidth=2.0,
                marker="o",
                markersize=3.0,
                x_col=0, y_col=1,
                row_start=r0_bind, row_end=r1_bind,
            ),
            Series(
                T_arr, BL_arr,
                label="Baseline",
                plot_type="Line",
                color="#ed7d31",
                linewidth=1.5,
                linestyle="--",
                x_col=0, y_col=2,
                row_start=r0_bind, row_end=r1_bind,
            ),
        ],
        at=(560, 20),
        size=(490, 300),
        title="DSC Trace — Heat Flow and Baseline",
        xlabel="Temperature (°C)",
        ylabel="Heat Flow (W/g)",
        grid=True,
        legend=True,
    )

    # Chart 2: Baseline-corrected Heat Flow vs Temperature
    s.chart(
        [
            Series(
                T_arr, COR_arr,
                label="Corrected HF",
                plot_type="Line+Symbol",
                color="#70ad47",
                linewidth=2.0,
                marker="o",
                markersize=3.0,
                x_col=0, y_col=3,
                row_start=r0_bind, row_end=r1_bind,
            ),
        ],
        at=(560, 340),
        size=(490, 300),
        title="Baseline-Corrected Heat Flow",
        xlabel="Temperature (°C)",
        ylabel="Corrected HF (W/g)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation (baseline-corrected HF and ΔH integral) ───────
    # mathtext: \frac (not \tfrac), \Delta, \dot, \mathrm{}
    s.equation(
        r"\Delta H = \frac{\int_{T_1}^{T_2} \Delta \dot{q}(T)\,dT}{\beta}",
        at=(560, 660),
        fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(310, 72),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        _HERE, "templates", "Analysis",
        "Thermal Analysis DSC.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
