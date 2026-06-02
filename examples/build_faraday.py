"""Build the "Faraday Induction" demo .ksheet example.

A worked electromagnetism example covering Faraday's law of induction.
A coil of N turns and cross-sectional area A sits in a sinusoidally
varying magnetic field B(t) = B0·sin(2πft).  The magnetic flux is
Φ = N·A·B0·sin(2πft) and the induced EMF is
ε = -dΦ/dt = -N·A·B0·(2πf)·cos(2πft).

Features demonstrated: editable input panel, fixed time grid (literals),
formula-driven flux and EMF columns, dual-series live-bound chart,
summary formulas, and an embedded mathtext equation.

Run:  python examples/build_faraday.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import numpy as np
from ksheet_author import Workbook, Series, PALETTE

# ---------------------------------------------------------------------------
# Physical constants and layout decisions
# ---------------------------------------------------------------------------
TWO_PI = 6.283185          # 2π as a plain decimal — never use E-notation
N_TURNS = 200              # number of turns (editable input)
A_COIL = 0.01              # coil area (m²)
B0 = 0.5                   # peak field (T)
FREQ = 50.0                # frequency (Hz)
N_POINTS = 41              # time-grid points (covers ~2 full periods)

# Input cell addresses (1-based, column B = index 1)
# Row 5 → N  (B5)
# Row 6 → A  (B6)
# Row 7 → B0 (B7)
# Row 8 → f  (B8)
N_REF  = "$B$5"
A_REF  = "$B$6"
B0_REF = "$B$7"
F_REF  = "$B$8"

# Table starts at 0-based row 11; header is sheet row 12; first data row is 13
TABLE_START = 11   # 0-based

# Time grid: two full periods for f = 50 Hz → T = 0.02 s → 2T = 0.04 s
T_END = 2.0 / FREQ         # 0.04 s
times = np.linspace(0.0, T_END, N_POINTS)

# Pre-compute numpy arrays for chart initial render (must match formulas)
phi_arr = N_TURNS * A_COIL * B0 * np.sin(TWO_PI * FREQ * times)
emf_arr = -N_TURNS * A_COIL * B0 * TWO_PI * FREQ * np.cos(TWO_PI * FREQ * times)


def build() -> str:
    wb = Workbook(min_rows=58, min_cols=16)
    s = wb.add_sheet("Faraday")

    # ── Title block ──────────────────────────────────────────────────────
    s.title_block(
        "Faraday Induction",
        "Flux and induced EMF in a coil under a sinusoidal magnetic field",
        span=8,
    )

    # ── Input panel ──────────────────────────────────────────────────────
    s.set(3, 0, "Inputs — edit these cells")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    s.merge(3, 0, 1, 4)

    inputs = [
        ("Number of turns  N",  N_TURNS, "0"),
        ("Coil area  A  (m²)",  A_COIL,  "0.0000"),
        ("Peak field  B₀  (T)", B0,      "0.000"),
        ("Frequency  f  (Hz)",  FREQ,    "0.0"),
    ]
    for i, (lbl, val, nfmt) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center",
              number_format=nfmt, bold=True)

    s.box(4, 0, 7, 1, color=PALETTE["accent"], width=1.2)
    s.col_width(0, 200)
    s.col_width(1, 90)

    s.note(4, 1,
           "Edit N, A, B0 or f here.\n"
           "Every flux and EMF cell is a live formula — "
           "values update instantly.",
           kind="note")

    # ── Summary panel ───────────────────────────────────────────────────
    # Peak EMF = N * A * B0 * 2π * f  (all referenced via input cells)
    # Period   = 1 / f
    s.set(3, 4, "Summary")
    s.fmt(3, 4, bold=True, font_color=PALETTE["header"])
    s.merge(3, 4, 1, 3)

    summary = [
        ("Peak EMF  |ε|  (V)",
         f"={N_REF}*{A_REF}*{B0_REF}*{TWO_PI}*{F_REF}",
         PALETTE["good"]),
        ("Period  T  (s)",
         f"=1/{F_REF}",
         PALETTE["band"]),
        ("Phase: EMF leads flux by (°)",
         "90",
         PALETTE["band_alt"]),
    ]
    for i, (lbl, val_or_formula, col) in enumerate(summary):
        r = 4 + i
        s.set(r, 4, lbl)
        if isinstance(val_or_formula, str) and val_or_formula.startswith("="):
            s.formula(r, 5, val_or_formula)
        else:
            s.set(r, 5, val_or_formula)
        s.fmt(r, 4, align="left")
        s.fmt(r, 5, bg=col, align="center", number_format="0.0000", bold=True)

    s.box(4, 4, 6, 5, color=PALETTE["header"], width=1.2)
    s.col_width(4, 220)
    s.col_width(5, 100)

    s.note(6, 5,
           "EMF always leads flux by exactly 90°.\n"
           "EMF is the derivative of flux w.r.t. time,\n"
           "so a cosine comes from a sine.",
           kind="note")

    # ── Data table: t | Φ | ε ───────────────────────────────────────────
    # Column layout (0-based): col 0 = t (literal), col 1 = Φ (formula),
    #                           col 2 = ε (formula)
    # Sheet col letters: A=0, B=1, C=2.
    # Table header is at sheet row TABLE_START+1 = 12.
    # First data row is at sheet row TABLE_START+2 = 13 (1-based).

    s.set(TABLE_START - 1, 0, "Time series — 2 periods")
    s.fmt(TABLE_START - 1, 0, bold=True, font_color=PALETTE["header"])

    table_rows = []
    for k, t in enumerate(times):
        # 1-based sheet row of this data row
        rr = TABLE_START + 2 + k          # header is at TABLE_START+1+1 = 13 for k=0
        t_str = f"{t:.6f}"               # literal, plain decimal — no sci notation
        phi_formula = (
            f"={N_REF}*{A_REF}*{B0_REF}"
            f"*SIN({TWO_PI}*{F_REF}*A{rr})"
        )
        emf_formula = (
            f"=-{N_REF}*{A_REF}*{B0_REF}"
            f"*{TWO_PI}*{F_REF}"
            f"*COS({TWO_PI}*{F_REF}*A{rr})"
        )
        table_rows.append([t_str, phi_formula, emf_formula])

    s.table(
        TABLE_START, 0,
        headers=["t  (s)", "Φ  (Wb)", "EMF  ε  (V)"],
        rows=table_rows,
        number_format="0.0000",
        banded=True,
    )

    # Designate columns for the chart axis hints
    s.designate(0, "X")
    s.designate(1, "Y")
    s.designate(2, "Y")

    s.col_width(0, 100)
    s.col_width(1, 110)
    s.col_width(2, 110)

    s.note(TABLE_START, 2,
           "EMF = -dΦ/dt.\n"
           "The negative sign means a rising flux induces\n"
           "an opposing (negative) EMF — Lenz's law.",
           kind="note")

    # ── Chart: Φ and ε vs time (dual series, live-bound) ────────────────
    # 0-based row bounds for the data region:
    #   header occupies TABLE_START (0-based row 11)
    #   first data row: TABLE_START + 1 = 12
    #   last data row:  TABLE_START + N_POINTS = 51
    row0 = TABLE_START + 1
    row1 = TABLE_START + N_POINTS

    s.chart(
        [
            Series(
                x=times, y=phi_arr,
                label="Flux Φ (Wb)",
                plot_type="Line",
                color="#4472c4",
                linewidth=2.0,
                x_col=0, y_col=1,
                row_start=row0, row_end=row1,
            ),
            Series(
                x=times, y=emf_arr,
                label="EMF ε (V)",
                plot_type="Line",
                color="#ed7d31",
                linewidth=2.0,
                linestyle="--",
                x_col=0, y_col=2,
                row_start=row0, row_end=row1,
            ),
        ],
        at=(480, 30),
        size=(470, 320),
        title="Flux and Induced EMF vs Time",
        xlabel="Time t (s)",
        ylabel="Φ (Wb)  /  ε (V)",
        grid=True,
        legend=True,
    )

    # ── Equation (mathtext — \frac, no \tfrac) ───────────────────────────
    # ε = -N dΦ/dt = -N A B₀ (2πf) cos(2πft)
    latex = (
        r"\mathcal{E} = -N\frac{d\Phi}{dt}"
        r" = -N A B_0 (2\pi f)\cos(2\pi f t)"
    )
    s.equation(
        latex,
        at=(480, 370),
        fontsize=17,
        color="#111111",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.3,
        size=(470, 56),
    )

    # ── Extra note: proportionality ──────────────────────────────────────
    s.note(8, 4,
           "Peak EMF = N · A · B₀ · 2πf.\n"
           "Doubling N or f doubles the peak EMF.\n"
           "This is why power-grid generators run at exactly 50 Hz.",
           kind="note")

    # ── Save ─────────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Faraday Induction.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
