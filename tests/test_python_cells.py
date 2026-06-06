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
    refs = extract_refs('ks("A1") + cell(\'B2:C3\') + xl("Sheet1!D4")')
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


def test_timeout_aborts_infinite_loop():
    rt = PythonRuntime()
    rt.timeout = 0.5
    res = rt.run("while True:\n    pass", None, 0, 0)
    assert not res.ok
    assert "TimeoutError" in res.error
    # Normal code still runs after a timeout.
    assert rt.run("2 + 2", None, 0, 0).value == 4


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


def test_ks_set_writes_and_recalcs(qapp):
    from khervesheet.workbook import WorkbookWidget
    wb = WorkbookWidget()
    s = wb.tabs.widget(0)
    # Scalar write to a single cell.
    _put(s, 0, 0, '=PY\nks_set("C1", 99)\n"done"')
    assert s.table.item(0, 2).text() == "99"
    assert s.table.item(0, 0).text() == "done"
    # Array writes down a column.
    _put(s, 1, 0, '=PY\nimport numpy as np\nks_set("D1", np.arange(4)*10)\n0')
    assert [s.table.item(r, 3).text() for r in range(4)] == \
        ["0", "10", "20", "30"]
    # Scalar fills a whole range.
    _put(s, 2, 0, '=PY\nks_set("E1:F2", 7)\n0')
    assert all(s.table.item(r, c).text() == "7"
               for r in range(2) for c in (4, 5))
    # A formula depending on a written cell recomputes.
    _put(s, 0, 7, "=C1*2")
    assert s.table.item(0, 7).text() in ("198", "198.00")
    _put(s, 3, 0, '=PY\nks_set("C1", 50)\n0')
    assert s.table.item(0, 7).text() in ("100", "100.00")


def test_python_udf_callable_from_formula(qapp):
    from khervesheet.workbook import WorkbookWidget
    wb = WorkbookWidget()
    s = wb.tabs.widget(0)
    _put(s, 0, 0, "=PY\ndef dbl(x):\n    return x * 2")
    _put(s, 0, 1, "21")                       # B1
    _put(s, 0, 2, "=dbl(B1)")                 # C1 lower-case
    _put(s, 1, 2, "=DBL(B1)")                 # C2 upper-case
    assert s.table.item(0, 2).text() in ("42", "42.00")
    assert s.table.item(1, 2).text() in ("42", "42.00")
    # Recomputes when the input changes.
    _put(s, 0, 1, "50")
    s._recalc_dependents(0, 1)
    assert s.table.item(0, 2).text() in ("100", "100.00")


def test_python_udf_does_not_clobber_builtin(qapp):
    from khervesheet.workbook import WorkbookWidget
    wb = WorkbookWidget()
    s = wb.tabs.widget(0)
    _put(s, 0, 0, "3")
    _put(s, 1, 0, "4")
    _put(s, 2, 0, "=PY\ndef SUM(x):\n    return 999")
    _put(s, 0, 1, "=SUM(A1:A2)")
    assert s.table.item(0, 1).text() in ("7", "7.00")


def test_py_plot_exports_vector(qapp, tmp_path):
    from khervesheet.workbook import WorkbookWidget
    wb = WorkbookWidget()
    s = wb.tabs.widget(0)
    _put(s, 0, 0,
         "=PY\nimport matplotlib.pyplot as plt\n"
         "plt.plot([1, 2, 3], [1, 4, 9])\nplt.gcf()")
    assert s._images, "the plot should have produced an embedded image"
    img = s._images[-1]
    assert img._mpl_figure is not None       # source figure retained
    svg = str(tmp_path / "p.svg")
    pdf = str(tmp_path / "p.pdf")
    assert img._save_figure(svg, "svg") is True
    assert img._save_figure(pdf, "pdf") is True
    assert "<svg" in open(svg, encoding="utf-8", errors="ignore").read()
    assert open(pdf, "rb").read(5) == b"%PDF-"
    # A plain image (no figure) reports no vector source.
    from khervesheet.embedded_image import EmbeddedImage
    from PyQt5.QtGui import QPixmap
    plain = EmbeddedImage(QPixmap(10, 10), None)
    assert plain._mpl_figure is None
    assert plain._save_figure(str(tmp_path / "x.svg"), "svg") is False


def test_sheet_python_error_shows_pyerr(qapp):
    from khervesheet.workbook import WorkbookWidget
    wb = WorkbookWidget()
    s = wb.tabs.widget(0)
    _put(s, 0, 0, "=PY\n1 / 0")
    assert s.table.item(0, 0).text() == "#PYERR"
    assert "ZeroDivisionError" in s.table.item(0, 0).toolTip()


