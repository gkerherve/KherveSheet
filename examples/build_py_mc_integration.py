"""Build "Monte Carlo Integration.ksheet" — a Python-cell simulation example.

=PY cells estimate the integral of f(x)=exp(-x^2) over [a,b] by random
sampling, compare to the true value via scipy.special.erf, and plot the
function with the sampled points.

Run:  python examples/build_py_mc_integration.py

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
    s = wb.add_sheet("MC Integration")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Monte Carlo Integration",
                  "Estimate ∫ₐᵇ exp(−x²) dx by random sampling")

    # ── Input parameters ───────────────────────────────────────────────
    inputs = [
        ("N samples",    10000),
        ("Seed",         42),
        ("Lower bound a", 0.0),
        ("Upper bound b", 2.0),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(3, 0, 6, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 160)
    s.col_width(1, 90)

    s.note(3, 1,
           "Edit N, seed, a or b then press Ctrl+Enter on the =PY cells below.",
           kind="note")

    # ── =PY cell: compute estimate + plot ─────────────────────────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "from scipy.special import erf",
        "N = int(ks('B4'))",
        "seed = int(ks('B5'))",
        "a = float(ks('B6'))",
        "b = float(ks('B7'))",
        "rng = np.random.default_rng(seed)",
        "xs = rng.uniform(a, b, N)",
        "fvals = np.exp(-xs**2)",
        "estimate = (b - a) * fvals.mean()",
        "true_val = (np.pi**0.5 / 2) * (erf(b) - erf(a))",
        "x_plot = np.linspace(a, b, 400)",
        "y_plot = np.exp(-x_plot**2)",
        "fig, ax = plt.subplots(figsize=(6, 4))",
        "ax.plot(x_plot, y_plot, color='#4472c4', linewidth=2.5, label='f(x) = exp(-x²)')",
        "# plot a random subset of samples (max 500 for clarity)",
        "n_show = min(N, 500)",
        "idx = rng.choice(N, n_show, replace=False)",
        "ax.scatter(xs[idx], fvals[idx], s=6, alpha=0.4, color='#ed7d31', label='Samples')",
        "ax.set_xlabel('x')",
        "ax.set_ylabel('f(x)')",
        "ax.set_title(f'MC estimate = {estimate:.5f}   true = {true_val:.5f}')",
        "ax.legend(fontsize=9)",
        "ax.grid(True, alpha=0.4)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(8, 0, py_plot)

    # ── =PY cell: return numerical results ────────────────────────────
    s.set(8, 4, "MC Estimate:")
    s.set(9, 4, "True value:")
    s.set(10, 4, "Error (%):")
    for r in range(8, 11):
        s.fmt(r, 4, bold=True, align="right")
    s.col_width(4, 130)

    py_results = "\n".join([
        "=PY",
        "import numpy as np",
        "from scipy.special import erf",
        "N = int(ks('B4'))",
        "seed = int(ks('B5'))",
        "a = float(ks('B6'))",
        "b = float(ks('B7'))",
        "rng = np.random.default_rng(seed)",
        "xs = rng.uniform(a, b, N)",
        "estimate = (b - a) * np.exp(-xs**2).mean()",
        "true_val = (np.pi**0.5 / 2) * (erf(b) - erf(a))",
        "err_pct = abs(estimate - true_val) / true_val * 100",
        "ks_set('F9', round(estimate, 6))",
        "ks_set('F10', round(true_val, 6))",
        "ks_set('F11', round(err_pct, 4))",
        "round(estimate, 6)",
    ])
    s.formula(8, 5, py_results)
    for r in range(8, 11):
        s.fmt(r, 5, bg=PALETTE["good"], bold=True, align="center",
              number_format="0.000000")
    s.box(8, 4, 10, 5, color=PALETTE["header"], width=1.0)
    s.col_width(5, 110)

    s.note(8, 0,
           "The plot shows the function and random sample points. "
           "Increase N to reduce the error.",
           kind="note")

    out = os.path.join(_REPO, "examples", "python", "Simulations",
                       "Monte Carlo Integration.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
