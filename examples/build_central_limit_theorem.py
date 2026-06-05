"""Build "Central Limit Theorem" Python-cell example .ksheet.

Inputs: sample size per draw, number of draws.
=PY draws from a skewed (exponential) distribution, computes sample means,
and plots their histogram overlaid with a normal approximation -- demonstrating CLT.

Run:  python examples/build_central_limit_theorem.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ksheet_author import Workbook, PALETTE


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("CLT")

    # Title
    s.title_block(
        "Central Limit Theorem",
        "Sample means from a skewed distribution converge to normal as N grows",
    )

    # Explanation
    s.set(3, 0, "Underlying distribution: Exponential(lambda=1)  (mean=1, right-skewed)")
    s.fmt(3, 0, italic=True, font_color="#555555")
    s.col_width(0, 240)
    s.col_width(1, 120)

    # Input panel
    s.set(4, 0, "Parameters")
    s.fmt(4, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Sample size per draw  n", 30),
        ("Number of draws  M", 2000),
        ("Random seed", 99),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 5 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0")

    s.box(5, 0, 7, 1, color=PALETTE["accent"], width=1.0)

    s.note(
        5, 1,
        "Try n=1 (histogram = exponential shape) vs n=30 (histogram = bell curve). "
        "Press Ctrl+Enter on the Python cell (A10) after changing inputs.",
        kind="note",
    )

    # Python cell: CLT demonstration plot
    # B6=n, B7=M, B8=seed  (1-based)
    plot_code = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "n    = int(ks('B6'))",
        "M    = int(ks('B7'))",
        "seed = int(ks('B8'))",
        "rng  = np.random.default_rng(seed)",
        "# Draw M samples each of size n from Exponential(1)",
        "draws = rng.exponential(scale=1.0, size=(M, n))",
        "means = draws.mean(axis=1)",
        "# Theoretical normal approximation: mean=1, std=1/sqrt(n)",
        "mu_theory    = 1.0",
        "sigma_theory = 1.0 / np.sqrt(n)",
        "x = np.linspace(means.min(), means.max(), 300)",
        "pdf = np.exp(-0.5*((x - mu_theory)/sigma_theory)**2) / (sigma_theory * np.sqrt(2*np.pi))",
        "fig, ax = plt.subplots(figsize=(6, 4))",
        "ax.hist(means, bins=40, density=True, alpha=0.6,",
        "        color='#4472c4', edgecolor='white', label=f'Sample means  (n={n}, M={M})')",
        "ax.plot(x, pdf, 'r-', linewidth=2, label=f'Normal(1, 1/sqrt({n}))')",
        "ax.set_xlabel('Sample mean')",
        "ax.set_ylabel('Density')",
        "ax.set_title('Central Limit Theorem')",
        "ax.legend()",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(9, 0, plot_code)
    s.set(9, 2, "<-- Plot cell (Ctrl+Enter to rerun)")
    s.fmt(9, 2, italic=True, font_color="#777777")

    # Python cell: key numerical summary
    summary_code = "\n".join([
        "=PY",
        "import numpy as np",
        "n    = int(ks('B6'))",
        "M    = int(ks('B7'))",
        "seed = int(ks('B8'))",
        "rng  = np.random.default_rng(seed)",
        "draws = rng.exponential(scale=1.0, size=(M, n))",
        "means = draws.mean(axis=1)",
        "sigma_theory = 1.0 / np.sqrt(n)",
        "[",
        "    ['Quantity', 'Observed', 'Theoretical'],",
        "    ['Mean of means',  round(float(np.mean(means)), 5), 1.0],",
        "    ['Std of means',   round(float(np.std(means)), 5),  round(sigma_theory, 5)],",
        "]",
    ])
    s.formula(11, 0, summary_code)
    s.note(
        11, 0,
        "Spills observed vs theoretical standard error of the mean.",
        kind="note",
    )

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "python", "Statistics", "Central Limit Theorem.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())