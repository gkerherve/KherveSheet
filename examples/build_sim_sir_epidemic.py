"""Build "SIR Epidemic.ksheet" — a Python-cell simulation example.

=PY cells integrate the deterministic SIR epidemic model using a
simple Euler scheme and plot S, I, R over time; a second =PY cell
returns the basic reproduction number R0.

Run:  python examples/build_sim_sir_epidemic.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=12)
    s = wb.add_sheet("SIR Epidemic")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("SIR Epidemic Model",
                  "Deterministic Susceptible-Infected-Recovered model "
                  "— edit inputs then press Ctrl+Enter")

    # ── Input parameters ──────────────────────────────────────────────
    # B4=N, B5=beta, B6=gamma, B7=I0, B8=days
    s.set(3, 0, "Population  N")
    s.set(3, 1, 10000)
    s.set(4, 0, "Infection rate  β  (day⁻¹)")
    s.set(4, 1, 0.3)
    s.set(5, 0, "Recovery rate  γ  (day⁻¹)")
    s.set(5, 1, 0.05)
    s.set(6, 0, "Initial infected  I₀")
    s.set(6, 1, 10)
    s.set(7, 0, "Days to simulate")
    s.set(7, 1, 160)

    for r in range(3, 8):
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.###")

    s.box(3, 0, 7, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 220)
    s.col_width(1, 90)

    s.note(3, 1,
           "Try β=0.5 for a faster outbreak, γ=0.1 for quicker recovery, "
           "or increase I₀. Press Ctrl+Enter on the =PY cells to rerun.",
           kind="note")

    # ── =PY scalar: R0 ────────────────────────────────────────────────
    s.set(8, 3, "Basic reproduction number R₀:")
    s.fmt(8, 3, bold=True, align="right")
    s.col_width(3, 250)
    s.col_width(4, 110)

    py_r0 = "\n".join([
        "=PY",
        "beta  = float(ks('B5'))",
        "gamma = float(ks('B6'))",
        "round(beta / gamma, 4)",
    ])
    s.formula(8, 4, py_r0)
    s.fmt(8, 4, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.00")

    s.set(9, 3, "(epidemic spreads when R₀ > 1)")
    s.fmt(9, 3, italic=True, font_color="#666666")

    # ── =PY plot cell (row 10 zero-based → A11) ───────────────────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "N     = float(ks('B4'))",
        "beta  = float(ks('B5'))",
        "gamma = float(ks('B6'))",
        "I0    = float(ks('B7'))",
        "days  = int(ks('B8'))",
        "# Euler integration of SIR ODEs",
        "dt    = 0.1",
        "steps = int(days / dt)",
        "S = np.zeros(steps + 1)",
        "I = np.zeros(steps + 1)",
        "R = np.zeros(steps + 1)",
        "S[0] = N - I0",
        "I[0] = I0",
        "R[0] = 0.0",
        "for k in range(steps):",
        "    new_inf = beta * S[k] * I[k] / N * dt",
        "    new_rec = gamma * I[k] * dt",
        "    S[k+1] = S[k] - new_inf",
        "    I[k+1] = I[k] + new_inf - new_rec",
        "    R[k+1] = R[k] + new_rec",
        "t = np.linspace(0, days, steps + 1)",
        "fig, ax = plt.subplots(figsize=(7, 4))",
        "ax.plot(t, S, color='#4472c4', lw=2, label='Susceptible S')",
        "ax.plot(t, I, color='#ed7d31', lw=2, label='Infected I')",
        "ax.plot(t, R, color='#70ad47', lw=2, label='Recovered R')",
        "ax.set_xlabel('Time (days)')",
        "ax.set_ylabel('Number of individuals')",
        "ax.set_title(f'SIR Model  (\\u03b2={beta}, \\u03b3={gamma},'",
        "             f' R\\u2080={beta/gamma:.2f})')",
        "ax.legend(fontsize=9)",
        "ax.grid(True, alpha=0.3)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(10, 0, py_plot)

    out = os.path.join(_REPO, "examples", "python", "Simulations",
                       "SIR Epidemic.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
