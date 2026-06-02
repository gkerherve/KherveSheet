"""Build the "Vacuum Pump-Down" demo .ksheet example.

Models the exponential pressure decay in a chamber evacuated by a
constant-speed pump:  P(t) = P_ult + (P0 - P_ult) * exp(-t / tau),
where  tau = V / S.

Editable inputs live in column B:
  B5 = V (chamber volume, L)
  B6 = S (pump speed, L/s)
  B7 = P0 (initial pressure, mbar)
  B8 = P_ult (ultimate pressure, mbar)
  B9 = N (number of time steps)

Run:  python examples/build_vacuum_pumpdown.py

Copyright (C) 2026 Gwilherm Kerherve - GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402


def build() -> str:
    # ── Physical inputs (default values) ─────────────────────────────
    V       = 50.0      # chamber volume (L)
    S       = 5.0       # pump speed (L/s)
    P0      = 1000.0    # initial pressure (mbar)
    P_ult   = 1e-3      # ultimate pressure (mbar)
    n_steps = 40        # number of time steps in table

    tau   = V / S                        # time constant (s)
    t_max = 5.0 * tau
    times     = np.linspace(0.0, t_max, n_steps)
    pressures = P_ult + (P0 - P_ult) * np.exp(-times / tau)

    # ── Workbook ──────────────────────────────────────────────────────
    wb = Workbook(min_rows=56, min_cols=14)
    s  = wb.add_sheet("Pump-Down")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 225)   # label column A
    s.col_width(1, 110)   # value column B
    s.col_width(2, 25)    # spacer C
    s.col_width(3, 110)   # t (s)  D
    s.col_width(4, 130)   # P (mbar)  E
    s.col_width(5, 110)   # log10(P)  F

    # ── Title block (rows 0-1) ────────────────────────────────────────
    s.title_block(
        "Vacuum Pump-Down",
        "P(t) = P_ult + (P0 - P_ult) * exp(-t/tau),  tau = V/S",
        span=8,
    )

    # ── Inputs panel  (rows 3-9, cols 0-1) ───────────────────────────
    #   Row 3 (index 3): "Inputs" heading
    #   Row 4 (index 4 = sheet row 5): this will be the FIRST input.
    #
    #   Mapping:
    #     B5 (row-index 4, col 1) = V
    #     B6 (row-index 5, col 1) = S
    #     B7 (row-index 6, col 1) = P0
    #     B8 (row-index 7, col 1) = P_ult
    #     B9 (row-index 8, col 1) = N

    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"], font_size=11)

    input_rows = [
        ("Chamber volume V (L)",            V),
        ("Pump speed S (L/s)",              S),
        ("Initial pressure P0 (mbar)",      P0),
        ("Ultimate pressure P_ult (mbar)",  P_ult),
        ("Time steps N",                    n_steps),
    ]
    for i, (lbl, val) in enumerate(input_rows):
        r = 4 + i                          # 0-based row indices 4..8
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="right", number_format="0.000")
    s.box(4, 0, 8, 1, color=PALETTE["accent"], width=1.2)

    # Yellow notes
    s.note(4, 1,
           "Edit V or S to change the time constant tau = V/S.  "
           "The whole table, chart and summary update automatically.",
           kind="note")
    s.note(6, 1,
           "P0 is the starting pressure (atmospheric = 1013 mbar).  "
           "Try values between 100 and 2000 mbar.",
           kind="note")
    s.note(7, 1,
           "P_ult is the pump's ultimate (base) pressure — "
           "the minimum it can reach regardless of pumping time.",
           kind="note")

    # ── Summary panel (rows 3-9, cols 3-4) ───────────────────────────
    #   Absolute cell refs (1-based sheet row = 0-based index + 1):
    #     $B$5 = V  (index 4)
    #     $B$6 = S  (index 5)
    #     $B$7 = P0 (index 6)
    #     $B$8 = P_ult (index 7)
    #
    #   Summary values placed at:
    #     E4 (index 3, col 4) — tau = V/S
    #     E5 (index 4, col 4) — P at t = tau
    #     E6 (index 5, col 4) — time to 1 mbar
    #     E7 (index 6, col 4) — time to 0.01 mbar
    #     E8 (index 7, col 4) — P at t = 5*tau
    #
    #   Guard against LN(<=0): instead of 1E-15 (formula engine treats 'E'
    #   as a column letter), use a literal tiny decimal 0.0000001.

    s.set(3, 3, "Summary")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"], font_size=11)
    s.col_width(3, 210)
    s.col_width(4, 140)

    # tau = V/S
    s.set(4, 3, "Time constant tau = V/S  (s)")
    s.formula(4, 4, "=$B$5/$B$6")
    s.fmt(4, 3, align="left")
    s.fmt(4, 4, bg=PALETTE["band"], align="right",
          number_format="0.00", bold=True)

    # P at t = tau: P_ult + (P0 - P_ult)*e^(-1)
    s.set(5, 3, "Pressure at t = tau  (mbar)")
    s.formula(5, 4, "=$B$8+($B$7-$B$8)*EXP(-1)")
    s.fmt(5, 3, align="left")
    s.fmt(5, 4, bg=PALETTE["band"], align="right",
          number_format="0.00E+00", bold=True)

    # Time to reach 1 mbar: tau * LN((P0-P_ult)/(1-P_ult))
    # Guard with MAX(..., 0.0000001) to avoid LN(0)
    s.set(6, 3, "Time to 1 mbar  (s)")
    s.formula(6, 4,
              "=($B$5/$B$6)*LN(($B$7-$B$8)/MAX(1-$B$8,0.0000001))")
    s.fmt(6, 3, align="left")
    s.fmt(6, 4, bg=PALETTE["good"], align="right",
          number_format="0.0", bold=True)

    # Time to reach 0.01 mbar: tau * LN((P0-P_ult)/(0.01-P_ult))
    s.set(7, 3, "Time to 0.01 mbar  (s)")
    s.formula(7, 4,
              "=($B$5/$B$6)*LN(($B$7-$B$8)/MAX(0.01-$B$8,0.0000001))")
    s.fmt(7, 3, align="left")
    s.fmt(7, 4, bg=PALETTE["good"], align="right",
          number_format="0.0", bold=True)

    # P at t = 5*tau: near-ultimate
    s.set(8, 3, "P at t = 5*tau  (mbar)")
    s.formula(8, 4, "=$B$8+($B$7-$B$8)*EXP(-5)")
    s.fmt(8, 3, align="left")
    s.fmt(8, 4, bg=PALETTE["good"], align="right",
          number_format="0.00E+00", bold=True)

    s.box(4, 3, 8, 4, color=PALETTE["header"], width=1.2)

    # ── Data table: t / P / log10(P) ─────────────────────────────────
    #   table() places header at start_row (0-based = 10), data starts
    #   at 0-based row 11 (sheet row 12, 1-based).
    #
    #   Column layout:
    #     col 3 (D) = t (s)
    #     col 4 (E) = P (mbar)
    #     col 5 (F) = log10(P)
    #
    #   Formulas reference:
    #     $B$5 = V,  $B$6 = S,  $B$7 = P0,  $B$8 = P_ult
    #
    #   t_k = 5*(V/S) * k/(N-1)  for k=0..N-1
    #   P_k = P_ult + (P0 - P_ult)*EXP(-5*k/(N-1))
    #
    #   NOTE: scientific notation literals such as 1E-15 MUST be avoided
    #   in formulas — the formula engine regex treats 'E' as a column
    #   letter.  Use a plain decimal 0.0000001 as the LOG10 guard.

    TABLE_START  = 10                  # 0-based index of table header row
    first_data_0 = TABLE_START + 1     # 0-based first data row
    first_data_1 = first_data_0 + 1    # 1-based sheet row of first data row

    s.set(9, 3, "Pump-Down Data")
    s.fmt(9, 3, bold=True, font_color=PALETTE["header"], font_size=11)

    table_rows = []
    for k in range(n_steps):
        frac = k / (n_steps - 1)       # 0 .. 1 along 0..5*tau
        # t formula: 5*(V/S)*frac — embed the Python float directly
        t_formula = f"=5*($B$5/$B$6)*{frac}"
        # P formula: P_ult + (P0-P_ult)*EXP(-5*frac)
        p_formula = f"=$B$8+($B$7-$B$8)*EXP(-5*{frac})"
        # log10(P) with tiny guard to keep LOG10 domain safe
        log_formula = f"=LOG10(MAX($B$8+($B$7-$B$8)*EXP(-5*{frac}),0.0000001))"
        table_rows.append([t_formula, p_formula, log_formula])

    s.table(
        TABLE_START, 3,
        headers=["t (s)", "P (mbar)", "log10(P)"],
        rows=table_rows,
        number_format="0.000E+00",
        banded=True,
    )
    # Override t column to plain decimal; log10 column to plain 3 d.p.
    for k in range(n_steps):
        dr = first_data_0 + 1 + k      # 0-based data row (table adds 1 for header)
        s.fmt(dr, 3, number_format="0.00")
        s.fmt(dr, 5, number_format="0.000")

    # Designate X/Y columns for axis hints
    s.designate(3, "X")
    s.designate(4, "Y")

    # ── Chart (live-bound, log Y scale) ──────────────────────────────
    #   table() inserts a header row at TABLE_START (0-based 10), so the
    #   0-based data rows run from first_data_0+1 (11) to
    #   first_data_0+n_steps (50).
    chart_r0 = first_data_0 + 1         # inclusive start (0-based)
    chart_r1 = first_data_0 + n_steps   # inclusive end   (0-based)

    s.chart(
        [Series(
            times, pressures,
            label="P(t)",
            plot_type="Line",
            color="#4472c4",
            linewidth=2.2,
            x_col=3,       # col D = t
            y_col=4,       # col E = P
            row_start=chart_r0,
            row_end=chart_r1,
        )],
        at=(710, 30),
        size=(460, 340),
        title="Chamber Pressure vs Time",
        xlabel="Time (s)",
        ylabel="Pressure (mbar)",
        yscale="log",
        grid=True,
        legend=True,
    )

    s.note(9, 5,
           "Log scale: pressure spans ~6 orders of magnitude "
           "(atmospheric to high-vacuum). A straight line on this "
           "log-linear plot means exponential decay.",
           kind="note")

    # ── LaTeX equation (mathtext: \\frac not \\tfrac) ─────────────────
    s.equation(
        r"P(t) = P_{ult} + (P_0 - P_{ult})\, e^{-t/\tau},"
        r"\quad \tau = V/S",
        at=(710, 390),
        fontsize=17,
        color="#1a1a2e",
        bg_color="#f5f8ff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(460, 58),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Vacuum Pump-Down.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
