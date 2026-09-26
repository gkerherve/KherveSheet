"""Formula results must not change while the engine is refactored.

tests/data/formula_golden.json records what the desktop sheet computes
for every formula in formula_corpus.  Regenerate it only for an intended
change:  KHERVESHEET_WRITE_GOLDEN=1 pytest tests/test_formula_golden.py

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PyQt5.QtWidgets")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).parent))
from formula_corpus import DATA, FORMULAS  # noqa: E402

GOLDEN = Path(__file__).with_name("data") / "formula_golden.json"
TARGET = (60, 20)   # an empty cell far from the data (room to spill)


@pytest.fixture(scope="module")
def workbook():
    from PyQt5.QtWidgets import QApplication, QTableWidgetItem
    from khervesheet.workbook import WorkbookWidget

    app = QApplication.instance() or QApplication([])  # noqa: F841
    wb = WorkbookWidget()
    names = list(DATA)
    sheets = wb.all_sheets()
    while len(sheets) < len(names):
        sheets.append(wb.add_sheet())
    for index, name in enumerate(names):
        sheet = sheets[index]
        wb.tabs.setTabText(wb.tabs.indexOf(sheet), name)
        sheet.table.setRowCount(max(sheet.table.rowCount(), 120))
        sheet.table.setColumnCount(max(sheet.table.columnCount(), 30))
        for (row, col), text in DATA[name].items():
            sheet.table.setItem(row, col, QTableWidgetItem(text))
    yield wb
    wb.deleteLater()


def evaluate_all(sheet):
    results = {}
    for formula in FORMULAS:
        value = sheet._evaluate_formula(formula, *TARGET)
        results[formula] = value if isinstance(value, (int, float)) \
            else str(value)
    return results


def test_formula_results_are_unchanged(workbook):
    results = evaluate_all(workbook.sheet_by_name("Data"))
    if os.environ.get("KHERVESHEET_WRITE_GOLDEN"):
        GOLDEN.write_text(json.dumps(results, indent=1, ensure_ascii=False))
    golden = json.loads(GOLDEN.read_text())
    assert results == golden
