"""Build "Random Sequential Adsorption.ksheet" — RSA coverage simulation.

=PY cells simulate random sequential adsorption of unit discs onto a
lattice (no overlap), plot the final coverage, and report the jamming
coverage fraction.

Run:  python examples/build_py_rsa.py

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
    s = wb.add_sheet("RSA")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Random Sequential Adsorption",
                  "Irreversible deposition of particles with no overlap")

    # ── Input parameters ──────────────────────────────────────────────
    inputs = [
        ("Grid size  L",          80),
        ("Deposition attempts",  8000),
        ("Random seed",            42),
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0")
    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 195)
    s.col_width(1, 90)

    s.note(3, 1,
           "Each attempt picks a random site; if it and its 4 neighbours\n"
           "are all empty the particle is adsorbed there.\n"
           "The jamming limit for this model is ~0.546.\n"
           "Edit inputs and press Ctrl+Enter on the =PY cells.",
           kind="note")

    # ── =PY cell: run RSA + plot ──────────────────────────────────────
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "L        = int(ks('B4'))",
        "attempts = int(ks('B5'))",
        "seed     = int(ks('B6'))",
        "rng = np.random.default_rng(seed)",
        "grid = np.zeros((L, L), dtype=np.int8)",
        "# Randomly pick sites; accept if site + 4-neighbours all empty",
        "rs = rng.integers(0, L, attempts)",
        "cs = rng.integers(0, L, attempts)",
        "placed = 0",
        "for r, c in zip(rs, cs):",
        "    if grid[r, c]:",
        "        continue",
        "    n = (grid[(r-1) % L, c] + grid[(r+1) % L, c]",
        "       + grid[r, (c-1) % L] + grid[r, (c+1) % L])",
        "    if n == 0:",
        "        grid[r, c] = 1",
        "        placed += 1",
        "coverage = placed / (L * L)",
        "fig, ax = plt.subplots(figsize=(5, 5))",
        "ax.imshow(grid, cmap='Blues', vmin=0, vmax=1, interpolation='nearest')",
        "ax.set_title(f'L={L},  placed={placed},  coverage={coverage:.3f}',",
        "             fontsize=11)",
        "ax.set_xlabel('column  j')",
        "ax.set_ylabel('row  i')",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(8, 0, py_plot)

    # ── =PY cell: return jamming coverage fraction ────────────────────
    s.set(8, 4, "Coverage fraction:")
    s.set(9, 4, "Particles placed:")
    for r in range(8, 10):
        s.fmt(r, 4, bold=True, align="right")
    s.col_width(4, 160)

    py_stats = "\n".join([
        "=PY",
        "import numpy as np",
        "L        = int(ks('B4'))",
        "attempts = int(ks('B5'))",
        "seed     = int(ks('B6'))",
        "rng = np.random.default_rng(seed)",
        "grid = np.zeros((L, L), dtype=np.int8)",
        "rs = rng.integers(0, L, attempts)",
        "cs = rng.integers(0, L, attempts)",
        "placed = 0",
        "for r, c in zip(rs, cs):",
        "    if grid[r, c]:",
        "        continue",
        "    n = (grid[(r-1) % L, c] + grid[(r+1) % L, c]",
        "       + grid[r, (c-1) % L] + grid[r, (c+1) % L])",
        "    if n == 0:",
        "        grid[r, c] = 1",
        "        placed += 1",
        "coverage = placed / (L * L)",
        "ks_set('F9', round(coverage, 4))",
        "ks_set('F10', placed)",
        "round(coverage, 4)",
    ])
    s.formula(8, 5, py_stats)
    s.fmt(8, 5, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.0000")
    s.fmt(9, 5, bg=PALETTE["band"], bold=True, align="center",
          number_format="0")
    s.box(8, 4, 9, 5, color=PALETTE["header"], width=1.0)
    s.col_width(5, 90)

    s.note(8, 0,
           "Coverage converges as attempts → ∞ to the jamming limit.\n"
           "Increase attempts to approach ~0.546.",
           kind="note")

    # ── Equation: RSA jamming limit ───────────────────────────────────
    s.equation(
        r"\theta_{\mathrm{jam}} \approx 0.546\quad(\mathrm{1D\ RSA\ analytic})",
        at=(520, 300), fontsize=15, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(380, 46),
    )

    out = os.path.join(_REPO, "examples", "python", "Materials Science",
                       "Random Sequential Adsorption.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
