"""Build "Damped Oscillation.ksheet" — a Python-cell physics example.

=PY reads amplitude A, damping coefficient gamma and angular frequency
omega from grid cells, then plots A·exp(-gamma·t)·cos(omega·t) together
with the exponential envelope.

Run:  python examples/build_py_damped.py

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
    s = wb.add_sheet("Damped")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Damped Oscillation",
                  "x(t) = A exp(-γ t) cos(ω t)  —  edit the "
                  "parameters and press Ctrl+Enter")

    # ── Input parameters ───────────────────────────────────────────────
    # B4 = A, B5 = gamma, B6 = omega
    labels = [
        "Amplitude  A",
        "Damping coefficient  γ  (s⁻¹)",
        "Angular frequency  ω  (rad/s)",
    ]
    values = [5.0, 0.3, 4.0]
    for i, (lbl, val) in enumerate(zip(labels, values)):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 230)
    s.col_width(1, 90)

    s.note(3, 1,
           "Try: small γ (e.g. 0.1) for light damping, large γ "
           "(e.g. 2.0) for heavy damping.  Press Ctrl+Enter on "
           "the =PY cell in row 8 to replot.",
           kind="note")

    # ── =PY cell: plot damped oscillation + envelope ───────────────────
    # 0-based row 7 → sheet row 8
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "A     = ks('B4')",
        "gamma = ks('B5')",
        "omega = ks('B6')",
        "# Show enough cycles to see the decay",
        "cycles = max(3, int(omega / (2 * np.pi) * 10))",
        "t_end  = cycles * 2 * np.pi / omega if omega > 0 else 10",
        "t      = np.linspace(0, t_end, 2000)",
        "envelope = A * np.exp(-gamma * t)",
        "x        = envelope * np.cos(omega * t)",
        "fig, ax = plt.subplots(figsize=(6, 4))",
        "ax.plot(t, x, color='#4472c4', linewidth=2, label='x(t)')",
        "ax.plot(t,  envelope, color='#c00', linewidth=1.2,",
        "        linestyle='--', label='envelope')",
        "ax.plot(t, -envelope, color='#c00', linewidth=1.2, linestyle='--')",
        "ax.set_xlabel('Time  t (s)')",
        "ax.set_ylabel('Displacement  x')",
        "ax.set_title(f'Damped oscillation  A={A},  γ={gamma},  ω={omega}')",
        "ax.legend(fontsize=9)",
        "ax.grid(True, alpha=0.4)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(7, 0, py_plot)

    # ── =PY cell: return time constant tau = 1/gamma ──────────────────
    s.set(7, 3, "Time constant  τ  =  1/γ  (s):")
    s.fmt(7, 3, bold=True, align="right")
    py_tau = "\n".join([
        "=PY",
        "gamma = ks('B5')",
        "round(1.0 / gamma, 4) if gamma != 0 else float('inf')",
    ])
    s.formula(7, 4, py_tau)
    s.fmt(7, 4, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.0000")
    s.col_width(3, 230)
    s.col_width(4, 100)

    out = os.path.join(_REPO, "examples", "python", "Physics",
                       "Damped Oscillation.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
