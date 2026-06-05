"""Build the "pH Titration Curve" demo .ksheet example.

Strong acid–strong base titration: plots pH vs volume of base added.
Inputs are editable in the sheet; the =PY cell reads them via ks().

Run:  python examples/build_ph_titration.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, PALETTE  # noqa: E402


PY_CODE = r"""=PY
import numpy as np
import matplotlib.pyplot as plt

# Read inputs from the sheet
# Inputs are at row=4,col=1 (B5); row=5,col=1 (B6); row=6,col=1 (B7) in 1-based
Ca  = ks("B5")   # acid concentration (mol/L)
Va  = ks("B6")   # acid volume (mL)
Cb  = ks("B7")   # base concentration (mol/L)

# Volume of base added (mL)
Vb = np.linspace(0, 2.0 * Ca * Va / Cb, 500)

# Moles at each point
moles_acid = Ca * Va / 1000.0       # mol
moles_base = Cb * Vb  / 1000.0      # mol
net = moles_acid - moles_base        # positive = excess acid

# pH calculation
pH = np.zeros_like(Vb)
Vtotal = (Va + Vb) / 1000.0         # L

# Excess acid region
mask_acid = net > 1e-15
H_conc = np.where(mask_acid, net / Vtotal, 1e-15)
pH = np.where(mask_acid, -np.log10(np.maximum(H_conc, 1e-15)), pH)

# Excess base region
mask_base = net < -1e-15
OH_conc = np.where(mask_base, -net / Vtotal, 1e-15)
pH = np.where(mask_base, 14.0 + np.log10(np.maximum(OH_conc, 1e-15)), pH)

# Equivalence point
mask_eq = ~mask_acid & ~mask_base
pH = np.where(mask_eq, 7.0, pH)

# Equivalence volume
Veq = Ca * Va / Cb

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(Vb, pH, color="#4472c4", linewidth=2.0, label="pH")
ax.axvline(Veq, color="#ed7d31", linestyle="--", linewidth=1.5,
           label=f"Equivalence point ({Veq:.1f} mL)")
ax.axhline(7.0, color="#70ad47", linestyle=":", linewidth=1.2,
           label="pH = 7")
ax.set_xlabel("Volume of base added (mL)")
ax.set_ylabel("pH")
ax.set_title("Strong Acid–Strong Base Titration")
ax.set_ylim(0, 14)
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.gcf()
"""

PY_EQUIV = r"""=PY
# Equivalence point volume
Ca = ks("B5")
Va = ks("B6")
Cb = ks("B7")
round(Ca * Va / Cb, 3)
"""


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Titration")

    # Title
    s.title_block("pH Titration Curve",
                  "Strong acid–strong base titration — edit inputs and press Ctrl+Enter")

    # Input parameters
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Acid concentration Ca (mol/L)", 0.1),
        ("Acid volume Va (mL)",          25.0),
        ("Base concentration Cb (mol/L)", 0.1),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.000")
    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.2)
    s.col_width(0, 240)
    s.col_width(1, 110)

    # Equivalence volume result cell
    s.set(8, 0, "Equivalence volume (mL):")
    s.fmt(8, 0, bold=True)
    s.formula(8, 1, PY_EQUIV)
    s.fmt(8, 1, bg=PALETTE["good"], align="center", number_format="0.00", bold=True)
    s.box(8, 0, 8, 1, color=PALETTE["header"], width=1.0)

    # Main Python cell (plot)
    s.formula(10, 0, PY_CODE)

    # Notes
    s.note(4, 1,
           "Edit Ca, Va, or Cb here. Then press Ctrl+Enter on the =PY cell "
           "in row 11 to replot.", kind="note")
    s.note(10, 0,
           "=PY cell: reads Ca/Va/Cb from B4:B6, computes pH across the "
           "titration range, and plots pH vs volume added.", kind="note")

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "python", "Chemistry", "pH Titration Curve.ksheet"
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
