"""Build "Dice Law of Large Numbers.ksheet" — a Python-cell simulation example.

=PY cells simulate rolling a die, plot the running average converging to 3.5,
and a second =PY cell plots a histogram of face counts.

Run:  python examples/build_py_dice_lln.py

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
    s = wb.add_sheet("Dice LLN")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Dice — Law of Large Numbers",
                  "Running average of a fair die converges to 3.5")

    # ── Input parameters ───────────────────────────────────────────────
    s.set(3, 0, "Number of rolls N")
    s.set(3, 1, 2000)
    s.set(4, 0, "Seed")
    s.set(4, 1, 7)
    s.fmt(3, 0, bold=True)
    s.fmt(4, 0, bold=True)
    s.fmt(3, 1, bg=PALETTE["warn"], align="center", number_format="0")
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0")
    s.box(3, 0, 4, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 180)
    s.col_width(1, 90)

    s.note(3, 1,
           "Edit N (e.g. 100, 500, 5000) then press Ctrl+Enter on both "
           "=PY cells to update the plots.",
           kind="note")

    # ── =PY cell 1: running-average convergence plot ──────────────────
    py_lln = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "N = int(ks('B4'))",
        "seed = int(ks('B5'))",
        "rng = np.random.default_rng(seed)",
        "rolls = rng.integers(1, 7, size=N)  # 1..6 inclusive",
        "cumavg = np.cumsum(rolls) / np.arange(1, N + 1)",
        "fig, ax = plt.subplots(figsize=(6, 4))",
        "ax.plot(np.arange(1, N + 1), cumavg, color='#4472c4', linewidth=1.5,",
        "        label='Running average')",
        "ax.axhline(3.5, color='#ed7d31', linewidth=2, linestyle='--',",
        "           label='True mean = 3.5')",
        "ax.set_xlabel('Number of rolls')",
        "ax.set_ylabel('Running average')",
        "ax.set_title(f'Law of Large Numbers  (N = {N})')",
        "ax.set_ylim(1, 6)",
        "ax.legend(fontsize=9)",
        "ax.grid(True, alpha=0.4)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(6, 0, py_lln)

    # ── =PY cell 2: face-count histogram ─────────────────────────────
    s.set(6, 4, "Face distribution:")
    s.fmt(6, 4, bold=True, font_color=PALETTE["header"])

    py_hist = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "N = int(ks('B4'))",
        "seed = int(ks('B5'))",
        "rng = np.random.default_rng(seed)",
        "rolls = rng.integers(1, 7, size=N)",
        "faces = np.arange(1, 7)",
        "counts = np.array([(rolls == f).sum() for f in faces])",
        "expected = N / 6",
        "fig, ax = plt.subplots(figsize=(4, 3.5))",
        "colors = ['#4472c4', '#ed7d31', '#a9d18e', '#ffc000', '#9dc3e6', '#c00000']",
        "ax.bar(faces, counts, color=colors, edgecolor='white', linewidth=0.8)",
        "ax.axhline(expected, color='#555555', linewidth=1.5, linestyle='--',",
        "           label=f'Expected = {expected:.0f}')",
        "ax.set_xlabel('Die face')",
        "ax.set_ylabel('Count')",
        "ax.set_title(f'Face counts  (N = {N})')",
        "ax.set_xticks(faces)",
        "ax.legend(fontsize=9)",
        "ax.grid(True, axis='y', alpha=0.4)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(7, 4, py_hist)
    s.col_width(4, 160)

    s.note(6, 0,
           "Left: running average. Right: histogram of face counts. "
           "Both converge to uniformity as N grows.",
           kind="note")

    out = os.path.join(_REPO, "examples", "python", "Simulations",
                       "Dice Law of Large Numbers.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
