"""Build "Self-Avoiding Walk.ksheet" — a Python-cell materials science example.

Grows self-avoiding random walks on a 2-D lattice (polymer model).
Plots one example chain; a second cell returns the mean squared end-to-end
distance and radius of gyration averaged over many chains.

Row/column mapping: set(r, c, v) → sheet cell letter(c) + str(r+1).
  set(3,1,v) → B4,  set(4,1,v) → B5,  set(5,1,v) → B6.

Run:  python examples/build_py_self_avoiding_walk.py

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
    s = wb.add_sheet("SAW")

    # ── Title (rows 0-1) ──────────────────────────────────────────────
    s.title_block(
        "Self-Avoiding Walk",
        "2-D lattice polymer model — plot one chain, compute mean R² and Rg over many chains",
    )

    # ── Input parameters ──────────────────────────────────────────────
    # set(3,1,v)→B4=N,  set(4,1,v)→B5=n_chains,  set(5,1,v)→B6=seed
    s.set(2, 0, "Parameters")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    input_rows = [
        (3, "Chain length  N  (steps)",  40,   "0"),
        (4, "Number of chains",           150,  "0"),
        (5, "Random seed",                42,   "0"),
    ]
    for r, lbl, val, nfmt in input_rows:
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format=nfmt)

    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 220)
    s.col_width(1, 100)

    # Note on first input cell (row 3, col 1 = B4)
    s.note(
        3, 1,
        "N=40, chains=150 runs in <2 s.  "
        "Increase N to see the Flory exponent nu~0.75 emerge (R2 ~ N^{2*nu}).  "
        "Press Ctrl+Enter on A9 to rerun.",
        kind="note",
    )

    # ── Output labels (row 7 = sheet row 8) ───────────────────────────
    # set(7,0,...)→A8, set(7,1,...)→B8, set(7,2,...)→C8, set(7,3,...)→D8
    s.set(7, 0, "Mean end-to-end R²  (lattice²):")
    s.fmt(7, 0, bold=True, align="right")
    s.set(7, 1, "")   # filled by ks_set('B8', ...) from plot cell
    s.fmt(7, 1, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.0000")

    s.set(7, 2, "Mean Rg²  (lattice²):")
    s.fmt(7, 2, bold=True, align="right")
    s.set(7, 3, "")   # filled by ks_set('D8', ...) from plot cell
    s.fmt(7, 3, bg=PALETTE["band"], bold=True, align="center",
          number_format="0.0000")

    s.col_width(2, 180)
    s.col_width(3, 110)

    s.note(
        7, 1,
        "R2 = mean squared end-to-end distance.  "
        "Rg2 = mean squared radius of gyration.  "
        "Both written by the plot cell via ks_set.",
        kind="note",
    )

    # ── =PY plot cell (row 8 = sheet row 9, col 0 = A) ───────────────
    # Reads: B4=N, B5=n_chains, B6=seed
    # Writes: B8 (mean R²), D8 (mean Rg²)
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "N          = int(ks('B4'))",
        "n_chains   = int(ks('B5'))",
        "seed       = int(ks('B6'))",
        "rng = np.random.default_rng(seed)",
        "DIRS = np.array([[1,0],[-1,0],[0,1],[0,-1]], dtype=np.int32)",
        "",
        "def grow_saw(N, rng):",
        "    path = [(0, 0)]",
        "    visited = {(0, 0)}",
        "    for _ in range(N):",
        "        x, y = path[-1]",
        "        nbrs = [(x+dx, y+dy) for dx,dy in DIRS",
        "                if (x+dx, y+dy) not in visited]",
        "        if not nbrs:",
        "            return None",
        "        nxt = nbrs[int(rng.integers(len(nbrs)))]",
        "        path.append(nxt)",
        "        visited.add(nxt)",
        "    return path",
        "",
        "chains = []",
        "attempts = 0",
        "while len(chains) < n_chains and attempts < n_chains * 20:",
        "    c = grow_saw(N, rng)",
        "    attempts += 1",
        "    if c is not None:",
        "        chains.append(c)",
        "",
        "r2_list, rg2_list = [], []",
        "for c in chains:",
        "    pts = np.array(c, dtype=float)",
        "    r2_list.append(float(np.sum((pts[-1] - pts[0])**2)))",
        "    cm = pts.mean(axis=0)",
        "    rg2_list.append(float(np.mean(np.sum((pts - cm)**2, axis=1))))",
        "mean_r2  = round(float(np.mean(r2_list)),  4)",
        "mean_rg2 = round(float(np.mean(rg2_list)), 4)",
        "ks_set('B8', mean_r2)",
        "ks_set('D8', mean_rg2)",
        "",
        "pts = np.array(chains[0], dtype=float)",
        "fig, ax = plt.subplots(figsize=(5, 5))",
        "ax.plot(pts[:,0], pts[:,1], color='#4472c4', linewidth=1.6, alpha=0.8)",
        "ax.scatter([pts[0,0]], [pts[0,1]], color='#70ad47', s=60, zorder=5,",
        "           label='start')",
        "ax.scatter([pts[-1,0]], [pts[-1,1]], color='#ed7d31', s=60, zorder=5,",
        "           label='end')",
        "ax.set_aspect('equal')",
        "ax.set_xlabel('x  (lattice units)')",
        "ax.set_ylabel('y  (lattice units)')",
        "ax.set_title(f'SAW  N={N}  (one chain of {len(chains)} grown)')",
        "ax.legend(fontsize=9)",
        "ax.grid(True, alpha=0.25)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(8, 0, py_plot)

    # ── Equation ──────────────────────────────────────────────────────
    s.equation(
        r"\langle R^2 \rangle \sim N^{2\nu},\quad \nu \approx 0.75",
        at=(530, 50), fontsize=18, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(310, 52),
    )

    out = os.path.join(
        _REPO, "examples", "python", "Materials Science",
        "Self-Avoiding Walk.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
