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
    "",
    "def tri_adatoms(Va, Vb, Vc, k=0.55):",
    "    # six adatoms = corners + edge midpoints of the half-cell",
    "    # triangle, shrunk toward its centroid by k.",
    "    G = (Va + Vb + Vc) / 3.0",
    "    Wa, Wb, Wc = (G + k * (V - G) for V in (Va, Vb, Vc))",
    "    return [Wa, Wb, Wc, (Wa+Wb)/2, (Wb+Wc)/2, (Wa+Wc)/2]",
    "",
    "ys, xs = np.mgrid[0:N, 0:N].astype(float)",
    "img = np.zeros((N, N))",
    "sig_a = 0.058 * L            # adatom spot width",
    "sig_h = 0.085 * L            # corner-hole width",
    "",
    "span = int(cells) + 3",
    "for m in range(-2, span):",
    "    for n in range(-2, span):",
    "        o = m * a1 + n * a2",
    "        # dark corner hole at every super-lattice point",
    "        img -= 0.9 * np.exp(-((xs-o[0])**2 + (ys-o[1])**2)",
    "                            / (2 * sig_h**2))",
    "        # rhombus split into unfaulted + faulted triangular halves",
    "        V0, V1, V2, V3 = o, o+a1, o+a2, o+a1+a2",
    "        for ada, amp in ((tri_adatoms(V0, V1, V2), 1.00),",
    "                         (tri_adatoms(V1, V2, V3), 0.82)):",
    "            for p in ada:",
    "                img += amp * np.exp(-((xs-p[0])**2 + (ys-p[1])**2)",
    "                                    / (2 * sig_a**2))",
    "",
    "img += 0.04 * rng.standard_normal((N, N))",
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
        ("Unit cells across", 3.5),
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

    out = os.path.join(_REPO, "Si(111) 7x7.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
