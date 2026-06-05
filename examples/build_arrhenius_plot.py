"""Build the "Arrhenius Plot" demo .ksheet example.

Input: a column of temperatures T (K) and rate constants k.
Plot: ln(k) vs 1/T with a fitted line. Returns activation energy Ea.

Run:  python examples/build_arrhenius_plot.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, PALETTE  # noqa: E402


# Temperature and rate constant data
TEMPS  = [300, 320, 340, 360, 380, 400, 420, 440]   # K
KRATES = [0.0023, 0.0087, 0.0290, 0.0870, 0.2300,
          0.5500, 1.2000, 2.4000]                     # arbitrary units


PY_PLOT = r"""=PY
import numpy as np
import matplotlib.pyplot as plt

# Read data from the sheet (columns A and B, rows 6..13)
T    = ks("A6:A13")   # Temperature (K)
k    = ks("B6:B13")   # Rate constant

inv_T  = 1.0 / T
ln_k   = np.log(k)

# Linear fit: ln(k) = ln(A) - Ea/(R*T)  =>  slope = -Ea/R
n  = len(inv_T)
sx = inv_T.sum();  sy = ln_k.sum()
sxx = (inv_T**2).sum();  sxy = (inv_T * ln_k).sum()
slope     = (n * sxy - sx * sy) / (n * sxx - sx**2)
intercept = (sy - slope * sx) / n

fit_line = slope * inv_T + intercept

fig, ax = plt.subplots(figsize=(7, 4.5))
ax.scatter(inv_T, ln_k, color="#c00000", zorder=5, s=60,
           label="Experimental data")
ax.plot(inv_T, fit_line, color="#4472c4", linewidth=2.0,
        label=f"Linear fit (R²={1 - np.var(ln_k - fit_line)/np.var(ln_k):.4f})")
ax.set_xlabel("1/T  (K⁻¹)")
ax.set_ylabel("ln(k)")
ax.set_title("Arrhenius Plot")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.gcf()
"""

PY_EA = r"""=PY
import numpy as np

T   = ks("A6:A13")
k   = ks("B6:B13")
R   = 8.314          # J/(mol·K)

inv_T = 1.0 / T
ln_k  = np.log(k)
n     = len(inv_T)
sx    = inv_T.sum();  sy = ln_k.sum()
sxx   = (inv_T**2).sum();  sxy = (inv_T * ln_k).sum()
slope = (n * sxy - sx * sy) / (n * sxx - sx**2)

Ea_kJ = -slope * R / 1000.0
round(Ea_kJ, 2)
"""


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Arrhenius")

    # Title
    s.title_block("Arrhenius Plot",
                  "ln(k) vs 1/T — determines activation energy Ea from slope")

    # Column headers for data
    s.set(4, 0, "T (K)")
    s.set(4, 1, "k (s⁻¹)")
    s.fmt(4, 0, bold=True, bg=PALETTE["header"], font_color="#ffffff", align="center")
    s.fmt(4, 1, bold=True, bg=PALETTE["header"], font_color="#ffffff", align="center")
    s.box(4, 0, 4 + len(TEMPS), 1, color=PALETTE["header"], width=1.0)

    for i, (T, k) in enumerate(zip(TEMPS, KRATES)):
        r = 5 + i
        band = PALETTE["band_alt"] if i % 2 else None
        s.set(r, 0, T)
        s.set(r, 1, k)
        kw_t = dict(align="center", number_format="0")
        kw_k = dict(align="center", number_format="0.0000")
        if band:
            kw_t["bg"] = band
            kw_k["bg"] = band
        s.fmt(r, 0, **kw_t)
        s.fmt(r, 1, **kw_k)

    s.col_width(0, 100)
    s.col_width(1, 110)

    # Result cell — activation energy
    s.set(3, 3, "Activation energy Ea (kJ/mol):")
    s.fmt(3, 3, bold=True)
    s.formula(3, 4, PY_EA)
    s.fmt(3, 4, bg=PALETTE["good"], align="center", number_format="0.00", bold=True)
    s.box(3, 3, 3, 4, color=PALETTE["header"], width=1.0)
    s.col_width(3, 220)
    s.col_width(4, 100)

    # Main plot cell
    s.formula(5, 3, PY_PLOT)

    # Notes
    s.note(5, 0,
           "Edit T or k values in columns A and B. "
           "Press Ctrl+Enter on the =PY cells to recompute.", kind="note")
    s.note(3, 4,
           "Ea = -slope × R, where slope comes from a least-squares "
           "fit of ln(k) vs 1/T.", kind="note")

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "python", "Chemistry", "Arrhenius Plot.ksheet"
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
