"""Live co-editing: two windows editing one workbook through the relay.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import socket
import time

import pytest

pytest.importorskip("PyQt5.QtWebSockets")
pytest.importorskip("pycrdt")
pytest.importorskip("pycrdt.websocket")
pytest.importorskip("hypercorn")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def server_url(tmp_path_factory):
    from khervesheet.collab.server import BackgroundServer

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = BackgroundServer(
        "127.0.0.1", port, str(tmp_path_factory.mktemp("live") / "rooms.db"))
    server.start()
    deadline = time.time() + 10
    while time.time() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.05)
    assert server.error is None
    yield f"ws://127.0.0.1:{port}"
    server.stop()


def make_window(monkeypatch):
    from khervesheet.mainwindow import MainWindow

    win = MainWindow()
    monkeypatch.setattr(win, "_add_recent", lambda _p: None)
    monkeypatch.setattr(win, "_maybe_save_changes", lambda: True)
    return win


def wait_for(app, condition, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def type_into(sheet, row, col, text):
    """Commit text the way the formula bar does."""
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


def text_at(sheet, row, col):
    item = sheet.table.item(row, col)
    return item.text() if item is not None else ""


def number_at(sheet, row, col):
    try:
        return float(text_at(sheet, row, col))
    except ValueError:
        return None


@pytest.fixture
def pair(app, server_url, monkeypatch):
    """Alice shares her workbook, Bob joins it."""
    import secrets
    from khervesheet.collab.session import LiveSession

    alice = make_window(monkeypatch)
    bob = make_window(monkeypatch)
    type_into(alice._workbook.current_sheet(), 0, 0, "7")
    type_into(alice._workbook.current_sheet(), 1, 0, "=A1*6")
    alice._workbook.tabs.setTabText(0, "Data")

    room = secrets.token_urlsafe(12)
    a = LiveSession(alice, server_url, room, "Alice", publish_local=True)
    a.start()
    assert wait_for(app, lambda: a._synced)
    bob._new_workbook()
    b = LiveSession(bob, server_url, room, "Bob", publish_local=False)
    b.start()
    assert wait_for(app, lambda: b._synced)
    yield app, alice, bob, a, b
    a.stop()
    b.stop()
    for win in (alice, bob):
        if hasattr(win, "_ai_dock"):
            win._ai_dock._backend.shutdown()
        win.deleteLater()


def test_joining_loads_the_shared_workbook(pair):
    app, alice, bob, a, b = pair
    sheet = bob._workbook.current_sheet()
    assert bob._workbook.sheet_names() == alice._workbook.sheet_names()
    assert bob._workbook.sheet_names()[0] == "Data"
    assert number_at(sheet, 0, 0) == 7
    # The formula travels, and Bob's copy computes it.
    assert sheet._cell_formulas.get((1, 0)) == "=A1*6"
    assert number_at(sheet, 1, 0) == 42


def test_edits_flow_both_ways_and_recalculate(pair):
    app, alice, bob, a, b = pair
    alice_sheet = alice._workbook.current_sheet()
    bob_sheet = bob._workbook.current_sheet()

    type_into(alice_sheet, 0, 0, "10")
    assert wait_for(app, lambda: number_at(bob_sheet, 1, 0) == 60)

    type_into(bob_sheet, 2, 1, "hello")
    assert wait_for(app, lambda: text_at(alice_sheet, 2, 1) == "hello")

    type_into(bob_sheet, 2, 1, "")
    assert wait_for(app, lambda: text_at(alice_sheet, 2, 1) == "")


def test_remote_edits_are_not_on_the_local_undo_stack(pair):
    app, alice, bob, a, b = pair
    before = bob._undo_stack.count()
    type_into(alice._workbook.current_sheet(), 3, 0, "remote")
    assert wait_for(
        app, lambda: text_at(bob._workbook.current_sheet(), 3, 0) == "remote")
    assert bob._undo_stack.count() == before


def test_formats_and_new_sheets_are_shared(pair):
    from khervesheet.cellformat import CellFormat

    app, alice, bob, a, b = pair
    alice_sheet = alice._workbook.current_sheet()
    alice_sheet._cell_formats[(0, 0)] = CellFormat(bold=True, bg_color="#ffee00")
    a._schedule_flush()
    bob_sheet = bob._workbook.current_sheet()
    assert wait_for(app, lambda: (0, 0) in bob_sheet._cell_formats)
    assert bob_sheet._cell_formats[(0, 0)].bold is True
    assert bob_sheet.table.item(0, 0).font().bold()

    new = alice._workbook.add_sheet("Results")
    type_into(new, 0, 0, "=Data!A1+1")
    a._schedule_flush()
    assert wait_for(app, lambda: "Results" in bob._workbook.sheet_names())
    results = bob._workbook.sheet_by_name("Results")
    assert wait_for(app, lambda: number_at(results, 0, 0) == 8)


def test_collaborators_see_each_other(pair):
    app, alice, bob, a, b = pair
    assert wait_for(app, lambda: [p.get("user") for p in a._peers] == ["Bob"])
    assert wait_for(app, lambda: [p.get("user") for p in b._peers]
                    == ["Alice"])


def test_remote_python_cells_do_not_run_without_consent(pair, monkeypatch):
    from khervesheet.collab.session import NOT_RUN

    app, alice, bob, a, b = pair
    asked = []
    monkeypatch.setattr(bob, "_confirm_python_trust",
                        lambda key: asked.append(key) or False)
    alice_sheet = alice._workbook.current_sheet()
    alice_sheet._cell_formulas[(5, 0)] = "=PY\nopen('/tmp/x', 'w')"
    a._schedule_flush()
    bob_sheet = bob._workbook.current_sheet()
    assert wait_for(app, lambda: text_at(bob_sheet, 5, 0) == NOT_RUN)
    assert asked == [f"live:{b.room}"]


def test_charts_are_shared_both_ways(pair):
    """A desktop chart reaches the others as a chart spec (what KherveCELL
    draws), and a spec written by the web becomes a desktop chart."""
    import json

    import numpy as np

    from khervesheet.collab import model
    from khervesheet.graph import EmbeddedChart

    app, alice, bob, a, b = pair
    sheet = alice._workbook.current_sheet()
    for r, (month, sales) in enumerate([("Jan", 3), ("Feb", 5), ("Mar", 4)]):
        type_into(sheet, 3 + r, 0, month)
        type_into(sheet, 3 + r, 1, str(sales))
    chart = EmbeddedChart(np.arange(3.0), np.array([3.0, 5.0, 4.0]), "Sales",
                          "Bar", sheet, sheet.table.viewport(), x_col=0,
                          y_col=1, row_start=3, row_end=5)
    chart._ax.set_title("Quarter")
    chart.resize(400, 260)
    chart.move(sheet.table.columnViewportPosition(3),
               sheet.table.rowViewportPosition(1))
    sheet._charts.append(chart)
    a._flush_local()

    bob_sheet = bob._workbook.current_sheet()
    assert wait_for(app, lambda: len(bob_sheet._charts) == 1)
    spec = json.loads(next(iter(b.ycharts.values())))
    assert spec["type"] == "Bar" and spec["title"] == "Quarter"
    assert spec["x"] == "A4:A6"
    assert [s["ref"] for s in spec["series"]] == ["B4:B6"]
    assert (spec["row"], spec["col"]) == (1, 3)
    assert bob_sheet._charts[0]._ax.get_title() == "Quarter"

    # The web adds a chart with a trendline (a spec in the shared map).
    web = {"sheetId": spec["sheetId"], "row": 10, "col": 1, "width": 360,
           "height": 240, "type": "Scatter", "title": "From the web",
           "x": "A1:A2", "series": [{"ref": "B4:B6", "name": "Sales"}],
           "trendlines": [{"series": 0, "model": "Linear", "forward": 2}]}
    with b.doc.transaction():
        b.ycharts["webchart0001"] = model.encode_json(web)
    assert wait_for(app, lambda: len(sheet._charts) == 2)
    made = next(c for c in sheet._charts
                if getattr(c, "_collab_id", None) == "webchart0001")
    assert made._ax.get_title() == "From the web"
    assert len(made._trendlines) == 1
    # Alice's window does not send it back changed: the forecast stays.
    a._flush_local()
    app.processEvents()
    assert json.loads(a.ycharts["webchart0001"])["trendlines"][0][
        "forward"] == 2

    # Deleting a chart on the desktop deletes it for everyone.
    from khervesheet.collab.charts import remove_chart
    remove_chart(chart)
    a._flush_local()
    assert wait_for(app, lambda: set(b.ycharts.keys()) == {"webchart0001"})
    # (Bob wrote the web chart himself, as a browser would: his desktop
    # window only draws charts that come from others.)
    assert wait_for(app, lambda: len(bob_sheet._charts) == 0)
