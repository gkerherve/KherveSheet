"""Build "Earth Globe 3D (live)" — a =PY template that renders a REAL 3D
sphere (matplotlib mplot3d) wrapped with an equirectangular Earth
texture and lit by the real-time Sun direction (day / night).  Put the
cell on a Python loop and it spins: each run rotates the camera azimuth
by a step and writes the new angle back to its cell.

The texture is downloaded once and cached in the shared namespace; if
the network is unavailable it falls back to a procedural land/ocean
globe built from simplified continent polygons, so the example always
works offline.

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

PY_BODY = r'''# Real 3D Earth globe (matplotlib mplot3d) that spins.
# A sphere is wrapped with an Earth texture (downloaded once, then
# cached) and shaded by the real-time Sun direction. Right-click this
# cell -> Python loop -> 0.5 second to make it turn: each run rotates the
# camera azimuth (B4) by the step in B5 and writes the new angle back.
import numpy as np, matplotlib.pyplot as plt, math, urllib.request
from datetime import datetime, timezone
from mpl_toolkits.mplot3d import Axes3D            # noqa: F401 (registers 3d)
from matplotlib.path import Path

tilt = float(ks("B3"))      # camera elevation, degrees
rot  = float(ks("B4"))      # camera azimuth (rotation), degrees
step = float(ks("B5"))      # degrees to spin per refresh
res  = int(ks("B6"))        # sphere grid resolution (higher = sharper/slower)
url  = str(ks("B7")).strip()  # equirectangular Earth texture URL ("" = procedural)

# Simplified continent polygons (lat, lon) for the offline fallback.
_C = [
  [(37,-9),(37,10),(33,32),(30,33),(12,44),(2,42),(-10,40),(-26,33),
   (-35,20),(-34,18),(-4,9),(5,1),(5,-5),(15,-17),(22,-17),(26,-15),
   (33,-8),(37,-9)],
  [(36,-9),(43,-9),(49,0),(54,6),(58,6),(65,12),(71,26),(64,30),
   (57,40),(48,35),(44,28),(41,25),(38,24),(36,15),(36,-9)],
  [(71,26),(72,60),(70,90),(72,120),(70,140),(66,170),(55,140),
   (42,132),(35,130),(22,114),(10,106),(1,104),(8,77),(22,72),
   (30,48),(32,36),(40,28),(44,28),(52,40),(64,30),(71,26)],
  [(72,-165),(72,-80),(60,-65),(47,-53),(41,-70),(25,-80),(20,-105),
   (32,-117),(48,-124),(58,-137),(64,-165),(72,-165)],
  [(12,-72),(2,-80),(-18,-70),(-35,-57),(-55,-66),(-46,-76),(-23,-42),
   (-5,-35),(6,-60),(12,-72)],
  [(-12,130),(-22,114),(-35,117),(-38,146),(-28,153),(-17,146),
   (-12,130)],
  [(76,-72),(82,-40),(78,-18),(72,-22),(66,-53),(72,-56),(76,-72)],
  [(-65,-60),(-72,-25),(-72,30),(-72,70),(-72,120),(-72,170),
   (-72,-170),(-72,-130),(-65,-60)],
]

# ── build sphere + base colour grid, cached between refreshes ────────
g = globals()
cache = g.get("_globe3d")
if cache is None or cache["key"] != (res, url):
    nlat, nlon = res, 2 * res
    lats = np.linspace(90, -90, nlat)
    lons = np.linspace(-180, 180, nlon)
    LON, LAT = np.meshgrid(lons, lats)
    la, lo = np.radians(LAT), np.radians(LON)
    X = np.cos(la) * np.cos(lo)
    Y = np.cos(la) * np.sin(lo)
    Z = np.sin(la)
    tex = None
    if url:
        try:                                   # download + decode the texture
            from PyQt5.QtGui import QImage
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=8).read()
            qi = QImage()
            qi.loadFromData(raw)
            qi = qi.convertToFormat(QImage.Format_RGB888)
            w, h = qi.width(), qi.height()
            ptr = qi.bits(); ptr.setsize(h * w * 3)
            tex = np.frombuffer(ptr, np.uint8).reshape(h, w, 3) / 255.0
        except Exception:
            tex = None
    if tex is not None:                        # sample texture onto the grid
        H, W = tex.shape[:2]
        ri = np.clip(((90 - LAT) / 180 * (H - 1)).astype(int), 0, H - 1)
        ci = np.clip(((LON + 180) / 360 * (W - 1)).astype(int), 0, W - 1)
        base = tex[ri, ci]
        src = "live texture"
    else:                                      # procedural land / ocean mask
        pts = np.column_stack([LON.ravel(), LAT.ravel()])
        land = np.zeros(LON.shape, bool)
        for poly in _C:
            xy = [(p[1], p[0]) for p in poly]
            land |= Path(xy).contains_points(pts).reshape(LON.shape)
        ocean = np.array([0.07, 0.27, 0.45]); grn = np.array([0.20, 0.45, 0.22])
        base = np.where(land[..., None], grn, ocean)
        src = "procedural"
    cache = {"key": (res, url), "X": X, "Y": Y, "Z": Z,
             "base": base, "src": src}
    g["_globe3d"] = cache

X, Y, Z, base, src = (cache["X"], cache["Y"], cache["Z"],
                      cache["base"], cache["src"])

# ── real-time Sun direction for day / night shading ─────────────────
now = datetime.now(timezone.utc)
doy = now.timetuple().tm_yday
hr = now.hour + now.minute / 60 + now.second / 3600
decl = -23.44 * math.cos(math.radians(360 / 365 * (doy + 10)))
sub_lon = -(hr - 12) * 15
slr, sll = math.radians(decl), math.radians(sub_lon)
sun = np.array([math.cos(slr) * math.cos(sll),
                math.cos(slr) * math.sin(sll), math.sin(slr)])
bright = np.clip(X * sun[0] + Y * sun[1] + Z * sun[2], -1, 1)
shade = (0.30 + 0.70 * np.clip(bright, 0, 1))[..., None]   # night stays dim
rgb = np.clip(base * shade, 0, 1)
rgba = np.concatenate([rgb, np.ones(rgb.shape[:2] + (1,))], axis=-1)

# ── draw the 3D sphere ──────────────────────────────────────────────
fig = plt.figure(figsize=(6.6, 6.6), facecolor="#05050f")
ax = fig.add_subplot(111, projection="3d")
ax.set_box_aspect((1, 1, 1))
ax.plot_surface(X, Y, Z, facecolors=rgba, rstride=1, cstride=1,
                linewidth=0, antialiased=False, shade=False)
ax.set_axis_off()
for lim in (ax.set_xlim, ax.set_ylim, ax.set_zlim):
    lim(-0.68, 0.68)
ax.view_init(elev=tilt, azim=rot)
fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
ax.set_title(f"Earth 3D — {now.strftime('%H:%M:%S UTC')}   "
             f"rotation {rot:+.0f}°   [{src}]",
             color="white", fontsize=11, fontweight="bold", y=0.93)

ks_set("B8", src)
ks_set("B9", now.strftime("%H:%M:%S UTC"))

# spin: advance the rotation cell for the next refresh (does not
# re-trigger this cell even though it reads B4).
if step:
    ks_set("B4", round((rot + step) % 360.0, 2))

plt.gcf()'''


def build():
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Earth 3D")
    s.title_block("Earth Globe 3D (live)",
                  "A real 3D sphere (mplot3d) wrapped with an Earth "
                  "texture, lit by the Sun and spinning")

    tex = ("https://raw.githubusercontent.com/mrdoob/three.js/dev/"
           "examples/textures/planets/earth_atmos_2048.jpg")
    inputs = [("Tilt (elev °)", 18),
              ("Rotation (azim °)", 0),
              ("Spin step (°)", 6),
              ("Resolution", 72),
              ("Texture URL", tex),
              ("Texture source", ""),
              ("UTC time", "")]
    for i, (label, v) in enumerate(inputs):
        r = 2 + i
        s.set(r, 0, label); s.set(r, 1, v)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="left")
    for r in (7, 8):                                   # auto-filled cells
        s.fmt(r, 1, bg=PALETTE["good"], align="center")

    s.set(1, 4, "Render ▼")
    s.fmt(1, 4, bold=True, font_color=PALETTE["header"])
    s.formula(2, 4, "=PY\n" + PY_BODY)

    s.note(0, 5,
           "Press Ctrl+Enter on the =PY cell (E3) to render the 3D globe. "
           "To make it spin, right-click the cell -> Python loop -> 0.5 "
           "second (3D rendering is heavier than 2D, so very fast loops "
           "may lag).  B4 is the rotation angle (incremented each frame by "
           "the step in B5 — set B5 = 0 to stop, negative to reverse).  B3 "
           "tilts the view, B6 sets sphere detail (higher = sharper but "
           "slower).  The texture (B7) is downloaded once and cached; clear "
           "B7 for a procedural land/ocean globe that needs no network.")
    s.col_width(0, 120)
    s.col_width(1, 360)

    out = os.path.join(os.path.dirname(__file__), "python", "Live Data",
                       "Earth Globe 3D (live).ksheet")
    wb.save(out)
    print("Wrote", out)


if __name__ == "__main__":
    build()
