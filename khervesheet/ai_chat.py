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

import base64

from PyQt5.QtCore import (
    Qt, QTimer, QSettings, QBuffer, QByteArray, QSize, pyqtSignal,
)
from PyQt5.QtGui import (
    QColor, QKeySequence, QImage, QPixmap, QTextDocument,
)
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


# Cap pasted images so payloads stay reasonable for the vision APIs.
_MAX_IMG_DIM = 1400


def _qimage_to_b64_png(img: QImage) -> str:
    """Encode a QImage as base64 PNG, downscaling very large images."""
    if max(img.width(), img.height()) > _MAX_IMG_DIM:
        img = img.scaled(_MAX_IMG_DIM, _MAX_IMG_DIM,
                         Qt.KeepAspectRatio, Qt.SmoothTransformation)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return base64.b64encode(bytes(ba)).decode("ascii")


# ── API key / settings dialog ─────────────────────────────────────

class ApiKeyDialog(QDialog):
    """Choose an AI provider (Anthropic, Mistral, Ollama) and configure
    its model, API key, and — for Ollama — the server host."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from .ai_providers import PROVIDERS, DEFAULT_HOST
        self._PROVIDERS = PROVIDERS
        self._DEFAULT_HOST = DEFAULT_HOST
        self.setWindowTitle("AI Chat Settings")
        self.setMinimumWidth(440)
        layout = QFormLayout(self)

        # Provider selector — annotate any whose SDK isn't installed.
        from .ai_providers import is_available
        self._provider_combo = QComboBox()
        self._provider_keys = list(PROVIDERS.keys())
        for key in self._provider_keys:
            label = PROVIDERS[key]["label"]
            if not is_available(key):
                label += "  — not installed"
            self._provider_combo.addItem(label, key)
        layout.addRow("Provider:", self._provider_combo)

        # Model (editable so local/custom names can be typed).
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        model_row = QHBoxLayout()
        model_row.addWidget(self._model_combo, stretch=1)
        self._refresh_btn = QToolButton()
        self._refresh_btn.setText("⟳")
        self._refresh_btn.setToolTip("Refresh model list from server")
        self._refresh_btn.clicked.connect(self._refresh_models)
        model_row.addWidget(self._refresh_btn)
        layout.addRow("Model:", model_row)

        # API key.
        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.Password)
        self._key_label = QLabel("API Key:")
        layout.addRow(self._key_label, self._key_edit)

        # Ollama host.
        self._host_edit = QLineEdit()
        self._host_edit.setPlaceholderText(DEFAULT_HOST)
        self._host_label = QLabel("Ollama Host:")
        layout.addRow(self._host_label, self._host_edit)

        # Provider-specific help text.
        self._help_texts = {
            "anthropic": (
                "To get an API key:\n"
                "1. Go to console.anthropic.com\n"
                "2. Sign up or log in\n"
                "3. Navigate to API Keys in the left sidebar\n"
                '4. Click "Create Key" and copy the key (starts with sk-ant-)\n'
                "5. Add credit to your account under Billing"
            ),
            "openai": (
                "To get an API key:\n"
                "1. Go to platform.openai.com\n"
                "2. Sign up or log in\n"
                "3. Navigate to API Keys in the left sidebar\n"
                '4. Click "Create new secret key" and copy it (starts with sk-)\n'
                "5. Add credit under Billing > Payment methods"
            ),
            "mistral": (
                "To get an API key:\n"
                "1. Go to console.mistral.ai\n"
                "2. Sign up or log in\n"
                "3. Navigate to API Keys\n"
                '4. Click "Create new key" and copy it\n'
                "5. Add credit under Billing"
            ),
            "ollama": (
                "Ollama runs locally \u2014 no API key needed.\n"
                "1. Download and install from ollama.com\n"
                '2. Run "ollama pull <model>" to download a model\n'
                "   (e.g. ollama pull llama3, ollama pull mistral)\n"
                "3. The server starts automatically on localhost:11434\n"
                "4. Use the Refresh button (\u27f3) to see available models"
            ),
        }
        from PyQt5.QtWidgets import QGroupBox
        self._help_group = QGroupBox("How to get an API key")
        help_layout = QVBoxLayout(self._help_group)
        self._help_label = QLabel()
        self._help_label.setWordWrap(True)
        font = self._help_label.font()
        font.setPointSize(max(font.pointSize() - 1, 7))
        self._help_label.setFont(font)
        self._help_label.setStyleSheet(
            "color: #555; background: transparent; padding: 2px;")
        help_layout.addWidget(self._help_label)
        layout.addRow(self._help_group)

        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

        # Load saved values and react to provider changes.
        s = QSettings("KherveSheet", "KherveSheet")
        self._host_edit.setText(s.value("ai/ollama_host", DEFAULT_HOST))
        saved_provider = s.value("ai/provider", "anthropic")
        if saved_provider not in PROVIDERS:
            saved_provider = "anthropic"
        self._provider_combo.setCurrentIndex(
            self._provider_keys.index(saved_provider))
        self._provider_combo.currentIndexChanged.connect(
            self._on_provider_changed)
        self._on_provider_changed()  # populate for the initial provider

    def _current_provider(self) -> str:
        return self._provider_combo.currentData()

    def _on_provider_changed(self):
        provider = self._current_provider()
        spec = self._PROVIDERS[provider]
        s = QSettings("KherveSheet", "KherveSheet")
        # Repopulate model list, restoring this provider's saved model.
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        self._model_combo.addItems(spec["models"])
        saved_model = s.value(
            f"ai/model_{provider}", spec["default_model"])
        self._model_combo.setCurrentText(saved_model)
        self._model_combo.blockSignals(False)
        # Show/hide key + host fields per provider needs.
        self._key_label.setVisible(spec["needs_key"])
        self._key_edit.setVisible(spec["needs_key"])
        self._key_edit.setText(s.value(f"ai/key_{provider}", ""))
        placeholder = {"anthropic": "sk-ant-...",
                       "openai": "sk-..."}.get(provider, "")
        self._key_edit.setPlaceholderText(placeholder)
        self._host_label.setVisible(spec["needs_host"])
        self._host_edit.setVisible(spec["needs_host"])
        # Refresh button only for providers that support model listing.
        self._refresh_btn.setVisible(spec.get("refreshable", False))
        # Update help text for this provider.
        self._help_label.setText(
            self._help_texts.get(provider, ""))
        title = ("How to set up Ollama" if provider == "ollama"
                 else "How to get an API key")
        self._help_group.setTitle(title)

    def _refresh_models(self):
        """Fetch the live model list from the provider's server."""
        from .ai_providers import fetch_models
        provider = self._current_provider()
        api_key = self._key_edit.text().strip()
        host = self._host_edit.text().strip()
        try:
            models = fetch_models(provider, api_key=api_key, host=host)
        except Exception as exc:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Refresh failed", str(exc))
            return
        current = self._model_combo.currentText()
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        self._model_combo.addItems(models)
        if current in models:
            self._model_combo.setCurrentText(current)
        self._model_combo.blockSignals(False)

    def accept(self):
        provider = self._current_provider()
        s = QSettings("KherveSheet", "KherveSheet")
        s.setValue("ai/provider", provider)
        s.setValue(f"ai/model_{provider}",
                   self._model_combo.currentText().strip())
        if self._PROVIDERS[provider]["needs_key"]:
            s.setValue(f"ai/key_{provider}", self._key_edit.text().strip())
        if self._PROVIDERS[provider]["needs_host"]:
            host = self._host_edit.text().strip() or self._DEFAULT_HOST
            s.setValue("ai/ollama_host", host)
        super().accept()


