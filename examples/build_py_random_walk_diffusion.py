"""Build "Random Walk Diffusion.ksheet" — a Python-cell materials science example.

Simulates many atoms performing a lattice random walk and computes the
mean-squared displacement (MSD) vs time step.  A second =PY cell fits the
MSD slope to return the estimated diffusion coefficient D.

Row/column mapping (0-based set() vs 1-based A1 references):
  set(r, c, v)  → sheet cell letter(c) + str(r+1)
  set(3, 1, v)  → B4
  set(4, 1, v)  → B5

Run:  python examples/build_py_random_walk_diffusion.py

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
    s = wb.add_sheet("Diffusion")

    # ── Title (rows 0-1, 0-based) ─────────────────────────────────────
    s.title_block(
        "Random Walk Diffusion",
        "Lattice random walk simulation — MSD grows linearly with time (Einstein relation)",
    )

    # ── Input parameters ──────────────────────────────────────────────
    # set(3,1,v)→B4, set(4,1,v)→B5, set(5,1,v)→B6, set(6,1,v)→B7
    s.set(2, 0, "Parameters")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    input_rows = [
        (3, "Number of atoms",    200,  "0"),
        (4, "Number of steps",    500,  "0"),
        (5, "Hop probability",    0.5,  "0.00"),
        (6, "Random seed",        42,   "0"),
    ]
    for r, lbl, val, nfmt in input_rows:
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format=nfmt)

    s.box(3, 0, 6, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 200)
    s.col_width(1, 100)

    # Note on first input cell B4 (0-based row 3, col 1)
    s.note(
        3, 1,
        "Edit num_atoms (e.g. 100-500), num_steps (200-1000), hop_prob "
        "(0-1), or seed, then press Ctrl+Enter on the plot cell (A10).",
        kind="note",
    )

    # ── Output label + result cell (row 8 = sheet row 9) ──────────────
    # D result will be written here by ks_set('E9', ...) from the plot cell
    # set(8,3,...)→D9, set(8,4,...)→E9
    s.set(8, 3, "Diffusion coefficient D  (lattice²/step):")
    s.fmt(8, 3, bold=True, align="right")
    s.set(8, 4, "")   # placeholder; ks_set fills it
    s.fmt(8, 4, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.000000")
    s.col_width(3, 260)
    s.col_width(4, 110)
    s.note(
        8, 4,
        "D = MSD_slope / (2d) where d=2.  "
        "For p_hop=0.5, D ≈ 0.25 lattice²/step.",
        kind="note",
    )

    # ── =PY plot cell (row 9 = sheet row 10, col 0 = A) ───────────────
    # Reads: B4=n_atoms, B5=n_steps, B6=p_hop, B7=seed
    # Writes D to E9 via ks_set
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "n_atoms = int(ks('B4'))",
        "n_steps = int(ks('B5'))",
        "p_hop   = float(ks('B6'))",
        "seed    = int(ks('B7'))",
        "rng = np.random.default_rng(seed)",
        "# 2-D lattice walk vectorised: shape (n_atoms, n_steps)",
        "r_rand = rng.random((n_atoms, n_steps))",
        "hop = r_rand < p_hop",
        "dx = rng.choice([-1, 1], size=(n_atoms, n_steps))",
        "dy = rng.choice([-1, 1], size=(n_atoms, n_steps))",
        "axis = rng.random((n_atoms, n_steps)) < 0.5",
        "step_x = np.where(hop & axis,  dx, 0)",
        "step_y = np.where(hop & ~axis, dy, 0)",
        "x = np.cumsum(step_x, axis=1)",
        "y = np.cumsum(step_y, axis=1)",
        "msd = np.mean(x**2 + y**2, axis=0)",
        "steps = np.arange(1, n_steps + 1)",
        "slope = float(np.polyfit(steps, msd, 1)[0])",
        "D_est = round(slope / 4.0, 6)",
        "ks_set('E9', D_est)",
        "fig, ax = plt.subplots(figsize=(6, 4))",
        "ax.plot(steps, msd, color='#4472c4', linewidth=1.8, label='MSD (sim)')",
        "ax.plot(steps, slope * steps, color='#ed7d31', linewidth=1.5,",
        "        linestyle='--', label=f'Linear fit  slope={slope:.4f}')",
        "ax.set_xlabel('Time step')",
        "ax.set_ylabel('MSD  (lattice units²)')",
        "ax.set_title(f'Mean-Squared Displacement  ({n_atoms} atoms, {n_steps} steps)')",
        "ax.legend(fontsize=9)",
        "ax.grid(True, alpha=0.35)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(9, 0, py_plot)
    s.set(9, 3, "MSD plot — edit inputs above, press Ctrl+Enter to rerun")
    s.fmt(9, 3, italic=True, font_color="#555555")

    # ── Equation (mathtext) ───────────────────────────────────────────
    s.equation(
        r"\langle r^2 \rangle = 4 D \, t",
        at=(540, 50), fontsize=20, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(220, 54),
    )

    out = os.path.join(
        _REPO, "examples", "python", "Materials Science",
        "Random Walk Diffusion.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
