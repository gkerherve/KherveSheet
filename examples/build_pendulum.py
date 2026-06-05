"""Build the "Simple Pendulum" worked example.

Small-angle period  T = 2*pi*sqrt(L/g).  Squaring gives the linear
relation  T^2 = (4*pi^2/g) * L, whose slope yields a measurement of g.
Editable inputs: pendulum length L and gravity g.

Run:  python examples/build_pendulum.py
Copyright (C) 2026 Gwilherm Kerherve - GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402


def build():
    wb = Workbook(min_rows=44, min_cols=12)
    s = wb.add_sheet("Pendulum")
    s.title_block("Simple Pendulum",
                  "Small-angle period and the T² vs L line for g", span=6)

    # Inputs: L=B5, g=B6
    for i, (lbl, v) in enumerate([("Length L (m)", 1.00),
                                  ("Gravity g (m/s²)", 9.81)]):
        s.set(4 + i, 0, lbl)
        s.set(4 + i, 1, v)
        s.fmt(4 + i, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 170)
    s.note(4, 1, "Edit L and g; the period, table and chart recompute.",
           kind="note")

    s.set(3, 3, "Results")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"])
    res = [
        ("Period T = 2π√(L/g) (s)", "=6.283185*SQRT(B5/B6)"),
        ("Frequency f = 1/T (Hz)", "=1/(6.283185*SQRT(B5/B6))"),
        ("Angular frequency ω (rad/s)", "=SQRT(B6/B5)"),
        ("T² (s²)", "=(6.283185*SQRT(B5/B6))^2"),
        ("Slope 4π²/g (s²/m)", "=39.4784/B6"),
    ]
    for i, (lbl, expr) in enumerate(res):
        s.set(4 + i, 3, lbl)
        s.formula(4 + i, 4, expr)
        s.fmt(4 + i, 4, bold=True, bg=PALETTE["band"], number_format="0.0000")
    s.box(4, 3, 8, 4, color=PALETTE["header"], width=1.0)
    s.col_width(3, 210)

    # Period vs length table
    TS = 11
    Ls = np.round(np.arange(0.1, 2.01, 0.1), 2)
    rows = []
    for i, L in enumerate(Ls):
        sr = TS + 2 + i
        rows.append([float(L), f"=6.283185*SQRT(A{sr}/$B$6)",
                     f"=(6.283185*SQRT(A{sr}/$B$6))^2"])
    s.set(10, 0, "Period and T² vs length")
    s.fmt(10, 0, bold=True, font_color=PALETTE["header"])
    s.table(TS, 0, headers=["L (m)", "T (s)", "T² (s²)"],
            rows=rows, number_format="0.000", banded=True, align_data="center")
    s.designate(0, "X")
    s.designate(1, "Y")
    s.designate(2, "Y")
    r0, r1 = TS + 1, TS + len(Ls)
    g = 9.81
    T = 2 * np.pi * np.sqrt(Ls / g)
    s.chart([Series(Ls, T, "T (s)", "Line+Symbol", color=PALETTE["header"],
                    marker="o", markersize=3.0,
                    x_col=0, y_col=1, row_start=r0, row_end=r1)],
            at=(560, 40), size=(440, 280),
            title="Period vs Length (T ∝ √L)",
            xlabel="Length L (m)", ylabel="Period T (s)", legend=False)
    s.chart([Series(Ls, T ** 2, "T² (s²)", "Line", color=PALETTE["accent"],
                    linewidth=2.0, x_col=0, y_col=2, row_start=r0, row_end=r1)],
            at=(560, 340), size=(440, 280),
            title="T² vs Length (straight line, slope = 4π²/g)",
            xlabel="Length L (m)", ylabel="T² (s²)", legend=False)

    s.equation(r"T = 2\pi \sqrt{\frac{L}{g}}",
               at=(1020, 40), fontsize=18, color="#222222",
               bg_color="#ffffff", border_color=PALETTE["header"],
               border_width=1.3, size=(170, 64))
    s.equation(r"T^2 = \frac{4\pi^2}{g}\,L",
               at=(1020, 120), fontsize=18, color="#222222",
               bg_color="#ffffff", border_color=PALETTE["accent"],
               border_width=1.3, size=(180, 56))
    s.note(10, 2, "Valid for small swings (< ~10°). The period does not "
                  "depend on the mass. A straight T²–L plot gives g.",
           kind="note")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Simple Pendulum.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
