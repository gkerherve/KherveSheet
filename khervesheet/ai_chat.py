"""AI chat dock — sidebar UI for the Claude assistant.

Provides ``AiChatDock`` (a QDockWidget) with a scrollable message
history, text input, typing indicator, and an API-key settings dialog.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer, QSettings, pyqtSignal
from PyQt5.QtGui import QColor, QKeySequence
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QToolButton, QScrollArea, QFrame,
    QDialog, QLineEdit, QComboBox, QFormLayout, QDialogButtonBox,
    QSizePolicy, QShortcut, QApplication,
)

from .ai_backend import AiBackend, HAVE_ANTHROPIC
from . import icons


# ── Re-export the guard so mainwindow can check without extra import.
__all__ = ["AiChatDock", "HAVE_ANTHROPIC"]


# ── API key / settings dialog ─────────────────────────────────────

class ApiKeyDialog(QDialog):
    """Small dialog to enter the Claude API key and choose a model."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Chat Settings")
        self.setMinimumWidth(420)
        layout = QFormLayout(self)

        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.Password)
        self._key_edit.setPlaceholderText("sk-ant-...")
        layout.addRow("API Key:", self._key_edit)

        self._model_combo = QComboBox()
        self._model_combo.addItems([
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-haiku-4-5-20251001",
        ])
        layout.addRow("Model:", self._model_combo)

        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

        # Load saved values.
        s = QSettings("KherveSheet", "KherveSheet")
        self._key_edit.setText(s.value("ai/api_key", ""))
        saved_model = s.value("ai/model", "claude-sonnet-4-20250514")
        idx = self._model_combo.findText(saved_model)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)

    def accept(self):
        s = QSettings("KherveSheet", "KherveSheet")
        s.setValue("ai/api_key", self._key_edit.text().strip())
        s.setValue("ai/model", self._model_combo.currentText())
        super().accept()


# ── Chat bubble ────────────────────────────────────────────────────

class ChatBubble(QFrame):
    """A single message bubble in the chat history."""

    def __init__(self, role: str, text: str = "", parent=None):
        super().__init__(parent)
        self._role = role
        self.setFrameShape(QFrame.StyledPanel)
        self.setLineWidth(0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)

        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self._label.setOpenExternalLinks(True)
        layout.addWidget(self._label)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._apply_style()

    def _apply_style(self):
        if self._role == "user":
            self.setStyleSheet(
                "ChatBubble { background: #DCE8F7; border-radius: 8px; }")
        elif self._role == "tool":
            self.setStyleSheet(
                "ChatBubble { background: #E8E8E8; border-radius: 6px; "
                "font-size: 11px; }")
        else:
            self.setStyleSheet(
                "ChatBubble { background: #F0F0F0; border-radius: 8px; }")

    def append_text(self, text: str):
        self._label.setText(self._label.text() + text)

    def set_text(self, text: str):
        self._label.setText(text)


# ── Typing indicator ──────────────────────────────────────────────

