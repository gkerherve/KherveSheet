"""Build the "Tauc Plot Band Gap" demo .ksheet example.

A semiconductor / optical-materials example demonstrating how the
optical band gap is extracted from a Tauc plot.  The absorption
coefficient near the band edge follows:

    alpha(h*nu) = K * sqrt(h*nu - Eg) / (h*nu)   (direct allowed gap, r=1/2)

The Tauc quantity  y = (alpha * h*nu)^2  is linear in h*nu above Eg and
its x-intercept equals Eg.  All derived cells are live formulas.

Run:  python examples/build_tauc.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Make the project importable when run from anywhere.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


def build() -> str:
    # ── Physical parameters (also written as editable literals) ──────
    Eg = 2.0          # band gap (eV)
    K  = 150.0        # absorption prefactor (cm^-1 eV^-0.5)

    # ── Photon-energy grid: fixed literals, 1.0–3.5 eV, 0.1 eV step ─
    hv_vals = np.round(np.arange(1.0, 3.51, 0.1), 2)   # 26 points
    n = len(hv_vals)

    # ── Pre-compute arrays for chart initial render ────────────────────
    alpha_arr = np.where(hv_vals > Eg,
                         K * np.sqrt(np.maximum(hv_vals - Eg, 0.0)) / hv_vals,
                         0.0)
    tauc_arr = (alpha_arr * hv_vals) ** 2

    # ── Workbook / sheet setup ────────────────────────────────────────
    wb = Workbook(min_rows=46, min_cols=14)
    s = wb.add_sheet("Tauc Plot")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block("Tauc Plot Band Gap",
                  "Direct optical band gap extraction from absorption data "
                  "(r = 1/2, direct allowed transition)")

    # ── Input panel ───────────────────────────────────────────────────
    # Eg  → 0-based (row=4, col=1) → spreadsheet B5
    # K   → 0-based (row=5, col=1) → spreadsheet B6
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    s.set(4, 0, "Band gap  Eg  (eV)")
    s.set(4, 1, Eg)
    s.fmt(4, 0, align="left")
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.00",
          bold=True)

    s.set(5, 0, "Prefactor  K  (cm⁻¹ eV⁻¹²)")
    s.set(5, 1, K)
    s.fmt(5, 0, align="left")
    s.fmt(5, 1, bg=PALETTE["warn"], align="center", number_format="0.0",
          bold=True)

    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.2)
    s.col_width(0, 220)
    s.col_width(1, 100)

    s.note(4, 1,
           "Edit Eg (e.g. 1.5, 2.5) — alpha, Tauc column and chart all "
           "recalculate. The extrapolated x-intercept in the summary "
           "should recover Eg.", kind="note")
    s.note(5, 1,
           "K is the absorption prefactor. Larger K = stronger absorption "
           "above the gap. Affects slope but not the extrapolated Eg.",
           kind="note")

    # ── Section label ─────────────────────────────────────────────────
    s.set(7, 0, "Tauc Table  —  (alpha · hν)²  vs  hν")
    s.fmt(7, 0, bold=True, font_color=PALETTE["header"])

    # ── Data table ────────────────────────────────────────────────────
    # table() layout:
    #   start_row = 8  → header at 0-based row 8  (sheet row 9,  1-based)
    #   data row k     → 0-based row (9+k)          (sheet row 10+k, 1-based)
    #
    # Input refs (1-based A1 notation):
    #   Eg  → $B$5   (0-based row 4, col 1  → sheet B5)
    #   K   → $B$6   (0-based row 5, col 1  → sheet B6)
    #
    # Column layout (0-based cols 0..2):
    #   col 0  A  hv (eV)      — literal independent variable
    #   col 1  B  alpha        — formula
    #   col 2  C  Tauc y       — formula

    table_start = 8
    rows = []
    for k, hv in enumerate(hv_vals):
        # 1-based sheet row of this data cell
        rr = table_start + 1 + 1 + k   # = 10 + k

        # alpha formula — MAX clamp prevents POWER of a negative number
        # even when the IF condition is False (both branches are evaluated).
        alpha_formula = (
            f"=IF(A{rr}>$B$5,"
            f"$B$6*POWER(MAX(A{rr}-$B$5,0),0.5)/A{rr},"
            f"0)"
        )
        # Tauc y = (alpha * hv)^2
        tauc_formula = f"=POWER(B{rr}*A{rr},2)"

        rows.append([round(float(hv), 2), alpha_formula, tauc_formula])

    s.table(
        table_start, 0,
        headers=[
            "hν (eV)",
            "α (cm⁻¹)",
            "(α hν)² (cm⁻² eV²)",
        ],
        rows=rows,
        number_format="0.000",
        banded=True,
    )

    # Column designations for axis hints
    s.designate(0, "X")
    s.designate(2, "Y")

    s.col_width(0, 90)
    s.col_width(1, 120)
    s.col_width(2, 155)

    # ── Summary panel ─────────────────────────────────────────────────
    # Uses the last two data rows to compute the linear Tauc slope and
    # extrapolate the x-intercept (= Eg).
    #
    # Last two 1-based rows:
    #   second-last: sheet row 10 + (n-2)  = 10 + 24 = 34  (hv = 3.4 eV)
    #   last:        sheet row 10 + (n-1)  = 10 + 25 = 35  (hv = 3.5 eV)
    row_sl = table_start + 1 + 1 + (n - 2)   # 1-based: 34 (hv=3.4)
    row_la = table_start + 1 + 1 + (n - 1)   # 1-based: 35 (hv=3.5)

    # Slope of Tauc line from last two points (well above Eg=2.0)
    # slope = (C_last - C_slast) / (A_last - A_slast)
    slope_formula  = f"=(C{row_la}-C{row_sl})/(A{row_la}-A{row_sl})"
    # x-intercept: x = x_last - y_last / slope
    xint_formula   = f"=A{row_la}-C{row_la}/((C{row_la}-C{row_sl})/(A{row_la}-A{row_sl}))"

    summ_col_lbl = 4
    summ_col_val = 5
    s.set(8, summ_col_lbl, "Summary")
    s.fmt(8, summ_col_lbl, bold=True, font_color=PALETTE["header"])

    summ_rows = [
        ("Eg input (eV)",           "=$B$5",          PALETTE["warn"]),
        ("Tauc slope (well above)", slope_formula,     PALETTE["band"]),
        ("Extrapolated Eg (eV)",    xint_formula,      PALETTE["good"]),
    ]
    for i, (lbl, expr, col) in enumerate(summ_rows):
        r = 9 + i
        s.set(r, summ_col_lbl, lbl)
        s.formula(r, summ_col_val, expr)
        s.fmt(r, summ_col_lbl, align="left")
        s.fmt(r, summ_col_val, bg=col, align="center",
              number_format="0.0000", bold=True)

    s.box(9, summ_col_lbl, 11, summ_col_val,
          color=PALETTE["header"], width=1.2)
    s.col_width(summ_col_lbl, 180)
    s.col_width(summ_col_val, 100)

    s.note(11, summ_col_val,
           "Extrapolated Eg is computed from the slope of the last two "
           "Tauc data points. It should match the Eg input (cell B5). "
           "Change Eg and verify!", kind="note")

    # ── Chart: Tauc y vs hv — data-bound to the table columns ─────────
    # 0-based rows of the table data: table_start+1 .. table_start+n
    # i.e. rows 9 .. 34  (inclusive).
    r0_chart = table_start + 1          # 0-based first data row = 9
    r1_chart = table_start + n          # 0-based last  data row = 34

    s.chart(
        [
            Series(
                x=hv_vals,
                y=tauc_arr,
                label="(α hν)²",
                plot_type="Line+Symbol",
                color="#4472c4",
                linewidth=2.0,
                marker="o",
                markersize=4.0,
                x_col=0,    # hv column
                y_col=2,    # Tauc y column
                row_start=r0_chart,
                row_end=r1_chart,
            )
        ],
        at=(540, 30),
        size=(440, 310),
        title="Tauc Plot  —  direct band gap",
        xlabel="Photon energy hν (eV)",
        ylabel="(α hν)² (cm⁻² eV²)",
        grid=True,
        legend=True,
    )

    # ── Equation (matplotlib mathtext) ────────────────────────────────
    # Tauc relation for direct gap.
    s.equation(
        r"(\alpha h\nu)^{2} = K^{2}(h\nu - E_{g})",
        at=(540, 360),
        fontsize=19,
        color="#1a1a2e",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(310, 54),
    )
    # Full Tauc-model formula for alpha
    s.equation(
        r"\alpha(h\nu) = \frac{K\sqrt{h\nu - E_{g}}}{h\nu}",
        at=(540, 430),
        fontsize=18,
        color="#1a1a2e",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.2,
        size=(285, 58),
    )

    # ── Note explaining direct vs indirect ────────────────────────────
    s.note(3, 4,
           "Direct allowed gap: exponent r = 1/2, plot (alpha*hv)^2 vs hv.\n"
           "Indirect gap: r = 2, plot (alpha*hv)^0.5 vs hv — a different "
           "linear region extrapolates to Eg.", kind="note")

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Tauc Plot Band Gap.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
