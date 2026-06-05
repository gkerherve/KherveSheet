"""Build the "FFT Spectrum" demo .ksheet example.

A signal processing example showing single-sided FFT magnitude spectrum.
Two sine frequencies are summed (plus noise) and the =PY cells compute
and plot the spectrum using np.fft.rfft / rfftfreq.

Run:  python examples/build_fft_spectrum.py

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
    s = wb.add_sheet("FFT Spectrum")

    # --- Title -------------------------------------------------------
    s.title_block(
        "FFT Spectrum Analysis",
        "Single-sided magnitude spectrum of a two-tone sine signal",
    )

    # --- Input parameters --------------------------------------------
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Sample rate fs (Hz)", 1000),
        ("Number of samples N",  1024),
        ("Frequency 1 f1 (Hz)",   50),
        ("Amplitude 1 A1",         1.0),
        ("Frequency 2 f2 (Hz)",  120),
        ("Amplitude 2 A2",         0.5),
        ("Noise seed",              42),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.##")

    s.box(4, 0, 10, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 210)
    s.col_width(1, 90)

    s.note(4, 1,
           "Edit fs, N, f1, A1, f2, A2 then press Ctrl+Enter on the "
           "Python cell to recompute the spectrum plot.",
           kind="note")

    # --- Python cell: generate signal and plot FFT -------------------
    # Inputs (1-based A1 refs):
    #   B5 = fs, B6 = N, B7 = f1, B8 = A1, B9 = f2, B10 = A2, B11 = seed
    py_code = """\
=PY
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator

fs   = float(ks("B5"))
N    = int(ks("B6"))
f1   = float(ks("B7"))
A1   = float(ks("B8"))
f2   = float(ks("B9"))
A2   = float(ks("B10"))
seed = int(ks("B11"))

rng = np.random.default_rng(seed)
t = np.arange(N) / fs
signal = A1 * np.sin(2 * np.pi * f1 * t) + A2 * np.sin(2 * np.pi * f2 * t)
signal += 0.1 * rng.standard_normal(N)

# Single-sided magnitude spectrum
spec  = np.fft.rfft(signal)
freqs = np.fft.rfftfreq(N, 1.0 / fs)
mag   = np.abs(spec) / N          # normalised amplitude
mag[1:-1] *= 2                    # single-sided correction

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(freqs, mag, color="#4472c4", linewidth=1.2)
ax.axvline(f1, color="#ed7d31", linestyle="--", linewidth=1.0, label=f"f1={f1} Hz")
ax.axvline(f2, color="#70ad47", linestyle="--", linewidth=1.0, label=f"f2={f2} Hz")
ax.set_xlabel("Frequency (Hz)", fontsize=11)
ax.set_ylabel("Magnitude", fontsize=11)
ax.set_title("Single-Sided FFT Magnitude Spectrum", fontsize=12, fontweight="bold")
ax.xaxis.set_minor_locator(AutoMinorLocator())
ax.yaxis.set_minor_locator(AutoMinorLocator())
ax.grid(True, which="major", alpha=0.4)
ax.grid(True, which="minor", alpha=0.15)
ax.legend(fontsize=9)
fig.tight_layout()
plt.gcf()
"""

    s.formula(12, 0, py_code)
    s.fmt(12, 0, font_family="Consolas", font_size=9, wrap=True)
    s.col_width(2, 120)

    s.note(12, 0,
           "This =PY cell reads B5:B11, builds the two-tone signal, "
           "runs rfft and plots the magnitude spectrum.",
           kind="note")

    # --- Save --------------------------------------------------------
    out = os.path.join(
        _REPO, "examples", "python", "Signal Processing", "FFT Spectrum.ksheet"
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