class _TypingIndicator(QLabel):
    """Animated '...' indicator shown while waiting for a response."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dots = 0
        self._timer = QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._tick)
        self.setStyleSheet(
            "color: #888; font-style: italic; padding: 4px 10px;")
        self.hide()

    def start(self):
        self._dots = 0
        self.setText("Claude is thinking")
        self.show()
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._dots = (self._dots + 1) % 4
        self.setText("Claude is thinking" + "." * self._dots)


# ── Send-on-enter text edit ───────────────────────────────────────

class _ChatInput(QPlainTextEdit):
    """Text input that emits *submit* on Enter (Ctrl+Enter for newline).

    Up/Down arrows recall previously sent messages, shell-style.  The
    history is persisted to QSettings so it survives restarts.  Arrow
    navigation only kicks in at the first/last line so multi-line
    drafts can still be edited normally.
    """

    submit = pyqtSignal()

    _MAX_HISTORY = 100
    _SETTINGS_KEY = "ai/input_history"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Ask Claude to edit the spreadsheet…")
        self.setMaximumHeight(80)
        self.setTabChangesFocus(True)
        # Sent-message history (oldest first), loaded from settings.
        s = QSettings("KherveSheet", "KherveSheet")
        stored = s.value(self._SETTINGS_KEY, []) or []
        self._history: list = [str(x) for x in stored]
        self._hist_index: int | None = None  # None = editing a fresh draft
        self._draft: str = ""                 # unsent text saved on recall

    def add_history(self, text: str):
        """Record a sent message and reset navigation state."""
        text = text.rstrip()
        if text and (not self._history or self._history[-1] != text):
            self._history.append(text)
            if len(self._history) > self._MAX_HISTORY:
                self._history = self._history[-self._MAX_HISTORY:]
            s = QSettings("KherveSheet", "KherveSheet")
            s.setValue(self._SETTINGS_KEY, self._history)
        self._hist_index = None
        self._draft = ""

    def clear_history(self):
        self._history.clear()
        self._hist_index = None
        self._draft = ""
        s = QSettings("KherveSheet", "KherveSheet")
        s.setValue(self._SETTINGS_KEY, [])

    # ── History navigation ──────────────────────────────────────

    def _on_first_line(self) -> bool:
        return self.textCursor().blockNumber() == 0

    def _on_last_line(self) -> bool:
        return (self.textCursor().blockNumber()
                == self.document().blockCount() - 1)

    def _move_cursor_end(self):
        cur = self.textCursor()
        cur.movePosition(cur.End)
        self.setTextCursor(cur)

    def _history_prev(self):
        if not self._history:
            return
        if self._hist_index is None:
            # Entering history — stash the current unsent draft.
            self._draft = self.toPlainText()
            self._hist_index = len(self._history)
        if self._hist_index > 0:
            self._hist_index -= 1
            self.setPlainText(self._history[self._hist_index])
            self._move_cursor_end()

    def _history_next(self):
        if self._hist_index is None:
            return
        self._hist_index += 1
        if self._hist_index >= len(self._history):
            # Past the newest entry — restore the saved draft.
            self._hist_index = None
            self.setPlainText(self._draft)
        else:
            self.setPlainText(self._history[self._hist_index])
        self._move_cursor_end()

    def keyPressEvent(self, event):
        key = event.key()
        ctrl = event.modifiers() & Qt.ControlModifier
        if key in (Qt.Key_Return, Qt.Key_Enter) and not ctrl:
            self.submit.emit()
            return
        # Ctrl+Enter → insert newline.
        if key in (Qt.Key_Return, Qt.Key_Enter) and ctrl:
            self.insertPlainText("\n")
            return
        # Up/Down recall history when at the first/last line.
        if key == Qt.Key_Up and self._on_first_line():
            self._history_prev()
            return
        if key == Qt.Key_Down and self._on_last_line():
            self._history_next()
            return
        super().keyPressEvent(event)


# ── Chat dock widget ──────────────────────────────────────────────

class AiChatDock(QDockWidget):
    """Dockable AI chat sidebar."""

    def __init__(self, mainwindow):
        super().__init__("AI Chat", mainwindow)
        self.setObjectName("AiChatDock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setMinimumWidth(320)
        self._mw = mainwindow
        self._current_bubble: ChatBubble | None = None
        self._busy = False

        # ── Container widget ────────────────────────────────────
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # Header.
        header = QHBoxLayout()
        title = QLabel("<b>Claude AI</b>")
        header.addWidget(title)
        header.addStretch()
        gear_btn = QToolButton()
        gear_btn.setIcon(icons.themed_icon("mdi.cog"))
        gear_btn.setToolTip("AI Chat settings")
        gear_btn.clicked.connect(self._open_settings)
        header.addWidget(gear_btn)
        clear_btn = QToolButton()
        clear_btn.setIcon(icons.themed_icon("mdi.delete-sweep"))
        clear_btn.setToolTip("Clear conversation")
        clear_btn.clicked.connect(self._clear_chat)
        header.addWidget(clear_btn)
        main_layout.addLayout(header)

        # Scroll area for messages.
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._msg_container = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setAlignment(Qt.AlignTop)
        self._msg_layout.setContentsMargins(2, 2, 2, 2)
        self._msg_layout.setSpacing(6)
        self._scroll.setWidget(self._msg_container)
        main_layout.addWidget(self._scroll, stretch=1)

        # Typing indicator.
        self._typing = _TypingIndicator()
        main_layout.addWidget(self._typing)

        # Input area.
        input_row = QHBoxLayout()
        self._input = _ChatInput()
        self._input.submit.connect(self._send)
        input_row.addWidget(self._input, stretch=1)

        btn_col = QVBoxLayout()
        self._send_btn = QToolButton()
        self._send_btn.setIcon(icons.themed_icon("mdi.send"))
        self._send_btn.setToolTip("Send (Enter)")
        self._send_btn.clicked.connect(self._send)
        btn_col.addWidget(self._send_btn)
        self._stop_btn = QToolButton()
        self._stop_btn.setIcon(icons.themed_icon("mdi.stop"))
        self._stop_btn.setToolTip("Stop generation")
        self._stop_btn.clicked.connect(self._cancel)
        self._stop_btn.hide()
        btn_col.addWidget(self._stop_btn)
        btn_col.addStretch()
        input_row.addLayout(btn_col)
        main_layout.addLayout(input_row)

        self.setWidget(container)

        # ── Backend ─────────────────────────────────────────────
        self._backend = AiBackend(mainwindow)
        self._backend.chunk_ready.connect(self._on_chunk)
        self._backend.tool_performed.connect(self._on_tool)
        self._backend.turn_done.connect(self._on_done)
        self._backend.error.connect(self._on_error)

        # Welcome bubble.
        welcome = ChatBubble("assistant",
                             "Hello! I can help you edit your spreadsheet. "
                             "Try asking me to create a template, fill data, "
                             "format cells, or insert a chart.")
        self._msg_layout.addWidget(welcome)

    # ── Actions ─────────────────────────────────────────────────

    def _send(self):
        text = self._input.toPlainText().strip()
        if not text or self._busy:
            return
        # Show user bubble.
        bubble = ChatBubble("user", text)
        self._msg_layout.addWidget(bubble)
        self._input.add_history(text)
        self._input.clear()
        self._set_busy(True)
        self._current_bubble = None
        self._backend.send(text)

    def _cancel(self):
        self._backend.cancel()
        self._set_busy(False)

    def _open_settings(self):
        dlg = ApiKeyDialog(self)
        dlg.exec_()

    def _clear_chat(self):
        # Remove all bubbles.
        while self._msg_layout.count():
            item = self._msg_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._current_bubble = None
        self._backend._messages.clear()
        # Re-add welcome.
        welcome = ChatBubble("assistant",
                             "Conversation cleared. How can I help?")
        self._msg_layout.addWidget(welcome)

    # ── Slots from backend ──────────────────────────────────────

    def _on_chunk(self, text: str):
        if self._current_bubble is None:
            self._typing.stop()
            self._current_bubble = ChatBubble("assistant")
            self._msg_layout.addWidget(self._current_bubble)
        self._current_bubble.append_text(text)
        self._scroll_to_bottom()

    def _on_tool(self, name: str, summary: str):
        bubble = ChatBubble("tool", f"⚙ {summary}")
        self._msg_layout.addWidget(bubble)
        self._scroll_to_bottom()

    def _on_done(self):
        self._set_busy(False)
        self._scroll_to_bottom()

    def _on_error(self, msg: str):
        self._typing.stop()
        bubble = ChatBubble("assistant")
        bubble.setStyleSheet(
            "ChatBubble { background: #FDDEDE; border-radius: 8px; }")
        bubble.set_text(f"Error: {msg}")
        self._msg_layout.addWidget(bubble)
        self._set_busy(False)
        self._scroll_to_bottom()

    # ── Helpers ─────────────────────────────────────────────────

    def _set_busy(self, busy: bool):
        self._busy = busy
        self._send_btn.setVisible(not busy)
        self._stop_btn.setVisible(busy)
        self._input.setReadOnly(busy)
        if busy:
            self._typing.start()
        else:
            self._typing.stop()

    def _scroll_to_bottom(self):
        QApplication.processEvents()
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def closeEvent(self, event):
        self._backend.shutdown()
        super().closeEvent(event)
