"""Build "MM1 Queue.ksheet" — a Python-cell simulation example.

=PY cells simulate an M/M/1 queue with exponential inter-arrival and
service times, plot the queue-length history and the waiting-time
distribution, and return the average customer wait time.

Run:  python examples/build_sim_mm1_queue.py

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
    s = wb.add_sheet("MM1 Queue")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("M/M/1 Queue Simulation",
                  "Single-server queue with Poisson arrivals and "
                  "exponential service — edit inputs then Ctrl+Enter")

    # ── Input parameters ──────────────────────────────────────────────
    # B4=lambda, B5=mu, B6=customers, B7=seed
    s.set(3, 0, "Arrival rate  λ  (customers/unit time)")
    s.set(3, 1, 0.8)
    s.set(4, 0, "Service rate  μ  (customers/unit time)")
    s.set(4, 1, 1.0)
    s.set(5, 0, "Number of customers")
    s.set(5, 1, 2000)
    s.set(6, 0, "Random seed")
    s.set(6, 1, 55)

    for r in range(3, 7):
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.###")

    s.box(3, 0, 6, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 280)
    s.col_width(1, 90)

    s.note(3, 1,
           "Keep λ < μ for a stable queue (ρ = λ/μ < 1). "
           "Try λ=0.95 near saturation. Press Ctrl+Enter on the =PY cells.",
           kind="note")

    # ── =PY scalar: average wait time ─────────────────────────────────
    s.set(7, 3, "Mean wait time (simulated):")
    s.fmt(7, 3, bold=True, align="right")
    s.col_width(3, 240)
    s.col_width(4, 120)

    py_wait = "\n".join([
        "=PY",
        "import numpy as np",
        "lam  = float(ks('B4'))",
        "mu   = float(ks('B5'))",
        "n    = int(ks('B6'))",
        "seed = int(ks('B7'))",
        "rng  = np.random.default_rng(seed)",
        "# Generate inter-arrival and service times",
        "inter = rng.exponential(1.0 / lam, size=n)",
        "svc   = rng.exponential(1.0 / mu,  size=n)",
        "arr   = np.cumsum(inter)",
        "# Simulate FCFS queue",
        "start = np.zeros(n)",
        "finish = np.zeros(n)",
        "start[0]  = arr[0]",
        "finish[0] = start[0] + svc[0]",
        "for i in range(1, n):",
        "    start[i]  = max(arr[i], finish[i-1])",
        "    finish[i] = start[i] + svc[i]",
        "wait = start - arr",
        "round(float(wait.mean()), 4)",
    ])
    s.formula(7, 4, py_wait)
    s.fmt(7, 4, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.0000")

    # Theoretical M/M/1 wait time W = rho / (mu - lambda)
    s.set(8, 3, "Theoretical  W = ρ/(μ−λ):")
    s.fmt(8, 3, bold=True, align="right")
    py_theor = "\n".join([
        "=PY",
        "lam  = float(ks('B4'))",
        "mu   = float(ks('B5'))",
        "rho  = lam / mu",
        "if mu > lam:",
        "    w = rho / (mu - lam)",
        "else:",
        "    w = float('inf')",
        "round(w, 4)",
    ])
    s.formula(8, 4, py_theor)
    s.fmt(8, 4, bg=PALETTE["band"], bold=True, align="center",
          number_format="0.0000")

    s.set(9, 3, "(only valid when λ < μ)")
    s.fmt(9, 3, italic=True, font_color="#666666")

    # ── =PY plot cell (row 10 zero-based → A11) ───────────────────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "lam  = float(ks('B4'))",
        "mu   = float(ks('B5'))",
        "n    = int(ks('B6'))",
        "seed = int(ks('B7'))",
        "rng  = np.random.default_rng(seed)",
        "inter = rng.exponential(1.0 / lam, size=n)",
        "svc   = rng.exponential(1.0 / mu,  size=n)",
        "arr   = np.cumsum(inter)",
        "start  = np.zeros(n)",
        "finish = np.zeros(n)",
        "start[0]  = arr[0]",
        "finish[0] = start[0] + svc[0]",
        "for i in range(1, n):",
        "    start[i]  = max(arr[i], finish[i-1])",
        "    finish[i] = start[i] + svc[i]",
        "wait = start - arr",
        "# Queue length over time (event-driven snapshot)",
        "rho = lam / mu",
        "fig, axes = plt.subplots(1, 2, figsize=(10, 4))",
        "# Left: waiting-time distribution",
        "axes[0].hist(wait, bins=50, density=True,",
        "             color='#4472c4', edgecolor='white', alpha=0.8,",
        "             label='Simulated')",
        "if mu > lam:",
        "    w_max = wait.max()",
        "    wt    = np.linspace(0, w_max, 300)",
        "    # Theoretical PDF: (mu-lam)*exp(-(mu-lam)*w)",
        "    axes[0].plot(wt, (mu - lam) * np.exp(-(mu - lam) * wt),",
        "                 'r-', lw=2, label='Theoretical')",
        "axes[0].set_xlabel('Waiting time')",
        "axes[0].set_ylabel('Density')",
        "axes[0].set_title('Waiting-time distribution')",
        "axes[0].legend(fontsize=8)",
        "axes[0].grid(True, alpha=0.3)",
        "# Right: first 500 customers waiting times",
        "m = min(500, n)",
        "axes[1].plot(np.arange(m), wait[:m], color='#ed7d31',",
        "             lw=0.7, alpha=0.8)",
        "axes[1].axhline(wait.mean(), color='k', ls='--', lw=1.5,",
        "                label=f'Mean={wait.mean():.3f}')",
        "axes[1].set_xlabel('Customer index')",
        "axes[1].set_ylabel('Wait time')",
        "axes[1].set_title(f'Wait times  (\\u03bb={lam}, \\u03bc={mu})')",
        "axes[1].legend(fontsize=8)",
        "axes[1].grid(True, alpha=0.3)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(10, 0, py_plot)

    out = os.path.join(_REPO, "examples", "python", "Simulations",
                       "MM1 Queue.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
