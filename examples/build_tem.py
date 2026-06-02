"""Build the "TEM Electron Wavelength" demo .ksheet example.

Transmission Electron Microscopy — relativistic de Broglie wavelength of
accelerated electrons.  Demonstrates: a title block, a styled banded data
table driven by formulas (relativistic and non-relativistic lambda columns),
designated X/Y columns, a summary panel, two live-bound chart series, and a
LaTeX equation.

Run:  python examples/build_tem.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os

import numpy as np

from ksheet_author import Workbook, Series, PALETTE


def build() -> str:
    # ── Physics constants / reference values ──────────────────────────
    # Relativistic de Broglie wavelength in picometres:
    #   lambda(pm) = 1226.39 / sqrt( V_volts * (1 + 0.00000097845 * V_volts) )
    # NOTE: 0.97845e-6 written as plain decimal (no scientific notation inside
    # formula strings — the engine reads 'E' as a column letter).

    V0_kV = 200.0          # editable highlight voltage (kV)

    # Fixed kV grid for the table: 20, 40, …, 300 kV  (15 rows)
    kv_grid = list(range(20, 320, 20))   # [20, 40, ..., 300]
    n = len(kv_grid)                     # 15 rows

    def lam_rel(kv):
        v = kv * 1000.0
        return 1226.39 / np.sqrt(v * (1.0 + 0.00000097845 * v))

    def lam_nonrel(kv):
        v = kv * 1000.0
        return 1226.39 / np.sqrt(v)

    # ── Workbook / sheet ──────────────────────────────────────────────
    wb = Workbook(min_rows=44, min_cols=14)
    s = wb.add_sheet("TEM Wavelength")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "TEM Electron Wavelength",
        "Relativistic de Broglie wavelength of accelerated electrons "
        "(Transmission Electron Microscopy)"
    )

    # ── Input panel: editable accelerating voltage ────────────────────
    #   V0 literal → B5 (1-based)  →  row=4, col=1
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    s.set(4, 0, "Accelerating voltage V₀ (kV)")
    s.set(4, 1, V0_kV)                    # <-- editable literal
    s.fmt(4, 0, align="left")
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.0")
    s.box(4, 0, 4, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 220)
    s.col_width(1, 90)

    s.note(4, 1,
           "Edit V₀ here (kV). The summary below recalculates "
           "instantly.", kind="note")

    # ── Data table: kV grid, relativistic lambda, non-relativistic lambda
    #   table() starts at row 7 (0-based).
    #   Header → sheet row 8 (1-based).
    #   First data row → sheet row 9 (1-based) → 0-based row index 8.
    table_start = 7     # 0-based

    s.set(6, 0, "Wavelength vs. Accelerating Voltage")
    s.fmt(6, 0, bold=True, font_color=PALETTE["header"])

    rows = []
    for k, kv in enumerate(kv_grid):
        # 1-based sheet row of this data row
        rr = table_start + 2 + k    # header at table_start+1+1 = table_start+2 in 1-based
        # Column A holds the kV literal; formulas reference A{rr}
        rel_formula    = f"=1226.39/SQRT((A{rr}*1000)*(1+0.00000097845*A{rr}*1000))"
        nonrel_formula = f"=1226.39/SQRT(A{rr}*1000)"
        rows.append([kv, rel_formula, nonrel_formula])

    s.table(
        table_start, 0,
        headers=[
            "V (kV)",
            "λ relativistic (pm)",
            "λ non-rel. (pm)",
        ],
        rows=rows,
        number_format="0.000",
        banded=True,
    )

    # Designate columns for chart axis binding
    s.designate(0, "X")   # col A: kV
    s.designate(1, "Y")   # col B: relativistic lambda
    s.designate(2, "Y")   # col C: non-relativistic lambda

    s.col_width(1, 150)
    s.col_width(2, 140)

    # ── Summary panel ─────────────────────────────────────────────────
    # Table data rows occupy 0-based rows table_start+1 … table_start+n
    # In 1-based references that is (table_start+2) … (table_start+1+n)
    first_row_1based = table_start + 2      # first data row, 1-based
    last_row_1based  = table_start + 1 + n  # last  data row, 1-based

    # lambda at V0: formula converts kV → volts inline, refs B5 for V0
    # B5 is (row=4, col=1) in 0-based → sheet row 5, col B → "B5"
    lam_at_v0_formula = (
        "=1226.39/SQRT(($B$5*1000)*(1+0.00000097845*$B$5*1000))"
    )

    # % relativistic correction at 300 kV = last row (B{last}/C{last}-1)*100
    pct_correction_formula = (
        f"=(B{last_row_1based}/C{last_row_1based}-1)*100"
    )

    s.set(6, 4, "Summary")
    s.fmt(6, 4, bold=True, font_color=PALETTE["header"])

    summ = [
        (f"λ at V₀ (pm)",       lam_at_v0_formula,       PALETTE["good"]),
        ("Δ at 300 kV (% correction)", pct_correction_formula,  PALETTE["warn"]),
        ("λ min at 300 kV (pm)",
         f"=B{last_row_1based}",                                     PALETTE["band"]),
    ]
    for i, (lbl, expr, col) in enumerate(summ):
        r = 7 + i
        s.set(r, 4, lbl)
        s.formula(r, 5, expr)
        s.fmt(r, 4, align="left")
        s.fmt(r, 5, bg=col, align="center", number_format="0.000", bold=True)

    s.box(7, 4, 9, 5, color=PALETTE["header"], width=1.0)
    s.col_width(4, 185)
    s.col_width(5, 100)

    # ── Notes ─────────────────────────────────────────────────────────
    s.note(
        table_start + 1, 1,
        "Shorter λ means higher resolution. "
        "200 kV gives ~2.51 pm — enabling atomic-resolution imaging.",
        kind="note",
    )
    s.note(
        table_start + 5, 2,
        "The relativistic correction becomes significant above ~100 kV "
        "and exceeds 5% at 300 kV. "
        "Non-relativistic formula overestimates λ.",
        kind="note",
    )
    s.note(
        6, 0,
        "Wavelengths are in picometres (10⁻¹² m). "
        "Typical atomic spacings are 100–300 pm, so TEM resolves atoms.",
        kind="note",
    )

    # ── Chart: lambda vs kV (two live-bound series) ───────────────────
    # 0-based data rows: table_start+1 … table_start+n  (inclusive)
    row_start_0 = table_start + 1
    row_end_0   = table_start + n      # inclusive

    kv_arr      = np.array(kv_grid, dtype=float)
    y_rel       = np.array([lam_rel(kv)    for kv in kv_grid], dtype=float)
    y_nonrel    = np.array([lam_nonrel(kv) for kv in kv_grid], dtype=float)

    s.chart(
        [
            Series(
                kv_arr, y_rel,
                label="λ relativistic",
                plot_type="Line+Symbol",
                color="#4472c4",
                linewidth=2.0,
                marker="o",
                markersize=5.0,
                x_col=0, y_col=1,
                row_start=row_start_0, row_end=row_end_0,
            ),
            Series(
                kv_arr, y_nonrel,
                label="λ non-relativistic",
                plot_type="Line+Symbol",
                color="#ed7d31",
                linewidth=2.0,
                linestyle="--",
                marker="s",
                markersize=4.0,
                x_col=0, y_col=2,
                row_start=row_start_0, row_end=row_end_0,
            ),
        ],
        at=(560, 30), size=(450, 320),
        title="Electron wavelength vs. accelerating voltage",
        xlabel="Accelerating voltage (kV)",
        ylabel="λ (pm)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    # Use \frac (not \tfrac/\dfrac), \mathrm{} (not \text{})
    # The full relativistic de Broglie relation:
    eq_latex = (
        r"\lambda = \frac{h}{\sqrt{2 m_0 e V"
        r"\left(1 + \frac{e V}{2 m_0 c^2}\right)}}"
    )
    s.equation(
        eq_latex,
        at=(560, 370), fontsize=16,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(450, 60),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "TEM Electron Wavelength.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