def test_ks_alias_resolves(qapp):
    from khervesheet.workbook import WorkbookWidget
    wb = WorkbookWidget()
    s = wb.tabs.widget(0)
    _put(s, 0, 0, "7")
    _put(s, 1, 0, "8")
    _put(s, 0, 1, '=PY\nint(sum(ks("A1:A2")))')
    assert s.table.item(0, 1).text() == "15"


def test_ai_set_python_cell_tool(qapp):
    from khervesheet.mainwindow import MainWindow
    from khervesheet.ai_tools import AiToolExecutor
    mw = MainWindow()
    ex = AiToolExecutor(mw)
    sheet_name = mw._workbook.name_of_sheet(mw._active_sheet())
    out = ex.execute("set_python_cell", {
        "sheet_name": sheet_name, "cell": "A1", "code": "6 * 7"})
    assert out["result"] == "42"
    # A leading =PY marker from the model is tolerated.
    out2 = ex.execute("set_python_cell", {
        "sheet_name": sheet_name, "cell": "A2", "code": "=PY\n2 ** 5"})
    assert out2["result"] == "32"
    # Errors are reported back to the model.
    out3 = ex.execute("set_python_cell", {
        "sheet_name": sheet_name, "cell": "A3", "code": "1 / 0"})
    assert out3["result"] == "#PYERR"
    assert "ZeroDivisionError" in out3["error"]


def test_python_help_html_has_examples():
    from khervesheet.python_engine import PYTHON_HELP_HTML
    assert "matplotlib" in PYTHON_HELP_HTML
    assert "ks(" in PYTHON_HELP_HTML
    assert "plt.gcf()" in PYTHON_HELP_HTML


def test_stdout_capture():
    rt = PythonRuntime()
    res = rt.run("print('hello')\n21 * 2", None, 0, 0)
    assert res.value == 42
    assert res.stdout.strip() == "hello"


def test_run_python_from_dialog_returns_output(qapp):
    from khervesheet.workbook import WorkbookWidget
    wb = WorkbookWidget()
    s = wb.tabs.widget(0)
    out = s._run_python_from_dialog(0, 0, "print('hi')\n6 * 7")
    assert out["result"] == "42"
    assert out["error"] is None
    assert out["stdout"].strip() == "hi"
    assert out["has_plot"] is False
    # The cell really became a =PY cell.
    assert s._cell_formulas[(0, 0)].startswith("=PY")


def test_error_line_parsed_from_traceback():
    from khervesheet.python_engine import PythonCellDialog
    tb = ('Traceback (most recent call last):\n'
          '  File "<py-cell>", line 2, in <module>\n'
          'ZeroDivisionError: division by zero')
    assert PythonCellDialog._error_line_from(tb) == 2
    assert PythonCellDialog._error_line_from("no line here") is None


def test_popout_pick_inserts_ref(qapp):
    from khervesheet.workbook import WorkbookWidget
    wb = WorkbookWidget()
    s = wb.tabs.widget(0)
    s.table.setCurrentCell(0, 0)
    s._open_python_popout()
    dlg = s._py_dialog
    dlg._pick_act.setChecked(True)
    assert s._py_pick_active is True
    s._on_cell_clicked(2, 3)            # D3
    assert 'ks("D3")' in dlg.editor.toPlainText()
    assert s._py_pick_active is False   # auto-disarmed
    dlg.close()


def test_popout_marks_error_line(qapp):
    from khervesheet.workbook import WorkbookWidget
    wb = WorkbookWidget()
    s = wb.tabs.widget(0)
    s.table.setCurrentCell(0, 0)
    s._open_python_popout()
    dlg = s._py_dialog
    dlg.editor.setPlainText("x = 1\ny = 1 / 0")
    dlg._run()
    assert dlg.editor._error_line == 2
    dlg.editor.setPlainText("2 + 2")
    dlg._run()
    assert dlg.editor._error_line is None
    dlg.close()


def test_dialog_comment_toggle(qapp):
    from khervesheet.python_engine import _DialogCodeEditor
    from PyQt5.QtGui import QTextCursor
    ed = _DialogCodeEditor()
    ed.setPlainText("x = 1\ny = 2")
    c = ed.textCursor()
    c.select(QTextCursor.Document)
    ed.setTextCursor(c)
    ed.toggle_comment()
    assert ed.toPlainText() == "# x = 1\n# y = 2"
    c = ed.textCursor()
    c.select(QTextCursor.Document)
    ed.setTextCursor(c)
    ed.toggle_comment()
    assert ed.toPlainText() == "x = 1\ny = 2"
