"""File ▸ Live Sharing: share a workbook, join one, see who is editing.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import getpass
import secrets
from typing import Optional

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtNetwork import QAbstractSocket, QHostAddress, QNetworkInterface
from PyQt5.QtWidgets import (
    QApplication, QButtonGroup, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QRadioButton,
    QVBoxLayout, QWidget,
)

SETTINGS_NAME = "live/name"
SETTINGS_SERVER = "live/server"
SETTINGS_HOST = "live/host_here"


def _settings() -> QSettings:
    return QSettings("Kherve", "KherveSheet")


def _lan_address() -> str:
    """This computer's address on the local network, for invitation links."""
    for iface in QNetworkInterface.allInterfaces():
        flags = iface.flags()
        if not (flags & QNetworkInterface.IsUp) or \
                flags & QNetworkInterface.IsLoopBack:
            continue
        for entry in iface.addressEntries():
            ip = entry.ip()
            if ip.protocol() == QAbstractSocket.IPv4Protocol and \
                    not ip.isEqual(QHostAddress(QHostAddress.LocalHost)):
                return ip.toString()
    return "127.0.0.1"


def _default_name() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "Me"


class ShareDialog(QDialog):
    """Name, and where the live server runs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Share Workbook Live")
        settings = _settings()
        self.name = QLineEdit(settings.value(SETTINGS_NAME, _default_name()))
        self.host_here = QRadioButton(
            "Host on this computer (people on the same network can join)")
        self.use_server = QRadioButton("Use a live server:")
        self.server = QLineEdit(settings.value(
            SETTINGS_SERVER, "ws://localhost:1235"))
        group = QButtonGroup(self)
        group.addButton(self.host_here)
        group.addButton(self.use_server)
        host = settings.value(SETTINGS_HOST, "true") == "true"
        (self.host_here if host else self.use_server).setChecked(True)
        self.server.setEnabled(not host)
        self.use_server.toggled.connect(self.server.setEnabled)

        intro = QLabel(
            "Everyone with the invitation link can edit this workbook with "
            "you, live. Changes, formats and new sheets appear for everyone "
            "within a second.")
        intro.setWordWrap(True)
        form = QFormLayout()
        form.addRow("Your name:", self.name)
        server_row = QHBoxLayout()
        server_row.addWidget(self.use_server)
        server_row.addWidget(self.server, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.addButton("Start Sharing", QDialogButtonBox.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self.host_here)
        layout.addLayout(server_row)
        layout.addWidget(buttons)
        self.resize(520, self.sizeHint().height())

    def accept(self):
        settings = _settings()
        settings.setValue(SETTINGS_NAME, self.name.text().strip())
        settings.setValue(SETTINGS_HOST,
                          "true" if self.host_here.isChecked() else "false")
        if self.use_server.isChecked():
            settings.setValue(SETTINGS_SERVER, self.server.text().strip())
        super().accept()


class JoinDialog(QDialog):
    def __init__(self, parent=None, link: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Join Shared Workbook")
        self.link = QLineEdit(link)
        self.link.setPlaceholderText("ws://server:1235/room")
        self.name = QLineEdit(_settings().value(SETTINGS_NAME,
                                                _default_name()))
        intro = QLabel("Paste the invitation link you were sent. The shared "
                       "workbook opens in place of the current one.")
        intro.setWordWrap(True)
        form = QFormLayout()
        form.addRow("Invitation link:", self.link)
        form.addRow("Your name:", self.name)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.addButton("Join", QDialogButtonBox.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.resize(520, self.sizeHint().height())

    def accept(self):
        from .session import split_link
        try:
            split_link(self.link.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Join Shared Workbook", str(exc))
            return
        _settings().setValue(SETTINGS_NAME, self.name.text().strip())
        super().accept()


class InviteDialog(QDialog):
    def __init__(self, link: str, hosting: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Invite People")
        text = QLabel(
            "Send this link to the people you want to edit with. They open "
            "File ▸ Live Sharing ▸ Join Shared Workbook… and paste it.")
        text.setWordWrap(True)
        field = QLineEdit(link)
        field.setReadOnly(True)
        field.selectAll()
        copy = QPushButton("Copy Link")
        copy.clicked.connect(
            lambda: (QApplication.clipboard().setText(link),
                     copy.setText("Copied ✓")))
        row = QHBoxLayout()
        row.addWidget(field, 1)
        row.addWidget(copy)
        layout = QVBoxLayout(self)
        layout.addWidget(text)
        layout.addLayout(row)
        if hosting:
            note = QLabel("This computer is the server: keep KherveSheet "
                          "open while others are editing.")
            note.setWordWrap(True)
            note.setStyleSheet("color: palette(mid);")
            layout.addWidget(note)
        warn = QLabel("Anyone with the link can edit: share it only with "
                      "people you trust.")
        warn.setWordWrap(True)
        layout.addWidget(warn)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        self.resize(560, self.sizeHint().height())


class LiveSharing(QWidget):
    """Owns the live session (and local server) of one main window.

    Also the status-bar indicator: "● Live — Anna, Ben".
    """

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.session = None
        self.server = None
        self._account = None
        self._overlays = {}
        self._doc_title = ""
        self.label = QLabel("")
        self.label.setTextFormat(Qt.RichText)
        self.label.hide()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.addWidget(self.label)
        QApplication.instance().aboutToQuit.connect(self.shutdown)

    # ── Menu ─────────────────────────────────────────────────────────
    def install_menu(self, file_menu):
        menu = file_menu.addMenu("Live Sharing")
        try:
            from .. import icons
            menu.setIcon(icons.themed_icon("mdi.account-multiple"))
        except Exception:
            pass
        self.kd_share_act = menu.addAction("Share on KherveDOC…",
                                           self.share_on_kherve_doc)
        self.kd_open_act = menu.addAction("Open from KherveDOC…",
                                          self.open_from_kherve_doc)
        menu.addSeparator()
        self.invite_act = menu.addAction("Invite People…", self.invite)
        self.stop_act = menu.addAction("Stop Sharing", self.stop)
        menu.addSeparator()
        local = menu.addMenu("Without KherveDOC (same network)")
        self.share_act = local.addAction("Share This Workbook…", self.share)
        self.join_act = local.addAction("Join by Link…", self.join)
        menu.addSeparator()
        self.sign_out_act = menu.addAction("Sign Out of KherveDOC",
                                           self.sign_out)
        menu.aboutToShow.connect(self._update_actions)
        self._update_actions()
        return menu

    def _update_actions(self):
        live = self.session is not None
        for act in (self.share_act, self.join_act, self.kd_share_act,
                    self.kd_open_act):
            act.setEnabled(not live)
        self.invite_act.setEnabled(live)
        self.stop_act.setEnabled(live)
        signed = bool(self._account and self._account.kd
                      and self._account.kd.session)
        self.sign_out_act.setEnabled(signed and not live)

    # ── Actions ──────────────────────────────────────────────────────
    def share(self):
        dialog = ShareDialog(self.window)
        if dialog.exec_() != QDialog.Accepted:
            return
        name = dialog.name.text().strip()
        if dialog.host_here.isChecked():
            server = self._host_here()
            if server is None:
                return
        else:
            server = dialog.server.text().strip().rstrip("/")
        room = secrets.token_urlsafe(12)
        self._start(server, room, name, publish_local=True)
        self._show_invite_when_live = True

    def join(self, link: Optional[str] = None):
        dialog = JoinDialog(self.window, link or "")
        if dialog.exec_() != QDialog.Accepted:
            return
        from .session import split_link
        server, room = split_link(dialog.link.text())
        before = self.window._workbook
        self.window._new_workbook()
        if self.window._workbook is before:
            return  # the user cancelled "save changes?"
        self._start(server, room, dialog.name.text().strip(),
                    publish_local=False)

    # ── KherveDOC ────────────────────────────────────────────────────
    @property
    def account(self):
        if self._account is None:
            from .signin import KherveDocAccount
            self._account = KherveDocAccount()
        return self._account

    def share_on_kherve_doc(self):
        """Put the workbook on KherveDOC and edit it there, live."""
        from .kherve_doc import KherveDocError
        kd = self.account.ensure(self.window)
        if kd is None:
            return
        path = getattr(self.window, "_current_file", None)
        import os
        title = (os.path.splitext(os.path.basename(path))[0] if path
                 else "Untitled spreadsheet")
        try:
            document = kd.create_spreadsheet(title)["id"]
        except KherveDocError as exc:
            QMessageBox.warning(self.window, "Share on KherveDOC", str(exc))
            return
        self._start_kherve_doc(kd, document, title, publish_local=True)
        self._show_invite_when_live = True

    def open_from_kherve_doc(self, document: Optional[str] = None):
        """Open a spreadsheet from KherveDOC and edit it live."""
        from .kherve_doc import KherveDocError
        from .kherve_doc_ui import OpenDialog
        kd = self.account.ensure(self.window)
        if kd is None:
            return
        title = ""
        if document is None:
            dialog = OpenDialog(kd, self.window)
            if dialog.exec_() != QDialog.Accepted:
                return
            document, title = dialog.document, dialog.title
        try:
            info = kd.document(document)
            if info.get("kind") not in (None, "sheet"):
                QMessageBox.information(
                    self.window, "Open from KherveDOC",
                    "That is a text document; open it in KherveDOC.")
                return
            title = title or info.get("title") or "Untitled spreadsheet"
        except KherveDocError as exc:
            QMessageBox.warning(self.window, "Open from KherveDOC", str(exc))
            return
        before = self.window._workbook
        self.window._new_workbook()
        if self.window._workbook is before:
            return  # the user cancelled "save changes?"
        self._start_kherve_doc(kd, document, title, publish_local=False)

    def sign_out(self):
        self.account.sign_out()
        if hasattr(self.window, "_status_msg"):
            self.window._status_msg("Signed out of KherveDOC", 4000)

    def _start_kherve_doc(self, kd, document, title, publish_local):
        from .kherve_doc import KherveDocError
        from .session import KherveDocLink, LiveSession
        try:
            initial = None if publish_local else kd.content(document)
        except KherveDocError as exc:
            QMessageBox.warning(self.window, "KherveDOC", str(exc))
            return
        link = KherveDocLink(
            ws_url=kd.ws_url(document), document=document,
            page_url=kd.page_url(document), headers=kd.ws_headers(),
            initial_update=initial,
            save=lambda update: kd.save_content(document, update))
        self._show_invite_when_live = False
        self._doc_title = title
        session = LiveSession(self.window, kd.server, document,
                              self.account.name or "KherveSheet user",
                              publish_local=publish_local, kherve_doc=link)
        session.status_changed.connect(self._on_status)
        session.peers_changed.connect(self._on_peers)
        session.ended.connect(self._on_ended)
        self.session = session
        session.start()

    def invite(self):
        if self.session is None:
            return
        if self.session.kherve_doc is not None:
            from .kherve_doc_ui import SharedDialog
            SharedDialog(self.account.kd, self.session.kherve_doc.document,
                         self._doc_title, self.session.read_only,
                         self.window).exec_()
        else:
            InviteDialog(self.session.link, self.server is not None,
                         self.window).exec_()

    def stop(self):
        if self.session is not None:
            self.session.stop()

    def shutdown(self):
        self.stop()
        if self.server is not None:
            self.server.stop()
            self.server = None

    # ── Internals ────────────────────────────────────────────────────
    def _host_here(self) -> Optional[str]:
        from .server import DEFAULT_DB, DEFAULT_PORT, BackgroundServer
        if self.server is None or not self.server.running:
            self.server = BackgroundServer("0.0.0.0", DEFAULT_PORT,
                                           DEFAULT_DB)
            self.server.start()
            if self.server.error is not None or not self.server.running:
                QMessageBox.warning(
                    self.window, "Share Workbook Live",
                    "Could not start the live server on port "
                    f"{DEFAULT_PORT}:\n{self.server.error or 'unknown error'}"
                    "\n\nIs another KherveSheet already hosting?")
                self.server = None
                return None
        return f"ws://{_lan_address()}:{DEFAULT_PORT}"

    def _start(self, server, room, name, publish_local):
        from .session import LiveSession
        self._show_invite_when_live = False
        session = LiveSession(self.window, server, room, name,
                              publish_local=publish_local)
        session.status_changed.connect(self._on_status)
        session.peers_changed.connect(self._on_peers)
        session.ended.connect(self._on_ended)
        self.session = session
        session.start()

    def _on_status(self, text):
        if text.startswith("Live") and self.session is not None:
            # The shared sheets exist now: show who is where.
            self._show_cursors(self.session._peers)
            tabs = self.window._workbook.tabs
            try:
                tabs.currentChanged.disconnect(self._refresh_cursors)
            except TypeError:
                pass
            tabs.currentChanged.connect(self._refresh_cursors)
        if text.startswith("Live") and self._show_invite_when_live:
            self._show_invite_when_live = False
            self.invite()
        self._render(text)

    def _on_peers(self, peers):
        self._render()
        self._show_cursors(peers)

    def _refresh_cursors(self, *_):
        if self.session is not None:
            self._show_cursors(self.session._peers)

    def _show_cursors(self, peers):
        """Collaborators' cells on each sheet's grid."""
        from .kherve_doc_ui import PresenceOverlay
        wb = self.window._workbook
        sheets = wb.all_sheets()
        alive = {id(sheet) for sheet in sheets}
        for key in [k for k in self._overlays if k not in alive]:
            self._overlays.pop(key)   # its sheet is gone
        for sheet in sheets:
            overlay = self._overlays.get(id(sheet))
            if overlay is None or overlay.sheet is not sheet:
                overlay = PresenceOverlay(sheet)
                self._overlays[id(sheet)] = overlay
            sheet_id = getattr(sheet, "_collab_id", None)
            overlay.set_peers([p for p in peers
                               if sheet_id and p.get("sheet") == sheet_id])

    def _render(self, status: Optional[str] = None):
        session = self.session
        if session is None:
            self.label.hide()
            return
        if status is not None:
            self._status = status
        status = getattr(self, "_status", "")
        if not status.startswith("Live"):
            self.label.setText(f"<span style='color:#e67700'>●</span> "
                               f"{status}")
        else:
            peers = session._peers
            names = ", ".join(
                f"<span style='color:{p.get('color', '#1971c2')}'>"
                f"{p.get('user', '?')}</span>" for p in peers)
            self.label.setText(
                f"<span style='color:#2f9e44'>●</span> {status}"
                + (f" — {names}" if names else " — waiting for others"))
            self.label.setToolTip("\n".join(
                f"{p.get('user', '?')}: {session.peer_location(p)}"
                for p in peers) or session.link)
        self.label.show()

    def _on_ended(self, reason):
        self._show_cursors([])
        self.session = None
        self.label.hide()
        self._update_actions()
        if reason and reason != "Stopped sharing":
            QMessageBox.information(self.window, "Live Sharing", reason)
        if hasattr(self.window, "_status_msg"):
            self.window._status_msg(reason or "Stopped sharing", 5000)
