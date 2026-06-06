"""Build "Portfolio Monte Carlo.ksheet" — portfolio value trajectory simulation.

=PY cells simulate portfolio value paths under GBM, plot the final-value
histogram plus a sample of trajectories, and return key percentile stats.

Run:  python examples/build_py_portfolio_mc.py

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
    s = wb.add_sheet("Portfolio MC")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block("Portfolio Monte Carlo",
                  "Distribution of final portfolio value — annual-step simulation")

    # ── Input parameters ───────────────────────────────────────────────
    inputs = [
        ("Initial value  (£)",           50000.0),
        ("Annual return  μ",               0.07),
        ("Annual volatility  σ",           0.15),
        ("Investment horizon  (years)",   20),
        ("Number of simulations",       5000),
        ("Random seed",                   99),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(3, 0, 8, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 210)
    s.col_width(1, 90)

    s.note(3, 1,
           "Edit initial value, mu, sigma, years or N sims, "
           "then press Ctrl+Enter on the =PY plot cell to refresh.",
           kind="note")

    # ── =PY cell: simulate trajectories and plot ──────────────────────
    # B4=V0, B5=mu, B6=sigma, B7=years, B8=N_sims, B9=seed
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "V0   = float(ks('B4'))",
        "mu   = float(ks('B5'))",
        "sig  = float(ks('B6'))",
        "yrs  = int(ks('B7'))",
        "N    = int(ks('B8'))",
        "seed = int(ks('B9'))",
        "rng  = np.random.default_rng(seed)",
        "# Annual log-normal returns: shape (N, yrs)",
        "Z       = rng.standard_normal((N, yrs))",
        "returns = np.exp((mu - 0.5 * sig**2) + sig * Z)",
        "# Cumulative portfolio value: shape (N, yrs+1)",
        "ones  = np.ones((N, 1)) * V0",
        "paths = np.concatenate([ones, ones * np.cumprod(returns, axis=1)], axis=1)",
        "final = paths[:, -1]",
        "fig, axes = plt.subplots(1, 2, figsize=(10, 4))",
        "# Left: sample trajectories",
        "ax1 = axes[0]",
        "t = np.arange(yrs + 1)",
        "n_show = min(N, 80)",
        "for i in range(n_show):",
        "    ax1.plot(t, paths[i] / 1e3, lw=0.5, alpha=0.4, color='#4472c4')",
        "mean_p = paths.mean(axis=0)",
        "p10 = np.percentile(paths, 10, axis=0)",
        "p90 = np.percentile(paths, 90, axis=0)",
        "ax1.plot(t, mean_p / 1e3, color='#ed7d31', lw=2.5, label='Mean')",
        "ax1.fill_between(t, p10 / 1e3, p90 / 1e3, alpha=0.18,",
        "                 color='#ed7d31', label='10th–90th pct')",
        "ax1.set_xlabel('Year')",
        "ax1.set_ylabel('Portfolio value  (£k)')",
        "ax1.set_title('Sample trajectories')",
        "ax1.legend(fontsize=8)",
        "ax1.grid(True, alpha=0.3)",
        "# Right: histogram of final values",
        "ax2 = axes[1]",
        "ax2.hist(final / 1e3, bins=60, color='#4472c4', edgecolor='white',",
        "         linewidth=0.4, alpha=0.85, density=True)",
        "ax2.axvline(np.median(final) / 1e3, color='#ed7d31', lw=2,",
        "            label=f'Median £{np.median(final)/1e3:.0f}k')",
        "ax2.axvline(V0 / 1e3, color='#555', lw=1.5, ls='--',",
        "            label=f'Initial £{V0/1e3:.0f}k')",
        "ax2.set_xlabel('Final value  (£k)')",
        "ax2.set_ylabel('Density')",
        "ax2.set_title(f'Final value distribution  (N={N})')",
        "ax2.legend(fontsize=8)",
        "ax2.grid(True, alpha=0.3)",
        "fig.suptitle(f'Portfolio MC  (mu={mu:.0%}, sigma={sig:.0%}, {yrs} yr)',",
        "             fontsize=11, fontweight='bold')",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(10, 0, py_plot)

    # ── =PY cell: summary statistics ──────────────────────────────────
    s.set(10, 4, "Final value statistics")
    s.fmt(10, 4, bold=True, font_color=PALETTE["header"])
    stat_labels = ["Median", "10th percentile", "90th percentile", "% above initial"]
    for i, lbl in enumerate(stat_labels):
        s.set(11 + i, 4, lbl)
        s.fmt(11 + i, 4, bold=True, align="right")
    s.col_width(4, 165)
    s.col_width(5, 110)

    py_stats = "\n".join([
        "=PY",
        "import numpy as np",
        "V0   = float(ks('B4'))",
        "mu   = float(ks('B5'))",
        "sig  = float(ks('B6'))",
        "yrs  = int(ks('B7'))",
        "N    = int(ks('B8'))",
        "seed = int(ks('B9'))",
        "rng  = np.random.default_rng(seed)",
        "Z       = rng.standard_normal((N, yrs))",
        "returns = np.exp((mu - 0.5 * sig**2) + sig * Z)",
        "ones  = np.ones((N, 1)) * V0",
        "paths = np.concatenate([ones, ones * np.cumprod(returns, axis=1)], axis=1)",
        "final = paths[:, -1]",
        "median_v = round(float(np.median(final)), 2)",
        "p10_v    = round(float(np.percentile(final, 10)), 2)",
        "p90_v    = round(float(np.percentile(final, 90)), 2)",
        "pct_up   = round(float(100 * np.mean(final > V0)), 2)",
        "ks_set('F12', median_v)",
        "ks_set('F13', p10_v)",
        "ks_set('F14', p90_v)",
        "ks_set('F15', pct_up)",
        "median_v",
    ])
    s.formula(11, 5, py_stats)
    bg_cycle = [PALETTE["good"], PALETTE["band"], PALETTE["band"], PALETTE["warn"]]
    for i in range(4):
        s.fmt(11 + i, 5, bg=bg_cycle[i], bold=True, align="center",
              number_format="0.00")
    s.box(10, 4, 14, 5, color=PALETTE["header"], width=1.0)

    s.note(10, 4,
           "Stats from same RNG seed as the plot. "
           "'% above initial' shows probability of beating the starting value.",
           kind="note")

    out = os.path.join(_REPO, "examples", "python", "Finance Simulations",
                       "Portfolio Monte Carlo.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
