"""Build "N-Body Gravity.ksheet" — gravitational N-body simulation.

Integrates the equations of motion for up to 5 bodies using leapfrog
(velocity-Verlet) and plots the 2-D trajectories.

Run:  python examples/build_py_nbody.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE  # noqa: E402

OUT_DIR = os.path.join(_REPO, "examples", "python", "Physics Simulations")
OUT_PATH = os.path.join(OUT_DIR, "N-Body Gravity.ksheet")


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("N-Body")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "N-Body Gravity",
        "Leapfrog integration of gravitational motion for up to 5 bodies",
    )

    # ── Input parameters ──────────────────────────────────────────────
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Number of bodies (2–5)", 4),   # B5
        ("Time step dt",          0.01),  # B6
        ("Number of steps",        800),  # B7
        ("Random seed",             42),  # B8
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.box(4, 0, 7, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 200)
    s.col_width(1, 110)

    # ── Sticky notes ──────────────────────────────────────────────────
    s.note(
        4, 1,
        "Edit B5–B8 then press Ctrl+Enter on the Python cell.\n"
        "Keep bodies <= 5 for best performance.\n"
        "dt=0.01, steps=800 gives a ~2-3 s integration.",
        kind="note",
    )

    # ── Python cell: leapfrog integration + trajectory plot ──────────
    py_code = """\
=PY
import numpy as np
import matplotlib.pyplot as plt

n_bodies = max(2, min(5, int(ks("B5"))))
dt       = float(ks("B6"))
n_steps  = max(10, min(2000, int(ks("B7"))))
seed     = int(ks("B8"))

rng = np.random.default_rng(seed)

# Masses: central heavy body + smaller satellites
masses = np.concatenate([[10.0], rng.uniform(0.3, 1.5, n_bodies - 1)])

# Initial positions on a ring (except heavy centre)
pos = np.zeros((n_bodies, 2))
if n_bodies > 1:
    angles = np.linspace(0, 2 * np.pi, n_bodies - 1, endpoint=False)
    r0 = 2.0
    pos[1:, 0] = r0 * np.cos(angles)
    pos[1:, 1] = r0 * np.sin(angles)

# Initial velocities: circular orbit speed around centre
vel = np.zeros((n_bodies, 2))
G = 1.0
for k in range(1, n_bodies):
    r = np.linalg.norm(pos[k])
    if r > 1e-9:
        v_circ = np.sqrt(G * masses[0] / r)
        # tangent direction (perpendicular to radial)
        tang = np.array([-pos[k, 1], pos[k, 0]]) / r
        vel[k] = v_circ * tang

# Leapfrog / velocity-Verlet integration
def accel(pos, masses, G):
    n = len(masses)
    acc = np.zeros_like(pos)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dr = pos[j] - pos[i]
            dist = np.sqrt(dr @ dr + 1e-4)   # softening
            acc[i] += G * masses[j] * dr / dist**3
    return acc

traj = np.empty((n_steps + 1, n_bodies, 2))
traj[0] = pos.copy()

acc = accel(pos, masses, G)
for step in range(n_steps):
    vel += 0.5 * dt * acc
    pos += dt * vel
    acc = accel(pos, masses, G)
    vel += 0.5 * dt * acc
    traj[step + 1] = pos.copy()

colors = ["#e05c00", "#4472c4", "#2aaa44", "#9b59b6", "#e74c3c"]
sizes  = [120, 60, 60, 60, 60]

fig, ax = plt.subplots(figsize=(6, 6))
for k in range(n_bodies):
    col = colors[k % len(colors)]
    ax.plot(traj[:, k, 0], traj[:, k, 1],
            lw=0.9, alpha=0.7, color=col)
    ax.scatter(traj[-1, k, 0], traj[-1, k, 1],
               s=sizes[k], color=col, zorder=5,
               edgecolors="white", linewidths=0.8,
               label=f"Body {k+1}  m={masses[k]:.2f}")

ax.set_xlabel("x")
ax.set_ylabel("y")
ax.set_title(f"N-Body Gravity ({n_bodies} bodies, {n_steps} steps)")
ax.legend(fontsize=8, loc="upper right")
ax.set_aspect("equal")
ax.grid(True, alpha=0.3)
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
