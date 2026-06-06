"""Build "Grain Growth.ksheet" — a Python-cell materials science example.

Runs a Q-state Potts model grain-growth simulation on an L×L lattice.
Plots the grain structure with imshow; a second =PY cell returns the
number of distinct grains remaining after the Monte Carlo steps.

Row/column mapping: set(r, c, v) → sheet cell letter(c) + str(r+1).
  set(3,1,v) → B4,  set(4,1,v) → B5,  set(5,1,v) → B6,  set(6,1,v) → B7.

Run:  python examples/build_py_grain_growth.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Grain Growth")

    # ── Title (rows 0-1) ──────────────────────────────────────────────
    s.title_block(
        "Grain Growth",
        "Q-state Potts model Monte Carlo — grain coarsening on a 2-D lattice",
    )

    # ── Input parameters ──────────────────────────────────────────────
    # set(3,1,v)→B4=L, set(4,1,v)→B5=Q, set(5,1,v)→B6=mc_steps, set(6,1,v)→B7=seed
    s.set(2, 0, "Parameters")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    input_rows = [
        (3, "Grid size  L  (cells)",       60,  "0"),
        (4, "Number of grain states  Q",   30,  "0"),
        (5, "Monte Carlo steps",           300, "0"),
        (6, "Random seed",                  42, "0"),
    ]
    for r, lbl, val, nfmt in input_rows:
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format=nfmt)

    s.box(3, 0, 6, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 220)
    s.col_width(1, 100)

    # Note on first input cell (row 3, col 1 = B4)
    s.note(
        3, 1,
        "L=60, Q=30, steps=300 runs in ~1 s (vectorised).  "
        "Increase steps to see more coarsening.  "
        "Press Ctrl+Enter on A11 to rerun.",
        kind="note",
    )

    # ── Output: number of distinct grains (row 8 = sheet row 9) ───────
    # set(8,3,...)→D9,  set(8,4,...)→E9
    s.set(8, 3, "Distinct grains remaining:")
    s.fmt(8, 3, bold=True, align="right")
    s.set(8, 4, "")   # filled by ks_set('E9', ...) from plot cell
    s.fmt(8, 4, bg=PALETTE["good"], bold=True, align="center",
          number_format="0")
    s.col_width(3, 220)
    s.col_width(4, 100)

    s.note(
        8, 4,
        "Starts at Q grains; coarsens toward fewer, larger grains.  "
        "More MC steps => fewer remaining grains (grain coarsening).",
        kind="note",
    )

    # ── =PY plot cell (row 10 = sheet row 11, col 0 = A) ──────────────
    # Reads: B4=L, B5=Q, B6=mc_steps, B7=seed
    # Writes: E9 (distinct grains remaining)
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "L        = int(ks('B4'))",
        "Q        = int(ks('B5'))",
        "mc_steps = int(ks('B6'))",
        "seed     = int(ks('B7'))",
        "rng = np.random.default_rng(seed)",
        "grid = rng.integers(0, Q, size=(L, L))",
        "# Vectorised Potts MC: each step attempts a flip on every cell.",
        "# Accept if new orientation has >= as many like neighbours.",
        "for _ in range(mc_steps):",
        "    new_state = rng.integers(0, Q, size=(L, L))",
        "    same_old = (",
        "        (grid == np.roll(grid,  1, 0)).astype(np.int8)",
        "      + (grid == np.roll(grid, -1, 0)).astype(np.int8)",
        "      + (grid == np.roll(grid,  1, 1)).astype(np.int8)",
        "      + (grid == np.roll(grid, -1, 1)).astype(np.int8)",
        "    )",
        "    same_new = (",
        "        (new_state == np.roll(grid,  1, 0)).astype(np.int8)",
        "      + (new_state == np.roll(grid, -1, 0)).astype(np.int8)",
        "      + (new_state == np.roll(grid,  1, 1)).astype(np.int8)",
        "      + (new_state == np.roll(grid, -1, 1)).astype(np.int8)",
        "    )",
        "    accept = same_new >= same_old",
        "    changed = new_state != grid",
        "    grid = np.where(accept & changed, new_state, grid)",
        "n_grains = int(np.unique(grid).size)",
        "ks_set('E9', n_grains)",
        "fig, ax = plt.subplots(figsize=(5, 5))",
        "ax.imshow(grid, cmap='tab20b', interpolation='nearest', origin='lower')",
        "ax.set_title(f'Grain structure  (L={L}, Q={Q}, {mc_steps} MC steps)')",
        "ax.set_xlabel('x  (cells)')",
        "ax.set_ylabel('y  (cells)')",
        "ax.axis('off')",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(10, 0, py_plot)
    s.set(10, 3, "Grain map — edit inputs above, press Ctrl+Enter to rerun")
    s.fmt(10, 3, italic=True, font_color="#555555")

    # ── Equation ──────────────────────────────────────────────────────
    s.equation(
        r"H = -J \sum_{\langle ij \rangle} \delta(s_i, s_j)",
        at=(540, 50), fontsize=18, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(310, 52),
    )

    out = os.path.join(
        _REPO, "examples", "python", "Materials Science",
        "Grain Growth.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
