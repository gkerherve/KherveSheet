"""=PY cells in the Qt-free engine (khervesheet.core.python)."""

import pytest

from khervesheet.core.engine import PYTHON_NOT_RUN, Workbook
from khervesheet.core.python import source_hash


@pytest.fixture
def wb():
    wb = Workbook()
    sheet = wb.add_sheet()
    for r, v in enumerate(["1", "2", "3", "4"]):
        sheet.set_cell(r, 0, v)
    return wb


def test_not_run_without_a_runtime(wb):
    sheet = wb.sheets[0]
    sheet.set_cell(0, 2, "=PY ks('A1:A4').sum()")
    assert sheet.text(0, 2) == PYTHON_NOT_RUN


def test_values_dependencies_and_formulas(wb):
    sheet = wb.sheets[0]
    wb.enable_python()
    sheet.set_cell(0, 2, "=PY\nimport numpy as np\nnp.sum(ks('A1:A4'))")
    assert sheet.text(0, 2) == "10"
    sheet.set_cell(0, 3, "=C1*2")
    assert sheet.text(0, 3) == "20.00"
    changes = sheet.set_cell(3, 0, "14")          # an input changes
    assert sheet.text(0, 2) == "20" and sheet.text(0, 3) == "40.00"
    assert ("Sheet1", 0, 2, "20") in changes


def test_spills_objects_errors_and_print(wb):
    sheet = wb.sheets[0]
    wb.enable_python()
    sheet.set_cell(0, 4, "=PY [x * 10 for x in ks('A1:A3')]")
    assert [sheet.text(r, 4) for r in range(3)] == ["10", "20", "30"]
    sheet.set_cell(5, 4, "=SUM(E1:E3)")
    assert sheet.text(5, 4) == "60.00"
    sheet.set_cell(0, 4, "=PY [1]")            # a shorter spill clears
    assert sheet.text(1, 4) == "" and sheet.text(5, 4) == "1.00"
    sheet.set_cell(0, 5, "=PY ks('A1:A4')")
    assert sheet.text(0, 5) == "▮ ndarray(4,)"
    sheet.set_cell(0, 6, "=PY\nprint('hello')\n1/0")
    assert sheet.text(0, 6) == "#PYERR"
    assert "ZeroDivisionError" in sheet.py_errors[(0, 6)]
    assert sheet.py_stdout[(0, 6)] == "hello\n"


def test_ks_set_and_figures(wb):
    sheet = wb.sheets[0]
    wb.enable_python()
    sheet.set_cell(0, 7, "=PY\nks_set('I1:I2', [5, 6])\n'done'")
    assert sheet.text(0, 8) == "5" and sheet.text(1, 8) == "6"
    sheet.set_cell(0, 9, "=PY\nimport matplotlib.pyplot as plt\n"
                         "plt.plot(ks('A1:A4'))")
    assert sheet.text(0, 9) == "📈 plot"
    assert "<svg" in sheet.py_figures[(0, 9)]


def test_only_trusted_code_runs(wb):
    sheet = wb.sheets[0]
    good, bad = "=PY 1+1", "=PY 2+2"
    sheet.set_cell(0, 2, good)
    sheet.set_cell(1, 2, bad)
    changes = wb.enable_python(trusted={source_hash(good)})
    assert sheet.text(0, 2) == "2" and sheet.text(1, 2) == PYTHON_NOT_RUN
    assert ("Sheet1", 0, 2, "2") in changes


def test_time_limit(wb):
    from khervesheet.core.python import PythonRuntime
    wb.enable_python(PythonRuntime(timeout=0.2))
    sheet = wb.sheets[0]
    sheet.set_cell(0, 2, "=PY\nwhile True:\n    pass")
    assert sheet.text(0, 2) == "#PYERR"
    assert "TimeoutError" in sheet.py_errors[(0, 2)]
