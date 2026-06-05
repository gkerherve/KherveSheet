"""Build "Random Walk" Python-cell example .ksheet.

Inputs: number of steps, number of walks (editable cells).
=PY simulates 1-D random walks, plots several paths, and a second =PY
cell returns the RMS displacement versus the sqrt(N) prediction.

Run:  python examples/build_random_walk.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ksheet_author import Workbook, PALETTE


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Random Walk")

    # Title
    s.title_block(
        "Random Walk",
        "1-D random walks: each step is +1 or -1 with equal probability",
    )

    # Input panel
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    s.col_width(0, 180)
    s.col_width(1, 110)

    inputs = [
        ("Number of steps  N", 200),
        ("Number of walks  W", 50),
        ("Walks to plot", 8),
        ("Random seed", 17),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0")

    s.box(4, 0, 7, 1, color=PALETTE["accent"], width=1.0)

    s.note(
        4, 1,
        "Edit steps (B5), walks (B6), walks to plot (B7), seed (B8). "
        "Press Ctrl+Enter on the Python cells to rerun.",
        kind="note",
    )

    # Python cell: plot walks
    # B5=N, B6=W, B7=n_plot, B8=seed
    plot_code = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "N      = int(ks('B5'))",
        "W      = int(ks('B6'))",
        "n_plot = int(ks('B7'))",
        "seed   = int(ks('B8'))",
        "rng    = np.random.default_rng(seed)",
        "steps  = rng.choice([-1, 1], size=(W, N))",
        "walks  = np.cumsum(steps, axis=1)",
        "t      = np.arange(1, N + 1)",
        "rms    = np.sqrt(np.mean(walks**2, axis=0))",
        "fig, ax = plt.subplots(figsize=(7, 4))",
        "colors = plt.cm.tab10(np.linspace(0, 1, min(n_plot, W)))",
        "for i in range(min(n_plot, W)):",
        "    ax.plot(t, walks[i], linewidth=0.8, alpha=0.7, color=colors[i])",
        "ax.plot(t, rms, 'k--', linewidth=2, label='RMS displacement')",
        "ax.plot(t, np.sqrt(t), 'r-', linewidth=2, label='sqrt(N) prediction')",
        "ax.set_xlabel('Step')",
        "ax.set_ylabel('Position')",
        "ax.set_title(f'Random Walks  (N={N}, W={W})')",
        "ax.legend()",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(9, 0, plot_code)
    s.set(9, 2, "<-- Plot cell (Ctrl+Enter to rerun)")
    s.fmt(9, 2, italic=True, font_color="#777777")

    # Python cell: RMS summary
    rms_code = "\n".join([
        "=PY",
        "import numpy as np",
        "N    = int(ks('B5'))",
        "W    = int(ks('B6'))",
        "seed = int(ks('B8'))",
        "rng  = np.random.default_rng(seed)",
        "steps = rng.choice([-1, 1], size=(W, N))",
        "walks = np.cumsum(steps, axis=1)",
        "rms_final = float(np.sqrt(np.mean(walks[:, -1]**2)))",
        "theoretical = float(np.sqrt(N))",
        "[",
        "    ['Quantity', 'Value'],",
        "    ['RMS displacement at step N',  round(rms_final, 4)],",
        "    ['Theoretical sqrt(N)',          round(theoretical, 4)],",
        "    ['Ratio observed / predicted',   round(rms_final / theoretical, 4)],",
        "]",
    ])
    s.formula(11, 0, rms_code)
    s.note(
        11, 0,
        "Spills the RMS final displacement and the sqrt(N) prediction.",
        kind="note",
    )

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "python", "Statistics", "Random Walk.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())