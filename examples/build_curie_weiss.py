"""Build the "Curie-Weiss Law" demo .ksheet example.

Paramagnetic susceptibility above the ordering temperature follows
chi(T) = C / (T - theta).  A plot of 1/chi vs T is a straight line
with x-intercept theta and slope 1/C.

Run:  python examples/build_curie_weiss.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os

import numpy as np

from ksheet_author import Workbook, Series, PALETTE


def build() -> str:
    # ------------------------------------------------------------------ #
    # Physical parameters (used only for the initial numpy render arrays) #
    # ------------------------------------------------------------------ #
    C_val = 0.5      # Curie constant (emu·K/mol)
    theta_val = 50.0  # Weiss temperature (K)  >0 → ferromagnet

    # Temperature grid: fixed literals, guaranteed > theta so no div/0.
    # Start at 60 K (10 K above the default theta=50 K), step 10 K to 400 K.
    T_arr = np.arange(60.0, 401.0, 10.0)   # 35 points
    n = len(T_arr)

    chi_arr = C_val / (T_arr - theta_val)
    inv_chi_arr = (T_arr - theta_val) / C_val

    # ------------------------------------------------------------------ #
    # Workbook / sheet                                                     #
    # ------------------------------------------------------------------ #
    wb = Workbook(min_rows=50, min_cols=14)
    s = wb.add_sheet("Curie-Weiss")

    # ------------------------------------------------------------------ #
    # Title block                                                          #
    # ------------------------------------------------------------------ #
    s.title_block(
        "Curie-Weiss Law",
        "Paramagnetic susceptibility  χ(T) = C / (T − θ)  "
        "above the magnetic ordering temperature",
        span=8,
    )

    # ------------------------------------------------------------------ #
    # Input panel  (editable literals — rows 3..4, cols 0..1)             #
    # B4 = C (row 3, col 1)                                               #
    # B5 = theta (row 4, col 1)                                           #
    # Spreadsheet 1-based: row 3 → sheet row 4, row 4 → sheet row 5      #
    # ------------------------------------------------------------------ #
    s.set(2, 0, "Inputs")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    s.set(3, 0, "Curie constant C (emu·K/mol)")
    s.set(3, 1, C_val)
    s.fmt(3, 0, align="left")
    s.fmt(3, 1, bg=PALETTE["warn"], align="center", number_format="0.000")

    s.set(4, 0, "Weiss temperature θ (K)")
    s.set(4, 1, theta_val)
    s.fmt(4, 0, align="left")
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.0")

    s.box(3, 0, 4, 1, color=PALETTE["accent"], width=1.2)
    s.col_width(0, 220)
    s.col_width(1, 110)

    # Input cells in 1-based A1 notation:
    #   C  → B4   (row index 3, col index 1)
    #   theta → B5 (row index 4, col index 1)
    C_ref    = "$B$4"   # absolute ref to Curie constant
    theta_ref = "$B$5"  # absolute ref to Weiss temperature

    # ------------------------------------------------------------------ #
    # Yellow sticky notes on inputs                                        #
    # ------------------------------------------------------------------ #
    s.note(3, 1,
           "Edit C here. Larger C → steeper 1/χ curve (1/C is the slope).",
           kind="note")
    s.note(4, 1,
           "θ > 0: ferromagnet (positive intercept).\n"
           "θ < 0: antiferromagnet (negative intercept).\n"
           "θ = 0: ideal paramagnet (Curie law).\n"
           "Keep θ below 60 K so T > θ everywhere.",
           kind="note")

    # ------------------------------------------------------------------ #
    # Data table                                                           #
    # Columns: A=T(K)  B=chi  C=1/chi                                    #
    # table() header is at row table_start (0-based),                     #
    # first data row is at table_start+1 (0-based) = sheet row            #
    # table_start+2 (1-based).                                            #
    # ------------------------------------------------------------------ #
    table_start = 7   # 0-based row index of the header row

    s.set(6, 0, "Temperature sweep (T grid is fixed; edit C and θ above)")
    s.fmt(6, 0, bold=True, font_color=PALETTE["header"])
    s.merge(6, 0, 1, 4)

    rows = []
    for k, T in enumerate(T_arr):
        # 1-based sheet row of this data row:
        rr = table_start + 2 + k   # header at table_start+1, data from +2
        col_A = f"A{rr}"            # temperature cell in this row
        rows.append([
            float(T),                                          # col A: literal T
            f"={C_ref}/({col_A}-{theta_ref})",                 # col B: chi
            f"=({col_A}-{theta_ref})/{C_ref}",                 # col C: 1/chi
        ])

    s.table(
        table_start, 0,
        headers=["T (K)", "χ (emu/mol)", "1/χ (mol/emu)"],
        rows=rows,
        number_format="0.0000",
        banded=True,
    )

    # Designate columns for chart axis hints (0-based col indices).
    s.designate(0, "X")   # col A = T
    s.designate(1, "Y")   # col B = chi
    s.designate(2, "Y")   # col C = 1/chi

    s.col_width(2, 130)

    # ------------------------------------------------------------------ #
    # Summary panel  (cols 4..5, rows 3..8)                               #
    # All cells are formulas referencing the table or inputs.             #
    # ------------------------------------------------------------------ #
    # 1-based sheet row of the first and last data rows:
    first_data_row_1based = table_start + 2         # = 9
    last_data_row_1based  = table_start + 1 + n     # = 43

    # chi at 300 K: find the row where T=300.
    # T grid starts at 60, step 10 → index of T=300 is (300-60)/10 = 24
    # 0-based row in table: table_start+1+24 → 1-based sheet row = 33
    row_300_1based = table_start + 2 + int((300.0 - 60.0) / 10.0)  # = 32

    s.set(2, 4, "Summary")
    s.fmt(2, 4, bold=True, font_color=PALETTE["header"])

    summary_items = [
        # (label, formula, bg)
        ("Weiss temp θ (K)",       f"={theta_ref}",          PALETTE["band"]),
        ("Curie const C",               f"={C_ref}",               PALETTE["band"]),
        ("χ at 300 K (emu/mol)",   f"=B{row_300_1based}",    PALETTE["good"]),
        ("1/C (slope of 1/χ vs T)",f"=1/{C_ref}",            PALETTE["band"]),
        ("Min χ in range",         f"=MIN(B{first_data_row_1based}:B{last_data_row_1based})", PALETTE["band_alt"]),
        ("Max χ in range",         f"=MAX(B{first_data_row_1based}:B{last_data_row_1based})", PALETTE["band_alt"]),
        ("Ordering type",
         f"=IF({theta_ref}>0,\"Ferromagnet\",IF({theta_ref}<0,\"Antiferromagnet\",\"Paramagnet\"))",
         PALETTE["warn"]),
    ]

    for i, (lbl, expr, bg) in enumerate(summary_items):
        r = 3 + i
        s.set(r, 4, lbl)
        s.formula(r, 5, expr)
        s.fmt(r, 4, align="left")
        s.fmt(r, 5, bg=bg, align="center", number_format="0.0000", bold=True)

    # Ordering-type cell is text — override number_format to General.
    s.fmt(3 + 6, 5, number_format="General")

    s.box(3, 4, 3 + len(summary_items) - 1, 5,
          color=PALETTE["header"], width=1.2)
    s.col_width(4, 190)
    s.col_width(5, 140)

    # Note on the 1/chi linearity
    s.note(3 + 2, 4,
           "1/χ vs T is a straight line: slope = 1/C, "
           "x-intercept = θ. Edit θ to watch the intercept shift.",
           kind="note")

    # Note on validity range
    s.note(3 + 4, 4,
           "The Curie-Weiss law is valid only well above the ordering\n"
           "temperature Tc (or TN). Below Tc the formula diverges.",
           kind="note")

    # ------------------------------------------------------------------ #
    # Chart: 1/chi vs T  (live-bound to col 0=T, col 2=1/chi)            #
    # 0-based data rows: table_start+1 .. table_start+n                  #
    # ------------------------------------------------------------------ #
    r0 = table_start + 1          # 0-based index of first data row
    r1 = table_start + n          # 0-based index of last data row

    s.chart(
        [Series(
            T_arr, inv_chi_arr,
            label="1/χ vs T",
            plot_type="Line+Symbol",
            color="#4472c4",
            linewidth=2.0,
            marker="o",
            markersize=4.0,
            x_col=0,   # col A = T
            y_col=2,   # col C = 1/chi
            row_start=r0,
            row_end=r1,
        )],
        at=(490, 40),
        size=(460, 310),
        title="Curie-Weiss Plot: 1/χ vs T",
        xlabel="Temperature T (K)",
        ylabel="1/χ (mol/emu)",
        grid=True,
        legend=True,
    )

    # ------------------------------------------------------------------ #
    # LaTeX equation (mathtext: \frac, \chi, \theta)                      #
    # ------------------------------------------------------------------ #
    s.equation(
        r"\chi(T) = \frac{C}{T - \theta}",
        at=(490, 370),
        fontsize=22,
        color="#1a1a2e",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(280, 58),
    )

    # ------------------------------------------------------------------ #
    # Save                                                                 #
    # ------------------------------------------------------------------ #
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Curie-Weiss Law.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
