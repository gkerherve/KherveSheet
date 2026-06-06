"""Build "Stock Price Paths.ksheet" — GBM Monte Carlo path simulation.

=PY cells simulate geometric Brownian motion paths and plot a fan of
sample trajectories; a second cell returns mean and 5th/95th percentile
of the terminal price distribution.

Run:  python examples/build_py_stock_price_paths.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE


def build() -> str:
    wb = Workbook(min_rows=44, min_cols=12)
    s = wb.add_sheet("Stock Paths")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block("Stock Price Paths",
                  "Geometric Brownian motion — fan of simulated price trajectories")

    # ── Input parameters ───────────────────────────────────────────────
    inputs = [
        ("Initial price  S₀",          100.0),
        ("Drift  μ (annual)",             0.08),
        ("Volatility  σ (annual)",        0.20),
        ("Trading days",                 252),
        ("Number of paths",              200),
        ("Random seed",                   42),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(3, 0, 8, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 200)
    s.col_width(1, 90)

    s.note(3, 1,
           "Edit S0, mu, sigma, days, N paths or seed, "
           "then press Ctrl+Enter on the =PY cells to rerun.",
           kind="note")

    # ── =PY cell: simulate GBM and plot paths ─────────────────────────
    # Inputs: B4=S0, B5=mu, B6=sigma, B7=days, B8=N_paths, B9=seed
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "import matplotlib.cm as cm",
        "S0    = float(ks('B4'))",
        "mu    = float(ks('B5'))",
        "sig   = float(ks('B6'))",
        "days  = int(ks('B7'))",
        "N     = int(ks('B8'))",
        "seed  = int(ks('B9'))",
        "rng   = np.random.default_rng(seed)",
        "dt    = 1.0 / 252.0",
        "# Vectorised GBM: shape (N, days)",
        "Z     = rng.standard_normal((N, days))",
        "daily = np.exp((mu - 0.5 * sig**2) * dt + sig * np.sqrt(dt) * Z)",
        "# Prepend S0 column then cumulative product",
        "ones  = np.ones((N, 1)) * S0",
        "paths = np.concatenate([ones, ones * np.cumprod(daily, axis=1)], axis=1)",
        "t     = np.arange(days + 1)",
        "fig, ax = plt.subplots(figsize=(8, 5))",
        "# Plot up to 100 paths, coloured by terminal value",
        "n_show = min(N, 100)",
        "terminal = paths[:n_show, -1]",
        "cmap = cm.RdYlGn",
        "t_min, t_max = terminal.min(), terminal.max()",
        "norm_range = max(t_max - t_min, 1e-9)",
        "for i in range(n_show):",
        "    c = cmap((terminal[i] - t_min) / norm_range)",
        "    ax.plot(t, paths[i], color=c, lw=0.6, alpha=0.55)",
        "# Overlay mean and percentile bands",
        "mean_path = paths.mean(axis=0)",
        "p05 = np.percentile(paths, 5, axis=0)",
        "p95 = np.percentile(paths, 95, axis=0)",
        "ax.plot(t, mean_path, color='#222222', lw=2.0, label='Mean')",
        "ax.fill_between(t, p05, p95, alpha=0.15, color='#4472c4',",
        "                label='5th–95th pct')",
        "ax.axhline(S0, color='#777777', lw=1.0, ls=':', label=f'S0={S0}')",
        "ax.set_xlabel('Trading day')",
        "ax.set_ylabel('Price')",
        "ax.set_title(f'GBM paths  (mu={mu}, sigma={sig}, N={N})')",
        "ax.legend(fontsize=8)",
        "ax.grid(True, alpha=0.3)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(10, 0, py_plot)

    # ── =PY cell: terminal price statistics ───────────────────────────
    s.set(10, 4, "Terminal price statistics")
    s.fmt(10, 4, bold=True, font_color=PALETTE["header"])
    stats_labels = ["Mean", "5th percentile", "95th percentile"]
    for i, lbl in enumerate(stats_labels):
        s.set(11 + i, 4, lbl)
        s.fmt(11 + i, 4, bold=True, align="right")
    s.col_width(4, 155)
    s.col_width(5, 110)

    py_stats = "\n".join([
        "=PY",
        "import numpy as np",
        "S0    = float(ks('B4'))",
        "mu    = float(ks('B5'))",
        "sig   = float(ks('B6'))",
        "days  = int(ks('B7'))",
        "N     = int(ks('B8'))",
        "seed  = int(ks('B9'))",
        "rng   = np.random.default_rng(seed)",
        "dt    = 1.0 / 252.0",
        "Z     = rng.standard_normal((N, days))",
        "daily = np.exp((mu - 0.5 * sig**2) * dt + sig * np.sqrt(dt) * Z)",
        "ST    = S0 * np.prod(daily, axis=1)",
        "ks_set('F12', round(float(ST.mean()), 4))",
        "ks_set('F13', round(float(np.percentile(ST, 5)), 4))",
        "ks_set('F14', round(float(np.percentile(ST, 95)), 4))",
        "round(float(ST.mean()), 4)",
    ])
    s.formula(11, 5, py_stats)
    for i in range(3):
        s.fmt(11 + i, 5, bg=PALETTE["band"], bold=True, align="center",
              number_format="0.00")
    s.box(10, 4, 13, 5, color=PALETTE["header"], width=1.0)

    s.note(10, 4,
           "Terminal statistics computed from the same seed as the plot — "
           "mean ≈ S0·exp(μ·T) by risk-neutral theory.",
           kind="note")

    out = os.path.join(_REPO, "examples", "python", "Finance Simulations",
                       "Stock Price Paths.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
