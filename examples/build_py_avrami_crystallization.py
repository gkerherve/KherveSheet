"""Build "Avrami Crystallization.ksheet" — a Python-cell materials science example.

Computes and plots the JMAK/Avrami transformed fraction X(t) = 1-exp(-(kt)^n)
vs time.  A second =PY cell makes an Avrami plot (ln(-ln(1-X)) vs ln t) and
returns the fitted exponent n.

Row/column mapping: set(r, c, v) → sheet cell letter(c) + str(r+1).
  set(3,1,v) → B4,  set(4,1,v) → B5,  set(5,1,v) → B6.

Run:  python examples/build_py_avrami_crystallization.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Avrami")

    # ── Title (rows 0-1) ──────────────────────────────────────────────
    s.title_block(
        "Avrami Crystallization",
        "JMAK kinetics: X(t) = 1 - exp(-(kt)^n).  Edit k, n and t_max, press Ctrl+Enter.",
    )

    # ── Input parameters ──────────────────────────────────────────────
    # set(3,1,v)→B4=k,  set(4,1,v)→B5=n,  set(5,1,v)→B6=t_max
    s.set(2, 0, "Parameters")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    input_rows = [
        (3, "Rate constant  k  (1/s)",  0.1,  "0.000"),
        (4, "Avrami exponent  n",        2.5,  "0.00"),
        (5, "Total time  t_max  (s)",   60.0,  "0.0"),
    ]
    for r, lbl, val, nfmt in input_rows:
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format=nfmt)

    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 220)
    s.col_width(1, 100)

    # Note on first input cell (row 3, col 1 = B4)
    s.note(
        3, 1,
        "Try k=0.05 (slower kinetics), n=4 (interface-controlled 3-D), "
        "or n=1 (diffusion-limited).  Press Ctrl+Enter on A9 to replot.",
        kind="note",
    )

    # ── Output: fitted Avrami exponent (row 7 = sheet row 8) ──────────
    # set(7,3,...)→D8,  set(7,4,...)→E8
    s.set(7, 3, "Fitted Avrami exponent  n_fit:")
    s.fmt(7, 3, bold=True, align="right")
    s.set(7, 4, "")   # filled by ks_set from the Avrami plot cell
    s.fmt(7, 4, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.0000")
    s.col_width(3, 240)
    s.col_width(4, 110)

    s.note(
        7, 4,
        "n_fit is recovered from the slope of ln(-ln(1-X)) vs ln(t).  "
        "Should match the input n exactly for noise-free JMAK data.",
        kind="note",
    )

    # ── =PY plot cell 1: X(t) sigmoid (row 8 = sheet row 9, col 0 = A) ─
    # Reads: B4=k, B5=n, B6=t_max
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "k      = float(ks('B4'))",
        "n      = float(ks('B5'))",
        "t_max  = float(ks('B6'))",
        "t = np.linspace(0.001, t_max, 400)",
        "X = 1.0 - np.exp(-(k * t)**n)",
        "fig, ax = plt.subplots(figsize=(6, 4))",
        "ax.plot(t, X, color='#4472c4', linewidth=2.2, label=f'k={k}, n={n}')",
        "ax.axhline(0.5, color='#ed7d31', linewidth=1.0, linestyle='--',",
        "           label='X=0.5  (half-transformed)')",
        "ax.set_xlabel('Time  t  (s)')",
        "ax.set_ylabel('Transformed fraction  X(t)')",
        "ax.set_title('JMAK / Avrami Crystallization Kinetics')",
        "ax.set_ylim(0, 1.05)",
        "ax.legend(fontsize=9)",
        "ax.grid(True, alpha=0.35)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(8, 0, py_plot)
    s.set(8, 3, "Sigmoid plot — edit k, n, t_max above, press Ctrl+Enter")
    s.fmt(8, 3, italic=True, font_color="#555555")

    # ── =PY cell 2: Avrami plot + fitted n (row 9 = sheet row 10, col 3 = D) ─
    # Must run AFTER cell 1 since shared namespace, but =PY cells run
    # top-to-bottom left-to-right, so (9,3) runs after (8,0). Good.
    # Writes fitted n to E8 via ks_set.
    py_avrami = "\n".join([
        "=PY",
        "import numpy as np",
        "k      = float(ks('B4'))",
        "n      = float(ks('B5'))",
        "t_max  = float(ks('B6'))",
        "t = np.linspace(0.01, t_max * 0.98, 300)",
        "X = 1.0 - np.exp(-(k * t)**n)",
        "mask = (X > 1e-6) & (X < 1.0 - 1e-6)",
        "lt   = np.log(t[mask])",
        "lnln = np.log(-np.log(1.0 - X[mask]))",
        "coeffs = np.polyfit(lt, lnln, 1)",
        "n_fit  = round(float(coeffs[0]), 4)",
        "ks_set('E8', n_fit)",
        "n_fit",
    ])
    s.formula(9, 3, py_avrami)
    s.fmt(9, 3, italic=True, font_color="#555555")
    s.set(9, 0, "Avrami plot cell (D10) writes fitted n to E8 via ks_set")
    s.fmt(9, 0, italic=True, font_color="#888888")

    # ── Equation ──────────────────────────────────────────────────────
    s.equation(
        r"X(t) = 1 - \exp\!\left(-(k t)^n\right)",
        at=(540, 50), fontsize=18, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(280, 52),
    )

    out = os.path.join(
        _REPO, "examples", "python", "Materials Science",
        "Avrami Crystallization.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
