"""Build the "Ideal Gas Isotherms" demo .ksheet example.

Inputs: amount n (mol), three temperatures T1/T2/T3.
Plots P vs V isotherms (P = nRT/V) for each temperature.

Run:  python examples/build_ideal_gas_isotherms.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, PALETTE  # noqa: E402


PY_PLOT = r"""=PY
import numpy as np
import matplotlib.pyplot as plt

R   = 8.314          # J/(mol·K)
# row=4,col=1 → B5; row=5,col=1 → B6 ... in 1-based A1 notation
n   = ks("B5")       # amount (mol)
T1  = ks("B6")       # temperature 1 (K)
T2  = ks("B7")       # temperature 2 (K)
T3  = ks("B8")       # temperature 3 (K)

V = np.linspace(0.001, 0.05, 500)   # m³

colors = ["#4472c4", "#ed7d31", "#c00000"]
temps  = [T1, T2, T3]
labels = [f"T = {T:.0f} K" for T in temps]

fig, ax = plt.subplots(figsize=(7, 4.5))
for T, col, lbl in zip(temps, colors, labels):
    P = n * R * T / V / 1000.0    # kPa
    ax.plot(V * 1000.0, P, color=col, linewidth=2.0, label=lbl)

ax.set_xlabel("Volume V  (L)")
ax.set_ylabel("Pressure P  (kPa)")
ax.set_title(f"Ideal Gas Isotherms  (n = {n:.2f} mol)")
ax.legend(fontsize=10)
ax.set_xlim(0, 50)
ax.set_ylim(0, None)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.gcf()
"""

PY_PRESSURES = r"""=PY
import numpy as np
R = 8.314
n = ks("B5")
T1 = ks("B6"); T2 = ks("B7"); T3 = ks("B8")
# Pressure at V=1 L for each temperature (kPa)
V = 0.001   # 1 L in m³
[round(n*R*T1/V/1000, 1), round(n*R*T2/V/1000, 1), round(n*R*T3/V/1000, 1)]
"""


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Isotherms")

    # Title
    s.title_block("Ideal Gas Isotherms",
                  "P = nRT/V — pressure–volume curves at fixed temperature")

    # Input parameters
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Amount n (mol)",       1.0),
        ("Temperature T1 (K)",  200.0),
        ("Temperature T2 (K)",  300.0),
        ("Temperature T3 (K)",  400.0),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.0")
    s.box(4, 0, 7, 1, color=PALETTE["accent"], width=1.2)
    s.col_width(0, 200)
    s.col_width(1, 110)

    # Pressure @ 1 L spill
    s.set(9, 0, "Pressure at V = 1 L  (kPa):")
    s.fmt(9, 0, bold=True)
    s.formula(9, 1, PY_PRESSURES)
    s.box(9, 0, 9, 3, color=PALETTE["header"], width=1.0)

    # Colour labels for the spill values
    s.set(10, 0, "T1"); s.fmt(10, 0, font_color="#4472c4", bold=True)
    s.set(10, 1, "T2"); s.fmt(10, 1, font_color="#ed7d31", bold=True)
    s.set(10, 2, "T3"); s.fmt(10, 2, font_color="#c00000", bold=True)

    # Main plot cell
    s.formula(12, 0, PY_PLOT)

    # Notes
    s.note(4, 1,
           "Edit n, T1, T2, or T3 here. Press Ctrl+Enter on the =PY cells "
           "to replot the isotherms.", kind="note")
    s.note(12, 0,
           "=PY cell: plots P = nRT/V for three isotherms. "
           "Higher T → higher curve. All three are shown on one figure.",
           kind="note")

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "python", "Chemistry", "Ideal Gas Isotherms.ksheet"
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
