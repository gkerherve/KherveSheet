"""Build "Earth Globe (live)" — a =PY template that renders a 3D Earth
globe (orthographic projection) showing the real-time day/night
terminator.  The terminator line marks where sunrise and sunset are
occurring right now.  Pure matplotlib — no external geo libraries.

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

PY_BODY = r'''# 3D Earth globe with real-time day/night terminator.
# The orange terminator line marks where sunrise/sunset is happening.
# Press Ctrl+Enter to refresh, or right-click -> Python loop -> 1 second
# to make the globe spin: each run reads the rotation angle in B4, draws
# the globe at that longitude, then advances B4 by the step in B5.
import numpy as np, matplotlib.pyplot as plt, math
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
view_lat = float(ks("B3"))
view_lon = float(ks("B4"))            # current rotation (longitude, deg)
step     = float(ks("B5"))            # degrees to spin per refresh
follow   = str(ks("B6")).strip().lower() in ("yes", "true", "1")

# ── solar position ──────────────────────────────────────────────────
doy  = now.timetuple().tm_yday
hr   = now.hour + now.minute / 60 + now.second / 3600
decl = -23.44 * math.cos(math.radians(360 / 365 * (doy + 10)))
sub_lat = decl                    # subsolar latitude  = declination
sub_lon = -(hr - 12) * 15        # subsolar longitude (noon @ 0° lon)
if follow:
    view_lon = sub_lon

ks_set("B7", now.strftime("%H:%M:%S UTC"))
ks_set("B8", f"{decl:+.2f}\u00b0")
ks_set("B9", f"({sub_lat:+.1f}\u00b0, {sub_lon:+.1f}\u00b0)")

slr = math.radians(sub_lat); sll = math.radians(sub_lon)
sun = np.array([math.cos(slr)*math.cos(sll),
                math.cos(slr)*math.sin(sll), math.sin(slr)])

# ── orthographic projection ────────────────────────────────────────
def ortho(lat, lon):
    la = np.radians(np.asarray(lat, float))
    lo = np.radians(np.asarray(lon, float))
    l0 = math.radians(view_lon); n0 = math.radians(view_lat)
    dl = lo - l0
    x = np.cos(la) * np.sin(dl)
    y = math.cos(n0)*np.sin(la) - math.sin(n0)*np.cos(la)*np.cos(dl)
    v = math.sin(n0)*np.sin(la) + math.cos(n0)*np.cos(la)*np.cos(dl)
    return x, y, v > 0

# ── figure ──────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7.2, 7.2), facecolor="#080820")
ax.set_aspect("equal"); ax.set_xlim(-1.18, 1.18); ax.set_ylim(-1.18, 1.18)
ax.axis("off"); ax.set_facecolor("#080820")

# stars
rng = np.random.default_rng(42)
sx, sy = rng.uniform(-1.18, 1.18, 350), rng.uniform(-1.18, 1.18, 350)
out = sx**2 + sy**2 > 1.06
ax.scatter(sx[out], sy[out], s=rng.uniform(0.1, 2.5, out.sum()),
           c="white", alpha=0.6, zorder=0, linewidths=0)

# atmosphere glow
for r, a in [(1.06, 0.06), (1.04, 0.10), (1.02, 0.15)]:
    ax.add_patch(plt.Circle((0, 0), r, fc="none", ec="#4a90d9",
                             lw=2, alpha=a, zorder=0.5))
# ocean
ax.add_patch(plt.Circle((0, 0), 1.0, fc="#14466a", ec="#2a6090",
                         lw=1.2, zorder=1))

# ── grid lines ──────────────────────────────────────────────────────
for g in range(-60, 90, 30):
    lo = np.linspace(-180, 180, 500)
    x, y, v = ortho(np.full(500, g), lo)
    x, y = x.copy(), y.copy(); x[~v] = np.nan
    ax.plot(x, y, c="white", alpha=0.10, lw=0.4, zorder=2)
for g in range(-150, 180, 30):
    la = np.linspace(-90, 90, 300)
    x, y, v = ortho(la, np.full(300, g))
    x, y = x.copy(), y.copy(); x[~v] = np.nan
    ax.plot(x, y, c="white", alpha=0.10, lw=0.4, zorder=2)
# equator / prime meridian slightly brighter
for g in (0,):
    lo = np.linspace(-180, 180, 500)
    x, y, v = ortho(np.full(500, g), lo)
    x2 = x.copy(); x2[~v] = np.nan
    ax.plot(x2, y, c="white", alpha=0.20, lw=0.6, zorder=2)
    la = np.linspace(-90, 90, 300)
    x, y, v = ortho(la, np.full(300, g))
    x2 = x.copy(); x2[~v] = np.nan
    ax.plot(x2, y, c="white", alpha=0.20, lw=0.6, zorder=2)

# ── simplified continent outlines ──────────────────────────────────
_C = [
  # Africa
  [(37,-9),(37,10),(33,32),(30,33),(12,44),(2,42),(-10,40),
   (-26,33),(-35,20),(-34,18),(-4,9),(5,1),(5,-5),(15,-17),
   (22,-17),(26,-15),(33,-8),(37,-9)],
  # Europe
  [(36,-9),(37,-5),(43,-9),(44,-1),(47,-2),(48,-5),(49,0),
   (51,2),(54,6),(56,8),(58,6),(63,5),(65,12),(68,16),(71,26),
   (70,28),(64,30),(57,40),(52,40),(48,35),(46,30),(44,28),
   (42,29),(41,25),(40,20),(38,24),(37,22),(36,15),(36,-5),(36,-9)],
  # Asia (main mass)
  [(71,26),(72,60),(70,90),(72,120),(70,140),(66,170),(60,165),
   (55,140),(50,130),(42,132),(35,130),(30,122),(22,114),
   (10,106),(1,104),(-8,112),(-8,120),(5,105),(10,100),
   (8,77),(20,88),(22,72),(25,57),(30,48),(32,36),(36,36),
   (40,28),(42,29),(44,28),(46,30),(48,35),(52,40),(57,40),
   (64,30),(70,28),(71,26)],
  # North America
  [(72,-165),(72,-80),(68,-60),(60,-65),(52,-56),(47,-53),
   (45,-62),(44,-67),(41,-70),(30,-81),(25,-80),(25,-90),
   (20,-87),(18,-88),(15,-84),(16,-90),(20,-105),(24,-110),
   (32,-117),(38,-123),(48,-124),(55,-130),(58,-137),(60,-147),
   (64,-165),(72,-165)],
  # South America
  [(12,-72),(10,-76),(7,-78),(4,-77),(2,-80),(-5,-81),
   (-14,-76),(-18,-70),(-23,-70),(-35,-57),(-42,-64),
   (-55,-66),(-56,-68),(-52,-72),(-46,-76),(-40,-73),
   (-23,-42),(-13,-39),(-5,-35),(-2,-50),(2,-52),
   (6,-60),(8,-62),(11,-72),(12,-72)],
  # Australia
  [(-12,130),(-14,127),(-22,114),(-32,115),(-35,117),
   (-38,141),(-38,146),(-33,152),(-28,153),(-22,150),
   (-17,146),(-13,136),(-12,130)],
  # Greenland
  [(76,-72),(82,-40),(82,-20),(78,-18),(76,-20),(72,-22),
   (68,-28),(65,-40),(66,-53),(69,-55),(72,-56),(76,-72)],
  # Antarctica (rough)
  [(-65,-60),(-68,-60),(-72,-25),(-70,0),(-72,30),(-68,50),
   (-72,70),(-68,100),(-72,120),(-67,140),(-72,170),
   (-72,-170),(-68,-150),(-72,-130),(-68,-100),(-65,-60)],
]

for pts in _C:
    la0, lo0 = zip(*pts)
    la0, lo0 = list(la0), list(lo0)
    # interpolate between vertices for smooth curves
    fla, flo = [], []
    for i in range(len(la0) - 1):
        n = max(3, int(abs(la0[i+1]-la0[i]) + abs(lo0[i+1]-lo0[i])) // 3)
        fla.extend(np.linspace(la0[i], la0[i+1], n, endpoint=False).tolist())
        flo.extend(np.linspace(lo0[i], lo0[i+1], n, endpoint=False).tolist())
    fla.append(la0[-1]); flo.append(lo0[-1])
    x, y, v = ortho(np.array(fla), np.array(flo))
    x, y = x.copy(), y.copy()
    x[~v] = np.nan; y[~v] = np.nan
    ax.plot(x, y, c="#3aaa5a", lw=1.0, zorder=3, solid_capstyle="round")

# ── night shading (pixel-level day/night mask) ─────────────────────
N = 500
xi = np.linspace(-1, 1, N)
YI, XI = np.meshgrid(xi, xi, indexing="ij")
R2 = XI**2 + YI**2; disk = R2 <= 1.0
rho = np.sqrt(np.where(disk, R2, 0))
rho_s = np.where(rho > 1e-9, rho, 1.0)
c_a = np.arcsin(np.clip(rho, 0, 1))

n0 = math.radians(view_lat); l0 = math.radians(view_lon)
lat_i = np.arcsin(np.clip(
    np.cos(c_a)*math.sin(n0) + YI*np.sin(c_a)*math.cos(n0)/rho_s, -1, 1))
lon_i = l0 + np.arctan2(
    XI * np.sin(c_a),
    rho_s*math.cos(n0)*np.cos(c_a) - YI*math.sin(n0)*np.sin(c_a))

dot = (np.cos(lat_i)*np.cos(lon_i)*sun[0] +
       np.cos(lat_i)*np.sin(lon_i)*sun[1] +
       np.sin(lat_i)*sun[2])

# city-lights tint on night side (warm amber glow)
img = np.zeros((N, N, 4))
shadow = np.clip(-dot * 6, 0, 1)           # 0 = day, 1 = deep night
img[:, :, 3] = np.where(disk, shadow * 0.55, 0)
ax.imshow(img, extent=[-1, 1, -1, 1], zorder=5,
          interpolation="bilinear", origin="lower")

# ── terminator line ────────────────────────────────────────────────
if abs(sun[2]) < 0.999:
    u = np.cross(sun, [0, 0, 1])
else:
    u = np.cross(sun, [1, 0, 0])
u /= np.linalg.norm(u); w = np.cross(sun, u)
t = np.linspace(0, 2*np.pi, 600)
pts3 = np.outer(np.cos(t), u) + np.outer(np.sin(t), w)
tla = np.degrees(np.arcsin(np.clip(pts3[:, 2], -1, 1)))
tlo = np.degrees(np.arctan2(pts3[:, 1], pts3[:, 0]))
tx, ty, tv = ortho(tla, tlo)
tx, ty = tx.copy(), ty.copy(); tx[~tv] = np.nan
ax.plot(tx, ty, c="#ff6b35", lw=2.0, zorder=6, alpha=0.85,
        label="Terminator (sunrise / sunset)")

# ── sun & midnight markers ─────────────────────────────────────────
sx2, sy2, sv2 = ortho(sub_lat, sub_lon)
if sv2:
    ax.plot(float(sx2), float(sy2), "*", c="#ffd700", ms=20,
            zorder=7, mew=0.5, mec="#ff8c00")
    ax.annotate("Noon", (float(sx2), float(sy2) - 0.06),
                color="#ffd700", fontsize=8, ha="center", va="top",
                fontweight="bold", zorder=7)
mx, my, mv = ortho(-sub_lat, sub_lon + 180)
if mv:
    ax.plot(float(mx), float(my), "o", c="#2a2a5a", ms=10,
            zorder=7, mew=1.2, mec="#8888cc")
    ax.annotate("Midnight", (float(mx), float(my) - 0.06),
                color="#8888cc", fontsize=8, ha="center", va="top",
                fontweight="bold", zorder=7)

# ── title ──────────────────────────────────────────────────────────
ax.set_title(
    f"Earth \u2014 {now.strftime('%Y-%m-%d  %H:%M:%S UTC')}\n"
    f"Rotation {view_lon:+.0f}\u00b0   \u2502   "
    f"Orange line = sunrise / sunset",
    color="white", fontsize=11, fontweight="bold", pad=12)
fig.tight_layout()

# \u2500\u2500 spin: advance the rotation cell for the next refresh \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Writing B4 (which this cell also reads) does NOT re-trigger this cell,
# so on a 1 s loop the globe turns by `step` degrees each tick.
if step and not follow:
    nxt = (view_lon + step + 180.0) % 360.0 - 180.0
    ks_set("B4", round(nxt, 2))

plt.gcf()'''


def build():
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Earth Globe")
    s.title_block("Earth Globe (live)",
                  "3D globe with real-time day/night terminator "
                  "(sunrise / sunset line)")

    inputs = [("View latitude", 20),
              ("Rotation (lon °)", 0),
              ("Rotation step (°)", 10),
              ("Follow Sun", "no"),
              ("UTC time", ""), ("Solar declination", ""),
              ("Subsolar point", "")]
    for i, (label, v) in enumerate(inputs):
        r = 2 + i
        s.set(r, 0, label); s.set(r, 1, v)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center")
    # Auto-filled cells (B7–B9) get green.
    for r in (6, 7, 8):
        s.fmt(r, 1, bg=PALETTE["good"], align="center")

    s.set(1, 4, "Fetch \u25bc")
    s.fmt(1, 4, bold=True, font_color=PALETTE["header"])
    s.formula(2, 4, "=PY\n" + PY_BODY)

    s.note(0, 5,
           "Press Ctrl+Enter on the =PY cell (E3) to render the globe "
           "with the current UTC time.  To make it spin, right-click the "
           "cell -> Python loop -> 1 second: each run draws the globe at "
           "the rotation angle in B4, then increments B4 by the step in "
           "B5 (degrees per refresh).  Set B5 = 0 to stop spinning, or a "
           "negative value to turn the other way.  Set 'Follow Sun' (B6) "
           "to 'yes' to auto-centre on the subsolar point (spin pauses).")
    s.col_width(0, 120)

    out = os.path.join(os.path.dirname(__file__), "python", "Live Data",
                       "Earth Globe (live).ksheet")
    wb.save(out)
    print("Wrote", out)


if __name__ == "__main__":
    build()
