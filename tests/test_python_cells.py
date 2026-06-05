"""Tests for the Python-in-cell (=PY) engine.

Engine-level tests exercise PythonRuntime directly (last-expression value,
shared namespace, value classification, errors).  The integration test
drives a real SheetWidget through a =PY cell to cover xl() resolution,
array spill, live-object storage and dependency recalculation.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from khervesheet.python_engine import (  # noqa: E402
    PyResult, PythonRuntime, badge_for, extract_refs, is_python_source,
    strip_marker,
)


# ── Marker / helper functions ────────────────────────────────────────

def test_is_python_source():
    assert is_python_source("=PY\nx = 1")
    assert is_python_source("=py 2+2")
    assert not is_python_source("=SUM(A1:A2)")
    assert not is_python_source("hello")
    assert not is_python_source(None)


def test_strip_marker():
    assert strip_marker("=PY\nfoo") == "foo"
    assert strip_marker("=PY bar") == "bar"
    assert strip_marker("=py\nx = 1\ny = 2") == "x = 1\ny = 2"


def test_extract_refs():
    refs = extract_refs('xl("A1") + cell(\'B2:C3\') + xl("Sheet1!D4")')
    assert refs == ["A1", "B2:C3", "Sheet1!D4"]


# ── PythonRuntime ────────────────────────────────────────────────────

def test_last_expression_value():
    rt = PythonRuntime()
    assert rt.run("2 ** 10", None, 0, 0).value == 1024


def test_statement_only_returns_none():
    rt = PythonRuntime()
    res = rt.run("x = 5", None, 0, 0)
    assert res.kind == PyResult.NONE
    assert res.value is None


def test_shared_namespace_across_cells():
    rt = PythonRuntime()
    rt.run("def sq(x):\n    return x * x", None, 0, 0)
    assert rt.run("sq(9)", None, 0, 0).value == 81


def test_reset_clears_namespace():
    rt = PythonRuntime()
    rt.run("token = 123", None, 0, 0)
    assert rt.run("token", None, 0, 0).value == 123
    rt.reset()
    assert not rt.run("token", None, 0, 0).ok


def test_list_classified_as_array():
    rt = PythonRuntime()
    res = rt.run("[1, 2, 3]", None, 0, 0)
    assert res.kind == PyResult.ARRAY1D
    assert res.value == [1, 2, 3]


def test_nested_list_is_2d():
    rt = PythonRuntime()
    res = rt.run("[[1, 2], [3, 4]]", None, 0, 0)
    assert res.kind == PyResult.ARRAY2D


def test_ndarray_is_object_not_spilled():
    rt = PythonRuntime()
    res = rt.run("import numpy as np\nnp.arange(5)", None, 0, 0)
    assert res.kind == PyResult.OBJECT
    assert isinstance(res.value, np.ndarray)


def test_figure_capture_without_return():
    rt = PythonRuntime()
    res = rt.run(
        "import matplotlib.pyplot as plt\n"
        "fig, ax = plt.subplots()\nax.plot([1, 2, 3])",
        None, 0, 0)
    assert res.kind == PyResult.FIGURE
    assert res.figure is not None


def test_error_is_captured():
    rt = PythonRuntime()
    res = rt.run("1 / 0", None, 0, 0)
    assert not res.ok
    assert "ZeroDivisionError" in res.error


def test_badge_for():
    assert badge_for(np.arange(7)).startswith("▮ ndarray(7,)")
    assert "dict" in badge_for({"a": 1})


# ── Integration via a real SheetWidget ───────────────────────────────

@pytest.fixture(scope="module")
def qapp():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _put(sheet, r, c, text):
    from PyQt5.QtWidgets import QTableWidgetItem
    sheet.table.blockSignals(True)
    it = sheet.table.item(r, c)
    if it is None:
        it = QTableWidgetItem()
        sheet.table.setItem(r, c, it)
    it.setText(text)
    sheet.table.blockSignals(False)
    sheet._on_cell_changed(r, c)


def test_sheet_xl_spill_object_recalc(qapp):
    from khervesheet.workbook import WorkbookWidget
    wb = WorkbookWidget()
    s = wb.tabs.widget(0)

    for i in range(5):
        _put(s, i, 0, str(i + 1))            # A1:A5 = 1..5

    # xl() over a range, builtin sum.
    _put(s, 0, 1, '=PY\nsum(xl("A1:A5"))')
    assert s.table.item(0, 1).text() == "15"

    # Shared namespace: define then use.
    _put(s, 0, 2, "=PY\ndef sq(x):\n    return x * x")
    _put(s, 0, 3, "=PY\nsq(8)")
    assert s.table.item(0, 3).text() == "64"

    # ndarray held live in the cell, referenced from another cell.
    _put(s, 0, 4, "=PY\nimport numpy as np\nnp.arange(5)")
    assert s.table.item(0, 4).text().startswith("▮ ndarray")
    _put(s, 0, 5, '=PY\nint(xl("E1").sum())')
    assert s.table.item(0, 5).text() == "10"

    # List spills down the column.
    _put(s, 0, 6, "=PY\n[10, 20, 30]")
    assert s.table.item(0, 6).text() == "10"
    assert s.table.item(1, 6).text() == "20"
    assert s.table.item(2, 6).text() == "30"

    # Dependency recalc when a referenced cell changes.
    _put(s, 0, 0, "100")
    s._recalc_dependents(0, 0)
    assert s.table.item(0, 1).text() == "114"   # 100+2+3+4+5


def test_sheet_python_error_shows_pyerr(qapp):
    from khervesheet.workbook import WorkbookWidget
    wb = WorkbookWidget()
    s = wb.tabs.widget(0)
    _put(s, 0, 0, "=PY\n1 / 0")
    assert s.table.item(0, 0).text() == "#PYERR"
    assert "ZeroDivisionError" in s.table.item(0, 0).toolTip()
