"""Build "Password Strength.ksheet" — a Daily Life template.

This template is a polished Password Strength Reference: it shows how
entropy bits and the effective key-space grow as character-set choices
are added to a password of user-adjustable length.  Editing the length
cell (B5) immediately recalculates entropy and the chart.

Run:  python examples/build_tpl_password.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import math
import os

import numpy as np

# Make the project importable from anywhere.
import sys
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Design constants ──────────────────────────────────────────────────

DEFAULT_LENGTH = 12          # editable password length

# Character-set rows (label, pool size, description)
CHAR_SETS = [
    ("Lowercase only",        26, "a–z"),
    ("Lowercase + Digits",    36, "a–z, 0–9"),
    ("Mixed case + Digits",   62, "a–z, A–Z, 0–9"),
    ("Full (+ Symbols ~32)",  94, "a–z, A–Z, 0–9, !@#…"),
]

# Strength thresholds (entropy bits) for nested IF labels
# ≥128 → Excellent, ≥96 → Very Strong, ≥72 → Strong, ≥50 → Moderate, else Weak
STRENGTH_THRESHOLDS = [128, 96, 72, 50]
STRENGTH_LABELS = ["Excellent", "Very Strong", "Strong", "Moderate", "Weak"]


def _strength_label(bits: float) -> str:
    for thr, lbl in zip(STRENGTH_THRESHOLDS, STRENGTH_LABELS):
        if bits >= thr:
            return lbl
    return STRENGTH_LABELS[-1]


def _strength_color(label: str) -> str:
    return {
        "Excellent":    PALETTE["good"],
        "Very Strong":  PALETTE["good"],
        "Strong":       PALETTE["band"],
        "Moderate":     PALETTE["warn"],
        "Weak":         PALETTE["bad"],
    }.get(label, "#ffffff")


def build() -> str:
    wb = Workbook(min_rows=44, min_cols=14)
    s = wb.add_sheet("Password Strength")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 200)  # A: labels
    s.col_width(1, 100)  # B: pool size / values
    s.col_width(2, 130)  # C: character set description
    s.col_width(3, 120)  # D: combinations (log10 display)
    s.col_width(4, 110)  # E: entropy bits
    s.col_width(5, 110)  # F: strength label

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Password Strength Reference",
        "How entropy bits and key-space grow with character-set choice",
        row=0, col=0, span=7,
    )

    # ── Input panel: editable password length (row 3–5) ───────────────
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    s.set(4, 0, "Password length (characters)")
    s.set(4, 1, DEFAULT_LENGTH)          # editable — sheet cell B5
    s.fmt(4, 1, bg=PALETTE["warn"], align="center",
          number_format="0", bold=True)
    s.fmt(4, 0, align="left")
    s.box(4, 0, 4, 1, color=PALETTE["accent"], width=1.2)

    # Yellow note next to the length cell
    s.note(4, 1,
           "Edit this cell to change the password length. "
           "All entropy values and the chart update automatically.",
           kind="note")

    # ── Formula key (row 6 — small reference) ─────────────────────────
    s.set(6, 0, "Entropy formula:")
    s.fmt(6, 0, italic=True, font_color="#555555")
    s.set(6, 1, "bits = length × log₂(pool size)")
    s.fmt(6, 1, italic=True, font_color="#555555")
    s.merge(6, 1, 1, 3)

    # ── Section heading for the table ─────────────────────────────────
    s.set(7, 0, "Character-Set Analysis")
    s.fmt(7, 0, bold=True, font_color=PALETTE["header"])
    s.merge(7, 0, 1, 6)

    # ── Data table ────────────────────────────────────────────────────
    #
    # Layout (0-based indices):
    #   col 0: Character Set label
    #   col 1: Pool size  (literal — independent variable)
    #   col 2: Description
    #   col 3: log10(combinations) — formula referencing B5 and col 1
    #   col 4: Entropy bits        — formula referencing B5 and col 1
    #   col 5: Strength label      — nested IF on col 4
    #
    # table() starts at start_row=8.
    # Header sits at 0-based row 8 (sheet row 9).
    # First data row is 0-based row 9 (sheet row 10).

    TABLE_START = 8

    headers = [
        "Character Set",
        "Pool Size",
        "Description",
        "log₁₀(Combinations)",
        "Entropy (bits)",
        "Strength",
    ]

    n_rows = len(CHAR_SETS)

    # Build rows with live formulas.
    # The pool-size column (col 1 = B) holds a literal; the formula
    # columns reference $B$5 (length) and the pool-size cell in that row.
    table_rows = []
    for i, (label, pool, desc) in enumerate(CHAR_SETS):
        # 1-based sheet row for this data row
        rr = TABLE_START + 2 + i   # header at TABLE_START+1, data starts TABLE_START+2

        # log10(pool^length) = length * log10(pool)
        log10_comb_formula = f"=$B$5*LOG10(B{rr})"

        # entropy bits = length * log2(pool) = length * LOG(pool, 2)
        entropy_formula = f"=$B$5*LOG(B{rr},2)"

        # Nested IF for strength label — uses entropy cell D{rr}
        # (col 4 is E; col 3 is D; 0-indexed col 4 → sheet col E)
        # Entropy is in col 4 (0-based) = sheet column E
        ent_cell = f"E{rr}"
        strength_formula = (
            f"=IF({ent_cell}>=128,\"Excellent\","
            f"IF({ent_cell}>=96,\"Very Strong\","
            f"IF({ent_cell}>=72,\"Strong\","
            f"IF({ent_cell}>=50,\"Moderate\",\"Weak\"))))"
        )

        table_rows.append([
            label,
            pool,          # literal pool size
            desc,
            log10_comb_formula,
            entropy_formula,
            strength_formula,
        ])

    s.table(
        TABLE_START, 0,
        headers=headers,
        rows=table_rows,
        number_format="0.00",
        banded=True,
    )

    # Override alignment: col 0 (labels) already left by table(); also
    # make col 2 (description) left-aligned.
    for i in range(n_rows):
        r = TABLE_START + 1 + i
        s.fmt(r, 2, align="left")

    # Colour-code the strength column (col 5) per computed value
    for i, (label, pool, _desc) in enumerate(CHAR_SETS):
        bits = DEFAULT_LENGTH * math.log2(pool)
        lbl = _strength_label(bits)
        r = TABLE_START + 1 + i
        s.fmt(r, 5, bg=_strength_color(lbl), bold=True, align="center")

    # ── Summary panel ─────────────────────────────────────────────────
    # Placed to the right of the table (col 8 onwards).
    # Uses MAX / MIN over the entropy column.

    # 1-based row range of the data rows
    data_first_sheet_row = TABLE_START + 2        # sheet row (1-based)
    data_last_sheet_row  = TABLE_START + 1 + n_rows

    SUMM_COL = 8
    s.set(TABLE_START - 1, SUMM_COL, "Summary")
    s.fmt(TABLE_START - 1, SUMM_COL, bold=True, font_color=PALETTE["header"])

    entropy_range = f"E{data_first_sheet_row}:E{data_last_sheet_row}"
    summary_items = [
        ("Min entropy (bits)",
         f"=MIN({entropy_range})", PALETTE["bad"]),
        ("Max entropy (bits)",
         f"=MAX({entropy_range})", PALETTE["good"]),
        ("Avg entropy (bits)",
         f"=AVERAGE({entropy_range})", PALETTE["band"]),
    ]
    for j, (lbl, expr, col) in enumerate(summary_items):
        r = TABLE_START + j
        s.set(r, SUMM_COL, lbl)
        s.formula(r, SUMM_COL + 1, expr)
        s.fmt(r, SUMM_COL, align="left")
        s.fmt(r, SUMM_COL + 1, bg=col, align="center",
              number_format="0.00", bold=True)

    s.box(TABLE_START, SUMM_COL,
          TABLE_START + len(summary_items) - 1, SUMM_COL + 1,
          color=PALETTE["header"], width=1.0)
    s.col_width(SUMM_COL, 160)
    s.col_width(SUMM_COL + 1, 90)

    # ── Designate columns for the chart ───────────────────────────────
    # Col 0 (A) = X labels, col 4 (E) = entropy bits Y
    s.designate(0, "X")
    s.designate(4, "Y")

    # ── Chart: Bar chart of entropy bits vs character-set ─────────────
    # Compute initial render values to match what the formula cells produce.
    pool_sizes = [cs[1] for cs in CHAR_SETS]
    entropy_values = [DEFAULT_LENGTH * math.log2(p) for p in pool_sizes]

    # x indices 0..3 (bar chart uses integer x-axis positions)
    x_idx = np.arange(len(CHAR_SETS), dtype=float)
    y_ent = np.array(entropy_values, dtype=float)

    # Data rows are 0-based rows TABLE_START+1 .. TABLE_START+n_rows
    row_start_0 = TABLE_START + 1
    row_end_0   = TABLE_START + n_rows

    s.chart(
        [Series(x_idx, y_ent, "Entropy (bits)", "Bar",
                color=PALETTE["header"],
                y_col=4,           # col 4 = E (entropy bits)
                row_start=row_start_0,
                row_end=row_end_0)],
        at=(520, 30),
        size=(440, 300),
        title="Password Entropy by Character Set",
        xlabel="Character Set (row index)",
        ylabel="Entropy (bits)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation ─────────────────────────────────────────────────
    # H = L \times \log_2(N)
    s.equation(
        r"H = L \times \log_{2}(N)",
        at=(520, 348),
        fontsize=22,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(240, 52),
    )

    # Small legend below the equation
    s.set(TABLE_START + n_rows + 3, 8,
          "H = entropy (bits), L = length, N = pool size")
    s.fmt(TABLE_START + n_rows + 3, 8,
          italic=True, font_color="#555555")
    s.merge(TABLE_START + n_rows + 3, 8, 1, 4)

    # ── Yellow notes ──────────────────────────────────────────────────
    s.note(0, 8,
           "This sheet estimates theoretical strength based on random "
           "uniform selection. It does NOT generate passwords. "
           "Never store real passwords in a spreadsheet.",
           kind="note")

    s.note(TABLE_START + 1, 5,
           "Strength labels update when you change the length in B5. "
           "Colours here are fixed at authoring time; the label text is live.",
           kind="note")

    s.note(TABLE_START + 1, 3,
           "log₁₀(Combinations) = length × log₁₀(pool). "
           "This is the exponent: actual combinations = 10^(this value).",
           kind="note")

    # ── Save ─────────────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Daily Life",
    )
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "Password Strength.ksheet")
    wb.save(out_path)
    return out_path


if __name__ == "__main__":
    print("Wrote", build())
