"""Build the "Springs (Hooke's Law)" worked example.

Hooke's law F = k x, elastic potential energy E = 1/2 k x^2, and the
mass-spring oscillation period T = 2*pi*sqrt(m/k).  Editable inputs:
spring constant k, mass m, gravity g.

Run:  python examples/build_springs.py
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
    s = wb.add_sheet("Springs")
    s.title_block("Springs (Hooke's Law)",
                  "Force, elastic energy and simple-harmonic period",
                  span=6)

    # Inputs: k=B5, m=B6, g=B7
    for i, (lbl, v, fmt) in enumerate([
            ("Spring constant k (N/m)", 200.0, "0.0"),
            ("Mass m (kg)", 0.50, "0.000"),
            ("Gravity g (m/s²)", 9.81, "0.00")]):
        s.set(4 + i, 0, lbl)
        s.set(4 + i, 1, v)
        s.fmt(4 + i, 1, bg=PALETTE["warn"], align="center", number_format=fmt)
    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 190)
    s.note(4, 1, "Edit k, m, g — every result, the table and the chart "
                 "recompute.", kind="note")

    # Derived results
    s.set(3, 3, "Results")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"])
    res = [
        ("Static extension xₒ = mg/k (m)", "=B6*B7/B5"),
        ("Angular frequency ω = √(k/m) (rad/s)", "=SQRT(B5/B6)"),
        ("Period T = 2π√(m/k) (s)", "=6.283185*SQRT(B6/B5)"),
        ("Frequency f = 1/T (Hz)", "=1/(6.283185*SQRT(B6/B5))"),
        ("Energy at xₒ = ½k xₒ² (J)", "=0.5*B5*(B6*B7/B5)^2"),
    ]
    for i, (lbl, expr) in enumerate(res):
        s.set(4 + i, 3, lbl)
        s.formula(4 + i, 4, expr)
        s.fmt(4 + i, 4, bold=True, bg=PALETTE["band"], number_format="0.0000")
    s.box(4, 3, 8, 4, color=PALETTE["header"], width=1.0)
    s.col_width(3, 230)

    # Force / energy vs extension table
    TS = 11
    xs = np.linspace(0, 0.5, 26)
    rows = []
    for i, x in enumerate(xs):
        sr = TS + 2 + i
        rows.append([round(float(x), 3), f"=$B$5*A{sr}",
                     f"=0.5*$B$5*A{sr}*A{sr}"])
    s.set(10, 0, "Force and elastic energy vs extension")
    s.fmt(10, 0, bold=True, font_color=PALETTE["header"])
    s.table(TS, 0, headers=["x (m)", "Force F (N)", "Energy Eₚ (J)"],
            rows=rows, number_format="0.000", banded=True, align_data="center")
    s.designate(0, "X")
    s.designate(1, "Y")
    s.designate(2, "Y")
    r0, r1 = TS + 1, TS + len(xs)
    k = 200.0
    s.chart([Series(xs, k * xs, "Force (N)", "Line", color=PALETTE["header"],
                    linewidth=2.0, x_col=0, y_col=1, row_start=r0, row_end=r1),
             Series(xs, 0.5 * k * xs ** 2, "Energy (J)", "Line",
                    color=PALETTE["accent"], linestyle="--",
                    x_col=0, y_col=2, row_start=r0, row_end=r1)],
            at=(560, 40), size=(450, 320),
            title="Hooke's Law: F and Eₚ vs extension",
            xlabel="Extension x (m)", ylabel="F (N) / Eₚ (J)", legend=True)

    # Equations
    s.equation(r"F = k\,x \qquad E_p = \frac{1}{2} k x^2",
               at=(560, 380), fontsize=18, color="#222222",
               bg_color="#ffffff", border_color=PALETTE["header"],
               border_width=1.3, size=(300, 46))
    s.equation(r"T = 2\pi \sqrt{\frac{m}{k}}",
               at=(560, 440), fontsize=18, color="#222222",
               bg_color="#ffffff", border_color=PALETTE["accent"],
               border_width=1.3, size=(170, 64))
    s.note(10, 2, "The area under the F–x line equals the stored elastic "
                  "energy ½kx². The period is independent of amplitude.",
           kind="note")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Springs.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
