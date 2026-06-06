"""Build "Buffon's Needle.ksheet" — a Python-cell simulation example.

=PY cells simulate dropping needles on ruled lines, estimate pi from the
crossing fraction, and plot a sample of needles over the ruled lines.

Run:  python examples/build_py_buffon_needle.py

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
    s = wb.add_sheet("Buffon")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Buffon's Needle",
                  "Estimate π by dropping needles on ruled paper")

    # ── Input parameters ───────────────────────────────────────────────
    inputs = [
        ("N drops",         5000),
        ("Needle length L",  1.0),
        ("Line spacing d",   1.5),
        ("Seed",             99),
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
           "Edit N, L, d or seed then press Ctrl+Enter on the =PY cells. "
           "For the formula to work, L must be ≤ d (short needle case).",
           kind="note")

    # ── =PY cell: simulate and plot ───────────────────────────────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "N = int(ks('B4'))",
        "L = float(ks('B5'))",
        "d = float(ks('B6'))",
        "seed = int(ks('B7'))",
        "rng = np.random.default_rng(seed)",
        "# needle centre y-coordinate (0 to d), and angle in [0, pi]",
        "y_c = rng.uniform(0, d, N)",
        "theta = rng.uniform(0, np.pi, N)",
        "half = (L / 2) * np.sin(theta)",
        "crosses = (y_c - half < 0) | ((y_c + half) > d)",
        "# For short needles: P(cross) = 2L/(pi*d)",
        "p_cross = crosses.mean()",
        "pi_est = 2 * L / (d * p_cross) if p_cross > 0 else float('nan')",
        "# ── Plot a sample of needles ──",
        "n_show = min(N, 300)",
        "idx = rng.choice(N, n_show, replace=False)",
        "fig, ax = plt.subplots(figsize=(6, 5))",
        "# ruled lines",
        "n_lines = 6",
        "for k in range(n_lines + 1):",
        "    ax.axhline(k * d, color='#aaaaaa', linewidth=1)",
        "for i in idx:",
        "    x0 = rng.uniform(0, 4)",
        "    dx = (L / 2) * np.cos(theta[i])",
        "    dy = (L / 2) * np.sin(theta[i])",
        "    col = '#ed7d31' if crosses[i] else '#4472c4'",
        "    ax.plot([x0 - dx, x0 + dx], [y_c[i] - dy, y_c[i] + dy],",
        "            color=col, linewidth=1.2, alpha=0.7)",
        "ax.set_xlim(0, 4)",
        "ax.set_ylim(-0.2, n_lines * d + 0.2)",
        "ax.set_xlabel('x')",
        "ax.set_ylabel('y')",
        "ax.set_title(f'Buffon estimate of π = {pi_est:.5f}  (true π = {np.pi:.5f})')",
        "from matplotlib.patches import Patch",
        "ax.legend(handles=[Patch(color='#ed7d31', label='Crosses line'),",
        "                   Patch(color='#4472c4', label='No cross')],",
        "          fontsize=9)",
        "ax.grid(False)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(8, 0, py_plot)

    # ── =PY cell: numerical result ─────────────────────────────────────
    s.set(8, 4, "π estimate:")
    s.set(9, 4, "True π:")
    s.set(10, 4, "Error (%):")
    for r in range(8, 11):
        s.fmt(r, 4, bold=True, align="right")
    s.col_width(4, 120)
    s.col_width(5, 110)

    py_result = "\n".join([
        "=PY",
        "import numpy as np",
        "N = int(ks('B4'))",
        "L = float(ks('B5'))",
        "d = float(ks('B6'))",
        "seed = int(ks('B7'))",
        "rng = np.random.default_rng(seed)",
        "y_c = rng.uniform(0, d, N)",
        "theta = rng.uniform(0, np.pi, N)",
        "half = (L / 2) * np.sin(theta)",
        "crosses = (y_c - half < 0) | ((y_c + half) > d)",
        "p_cross = crosses.mean()",
        "pi_est = 2 * L / (d * p_cross) if p_cross > 0 else float('nan')",
        "err_pct = abs(pi_est - np.pi) / np.pi * 100",
        "ks_set('F9', round(pi_est, 6))",
        "ks_set('F10', round(np.pi, 6))",
        "ks_set('F11', round(err_pct, 4))",
        "round(pi_est, 6)",
    ])
    s.formula(8, 5, py_result)
    for r in range(8, 11):
        s.fmt(r, 5, bg=PALETTE["good"], bold=True, align="center",
              number_format="0.000000")
    s.box(8, 4, 10, 5, color=PALETTE["header"], width=1.0)

    s.note(8, 0,
           "Orange needles cross a ruled line; blue needles do not. "
           "More drops = better π estimate.",
           kind="note")

    out = os.path.join(_REPO, "examples", "python", "Simulations",
                       "Buffon's Needle.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
