"""Build "Gambler's Ruin.ksheet" — a Python-cell simulation example.

=PY cells simulate many gambler trajectories, estimate the probability of
reaching the target before ruin, and plot several capital trajectories.

Run:  python examples/build_py_gamblers_ruin.py

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
    s = wb.add_sheet("Gamblers Ruin")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Gambler's Ruin",
                  "Probability of reaching a target before going broke")

    # ── Input parameters ───────────────────────────────────────────────
    inputs = [
        ("Starting capital",  10),
        ("Win probability p",  0.48),
        ("Target capital",     20),
        ("Number of games",   200),
        ("Seed",               55),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(3, 0, 7, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 175)
    s.col_width(1, 90)

    s.note(3, 1,
           "Try p=0.5 (fair game) vs p=0.45 (casino edge). "
           "Press Ctrl+Enter on both =PY cells to update.",
           kind="note")

    # ── =PY cell: simulate trajectories + plot ────────────────────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "start  = int(ks('B4'))",
        "p      = float(ks('B5'))",
        "target = int(ks('B6'))",
        "n_games = int(ks('B7'))",
        "seed   = int(ks('B8'))",
        "rng = np.random.default_rng(seed)",
        "n_show = min(n_games, 40)  # plot at most 40 trajectories",
        "reached = 0",
        "all_paths = []",
        "for _ in range(n_games):",
        "    capital = start",
        "    path = [capital]",
        "    while 0 < capital < target:",
        "        capital += 1 if rng.random() < p else -1",
        "        path.append(capital)",
        "        if len(path) > 5000:",
        "            break  # safety cap",
        "    if capital >= target:",
        "        reached += 1",
        "    all_paths.append(path)",
        "prob_sim = reached / n_games",
        "# Theoretical ruin probability (p != 0.5 case)",
        "q = 1 - p",
        "if abs(p - 0.5) < 1e-9:",
        "    prob_theory = start / target",
        "else:",
        "    ratio = q / p",
        "    prob_theory = (1 - ratio**start) / (1 - ratio**target)",
        "fig, ax = plt.subplots(figsize=(7, 4))",
        "for i, path in enumerate(all_paths[:n_show]):",
        "    won = path[-1] >= target",
        "    col = '#4472c4' if won else '#ed7d31'",
        "    ax.plot(path, color=col, alpha=0.35, linewidth=0.9)",
        "ax.axhline(target, color='#a9d18e', linewidth=2, linestyle='--',",
        "           label=f'Target = {target}')",
        "ax.axhline(0, color='#c00000', linewidth=1.5, linestyle='--',",
        "           label='Ruin = 0')",
        "ax.set_xlabel('Step')",
        "ax.set_ylabel('Capital')",
        "ax.set_title(",
        "    f'p={p:.2f}  Sim P(win)={prob_sim:.3f}  Theory={prob_theory:.3f}'",
        ")",
        "from matplotlib.patches import Patch",
        "ax.legend(handles=[",
        "    Patch(color='#4472c4', label='Reached target'),",
        "    Patch(color='#ed7d31', label='Ruined'),",
        "    Patch(color='#a9d18e', label=f'Target={target}'),",
        "    Patch(color='#c00000', label='Ruin'),",
        "], fontsize=8)",
        "ax.grid(True, alpha=0.3)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(9, 0, py_plot)

    # ── =PY cell: numerical results ───────────────────────────────────
    s.set(9, 4, "Simulated P(win):")
    s.set(10, 4, "Theoretical P(win):")
    s.set(11, 4, "Difference:")
    for r in range(9, 12):
        s.fmt(r, 4, bold=True, align="right")
    s.col_width(4, 160)
    s.col_width(5, 110)

    py_result = "\n".join([
        "=PY",
        "import numpy as np",
        "start  = int(ks('B4'))",
        "p      = float(ks('B5'))",
        "target = int(ks('B6'))",
        "n_games = int(ks('B7'))",
        "seed   = int(ks('B8'))",
        "rng = np.random.default_rng(seed)",
        "reached = 0",
        "for _ in range(n_games):",
        "    capital = start",
        "    steps = 0",
        "    while 0 < capital < target and steps < 5000:",
        "        capital += 1 if rng.random() < p else -1",
        "        steps += 1",
        "    if capital >= target:",
        "        reached += 1",
        "prob_sim = reached / n_games",
        "q = 1 - p",
        "if abs(p - 0.5) < 1e-9:",
        "    prob_theory = start / target",
        "else:",
        "    ratio = q / p",
        "    prob_theory = (1 - ratio**start) / (1 - ratio**target)",
        "diff = prob_sim - prob_theory",
        "ks_set('F10', round(prob_sim, 4))",
        "ks_set('F11', round(prob_theory, 4))",
        "ks_set('F12', round(diff, 4))",
        "round(prob_sim, 4)",
    ])
    s.formula(9, 5, py_result)
    s.fmt(9, 5, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.0000")
    s.fmt(10, 5, bg=PALETTE["band"], bold=True, align="center",
          number_format="0.0000")
    s.fmt(11, 5, bg=PALETTE["warn"], bold=True, align="center",
          number_format="0.0000")
    s.box(9, 4, 11, 5, color=PALETTE["header"], width=1.0)

    s.note(9, 0,
           "Blue = gambler reached target; orange = gambler went broke. "
           "Shows up to 40 sample trajectories.",
           kind="note")

    out = os.path.join(_REPO, "examples", "python", "Simulations",
                       "Gambler's Ruin.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
