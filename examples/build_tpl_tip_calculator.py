"""Build the "Tip Calculator" Finance template .ksheet file.

A polished, real-world-ready tip calculator with:
  - Editable inputs (amber): Bill Amount, Tip %, Number of People
  - Live result panel: Tip Amount, Total Bill, Per-Person Share
  - Reference table of 4 common tip percentages (10/15/18/20%) with
    tip and total for each — all formulas referencing the live bill.
  - A data-bound bar chart: Total-per-Person for each tip-% option.
  - A LaTeX equation for the tip formula.
  - Instructive yellow sticky notes.

Save path: examples/templates/Finance/Tip Calculator.ksheet

Run:  python examples/build_tpl_tip_calculator.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Ensure the repo root is importable.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Default input values ──────────────────────────────────────────────
BILL      = 85.00   # £ total bill before tip
TIP_PCT   = 15.0    # tip percentage chosen by user
N_PEOPLE  = 4       # number of diners

# Reference tip options shown in the lookup table.
REF_PCTS  = [10.0, 15.0, 18.0, 20.0]


def _compute_ref(bill: float, pct: float, n: int) -> tuple:
    """Return (tip_amount, total, per_person) for one tip %."""
    tip   = bill * pct / 100.0
    total = bill + tip
    per   = total / n
    return tip, total, per


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s  = wb.add_sheet("Tip Calculator")

    # ── Column widths ──────────────────────────────────────────────────
    s.col_width(0, 200)   # A: label
    s.col_width(1, 130)   # B: value
    s.col_width(2, 30)    # C: spacer
    s.col_width(3, 200)   # D: result label
    s.col_width(4, 130)   # E: result value
    s.col_width(5, 30)    # F: spacer
    s.col_width(6, 90)    # G: Tip %
    s.col_width(7, 115)   # H: Tip Amount
    s.col_width(8, 115)   # I: Total Bill
    s.col_width(9, 125)   # J: Per Person

    # ── Title block ───────────────────────────────────────────────────
    # 0-based rows 0-1; merges across columns 0..9
    s.title_block("Tip Calculator",
                  "Enter your bill below — all results update instantly",
                  span=10)

    # ── Input panel ──────────────────────────────────────────────────
    # Labels col A (0), values col B (1).
    # 0-based rows 3..5  →  1-based sheet refs B4, B5, B6.
    s.set(2, 0, "Inputs")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"], font_size=11)

    inputs = [
        ("Bill Amount (£)",       BILL,      "$#,##0.00"),
        ("Tip Percentage (%)",    TIP_PCT,   "0.0"),
        ("Number of People",      N_PEOPLE,  "0"),
    ]
    for i, (lbl, val, nfmt) in enumerate(inputs):
        r = 3 + i   # 0-based rows 3, 4, 5
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center",
              number_format=nfmt, bold=True, font_size=12)

    s.box(3, 0, 5, 1, color=PALETTE["accent"], width=2.0)

    # Notes on inputs.
    s.note(3, 1,
           "Edit B4 to enter the bill total (before tip).\n"
           "The tip amount, total, and split all recalculate.",
           kind="note")
    s.note(4, 1,
           "Edit B5 to change the tip percentage.\n"
           "The reference table below shows 10/15/18/20% comparisons.",
           kind="note")
    s.note(5, 1,
           "Edit B6 to split the bill among N diners.\n"
           "Per-person share updates throughout.",
           kind="note")

    # ── Results panel ─────────────────────────────────────────────────
    # D (col 3) = label, E (col 4) = formula result.
    # Inputs: B4=Bill, B5=Tip%, B6=N_People  (1-based sheet rows 4, 5, 6)
    s.set(2, 3, "Results")
    s.fmt(2, 3, bold=True, font_color=PALETTE["header"], font_size=11)

    # Row 3 (0-based) → sheet row 4: Tip Amount = Bill * TipPct / 100
    s.set(3, 3, "Tip Amount (£)")
    s.formula(3, 4, "=$B$4*$B$5/100")
    s.fmt(3, 3, align="left")
    s.fmt(3, 4, bg=PALETTE["band"], align="right",
          number_format="$#,##0.00", bold=True, font_size=13)

    # Row 4 → sheet row 5: Total = Bill + TipAmount
    s.set(4, 3, "Total Bill (£)")
    s.formula(4, 4, "=$B$4+$B$4*$B$5/100")
    s.fmt(4, 3, align="left")
    s.fmt(4, 4, bg=PALETTE["good"], align="right",
          number_format="$#,##0.00", bold=True, font_size=13)

    # Row 5 → sheet row 6: Per Person = Total / N_People
    s.set(5, 3, "Each Person Pays (£)")
    s.formula(5, 4, "=($B$4+$B$4*$B$5/100)/$B$6")
    s.fmt(5, 3, align="left")
    s.fmt(5, 4, bg=PALETTE["accent"], font_color="#ffffff",
          align="right", number_format="$#,##0.00", bold=True, font_size=14)

    s.box(3, 3, 5, 4, color=PALETTE["header"], width=2.0)

    # ── Reference table — common tip percentages ───────────────────────
    # Header at 0-based row 8 → sheet row 9.
    # First data row at 0-based row 9 → sheet row 10.
    # Bill lives at $B$4 (1-based).  N_People at $B$6.
    #
    # Columns: G=Tip%, H=Tip Amount, I=Total Bill, J=Per Person
    # 0-based: col 6, 7, 8, 9.
    TABLE_START = 8

    s.set(7, 6, "Tip Comparison Table")
    s.fmt(7, 6, bold=True, font_color=PALETTE["header"], font_size=11)
    s.merge(7, 6, 1, 4)

    s.note(TABLE_START, 6,
           "This table compares common tip percentages.\n"
           "The bill (B4) and diners (B6) are live-linked here too.",
           kind="note")

    ref_rows = []
    for pct in REF_PCTS:
        # All three result cells are formulas referencing $B$4 and $B$6.
        # The Tip% literal stays as a plain number (the independent variable).
        rr_label = f"{pct:.0f}%"
        tip_formula   = f"=$B$4*{pct}/100"
        total_formula = f"=$B$4+$B$4*{pct}/100"
        # Per-person: total / N_People
        per_formula   = f"=($B$4+$B$4*{pct}/100)/$B$6"
        ref_rows.append([rr_label, tip_formula, total_formula, per_formula])

    s.table(TABLE_START, 6,
            headers=["Tip %", "Tip Amount (£)", "Total Bill (£)",
                     "Per Person (£)"],
            rows=ref_rows,
            number_format="$#,##0.00",
            banded=True)

    # Mark the Tip% column (col 6 = G) as X; Per-Person (col 9 = J) as Y.
    s.designate(6, "X")
    s.designate(9, "Y")

    # ── Bar chart: Per-Person across tip options ──────────────────────
    # 0-based data rows: TABLE_START+1 .. TABLE_START+len(REF_PCTS)
    #   = rows 9 .. 12.
    # x_col = 6 (Tip % label, but numeric X from row index is fine;
    #   we supply REF_PCTS as x array for first render).
    # y_col = 9 (Per Person).
    r0 = TABLE_START + 1           # 0-based first data row (= 9)
    r1 = TABLE_START + len(REF_PCTS)  # 0-based last data row (= 12)

    # Pre-compute y values for first render — match formula semantics.
    x_pcts = np.array(REF_PCTS, dtype=float)
    y_per  = np.array(
        [(_compute_ref(BILL, p, N_PEOPLE)[2]) for p in REF_PCTS],
        dtype=float)

    s.chart(
        [Series(
            x_pcts, y_per,
            label="Per-Person Share",
            plot_type="Bar",
            color=PALETTE["header"],
            x_col=6,   # G = Tip %  (0-based col 6)
            y_col=9,   # J = Per Person (0-based col 9)
            row_start=r0,
            row_end=r1,
        )],
        at=(530, 30),
        size=(430, 270),
        title="Per-Person Share by Tip %",
        xlabel="Tip Option",
        ylabel="Amount per Person (£)",
        grid=True,
        legend=False,
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    # Tip formula: Tip = Bill * p/100;  Total = Bill * (1 + p/100)
    s.equation(
        r"\mathrm{Total} = \mathrm{Bill} \times \left(1 + \frac{p}{100}\right)",
        at=(530, 320),
        fontsize=18,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(340, 56),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Finance", "Tip Calculator.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
