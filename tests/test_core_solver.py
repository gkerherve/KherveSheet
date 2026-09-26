"""The Solver without Qt (khervesheet.core.solver) on the Qt-free engine."""

import pytest

from khervesheet.core import solver
from khervesheet.core.engine import Workbook


def _sheet(cells):
    wb = Workbook()
    sheet = wb.add_sheet()
    for ref, text in cells.items():
        r, c = solver.parse_ref(ref)
        sheet.set_cell(r, c, text)
    return sheet


def test_refs():
    assert solver.parse_ref("$B$3") == (2, 1)
    assert solver.parse_range("A1:B2,D5") == [(0, 0), (0, 1), (1, 0),
                                              (1, 1), (4, 3)]
    assert solver.ref_str(2, 1) == "$B$3"
    assert solver.display_number(2.0000001, 3) == "2"
    assert solver.display_number(1.23456, 3) == "1.235"


def test_minimise_a_parabola():
    sheet = _sheet({"A1": "0", "B1": "=(A1-3)^2+2"})
    host = solver.EngineHost(sheet)
    out = solver.solve(host, solver.Problem(objective=(0, 1),
                                            variables=[(0, 0)]))
    assert out.success
    assert out.x[0] == pytest.approx(3, abs=1e-5)


def test_goal_value_and_constraint():
    sheet = _sheet({"A1": "1", "A2": "1", "B1": "=A1*A2"})
    host = solver.EngineHost(sheet)
    out = solver.solve(host, solver.Problem(
        objective=(0, 1), variables=[(0, 0), (1, 0)], goal="value",
        target=12, constraints=[solver.Constraint((0, 0), "<=", 2)]))
    a, b = out.x
    assert a <= 2 + 1e-9
    assert a * b == pytest.approx(12, rel=1e-4)


def test_maximise_evolutionary_non_negative():
    sheet = _sheet({"A1": "1", "B1": "=-(A1-4)^2+10"})
    out = solver.solve(solver.EngineHost(sheet), solver.Problem(
        objective=(0, 1), variables=[(0, 0)], goal="max",
        method="Evolutionary", non_negative=True))
    assert out.x[0] == pytest.approx(4, abs=1e-3)


def test_cancel_keeps_the_best():
    sheet = _sheet({"A1": "0", "B1": "=(A1-3)^2"})
    calls = []

    def pump():
        calls.append(1)
        if len(calls) > 3:
            raise solver.Cancelled

    out = solver.solve(solver.EngineHost(sheet), solver.Problem(
        objective=(0, 1), variables=[(0, 0)], keep_searching=True), pump)
    assert out.cancelled and out.x is not None
