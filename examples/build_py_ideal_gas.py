"""Build "Ideal Gas in a Box.ksheet" — 2-D particle simulation with elastic walls.

Simulates N particles in a 2-D box with elastic reflections and plots the
speed histogram alongside the Maxwell-Boltzmann distribution.

Run:  python examples/build_py_ideal_gas.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE  # noqa: E402

OUT_DIR = os.path.join(_REPO, "examples", "python", "Physics Simulations")
OUT_PATH = os.path.join(OUT_DIR, "Ideal Gas in a Box.ksheet")


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Ideal Gas")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Ideal Gas in a Box",
        "2-D elastic particle simulation — speed distribution vs Maxwell-Boltzmann",
    )

    # ── Input parameters ──────────────────────────────────────────────
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Number of particles",  200),   # B5
        ("Temperature T (K)",    300.0),  # B6
        ("Simulation steps",     300),   # B7
        ("Random seed",           42),   # B8
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.box(4, 0, 7, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 190)
    s.col_width(1, 110)

    # ── Sticky note ───────────────────────────────────────────────────
    s.note(
        4, 1,
        "Edit B5–B8 then press Ctrl+Enter on the Python cell.\n"
        "Increase T to shift the MB peak to higher speeds.\n"
        "Keep particles <= 500 for fast rendering.",
        kind="note",
    )

    # ── Python cell: vectorised simulation + histogram + MB curve ────
    py_code = """\
=PY
import numpy as np
import matplotlib.pyplot as plt

N_part = max(10, min(1000, int(ks("B5"))))
T      = max(1.0, float(ks("B6")))
steps  = max(10, min(2000, int(ks("B7"))))
seed   = int(ks("B8"))

rng  = np.random.default_rng(seed)
k_B  = 1.380649e-23
m    = 4.65e-26         # ~N2 molecule mass (kg)
L    = 1.0              # box side length

# Initial positions and velocities (MB distribution for given T)
pos = rng.uniform(0.05, 0.95, (N_part, 2)) * L
sigma = np.sqrt(k_B * T / m)
vel   = rng.normal(0, sigma, (N_part, 2))

dt = L / (10.0 * sigma)   # adaptive small step

# Vectorised time integration with elastic wall bounces
for _ in range(steps):
    pos += vel * dt
    # Reflect off walls
    for d in range(2):
        mask_lo = pos[:, d] < 0
        mask_hi = pos[:, d] > L
        pos[mask_lo, d] = -pos[mask_lo, d]
        pos[mask_hi, d] = 2 * L - pos[mask_hi, d]
        vel[mask_lo, d] = -vel[mask_lo, d]
        vel[mask_hi, d] = -vel[mask_hi, d]

speeds = np.linalg.norm(vel, axis=1)

# Maxwell-Boltzmann 2-D speed distribution  f(v) = (m/kT) v exp(-mv²/2kT)
v_max = speeds.max() * 1.1
v_arr = np.linspace(0, v_max, 300)
mb    = (m / (k_B * T)) * v_arr * np.exp(-m * v_arr**2 / (2 * k_B * T))
# Normalise MB to histogram bin width × N
bin_w = v_max / 30
mb_scaled = mb * N_part * bin_w

fig, axes = plt.subplots(1, 2, figsize=(9, 4))

# Left: particle positions
sc = axes[0].scatter(pos[:, 0], pos[:, 1],
                     c=speeds, cmap="plasma", s=6, alpha=0.75)
axes[0].set_xlim(0, L); axes[0].set_ylim(0, L)
axes[0].set_xlabel("x (m)"); axes[0].set_ylabel("y (m)")
axes[0].set_title("Particle positions (colour = speed)")
axes[0].set_aspect("equal")
fig.colorbar(sc, ax=axes[0], label="speed (m/s)", fraction=0.046)

# Right: speed histogram + MB curve
axes[1].hist(speeds, bins=30, color="#4472c4", alpha=0.65,
             edgecolor="white", linewidth=0.4, label="Simulation")
axes[1].plot(v_arr, mb_scaled, color="#e05c00", linewidth=2.2,
             label="Maxwell-Boltzmann")
axes[1].set_xlabel("Speed (m/s)")
axes[1].set_ylabel("Count")
axes[1].set_title(f"Speed distribution  T={T:.0f} K, N={N_part}")
axes[1].legend(fontsize=9)
axes[1].grid(True, alpha=0.3)

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
