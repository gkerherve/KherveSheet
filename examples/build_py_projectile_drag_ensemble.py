"""Build "Projectile Drag Ensemble.ksheet" — ensemble of projectiles with drag.

Launches many projectiles with randomised speed/angle and quadratic air drag,
plots all trajectories, and returns mean/std of landing range.

Run:  python examples/build_py_projectile_drag_ensemble.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE  # noqa: E402

OUT_DIR = os.path.join(_REPO, "examples", "python", "Physics Simulations")
OUT_PATH = os.path.join(OUT_DIR, "Projectile Drag Ensemble.ksheet")


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Drag Ensemble")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Projectile Drag Ensemble",
        "Randomised launch with quadratic air drag — spread of landing ranges",
    )

    # ── Input parameters ──────────────────────────────────────────────
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Mean launch speed v₀ (m/s)",   40.0),  # B5
        ("Std of speed σ_v (m/s)",        5.0),  # B6
        ("Mean launch angle θ (°)",       45.0),  # B7
        ("Std of angle σ_θ (°)",          5.0),  # B8
        ("Drag coefficient C_d",          0.02),  # B9
        ("Number of projectiles",           60),  # B10
        ("Random seed",                     42),  # B11
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.box(4, 0, 10, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 210)
    s.col_width(1, 110)

    # ── Sticky note ───────────────────────────────────────────────────
    s.note(
        4, 1,
        "Edit B5–B11 then press Ctrl+Enter on each Python cell.\n"
        "C_d=0 gives zero drag (analytical parabola).\n"
        "Keep projectiles <= 200 for fast rendering.",
        kind="note",
    )

    # ── Python cell 1: trajectory plot ───────────────────────────────
    py_plot = """\
=PY
import numpy as np
import matplotlib.pyplot as plt

v0_mean  = float(ks("B5"))
v0_std   = float(ks("B6"))
th_mean  = float(ks("B7"))
th_std   = float(ks("B8"))
Cd       = float(ks("B9"))
n_proj   = max(1, min(300, int(ks("B10"))))
seed     = int(ks("B11"))

rng = np.random.default_rng(seed)
g   = 9.81
dt  = 0.02

speeds = rng.normal(v0_mean, v0_std, n_proj)
angles = np.radians(rng.normal(th_mean, th_std, n_proj))

landing_ranges = []
fig, ax = plt.subplots(figsize=(7, 4))

for i in range(n_proj):
    vx = speeds[i] * np.cos(angles[i])
    vy = speeds[i] * np.sin(angles[i])
    xs, ys = [0.0], [0.0]
    x, y = 0.0, 0.0
    for _ in range(5000):
        v = np.sqrt(vx**2 + vy**2)
        ax_drag = -Cd * v * vx
        ay_drag = -Cd * v * vy
        vx += (ax_drag) * dt
        vy += (-g + ay_drag) * dt
        x  += vx * dt
        y  += vy * dt
        if y < 0:
            break
        xs.append(x)
        ys.append(y)
    landing_ranges.append(x)
    ax.plot(xs, ys, lw=0.5, alpha=0.35, color="#4472c4")

ax.set_xlabel("Horizontal distance (m)")
ax.set_ylabel("Height (m)")
ax.set_title(f"Projectile Ensemble  n={n_proj}, Cd={Cd:.3f}")
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.gcf()
"""
    s.set(12, 0, "Trajectory Plot")
    s.fmt(12, 0, bold=True, font_color=PALETTE["header"])
    s.formula(13, 0, py_plot)
    s.fmt(13, 0, bg=PALETTE["band"], font_family="Courier New", font_size=9)

    # ── Python cell 2: statistics ─────────────────────────────────────
    py_stats = """\
=PY
import numpy as np

v0_mean  = float(ks("B5"))
v0_std   = float(ks("B6"))
th_mean  = float(ks("B7"))
th_std   = float(ks("B8"))
Cd       = float(ks("B9"))
n_proj   = max(1, min(300, int(ks("B10"))))
seed     = int(ks("B11"))

rng = np.random.default_rng(seed)
g   = 9.81
dt  = 0.02

speeds = rng.normal(v0_mean, v0_std, n_proj)
angles = np.radians(rng.normal(th_mean, th_std, n_proj))

landing_ranges = []
for i in range(n_proj):
    vx = speeds[i] * np.cos(angles[i])
    vy = speeds[i] * np.sin(angles[i])
    x, y = 0.0, 0.0
    for _ in range(5000):
        v = np.sqrt(vx**2 + vy**2)
        vx += (-Cd * v * vx) * dt
        vy += (-g + (-Cd * v * vy)) * dt
        x  += vx * dt
        y  += vy * dt
        if y < 0:
            break
    landing_ranges.append(x)

ranges = np.array(landing_ranges)
f"Mean range: {ranges.mean():.2f} m,  Std: {ranges.std():.2f} m"
"""
    s.set(12, 3, "Landing Range Statistics")
    s.fmt(12, 3, bold=True, font_color=PALETTE["header"])
    s.formula(13, 3, py_stats)
    s.fmt(13, 3, bg=PALETTE["good"], font_family="Courier New", font_size=9,
          wrap=True)
    s.col_width(3, 260)

    os.makedirs(OUT_DIR, exist_ok=True)
    wb.save(OUT_PATH)
    return OUT_PATH


if __name__ == "__main__":
    print("Wrote", build())
