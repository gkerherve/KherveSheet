"""The MCP stdio server must speak protocol to a live KherveSheet.

These tests exercise ``khervesheet.mcp_server`` — the half an MCP host
launches — against a stand-in for the in-app bridge, so the handshake,
tool listing, tool calls and the "app not running" path are all
covered without needing a GUI.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import socket
import threading

import pytest

from khervesheet import mcp_server


_FAKE_TOOLS = [
    {"name": "read_cells", "description": "Read a range.",
     "input_schema": {"type": "object",
                      "properties": {"range": {"type": "string"}},
                      "required": ["range"]}},
]


class FakeBridge:
    """A one-connection stand-in for ``McpBridge`` on a real socket."""

    def __init__(self):
        self.token = "s3cret-token"
        self.calls = []
        self._srv = socket.socket()
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(4)
        self.port = self._srv.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._stop = False
        self._thread.start()

    def _serve(self):
        while not self._stop:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            threading.Thread(target=self._session, args=(conn,),
                             daemon=True).start()

    def _session(self, conn):
        buf = b""
        with conn:
            while not self._stop:
                try:
                    chunk = conn.recv(65536)
                except OSError:
                    return
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    line, _, buf = buf.partition(b"\n")
                    reply = self._handle(json.loads(line))
                    conn.sendall((json.dumps(reply) + "\n").encode())

    def _handle(self, req):
        if req.get("token") != self.token:
            return {"id": req.get("id"), "error": "Invalid bridge token."}
        method = req.get("method")
        if method == "get_status":
            return {"id": req["id"],
                    "result": {"version": "0.1.99+abc", "sheets": ["S1"]}}
        if method == "list_tools":
            return {"id": req["id"], "result": _FAKE_TOOLS}
        if method == "call_tool":
            self.calls.append(req["params"])
            name = req["params"]["name"]
            if name == "boom":
                return {"id": req["id"],
                        "result": {"error": "no such sheet"}}
            return {"id": req["id"], "result": {"values": [["1", "2"]]}}
        return {"id": req.get("id"), "error": f"unknown {method}"}

    def close(self):
        self._stop = True
        self._srv.close()


@pytest.fixture
def bridge_endpoint(tmp_path):
    fake = FakeBridge()
    path = tmp_path / "mcp-bridge.json"
    path.write_text(json.dumps({"host": "127.0.0.1", "port": fake.port,
                                "token": fake.token, "pid": 1,
                                "version": "0.1.99+abc"}))
    yield fake, str(path)
    fake.close()


@pytest.fixture
def server(bridge_endpoint):
    _fake, path = bridge_endpoint
    return mcp_server.McpServer(mcp_server.BridgeClient(path))


def _rpc(server, method, params=None, msg_id=1):
    return server.handle({"jsonrpc": "2.0", "id": msg_id,
                          "method": method, "params": params or {}})


# ── Handshake ──────────────────────────────────────────────────────

def test_initialize_echoes_a_protocol_version_the_client_asked_for(server):
    reply = _rpc(server, "initialize", {"protocolVersion": "2024-11-05"})
    assert reply["result"]["protocolVersion"] == "2024-11-05"
    assert reply["result"]["capabilities"]["tools"] == {"listChanged": False}


def test_initialize_falls_back_for_an_unknown_protocol_version(server):
    reply = _rpc(server, "initialize", {"protocolVersion": "1999-01-01"})
    assert reply["result"]["protocolVersion"] == mcp_server.LATEST_PROTOCOL


def test_initialize_reports_the_running_app_version(server):
    reply = _rpc(server, "initialize", {})
    assert reply["result"]["serverInfo"]["version"] == "0.1.99+abc"


def test_a_notification_gets_no_reply(server):
    assert server.handle({"jsonrpc": "2.0",
                          "method": "notifications/initialized"}) is None


# ── Tools ──────────────────────────────────────────────────────────

def test_tools_are_republished_with_mcp_schema_keys(server):
    tools = _rpc(server, "tools/list")["result"]["tools"]
    assert [t["name"] for t in tools] == ["read_cells"]
    # MCP spells it inputSchema; the app's tool table spells it
    # input_schema.  The translation is the point of this layer.
    assert tools[0]["inputSchema"]["required"] == ["range"]
    assert "input_schema" not in tools[0]


def test_a_tool_call_reaches_the_application(server, bridge_endpoint):
    fake, _ = bridge_endpoint
    reply = _rpc(server, "tools/call",
                 {"name": "read_cells",
                  "arguments": {"sheet_name": "S1", "range": "A1:B1"}})
    assert fake.calls == [{"name": "read_cells",
                           "input": {"sheet_name": "S1",
                                     "range": "A1:B1"}}]
    assert reply["result"]["isError"] is False
    assert json.loads(reply["result"]["content"][0]["text"]) == {
        "values": [["1", "2"]]}


def test_a_tool_error_is_flagged_rather_than_raised(server):
    reply = _rpc(server, "tools/call", {"name": "boom", "arguments": {}})
    assert reply["result"]["isError"] is True
    assert "no such sheet" in reply["result"]["content"][0]["text"]


def test_empty_resource_and_prompt_lists_keep_probing_hosts_quiet(server):
    assert _rpc(server, "resources/list")["result"] == {"resources": []}
    assert _rpc(server, "prompts/list")["result"] == {"prompts": []}


def test_an_unknown_method_is_a_jsonrpc_error(server):
    reply = _rpc(server, "sheets/teleport")
    assert reply["error"]["code"] == -32601


# ── The application is not running ─────────────────────────────────

def test_a_missing_endpoint_reports_how_to_fix_it(tmp_path):
    server = mcp_server.McpServer(
        mcp_server.BridgeClient(str(tmp_path / "absent.json")))
    reply = _rpc(server, "tools/call", {"name": "read_cells"})
    assert reply["error"]["code"] == -32000
    assert "Tools ▸ MCP Server" in reply["error"]["message"]


def test_initialize_still_succeeds_without_a_running_app(tmp_path):
    """A host that starts before KherveSheet must not see a failure."""
    server = mcp_server.McpServer(
        mcp_server.BridgeClient(str(tmp_path / "absent.json")))
    reply = _rpc(server, "initialize", {})
    assert reply["result"]["serverInfo"]["version"] == "unknown"


def test_a_bad_token_is_refused(bridge_endpoint, tmp_path):
    fake, _ = bridge_endpoint
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"host": "127.0.0.1", "port": fake.port,
                                "token": "not-the-token"}))
    server = mcp_server.McpServer(mcp_server.BridgeClient(str(path)))
    reply = _rpc(server, "tools/list")
    assert "token" in reply["error"]["message"].lower()


# ── The in-app bridge ──────────────────────────────────────────────

pytest.importorskip("PyQt5.QtNetwork")


class _FakeStack:
    """Records macro nesting so the undo policy can be asserted."""

    def __init__(self):
        self.macros = []
        self.open = 0

    def beginMacro(self, text):
        self.macros.append(text)
        self.open += 1

    def endMacro(self):
        self.open -= 1


class _FakeWorkbook:
    def all_sheets(self):
        return ["s1"]

    def name_of_sheet(self, s):
        return "Sheet1"


def _fake_window():
    """A QObject stand-in — McpBridge parents itself to the window."""
    from PyQt5.QtCore import QObject

    win = QObject()
    win._workbook = _FakeWorkbook()
    win._undo_stack = _FakeStack()
    return win


class _FakeExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, name, tool_input):
        self.calls.append((name, tool_input))
        if name == "explode":
            raise RuntimeError("kaboom")
        return {"ok": name}


@pytest.fixture
def live_bridge(tmp_path, monkeypatch):
    from PyQt5.QtWidgets import QApplication
    from khervesheet import mcp_bridge

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(mcp_bridge, "state_dir", lambda: str(tmp_path))
    monkeypatch.setattr(mcp_bridge, "endpoint_path",
                        lambda: str(tmp_path / "mcp-bridge.json"))
    win = _fake_window()
    bridge = mcp_bridge.McpBridge(win)
    bridge._executor = _FakeExecutor()
    assert bridge.start()
    yield bridge, win, app
    bridge.stop()


def _ask(bridge, app, method, params=None, token=None):
    """One request/response round-trip, pumping the Qt event loop."""
    sock = socket.create_connection(("127.0.0.1", bridge.port()), 5)
    sock.settimeout(5)
    sock.sendall((json.dumps({
        "id": 7,
        "token": bridge.token() if token is None else token,
        "method": method,
        "params": params or {},
    }) + "\n").encode())
    buf = b""
    for _ in range(500):
        app.processEvents()
        try:
            sock.settimeout(0.02)
            chunk = sock.recv(65536)
        except socket.timeout:
            continue
        if not chunk:
            break
        buf += chunk
        if b"\n" in buf:
            break
    sock.close()
    return json.loads(buf.split(b"\n")[0])


def test_the_bridge_publishes_an_endpoint_file(live_bridge, tmp_path):
    bridge, _win, _app = live_bridge
    info = json.loads((tmp_path / "mcp-bridge.json").read_text())
    assert info["port"] == bridge.port()
    assert info["token"] == bridge.token()
    assert info["host"] == "127.0.0.1"


def test_stopping_removes_the_endpoint_file(live_bridge, tmp_path):
    bridge, _win, _app = live_bridge
    bridge.stop()
    assert not (tmp_path / "mcp-bridge.json").exists()


def test_a_request_without_the_token_is_refused(live_bridge):
    bridge, win, app = live_bridge
    reply = _ask(bridge, app, "list_tools", token="guess")
    assert "token" in reply["error"].lower()
    assert win._undo_stack.macros == []


def test_a_mutating_call_is_wrapped_in_one_undo_macro(live_bridge):
    bridge, win, app = live_bridge
    reply = _ask(bridge, app, "call_tool",
                 {"name": "write_cells", "input": {"range": "A1"}})
    assert reply["result"] == {"ok": "write_cells"}
    assert win._undo_stack.macros == ["MCP: write_cells"]
    assert win._undo_stack.open == 0


def test_a_read_only_call_leaves_the_undo_stack_alone(live_bridge):
    bridge, win, app = live_bridge
    _ask(bridge, app, "call_tool",
         {"name": "read_cells", "input": {"range": "A1"}})
    assert win._undo_stack.macros == []


def test_a_raising_tool_closes_its_macro_and_answers(live_bridge):
    bridge, win, app = live_bridge
    reply = _ask(bridge, app, "call_tool", {"name": "explode"})
    assert "kaboom" in reply["error"]
    # A macro left open would swallow every later edit into it.
    assert win._undo_stack.open == 0


def test_the_bridge_lists_the_apps_real_tool_table(live_bridge):
    bridge, _win, app = live_bridge
    names = [t["name"] for t in _ask(bridge, app, "list_tools")["result"]]
    assert {"read_cells", "write_cells", "run_solver",
            "save_workbook"} <= set(names)
    # Default access is "edit", which withholds code execution.
    assert "set_python_cell" not in names


def test_full_access_publishes_the_python_tool(live_bridge):
    bridge, _win, app = live_bridge
    bridge.set_access("full")
    names = [t["name"] for t in _ask(bridge, app, "list_tools")["result"]]
    assert "set_python_cell" in names