# ── Markdown rendering ─────────────────────────────────────────────

def _markdown_to_html(md: str, font) -> str:
    """Render Markdown to Qt-compatible HTML using Qt's own parser.

    Uses QTextDocument.setMarkdown (GitHub dialect) so no extra
    dependency is needed; the document's default font is set to *font*
    so the rendered size tracks the chat's zoom level.
    """
    doc = QTextDocument()
    if font is not None:
        doc.setDefaultFont(font)
    try:
        doc.setMarkdown(md, QTextDocument.MarkdownDialectGitHub)
    except Exception:
        doc.setPlainText(md)
    return doc.toHtml()


# ── Chat bubble ────────────────────────────────────────────────────

class ChatBubble(QFrame):
    """A single message bubble in the chat history.

    Assistant/tool bubbles render their text as Markdown; user bubbles
    stay plain so a typed ``*`` or ``#`` is shown verbatim.
    """

    def __init__(self, role: str, text: str = "", parent=None,
                 font_pt: float = 10.0):
        super().__init__(parent)
        self._role = role
        self._raw = text          # markdown / plain source text
        self._font_pt = font_pt
        self.setFrameShape(QFrame.StyledPanel)
        self.setLineWidth(0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)

        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setMinimumWidth(0)
        self._label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self._label.setOpenExternalLinks(True)
        self._label.setStyleSheet("background: transparent;")
        layout.addWidget(self._label)

        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._apply_style()
        self.set_font_pt(font_pt)

    def _apply_style(self):
        # Background only — font size is controlled via set_font_pt so the
        # dock's zoom buttons take effect (a stylesheet font-size would
        # override QFont and break zooming).
        if self._role == "user":
            self.setStyleSheet(
                "ChatBubble { background: #DCE8F7; border-radius: 8px; }")
        elif self._role == "tool":
            self.setStyleSheet(
                "ChatBubble { background: #E8E8E8; border-radius: 6px; }")
        else:
            self.setStyleSheet(
                "ChatBubble { background: #F0F0F0; border-radius: 8px; }")

    def set_font_pt(self, pt: float):
        """Apply a point size; tool 'receipts' render one point smaller."""
        self._font_pt = pt
        f = self._label.font()
        f.setPointSizeF(max(7.0, pt - 1.0) if self._role == "tool" else pt)
        self._label.setFont(f)
        self._render()

    def _render(self):
        """Refresh the label from the raw source text."""
        if self._role == "assistant":
            self._label.setTextFormat(Qt.RichText)
            self._label.setText(
                _markdown_to_html(self._raw, self._label.font()))
        else:
            # User text and tool receipts (which contain formulas with
            # * and _ that markdown would mangle) stay verbatim.
            self._label.setTextFormat(Qt.PlainText)
            self._label.setText(self._raw)

    def append_text(self, text: str):
        self._raw += text
        self._render()

    def set_text(self, text: str):
        self._raw = text
        self._render()

    def add_image_b64(self, b64: str):
        """Show a base64-PNG thumbnail inside the bubble."""
        pm = QPixmap()
        try:
            pm.loadFromData(base64.b64decode(b64))
        except Exception:
            return
        if pm.isNull():
            return
        lbl = QLabel()
        lbl.setPixmap(pm.scaledToWidth(
            min(220, pm.width()), Qt.SmoothTransformation))
        self.layout().addWidget(lbl)


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
    image_pasted = pyqtSignal(object)  # QImage

    _MAX_HISTORY = 100
    _SETTINGS_KEY = "ai/input_history"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Ask Claude to edit the spreadsheet…")
        self.setMaximumHeight(80)
        self.setMinimumWidth(40)
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

    # ── Image paste ─────────────────────────────────────────────

    def canInsertFromMimeData(self, source):
        if source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        """Intercept pasted images; let everything else paste as text."""
        if source.hasImage():
            img = source.imageData()
            if not isinstance(img, QImage):
                img = QImage(img)
            if img is not None and not img.isNull():
                self.image_pasted.emit(img)
                return
        super().insertFromMimeData(source)


