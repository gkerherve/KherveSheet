"""Build the "Arrhenius Activation Energy" exercise .ksheet.

A Year-4 MSci physical-chemistry exercise:
  Sheet 1 "Problem"  — problem statement, editable data, task list.
  Sheet 2 "Solution" — full worked solution with least-squares fit,
                       live chart, and LaTeX equations.

Run:  python examples/build_arrhenius_exercise.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Make the project importable from any working directory.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402

# ── Physical constants & synthetic data ─────────────────────────────
R_GAS = 8.314          # J mol⁻¹ K⁻¹
# Seven T / k data points constructed from Ea ≈ 75 kJ/mol, A ≈ 1e13 s⁻¹
# with mild multiplicative scatter to simulate real measurements.
T_VALS = [300, 320, 340, 360, 380, 400, 420]   # K (fixed grid, literals)
K_VALS = [0.855, 5.887, 29.11, 133.7, 485.1, 1670.0, 4511.0]  # s⁻¹
N_PTS = len(T_VALS)

# Pre-compute numpy arrays for chart initial render (must match formulas).
_inv_T = np.array([1.0 / t for t in T_VALS])   # 1/T
_ln_k  = np.array([np.log(k) for k in K_VALS])  # ln k

# Least-squares slope/intercept for fit-line series render data.
_Sx  = np.sum(_inv_T)
_Sy  = np.sum(_ln_k)
_Sxx = np.sum(_inv_T ** 2)
_Sxy = np.sum(_inv_T * _ln_k)
_slope     = (N_PTS * _Sxy - _Sx * _Sy) / (N_PTS * _Sxx - _Sx ** 2)
_intercept = (_Sy - _slope * _Sx) / N_PTS
_fit_ln_k  = _slope * _inv_T + _intercept


# ═════════════════════════════════════════════════════════════════════
#  Sheet 1 — Problem
# ═════════════════════════════════════════════════════════════════════

def _build_problem(wb: Workbook) -> None:
    s = wb.add_sheet("Problem")

    # ── Title block ──────────────────────────────────────────────────
    s.title_block(
        "Arrhenius Activation Energy",
        "Year 4 MSci Physical Chemistry — Data Analysis Exercise",
        span=8,
    )

    # ── Problem statement (rows 3–5) ─────────────────────────────────
    stmt = (
        "You have measured the first-order rate constant k (s⁻¹) of a "
        "gas-phase reaction at seven temperatures T (K).  Your tasks are to "
        "determine the activation energy Eₐ (kJ/mol) and the pre-exponential "
        "factor A (s⁻¹) by constructing an Arrhenius plot of ln k vs 1/T "
        "and performing a weighted least-squares fit."
    )
    s.set(3, 0, stmt)
    s.fmt(3, 0, italic=True, wrap=True, font_color="#444444")
    s.merge(3, 0, 2, 8)

    # ── Gas constant (row 6) ─────────────────────────────────────────
    s.set(6, 0, "Gas constant R")
    s.set(6, 1, R_GAS)
    s.set(6, 2, "J mol⁻¹ K⁻¹")
    s.fmt(6, 0, bold=True)
    s.fmt(6, 1, bold=True, bg=PALETTE["band"], align="center",
          number_format="0.000")
    s.fmt(6, 2, italic=True, font_color="#555555")
    s.note(6, 1,
           "R = 8.314 J mol⁻¹ K⁻¹ — do not edit.",
           kind="note")

    # ── Data table (rows 8–16) ───────────────────────────────────────
    # Table header at 0-based row 8 (sheet row 9, 1-based).
    # Data rows at 0-based rows 9..15 (sheet rows 10..16, 1-based).
    s.set(7, 0, "Measured Data")
    s.fmt(7, 0, bold=True, font_color=PALETTE["header"])

    DATA_TABLE_ROW = 8   # 0-based row for the header line
    headers_p = ["T (K)", "k (s⁻¹)"]
    s.col_width(0, 90)
    s.col_width(1, 110)
    s.col_width(2, 160)
    s.col_width(3, 180)
    s.col_width(4, 160)
    s.col_width(5, 160)

    # Header row.
    for j, h in enumerate(headers_p):
        s.set(DATA_TABLE_ROW, j, h)
        s.fmt(DATA_TABLE_ROW, j, bold=True, bg=PALETTE["header"],
              font_color="#ffffff", align="center")

    # Data rows — T is a fixed literal; k is editable amber.
    for i, (t_val, k_val) in enumerate(zip(T_VALS, K_VALS)):
        r = DATA_TABLE_ROW + 1 + i   # 0-based row index
        band = PALETTE["band_alt"] if (i % 2) else None
        s.set(r, 0, t_val)
        s.fmt(r, 0, align="center",
              **({"bg": band} if band else {}))
        s.set(r, 1, k_val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center",
              number_format="0.000")

    s.box(DATA_TABLE_ROW, 0,
          DATA_TABLE_ROW + N_PTS, 1,
          color=PALETTE["header"], width=1.0)
    s.note(DATA_TABLE_ROW + 1, 1,
           "Amber cells are the measured rate constants — "
           "you may adjust them to explore how the fit changes.",
           kind="note")

    # ── Tasks (rows 18–25) ───────────────────────────────────────────
    TASK_ROW = DATA_TABLE_ROW + N_PTS + 2   # gap after table
    s.set(TASK_ROW, 0, "Tasks")
    s.fmt(TASK_ROW, 0, bold=True, font_size=12,
          font_color=PALETTE["accent"])

    tasks = [
        ("1.", "Add two columns next to the data: compute 1/T (K⁻¹) "
               "and ln k for each row."),
        ("2.", "Plot ln k (y-axis) vs 1/T (x-axis) and verify "
               "linearity (the Arrhenius plot)."),
        ("3.", "Fit a straight line by least squares.  "
               "The slope m and intercept c satisfy: m = −Eₐ/R, "
               "c = ln A."),
        ("4.", "Extract Eₐ = −m×R (convert to kJ/mol) "
               "and A = eᶜ."),
        ("5.", "Calculate R² to assess the quality of the linear fit."),
    ]
    for i, (num, text) in enumerate(tasks):
        r = TASK_ROW + 1 + i
        s.set(r, 0, num)
        s.fmt(r, 0, bold=True, align="center",
              font_color=PALETTE["accent"])
        s.set(r, 1, text)
        s.fmt(r, 1, wrap=True)
        s.merge(r, 1, 1, 6)

    # ── Your Answers panel (rows 27–33) ──────────────────────────────
    ANS_ROW = TASK_ROW + len(tasks) + 2
    s.set(ANS_ROW, 0, "Your Answers")
    s.fmt(ANS_ROW, 0, bold=True, font_size=12,
          font_color=PALETTE["header"])

    answers = [
        ("Slope m", "K"),
        ("Intercept c", "(dimensionless)"),
        ("Eₐ", "kJ/mol"),
        ("A", "s⁻¹"),
        ("R²", "(dimensionless)"),
    ]
    for i, (lbl, unit) in enumerate(answers):
        r = ANS_ROW + 1 + i
        s.set(r, 0, lbl)
        s.fmt(r, 0, align="right")
        # Blank answer cell.
        s.set(r, 1, "")
        s.fmt(r, 1, bg="#f5f5f5", align="center")
        s.set(r, 2, unit)
        s.fmt(r, 2, italic=True, font_color="#777777")

    s.box(ANS_ROW + 1, 0,
          ANS_ROW + len(answers), 2,
          color=PALETTE["header"], width=1.0)
    s.note(ANS_ROW, 0,
           "Fill in your answers after completing the tasks. "
           "See Sheet 2 for the full worked solution.",
           kind="note")


# ═════════════════════════════════════════════════════════════════════
#  Sheet 2 — Solution
# ═════════════════════════════════════════════════════════════════════

def _build_solution(wb: Workbook) -> None:  # noqa: C901
    s = wb.add_sheet("Solution")

    # ── Title block ──────────────────────────────────────────────────
    s.title_block(
        "Arrhenius Activation Energy — Solution",
        "Least-squares linear fit to ln k vs 1/T",
        span=8,
    )

    # ── Constants (row 3) ────────────────────────────────────────────
    # R at 0-based (3, 1) → 1-based B4.
    s.set(3, 0, "Gas constant R (J/mol/K)")
    s.fmt(3, 0, bold=True)
    s.set(3, 1, R_GAS)
    s.fmt(3, 1, bold=True, bg=PALETTE["band"], align="center",
          number_format="0.000")
    # Absolute reference: $B$4.
    s.note(3, 1, "R = 8.314 J mol⁻¹ K⁻¹", kind="note")
    s.col_width(0, 220)
    s.col_width(1, 110)
    s.col_width(2, 110)
    s.col_width(3, 110)
    s.col_width(4, 110)

    # ── Data + computed columns (rows 5–13) ──────────────────────────
    # Table header at 0-based row 5 → sheet row 6.
    # Data rows at 0-based rows 6..12 → sheet rows 7..13 (1-based).
    DATA_START = 5   # 0-based header row

    s.set(4, 0, "Measured Data and Computed Columns")
    s.fmt(4, 0, bold=True, font_color=PALETTE["header"])
    s.merge(4, 0, 1, 4)

    headers_sol = [
        "T (K)",
        "k (s⁻¹)",
        "1/T (K⁻¹)",
        "ln k",
        "Fit: ln k",
    ]
    for j, h in enumerate(headers_sol):
        s.set(DATA_START, j, h)
        s.fmt(DATA_START, j, bold=True, bg=PALETTE["header"],
              font_color="#ffffff", align="center")

    # Data rows.
    # Sheet row of first data row = DATA_START + 2  (1-based).
    first_sheet_row = DATA_START + 2   # = 7  (1-based)
    last_sheet_row  = first_sheet_row + N_PTS - 1  # = 13 (1-based)

    for i, (t_val, k_val) in enumerate(zip(T_VALS, K_VALS)):
        r = DATA_START + 1 + i     # 0-based row index: 6..12
        sr = r + 1                  # 1-based sheet row:  7..13
        band = PALETTE["band_alt"] if (i % 2) else None
        bkw = {"bg": band} if band else {}

        # Col 0 — T (literal, fixed independent variable).
        s.set(r, 0, t_val)
        s.fmt(r, 0, align="center", **bkw)

        # Col 1 — k (literal, editable amber — the input data).
        s.set(r, 1, k_val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center",
              number_format="0.000")

        # Col 2 — 1/T = 1/A<sr>  (formula).
        s.formula(r, 2, f"=1/A{sr}")
        s.fmt(r, 2, align="right", number_format="0.000000", **bkw)

        # Col 3 — ln k = LN(B<sr>)  (formula).
        s.formula(r, 3, f"=LN(B{sr})")
        s.fmt(r, 3, align="right", number_format="0.0000", **bkw)

        # Col 4 — fit: use A{sr} directly to avoid 1/T precision loss.
        # (slope at $B$24 = 0-based row 23, col 1; intercept at $B$25).
        s.formula(r, 4, f"=$B$24/A{sr}+$B$25")
        s.fmt(r, 4, align="right", number_format="0.0000", **bkw)

        # (Cols 5–6 removed; sums are built as 7-term direct expressions.)

    s.box(DATA_START, 0,
          DATA_START + N_PTS, 4,
          color=PALETTE["header"], width=1.0)

    # Designate columns for chart axis hints.
    s.designate(2, "X")   # 1/T
    s.designate(3, "Y")   # ln k (measured)
    s.designate(4, "Y")   # fit

    # ── Helper sums block (rows 15–21) ───────────────────────────────
    # 0-based row 15 → sheet row 16.
    SUM_ROW = DATA_START + N_PTS + 3   # = 5 + 7 + 3 = 15

    s.set(SUM_ROW, 0, "Helper Sums (Least-Squares Normal Equations)")
    s.fmt(SUM_ROW, 0, bold=True, font_color=PALETTE["accent"])
    s.merge(SUM_ROW, 0, 1, 4)

    # Row indices for the sum cells (0-based → sheet row = 0-based + 1).
    # SUM_ROW+1..SUM_ROW+5 → 0-based 16..20 → sheet rows 17..21.
    #
    # IMPORTANT: all five sums are expressed as explicit 7-term formulas
    # referencing T (col A) and k (col B) DIRECTLY — never through the
    # intermediate display columns C/D, whose stored strings are rounded
    # to 3–4 decimal places and would lose precision in the sums.
    A_refs = [f"A{sr}" for sr in range(first_sheet_row, last_sheet_row + 1)]
    B_refs = [f"B{sr}" for sr in range(first_sheet_row, last_sheet_row + 1)]
    f_sx  = "=" + "+".join(f"1/{ar}" for ar in A_refs)
    f_sy  = "=" + "+".join(f"LN({br})" for br in B_refs)
    f_sxx = "=" + "+".join(f"(1/{ar})^2" for ar in A_refs)
    f_sxy = "=" + "+".join(f"LN({br})/{ar}"
                           for ar, br in zip(A_refs, B_refs))
    sums = [
        ("n (number of points)", str(N_PTS)),
        ("Σ (1/T)  [xᵢ sum]",         f_sx),
        ("Σ (ln k) [yᵢ sum]",          f_sy),
        ("Σ (1/T)² [xᵢ² sum]",        f_sxx),
        ("Σ (1/T × ln k) [xᵢ yᵢ sum]", f_sxy),
    ]
    # Cell addresses for the sum values (1-based): B17..B21.
    sum_b_rows = [SUM_ROW + 1 + k for k in range(len(sums))]
    # 0-based: 16,17,18,19,20 → sheet rows: 17,18,19,20,21.
    b_n   = sum_b_rows[0] + 1   # sheet row for n          = 17
    b_sx  = sum_b_rows[1] + 1   # sheet row for Σ(1/T)     = 18
    b_sy  = sum_b_rows[2] + 1   # sheet row for Σ(ln k)    = 19
    b_sxx = sum_b_rows[3] + 1   # sheet row for Σ(1/T)²    = 20
    b_sxy = sum_b_rows[4] + 1   # sheet row for Σ(1/T·lnk) = 21

    for k, (lbl, val) in enumerate(sums):
        r = SUM_ROW + 1 + k
        s.set(r, 0, lbl)
        s.fmt(r, 0, align="right", italic=True)
        if val.startswith("="):
            s.formula(r, 1, val)
        else:
            s.set(r, 1, val)
        s.fmt(r, 1, align="center", bg=PALETTE["band"],
              number_format="0.000000")

    s.box(SUM_ROW + 1, 0, SUM_ROW + len(sums), 1,
          color=PALETTE["accent"], width=1.0)
    s.note(SUM_ROW, 0,
           "These five cells accumulate the sums needed for the "
           "normal equations of least-squares.  Edit k values above "
           "and every quantity below updates automatically.",
           kind="note")

    # ── Fit results (rows 23–28) ─────────────────────────────────────
    # Slope at 0-based row 23, col 1 → sheet cell B24.
    # Intercept at 0-based row 24, col 1 → sheet cell B25.
    # These are referenced as $B$24 / $B$25 by the fit column above.
    RES_ROW = SUM_ROW + len(sums) + 2   # = 15 + 5 + 2 = 22

    s.set(RES_ROW, 0, "Fit Results")
    s.fmt(RES_ROW, 0, bold=True, font_color=PALETTE["header"])
    s.merge(RES_ROW, 0, 1, 4)

    # Build the results in 0-based rows RES_ROW+1 .. RES_ROW+6.
    # We need slope at 0-based (RES_ROW+1, 1) → sheet row RES_ROW+2.
    res_slope_0row = RES_ROW + 1   # 0-based
    res_icp_0row   = RES_ROW + 2
    res_ea_j_0row  = RES_ROW + 3
    res_ea_kj_0row = RES_ROW + 4
    res_A_0row     = RES_ROW + 5
    res_r2_0row    = RES_ROW + 6

    # 1-based sheet row references:
    sr_slope = res_slope_0row + 1   # B<sr_slope> = slope cell
    sr_icp   = res_icp_0row   + 1   # B<sr_icp>   = intercept cell
    sr_ea_j  = res_ea_j_0row  + 1
    sr_ea_kj = res_ea_kj_0row + 1
    sr_A     = res_A_0row     + 1
    sr_r2    = res_r2_0row    + 1

    # Verify the 0-based → 1-based mapping matches the hard-coded $B$24/$B$25
    # references in the data-table formulas above.
    assert sr_slope == 24, (
        f"Slope cell must be B24 for fit-column refs to work, got B{sr_slope}. "
        "Adjust DATA_START or SUM_ROW."
    )
    assert sr_icp == 25, (
        f"Intercept cell must be B25, got B{sr_icp}."
    )

    # ── Inline formulas for slope and intercept ────────────────────
    # We compute slope and intercept as SINGLE eval expressions that
    # reference A7..A13 (T) and B7..B13 (k) directly.  This avoids the
    # 3-decimal-place truncation that would corrupt the intermediate sum
    # cells (e.g. Σ(1/T)² ≈ 6e-5 rounds to 0).
    # The display sum cells above are kept for pedagogical transparency
    # but are not used in the actual fit computation.
    n = N_PTS   # = 7

    sx_terms  = "+".join(f"1/{ar}" for ar in A_refs)           # Σ(1/T)
    sy_terms  = "+".join(f"LN({br})" for br in B_refs)         # Σ(ln k)
    sxx_terms = "+".join(f"(1/{ar})^2" for ar in A_refs)       # Σ(1/T)²
    sxy_terms = "+".join(f"LN({br})/{ar}"
                         for ar, br in zip(A_refs, B_refs))    # Σ(1/T·lnk)

    # slope = (n·Σxy − Σx·Σy) / (n·Σxx − Σx²)
    f_slope = (
        f"=({n}*({sxy_terms})-({sx_terms})*({sy_terms}))"
        f"/({n}*({sxx_terms})-({sx_terms})^2)"
    )
    # intercept = (Σy − slope·Σx) / n  — references stored slope cell
    # (slope is stored as ~-9019.3, one dp error is negligible for intercept)
    f_icp = (
        f"=(({sy_terms})-B{sr_slope}*({sx_terms}))/{n}"
    )
    # Ea (J/mol) = −slope × R
    f_ea_j  = f"=-B{sr_slope}*$B$4"
    # Ea (kJ/mol)
    f_ea_kj = f"=B{sr_ea_j}/1000"
    # A = exp(intercept)
    f_A = f"=EXP(B{sr_icp})"
    # R² = 1 − SS_res / SS_tot  (all inline, no stored-intermediate refs)
    #   SS_res = Σ(ln(kᵢ) − (slope/Tᵢ + intercept))²
    #   SS_tot = Σ(ln kᵢ)² − (Σ ln kᵢ)²/n
    # We reference $B$24 (slope) and $B$25 (intercept) which are stored
    # with sufficient precision (~1 dp for slope, 4 dp for intercept).
    ss_res_terms = "+".join(
        f"(LN({br})-($B${sr_slope}/{ar}+$B${sr_icp}))^2"
        for ar, br in zip(A_refs, B_refs)
    )
    sy2_terms = "+".join(f"LN({br})^2" for br in B_refs)
    f_r2 = (
        f"=1-({ss_res_terms})"
        f"/(({sy2_terms})-({sy_terms})^2/{n})"
    )

    results = [
        ("Slope  m  (K)",                 f_slope,  "0.0"),
        ("Intercept  c  (dimensionless)",  f_icp,    "0.0000"),
        ("Eₐ  (J/mol)",              f_ea_j,   "0.0"),
        ("Eₐ  (kJ/mol)",             f_ea_kj,  "0.000"),
        ("A  (s⁻¹)",            f_A,      "0.000E+00"),
        ("R²",                        f_r2,     "0.000000"),
    ]
    res_colors = [
        PALETTE["band"], PALETTE["band"],
        PALETTE["good"], PALETTE["good"],
        PALETTE["good"], PALETTE["band"],
    ]

    for k, ((lbl, expr, nfmt), col) in enumerate(
            zip(results, res_colors)):
        r = RES_ROW + 1 + k
        s.set(r, 0, lbl)
        s.fmt(r, 0, bold=True, align="right")
        s.formula(r, 1, expr)
        s.fmt(r, 1, bold=True, bg=col, align="center",
              number_format=nfmt)

    s.box(RES_ROW + 1, 0, RES_ROW + len(results), 1,
          color=PALETTE["header"], width=1.5, inner=False)

    s.note(res_ea_kj_0row, 1,
           "Ea (kJ/mol) — for a typical gas-phase bond-breaking "
           "reaction expect 40–200 kJ/mol.",
           kind="note")
    s.note(res_A_0row, 1,
           "A = exp(intercept) — collision-frequency factor; "
           "for unimolecular gas reactions typically 10¹²–10¹³ s⁻¹.",
           kind="note")

    # ── Chart: ln k vs 1/T with best-fit line ────────────────────────
    # Data series:  x = col 2 (1/T), y = col 3 (ln k)
    #               0-based rows DATA_START+1 .. DATA_START+N_PTS  = 6..12
    r0_chart = DATA_START + 1   # 0-based first data row = 6
    r1_chart = DATA_START + N_PTS  # 0-based last data row  = 12

    s.chart(
        [
            Series(
                x=_inv_T, y=_ln_k,
                label="ln k (measured)", plot_type="Scatter",
                color=PALETTE["header"], marker="o", markersize=7.0,
                markerfacecolor=PALETTE["header"],
                markeredgecolor="#ffffff",
                x_col=2, y_col=3, row_start=r0_chart, row_end=r1_chart,
            ),
            Series(
                x=_inv_T, y=_fit_ln_k,
                label="Best-fit line", plot_type="Line",
                color=PALETTE["accent"], linewidth=2.0,
                x_col=2, y_col=4, row_start=r0_chart, row_end=r1_chart,
            ),
        ],
        at=(540, 20), size=(460, 320),
        title="Arrhenius Plot: ln k vs 1/T",
        xlabel="1/T  (K⁻¹)", ylabel="ln k",
        grid=True, legend=True,
    )

    # ── Equations (mathtext) ─────────────────────────────────────────
    # Equation 1: k = A exp(−Ea/RT)
    s.equation(
        r"k = A \, e^{-E_a / RT}",
        at=(540, 360), fontsize=20,
        color="#222222", bg_color="#ffffff",
        border_color=PALETTE["header"], border_width=1.2,
        size=(240, 52),
    )
    # Equation 2: linearised form
    s.equation(
        r"\ln k = \ln A - \frac{E_a}{R} \cdot \frac{1}{T}",
        at=(540, 430), fontsize=20,
        color="#222222", bg_color="#ffffff",
        border_color=PALETTE["accent"], border_width=1.2,
        size=(310, 56),
    )

    # ── Instructional notes ──────────────────────────────────────────
    s.note(DATA_START + 1, 1,
           "Amber cells are the experimental k values — try changing "
           "one to see how slope, Ea, A, and R² all update.",
           kind="note")
    s.note(DATA_START, 4,
           "Fit column: slope × (1/T) + intercept, referencing "
           "T (col A) directly for full precision.  "
           "Slope = $B$24, intercept = $B$25.",
           kind="note")


# ═════════════════════════════════════════════════════════════════════
#  Main
# ═════════════════════════════════════════════════════════════════════

def build() -> str:
    wb = Workbook(min_rows=50, min_cols=10)
    _build_problem(wb)
    _build_solution(wb)

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "exercises", "Year 4",
        "Arrhenius Activation Energy.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    path = build()
    print("Wrote", path)
