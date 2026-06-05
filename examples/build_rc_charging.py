"""Build the "RC Charging" Python-cell example .ksheet.

Models a capacitor charging through a resistor: Vc(t) = V(1 - exp(-t/RC)).
One =PY cell returns the time constant τ=RC; another plots the curve.

Run:  python examples/build_rc_charging.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE

OUTPUT = os.path.join(
    _REPO, "examples", "python", "Engineering", "RC Charging.ksheet"
)


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("RC Charging")

    # Title
    s.title_block(
        "RC Circuit Charging",
        "Capacitor voltage Vc(t) = V(1 − e^(−t/RC))  — edit inputs and press Ctrl+Enter",
    )

    # Input parameters
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Resistance  R (Ω)", 1000.0),
        ("Capacitance  C (µF)", 100.0),
        ("Supply voltage  V (V)", 5.0),
        ("Simulation time  t_end (s)", 1.0),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.###")

    s.box(4, 0, 7, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 220)
    s.col_width(1, 110)

    # Note about units
    s.note(5, 1,
           "C is entered in µF (micro-farads). The =PY cell converts "
           "it to Farads internally (C_F = C_µF × 1e-6).",
           kind="note")

    # Derived: time constant τ = RC  (=PY cell, returns a number)
    s.set(9, 0, "Time constant  τ = RC (s)")
    s.fmt(9, 0, bold=True)
    s.formula(
        9, 1,
        "=PY\n"
        "R = ks('B5')\n"
        "C_uF = ks('B6')\n"
        "C_F = C_uF * 1e-6\n"
        "tau = R * C_F\n"
        "round(tau, 6)\n"
    )
    s.fmt(9, 1, bg=PALETTE["good"], bold=True, align="center", number_format="0.000000")
    s.box(9, 0, 9, 1, color=PALETTE["header"], width=1.5)

    # Voltage at 5τ
    s.set(10, 0, "Voltage at 5τ (≈ 99.3% charged, V)")
    s.fmt(10, 0, bold=True)
    s.formula(
        10, 1,
        "=PY\n"
        "import numpy as np\n"
        "R = ks('B5')\n"
        "C_uF = ks('B6')\n"
        "V = ks('B7')\n"
        "tau = R * C_uF * 1e-6\n"
        "round(V * (1 - np.exp(-5)), 4)\n"
    )
    s.fmt(10, 1, bg=PALETTE["band"], bold=True, align="center", number_format="0.0000")
    s.box(10, 0, 10, 1, color=PALETTE["header"], width=1.5)

    # Instruction row
    s.set(12, 0, "Charging curve  (=PY plot — press Ctrl+Enter to refresh)")
    s.fmt(12, 0, bold=True, font_color=PALETTE["header"])

    # =PY plot cell
    py_code = (
        "=PY\n"
        "import numpy as np, matplotlib.pyplot as plt\n"
        "R    = ks('B5')\n"
        "C_uF = ks('B6')\n"
        "V    = ks('B7')\n"
        "t_end = ks('B8')\n"
        "C_F  = C_uF * 1e-6\n"
        "tau  = R * C_F\n"
        "t    = np.linspace(0, t_end, 500)\n"
        "Vc   = V * (1 - np.exp(-t / tau))\n"
        "fig, ax = plt.subplots(figsize=(6, 4))\n"
        "ax.plot(t, Vc, color='#4472c4', linewidth=2.5, label='Vc(t)')\n"
        "ax.axhline(V, color='#ed7d31', linestyle='--', linewidth=1.5, label='V (supply)')\n"
        "ax.axvline(tau, color='#70ad47', linestyle=':', linewidth=1.5, label=f'τ = {tau*1000:.1f} ms')\n"
        "ax.set_xlabel('Time  t (s)')\n"
        "ax.set_ylabel('Capacitor voltage  Vc (V)')\n"
        "ax.set_title('RC Circuit Charging')\n"
        "ax.legend()\n"
        "ax.grid(True, linestyle='--', alpha=0.5)\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )
    s.formula(13, 0, py_code)
    s.fmt(13, 0, bg="#f0f4ff", font_family="Consolas", font_size=9)

    s.note(13, 0,
           "The orange dashed line marks the supply voltage V; "
           "the green dotted line marks the time constant τ (63.2% charged).",
           kind="note")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    wb.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print("Wrote", build())
