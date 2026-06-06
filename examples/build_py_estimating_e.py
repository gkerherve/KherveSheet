"""Build "Estimating e.ksheet" — a Python-cell simulation example.

=PY cells estimate Euler's number e by the expected number of uniform(0,1)
draws needed to exceed 1, return the estimate, and plot convergence vs trials.

Run:  python examples/build_py_estimating_e.py

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
    s = wb.add_sheet("Estimating e")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Estimating Euler's Number e",
                  "E[# of Uniform(0,1) draws until sum > 1] = e")

    # ── Input parameters ───────────────────────────────────────────────
    s.set(3, 0, "Number of trials N")
    s.set(3, 1, 50000)
    s.set(4, 0, "Seed")
    s.set(4, 1, 314)
    s.fmt(3, 0, bold=True)
    s.fmt(4, 0, bold=True)
    s.fmt(3, 1, bg=PALETTE["warn"], align="center", number_format="0")
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0")
    s.box(3, 0, 4, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 180)
    s.col_width(1, 90)

    s.note(3, 1,
           "Edit N (e.g. 1000, 100000) then press Ctrl+Enter on both "
           "=PY cells to update the estimate and convergence plot.",
           kind="note")

    # ── =PY cell: convergence plot ────────────────────────────────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "N = int(ks('B4'))",
        "seed = int(ks('B5'))",
        "rng = np.random.default_rng(seed)",
        "# For each trial, draw uniforms until cumulative sum exceeds 1",
        "# The count needed is the estimate contribution",
        "counts = np.zeros(N, dtype=np.int64)",
        "for i in range(N):",
        "    s_val = 0.0",
        "    k = 0",
        "    while s_val <= 1.0:",
        "        s_val += rng.random()",
        "        k += 1",
        "    counts[i] = k",
        "# Running mean of counts converges to e",
        "running_mean = np.cumsum(counts) / np.arange(1, N + 1)",
        "# Subsample for plotting (max 2000 points for clarity)",
        "step = max(1, N // 2000)",
        "idx = np.arange(1, N + 1, step)",
        "fig, ax = plt.subplots(figsize=(6, 4))",
        "ax.plot(idx, running_mean[idx - 1], color='#4472c4', linewidth=1.5,",
        "        label='Running estimate of e')",
        "ax.axhline(np.e, color='#ed7d31', linewidth=2, linestyle='--',",
        "           label=f'True e = {np.e:.6f}')",
        "ax.set_xlabel('Number of trials')",
        "ax.set_ylabel('Estimate of e')",
        "ax.set_title(f'Estimating e  (N = {N},  final = {running_mean[-1]:.5f})')",
        "ax.set_ylim(2.0, 3.5)",
        "ax.legend(fontsize=9)",
        "ax.grid(True, alpha=0.4)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(6, 0, py_plot)

    # ── =PY cell: numerical results ───────────────────────────────────
    s.set(6, 4, "Estimated e:")
    s.set(7, 4, "True e:")
    s.set(8, 4, "Error (%):")
    for r in range(6, 9):
        s.fmt(r, 4, bold=True, align="right")
    s.col_width(4, 130)
    s.col_width(5, 110)

    py_result = "\n".join([
        "=PY",
        "import numpy as np",
        "N = int(ks('B4'))",
        "seed = int(ks('B5'))",
        "rng = np.random.default_rng(seed)",
        "counts = np.zeros(N, dtype=np.int64)",
        "for i in range(N):",
        "    s_val = 0.0",
        "    k = 0",
        "    while s_val <= 1.0:",
        "        s_val += rng.random()",
        "        k += 1",
        "    counts[i] = k",
        "e_est = counts.mean()",
        "err_pct = abs(e_est - np.e) / np.e * 100",
        "ks_set('F7', round(e_est, 6))",
        "ks_set('F8', round(np.e, 6))",
        "ks_set('F9', round(err_pct, 4))",
        "round(e_est, 6)",
    ])
    s.formula(6, 5, py_result)
    s.fmt(6, 5, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.000000")
    s.fmt(7, 5, bg=PALETTE["band"], bold=True, align="center",
          number_format="0.000000")
    s.fmt(8, 5, bg=PALETTE["warn"], bold=True, align="center",
          number_format="0.0000")
    s.box(6, 4, 8, 5, color=PALETTE["header"], width=1.0)

    s.note(6, 0,
           "The running mean of counts-until-sum>1 converges to e = 2.71828... "
           "Larger N gives a tighter estimate.",
           kind="note")

    out = os.path.join(_REPO, "examples", "python", "Simulations",
                       "Estimating e.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
