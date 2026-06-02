"""Build the "Least-Squares Linear Fit" MSci Year-4 exercise .ksheet.

Two-sheet exercise:
  Sheet 1 "Problem"  — statement, editable data, numbered tasks, blank answers.
  Sheet 2 "Solution" — self-contained data, helper columns, OLS slope/intercept
                       computed from sums (SLOPE/INTERCEPT are unimplemented),
                       R^2, residuals, live chart, mathtext equations.

Run:  python examples/build_least_squares_linear_fit.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import numpy as np

# ---------------------------------------------------------------------------
# Repo root on sys.path so ksheet_author imports khervesheet.cellformat
# ---------------------------------------------------------------------------
import sys
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ---------------------------------------------------------------------------
# Experimental (x, y) data  — roughly linear with realistic scatter
# ---------------------------------------------------------------------------
X_DATA = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
Y_DATA = [2.31, 4.05, 5.72, 7.88, 9.43, 11.82, 13.21, 15.67, 17.44, 19.98]
N = len(X_DATA)

# True OLS values (used only for chart render arrays)
_x = np.array(X_DATA)
_y = np.array(Y_DATA)
_n = float(N)
_Sx  = float(np.sum(_x))
_Sy  = float(np.sum(_y))
_Sxx = float(np.sum(_x * _x))
_Sxy = float(np.sum(_x * _y))
_m   = (_n * _Sxy - _Sx * _Sy) / (_n * _Sxx - _Sx * _Sx)
_c   = (_Sy - _m * _Sx) / _n
_yhat = _m * _x + _c
_resid = _y - _yhat
_SStot = float(np.sum((_y - np.mean(_y)) ** 2))
_SSres = float(np.sum(_resid ** 2))
_R2    = 1.0 - _SSres / _SStot


def _col_letter(c: int) -> str:
    """0-based column index → A1-style letter (single or double)."""
    letters = ""
    c += 1
    while c:
        c, rem = divmod(c - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


# ===========================================================================
# SHEET 1 — Problem
# ===========================================================================

def build_problem_sheet(wb: Workbook) -> None:
    s = wb.add_sheet("Problem")

    s.col_width(0, 220)
    s.col_width(1, 110)
    s.col_width(2, 110)
    s.col_width(3, 180)
    s.col_width(4, 160)

    # --- Title block --------------------------------------------------------
    s.title_block(
        "Least-Squares Linear Fit",
        "Year 4 MSci Data Analysis Exercise  ·  Ordinary Least Squares",
        row=0, col=0, span=5,
    )

    # --- Problem statement --------------------------------------------------
    s.set(2, 0, "Problem Statement")
    s.fmt(2, 0, bold=True, font_size=12, font_color=PALETTE["header"])
    s.merge(2, 0, 1, 5)

    statement_lines = [
        ("You have collected 10 pairs of measurements (x, y) from an "
         "experiment expected to follow a linear trend."),
        ("Your task is to find the best-fit straight line  y = m x + c  "
         "using ordinary least squares (OLS), and assess the quality of "
         "the fit."),
        ("All calculations must be performed from first principles "
         "using the sums of x, y, x² and xy — do not use a "
         "built-in SLOPE or INTERCEPT function."),
    ]
    for i, line in enumerate(statement_lines):
        s.set(3 + i, 0, line)
        s.fmt(3 + i, 0, wrap=True, italic=(i == 2))
        s.merge(3 + i, 0, 1, 5)

    # --- Data table (editable amber cells) ----------------------------------
    s.set(7, 0, "Experimental Data")
    s.fmt(7, 0, bold=True, font_color=PALETTE["header"])

    data_headers = ["x (a.u.)", "y (a.u.)"]
    s.set(8, 0, data_headers[0])
    s.set(8, 1, data_headers[1])
    s.fmt(8, 0, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.fmt(8, 1, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")

    for i, (xi, yi) in enumerate(zip(X_DATA, Y_DATA)):
        r = 9 + i
        s.set(r, 0, xi)
        s.set(r, 1, yi)
        s.fmt(r, 0, bg=PALETTE["warn"], align="center", number_format="0.00")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.00")

    s.box(8, 0, 18, 1, color=PALETTE["header"], width=1.5)
    s.note(9, 1,
           "Edit these y-values — they are your\n"
           "experimental measurements. The Solution\n"
           "sheet will recompute everything live.",
           kind="note")

    # --- Tasks (numbered) ---------------------------------------------------
    s.set(7, 3, "Tasks")
    s.fmt(7, 3, bold=True, font_color=PALETTE["header"])

    tasks = [
        ("1.", "Compute the five sums: n, Sx = Σx, Sy = Σy, "
               "Sxx = Σx², Sxy = Σxy."),
        ("2.", "Calculate the OLS slope:  m = (n Sxy − Sx Sy) / "
               "(n Sxx − Sx²)."),
        ("3.", "Calculate the OLS intercept:  c = (Sy − m Sx) / n."),
        ("4.", "Compute fitted values  ŷᵢ = m xᵢ + c  and "
               "residuals  eᵢ = yᵢ − ŷᵢ."),
        ("5.", "Calculate R² = 1 − SSᴿᵉˢ / "
               "SSᵀᵒᵀ  where  SSᴿᵉˢ = Σeᵢ²  "
               "and  SSᵀᵒᵀ = Σ(yᵢ − ȳ)²."),
        ("6.", "Plot the data as a scatter plot overlaid with the best-fit line."),
        ("7.", "Plot the residuals eᵢ vs xᵢ. What pattern (if any) do you see?"),
    ]
    for i, (num, text) in enumerate(tasks):
        r = 8 + i
        s.set(r, 3, num)
        s.set(r, 4, text)
        s.fmt(r, 3, bold=True, align="center",
              bg=(PALETTE["band"] if i % 2 == 0 else PALETTE["band_alt"]))
        s.fmt(r, 4, wrap=True,
              bg=(PALETTE["band"] if i % 2 == 0 else PALETTE["band_alt"]))

    s.box(8, 3, 14, 4, color=PALETTE["header"], width=1.0)
    s.note(7, 3,
           "Work through tasks 1-7 in order.\n"
           "Write your answers in the cells below.",
           kind="note")

    # --- Your answers (blank) -----------------------------------------------
    s.set(16, 0, "Your Answers")
    s.fmt(16, 0, bold=True, font_color=PALETTE["accent"])

    answer_rows = [
        ("Slope m", "", "a.u. / a.u."),
        ("Intercept c", "", "a.u."),
        ("R²", "", "(dimensionless)"),
        ("SSᴿᵉˢ", "", "a.u.²"),
        ("SSᵀᵒᵀ", "", "a.u.²"),
    ]
    s.set(17, 0, "Quantity")
    s.set(17, 1, "Value")
    s.set(17, 2, "Units")
    s.fmt(17, 0, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.fmt(17, 1, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.fmt(17, 2, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")

    for i, (qty, val, unit) in enumerate(answer_rows):
        r = 18 + i
        s.set(r, 0, qty)
        s.set(r, 1, val)          # blank — student fills in
        s.set(r, 2, unit)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg="#f2f2f2", align="center", number_format="0.0000")
        s.fmt(r, 2, italic=True, align="left")

    s.box(17, 0, 22, 2, color=PALETTE["accent"], width=1.5)
    s.note(18, 1,
           "Enter your computed values here.\n"
           "Check against Sheet 2 (Solution).",
           kind="note")


# ===========================================================================
# SHEET 2 — Solution
# ===========================================================================
#
# Column layout (0-based):
#   A(0)  x        — literal independent variable
#   B(1)  y        — literal measured data (self-contained copy)
#   C(2)  x^2      — formula =A*A
#   D(3)  x*y      — formula =A*B
#   E(4)  y_hat    — formula =m*x + c   (refs $I$3 and $I$4 for m and c)
#   F(5)  residual — formula =B - E
#   G(6)  (y-ybar)^2 — for SStot
#   H(7)  e^2       — for SSres
#
# Sums panel at row 17 (0-based) in cols A-H  (sheet row 18, after 10 data rows)
# Fit results at rows 20-26, cols I-K
#
# m lives at J21 (0-based row=20, col=9), c at J22 (row=21, col=9)
# AVERAGE(y) at J20 (row=19, col=9)
# R^2 at J25 (row=24, col=9)
#
# Data rows (0-based): header=4, data=5..14 → sheet rows 5+1=6 .. 14+1=15
# i.e. first data sheet row = 6, last = 15
#
# Table start_row (0-based API) = 4
#  → header at sheet row 5 (1-based)
#  → first data row at sheet row 6 (1-based)  i.e. row index 5
#  → last  data row at sheet row 15 (1-based) i.e. row index 14

DATA_TABLE_START = 4    # 0-based row for the table() header
DATA_FIRST_ROW   = 5    # 0-based row of first data point
DATA_LAST_ROW    = 14   # 0-based row of last  data point  (10 rows total)

# 1-based sheet references for the data range
_SR_FIRST = DATA_FIRST_ROW + 1    # = 6
_SR_LAST  = DATA_LAST_ROW  + 1    # = 15

# Sums row (0-based): one row below the data table
SUMS_ROW = DATA_LAST_ROW + 2      # = 16  (row 17 in sheet, leaving a blank row 16)

# Fit results block (0-based rows)
FIT_ROW_START = SUMS_ROW + 2      # = 18
# Cells holding fit parameters (0-based):
ROW_N    = FIT_ROW_START           # n
ROW_SX   = FIT_ROW_START + 1      # Sx
ROW_SY   = FIT_ROW_START + 2      # Sy
ROW_SXX  = FIT_ROW_START + 3      # Sxx
ROW_SXY  = FIT_ROW_START + 4      # Sxy
ROW_YBAR = FIT_ROW_START + 5      # y-bar
ROW_M    = FIT_ROW_START + 6      # slope m
ROW_C    = FIT_ROW_START + 7      # intercept c
ROW_SSR  = FIT_ROW_START + 8      # SSres
ROW_SST  = FIT_ROW_START + 9      # SStot
ROW_R2   = FIT_ROW_START + 10     # R^2

# Columns for the fit panel (0-based)
COL_FIT_LBL = 9   # J — label
COL_FIT_VAL = 10  # K — value
COL_FIT_UNI = 11  # L — units/meaning


def _sr(row_0based: int) -> int:
    """0-based row → 1-based sheet row."""
    return row_0based + 1


def _ref(row_0based: int, col_0based: int, abs_row=True, abs_col=True) -> str:
    """Build an A1-style cell reference."""
    col = _col_letter(col_0based)
    row = _sr(row_0based)
    if abs_row and abs_col:
        return f"${col}${row}"
    if abs_col:
        return f"${col}{row}"
    if abs_row:
        return f"{col}${row}"
    return f"{col}{row}"


def build_solution_sheet(wb: Workbook) -> None:
    s = wb.add_sheet("Solution")

    # Column widths
    s.col_width(0, 90)   # A: x
    s.col_width(1, 90)   # B: y
    s.col_width(2, 90)   # C: x^2
    s.col_width(3, 90)   # D: xy
    s.col_width(4, 90)   # E: y_hat
    s.col_width(5, 90)   # F: residual
    s.col_width(6, 100)  # G: (y-ybar)^2
    s.col_width(7, 90)   # H: e^2
    s.col_width(8, 20)   # (spacer)
    s.col_width(9, 160)  # J: label
    s.col_width(10, 120) # K: value
    s.col_width(11, 160) # L: units

    # --- Title --------------------------------------------------------------
    s.title_block(
        "Solution — Least-Squares Linear Fit",
        "OLS slope and intercept computed from first-principles sums",
        row=0, col=0, span=8,
    )

    # --- Designate X and Y columns ------------------------------------------
    s.designate(0, "X")   # col A = x
    s.designate(4, "Y")   # col E = y_hat   (used for line series)

    # --- Data + helper-column table -----------------------------------------
    # Columns: x | y | x^2 | x*y | y_hat | residual | (y-ybar)^2 | e^2
    #
    # y_hat and residual depend on m (K{ROW_M+1}) and c (K{ROW_C+1}),
    # which are themselves formula cells, so the whole chain is live.
    #
    # (y - ybar)^2 uses AVERAGE over the y column directly so it always
    # reflects the current data without needing a separate ybar cell
    # reference that would cause a circular dependency.

    r_m_ref   = _ref(ROW_M, COL_FIT_VAL)   # absolute ref to slope m
    r_c_ref   = _ref(ROW_C, COL_FIT_VAL)   # absolute ref to intercept c
    y_avg_ref = f"AVERAGE(B{_SR_FIRST}:B{_SR_LAST})"

    table_rows = []
    for i in range(N):
        rr = _SR_FIRST + i   # 1-based sheet row for this data row
        row_data = [
            X_DATA[i],          # col 0: x — editable literal
            Y_DATA[i],          # col 1: y — editable literal
            f"=A{rr}*A{rr}",               # col 2: x^2
            f"=A{rr}*B{rr}",               # col 3: x*y
            f"={r_m_ref}*A{rr}+{r_c_ref}", # col 4: y_hat
            f"=B{rr}-E{rr}",               # col 5: residual
            f"=(B{rr}-{y_avg_ref})*(B{rr}-{y_avg_ref})",  # col 6: (y-ybar)^2
            f"=F{rr}*F{rr}",               # col 7: e^2
        ]
        table_rows.append(row_data)

    s.set(3, 0, "Data and helper columns")
    s.fmt(3, 0, bold=True, font_color=PALETTE["header"])

    headers = ["x", "y", "x²", "x·y",
               "ŷ (fitted)", "e = y−ŷ",
               "(y−ȳ)²", "e²"]
    s.table(
        DATA_TABLE_START, 0,
        headers=headers,
        rows=table_rows,
        number_format="0.0000",
        banded=True,
    )

    # Override alignment: x/y columns left-aligned (they are the inputs)
    for i in range(N):
        s.fmt(DATA_FIRST_ROW + i, 0, align="center",
              bg=PALETTE["warn"], number_format="0.00")
        s.fmt(DATA_FIRST_ROW + i, 1, align="center",
              bg=PALETTE["warn"], number_format="0.00")

    s.note(DATA_FIRST_ROW, 1,
           "These amber cells are the data.\n"
           "Edit y to see slope, intercept and R² update.",
           kind="note")
    s.note(DATA_FIRST_ROW, 4,
           "y_hat = m*x + c  (live formula — references\n"
           "the slope and intercept cells below)",
           kind="note")

    # --- Sums panel (row SUMS_ROW, cols A-H) --------------------------------
    sums_labels = [
        f"=SUM(A{_SR_FIRST}:A{_SR_LAST})",   # col 0: Sx
        f"=SUM(B{_SR_FIRST}:B{_SR_LAST})",   # col 1: Sy
        f"=SUM(C{_SR_FIRST}:C{_SR_LAST})",   # col 2: Sxx
        f"=SUM(D{_SR_FIRST}:D{_SR_LAST})",   # col 3: Sxy
        "",                                   # col 4: (blank under y_hat)
        "",                                   # col 5: (blank under residual)
        f"=SUM(G{_SR_FIRST}:G{_SR_LAST})",   # col 6: SStot
        f"=SUM(H{_SR_FIRST}:H{_SR_LAST})",   # col 7: SSres
    ]
    sums_hdr_labels = [
        "Sx", "Sy", "Sxx", "Sxy", "", "", "SStot", "SSres",
    ]

    for j, (hdr, expr) in enumerate(zip(sums_hdr_labels, sums_labels)):
        if not hdr:
            continue
        s.set(SUMS_ROW - 1, j, hdr)
        s.fmt(SUMS_ROW - 1, j, bold=True, align="center",
              bg=PALETTE["header"], font_color=PALETTE["header_text"])
        s.formula(SUMS_ROW, j, expr)
        s.fmt(SUMS_ROW, j, bg=PALETTE["band"], align="center",
              number_format="0.0000", bold=True)

    s.box(SUMS_ROW - 1, 0, SUMS_ROW, 7,
          color=PALETTE["header"], width=1.5)
    s.note(SUMS_ROW - 1, 0,
           "Intermediate sums used in the OLS\n"
           "formulas below. Recompute automatically\n"
           "when data changes.",
           kind="note")

    # --- Fit results panel (rows FIT_ROW_START.., cols J-L) -----------------
    # All quantities reference the sums, which reference the data — live chain.

    # Shorthand refs to the sums row
    r_Sx  = _ref(SUMS_ROW, 0)   # $A$17 (or wherever)
    r_Sy  = _ref(SUMS_ROW, 1)
    r_Sxx = _ref(SUMS_ROW, 2)
    r_Sxy = _ref(SUMS_ROW, 3)
    r_SSt = _ref(SUMS_ROW, 6)   # SStot
    r_SSr = _ref(SUMS_ROW, 7)   # SSres

    fit_label_col = COL_FIT_LBL
    fit_value_col = COL_FIT_VAL
    fit_unit_col  = COL_FIT_UNI

    s.set(FIT_ROW_START - 1, fit_label_col, "OLS Fit Results")
    s.fmt(FIT_ROW_START - 1, fit_label_col, bold=True,
          font_size=12, font_color=PALETTE["header"])
    s.merge(FIT_ROW_START - 1, fit_label_col, 1, 3)

    # n (number of points)
    n_ref_expr = f"=COUNT(A{_SR_FIRST}:A{_SR_LAST})"
    n_ref_cell = _ref(ROW_N, fit_value_col)

    fit_items = [
        # (label,     formula for value col,               unit_text)
        ("n  (count)", n_ref_expr,
         "number of points"),
        ("Sx  = Σx", f"={r_Sx}",
         "a.u."),
        ("Sy  = Σy", f"={r_Sy}",
         "a.u."),
        ("Sxx = Σx²", f"={r_Sxx}",
         "a.u.²"),
        ("Sxy = Σxy", f"={r_Sxy}",
         "a.u.²"),
        ("ȳ = mean(y)", f"=AVERAGE(B{_SR_FIRST}:B{_SR_LAST})",
         "a.u."),
        # Slope: m = (n*Sxy - Sx*Sy)/(n*Sxx - Sx^2)
        # Use n from the n cell to avoid recomputing COUNT
        ("Slope  m",
         f"=({n_ref_cell}*{r_Sxy}-{r_Sx}*{r_Sy})/({n_ref_cell}*{r_Sxx}-{r_Sx}*{r_Sx})",
         "a.u. / a.u."),
        # Intercept: c = (Sy - m*Sx)/n
        ("Intercept  c",
         f"=({r_Sy}-{r_m_ref}*{r_Sx})/{n_ref_cell}",
         "a.u."),
        # SSres — reference the sum column
        ("SSres = Σe²", f"={r_SSr}",
         "a.u.²"),
        # SStot — reference the sum column
        ("SStot = Σ(y−ȳ)²", f"={r_SSt}",
         "a.u.²"),
        # R^2
        ("R²", f"=1-{r_SSr}/{r_SSt}",
         "(dimensionless)"),
    ]

    for i, (lbl, expr, unit) in enumerate(fit_items):
        r = FIT_ROW_START + i
        s.set(r, fit_label_col, lbl)
        s.formula(r, fit_value_col, expr)
        s.set(r, fit_unit_col, unit)
        band = PALETTE["band"] if i % 2 == 0 else PALETTE["band_alt"]
        s.fmt(r, fit_label_col, align="left", bg=band)
        s.fmt(r, fit_value_col, align="center", bg=band,
              number_format="0.000000")
        s.fmt(r, fit_unit_col, align="left", italic=True, bg=band)

    # Highlight slope, intercept, R^2 rows more strongly
    for highlight_row in (ROW_M, ROW_C, ROW_R2):
        s.fmt(highlight_row, fit_value_col,
              bold=True, bg=PALETTE["good"], number_format="0.000000")

    s.box(FIT_ROW_START, fit_label_col,
          FIT_ROW_START + len(fit_items) - 1, fit_unit_col,
          color=PALETTE["header"], width=1.5)

    s.note(ROW_M, fit_label_col,
           "m = (n·Sxy − Sx·Sy) / (n·Sxx − Sx²)\n"
           "Derived from d/dm[SSres]=0.",
           kind="note")
    s.note(ROW_R2, fit_label_col,
           "R² = 1 − SSres/SStot\n"
           "Values close to 1 indicate a good linear fit.",
           kind="note")

    # --- Chart: data (Scatter) + fitted line (Line) -------------------------
    # Bound to:
    #   Series 0: x = col A (0), y = col B (1)  — raw data
    #   Series 1: x = col A (0), y = col E (4)  — fitted line
    # Both cover 0-based rows DATA_FIRST_ROW..DATA_LAST_ROW

    r0, r1 = DATA_FIRST_ROW, DATA_LAST_ROW
    x_arr   = np.array(X_DATA)
    y_arr   = np.array(Y_DATA)
    yhat_arr = _yhat   # computed numerically above

    s.chart(
        [
            Series(
                x_arr, y_arr,
                label="Data", plot_type="Scatter",
                color=PALETTE["header"], marker="o", markersize=7.0,
                markerfacecolor=PALETTE["warn"],
                markeredgecolor=PALETTE["header"],
                x_col=0, y_col=1, row_start=r0, row_end=r1,
            ),
            Series(
                x_arr, yhat_arr,
                label="Best-fit line", plot_type="Line",
                color=PALETTE["accent"], linewidth=2.0,
                x_col=0, y_col=4, row_start=r0, row_end=r1,
            ),
        ],
        at=(800, 30), size=(460, 320),
        title="OLS Linear Fit",
        xlabel="x (a.u.)", ylabel="y (a.u.)",
        grid=True, legend=True,
    )

    # --- Residual chart (Scatter) -------------------------------------------
    # Bound to col A (x) and col F (residuals)
    resid_arr = _resid
    s.chart(
        [
            Series(
                x_arr, resid_arr,
                label="Residuals", plot_type="Scatter",
                color=PALETTE["bad"], marker="o", markersize=7.0,
                markerfacecolor=PALETTE["bad"],
                markeredgecolor="#880000",
                x_col=0, y_col=5, row_start=r0, row_end=r1,
            ),
        ],
        at=(800, 380), size=(460, 260),
        title="Residuals  eᵢ = yᵢ − ŷᵢ",
        xlabel="x (a.u.)", ylabel="Residual (a.u.)",
        grid=True, legend=False,
    )

    # --- Mathtext equations -------------------------------------------------
    # Equation 1: OLS normal equations / formulas
    s.equation(
        r"\hat{m} = \frac{n\sum x_i y_i - \sum x_i \sum y_i}"
        r"{n\sum x_i^2 - \left(\sum x_i\right)^2}",
        at=(800, 670), fontsize=16,
        color="#111111", bg_color="#ffffff",
        border_color=PALETTE["header"], border_width=1.2,
        size=(380, 60),
    )

    # Equation 2: R^2
    s.equation(
        r"R^2 = 1 - \frac{SS_{\mathrm{res}}}{SS_{\mathrm{tot}}}"
        r" = 1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y})^2}",
        at=(800, 750), fontsize=16,
        color="#111111", bg_color="#ffffff",
        border_color=PALETTE["header"], border_width=1.2,
        size=(460, 60),
    )


# ===========================================================================
# Main
# ===========================================================================

def build() -> str:
    wb = Workbook(min_rows=50, min_cols=14)
    build_problem_sheet(wb)
    build_solution_sheet(wb)

    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "exercises", "Year 4",
    )
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Least-Squares Linear Fit.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    path = build()
    print(f"Wrote: {path}")
    print(f"  n = {N}")
    print(f"  slope m    = {_m:.6f}")
    print(f"  intercept c= {_c:.6f}")
    print(f"  R^2        = {_R2:.6f}")
