"""Build the "Electrochemistry CV-DPV" analysis template .ksheet file.

A polished cyclic voltammetry (CV) analysis workbook demonstrating:
  1. A realistic "duck-shaped" CV: anodic + cathodic peaks on a capacitive
     baseline, synthesised from editable peak-parameter cells.
  2. Analysis block: Ipa (anodic peak current), Ipc (cathodic peak current),
     peak separation ΔEp = Epa − Epc, half-wave potential E½, peak ratio.
  3. Randles–Ševčík block: Ip vs √ν table (6 scan rates) with a two-point
     analytic slope and diffusion coefficient D estimated from it.
  4. Two live-bound charts: CV (I vs E) and Randles–Ševčík (Ip vs √ν).
  5. Two mathtext equations, three instructive sticky notes.

All derived cells are live per-row scalar formulas referencing editable
input cells ($B$5 … $B$10, $I$5 … $I$8) — editing any parameter
instantly recalculates the full table, summary, and charts.

Saved to:  examples/templates/Analysis/Electrochemistry CV-DPV.ksheet

Run:  python examples/build_tpl_electrochemistry_cv.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402

# ── Electrochemical defaults ──────────────────────────────────────────────────
#
# Reversible one-electron redox couple
#   Epa = +0.355 V  (anodic peak potential)
#   Epc = +0.245 V  (cathodic peak potential)
#   ΔEp = 110 mV  ≈ 2.25×(RT/nF) at room temperature (quasi-reversible)
#   E½  = 0.300 V  (formal potential E°')
#
# Capacitive background: I_cap = I₀ + k_cap × E
#   I₀ = 2.0 µA   k_cap = 1.5 µA/V
#
# Gaussian peak shapes (width in V):
#   σ_a = 0.040 V  (anodic)
#   σ_c = 0.042 V  (cathodic)
#
# Potential window: −0.10 V → +0.70 V (forward), +0.70 → −0.10 V (reverse)
# 41 forward + 40 reverse = 81 points total, step ≈ 0.020 V

EPA_VAL   = 0.355    # anodic peak potential (V)
EPC_VAL   = 0.245    # cathodic peak potential (V)
IPA_VAL   = 35.0     # anodic peak height (µA)
IPC_VAL   = -33.5    # cathodic peak height (µA)
I0_VAL    = 2.0      # capacitive offset (µA)
KCAP_VAL  = 1.5      # capacitive slope (µA/V)

SIG_A = 0.040        # anodic Gaussian width (V) — stored as literal in formulas
SIG_C = 0.042        # cathodic Gaussian width (V) — stored as literal in formulas

E_fwd = np.linspace(-0.1, 0.7, 41)
E_rev = np.linspace(0.7, -0.1, 41)[1:]    # skip duplicate 0.700 V
E_all = np.concatenate([E_fwd, E_rev])     # 81 points
N_CV  = len(E_all)   # 81

# Pre-compute CV current for chart initial render (must match formulas)
I_cap    = I0_VAL + KCAP_VAL * E_all
I_anodic = IPA_VAL * np.exp(-0.5 * ((E_all - EPA_VAL) / SIG_A) ** 2)
I_cath   = IPC_VAL * np.exp(-0.5 * ((E_all - EPC_VAL) / SIG_C) ** 2)
I_all    = I_cap + I_anodic + I_cath

# ── Randles–Ševčík defaults ───────────────────────────────────────────────────
#
# Formula (Randles–Ševčík):
#   Ip (µA) = 268700 × n^1.5 × A × √D × C_mM × √ν
#
# where:
#   n      = 1        (number of electrons)
#   A      = 1.0      cm²  (electrode area)
#   C_mM   = 1.0      mM   (bulk concentration; 1 mM = 1e-6 mol/cm³)
#   D      = 1e-5     cm²/s (diffusion coefficient — derived from slope)
#   ν      = scan rate (V/s)
#   RS_CONST = 268700 (from 2.6884×10⁵ A·s^0.5·mol⁻¹·cm⁻²·V⁻⁰·⁵)
#   Unit factor: C in mol/cm³ = C_mM × 1e-6 → absorbed in RS_CONST×1e-6×1e6 = RS_CONST
#     (i.e. use C_mM directly with RS_CONST = 268700)
#
# Scan rates:
NU_VALS  = np.array([0.010, 0.020, 0.050, 0.100, 0.200, 0.500])  # V/s
N_RS     = len(NU_VALS)   # 6

RS_CONST  = 268700.0   # see above
N_E       = 1
A_E       = 1.0        # cm²
D_E       = 1e-5       # cm²/s  (true value for numpy arrays)
D_E_UNIT  = 10.0       # D stored as × 10^-6 cm²/s (avoids sub-0.001 display)
#   I8 = D × 10^-6 cm²/s  →  D (cm²/s) = I8 / 1000000
#   Ip formula uses SQRT(I8/1000000) = SQRT(D_true)
C_MM     = 1.0        # mM

SQRT_NU = np.sqrt(NU_VALS)
IP_RS   = RS_CONST * N_E**1.5 * A_E * np.sqrt(D_E) * C_MM * SQRT_NU  # µA

# ── Layout constants (all 0-based) ───────────────────────────────────────────
#
# Column assignments:
#   Col 0  (A)  CV — Potential E (V)         [X, literal]
#   Col 1  (B)  CV — Current I (µA)          [Y, formula]
#   Col 2  (C)  spacer
#   Col 3  (D)  RS — Scan rate ν (V/s)       [literal]
#   Col 4  (E)  RS — Ip (µA)                 [formula]
#   Col 5  (F)  RS — √ν  (V/s)^0.5          [formula]
#   Col 6  (G)  spacer
#   Col 7  (H)  Label column
#   Col 8  (I)  Value column

# Input cells (1-based A1 notation):
#   Epa      → B5    (row 4 col 1)
#   Epc      → B6    (row 5 col 1)
#   Ipa_par  → B7    (row 6 col 1)
#   Ipc_par  → B8    (row 7 col 1)
#   I0_par   → B9    (row 8 col 1)
#   kcap_par → B10   (row 9 col 1)
#   n_par    → I5    (row 4 col 8)
#   A_par    → I6    (row 5 col 8)
#   C_mM_par → I7    (row 6 col 8)
#   (D is derived — displayed at I10)

# Analysis block: rows 11–16, cols H–I (0-based rows 11-16, cols 7-8)
# RS table: RS_TABLE_START = 19
RS_TABLE_START = 19
RS_FIRST_0B    = RS_TABLE_START + 1   # 0-based first data row = 20
RS_FIRST_SR    = RS_FIRST_0B + 1      # 1-based = 21
RS_LAST_SR     = RS_FIRST_SR + N_RS - 1  # 1-based last = 26

# CV table: CV_TABLE_START = 28
CV_TABLE_START = 28
CV_FIRST_0B    = CV_TABLE_START + 1   # 0-based = 29
CV_FIRST_SR    = CV_FIRST_0B + 1      # 1-based = 30
CV_LAST_SR     = CV_FIRST_SR + N_CV - 1  # 1-based = 110

MIN_ROWS = CV_LAST_SR + 8   # comfortable padding


def build() -> str:
    wb = Workbook(min_rows=MIN_ROWS, min_cols=14)
    s = wb.add_sheet("CV Analysis")

    # ── Column widths ─────────────────────────────────────────────────────────
    s.col_width(0, 130)   # A  E (V)
    s.col_width(1, 130)   # B  I (µA)
    s.col_width(2,  18)   # C  spacer
    s.col_width(3, 120)   # D  ν (V/s)
    s.col_width(4, 120)   # E  Ip (µA)
    s.col_width(5, 110)   # F  √ν
    s.col_width(6,  18)   # G  spacer
    s.col_width(7, 230)   # H  label
    s.col_width(8, 135)   # I  value

    # ── Title block ───────────────────────────────────────────────────────────
    s.title_block(
        "Electrochemistry — Cyclic Voltammetry Analysis",
        "Edit CV parameters (B5:B10) or RS parameters (I5:I7) "
        "to recalculate all columns, analysis, and charts",
        row=0, col=0, span=8,
    )

    # ── CV Parameter panel — rows 3–9, cols A–B ───────────────────────────────
    #
    #  Row 3: section label
    #  Row 4: Epa   → B5
    #  Row 5: Epc   → B6
    #  Row 6: Ipa   → B7
    #  Row 7: Ipc   → B8
    #  Row 8: I₀    → B9
    #  Row 9: k_cap → B10

    s.set(3, 0, "CV Parameters  (edit yellow cells)")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    s.merge(3, 0, 1, 2)

    cv_inputs = [
        ("Anodic peak potential  Epa  (V)",    EPA_VAL),   # B5
        ("Cathodic peak potential  Epc  (V)",  EPC_VAL),   # B6
        ("Anodic peak current  Ipa  (µA)",     IPA_VAL),   # B7
        ("Cathodic peak current  Ipc  (µA)",   IPC_VAL),   # B8
        ("Capacitive offset  I₀  (µA)",        I0_VAL),    # B9
        ("Capacitive slope  k  (µA/V)",        KCAP_VAL),  # B10
    ]
    for i, (lbl, val) in enumerate(cv_inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.fmt(r, 0, align="left")
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.000")

    s.box(4, 0, 9, 1, color=PALETTE["accent"], width=1.5)

    s.note(
        4, 1,
        "CV PEAK PARAMETERS\n"
        "B5: anodic peak potential Epa (V)\n"
        "B6: cathodic peak potential Epc (V)\n"
        "B7: anodic peak current Ipa (µA) — positive\n"
        "B8: cathodic peak current Ipc (µA) — negative\n"
        "B9: capacitive background offset I₀ (µA)\n"
        "B10: capacitive slope k (µA/V)\n\n"
        "Edit any cell to see the CV shape, analysis block, and chart update.",
        kind="note",
    )

    # ── Randles–Ševčík parameter panel — rows 3–9, cols H–I ──────────────────
    #
    #  Row 3: section label
    #  Row 4: n   → I5
    #  Row 5: A   → I6
    #  Row 6: C_mM→ I7
    #  Row 8: D   → I9  (formula derived from RS slope)

    s.set(3, 7, "Randles–Ševčík Parameters")
    s.fmt(3, 7, bold=True, font_color=PALETTE["header"])
    s.merge(3, 7, 1, 2)

    rs_inputs = [
        ("Number of electrons  n",                   N_E),   # I5
        ("Electrode area  A  (cm²)",                 A_E),   # I6
        ("Concentration  C  (mM)",                   C_MM),  # I7
    ]
    for i, (lbl, val) in enumerate(rs_inputs):
        r = 4 + i
        s.set(r, 7, lbl)
        s.fmt(r, 7, align="left")
        s.set(r, 8, val)
        s.fmt(r, 8, bg=PALETTE["warn"], align="center", number_format="0.000")

    s.box(4, 7, 6, 8, color=PALETTE["accent"], width=1.5)

    # ── CV Analysis panel — rows 11–16, cols H–I ─────────────────────────────
    #
    # Rows use references to CV current column (B) and parameter cells (B5, B6).
    # 1-based CV current range: B30:B110

    CV_I_RANGE = f"$B${CV_FIRST_SR}:$B${CV_LAST_SR}"

    s.set(11, 7, "CV Analysis")
    s.fmt(11, 7, bold=True, font_color=PALETTE["header"], font_size=12)
    s.merge(11, 7, 1, 2)

    analysis_items = [
        # (label, formula, bg)
        ("Anodic peak current  Ipa obs  (µA)",
         f"=MAX({CV_I_RANGE})",
         PALETTE["good"]),
        ("Cathodic peak current  Ipc obs  (µA)",
         f"=MIN({CV_I_RANGE})",
         PALETTE["bad"]),
        ("Peak separation  ΔEp  (V)",
         "=$B$5-$B$6",
         PALETTE["warn"]),
        ("Half-wave potential  E½  (V)",
         "=($B$5+$B$6)/2",
         PALETTE["band"]),
        ("Peak ratio  |Ipa/Ipc|",
         f"=ABS(MAX({CV_I_RANGE})/MIN({CV_I_RANGE}))",
         PALETTE["band_alt"]),
        ("Reversibility criterion  ΔEp×1000 (mV)",
         "=($B$5-$B$6)*1000",
         PALETTE["band"]),
    ]
    for i, (lbl, expr, bg) in enumerate(analysis_items):
        r = 12 + i
        s.set(r, 7, lbl)
        s.fmt(r, 7, align="left")
        s.formula(r, 8, expr)
        s.fmt(r, 8, bg=bg, align="center", number_format="0.000", bold=True)

    s.box(12, 7, 12 + len(analysis_items) - 1, 8,
          color=PALETTE["header"], width=1.2)

    s.note(
        12, 8,
        "CV ANALYSIS\n"
        "Ipa obs / Ipc obs: MAX/MIN of the measured current column B.\n"
        "ΔEp = Epa − Epc: for a perfectly reversible one-electron process "
        "at 25 °C, ΔEp ≈ 59 mV (= RT/nF × 2.303).\n"
        "E½ = (Epa + Epc)/2 ≈ formal potential E°'\n"
        "Peak ratio |Ipa/Ipc| ≈ 1.0 for a reversible couple.\n\n"
        "Increasing ΔEp or |Ipa/Ipc| ≠ 1 indicates quasi-reversibility "
        "or chemical complications.",
        kind="note",
    )

    # ── Randles–Ševčík data table — RS_TABLE_START = 19 ──────────────────────
    #
    # Columns D (ν), E (Ip µA), F (√ν)
    # Header at 0-based row 19 → sheet row 20 (1-based)
    # Data rows: 0-based 20..25 → sheet rows 21..26 (1-based)
    #
    # D layout (non-circular):
    #   I8 (row 7 col 8) = D_input  [editable, used by all RS Ip formulas]
    #   I9 (row 8 col 8) = D_derived [formula from two-point slope of E/F columns]
    # Chain: D_input → Ip (col E) → D_derived.  No circularity: I8 ≠ I9.
    #
    # D is stored in units of 10^-6 cm²/s so it displays as ~10.0 (not 0.000).
    # Ip formula: 268700 * n^1.5 * A * C_mM * SQRT(I8/1000000) * SQRT(nu)

    # Add D_input row (row 7, col 7-8)
    # D is stored in units of 10^-6 cm²/s so the display value (~10.0) is
    # comfortably above the 3-decimal rounding threshold.
    # The Ip formulas use SQRT(I8/1000000) = SQRT(D_cm2_per_s).
    # D_derived is also returned in the same scaled units (× 10^-6 cm²/s).
    s.set(7, 7, "D input  (x10^-6 cm^2/s)  [edit to match D derived]")
    s.fmt(7, 7, align="left")
    s.set(7, 8, D_E_UNIT)   # 10.0 = 1e-5 cm²/s in scaled units
    s.fmt(7, 8, bg=PALETTE["warn"], align="center", number_format="0.000")
    s.box(7, 7, 7, 8, color=PALETTE["accent"], width=1.2)

    # D_derived: back-calculated from the two-point slope of the RS table.
    # slope (uA per (V/s)^0.5) = (Ip_last - Ip_first) / (sqrtnu_last - sqrtnu_first)
    # sqrt(D) = slope / (268700 * n^1.5 * A * C_mM)
    # D (cm²/s) = (slope / ...)^2
    # Return in units of 10^-6 cm²/s = D_cm2_s * 1000000  (avoids display rounding to 0)
    D_derived_formula = (
        f"=POWER(("
        f"E{RS_LAST_SR}-E{RS_FIRST_SR})"
        f"/(F{RS_LAST_SR}-F{RS_FIRST_SR})"
        f"/(268700*POWER($I$5,1.5)*$I$6*$I$7),2)"
        f"*1000000"
    )
    s.set(8, 7, "D derived  (x10^-6 cm^2/s)  [from RS slope]")
    s.fmt(8, 7, align="left", bold=True, font_color=PALETTE["header"])
    s.formula(8, 8, D_derived_formula)
    s.fmt(8, 8, bold=True, bg=PALETTE["good"], align="center", number_format="0.000")
    s.box(8, 7, 8, 8, color=PALETTE["header"], width=1.2)

    s.note(
        8, 8,
        "RANDLES–ŠEVČÍK: DIFFUSION COEFFICIENT\n"
        "D derived is back-calculated from the two-point slope of the "
        "Ip vs √ν Randles–Ševčík table below.\n\n"
        "After running a real scan-rate series, paste your Ip values into "
        "column E and the slope will update automatically.\n\n"
        "If D derived ≠ D input, update I8 to converge.\n"
        "(Self-consistent solution: set I8 = I9 then re-open.)",
        kind="note",
    )

    # Section label for RS table
    s.set(18, 3, "Randles–Ševčík Scan-Rate Series")
    s.fmt(18, 3, bold=True, font_color=PALETTE["header"])
    s.merge(18, 3, 1, 3)

    # Build RS table rows
    rs_rows = []
    for k, nu in enumerate(NU_VALS):
        rr = RS_FIRST_SR + k   # 1-based sheet row
        # I8 holds D in units of 10^-6 cm^2/s; divide by 1000000 for true D.
        ip_formula = (
            f"=268700*POWER($I$5,1.5)*$I$6*$I$7*SQRT($I$8/1000000)*SQRT(D{rr})"
        )
        sqrtnu_formula = f"=SQRT(D{rr})"
        rs_rows.append([
            round(float(nu), 3),   # ν literal (independent variable)
            ip_formula,
            sqrtnu_formula,
        ])

    s.table(
        RS_TABLE_START, 3,
        headers=["ν (V/s)", "Ip (µA)", "√ν  (V/s)^0.5"],
        rows=rs_rows,
        banded=True,
    )
    # Apply number formats to RS data rows
    for k in range(N_RS):
        r0b = RS_FIRST_0B + k
        s.fmt(r0b, 3, number_format="0.000",  align="right")
        s.fmt(r0b, 4, number_format="0.000",  align="right")
        s.fmt(r0b, 5, number_format="0.0000", align="right")

    # RS designations (for Randles-Sevcik chart: x=F=√ν, y=E=Ip)
    s.designate(5, "X")   # F = √ν
    s.designate(4, "Y")   # E = Ip

    # ── CV data table — CV_TABLE_START = 28 ──────────────────────────────────
    #
    # Columns A (E) and B (I)
    # Header at 0-based row 28 → sheet row 29 (1-based)
    # Data rows: 0-based 29..109 → sheet rows 30..110 (1-based)
    #
    # I formula at row rr:
    #   = ($B$9 + $B$10*A{rr})
    #     + $B$7 * EXP(-0.5 * ((A{rr} - $B$5) / 0.040)^2)
    #     + $B$8 * EXP(-0.5 * ((A{rr} - $B$6) / 0.042)^2)
    #
    # Gaussian widths 0.040 and 0.042 are plain decimal literals (no E-notation).

    s.set(27, 0, "Cyclic Voltammogram Data  (81 points, −0.10 V → +0.70 V → −0.10 V)")
    s.fmt(27, 0, bold=True, font_color=PALETTE["header"])
    s.merge(27, 0, 1, 2)

    cv_rows = []
    for k, E_val in enumerate(E_all):
        rr = CV_FIRST_SR + k   # 1-based sheet row
        i_formula = (
            f"=($B$9+$B$10*A{rr})"
            f"+$B$7*EXP(-0.5*((A{rr}-$B$5)/0.040)^2)"
            f"+$B$8*EXP(-0.5*((A{rr}-$B$6)/0.042)^2)"
        )
        cv_rows.append([
            round(float(E_val), 4),   # E literal (independent variable)
            i_formula,
        ])

    s.table(
        CV_TABLE_START, 0,
        headers=["Potential  E  (V)", "Current  I  (µA)"],
        rows=cv_rows,
        banded=True,
    )
    for k in range(N_CV):
        r0b = CV_FIRST_0B + k
        s.fmt(r0b, 0, number_format="0.000", align="right")
        s.fmt(r0b, 1, number_format="0.000", align="right")

    # CV designations
    s.designate(0, "X")   # A = E
    s.designate(1, "Y")   # B = I

    # ── Chart 1: Cyclic Voltammogram ──────────────────────────────────────────
    # Live-bound to col A (E) and col B (I)
    # 0-based row range: CV_FIRST_0B .. CV_FIRST_0B + N_CV - 1

    cv_r0 = CV_FIRST_0B
    cv_r1 = CV_FIRST_0B + N_CV - 1

    s.chart(
        [Series(
            E_all, I_all,
            label="I (µA)",
            plot_type="Line",
            color="#4472c4",
            linewidth=2.2,
            x_col=0,
            y_col=1,
            row_start=cv_r0,
            row_end=cv_r1,
        )],
        at=(560, 20),
        size=(460, 310),
        title="Cyclic Voltammogram",
        xlabel="Potential  E  (V)",
        ylabel="Current  I  (µA)",
        grid=True,
        legend=False,
    )

    # ── Chart 2: Randles–Ševčík plot ─────────────────────────────────────────
    # Live-bound: x = col F (√ν, col 5), y = col E (Ip, col 4)
    # 0-based row range: RS_FIRST_0B .. RS_FIRST_0B + N_RS - 1

    rs_r0 = RS_FIRST_0B
    rs_r1 = RS_FIRST_0B + N_RS - 1

    s.chart(
        [Series(
            SQRT_NU, IP_RS,
            label="Ip (µA)",
            plot_type="Line+Symbol",
            color="#ed7d31",
            linewidth=2.0,
            marker="o",
            markersize=6.0,
            x_col=5,
            y_col=4,
            row_start=rs_r0,
            row_end=rs_r1,
        )],
        at=(560, 345),
        size=(460, 280),
        title="Randles–Ševčík: Ip vs √ν",
        xlabel="√ν  (V/s)^0.5",
        ylabel="Ip  (µA)",
        grid=True,
        legend=False,
    )

    # ── LaTeX equations ───────────────────────────────────────────────────────

    # Equation 1: Randles–Ševčík
    s.equation(
        r"I_p = 2.687 \times 10^{5} \, n^{3/2} \, A \, \sqrt{D} \, C \, \sqrt{\nu}",
        at=(560, 640),
        fontsize=16,
        color="#1a3a6b",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(460, 52),
    )

    # Equation 2: ΔEp and E½
    s.equation(
        r"\Delta E_p = E_{pa} - E_{pc} \qquad "
        r"E_{1/2} = \frac{E_{pa} + E_{pc}}{2} \approx E^{\circ\prime}",
        at=(560, 706),
        fontsize=15,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.2,
        size=(460, 54),
    )

    s.note(
        RS_TABLE_START, 5,
        "RANDLES–ŠEVČÍK EQUATION\n"
        "Ip is linear in √ν for a diffusion-controlled process.\n"
        "The slope of the Ip vs √ν line equals:\n"
        "  slope = 268700 × n^1.5 × A × √D × C_mM\n\n"
        "D (diffusion coefficient) is back-calculated in cell I9.\n"
        "n = number of electrons transferred\n"
        "A = electrode area (cm²)\n"
        "C = concentration in mM (1 mM = 10⁻⁶ mol/cm³)\n\n"
        "A non-linear Ip vs √ν plot may indicate adsorption control "
        "(Ip ∝ ν) or a following chemical reaction (EC mechanism).",
        kind="note",
    )

    # ── Save ──────────────────────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Analysis",
    )
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Electrochemistry CV-DPV.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
