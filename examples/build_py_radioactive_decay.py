"""Build "Radioactive Decay.ksheet" — a Python-cell physics example.

Shows N(t) = N0 * (1/2)^(t/t_half) for user-supplied N0 and half-life.
A second =PY cell returns the amount remaining at a chosen time t.

Run:  python examples/build_py_radioactive_decay.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE  # noqa: E402

OUT_PATH = os.path.join(
    _REPO, "examples", "python", "Physics", "Radioactive Decay.ksheet"
)


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Decay")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Radioactive Decay",
        "N(t) = N₀ · (½)^(t / t½)  —  edit the inputs, press Ctrl+Enter to replot",
    )

    # ── Input parameters ──────────────────────────────────────────────
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Initial amount N₀",       5000.0),   # B5
        ("Half-life t½ (years)",      12.32),   # B6  (Cs-137 default)
        ("Query time t (years)",      30.0),    # B7
        ("Plot end time (years)",    100.0),    # B8
    ]
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.box(4, 0, 7, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 190)
    s.col_width(1, 120)

    # ── Sticky note ───────────────────────────────────────────────────
    s.note(
        4, 1,
        "Cs-137 defaults (t½ = 12.32 yr, common in nuclear accidents).\n"
        "Try Po-210: t½ = 0.378 yr (138 days).\n"
        "Edit B5–B8 then press Ctrl+Enter on each Python cell.",
        kind="note",
    )

    # ── Python cell 1: plot N(t) ──────────────────────────────────────
    py_plot = """\
=PY
import numpy as np
import matplotlib.pyplot as plt

N0     = float(ks("B5"))   # initial amount
t_half = float(ks("B6"))   # half-life (years)
t_q    = float(ks("B7"))   # query time (years)
t_end  = float(ks("B8"))   # x-axis end (years)

t = np.linspace(0, t_end, 500)
N = N0 * (0.5 ** (t / t_half))

# Amount at query time
N_q = N0 * (0.5 ** (t_q / t_half))

fig, ax = plt.subplots(figsize=(6.5, 4))
ax.plot(t, N, color="#4472c4", linewidth=2.2, label="N(t)")
ax.fill_between(t, N, alpha=0.12, color="#4472c4")

# Mark query point
ax.plot(t_q, N_q, "o", color="#e05c00", markersize=9,
        zorder=5, label=f"N(t={t_q:.1f} yr) = {N_q:.1f}")
ax.axvline(t_q, color="#e05c00", linestyle=":", linewidth=1.3, alpha=0.7)
ax.axhline(N_q, color="#e05c00", linestyle=":", linewidth=1.3, alpha=0.7)

# Mark half-lives as vertical dashed lines
for k in range(1, int(t_end / t_half) + 1):
    tk = k * t_half
    if tk <= t_end:
        ax.axvline(tk, color="#888888", linestyle="--",
                   linewidth=0.8, alpha=0.55)

ax.set_xlabel("Time (years)", fontsize=11)
ax.set_ylabel("Amount remaining N(t)", fontsize=11)
ax.set_title(f"Radioactive Decay  —  N₀={N0:.0f}, t½={t_half:.2f} yr",
             fontsize=12)
ax.legend(fontsize=9)
ax.grid(True, alpha=0.35)
plt.tight_layout()
plt.gcf()
"""
    s.set(9, 0, "Plot cell")
    s.fmt(9, 0, bold=True, font_color=PALETTE["header"])
    s.formula(10, 0, py_plot)
    s.fmt(10, 0, bg=PALETTE["band"], font_family="Courier New", font_size=9)

    # ── Python cell 2: return N at query time (scalar) ────────────────
    py_query = """\
=PY
import numpy as np

N0     = float(ks("B5"))
t_half = float(ks("B6"))
t_q    = float(ks("B7"))

N_q = N0 * (0.5 ** (t_q / t_half))
round(N_q, 4)
"""
    s.set(9, 3, "Amount remaining at t = B7")
    s.fmt(9, 3, bold=True, font_color=PALETTE["header"])
    s.formula(10, 3, py_query)
    s.fmt(10, 3, bg=PALETTE["good"], align="center",
          number_format="0.0000", bold=True)
    s.col_width(3, 220)

    wb.save(OUT_PATH)
    return OUT_PATH


if __name__ == "__main__":
    print("Wrote", build())
