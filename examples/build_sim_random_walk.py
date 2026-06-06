"""Build "2D Random Walk.ksheet" — a Python-cell simulation example.

=PY cells simulate 2-D random walks (multiple walkers), plot paths,
and return the mean squared displacement at the final step.

Run:  python examples/build_sim_random_walk.py

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
    s = wb.add_sheet("Random Walk")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("2D Random Walk",
                  "Simulate independent walkers on the plane — "
                  "edit inputs then press Ctrl+Enter")

    # ── Input parameters ──────────────────────────────────────────────
    # B4 = N (steps), B5 = walkers, B6 = seed
    s.set(3, 0, "Number of steps  N")
    s.set(3, 1, 500)
    s.set(4, 0, "Number of walkers")
    s.set(4, 1, 8)
    s.set(5, 0, "Random seed")
    s.set(5, 1, 42)

    for r in range(3, 6):
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0")

    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 200)
    s.col_width(1, 90)

    s.note(3, 1,
           "Edit N (steps), number of walkers, or seed, then press "
           "Ctrl+Enter on the =PY plot cell in row 8 to rerun.",
           kind="note")

    # ── =PY plot cell (row 7 zero-based → A8 in sheet) ────────────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "N       = int(ks('B4'))",
        "n_walk  = int(ks('B5'))",
        "seed    = int(ks('B6'))",
        "rng     = np.random.default_rng(seed)",
        "# Steps: random choice of ±1 in x and y independently",
        "steps   = rng.choice([-1, 1], size=(n_walk, N, 2))",
        "paths   = np.zeros((n_walk, N + 1, 2))",
        "paths[:, 1:, :] = np.cumsum(steps, axis=1)",
        "colors  = plt.cm.tab10(np.linspace(0, 1, n_walk))",
        "fig, ax = plt.subplots(figsize=(6, 5))",
        "for i in range(n_walk):",
        "    ax.plot(paths[i, :, 0], paths[i, :, 1],",
        "            lw=0.8, alpha=0.75, color=colors[i],",
        "            label=f'Walker {i+1}')",
        "    ax.plot(paths[i, -1, 0], paths[i, -1, 1],",
        "            'o', color=colors[i], ms=5)",
        "ax.plot(0, 0, 'k*', ms=10, zorder=5, label='Origin')",
        "ax.set_aspect('equal')",
        "ax.set_xlabel('x steps')",
        "ax.set_ylabel('y steps')",
        "ax.set_title(f'2-D Random Walk  (N={N}, walkers={n_walk})')",
        "ax.legend(fontsize=7, ncol=2)",
        "ax.grid(True, alpha=0.3)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(7, 0, py_plot)

    # ── =PY scalar: mean squared displacement ─────────────────────────
    s.set(7, 3, "Mean squared displacement:")
    s.fmt(7, 3, bold=True, align="right")
    s.col_width(3, 210)
    s.col_width(4, 110)

    py_msd = "\n".join([
        "=PY",
        "import numpy as np",
        "N       = int(ks('B4'))",
        "n_walk  = int(ks('B5'))",
        "seed    = int(ks('B6'))",
        "rng     = np.random.default_rng(seed)",
        "steps   = rng.choice([-1, 1], size=(n_walk, N, 2))",
        "paths   = np.zeros((n_walk, N + 1, 2))",
        "paths[:, 1:, :] = np.cumsum(steps, axis=1)",
        "# MSD at final step, averaged over walkers",
        "msd = float(np.mean(np.sum(paths[:, -1, :]**2, axis=1)))",
        "round(msd, 3)",
    ])
    s.formula(7, 4, py_msd)
    s.fmt(7, 4, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.00")

    s.set(8, 3, "(expected  ≈  N  =  steps)")
    s.fmt(8, 3, italic=True, font_color="#666666")

    out = os.path.join(_REPO, "examples", "python", "Simulations",
                       "2D Random Walk.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
