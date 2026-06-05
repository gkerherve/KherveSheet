"""Build the "Screw / Bolt Torque" worked example.

The torque-tension relation  T = K * F * d  links tightening torque T,
bolt preload (clamp force) F and nominal diameter d through the nut
factor K (which depends on lubrication).  With F in kN and d in mm the
product K*F*d comes out directly in N*m (kN*mm = N*m).

Run:  python examples/build_screw_torque.py
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
    wb = Workbook(min_rows=46, min_cols=14)
    s = wb.add_sheet("Bolt Torque")
    s.title_block("Screw / Bolt Torque",
                  "Torque-tension relation T = K F d", span=7)

    # Inputs: K=B5, d=B6 (mm), F=B7 (kN)
    for i, (lbl, v, fmt) in enumerate([
            ("Nut factor K", 0.20, "0.000"),
            ("Nominal diameter d (mm)", 10.0, "0.0"),
            ("Target preload F (kN)", 20.0, "0.0")]):
        s.set(4 + i, 0, lbl)
        s.set(4 + i, 1, v)
        s.fmt(4 + i, 1, bg=PALETTE["warn"], align="center", number_format=fmt)
    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 200)
    s.note(4, 1, "Edit K, d, F. K ~ 0.20 dry, 0.15 lightly oiled, "
                 "0.10 waxed/anti-seize.", kind="note")

    # Result: torque (N*m)  =  K * F(kN) * d(mm)
    s.set(3, 3, "Result")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"])
    res = [
        ("Tightening torque T = K F d (N·m)", "=B5*B7*B6"),
        ("Torque in lbf·ft", "=B5*B7*B6*0.737562"),
        ("If lubricated (K=0.15) (N·m)", "=0.15*B7*B6"),
        ("If waxed (K=0.10) (N·m)", "=0.10*B7*B6"),
    ]
    for i, (lbl, expr) in enumerate(res):
        s.set(4 + i, 3, lbl)
        s.formula(4 + i, 4, expr)
        s.fmt(4 + i, 4, bold=True, bg=PALETTE["band"], number_format="0.00")
    s.box(4, 3, 7, 4, color=PALETTE["header"], width=1.0)
    s.col_width(3, 230)

    # Torque vs preload table (for the chosen K, d)
    TS = 11
    Fs = np.arange(0, 41, 2.5)
    rows = []
    for i, F in enumerate(Fs):
        sr = TS + 2 + i
        rows.append([round(float(F), 1), f"=$B$5*A{sr}*$B$6"])
    s.set(10, 0, "Torque vs preload (chosen K, d)")
    s.fmt(10, 0, bold=True, font_color=PALETTE["header"])
    s.table(TS, 0, headers=["Preload F (kN)", "Torque T (N·m)"],
            rows=rows, number_format="0.00", banded=True, align_data="center")
    s.designate(0, "X")
    s.designate(1, "Y")
    r0, r1 = TS + 1, TS + len(Fs)
    K0, d0 = 0.20, 10.0
    s.chart([Series(Fs, K0 * Fs * d0, "Torque (N·m)", "Line",
                    color=PALETTE["header"], linewidth=2.0,
                    x_col=0, y_col=1, row_start=r0, row_end=r1)],
            at=(560, 40), size=(440, 280), title="Torque vs Preload",
            xlabel="Preload F (kN)", ylabel="Torque T (N·m)", legend=False)

    # Standard bolt comparison at the chosen preload F
    TS2 = TS + len(Fs) + 3
    bolts = [("M6", 6), ("M8", 8), ("M10", 10), ("M12", 12),
             ("M16", 16), ("M20", 20)]
    rows2 = []
    for i, (nm, dia) in enumerate(bolts):
        sr = TS2 + 2 + i
        rows2.append([nm, dia, f"=$B$5*$B$7*B{sr}"])
    s.set(TS2 - 1, 0, "Recommended torque by bolt size (at preload F)")
    s.fmt(TS2 - 1, 0, bold=True, font_color=PALETTE["header"])
    s.table(TS2, 0, headers=["Bolt", "d (mm)", "Torque T (N·m)"],
            rows=rows2, number_format="0.00", banded=True, align_data="center")
    rr0, rr1 = TS2 + 1, TS2 + len(bolts)
    s.chart([Series(np.arange(len(bolts)),
                    np.array([0.20 * 20.0 * d for _, d in bolts]),
                    "Torque", "Bar", color=PALETTE["accent"],
                    y_col=2, row_start=rr0, row_end=rr1)],
            at=(560, 340), size=(440, 280), title="Torque by Bolt Size",
            xlabel="Bolt", ylabel="Torque (N·m)", legend=False)

    s.equation(r"T = K\,F\,d",
               at=(1040, 40), fontsize=20, color="#222222",
               bg_color="#ffffff", border_color=PALETTE["header"],
               border_width=1.3, size=(150, 50))
    s.note(TS2, 1, "Preload is typically ~75% of the bolt's proof load. "
                   "Always follow the manufacturer's spec.", kind="note")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Screw Torque.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
