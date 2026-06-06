"""Build "BET Surface Area.ksheet" — a Python-cell materials-science example.

N2 adsorption isotherm (P/P0 vs V_ads).  A =PY cell builds the BET
transform, linear-fits the 0.05-0.30 region, computes Vm, C constant,
and specific surface area in m2/g, then plots the isotherm and BET fit.

Row/column mapping: set(r, c, v) -> sheet cell letter(c) + str(r+1).

Run:  python examples/build_py_bet_surface_area.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

import numpy as np
from ksheet_author import Workbook, PALETTE


def build() -> str:
    # ── Synthetic BET isotherm ────────────────────────────────────────
    rng = np.random.default_rng(17)

    # BET parameters
    Vm_true = 85.0     # monolayer volume cm3/g STP
    C_true  = 120.0    # BET C constant

    # P/P0 array: 30 points from 0.01 to 0.99
    pp0 = np.array([
        0.01, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20,
        0.22, 0.25, 0.28, 0.30, 0.33, 0.36, 0.40, 0.44, 0.48, 0.52,
        0.56, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.94, 0.97,
    ])

    # BET equation: V = Vm*C*x / ((1-x)*(1 + (C-1)*x))  where x = P/P0
    def bet_volume(x, Vm, C):
        return Vm * C * x / ((1 - x) * (1 + (C - 1) * x))

    V_ads = bet_volume(pp0, Vm_true, C_true)
    V_ads += rng.normal(0, 0.8, len(pp0))   # instrument noise
    V_ads = np.maximum(V_ads, 0.1)

    N = len(pp0)  # 30 points

    # ── Workbook ──────────────────────────────────────────────────────
    wb = Workbook(min_rows=max(N + 15, 60), min_cols=16)
    s = wb.add_sheet("BET")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block(
        "BET Surface Area Analysis",
        "N2 physisorption isotherm.  BET linear transform, Vm, C constant, SBET (m2/g).",
    )

    # ── Input parameters (rows 2-4 = sheet rows 3-5) ─────────────────
    s.set(2, 0, "Instrument / sample")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Sample mass (g)",       1.0,   "0.0000"),
        ("BET fit x_min (P/P0)",  0.05,  "0.00"),
        ("BET fit x_max (P/P0)",  0.30,  "0.00"),
    ]
    for i, (lbl, val, nfmt) in enumerate(inputs):
        r = 3 + i   # rows 3..5 -> B4..B6
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format=nfmt)

    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 200)
    s.col_width(1, 110)

    s.note(
        3, 1,
        "Change the BET linear-fit range (default 0.05-0.30) to see how "
        "it affects Vm and C.  The surface area recalculates automatically.",
        kind="note",
    )

    # ── Result cells (rows 7-10 = sheet rows 8-11) ───────────────────
    s.set(6, 0, "BET Results")
    s.fmt(6, 0, bold=True, font_color=PALETTE["header"])

    result_labels = ["Monolayer vol Vm (cm3/g)", "BET C constant",
                     "Surface area SBET (m2/g)", "R² of BET fit"]
    for i, lbl in enumerate(result_labels):
        r = 7 + i
        s.set(r, 0, lbl)
        s.set(r, 1, "")    # filled by =PY
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["good"], align="center", bold=True,
              number_format="0.00")

    s.col_width(1, 110)
    s.box(7, 0, 10, 1, color=PALETTE["header"], width=1.0)

    s.note(7, 1,
           "Results written by the =PY cell in column H. "
           "Vm and C come from the BET linear-fit slope and intercept.",
           kind="note")

    # ── Data columns: P/P0 (col 3=D), V_ads (col 4=E) ───────────────
    s.set(12, 3, "P/P0")
    s.set(12, 4, "V_ads (cm3/g STP)")
    s.fmt(12, 3, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.fmt(12, 4, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.col_width(3, 100)
    s.col_width(4, 150)

    for i in range(N):
        r = 13 + i   # data rows 13..42 -> sheet rows 14..43
        s.set(r, 3, round(float(pp0[i]), 4))
        s.set(r, 4, round(float(V_ads[i]), 4))

    s.note(12, 3,
           "Adsorption isotherm data: relative pressure P/P0 and volume "
           "adsorbed at STP.  The =PY cell builds the BET transform and fits it.",
           kind="note")

    # ── =PY cell: col 7 (H), row 12 (sheet row 13) ───────────────────
    # Data: D14:E43 (rows 13..42, cols 3..4)
    # Reads: B4 (mass), B5 (x_min), B6 (x_max)
    # Writes: B8..B11 (results)
    last_data = 13 + N - 1   # sheet row last_data+1

    py_code = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "",
        "# Parameters",
        "x_min = float(ks('B5'))",
        "x_max = float(ks('B6'))",
        "",
        "# Read isotherm data",
        f"pp0 = ks('D14:D{13 + N}')",
        f"V   = ks('E14:E{13 + N}')",
        "m = np.isfinite(pp0) & np.isfinite(V) & (V > 0)",
        "pp0, V = pp0[m], V[m]",
        "",
        "# BET transform: y = 1/(V*(1/x - 1))  vs x = P/P0",
        "x = pp0",
        "y_bet = 1.0 / (V * (1.0/x - 1.0))",
        "",
        "# Linear fit over 0.05-0.30 range",
        "fit_m = (x >= x_min) & (x <= x_max)",
        "x_fit = x[fit_m]; y_fit = y_bet[fit_m]",
        "if len(x_fit) >= 2:",
        "    coeffs = np.polyfit(x_fit, y_fit, 1)",
        "    slope = coeffs[0]; intercept = coeffs[1]",
        "    y_pred = np.polyval(coeffs, x_fit)",
        "    ss_res = np.sum((y_fit - y_pred)**2)",
        "    ss_tot = np.sum((y_fit - y_fit.mean())**2)",
        "    r2 = 1.0 - ss_res/ss_tot if ss_tot > 0 else 1.0",
        "    Vm = 1.0 / (slope + intercept)",
        "    C = slope / intercept + 1.0",
        "    # Surface area: S = (Vm/22414)*Na*Am  [m2/g]",
        "    Na = 6.02214076e23",
        "    Am = 0.162e-18   # m^2 per N2 molecule",
        "    S_bet = (Vm / 22414.0) * Na * Am",
        "else:",
        "    slope = intercept = 0.0; r2 = 0.0",
        "    Vm = C = S_bet = 0.0",
        "",
        "# Write results to B8..B11",
        "ks_set('B8', round(float(Vm), 3))",
        "ks_set('B9', round(float(C), 2))",
        "ks_set('B10', round(float(S_bet), 2))",
        "ks_set('B11', round(float(r2), 6))",
        "",
        "# Plot",
        "fig, axes = plt.subplots(1, 2, figsize=(10, 4))",
        "",
        "# Left: isotherm",
        "ax1 = axes[0]",
        "ax1.plot(pp0, V, 'o-', color='#4472c4', linewidth=1.8,",
        "         markersize=5, label='Isotherm')",
        "ax1.set_xlabel('Relative pressure P/P0')",
        "ax1.set_ylabel('V adsorbed (cm³/g STP)')",
        "ax1.set_title('N2 Adsorption Isotherm')",
        "ax1.grid(True, alpha=0.3)",
        "ax1.legend(fontsize=9)",
        "",
        "# Right: BET transform + fit",
        "ax2 = axes[1]",
        "ax2.scatter(x, y_bet, color='#4472c4', s=30, label='BET transform', zorder=3)",
        "if len(x_fit) >= 2:",
        "    x_line = np.linspace(x_min, x_max, 50)",
        "    ax2.plot(x_line, np.polyval(coeffs, x_line), '-',",
        "             color='#ed7d31', linewidth=2.0,",
        "             label=f'Linear fit R²={r2:.4f}')",
        "    ax2.axvspan(x_min, x_max, alpha=0.1, color='#ed7d31')",
        "ax2.set_xlabel('Relative pressure P/P0')",
        "ax2.set_ylabel('1 / [V(1/x-1)]')",
        "ax2.set_title(f'BET Transform  Vm={Vm:.1f}  C={C:.0f}')",
        "ax2.grid(True, alpha=0.3)",
        "ax2.legend(fontsize=9)",
        "",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(12, 7, py_code)
    s.fmt(12, 7, italic=True, font_color="#555555")
    s.col_width(7, 280)
    s.set(12, 8, "Analysis cell (col H) — Ctrl+Enter to re-run")
    s.fmt(12, 8, italic=True, font_color="#888888")

    # ── Equation ──────────────────────────────────────────────────────
    s.equation(
        r"\frac{1}{V\!\left(\frac{P_0}{P}-1\right)} = "
        r"\frac{C-1}{V_m C}\frac{P}{P_0} + \frac{1}{V_m C}",
        at=(550, 50), fontsize=14, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(380, 52),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        _REPO, "examples", "python", "Materials Science",
        "BET Surface Area.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
