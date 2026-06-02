"""Build the "XRF Moseley Law" demo .ksheet example.

X-ray Fluorescence (XRF) — Moseley's law for K-alpha emission.

Moseley discovered that sqrt(E_Kalpha) is a linear function of atomic
number Z.  The physics: E_Kalpha = R*(Z - sigma)^2 * (1 - 1/4) where R
is the Rydberg energy (~13.6 eV) and sigma is the screening constant.
Simplified: E_Kalpha (keV) = 0.0102 * (Z - sigma)^2.  A plot of
sqrt(E_Kalpha) vs Z is the classic "Moseley plot" — a straight line that
lets you identify elements from their X-ray fluorescence energies.

Features demonstrated
---------------------
* Editable inputs (sigma, Rydberg prefactor in keV) in a styled panel.
* Fixed Z grid (Z=11..42) as literals; E_Kalpha and sqrt(E) as formulas.
* Banded, bordered data table with 32 XRF elements.
* Summary panel with SQRT(E) and energy for key reference elements.
* Live-bound Moseley-plot chart (sqrt(E) vs Z): editing sigma moves
  every point.
* LaTeX mathtext equation block.
* Three instructive yellow notes.

Run:  python examples/build_xrf.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Make the project importable from any working directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402


def build() -> str:
    # ── Physical constants (also used for numpy initial-render arrays) ─
    sigma_val = 1.0        # screening constant (dimensionless)
    R_keV     = 0.0102     # Rydberg prefactor in keV  (= 13.6 eV * 0.75 / 1000)

    # Elements Z = 11 (Na) to Z = 42 (Mo) — the classic XRF working range.
    Z_arr = np.arange(11, 43, dtype=float)   # length 32
    n_elements = len(Z_arr)                  # 32

    # Pre-compute for numpy arrays used ONLY for initial chart render.
    E_arr    = R_keV * (Z_arr - sigma_val) ** 2
    sqrtE_arr = np.sqrt(E_arr)

    # ── Workbook / sheet ──────────────────────────────────────────────
    wb = Workbook(min_rows=50, min_cols=16)
    s  = wb.add_sheet("Moseley Law")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 90)   # Z (atomic number)
    s.col_width(1, 75)   # Element symbol
    s.col_width(2, 120)  # E_Kalpha (keV)
    s.col_width(3, 120)  # SQRT(E_Kalpha)
    s.col_width(5, 190)  # summary labels
    s.col_width(6, 110)  # summary values

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block(
        "XRF Moseley Law",
        "K-alpha X-ray energies via Moseley's law   •   "
        "Elements Z = 11 (Na) to Z = 42 (Mo)",
        span=8,
    )

    # ── Input panel ───────────────────────────────────────────────────
    # Input cell positions (0-based):
    #   sigma  → row 4, col 1  → sheet cell B5
    #   R_keV  → row 5, col 1  → sheet cell B6
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    s.set(4, 0, "Screening constant  σ")
    s.set(4, 1, sigma_val)
    s.fmt(4, 0, align="left")
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.000",
          bold=True)

    s.set(5, 0, "Rydberg prefactor  R (keV)")
    s.set(5, 1, R_keV)
    s.fmt(5, 0, align="left")
    s.fmt(5, 1, bg=PALETTE["warn"], align="center", number_format="0.0000",
          bold=True)

    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.5)

    s.note(4, 1,
           "Edit sigma (screening constant, default 1.0). "
           "Every E_Kalpha and sqrt(E) cell recalculates, "
           "and the Moseley chart updates instantly.",
           kind="note")
    s.note(5, 1,
           "R = 0.0102 keV = 13.6 eV × 0.75 / 1000 is the "
           "Rydberg energy times the K-alpha transition factor. "
           "Change it to explore alternative calibrations.",
           kind="note")

    # ── Element-symbol lookup helper (col 1 of table) ─────────────────
    # Written as literals in column B of the table — they are labels, not
    # computed values, so literals are correct here.
    _SYMBOLS = [
        "Na", "Mg", "Al", "Si", "P",  "S",  "Cl", "Ar",
        "K",  "Ca", "Sc", "Ti", "V",  "Cr", "Mn", "Fe",
        "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se",
        "Br", "Kr", "Rb", "Sr", "Y",  "Zr", "Nb", "Mo",
    ]

    # ── Data table ────────────────────────────────────────────────────
    # Layout: col 0=Z, col 1=Symbol, col 2=E_Kalpha (keV), col 3=sqrt(E)
    #
    # table() places header at (table_start, *) — sheet row table_start+1.
    # First data row is table_start+1+1 = table_start+2 in 0-based,
    # which is sheet row (table_start+2)+1 = table_start+3 in 1-based.
    #
    # Wait — the table() API: header is at row=start_row (0-based),
    # first data row is at row=start_row+1 (0-based).
    # Sheet row (1-based) = 0-based row + 1.
    # So data row i (0-indexed within data) → 0-based row = table_start+1+i
    #                                       → sheet row   = table_start+2+i
    table_start = 8   # 0-based; header lands at sheet row 9 (1-based)

    rows = []
    for i, Z in enumerate(Z_arr):
        # 0-based row of this data cell = table_start + 1 + i
        # 1-based sheet row             = table_start + 2 + i
        rr = table_start + 2 + i          # 1-based sheet row for formula refs
        col_e   = "C"                     # E_Kalpha column (col index 2 → letter C)
        Z_cell  = f"A{rr}"               # atomic number cell in this row
        rows.append([
            int(Z),
            _SYMBOLS[i],
            f"=$B$6*({Z_cell}-$B$5)^2",           # E_Kalpha (keV)
            f"=SQRT({col_e}{rr})",                 # sqrt(E_Kalpha)
        ])

    s.set(7, 0, "K-alpha XRF data table")
    s.fmt(7, 0, bold=True, font_color=PALETTE["header"])

    s.table(
        table_start, 0,
        headers=["Z", "Element", "E_Kα (keV)", "√E_Kα  (keV^½)"],
        rows=rows,
        banded=True,
    )

    # Override: first two columns (Z, Symbol) stay left-aligned;
    # the numeric columns right-aligned with number_format.
    n_rows_data = n_elements
    for i in range(n_rows_data):
        r0 = table_start + 1 + i
        s.fmt(r0, 0, align="center", number_format="0")
        s.fmt(r0, 1, align="center")
        s.fmt(r0, 2, align="right", number_format="0.0000")
        s.fmt(r0, 3, align="right", number_format="0.0000")

    # ── Designate axes for the chart ──────────────────────────────────
    s.designate(0, "X")   # Z column
    s.designate(3, "Y")   # sqrt(E) column

    # ── Summary panel ─────────────────────────────────────────────────
    # Located to the right of the table (columns 5–6), rows 4–12.
    # References formulas in the E_Kalpha table.

    # Identify 1-based sheet rows for key elements:
    #   Fe = Z=26 → index 15 (0-based in Z_arr) → data row i=15
    #       → sheet row = table_start + 2 + 15 = 8+2+15 = 25
    #   Cu = Z=29 → index 18 → sheet row = 8+2+18 = 28
    #   Mo = Z=42 → index 31 → sheet row = 8+2+31 = 41

    sr_fe = table_start + 2 + 15   # sheet row for Fe (Z=26)
    sr_cu = table_start + 2 + 18   # sheet row for Cu (Z=29)
    sr_mo = table_start + 2 + 31   # sheet row for Mo (Z=42)

    # Moseley slope = sqrt(R_keV)  →  a formula referencing the input cell
    # SQRT(B6) gives sqrt of the prefactor which equals the slope k.

    s.set(3, 5, "Key Reference Values")
    s.fmt(3, 5, bold=True, font_color=PALETTE["header"])

    # Summary rows: (label, formula, bg colour)
    summ = [
        ("Fe (Z=26)  E_Kα (keV)",  f"=C{sr_fe}",         PALETTE["band"]),
        ("Fe (Z=26)  √E_Kα",       f"=D{sr_fe}",         PALETTE["band"]),
        ("Cu (Z=29)  E_Kα (keV)",  f"=C{sr_cu}",         PALETTE["band_alt"]),
        ("Cu (Z=29)  √E_Kα",       f"=D{sr_cu}",         PALETTE["band_alt"]),
        ("Mo (Z=42)  E_Kα (keV)",  f"=C{sr_mo}",         PALETTE["band"]),
        ("Mo (Z=42)  √E_Kα",       f"=D{sr_mo}",         PALETTE["band"]),
        ("Moseley slope k",         "=SQRT($B$6)",        PALETTE["good"]),
        ("Max E_Kα in table (keV)",
         f"=MAX(C{table_start+2}:C{table_start+1+n_elements})",
         PALETTE["good"]),
        ("Min E_Kα in table (keV)",
         f"=MIN(C{table_start+2}:C{table_start+1+n_elements})",
         PALETTE["good"]),
    ]

    for i, (lbl, expr, bg) in enumerate(summ):
        r = 4 + i
        s.set(r, 5, lbl)
        s.formula(r, 6, expr)
        s.fmt(r, 5, align="left")
        s.fmt(r, 6, bg=bg, align="right", number_format="0.0000", bold=True)

    s.box(4, 5, 4 + len(summ) - 1, 6,
          color=PALETTE["header"], width=1.5)

    # ── Third note — XRF technique ─────────────────────────────────────
    s.note(3, 5,
           "XRF is a non-destructive elemental analysis technique. "
           "Each element emits characteristic X-rays when excited "
           "by a primary X-ray beam — energies measured here via "
           "Moseley's empirical law.",
           kind="note")

    # ── Chart: Moseley plot (sqrt(E) vs Z) ────────────────────────────
    # Data rows occupy 0-based rows table_start+1 .. table_start+n_elements.
    # col 0 = Z (X), col 3 = sqrt(E) (Y).
    r0_chart = table_start + 1               # 0-based first data row
    r1_chart = table_start + n_elements      # 0-based last data row

    s.chart(
        [Series(
            x=Z_arr,
            y=sqrtE_arr,
            label="√E_Kα vs Z",
            plot_type="Line+Symbol",
            color="#4472c4",
            linewidth=2.0,
            marker="o",
            markersize=5.0,
            markerfacecolor="#4472c4",
            markeredgecolor="#2255aa",
            x_col=0,
            y_col=3,
            row_start=r0_chart,
            row_end=r1_chart,
        )],
        at=(560, 30),
        size=(460, 320),
        title="Moseley Plot: √E_Kα vs Atomic Number Z",
        xlabel="Atomic number Z",
        ylabel="√E_Kα  (keV^½)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    # mathtext: \sqrt, \sigma, \alpha, \mathrm, \frac — all valid.
    s.equation(
        r"\sqrt{E_{K\alpha}} = \sqrt{R} \,(Z - \sigma)"
        r"\quad \Rightarrow \quad"
        r"E_{K\alpha} = 0.0102\,(Z - 1)^{2}\ \mathrm{keV}",
        at=(560, 370),
        fontsize=16,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(460, 56),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(_HERE, "XRF Moseley Law.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
