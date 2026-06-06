"""Build "Kepler Orbit.ksheet" — planet orbiting a star.

Integrates the two-body gravitational orbit using velocity-Verlet and
plots the elliptical trajectory. A second cell returns the orbital period.

Run:  python examples/build_py_kepler_orbit.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE  # noqa: E402

OUT_DIR = os.path.join(_REPO, "examples", "python", "Physics Simulations")
OUT_PATH = os.path.join(OUT_DIR, "Kepler Orbit.ksheet")


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Kepler Orbit")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Kepler Orbit",
        "Velocity-Verlet integration of planetary motion — Kepler's laws",
    )

    # ── Input parameters ──────────────────────────────────────────────
    # We use scaled units: G=1, M_star=1.
    # For Earth-like orbit: semi-major axis a=1 AU, period T=2π years.
    s.set(3, 0, "Parameters  (G = M★ = 1, AU / yr units)")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Initial x-position x₀ (AU)",        1.0),   # B5  (aphelion)
        ("Initial y-position y₀ (AU)",         0.0),   # B6
        ("Initial x-velocity vx₀ (AU/yr)",     0.0),   # B7
        ("Initial y-velocity vy₀ (AU/yr)",     5.0),   # B8  (circular ~2π≈6.28)
        ("Time step dt (yr)",                  0.001),  # B9
        ("Number of steps",                   7000),   # B10
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.000")

    s.box(4, 0, 9, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 230)
    s.col_width(1, 110)

    # ── Sticky notes ──────────────────────────────────────────────────
    s.note(
        4, 1,
        "Default: circular orbit at 1 AU (vy₀ = 2π ≈ 6.28 AU/yr).\n"
        "Try vy₀ = 5.0 for an ellipse, vy₀ = 4.0 for a tighter ellipse.\n"
        "Edit B5–B10 then press Ctrl+Enter on each Python cell.",
        kind="note",
    )

    # ── Python cell 1: orbit plot ─────────────────────────────────────
    py_plot = """\
=PY
import numpy as np
import matplotlib.pyplot as plt

x0  = float(ks("B5"))
y0  = float(ks("B6"))
vx0 = float(ks("B7"))
vy0 = float(ks("B8"))
dt  = float(ks("B9"))
N   = max(100, min(20000, int(ks("B10"))))

# Gravitational constant * star mass = 1 in scaled units (2π yr period at 1 AU)
GM = 4 * np.pi**2   # AU^3/yr^2

pos = np.array([x0, y0], dtype=float)
vel = np.array([vx0, vy0], dtype=float)

def grav_acc(p):
    r = np.sqrt(p @ p)
    return -GM * p / r**3

traj = np.empty((N + 1, 2))
traj[0] = pos

acc = grav_acc(pos)
for i in range(N):
    vel += 0.5 * dt * acc
    pos += dt * vel
    acc  = grav_acc(pos)
    vel += 0.5 * dt * acc
    traj[i + 1] = pos

x, y = traj[:, 0], traj[:, 1]
r    = np.sqrt(x**2 + y**2)

fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))

# Left: orbit path coloured by speed
speeds = np.sqrt(np.diff(x)**2 + np.diff(y)**2) / dt
from matplotlib.collections import LineCollection
pts  = np.column_stack([x, y]).reshape(-1, 1, 2)
segs = np.concatenate([pts[:-1], pts[1:]], axis=1)
norm = plt.Normalize(speeds.min(), speeds.max())
lc   = LineCollection(segs, cmap="plasma", norm=norm, linewidth=1.5)
lc.set_array(speeds)
axes[0].add_collection(lc)
axes[0].autoscale()
axes[0].set_aspect("equal")
axes[0].plot(0, 0, "o", color="#f0c040", markersize=14,
             label="Star", zorder=5)
axes[0].plot(x0, y0, "o", color="#4472c4", markersize=6,
             label="Start", zorder=5)
axes[0].set_xlabel("x (AU)"); axes[0].set_ylabel("y (AU)")
axes[0].set_title("Planetary orbit (colour = orbital speed)")
axes[0].legend(fontsize=8)
axes[0].grid(True, alpha=0.25)
fig.colorbar(lc, ax=axes[0], label="speed (AU/yr)", fraction=0.04)

# Right: r(t) showing periodic variation
t_arr = np.arange(N + 1) * dt
axes[1].plot(t_arr, r, color="#4472c4", linewidth=1.2)
axes[1].set_xlabel("Time (yr)")
axes[1].set_ylabel("Distance from star (AU)")
axes[1].set_title("Distance vs time")
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.gcf()
"""
    s.set(11, 0, "Orbit Plot")
    s.fmt(11, 0, bold=True, font_color=PALETTE["header"])
    s.formula(12, 0, py_plot)
    s.fmt(12, 0, bg=PALETTE["band"], font_family="Courier New", font_size=9)

    # ── Python cell 2: orbital period ────────────────────────────────
    py_period = """\
=PY
import numpy as np

x0  = float(ks("B5"))
y0  = float(ks("B6"))
vx0 = float(ks("B7"))
vy0 = float(ks("B8"))
dt  = float(ks("B9"))
N   = max(100, min(20000, int(ks("B10"))))

GM = 4 * np.pi**2

pos = np.array([x0, y0], dtype=float)
vel = np.array([vx0, vy0], dtype=float)

def grav_acc(p):
    r = np.sqrt(p @ p)
    return -GM * p / r**3

r0     = np.sqrt(pos @ pos)
was_above = y0 >= 0
period = None

acc = grav_acc(pos)
for i in range(N):
    vel += 0.5 * dt * acc
    pos += dt * vel
    acc  = grav_acc(pos)
    vel += 0.5 * dt * acc
    r_now = np.sqrt(pos @ pos)
    # Detect one full y crossing back near x0 with same sign of x
    now_above = pos[1] >= 0
    if i > 10 and was_above and not now_above and pos[0] > 0:
        period = (i + 1) * dt
        break
    was_above = now_above

# Semi-major axis from initial conditions
r0 = np.sqrt(x0**2 + y0**2)
v0 = np.sqrt(vx0**2 + vy0**2)
E  = 0.5 * v0**2 - GM / r0          # specific orbital energy
if E < 0:
    a = -GM / (2 * E)
    T_kepler = 2 * np.pi * np.sqrt(a**3 / GM)
else:
    T_kepler = float("inf")

if period is not None:
    f"Numerical period: {period:.4f} yr   Kepler T=2π√(a³/GM): {T_kepler:.4f} yr"
else:
    f"Period not detected in {N} steps   Kepler T: {T_kepler:.4f} yr"
"""
    s.set(11, 3, "Orbital Period")
    s.fmt(11, 3, bold=True, font_color=PALETTE["header"])
    s.formula(12, 3, py_period)
    s.fmt(12, 3, bg=PALETTE["good"], font_family="Courier New", font_size=9,
          wrap=True)
    s.col_width(3, 280)

    os.makedirs(OUT_DIR, exist_ok=True)
    wb.save(OUT_PATH)
    return OUT_PATH


if __name__ == "__main__":
    print("Wrote", build())
