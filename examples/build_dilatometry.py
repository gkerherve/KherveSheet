"""Build the "Dilatometry" demo .ksheet example.

A materials-science example of thermal expansion (dilatometry) with two
CTE regimes split at a phase-transition temperature.  Features: editable
input panel, a large banded formula table, a live-bound strain vs.
temperature chart showing the kink at the phase transition, a LaTeX
equation, and three yellow sticky notes.

CTE inputs are stored as integer ppm (µm/m/°C = 10^-6 /°C) so that the
cell values remain human-readable integers.  Formulas divide by 1 000 000
to recover the dimensionless CTE.

Run:  python examples/build_dilatometry.py

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


# ── Physical parameters ───────────────────────────────────────────────
L0           = 10.0     # initial length (mm)
T0           = 25.0     # reference temperature (°C)
alpha1_ppm   = 12.0     # CTE below transition (µm/m/°C = 12e-6 /°C)
alpha2_ppm   = 20.0     # CTE above transition (µm/m/°C = 20e-6 /°C)
T_trans      = 350.0    # phase-transition temperature (°C)
T_START      = 25.0     # table start (°C)
T_END        = 800.0    # table end (°C)
N_STEPS      = 32       # temperature steps in table


def strain_py(T, alpha1=alpha1_ppm * 1e-6, alpha2=alpha2_ppm * 1e-6):
    """Two-regime linear strain — mirrors the sheet formula."""
    if T <= T_trans:
        return alpha1 * (T - T0)
    else:
        return alpha1 * (T_trans - T0) + alpha2 * (T - T_trans)


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=14)
    s = wb.add_sheet("Dilatometry")

    # ── Column widths ────────────────────────────────────────────────
    s.col_width(0, 200)   # label column (inputs)
    s.col_width(1, 110)   # value column (inputs)
    s.col_width(3, 120)   # T (°C)
    s.col_width(4, 145)   # strain
    s.col_width(5, 130)   # ΔL (µm)
    s.col_width(6, 115)   # L (mm)
    s.col_width(9, 175)   # summary label
    s.col_width(10, 120)  # summary value

    # ── Title block ─────────────────────────────────────────────────
    s.title_block("Dilatometry — Thermal Expansion",
                  "Two-regime CTE model with phase-transition kink  "
                  "|  Materials Science")

    # ── Input panel (rows 3–8, cols 0–1) ────────────────────────────
    # Row 3 = header; rows 4–8 = inputs.
    # 1-based sheet cells: B5=L0, B6=T0, B7=alpha1_ppm, B8=alpha2_ppm, B9=T_trans
    s.set(3, 0, "Editable Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    input_rows = [
        ("Initial length L0 (mm)",            L0,           "0.00"),
        ("Reference temp T0 (deg C)",          T0,           "0.0"),
        ("CTE below alpha1 (ppm = 1e-6/degC)", alpha1_ppm,   "0.0"),
        ("CTE above alpha2 (ppm = 1e-6/degC)", alpha2_ppm,   "0.0"),
        ("Transition temp T_trans (deg C)",     T_trans,      "0.0"),
    ]
    INPUT_ROW_START = 4   # 0-based row of first input
    for i, (lbl, val, nfmt) in enumerate(input_rows):
        r = INPUT_ROW_START + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format=nfmt)

    s.box(INPUT_ROW_START, 0, INPUT_ROW_START + 4, 1,
          color=PALETTE["accent"], width=1.2)

    # ── Sticky note 1: edit inputs ───────────────────────────────────
    s.note(INPUT_ROW_START, 1,
           "Edit any yellow cell - the table and chart recalculate.\n"
           "CTE is stored in ppm (1 ppm = 1e-6 /degC). "
           "The slope of the strain curve equals the CTE.",
           kind="note")

    # ── Table layout constants ───────────────────────────────────────
    # TABLE_START = 13 (0-based).  Header at 0-based row 13 (sheet row 14).
    # First data row at 0-based row 14 (sheet row 15).
    # Last data row at 0-based row 14 + N_STEPS - 1 = 45 (sheet row 46).
    TABLE_START = 13
    # 1-based sheet row of first data row:
    SR_FIRST = TABLE_START + 2    # = 15
    SR_LAST  = TABLE_START + 1 + N_STEPS  # = 46

    # Column letters for formulas (columns 3-6 → D-G).
    T_COL      = "D"   # col 3
    STRAIN_COL = "E"   # col 4
    DL_COL     = "F"   # col 5
    L_COL      = "G"   # col 6

    # ── Summary panel (rows 3–9, cols 9–10) ─────────────────────────
    # All formulas below reference: B5=L0, B6=T0, B7=alpha1_ppm,
    #                               B8=alpha2_ppm, B9=T_trans.
    s.set(3, 9, "Summary")
    s.fmt(3, 9, bold=True, font_color=PALETTE["header"])

    summ = [
        ("alpha1 (ppm)", "=$B$7", PALETTE["band"]),
        ("alpha2 (ppm)", "=$B$8", PALETTE["band"]),
        ("T_trans (deg C)", "=$B$9", PALETTE["band_alt"]),
        # strain at T_trans = alpha1_ppm/1e6 * (T_trans - T0)
        ("Strain at T_trans",
         "=$B$7/1000000*($B$9-$B$6)",
         PALETTE["good"]),
        # total DeltaL over range
        (f"Total DL {T_START}-{T_END}C (um)",
         f"=MAX({DL_COL}{SR_FIRST}:{DL_COL}{SR_LAST})"
         f"-MIN({DL_COL}{SR_FIRST}:{DL_COL}{SR_LAST})",
         PALETTE["good"]),
        ("Max length L (mm)",
         f"=MAX({L_COL}{SR_FIRST}:{L_COL}{SR_LAST})",
         PALETTE["good"]),
    ]
    SUMM_FMT = ["0.0", "0.0", "0.0", "0.000", "0.0", "0.000"]
    for i, ((lbl, expr, col), nfmt) in enumerate(zip(summ, SUMM_FMT)):
        r = 4 + i
        s.set(r, 9, lbl)
        s.formula(r, 10, expr)
        s.fmt(r, 9, align="left")
        s.fmt(r, 10, bg=col, align="center", number_format=nfmt, bold=True)

    s.box(4, 9, 4 + len(summ) - 1, 10,
          color=PALETTE["header"], width=1.0)

    # ── Section label ────────────────────────────────────────────────
    s.set(12, 3, "Dilatometry Table")
    s.fmt(12, 3, bold=True, font_color=PALETTE["header"])

    # ── Pre-compute numpy arrays for chart data-binding ──────────────
    temps   = np.linspace(T_START, T_END, N_STEPS)
    alpha1  = alpha1_ppm * 1e-6
    alpha2  = alpha2_ppm * 1e-6
    strains = np.array([strain_py(T) for T in temps])
    dL_um   = strains * L0 * 1000.0

    # ── Data table ───────────────────────────────────────────────────
    # Formulas reference inputs via absolute $B$ refs:
    #   $B$5=L0, $B$6=T0, $B$7=alpha1_ppm, $B$8=alpha2_ppm, $B$9=T_trans
    # CTE is divided by 1000000 to convert ppm → dimensionless.
    rows = []
    for k, T in enumerate(temps):
        # 1-based sheet row of this data row.
        # table() places row k at 0-based row TABLE_START+1+k.
        # 1-based = 0-based + 1 = TABLE_START + 2 + k.
        sr = TABLE_START + 2 + k

        # Two-regime strain formula (both IF branches are numeric — safe).
        strain_formula = (
            f"=IF({T_COL}{sr}<=$B$9,"
            f"$B$7/1000000*({T_COL}{sr}-$B$6),"
            f"$B$7/1000000*($B$9-$B$6)+$B$8/1000000*({T_COL}{sr}-$B$9))"
        )
        dl_formula = f"={STRAIN_COL}{sr}*$B$5*1000"
        l_formula  = f"=$B$5+{STRAIN_COL}{sr}*$B$5"

        rows.append([
            round(float(T), 4),
            strain_formula,
            dl_formula,
            l_formula,
        ])

    s.table(TABLE_START, 3,
            headers=["T (deg C)", "Strain dL/L0", "dL (um)", "L (mm)"],
            rows=rows,
            number_format="0.0000",
            banded=True)

    # Override temperature column format.
    for k in range(N_STEPS):
        r = TABLE_START + 1 + k
        s.fmt(r, 3, align="right", number_format="0.0")

    # Designate chart axis columns.
    s.designate(3, "X")   # temperature
    s.designate(4, "Y")   # strain
    s.designate(5, "Y")   # ΔL µm

    # ── Sticky note 2: the kink ──────────────────────────────────────
    s.note(TABLE_START, 3,
           "The slope of the strain curve equals the CTE.\n"
           "At T_trans the slope changes from alpha1 to alpha2 -\n"
           "visible as a kink in the chart.",
           kind="note")

    # ── Sticky note 3: dilatometry applications ──────────────────────
    s.note(TABLE_START, 6,
           "Dilatometry detects phase transitions, sintering onset,\n"
           "and densification events as abrupt slope changes in dL vs T.",
           kind="note")

    # ── Chart 1: Strain vs T (live-bound) ────────────────────────────
    r0_bind = TABLE_START + 1
    r1_bind = TABLE_START + N_STEPS

    s.chart(
        [Series(
            x=temps,
            y=strains,
            label="Strain dL/L0",
            plot_type="Line+Symbol",
            color="#4472c4",
            linewidth=2.0,
            marker="o",
            markersize=4.0,
            x_col=3,
            y_col=4,
            row_start=r0_bind,
            row_end=r1_bind,
        )],
        at=(560, 30),
        size=(450, 320),
        title="Thermal Strain vs. Temperature",
        xlabel="Temperature (deg C)",
        ylabel="Strain  dL / L0",
        grid=True,
        legend=True,
    )

    # ── Chart 2: DeltaL (µm) vs T (live-bound) ───────────────────────
    s.chart(
        [Series(
            x=temps,
            y=dL_um,
            label="dL (um)",
            plot_type="Line+Symbol",
            color="#ed7d31",
            linewidth=2.0,
            marker="s",
            markersize=4.0,
            x_col=3,
            y_col=5,
            row_start=r0_bind,
            row_end=r1_bind,
        )],
        at=(560, 380),
        size=(450, 300),
        title="Thermal Elongation vs. Temperature",
        xlabel="Temperature (deg C)",
        ylabel="dL (um)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ───────────────────────────────────────────────
    # mathtext: \frac (not \tfrac), \alpha, \Delta, \mathrm{}
    s.equation(
        r"\frac{\Delta L}{L_0} = \alpha \, (T - T_0)",
        at=(560, 700),
        fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(300, 58),
    )

    # ── Save ─────────────────────────────────────────────────────────
    out = os.path.join(_HERE, "Dilatometry.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
