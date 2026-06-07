"""Build "Bouncing Particles" — a =PY template that animates circular
particles in a square box.  They move at constant speed and undergo
equal-mass elastic collisions with each other and with the four walls.
State is kept in the shared Python namespace between refreshes, so each
re-run advances the simulation by one frame; put the cell on a fast
Python loop (0.1 s) to animate it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from ksheet_author import Workbook, PALETTE  # noqa: E402

PY_BODY = r'''# Bouncing particles in a box (equal-mass elastic collisions).
# Each refresh advances the simulation one frame; the particle state is
# kept in the shared namespace between runs.  Right-click this cell ->
# Python loop -> 0.1 second to animate. Edit B3..B7 then re-run to reset.
import numpy as np, matplotlib.pyplot as plt

n    = int(ks("B3"))      # number of particles
box  = float(ks("B4"))    # box side length
spd  = float(ks("B5"))    # speed (units moved per frame)
seed = int(ks("B6"))      # random seed (reproducible start)
rad  = float(ks("B7"))    # particle radius

# Keep the simulation state across refreshes in the shared namespace.
# Re-initialise whenever any input changes (so editing a cell resets it).
g = globals()
st = g.get("_balls")
key = (n, box, seed, round(spd, 6), round(rad, 6))
if st is None or st["key"] != key:
    rng = np.random.default_rng(seed)
    pos = rng.uniform(rad, box - rad, size=(n, 2))
    ang = rng.uniform(0, 2 * np.pi, n)
    vel = np.column_stack([np.cos(ang), np.sin(ang)]) * spd
    st = {"key": key, "pos": pos, "vel": vel,
          "c": rng.random(n), "frame": 0}
    g["_balls"] = st

pos, vel = st["pos"], st["vel"]

# 1) advance one step
pos += vel

# 2) bounce off the four walls (reflect the velocity component)
for d in (0, 1):
    lo = pos[:, d] < rad
    pos[lo, d] = rad
    vel[lo, d] = np.abs(vel[lo, d])
    hi = pos[:, d] > box - rad
    pos[hi, d] = box - rad
    vel[hi, d] = -np.abs(vel[hi, d])

# 3) particle-particle elastic collisions (equal mass): swap the
#    velocity components along the line joining the two centres.
for i in range(n):
    for j in range(i + 1, n):
        dx = pos[j] - pos[i]
        dist = float(np.hypot(dx[0], dx[1]))
        if 1e-9 < dist < 2 * rad:
            nrm = dx / dist
            overlap = 2 * rad - dist
            pos[i] -= nrm * overlap / 2.0     # push apart so they separate
            pos[j] += nrm * overlap / 2.0
            vn = float((vel[i] - vel[j]) @ nrm)
            if vn > 0:                         # only if approaching
                vel[i] -= vn * nrm
                vel[j] += vn * nrm

st["frame"] += 1
ks_set("B8", st["frame"])                      # frame counter

# 4) draw the box and the circles
fig, ax = plt.subplots(figsize=(6.2, 6.2), facecolor="#0e1117")
ax.set_xlim(0, box); ax.set_ylim(0, box)
ax.set_aspect("equal"); ax.set_facecolor("#0e1117")
ax.set_xticks([]); ax.set_yticks([])
for sp in ax.spines.values():
    sp.set_color("#4a90d9"); sp.set_linewidth(2.5)
cmap = plt.get_cmap("turbo")
for i in range(n):
    ax.add_patch(plt.Circle(pos[i], rad, color=cmap(st["c"][i]),
                            ec="white", lw=0.6, zorder=3))
ax.set_title(f"{n} particles  ·  frame {st['frame']}",
             color="white", fontsize=11, fontweight="bold")
fig.tight_layout()
plt.gcf()'''


def build():
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Particles")
    s.title_block("Bouncing Particles",
                  "Circles in a box with elastic wall & particle "
                  "collisions")

    inputs = [("Particles", 14), ("Box size", 10.0), ("Speed", 0.18),
              ("Seed", 7), ("Radius", 0.45), ("Frame", 0)]
    for i, (label, v) in enumerate(inputs):
        r = 2 + i
        s.set(r, 0, label); s.set(r, 1, v)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center")
    s.fmt(7, 1, bg=PALETTE["good"], align="center")   # frame (auto)

    s.set(1, 4, "Run ▼")
    s.fmt(1, 4, bold=True, font_color=PALETTE["header"])
    s.formula(2, 4, "=PY\n" + PY_BODY)

    s.note(0, 5,
           "Press Ctrl+Enter on the =PY cell (E3) to step the simulation "
           "once.  To animate it, right-click the cell -> Python loop -> "
           "0.1 second (or 0.5 s for a calmer pace).  The particles bounce "
           "off the walls and collide elastically with each other.  Edit "
           "Particles / Box size / Speed / Seed / Radius (B3:B7) and re-run "
           "to restart with a new configuration.")
    s.col_width(0, 90)

    out = os.path.join(os.path.dirname(__file__), "python", "Simulations",
                       "Bouncing Particles.ksheet")
    wb.save(out)
    print("Wrote", out)


if __name__ == "__main__":
    build()