# ── Chat dock widget ──────────────────────────────────────────────

class AiChatDock(QDockWidget):
    """Dockable AI chat sidebar."""

    def __init__(self, mainwindow):
        super().__init__("AI Chat", mainwindow)
        self.setObjectName("AiChatDock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setMinimumWidth(120)
        self.setMaximumWidth(600)
        self._mw = mainwindow
        self._current_bubble: ChatBubble | None = None
        self._busy = False
        # Chat font size (points), persisted across sessions.
        _s = QSettings("KherveSheet", "KherveSheet")
        self._font_pt = float(_s.value("ai/chat_font_pt", 10.0))

        # ── Container widget ────────────────────────────────────
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # Header.
        header = QHBoxLayout()
        self._title = QLabel("<b>AI Assistant</b>")
        self._title.setMinimumWidth(0)
        self._title.setSizePolicy(
            QSizePolicy.Ignored, QSizePolicy.Preferred)
        header.addWidget(self._title, stretch=1)
        header.addStretch()
        smaller_btn = QToolButton()
        smaller_btn.setText("A−")  # A−
        smaller_btn.setToolTip("Decrease text size")
        smaller_btn.clicked.connect(lambda: self._change_font(-1))
        header.addWidget(smaller_btn)
        larger_btn = QToolButton()
        larger_btn.setText("A+")
        larger_btn.setToolTip("Increase text size")
        larger_btn.clicked.connect(lambda: self._change_font(+1))
        header.addWidget(larger_btn)
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
        self._scroll.setMinimumWidth(0)
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

        # Pending-image attachment strip (hidden until an image is pasted).
        self._pending_images: list = []  # [{"media_type","data","chip"}]
        self._attach_bar = QWidget()
        self._attach_layout = QHBoxLayout(self._attach_bar)
        self._attach_layout.setContentsMargins(2, 2, 2, 2)
        self._attach_layout.setSpacing(4)
        self._attach_layout.addStretch()
        self._attach_bar.hide()
        main_layout.addWidget(self._attach_bar)

        # Input area.
        input_row = QHBoxLayout()
        self._input = _ChatInput()
        self._input.submit.connect(self._send)
        self._input.image_pasted.connect(self._on_image_pasted)
        self._input.setToolTip(
            "Paste an image or screenshot (Ctrl+V) to attach it")
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
                             "format cells, or insert a chart. You can also "
                             "paste a screenshot or image (Ctrl+V) for me to "
                             "look at.\n"
                             "Set your provider (Anthropic, OpenAI, Mistral, "
                             "or Ollama) and API key via the gear icon.",
                             font_pt=self._font_pt)
        self._msg_layout.addWidget(welcome)
        self._update_title()
        self._apply_font()

    def sizeHint(self):
        return QSize(280, 600)

    # ── Actions ─────────────────────────────────────────────────

    def _change_font(self, delta: float):
        """Grow or shrink the chat text, clamped and persisted."""
        self._font_pt = max(7.0, min(24.0, self._font_pt + delta))
        QSettings("KherveSheet", "KherveSheet").setValue(
            "ai/chat_font_pt", self._font_pt)
        self._apply_font()

    def _apply_font(self):
        """Apply the current font size to the input and every bubble."""
        f = self._input.font()
        f.setPointSizeF(self._font_pt)
        self._input.setFont(f)
        for i in range(self._msg_layout.count()):
            w = self._msg_layout.itemAt(i).widget()
            if isinstance(w, ChatBubble):
                w.set_font_pt(self._font_pt)

    def _update_title(self):
        """Reflect the active provider/model in the header."""
        from .ai_providers import PROVIDERS
        s = QSettings("KherveSheet", "KherveSheet")
        provider = s.value("ai/provider", "anthropic")
        spec = PROVIDERS.get(provider, PROVIDERS["anthropic"])
        model = s.value(f"ai/model_{provider}", spec["default_model"])
        self._title.setText(f"<b>AI Assistant</b> <span style='color:#888;"
                            f"font-size:10px;'>{spec['label']} · "
                            f"{model}</span>")

    def _send(self):
        text = self._input.toPlainText().strip()
        if (not text and not self._pending_images) or self._busy:
            return
        images = [{"media_type": im["media_type"], "data": im["data"]}
                  for im in self._pending_images]
        # Show user bubble (text + any attached image thumbnails).
        bubble = ChatBubble("user", text, font_pt=self._font_pt)
        for im in images:
            bubble.add_image_b64(im["data"])
        self._msg_layout.addWidget(bubble)
        if text:
            self._input.add_history(text)
        self._input.clear()
        self._clear_attachments()
        self._set_busy(True)
        self._current_bubble = None
        self._backend.send(text, images or None)

    # ── Image attachments ───────────────────────────────────────

    def _on_image_pasted(self, qimage):
        """Attach a pasted image as a removable thumbnail chip."""
        try:
            data = _qimage_to_b64_png(qimage)
        except Exception:
            return
        chip = QFrame()
        chip.setStyleSheet(
            "QFrame { background: #E8E8E8; border-radius: 4px; }")
        row = QHBoxLayout(chip)
        row.setContentsMargins(4, 2, 2, 2)
        row.setSpacing(2)
        thumb = QLabel()
        pm = QPixmap()
        pm.loadFromData(base64.b64decode(data))
        thumb.setPixmap(pm.scaledToHeight(28, Qt.SmoothTransformation))
        row.addWidget(thumb)
        entry = {"media_type": "image/png", "data": data, "chip": chip}
        remove = QToolButton()
        remove.setText("✕")
        remove.setToolTip("Remove image")
        remove.clicked.connect(lambda: self._remove_attachment(entry))
        row.addWidget(remove)
        # Insert before the trailing stretch.
        self._attach_layout.insertWidget(
            self._attach_layout.count() - 1, chip)
        self._pending_images.append(entry)
        self._attach_bar.show()

    def _remove_attachment(self, entry):
        if entry in self._pending_images:
            self._pending_images.remove(entry)
        entry["chip"].setParent(None)
        entry["chip"].deleteLater()
        if not self._pending_images:
            self._attach_bar.hide()

    def _clear_attachments(self):
        for entry in list(self._pending_images):
            entry["chip"].setParent(None)
            entry["chip"].deleteLater()
        self._pending_images.clear()
        self._attach_bar.hide()

    def _cancel(self):
        self._backend.cancel()
        self._set_busy(False)

    def _open_settings(self):
        dlg = ApiKeyDialog(self)
        if dlg.exec_():
            self._update_title()

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
                             "Conversation cleared. How can I help?",
                             font_pt=self._font_pt)
        self._msg_layout.addWidget(welcome)

    # ── Slots from backend ──────────────────────────────────────

    def _on_chunk(self, text: str):
        if self._current_bubble is None:
            self._typing.stop()
            self._current_bubble = ChatBubble(
                "assistant", font_pt=self._font_pt)
            self._msg_layout.addWidget(self._current_bubble)
        self._current_bubble.append_text(text)
        self._scroll_to_bottom()

    def _on_tool(self, name: str, summary: str):
        bubble = ChatBubble("tool", f"⚙ {summary}", font_pt=self._font_pt)
        self._msg_layout.addWidget(bubble)
        self._scroll_to_bottom()

    def _on_done(self):
        self._set_busy(False)
        self._scroll_to_bottom()

    def _on_error(self, msg: str):
        self._typing.stop()
        bubble = ChatBubble("assistant", font_pt=self._font_pt)
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
