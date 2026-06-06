"""Build "Percolation.ksheet" — site percolation with cluster labelling.

=PY cells generate a random occupied grid, label clusters with
scipy.ndimage.label, plot coloured clusters, and report whether a
spanning cluster exists.

Run:  python examples/build_py_percolation.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=12)
    s = wb.add_sheet("Percolation")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Site Percolation",
                  "Random lattice — colours show distinct clusters")

    # ── Input parameters ──────────────────────────────────────────────
    inputs = [
        ("Grid size  L",          80),
        ("Occupation probability p", 0.593),
        ("Random seed",            42),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.000")
    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 210)
    s.col_width(1, 90)

    s.note(3, 1,
           "p_c ≈ 0.5927 for the 2-D square lattice.\n"
           "Try p=0.4 (no spanning), p=0.593, or p=0.7 (large cluster).\n"
           "Edit inputs and press Ctrl+Enter on the =PY cells.",
           kind="note")

    # ── =PY cell: generate grid, label clusters, plot ─────────────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "from scipy.ndimage import label",
        "L    = int(ks('B4'))",
        "p    = float(ks('B5'))",
        "seed = int(ks('B6'))",
        "rng  = np.random.default_rng(seed)",
        "grid = (rng.random((L, L)) < p).astype(np.int32)",
        "# Label connected components (4-connectivity)",
        "labeled, n_clusters = label(grid)",
        "# Build display image: 0 = empty (white), clusters = colour index",
        "display = labeled.astype(float)",
        "display[grid == 0] = np.nan",
        "fig, ax = plt.subplots(figsize=(5, 5))",
        "im = ax.imshow(display, cmap='tab20', interpolation='nearest',",
        "               vmin=1, vmax=max(n_clusters, 1))",
        "ax.set_title(f'L={L},  p={p:.3f},  clusters={n_clusters}', fontsize=11)",
        "ax.set_xlabel('column  j')",
        "ax.set_ylabel('row  i')",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(8, 0, py_plot)

    # ── =PY cell: spanning cluster test + largest cluster fraction ────
    s.set(8, 4, "Spanning cluster:")
    s.set(9, 4, "Largest cluster (%):")
    for r in range(8, 10):
        s.fmt(r, 4, bold=True, align="right")
    s.col_width(4, 175)

    py_stats = "\n".join([
        "=PY",
        "import numpy as np",
        "from scipy.ndimage import label",
        "L    = int(ks('B4'))",
        "p    = float(ks('B5'))",
        "seed = int(ks('B6'))",
        "rng  = np.random.default_rng(seed)",
        "grid = (rng.random((L, L)) < p).astype(np.int32)",
        "labeled, n_clusters = label(grid)",
        "spans = False",
        "largest_frac = 0.0",
        "if n_clusters > 0:",
        "    sizes = np.bincount(labeled.ravel())[1:]",
        "    largest = sizes.max()",
        "    largest_frac = float(largest) / (L * L)",
        "    # Check each cluster for top-to-bottom span",
        "    for cid in range(1, n_clusters + 1):",
        "        rows_hit = np.where(labeled == cid)[0]",
        "        if rows_hit.min() == 0 and rows_hit.max() == L - 1:",
        "            spans = True",
        "            break",
        "span_str = 'YES' if spans else 'NO'",
        "ks_set('F9', span_str)",
        "ks_set('F10', round(largest_frac * 100, 2))",
        "span_str",
    ])
    s.formula(8, 5, py_stats)
    s.fmt(8, 5, bg=PALETTE["good"], bold=True, align="center")
    s.fmt(9, 5, bg=PALETTE["band"], bold=True, align="center",
          number_format="0.00")
    s.box(8, 4, 9, 5, color=PALETTE["header"], width=1.0)
    s.col_width(5, 80)

    s.note(8, 0,
           "Each colour is a distinct connected cluster.\n"
           "Unoccupied sites are white.  Near p_c a cluster\n"
           "first spans the full grid top-to-bottom.",
           kind="note")

    # ── Equation: percolation threshold label ────────────────────────
    s.equation(
        r"p_c \approx 0.5927\quad(\mathrm{2D\ square\ lattice})",
        at=(520, 300), fontsize=15, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(340, 46),
    )

    out = os.path.join(_REPO, "examples", "python", "Materials Science",
                       "Percolation.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
