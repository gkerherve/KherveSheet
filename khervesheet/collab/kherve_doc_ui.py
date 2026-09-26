"""KherveDOC sharing in KherveSheet's window: collaborators' cursors on the
grid, the "shared" dialog with invitations, and opening shared workbooks.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt5.QtCore import QEvent, QObject, QRect, Qt, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from .kherve_doc import KherveDoc, KherveDocError, document_id_from

ROLES = [("editor", "Can edit"), ("commenter", "Can comment"),
         ("reader", "Can read")]


# ── Collaborators' cursors on the grid ───────────────────────────────
class PresenceOverlay(QWidget):
    """Coloured boxes with names over the cells collaborators have
    selected, and their colour on the matching row and column headers."""

    def __init__(self, sheet):
        super().__init__(sheet.table.viewport())
        self.sheet = sheet
        self.peers: List[dict] = []
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        table = sheet.table
        table.viewport().installEventFilter(self)
        table.horizontalScrollBar().valueChanged.connect(self._refresh)
        table.verticalScrollBar().valueChanged.connect(self._refresh)
        table.horizontalHeader().sectionResized.connect(self._refresh)
        self._header_marks = [
            _HeaderMarks(table.horizontalHeader(), self, horizontal=True),
            _HeaderMarks(table.verticalHeader(), self, horizontal=False),
        ]
        self.resize(table.viewport().size())
        self.show()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Resize:
            self.resize(obj.size())
        return False

    def set_peers(self, peers: List[dict]):
        self.peers = peers
        self._refresh()

    def _refresh(self, *_):
        self.raise_()
        self.update()
        for marks in self._header_marks:
            marks.update()

    def cell_rect(self, row: int, col: int) -> QRect:
        table = self.sheet.table
        return table.visualRect(table.model().index(row, col))

    def paintEvent(self, _event):
        if not self.peers:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont(self.font())
        font.setPointSizeF(max(7.0, font.pointSizeF() - 2))
        painter.setFont(font)
        for peer in self.peers:
            cell = peer.get("cell")
            if not cell:
                continue
            rect = self.cell_rect(cell[0], cell[1])
            if not rect.isValid() or not rect.intersects(self.rect()):
                continue
            color = QColor(peer.get("color") or "#1971c2")
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
            name = str(peer.get("user") or "Someone")
            width = painter.fontMetrics().horizontalAdvance(name) + 8
            height = painter.fontMetrics().height() + 2
            # Above the cell, or below it on the top row.
            top = rect.top() - height if rect.top() >= height \
                else rect.bottom() + 1
            tag = QRect(rect.left(), top, width, height)
            painter.fillRect(tag, color)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(tag, Qt.AlignCenter, name)
        painter.end()


class _PaintedWidget(QWidget):
    """A transparent widget painted by a callback."""

    def __init__(self, parent, paint):
        super().__init__(parent)
        self._paint_cb = paint
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)

    def paintEvent(self, event):
        self._paint_cb(event)


class _HeaderMarks(QObject):
    """A collaborator's colour on the row number and column letter of the
    cell they are on (the grid's "sides")."""

    def __init__(self, header, overlay: PresenceOverlay, horizontal: bool):
        super().__init__(header)
        self.header = header
        self.overlay = overlay
        self.horizontal = horizontal
        self.widget = _PaintedWidget(header.viewport(), self._paint)
        header.viewport().installEventFilter(self)
        self.widget.resize(header.viewport().size())
        self.widget.show()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Resize:
            self.widget.resize(obj.size())
        return False

    def update(self):
        self.widget.resize(self.header.viewport().size())
        self.widget.raise_()
        self.widget.update()

    def _paint(self, _event):
        peers = self.overlay.peers
        if not peers:
            return
        painter = QPainter(self.widget)
        for peer in peers:
            cell = peer.get("cell")
            if not cell:
                continue
            index = cell[1] if self.horizontal else cell[0]
            pos = self.header.sectionViewportPosition(index)
            size = self.header.sectionSize(index)
            color = QColor(peer.get("color") or "#1971c2")
            tint = QColor(color)
            tint.setAlpha(110)
            if self.horizontal:
                painter.fillRect(pos, 0, size, self.widget.height(), tint)
                painter.fillRect(pos, self.widget.height() - 3, size, 3,
                                 color.darker(130))
            else:
                painter.fillRect(0, pos, self.widget.width(), size, tint)
                painter.fillRect(self.widget.width() - 3, pos, 3, size,
                                 color.darker(130))
        painter.end()


# ── Shared: link and invitations ─────────────────────────────────────
class SharedDialog(QDialog):
    """The workbook is on KherveDOC: invite people, copy or open the link."""

    def __init__(self, kd: KherveDoc, document: str, title: str,
                 read_only: bool = False, parent=None):
        super().__init__(parent)
        self.kd = kd
        self.document = document
        self.setWindowTitle("Shared on KherveDOC")
        link = kd.page_url(document)
        intro = QLabel(
            f"<b>{title or 'This workbook'}</b> is on KherveDOC. Everyone you "
            "invite can edit it with you, live — in KherveSheet or in their "
            "browser — and sees where the others are working.")
        intro.setWordWrap(True)

        self.email = QLineEdit()
        self.email.setPlaceholderText("name@example.org")
        self.role = QComboBox()
        for value, label in ROLES:
            self.role.addItem(label, value)
        invite = QPushButton("Invite")
        invite.setDefault(True)
        invite.clicked.connect(self._invite)
        self.email.returnPressed.connect(self._invite)
        row = QHBoxLayout()
        row.addWidget(self.email, 1)
        row.addWidget(self.role)
        row.addWidget(invite)
        self.result = QLabel("")
        self.result.setWordWrap(True)
        for widget in (self.email, self.role, invite):
            widget.setEnabled(not read_only)

        field = QLineEdit(link)
        field.setReadOnly(True)
        copy = QPushButton("Copy Link")
        copy.clicked.connect(lambda: (QApplication.clipboard().setText(link),
                                      copy.setText("Copied ✓")))
        open_web = QPushButton("Open in KherveDOC")
        open_web.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(link)))
        links = QHBoxLayout()
        links.addWidget(field, 1)
        links.addWidget(copy)
        links.addWidget(open_web)
        note = QLabel("Sharing settings (who can find it, public links…) are "
                      "under Share in KherveDOC.")
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(mid);")

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(QLabel("Invite people by e-mail:"))
        layout.addLayout(row)
        layout.addWidget(self.result)
        layout.addLayout(links)
        layout.addWidget(note)
        layout.addWidget(buttons)
        self.resize(620, self.sizeHint().height())

    def _invite(self):
        email = self.email.text().strip()
        if "@" not in email:
            self.result.setText("Type an e-mail address.")
            return
        try:
            how = self.kd.invite(self.document, email, self.role.currentData())
        except KherveDocError as exc:
            self.result.setText(f"Could not invite {email}: {exc}")
            return
        self.result.setText(
            f"✓ {email} can now open it." if how == "access" else
            f"✓ {email} was sent an invitation to create their account.")
        self.email.clear()


