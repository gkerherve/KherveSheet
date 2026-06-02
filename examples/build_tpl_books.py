"""Build the "Book Collection" Daily Life template .ksheet.

A personal reading catalogue: enter Title, Author, Genre, Year, Pages,
Rating (1-5) and reading Status for each book.  The Summary panel
derives Total Books (COUNT of the numeric Rating column), Average Rating
(AVERAGE), Total Pages (SUM) and Longest Book (MAX) as live formulas.
An embedded Bar chart shows pages per book.  Status cells carry a
dropdown (To Read / Reading / Read).

Run:  python examples/build_tpl_books.py

Copyright (C) 2026 Gwilherm Kerherve -- GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

# Make project importable from any cwd.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402

# ── Sample books (users edit these in the sheet) ──────────────────────
# Columns: Title, Author, Genre, Year, Pages, Rating, Status
BOOKS = [
    ("The Pragmatic Programmer",  "Hunt & Thomas",    "Technology",   1999, 352, 5, "Read"),
    ("Sapiens",                   "Yuval Noah Harari","History",       2011, 443, 5, "Read"),
    ("Project Hail Mary",         "Andy Weir",        "Sci-Fi",        2021, 476, 5, "Read"),
    ("Atomic Habits",             "James Clear",      "Self-Help",     2018, 320, 4, "Read"),
    ("The Name of the Wind",      "Patrick Rothfuss", "Fantasy",       2007, 662, 4, "Reading"),
    ("Dune",                      "Frank Herbert",    "Sci-Fi",        1965, 688, 5, "Read"),
    ("Deep Work",                 "Cal Newport",      "Self-Help",     2016, 304, 4, "Read"),
    ("1984",                      "George Orwell",    "Fiction",       1949, 328, 5, "Read"),
    ("The Martian",               "Andy Weir",        "Sci-Fi",        2011, 369, 4, "Read"),
    ("Thinking, Fast and Slow",   "Daniel Kahneman",  "Psychology",    2011, 499, 4, "To Read"),
    ("Clean Code",                "Robert C. Martin", "Technology",    2008, 431, 4, "To Read"),
    ("The Hobbit",                "J.R.R. Tolkien",   "Fantasy",       1937, 310, 5, "Read"),
]

N = len(BOOKS)

# ── Status choices for dropdown ───────────────────────────────────────
STATUS_OPTIONS = ["To Read", "Reading", "Read"]


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=16)
    s = wb.add_sheet("Book Collection")

    # ── Column widths ─────────────────────────────────────────────────
    # Cols: 0=Title  1=Author  2=Genre  3=Year  4=Pages  5=Rating  6=Status
    s.col_width(0, 220)   # Title
    s.col_width(1, 160)   # Author
    s.col_width(2, 110)   # Genre
    s.col_width(3, 60)    # Year
    s.col_width(4, 70)    # Pages
    s.col_width(5, 75)    # Rating
    s.col_width(6, 90)    # Status

    # ── Table layout constants ────────────────────────────────────────
    # table() places:
    #   Header at 0-based row TABLE_START     → 1-based row TABLE_START+1
    #   Data k at 0-based row TABLE_START+1+k → 1-based row TABLE_START+2+k
    #
    # Rating column = col 5 → letter "F"
    # Pages  column = col 4 → letter "E"
    TABLE_START = 5   # 0-based header row

    DATA_1B_FIRST = TABLE_START + 2       # 1-based row of first data row = 7
    DATA_1B_LAST  = TABLE_START + 1 + N   # 1-based row of last  data row = 18

    # ── Title block ──────────────────────────────────────────────────
    s.title_block(
        "Book Collection",
        "Personal reading catalogue — edit Title, Author, Genre, Year, "
        "Pages, Rating and Status.  Summary and chart update automatically.",
        span=7,
    )

    # ── Instruction note ──────────────────────────────────────────────
    s.note(0, 8,
           "Add or edit rows in the table below.  "
           "Rating must be a number 1-5 so that COUNT, AVERAGE, SUM and MAX work.",
           kind="note")

    # ── Summary panel (right of table) ───────────────────────────────
    # Rating col = F  (1-based letter for col 5)
    # Pages  col = E  (1-based letter for col 4)
    SUMM_COL = 9

    s.set(2, SUMM_COL, "Reading Summary")
    s.fmt(2, SUMM_COL, bold=True, font_size=13, font_color=PALETTE["header"])
    s.merge(2, SUMM_COL, 1, 2)

    # Summary rows
    # Total Books = COUNT of the Rating column (numeric; ignores blanks & text)
    # Average Rating = AVERAGE of Rating column
    # Total Pages = SUM of Pages column
    # Longest Book = MAX of Pages column
    summary_rows = [
        ("Total Books",    f"=COUNT(F{DATA_1B_FIRST}:F{DATA_1B_LAST})",
         PALETTE["band"],  "0"),
        ("Avg Rating",     f"=IFERROR(AVERAGE(F{DATA_1B_FIRST}:F{DATA_1B_LAST}),0)",
         PALETTE["good"],  "0.00"),
        ("Total Pages",    f"=SUM(E{DATA_1B_FIRST}:E{DATA_1B_LAST})",
         PALETTE["band"],  "#,##0"),
        ("Longest Book",   f"=MAX(E{DATA_1B_FIRST}:E{DATA_1B_LAST})",
         PALETTE["warn"],  "#,##0"),
    ]

    for i, (lbl, expr, bg, nf) in enumerate(summary_rows):
        r = 3 + i
        s.set(r, SUMM_COL, lbl)
        s.formula(r, SUMM_COL + 1, expr)
        s.fmt(r, SUMM_COL, align="left")
        s.fmt(r, SUMM_COL + 1, bg=bg, align="right", bold=True, number_format=nf)

    s.box(3, SUMM_COL, 3 + len(summary_rows) - 1, SUMM_COL + 1,
          color=PALETTE["header"], width=1.0)
    s.col_width(SUMM_COL, 140)
    s.col_width(SUMM_COL + 1, 100)

    # ── Catalogue table ───────────────────────────────────────────────
    headers = [
        "Title", "Author", "Genre", "Year", "Pages", "Rating (1-5)", "Status",
    ]

    rows = []
    for k, (title, author, genre, year, pages, rating, status) in enumerate(BOOKS):
        # All columns are plain editable literals — no derived columns in the
        # catalogue itself.  Derivation happens in the Summary panel only.
        rows.append([title, author, genre, year, pages, rating, status])

    s.table(
        TABLE_START, 0,
        headers=headers,
        rows=rows,
        banded=True,
        align_data="right",
    )

    # Per-cell format overrides: text columns left-aligned, numerics right.
    for k in range(N):
        r = TABLE_START + 1 + k   # 0-based data row
        s.fmt(r, 0, align="left", wrap=False)   # Title
        s.fmt(r, 1, align="left")               # Author
        s.fmt(r, 2, align="left")               # Genre
        s.fmt(r, 3, align="center", number_format="0")   # Year
        s.fmt(r, 4, align="right",  number_format="#,##0")  # Pages
        s.fmt(r, 5, align="center", number_format="0",
              bg=PALETTE["band"])                # Rating (editable highlight)
        s.fmt(r, 6, align="left")               # Status

    # ── Status dropdowns ─────────────────────────────────────────────
    for k in range(N):
        r = TABLE_START + 1 + k   # 0-based data row
        s.dropdown(r, 6, STATUS_OPTIONS)

    # ── Rating column header note ─────────────────────────────────────
    s.note(TABLE_START, 5,
           "Rating must be a number (1-5). COUNT uses this column to "
           "count total books; blank rows are automatically ignored.",
           kind="note")

    # ── Status column note ────────────────────────────────────────────
    s.note(TABLE_START, 6,
           "Click any Status cell and choose from the dropdown: "
           "To Read / Reading / Read.",
           kind="note")

    # ── Column designations ───────────────────────────────────────────
    s.designate(4, "Y")   # Pages is the primary Y axis for the chart

    # ── Bar chart: Pages per book ─────────────────────────────────────
    # Data rows occupy 0-based rows TABLE_START+1 .. TABLE_START+N
    chart_row_start = TABLE_START + 1        # 0-based first data row = 6
    chart_row_end   = TABLE_START + N        # 0-based last  data row = 17

    # Initial render values — must match what the Pages column (col 4) holds.
    init_x = np.arange(N, dtype=float)
    init_pages = np.array([b[4] for b in BOOKS], dtype=float)

    s.chart(
        [
            Series(
                init_x, init_pages,
                label="Pages",
                plot_type="Bar",
                color="#4472c4",
                y_col=4,                     # 0-based column E (Pages)
                row_start=chart_row_start,
                row_end=chart_row_end,
            ),
        ],
        at=(10, 520),
        size=(540, 300),
        title="Pages per Book",
        xlabel="Book",
        ylabel="Pages",
        grid=True,
        legend=False,
    )

    # ── Rating chart ──────────────────────────────────────────────────
    init_ratings = np.array([b[5] for b in BOOKS], dtype=float)

    s.chart(
        [
            Series(
                init_x, init_ratings,
                label="Rating",
                plot_type="Bar",
                color="#ed7d31",
                y_col=5,                     # 0-based column F (Rating)
                row_start=chart_row_start,
                row_end=chart_row_end,
            ),
        ],
        at=(570, 520),
        size=(400, 300),
        title="Rating per Book",
        xlabel="Book",
        ylabel="Rating (1-5)",
        grid=True,
        legend=False,
    )

    # ── Equation: average rating formula ─────────────────────────────
    s.equation(
        r"\overline{R} = \frac{1}{N} \sum_{i=1}^{N} R_i",
        at=(10, 840),
        fontsize=18,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(260, 56),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Daily Life", "Book Collection.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
