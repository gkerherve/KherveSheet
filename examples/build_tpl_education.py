"""Build the rich Education template set (examples/templates/Education/).

Grade Book, Multiplication Table, Fibonacci Sequence, Prime Numbers,
Hex/Dec/Binary, ASCII Table.

Run:  python examples/build_tpl_education.py
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
                   "templates", "Education")


def _save(wb, name):
    wb.save(os.path.join(OUT, name))


def grade_book():
    wb = Workbook(min_rows=36, min_cols=12)
    s = wb.add_sheet("Grades")
    s.title_block("Grade Book",
                  "Test scores with averages and letter grades", span=8)
    students = [
        ("Alice", 82, 88, 91), ("Ben", 74, 69, 80),
        ("Chloe", 95, 92, 98), ("Daniel", 61, 58, 70),
        ("Ella", 88, 84, 79), ("Femi", 70, 75, 72),
        ("Grace", 99, 95, 100), ("Henry", 55, 62, 49),
    ]
    TS = 4
    rows = []
    for i, (nm, t1, t2, t3) in enumerate(students):
        sr = TS + 2 + i
        rows.append([nm, t1, t2, t3, f"=AVERAGE(B{sr}:D{sr})",
                     (f'=IF(E{sr}>=90,"A",IF(E{sr}>=80,"B",'
                      f'IF(E{sr}>=70,"C",IF(E{sr}>=60,"D","F"))))')])
    s.table(TS, 0, headers=["Student", "Test 1", "Test 2", "Test 3",
                            "Average", "Grade"],
            rows=rows, number_format="0.0", banded=True, align_data="center")
    for i in range(len(students)):
        s.fmt(TS + 1 + i, 0, align="left")
    last = TS + 1 + len(students)
    s.set(last + 1, 0, "Class average")
    s.fmt(last + 1, 0, bold=True)
    s.formula(last + 1, 4, f"=AVERAGE(E{TS + 2}:E{last})")
    s.fmt(last + 1, 4, bold=True, bg=PALETTE["good"], number_format="0.0")
    r0, r1 = TS + 1, TS + len(students)
    s.chart([Series(np.arange(len(students)),
                    np.array([(a + b + c) / 3 for _, a, b, c in students]),
                    "Average", "Bar", color=PALETTE["header"],
                    y_col=4, row_start=r0, row_end=r1)],
            at=(620, 40), size=(420, 300), title="Average Score by Student",
            xlabel="Student", ylabel="Score", legend=False)
    s.note(TS, 1, "Edit the test scores; Average and Grade recompute.",
           kind="note")
    _save(wb, "Grade Book.ksheet")


def multiplication_table():
    wb = Workbook(min_rows=20, min_cols=16)
    s = wb.add_sheet("Times Table")
    s.title_block("Multiplication Table",
                  "12 x 12 — every cell is a live product", span=8)
    HR = 4  # 0-based row of the column-header band; 1-based = HR+1
    n = 12
    s.set(HR, 0, "×")
    s.fmt(HR, 0, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    for j in range(1, n + 1):
        s.set(HR, j, j)
        s.fmt(HR, j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
        s.set(HR + j, 0, j)
        s.fmt(HR + j, 0, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    hr1 = HR + 1  # 1-based header row
    for i in range(1, n + 1):
        sr = HR + i + 1  # 1-based sheet row of this body row
        for j in range(1, n + 1):
            colL = chr(ord("A") + j)
            s.formula(HR + i, j, f"=$A{sr}*{colL}${hr1}")
            s.fmt(HR + i, j, align="center",
                  bg=(PALETTE["band_alt"] if (i + j) % 2 else None))
    s.box(HR, 0, HR + n, n, color=PALETTE["header"], width=1.0)
    for c in range(n + 1):
        s.col_width(c, 44)
    _save(wb, "Multiplication Table.ksheet")


def fibonacci():
    wb = Workbook(min_rows=36, min_cols=10)
    s = wb.add_sheet("Fibonacci")
    s.title_block("Fibonacci Sequence",
                  "F(n) = F(n-1) + F(n-2); ratio -> golden ratio", span=6)
    TS = 4
    n_terms = 20
    rows = []
    for i in range(n_terms):
        sr = TS + 2 + i
        nidx = i + 1
        if i == 0:
            fexpr, rexpr = "1", ""
        elif i == 1:
            fexpr, rexpr = "1", f"=B{sr}/B{sr - 1}"
        else:
            fexpr = f"=B{sr - 1}+B{sr - 2}"
            rexpr = f"=B{sr}/B{sr - 1}"
        rows.append([nidx, fexpr, rexpr])
    s.table(TS, 0, headers=["n", "F(n)", "F(n)/F(n-1)"],
            rows=rows, number_format="0", banded=True, align_data="center")
    # ratio column nicer format
    for i in range(n_terms):
        s.fmt(TS + 1 + i, 2, number_format="0.000000", align="center")
    r0, r1 = TS + 1, TS + n_terms
    s.chart([Series(np.arange(1, n_terms + 1),
                    np.array([1, 1] + [0] * (n_terms - 2), dtype=float),
                    "F(n)", "Line+Symbol", color=PALETTE["header"],
                    marker="o", x_col=0, y_col=1, row_start=r0, row_end=r1)],
            at=(440, 40), size=(440, 300), title="Fibonacci Growth",
            xlabel="n", ylabel="F(n)", legend=False)
    s.note(TS, 2, "The ratio converges to the golden ratio 1.6180339...",
           kind="note")
    _save(wb, "Fibonacci Sequence.ksheet")


def _primes(count):
    out, k = [], 2
    while len(out) < count:
        if all(k % p for p in out if p * p <= k):
            out.append(k)
        k += 1
    return out


def prime_numbers():
    wb = Workbook(min_rows=40, min_cols=8)
    s = wb.add_sheet("Primes")
    s.title_block("Prime Numbers",
                  "The first 30 primes and the gaps between them", span=5)
    primes = _primes(30)
    TS = 4
    rows = []
    for i, p in enumerate(primes):
        sr = TS + 2 + i
        gap = "" if i == 0 else f"=B{sr}-B{sr - 1}"
        rows.append([i + 1, p, gap])
    s.table(TS, 0, headers=["Index", "Prime", "Gap"],
            rows=rows, number_format="0", banded=True, align_data="center")
    r0, r1 = TS + 1, TS + len(primes)
    gaps = [0] + [primes[i] - primes[i - 1] for i in range(1, len(primes))]
    s.chart([Series(np.array(primes, dtype=float), np.array(gaps, dtype=float),
                    "Gap", "Bar", color=PALETTE["accent"],
                    x_col=1, y_col=2, row_start=r0, row_end=r1)],
            at=(420, 40), size=(440, 300), title="Prime Gaps",
            xlabel="Prime", ylabel="Gap to previous", legend=False)
    _save(wb, "Prime Numbers.ksheet")


def hex_dec_bin():
    wb = Workbook(min_rows=44, min_cols=8)
    s = wb.add_sheet("Number Bases")
    s.title_block("Hex / Dec / Binary",
                  "Decimal 0-31 in three bases (reference)", span=5)
    TS = 4
    rows = [[d, format(d, "X"), format(d, "05b"), format(d, "o")]
            for d in range(32)]
    s.table(TS, 0, headers=["Decimal", "Hex", "Binary", "Octal"],
            rows=rows, number_format="0", banded=True, align_data="center")
    s.note(TS, 1, "A reference table; values are fixed conversions.",
           kind="note")
    _save(wb, "Hex Dec Binary.ksheet")


def ascii_table():
    wb = Workbook(min_rows=110, min_cols=8)
    s = wb.add_sheet("ASCII")
    s.title_block("ASCII Table",
                  "Printable characters 32-126 (reference)", span=5)
    TS = 4
    headers = ["Code", "Char", "Hex", "Binary"]
    for j, h in enumerate(headers):
        s.set(TS, j, h)
        s.fmt(TS, j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    # Build the body with set() only, so a char like '=' is never parsed
    # as a formula (table() would treat a leading '=' as a formula).
    for i, c in enumerate(range(32, 127)):
        r = TS + 1 + i
        # '=' (code 61) cannot be stored as a literal cell — the .ksheet
        # format reads a leading '=' as a formula — so name it instead.
        ch = {32: "(space)", 61: "(equals)"}.get(c, chr(c))
        vals = [c, ch, format(c, "X"), format(c, "08b")]
        band = PALETTE["band_alt"] if i % 2 else None
        for j, v in enumerate(vals):
            s.set(r, j, v)
            s.fmt(r, j, align="center", bg=band)
    s.box(TS, 0, TS + 95, 3, color=PALETTE["header"], width=1.0)
    for c in range(4):
        s.col_width(c, 80)
    _save(wb, "ASCII Table.ksheet")


def build():
    os.makedirs(OUT, exist_ok=True)
    grade_book()
    multiplication_table()
    fibonacci()
    prime_numbers()
    hex_dec_bin()
    ascii_table()
    print("Education templates written to", OUT)


if __name__ == "__main__":
    build()
