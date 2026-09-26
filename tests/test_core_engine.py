"""The Qt-free engine (khervesheet.core) computes what the desktop sheet
computes: the golden formulas, and cell-by-cell after the same typing.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from formula_corpus import DATA, FORMULAS  # noqa: E402

from khervesheet.core.engine import (  # noqa: E402
    DEFAULT_COLS, DEFAULT_ROWS, PYTHON_NOT_RUN, Workbook,
)

GOLDEN = Path(__file__).with_name("data") / "formula_golden.json"
TARGET = (60, 20)
ROOT = Path(__file__).resolve().parents[1]


def typed_workbook():
    """The corpus data typed in cell by cell, as the golden test's desktop
    sheet receives it (each value goes through the typing path)."""
    wb = Workbook()
    for name, cells in DATA.items():
        sheet = wb.add_sheet(name)
        for (row, col), text in cells.items():
            sheet.set_cell(row, col, text)
    return wb


def test_engine_matches_the_golden_formulas():
    sheet = typed_workbook().sheet_by_name("Data")
    results = {}
    for formula in FORMULAS:
        value = sheet._evaluate_formula(formula, *TARGET)
        results[formula] = value if isinstance(value, (int, float)) \
            else str(value)
    assert results == json.loads(GOLDEN.read_text())


def test_core_runs_without_qt():
    code = (
        "import sys, importlib.abc\n"
        "class Block(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, name, path, target=None):\n"
        "        if name.startswith(('PyQt5', 'PyQt6', 'PySide')):\n"
        "            raise ImportError(name)\n"
        "sys.meta_path.insert(0, Block())\n"
        "from khervesheet.core.engine import Workbook\n"
        "wb = Workbook(); s = wb.add_sheet('S')\n"
        "s.set_cell(0, 0, '2'); s.set_cell(0, 1, '=A1*21')\n"
        "print(s.text(0, 1))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "42.00"


def test_loading_keeps_saved_values_and_computes_formulas():
    wb = Workbook()
    wb.load({"S": {(0, 0): "1.8333", (1, 0): "=A1*3", (2, 0): "=A2+1",
                   (3, 0): "=PY\nx = 1"}})
    s = wb.sheet_by_name("S")
    assert s.text(0, 0) == "1.8333"       # values load as saved
    assert s.text(1, 0) == "5.5"
    assert s.text(2, 0) == "6.5"
    assert s.text(3, 0) == PYTHON_NOT_RUN


def test_new_sheets_are_excel_sized():
    sheet = Workbook().add_sheet()
    assert (sheet.rows, sheet.cols) == (DEFAULT_ROWS, DEFAULT_COLS) \
        == (5000, 50)
    assert sheet.name == "Sheet1"


def test_typing_recalculates_dependents_in_order():
    wb = Workbook()
    s = wb.add_sheet("S")
    s.set_cell(0, 0, "1")
    s.set_cell(1, 0, "=A1*2")
    s.set_cell(2, 0, "=A2+A1")
    s.set_cell(3, 0, "=SUM(A1:A3)")
    changes = s.set_cell(0, 0, "10")
    assert [s.text(r, 0) for r in range(4)] == \
        ["10.00", "20.00", "30.00", "60.00"]
    # Every changed cell reported once, with its new text.
    assert sorted(changes) == [("S", 0, 0, "10.00"), ("S", 1, 0, "20.00"),
                               ("S", 2, 0, "30.00"), ("S", 3, 0, "60.00")]


def test_cross_sheet_formulas_follow_their_source():
    wb = Workbook()
    a = wb.add_sheet("Data")
    b = wb.add_sheet("Results")
    a.set_cell(0, 0, "3")
    b.set_cell(0, 0, "=Data!A1*2")
    changes = a.set_cell(0, 0, "4")
    assert b.text(0, 0) == "8.00"
    assert ("Results", 0, 0, "8.00") in changes


def test_clearing_a_cell():
    s = Workbook().add_sheet("S")
    s.set_cell(0, 0, "5")
    s.set_cell(0, 1, "=A1+1")
    s.set_cell(0, 0, "")
    assert (s.source(0, 0), s.text(0, 0)) == ("", "")
    assert s.text(0, 1) == "1.00"


def test_formulas_read_full_precision_not_the_rounded_text():
    s = Workbook().add_sheet("S")
    s.set_cell(0, 0, "=1/3")
    s.set_cell(0, 1, "=A1*3")
    assert s.text(0, 0) == "0.33" and s.text(0, 1) == "1.00"
    s.set_cell(1, 0, "2.718281828")
    s.set_cell(1, 1, "=A2*1000000")
    assert s.text(1, 1) == "2718281.83"
    # A cell rewritten without its exact value falls back to its text.
    s.texts[(0, 0)] = "0.5"
    s.set_cell(0, 1, "=A1*3")
    assert s.text(0, 1) == "1.50"


def test_python_cells_need_the_marker_alone():
    s = Workbook().add_sheet("S")
    s.set_cell(0, 0, "=PYTHAGORAS(3,4)")
    assert s.text(0, 0) == "#NAME?"
    s.set_cell(0, 1, "=PY 1+1")
    assert s.text(0, 1) == PYTHON_NOT_RUN


def test_python_cells_are_kept_but_not_run():
    s = Workbook().add_sheet("S")
    s.set_cell(0, 0, "=PY\nimport os")
    assert s.text(0, 0) == PYTHON_NOT_RUN
    assert s.source(0, 0) == "=PY\nimport os"


def test_number_formats():
    s = Workbook().add_sheet("S")
    s.set_cell(0, 0, "3.14159")
    s.set_number_format(0, 0, "0.0")
    assert s.text(0, 0) == "3.1"
    s.set_number_format(0, 0, "Text")
    assert s.text(0, 0) == "3.142"        # shown as typed, 3 decimals
    s.column_formats[1] = "0.000"
    s.set_cell(0, 1, "=1/3")
    assert s.text(0, 1) == "0.333"


def test_sheets_can_be_renamed_and_removed():
    wb = Workbook()
    a = wb.add_sheet("Data")
    b = wb.add_sheet("Results")
    a.set_cell(0, 0, "7")
    b.set_cell(0, 0, "=Data!A1")
    wb.rename_sheet("Data", "Raw")
    assert b.text(0, 0) == "0.00"         # the reference now points nowhere
    with pytest.raises(ValueError):
        wb.add_sheet("results")
    wb.remove_sheet("Raw")
    assert wb.sheet_names() == ["Results"]


# ── Side by side with the desktop sheet ──────────────────────────────
SCRIPT = [
    ("Data", 0, 0, "5"), ("Data", 1, 0, "7.25"), ("Data", 2, 0, "=A1+A2"),
    ("Data", 3, 0, "=SUM(A1:A3)"), ("Data", 0, 1, "hello"),
    ("Data", 1, 1, "=UPPER(B1)"), ("Data", 2, 1, "=LEN(B1)*A1"),
    ("Other", 0, 0, "=Data!A4/2"), ("Other", 1, 0, "=A1+Data!A1"),
    ("Data", 0, 0, "11"), ("Data", 4, 0, "=AVERAGE(A1:A4)"),
    ("Data", 5, 0, "=IF(A5>10,\"big\",\"small\")"), ("Data", 1, 0, ""),
    ("Data", 6, 0, "TRUE"), ("Data", 7, 0, "=A7+1"), ("Data", 8, 0, "="),
    ("Data", 0, 2, "0.1"), ("Data", 1, 2, "=C1*3"), ("Data", 2, 2, "=C2*C2"),
    ("Other", 2, 0, "=SUM(Data!A1:A3)"), ("Data", 2, 0, "100"),
    # Full precision behind rounded cells, and Excel syntax
    ("Data", 0, 3, "=1/3"), ("Data", 1, 3, "=D1*3"), ("Data", 2, 3, "0.123456"),
    ("Data", 3, 3, "=D3*1000"), ("Data", 4, 3, "=IF(D2=1,\"exact\",\"rounded\")"),
    ("Data", 5, 3, "=B1&\"!\""), ("Data", 6, 3, "=IFERROR(B1*2,\"text\")"),
]


@pytest.fixture
def desktop():
    pytest.importorskip("PyQt5.QtWidgets")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication
    from khervesheet.workbook import WorkbookWidget

    app = QApplication.instance() or QApplication([])  # noqa: F841
    wb = WorkbookWidget()
    sheets = wb.all_sheets()
    for index, name in enumerate(["Data", "Other"]):
        wb.tabs.setTabText(wb.tabs.indexOf(sheets[index]), name)
    yield wb
    wb.deleteLater()


def desktop_type(sheet, row, col, text):
    from PyQt5.QtWidgets import QTableWidgetItem
    table = sheet.table
    table.blockSignals(True)
    item = table.item(row, col)
    if item is None:
        item = QTableWidgetItem(text)
        table.setItem(row, col, item)
    else:
        item.setText(text)
    table.blockSignals(False)
    sheet._on_cell_changed(row, col)


def test_same_texts_as_the_desktop_after_the_same_typing(desktop):
    engine = Workbook()
    for name in ("Data", "Other"):
        engine.add_sheet(name)
    for step, (name, row, col, text) in enumerate(SCRIPT):
        desktop_type(desktop.sheet_by_name(name), row, col, text)
        engine.sheet_by_name(name).set_cell(row, col, text)
        for sheet_name in ("Data", "Other"):
            d = desktop.sheet_by_name(sheet_name)
            e = engine.sheet_by_name(sheet_name)
            for r in range(10):
                for c in range(4):
                    item = d.table.item(r, c)
                    expected = item.text() if item is not None else ""
                    assert e.text(r, c) == expected, (
                        f"after step {step} {SCRIPT[step]}: "
                        f"{sheet_name}!{r},{c}")
