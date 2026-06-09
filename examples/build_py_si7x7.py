"""Build "Si(111) 7x7.ksheet" — a =PY cell that synthesises an STM-like
image of the Si(111)-(7x7) DAS reconstruction and writes the intensity
matrix into the grid starting at B10.

The A2 Python cell builds an N x N field (default 200 x 200): a hexagonal
super-lattice of dark corner holes with, in each rhombic unit cell, two
triangular half-cells of six bright adatoms each (the 12-adatom
Dimer-Adatom-Stacking-fault model).  It writes the matrix to B10 with
ks_set() and returns a preview figure.  Select B10:GR209 and Insert a
Heatmap to view the data that was written.

Run:  python examples/build_py_si7x7.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE


PY_CODE = "\n".join([
    "=PY",
    "import numpy as np",
    "import matplotlib.pyplot as plt",
    "try:",
    "    from scipy.ndimage import gaussian_filter",
    "except Exception:",
    "    gaussian_filter = None",
    "",
    "# ---- inputs (edit B4:B6, then press Ctrl+Enter) -----------------",
    "N     = int(ks('B4'))        # matrix size (N x N); keep <= 200",
    "cells = float(ks('B5'))      # number of 7x7 unit cells across",
    "seed  = int(ks('B6'))        # noise seed",
    "",
    "rng = np.random.default_rng(seed)",
    "L  = N / cells               # 7x7 cell side, in pixels",
    "a1 = np.array([L, 0.0])                       # hexagonal surface net",
    "a2 = np.array([L * 0.5, L * np.sqrt(3) / 2])  # 60 deg between a1, a2",
    "ys, xs = np.mgrid[0:N, 0:N].astype(float)",
    "",
    "def gauss(p, s):",
    "    return np.exp(-((xs-p[0])**2 + (ys-p[1])**2) / (2*s*s))",
    "",
    "def adatoms(Va, Vb, Vc, k=0.50):",
    "    # 6 adatoms per half-cell: 3 bright corner + 3 dimmer centre,",
    "    # forming an open ring (corners/edge-mids shrunk toward centroid).",
    "    G = (Va + Vb + Vc) / 3.0",
    "    corner = [Va+k*(G-Va), Vb+k*(G-Vb), Vc+k*(G-Vc)]",
    "    mid    = [(Va+Vb)/2, (Vb+Vc)/2, (Vc+Va)/2]",
    "    centre = [m+k*(G-m) for m in mid]",
    "    return corner, centre",
    "",
    "def tri_core(Va, Vb, Vc, t=0.20, e=0.018):",
    "    # soft triangular dark 'hole' around the half-cell centroid,",
    "    # enclosed by the adatom ring (via barycentric coordinates).",
    "    det = (Vb[1]-Vc[1])*(Va[0]-Vc[0]) + (Vc[0]-Vb[0])*(Va[1]-Vc[1])",
    "    l0 = ((Vb[1]-Vc[1])*(xs-Vc[0]) + (Vc[0]-Vb[0])*(ys-Vc[1]))/det",
    "    l1 = ((Vc[1]-Va[1])*(xs-Vc[0]) + (Va[0]-Vc[0])*(ys-Vc[1]))/det",
    "    mn = np.minimum(np.minimum(l0, l1), 1.0-l0-l1)",
    "    return 1.0 / (1.0 + np.exp(-(mn-t)/e))",
    "",
    "sig_c, sig_m, sig_h = 0.058*L, 0.048*L, 0.078*L",
    "img = np.full((N, N), 0.32)  # mid-grey background",
    "span = int(cells) + 3",
    "for m in range(-2, span):",
    "    for n in range(-2, span):",
    "        o = m*a1 + n*a2",
    "        V0, V1, V2, V3 = o, o+a1, o+a2, o+a1+a2",
    "        # rhombus split into unfaulted + faulted triangular halves",
    "        for (Va, Vb, Vc), amp in (((V0,V1,V2), 1.00),",
    "                                  ((V1,V3,V2), 0.86)):",
    "            cor, cen = adatoms(Va, Vb, Vc)",
    "            for p in cor:",
    "                img += amp*1.05*gauss(p, sig_c)",
    "            for p in cen:",
    "                img += amp*0.78*gauss(p, sig_m)",
    "            img -= 0.95*tri_core(Va, Vb, Vc)   # dark triangle",
    "        img -= 1.6*gauss(o, sig_h)             # deep corner hole",
    "",
    "if gaussian_filter is not None:",
    "    img = gaussian_filter(img, sigma=0.012*L)  # STM tip blur",
    "img += 0.020 * rng.standard_normal((N, N))",
    "img -= img.min()",
    "img /= img.max()",
    "",
    "# write the intensity matrix into the grid, top-left at B10",
    "ks_set('B10', np.round(img, 4))",
    "",
    "# preview (the data itself now lives in B10:.. as a heatmap source)",
    "fig, ax = plt.subplots(figsize=(5, 5))",
    "ax.imshow(img, cmap='afmhot', origin='lower', interpolation='bilinear')",
    "ax.set_title(f'Si(111)-(7x7)  -  {N}x{N}', fontsize=11)",
    "ax.set_axis_off()",
    "plt.tight_layout(pad=0.2)",
    "plt.gcf()",
])


def build() -> str:
    # Pre-allocate >= 201 columns: ks_set() grows rows but never columns,
    # so a 200-wide block starting at B (col 1) needs columns out to 200.
    wb = Workbook(min_rows=212, min_cols=205)
    s = wb.add_sheet("Si(111) 7x7")

    # Big title on row 0 (merged across the top).
    s.set(0, 0, "Si(111)-(7x7) Reconstruction")
    s.fmt(0, 0, bold=True, font_size=18, font_color=PALETTE["header"])
    s.merge(0, 0, 1, 6)

    # Row 1: A2 label points at the =PY program in B2; subtitle sits to
    # the right (C2:F2) so it never overlaps the B2 code cell.
    s.set(1, 0, "=PY  ->")
    s.fmt(1, 0, bold=True, align="right")
    s.set(1, 2, "An STM-like intensity matrix written to B10")
    s.fmt(1, 2, italic=True, font_color="#555555")
    s.merge(1, 2, 1, 4)

    inputs = [
        ("Matrix size  N  (<= 200)", 200),
        ("Unit cells across", 3.0),
        ("Noise seed", 0),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center")
    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 210)
    s.col_width(1, 90)

    # The =PY program in B2 (row index 1, col 1).
    s.formula(1, 1, PY_CODE)

    s.note(1, 1,
           "Press Ctrl+Enter on this cell to run it.\n"
           "It fills B10:GR209 with a 200x200 matrix and shows a preview.\n"
           "Then select that range and Insert > Heatmap to plot it.\n"
           "The 12-adatom DAS model: 2 triangular halves per rhombus,\n"
           "dark corner holes on a hexagonal super-lattice.",
           kind="note")

    s.set(7, 0, "Matrix (200x200) is written below, starting at B10:")
    s.fmt(7, 0, italic=True, font_color="#555555")
    s.set(9, 0, "B10 ->")
    s.fmt(9, 0, bold=True, align="right")

    out = os.path.join(_REPO, "examples", "python", "Materials Science",
                       "Si(111) 7x7.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
