"""Cell references in the Qt-free core, and the desktop sheet's use of them.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

import pytest

from khervesheet.core.refs import (
    col_index_to_letter, compile_xref, letter_to_col_index, parse_cell_refs,
    quote_sheet_name, shift_formula,
)


@pytest.mark.parametrize("index, letters", [
    (0, "A"), (25, "Z"), (26, "AA"), (49, "AX"), (701, "ZZ"), (702, "AAA"),
])
def test_column_letters_round_trip(index, letters):
    assert col_index_to_letter(index) == letters
    assert letter_to_col_index(letters) == index
    assert letter_to_col_index(letters.lower()) == index


def test_copied_formulas_shift_relative_references_only():
    assert shift_formula("=A1+$B$2+C$3+$D4", 2, 1) == "=B3+$B$2+D$3+$D6"
    assert shift_formula("=A1", -5, -5) == "=A1"      # clamped at A1


def test_references_a_formula_reads():
    assert parse_cell_refs("=SUM(A1:B2)+C3*2") == \
        [(0, 0), (0, 1), (1, 0), (1, 1), (2, 2)]
    # Other sheets' cells and function names are not local cells.
    assert parse_cell_refs("=Other!A1+LOG10(D4)") == [(3, 3)]


def test_cross_sheet_references():
    assert quote_sheet_name("Data") == "Data"
    assert quote_sheet_name("My Sheet") == "'My Sheet'"
    assert compile_xref("My Sheet", "B5") == "_XC('My Sheet',4,1)"
    assert compile_xref("S", "A1:B3") == "_XRANGE('S',0,0,1,2)"


def test_desktop_formula_highlighting_uses_the_core_patterns():
    pytest.importorskip("PyQt5.QtWidgets")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication
    from khervesheet.sheet import SheetWidget

    app = QApplication.instance() or QApplication([])  # noqa: F841
    tokens = SheetWidget()._parse_ref_tokens("=SUM(A1:B3)+C4*2")
    assert [t["text"] for t in tokens] == ["A1:B3", "C4"]
