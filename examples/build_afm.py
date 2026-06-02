"""Build the "AFM Force-Distance" demo .ksheet example.

Atomic Force Microscopy (AFM) — tip–sample Lennard-Jones interaction
and cantilever Hooke deflection.  A worked materials-science example
showing a rich, formula-driven sheet with an interactive chart.

Physics implemented:
    F(z) = (12·ε/σ) · [(σ/z)^13 − (σ/z)^7]   (Lennard-Jones force, nN)
    d    = F / k                                (Hooke deflection, nm)

Run:  python examples/build_afm.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import numpy as np

from ksheet_author import Workbook, Series, PALETTE


def build() -> str:
    # ── Physical defaults (written as literals into input cells) ──────
    epsilon = 1.0      # well depth (nN·nm)
    sigma   = 0.3      # equilibrium separation (nm)
    k       = 0.5      # cantilever spring constant (nN/nm = N/m)

    # ── Independent variable grid — fixed literals ────────────────────
    n   = 40
    z   = np.linspace(0.25, 1.20, n)   # separation (nm), avoids z=0

    # ── Pre-compute numpy arrays for chart initial render ─────────────
    # Must match what the formulas evaluate to exactly.
    F_np = (12 * epsilon / sigma) * ((sigma / z) ** 13 - (sigma / z) ** 7)
    d_np = F_np / k

    # ── Workbook / sheet setup ────────────────────────────────────────
    wb = Workbook(min_rows=52, min_cols=14)
    s = wb.add_sheet("AFM Force-Distance")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "AFM Force-Distance Curve",
        "Lennard-Jones tip–sample interaction and cantilever deflection"
    )
    s.col_width(0, 180)   # z / label column

    # ── Input panel ───────────────────────────────────────────────────
    # Inputs occupy B5, B6, B7  (0-based: row 4,col 1 / row 5,col 1 / row 6,col 1)
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    input_rows = [
        ("ε  –  well depth (nN·nm)", epsilon),
        ("σ  –  equilibrium sep. (nm)", sigma),
        ("k  –  spring constant (nN/nm)", k),
    ]
    for i, (lbl, val) in enumerate(input_rows):
        r = 4 + i          # 0-based rows 4,5,6
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.000")
    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.2)
    s.col_width(1, 110)

    # Instructional notes
    s.note(4, 1,
           "Edit ε (well depth, nN·nm) — controls interaction strength. "
           "The force curve, deflection column and chart all recalculate.",
           kind="note")
    s.note(6, 1,
           "k is the cantilever spring constant (nN/nm = N/m). "
           "A stiffer cantilever (larger k) gives smaller deflection d = F/k.",
           kind="note")

    # ── Summary panel (formulas, not literals) ─────────────────────────
    # Table occupies 0-based rows 9..9+n (header=9, data rows 10..9+n).
    # Sheet refs: z column = A, 1-based rows data_row_1 = 10+1=11, data_row_last = 9+n+1 = 50.
    table_start   = 9
    data_row_1    = table_start + 1 + 1   # 1-based first data row = 11
    data_row_last = table_start + 1 + n   # 1-based last  data row = 50

    # Equilibrium separation: z_eq = 2^(1/6) * sigma
    # In formula: =POWER(2,1/6)*$B$6
    s.set(3, 3, "Summary")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"])

    summary = [
        ("Equilibrium z_eq (nm)",
         f"=POWER(2,1/6)*$B$6",
         PALETTE["band"]),
        ("Min force – repulsive peak (nN)",
         f"=MIN(B{data_row_1}:B{data_row_last})",
         PALETTE["bad"]),
        ("Max attractive force (nN)",
         f"=MAX(B{data_row_1}:B{data_row_last})",
         PALETTE["good"]),
        ("Deflection at min force (nm)",
         f"=MIN(C{data_row_1}:C{data_row_last})",
         PALETTE["band"]),
    ]
    for i, (lbl, expr, col) in enumerate(summary):
        r = 4 + i
        s.set(r, 3, lbl)
        s.formula(r, 4, expr)
        s.fmt(r, 3, align="left")
        s.fmt(r, 4, bg=col, align="center", number_format="0.0000", bold=True)
    s.box(4, 3, 7, 4, color=PALETTE["header"], width=1.2)
    s.col_width(3, 200)
    s.col_width(4, 110)

    # Note on equilibrium
    s.note(4, 4,
           "Equilibrium where F=0 (net force = 0): z_eq = 2^(1/6)·σ ≈ 1.122·σ. "
           "Above z_eq the force is attractive; below z_eq it is repulsive.",
           kind="note")

    # ── Data table ────────────────────────────────────────────────────
    # Columns: A=z (literal), B=F (formula), C=d (formula)
    # table_start=9 → header at 0-based row 9 = sheet row 10
    #               → first data at 0-based row 10 = sheet row 11
    s.set(8, 0, "Force-Distance Data")
    s.fmt(8, 0, bold=True, font_color=PALETTE["header"])

    rows = []
    for idx, z_val in enumerate(z):
        rr = table_start + 2 + idx   # 1-based sheet row of this data row
        rows.append([
            round(float(z_val), 4),           # col A: literal z (nm)
            # col B: F(z) = (12*eps/sig)*[(sig/z)^13 - (sig/z)^7]  (nN)
            f"=(12*$B$5/$B$6)*(POWER($B$6/A{rr},13)-POWER($B$6/A{rr},7))",
            # col C: d = F/k  (nm)
            f"=B{rr}/$B$7",
        ])

    s.table(
        table_start, 0,
        headers=["z (nm)", "F (nN)", "d (nm)"],
        rows=rows,
        number_format="0.0000",
    )

    # Designate columns for axis hints
    s.designate(0, "X")
    s.designate(1, "Y")
    s.designate(2, "Y")

    # ── Chart: Force vs separation (live-bound) ───────────────────────
    # Data occupies 0-based rows table_start+1 .. table_start+n  (i.e. 10..49).
    r0 = table_start + 1      # 0-based, inclusive start
    r1 = table_start + n      # 0-based, inclusive end

    s.chart(
        [Series(
            z, F_np,
            label="LJ Force F(z)",
            plot_type="Line+Symbol",
            color="#4472c4",
            linewidth=2.0,
            marker="o",
            markersize=3.5,
            markerfacecolor="#4472c4",
            markeredgecolor="#2f528f",
            x_col=0,   # column A
            y_col=1,   # column B
            row_start=r0,
            row_end=r1,
        )],
        at=(520, 30),
        size=(460, 320),
        title="AFM Force-Distance Curve",
        xlabel="Tip-sample separation  z  (nm)",
        ylabel="Force  F  (nN)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ─────────────────────────────────────────────────
    # mathtext: \frac (not \tfrac), no \left/\right (not supported in mathtext)
    latex = (
        r"F(z) = \frac{12\epsilon}{\sigma}"
        r"\left[\left(\frac{\sigma}{z}\right)^{13}"
        r" - \left(\frac{\sigma}{z}\right)^{7}\right]"
    )
    s.equation(
        latex,
        at=(520, 370),
        fontsize=17,
        color="#1a1a2e",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(400, 56),
    )

    # ── Regime note ───────────────────────────────────────────────────
    s.note(8, 3,
           "Repulsive regime: z < z_eq (tip pushed away, F > 0). "
           "Attractive regime: z > z_eq (van-der-Waals pull, F < 0). "
           "Edit σ to shift the equilibrium left or right.",
           kind="note")

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "AFM Force-Distance.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
