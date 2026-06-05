"""Build "Normal Distribution" Python-cell example .ksheet.

Inputs: mean, standard deviation, sample size N -- all editable cells.
=PY cell draws a sample (reproducible seed), plots histogram + PDF overlay.
A second =PY cell spills summary statistics.

Run:  python examples/build_normal_distribution.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ksheet_author import Workbook, PALETTE


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Normal Distribution")

    # Title
    s.title_block(
        "Normal Distribution",
        "Draw a random sample and compare its histogram to the theoretical PDF",
    )

    # Input panel
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Mean  mu", 0.0),
        ("Std dev  sigma", 1.0),
        ("Sample size  N", 500),
        ("Random seed", 42),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.##")

    s.box(4, 0, 7, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 160)
    s.col_width(1, 100)

    s.note(
        4, 1,
        "Edit mean (B5), std dev (B6), N (B7) or seed (B8), "
        "then press Ctrl+Enter on the Python cell (A10) to rerun.",
        kind="note",
    )

    # Python cell: plot
    # Inputs live at: B5=mean, B6=sigma, B7=N, B8=seed  (1-based)
    plot_code = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "mu    = ks('B5')",
        "sigma = ks('B6')",
        "N     = int(ks('B7'))",
        "seed  = int(ks('B8'))",
        "rng   = np.random.default_rng(seed)",
        "data  = rng.normal(mu, sigma, N)",
        "fig, ax = plt.subplots(figsize=(6, 4))",
        "ax.hist(data, bins=30, density=True, alpha=0.6,",
        "        color='#4472c4', edgecolor='white', label='Sample')",
        "x = np.linspace(mu - 4*sigma, mu + 4*sigma, 300)",
        "pdf = np.exp(-0.5*((x - mu)/sigma)**2) / (sigma * np.sqrt(2*np.pi))",
        "ax.plot(x, pdf, 'r-', linewidth=2, label='Theoretical PDF')",
        "ax.set_xlabel('Value')",
        "ax.set_ylabel('Density')",
        "ax.set_title(f'Normal Distribution  mu={mu},  sigma={sigma},  N={N}')",
        "ax.legend()",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(9, 0, plot_code)
    s.set(9, 2, "<-- Plot cell (Ctrl+Enter to rerun)")
    s.fmt(9, 2, italic=True, font_color="#777777")

    # Python cell: summary statistics
    stats_code = "\n".join([
        "=PY",
        "import numpy as np",
        "mu    = ks('B5')",
        "sigma = ks('B6')",
        "N     = int(ks('B7'))",
        "seed  = int(ks('B8'))",
        "rng   = np.random.default_rng(seed)",
        "data  = rng.normal(mu, sigma, N)",
        "[",
        "    ['Statistic', 'Sample', 'Theoretical'],",
        "    ['Mean',      round(float(np.mean(data)), 4),   mu],",
        "    ['Std Dev',   round(float(np.std(data, ddof=1)), 4), sigma],",
        "    ['Min',       round(float(np.min(data)), 4),    ''],",
        "    ['Max',       round(float(np.max(data)), 4),    ''],",
        "]",
    ])
    s.formula(11, 0, stats_code)
    s.note(
        11, 0,
        "This cell spills a table of sample vs theoretical statistics.",
        kind="note",
    )

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "python", "Statistics", "Normal Distribution.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())