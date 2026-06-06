"""Build the "Heat Conduction" Python-cell example .ksheet.

Steady-state 1-D heat conduction along a rod. The temperature profile
is linear (T(x) = T1 + (T2-T1)*x/L). A =PY cell also shows a simple
transient approach using a finite-difference snapshot.

Run:  python examples/build_heat_conduction.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE

OUTPUT = os.path.join(
    _REPO, "examples", "python", "Engineering", "Heat Conduction.ksheet"
)


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Heat Conduction")

    # Title
    s.title_block(
        "1-D Heat Conduction",
        "Steady-state temperature profile along a rod — edit inputs, press Ctrl+Enter",
    )

    # Input parameters
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Rod length  L (m)", 1.0),
        ("Left-end temperature  T1 (°C)", 100.0),
        ("Right-end temperature  T2 (°C)", 20.0),
        ("Thermal diffusivity  α (m²/s)", 0.0001),
        ("Simulation time  t (s)", 5.0),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.####")

    s.box(4, 0, 8, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 240)
    s.col_width(1, 110)

    s.note(4, 1,
           "Edit any parameter and press Ctrl+Enter on the =PY cell below "
           "to update the plot. α (thermal diffusivity) controls the transient speed.",
           kind="note")

    # Derived: steady-state heat flux  q = k·ΔT/L  (expressed via ΔT/L ratio)
    s.set(10, 0, "Temperature gradient  ΔT/L (°C/m)")
    s.fmt(10, 0, bold=True)
    s.formula(
        10, 1,
        "=PY\n"
        "L  = ks('B5')\n"
        "T1 = ks('B6')\n"
        "T2 = ks('B7')\n"
        "round((T1 - T2) / L, 4)\n"
    )
    s.fmt(10, 1, bg=PALETTE["good"], bold=True, align="center", number_format="0.0000")
    s.box(10, 0, 10, 1, color=PALETTE["header"], width=1.5)

    # Mid-point steady-state temperature
    s.set(11, 0, "Mid-point steady-state T (°C)")
    s.fmt(11, 0, bold=True)
    s.formula(
        11, 1,
        "=PY\n"
        "T1 = ks('B6')\n"
        "T2 = ks('B7')\n"
        "round((T1 + T2) / 2.0, 4)\n"
    )
    s.fmt(11, 1, bg=PALETTE["band"], bold=True, align="center", number_format="0.0000")
    s.box(11, 0, 11, 1, color=PALETTE["header"], width=1.5)

    # Instruction row
    s.set(13, 0, "Temperature profile  (=PY plot — press Ctrl+Enter to refresh)")
    s.fmt(13, 0, bold=True, font_color=PALETTE["header"])

    # =PY plot cell — steady state + several transient snapshots
    py_code = (
        "=PY\n"
        "import numpy as np, matplotlib.pyplot as plt\n"
        "trapz = getattr(np, 'trapezoid', None) or np.trapz  # NumPy 2 safe\n"
        "L     = ks('B5')\n"
        "T1    = ks('B6')\n"
        "T2    = ks('B7')\n"
        "alpha = ks('B8')\n"
        "t_end = ks('B9')\n"
        "x = np.linspace(0, L, 200)\n"
        "# Steady-state: linear profile\n"
        "T_ss = T1 + (T2 - T1) * x / L\n"
        "# Transient solution via Fourier series (first 20 terms)\n"
        "# Initial condition: rod at T2 everywhere; BCs: T(0)=T1, T(L)=T2\n"
        "# Separate into steady + transient: u(x,t) = T_ss + v(x,t)\n"
        "# v(x,0) = T2 - T_ss(x)  (since rod starts at T2 uniform)\n"
        "# v satisfies homogeneous BCs => sine series\n"
        "fig, ax = plt.subplots(figsize=(7, 4))\n"
        "colors = plt.cm.Blues(np.linspace(0.4, 0.9, 5))\n"
        "times = np.linspace(0, t_end, 6)[1:]  # exclude t=0\n"
        "for idx, t in enumerate(times):\n"
        "    T_transient = np.zeros_like(x)\n"
        "    for n in range(1, 21):\n"
        "        bn = (2.0 / L) * trapz(\n"
        "            (T2 - (T1 + (T2 - T1) * x / L)) * np.sin(n * np.pi * x / L), x\n"
        "        )\n"
        "        T_transient += bn * np.exp(-alpha * (n * np.pi / L)**2 * t) * np.sin(n * np.pi * x / L)\n"
        "    T_total = T_ss + T_transient\n"
        "    lbl = f't = {t:.1f} s' if idx < len(times) - 1 else f't = {t:.1f} s (final)'\n"
        "    ax.plot(x, T_total, color=colors[min(idx, len(colors)-1)], linewidth=1.5,\n"
        "            linestyle='-', alpha=0.8, label=lbl)\n"
        "ax.plot(x, T_ss, color='#ed7d31', linewidth=2.5, linestyle='--', label='Steady state')\n"
        "ax.set_xlabel('Position  x (m)')\n"
        "ax.set_ylabel('Temperature  T (°C)')\n"
        "ax.set_title('1-D Heat Conduction')\n"
        "ax.legend(fontsize=8)\n"
        "ax.grid(True, linestyle='--', alpha=0.4)\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )
    s.formula(14, 0, py_code)
    s.fmt(14, 0, bg="#f0f4ff", font_family="Consolas", font_size=9)

    s.note(14, 0,
           "Blue curves show the transient temperature at successive time snapshots; "
           "the orange dashed line is the steady-state linear profile T(x) = T1 + (T2−T1)x/L.",
           kind="note")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    wb.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print("Wrote", build())
