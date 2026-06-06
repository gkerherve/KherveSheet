"""Build "Brownian Motion.ksheet" — a Python-cell simulation example.

=PY cells simulate 1-D Brownian motion paths and plot several
trajectories over time; a second =PY cell returns the theoretical
diffusion coefficient check.

Run:  python examples/build_sim_brownian_motion.py

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
    s = wb.add_sheet("Brownian Motion")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Brownian Motion",
                  "1-D Wiener process paths — edit inputs then "
                  "press Ctrl+Enter to rerun")

    # ── Input parameters ──────────────────────────────────────────────
    # B4=steps, B5=dt, B6=sigma (diffusivity), B7=seed
    s.set(3, 0, "Number of steps  N")
    s.set(3, 1, 400)
    s.set(4, 0, "Time step  dt  (s)")
    s.set(4, 1, 0.01)
    s.set(5, 0, "Volatility  σ")
    s.set(5, 1, 1.0)
    s.set(6, 0, "Number of paths")
    s.set(6, 1, 6)
    s.set(7, 0, "Random seed")
    s.set(7, 1, 7)

    for r in range(3, 8):
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.###")

    s.box(3, 0, 7, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 200)
    s.col_width(1, 90)

    s.note(3, 1,
           "Edit N (steps), dt, volatility σ or the number of paths, "
           "then press Ctrl+Enter on the =PY cell in row 10 to replot.",
           kind="note")

    # ── =PY plot cell (row 9 zero-based → A10) ────────────────────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "N      = int(ks('B4'))",
        "dt     = float(ks('B5'))",
        "sigma  = float(ks('B6'))",
        "n_path = int(ks('B7'))",
        "seed   = int(ks('B8'))",
        "rng    = np.random.default_rng(seed)",
        "# Brownian increments: N(0, sigma^2 * dt)",
        "dW     = rng.normal(0.0, sigma * np.sqrt(dt), size=(n_path, N))",
        "W      = np.zeros((n_path, N + 1))",
        "W[:, 1:] = np.cumsum(dW, axis=1)",
        "t      = np.linspace(0.0, N * dt, N + 1)",
        "colors = plt.cm.plasma(np.linspace(0.1, 0.9, n_path))",
        "fig, ax = plt.subplots(figsize=(7, 4))",
        "for i in range(n_path):",
        "    ax.plot(t, W[i], lw=0.9, alpha=0.8, color=colors[i],",
        "            label=f'Path {i+1}')",
        "# Theoretical ±1-sigma envelope: ±sigma*sqrt(t)",
        "env = sigma * np.sqrt(t)",
        "ax.fill_between(t, -env, env, alpha=0.12, color='grey',",
        "                label=r'$\\pm\\sigma\\sqrt{t}$')",
        "ax.axhline(0, color='k', lw=0.5, ls='--')",
        "ax.set_xlabel('Time  t')",
        "ax.set_ylabel('Position  W(t)')",
        "ax.set_title(f'Brownian Motion  (N={N}, dt={dt}, \\u03c3={sigma})')",
        "ax.legend(fontsize=7, ncol=2)",
        "ax.grid(True, alpha=0.3)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(9, 0, py_plot)

    # ── =PY scalar: empirical vs theoretical variance ─────────────────
    s.set(9, 3, "Empirical var / theoretical var:")
    s.fmt(9, 3, bold=True, align="right")
    s.col_width(3, 230)
    s.col_width(4, 110)

    py_var = "\n".join([
        "=PY",
        "import numpy as np",
        "N      = int(ks('B4'))",
        "dt     = float(ks('B5'))",
        "sigma  = float(ks('B6'))",
        "n_path = int(ks('B7'))",
        "seed   = int(ks('B8'))",
        "rng    = np.random.default_rng(seed)",
        "dW     = rng.normal(0.0, sigma * np.sqrt(dt), size=(n_path, N))",
        "W      = np.zeros((n_path, N + 1))",
        "W[:, 1:] = np.cumsum(dW, axis=1)",
        "emp_var   = float(np.var(W[:, -1]))",
        "theor_var = sigma**2 * N * dt",
        "round(emp_var / theor_var, 4)",
    ])
    s.formula(9, 4, py_var)
    s.fmt(9, 4, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.0000")

    s.set(10, 3, "(should be close to 1.0)")
    s.fmt(10, 3, italic=True, font_color="#666666")

    out = os.path.join(_REPO, "examples", "python", "Simulations",
                       "Brownian Motion.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
