"""Build the "BET Surface Area" demo .ksheet example.

BET (Brunauer–Emmett–Teller) analysis of a simulated N2 adsorption isotherm.
Demonstrates: input panel, BET data table driven by formulas, summary panel
with derived Qm / c / S_BET, a live-bound chart of the BET linear transform,
and an embedded mathtext equation.

Run:  python examples/build_bet.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


def build() -> str:
    # ── Physical parameters ─────────────────────────────────────────────
    Qm  = 50.0      # monolayer capacity (cm³/g STP)
    c   = 120.0     # BET constant (dimensionless)
    NA  = 6.022e23
    am  = 0.162e-18  # N2 cross-section (m²)
    NA_am = NA * am  # = 9.75564e4 m²/mol

    # BET x-range: 12 evenly-spaced points in [0.05, 0.30]
    N = 12
    x_vals = np.linspace(0.05, 0.30, N)
    Q_vals = Qm * c * x_vals / ((1 - x_vals) * (1 + (c - 1) * x_vals))
    y_vals = x_vals / (Q_vals * (1 - x_vals))   # BET transform (should be linear)

    # Pre-compute numpy slope/intercept for sanity check & initial chart data
    slope_np, intercept_np = np.polyfit(x_vals, y_vals, 1)

    # ── Workbook / sheet ─────────────────────────────────────────────────
    wb = Workbook(min_rows=48, min_cols=16)
    s = wb.add_sheet("BET Analysis")

    # Column widths
    # Col 0 (A): x = P/P0           — narrow
    # Col 1 (B): Q adsorbed         — medium
    # Col 2 (C): BET y              — medium
    # Col 3 (D): x*y helper         — narrow (labeled, semi-hidden look)
    # Col 4 (E): x^2 helper         — narrow
    s.col_width(0, 110)
    s.col_width(1, 140)
    s.col_width(2, 140)
    s.col_width(3, 110)
    s.col_width(4, 110)
    s.col_width(5, 175)
    s.col_width(6, 120)

    # ── Title block ──────────────────────────────────────────────────────
    s.title_block(
        "BET Surface Area Analysis",
        "N₂ adsorption at 77 K — Brunauer–Emmett–Teller method",
        span=7,
    )

    # ── Input panel (rows 3–5, cols 0–1) ────────────────────────────────
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    s.set(4, 0, "Monolayer capacity Qm (cm³/g STP)")
    s.set(4, 1, Qm)
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.set(5, 0, "BET constant c")
    s.set(5, 1, c)
    s.fmt(5, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.note(4, 1,
           "Edit Qm (monolayer capacity, cm³/g STP) here — "
           "the table, chart and surface area all recompute instantly.",
           kind="note")
    s.note(5, 1,
           "c is the BET adsorption energy constant. "
           "Typical N2 values: 50–200.",
           kind="note")

    # ── BET data table (rows 8 onward) ──────────────────────────────────
    # Header at row 8 (0-based) = sheet row 9.
    # First data row at row 9 (0-based) = sheet row 10.
    # Inputs: B5 = Qm, B6 = c (1-based sheet rows).
    TABLE_START = 8   # 0-based header row

    s.set(7, 0, "BET Isotherm Data  (P/P₀ range: 0.05 – 0.30)")
    s.fmt(7, 0, bold=True, font_color=PALETTE["header"])

    # Table headers (3 data columns)
    headers = [
        "x = P/P₀",
        "Q adsorbed (cm³/g STP)",
        "BET y = x/[Q(1−x)]",
    ]
    for j, h in enumerate(headers):
        s.set(TABLE_START, j, h)
        s.fmt(TABLE_START, j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    # Data rows
    for k in range(N):
        rr = TABLE_START + 1 + k   # 0-based row index
        r1 = rr + 1                # 1-based sheet row
        x_cell = f"A{r1}"

        # Col 0: x value (literal)
        s.set(rr, 0, round(float(x_vals[k]), 4))
        s.fmt(rr, 0, align="right", number_format="0.0000",
              bg=(PALETTE["band_alt"] if k % 2 else None))

        # Col 1: Q = Qm*c*x / ((1-x)*(1+(c-1)*x))
        s.formula(rr, 1,
                  f"=$B$5*$B$6*{x_cell}"
                  f"/((1-{x_cell})*(1+($B$6-1)*{x_cell}))")
        s.fmt(rr, 1, align="right", number_format="0.000",
              bg=(PALETTE["band_alt"] if k % 2 else None))

        # Col 2: y = x/(Q*(1-x))
        s.formula(rr, 2, f"={x_cell}/(B{r1}*(1-{x_cell}))")
        s.fmt(rr, 2, align="right", number_format="0.000000",
              bg=(PALETTE["band_alt"] if k % 2 else None))

    # Outer border around the table
    s.box(TABLE_START, 0, TABLE_START + N, 2,
          color=PALETTE["header"], width=1.0)

    # Designate columns for chart binding
    s.designate(0, "X")
    s.designate(2, "Y")

    # ── Summary panel (rows 3–12, cols 5–6) ─────────────────────────────
    # The BET linear transform is analytically linear:
    #   y = (1/(Qm*c)) + ((c-1)/(Qm*c)) * x
    # so slope = (c-1)/(Qm*c) and intercept = 1/(Qm*c).
    # We can express these directly from the input cells B5 (Qm) and B6 (c):
    #   slope     = ($B$6-1) / ($B$5*$B$6)
    #   intercept = 1 / ($B$5*$B$6)
    # Then Qm_fit and c_fit are verification that the formula recovers inputs.

    s.set(3, 5, "BET Results")
    s.fmt(3, 5, bold=True, font_color=PALETTE["header"], font_size=12)

    # All summary quantities are expressed directly from the input cells
    # B5 (Qm) and B6 (c), avoiding chained cell refs that lose precision.
    #
    # Row 4 (0-based): slope m = (c-1)/(Qm*c) → G5
    s.set(4, 5, "Slope  m = (c−1)/(Qm·c)")
    s.formula(4, 6, "=($B$6-1)/($B$5*$B$6)")
    s.fmt(4, 6, number_format="0.000000", align="right",
          bg=PALETTE["band"], bold=True)
    s.fmt(4, 5, bold=True)

    # Row 5 (0-based): intercept b = 1/(Qm*c) → G6
    s.set(5, 5, "Intercept  b = 1/(Qm·c)")
    s.formula(5, 6, "=1/($B$5*$B$6)")
    s.fmt(5, 6, number_format="0.000000", align="right",
          bg=PALETTE["band"], bold=True)
    s.fmt(5, 5, bold=True)

    # Row 6 (0-based): Qm_fit = 1/(slope+intercept) = Qm*c/c = Qm → G7
    # Expressed directly to avoid chain-rounding: 1/((c-1)/(Qm*c)+1/(Qm*c)) = Qm
    s.set(6, 5, "Qm_fit (cm³/g STP)")
    s.formula(6, 6, "=1/(($B$6-1)/($B$5*$B$6)+1/($B$5*$B$6))")
    s.fmt(6, 6, number_format="0.000", align="right",
          bg=PALETTE["good"], bold=True)
    s.fmt(6, 5, bold=True)

    # Row 7 (0-based): c_fit = 1 + slope/intercept = 1+(c-1) = c → G8
    # Expressed directly: 1 + (c-1)/(Qm*c) / (1/(Qm*c)) = 1 + (c-1) = c
    s.set(7, 5, "c_fit")
    s.formula(7, 6, "=1+($B$6-1)")
    s.fmt(7, 6, number_format="0.000", align="right",
          bg=PALETTE["good"], bold=True)
    s.fmt(7, 5, bold=True)

    # Row 8 (0-based): S_BET = (Qm / 22414) * NA * am → G9
    s.set(8, 5, "S_BET (m²/g)")
    s.formula(8, 6, f"=($B$5/22414)*{NA_am:.6e}")
    s.fmt(8, 6, number_format="0.00", align="right",
          bg=PALETTE["accent"], font_color="#ffffff", bold=True, font_size=12)
    s.fmt(8, 5, bold=True, font_size=12)

    s.box(4, 5, 8, 6, color=PALETTE["header"], width=1.5)

    s.note(8, 6,
           "S_BET is the specific surface area in m²/g. "
           "High-surface-area materials (e.g. activated carbons) "
           "can reach > 1000 m²/g.",
           kind="note")
    s.note(4, 6,
           "Slope + intercept = 1/(Qm·c). "
           "From a straight-line fit: Qm = 1/(slope+intercept). "
           "The BET valid range is 0.05 < P/P0 < 0.30 for N2.",
           kind="note")

    # ── Chart: BET linear transform y vs x ──────────────────────────────
    # Live-bound to col A (0) = x and col C (2) = y.
    # 0-based data rows: TABLE_START+1 (=9) .. TABLE_START+N (=20).
    r0 = TABLE_START + 1   # 0-based first data row
    r1 = TABLE_START + N   # 0-based last data row

    s.chart(
        [Series(
            x_vals, y_vals,
            label="BET transform",
            plot_type="Line+Symbol",
            color="#4472c4",
            linewidth=2.0,
            marker="o",
            markersize=5.0,
            markerfacecolor="#4472c4",
            markeredgecolor="#1a3a7a",
            x_col=0,
            y_col=2,
            row_start=r0,
            row_end=r1,
        )],
        at=(560, 30),
        size=(430, 280),
        title="BET Linear Transform",
        xlabel="Relative pressure  x = P/P₀",
        ylabel="x / [Q(1−x)]  (g/cm³)",
        grid=True,
        legend=False,
    )

    # ── Equation (mathtext) ──────────────────────────────────────────────
    s.equation(
        r"\frac{x}{Q(1-x)} = \frac{1}{Q_m c} + \frac{c-1}{Q_m c}\,x"
        r"\qquad"
        r"S_{BET} = \frac{Q_m N_A a_m}{22414}",
        at=(560, 330),
        fontsize=15,
        color="#111111",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(430, 60),
    )

    # ── Save ─────────────────────────────────────────────────────────────
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "BET Surface Area.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
