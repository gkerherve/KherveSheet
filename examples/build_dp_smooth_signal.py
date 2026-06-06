"""Build "Smooth Signal.ksheet" — a data-processing Python-cell example.

Embeds a noisy signal column (80 samples) and a window-size parameter cell.
The =PY cell computes a moving average AND a Savitzky-Golay smooth, writes
both result columns back with ks_set, and plots raw vs both smoothers.

Run:  python examples/build_dp_smooth_signal.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

import numpy as np
from ksheet_author import Workbook, PALETTE

N = 80
SEED = 7
DATA_ROW_START = 8   # 0-based; sheet row 9
PY_COL = 5           # column F — clear of A..D


def build() -> str:
    rng = np.random.default_rng(SEED)
    t = np.linspace(0, 2 * np.pi, N)
    clean = np.sin(t) + 0.4 * np.sin(3 * t)
    noisy = clean + 0.35 * rng.standard_normal(N)

    wb = Workbook(min_rows=N + 15, min_cols=12)
    s = wb.add_sheet("Smooth Signal")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block(
        "Smooth Signal",
        "Moving average and Savitzky-Golay smoothing with editable window size",
    )

    # ── Parameter block ───────────────────────────────────────────────
    # Params at rows 3-5 (0-based), cols 0-1  → A4:B6
    s.set(2, 0, "Parameters")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Window size W (odd number)",  11),
        ("SG polynomial order",          3),
        ("Noise seed",                 SEED),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 3 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0")

    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 220)
    s.col_width(1, 90)

    s.note(3, 1,
           "Edit window size W (B4) — must be odd and > poly order.  "
           "Press Ctrl+Enter on the =PY cell in column F to update.",
           kind="note")

    # ── Data table header ─────────────────────────────────────────────
    # Columns: A=index, B=noisy, C=moving-avg, D=SG-smooth (0-based: 0,1,2,3)
    hdr_row = DATA_ROW_START - 1
    for c, label in enumerate(["Index", "Noisy signal", "Moving avg", "SG smooth"]):
        s.set(hdr_row, c, label)
        s.fmt(hdr_row, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    s.col_width(0, 70)
    s.col_width(2, 120)
    s.col_width(3, 120)
    s.col_width(PY_COL, 460)

    # ── Data rows ─────────────────────────────────────────────────────
    for i in range(N):
        r = DATA_ROW_START + i
        band = PALETTE["band_alt"] if i % 2 else None
        s.set(r, 0, i + 1)
        s.set(r, 1, round(float(noisy[i]), 5))
        s.fmt(r, 1, number_format="0.00000",
              bg=band if band else None)
        s.set(r, 2, "")
        s.set(r, 3, "")

    s.box(hdr_row, 0, DATA_ROW_START + N - 1, 3,
          color=PALETTE["header"], width=1.0)

    s.note(hdr_row, 1,
           "Column B = noisy signal (edit any value).  "
           "Columns C and D are filled by the =PY cell.",
           kind="note")

    # ── =PY cell ──────────────────────────────────────────────────────
    first_data = DATA_ROW_START + 1   # 1-based = 9
    last_data  = DATA_ROW_START + N   # 1-based = 88
    py_code = f"""\
=PY
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter

# Read parameters
W    = max(3, int(ks("B4")))
poly = max(1, int(ks("B5")))
# Ensure W is odd and larger than poly
if W % 2 == 0:
    W += 1
W = max(W, poly + 2 if (poly + 2) % 2 == 1 else poly + 3)

# Read signal
sig = np.asarray(ks("B{first_data}:B{last_data}"), dtype=float)

# Moving average (uniform convolution, same length)
kernel = np.ones(W) / W
ma = np.convolve(sig, kernel, mode="same")

# Savitzky-Golay
sg = savgol_filter(sig, window_length=W, polyorder=poly)

# Write results
ks_set("C{first_data}", ma.tolist())
ks_set("D{first_data}", sg.tolist())

# Plot
idx = np.arange(1, len(sig) + 1)
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(idx, sig, color="#bfbfbf", linewidth=0.9, alpha=0.9, label="Noisy")
ax.plot(idx, ma,  color="#4472c4", linewidth=2.0, label=f"Moving avg (W={{W}})")
ax.plot(idx, sg,  color="#ed7d31", linewidth=2.0, linestyle="--",
        label=f"Savitzky-Golay (W={{W}}, ord={{poly}})")
ax.set_xlabel("Sample index", fontsize=11)
ax.set_ylabel("Amplitude", fontsize=11)
ax.set_title("Signal Smoothing: Moving Average vs Savitzky-Golay",
             fontsize=12, fontweight="bold")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.35)
fig.tight_layout()
plt.gcf()
"""

    s.formula(DATA_ROW_START - 1, PY_COL, py_code)
    s.fmt(DATA_ROW_START - 1, PY_COL,
          font_family="Consolas", font_size=9, wrap=True)

    s.note(DATA_ROW_START - 1, PY_COL,
           "=PY cell: reads B4 (window W), B9:B88 (noisy signal), "
           "writes moving-avg → C9:C88 and SG smooth → D9:D88.",
           kind="note")

    # ── Equation ──────────────────────────────────────────────────────
    s.equation(
        r"\bar{y}_i = \frac{1}{W}\sum_{k=0}^{W-1} y_{i-k}",
        at=(580, 30), fontsize=17, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(260, 52),
    )

    out = os.path.join(
        _REPO, "examples", "python", "Data Processing",
        "Smooth Signal.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
