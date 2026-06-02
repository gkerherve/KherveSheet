"""Build the "Acid-Base Titration" demo .ksheet example.

A worked chemistry example: strong acid (HCl) titrated by strong base (NaOH).
Editable inputs let the user change acid concentration, acid volume, and
titrant concentration. A 51-row data table computes pH across the full
titration curve using IF for before/after the equivalence point.
A live-bound chart shows the classic S-curve. A LaTeX equation renders
the definition of pH.

Run:  python examples/build_titration.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import numpy as np

from ksheet_author import Workbook, Series, PALETTE


def build() -> str:
    # ── Physical constants / default inputs ──────────────────────────
    Ca  = 0.10    # acid concentration (mol/L)
    Va  = 25.0    # acid volume (mL)
    Cb  = 0.10    # base concentration (mol/L)

    # Derived quantities (for numpy pre-computation, matching formulas)
    moles_acid = Ca * (Va / 1000.0)              # mol
    V_eq       = moles_acid / Cb * 1000.0        # mL of base at equivalence

    # ── Titration volume array: 0 to 2*Veq in 51 steps ──────────────
    n_steps = 51
    Vb_arr  = np.linspace(0.0, 2.0 * V_eq, n_steps)   # mL added

    # ── pH computation (numpy, mirrors the sheet formulas) ────────────
    # Mirrors the IF formula: conc = MAX(ABS(net)/Vtot, 1E-7)
    #   acid region (net > 0): pH = -LOG10(conc)
    #   base region (net <= 0): pH = 14 + LOG10(conc)
    pH_arr = np.empty(n_steps)
    for i, Vb in enumerate(Vb_arr):
        Va_L  = Va   / 1000.0
        Vb_L  = Vb   / 1000.0
        Vtot  = Va_L + Vb_L
        moles_H   = Ca * Va_L
        moles_OH  = Cb * Vb_L
        net       = moles_H - moles_OH           # positive = excess H+
        conc      = max(abs(net) / Vtot, 1e-7)
        if net > 0:
            pH_arr[i] = -np.log10(conc)
        else:
            pH_arr[i] = 14.0 + np.log10(conc)

    # ── Workbook ─────────────────────────────────────────────────────
    wb = Workbook(min_rows=70, min_cols=14)
    s  = wb.add_sheet("Titration")

    # ── Title block ──────────────────────────────────────────────────
    s.title_block("Acid-Base Titration",
                  "Strong acid (HCl) titrated with strong base (NaOH) "
                  "— edit the yellow cells to recalculate everything",
                  span=8)

    # ── Input panel ──────────────────────────────────────────────────
    # Rows 3-5 (0-based); sheet rows 4-6.
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Acid concentration Ca (mol/L)", Ca,   "0.0000"),
        ("Acid initial volume Va (mL)",   Va,   "0.00"),
        ("Base concentration Cb (mol/L)", Cb,   "0.0000"),
    ]
    for i, (lbl, val, nf) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format=nf)

    s.col_width(0, 230)
    s.col_width(1, 90)
    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.2)

    s.note(4, 1,
           "Edit Ca, Va or Cb here — the full pH curve and chart "
           "recalculate automatically on open.", kind="note")

    # ── Summary panel (cols 3-5, rows 3-8) ──────────────────────────
    # Sheet addresses: Ca=B5, Va=B6, Cb=B7  (rows 4,5,6 → 1-based 5,6,7)
    s.set(3, 3, "Summary")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"])

    summ_rows = [
        # label, formula (or value), bg colour, number_format
        ("Moles of acid (mol)",     "=B5*B6/1000",         PALETTE["band"],      "0.00000"),
        ("Equivalence volume (mL)", "=B5*B6/B7",           PALETTE["good"],      "0.00"),
        ("pH at start (Vb = 0)",    "=-LOG10(B5)",         PALETTE["band"],      "0.00"),
        ("pH at equivalence",       "7.00",                PALETTE["band"],      "0.00"),
    ]
    for i, (lbl, expr, bg, nf) in enumerate(summ_rows):
        r = 4 + i
        s.set(r, 3, lbl)
        if isinstance(expr, str) and expr.startswith("="):
            s.formula(r, 4, expr)
        else:
            s.set(r, 4, expr)
        s.fmt(r, 3, align="left")
        s.fmt(r, 4, bg=bg, align="center", number_format=nf, bold=True)

    s.col_width(3, 200)
    s.col_width(4, 90)
    s.box(4, 3, 7, 4, color=PALETTE["header"], width=1.2)

    # ── Data table ───────────────────────────────────────────────────
    # Table header at row 9 (0-based) → sheet row 10.
    # First data row at row 10 → sheet row 11.
    table_start = 9
    first_data_sheet_row = table_start + 2   # 1-based sheet row of first data row

    # The Vb values go into column A (col 0), pH computed in column B (col 1).
    # Inputs: Ca=B5, Va=B6, Cb=B7 (1-based).
    # Formula (for row r, 1-based):
    #   net  = $B$5*$B$6/1000 - $B$7*A{r}/1000   (positive => excess H+)
    #   Vtot = $B$6/1000 + A{r}/1000
    #   conc = MAX(ABS(net)/Vtot, 1E-7)      -- clamped at 1E-7 mol/L
    #
    # Note: the formula engine evaluates IF branches eagerly, so BOTH
    # log arguments must be positive even when the branch is not taken.
    # Using ABS(net) and clamping at 1E-7 (not 1E-14) ensures:
    #   - LOG10 never receives zero or negative input
    #   - At exact equivalence net=0: MAX(0, 1E-7)=1E-7, giving
    #     -LOG10(1E-7)=7 (acid branch) or 14+LOG10(1E-7)=7 (base branch)
    #
    #   Acid region (net > 0): pH = -LOG10(conc)
    #   Base region (net < 0): pH = 14 + LOG10(conc) = 14 - pOH
    #   At equivalence:        pH = 7 from either branch

    rows = []
    for k, Vb in enumerate(Vb_arr):
        rr = first_data_sheet_row + k   # 1-based sheet row for this data row
        # net  = $B$5*$B$6/1000 - $B$7*A{rr}/1000
        # Vtot = $B$6/1000 + A{rr}/1000
        # clamped concentration: MAX(ABS(net)/Vtot, 1E-7)
        net_expr   = f"$B$5*$B$6/1000-$B$7*A{rr}/1000"
        vtot_expr  = f"$B$6/1000+A{rr}/1000"
        conc_expr  = f"MAX(ABS({net_expr})/({vtot_expr}),1E-7)"
        formula = (
            f"=IF(({net_expr})>0,"
            f"-LOG10({conc_expr}),"
            f"14+LOG10({conc_expr}))"
        )
        rows.append([round(float(Vb), 3), formula])

    s.set(8, 0, "Titration data")
    s.fmt(8, 0, bold=True, font_color=PALETTE["header"])

    s.table(table_start, 0,
            headers=["Volume NaOH added (mL)", "pH"],
            rows=rows,
            number_format="0.00",
            banded=True)

    # Designate columns for chart axis hints
    s.designate(0, "X")
    s.designate(1, "Y")

    # Right-align both numeric columns
    for i in range(n_steps):
        r = table_start + 1 + i
        s.fmt(r, 0, align="right", number_format="0.00")

    # ── Notes ────────────────────────────────────────────────────────
    # Note 1: equivalence point (placed on the summary panel)
    s.note(5, 4,
           "Equivalence point: moles H+ = moles OH-. "
           "At this volume, pH = 7 for a strong acid/base pair. "
           "Change Ca or Cb to shift where equivalence falls.",
           kind="note")

    # Note 2: the pH jump near equivalence (placed on the data table area)
    eq_table_row = table_start + 1 + n_steps // 2   # roughly middle row
    s.note(eq_table_row, 1,
           "The steep pH jump near equivalence arises because "
           "tiny additions of base rapidly exhaust the remaining H+. "
           "A clamp (1e-14 mol) prevents log(0) at exact equivalence.",
           kind="note")

    # Note 3: editable range
    s.note(table_start, 0,
           "Vb ranges from 0 to 2x the equivalence volume. "
           "Edit Ca, Va, or Cb above and the entire curve updates.",
           kind="note")

    # ── Chart (live-bound) ───────────────────────────────────────────
    # Data rows occupy 0-based rows table_start+1 .. table_start+n_steps
    # i.e. rows 10..60 (0-based).
    r0 = table_start + 1
    r1 = table_start + n_steps   # inclusive

    s.chart(
        [Series(
            x=Vb_arr,
            y=pH_arr,
            label="pH curve",
            plot_type="Line+Symbol",
            color="#4472c4",
            linewidth=2.0,
            marker="o",
            markersize=3.0,
            x_col=0,
            y_col=1,
            row_start=r0,
            row_end=r1,
        )],
        at=(320, 90),
        size=(450, 340),
        title="Acid-Base Titration Curve",
        xlabel="Volume NaOH added (mL)",
        ylabel="pH",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    # pH definition in mathtext — use \log, \mathrm, \left[ \right]
    s.equation(
        r"pH = -\log_{10}\left[\mathrm{H}^{+}\right]",
        at=(320, 450),
        fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(290, 56),
    )

    # ── Save ─────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Acid-Base Titration.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
