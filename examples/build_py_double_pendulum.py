"""Build "Double Pendulum.ksheet" — chaotic double-pendulum trajectory.

Integrates the double-pendulum ODEs with RK4 and plots the path of the
lower bob to visualise chaotic behaviour.

Run:  python examples/build_py_double_pendulum.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE  # noqa: E402

OUT_DIR = os.path.join(_REPO, "examples", "python", "Physics Simulations")
OUT_PATH = os.path.join(OUT_DIR, "Double Pendulum.ksheet")


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Double Pendulum")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Double Pendulum",
        "Chaotic motion — RK4 integration of the double-pendulum equations",
    )

    # ── Input parameters ──────────────────────────────────────────────
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Initial angle θ₁ (°)",   120.0),  # B5
        ("Initial angle θ₂ (°)",   -30.0),  # B6
        ("Rod length L₁ (m)",        1.0),  # B7
        ("Rod length L₂ (m)",        1.0),  # B8
        ("Mass m₁ (kg)",             1.0),  # B9
        ("Mass m₂ (kg)",             1.0),  # B10
        ("Simulation time (s)",     15.0),  # B11
        ("Number of steps",        2000),   # B12
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.box(4, 0, 11, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 190)
    s.col_width(1, 110)

    # ── Sticky notes ──────────────────────────────────────────────────
    s.note(
        4, 1,
        "Edit B5–B12 then press Ctrl+Enter on the Python cell.\n"
        "Try θ₁=120°, θ₂=-30° (default) vs θ₂=-31° to see chaos.\n"
        "Keep steps <= 3000 for fast rendering.",
        kind="note",
    )
    s.note(
        5, 1,
        "The double pendulum is the classic chaos demo:\n"
        "tiny changes in initial angle lead to wildly\n"
        "different trajectories after a few seconds.",
        kind="comment",
    )

    # ── Python cell: RK4 integration + plot ──────────────────────────
    py_code = """\
=PY
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

th1_0 = np.radians(float(ks("B5")))
th2_0 = np.radians(float(ks("B6")))
L1    = float(ks("B7"))
L2    = float(ks("B8"))
m1    = float(ks("B9"))
m2    = float(ks("B10"))
T     = float(ks("B11"))
N     = max(100, min(5000, int(ks("B12"))))
g     = 9.81

def derivs(state, L1, L2, m1, m2, g):
    th1, w1, th2, w2 = state
    dth = th2 - th1
    denom1 = (m1 + m2) * L1 - m2 * L1 * np.cos(dth) ** 2
    denom2 = (L2 / L1) * denom1
    dw1 = (m2 * L1 * w1**2 * np.sin(dth) * np.cos(dth)
           + m2 * g * np.sin(th2) * np.cos(dth)
           + m2 * L2 * w2**2 * np.sin(dth)
           - (m1 + m2) * g * np.sin(th1)) / denom1
    dw2 = (-m2 * L2 * w2**2 * np.sin(dth) * np.cos(dth)
           + (m1 + m2) * g * np.sin(th1) * np.cos(dth)
           - (m1 + m2) * L1 * w1**2 * np.sin(dth)
           - (m1 + m2) * g * np.sin(th2)) / denom2
    return np.array([w1, dw1, w2, dw2])

dt    = T / N
state = np.array([th1_0, 0.0, th2_0, 0.0])
traj  = np.empty((N + 1, 4))
traj[0] = state

for i in range(N):
    k1 = derivs(state, L1, L2, m1, m2, g)
    k2 = derivs(state + 0.5 * dt * k1, L1, L2, m1, m2, g)
    k3 = derivs(state + 0.5 * dt * k2, L1, L2, m1, m2, g)
    k4 = derivs(state + dt * k3, L1, L2, m1, m2, g)
    state = state + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)
    traj[i + 1] = state

# Lower bob position
x2 = (L1 * np.sin(traj[:, 0]) + L2 * np.sin(traj[:, 2]))
y2 = -(L1 * np.cos(traj[:, 0]) + L2 * np.cos(traj[:, 2]))

# Colour by time for visual interest
times = np.linspace(0, 1, len(x2))
pts   = np.column_stack([x2, y2]).reshape(-1, 1, 2)
segs  = np.concatenate([pts[:-1], pts[1:]], axis=1)
norm  = plt.Normalize(0, 1)
lc    = LineCollection(segs, cmap="plasma", norm=norm, linewidth=0.7, alpha=0.85)
lc.set_array(times)

fig, ax = plt.subplots(figsize=(6, 6))
ax.add_collection(lc)
ax.autoscale()
ax.set_aspect("equal")
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_title(f"Double Pendulum  th1={np.degrees(th1_0):.1f}deg  th2={np.degrees(th2_0):.1f}deg  T={T:.1f}s")
fig.colorbar(lc, ax=ax, label="Time", fraction=0.04, pad=0.02)
ax.grid(True, alpha=0.25)
plt.tight_layout()
plt.gcf()
"""
    s.set(13, 0, "Simulation + Plot")
    s.fmt(13, 0, bold=True, font_color=PALETTE["header"])
    s.formula(14, 0, py_code)
    s.fmt(14, 0, bg=PALETTE["band"], font_family="Courier New", font_size=9)

    os.makedirs(OUT_DIR, exist_ok=True)
    wb.save(OUT_PATH)
    return OUT_PATH


if __name__ == "__main__":
    print("Wrote", build())
