"""Build "Diffusion-Limited Aggregation.ksheet" — DLA fractal growth.

=PY cells grow a DLA cluster from a central seed by random-walking
sticky particles on a bounded grid and plot the aggregate.

Run:  python examples/build_py_dla.py

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
    s = wb.add_sheet("DLA")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Diffusion-Limited Aggregation",
                  "Fractal cluster grown from a central seed particle")

    # ── Input parameters ──────────────────────────────────────────────
    inputs = [
        ("Grid size  (odd)",  101),
        ("Number of walkers", 1200),
        ("Random seed",        42),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0")
    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 185)
    s.col_width(1, 90)

    s.note(3, 1,
           "Walkers are launched from a random point on the boundary\n"
           "and stick when they touch the cluster.\n"
           "Max walkers: 1500; grid size ≤ 101 to stay fast.\n"
           "Edit and press Ctrl+Enter on the =PY cell.",
           kind="note")

    # ── =PY cell: grow DLA cluster + plot ────────────────────────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "N_raw  = int(ks('B4'))",
        "walkers = int(ks('B5'))",
        "seed   = int(ks('B6'))",
        "# Clamp sizes to keep runtime safe",
        "N = min(max(N_raw | 1, 11), 101)   # ensure odd, cap at 101",
        "walkers = min(walkers, 1500)",
        "rng = np.random.default_rng(seed)",
        "grid = np.zeros((N, N), dtype=np.int32)",
        "cx = cy = N // 2",
        "grid[cx, cy] = 1",
        "# Direction arrays for fast neighbour lookup",
        "dr = np.array([-1, 1,  0, 0])",
        "dc = np.array([ 0, 0, -1, 1])",
        "for _ in range(walkers):",
        "    # Launch from a random edge cell",
        "    edge = rng.integers(0, 4)",
        "    if edge == 0:",
        "        r, c = 0, rng.integers(0, N)",
        "    elif edge == 1:",
        "        r, c = N-1, rng.integers(0, N)",
        "    elif edge == 2:",
        "        r, c = rng.integers(0, N), 0",
        "    else:",
        "        r, c = rng.integers(0, N), N-1",
        "    # Random walk until sticking or leaving the grid",
        "    for _step in range(N * N * 4):",
        "        d = rng.integers(0, 4)",
        "        nr, nc = r + dr[d], c + dc[d]",
        "        if nr < 0 or nr >= N or nc < 0 or nc >= N:",
        "            break   # wandered off grid — abandon",
        "        r, c = nr, nc",
        "        # Check if adjacent to cluster",
        "        for k in range(4):",
        "            ar, ac = r + dr[k], c + dc[k]",
        "            if 0 <= ar < N and 0 <= ac < N and grid[ar, ac]:",
        "                grid[r, c] = 1",
        "                break",
        "        if grid[r, c]:",
        "            break",
        "n_stuck = int(grid.sum()) - 1   # exclude seed",
        "fig, ax = plt.subplots(figsize=(5, 5))",
        "ax.imshow(grid, cmap='inferno', interpolation='nearest')",
        "ax.set_title(f'DLA  N={N},  stuck={n_stuck}', fontsize=11)",
        "ax.set_xlabel('column  j')",
        "ax.set_ylabel('row  i')",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(8, 0, py_plot)

    # ── =PY cell: return number of stuck particles ────────────────────
    s.set(8, 4, "Particles stuck:")
    s.fmt(8, 4, bold=True, align="right")
    s.col_width(4, 145)

    py_count = "\n".join([
        "=PY",
        "import numpy as np",
        "N_raw   = int(ks('B4'))",
        "walkers = int(ks('B5'))",
        "seed    = int(ks('B6'))",
        "N = min(max(N_raw | 1, 11), 101)",
        "walkers = min(walkers, 1500)",
        "rng = np.random.default_rng(seed)",
        "grid = np.zeros((N, N), dtype=np.int32)",
        "cx = cy = N // 2",
        "grid[cx, cy] = 1",
        "dr = np.array([-1, 1,  0, 0])",
        "dc = np.array([ 0, 0, -1, 1])",
        "for _ in range(walkers):",
        "    edge = rng.integers(0, 4)",
        "    if edge == 0:",
        "        r, c = 0, rng.integers(0, N)",
        "    elif edge == 1:",
        "        r, c = N-1, rng.integers(0, N)",
        "    elif edge == 2:",
        "        r, c = rng.integers(0, N), 0",
        "    else:",
        "        r, c = rng.integers(0, N), N-1",
        "    for _step in range(N * N * 4):",
        "        d = rng.integers(0, 4)",
        "        nr, nc = r + dr[d], c + dc[d]",
        "        if nr < 0 or nr >= N or nc < 0 or nc >= N:",
        "            break",
        "        r, c = nr, nc",
        "        for k in range(4):",
        "            ar, ac = r + dr[k], c + dc[k]",
        "            if 0 <= ar < N and 0 <= ac < N and grid[ar, ac]:",
        "                grid[r, c] = 1",
        "                break",
        "        if grid[r, c]:",
        "            break",
        "int(grid.sum()) - 1",
    ])
    s.formula(8, 5, py_count)
    s.fmt(8, 5, bg=PALETTE["good"], bold=True, align="center",
          number_format="0")
    s.box(8, 4, 8, 5, color=PALETTE["header"], width=1.0)
    s.col_width(5, 80)

    s.note(8, 0,
           "The branching fractal structure arises because walkers\n"
           "are more likely to hit protruding tips than re-entrant gaps.",
           kind="note")

    # ── Equation: DLA fractal dimension ──────────────────────────────
    s.equation(
        r"D_f \approx 1.71\quad(\mathrm{2D\ DLA})",
        at=(520, 300), fontsize=16, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(280, 48),
    )

    out = os.path.join(_REPO, "examples", "python", "Materials Science",
                       "Diffusion-Limited Aggregation.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
