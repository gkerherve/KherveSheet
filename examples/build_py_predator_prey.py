"""Build "Predator-Prey (Lotka-Volterra)" Python-cell example for KherveSheet.

Demonstrates =PY cells: reads Lotka-Volterra parameters from the grid,
integrates the ODEs with scipy.integrate.odeint, and plots prey and
predator populations over time, plus a phase-space portrait.

Run:  python examples/build_py_predator_prey.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ksheet_author import Workbook, PALETTE

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "examples", "python", "Biology",
                   "Predator-Prey.ksheet")


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=12)
    s = wb.add_sheet("Predator-Prey")

    # Title
    s.title_block("Predator-Prey Dynamics",
                  "Lotka-Volterra model: dN/dt = αN − βNP,  dP/dt = δNP − γP")

    # Input parameters
    s.set(3, 0, "Lotka-Volterra Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("α  — prey growth rate", 1.0),
        ("β  — predation rate", 0.1),
        ("δ  — predator growth efficiency", 0.075),
        ("γ  — predator death rate", 1.5),
        ("N₀  — initial prey", 10.0),
        ("P₀  — initial predators", 5.0),
        ("Time span (years)", 30.0),
    ]
    for i, (label, value) in enumerate(params):
        r = 4 + i
        s.set(r, 0, label)
        s.fmt(r, 0, align="left")
        s.set(r, 1, value)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.000")

    s.box(4, 0, 10, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 230)
    s.col_width(1, 100)

    s.note(4, 1,
           "Edit any Lotka-Volterra parameter or initial condition, then "
           "press Ctrl+Enter on the =PY cell in A13 to reintegrate and "
           "replot.", kind="note")

    # Equilibrium summary
    s.set(3, 3, "Equilibrium values")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"])

    py_equil_prey = (
        "=PY\n"
        "# Non-trivial equilibrium: N* = gamma/delta, P* = alpha/beta\n"
        "alpha = ks('B5')\n"
        "beta  = ks('B6')\n"
        "delta = ks('B7')\n"
        "gamma = ks('B8')\n"
        "N_star = gamma / delta if delta != 0 else float('nan')\n"
        "round(N_star, 3)"
    )
    s.set(4, 3, "N* (prey equilibrium):")
    s.fmt(4, 3, align="left")
    s.formula(4, 4, py_equil_prey)
    s.fmt(4, 4, bg=PALETTE["good"], align="center", bold=True,
          number_format="0.000")

    py_equil_pred = (
        "=PY\n"
        "alpha = ks('B5')\n"
        "beta  = ks('B6')\n"
        "P_star = alpha / beta if beta != 0 else float('nan')\n"
        "round(P_star, 3)"
    )
    s.set(5, 3, "P* (predator equilibrium):")
    s.fmt(5, 3, align="left")
    s.formula(5, 4, py_equil_pred)
    s.fmt(5, 4, bg=PALETTE["band"], align="center", bold=True,
          number_format="0.000")

    s.box(4, 3, 5, 4, color=PALETTE["header"], width=1.0)
    s.col_width(3, 210)
    s.col_width(4, 100)

    # Main =PY plot cell
    py_plot = (
        "=PY\n"
        "import numpy as np\n"
        "import matplotlib.pyplot as plt\n"
        "from scipy.integrate import odeint\n"
        "alpha = ks('B5')\n"
        "beta  = ks('B6')\n"
        "delta = ks('B7')\n"
        "gamma = ks('B8')\n"
        "N0    = ks('B9')\n"
        "P0    = ks('B10')\n"
        "T_max = ks('B11')\n"
        "def lotka_volterra(state, t):\n"
        "    N, P = state\n"
        "    dN = alpha * N - beta * N * P\n"
        "    dP = delta * N * P - gamma * P\n"
        "    return [dN, dP]\n"
        "t = np.linspace(0, T_max, 2000)\n"
        "sol = odeint(lotka_volterra, [N0, P0], t)\n"
        "N_t = sol[:, 0]\n"
        "P_t = sol[:, 1]\n"
        "fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))\n"
        "ax1 = axes[0]\n"
        "ax1.plot(t, N_t, color='#4472c4', linewidth=2.0, label='Prey N(t)')\n"
        "ax1.plot(t, P_t, color='#c00000', linewidth=2.0, label='Predators P(t)')\n"
        "ax1.set_xlabel('Time (years)', fontsize=11)\n"
        "ax1.set_ylabel('Population', fontsize=11)\n"
        "ax1.set_title('Population dynamics', fontsize=12)\n"
        "ax1.legend(fontsize=9)\n"
        "ax1.grid(True, alpha=0.3)\n"
        "ax2 = axes[1]\n"
        "ax2.plot(N_t, P_t, color='#70ad47', linewidth=1.5)\n"
        "ax2.plot(N_t[0], P_t[0], 'ko', markersize=6, label='Start')\n"
        "N_star = gamma / delta if delta != 0 else None\n"
        "P_star = alpha / beta if beta != 0 else None\n"
        "if N_star and P_star:\n"
        "    ax2.plot(N_star, P_star, 'r*', markersize=10, label='Equilibrium')\n"
        "ax2.set_xlabel('Prey N', fontsize=11)\n"
        "ax2.set_ylabel('Predators P', fontsize=11)\n"
        "ax2.set_title('Phase portrait', fontsize=12)\n"
        "ax2.legend(fontsize=9)\n"
        "ax2.grid(True, alpha=0.3)\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )

    s.set(12, 0, "Python cell below")
    s.fmt(12, 0, bold=True, font_color=PALETTE["header"])
    s.formula(13, 0, py_plot)
    s.fmt(13, 0, bg=PALETTE["band"], bold=True, align="center")
    s.set(13, 1, "← Python cell: integrates ODEs, plots time series + phase portrait")
    s.fmt(13, 1, italic=True, font_color="#555555")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb.save(OUT)
    return OUT


if __name__ == "__main__":
    print("Wrote", build())
