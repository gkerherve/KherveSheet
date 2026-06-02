"""Build the "Blackbody Radiation" Year-3 undergraduate physics exercise.

Two sheets:
  - "Problem"  : problem statement, editable inputs, numbered tasks,
                 blank "Your answer" cells.
  - "Solution" : self-contained constants + formulas, Planck spectral
                 radiance table, live chart, mathtext equations.

Run:  python examples/build_blackbody_radiation.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Physical constants (used in Python for numpy chart arrays only) ──
H_PLANCK = 6.626e-34     # J·s
C_LIGHT   = 3.0e8        # m/s
K_BOLTZ   = 1.381e-23    # J/K
B_WIEN    = 2.898e-3     # m·K
T_SUN     = 5800.0       # K (example temperature)

# Wavelength grid: 100 nm to 2000 nm in steps of 50 nm (39 points)
LAMBDA_NM = np.arange(100, 2050, 50, dtype=float)   # nm


def planck_B(lam_nm: np.ndarray, T: float) -> np.ndarray:
    """Spectral radiance B(lambda, T) in W·sr⁻¹·m⁻³."""
    lam = lam_nm * 1e-9
    x   = H_PLANCK * C_LIGHT / (lam * K_BOLTZ * T)
    return (2.0 * H_PLANCK * C_LIGHT**2 / lam**5) / (np.exp(x) - 1.0)


# ── Sheet 1: Problem ─────────────────────────────────────────────────

def build_problem(wb: Workbook) -> None:
    s = wb.add_sheet("Problem")

    # --- Title block ---------------------------------------------------
    s.title_block(
        "Blackbody Radiation",
        "Year 3 Undergraduate Physics  ·  Planck's Law & Wien's Displacement",
        span=8,
    )

    # --- Problem statement ---------------------------------------------
    s.set(3, 0, "Background")
    s.fmt(3, 0, bold=True, font_size=12, font_color=PALETTE["header"])
    s.merge(3, 0, 1, 8)

    stmt_lines = [
        ("A blackbody is a perfect absorber and emitter of electromagnetic "
         "radiation.  Planck's law gives the spectral radiance as a function "
         "of wavelength λ and temperature T:"),
        ("      B(λ, T)  =  (2 h c² / λ⁵) / [exp(h c / λ k T) − 1]"),
        ("where  h = 6.626×10⁻³⁴ J·s  (Planck),  c = 3.00×10⁸ m/s  (speed of "
         "light),  k = 1.381×10⁻²³ J/K  (Boltzmann)."),
        ("Wien's displacement law gives the peak wavelength:"),
        ("      λ_max  =  b / T        (b = 2.898×10⁻³ m·K)"),
    ]
    for i, line in enumerate(stmt_lines):
        r = 4 + i
        s.set(r, 0, line)
        s.fmt(r, 0, wrap=True, font_size=10)
        s.merge(r, 0, 1, 8)
        s.col_width(0, 640)

    # --- Given: editable inputs ----------------------------------------
    s.set(10, 0, "Given  (editable — change these values)")
    s.fmt(10, 0, bold=True, font_color=PALETTE["accent"])
    s.merge(10, 0, 1, 4)

    given_rows = [
        ("Temperature  T  (K)", T_SUN, "Sun surface temperature"),
    ]
    for i, (lbl, val, tip) in enumerate(given_rows):
        r = 11 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center",
              number_format="0", bold=True)
        s.note(r, 1, tip + "\nEdit this cell and re-open to see the solution "
               "update.", kind="note")
    s.col_width(0, 240)
    s.col_width(1, 100)

    # Constants (read-only display)
    s.set(13, 0, "Constants  (for reference)")
    s.fmt(13, 0, bold=True, font_color=PALETTE["header"])
    const_rows = [
        ("Planck constant  h  (J·s)",   "6.626e-34"),
        ("Speed of light   c  (m/s)",   "3.0e8"),
        ("Boltzmann const  k  (J/K)",   "1.381e-23"),
        ("Wien constant    b  (m·K)",   "2.898e-3"),
    ]
    for i, (lbl, val) in enumerate(const_rows):
        r = 14 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left", italic=True, font_color="#555555")
        s.fmt(r, 1, align="center", italic=True, font_color="#555555")
    s.box(11, 0, 17, 1, color=PALETTE["accent"], width=1.2)

    # --- Tasks ---------------------------------------------------------
    s.set(20, 0, "Tasks")
    s.fmt(20, 0, bold=True, font_size=12, font_color=PALETTE["header"])
    s.merge(20, 0, 1, 8)

    tasks = [
        ("1.", "Calculate the peak wavelength  λ_max  using Wien's displacement "
               "law.  Express your answer in nanometres."),
        ("2.", "Sketch (or compute) the spectral radiance  B(λ, T)  over the "
               "visible range 400–700 nm and the near-infrared up to 2000 nm.  "
               "Label the axes with correct SI units."),
        ("3.", "Identify the colour / spectral region of the peak.  Is this "
               "consistent with the Sun appearing yellow-white to the human eye?"),
        ("4.", "How does  λ_max  change if the temperature is doubled?  "
               "What does this imply for the colour of hotter stars?"),
        ("5.", "The Stefan–Boltzmann law states that the total power radiated "
               "is  P ∝ T⁴.  If the temperature increases by 10 %, by approximately "
               "how much does the total radiated power increase?"),
    ]
    for i, (num, text) in enumerate(tasks):
        r = 21 + i * 2
        s.set(r, 0, num)
        s.set(r, 1, text)
        s.fmt(r, 0, bold=True, font_color=PALETTE["accent"], align="center")
        s.fmt(r, 1, wrap=True, font_size=10)
        s.merge(r, 1, 1, 7)

    # --- Your answer cells ---------------------------------------------
    ans_start = 32
    s.set(ans_start, 0, "Your answers")
    s.fmt(ans_start, 0, bold=True, font_size=11,
          font_color=PALETTE["header"])
    s.merge(ans_start, 0, 1, 8)

    ans_rows = [
        ("Task 1: λ_max  =", "", "nm"),
        ("Task 3: Spectral region  =", "", ""),
        ("Task 4: λ_max doubles / halves / …?", "", ""),
        ("Task 5: Power increase ≈", "", "%"),
    ]
    for i, (lbl, blank, unit) in enumerate(ans_rows):
        r = ans_start + 1 + i
        s.set(r, 0, lbl)
        s.set(r, 1, blank)   # intentionally empty — student fills in
        s.set(r, 2, unit)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg="#ffffff", align="center",
              number_format="0.00")
        s.fmt(r, 2, italic=True, font_color="#555555")
    s.box(ans_start + 1, 0, ans_start + len(ans_rows), 2,
          color=PALETTE["header"], width=1.0)

    s.note(ans_start + 1, 1,
           "Leave these cells blank — this is your answer space.\n"
           "Open the 'Solution' sheet to check your work.", kind="note")
    s.note(20, 0,
           "This is a Year-3 undergraduate physics exercise.\n"
           "Attempt all tasks before looking at the Solution sheet.",
           kind="note")


# ── Sheet 2: Solution ────────────────────────────────────────────────

def build_solution(wb: Workbook) -> None:
    s = wb.add_sheet("Solution")

    # --- Title block ---------------------------------------------------
    s.title_block(
        "Solution: Blackbody Radiation",
        "Planck's Law  ·  Wien's Displacement  ·  Stefan–Boltzmann",
        span=9,
    )

    # --- Self-contained inputs ----------------------------------------
    # T lives at (row=4, col=1) → sheet cell B5
    # h  at (row=5, col=1) → B6
    # c  at (row=6, col=1) → B7
    # k  at (row=7, col=1) → B8
    # b  at (row=8, col=1) → B9

    s.set(3, 0, "Inputs & Constants")
    s.fmt(3, 0, bold=True, font_size=11, font_color=PALETTE["header"])
    s.merge(3, 0, 1, 4)

    param_rows = [
        (4, "Temperature  T  (K)",              T_SUN,       "0"),
        (5, "Planck constant  h  (J·s)",         6.626e-34,   "0.00E+00"),
        (6, "Speed of light   c  (m/s)",          3.0e8,       "0.00E+00"),
        (7, "Boltzmann const  k  (J/K)",          1.381e-23,   "0.00E+00"),
        (8, "Wien constant    b  (m·K)",           2.898e-3,    "0.000000"),
    ]
    for row, lbl, val, nfmt in param_rows:
        s.set(row, 0, lbl)
        s.set(row, 1, val)          # literal cell value — sci-notation OK here
        s.fmt(row, 0, align="left")
        s.fmt(row, 1, bg=PALETTE["warn"], align="center",
              number_format=nfmt, bold=(row == 4))
    s.box(4, 0, 8, 1, color=PALETTE["accent"], width=1.2)
    s.col_width(0, 260)
    s.col_width(1, 110)

    s.note(4, 1,
           "Edit T here (e.g. 3000 for a cool red star, 10000 for a "
           "hot blue star).\nThe Planck table and chart update automatically.",
           kind="note")

    # --- Wien's law ---------------------------------------------------
    # lambda_max (m)  = b / T   →  $B$9 / $B$5
    # lambda_max (nm) = (b / T) / 0.000000001  (i.e. ÷ 1 nm in metres)
    #
    # Cell positions (0-based row, col):
    #   (10, 0): label "λ_max (m)"      (10, 1): formula → sheet B11
    #   (11, 0): label "λ_max (nm)"     (11, 1): formula → sheet B12

    s.set(10, 0, "Wien's law  —  Peak wavelength")
    s.fmt(10, 0, bold=True, font_color=PALETTE["header"])
    s.merge(10, 0, 1, 3)

    s.set(11, 0, "λ_max  (metres)")
    s.formula(11, 1, "=$B$9/$B$5")
    s.fmt(11, 0, align="left")
    s.fmt(11, 1, bg=PALETTE["good"], align="center",
          number_format="0.00E+00", bold=True)

    s.set(12, 0, "λ_max  (nanometres)")
    # ÷ 0.000000001 converts m → nm
    s.formula(12, 1, "=($B$9/$B$5)/0.000000001")
    s.fmt(12, 0, align="left")
    s.fmt(12, 1, bg=PALETTE["good"], align="center",
          number_format="0.0", bold=True)

    s.box(11, 0, 12, 1, color=PALETTE["header"], width=1.0)

    s.note(12, 1,
           "At T = 5800 K (Sun) this evaluates to ~500 nm — green/cyan, "
           "consistent with the broad solar spectrum appearing white-yellow.",
           kind="note")

    # --- Planck spectral radiance table --------------------------------
    # Table starts at row 15 (0-based).
    # Header at sheet row 16 (1-based).  First data row at sheet row 17.
    # 0-based indices: header row = 15, first data row = 16.
    #
    # Columns:
    #   col 0: λ (nm)  — literal fixed grid
    #   col 1: B(λ,T)  — live formula
    #
    # Formula for row with sheet-row rr (1-based):
    #   =(2*$B$6*$B$7*$B$7/POWER(A{rr}*0.000000001,5)) /
    #     (EXP($B$6*$B$7/((A{rr}*0.000000001)*$B$8*$B$5))-1)
    #
    # Guard overflow: use IFERROR(..., 0)

    table_start = 15    # 0-based row of header
    n = len(LAMBDA_NM)  # 39 points

    s.set(14, 0, "Planck Spectral Radiance  B(λ, T)")
    s.fmt(14, 0, bold=True, font_size=11, font_color=PALETTE["header"])
    s.merge(14, 0, 1, 4)

    data_rows = []
    for k, lnm in enumerate(LAMBDA_NM):
        # 0-based row of this data row = table_start + 1 + k = 16 + k
        rr = table_start + 2 + k   # 1-based sheet row
        formula_str = (
            f"=IFERROR((2*$B$6*$B$7*$B$7/"
            f"POWER(A{rr}*0.000000001,5))/"
            f"(EXP($B$6*$B$7/((A{rr}*0.000000001)*$B$8*$B$5))-1),0)"
        )
        data_rows.append([int(lnm), formula_str])

    s.table(
        table_start, 0,
        headers=["λ (nm)", "B(λ,T)  (W·sr⁻¹·m⁻³)"],
        rows=data_rows,
        number_format="0.00E+00",
        banded=True,
    )
    s.col_width(0, 90)
    s.col_width(1, 160)

    # Designate columns for axis binding
    s.designate(0, "X")
    s.designate(1, "Y")

    # --- Chart: blackbody curve (live-bound) --------------------------
    # Data rows occupy 0-based rows table_start+1 .. table_start+n (i.e. 16..54)
    r0 = table_start + 1
    r1 = table_start + n    # inclusive

    lam_nm_arr = LAMBDA_NM
    B_arr      = planck_B(lam_nm_arr, T_SUN)

    s.chart(
        [Series(
            lam_nm_arr, B_arr,
            label="B(λ, T)",
            plot_type="Line",
            color="#c0392b",
            linewidth=2.5,
            x_col=0,
            y_col=1,
            row_start=r0,
            row_end=r1,
        )],
        at=(400, 40), size=(460, 320),
        title=f"Blackbody Spectrum  (T = {int(T_SUN)} K)",
        xlabel="Wavelength  λ  (nm)",
        ylabel="Spectral Radiance  B  (W·sr⁻¹·m⁻³)",
        grid=True, legend=True,
    )

    # --- Summary panel ------------------------------------------------
    # Placed to the right of the table (col 3..5)
    s.set(14, 3, "Summary")
    s.fmt(14, 3, bold=True, font_color=PALETTE["header"])
    s.merge(14, 3, 1, 2)

    first_data = table_start + 2          # 1-based row of first data cell
    last_data  = table_start + 1 + n      # 1-based row of last data cell

    summ = [
        ("λ_max  (nm)",
         "=($B$9/$B$5)/0.000000001",
         PALETTE["good"]),
        ("B_max  (W·sr⁻¹·m⁻³)",
         f"=MAX(B{first_data}:B{last_data})",
         PALETTE["band"]),
        ("Visible peak?",
         f"=IF(($B$9/$B$5)/0.000000001>400,"
         f"IF(($B$9/$B$5)/0.000000001<700,\"Yes\",\"IR\"),\"UV\")",
         PALETTE["band_alt"]),
    ]
    for i, (lbl, expr, bg) in enumerate(summ):
        r = 15 + i
        s.set(r, 3, lbl)
        s.formula(r, 4, expr)
        s.fmt(r, 3, align="left")
        s.fmt(r, 4, bg=bg, align="center",
              number_format="0.0", bold=True)
    s.box(15, 3, 17, 4, color=PALETTE["header"], width=1.0)
    s.col_width(3, 170)
    s.col_width(4, 120)

    # --- Equations (mathtext) -----------------------------------------
    # Planck's law
    s.equation(
        r"B(\lambda,T)=\frac{2hc^{2}}{\lambda^{5}}"
        r"\frac{1}{e^{hc/\lambda k T}-1}",
        at=(400, 380), fontsize=18,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(370, 58),
    )

    # Wien's displacement law
    s.equation(
        r"\lambda_{\mathrm{max}} = \frac{b}{T},"
        r"\quad b = 2.898\times10^{-3}\ \mathrm{m\cdot K}",
        at=(400, 460), fontsize=16,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.2,
        size=(400, 48),
    )

    # --- Notes --------------------------------------------------------
    s.note(10, 0,
           "The peak shifts to shorter (bluer) wavelengths as T increases "
           "(Wien's law: λ_max ∝ 1/T).\n"
           "Doubling T halves λ_max.",
           kind="note")

    s.note(14, 0,
           "Formula in column B: Planck spectral radiance.\n"
           "Edit T in B5 — every row recalculates.\n"
           "nm → m conversion uses the factor 0.000000001 (avoids E-notation "
           "inside formula strings).",
           kind="note")

    s.note(14, 3,
           "Stefan–Boltzmann law: total power P ∝ T⁴.\n"
           "A 10 % rise in T gives a ~46 % rise in P  (1.1⁴ ≈ 1.464).",
           kind="note")


# ── Main ─────────────────────────────────────────────────────────────

def build() -> str:
    wb = Workbook(min_rows=60, min_cols=12)
    build_problem(wb)
    build_solution(wb)

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "exercises", "Year 3", "Blackbody Radiation.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    path = build()
    print("Wrote", path)
