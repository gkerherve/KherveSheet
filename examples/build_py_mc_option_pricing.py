"""Build "Monte Carlo Option Pricing.ksheet" — a Python-cell finance example.

=PY cells simulate terminal stock prices under geometric Brownian motion,
price a European call by discounted average payoff, and plot the
payoff/terminal-price distribution.

Run:  python examples/build_py_mc_option_pricing.py

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
    s = wb.add_sheet("Option Pricing")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Monte Carlo Option Pricing",
                  "European call price via simulated GBM terminal prices")

    # ── Input parameters ───────────────────────────────────────────────
    inputs = [
        ("Spot price S₀",       100.0),
        ("Strike price K",       105.0),
        ("Volatility σ",          0.20),
        ("Risk-free rate r",      0.05),
        ("Time to maturity T (y)",1.00),
        ("N paths",            20000),
        ("Seed",                  123),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(3, 0, 9, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 185)
    s.col_width(1, 90)

    s.note(3, 1,
           "Edit any input then press Ctrl+Enter on the =PY cells. "
           "Try changing K (e.g. 95) or σ (e.g. 0.30) to see the price shift.",
           kind="note")

    # ── =PY cell: simulate and plot ───────────────────────────────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "S0 = float(ks('B4'))",
        "K  = float(ks('B5'))",
        "sig = float(ks('B6'))",
        "r  = float(ks('B7'))",
        "T  = float(ks('B8'))",
        "N  = int(ks('B9'))",
        "seed = int(ks('B10'))",
        "rng = np.random.default_rng(seed)",
        "Z = rng.standard_normal(N)",
        "ST = S0 * np.exp((r - 0.5 * sig**2) * T + sig * np.sqrt(T) * Z)",
        "payoff = np.maximum(ST - K, 0.0)",
        "price = np.exp(-r * T) * payoff.mean()",
        "fig, axes = plt.subplots(1, 2, figsize=(9, 4))",
        "# Left: terminal price distribution",
        "ax = axes[0]",
        "ax.hist(ST, bins=60, color='#4472c4', edgecolor='white', linewidth=0.5,",
        "        density=True, alpha=0.85)",
        "ax.axvline(K, color='#ed7d31', linewidth=2, linestyle='--',",
        "           label=f'Strike K = {K}')",
        "ax.axvline(S0, color='#555555', linewidth=1.5, linestyle=':',",
        "           label=f'S₀ = {S0}')",
        "ax.set_xlabel('Terminal price Sₜ')",
        "ax.set_ylabel('Density')",
        "ax.set_title('Terminal price distribution')",
        "ax.legend(fontsize=8)",
        "ax.grid(True, alpha=0.3)",
        "# Right: payoff distribution (positive payoffs only)",
        "ax2 = axes[1]",
        "itm = payoff[payoff > 0]",
        "if len(itm) > 0:",
        "    ax2.hist(itm, bins=50, color='#a9d18e', edgecolor='white',",
        "             linewidth=0.5, density=True, alpha=0.9)",
        "ax2.set_xlabel('Payoff  max(Sₜ − K, 0)')",
        "ax2.set_ylabel('Density')",
        "ax2.set_title(f'Payoff distribution  (ITM = {100*len(itm)/N:.1f}%)')",
        "ax2.grid(True, alpha=0.3)",
        "fig.suptitle(f'MC Call Price = {price:.4f}', fontsize=12, fontweight='bold')",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(11, 0, py_plot)

    # ── =PY cell: numerical results ───────────────────────────────────
    s.set(11, 4, "MC Call Price:")
    s.set(12, 4, "Black-Scholes:")
    s.set(13, 4, "Difference:")
    for r in range(11, 14):
        s.fmt(r, 4, bold=True, align="right")
    s.col_width(4, 140)
    s.col_width(5, 110)

    py_price = "\n".join([
        "=PY",
        "import numpy as np",
        "from scipy.stats import norm",
        "S0 = float(ks('B4'))",
        "K  = float(ks('B5'))",
        "sig = float(ks('B6'))",
        "r  = float(ks('B7'))",
        "T  = float(ks('B8'))",
        "N  = int(ks('B9'))",
        "seed = int(ks('B10'))",
        "rng = np.random.default_rng(seed)",
        "Z = rng.standard_normal(N)",
        "ST = S0 * np.exp((r - 0.5 * sig**2) * T + sig * np.sqrt(T) * Z)",
        "payoff = np.maximum(ST - K, 0.0)",
        "mc_price = np.exp(-r * T) * payoff.mean()",
        "# Black-Scholes analytical price",
        "d1 = (np.log(S0 / K) + (r + 0.5 * sig**2) * T) / (sig * np.sqrt(T))",
        "d2 = d1 - sig * np.sqrt(T)",
        "bs_price = S0 * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)",
        "diff = mc_price - bs_price",
        "ks_set('F12', round(mc_price, 4))",
        "ks_set('F13', round(bs_price, 4))",
        "ks_set('F14', round(diff, 4))",
        "round(mc_price, 4)",
    ])
    s.formula(11, 5, py_price)
    s.fmt(11, 5, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.0000")
    s.fmt(12, 5, bg=PALETTE["band"], bold=True, align="center",
          number_format="0.0000")
    s.fmt(13, 5, bg=PALETTE["warn"], bold=True, align="center",
          number_format="0.0000")
    s.box(11, 4, 13, 5, color=PALETTE["header"], width=1.0)

    s.note(11, 0,
           "Left: terminal price histogram with strike line. "
           "Right: in-the-money payoff distribution.",
           kind="note")

    out = os.path.join(_REPO, "examples", "python", "Simulations",
                       "Monte Carlo Option Pricing.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
