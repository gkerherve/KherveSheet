"""Build the "Spin-Orbit Coupling" demo .ksheet example.

XPS Doublets — Surface Science.

Spin-orbit coupling splits a core level (l > 0) into j = l-1/2 and
j = l+1/2, separated by Delta_SO, with intensity ratio
(2j_low+1):(2j_high+1).  For a p level (l=1): j=1/2 (p1/2) and
j=3/2 (p3/2) → area ratio 2:4 = 1:2.

Run:  python examples/build_spin_orbit.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import numpy as np
from ksheet_author import Workbook, Series, PALETTE

# ─── Physics defaults ────────────────────────────────────────────────
BE0 = 284.0      # p3/2 binding energy (eV)  — C 1s-like for illustration
DELTA_SO = 6.0   # spin-orbit splitting (eV)  — p level
FWHM = 1.2       # Gaussian full-width at half-maximum (eV)
AMP = 1000.0     # amplitude of p3/2 peak (counts)
BRANCH = 0.5     # branching ratio = A_low / A_high (= 1/2 for p)

# BE grid: 50 evenly-spaced points spanning the doublet + margins
N = 50
BE_MIN = BE0 - 4.0
BE_MAX = BE0 + DELTA_SO + 4.0
be_arr = np.linspace(BE_MIN, BE_MAX, N)

# ─── Gaussian helper ─────────────────────────────────────────────────
def gauss(be, centre, amp, fwhm):
    return amp * np.exp(-4 * np.log(2) * ((be - centre) / fwhm) ** 2)

# Pre-compute arrays for the chart's initial render
y_p32 = gauss(be_arr, BE0, AMP, FWHM)
y_p12 = gauss(be_arr, BE0 + DELTA_SO, AMP * BRANCH, FWHM)
BG = 50.0        # flat background (built into the total)
y_tot = BG + y_p32 + y_p12


def build() -> str:
    wb = Workbook(min_rows=60, min_cols=14)
    s = wb.add_sheet("XPS Doublet")

    # ── Title ────────────────────────────────────────────────────────
    s.title_block(
        "Spin-Orbit Coupling — XPS Doublet Simulation",
        "Core-level photoemission: p doublet (p3/2 and p1/2) modelled as Gaussians",
        span=8,
    )

    # ── Input panel ──────────────────────────────────────────────────
    s.set(3, 0, "Editable inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("BE₀ — p3/2 binding energy (eV)", BE0),
        ("Delta_SO — spin-orbit splitting (eV)", DELTA_SO),
        ("FWHM (eV)", FWHM),
        ("Amplitude A (counts)", AMP),
        ("Branching ratio (A_p1/2 / A_p3/2)", BRANCH),
        ("Background (flat, counts)", BG),
    ]
    # Rows 4-9, cols 0-1  →  sheet rows B5:B10
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(4, 0, 9, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 240)
    s.col_width(1, 100)

    # ── Summary panel ────────────────────────────────────────────────
    # Input cell references (1-based): B5=BE0, B6=Delta_SO, B7=FWHM,
    # B8=Amplitude, B9=branching ratio, B10=background
    s.set(3, 3, "Summary")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"])

    summary_items = [
        ("p3/2 position (eV)",  "=$B$5"),
        ("p1/2 position (eV)",  "=$B$5+$B$6"),
        ("Splitting Delta_SO",  "=$B$6"),
        ("Area ratio p1/2:p3/2", "=$B$9"),
    ]
    for i, (lbl, expr) in enumerate(summary_items):
        r = 4 + i
        s.set(r, 3, lbl)
        s.formula(r, 4, expr)
        s.fmt(r, 3, align="left")
        s.fmt(r, 4, bg=PALETTE["band"], align="center",
              number_format="0.000", bold=True)
    s.box(4, 3, 7, 4, color=PALETTE["header"], width=1.0)
    s.col_width(3, 200)
    s.col_width(4, 100)

    # ── Data table ───────────────────────────────────────────────────
    # Table starts at row 11 (0-based).
    # Header occupies 0-based row 11 → sheet row 12.
    # First data row is 0-based row 12 → sheet row 13.
    TABLE_START = 11
    FIRST_DATA_SHEET_ROW = TABLE_START + 2   # = 13 (1-based sheet row)

    s.set(10, 0, "Spectral data table  (BE values are fixed; all other columns are live formulas)")
    s.fmt(10, 0, bold=True, font_color=PALETTE["header"])
    s.merge(10, 0, 1, 5)

    # Designate column roles for chart auto-detection
    s.designate(0, "X")
    s.designate(1, "Y")
    s.designate(2, "Y")
    s.designate(3, "Y")

    col_widths_data = [80, 100, 100, 100]
    for ci, w in enumerate(col_widths_data):
        s.col_width(ci, w)

    rows = []
    for k in range(N):
        be_val = float(be_arr[k])
        # 1-based sheet row of this data row
        sheet_row = FIRST_DATA_SHEET_ROW + k
        # Column letters: A=BE, B=p3/2, C=p1/2, D=Total
        # Gaussian formula: A*EXP(-4*LN(2)*((BE-centre)/FWHM)^2)
        # $B$5 = BE0, $B$6 = Delta_SO, $B$7 = FWHM
        # $B$8 = Amplitude, $B$9 = branching ratio, $B$10 = background
        f_p32 = (
            f"=$B$8*EXP(-4*LN(2)*((A{sheet_row}-$B$5)/$B$7)^2)"
        )
        f_p12 = (
            f"=$B$8*$B$9*EXP(-4*LN(2)*((A{sheet_row}-($B$5+$B$6))/$B$7)^2)"
        )
        f_tot = f"=$B$10+B{sheet_row}+C{sheet_row}"

        rows.append([round(be_val, 4), f_p32, f_p12, f_tot])

    s.table(
        TABLE_START, 0,
        headers=["BE (eV)", "p3/2 peak", "p1/2 peak", "Total"],
        rows=rows,
        number_format="0.0",
        banded=True,
    )
    # Override first column (BE) to be right-aligned with 3 dp
    for k in range(N):
        s.fmt(TABLE_START + 1 + k, 0, align="right", number_format="0.000")

    # ── Chart ────────────────────────────────────────────────────────
    # Bind to 0-based rows: TABLE_START+1 .. TABLE_START+N (inclusive)
    r0_bind = TABLE_START + 1
    r1_bind = TABLE_START + N

    # X col = 0 (BE), Y cols = 1 (p3/2), 2 (p1/2), 3 (total)
    s.chart(
        [
            Series(
                be_arr, y_tot, "Total", "Line",
                color="#1f1f1f", linewidth=2.0,
                x_col=0, y_col=3, row_start=r0_bind, row_end=r1_bind,
            ),
            Series(
                be_arr, y_p32, "p3/2", "Line",
                color="#4472c4", linewidth=1.5, linestyle="--",
                x_col=0, y_col=1, row_start=r0_bind, row_end=r1_bind,
            ),
            Series(
                be_arr, y_p12, "p1/2", "Line",
                color="#ed7d31", linewidth=1.5, linestyle="--",
                x_col=0, y_col=2, row_start=r0_bind, row_end=r1_bind,
            ),
        ],
        at=(540, 30), size=(460, 320),
        title="XPS Doublet — Spin-Orbit Split Core Level",
        xlabel="Binding Energy (eV)",
        ylabel="Intensity (counts)",
        grid=True, legend=True,
    )

    # ── Equations ────────────────────────────────────────────────────
    # Degeneracy ratio
    s.equation(
        r"\frac{I_{j_1}}{I_{j_2}} = \frac{2j_1+1}{2j_2+1}",
        at=(540, 365), fontsize=18,
        color="#222222", bg_color="#ffffff",
        border_color=PALETTE["header"], border_width=1.2,
        size=(260, 58),
    )
    # Gaussian lineshape
    s.equation(
        r"G(E) = A \exp\!\left(-4\ln 2 \cdot \frac{(E - E_0)^2}{w^2}\right)",
        at=(540, 438), fontsize=16,
        color="#222222", bg_color="#ffffff",
        border_color=PALETTE["accent"], border_width=1.2,
        size=(400, 58),
    )

    # ── Notes ────────────────────────────────────────────────────────
    s.note(
        4, 0,
        "Origin of splitting: relativistic spin-orbit interaction couples "
        "the electron spin (s=1/2) to the orbital angular momentum (l), "
        "lifting the degeneracy of the l>0 core levels into j=l-1/2 and "
        "j=l+1/2 components. The splitting Delta_SO increases strongly "
        "with atomic number Z (heavier elements show larger splittings).",
        kind="note",
    )
    s.note(
        6, 0,
        "Branching ratios (area ratio low-j : high-j) from degeneracy "
        "(2j+1):\n"
        "  p level (l=1): p1/2 : p3/2 = 2 : 4 = 1 : 2  (ratio = 0.5)\n"
        "  d level (l=2): d3/2 : d5/2 = 4 : 6 = 2 : 3  (ratio = 0.667)\n"
        "  f level (l=3): f5/2 : f7/2 = 6 : 8 = 3 : 4  (ratio = 0.75)\n"
        "Edit B9 to explore other orbital symmetries.",
        kind="note",
    )
    s.note(
        10, 0,
        "Edit the yellow input cells (B5-B10) — the entire table, summary "
        "panel and chart update automatically via live formulas. Try "
        "increasing Delta_SO (B6) to see the doublet separation grow.",
        kind="note",
    )

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Spin-Orbit Coupling.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
