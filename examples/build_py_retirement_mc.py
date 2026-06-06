"""Build "Retirement Monte Carlo.ksheet" — retirement nest-egg simulation.

=PY cells simulate nest-egg growth with annual contributions and random
returns, return the probability of exceeding a target balance, and plot
the distribution of final balances.

Run:  python examples/build_py_retirement_mc.py

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
    s = wb.add_sheet("Retirement MC")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block("Retirement Monte Carlo",
                  "Probability of meeting a retirement target — stochastic nest-egg growth")

    # ── Input parameters ───────────────────────────────────────────────
    inputs = [
        ("Starting savings  (£)",          20000.0),
        ("Annual contribution  (£)",        6000.0),
        ("Mean annual return  μ",             0.07),
        ("Annual volatility  σ",              0.12),
        ("Years to retirement",              30),
        ("Retirement target  (£)",         500000.0),
        ("Number of simulations",           8000),
        ("Random seed",                       55),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(3, 0, 10, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 215)
    s.col_width(1, 100)

    s.note(3, 1,
           "Edit savings, contribution, return, volatility, years, "
           "or the retirement target, then press Ctrl+Enter to refresh.",
           kind="note")

    # ── =PY cell: simulate and plot ────────────────────────────────────
    # B4=S0, B5=contrib, B6=mu, B7=sig, B8=yrs, B9=target, B10=N, B11=seed
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "S0     = float(ks('B4'))",
        "contrib = float(ks('B5'))",
        "mu     = float(ks('B6'))",
        "sig    = float(ks('B7'))",
        "yrs    = int(ks('B8'))",
        "target = float(ks('B9'))",
        "N      = int(ks('B10'))",
        "seed   = int(ks('B11'))",
        "rng    = np.random.default_rng(seed)",
        "# Annual log-normal returns: shape (N, yrs)",
        "Z       = rng.standard_normal((N, yrs))",
        "r_ann   = np.exp((mu - 0.5 * sig**2) + sig * Z)",
        "# Build balance paths: each year apply return then add contribution",
        "balance = np.zeros((N, yrs + 1))",
        "balance[:, 0] = S0",
        "for yr in range(yrs):",
        "    balance[:, yr + 1] = balance[:, yr] * r_ann[:, yr] + contrib",
        "final = balance[:, -1]",
        "prob_target = 100.0 * np.mean(final >= target)",
        "fig, axes = plt.subplots(1, 2, figsize=(11, 4))",
        "# Left: sample trajectories",
        "ax1 = axes[0]",
        "t = np.arange(yrs + 1)",
        "n_show = min(N, 80)",
        "for i in range(n_show):",
        "    ax1.plot(t, balance[i] / 1e3, lw=0.5, alpha=0.35, color='#4472c4')",
        "mean_bal = balance.mean(axis=0)",
        "p10 = np.percentile(balance, 10, axis=0)",
        "p90 = np.percentile(balance, 90, axis=0)",
        "ax1.plot(t, mean_bal / 1e3, color='#ed7d31', lw=2.5, label='Mean')",
        "ax1.fill_between(t, p10 / 1e3, p90 / 1e3, alpha=0.18,",
        "                 color='#ed7d31', label='10th–90th pct')",
        "ax1.axhline(target / 1e3, color='#c00000', lw=1.5, ls='--',",
        "            label=f'Target £{target/1e3:.0f}k')",
        "ax1.set_xlabel('Year')",
        "ax1.set_ylabel('Balance  (£k)')",
        "ax1.set_title('Nest-egg trajectories')",
        "ax1.legend(fontsize=8)",
        "ax1.grid(True, alpha=0.3)",
        "# Right: histogram of final values",
        "ax2 = axes[1]",
        "ax2.hist(final / 1e3, bins=60, color='#4472c4', edgecolor='white',",
        "         linewidth=0.3, alpha=0.85, density=True)",
        "ax2.axvline(target / 1e3, color='#c00000', lw=2.0, ls='--',",
        "            label=f'Target £{target/1e3:.0f}k')",
        "ax2.axvline(np.median(final) / 1e3, color='#ed7d31', lw=1.8,",
        "            label=f'Median £{np.median(final)/1e3:.0f}k')",
        "ax2.set_xlabel('Final balance  (£k)')",
        "ax2.set_ylabel('Density')",
        "ax2.set_title(f'Final balance  — P(goal) = {prob_target:.1f}%')",
        "ax2.legend(fontsize=8)",
        "ax2.grid(True, alpha=0.3)",
        "fig.suptitle(f'Retirement MC  (mu={mu:.0%}, sigma={sig:.0%}, {yrs} yr, N={N})',",
        "             fontsize=11, fontweight='bold')",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(12, 0, py_plot)

    # ── =PY cell: probability and summary stats ────────────────────────
    s.set(12, 4, "Retirement statistics")
    s.fmt(12, 4, bold=True, font_color=PALETTE["header"])
    stat_labels = ["P(reach target)  (%)",
                   "Median final balance  (£)",
                   "10th percentile  (£)",
                   "90th percentile  (£)"]
    for i, lbl in enumerate(stat_labels):
        s.set(13 + i, 4, lbl)
        s.fmt(13 + i, 4, bold=True, align="right")
    s.col_width(4, 195)
    s.col_width(5, 115)

    py_stats = "\n".join([
        "=PY",
        "import numpy as np",
        "S0     = float(ks('B4'))",
        "contrib = float(ks('B5'))",
        "mu     = float(ks('B6'))",
        "sig    = float(ks('B7'))",
        "yrs    = int(ks('B8'))",
        "target = float(ks('B9'))",
        "N      = int(ks('B10'))",
        "seed   = int(ks('B11'))",
        "rng    = np.random.default_rng(seed)",
        "Z       = rng.standard_normal((N, yrs))",
        "r_ann   = np.exp((mu - 0.5 * sig**2) + sig * Z)",
        "balance = np.zeros((N, yrs + 1))",
        "balance[:, 0] = S0",
        "for yr in range(yrs):",
        "    balance[:, yr + 1] = balance[:, yr] * r_ann[:, yr] + contrib",
        "final = balance[:, -1]",
        "prob  = round(float(100.0 * np.mean(final >= target)), 2)",
        "med_v = round(float(np.median(final)), 2)",
        "p10_v = round(float(np.percentile(final, 10)), 2)",
        "p90_v = round(float(np.percentile(final, 90)), 2)",
        "ks_set('F14', prob)",
        "ks_set('F15', med_v)",
        "ks_set('F16', p10_v)",
        "ks_set('F17', p90_v)",
        "prob",
    ])
    s.formula(13, 5, py_stats)
    bg_cycle = [PALETTE["good"], PALETTE["band"], PALETTE["band_alt"],
                PALETTE["band"]]
    for i in range(4):
        s.fmt(13 + i, 5, bg=bg_cycle[i], bold=True, align="center",
              number_format="0.00")
    s.box(12, 4, 16, 5, color=PALETTE["header"], width=1.0)

    s.note(12, 4,
           "P(reach target) is the fraction of simulations that meet or "
           "exceed the retirement goal. Increase N sims for a more stable estimate.",
           kind="note")

    out = os.path.join(_REPO, "examples", "python", "Finance Simulations",
                       "Retirement Monte Carlo.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
