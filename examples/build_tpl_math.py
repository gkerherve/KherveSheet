"""Build the rich Math template set (examples/templates/Math/).

Sine/Cosine Table, Quadratic Solver, Matrix Operations, Exponential
Growth, Regression Data, Statistics Sample.

Run:  python examples/build_tpl_math.py
Copyright (C) 2026 Gwilherm Kerherve - GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "templates", "Math")


def _save(wb, name):
    wb.save(os.path.join(OUT, name))


def _colL(c):
    return chr(ord("A") + c)


def sine_cosine():
    wb = Workbook(min_rows=40, min_cols=10)
    s = wb.add_sheet("Trig")
    s.title_block("Sine / Cosine Table",
                  "sin, cos and tan from 0 to 360 degrees", span=6)
    TS = 4
    angles = list(range(0, 361, 15))
    rows = []
    for i, a in enumerate(angles):
        sr = TS + 2 + i
        rows.append([a, f"=RADIANS(A{sr})", f"=SIN(RADIANS(A{sr}))",
                     f"=COS(RADIANS(A{sr}))", f"=TAN(RADIANS(A{sr}))"])
    s.table(TS, 0, headers=["Angle°", "Radians", "sin", "cos", "tan"],
            rows=rows, number_format="0.0000", banded=True, align_data="center")
    r0, r1 = TS + 1, TS + len(angles)
    s.chart([Series(np.array(angles, dtype=float),
                    np.sin(np.radians(angles)), "sin", "Line",
                    color=PALETTE["header"], x_col=0, y_col=2,
                    row_start=r0, row_end=r1),
             Series(np.array(angles, dtype=float),
                    np.cos(np.radians(angles)), "cos", "Line",
                    color=PALETTE["accent"], x_col=0, y_col=3,
                    row_start=r0, row_end=r1)],
            at=(560, 40), size=(440, 300), title="sin and cos",
            xlabel="Angle (deg)", ylabel="value", legend=True)
    _save(wb, "Sine Cosine Table.ksheet")


def quadratic_solver():
    wb = Workbook(min_rows=40, min_cols=10)
    s = wb.add_sheet("Quadratic")
    s.title_block("Quadratic Solver",
                  "Roots of a x^2 + b x + c = 0", span=6)
    s.set(3, 0, "Coefficients")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    for i, (lbl, val) in enumerate([("a", 1.0), ("b", -3.0), ("c", 2.0)]):
        s.set(4 + i, 0, lbl)
        s.set(4 + i, 1, val)
        s.fmt(4 + i, 1, bg=PALETTE["warn"], align="center", number_format="0.0###")
    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.0)
    # Inputs: a=B5, b=B6, c=B7 (0-based rows 4-6 -> 1-based 5-7).
    res = [
        ("Discriminant", "=B6*B6-4*B5*B7"),
        ("Root 1", "=(0-B6+SQRT(MAX(B6*B6-4*B5*B7,0)))/(2*B5)"),
        ("Root 2", "=(0-B6-SQRT(MAX(B6*B6-4*B5*B7,0)))/(2*B5)"),
        ("Vertex x", "=(0-B6)/(2*B5)"),
        ("Vertex y", "=B5*((0-B6)/(2*B5))^2+B6*((0-B6)/(2*B5))+B7"),
        ("Nature",
         '=IF(B6*B6-4*B5*B7>0,"Two real roots",'
         'IF(B6*B6-4*B5*B7==0,"One real root","Complex roots"))'),
    ]
    s.set(3, 3, "Results")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"])
    for i, (lbl, expr) in enumerate(res):
        s.set(4 + i, 3, lbl)
        s.formula(4 + i, 4, expr)
        s.fmt(4 + i, 4, bold=True, bg=PALETTE["band"], number_format="0.000")
    s.box(4, 3, 9, 4, color=PALETTE["header"], width=1.0)
    s.col_width(3, 130)
    # Parabola plot
    TS = 12
    xs = np.linspace(-3, 5, 33)
    rows = []
    for i, x in enumerate(xs):
        sr = TS + 2 + i
        rows.append([round(float(x), 3), f"=$B$5*A{sr}*A{sr}+$B$6*A{sr}+$B$7"])
    s.set(11, 0, "Curve  y = a x² + b x + c")
    s.fmt(11, 0, bold=True, font_color=PALETTE["header"])
    s.table(TS, 0, headers=["x", "y"], rows=rows,
            number_format="0.00", banded=True, align_data="center")
    r0, r1 = TS + 1, TS + len(xs)
    s.chart([Series(xs, xs * xs - 3 * xs + 2, "y", "Line",
                    color=PALETTE["header"], x_col=0, y_col=1,
                    row_start=r0, row_end=r1)],
            at=(560, 40), size=(440, 300), title="Parabola",
            xlabel="x", ylabel="y", legend=False)
    s.note(4, 1, "Edit a, b, c — roots, vertex and the curve update.",
           kind="note")
    _save(wb, "Quadratic Solver.ksheet")


def matrix_operations():
    wb = Workbook(min_rows=30, min_cols=10)
    s = wb.add_sheet("Matrices")
    s.title_block("Matrix Operations",
                  "3x3 matrices: A + B and A x B (live)", span=7)

    def Ae(i, j):
        return f"{_colL(j)}{6 + i}"        # cols A,B,C rows 6,7,8

    def Be(i, j):
        return f"{_colL(4 + j)}{6 + i}"     # cols E,F,G rows 6,7,8

    A = [[1, 2, 3], [0, 1, 4], [5, 6, 0]]
    B = [[2, 0, 1], [1, 3, 2], [4, 1, 0]]
    s.set(4, 0, "Matrix A")
    s.fmt(4, 0, bold=True, font_color=PALETTE["accent"])
    s.set(4, 4, "Matrix B")
    s.fmt(4, 4, bold=True, font_color=PALETTE["accent"])
    for i in range(3):
        for j in range(3):
            s.set(5 + i, j, A[i][j])
            s.fmt(5 + i, j, bg=PALETTE["warn"], align="center")
            s.set(5 + i, 4 + j, B[i][j])
            s.fmt(5 + i, 4 + j, bg=PALETTE["warn"], align="center")
    s.box(5, 0, 7, 2, color=PALETTE["accent"], width=1.0)
    s.box(5, 4, 7, 6, color=PALETTE["accent"], width=1.0)
    # A + B
    s.set(9, 0, "A + B")
    s.fmt(9, 0, bold=True, font_color=PALETTE["header"])
    for i in range(3):
        for j in range(3):
            s.formula(10 + i, j, f"={Ae(i, j)}+{Be(i, j)}")
            s.fmt(10 + i, j, bg=PALETTE["band"], align="center")
    s.box(10, 0, 12, 2, color=PALETTE["header"], width=1.0)
    # A x B
    s.set(9, 4, "A × B")
    s.fmt(9, 4, bold=True, font_color=PALETTE["header"])
    for i in range(3):
        for j in range(3):
            expr = "+".join(f"{Ae(i, k)}*{Be(k, j)}" for k in range(3))
            s.formula(10 + i, 4 + j, "=" + expr)
            s.fmt(10 + i, 4 + j, bg=PALETTE["band"], align="center")
    s.box(10, 4, 12, 6, color=PALETTE["header"], width=1.0)
    s.note(5, 0, "Edit A or B; the sum and product recompute.", kind="note")
    _save(wb, "Matrix Operations.ksheet")


def exponential_growth():
    wb = Workbook(min_rows=40, min_cols=10)
    s = wb.add_sheet("Growth")
    s.title_block("Exponential Growth",
                  "Discrete and continuous compounding", span=6)
    for i, (lbl, val) in enumerate([("Initial N0", 100.0),
                                    ("Growth rate % per step", 8.0)]):
        s.set(4 + i, 0, lbl)
        s.set(4 + i, 1, val)
        s.fmt(4 + i, 1, bg=PALETTE["warn"], align="center", number_format="0.0##")
    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 170)
    TS = 7
    n = 25
    rows = []
    for t in range(n):
        sr = TS + 2 + t
        rows.append([t, f"=$B$5*POWER(1+$B$6/100,A{sr})",
                     f"=$B$5*EXP($B$6/100*A{sr})"])
    s.set(6, 0, "Growth table")
    s.fmt(6, 0, bold=True, font_color=PALETTE["header"])
    s.table(TS, 0, headers=["t", "Discrete", "Continuous"], rows=rows,
            number_format="0.0", banded=True, align_data="center")
    r0, r1 = TS + 1, TS + n
    t = np.arange(n)
    s.chart([Series(t, 100 * (1.08 ** t), "Discrete", "Line",
                    color=PALETTE["header"], x_col=0, y_col=1,
                    row_start=r0, row_end=r1),
             Series(t, 100 * np.exp(0.08 * t), "Continuous", "Line",
                    color=PALETTE["accent"], linestyle="--",
                    x_col=0, y_col=2, row_start=r0, row_end=r1)],
            at=(440, 40), size=(440, 300), title="Exponential Growth",
            xlabel="t", ylabel="N", legend=True)
    _save(wb, "Exponential Growth.ksheet")


def regression_data():
    wb = Workbook(min_rows=40, min_cols=12)
    s = wb.add_sheet("Regression")
    s.title_block("Regression Data",
                  "Least-squares straight-line fit (from sums)", span=7)
    xs = list(range(1, 12))
    ys = [2.3, 4.1, 5.9, 8.4, 9.8, 12.6, 14.0, 16.3, 18.1, 19.9, 22.4]
    TS = 4
    last = TS + 1 + len(xs)
    # Panel value cells (col J = index 9): J4 meanY, J5 n, J6 slope,
    # J7 intercept, J8 SSres, J9 SStot, J10 R^2.
    rows = []
    for i, (x, y) in enumerate(zip(xs, ys)):
        sr = TS + 2 + i
        rows.append([x, y, f"=A{sr}*A{sr}", f"=A{sr}*B{sr}",
                     f"=$J$6*A{sr}+$J$7",            # fit yhat
                     f"=(B{sr}-E{sr})^2",            # residual^2
                     f"=(B{sr}-$J$4)^2"])            # (y-meanY)^2
    s.table(TS, 0, headers=["x", "y", "x²", "x·y", "fit ŷ", "resid²", "dev²"],
            rows=rows, number_format="0.000", banded=True, align_data="center")

    def R(col):
        return f"{col}{TS + 2}:{col}{last}"

    panel = [
        ("mean y", f"=AVERAGE({R('B')})"),                       # J4
        ("n", f"=COUNT({R('A')})"),                              # J5
        ("slope m", f"=(J5*SUM({R('D')})-SUM({R('A')})*SUM({R('B')}))/"
                    f"(J5*SUM({R('C')})-SUM({R('A')})*SUM({R('A')}))"),  # J6
        ("intercept c", f"=(SUM({R('B')})-J6*SUM({R('A')}))/J5"),  # J7
        ("SS resid", f"=SUM({R('F')})"),                          # J8
        ("SS total", f"=SUM({R('G')})"),                          # J9
        ("R²", "=1-J8/J9"),                                       # J10
    ]
    s.set(2, 8, "Least-squares fit")
    s.fmt(2, 8, bold=True, font_color=PALETTE["header"])
    for i, (lbl, expr) in enumerate(panel):
        s.set(3 + i, 8, lbl)
        s.formula(3 + i, 9, expr)
        s.fmt(3 + i, 9, bold=True, bg=PALETTE["band"], number_format="0.0000")
    s.box(3, 8, 9, 9, color=PALETTE["header"], width=1.0)
    s.col_width(8, 110)
    r0, r1 = TS + 1, TS + len(xs)
    xa = np.array(xs, dtype=float)
    ya = np.array(ys)
    m, c = np.polyfit(xa, ya, 1)
    s.chart([Series(xa, ya, "data", "Scatter", color=PALETTE["accent"],
                    marker="o", x_col=0, y_col=1, row_start=r0, row_end=r1),
             Series(xa, m * xa + c, "fit", "Line", color=PALETTE["header"],
                    x_col=0, y_col=4, row_start=r0, row_end=r1)],
            at=(560, 40), size=(440, 300), title="Linear Regression",
            xlabel="x", ylabel="y", legend=True)
    s.note(TS, 1, "Edit y values; slope, intercept, R² and fit update.",
           kind="note")
    _save(wb, "Regression Data.ksheet")


def statistics_sample():
    wb = Workbook(min_rows=44, min_cols=10)
    s = wb.add_sheet("Statistics")
    s.title_block("Statistics Sample",
                  "Descriptive statistics of a data set", span=6)
    data = [23, 45, 12, 67, 34, 89, 21, 56, 78, 43,
            38, 52, 29, 61, 47, 33, 70, 25, 58, 41]
    TS = 4
    last = TS + 1 + len(data)
    rows = [[i + 1, v] for i, v in enumerate(data)]
    s.table(TS, 0, headers=["#", "Value"], rows=rows,
            number_format="0", banded=True, align_data="center")
    rng = f"B{TS + 2}:B{last}"
    # NB: MEDIAN and VAR are in the catalog but unimplemented in the
    # engine; use STDEV and STDEV^2 for the spread instead.
    stats = [
        ("Count", f"=COUNT({rng})"), ("Sum", f"=SUM({rng})"),
        ("Mean", f"=AVERAGE({rng})"),
        ("Std dev (sample)", f"=STDEV({rng})"),
        ("Variance (sample)", f"=STDEV({rng})^2"),
        ("Min", f"=MIN({rng})"), ("Max", f"=MAX({rng})"),
        ("Range", f"=MAX({rng})-MIN({rng})"),
    ]
    s.set(3, 3, "Summary")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"])
    for i, (lbl, expr) in enumerate(stats):
        s.set(4 + i, 3, lbl)
        s.formula(4 + i, 4, expr)
        s.fmt(4 + i, 4, bold=True, bg=PALETTE["band"], number_format="0.00")
    s.box(4, 3, 11, 4, color=PALETTE["header"], width=1.0)
    s.col_width(3, 150)
    r0, r1 = TS + 1, TS + len(data)
    s.chart([Series(np.arange(1, len(data) + 1), np.array(data, dtype=float),
                    "Value", "Bar", color=PALETTE["header"],
                    y_col=1, row_start=r0, row_end=r1)],
            at=(560, 40), size=(440, 300), title="Sample Values",
            xlabel="#", ylabel="value", legend=False)
    _save(wb, "Statistics Sample.ksheet")


def build():
    os.makedirs(OUT, exist_ok=True)
    sine_cosine()
    quadratic_solver()
    matrix_operations()
    exponential_growth()
    regression_data()
    statistics_sample()
    print("Math templates written to", OUT)


if __name__ == "__main__":
    build()
