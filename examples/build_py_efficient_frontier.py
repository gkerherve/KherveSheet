"""Build "Efficient Frontier.ksheet" — random portfolio optimisation.

=PY cells generate random portfolio weights across 4 assets, compute
expected return and volatility, plot the risk-return scatter coloured
by Sharpe ratio, and mark the maximum-Sharpe portfolio.

Run:  python examples/build_py_efficient_frontier.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=14)
    s = wb.add_sheet("Efficient Frontier")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block("Efficient Frontier",
                  "Random portfolio weights — Sharpe-ratio scatter across 4 assets")

    # ── Simulation inputs ──────────────────────────────────────────────
    s.set(3, 0, "Simulation inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    sim_inputs = [
        ("Number of random portfolios", 4000),
        ("Random seed",                  88),
        ("Risk-free rate  r_f",           0.02),
    ]
    for i, (lbl, val) in enumerate(sim_inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.0000")
    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 225)
    s.col_width(1, 90)

    # ── Asset parameters (fixed in sheet, read by =PY) ─────────────────
    s.set(3, 3, "Asset parameters")
    s.fmt(3, 3, bold=True, font_color=PALETTE["accent"])

    asset_headers = ["Asset", "Exp. return", "Volatility"]
    asset_data = [
        ("US Equities",   0.10, 0.18),
        ("Int'l Equities",0.08, 0.22),
        ("Bonds",         0.04, 0.07),
        ("Commodities",   0.06, 0.20),
    ]
    s.table(4, 3, headers=asset_headers, rows=[list(d) for d in asset_data],
            number_format="0.00", banded=True)
    s.col_width(3, 145)
    s.col_width(4, 110)
    s.col_width(5, 110)

    # ── Correlation matrix (fixed values in cells, read by =PY) ────────
    s.set(3, 7, "Correlation matrix")
    s.fmt(3, 7, bold=True, font_color=PALETTE["accent"])

    corr_headers = ["", "US Eq", "Intl Eq", "Bonds", "Commod"]
    corr_rows = [
        ["US Eq",    1.00,  0.75,  0.10,  0.20],
        ["Intl Eq",  0.75,  1.00,  0.05,  0.18],
        ["Bonds",    0.10,  0.05,  1.00,  0.02],
        ["Commod",   0.20,  0.18,  0.02,  1.00],
    ]
    s.table(4, 7, headers=corr_headers, rows=corr_rows,
            number_format="0.00", banded=True)
    for c in range(7, 12):
        s.col_width(c, 70)

    s.note(4, 1,
           "Edit N portfolios, seed or risk-free rate, then press "
           "Ctrl+Enter on the =PY plot cell (row 11) to refresh the frontier.",
           kind="note")

    # ── =PY cell: generate random portfolios and plot frontier ─────────
    # B5=N, B6=seed, B7=rf
    # Asset returns: E5:E8, vols: F5:F8
    # Correlation matrix: I5:L8
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "import matplotlib.cm as cm",
        "N_port = int(ks('B5'))",
        "seed   = int(ks('B6'))",
        "rf     = float(ks('B7'))",
        "# Asset expected returns and volatilities",
        "# table(4,3) puts header at sheet row 5, data at rows 6-9",
        "mu_a  = np.array(ks('E6:E9'), dtype=float).ravel()",
        "sig_a = np.array(ks('F6:F9'), dtype=float).ravel()",
        "# Correlation matrix (4x4): table(4,7) data rows 6-9, numeric cols I-L",
        "corr  = np.array(ks('I6:L9'), dtype=float)",
        "# Covariance matrix",
        "cov   = corr * np.outer(sig_a, sig_a)",
        "n_assets = len(mu_a)",
        "rng = np.random.default_rng(seed)",
        "# Random Dirichlet weights: shape (N_port, n_assets)",
        "raw    = rng.exponential(1.0, (N_port, n_assets))",
        "weights = raw / raw.sum(axis=1, keepdims=True)",
        "# Portfolio returns and volatilities",
        "p_ret = weights @ mu_a",
        "p_var = np.einsum('ni,ij,nj->n', weights, cov, weights)",
        "p_vol = np.sqrt(p_var)",
        "# Sharpe ratios",
        "sharpe = (p_ret - rf) / (p_vol + 1e-12)",
        "# Maximum Sharpe portfolio",
        "idx_ms = np.argmax(sharpe)",
        "ms_ret = p_ret[idx_ms]",
        "ms_vol = p_vol[idx_ms]",
        "ms_sr  = sharpe[idx_ms]",
        "fig, ax = plt.subplots(figsize=(7, 5))",
        "sc = ax.scatter(p_vol * 100, p_ret * 100,",
        "                c=sharpe, cmap='RdYlGn', s=8, alpha=0.65,",
        "                linewidths=0)",
        "cbar = fig.colorbar(sc, ax=ax)",
        "cbar.set_label('Sharpe ratio')",
        "# Mark individual assets",
        "asset_names = ['US Eq', 'Intl Eq', 'Bonds', 'Commod']",
        "for i in range(n_assets):",
        "    ax.scatter(sig_a[i] * 100, mu_a[i] * 100,",
        "               marker='D', s=60, zorder=5,",
        "               color='#222222', linewidths=0)",
        "    ax.annotate(asset_names[i],",
        "                (sig_a[i] * 100, mu_a[i] * 100),",
        "                fontsize=7, ha='left', xytext=(3, 2),",
        "                textcoords='offset points')",
        "# Mark max-Sharpe portfolio",
        "ax.scatter(ms_vol * 100, ms_ret * 100,",
        "           marker='*', s=220, color='#ed7d31', zorder=6,",
        "           label=f'Max Sharpe  SR={ms_sr:.2f}')",
        "ax.set_xlabel('Portfolio volatility  (%)')",
        "ax.set_ylabel('Expected return  (%)')",
        "ax.set_title(f'Efficient Frontier  ({N_port} random portfolios)')",
        "ax.legend(fontsize=9)",
        "ax.grid(True, alpha=0.25)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(11, 0, py_plot)

    # ── =PY cell: max-Sharpe weights and stats ─────────────────────────
    s.set(11, 8, "Max-Sharpe portfolio")
    s.fmt(11, 8, bold=True, font_color=PALETTE["header"])
    ms_labels = ["Expected return", "Volatility", "Sharpe ratio",
                 "Weight: US Eq", "Weight: Intl Eq",
                 "Weight: Bonds", "Weight: Commod"]
    for i, lbl in enumerate(ms_labels):
        s.set(12 + i, 8, lbl)
        s.fmt(12 + i, 8, bold=True, align="right")
    s.col_width(8, 160)
    s.col_width(9, 100)

    py_ms = "\n".join([
        "=PY",
        "import numpy as np",
        "N_port = int(ks('B5'))",
        "seed   = int(ks('B6'))",
        "rf     = float(ks('B7'))",
        "mu_a  = np.array(ks('E6:E9'), dtype=float).ravel()",
        "sig_a = np.array(ks('F6:F9'), dtype=float).ravel()",
        "corr  = np.array(ks('I6:L9'), dtype=float)",
        "cov   = corr * np.outer(sig_a, sig_a)",
        "n_assets = len(mu_a)",
        "rng = np.random.default_rng(seed)",
        "raw    = rng.exponential(1.0, (N_port, n_assets))",
        "weights = raw / raw.sum(axis=1, keepdims=True)",
        "p_ret = weights @ mu_a",
        "p_var = np.einsum('ni,ij,nj->n', weights, cov, weights)",
        "p_vol = np.sqrt(p_var)",
        "sharpe = (p_ret - rf) / (p_vol + 1e-12)",
        "idx_ms = np.argmax(sharpe)",
        "w_ms = weights[idx_ms]",
        "ks_set('J13', round(float(p_ret[idx_ms]), 4))",
        "ks_set('J14', round(float(p_vol[idx_ms]), 4))",
        "ks_set('J15', round(float(sharpe[idx_ms]), 4))",
        "ks_set('J16', round(float(w_ms[0]), 4))",
        "ks_set('J17', round(float(w_ms[1]), 4))",
        "ks_set('J18', round(float(w_ms[2]), 4))",
        "ks_set('J19', round(float(w_ms[3]), 4))",
        "round(float(sharpe[idx_ms]), 4)",
    ])
    s.formula(12, 9, py_ms)
    good_bg = [PALETTE["good"], PALETTE["band"], PALETTE["warn"]] + \
              [PALETTE["band_alt"]] * 4
    for i in range(7):
        s.fmt(12 + i, 9, bg=good_bg[i], bold=True, align="center",
              number_format="0.0000")
    s.box(11, 8, 18, 9, color=PALETTE["header"], width=1.0)

    s.note(11, 8,
           "Max-Sharpe portfolio = tangency portfolio on the capital market line. "
           "Increase N portfolios for a smoother frontier.",
           kind="note")

    out = os.path.join(_REPO, "examples", "python", "Finance Simulations",
                       "Efficient Frontier.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
