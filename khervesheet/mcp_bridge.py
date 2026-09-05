"""In-app half of KherveSheet's MCP support.

``McpBridge`` listens on a loopback TCP port and answers newline-
delimited JSON requests by running KherveSheet's existing AI tools —
the same twenty-odd tools the built-in AI chat uses — against the live
workbook.  ``mcp_server.py`` (spawned by the MCP host) is the only
intended client.

Why a socket rather than serving MCP from inside the app: MCP hosts
launch their servers as stdio subprocesses they own and restart at
will, while spreadsheet tools must run on the Qt GUI thread of an
already-running window.  The socket is the seam between the two.

Security posture: the listener binds to 127.0.0.1 only, and every
request must carry the random token from the endpoint file, which is
written user-readable only.  The bridge is off unless the user turns
it on in Tools ▸ MCP Server.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from collections import deque
from typing import Dict, Optional

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

from . import __version__
from .mcp_server import endpoint_path, state_dir

#: 0 lets the OS pick a free port; the endpoint file carries the choice.
DEFAULT_PORT = 0

#: Refuse absurd payloads rather than buffering without bound.
_MAX_LINE = 8 * 1024 * 1024

#: Tools that only inspect the workbook.  Wrapping these in an undo
#: macro would litter the stack with empty "MCP: read_cells" entries.
_READ_ONLY_TOOLS = frozenset({
    "get_sheet_info", "read_cells", "read_selection",
    "search_functions", "get_function_details",
    "list_charts", "get_chart_details",
    "get_document_info", "list_fit_models",
})

#: Tools that must run *outside* an undo macro.
#:
#: The document ones manipulate the stack themselves — saving marks it
#: clean, opening clears it — and Qt refuses both mid-macro, which
#: silently leaves a saved workbook still flagged as modified.  The
#: analysis ones each push exactly one bulk command already, so a
#: wrapper would only add an entry (an empty one when the caller asked
#: for a report and no output_cell).
_NO_MACRO_TOOLS = _READ_ONLY_TOOLS | {
    "save_workbook", "open_workbook", "new_workbook",
    "run_solver", "fit_trendline", "fit_peaks",
}

#: Tools that execute code the client wrote, in this process.
_CODE_TOOLS = frozenset({"set_python_cell"})

#: What a connected client is allowed to do, weakest first.  "edit" is
#: the default: an MCP client can change the workbook, but running
#: arbitrary Python in the app's own process is a separate, explicit
#: decision the user makes in Tools ▸ MCP Server.
ACCESS_LEVELS = ("read", "edit", "full")
DEFAULT_ACCESS = "edit"

#: How many recent calls the dialog's activity log shows.
_LOG_LEN = 200


def tool_allowed(name: str, access: str) -> bool:
    """Is *name* callable at this access level?"""
    if access == "full":
        return True
    if name in _CODE_TOOLS:
        return False
    if access == "edit":
        return True
    return name in _READ_ONLY_TOOLS


class McpBridge(QObject):
    """Loopback JSON server exposing the AI tool set to MCP clients."""

    started = pyqtSignal(int)              # port
    stopped = pyqtSignal()
    tool_invoked = pyqtSignal(str, str)    # tool name, summary

    def __init__(self, mainwindow):
        super().__init__(mainwindow)
        self._mw = mainwindow
        self._server: Optional[QTcpServer] = None
        self._buffers: Dict[QTcpSocket, bytes] = {}
        self._token = ""
        self._executor = None
        self._access = DEFAULT_ACCESS
        self._busy = False
        self.log: deque = deque(maxlen=_LOG_LEN)

    # ── Lifecycle ───────────────────────────────────────────────

    def is_running(self) -> bool:
        return self._server is not None and self._server.isListening()

    def port(self) -> int:
        return self._server.serverPort() if self.is_running() else 0

    def token(self) -> str:
        return self._token

    def access(self) -> str:
        return self._access

    def set_access(self, level: str):
        """Change what connected clients may do, effective immediately.

        Hosts cache ``tools/list`` from their startup, so tightening
        this mid-session shows up as a refusal rather than a shorter
        tool list until they reconnect.
        """
        if level not in ACCESS_LEVELS:
            raise ValueError(f"Unknown access level {level!r}")
        self._access = level

    def visible_tools(self) -> list:
        """The tool table as this access level sees it."""
        from .ai_backend import MCP_TOOLS
        return [t for t in MCP_TOOLS
                if tool_allowed(t["name"], self._access)]

    def start(self, port: int = DEFAULT_PORT) -> bool:
        """Begin listening.  Returns False (with no side effects) if
        the port could not be bound."""
        if self.is_running():
            return True
        server = QTcpServer(self)
        if not server.listen(QHostAddress.LocalHost, port):
            server.deleteLater()
            return False
        server.newConnection.connect(self._on_new_connection)
        self._server = server
        self._token = secrets.token_urlsafe(32)
        self._write_endpoint()
        self.started.emit(server.serverPort())
        return True

    def stop(self):
        if self._server is not None:
            for sock in list(self._buffers):
                sock.disconnectFromHost()
            self._buffers.clear()
            self._server.close()
            self._server.deleteLater()
            self._server = None
        self._token = ""
        self._clear_endpoint()
        self.stopped.emit()

    # ── Endpoint file ───────────────────────────────────────────

    def _write_endpoint(self):
        """Publish host/port/token so the stdio server can find us."""
        try:
            os.makedirs(state_dir(), exist_ok=True)
            path = endpoint_path()
            payload = {
                "host": "127.0.0.1",
                "port": self.port(),
                "token": self._token,
                "pid": os.getpid(),
                "version": __version__,
            }
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            try:
                os.chmod(path, 0o600)   # best effort; a no-op on Windows
            except OSError:
                pass
        except Exception:
            pass

    def _clear_endpoint(self):
        try:
            os.remove(endpoint_path())
        except OSError:
            pass

    # ── Socket plumbing ─────────────────────────────────────────

    def _on_new_connection(self):
        while self._server is not None and self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            self._buffers[sock] = b""
            sock.readyRead.connect(lambda s=sock: self._on_ready_read(s))
            sock.disconnected.connect(lambda s=sock: self._on_closed(s))

    def _on_closed(self, sock: QTcpSocket):
        self._buffers.pop(sock, None)
        sock.deleteLater()

    def _on_ready_read(self, sock: QTcpSocket):
        buf = self._buffers.get(sock, b"") + bytes(sock.readAll())
        if len(buf) > _MAX_LINE:
            sock.disconnectFromHost()
            self._buffers.pop(sock, None)
            return
        while b"\n" in buf:
            line, _, buf = buf.partition(b"\n")
            if line.strip():
                self._handle_line(sock, line)
        self._buffers[sock] = buf

    def _handle_line(self, sock: QTcpSocket, line: bytes):
        try:
            req = json.loads(line.decode("utf-8"))
        except Exception:
            self._reply(sock, None, error="Malformed JSON request.")
            return
        req_id = req.get("id")
        if not secrets.compare_digest(str(req.get("token", "")),
                                      self._token):
            self._reply(sock, req_id, error="Invalid bridge token.")
            return
        method = req.get("method")
        params = req.get("params") or {}
        try:
            if method == "get_status":
                self._reply(sock, req_id, result=self._status())
            elif method == "list_tools":
                self._reply(sock, req_id, result=self.visible_tools())
            elif method == "call_tool":
                self._reply(sock, req_id,
                            result=self._call_tool(params))
            else:
                self._reply(sock, req_id,
                            error=f"Unknown bridge method: {method!r}")
        except Exception as exc:
            self._reply(sock, req_id, error=str(exc))

    def _reply(self, sock: QTcpSocket, req_id, *, result=None, error=None):
        payload = {"id": req_id}
        if error is not None:
            payload["error"] = error
        else:
            payload["result"] = result
        try:
            data = json.dumps(payload, default=str) + "\n"
        except Exception as exc:
            data = json.dumps(
                {"id": req_id,
                 "error": f"Unserialisable result: {exc}"}) + "\n"
        sock.write(data.encode("utf-8"))
        sock.flush()

    # ── Tool execution (main/GUI thread) ────────────────────────

    def _status(self) -> dict:
        wb = self._mw._workbook
        return {
            "app": "KherveSheet",
            "version": __version__,
            "pid": os.getpid(),
            "access": self._access,
            "sheets": [wb.name_of_sheet(s) for s in wb.all_sheets()],
        }

    def _record(self, name: str, outcome: str):
        self.log.append({"time": time.strftime("%H:%M:%S"),
                         "tool": name, "outcome": outcome})
        self.tool_invoked.emit(name, outcome)

    def _call_tool(self, params: dict) -> dict:
        name = params.get("name")
        if not name:
            return {"error": "Missing tool name."}
        if not tool_allowed(name, self._access):
            reason = (
                f"{name} runs code the client supplies inside "
                f"KherveSheet, which needs MCP access set to 'Full'."
                if name in _CODE_TOOLS else
                f"{name} would change the workbook, and MCP access is "
                f"set to 'Read only'.")
            self._record(str(name), "refused")
            return {"error": f"Refused: {reason} The user can change "
                             f"this in Tools \u25b8 MCP Server."}
        # The Solver and the fitting tools pump the Qt event loop while
        # they run, which can deliver a second request into this same
        # handler.  Two tool calls interleaving on one workbook would
        # corrupt both, so make the second wait its turn by failing.
        if self._busy:
            self._record(str(name), "busy")
            return {"error": "KherveSheet is still running the previous "
                             "tool call. Retry when it finishes."}
        tool_input = params.get("input") or {}
        if self._executor is None:
            from .ai_tools import AiToolExecutor
            self._executor = AiToolExecutor(self._mw)
        # One macro per mutating call keeps the app's undo promise: a
        # single Ctrl+Z reverts whatever the remote agent just did.
        stack = self._mw._undo_stack
        macro = name not in _NO_MACRO_TOOLS
        if macro:
            stack.beginMacro(f"MCP: {name}")
        self._busy = True
        try:
            result = self._executor.execute(name, tool_input)
        finally:
            self._busy = False
            if macro:
                stack.endMacro()
        summary = (result.get("error") if isinstance(result, dict)
                   and "error" in result else "ok")
        self._record(str(name), str(summary))
        return result
