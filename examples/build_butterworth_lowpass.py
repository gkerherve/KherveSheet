"""Build the "Butterworth Lowpass" demo .ksheet example.

A signal processing example showing IIR Butterworth low-pass filtering.
The =PY cell uses scipy.signal.butter + filtfilt on a noisy signal
with a user-editable cutoff frequency.

Run:  python examples/build_butterworth_lowpass.py

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
    s = wb.add_sheet("Butterworth LP")

    # --- Title -------------------------------------------------------
    s.title_block(
        "Butterworth Low-Pass Filter",
        "Zero-phase IIR filter (butter + filtfilt) applied to a noisy signal",
    )

    # --- Input parameters --------------------------------------------
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Sample rate fs (Hz)",       1000),
        ("Number of samples N",        512),
        ("Signal frequency (Hz)",       50),
        ("High-freq component (Hz)",   200),
        ("Noise amplitude",            0.3),
        ("Noise seed",                  13),
        ("Cutoff frequency fc (Hz)",    80),
        ("Filter order",                 4),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.##")

    s.box(4, 0, 11, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 220)
    s.col_width(1, 90)

    s.note(4, 1,
           "Edit the cutoff frequency fc (B10) and filter order (B11), "
           "then press Ctrl+Enter on the Python cell to refilter.",
           kind="note")

    # --- Python cell: generate signal, filter, plot ------------------
    # 1-based refs:
    #   B5=fs, B6=N, B7=sig_freq, B8=hi_freq, B9=noise_a,
    #   B10=seed, B11=fc, B12=order
    py_code = """\
=PY
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt

fs      = float(ks("B5"))
N       = int(ks("B6"))
f_sig   = float(ks("B7"))
f_hi    = float(ks("B8"))
noise_a = float(ks("B9"))
seed    = int(ks("B10"))
fc      = float(ks("B11"))
order   = int(ks("B12"))

rng = np.random.default_rng(seed)
t = np.arange(N) / fs
signal = (np.sin(2 * np.pi * f_sig * t)
          + 0.4 * np.sin(2 * np.pi * f_hi * t)
          + noise_a * rng.standard_normal(N))

# Butterworth low-pass (zero-phase via filtfilt)
nyq = fs / 2.0
wn = max(0.001, min(fc / nyq, 0.999))
b, a = butter(order, wn, btype="low")
filtered = filtfilt(b, a, signal)

fig, axes = plt.subplots(2, 1, figsize=(7, 5), sharex=True)
axes[0].plot(t, signal, color="#bfbfbf", linewidth=0.7, label="Raw")
axes[0].set_ylabel("Amplitude", fontsize=10)
axes[0].set_title("Raw Signal", fontsize=11, fontweight="bold")
axes[0].grid(True, alpha=0.35)

axes[1].plot(t, signal,   color="#bfbfbf", linewidth=0.7, alpha=0.6, label="Raw")
axes[1].plot(t, filtered, color="#4472c4", linewidth=2.0, label=f"Filtered (fc={fc} Hz, ord={order})")
axes[1].set_xlabel("Time (s)", fontsize=10)
axes[1].set_ylabel("Amplitude", fontsize=10)
axes[1].set_title("Butterworth Low-Pass Filtered", fontsize=11, fontweight="bold")
axes[1].legend(fontsize=9)
axes[1].grid(True, alpha=0.35)

fig.tight_layout()
plt.gcf()
"""

    s.formula(13, 0, py_code)
    s.fmt(13, 0, font_family="Consolas", font_size=9, wrap=True)

    s.note(13, 0,
           "This =PY cell builds a mixed-frequency signal, designs a "
           "Butterworth filter with your cutoff and order, and plots "
           "raw vs filtered side-by-side.",
           kind="note")

    # --- Save --------------------------------------------------------
    out = os.path.join(
        _REPO, "examples", "python", "Signal Processing",
        "Butterworth Lowpass.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
