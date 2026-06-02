"""Build the "Radioactive Decay" demo .ksheet example.

A physics worked example covering exponential decay:
    N(t) = N₀ · exp(−λ·t)
with an editable input panel (N₀, half-life T½, number of time steps),
a banded formula-driven table (time, remaining quantity, fraction,
activity), a summary panel (λ, mean lifetime τ, N after one T½), a
live-bound chart of N(t) vs time, and two LaTeX equations.

Run:  python examples/build_radioactive_decay.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os

import numpy as np

from ksheet_author import Workbook, Series, PALETTE


def build() -> str:
    # ── Physical defaults ────────────────────────────────────────────
    N0 = 1000.0          # initial quantity (arbitrary units)
    T_half = 5.0         # half-life  (same time unit as t column)
    n_steps = 20         # number of time steps in the table

    lam = np.log(2) / T_half          # decay constant
    tau = 1.0 / lam                    # mean lifetime
    t_max = 5.0 * T_half              # show 5 half-lives
    times = np.linspace(0.0, t_max, n_steps + 1)
    N_vals = N0 * np.exp(-lam * times)
    frac_vals = N_vals / N0
    activity_vals = lam * N_vals       # = λ · N(t)

    # ── Workbook & sheet ─────────────────────────────────────────────
    wb = Workbook(min_rows=44, min_cols=14)
    s = wb.add_sheet("Decay")

    # ── Title block ──────────────────────────────────────────────────
    s.title_block("Radioactive Decay",
                  "N(t) = N₀ · exp(−λ·t)  |  edit the yellow cells to "
                  "explore any isotope",
                  span=8)

    # ── Column widths ────────────────────────────────────────────────
    s.col_width(0, 210)   # label column
    s.col_width(1, 110)   # value column
    s.col_width(2, 20)    # spacer
    s.col_width(3, 190)   # derived-label column
    s.col_width(4, 120)   # derived-value column
    s.col_width(5, 20)    # spacer
    s.col_width(6, 100)   # table: time
    s.col_width(7, 120)   # table: N(t)
    s.col_width(8, 120)   # table: fraction
    s.col_width(9, 130)   # table: activity

    # ── Input panel (editable, highlighted amber) ────────────────────
    #  Inputs live at:
    #    B5  = N0       (row 4, col 1)
    #    B6  = T_half   (row 5, col 1)
    #    B7  = n_steps  (row 6, col 1)  — informational, table is static
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    input_rows = [
        ("Initial quantity N₀ (atoms/Bq)", N0),
        ("Half-life T½ (time units)",       T_half),
        ("Time steps shown",                n_steps + 1),  # 21 rows
    ]
    for i, (lbl, val) in enumerate(input_rows):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.5)
    s.note(4, 1,
           "Edit N₀ (initial quantity), T½ (half-life), then save "
           "to recompute the whole table, summary, and chart.",
           kind="note")

    # ── Derived / summary panel ──────────────────────────────────────
    #  Derived values reference $B$5 (N0) and $B$6 (T_half).
    #    E5 = lambda   = LN(2) / B6      (row 4, col 4)
    #    E6 = tau      = 1 / E5          (row 5, col 4)
    #    E7 = N(T½)    = B5 / 2          (row 6, col 4)
    s.set(3, 3, "Derived constants")
    s.fmt(3, 3, bold=True, font_color=PALETTE["accent"])

    derived = [
        ("Decay constant λ  =  ln(2) / T½",    "=LN(2)/$B$6",  PALETTE["band"]),
        ("Mean lifetime τ  =  1 / λ",           "=1/$E$5",      PALETTE["band_alt"]),
        ("Quantity after one T½  (= N₀ / 2)",   "=$B$5/2",      PALETTE["good"]),
    ]
    for i, (lbl, expr, fill) in enumerate(derived):
        r = 4 + i
        s.set(r, 3, lbl)
        s.formula(r, 4, expr)
        s.fmt(r, 3, align="left")
        s.fmt(r, 4, bg=fill, align="center", number_format="0.0000", bold=True)

    s.box(4, 3, 6, 4, color=PALETTE["header"], width=1.5)
    s.note(4, 4,
           "λ and τ recalculate automatically from T½ in B6.",
           kind="note")

    # ── Data table ───────────────────────────────────────────────────
    #  Layout: columns G..J  (indices 6..9)
    #  table() places the header at sheet row (table_start+1) and the
    #  first data row at sheet row (table_start+2).
    #
    #  Input cells referenced by absolute addresses:
    #    $B$5  = N0        (row 4, col 1)
    #    $B$6  = T_half    (row 5, col 1)
    #    $E$5  = lambda    (row 4, col 4)
    #
    #  Column mapping (0-based):
    #    col 6 → G : time
    #    col 7 → H : N(t)
    #    col 8 → I : fraction remaining
    #    col 9 → J : activity

    table_start = 8          # header at sheet row 9 (0-based row 8)
    # first data row in 1-based sheet addressing:
    first_data_sheet_row = table_start + 2   # = 10

    table_rows = []
    for k in range(n_steps + 1):
        rr = first_data_sheet_row + k   # 1-based sheet row for this data row
        t_val = round(float(times[k]), 4)
        table_rows.append([
            t_val,
            f"=$B$5*EXP(-$E$5*G{rr})",       # N(t)
            f"=H{rr}/$B$5",                   # fraction remaining
            f"=$E$5*H{rr}",                   # activity = lambda * N(t)
        ])

    s.set(7, 6, "Decay table")
    s.fmt(7, 6, bold=True, font_color=PALETTE["header"])
    s.table(
        table_start, 6,
        headers=["t (time units)", "N(t) (atoms)", "Fraction remaining",
                 "Activity  λN(t)"],
        rows=table_rows,
        number_format="0.0000",
        banded=True,
    )

    # Override first column to left-align (time values are numeric but
    # look cleaner right-aligned — keep default).
    # Designate columns for chart axis hints.
    s.designate(6, "X")
    s.designate(7, "Y")
    s.designate(8, "Y")
    s.designate(9, "Y")

    # ── Chart — N(t) vs time, live-bound to table columns ────────────
    #  Data rows in 0-based indexing: table_start+1 .. table_start+1+n_steps
    r0 = table_start + 1               # first data row (0-based)
    r1 = table_start + 1 + n_steps     # last  data row (0-based)

    s.chart(
        [
            Series(
                times, N_vals,
                label="N(t)",
                plot_type="Line+Symbol",
                color="#4472c4",
                linewidth=2.0,
                marker="o",
                markersize=4.0,
                x_col=6,    # column G (0-based index 6) = time
                y_col=7,    # column H (0-based index 7) = N(t)
                row_start=r0,
                row_end=r1,
            ),
            Series(
                times, activity_vals,
                label="Activity λN(t)",
                plot_type="Line",
                color=PALETTE["accent"],
                linewidth=1.8,
                linestyle="--",
                x_col=6,    # column G = time
                y_col=9,    # column J = activity
                row_start=r0,
                row_end=r1,
            ),
        ],
        at=(820, 30),
        size=(460, 310),
        title="Radioactive Decay Curve",
        xlabel="t (time units)",
        ylabel="N(t) / Activity",
        grid=True,
        legend=True,
    )

    # ── LaTeX equations ──────────────────────────────────────────────
    #  Equation 1: the decay law  N(t) = N_0 exp(-lambda t)
    s.equation(
        r"N(t) = N_0 \, e^{-\lambda t}",
        at=(820, 360),
        fontsize=22,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(280, 52),
    )

    #  Equation 2: definition of lambda and tau
    s.equation(
        r"\lambda = \frac{\ln 2}{T_{1/2}} \;,\quad "
        r"\tau = \frac{1}{\lambda}",
        at=(820, 430),
        fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.2,
        size=(320, 52),
    )

    # ── Yellow notes ─────────────────────────────────────────────────
    s.note(0, 11,
           "This workbook was generated by the ksheet-example-author "
           "agent. All formulas re-evaluate on open.",
           kind="note")
    s.note(table_start, 9,
           "Activity = λ · N(t). Halves every T½, just like N(t).",
           kind="note")

    # ── Save ─────────────────────────────────────────────────────────
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Radioactive Decay.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
