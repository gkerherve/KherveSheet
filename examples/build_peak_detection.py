"""Build the "Peak Detection" demo .ksheet example.

A signal processing example showing automatic peak finding.
scipy.signal.find_peaks is used on a multi-peak signal with a
user-editable prominence threshold.  Detected peak positions are
spilled into the sheet.

Run:  python examples/build_peak_detection.py

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
    s = wb.add_sheet("Peak Detection")

    # --- Title -------------------------------------------------------
    s.title_block(
        "Peak Detection",
        "Automatic peak finding with scipy.signal.find_peaks",
    )

    # --- Input parameters --------------------------------------------
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Number of samples N",  300),
        ("Noise amplitude",      0.15),
        ("Noise seed",             99),
        ("Prominence threshold", 0.4),
        ("Min peak distance",     20),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.###")

    s.box(4, 0, 8, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 210)
    s.col_width(1, 90)

    s.note(4, 1,
           "Edit the prominence threshold (B7) to catch smaller or "
           "larger peaks, then press Ctrl+Enter on each Python cell.",
           kind="note")

    # --- Python cell 1: build signal, detect peaks, plot -------------
    # 1-based refs: B5=N, B6=noise_a, B7=seed, B8=prominence, B9=min_dist
    py_plot = """\
=PY
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

N          = int(ks("B5"))
noise_a    = float(ks("B6"))
seed       = int(ks("B7"))
prominence = float(ks("B8"))
min_dist   = int(ks("B9"))

rng = np.random.default_rng(seed)
x = np.linspace(0, 4 * np.pi, N)
# Multi-peak signal: several Gaussians at known positions + sine baseline
centres = [0.4, 1.1, 1.9, 2.7, 3.4, 4.0, 4.8, 6.0, 7.5, 9.8, 11.5]
heights = [0.9, 0.5, 1.2, 0.7, 1.0, 0.45, 0.85, 0.6, 1.1, 0.75, 0.95]
signal = 0.15 * np.sin(x)
for c, h in zip(centres, heights):
    signal += h * np.exp(-0.5 * ((x - c) / 0.25) ** 2)
signal += noise_a * rng.standard_normal(N)

peaks, props = find_peaks(signal, prominence=prominence, distance=min_dist)
peak_x = x[peaks]
peak_y = signal[peaks]

fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(x, signal, color="#4472c4", linewidth=1.2, label="Signal")
ax.plot(peak_x, peak_y, "v", color="#ed7d31", markersize=8,
        label=f"{len(peaks)} peaks detected")
for px, py in zip(peak_x, peak_y):
    ax.annotate(f"{py:.2f}", xy=(px, py), xytext=(0, 8),
                textcoords="offset points", ha="center",
                fontsize=7, color="#ed7d31")
ax.set_xlabel("x (rad)", fontsize=11)
ax.set_ylabel("Amplitude", fontsize=11)
ax.set_title(f"Peak Detection (prominence > {prominence})", fontsize=12, fontweight="bold")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.35)
fig.tight_layout()
plt.gcf()
"""

    s.formula(10, 0, py_plot)
    s.fmt(10, 0, font_family="Consolas", font_size=9, wrap=True)

    s.note(10, 0,
           "This =PY cell generates the multi-peak signal, calls "
           "find_peaks, and marks detected peaks with orange triangles.",
           kind="note")

    # --- Python cell 2: spill peak positions -------------------------
    # Placed to the right so it doesn't overlap the plot spill area
    py_spill = """\
=PY
import numpy as np
from scipy.signal import find_peaks

N          = int(ks("B5"))
noise_a    = float(ks("B6"))
seed       = int(ks("B7"))
prominence = float(ks("B8"))
min_dist   = int(ks("B9"))

rng = np.random.default_rng(seed)
x = np.linspace(0, 4 * np.pi, N)
centres = [0.4, 1.1, 1.9, 2.7, 3.4, 4.0, 4.8, 6.0, 7.5, 9.8, 11.5]
heights = [0.9, 0.5, 1.2, 0.7, 1.0, 0.45, 0.85, 0.6, 1.1, 0.75, 0.95]
signal = 0.15 * np.sin(x)
for c, h in zip(centres, heights):
    signal += h * np.exp(-0.5 * ((x - c) / 0.25) ** 2)
signal += noise_a * rng.standard_normal(N)

peaks, props = find_peaks(signal, prominence=prominence, distance=min_dist)
# Spill: header + (x, amplitude) pairs
rows = [["Peak x (rad)", "Amplitude"]]
for i in peaks:
    rows.append([round(float(x[i]), 4), round(float(signal[i]), 4)])
rows
"""

    s.formula(10, 4, py_spill)
    s.fmt(10, 4, font_family="Consolas", font_size=9, wrap=True)
    s.set(9, 4, "Detected Peaks")
    s.fmt(9, 4, bold=True, font_color=PALETTE["header"])

    s.note(10, 4,
           "This second =PY cell spills the detected peak positions "
           "and amplitudes into the cells below.",
           kind="note")

    s.col_width(4, 140)
    s.col_width(5, 100)

    # --- Save --------------------------------------------------------
    out = os.path.join(
        _REPO, "examples", "python", "Signal Processing",
        "Peak Detection.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
