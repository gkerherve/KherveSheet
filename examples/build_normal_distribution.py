"""Build the "Normal Distribution" demo .ksheet example.

A statistics example exploring the Gaussian probability density function.
Editable inputs: mean (mu), standard deviation (sigma), number of sample
points, and the x-range in standard deviations.  The data table computes
x, f(x) = 1/(sigma*SQRT(2*PI()))*EXP(-((x-mu)^2)/(2*sigma^2)), and the
z-score for each row.  A summary panel reports peak density and the
68-95-99.7 rule.  A live-bound bell-curve chart and a mathtext PDF equation
complete the workbook.

Run:  python examples/build_normal_distribution.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os

import numpy as np

from ksheet_author import Workbook, Series, PALETTE


def build() -> str:
    # ── Default parameter values ──────────────────────────────────────
    mu = 0.0          # mean
    sigma = 1.0       # standard deviation
    n = 61            # number of sample points
    x_range_sigma = 4.0  # plot extent: +/- x_range_sigma * sigma

    # ── Numpy arrays matching what the sheet formulas produce ─────────
    x_vals = np.linspace(mu - x_range_sigma * sigma,
                         mu + x_range_sigma * sigma, n)
    pdf_vals = (1.0 / (sigma * np.sqrt(2.0 * np.pi))
                * np.exp(-0.5 * ((x_vals - mu) / sigma) ** 2))
    z_vals = (x_vals - mu) / sigma

    # ── Column layout (0-based) ───────────────────────────────────────
    # Col 0  : x
    # Col 1  : f(x)  — Y column for the chart
    # Col 2  : z-score
    # (summary panel starts at col 5)

    wb = Workbook(min_rows=70, min_cols=14)
    s = wb.add_sheet("Normal Distribution")

    # ── Title block ───────────────────────────────────────────────────
    s.title_block("Normal Distribution",
                  "Gaussian probability density function — edit the "
                  "inputs and watch the bell curve update",
                  span=8)

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 100)   # x
    s.col_width(1, 130)   # f(x)
    s.col_width(2, 100)   # z-score
    s.col_width(3, 20)    # spacer
    s.col_width(4, 170)   # input label
    s.col_width(5, 110)   # input value / summary label
    s.col_width(6, 140)   # summary value

    # ── Input panel (rows 3-6, 0-based) ──────────────────────────────
    # Sheet rows (1-based): 4, 5, 6, 7
    # So B4=$B$4=row3,col1; B5=row4,col1; B6=row5,col1; B7=row6,col1
    s.set(3, 4, "Parameters (editable)")
    s.fmt(3, 4, bold=True, font_color=PALETTE["accent"], font_size=11)

    inputs = [
        ("Mean  mu", mu),          # row 4 (0-based 3+1=4 => sheet row 5)
        ("Std deviation  sigma", sigma),
        ("Sample points  n", n),
        ("Range (+/- sigma)", x_range_sigma),
    ]
    # 0-based rows 4, 5, 6, 7  => sheet rows 5, 6, 7, 8
    for i, (lbl, val) in enumerate(inputs):
        r = 4 + i
        s.set(r, 4, lbl)
        s.set(r, 5, val)
        s.fmt(r, 4, align="left")
        s.fmt(r, 5, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.box(4, 4, 7, 5, color=PALETTE["accent"], width=1.2)

    # Notes — placed next to the editable inputs
    s.note(4, 5,
           "Edit mu (mean) to shift the bell curve left or right. "
           "The chart, table, and summary all recompute automatically.",
           kind="note")
    s.note(5, 5,
           "Edit sigma (std deviation) to change the spread. "
           "Larger sigma = wider, flatter curve; "
           "smaller sigma = taller, narrower curve.",
           kind="note")
    s.note(7, 5,
           "68-95-99.7 Rule: ~68% of probability lies within +/-1 sigma, "
           "~95% within +/-2 sigma, and ~99.7% within +/-3 sigma of mu.",
           kind="note")

    # ── Data table ────────────────────────────────────────────────────
    # table_start = 9 (0-based) → header at sheet row 10, first data row 11
    table_start = 9
    first_data_sheet_row = table_start + 2   # = 11  (1-based)

    # Input cells in 1-based A1 notation:
    #   mu    = F5  (0-based row 4, col 5  => sheet row 5, col F)
    #   sigma = F6  (0-based row 5, col 5  => sheet row 6, col F)
    #   n     = F7  (0-based row 6, col 5  => sheet row 7, col F)
    #   range = F8  (0-based row 7, col 5  => sheet row 8, col F)

    s.set(8, 0, "Probability density table")
    s.fmt(8, 0, bold=True, font_color=PALETTE["header"])

    rows = []
    for k in range(n):
        rr = first_data_sheet_row + k   # 1-based sheet row for this data row
        x_val = round(float(x_vals[k]), 6)
        # PI is a constant (not a function) in the formula engine; use PI not PI()
        pdf_formula = (
            f"=1/($F$6*SQRT(2*PI))*EXP(-(A{rr}-$F$5)^2/(2*$F$6^2))"
        )
        z_formula = f"=(A{rr}-$F$5)/$F$6"
        rows.append([x_val, pdf_formula, z_formula])

    s.table(table_start, 0,
            headers=["x", "f(x)  — PDF", "z-score"],
            rows=rows,
            number_format="0.000000",
            banded=True,
            align_data="right")

    # Left-align the x column (label column gets left-align already from
    # table() but it is numeric here, so we override to right-align it)
    for k in range(n):
        s.fmt(table_start + 1 + k, 0, align="right", number_format="0.000000")

    # Designate columns for chart axis hints
    s.designate(0, "X")
    s.designate(1, "Y")

    # ── Summary panel ─────────────────────────────────────────────────
    # Placed at rows 4-14, cols 5-6  (0-based 4..13, cols 5,6 but col 5
    # is already the input value column — put summary at cols 7-8 instead,
    # starting at row 10 after the input box)

    # Summary block: 0-based rows 10..14, cols 4..6
    summary_start = 10

    s.set(summary_start - 1, 4, "Summary")
    s.fmt(summary_start - 1, 4, bold=True, font_color=PALETTE["header"],
          font_size=11)

    # last data row (1-based)
    last_data_sheet_row = first_data_sheet_row + n - 1
    data_range_B = f"B{first_data_sheet_row}:B{last_data_sheet_row}"

    # Peak density = 1/(sigma*sqrt(2*pi))  using sheet formula
    peak_density = 1.0 / (sigma * np.sqrt(2.0 * np.pi))

    # density at +1 sigma: x = mu + sigma, z = 1
    density_1sigma = (1.0 / (sigma * np.sqrt(2.0 * np.pi))
                      * np.exp(-0.5))

    summary_items = [
        ("Peak density  f(mu)",
         "=1/($F$6*SQRT(2*PI))",
         PALETTE["good"]),
        ("f(mu + sigma)  [z=+1]",
         "=1/($F$6*SQRT(2*PI))*EXP(-0.5)",
         PALETTE["band"]),
        ("f(mu - sigma)  [z=-1]",
         "=1/($F$6*SQRT(2*PI))*EXP(-0.5)",
         PALETTE["band"]),
        ("68% rule: ±1σ coverage",
         "68.27%",
         PALETTE["band_alt"]),
        ("95% rule: ±2σ coverage",
         "95.45%",
         PALETTE["band_alt"]),
        ("99.7% rule: ±3σ coverage",
         "99.73%",
         PALETTE["band_alt"]),
    ]

    for i, (lbl, val, col) in enumerate(summary_items):
        r = summary_start + i
        s.set(r, 4, lbl)
        s.fmt(r, 4, align="left")
        if isinstance(val, str) and val.startswith("="):
            s.formula(r, 5, val)
            s.fmt(r, 5, bg=col, align="center", number_format="0.000000",
                  bold=True)
        else:
            s.set(r, 5, val)
            s.fmt(r, 5, bg=col, align="center", bold=True)

    s.box(summary_start, 4, summary_start + len(summary_items) - 1, 5,
          color=PALETTE["header"], width=1.2)

    # ── Chart (live-bound to columns 0 and 1) ─────────────────────────
    # Data rows in 0-based indexing: rows table_start+1 .. table_start+n
    r0 = table_start + 1
    r1 = table_start + n

    s.chart(
        [Series(
            x_vals, pdf_vals,
            label="f(x)",
            plot_type="Line",
            color="#4472c4",
            linewidth=2.5,
            x_col=0, y_col=1,
            row_start=r0, row_end=r1,
        )],
        at=(560, 30),
        size=(460, 320),
        title="Gaussian Bell Curve",
        xlabel="x",
        ylabel="Probability density f(x)",
        grid=True,
        legend=True,
    )

    # ── Equation (matplotlib mathtext) ────────────────────────────────
    # f(x) = 1/(sigma * sqrt(2*pi)) * exp(-(x-mu)^2 / (2*sigma^2))
    s.equation(
        r"f(x) = \frac{1}{\sigma\sqrt{2\pi}}"
        r"\,\exp\!\left(-\frac{(x-\mu)^{2}}{2\sigma^{2}}\right)",
        at=(560, 370),
        fontsize=18,
        color="#1a1a2e",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(340, 64),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Normal Distribution.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
