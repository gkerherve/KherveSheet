"""Build the "TGA Curve Processing" data-manipulation template.

Demonstrates the step-by-step workflow for processing raw TGA
(thermogravimetric) data: normalisation to mass%, central-difference
DTG derivative, and decomposition-step analysis — all as live formulas.

Output: examples/templates/Data Processing/TGA Curve Processing.ksheet

Run:  python examples/build_tga_processing.py

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

# ── Raw TGA data (physically realistic) ──────────────────────────────
# Two-step decomposition:
#   Step 1 — moisture / adsorbed solvent loss:  ~75–150 °C,  ~7.4% loss
#   Step 2 — organic polymer decomposition:  ~300–550 °C,  ~51.4% loss
#   Residue at 875 °C — mineral filler / char:  ~35%
#
# Generated from a logistic (sigmoid) model; values rounded to 3 d.p.
# for realistic-looking experimental data.

TEMPS = [
    25,  50,  75, 100, 125, 150, 175, 200, 225, 250,
    275, 300, 325, 350, 375, 400, 425, 450, 475, 500,
    525, 550, 575, 600, 625, 650, 675, 700, 725, 750,
    775, 800, 825, 850, 875,
]

MASS_MG = [
    25.167, 25.154, 25.062, 24.552, 23.590, 23.198, 23.114, 23.061,
    22.978, 22.827, 22.553, 22.068, 21.249, 19.961, 18.154, 15.983,
    13.811, 12.005, 10.717,  9.898,  9.413,  9.139,  8.988,  8.906,
     8.861,  8.837,  8.824,  8.817,  8.814,  8.812,  8.811,  8.810,
     8.810,  8.810,  8.810,
]

N = len(TEMPS)
assert len(MASS_MG) == N, "Data length mismatch"

M0 = MASS_MG[0]           # initial mass (mg) — stored in sheet as input

# Pre-compute Mass% and DTG for chart data binding (numpy arrays must
# match what the formulas evaluate to on first load).
T_arr  = np.array(TEMPS, dtype=float)
wt_pct = np.array(MASS_MG, dtype=float) / M0 * 100.0

# DTG = d(Mass%)/dT — central difference; forward/backward at edges
dtg = np.zeros(N)
dtg[0]  = (wt_pct[1]  - wt_pct[0])  / (T_arr[1]  - T_arr[0])   # forward
for i in range(1, N - 1):
    dtg[i] = (wt_pct[i + 1] - wt_pct[i - 1]) / (T_arr[i + 1] - T_arr[i - 1])
dtg[-1] = (wt_pct[-1] - wt_pct[-2]) / (T_arr[-1] - T_arr[-2])   # backward


def build() -> str:
    wb = Workbook(min_rows=60, min_cols=14)
    s = wb.add_sheet("TGA Processing")

    # ── Column widths ────────────────────────────────────────────────
    s.col_width(0, 115)   # A — Temperature (°C)
    s.col_width(1, 100)   # B — Mass (mg)
    s.col_width(2, 100)   # C — Mass %
    s.col_width(3, 120)   # D — DTG (%/°C)
    s.col_width(4, 16)    # E — spacer
    s.col_width(5, 200)   # F — summary / input label
    s.col_width(6, 115)   # G — summary / input value

    # ── Title block ──────────────────────────────────────────────────
    s.title_block(
        "TGA Curve Processing",
        "Step-by-step data workflow: normalise → DTG derivative → "
        "decomposition-step analysis",
        span=7,
    )

    # ── Input panel (rows 3–4, cols 0–1) ────────────────────────────
    # Only ONE editable input: the initial mass m0 (mg).
    # Everything else is calculated from the raw Mass (mg) column and m0.
    s.set(3, 0, "Sample Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    s.set(4, 0, "Initial mass  m0  (mg)")
    s.set(4, 1, round(M0, 3))
    s.fmt(4, 0, align="left")
    s.fmt(4, 1, bg=PALETTE["warn"], align="center",
          number_format="0.000", bold=True)
    s.box(4, 0, 4, 1, color=PALETTE["accent"], width=1.2)

    # Note 1: edit the initial mass
    s.note(
        4, 1,
        "Edit this cell to change the normalisation reference.\n"
        "All Mass % values (column C) and DTG values (column D)\n"
        "recalculate automatically via live formulas.",
        kind="note",
    )

    # ── Section label ────────────────────────────────────────────────
    s.set(6, 0, "Processing Steps:")
    s.fmt(6, 0, bold=True, font_color=PALETTE["header"])
    s.set(7, 0, "1) Mass % = (Mass / m0) × 100   (col C)")
    s.fmt(7, 0, italic=True, font_color="#444444")
    s.set(8, 0, "2) DTG = d(Mass%)/dT  central diff  (col D)")
    s.fmt(8, 0, italic=True, font_color="#444444")

    # ── Table layout constants ────────────────────────────────────────
    # table() places header at 0-based row TABLE_START and
    # first data row at 0-based row TABLE_START+1.
    # Sheet rows (1-based) = 0-based + 1.
    TABLE_START      = 10            # 0-based row of header
    FIRST_DATA_0B    = TABLE_START + 1        # 0-based first data row = 11
    FIRST_DATA_SR    = FIRST_DATA_0B + 1      # 1-based sheet row      = 12
    LAST_DATA_SR     = FIRST_DATA_SR + N - 1  # 1-based last data row  = 46
    # m0 is in cell B5 (0-based row 4, col 1 → 1-based = row 5, col B)
    M0_REF = "$B$5"

    # Pre-label above the table
    s.set(9, 0, "Raw Data and Processed Columns  (35 data points, 25–875 °C)")
    s.fmt(9, 0, bold=True, font_color=PALETTE["header"])
    s.merge(9, 0, 1, 4)

    # ── Build table rows ─────────────────────────────────────────────
    rows = []
    for i, (T, m) in enumerate(zip(TEMPS, MASS_MG)):
        # 1-based sheet row for this data row
        rr = FIRST_DATA_SR + i

        # Column C: Mass % = mass_mg / m0 * 100
        mass_pct_formula = f"=B{rr}/{M0_REF}*100"

        # Column D: DTG = d(Mass%)/dT — central/forward/backward difference
        if i == 0:
            # Forward difference (first row — no prior row available)
            dtg_formula = f"=(C{rr + 1}-C{rr})/(A{rr + 1}-A{rr})"
        elif i == N - 1:
            # Backward difference (last row — no next row available)
            dtg_formula = f"=(C{rr}-C{rr - 1})/(A{rr}-A{rr - 1})"
        else:
            # Central difference (all interior rows)
            dtg_formula = f"=(C{rr + 1}-C{rr - 1})/(A{rr + 1}-A{rr - 1})"

        rows.append([
            float(T),       # col 0: Temperature — literal (independent grid)
            round(m, 3),    # col 1: Mass (mg)   — literal (raw data)
            mass_pct_formula,   # col 2: Mass %  — FORMULA
            dtg_formula,        # col 3: DTG     — FORMULA
        ])

    s.table(
        TABLE_START, 0,
        headers=["Temperature (°C)", "Mass (mg)", "Mass %", "DTG (%/°C)"],
        rows=rows,
        banded=True,
    )

    # Override per-column number formats and alignment
    for i in range(N):
        r0 = FIRST_DATA_0B + i
        s.fmt(r0, 0, align="right", number_format="0")
        s.fmt(r0, 1, align="right", number_format="0.000")
        s.fmt(r0, 2, align="right", number_format="0.000")
        s.fmt(r0, 3, align="right", number_format="0.00000")

    # Designate axis columns
    s.designate(0, "X")   # Temperature
    s.designate(2, "Y")   # Mass %
    s.designate(3, "Y")   # DTG

    # Note 2: Mass% normalisation
    s.note(
        TABLE_START, 2,
        "Mass % = (Mass(mg) / m0) × 100\n"
        "Normalises the raw mass signal to a percentage of the\n"
        "starting mass. Editing m0 (yellow cell) rescales every row.",
        kind="note",
    )

    # Note 3: DTG central difference
    s.note(
        TABLE_START, 3,
        "DTG = d(Mass%)/dT — derivative of Mass% w.r.t. Temperature.\n"
        "Central difference: (M%[i+1] - M%[i-1]) / (T[i+1] - T[i-1])\n"
        "Edges use forward/backward diff to avoid #ERROR.\n"
        "Peaks (most negative) give the decomposition step temperatures.",
        kind="note",
    )

    # ── Summary panel (rows 3–12, cols 5–6) ──────────────────────────
    # Decomposition step bounds (row indices based on fixed temp grid):
    #   Step 1: onset T=75  → sheet row FIRST_DATA_SR+2  = SR of i=2
    #           end   T=150 → sheet row FIRST_DATA_SR+5  = SR of i=5
    #   Step 2: onset T=300 → sheet row FIRST_DATA_SR+11 = SR of i=11
    #           end   T=550 → sheet row FIRST_DATA_SR+21 = SR of i=21
    # Peak DTG (most negative DTG) temperatures:
    #   Step 1: T=100 → sheet row FIRST_DATA_SR+3  = SR of i=3
    #   Step 2: T=400 → sheet row FIRST_DATA_SR+15 = SR of i=15
    #   (identified from the data; DTG peaks at -0.117 and -0.345 %/°C)

    SR_ONSET1 = FIRST_DATA_SR + 2    # T=75  °C
    SR_END1   = FIRST_DATA_SR + 5    # T=150 °C
    SR_PEAK1  = FIRST_DATA_SR + 3    # T=100 °C (peak DTG step 1)
    SR_ONSET2 = FIRST_DATA_SR + 11   # T=300 °C
    SR_END2   = FIRST_DATA_SR + 21   # T=550 °C
    SR_PEAK2  = FIRST_DATA_SR + 15   # T=400 °C (peak DTG step 2)
    SR_LAST   = LAST_DATA_SR         # T=875 °C (final)

    s.set(3, 5, "Analysis Summary")
    s.fmt(3, 5, bold=True, font_color=PALETTE["header"])

    summ = [
        # (label, formula, bg_color, number_format)
        ("Initial mass m0 (mg)",
         f"={M0_REF}",
         PALETTE["band"], "0.000"),
        ("Final residue % (875 °C)",
         f"=C{SR_LAST}",
         PALETTE["good"], "0.00"),
        ("Total mass loss %",
         f"=C{FIRST_DATA_SR}-C{SR_LAST}",
         PALETTE["bad"], "0.00"),
        # ── Step 1 ──────────────────────────────────────────────────
        ("Step 1 onset temp (°C)",
         f"=A{SR_ONSET1}",
         PALETTE["band_alt"], "0"),
        ("Step 1 end temp (°C)",
         f"=A{SR_END1}",
         PALETTE["band_alt"], "0"),
        ("Step 1 mass loss %  (75–150 °C)",
         f"=C{SR_ONSET1}-C{SR_END1}",
         PALETTE["warn"], "0.00"),
        ("Step 1 peak DTG temp (°C)",
         f"=A{SR_PEAK1}",
         PALETTE["warn"], "0"),
        # ── Step 2 ──────────────────────────────────────────────────
        ("Step 2 onset temp (°C)",
         f"=A{SR_ONSET2}",
         PALETTE["band_alt"], "0"),
        ("Step 2 end temp (°C)",
         f"=A{SR_END2}",
         PALETTE["band_alt"], "0"),
        ("Step 2 mass loss %  (300–550 °C)",
         f"=C{SR_ONSET2}-C{SR_END2}",
         PALETTE["bad"], "0.00"),
        ("Step 2 peak DTG temp (°C)",
         f"=A{SR_PEAK2}",
         PALETTE["bad"], "0"),
    ]

    for i, (lbl, expr, col, nfmt) in enumerate(summ):
        r = 4 + i
        s.set(r, 5, lbl)
        s.formula(r, 6, expr)
        s.fmt(r, 5, align="left")
        s.fmt(r, 6, bg=col, align="center", number_format=nfmt, bold=True)

    s.box(4, 5, 4 + len(summ) - 1, 6, color=PALETTE["header"], width=1.2)

    # Note 4: onset / residue / decomposition steps
    s.note(
        4, 5,
        "Onset temp = temperature where significant mass loss begins.\n"
        "Peak DTG temp = temperature of maximum decomposition rate.\n"
        "Residue % = remaining mass at end of run (ash / char / filler).\n"
        "Step mass loss = Mass% at onset minus Mass% at end of step.",
        kind="note",
    )

    # ── Chart: Mass% and DTG vs Temperature (two series, live-bound) ─
    # Data rows occupy 0-based rows FIRST_DATA_0B .. FIRST_DATA_0B+N-1
    row0_bind = FIRST_DATA_0B
    row1_bind = FIRST_DATA_0B + N - 1

    s.chart(
        [
            Series(
                T_arr, wt_pct,
                label="Mass %",
                plot_type="Line+Symbol",
                color="#4472c4",
                linewidth=2.0,
                marker="o",
                markersize=3.5,
                x_col=0, y_col=2,
                row_start=row0_bind, row_end=row1_bind,
            ),
            Series(
                T_arr, dtg,
                label="DTG (%/°C)",
                plot_type="Line",
                color="#ed7d31",
                linewidth=1.8,
                linestyle="--",
                x_col=0, y_col=3,
                row_start=row0_bind, row_end=row1_bind,
            ),
        ],
        at=(560, 20),
        size=(490, 340),
        title="TGA Curve — Mass % and DTG vs Temperature",
        xlabel="Temperature (°C)",
        ylabel="Mass % / DTG (%/°C)",
        grid=True,
        legend=True,
    )

    # ── Equation: central-difference DTG ─────────────────────────────
    # Mathtext: \frac, \mathrm{} — no \tfrac/\dfrac/\text/\bigg
    s.equation(
        r"\left.\frac{dw}{dT}\right|_{i} \approx "
        r"\frac{w_{i+1} - w_{i-1}}{T_{i+1} - T_{i-1}}",
        at=(560, 380),
        fontsize=17,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(340, 72),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        _HERE,
        "templates", "Data Processing",
        "TGA Curve Processing.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
