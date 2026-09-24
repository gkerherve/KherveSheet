"""Document I/O and analysis must work without opening a dialog.

Exercises the tools an MCP client (or the built-in chat) uses to save,
open, solve and fit, plus the access levels that decide which of them a
connected client may call at all.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

import pytest

pytest.importorskip("PyQt5.QtWidgets")
pytest.importorskip("numpy")
np = pytest.importorskip("numpy")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    """A real MainWindow, kept off screen and off the recent-files list."""
    from khervesheet.mainwindow import MainWindow

    win = MainWindow()
    monkeypatch.setattr(win, "_add_recent", lambda _p: None)
    yield win
    if hasattr(win, "_ai_dock"):
        win._ai_dock._backend.shutdown()
    win.deleteLater()


@pytest.fixture
def ex(window):
    from khervesheet.ai_tools import AiToolExecutor
    return AiToolExecutor(window)


def _put(ex, sheet_name, cell, text):
    ex.execute("set_formula" if text.startswith("=") else "write_cells",
               {"sheet_name": sheet_name, "cell": cell, "formula": text}
               if text.startswith("=") else
               {"sheet_name": sheet_name, "range": cell,
                "values": [[text]]})


# ── The document ───────────────────────────────────────────────────

def test_a_fresh_workbook_reports_that_it_has_no_file(ex):
    info = ex.execute("get_document_info", {})
    assert info["file_path"] is None
    assert info["can_save_in_place"] is False
    assert info["sheets"][0] == "Sheet1"


def test_saving_a_never_saved_workbook_needs_a_path(ex):
    result = ex.execute("save_workbook", {})
    assert "path" in result["error"]


def test_an_unknown_extension_is_refused(ex, tmp_path):
    result = ex.execute("save_workbook",
                        {"path": str(tmp_path / "book.docx")})
    assert ".ksheet" in result["error"]


def test_save_then_save_again_without_a_path(ex, tmp_path):
    target = tmp_path / "book.ksheet"
    first = ex.execute("save_workbook", {"path": str(target)})
    assert first["saved"] == str(target)
    assert target.exists()
    # The document now knows its file, so a bare save works.
    again = ex.execute("save_workbook", {})
    assert again["saved"] == str(target)


def test_a_csv_export_survives_a_round_trip(ex, tmp_path):
    _put(ex, "Sheet1", "A1", "hello")
    _put(ex, "Sheet1", "B1", "42")
    path = tmp_path / "data.csv"
    assert ex.execute("save_workbook", {"path": str(path)})["saved"]
    ex.execute("new_workbook", {"discard_unsaved_changes": True})
    ex.execute("open_workbook", {"path": str(path)})
    # A CSV loads into the active sheet, keeping that sheet's name.
    back = ex.execute("read_cells",
                      {"sheet_name": "Sheet1", "range": "A1:B1"})
    assert back["values"][0] == ["hello", "42"]


def test_opening_over_unsaved_work_is_refused(ex, tmp_path):
    path = tmp_path / "book.ksheet"
    ex.execute("save_workbook", {"path": str(path)})
    _put(ex, "Sheet1", "A1", "unsaved edit")
    result = ex.execute("open_workbook", {"path": str(path)})
    assert "unsaved" in result["error"].lower()
    assert "discard_unsaved_changes" in result["error"]


def test_opening_proceeds_when_the_caller_accepts_the_loss(ex, tmp_path):
    path = tmp_path / "book.ksheet"
    ex.execute("save_workbook", {"path": str(path)})
    _put(ex, "Sheet1", "A1", "unsaved edit")
    result = ex.execute("open_workbook",
                        {"path": str(path),
                         "discard_unsaved_changes": True})
    assert result["opened"] == str(path)


def test_opening_a_missing_file_says_so(ex, tmp_path):
    result = ex.execute("open_workbook",
                        {"path": str(tmp_path / "nope.ksheet")})
    assert "No such file" in result["error"]


def test_a_new_workbook_replaces_the_old_one(ex):
    _put(ex, "Sheet1", "A1", "old")
    assert "error" in ex.execute("new_workbook", {})
    result = ex.execute("new_workbook", {"discard_unsaved_changes": True})
    assert result["created"] is True
    assert ex.execute("read_cells",
                      {"sheet_name": "Sheet1",
                       "range": "A1"})["values"] == [[""]]


# ── Solver ─────────────────────────────────────────────────────────

def test_the_solver_minimises_a_formula_cell(ex):
    _put(ex, "Sheet1", "A1", "0")
    _put(ex, "Sheet1", "A2", "0")
    _put(ex, "Sheet1", "B1", "=(A1-3)^2+(A2+1)^2")
    result = ex.execute("run_solver",
                        {"sheet_name": "Sheet1",
                         "objective_cell": "B1",
                         "variable_cells": "A1:A2", "goal": "min"})
    assert result["solved"] is True
    assert float(result["objective_value"]) == pytest.approx(0, abs=1e-6)
    assert float(result["variables"]["$A$1"]) == pytest.approx(3, abs=1e-3)


def test_a_solver_constraint_binds(ex):
    _put(ex, "Sheet1", "A1", "0")
    _put(ex, "Sheet1", "B1", "=A1")
    result = ex.execute("run_solver",
                        {"sheet_name": "Sheet1",
                         "objective_cell": "B1",
                         "variable_cells": "A1", "goal": "max",
                         "constraints": [{"cell": "A1", "op": "<=",
                                          "value": "2.5"}]})
    assert float(result["variables"]["$A$1"]) == pytest.approx(2.5, abs=1e-6)


def test_a_bad_objective_reports_instead_of_raising(ex):
    result = ex.execute("run_solver",
                        {"sheet_name": "Sheet1",
                         "objective_cell": "not-a-cell",
                         "variable_cells": "A1"})
    assert "Invalid objective cell" in result["error"]


def test_a_target_goal_needs_a_target(ex):
    result = ex.execute("run_solver",
                        {"sheet_name": "Sheet1", "objective_cell": "B1",
                         "variable_cells": "A1", "goal": "value"})
    assert "target_value" in result["error"]


# ── Fitting ────────────────────────────────────────────────────────

@pytest.fixture
def linear_data(ex):
    xs = np.linspace(0.0, 10.0, 21)
    ys = 3.0 * xs + 7.0
    ex.execute("write_cells",
               {"sheet_name": "Sheet1", "range": "A1",
                "values": [[f"{x:g}"] for x in xs]})
    ex.execute("write_cells",
               {"sheet_name": "Sheet1", "range": "B1",
                "values": [[f"{y:g}"] for y in ys]})
    return "A1:A21", "B1:B21"


def test_a_linear_trendline_recovers_the_slope(ex, linear_data):
    x_range, y_range = linear_data
    result = ex.execute("fit_trendline",
                        {"sheet_name": "Sheet1", "x_range": x_range,
                         "y_range": y_range, "model": "Linear"})
    assert result["params"]["a"] == pytest.approx(3.0, abs=1e-6)
    assert result["params"]["b"] == pytest.approx(7.0, abs=1e-6)
    assert result["goodness_of_fit"]["R²"] == pytest.approx(1.0, abs=1e-9)


def test_a_trendline_can_write_its_curve_into_the_sheet(ex, linear_data):
    x_range, y_range = linear_data
    result = ex.execute("fit_trendline",
                        {"sheet_name": "Sheet1", "x_range": x_range,
                         "y_range": y_range, "model": "Linear",
                         "output_cell": "D1"})
    assert result["written"]["columns_written"] == 1
    col = ex.execute("read_cells",
                     {"sheet_name": "Sheet1", "range": "D1:D3"})["values"]
    assert col[0][0] == "Linear fit"
    assert float(col[1][0]) == pytest.approx(7.0, abs=1e-3)


def test_mismatched_ranges_are_rejected(ex, linear_data):
    x_range, _ = linear_data
    result = ex.execute("fit_trendline",
                        {"sheet_name": "Sheet1", "x_range": x_range,
                         "y_range": "B1:B10"})
    assert "must match" in result["error"]


def test_an_unknown_model_is_named_in_the_error(ex, linear_data):
    x_range, y_range = linear_data
    result = ex.execute("fit_trendline",
                        {"sheet_name": "Sheet1", "x_range": x_range,
                         "y_range": y_range, "model": "Telepathy"})
    assert "Telepathy" in result["error"]


def test_peak_fitting_recovers_two_gaussians(ex):
    xs = np.linspace(280.0, 296.0, 81)
    ys = (100 * np.exp(-0.5 * ((xs - 285.0) / 0.8) ** 2)
          + 60 * np.exp(-0.5 * ((xs - 288.5) / 1.0) ** 2))
    ex.execute("write_cells",
               {"sheet_name": "Sheet1", "range": "A1",
                "values": [[f"{v:.10g}"] for v in xs]})
    ex.execute("write_cells",
               {"sheet_name": "Sheet1", "range": "B1",
                "values": [[f"{v:.10g}"] for v in ys]})
    result = ex.execute(
        "fit_peaks",
        {"sheet_name": "Sheet1", "x_range": "A1:A81",
         "y_range": "B1:B81",
         "peaks": [{"model": "Gaussian", "center": 285.0},
                   {"model": "Gaussian", "center": 288.5}],
         "background": "None"})
    centres = sorted(p["params"]["center"]["value"] for p in result["peaks"])
    assert centres[0] == pytest.approx(285.0, abs=1e-3)
    assert centres[1] == pytest.approx(288.5, abs=1e-3)
    assert result["success"] is True


def test_peak_fitting_writes_its_components(ex):
    xs = np.linspace(-5.0, 5.0, 41)
    ys = 10 * np.exp(-0.5 * (xs / 1.0) ** 2)
    ex.execute("write_cells",
               {"sheet_name": "Sheet1", "range": "A1",
                "values": [[f"{v:.10g}"] for v in xs]})
    ex.execute("write_cells",
               {"sheet_name": "Sheet1", "range": "B1",
                "values": [[f"{v:.10g}"] for v in ys]})
    result = ex.execute(
        "fit_peaks",
        {"sheet_name": "Sheet1", "x_range": "A1:A41",
         "y_range": "B1:B41", "peaks": ["Gaussian"],
         "output_cell": "D1"})
    headers = ex.execute("read_cells",
                         {"sheet_name": "Sheet1",
                          "range": "D1:H1"})["values"][0]
    assert headers[:2] == ["x", "data"]
    assert "fit" in headers and "residual" in headers
    assert result["written"]["columns_written"] == len(
        [h for h in headers if h])


def test_an_unknown_peak_shape_points_at_the_catalogue(ex):
    ex.execute("write_cells", {"sheet_name": "Sheet1", "range": "A1",
                               "values": [["1"], ["2"], ["3"], ["4"]]})
    ex.execute("write_cells", {"sheet_name": "Sheet1", "range": "B1",
                               "values": [["1"], ["4"], ["9"], ["16"]]})
    result = ex.execute("fit_peaks",
                        {"sheet_name": "Sheet1", "x_range": "A1:A4",
                         "y_range": "B1:B4", "peaks": ["Blancmange"]})
    assert "list_fit_models" in result["error"]


def test_the_model_catalogue_lists_both_families(ex):
    models = ex.execute("list_fit_models", {})
    assert "Linear" in models["trendline_models"]
    assert any(p["name"] == "Gaussian" for p in models["peak_shapes"])
    assert "Shirley (XPS)" in models["backgrounds"]


# ── The bulk-write ceiling ─────────────────────────────────────────

def test_a_huge_write_is_refused_with_advice(ex):
    from khervesheet.ai_tools import MAX_WRITE_CELLS
    rows = [["1"] * 100 for _ in range(MAX_WRITE_CELLS // 100 + 1)]
    result = ex.execute("write_cells",
                        {"sheet_name": "Sheet1", "range": "A1",
                         "values": rows})
    assert "=PY" in result["error"]


def test_an_ordinary_write_still_goes_through(ex):
    result = ex.execute("write_cells",
                        {"sheet_name": "Sheet1", "range": "A1",
                         "values": [["a", "b"], ["c", "d"]]})
    assert result["cells_written"] == 4


# ── Access levels ──────────────────────────────────────────────────

@pytest.mark.parametrize("level,tool,allowed", [
    ("read", "read_cells", True),
    ("read", "get_document_info", True),
    ("read", "write_cells", False),
    ("read", "set_python_cell", False),
    ("edit", "write_cells", True),
    ("edit", "save_workbook", True),
    ("edit", "set_python_cell", False),
    ("full", "set_python_cell", True),
    ("full", "write_cells", True),
])
def test_each_access_level_allows_the_right_tools(level, tool, allowed):
    from khervesheet.mcp_bridge import tool_allowed
    assert tool_allowed(tool, level) is allowed


def test_read_only_hides_the_mutating_tools_from_the_client(window):
    bridge = window.mcp_bridge()
    bridge.set_access("read")
    names = {t["name"] for t in bridge.visible_tools()}
    assert "read_cells" in names
    assert "write_cells" not in names
    bridge.set_access("full")
    assert "set_python_cell" in {t["name"] for t in bridge.visible_tools()}


def test_a_refused_call_explains_which_setting_blocked_it(window):
    bridge = window.mcp_bridge()
    bridge.set_access("edit")
    result = bridge._call_tool(
        {"name": "set_python_cell",
         "input": {"sheet_name": "Sheet1", "cell": "A1", "code": "1"}})
    assert "'Full'" in result["error"]
    assert bridge.log[-1]["outcome"] == "refused"


def test_an_unknown_access_level_is_rejected(window):
    import pytest as _pytest
    with _pytest.raises(ValueError):
        window.mcp_bridge().set_access("root")


# ── Undo bookkeeping through the bridge ────────────────────────────

def test_saving_through_the_bridge_marks_the_document_clean(window,
                                                            tmp_path):
    """A macro around the save would make setClean() a silent no-op."""
    bridge = window.mcp_bridge()
    bridge._call_tool({"name": "write_cells",
                       "input": {"sheet_name": "Sheet1", "range": "A1",
                                 "values": [["x"]]}})
    assert not window._undo_stack.isClean()
    result = bridge._call_tool(
        {"name": "save_workbook",
         "input": {"path": str(tmp_path / "book.ksheet")}})
    assert result["saved"]
    assert window._undo_stack.isClean()


def test_a_reporting_only_fit_adds_nothing_to_the_undo_stack(window):
    bridge = window.mcp_bridge()
    bridge._call_tool({"name": "write_cells",
                       "input": {"sheet_name": "Sheet1", "range": "A1",
                                 "values": [[str(v)] for v in range(6)]}})
    bridge._call_tool({"name": "write_cells",
                       "input": {"sheet_name": "Sheet1", "range": "B1",
                                 "values": [[str(2 * v)]
                                            for v in range(6)]}})
    before = window._undo_stack.count()
    bridge._call_tool({"name": "fit_trendline",
                       "input": {"sheet_name": "Sheet1",
                                 "x_range": "A1:A6", "y_range": "B1:B6",
                                 "model": "Linear"}})
    assert window._undo_stack.count() == before


def test_a_mutating_call_is_one_undo_entry(window):
    bridge = window.mcp_bridge()
    before = window._undo_stack.count()
    bridge._call_tool({"name": "write_cells",
                       "input": {"sheet_name": "Sheet1", "range": "A1",
                                 "values": [["a", "b"], ["c", "d"]]}})
    assert window._undo_stack.count() == before + 1
    window._undo_stack.undo()
    assert window._workbook.sheet_by_name("Sheet1").cell_text(0, 0) == ""


# ── The Solver dialog still talks to the user ──────────────────────

def test_the_dialog_still_shows_the_boxes_the_hook_replaced(app,
                                                            monkeypatch):
    """Routing messages through _report must not mute the real dialog."""
    from PyQt5.QtWidgets import QMessageBox, QUndoStack
    from khervesheet.sheet import SheetWidget
    from khervesheet.solver import SolverDialog

    shown = []

    def _spy(kind):
        def _record(_parent, title, text, *_a, **_k):
            shown.append((kind, title, text))
        return staticmethod(_record)

    for kind in ("critical", "warning", "information"):
        monkeypatch.setattr(QMessageBox, kind, _spy(kind))

    sheet = SheetWidget(rows=10, cols=5)
    sheet._undo_stack = QUndoStack()
    dlg = SolverDialog(sheet)
    try:
        dlg._report("warning", "Solver", "something is off")
        dlg._report("info", "Solver", "all good")
        assert shown == [("warning", "Solver", "something is off"),
                         ("information", "Solver", "all good")]
        # And it is recorded either way, for a headless caller to relay.
        assert [e["text"] for e in dlg._report_log] == [
            "something is off", "all good"]
    finally:
        dlg._disconnect_sheet()
        dlg.deleteLater()


def test_a_headless_solver_asks_nobody(app, monkeypatch):
    from PyQt5.QtWidgets import QMessageBox, QUndoStack
    from khervesheet.sheet import SheetWidget
    from khervesheet.solver import SolverDialog

    def _boom(*_a, **_k):
        raise AssertionError("headless solve must not open a dialog")

    for kind in ("critical", "warning", "information", "question"):
        monkeypatch.setattr(QMessageBox, kind, staticmethod(_boom))

    sheet = SheetWidget(rows=10, cols=5)
    sheet._undo_stack = QUndoStack()
    dlg = SolverDialog(sheet, headless=True)
    try:
        assert dlg._report("critical", "Solver", "nope") is True
        assert dlg._report_log[-1]["level"] == "critical"
    finally:
        dlg._disconnect_sheet()
        dlg.deleteLater()


# ── Which caller sees which tools ──────────────────────────────────

_MCP_ONLY = {"get_document_info", "save_workbook", "open_workbook",
             "new_workbook", "run_solver", "fit_trendline", "fit_peaks",
             "list_fit_models"}


def test_the_chat_is_not_offered_the_mcp_only_tools():
    """In the window, File ▸ Save and Tools ▸ Solver are a click away."""
    from khervesheet.ai_backend import TOOLS
    assert _MCP_ONLY.isdisjoint({t["name"] for t in TOOLS})
    assert "read_cells" in {t["name"] for t in TOOLS}


def test_an_mcp_client_is_offered_both_tables():
    from khervesheet.ai_backend import MCP_TOOLS, TOOLS
    names = {t["name"] for t in MCP_TOOLS}
    assert _MCP_ONLY <= names
    assert {t["name"] for t in TOOLS} <= names
    assert len(MCP_TOOLS) == len(names)      # no duplicate definitions


def test_the_executor_can_still_run_every_name_in_either_table(ex):
    from khervesheet.ai_backend import MCP_TOOLS
    missing = [t["name"] for t in MCP_TOOLS
               if t["name"] not in ex._dispatch]
    assert missing == []


def test_opening_foreign_python_cells_never_blocks_on_a_dialog(
        ex, window, tmp_path):
    path = str(tmp_path / "py.ksheet")
    ex.execute("set_python_cell",
               {"sheet_name": "Sheet1", "cell": "A1", "code": "1+1"})
    ex.execute("save_workbook", {"path": path})
    window._trusted_py_paths.clear()      # as if authored elsewhere
    ex.execute("new_workbook", {"discard_unsaved_changes": True})
    result = ex.execute("open_workbook", {"path": path})
    assert result["opened"] == path
    assert "python_cells_not_run" in result


def test_argument_spelling_is_forgiving(ex):
    ex.execute("write_cells", {"sheet_name": "Sheet1", "range": "A1:B3",
                               "values": [[1, 2], [2, 4], [3, 7]]})
    chart = ex.execute("insert_chart", {
        "sheet_name": "Sheet1", "chart_type": "scatter",
        "x_range": "A1:A3", "y_range": "B1:B3"})
    assert chart["chart_type"] == "Scatter"
    assert ex.execute("delete_charts", {"sheet_name": "Sheet1",
                                        "indices": [0]})["deleted"] == 1
    fit = ex.execute("fit_trendline", {
        "sheet_name": "Sheet1", "x_range": "A1:A3", "y_range": "B1:B3",
        "model": "linear"})
    assert fit["model"] == "Linear"
    assert "style_name" in ex.execute(
        "apply_table_style", {"sheet_name": "Sheet1",
                              "range": "A1:B3"})["error"]
