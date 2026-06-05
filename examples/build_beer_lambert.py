"""Build the "Beer-Lambert Law" demo .ksheet example.

Inputs: a column of concentrations c, molar absorptivity ε, path length l.
Computes A = ε·l·c and plots absorbance vs concentration.

Run:  python examples/build_beer_lambert.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, PALETTE  # noqa: E402


# Concentration data points (mol/L)
CONCENTRATIONS = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]


PY_PLOT = r"""=PY
import numpy as np
import matplotlib.pyplot as plt

# Inputs
# row=4,col=1 → B5; row=5,col=1 → B6 in 1-based A1 notation
epsilon = ks("B5")    # molar absorptivity (L/mol/cm)
ell     = ks("B6")    # path length (cm)

# Concentration column: set at rows 9..18 (0-based) → A10:A19 in 1-based
c = ks("A10:A19")     # mol/L

A_calc = epsilon * ell * c

# Smooth line for theory
c_line = np.linspace(0, c.max() * 1.05, 200)
A_line = epsilon * ell * c_line

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(c_line, A_line, color="#4472c4", linewidth=2.0,
        label=f"A = ε·l·c  (ε={epsilon:.0f}, l={ell:.1f} cm)")
ax.scatter(c, A_calc, color="#c00000", zorder=5, s=60,
           label="Data points")
ax.set_xlabel("Concentration c  (mol/L)")
ax.set_ylabel("Absorbance A  (dimensionless)")
ax.set_title("Beer–Lambert Law:  A = ε · l · c")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.gcf()
"""

PY_ABSORBANCES = r"""=PY
import numpy as np
epsilon = ks("B5")
ell     = ks("B6")
c       = ks("A10:A19")
list(np.round(epsilon * ell * c, 4))
"""


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Beer-Lambert")

    # Title
    s.title_block("Beer-Lambert Law",
                  "A = ε · l · c — absorbance as a function of concentration")

    # Input parameters
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Molar absorptivity ε (L mol⁻¹ cm⁻¹)", 250.0),
        ("Path length l (cm)",                    1.0),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.2)
    s.col_width(0, 280)
    s.col_width(1, 100)

    # Concentration data column header
    s.set(7, 0, "Concentration data (edit freely)")
    s.fmt(7, 0, bold=True, font_color=PALETTE["header"])

    s.set(8, 0, "c (mol/L)")
    s.fmt(8, 0, bold=True, bg=PALETTE["header"],
          font_color="#ffffff", align="center")

    for i, c in enumerate(CONCENTRATIONS):
        r = 9 + i
        band = PALETTE["band_alt"] if i % 2 else None
        s.set(r, 0, c)
        kw = dict(align="center", number_format="0.00")
        if band:
            kw["bg"] = band
        s.fmt(r, 0, **kw)
    s.box(8, 0, 8 + len(CONCENTRATIONS), 0, color=PALETTE["header"], width=1.0)

    # Spill of computed absorbances
    s.set(8, 2, "Absorbance A (spill)")
    s.fmt(8, 2, bold=True, bg=PALETTE["header"],
          font_color="#ffffff", align="center")
    s.formula(9, 2, PY_ABSORBANCES)
    s.col_width(2, 160)

    # Main plot cell
    s.formula(9, 4, PY_PLOT)

    # Notes
    s.note(4, 1,
           "Edit ε or l here. Press Ctrl+Enter on the =PY cells to recompute.",
           kind="note")
    s.note(9, 0,
           "Add or change concentrations in column A (rows 9–18). "
           "The plot and computed absorbances update on Ctrl+Enter.", kind="note")

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "python", "Chemistry", "Beer-Lambert Law.ksheet"
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
