"""Build the "Savitzky-Golay Smoothing" demo .ksheet example.

A signal processing example showing polynomial smoothing of a noisy
signal.  The =PY cell uses scipy.signal.savgol_filter with user-
editable window length and polynomial order.

Run:  python examples/build_savitzky_golay.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, PALETTE


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=14)
    s = wb.add_sheet("SG Smoothing")

    # --- Title -------------------------------------------------------
    s.title_block(
        "Savitzky-Golay Smoothing",
        "Polynomial least-squares filter applied to a noisy signal",
    )

    # --- Input parameters --------------------------------------------
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Number of samples N",  200),
        ("Signal frequency (Hz)",  3),
        ("Noise amplitude",       0.4),
        ("Noise seed",             7),
        ("Window length (odd)",   21),
        ("Polynomial order",       3),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.##")

    s.box(4, 0, 9, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 210)
    s.col_width(1, 90)

    s.note(4, 1,
           "Edit window length (must be odd and > poly order) and "
           "poly order, then press Ctrl+Enter on the Python cell.",
           kind="note")

    # --- Python cell: generate noisy signal, smooth, plot ------------
    # Inputs (1-based):
    #   B5 = N, B6 = freq, B7 = noise_amp, B8 = seed
    #   B9 = window_length, B10 = poly_order
    py_code = """\
=PY
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter

N        = int(ks("B5"))
freq     = float(ks("B6"))
noise_a  = float(ks("B7"))
seed     = int(ks("B8"))
win      = int(ks("B9"))
poly     = int(ks("B10"))

rng = np.random.default_rng(seed)
t = np.linspace(0, 1, N)
clean  = np.sin(2 * np.pi * freq * t)
noisy  = clean + noise_a * rng.standard_normal(N)

# Clamp window so it is always odd and at least poly+2
if win % 2 == 0:
    win += 1
win = max(win, poly + 2 if (poly + 2) % 2 == 1 else poly + 3)
smoothed = savgol_filter(noisy, window_length=win, polyorder=poly)

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(t, noisy,    color="#bfbfbf", linewidth=0.8, alpha=0.9, label="Noisy")
ax.plot(t, clean,    color="#70ad47", linewidth=1.2, linestyle="--", label="Clean")
ax.plot(t, smoothed, color="#4472c4", linewidth=2.0, label=f"SG (win={win}, ord={poly})")
ax.set_xlabel("Time (s)", fontsize=11)
ax.set_ylabel("Amplitude", fontsize=11)
ax.set_title("Savitzky-Golay Smoothing", fontsize=12, fontweight="bold")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.35)
fig.tight_layout()
plt.gcf()
"""

    s.formula(11, 0, py_code)
    s.fmt(11, 0, font_family="Consolas", font_size=9, wrap=True)

    s.note(11, 0,
           "The =PY cell generates the noisy sine, runs savgol_filter "
           "and overlays raw, clean and smoothed traces.",
           kind="note")

    # --- Save --------------------------------------------------------
    out = os.path.join(
        _REPO, "examples", "python", "Signal Processing",
        "Savitzky-Golay Smoothing.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
