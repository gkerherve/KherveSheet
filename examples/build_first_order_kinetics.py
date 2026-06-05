"""Build the "First-Order Kinetics" demo .ksheet example.

Inputs: rate constant k, initial concentration [A]0.
Plots [A](t) = [A]0 * exp(-k*t); returns half-life.

Run:  python examples/build_first_order_kinetics.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, PALETTE  # noqa: E402


PY_PLOT = r"""=PY
import numpy as np
import matplotlib.pyplot as plt

k   = ks("B5")   # rate constant (1/s)  [row=4,col=1 → B5 in 1-based]
A0  = ks("B6")   # initial concentration (mol/L)  [row=5,col=1 → B6]

t_half = np.log(2) / k
t_max  = 5.0 * t_half
t = np.linspace(0, t_max, 400)
A = A0 * np.exp(-k * t)

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(t, A, color="#4472c4", linewidth=2.5, label="[A](t)")
ax.axhline(A0 / 2.0, color="#ed7d31", linestyle="--", linewidth=1.5,
           label=f"[A]₀/2 = {A0/2:.3f} mol/L")
ax.axvline(t_half, color="#70ad47", linestyle=":", linewidth=1.5,
           label=f"t½ = {t_half:.3f} s")
ax.set_xlabel("Time (s)")
ax.set_ylabel("[A]  (mol/L)")
ax.set_title("First-Order Kinetics: [A](t) = [A]₀ · e^(−kt)")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.gcf()
"""

PY_HALF_LIFE = r"""=PY
import numpy as np
k = ks("B5")
round(np.log(2) / k, 4)
"""


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Kinetics")

    # Title
    s.title_block("First-Order Kinetics",
                  "[A](t) = [A]₀ · e^(−kt) — edit k and [A]₀, press Ctrl+Enter")

    # Input parameters
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Rate constant k (s⁻¹)", 0.35),
        ("Initial concentration [A]₀ (mol/L)", 1.0),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.0000")
    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.2)
    s.col_width(0, 260)
    s.col_width(1, 120)

    # Half-life result
    s.set(7, 0, "Half-life t½ (s):")
    s.fmt(7, 0, bold=True)
    s.formula(7, 1, PY_HALF_LIFE)
    s.fmt(7, 1, bg=PALETTE["good"], align="center", number_format="0.0000", bold=True)
    s.box(7, 0, 7, 1, color=PALETTE["header"], width=1.0)

    # Main plot cell
    s.formula(9, 0, PY_PLOT)

    # Notes
    s.note(4, 1,
           "Edit k (rate constant) or [A]₀ (initial concentration). "
           "Press Ctrl+Enter on the =PY cells to recompute.", kind="note")
    s.note(9, 0,
           "=PY plot: shows exponential decay [A](t)=[A]₀·e^(−kt), "
           "marks the half-life and the [A]₀/2 level.", kind="note")

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "python", "Chemistry", "First-Order Kinetics.ksheet"
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
