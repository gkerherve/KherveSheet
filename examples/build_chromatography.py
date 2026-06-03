"""Build the "Chromatography HPLC-GC" analysis template .ksheet.

Demonstrates a complete HPLC/GC peak-table analysis with live formulas for:
  - Plate count N = 5.54 * (tR / W½)^2
  - Resolution Rs = 2*(tR2 - tR1) / (W½1 + W½2)  (referencing adjacent rows)
  - Tailing Factor TF = (a + b) / (2 * a)  (a = left half-width, b = right)
  - Area % = Area / SUM(all areas) * 100  (absolute-ref the range)

Two sheets:
  "Peak Analysis" — peak table, summary, plate-count chart, equations, notes.
  "Chromatogram"  — simulated Gaussian trace (intensity vs time) with live chart.
                    Each intensity cell references the peak params via local
                    cells on the SAME sheet (a mirrored helper block in cols
                    P-T), so only local refs are used — no cross-sheet limit.

Run:  python examples/build_chromatography.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys
import numpy as np

# Make the project importable from any cwd.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402

# ── Realistic 10-peak HPLC dataset ───────────────────────────────────────────
# Columns: (name, tR min, Area counts, Height mAU, W½ min, a min, b min)
#   W½ = full width at half maximum (FWHM)
#   a  = left half-width at 10% peak height  (for tailing calculation)
#   b  = right half-width at 10% peak height
PEAKS = [
    ("Solvent front",    1.23,  45200, 1820, 0.041, 0.020, 0.025),
    ("Impurity A",       2.87,  18400,  620, 0.068, 0.033, 0.041),
    ("Caffeine",         4.51, 312000, 9850, 0.095, 0.046, 0.055),
    ("Theobromine",      5.84, 187500, 5920, 0.112, 0.054, 0.071),
    ("Theophylline",     7.22,  98400, 3110, 0.128, 0.062, 0.082),
    ("Paraxanthine",     8.93,  54200, 1680, 0.141, 0.068, 0.094),
    ("Hypoxanthine",    10.46,  29800,  910, 0.158, 0.076, 0.108),
    ("Xanthine",        12.05,  16300,  495, 0.172, 0.083, 0.122),
    ("Uric Acid",       14.37,   8750,  261, 0.189, 0.091, 0.137),
    ("Internal Std.",   16.82,  92100, 2845, 0.204, 0.098, 0.154),
]
N_PEAKS = len(PEAKS)

# ── Column letter helper ──────────────────────────────────────────────────────

def col_letter(c):
    """0-based column index → Excel column letter (A, B, …, Z, AA, …)."""
    s = ""
    c += 1
    while c > 0:
        c, rem = divmod(c - 1, 26)
        s = chr(ord("A") + rem) + s
    return s


# ── Sheet 1 layout (0-based rows / cols) ─────────────────────────────────────
#
#  Row 0:  Title
#  Row 1:  Subtitle
#  Row 3:  "Instrument & Method" section header
#  Row 4-7: Instrument inputs
#  Row 9:  Peak table section header
#  Row 10: Peak table column headers        (TABLE_HEADER_ROW)
#  Rows 11-20: 10 peak data rows            (FIRST_PEAK_ROW … LAST_PEAK_ROW)
#  Row 22: Totals row                       (TOTALS_ROW)
#  Rows 24-32: Summary panel (cols 13-14)
#
#  Columns (0-based):
#   0=A  Peak #      (literal)
#   1=B  Peak Name   (literal)
#   2=C  tR (min)    [INPUT]
#   3=D  Area        [INPUT]
#   4=E  Height mAU  [INPUT]
#   5=F  W½ (min)    [INPUT]
#   6=G  a (min)     [INPUT]
#   7=H  b (min)     [INPUT]
#   8=I  Rs          [FORMULA]
#   9=J  N plates    [FORMULA]
#  10=K  Tailing TF  [FORMULA]
#  11=L  Area %      [FORMULA]

TABLE_HEADER_ROW  = 10
FIRST_PEAK_ROW    = 11     # 0-based → 1-based = 12
LAST_PEAK_ROW     = FIRST_PEAK_ROW + N_PEAKS - 1   # 20 (0-based) → 21 (1-based)
TOTALS_ROW        = LAST_PEAK_ROW + 2              # 22 (0-based) → 23 (1-based)

FIRST_PEAK_ROW_1  = FIRST_PEAK_ROW + 1    # 12
LAST_PEAK_ROW_1   = LAST_PEAK_ROW + 1     # 21
TOTALS_ROW_1      = TOTALS_ROW + 1        # 23

C_PEAK_NUM  = 0;  L_PEAKNUM  = col_letter(C_PEAK_NUM)   # A
C_NAME      = 1;  L_NAME     = col_letter(C_NAME)        # B
C_TR        = 2;  L_TR       = col_letter(C_TR)          # C
C_AREA      = 3;  L_AREA     = col_letter(C_AREA)        # D
C_HEIGHT    = 4;  L_HEIGHT   = col_letter(C_HEIGHT)      # E
C_WHALF     = 5;  L_WHALF    = col_letter(C_WHALF)       # F
C_A         = 6;  L_A        = col_letter(C_A)           # G
C_B         = 7;  L_B        = col_letter(C_B)           # H
C_RS        = 8;  L_RS       = col_letter(C_RS)          # I
C_N         = 9;  L_N        = col_letter(C_N)           # J
C_TF        = 10; L_TF       = col_letter(C_TF)          # K
C_AREAPCT   = 11; L_APCT     = col_letter(C_AREAPCT)     # L

# Absolute area sum range (1-based)
AREA_SUM_REF = f"${L_AREA}${FIRST_PEAK_ROW_1}:${L_AREA}${LAST_PEAK_ROW_1}"

# ── Sheet 2 layout (Chromatogram) ────────────────────────────────────────────
#
#  Row 0: Title
#  Row 1: Subtitle
#  Row 3: Column headers
#  Rows 4 – 4+N_T-1: Time (literal) | Intensity (Gaussian-sum formula, LOCAL refs)
#
#  Helper block (peak params mirror, cols 4-8, rows 4–4+N_PEAKS-1):
#   Col 4=E  tR_i  (literal, mirrors Peak Analysis)
#   Col 5=F  H_i   (height, literal)
#   Col 6=G  W½_i  (literal)
#
#  Intensity formula in col B row r = sum of local Gaussians using
#  $E$5:$E$14 (tR), $F$5:$F$14 (H), $G$5:$G$14 (W½) — NO cross-sheet refs!

CHROM_HEADER   = 3
CHROM_DATA_ROW0 = 4    # 0-based first data row → 1-based = 5

# Helper block location (on Chromatogram sheet)
HELPER_ROW0 = 4        # 0-based row of first helper peak
C_HELP_TR  = 4;  L_HELP_TR  = col_letter(C_HELP_TR)   # E
C_HELP_H   = 5;  L_HELP_H   = col_letter(C_HELP_H)    # F
C_HELP_W   = 6;  L_HELP_W   = col_letter(C_HELP_W)    # G

# Helper rows 1-based: HELPER_ROW0+1 = 5 … HELPER_ROW0+N_PEAKS = 14
HELP_ROW_FIRST_1 = HELPER_ROW0 + 1   # 5
HELP_ROW_LAST_1  = HELPER_ROW0 + N_PEAKS  # 14

# ── Numpy arrays ──────────────────────────────────────────────────────────────

def gauss_peak(t, t_r, whalf):
    sigma = whalf / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    return np.exp(-0.5 * ((t - t_r) / max(sigma, 1e-9)) ** 2)


# Chromatogram time axis
T_START, T_END, T_STEP = 0.0, 20.0, 0.1
t_arr = np.arange(T_START, T_END + T_STEP * 0.5, T_STEP)
N_T   = len(t_arr)   # 201 points

# Synthesise intensity for chart initial render
intensity = np.zeros(N_T)
for _name, tr, area, height, whalf, _a, _b in PEAKS:
    intensity += height * gauss_peak(t_arr, tr, whalf)

# Plate count for chart
tr_peaks = np.array([p[1] for p in PEAKS])
wh_peaks = np.array([p[4] for p in PEAKS])
N_plates  = 5.54 * (tr_peaks / np.maximum(wh_peaks, 1e-9)) ** 2


# ── Builder ───────────────────────────────────────────────────────────────────

def build() -> str:
    wb = Workbook(min_rows=60, min_cols=20)

    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 1 — Peak Analysis
    # ══════════════════════════════════════════════════════════════════════════
    s = wb.add_sheet("Peak Analysis")

    # ── Column widths ─────────────────────────────────────────────────────────
    s.col_width(C_PEAK_NUM, 55)
    s.col_width(C_NAME,    130)
    s.col_width(C_TR,       85)
    s.col_width(C_AREA,     95)
    s.col_width(C_HEIGHT,   80)
    s.col_width(C_WHALF,    90)
    s.col_width(C_A,        80)
    s.col_width(C_B,        80)
    s.col_width(C_RS,       85)
    s.col_width(C_N,        90)
    s.col_width(C_TF,       85)
    s.col_width(C_AREAPCT,  75)
    s.col_width(12,         20)   # spacer
    s.col_width(13,        175)   # summary labels
    s.col_width(14,        100)   # summary values

    # ── Title block ───────────────────────────────────────────────────────────
    s.title_block(
        "Chromatography Analysis — HPLC / GC",
        "Peak integration table with Resolution, Plate Count N, Tailing Factor, "
        "and Area % — edit yellow cells to update all calculated columns",
        row=0, col=0, span=12,
    )

    # ── Instrument / Method inputs ────────────────────────────────────────────
    s.set(3, 0, "Instrument & Method")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    s.merge(3, 0, 1, 5)

    method_inputs = [
        ("Instrument / Method",  "Agilent 1260 — C18 reversed-phase"),
        ("Column",               "Zorbax SB-C18 150 mm × 4.6 mm, 5 µm"),
        ("Detector",             "UV 254 nm"),
        ("Flow rate (mL/min)",   1.2),
    ]
    for i, (lbl, val) in enumerate(method_inputs):
        r = 4 + i
        s.set(r, 0, lbl);   s.fmt(r, 0, align="left")
        s.set(r, 1, val);   s.fmt(r, 1, bg=PALETTE["warn"], align="left")
        s.merge(r, 1, 1, 4)
    s.box(4, 0, 7, 5, color=PALETTE["accent"], width=1.2)

    # ── Peak table section label ──────────────────────────────────────────────
    s.set(9, 0,
          "Peak Table  (yellow = editable inputs; green = calculated — auto-update)")
    s.fmt(9, 0, bold=True, font_color=PALETTE["header"])
    s.merge(9, 0, 1, 12)

    # ── Table header row ──────────────────────────────────────────────────────
    HEADERS = [
        "Peak #",
        "Peak Name",
        "tR (min)",
        "Area (counts)",
        "Height (mAU)",
        "W½ (min)",
        "a (min)",
        "b (min)",
        "Rs",
        "N (plates)",
        "Tailing TF",
        "Area %",
    ]
    for j, h in enumerate(HEADERS):
        s.set(TABLE_HEADER_ROW, j, h)
        s.fmt(TABLE_HEADER_ROW, j,
              bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    # ── Peak data rows ────────────────────────────────────────────────────────
    INPUT_BG = PALETTE["warn"]
    CALC_BG  = PALETTE["good"]

    for i, (name, tr, area, height, whalf, a, b) in enumerate(PEAKS):
        r  = FIRST_PEAK_ROW + i   # 0-based
        r1 = r + 1                # 1-based sheet row

        # Peak # and Name (literals — these are labels, not computed outputs)
        s.set(r, C_PEAK_NUM, i + 1)
        s.fmt(r, C_PEAK_NUM, align="center",
              bg=(PALETTE["band_alt"] if i % 2 else None))

        s.set(r, C_NAME, name)
        s.fmt(r, C_NAME, align="left",
              bg=(PALETTE["band_alt"] if i % 2 else None))

        # Editable inputs — amber fill
        s.set(r, C_TR,     round(tr,    3))
        s.fmt(r, C_TR,     bg=INPUT_BG, align="right", number_format="0.000")
        s.set(r, C_AREA,   int(area))
        s.fmt(r, C_AREA,   bg=INPUT_BG, align="right", number_format="0")
        s.set(r, C_HEIGHT, int(height))
        s.fmt(r, C_HEIGHT, bg=INPUT_BG, align="right", number_format="0")
        s.set(r, C_WHALF,  round(whalf, 3))
        s.fmt(r, C_WHALF,  bg=INPUT_BG, align="right", number_format="0.000")
        s.set(r, C_A,      round(a,     3))
        s.fmt(r, C_A,      bg=INPUT_BG, align="right", number_format="0.000")
        s.set(r, C_B,      round(b,     3))
        s.fmt(r, C_B,      bg=INPUT_BG, align="right", number_format="0.000")

        # ── CALCULATED columns ────────────────────────────────────────────────

        # Resolution Rs = 2*(tR_this - tR_prev) / (W½_prev + W½_this)
        # First peak has no predecessor → literal 0 (cannot be computed)
        if i == 0:
            s.set(r, C_RS, 0)
        else:
            prev_r1 = r1 - 1
            s.formula(r, C_RS,
                       f"=2*({L_TR}{r1}-{L_TR}{prev_r1})"
                       f"/MAX({L_WHALF}{prev_r1}+{L_WHALF}{r1},0.001)")
        s.fmt(r, C_RS, bg=CALC_BG, align="right", number_format="0.00")

        # Plate count N = 5.54 * (tR / W½)^2
        s.formula(r, C_N,
                  f"=5.54*POWER({L_TR}{r1}/MAX({L_WHALF}{r1},0.001),2)")
        s.fmt(r, C_N, bg=CALC_BG, align="right", number_format="0")

        # Tailing Factor TF = (a + b) / (2 * a)
        s.formula(r, C_TF,
                  f"=({L_A}{r1}+{L_B}{r1})/(2*MAX({L_A}{r1},0.001))")
        s.fmt(r, C_TF, bg=CALC_BG, align="right", number_format="0.00")

        # Area % = Area / SUM(all areas) * 100
        s.formula(r, C_AREAPCT,
                  f"={L_AREA}{r1}/SUM({AREA_SUM_REF})*100")
        s.fmt(r, C_AREAPCT, bg=CALC_BG, align="right", number_format="0.00")

    # ── Totals row ────────────────────────────────────────────────────────────
    s.set(TOTALS_ROW, C_NAME, "TOTAL")
    s.fmt(TOTALS_ROW, C_NAME, bold=True, align="right")

    s.formula(TOTALS_ROW, C_AREA,
              f"=SUM({L_AREA}{FIRST_PEAK_ROW_1}:{L_AREA}{LAST_PEAK_ROW_1})")
    s.fmt(TOTALS_ROW, C_AREA,
          bold=True, align="right", number_format="0", bg=PALETTE["band"])

    s.formula(TOTALS_ROW, C_AREAPCT,
              f"=SUM({L_APCT}{FIRST_PEAK_ROW_1}:{L_APCT}{LAST_PEAK_ROW_1})")
    s.fmt(TOTALS_ROW, C_AREAPCT,
          bold=True, align="right", number_format="0.00", bg=PALETTE["band"])

    # Box and subtle inner gridlines
    s.box(TABLE_HEADER_ROW, 0, TOTALS_ROW, C_AREAPCT,
          color=PALETTE["header"], width=1.2)
    s.box(TABLE_HEADER_ROW, 0, TOTALS_ROW, C_AREAPCT,
          color="#d0d0d0", width=0.5, inner=True)

    # ── Summary panel (cols 13-14) ────────────────────────────────────────────
    SUMM_L = 13
    SUMM_V = 14
    s.set(3, SUMM_L, "Summary Statistics")
    s.fmt(3, SUMM_L, bold=True, font_color=PALETTE["header"], font_size=11)
    s.merge(3, SUMM_L, 1, 2)

    summary_items = [
        ("Mean Plate Count N",   f"=AVERAGE({L_N}{FIRST_PEAK_ROW_1}:{L_N}{LAST_PEAK_ROW_1})",
         "0", PALETTE["good"]),
        ("Min Resolution Rs",    f"=MIN({L_RS}{FIRST_PEAK_ROW_1+1}:{L_RS}{LAST_PEAK_ROW_1})",
         "0.00", PALETTE["good"]),
        ("Max Tailing Factor",   f"=MAX({L_TF}{FIRST_PEAK_ROW_1}:{L_TF}{LAST_PEAK_ROW_1})",
         "0.00", PALETTE["warn"]),
        ("Total Peak Area",      f"=SUM({AREA_SUM_REF})",
         "0", PALETTE["band"]),
        ("Number of Peaks",      str(N_PEAKS),
         "0", PALETTE["band"]),
        ("Mean N > 5000?",
         f"=IF(AVERAGE({L_N}{FIRST_PEAK_ROW_1}:{L_N}{LAST_PEAK_ROW_1})>5000,\"PASS\",\"REVIEW\")",
         None, PALETTE["good"]),
        ("All Rs > 1.5?",
         f"=IF(MIN({L_RS}{FIRST_PEAK_ROW_1+1}:{L_RS}{LAST_PEAK_ROW_1})>1.5,\"PASS\",\"REVIEW\")",
         None, PALETTE["good"]),
        ("All TF < 2.0?",
         f"=IF(MAX({L_TF}{FIRST_PEAK_ROW_1}:{L_TF}{LAST_PEAK_ROW_1})<2.0,\"PASS\",\"REVIEW\")",
         None, PALETTE["good"]),
    ]
    for i, (lbl, expr, nfmt, bg) in enumerate(summary_items):
        r = 4 + i
        s.set(r, SUMM_L, lbl)
        s.fmt(r, SUMM_L, align="left")
        if expr.startswith("="):
            s.formula(r, SUMM_V, expr)
        else:
            s.set(r, SUMM_V, expr)
        kw = dict(align="center", bold=True, bg=bg)
        if nfmt:
            kw["number_format"] = nfmt
        s.fmt(r, SUMM_V, **kw)
    s.box(4, SUMM_L, 4 + len(summary_items) - 1, SUMM_V,
          color=PALETTE["header"], width=1.2)

    # ── Designations ──────────────────────────────────────────────────────────
    s.designate(C_TR, "X")
    s.designate(C_N,  "Y")

    # ── Plate count chart (Peak Analysis sheet) ───────────────────────────────
    s.chart(
        [
            Series(
                tr_peaks, N_plates,
                label="Plate Count N",
                plot_type="Line+Symbol",
                color="#4472c4",
                linewidth=1.8,
                marker="o",
                markersize=7,
                markerfacecolor="#4472c4",
                x_col=C_TR,
                y_col=C_N,
                row_start=FIRST_PEAK_ROW,
                row_end=LAST_PEAK_ROW,
            ),
        ],
        at=(900, 30),
        size=(470, 300),
        title="Column Efficiency: Plate Count vs Retention Time",
        xlabel="Retention Time (min)",
        ylabel="Theoretical Plates N",
        grid=True,
        legend=True,
    )

    # ── LaTeX equations ───────────────────────────────────────────────────────
    s.equation(
        r"N = 5.54 \left(\frac{t_R}{W_{1/2}}\right)^2",
        at=(900, 348),
        fontsize=20,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(280, 60),
    )
    s.equation(
        r"R_s = \frac{2(t_{R2} - t_{R1})}{W_{1/2,1} + W_{1/2,2}}",
        at=(900, 426),
        fontsize=18,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.5,
        size=(330, 60),
    )
    s.equation(
        r"TF = \frac{a + b}{2a}",
        at=(900, 504),
        fontsize=20,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color="#888888",
        border_width=1.5,
        size=(200, 55),
    )

    # ── Yellow sticky notes ────────────────────────────────────────────────────
    s.note(
        TABLE_HEADER_ROW, C_RS,
        "Resolution Rs measures how well two adjacent peaks are separated.\n"
        "Rs > 1.5 → baseline resolution (USP criterion).\n"
        "Rs = 1.0 → ~94% separation; Rs < 1.0 → overlapping peaks.\n"
        "Edit tR or W½ to see Rs update instantly.",
        kind="note",
    )
    s.note(
        TABLE_HEADER_ROW, C_N,
        "Plate Count N reflects column efficiency.\n"
        "N = 5.54·(tR/W½)²  (Gaussian peak approximation).\n"
        "Typical HPLC: 5 000–20 000 plates.\n"
        "Low N may indicate column degradation or poor packing.",
        kind="note",
    )
    s.note(
        TABLE_HEADER_ROW, C_TF,
        "Tailing Factor (USP) = (a + b) / (2a)\n"
        "a = left half-width at 10% peak height.\n"
        "b = right half-width at 10% peak height.\n"
        "TF = 1.0 → symmetric.  Acceptable range: 0.8–2.0.\n"
        "Edit columns G (a) and H (b) to model asymmetric peaks.",
        kind="note",
    )
    s.note(
        TABLE_HEADER_ROW, C_AREAPCT,
        "Area% = peak area / total area × 100.\n"
        "Used for relative quantification without a calibration curve.\n"
        "The SUM denominator uses an absolute ref to all 10 area cells,\n"
        "so editing any area updates every Area% simultaneously.",
        kind="note",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 2 — Chromatogram
    # Intensity formula uses local refs only (no cross-sheet limit issue).
    # Peak parameters are mirrored in a helper block (cols E-G, rows 5-14).
    # ══════════════════════════════════════════════════════════════════════════
    s2 = wb.add_sheet("Chromatogram")

    s2.col_width(0, 110)   # A  Time
    s2.col_width(1, 120)   # B  Intensity
    s2.col_width(2,  20)   # C  spacer
    s2.col_width(3,  20)   # D  spacer
    s2.col_width(C_HELP_TR, 100)  # E  tR_i
    s2.col_width(C_HELP_H,  100)  # F  H_i
    s2.col_width(C_HELP_W,  100)  # G  W½_i

    # Title
    s2.title_block(
        "Simulated Chromatogram",
        "Gaussian-sum intensity trace — edit tR, Height or W½ in the helper "
        "table (cols E-G) to update the chromatogram chart",
        row=0, col=0, span=6,
    )

    # ── Helper block: peak parameters (editable on this sheet) ───────────────
    s2.set(3, C_HELP_TR, "tR (min)")
    s2.set(3, C_HELP_H,  "Height (mAU)")
    s2.set(3, C_HELP_W,  "W½ (min)")
    for j in [C_HELP_TR, C_HELP_H, C_HELP_W]:
        s2.fmt(3, j, bold=True, bg=PALETTE["header"],
               font_color=PALETTE["header_text"], align="center")

    for i, (name, tr, area, height, whalf, a, b) in enumerate(PEAKS):
        r = HELPER_ROW0 + i   # 0-based rows 4-13
        s2.set(r, C_HELP_TR, round(tr,    3))
        s2.fmt(r, C_HELP_TR, bg=PALETTE["warn"], align="right",
               number_format="0.000")
        s2.set(r, C_HELP_H,  int(height))
        s2.fmt(r, C_HELP_H,  bg=PALETTE["warn"], align="right",
               number_format="0")
        s2.set(r, C_HELP_W,  round(whalf, 3))
        s2.fmt(r, C_HELP_W,  bg=PALETTE["warn"], align="right",
               number_format="0.000")
    s2.box(3, C_HELP_TR, 3 + N_PEAKS, C_HELP_W,
           color=PALETTE["accent"], width=1.2)

    # ── Chromatogram data header ──────────────────────────────────────────────
    s2.set(CHROM_HEADER, 0, "Time (min)")
    s2.set(CHROM_HEADER, 1, "Intensity (mAU)")
    for j in [0, 1]:
        s2.fmt(CHROM_HEADER, j, bold=True,
               bg=PALETTE["header"], font_color=PALETTE["header_text"],
               align="center")

    # ── Chromatogram data: time literals + Gaussian-sum formulas ─────────────
    # For 10 peaks in helper rows 5-14 (1-based), helper cols E,F,G:
    #   tR_i at E5…E14, H_i at F5…F14, W½_i at G5…G14
    # Each formula: sum_i [ F_(5+i) * EXP(-0.5*((t - E_(5+i))*2.3548/G_(5+i))^2) ]
    # This uses only 3 cross-sheet refs per peak → 30 total, BUT all on same sheet!
    # Actually: no cross-sheet refs at all since helper is on this sheet.
    # Formula will reference local cells directly.
    SIGMA_DENOM = "2.3548"  # 2*sqrt(2*ln(2))

    for k in range(N_T):
        r = CHROM_DATA_ROW0 + k       # 0-based
        r1 = r + 1                    # 1-based
        t_val = round(float(t_arr[k]), 2)
        t_cell = f"A{r1}"

        # Time: independent variable literal
        s2.set(r, 0, t_val)
        s2.fmt(r, 0, align="right", number_format="0.00",
               bg=(PALETTE["band_alt"] if k % 2 else None))

        # Intensity: Gaussian sum using LOCAL helper block
        # Each term: F5*EXP(-0.5*POWER((A5-E5)*2.3548/MAX(G5,0.001),2))
        terms = []
        for i in range(N_PEAKS):
            help_r1 = HELP_ROW_FIRST_1 + i  # 5,6,...,14
            ht_ref = f"${L_HELP_H}${help_r1}"
            tr_ref = f"${L_HELP_TR}${help_r1}"
            wh_ref = f"${L_HELP_W}${help_r1}"
            term = (f"{ht_ref}*EXP(-0.5*POWER(({t_cell}-{tr_ref})"
                    f"*{SIGMA_DENOM}/MAX({wh_ref},0.001),2))")
            terms.append(term)

        s2.formula(r, 1, "=" + "+".join(terms))
        s2.fmt(r, 1, align="right", number_format="0.0",
               bg=(PALETTE["band_alt"] if k % 2 else None))

    # Designate axes
    s2.designate(0, "X")
    s2.designate(1, "Y")

    # ── Chromatogram chart ────────────────────────────────────────────────────
    r0 = CHROM_DATA_ROW0
    r1 = CHROM_DATA_ROW0 + N_T - 1

    s2.chart(
        [
            Series(
                t_arr, intensity,
                label="Intensity",
                plot_type="Line",
                color="#4472c4",
                linewidth=1.6,
                x_col=0,
                y_col=1,
                row_start=r0,
                row_end=r1,
            ),
        ],
        at=(440, 40),
        size=(530, 360),
        title="HPLC Chromatogram — Simulated Gaussian Peaks",
        xlabel="Retention Time (min)",
        ylabel="Intensity (mAU)",
        grid=True,
        legend=False,
    )

    # Sticky note on the helper block
    s2.note(
        3, C_HELP_TR,
        "Helper table: edit tR, Height or W½ here to update the "
        "chromatogram trace in real time.\n"
        "These values are independent of the Peak Analysis sheet —\n"
        "they represent the 'model' parameters for the simulation.",
        kind="note",
    )

    # ── Save ──────────────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Analysis",
        "Chromatography HPLC-GC.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
