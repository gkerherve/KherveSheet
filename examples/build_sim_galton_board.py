"""Build "Galton Board.ksheet" — a Python-cell simulation example.

=PY cells simulate balls dropping through a Galton board (Quincunx)
and plot the resulting histogram overlaid with the limiting
binomial / normal distribution.

Run:  python examples/build_sim_galton_board.py

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
    s = wb.add_sheet("Galton Board")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Galton Board",
                  "Simulate balls through a peg board — converges to "
                  "the binomial distribution")

    # ── Input parameters ──────────────────────────────────────────────
    # B4=rows (pegs), B5=balls, B6=seed
    s.set(3, 0, "Number of peg rows  n")
    s.set(3, 1, 12)
    s.set(4, 0, "Number of balls")
    s.set(4, 1, 2000)
    s.set(5, 0, "Random seed")
    s.set(5, 1, 99)

    for r in range(3, 6):
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0")

    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 200)
    s.col_width(1, 90)

    s.note(3, 1,
           "Edit n (peg rows) or the number of balls, then press "
           "Ctrl+Enter on the =PY cell in row 8 to re-simulate.",
           kind="note")

    # ── =PY plot cell (row 7 zero-based → A8) ─────────────────────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "from scipy.stats import binom, norm",
        "n_rows = int(ks('B4'))",
        "n_ball = int(ks('B5'))",
        "seed   = int(ks('B6'))",
        "rng    = np.random.default_rng(seed)",
        "# Each ball deflects left(0) or right(1) at every peg",
        "deflections = rng.integers(0, 2, size=(n_ball, n_rows))",
        "slots = deflections.sum(axis=1)   # final bin: 0..n_rows",
        "bins  = np.arange(-0.5, n_rows + 1.5)",
        "fig, ax = plt.subplots(figsize=(7, 4))",
        "ax.hist(slots, bins=bins, density=True,",
        "        color='#4472c4', alpha=0.7, edgecolor='white',",
        "        label=f'Simulated ({n_ball} balls)')",
        "# Binomial PMF overlay",
        "k     = np.arange(0, n_rows + 1)",
        "pmf   = binom.pmf(k, n_rows, 0.5)",
        "ax.bar(k, pmf, width=0.25, color='#ed7d31', alpha=0.85,",
        "       label='Binomial PMF')",
        "# Normal approximation",
        "mu, sig = n_rows * 0.5, np.sqrt(n_rows * 0.25)",
        "x_c   = np.linspace(0, n_rows, 300)",
        "ax.plot(x_c, norm.pdf(x_c, mu, sig), 'k--', lw=1.5,",
        "        label='Normal approx')",
        "ax.set_xlabel('Slot (number of right deflections)')",
        "ax.set_ylabel('Density')",
        "ax.set_title(f'Galton Board  (n={n_rows} rows, {n_ball} balls)')",
        "ax.legend(fontsize=8)",
        "ax.grid(True, alpha=0.3)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(7, 0, py_plot)

    # ── =PY scalar: empirical mean bin ────────────────────────────────
    s.set(7, 3, "Empirical mean slot:")
    s.fmt(7, 3, bold=True, align="right")
    s.col_width(3, 200)
    s.col_width(4, 110)

    py_mean = "\n".join([
        "=PY",
        "import numpy as np",
        "n_rows = int(ks('B4'))",
        "n_ball = int(ks('B5'))",
        "seed   = int(ks('B6'))",
        "rng    = np.random.default_rng(seed)",
        "deflections = rng.integers(0, 2, size=(n_ball, n_rows))",
        "slots = deflections.sum(axis=1)",
        "round(float(slots.mean()), 4)",
    ])
    s.formula(7, 4, py_mean)
    s.fmt(7, 4, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.0000")

    s.set(8, 3, "(expected = n / 2)")
    s.fmt(8, 3, italic=True, font_color="#666666")

    out = os.path.join(_REPO, "examples", "python", "Simulations",
                       "Galton Board.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
