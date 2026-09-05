# KherveSheet — MCP server dialog
# Copyright (C) 2024-2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later

"""Control panel for the MCP (Model Context Protocol) bridge.

Shows whether the bridge is listening and, more usefully, hands the
user a ready-made configuration block for their MCP host — Claude
Desktop, Claude Code, Cursor and friends all take the same
``command``/``args`` shape, so one snippet plus a Copy button covers
the lot.  Getting that snippet right by hand (the interpreter path in
particular) is the step people trip on.
"""

from __future__ import annotations

import json
import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from .mcp_server import SERVER_NAME, endpoint_path


def launch_command() -> list:
    """Argv an MCP host should run to reach this installation.

    A frozen build re-executes itself with ``--mcp-server``; a source
    checkout runs the module under the same interpreter, from the
    package's parent directory so the import resolves.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--mcp-server"]
    return [sys.executable, "-m", "khervesheet.mcp_server"]


def host_config(indent_key: bool = True) -> str:
    """JSON snippet for an MCP host's config file."""
    argv = launch_command()
    entry = {"command": argv[0], "args": argv[1:]}
    if not getattr(sys, "frozen", False):
        # Run from the checkout so `-m khervesheet.mcp_server` resolves
        # regardless of where the host launches the process.
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        entry["cwd"] = root
    block = {"mcpServers": {SERVER_NAME: entry}}
    return json.dumps(block, indent=2)


def cli_command() -> str:
    """One-liner for `claude mcp add`."""
    argv = launch_command()
    quoted = " ".join(
        f'"{a}"' if " " in a else a for a in argv)
    return f"claude mcp add {SERVER_NAME} -- {quoted}"


class McpServerDialog(QDialog):
    """Enable/disable the bridge and copy the host configuration."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self.setWindowTitle("MCP Server")
        self.setMinimumWidth(620)
        self._build_ui()
        self._refresh()
        # Bound methods, not lambdas: PyQt drops the connection when
        # this dialog is destroyed (it is WA_DeleteOnClose), whereas a
        # lambda would outlive it and fire on a deleted widget.
        bridge.started.connect(self._on_bridge_started)
        bridge.stopped.connect(self._refresh)

    # ── UI ───────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)

        blurb = QLabel(
            "Let any MCP-compatible assistant — Claude Desktop, Claude "
            "Code, Cursor, Zed — read and edit this workbook directly.\n"
            "The assistant gets the same tools as the built-in AI chat, "
            "and every change it makes is undoable with Ctrl+Z.")
        blurb.setWordWrap(True)
        lay.addWidget(blurb)

        self._enable = QCheckBox("Enable MCP server")
        self._enable.toggled.connect(self._on_toggled)
        lay.addWidget(self._enable)

        self._status = QLabel()
        self._status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self._status)

        row = QHBoxLayout()
        row.addWidget(QLabel("Configuration for:"))
        self._flavour = QComboBox()
        self._flavour.addItems([
            "Claude Desktop / Cursor / Zed (JSON)",
            "Claude Code (command line)",
        ])
        self._flavour.currentIndexChanged.connect(self._refresh_snippet)
        row.addWidget(self._flavour, 1)
        lay.addLayout(row)

        self._snippet = QPlainTextEdit()
        self._snippet.setReadOnly(True)
        mono = QFont("Consolas" if sys.platform.startswith("win")
                     else "Monospace")
        mono.setStyleHint(QFont.TypeWriter)
        mono.setPointSize(9)
        self._snippet.setFont(mono)
        self._snippet.setMinimumHeight(150)
        lay.addWidget(self._snippet)

        hint = QLabel(
            "Paste the JSON into your host's config file (Claude "
            "Desktop: <i>claude_desktop_config.json</i>), then restart "
            "it. KherveSheet must be running with this box ticked for "
            "the tools to work.")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        copy = QPushButton("Copy")
        copy.clicked.connect(self._copy)
        btns.addButton(copy, QDialogButtonBox.ActionRole)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    # ── Behaviour ────────────────────────────────────────────────────

    def _on_bridge_started(self, _port: int):
        self._refresh()

    def _on_toggled(self, on: bool):
        if on:
            if not self._bridge.start():
                self._enable.setChecked(False)
                self._status.setText(
                    "<b>Could not open a local port.</b> Another "
                    "process may be holding it.")
                return
        else:
            self._bridge.stop()
        self._save_pref(on)
        self._refresh()

    def _save_pref(self, on: bool):
        from PyQt5.QtCore import QSettings
        QSettings("KherveSheet", "KherveSheet").setValue(
            "mcp/enabled", bool(on))

    def _refresh(self):
        running = self._bridge.is_running()
        self._enable.blockSignals(True)
        self._enable.setChecked(running)
        self._enable.blockSignals(False)
        if running:
            self._status.setText(
                f"<b style='color:#2e7d32'>Listening</b> on "
                f"127.0.0.1:{self._bridge.port()} — endpoint file: "
                f"{endpoint_path()}")
        else:
            self._status.setText(
                "<b style='color:#b71c1c'>Stopped</b> — MCP clients "
                "cannot reach this workbook.")
        self._refresh_snippet()

    def _refresh_snippet(self):
        if self._flavour.currentIndex() == 0:
            self._snippet.setPlainText(host_config())
        else:
            self._snippet.setPlainText(cli_command())

    def _copy(self):
        QApplication.clipboard().setText(self._snippet.toPlainText())
