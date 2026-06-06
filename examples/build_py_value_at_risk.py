"""Build "Value at Risk.ksheet" — VaR and CVaR via Monte Carlo simulation.

=PY cells simulate portfolio returns over the horizon, compute VaR and
CVaR at the specified confidence level, and plot the return distribution
with the VaR threshold clearly marked.

Run:  python examples/build_py_value_at_risk.py

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
    s = wb.add_sheet("VaR")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block("Value at Risk",
                  "Monte Carlo VaR and CVaR — parametric normal returns")

    # ── Input parameters ───────────────────────────────────────────────
    inputs = [
        ("Portfolio value  (£)",        100000.0),
        ("Expected daily return  μ",       0.0005),
        ("Daily volatility  σ",            0.012),
        ("Horizon  (days)",               10),
        ("Confidence level  (e.g. 0.95)",  0.95),
        ("Number of simulations",        50000),
        ("Random seed",                     7),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.0000")
    s.box(3, 0, 9, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 220)
    s.col_width(1, 95)

    s.note(3, 1,
           "Inputs: portfolio value, daily mu and sigma, horizon in days, "
           "confidence level (e.g. 0.95 or 0.99). "
           "Press Ctrl+Enter on the =PY cells to refresh.",
           kind="note")

    # ── =PY cell: simulate returns and plot ───────────────────────────
    # B4=V, B5=mu, B6=sig, B7=horizon, B8=conf, B9=N, B10=seed
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "V    = float(ks('B4'))",
        "mu   = float(ks('B5'))",
        "sig  = float(ks('B6'))",
        "h    = int(ks('B7'))",
        "conf = float(ks('B8'))",
        "N    = int(ks('B9'))",
        "seed = int(ks('B10'))",
        "rng  = np.random.default_rng(seed)",
        "# Multi-day return via GBM: sum of daily log returns",
        "# Shape (N, h); total log-return is the sum across h days",
        "Z         = rng.standard_normal((N, h))",
        "log_ret   = (mu - 0.5 * sig**2) + sig * Z",
        "total_log = log_ret.sum(axis=1)",
        "pnl       = V * (np.exp(total_log) - 1.0)",
        "# VaR: loss at confidence level (negative pnl)",
        "alpha   = 1.0 - conf",
        "var_val = -np.percentile(pnl, 100 * alpha)",
        "# CVaR (Expected Shortfall): mean of losses beyond VaR",
        "losses  = -pnl",
        "cvar_val = losses[losses >= var_val].mean()",
        "fig, ax = plt.subplots(figsize=(8, 5))",
        "ax.hist(pnl / 1e3, bins=80, color='#4472c4', edgecolor='white',",
        "        linewidth=0.3, alpha=0.82, density=True, label='P&L distribution')",
        "var_k = -var_val / 1e3",
        "cvar_k = -cvar_val / 1e3",
        "ax.axvline(var_k, color='#ed7d31', lw=2.0,",
        "           label=f'VaR ({conf:.0%}) = £{var_val/1e3:.2f}k')",
        "ax.axvline(cvar_k, color='#c00000', lw=2.0, ls='--',",
        "           label=f'CVaR = £{cvar_val/1e3:.2f}k')",
        "# Shade tail region",
        "pnl_k = pnl / 1e3",
        "ax.fill_between(",
        "    sorted(pnl_k[pnl_k <= var_k]),",
        "    0,",
        "    [0]*len(pnl_k[pnl_k <= var_k]),",
        "    alpha=0.0)",
        "# Simpler shading: histogram of tail",
        "ax.hist(pnl_k[pnl_k <= var_k], bins=40, color='#c00000',",
        "        alpha=0.55, density=True, label='Tail')",
        "ax.set_xlabel('P&L  (£k)')",
        "ax.set_ylabel('Density')",
        "ax.set_title(f'{h}-day P&L distribution  (V=£{V/1e3:.0f}k, conf={conf:.0%})')",
        "ax.legend(fontsize=9)",
        "ax.grid(True, alpha=0.3)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(11, 0, py_plot)

    # ── =PY cell: VaR and CVaR numbers ────────────────────────────────
    s.set(11, 4, "Risk metrics")
    s.fmt(11, 4, bold=True, font_color=PALETTE["header"])
    result_labels = ["VaR  (£)", "CVaR / ES  (£)", "VaR  (% of portfolio)"]
    for i, lbl in enumerate(result_labels):
        s.set(12 + i, 4, lbl)
        s.fmt(12 + i, 4, bold=True, align="right")
    s.col_width(4, 185)
    s.col_width(5, 115)

    py_risk = "\n".join([
        "=PY",
        "import numpy as np",
        "V    = float(ks('B4'))",
        "mu   = float(ks('B5'))",
        "sig  = float(ks('B6'))",
        "h    = int(ks('B7'))",
        "conf = float(ks('B8'))",
        "N    = int(ks('B9'))",
        "seed = int(ks('B10'))",
        "rng  = np.random.default_rng(seed)",
        "Z         = rng.standard_normal((N, h))",
        "log_ret   = (mu - 0.5 * sig**2) + sig * Z",
        "total_log = log_ret.sum(axis=1)",
        "pnl       = V * (np.exp(total_log) - 1.0)",
        "alpha   = 1.0 - conf",
        "var_val  = -np.percentile(pnl, 100 * alpha)",
        "losses   = -pnl",
        "cvar_val = losses[losses >= var_val].mean()",
        "var_pct  = round(100 * var_val / V, 4)",
        "ks_set('F13', round(var_val, 2))",
        "ks_set('F14', round(cvar_val, 2))",
        "ks_set('F15', var_pct)",
        "round(var_val, 2)",
    ])
    s.formula(12, 5, py_risk)
    bg_cycle = [PALETTE["bad"], PALETTE["warn"], PALETTE["band"]]
    for i in range(3):
        s.fmt(12 + i, 5, bg=bg_cycle[i], bold=True, align="center",
              number_format="0.00")
    s.box(11, 4, 14, 5, color=PALETTE["header"], width=1.0)

    s.note(11, 4,
           "VaR = worst loss at confidence level. "
           "CVaR (Expected Shortfall) = mean loss in the tail — "
           "a more conservative risk measure.",
           kind="note")

    out = os.path.join(_REPO, "examples", "python", "Finance Simulations",
                       "Value at Risk.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
