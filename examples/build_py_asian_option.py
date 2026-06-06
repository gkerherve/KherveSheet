"""Build "Asian Option Pricing.ksheet" — arithmetic-average Asian call by MC.

=PY cells simulate GBM paths, compute the arithmetic average price along
each path, price the Asian call by discounted average payoff, and plot
the distribution of path averages and payoffs.

Run:  python examples/build_py_asian_option.py

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
    s = wb.add_sheet("Asian Option")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block("Asian Option Pricing",
                  "Arithmetic-average Asian call — Monte Carlo simulation")

    # ── Input parameters ───────────────────────────────────────────────
    inputs = [
        ("Spot price  S₀",            100.0),
        ("Strike price  K",           100.0),
        ("Volatility  σ (annual)",      0.25),
        ("Risk-free rate  r (annual)",  0.05),
        ("Maturity  T (years)",          1.0),
        ("Number of paths",           20000),
        ("Random seed",                  17),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.0000")
    s.box(3, 0, 9, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 215)
    s.col_width(1, 90)

    s.note(3, 1,
           "Edit S0, K, sigma, r or maturity T, "
           "then press Ctrl+Enter on the =PY cells. "
           "Asian options are cheaper than European calls because "
           "averaging reduces volatility.",
           kind="note")

    # ── =PY cell: simulate paths and plot distributions ────────────────
    # B4=S0, B5=K, B6=sig, B7=r, B8=T, B9=N, B10=seed
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "S0   = float(ks('B4'))",
        "K    = float(ks('B5'))",
        "sig  = float(ks('B6'))",
        "r    = float(ks('B7'))",
        "T    = float(ks('B8'))",
        "N    = int(ks('B9'))",
        "seed = int(ks('B10'))",
        "rng  = np.random.default_rng(seed)",
        "steps = 252",
        "dt    = T / steps",
        "# Vectorised GBM: shape (N, steps)",
        "Z     = rng.standard_normal((N, steps))",
        "daily = np.exp((r - 0.5 * sig**2) * dt + sig * np.sqrt(dt) * Z)",
        "# Full price path: prepend S0, then cumulative product",
        "ones  = np.ones((N, 1)) * S0",
        "paths = np.concatenate([ones, ones * np.cumprod(daily, axis=1)], axis=1)",
        "# Arithmetic average over the full path (excluding t=0)",
        "avg_price = paths[:, 1:].mean(axis=1)",
        "payoff    = np.maximum(avg_price - K, 0.0)",
        "price     = np.exp(-r * T) * payoff.mean()",
        "fig, axes = plt.subplots(1, 2, figsize=(10, 4))",
        "# Left: distribution of arithmetic average prices",
        "ax1 = axes[0]",
        "ax1.hist(avg_price, bins=60, color='#4472c4', edgecolor='white',",
        "         linewidth=0.3, alpha=0.85, density=True)",
        "ax1.axvline(K, color='#ed7d31', lw=2.0, ls='--',",
        "            label=f'Strike K={K}')",
        "ax1.axvline(S0, color='#555555', lw=1.5, ls=':',",
        "            label=f'S0={S0}')",
        "ax1.axvline(avg_price.mean(), color='#a9d18e', lw=2.0,",
        "            label=f'Mean avg={avg_price.mean():.2f}')",
        "ax1.set_xlabel('Arithmetic average price')",
        "ax1.set_ylabel('Density')",
        "ax1.set_title('Distribution of path average prices')",
        "ax1.legend(fontsize=8)",
        "ax1.grid(True, alpha=0.3)",
        "# Right: payoff distribution (in-the-money only)",
        "ax2 = axes[1]",
        "itm = payoff[payoff > 0]",
        "if len(itm) > 0:",
        "    ax2.hist(itm, bins=50, color='#a9d18e', edgecolor='white',",
        "             linewidth=0.3, alpha=0.88, density=True)",
        "itm_frac = 100.0 * len(itm) / N",
        "ax2.set_xlabel('Payoff  max(Avg − K, 0)')",
        "ax2.set_ylabel('Density')",
        "ax2.set_title(f'In-the-money payoffs  ({itm_frac:.1f}% of paths)')",
        "ax2.grid(True, alpha=0.3)",
        "fig.suptitle(f'Asian Call Price = {price:.4f}  (N={N})',",
        "             fontsize=12, fontweight='bold')",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(11, 0, py_plot)

    # ── =PY cell: option price and comparison stats ────────────────────
    s.set(11, 4, "Asian option results")
    s.fmt(11, 4, bold=True, font_color=PALETTE["header"])
    result_labels = ["Asian call price  (MC)",
                     "European call  (BS)",
                     "Reduction  (Asian / Euro)",
                     "% paths in the money"]
    for i, lbl in enumerate(result_labels):
        s.set(12 + i, 4, lbl)
        s.fmt(12 + i, 4, bold=True, align="right")
    s.col_width(4, 210)
    s.col_width(5, 115)

    py_price = "\n".join([
        "=PY",
        "import numpy as np",
        "from scipy.stats import norm",
        "S0   = float(ks('B4'))",
        "K    = float(ks('B5'))",
        "sig  = float(ks('B6'))",
        "r    = float(ks('B7'))",
        "T    = float(ks('B8'))",
        "N    = int(ks('B9'))",
        "seed = int(ks('B10'))",
        "rng  = np.random.default_rng(seed)",
        "steps = 252",
        "dt    = T / steps",
        "Z     = rng.standard_normal((N, steps))",
        "daily = np.exp((r - 0.5 * sig**2) * dt + sig * np.sqrt(dt) * Z)",
        "ones  = np.ones((N, 1)) * S0",
        "paths = np.concatenate([ones, ones * np.cumprod(daily, axis=1)], axis=1)",
        "avg_price = paths[:, 1:].mean(axis=1)",
        "payoff    = np.maximum(avg_price - K, 0.0)",
        "asian_price = np.exp(-r * T) * payoff.mean()",
        "# Black-Scholes European call for comparison",
        "d1 = (np.log(S0 / K) + (r + 0.5 * sig**2) * T) / (sig * np.sqrt(T))",
        "d2 = d1 - sig * np.sqrt(T)",
        "bs_price = S0 * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)",
        "ratio    = round(float(asian_price / bs_price), 4) if bs_price > 0 else 0.0",
        "itm_pct  = round(float(100.0 * np.mean(payoff > 0)), 2)",
        "ks_set('F13', round(float(asian_price), 4))",
        "ks_set('F14', round(float(bs_price), 4))",
        "ks_set('F15', ratio)",
        "ks_set('F16', itm_pct)",
        "round(float(asian_price), 4)",
    ])
    s.formula(12, 5, py_price)
    bg_cycle = [PALETTE["good"], PALETTE["band"], PALETTE["warn"], PALETTE["band_alt"]]
    for i in range(4):
        s.fmt(12 + i, 5, bg=bg_cycle[i], bold=True, align="center",
              number_format="0.0000")
    s.box(11, 4, 15, 5, color=PALETTE["header"], width=1.0)

    s.note(11, 4,
           "Asian call is always cheaper than a European call because "
           "averaging dampens effective volatility. "
           "Ratio < 1.0 quantifies this discount.",
           kind="note")

    out = os.path.join(_REPO, "examples", "python", "Finance Simulations",
                       "Asian Option Pricing.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
