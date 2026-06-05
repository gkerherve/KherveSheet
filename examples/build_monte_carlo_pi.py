"""Build "Monte Carlo Pi.ksheet" — a =PY science example.

Estimates pi by counting random points inside the unit circle.
Input: number of samples N, random seed (read from cells).
A spill cell gives pi estimate, inside count, and error;
a plot cell shows inside/outside points.

Run:  python examples/build_monte_carlo_pi.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

from ksheet_author import Workbook, PALETTE  # noqa: E402


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=14)
    s = wb.add_sheet("Monte Carlo Pi")

    # ── Title ──────────────────────────────────────────────────────────
    s.title_block(
        "Monte Carlo Estimation of Pi",
        "Random sampling inside a unit square to approximate pi",
    )

    # ── Input parameters ───────────────────────────────────────────────
    # Row 3 (0-based) = B4 in 1-based; row 4 = B5.
    s.set(2, 0, "Inputs")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    s.set(3, 0, "Number of samples N")
    s.set(3, 1, 5000)
    s.set(4, 0, "Random seed")
    s.set(4, 1, 42)
    s.fmt(3, 0, bold=True); s.fmt(4, 0, bold=True)
    s.fmt(3, 1, bg=PALETTE["warn"], align="center", number_format="0")
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0")
    s.box(3, 0, 4, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 180)
    s.col_width(1, 100)

    # ── Result labels ──────────────────────────────────────────────────
    # Results spill from C7 (row 6, col 2 = 0-based).
    s.set(6, 0, "Results")
    s.fmt(6, 0, bold=True, font_color=PALETTE["accent"])
    s.set(7, 0, "Pi estimate")
    s.set(8, 0, "Points inside circle")
    s.set(9, 0, "Absolute error |pi_est - pi|")
    s.fmt(7, 0, bold=True); s.fmt(8, 0, bold=True); s.fmt(9, 0, bold=True)

    # ── Python cell: estimate pi, spill 3 results ─────────────────────
    # Placed at row 6, col 1 (0-based) = B7 in 1-based.
    # N=B4, seed=B5.
    py_estimate = (
        "=PY\n"
        "import numpy as np\n"
        "N = int(ks('B4'))\n"
        "seed = int(ks('B5'))\n"
        "rng = np.random.default_rng(seed)\n"
        "x = rng.uniform(-1, 1, N)\n"
        "y = rng.uniform(-1, 1, N)\n"
        "inside = (x**2 + y**2) <= 1.0\n"
        "pi_est = 4.0 * inside.sum() / N\n"
        "err = abs(pi_est - np.pi)\n"
        "[round(pi_est, 8), int(inside.sum()), round(err, 8)]"
    )
    s.formula(6, 1, py_estimate)
    s.fmt(6, 1, bg=PALETTE["good"], bold=True, align="right", number_format="0.00000000")
    s.fmt(7, 1, bg=PALETTE["band"], bold=True, align="right", number_format="0")
    s.fmt(8, 1, bg=PALETTE["bad"], bold=True, align="right", number_format="0.00000000")
    s.col_width(1, 130)

    # ── Python cell: scatter plot ──────────────────────────────────────
    # Placed at row 2, col 3 (0-based) = D3 in 1-based.
    py_plot = (
        "=PY\n"
        "import numpy as np, matplotlib.pyplot as plt\n"
        "N = int(ks('B4'))\n"
        "seed = int(ks('B5'))\n"
        "rng = np.random.default_rng(seed)\n"
        "x = rng.uniform(-1, 1, N)\n"
        "y = rng.uniform(-1, 1, N)\n"
        "inside = (x**2 + y**2) <= 1.0\n"
        "pi_est = 4.0 * inside.sum() / N\n"
        "nplot = min(N, 3000)\n"
        "idx = np.arange(N)[:nplot]\n"
        "fig, ax = plt.subplots(figsize=(5.5, 5.5))\n"
        "ax.scatter(x[idx][~inside[idx]], y[idx][~inside[idx]],\n"
        "           s=2, color='#ffc7ce', alpha=0.7, label='Outside')\n"
        "ax.scatter(x[idx][inside[idx]], y[idx][inside[idx]],\n"
        "           s=2, color='#4472c4', alpha=0.7, label='Inside')\n"
        "theta = np.linspace(0, 2*np.pi, 300)\n"
        "ax.plot(np.cos(theta), np.sin(theta), 'k-', linewidth=1.5)\n"
        "ax.set_aspect('equal'); ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05)\n"
        "ax.set_title(f'Monte Carlo pi  N={N}  pi~{pi_est:.6f}')\n"
        "ax.legend(fontsize=9, markerscale=5)\n"
        "ax.grid(True, alpha=0.2)\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )
    s.formula(2, 3, py_plot)

    # ── Convergence table ─────────────────────────────────────────────
    s.set(12, 0, "Convergence with sample size  (fixed seed=42)")
    s.fmt(12, 0, bold=True, font_color=PALETTE["header"])
    s.set(13, 0, "N samples")
    s.set(13, 1, "Pi estimate")
    s.set(13, 2, "|error|")
    for c in range(3):
        s.fmt(13, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    s.col_width(2, 110)

    ns = [100, 500, 1000, 2000, 5000, 10000, 50000]
    for i, n_val in enumerate(ns):
        rng = np.random.default_rng(42)
        xi = rng.uniform(-1, 1, n_val)
        yi = rng.uniform(-1, 1, n_val)
        est = 4.0 * ((xi**2 + yi**2) <= 1.0).sum() / n_val
        err = abs(est - np.pi)
        r = 14 + i
        band = PALETTE["band_alt"] if i % 2 else None
        s.set(r, 0, n_val)
        s.set(r, 1, round(float(est), 6))
        s.set(r, 2, round(float(err), 6))
        s.fmt(r, 0, align="right", bg=band or "")
        s.fmt(r, 1, align="right", number_format="0.000000", bg=band or "")
        s.fmt(r, 2, align="right", number_format="0.000000", bg=band or "")
    s.box(13, 0, 14 + len(ns) - 1, 2, color=PALETTE["header"], width=1.0)

    # ── Sticky notes ───────────────────────────────────────────────────
    s.note(
        3, 1,
        "Change N in B4 (e.g. 1000 or 50000) or the seed in B5, "
        "then press Ctrl+Enter on B7 and D3 to recompute.",
        kind="note",
    )
    s.note(
        6, 1,
        "B7 spills downward: row 7 = pi estimate, row 8 = inside count, "
        "row 9 = |error|.  The estimate improves as N grows (scales as 1/sqrt(N)).",
        kind="note",
    )
    s.note(
        2, 3,
        "Blue dots are inside the unit circle, red outside.  "
        "pi/4 equals the fraction of dots that land inside.",
        kind="note",
    )

    out = os.path.join(
        _ROOT, "examples", "python", "Numerical Methods",
        "Monte Carlo Pi.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
