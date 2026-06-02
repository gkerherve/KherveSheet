"""Build the "Carrier Concentration" demo .ksheet example.

Demonstrates thermally-activated electron concentration in a semiconductor
conduction band (Arrhenius behaviour), with a live-bound Arrhenius plot,
summary formulas, and a LaTeX equation.

Physics:
    n(T) = Nc * exp( -(Ec - EF) / (kB * T) )
    kB = 0.00008617 eV/K  (never written in scientific notation inside
    formula strings — the 'E' would be parsed as column E).

Run:  python examples/build_carrier_concentration.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import numpy as np
from ksheet_author import Workbook, Series, PALETTE

# Physical constants (Python-side, for initial render only)
KB = 8.617e-5        # eV/K
KB_FORMULA = "0.00008617"  # plain decimal for formula strings (avoids E-col bug)

# Default inputs
NC_DEFAULT = 2.8e19   # cm^-3  (literal cell value — OK as a number)
EACT_DEFAULT = 0.55   # eV  (Ec - EF)

# Temperature grid: fixed literals 250..500 K in 11 steps
T_VALS = np.linspace(250, 500, 26)   # 26 rows (250, 260, ..., 500 K)
N_ROWS = len(T_VALS)


def build() -> str:
    wb = Workbook(min_rows=44, min_cols=16)
    s = wb.add_sheet("Carrier Conc.")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block(
        "Carrier Concentration in Semiconductors",
        "Thermally activated electron density n(T) = Nc · exp(-(Ec-EF) / kB·T)",
        span=7,
    )

    # ── Input panel ────────────────────────────────────────────────────
    # Row 3: section label
    s.set(3, 0, "Editable Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"], font_size=11)

    # Row 4: Nc  → B5 in A1 (0-based row 4, col 1)
    s.set(4, 0, "Effective DOS  Nc (cm⁻³)")
    s.set(4, 1, NC_DEFAULT)
    s.fmt(4, 0, align="left")
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", bold=True,
          number_format="0.00E+00")

    # Row 5: Eact → B6 in A1
    s.set(5, 0, "Activation energy  Ec−EF (eV)")
    s.set(5, 1, EACT_DEFAULT)
    s.fmt(5, 0, align="left")
    s.fmt(5, 1, bg=PALETTE["warn"], align="center", bold=True,
          number_format="0.000")

    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 230)
    s.col_width(1, 120)

    s.note(4, 1,
           "Edit Nc here — n(T), ln(n) and the Arrhenius chart all recompute.",
           kind="note")
    s.note(5, 1,
           "Edit Ec−EF (activation energy) here. "
           "The slope of ln(n) vs 1000/T equals −(Ec−EF)/(kB·1000).",
           kind="note")

    # ── Data table ─────────────────────────────────────────────────────
    # Column layout (0-based):
    #   A (0): T (K)       — fixed literal
    #   B (1): 1000/T      — formula
    #   C (2): n (cm^-3)   — formula
    #   D (3): ln(n)       — formula
    #
    # table() header sits at sheet row (table_start+1) → 0-based row 8.
    # First data row (0-based) = 9;  A1 row = 10.

    TABLE_START = 8   # 0-based row index of the header row

    s.set(7, 0, "Arrhenius Data Table")
    s.fmt(7, 0, bold=True, font_color=PALETTE["header"], font_size=11)

    # Build rows: T literal, then formula strings using A1 sheet rows.
    rows = []
    for k, T in enumerate(T_VALS):
        # 1-based sheet row of this data row
        rr = TABLE_START + 2 + k   # header at TABLE_START+1, data starts +2

        # Column A: T literal (K)
        t_cell = f"A{rr}"
        # Column B: 1000/T
        inv_t = f"=1000/{t_cell}"
        # Column C: n(T) = Nc * EXP(-(Ec-EF)/(kB*T))
        #   Nc is at B5, Eact is at B6, kB = 0.00008617 (no sci-notation!)
        n_cell = f"C{rr}"
        n_formula = f"=$B$5*EXP(-$B$6/({KB_FORMULA}*{t_cell}))"
        # Column D: ln(n)
        ln_formula = f"=LN({n_cell})"

        rows.append([round(float(T), 1), inv_t, n_formula, ln_formula])

    s.table(
        TABLE_START, 0,
        headers=["T (K)", "1000/T (K⁻¹)", "n (cm⁻³)", "ln(n)"],
        rows=rows,
        number_format="0.0000",
        banded=True,
    )

    # Override column-A formatting to show 1 decimal, left-aligned
    for k in range(N_ROWS):
        r = TABLE_START + 1 + k
        s.fmt(r, 0, number_format="0.0", align="right")

    # Column widths
    s.col_width(0, 80)
    s.col_width(1, 120)
    s.col_width(2, 130)
    s.col_width(3, 110)

    # Designate axes for the app's column-role hints
    s.designate(1, "X")   # 1000/T
    s.designate(3, "Y")   # ln(n)

    # ── Summary panel ──────────────────────────────────────────────────
    # Placed in columns F-G (5-6, 0-based), rows 4-9.
    # 1-based sheet rows of the data block
    first_data_row = TABLE_START + 2          # e.g. 11
    last_data_row  = TABLE_START + 1 + N_ROWS # e.g. 36

    s.set(3, 5, "Summary")
    s.fmt(3, 5, bold=True, font_color=PALETTE["header"], font_size=11)

    # Slope of Arrhenius plot: -(Ec-EF) / (kB * 1000)
    #   Written as a formula referencing $B$6 and kB literal
    slope_formula = f"=-$B$6/({KB_FORMULA}*1000)"

    # n at 300 K: Nc * EXP(-(Ec-EF)/(kB*300))
    n300_formula = f"=$B$5*EXP(-$B$6/({KB_FORMULA}*300))"
    # n at 400 K
    n400_formula = f"=$B$5*EXP(-$B$6/({KB_FORMULA}*400))"
    # ratio n(400)/n(300)
    ratio_formula = f"=$B$5*EXP(-$B$6/({KB_FORMULA}*400))/($B$5*EXP(-$B$6/({KB_FORMULA}*300)))"

    summ = [
        ("Arrhenius slope (K)",           slope_formula,  PALETTE["band"]),
        ("n at 300 K (cm⁻³)",             n300_formula,   PALETTE["good"]),
        ("n at 400 K (cm⁻³)",             n400_formula,   PALETTE["good"]),
        ("Ratio n(400K)/n(300K)",          ratio_formula,  PALETTE["warn"]),
        ("Max n in table (cm⁻³)",
            f"=MAX(C{first_data_row}:C{last_data_row})",   PALETTE["band"]),
    ]

    s.col_width(5, 180)
    s.col_width(6, 140)

    for i, (lbl, expr, color) in enumerate(summ):
        r = 4 + i
        s.set(r, 5, lbl)
        s.formula(r, 6, expr)
        s.fmt(r, 5, align="left")
        s.fmt(r, 6, bg=color, align="center", number_format="0.00E+00",
              bold=True)

    s.box(4, 5, 8, 6, color=PALETTE["header"], width=1.2)

    s.note(4, 6,
           "Slope = −(Ec−EF)/(kB·1000). "
           "Measuring this from an Arrhenius plot gives the activation energy.",
           kind="note")

    # ── Chart: ln(n) vs 1000/T ─────────────────────────────────────────
    # Initial render arrays (must match what the formulas evaluate to)
    inv_T_arr = 1000.0 / T_VALS
    n_arr  = NC_DEFAULT * np.exp(-EACT_DEFAULT / (KB * T_VALS))
    ln_n_arr = np.log(n_arr)

    # 0-based data rows for binding: TABLE_START+1 .. TABLE_START+N_ROWS
    row_start_0 = TABLE_START + 1          # first data row (0-based)
    row_end_0   = TABLE_START + N_ROWS     # last  data row (0-based)

    s.chart(
        [Series(
            inv_T_arr, ln_n_arr,
            label="ln(n) vs 1000/T",
            plot_type="Line+Symbol",
            color="#4472c4",
            linewidth=2.0,
            marker="o",
            markersize=5.0,
            x_col=1,   # column B (0-based): 1000/T
            y_col=3,   # column D (0-based): ln(n)
            row_start=row_start_0,
            row_end=row_end_0,
        )],
        at=(560, 30),
        size=(450, 310),
        title="Arrhenius Plot — ln(n) vs 1000/T",
        xlabel="1000/T  (K⁻¹)",
        ylabel="ln(n)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ─────────────────────────────────────────────────
    # mathtext: use \frac (not \tfrac/\dfrac), \mathrm (not \text)
    s.equation(
        r"n(T) = N_c \, \exp\!\left(-\frac{E_c - E_F}{k_B T}\right)"
        r"\quad \Rightarrow \quad"
        r"\ln n = \ln N_c - \frac{E_c - E_F}{k_B} \cdot \frac{1}{T}",
        at=(560, 360),
        fontsize=14,
        color="#111111",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(450, 64),
    )

    s.note(TABLE_START + 1, 3,
           "Higher temperature → exponentially more electrons in the "
           "conduction band (thermal activation).",
           kind="note")

    # ── Save ───────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Carrier Concentration.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
