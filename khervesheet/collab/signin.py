"""Signing in to KherveDOC from KherveSheet, and remembering it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

KherveDOC's own sign-in page opens in a small window (a private web view,
so nothing mixes with the user's browser). When it finishes, KherveSheet
keeps the KherveDOC session cookie, as a browser would, and acts with it.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QSettings, QUrl, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox,
    QVBoxLayout,
)

from .kherve_doc import (
    CSRF_COOKIE, SESSION_COOKIE, KherveDoc, KherveDocError, NotSignedIn,
)

DEFAULT_SERVER = "http://localhost:3000"
KEYS = {
    "server": "kherve_doc/server",
    "api": "kherve_doc/api",
    "session": "kherve_doc/session",
    "csrf": "kherve_doc/csrf",
    "name": "kherve_doc/name",
}


def _settings() -> QSettings:
    return QSettings("Kherve", "KherveSheet")


class ServerDialog(QDialog):
    """Ask for the KherveDOC address (the page people open)."""

    def __init__(self, server: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sign in to KherveDOC")
        self.server = QLineEdit(server)
        text = QLabel(
            "KherveSheet shares workbooks through your KherveDOC server: "
            "the same accounts, sharing and permissions as your documents.")
        text.setWordWrap(True)
        form = QFormLayout()
        form.addRow("KherveDOC address:", self.server)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.addButton("Continue", QDialogButtonBox.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(text)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.resize(480, self.sizeHint().height())


class SignInDialog(QDialog):
    """KherveDOC's sign-in page, in a private web view."""

    signed_in = pyqtSignal()

    def __init__(self, kd: KherveDoc, parent=None):
        super().__init__(parent)
        from PyQt5.QtWebEngineWidgets import (
            QWebEnginePage, QWebEngineProfile, QWebEngineView,
        )
        self.kd = kd
        self.session = ""
        self.csrf = ""
        self.setWindowTitle("Sign in to KherveDOC")
        self.resize(560, 720)
        self.profile = QWebEngineProfile(self)          # off the record
        self.profile.cookieStore().cookieAdded.connect(self._on_cookie)
        self.view = QWebEngineView(self)
        self.page = QWebEnginePage(self.profile, self.view)
        self.view.setPage(self.page)
        self.page.urlChanged.connect(self._on_url)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.view.load(QUrl(kd.login_url()))

    def _on_cookie(self, cookie):
        name = bytes(cookie.name()).decode(errors="replace")
        value = bytes(cookie.value()).decode(errors="replace")
        if name == SESSION_COOKIE:
            self.session = value
        elif name == CSRF_COOKIE:
            self.csrf = value

    def _on_url(self, url: QUrl):
        # Back on KherveDOC with a session: check it and finish.
        if self.session and url.toString().startswith(self.kd.server):
            self.kd.session = self.session
            if self.csrf:
                self.kd.csrf = self.csrf
            try:
                self.kd.me()
            except KherveDocError:
                return
            self.accept()

    def done(self, result):
        # Web views must go before their profile.
        self.view.setPage(None)
        self.page.deleteLater()
        super().done(result)


class KherveDocAccount:
    """The KherveDOC server and session KherveSheet uses, kept in settings."""

    def __init__(self):
        s = _settings()
        self.kd: Optional[KherveDoc] = None
        server = s.value(KEYS["server"], "")
        if server:
            self.kd = KherveDoc(server, api=s.value(KEYS["api"], "") or None,
                                session=s.value(KEYS["session"], ""),
                                csrf=s.value(KEYS["csrf"], ""))
        self.name = s.value(KEYS["name"], "")

    def _store(self):
        s = _settings()
        if self.kd:
            s.setValue(KEYS["server"], self.kd.server)
            s.setValue(KEYS["api"], self.kd.api or "")
            s.setValue(KEYS["session"], self.kd.session)
            s.setValue(KEYS["csrf"], self.kd.csrf)
        s.setValue(KEYS["name"], self.name)

    def sign_out(self):
        s = _settings()
        for key in ("session", "csrf", "name"):
            s.remove(KEYS[key])
        if self.kd:
            self.kd.session = ""
        self.name = ""

    def signed_in(self) -> Optional[KherveDoc]:
        """The server, if the saved session still works (no dialogs)."""
        if not self.kd or not self.kd.session:
            return None
        try:
            user = self.kd.me()
        except NotSignedIn:
            return None
        self.name = user.get("full_name") or user.get("email") or self.name
        self._store()
        return self.kd

    def ensure(self, parent=None) -> Optional[KherveDoc]:
        """A signed-in server, asking the user to sign in if needed."""
        try:
            kd = self.signed_in()
        except KherveDocError as exc:
            QMessageBox.warning(parent, "KherveDOC", str(exc))
            return None
        if kd:
            return kd
        try:
            from PyQt5 import QtWebEngineWidgets  # noqa: F401
        except ImportError:
            QMessageBox.warning(
                parent, "Sign in to KherveDOC",
                "Signing in needs Qt's web view. Install it with:\n\n"
                "    pip install PyQtWebEngine")
            return None
        server = self.kd.server if self.kd else DEFAULT_SERVER
        ask = ServerDialog(server, parent)
        if ask.exec_() != QDialog.Accepted:
            return None
        kd = KherveDoc(ask.server.text().strip() or DEFAULT_SERVER)
        try:
            kd.discover()
        except KherveDocError as exc:
            QMessageBox.warning(parent, "Sign in to KherveDOC", str(exc))
            return None
        dialog = SignInDialog(kd, parent)
        if dialog.exec_() != QDialog.Accepted:
            return None
        self.kd = kd
        return self.signed_in()
