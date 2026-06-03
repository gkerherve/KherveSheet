"""Build the "Reaction Kinetics" Analysis template .ksheet.

Covers integrated rate law analysis for a first-order reaction A → P:
  [A](t) = [A]₀ · exp(−k·t)

Features
--------
* Editable inputs: [A]₀, k, gas constant R — all referenced via $-anchors.
* 25-row data table (Time, [A], [P], ln([A]), 1/[A]) with every output
  column driven by live scalar formulas.
* Summary panel: half-life t½ = ln(2)/k.
* Arrhenius mini-block (6 temperatures): 1/T and ln(k_arr) columns, plus
  Ea derived analytically from the two endpoint rows (avoids SLOPE which
  is unimplemented).
* Two live-bound charts:
    (a) ln([A]) vs Time  — confirms first-order linearity
    (b) ln(k) vs 1/T    — Arrhenius plot
* Two LaTeX equations: integrated rate law and Arrhenius.
* Three instructive sticky notes.

Run:  python examples/build_tpl_reaction_kinetics.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

from __future__ import annotations

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Physical defaults ─────────────────────────────────────────────────
A0      = 1.0        # initial concentration (M)
K_RATE  = 0.1       # first-order rate constant (s⁻¹)
R_GAS   = 8.314      # J mol⁻¹ K⁻¹

N_ROWS  = 25         # number of time rows (t = 0 … 4·t½)

# ── Column layout (0-based) for the main kinetics table ──────────────
#   col 0  A : Time (s)
#   col 1  B : [A] (M)
#   col 2  C : [P] (M)
#   col 3  D : ln([A])
#   col 4  E : 1/[A]
COL_TIME = 0
COL_A    = 1
COL_P    = 2
COL_LNA  = 3
COL_INVA = 4

# spacer col 5

# ── Arrhenius block column layout (0-based) ───────────────────────────
#   col 6  G : T (K)
#   col 7  H : 1/T (K⁻¹)
#   col 8  I : k_arr (s⁻¹)  [= A_pre * exp(-Ea/RT)]
#   col 9  J : ln(k_arr)
COL_TEMP  = 6
COL_INVT  = 7
COL_KARR  = 8
COL_LNKARR = 9

# Arrhenius parameters for the mini-block
A_PRE   = 1.0e10     # pre-exponential (s⁻¹)  — scaled so log10(A)≈10
EA_DEF  = 50_000.0   # activation energy (J/mol)

N_ARR   = 6          # number of temperature points (300–550 K)

# ── Table placement ───────────────────────────────────────────────────
TABLE_START = 8          # 0-based row for kinetics table header
ARR_START   = 8          # 0-based row for Arrhenius table header (same line)

# Input cell 1-based addresses
#   [A]₀ : B5  → (row=4, col=1)
#   k     : B6  → (row=5, col=1)
#   R     : B7  → (row=6, col=1)
#   A_pre : H5  → (row=4, col=7)
#   Ea    : H6  → (row=5, col=7)
ADDR_A0    = "$B$5"
ADDR_K     = "$B$6"
ADDR_R     = "$B$7"
ADDR_APRE  = "$H$5"
ADDR_EA    = "$H$6"


def build() -> str:
    # ── Pre-compute numpy arrays for chart initial render ─────────────
    t_half  = np.log(2) / K_RATE
    t_max   = 4.0 * t_half
    times   = np.linspace(0.0, t_max, N_ROWS)
    A_vals  = A0 * np.exp(-K_RATE * times)
    P_vals  = A0 - A_vals
    lnA_vals = np.log(np.maximum(A_vals, 1e-30))
    invA_vals = 1.0 / np.maximum(A_vals, 1e-30)

    T_arr   = np.linspace(300.0, 550.0, N_ARR)
    invT    = 1.0 / T_arr
    k_arr   = A_PRE * np.exp(-EA_DEF / (R_GAS * T_arr))
    lnk_arr = np.log(k_arr)

    # ── Workbook ──────────────────────────────────────────────────────
    wb = Workbook(min_rows=40, min_cols=14)
    s  = wb.add_sheet("Kinetics")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Reaction Kinetics — Integrated Rate Law Analysis",
        "First-order: [A](t) = [A]₀·exp(−k·t)  |  Edit yellow cells to "
        "recalculate the table, half-life, and charts",
        span=10,
    )

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 100)   # A: Time
    s.col_width(1, 100)   # B: [A]
    s.col_width(2, 100)   # C: [P]
    s.col_width(3, 100)   # D: ln([A])
    s.col_width(4, 100)   # E: 1/[A]
    s.col_width(5, 18)    # spacer
    s.col_width(6, 80)    # G: T (K)
    s.col_width(7, 100)   # H: 1/T
    s.col_width(8, 110)   # I: k_arr
    s.col_width(9, 100)   # J: ln(k_arr)

    # ── Input panel — kinetics (cols A-B, rows 4-7) ───────────────────
    s.set(3, 0, "Kinetics Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    kin_inputs = [
        ("[A]₀  — initial concentration (M)",  A0),
        ("k  — rate constant (s⁻¹)",            K_RATE),
        ("R  — gas constant (J mol⁻¹ K⁻¹)",     R_GAS),
    ]
    for i, (lbl, val) in enumerate(kin_inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.0000")
    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.5)

    # ── Summary panel — half-life and % remaining at 2·t½ ────────────
    s.set(3, 2, "Summary")
    s.fmt(3, 2, bold=True, font_color=PALETTE["header"])

    summ_items = [
        ("Half-life  t½ = ln(2) / k  (s)",
         f"=LN(2)/{ADDR_K}",
         PALETTE["band"]),
        ("[A] after 1 half-life  (M)",
         f"={ADDR_A0}/2",
         PALETTE["good"]),
        ("[A] after 2 half-lives  (M)",
         f"={ADDR_A0}/4",
         PALETTE["good"]),
    ]
    for i, (lbl, expr, bg) in enumerate(summ_items):
        r = 4 + i
        s.set(r, 2, lbl)
        s.formula(r, 3, expr)
        s.fmt(r, 2, align="left")
        s.fmt(r, 3, bg=bg, align="center", number_format="0.0000", bold=True)

    s.box(4, 2, 6, 3, color=PALETTE["header"], width=1.5)

    # ── Input panel — Arrhenius (cols G-H, rows 4-7) ─────────────────
    s.set(3, 6, "Arrhenius Inputs")
    s.fmt(3, 6, bold=True, font_color=PALETTE["accent"])

    arr_inputs = [
        ("A  — pre-exponential factor (s⁻¹)", A_PRE),
        ("Eₐ — activation energy (J/mol)",     EA_DEF),
    ]
    for i, (lbl, val) in enumerate(arr_inputs):
        r = 4 + i
        s.set(r, 6, lbl)
        s.set(r, 7, val)
        s.fmt(r, 7, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(4, 6, 5, 7, color=PALETTE["accent"], width=1.5)

    # ── Arrhenius summary — Ea from two endpoints ─────────────────────
    # Ea estimated analytically from first and last rows of Arrhenius table:
    #   Ea = −R · (ln(k_last) − ln(k_first)) / (1/T_last − 1/T_first)
    # Table header at ARR_START (=8), first data 1-based = ARR_START+2 = 10,
    # last data 1-based = ARR_START+1+N_ARR = 15
    arr_first_sr = ARR_START + 2           # 1-based sheet row of first Arr row
    arr_last_sr  = ARR_START + 1 + N_ARR  # 1-based sheet row of last Arr row

    # Ea formula: -R*(lnk_last - lnk_first)/(1/T_last - 1/T_first)
    # Columns: G=T, H=1/T, J=ln(k_arr)
    ea_formula = (
        f"=-{ADDR_R}"
        f"*(J{arr_last_sr}-J{arr_first_sr})"
        f"/(H{arr_last_sr}-H{arr_first_sr})"
    )

    s.set(6, 6, "Eₐ from table endpoints (J/mol)")
    s.formula(6, 7, ea_formula)
    s.fmt(6, 6, align="left")
    s.fmt(6, 7, bg=PALETTE["band"], align="center",
          number_format="0.00", bold=True)
    s.box(6, 6, 6, 7, color=PALETTE["header"], width=1.5)

    # ── Main kinetics table ───────────────────────────────────────────
    # Header at TABLE_START (row 8 0-based → sheet row 9),
    # first data at TABLE_START+1 (0-based) → 1-based sheet row = TABLE_START+2 = 10
    first_data_sr = TABLE_START + 2   # 1-based sheet row of first data row

    s.set(TABLE_START - 1, 0, "Kinetics data table")
    s.fmt(TABLE_START - 1, 0, bold=True, font_color=PALETTE["header"])

    kin_rows = []
    for idx in range(N_ROWS):
        sr  = first_data_sr + idx    # 1-based sheet row
        t_v = round(float(times[idx]), 4)
        kin_rows.append([
            t_v,                                    # Time — literal (independent var)
            f"={ADDR_A0}*EXP(-{ADDR_K}*A{sr})",   # [A](t)
            f"={ADDR_A0}-B{sr}",                    # [P] = [A]₀ - [A]
            f"=LN(B{sr})",                          # ln([A])
            f"=1/B{sr}",                            # 1/[A]
        ])

    s.table(
        TABLE_START, COL_TIME,
        headers=[
            "Time (s)",
            "[A] (M)",
            "[P] (M)",
            "ln([A])",
            "1/[A] (M⁻¹)",
        ],
        rows=kin_rows,
        number_format="0.0000",
        banded=True,
    )

    # Right-align numeric header labels (table() centres headers, which is fine)
    # Designate columns
    s.designate(COL_TIME, "X")
    s.designate(COL_LNA,  "Y")

    # ── Arrhenius mini-table ──────────────────────────────────────────
    # Header at ARR_START (= 8), same row as kinetics header.
    s.set(ARR_START - 1, COL_TEMP, "Arrhenius data")
    s.fmt(ARR_START - 1, COL_TEMP, bold=True, font_color=PALETTE["header"])

    arr_rows = []
    for idx, T_v in enumerate(T_arr):
        sr = arr_first_sr + idx    # 1-based sheet row
        arr_rows.append([
            round(float(T_v), 2),                       # T — literal
            f"=1/G{sr}",                                # 1/T
            f"={ADDR_APRE}*EXP(-{ADDR_EA}/({ADDR_R}*G{sr}))",  # k_arr
            f"=LN(I{sr})",                              # ln(k_arr)
        ])

    s.table(
        ARR_START, COL_TEMP,
        headers=[
            "T (K)",
            "1/T (K⁻¹)",
            "k (s⁻¹)",
            "ln(k)",
        ],
        rows=arr_rows,
        number_format="0.0000",
        banded=True,
    )

    s.designate(COL_INVT,   "X")
    s.designate(COL_LNKARR, "Y")

    # ── Chart 1: ln([A]) vs Time (first-order linearisation) ─────────
    # 0-based data rows: TABLE_START+1 .. TABLE_START+N_ROWS (inclusive)
    r0_kin = TABLE_START + 1
    r1_kin = TABLE_START + N_ROWS

    s.chart(
        [Series(
            x=list(times),
            y=list(lnA_vals),
            label="ln([A])",
            plot_type="Line+Symbol",
            color=PALETTE["header"],
            linewidth=2.0,
            marker="o",
            markersize=4.5,
            markerfacecolor=PALETTE["header"],
            markeredgecolor="#ffffff",
            x_col=COL_TIME,
            y_col=COL_LNA,
            row_start=r0_kin,
            row_end=r1_kin,
        )],
        at=(530, 30),
        size=(420, 280),
        title="First-Order Linearisation: ln([A]) vs Time",
        xlabel="Time (s)",
        ylabel="ln([A])",
        grid=True,
        legend=True,
    )

    # ── Chart 2: Arrhenius ln(k) vs 1/T ──────────────────────────────
    r0_arr = ARR_START + 1
    r1_arr = ARR_START + N_ARR

    s.chart(
        [Series(
            x=list(invT),
            y=list(lnk_arr),
            label="ln(k)",
            plot_type="Line+Symbol",
            color=PALETTE["accent"],
            linewidth=2.0,
            marker="s",
            markersize=5.0,
            markerfacecolor=PALETTE["accent"],
            markeredgecolor="#ffffff",
            x_col=COL_INVT,
            y_col=COL_LNKARR,
            row_start=r0_arr,
            row_end=r1_arr,
        )],
        at=(530, 330),
        size=(420, 260),
        title="Arrhenius Plot: ln(k) vs 1/T",
        xlabel="1/T  (K⁻¹)",
        ylabel="ln(k)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equations ───────────────────────────────────────────────
    # Integrated first-order rate law
    s.equation(
        r"[A](t) = [A]_0 \, e^{-kt}",
        at=(960, 30),
        fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(240, 52),
    )

    # Arrhenius equation
    s.equation(
        r"k = A \, e^{-E_a / (RT)}",
        at=(960, 100),
        fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.2,
        size=(220, 52),
    )

    # Half-life expression
    s.equation(
        r"t_{1/2} = \frac{\ln 2}{k}",
        at=(960, 170),
        fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(180, 52),
    )

    # ── Sticky notes ─────────────────────────────────────────────────
    s.note(
        4, 1,
        "Edit [A]₀ (B5) and k (B6) — the table, half-life, "
        "and ln([A]) chart update instantly.\n"
        "A straight line on ln([A]) vs t confirms first-order kinetics.\n"
        "Use KherveSheet's Trendline (right-click chart) to fit the slope → k.",
        kind="note",
    )
    s.note(
        TABLE_START, 4,
        "1/[A] vs Time is linear for 2nd-order reactions.\n"
        "Use Tools ▸ Solver to find the k that minimises residuals "
        "from your experimental data.",
        kind="note",
    )
    s.note(
        4, 7,
        "Edit Eₐ (H6) or A (H5) to explore how the Arrhenius plot tilts.\n"
        "Slope of ln(k) vs 1/T  =  −Eₐ/R.\n"
        "Eₐ (cell H7) is recovered analytically from the two endpoint rows.",
        kind="note",
    )

    # ── Save ──────────────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Analysis",
    )
    out = os.path.join(out_dir, "Reaction Kinetics.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
