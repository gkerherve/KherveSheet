"""Cell references: A1 ↔ indexes, cross-sheet refs, shifting formulas.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re

# ── Column letter helpers ────────────────────────────────────────────
def col_index_to_letter(idx: int) -> str:
    """0 → A, 1 → B, … 25 → Z, 26 → AA, 27 → AB, …"""
    result = ""
    while True:
        result = chr(ord('A') + idx % 26) + result
        idx = idx // 26 - 1
        if idx < 0:
            break
    return result


def letter_to_col_index(letters: str) -> int:
    """A → 0, B → 1, … Z → 25, AA → 26, AB → 27, …"""
    result = 0
    for ch in letters.upper():
        result = result * 26 + (ord(ch) - ord('A') + 1)
    return result - 1


# Cross-sheet reference token:  Sheet1!B5  or  'My Sheet'!A1:A10
# Group 1 = sheet name (quoted or bare), group 2 = the A1 / A1:B10 ref.
XREF_PATTERN = re.compile(
    r"(?:'([^']+)'|([A-Za-z_]\w*))\s*!\s*"
    r"(\$?[A-Za-z]{1,3}\$?\d{1,7}(?:\s*:\s*\$?[A-Za-z]{1,3}\$?\d{1,7})?)")


def quote_sheet_name(name: str) -> str:
    """Wrap a sheet name in single quotes if it isn't a bare identifier."""
    if re.fullmatch(r"[A-Za-z_]\w*", name or ""):
        return name
    return "'" + (name or "").replace("'", "") + "'"


def parse_a1(ref: str):
    """'B5' / '$B$5' → (col_index, row_index)."""
    m = re.fullmatch(r'\$?([A-Za-z]{1,3})\$?(\d{1,7})', ref.strip())
    return letter_to_col_index(m.group(1)), int(m.group(2)) - 1


def compile_xref(name: str, ref: str) -> str:
    """Build the runtime call for a cross-sheet ref: a single cell →
    ``_XC("Sheet", r, c)``; a range → ``_XRANGE("Sheet", c1, r1, c2, r2)``."""
    name_lit = repr(name)
    if ":" in ref:
        a, b = ref.split(":", 1)
        c1, r1 = parse_a1(a)
        c2, r2 = parse_a1(b)
        return f"_XRANGE({name_lit},{c1},{r1},{c2},{r2})"
    c, r = parse_a1(ref)
    return f"_XC({name_lit},{r},{c})"


def shift_formula(formula: str, d_row: int, d_col: int) -> str:
    """Shift cell references in *formula* by (d_row, d_col).

    Handles Excel-style absolute references:
      $A$1 — both fixed    $A1 — column fixed    A$1 — row fixed
      A1   — both relative
    """
    import re

    def _shift(m):
        dollar_col = m.group(1) or ""   # '$' or ''
        letters = m.group(2)
        dollar_row = m.group(3) or ""   # '$' or ''
        row_num = int(m.group(4))

        if not dollar_col:
            new_col = letter_to_col_index(letters) + d_col
            if new_col < 0:
                new_col = 0
            letters = col_index_to_letter(new_col)
        if not dollar_row:
            row_num += d_row
            if row_num < 1:
                row_num = 1

        return f"{dollar_col}{letters}{dollar_row}{row_num}"

    # Match optional $ before letters and optional $ before digits.
    return re.sub(
        r'(\$?)([A-Z]+)(\$?)(\d+)',
        _shift, formula, flags=re.IGNORECASE)