# ── Open a shared workbook ───────────────────────────────────────────
class OpenDialog(QDialog):
    """Choose a spreadsheet on KherveDOC, or paste its link."""

    def __init__(self, kd: KherveDoc, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open from KherveDOC")
        self.document: Optional[str] = None
        self.title = ""
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _item: self.accept())
        try:
            sheets = kd.spreadsheets()
        except KherveDocError as exc:
            sheets = []
            QMessageBox.warning(parent, "Open from KherveDOC", str(exc))
        for sheet in sheets:
            title = sheet.get("title") or "Untitled spreadsheet"
            when = (sheet.get("updated_at") or "")[:16].replace("T", " ")
            item = QListWidgetItem(f"{title}    —    {when}")
            item.setData(Qt.UserRole, (sheet["id"], title))
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.link = QLineEdit()
        self.link.setPlaceholderText("…or paste a KherveDOC link")
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.addButton("Open", QDialogButtonBox.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Spreadsheets you can open:"))
        layout.addWidget(self.list, 1)
        layout.addWidget(self.link)
        layout.addWidget(buttons)
        self.resize(560, 420)

    def accept(self):
        pasted = document_id_from(self.link.text())
        if pasted:
            self.document, self.title = pasted, ""
        elif self.list.currentItem():
            self.document, self.title = self.list.currentItem().data(
                Qt.UserRole)
        if not self.document:
            QMessageBox.information(self, "Open from KherveDOC",
                                    "Choose a spreadsheet or paste its link.")
            return
        super().accept()
