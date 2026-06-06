"""Build "Birthday Paradox.ksheet" — a Python-cell simulation example.

=PY cells estimate the probability that at least two people in a group
share a birthday by Monte Carlo simulation; a second =PY cell plots the
empirical probability vs group size alongside the theoretical curve.

Run:  python examples/build_sim_birthday_paradox.py

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
    s = wb.add_sheet("Birthday Paradox")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Birthday Paradox",
                  "Monte Carlo estimate of shared-birthday probability "
                  "— edit inputs then press Ctrl+Enter")

    # ── Input parameters ──────────────────────────────────────────────
    # B4=group size, B5=trials, B6=seed
    s.set(3, 0, "Group size  n")
    s.set(3, 1, 23)
    s.set(4, 0, "Simulation trials")
    s.set(4, 1, 10000)
    s.set(5, 0, "Random seed")
    s.set(5, 1, 17)

    for r in range(3, 6):
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0")

    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 200)
    s.col_width(1, 90)

    s.note(3, 1,
           "Try group size 23 (~50 %), 50 (~97 %), or 70 (~99.9 %). "
           "Press Ctrl+Enter on the =PY cells in rows 8 and 9 to rerun.",
           kind="note")

    # ── =PY scalar: probability for the given group size ──────────────
    s.set(7, 3, "P(shared birthday):")
    s.fmt(7, 3, bold=True, align="right")
    s.col_width(3, 200)
    s.col_width(4, 110)

    py_prob = "\n".join([
        "=PY",
        "import numpy as np",
        "n      = int(ks('B4'))",
        "trials = int(ks('B5'))",
        "seed   = int(ks('B6'))",
        "rng    = np.random.default_rng(seed)",
        "# Sample birthdays (0-364) for each group; check for duplicates",
        "groups  = rng.integers(0, 365, size=(trials, n))",
        "# A group has a shared birthday if the number of unique days < n",
        "shared  = np.array([len(np.unique(row)) < n for row in groups])",
        "p_hat   = float(shared.mean())",
        "round(p_hat, 4)",
    ])
    s.formula(7, 4, py_prob)
    s.fmt(7, 4, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.0000")

    # ── =PY plot: empirical + theoretical curve vs group size ─────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "trials  = int(ks('B5'))",
        "seed    = int(ks('B6'))",
        "rng     = np.random.default_rng(seed)",
        "sizes   = np.arange(1, 71)",
        "# Theoretical probability: 1 - prod_{k=0}^{n-1} (365-k)/365",
        "p_theor = np.zeros(len(sizes))",
        "for idx, n in enumerate(sizes):",
        "    log_no_match = np.sum(np.log((365 - np.arange(n)) / 365))",
        "    p_theor[idx] = 1.0 - np.exp(log_no_match)",
        "# Empirical: run fewer trials per group to keep it fast",
        "t_quick = min(trials, 3000)",
        "p_emp   = np.zeros(len(sizes))",
        "for idx, n in enumerate(sizes):",
        "    groups  = rng.integers(0, 365, size=(t_quick, int(n)))",
        "    shared  = np.array([len(np.unique(row)) < int(n)",
        "                        for row in groups])",
        "    p_emp[idx] = shared.mean()",
        "fig, ax = plt.subplots(figsize=(7, 4))",
        "ax.plot(sizes, p_theor, color='#4472c4', lw=2.5,",
        "        label='Theoretical')",
        "ax.scatter(sizes, p_emp, s=15, color='#ed7d31', alpha=0.7,",
        "           label=f'Simulated ({t_quick} trials each)')",
        "ax.axhline(0.5, color='grey', ls='--', lw=1, label='50 %')",
        "ax.axvline(23, color='grey', ls=':', lw=1, label='n=23')",
        "ax.set_xlabel('Group size  n')",
        "ax.set_ylabel('P(at least one shared birthday)')",
        "ax.set_title('Birthday Paradox')",
        "ax.set_ylim(0, 1)",
        "ax.legend(fontsize=8)",
        "ax.grid(True, alpha=0.3)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(8, 0, py_plot)

    out = os.path.join(_REPO, "examples", "python", "Simulations",
                       "Birthday Paradox.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
