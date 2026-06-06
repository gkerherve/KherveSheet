"""Build "Ising Model.ksheet" — 2-D Ising Metropolis simulation.

=PY cells run a checkerboard-vectorised Metropolis sweep, plot the final
spin configuration with imshow, and return the average magnetization.

Run:  python examples/build_py_ising_model.py

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
    s = wb.add_sheet("Ising Model")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("2-D Ising Model",
                  "Metropolis Monte Carlo — edit T and press Ctrl+Enter")

    # ── Input parameters ──────────────────────────────────────────────
    inputs = [
        ("Lattice size  L",    24),
        ("Temperature  T  (J/k_B)", 2.27),
        ("Number of sweeps",   300),
        ("Random seed",        42),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(3, 0, 6, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 200)
    s.col_width(1, 90)

    s.note(3, 1,
           "T_c ≈ 2.269 J/k_B for the 2-D Ising model.\n"
           "Try T < 2.27 (ordered) or T > 2.27 (disordered).\n"
           "Edit inputs and press Ctrl+Enter on the =PY cell.",
           kind="note")

    # ── =PY cell: run simulation + plot spin lattice ──────────────────
    # Cell at row 8 (0-based) → sheet row 9
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "L      = int(ks('B4'))",
        "T      = float(ks('B5'))",
        "sweeps = int(ks('B6'))",
        "seed   = int(ks('B7'))",
        "rng = np.random.default_rng(seed)",
        "# Initialise random +/-1 spins",
        "spins = rng.choice([-1, 1], size=(L, L)).astype(np.int8)",
        "beta = 1.0 / max(T, 1e-6)",
        "# Precompute Boltzmann factors for dE in {4, 8} (only > 0 needed)",
        "exp_neg = {dE: np.exp(-beta * dE) for dE in [4, 8]}",
        "# Checkerboard Metropolis: vectorised sublattice sweeps",
        "rows = np.arange(L)",
        "cols = np.arange(L)",
        "R, C = np.meshgrid(rows, cols, indexing='ij')",
        "for _ in range(sweeps):",
        "    for parity in (0, 1):",
        "        mask = ((R + C) % 2 == parity)",
        "        nb = (spins[(R-1) % L, C] + spins[(R+1) % L, C]",
        "            + spins[R, (C-1) % L] + spins[R, (C+1) % L])",
        "        dE = 2 * spins * nb",
        "        accept = np.where(",
        "            dE <= 0,",
        "            True,",
        "            rng.random((L, L)) < np.where(dE == 4, exp_neg[4], exp_neg[8])",
        "        )",
        "        flip = mask & accept",
        "        spins[flip] = -spins[flip]",
        "mag = float(np.abs(spins.mean()))",
        "fig, ax = plt.subplots(figsize=(5, 5))",
        "ax.imshow(spins, cmap='RdBu', vmin=-1, vmax=1, interpolation='nearest')",
        "ax.set_title(f'L={L},  T={T:.3f},  |m|={mag:.3f}',  fontsize=11)",
        "ax.set_xlabel('column  j')",
        "ax.set_ylabel('row  i')",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(8, 0, py_plot)

    # ── =PY cell: return average |magnetization| per spin ────────────
    s.set(8, 4, "Mean |m| per spin:")
    s.fmt(8, 4, bold=True, align="right")
    s.col_width(4, 165)

    py_mag = "\n".join([
        "=PY",
        "import numpy as np",
        "L      = int(ks('B4'))",
        "T      = float(ks('B5'))",
        "sweeps = int(ks('B6'))",
        "seed   = int(ks('B7'))",
        "rng = np.random.default_rng(seed)",
        "spins = rng.choice([-1, 1], size=(L, L)).astype(np.int8)",
        "beta = 1.0 / max(T, 1e-6)",
        "exp_neg = {dE: np.exp(-beta * dE) for dE in [4, 8]}",
        "rows = np.arange(L)",
        "cols = np.arange(L)",
        "R, C = np.meshgrid(rows, cols, indexing='ij')",
        "for _ in range(sweeps):",
        "    for parity in (0, 1):",
        "        mask = ((R + C) % 2 == parity)",
        "        nb = (spins[(R-1) % L, C] + spins[(R+1) % L, C]",
        "            + spins[R, (C-1) % L] + spins[R, (C+1) % L])",
        "        dE = 2 * spins * nb",
        "        accept = np.where(",
        "            dE <= 0,",
        "            True,",
        "            rng.random((L, L)) < np.where(dE == 4, exp_neg[4], exp_neg[8])",
        "        )",
        "        flip = mask & accept",
        "        spins[flip] = -spins[flip]",
        "round(float(np.abs(spins.mean())), 4)",
    ])
    s.formula(8, 5, py_mag)
    s.fmt(8, 5, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.0000")
    s.box(8, 4, 8, 5, color=PALETTE["header"], width=1.0)
    s.col_width(5, 100)

    s.note(8, 0,
           "The colour map shows +1 spins (blue) and -1 spins (red).\n"
           "Below T_c the lattice develops large domains.",
           kind="note")

    # ── Equation: Boltzmann acceptance criterion ──────────────────────
    s.equation(
        r"P(\mathrm{flip}) = \min\!\left(1,\; e^{-\Delta E / k_B T}\right)",
        at=(520, 300), fontsize=16, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(380, 52),
    )

    out = os.path.join(_REPO, "examples", "python", "Materials Science",
                       "Ising Model.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
