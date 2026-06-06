"""Build "Radioactive Decay (stochastic).ksheet" — Monte Carlo decay simulation.

Simulates atom-by-atom stochastic decay and plots the surviving count against
the exponential expectation N₀ · exp(-λ·t).

Run:  python examples/build_py_stochastic_decay.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE  # noqa: E402

OUT_DIR = os.path.join(_REPO, "examples", "python", "Physics Simulations")
OUT_PATH = os.path.join(OUT_DIR, "Radioactive Decay (stochastic).ksheet")


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Stochastic Decay")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Radioactive Decay (stochastic)",
        "Monte Carlo atom-by-atom simulation vs exponential expectation",
    )

    # ── Input parameters ──────────────────────────────────────────────
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Initial number of atoms N₀",    1000),   # B5
        ("Decay probability p per step",   0.03),  # B6
        ("Number of steps",                200),   # B7
        ("Random seed",                     42),   # B8
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.000")

    s.box(4, 0, 7, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 220)
    s.col_width(1, 110)

    # ── Sticky notes ──────────────────────────────────────────────────
    s.note(
        4, 1,
        "Edit B5–B8 then press Ctrl+Enter on the Python cell.\n"
        "The stochastic curve is noisy; the exponential is the mean expectation.\n"
        "Half-life ≈ ln(2) / p steps.",
        kind="note",
    )
    s.note(
        5, 1,
        "With large N₀ the stochastic curve hugs the exponential.\n"
        "Try N₀=50 to see strong statistical fluctuations.",
        kind="comment",
    )

    # ── Python cell: stochastic simulation + plot ─────────────────────
    py_code = """\
=PY
import numpy as np
import matplotlib.pyplot as plt

N0    = max(1, min(100000, int(ks("B5"))))
p     = max(0.0, min(1.0, float(ks("B6"))))
steps = max(10, min(5000, int(ks("B7"))))
seed  = int(ks("B8"))

rng = np.random.default_rng(seed)

# Stochastic simulation: each atom decays independently each step
surviving = np.empty(steps + 1, dtype=int)
surviving[0] = N0
n = N0
for t in range(steps):
    # Number of decays ~ Binomial(n, p)
    decays = int(rng.binomial(n, p))
    n = max(0, n - decays)
    surviving[t + 1] = n

t_arr = np.arange(steps + 1)

# Exponential expectation: N(t) = N0 * (1-p)^t = N0 * exp(-lambda * t)
lam      = -np.log(1.0 - p)
expected = N0 * np.exp(-lam * t_arr)
half_life = np.log(2) / lam

fig, axes = plt.subplots(1, 2, figsize=(10, 4))

# Left: linear scale
axes[0].plot(t_arr, surviving,   color="#4472c4", linewidth=1.5,
             alpha=0.8,          label="Stochastic")
axes[0].plot(t_arr, expected,    color="#e05c00", linewidth=2.0,
             linestyle="--",     label=f"Exp. N₀·e^(−λt)")
axes[0].axvline(half_life, color="#888888", linestyle=":", linewidth=1.2)
axes[0].text(half_life + steps * 0.01, N0 * 0.55,
             f"t½≈{half_life:.1f}", fontsize=8, color="#555555")
axes[0].set_xlabel("Step")
axes[0].set_ylabel("Atoms surviving")
axes[0].set_title(f"Stochastic Decay  N₀={N0}, p={p:.3f}")
axes[0].legend(fontsize=9)
axes[0].grid(True, alpha=0.3)

# Right: log scale to verify exponential
s_safe   = np.clip(surviving, 1, None)
exp_safe = np.clip(expected,  1, None)
axes[1].semilogy(t_arr, s_safe,   color="#4472c4", linewidth=1.5,
                 alpha=0.8,       label="Stochastic")
axes[1].semilogy(t_arr, exp_safe, color="#e05c00", linewidth=2.0,
                 linestyle="--",  label="Expectation")
axes[1].set_xlabel("Step")
axes[1].set_ylabel("log(atoms surviving)")
axes[1].set_title("Semi-log view (straight → exponential)")
axes[1].legend(fontsize=9)
axes[1].grid(True, alpha=0.3, which="both")

plt.tight_layout()
plt.gcf()
"""
    s.set(9, 0, "Simulation + Plot")
    s.fmt(9, 0, bold=True, font_color=PALETTE["header"])
    s.formula(10, 0, py_code)
    s.fmt(10, 0, bg=PALETTE["band"], font_family="Courier New", font_size=9)

    os.makedirs(OUT_DIR, exist_ok=True)
    wb.save(OUT_PATH)
    return OUT_PATH


if __name__ == "__main__":
    print("Wrote", build())
