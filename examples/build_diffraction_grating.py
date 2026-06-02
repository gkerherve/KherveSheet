"""Build the "Diffraction Grating" exercise .ksheet (Year-2 Physics).

Two-sheet workbook:
  Sheet 1 "Problem"  — problem statement, given inputs, numbered tasks,
                        blank answer cells.
  Sheet 2 "Solution" — self-contained inputs, live formula table
                        (m, sin θ, θ in degrees), highest order, angular
                        separation, data-bound Bar chart, grating equation.

Key design note on units (avoids the rounding-to-zero trap):
  λ is stored in nm (B6), N in lines/mm (B5).
  Formulas avoid any intermediate cell whose value would be < 5e-4 after
  3-decimal rounding (which would round to 0.0 and break chained refs).
  Instead every derived formula inlines the unit conversions:
    sin θ_m  = m * λ(nm) * N(lines/mm) / 1_000_000
    m_max    = INT( 1_000_000 / (N * λ_nm) )
    d (µm)   = 1_000 / N   [display only — no cell depends on it]
    d (m)    = 1 / (N * 1000)  [shown in summary as a TEXT formula]

Run:  python examples/build_diffraction_grating.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys
import math

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Physical constants / default inputs ──────────────────────────────
LINES_PER_MM = 600           # N, lines per mm
LAMBDA_NM    = 633.0         # λ, wavelength in nm (HeNe laser)
D_M          = 1.0 / (LINES_PER_MM * 1000.0)   # grating spacing in m (numpy only)
D_UM         = 1000.0 / LINES_PER_MM            # grating spacing in µm (display)

ORDERS = [1, 2, 3, 4, 5]


def _theta_deg(m, d_m, lam_m):
    """Compute diffraction angle in degrees; NaN if evanescent."""
    ratio = m * lam_m / d_m
    if ratio > 1.0:
        return float("nan")
    return math.degrees(math.asin(ratio))


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=14)

    # ================================================================
    # SHEET 1 — PROBLEM
    # ================================================================
    prob = wb.add_sheet("Problem")

    prob.title_block(
        "Diffraction Grating",
        "Year 2 Physics Exercise — Normal Incidence, Monochromatic Light",
        span=8,
    )

    # ── Background / context ──────────────────────────────────────────
    prob.set(3, 0, "Background")
    prob.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    context_lines = [
        "A diffraction grating consists of N equally-spaced slits (or ruled",
        "lines) per unit length.  When monochromatic light of wavelength λ",
        "is incident normally, bright maxima appear at angles θ satisfying:",
        "",
        "         d sin θ  =  m λ          (m = 0, ±1, ±2, …)",
        "",
        "where d = 1/N is the grating spacing and m is the diffraction order.",
        "The highest visible order m_max satisfies m λ ≤ d.",
    ]
    for i, line in enumerate(context_lines):
        prob.set(4 + i, 0, line)
        if "d sin" in line:
            prob.fmt(4 + i, 0, font_family="Courier New", italic=True)
        prob.merge(4 + i, 0, 1, 9)

    # ── Given (editable inputs) ───────────────────────────────────────
    prob.set(13, 0, "Given (editable values)")
    prob.fmt(13, 0, bold=True, font_size=12, font_color=PALETTE["header"])
    prob.merge(13, 0, 1, 8)

    given_rows = [
        ("Lines per mm", "N", LINES_PER_MM, "lines/mm"),
        ("Wavelength λ", "λ", LAMBDA_NM,    "nm  (HeNe laser: 632.8 nm)"),
    ]
    prob.set(14, 0, "Quantity")
    prob.set(14, 1, "Symbol")
    prob.set(14, 2, "Value")
    prob.set(14, 3, "Units / Notes")
    for c in range(4):
        prob.fmt(14, c, bold=True, bg=PALETTE["header"],
                 font_color=PALETTE["header_text"], align="center")

    for i, (qty, sym, val, units) in enumerate(given_rows):
        r = 15 + i
        prob.set(r, 0, qty)
        prob.set(r, 1, sym)
        prob.set(r, 2, val)
        prob.set(r, 3, units)
        prob.fmt(r, 0, align="left")
        prob.fmt(r, 1, align="center", italic=True)
        prob.fmt(r, 2, bg=PALETTE["warn"], align="center",
                 number_format="0.0")
        prob.fmt(r, 3, align="left", italic=True, font_color="#555555")

    prob.col_width(0, 160)
    prob.col_width(1, 60)
    prob.col_width(2, 90)
    prob.col_width(3, 220)
    prob.box(14, 0, 16, 3, color=PALETTE["accent"], width=1.2)

    prob.note(15, 2,
              "Edit N or λ on the Solution sheet to see all answers "
              "recalculate instantly.",
              kind="note")

    # ── Tasks ─────────────────────────────────────────────────────────
    prob.set(18, 0, "Tasks")
    prob.fmt(18, 0, bold=True, font_size=12, font_color=PALETTE["header"])
    prob.merge(18, 0, 1, 8)

    tasks = [
        ("1",  "Calculate the grating spacing d in metres.",
         "d  =", "m"),
        ("2a", "Calculate the diffraction angle θ₁ for order m = 1.",
         "θ₁ =", "°"),
        ("2b", "Calculate the diffraction angle θ₂ for order m = 2.",
         "θ₂ =", "°"),
        ("2c", "Calculate the diffraction angle θ₃ for order m = 3.",
         "θ₃ =", "°"),
        ("3",  "Determine the highest observable order m_max.",
         "m_max =", "(integer)"),
        ("4",  "Calculate the angular separation Δθ = θ₂ − θ₁.",
         "Δθ  =", "°"),
    ]

    prob.set(19, 0, "#")
    prob.set(19, 1, "Task description")
    prob.set(19, 6, "Your answer")
    prob.set(19, 8, "Units")
    for c in [0, 1, 6, 8]:
        prob.fmt(19, c, bold=True, bg=PALETTE["header"],
                 font_color=PALETTE["header_text"], align="center")
    prob.merge(19, 1, 1, 5)
    prob.merge(19, 6, 1, 2)

    for i, (num, desc, _lbl, units) in enumerate(tasks):
        r = 20 + i
        prob.set(r, 0, num)
        prob.set(r, 1, desc)
        prob.set(r, 6, "")      # blank — student fills in
        prob.set(r, 8, units)
        band = PALETTE["band_alt"] if i % 2 else None
        prob.fmt(r, 0, align="center", bold=True,
                 bg=band or PALETTE["band"])
        prob.fmt(r, 1, align="left", bg=band)
        prob.merge(r, 1, 1, 5)
        prob.fmt(r, 6, bg="#ffffff", align="center")
        prob.merge(r, 6, 1, 2)
        prob.fmt(r, 8, align="left", italic=True, font_color="#555555")

    prob.col_width(6, 120)
    prob.col_width(8, 90)
    prob.box(19, 0, 25, 8, color=PALETTE["header"], width=1.2, inner=True)

    prob.note(19, 6,
              "Leave these cells blank — work through the tasks by hand, "
              "then check with the Solution sheet.",
              kind="note")

    prob.set(27, 0, "Useful relation:  d sin θ = m λ   where  d = 1/(N×1000) m,  λ in metres")
    prob.fmt(27, 0, font_family="Courier New", italic=True)
    prob.merge(27, 0, 1, 9)

    # ================================================================
    # SHEET 2 — SOLUTION
    # ================================================================
    sol = wb.add_sheet("Solution")

    sol.title_block(
        "Diffraction Grating — Solution",
        "Year 2 Physics · Edit B5 (N lines/mm) or B6 (λ nm) — all cells update",
        span=8,
    )

    # ── Self-contained inputs ─────────────────────────────────────────
    # row 4 (0-based) → sheet row 5 → B5 = N (lines/mm)
    # row 5 (0-based) → sheet row 6 → B6 = λ (nm)
    sol.set(3, 0, "Inputs")
    sol.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    sol.set(4, 0, "Lines per mm  (N)")
    sol.set(4, 1, LINES_PER_MM)      # editable literal
    sol.set(4, 2, "lines/mm")

    sol.set(5, 0, "Wavelength  λ (nm)")
    sol.set(5, 1, LAMBDA_NM)         # editable literal
    sol.set(5, 2, "nm  (e.g. HeNe = 632.8, Na D = 589, Ar = 514)")

    for r in [4, 5]:
        sol.fmt(r, 0, align="left")
        sol.fmt(r, 1, bg=PALETTE["warn"], align="center",
                number_format="0.0")
        sol.fmt(r, 2, align="left", italic=True, font_color="#555555")

    sol.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.2)
    sol.col_width(0, 170)
    sol.col_width(1, 100)
    sol.col_width(2, 240)

    sol.note(4, 1,
             "Edit N (lines per mm) here — all angles and m_max recalculate.",
             kind="note")
    sol.note(5, 1,
             "Edit λ (nm) here — try 589 nm (Na D line) or 405 nm (violet laser).",
             kind="note")

    # ── Derived: grating spacing d shown in µm (avoids sub-millimeter) ──
    # d in µm = 1000 / N   [well above 3-decimal rounding threshold]
    # d in m  = d_um / 1000000  — kept for display only, no cell references it.
    # NOTE: no formula cell in the sheet depends on the d cell for arithmetic.
    # All derived formulas inline the unit conversion directly.
    sol.set(7, 0, "Grating spacing")
    sol.fmt(7, 0, bold=True, font_color=PALETTE["accent"])

    # d in µm — robust against 3-decimal display rounding (1000/600 = 1.667 µm)
    sol.set(8, 0, "d  (µm)")
    sol.formula(8, 1, "=1000/$B$5")     # B5 = N lines/mm → d in µm
    sol.set(8, 2, "µm  (= 1000/N — for reference only)")
    sol.fmt(8, 0, align="left")
    sol.fmt(8, 1, bg=PALETTE["good"], align="center", bold=True,
            number_format="0.0000")
    sol.fmt(8, 2, align="left", italic=True, font_color="#555555")
    sol.box(8, 0, 8, 1, color=PALETTE["header"], width=1.2)

    sol.note(8, 1,
             "d is shown in µm for readability. "
             "All angle formulas compute sin θ = m·λ(nm)·N / 1 000 000 "
             "to avoid tiny intermediate values that would round to zero.",
             kind="note")

    # ── Diffraction angle table ───────────────────────────────────────
    # Table starts at row 11 (0-based).
    #   header     → 0-based row 11  (sheet row 12)
    #   data rows  → 0-based rows 12–16  (sheet rows 13–17, orders 1–5)
    #
    # KEY: all formulas bypass d_cell and compute inline:
    #   sin θ = m * λ_nm * N / 1_000_000
    #           (= m * λ(m) * N(m⁻¹) = m * (B6/1e9) * (B5*1000)
    #            = m * B5 * B6 / 1_000_000  — no sci-notation literals needed)
    #
    # θ (deg) = IF(sin>1, "--", DEGREES(ASIN(MIN(sin,1))))
    #           IF evaluates both branches, so MIN clamps before ASIN.

    TABLE_START = 11      # 0-based row of the table header
    # First data sheet-row (1-based) = TABLE_START + 2 = 13
    first_data_1b = TABLE_START + 2

    headers = ["Order  m", "sin θ = m λ N / 10⁶", "θ  (degrees)", "Observable?"]
    table_rows = []
    for k, m in enumerate(ORDERS):
        rr = first_data_1b + k    # 1-based sheet row: 13, 14, 15, 16, 17
        # sin θ column (col B = col index 1)
        sin_formula   = f"={m}*$B$5*$B$6/1000000"
        # theta col — clamp with MIN(B<rr>,1) so ASIN never blows up
        theta_formula = f"=IF(B{rr}>1,\"--\",DEGREES(ASIN(MIN(B{rr},1))))"
        obs_formula   = f"=IF(B{rr}>1,\"No\",\"Yes\")"
        table_rows.append([m, sin_formula, theta_formula, obs_formula])

    sol.table(
        TABLE_START, 0,
        headers=headers,
        rows=table_rows,
        number_format="0.0000",
        banded=True,
        align_data="right",
    )

    sol.col_width(0, 90)
    sol.col_width(1, 190)
    sol.col_width(2, 130)
    sol.col_width(3, 110)

    # Designate columns for chart binding
    sol.designate(0, "X")   # order m
    sol.designate(2, "Y")   # theta_deg

    # ── Summary panel ─────────────────────────────────────────────────
    # m_max = INT(d/lambda) = INT(1/(N*1000) / (lambda_nm/1e9))
    #       = INT(1e9 / (N*1000*lambda_nm))
    #       = INT(1000000 / (N * lambda_nm))
    #       — all values in the thousands, safe from rounding.
    #
    # Angular separation: θ₂ − θ₁ = C<row_m2> - C<row_m1>
    #   (if θ₂ is "--" string, IFERROR returns "--")

    # Summary block starts 2 rows below last data row
    SUM_ROW = TABLE_START + 1 + len(ORDERS) + 2   # = 11+1+5+2 = 19 (0-based)

    sol.set(SUM_ROW - 1, 0, "Summary")
    sol.fmt(SUM_ROW - 1, 0, bold=True, font_color=PALETTE["header"])

    # theta column is C (col index 2); row m=1 → 1-based row first_data_1b
    # row m=2 → first_data_1b + 1
    c_m1 = f"C{first_data_1b}"          # θ₁  (1-based)
    c_m2 = f"C{first_data_1b + 1}"      # θ₂

    # d in m for the display label: 1/(N*1000) — but this tiny value
    # (1.67e-6) would round to 0 if stored in a cell. Use the µm cell
    # multiplied back: 1000/B5 µm × 1e-6 = not helpful.
    # Instead just show the µm value with a label.
    d_um_formula = "=1000/$B$5"    # safe: result ≈ 1.667

    summ_items = [
        ("Grating spacing  d  (µm)",
         d_um_formula,
         PALETTE["good"],
         "0.0000"),
        ("Highest observable order  m_max",
         "=INT(1000000/($B$5*$B$6))",
         PALETTE["band"],
         "0"),
        ("θ  for m = 1  (°)",
         f"={c_m1}",
         PALETTE["band_alt"],
         "0.0000"),
        ("θ  for m = 2  (°)",
         f"={c_m2}",
         PALETTE["band_alt"],
         "0.0000"),
        ("Angular separation  Δθ = θ₂ − θ₁  (°)",
         f"=IFERROR({c_m2}-{c_m1},\"--\")",
         PALETTE["warn"],
         "0.0000"),
    ]

    for i, (lbl, expr, bg, nfmt) in enumerate(summ_items):
        r = SUM_ROW + i
        sol.set(r, 0, lbl)
        sol.formula(r, 1, expr)
        sol.fmt(r, 0, align="left")
        sol.fmt(r, 1, bg=bg, align="center", bold=True,
                number_format=nfmt)

    sol.box(SUM_ROW, 0, SUM_ROW + len(summ_items) - 1, 1,
            color=PALETTE["header"], width=1.2)

    sol.note(SUM_ROW + 1, 1,
             "m_max = INT(1 000 000 / (N · λ_nm)):  the largest order m "
             "for which m·λ ≤ d, i.e. sin θ ≤ 1.  Beyond this no real "
             "diffraction angle exists.",
             kind="note")

    # ── Chart: diffraction angle vs order ─────────────────────────────
    # Pre-compute matching arrays for initial render.
    lam_m = LAMBDA_NM * 1e-9
    x_orders = np.array(ORDERS, dtype=float)
    y_theta = np.array([
        (_theta_deg(m, D_M, lam_m) if not math.isnan(_theta_deg(m, D_M, lam_m)) else 0.0)
        for m in ORDERS
    ], dtype=float)

    # 0-based row bounds of the data section in the table
    r0 = TABLE_START + 1              # first data row (0-based) = 12
    r1 = TABLE_START + len(ORDERS)    # last  data row (0-based) = 16

    sol.chart(
        [Series(
            x=x_orders,
            y=y_theta,
            label="θ  (°)",
            plot_type="Bar",
            color=PALETTE["header"],
            x_col=0,   # order m column
            y_col=2,   # theta_deg column
            row_start=r0,
            row_end=r1,
        )],
        at=(460, 30),
        size=(440, 290),
        title="Diffraction Angle vs Order",
        xlabel="Diffraction order  m",
        ylabel="θ  (degrees)",
        grid=True,
        legend=False,
    )

    # ── Grating equation (mathtext) ───────────────────────────────────
    sol.equation(
        r"d \sin\theta = m\lambda",
        at=(460, 340),
        fontsize=22,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(250, 54),
    )

    sol.note(10, 4,
             "Orders shown as '--' or 'No' have sin θ > 1 (evanescent). "
             "Reducing λ or increasing N (denser grating) shifts m_max up.",
             kind="note")

    # ── Save ──────────────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "exercises", "Year 2",
    )
    out = os.path.join(out_dir, "Diffraction Grating.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
