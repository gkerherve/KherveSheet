"""Build the "Moving Average" demo .ksheet example.

A signal processing example showing convolution-based moving average
smoothing of a noisy signal, with a user-editable window size.

Run:  python examples/build_moving_average.py

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
    s = wb.add_sheet("Moving Average")

    # --- Title -------------------------------------------------------
    s.title_block(
        "Moving Average Smoothing",
        "Convolution-based sliding window average on a noisy signal",
    )

    # --- Input parameters --------------------------------------------
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Number of samples N",  250),
        ("Signal frequency (Hz)",  2),
        ("Noise amplitude",       0.5),
        ("Noise seed",             55),
        ("Window size W",          15),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.##")

    s.box(4, 0, 8, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 210)
    s.col_width(1, 90)

    s.note(4, 1,
           "Edit the window size W (B8) to widen or narrow the "
           "smoothing, then press Ctrl+Enter on the Python cell.",
           kind="note")

    # --- Python cell: generate noisy signal, apply MA, plot ----------
    # 1-based refs: B5=N, B6=freq, B7=noise_a, B8=seed, B9=W
    py_code = """\
=PY
import numpy as np
import matplotlib.pyplot as plt

N       = int(ks("B5"))
freq    = float(ks("B6"))
noise_a = float(ks("B7"))
seed    = int(ks("B8"))
W       = max(1, int(ks("B9")))

rng = np.random.default_rng(seed)
t = np.linspace(0, 2, N)
clean  = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * 3 * freq * t)
noisy  = clean + noise_a * rng.standard_normal(N)

# Moving average via uniform convolution (mode="same" keeps length)
kernel = np.ones(W) / W
ma = np.convolve(noisy, kernel, mode="same")

# Simple RMS error vs clean signal
rms_raw = np.sqrt(np.mean((noisy - clean) ** 2))
rms_ma  = np.sqrt(np.mean((ma    - clean) ** 2))

fig, axes = plt.subplots(2, 1, figsize=(7, 5), sharex=True)

axes[0].plot(t, noisy, color="#bfbfbf", linewidth=0.8, label="Noisy")
axes[0].plot(t, clean, color="#70ad47", linewidth=1.2,
             linestyle="--", label="Clean")
axes[0].set_ylabel("Amplitude", fontsize=10)
axes[0].set_title(f"Noisy signal  (RMS noise = {rms_raw:.3f})", fontsize=11)
axes[0].legend(fontsize=9)
axes[0].grid(True, alpha=0.35)

axes[1].plot(t, noisy, color="#bfbfbf", linewidth=0.8, alpha=0.7, label="Noisy")
axes[1].plot(t, ma,    color="#4472c4", linewidth=2.0,
             label=f"Moving avg (W={W})  RMS={rms_ma:.3f}")
axes[1].set_xlabel("Time (s)", fontsize=10)
axes[1].set_ylabel("Amplitude", fontsize=10)
axes[1].set_title("After Moving Average", fontsize=11)
axes[1].legend(fontsize=9)
axes[1].grid(True, alpha=0.35)

fig.suptitle("Moving Average Smoothing", fontsize=13, fontweight="bold")
fig.tight_layout()
plt.gcf()
"""

    s.formula(10, 0, py_code)
    s.fmt(10, 0, font_family="Consolas", font_size=9, wrap=True)

    s.note(10, 0,
           "The =PY cell computes a moving average via np.convolve "
           "and shows the RMS improvement vs the clean reference.",
           kind="note")

    # --- Save --------------------------------------------------------
    out = os.path.join(
        _REPO, "examples", "python", "Signal Processing",
        "Moving Average.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
