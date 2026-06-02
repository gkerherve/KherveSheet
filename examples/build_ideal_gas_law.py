"""Build the "Ideal Gas Law" demo .ksheet example.

Demonstrates Boyle's Law (isothermal process): for fixed amount n and
temperature T, pressure P = nRT/V varies inversely with volume V so the
product P*V remains constant (= nRT).

Features shown:
  - Title block, editable input panel (n, T, R, V range)
  - Banded data table with formulas for P and P*V
  - Summary panel (nRT product, min/max P)
  - Live-bound chart: Pressure vs Volume (hyperbolic curve)
  - Two LaTeX equations (PV = nRT and P = nRT/V)
  - Three yellow sticky notes

Run:  python examples/build_ideal_gas_law.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import numpy as np
from ksheet_author import Workbook, Series, PALETTE


# ── Physical constants & default parameters ──────────────────────────
R_GAS = 8.314        # J mol-1 K-1
N_MOL = 1.0          # mol
T_K   = 298.15       # K  (≈ 25 °C, room temperature)
V_MIN = 0.5          # L  (litres)
V_MAX = 10.0         # L
N_PTS = 20           # number of volume steps

# Convert litres → m³ for SI pressure (Pa), then convert Pa → kPa
# P (kPa) = n R T / V  where V in m³  →  V_m3 = V_L * 1e-3
# P_kPa   = n * R * T / (V_L * 1e-3) / 1000


def build() -> str:
    wb = Workbook(min_rows=44, min_cols=14)
    s = wb.add_sheet("Boyle's Law")

    # ── Column widths ────────────────────────────────────────────────
    s.col_width(0, 190)   # label column
    s.col_width(1, 110)   # value column
    s.col_width(3, 160)   # V column
    s.col_width(4, 140)   # P column
    s.col_width(5, 140)   # P*V column
    s.col_width(7, 190)   # summary label
    s.col_width(8, 120)   # summary value

    # ── Title block ──────────────────────────────────────────────────
    s.title_block("Ideal Gas Law — Boyle's Law",
                  "Isothermal process: P·V = nRT = constant  "
                  "(volume in L, pressure in kPa)")

    # ── Input panel ──────────────────────────────────────────────────
    # Cells B5..B9 (0-based: row 4..8, col 1) hold editable inputs.
    # Sheet refs (1-based):  B5=n  B6=T  B7=R  B8=V_start  B9=V_end
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"], font_size=11)

    input_data = [
        ("Amount n  (mol)",           N_MOL),
        ("Temperature T  (K)",        T_K),
        ("Gas constant R  (J/mol·K)", R_GAS),
        ("Volume start  (L)",         V_MIN),
        ("Volume end  (L)",           V_MAX),
    ]
    for i, (lbl, val) in enumerate(input_data):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.000")

    s.box(4, 0, 8, 1, color=PALETTE["accent"], width=1.2)

    s.note(4, 1,
           "Edit n, T, or the volume range — the table and chart "
           "recalculate automatically on open.",
           kind="note")
    s.note(6, 1,
           "R = 8.314 J mol⁻¹ K⁻¹ (universal gas constant). "
           "Keep this fixed for SI units.",
           kind="note")

    # ── Data table ───────────────────────────────────────────────────
    # Volume values are computed by Python (linspace) and written as
    # literals; P and P*V columns use formulas that reference the inputs.
    #
    # Header at sheet row 10 (0-based row 9).
    # First data row at sheet row 11 (0-based row 10).
    # Last data row  at sheet row 30 (0-based row 29).
    #
    # Formula cell refs (1-based):
    #   V column  → D{rr}   (col 3, 0-based)
    #   P formula → =($B$5*$B$6*$B$7)/(D{rr}*0.001)/1000   (kPa)
    #   PV product→ =E{rr}*D{rr}
    #
    # P = n R T / V_m3   where V_m3 = V_L * 0.001
    # P_Pa = n R T / (V_L * 0.001)
    # P_kPa = P_Pa / 1000

    table_start = 9      # 0-based row of header
    vols = np.linspace(V_MIN, V_MAX, N_PTS)

    s.set(8, 3, "Boyle's Law — Pressure vs Volume")
    s.fmt(8, 3, bold=True, font_color=PALETTE["header"], font_size=11)
    s.merge(8, 3, 1, 3)

    rows = []
    for k, v in enumerate(vols):
        rr = table_start + 2 + k   # 1-based sheet row of this data row
        rows.append([
            round(float(v), 4),
            f"=($B$5*$B$6*$B$7)/(D{rr}*0.001)/1000",   # P in kPa  (n*R*T / V_m3 / 1000)
            f"=E{rr}*D{rr}",                             # P*V
        ])

    s.table(table_start, 3,
            headers=["Volume (L)", "Pressure (kPa)", "P·V (kPa·L)"],
            rows=rows, number_format="0.000", banded=True)

    # Designate columns so the app can detect X/Y axes.
    s.designate(3, "X")
    s.designate(4, "Y")

    # ── Summary panel ────────────────────────────────────────────────
    # Placed to the right of the table, starting at row 4.
    # Sheet refs for the table data rows: E11:E30  (P column, 1-based)
    first_data_row = table_start + 2          # = 11  (1-based)
    last_data_row  = table_start + 1 + N_PTS  # = 30  (1-based)

    s.set(3, 7, "Summary")
    s.fmt(3, 7, bold=True, font_color=PALETTE["accent"], font_size=11)

    # nRT in kPa·L: n*R*T [J] = n*R*T [Pa·m³] = n*R*T [kPa·L]
    # (since 1 Pa·m³ = 1 kPa · 0.001 m³ = 1 kPa·L when V is in litres)
    summ_rows = [
        ("nRT  (kPa·L)",   "=$B$5*$B$6*$B$7",                           PALETTE["good"]),
        ("Min pressure (kPa)", f"=MIN(E{first_data_row}:E{last_data_row})", PALETTE["band"]),
        ("Max pressure (kPa)", f"=MAX(E{first_data_row}:E{last_data_row})", PALETTE["band"]),
        ("Min volume (L)",     f"=MIN(D{first_data_row}:D{last_data_row})", PALETTE["band_alt"]),
        ("Max volume (L)",     f"=MAX(D{first_data_row}:D{last_data_row})", PALETTE["band_alt"]),
        ("Mean P·V  (kPa·L)",  f"=AVERAGE(F{first_data_row}:F{last_data_row})", PALETTE["good"]),
    ]
    for i, (lbl, expr, col) in enumerate(summ_rows):
        r = 4 + i
        s.set(r, 7, lbl)
        s.formula(r, 8, expr)
        s.fmt(r, 7, align="left")
        s.fmt(r, 8, bg=col, align="center", number_format="0.000", bold=True)

    s.box(4, 7, 4 + len(summ_rows) - 1, 8,
          color=PALETTE["header"], width=1.2)

    s.note(4, 8,
           "nRT is the constant product for an ideal gas at fixed n and T. "
           "The Mean P·V in the table should match this value.",
           kind="note")

    # ── Chart: Pressure vs Volume (live-bound) ───────────────────────
    # numpy arrays that match what the formulas evaluate to:
    nRT_J   = N_MOL * R_GAS * T_K          # joules = Pa·m³
    P_kPa   = nRT_J / (vols * 1e-3) / 1e3  # kPa

    # 0-based row bounds of the data in the sheet:
    r0 = table_start + 1    # first data row, 0-based (= 10)
    r1 = table_start + N_PTS  # last  data row, 0-based (= 29)

    s.chart(
        [Series(
            x=vols, y=P_kPa,
            label="P vs V (isothermal)",
            plot_type="Line+Symbol",
            color="#4472c4",
            linewidth=2.0,
            marker="o",
            markersize=5.0,
            markerfacecolor="#4472c4",
            markeredgecolor="#ffffff",
            x_col=3,      # Volume column (0-based col D)
            y_col=4,      # Pressure column (0-based col E)
            row_start=r0,
            row_end=r1,
        )],
        at=(620, 30),
        size=(460, 310),
        title="Boyle's Law: P vs V (isothermal)",
        xlabel="Volume (L)",
        ylabel="Pressure (kPa)",
        grid=True,
        legend=True,
        yscale="linear",
    )

    # ── LaTeX equations ──────────────────────────────────────────────
    # Equation 1: PV = nRT  (the ideal gas law)
    s.equation(
        r"PV = nRT",
        at=(620, 360),
        fontsize=22,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(200, 50),
    )

    # Equation 2: P = nRT/V  (Boyle's law rearranged)
    s.equation(
        r"P = \frac{nRT}{V}",
        at=(840, 360),
        fontsize=22,
        color=PALETTE["header"],
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.5,
        size=(200, 50),
    )

    # ── Save ─────────────────────────────────────────────────────────
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Ideal Gas Law.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
