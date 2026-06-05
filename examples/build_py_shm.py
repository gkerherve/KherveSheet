"""Build "Simple Harmonic Motion.ksheet" — a Python-cell physics example.

=PY reads amplitude A and frequency f from grid cells, then plots
x(t) = A cos(2 pi f t) over the specified duration.

Run:  python examples/build_py_shm.py

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
    s = wb.add_sheet("SHM")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block("Simple Harmonic Motion",
                  "x(t) = A cos(2π f t)  —  edit amplitude, frequency "
                  "and duration, then press Ctrl+Enter")

    # ── Input parameters ───────────────────────────────────────────────
    # B4 = A, B5 = f, B6 = duration
    inputs = [
        ("Amplitude  A  (m)",    3, 1,   2.0),
        ("Frequency  f  (Hz)",   4, 1,   1.5),
        ("Duration   T  (s)",    5, 1,   4.0),
    ]
    labels = [
        "Amplitude  A  (m)",
        "Frequency  f  (Hz)",
        "Duration   T  (s)",
    ]
    values = [2.0, 1.5, 4.0]
    for i, (lbl, val) in enumerate(zip(labels, values)):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.0")
    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 190)
    s.col_width(1, 90)

    s.note(3, 1,
           "Edit amplitude (m), frequency (Hz) or duration (s), "
           "then press Ctrl+Enter on the =PY cell in row 8 to replot.",
           kind="note")

    # ── =PY cell: plot x(t) ───────────────────────────────────────────
    # 0-based row 7 → sheet row 8
    py_plot = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "A   = ks('B4')",
        "f   = ks('B5')",
        "dur = ks('B6')",
        "t   = np.linspace(0, dur, 1000)",
        "x   = A * np.cos(2 * np.pi * f * t)",
        "fig, ax = plt.subplots(figsize=(6, 4))",
        "ax.plot(t, x, color='#ed7d31', linewidth=2.5)",
        "ax.axhline(0, color='#555', linewidth=0.8, linestyle='--')",
        "ax.set_xlabel('Time  t (s)')",
        "ax.set_ylabel('Displacement  x (m)')",
        "ax.set_title(f'SHM  A={A} m,  f={f} Hz')",
        "ax.set_ylim(-A*1.3, A*1.3)",
        "ax.grid(True, alpha=0.4)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(7, 0, py_plot)

    # ── =PY cell: return period T = 1/f ───────────────────────────────
    s.set(7, 3, "Period  T  (s)  =  1/f :")
    s.fmt(7, 3, bold=True, align="right")
    py_period = "\n".join([
        "=PY",
        "f = ks('B5')",
        "round(1.0 / f, 4)",
    ])
    s.formula(7, 4, py_period)
    s.fmt(7, 4, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.0000")
    s.col_width(3, 200)
    s.col_width(4, 100)

    out = os.path.join(_REPO, "examples", "python", "Physics",
                       "Simple Harmonic Motion.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
