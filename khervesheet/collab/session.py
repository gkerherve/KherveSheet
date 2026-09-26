"""Live co-editing client: keeps a workbook and a shared Yjs doc in step.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Everything runs on the GUI thread: the WebSocket is a ``QWebSocket`` and
pycrdt is called synchronously, like the MCP bridge.

Local edits are found by diffing the workbook against what was last
synchronised, whenever the undo stack moves (every user edit pushes a
command) and on a slow timer for writers that do not.  Remote edits are
applied through the sheet's own cell path, so formulas recalculate, but
never pushed on the local undo stack.  Collaborators' Python (=PY) cells
are only run after the user agrees, as when opening a file.
"""

from __future__ import annotations

import json
import random
import time
from typing import Dict, Optional

from dataclasses import dataclass, field
from typing import Callable

from PyQt5.QtCore import QByteArray, QObject, QTimer, QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtGui import QFont
from PyQt5.QtWebSockets import QWebSocket
from PyQt5.QtNetwork import QAbstractSocket
from PyQt5.QtWidgets import QTableWidgetItem

from pycrdt import (
    Awareness, Doc, Map, YMessageType, YSyncMessageType,
    create_awareness_message, create_sync_message, create_update_message,
    handle_sync_message, read_message,
)

from ..python_engine import is_python_source
from . import hocuspocus, model

FLUSH_DELAY_MS = 200
POLL_MS = 1500
HEARTBEAT_S = 15
PEER_TIMEOUT_S = 45
RECONNECT_MS = 3000
NOT_RUN = "⟨Python — not run⟩"
SAVE_MS = 30000

PEER_COLORS = ["#d9480f", "#1971c2", "#2f9e44", "#9c36b5",
               "#e67700", "#0c8599", "#c2255c", "#5f3dc4"]


def room_url(server: str, room: str) -> str:
    return f"{server.rstrip('/')}/{room}"


def split_link(link: str):
    """``ws://host:port/room`` → (``ws://host:port``, ``room``)."""
    link = link.strip()
    server, _, room = link.rstrip("/").rpartition("/")
    if not server or "://" not in link or not room:
        raise ValueError("A live link looks like ws://server:1235/room")
    return server, room


@dataclass
class KherveDocLink:
    """A spreadsheet on a KherveDOC server, reached through its
    collaboration server (Hocuspocus) with the user's session."""

    ws_url: str                    # …/collaboration/ws/?room=<document id>
    document: str                  # the document id (the room)
    page_url: str                  # where people open it in a browser
    headers: Dict[str, str] = field(default_factory=dict)  # Cookie, Origin
    initial_update: Optional[bytes] = None   # content saved on the server
    save: Optional[Callable[[bytes], None]] = None


class LiveSession(QObject):
    """One workbook shared in one room."""

    status_changed = pyqtSignal(str)
    peers_changed = pyqtSignal(list)
    ended = pyqtSignal(str)

    def __init__(self, window, server: str, room: str, user: str,
                 publish_local: bool, parent=None,
                 kherve_doc: Optional[KherveDocLink] = None):
        super().__init__(parent or window)
        self.window = window
        self.server = server
        self.room = room
        self.user = user or "Someone"
        self.publish_local = publish_local
        self.kherve_doc = kherve_doc
        self.link = kherve_doc.page_url if kherve_doc else room_url(server, room)
        #: The server lets us read but not edit (KherveDOC viewers).
        self.read_only = False
        self._dirty = False

        self._wb = window._workbook
        self._sheets: Dict[str, object] = {}
        self._last_meta: Dict[str, str] = {}
        self._last_cells: Dict[str, Dict] = {}
        self._last_formats: Dict[str, Dict] = {}
        self._last_widths: Dict[str, Dict] = {}

        self.doc = Doc()
        if kherve_doc and kherve_doc.initial_update:
            # What the server saved: the room may be empty until someone
            # brings it, as KherveDOC's browsers do.
            self.doc.apply_update(kherve_doc.initial_update)
        self.ysheets = self.doc.get(model.SHEETS, type=Map)
        self.ycells = self.doc.get(model.CELLS, type=Map)
        self.yformats = self.doc.get(model.FORMATS, type=Map)
        self.ywidths = self.doc.get(model.WIDTHS, type=Map)
        self.awareness = Awareness(self.doc)
        self.color = random.choice(PEER_COLORS)

        self._remote = False       # inside a remote update
        self._busy = False         # applying remote edits
        self._synced = False
        self._stopped = False
        self._python_trusted: Optional[bool] = None
        self._pending = {name: set() for name in
                         (model.SHEETS, model.CELLS, model.FORMATS,
                          model.WIDTHS)}
        self._last_heartbeat = 0.0
        self._peers: list = []

        self._subscriptions = [(self.doc, self.doc.observe(
            self._on_doc_transaction))]
        for name, ymap in ((model.SHEETS, self.ysheets),
                           (model.CELLS, self.ycells),
                           (model.FORMATS, self.yformats),
                           (model.WIDTHS, self.ywidths)):
            self._subscriptions.append(
                (ymap, ymap.observe(self._map_observer(name))))

        self._flush_timer = QTimer(self, singleShot=True,
                                   interval=FLUSH_DELAY_MS)
        self._flush_timer.timeout.connect(self._flush_local)
        self._poll_timer = QTimer(self, interval=POLL_MS)
        self._poll_timer.timeout.connect(self._tick)
        self._apply_timer = QTimer(self, singleShot=True, interval=0)
        self._apply_timer.timeout.connect(self._apply_remote)
        self._reconnect_timer = QTimer(self, singleShot=True,
                                       interval=RECONNECT_MS)
        self._reconnect_timer.timeout.connect(self._open)
        self._save_timer = QTimer(self, interval=SAVE_MS)
        self._save_timer.timeout.connect(self.save)

        self.ws = QWebSocket()
        self.ws.setParent(self)
        self.ws.connected.connect(self._on_connected)
        self.ws.disconnected.connect(self._on_disconnected)
        self.ws.binaryMessageReceived.connect(self._on_message)
        self.ws.error.connect(self._on_socket_error)

    # ── Lifecycle ────────────────────────────────────────────────────
    def start(self):
        self.status_changed.emit("Connecting…")
        self._open()

    @staticmethod
    def _socket_url(url: str) -> QUrl:
        """*url* with "localhost" as 127.0.0.1: Qt tries IPv6 (::1) only,
        which Docker/Colima port forwarding may refuse."""
        qurl = QUrl(url)
        if qurl.host() == "localhost":
            qurl.setHost("127.0.0.1")
        return qurl

    def _open(self):
        if self._stopped:
            return
        if self.kherve_doc:
            request = QNetworkRequest(self._socket_url(self.kherve_doc.ws_url))
            for name, value in self.kherve_doc.headers.items():
                request.setRawHeader(QByteArray(name.encode()),
                                     QByteArray(value.encode()))
            self.ws.open(request)
        else:
            self.ws.open(self._socket_url(self.link))

    def save(self):
        """Store the workbook on KherveDOC if this window changed it (the
        collaboration server keeps nothing itself)."""
        link = self.kherve_doc
        if link and link.save and self._dirty and self._synced \
                and not self.read_only:
            self._dirty = False
            try:
                link.save(self.doc.get_update())
            except Exception as exc:  # network down: try again later
                self._dirty = True
                self.status_changed.emit(f"Could not save to KherveDOC: {exc}")

    def stop(self, reason: str = "Stopped sharing"):
        if self._stopped:
            return
        if self._synced:
            self._flush_local()
            self.save()
        self._stopped = True
        for timer in (self._flush_timer, self._poll_timer,
                      self._apply_timer, self._reconnect_timer,
                      self._save_timer):
            timer.stop()
        try:
            self.window._undo_stack.indexChanged.disconnect(
                self._schedule_flush)
        except TypeError:
            pass
        if self.ws.state() != QAbstractSocket.UnconnectedState:
            # Tell the others we left, then close.
            self.awareness.set_local_state(None)
            self._send_awareness()
            self.ws.close()
        # pycrdt subscriptions must be dropped on the thread that made them.
        for target, subscription in self._subscriptions:
            target.unobserve(subscription)
        self._subscriptions = []
        self.status_changed.emit("")
        self.ended.emit(reason)

    def _on_connected(self):
        self.status_changed.emit("Synchronising…")
        if self.kherve_doc:
            # Hocuspocus first wants the (empty) token; it checks the user
            # from the session cookie sent with the connection.
            self.ws.sendBinaryMessage(
                hocuspocus.auth_message(self.kherve_doc.document))
        self._send(create_sync_message(self.doc))
        self._update_presence(force=True)

    def _on_disconnected(self):
        if self._stopped:
            return
        self.status_changed.emit("Connection lost — reconnecting…")
        self._reconnect_timer.start()

    def _on_socket_error(self, _error):
        if self._stopped:
            return
        if not self._synced:
            self.stop(f"Could not reach the live server at {self.server}: "
                      f"{self.ws.errorString()}")
        # After the first sync, _on_disconnected keeps retrying.

    # ── Wire protocol ────────────────────────────────────────────────
    def _send(self, data: bytes):
        if self.ws.state() == QAbstractSocket.ConnectedState:
            if self.kherve_doc:
                data = hocuspocus.frame(self.kherve_doc.document, data)
            self.ws.sendBinaryMessage(data)

    def _send_awareness(self):
        update = self.awareness.encode_awareness_update(
            [self.awareness.client_id])
        self._send(create_awareness_message(update))

    def _on_message(self, message):
        data = bytes(message)
        if not data:
            return
        if self.kherve_doc:
            data = self._unwrap_hocuspocus(data)
            if data is None:
                return
        if data[0] == YMessageType.SYNC:
            self._remote = True
            try:
                reply = handle_sync_message(data[1:], self.doc)
            finally:
                self._remote = False
            if reply is not None:
                self._send(reply)
            if (len(data) > 1 and data[1] == YSyncMessageType.SYNC_STEP2
                    and not self._synced):
                self._synced = True
                self._after_first_sync()
            elif self._synced:
                self._apply_timer.start()
        elif data[0] == YMessageType.AWARENESS:
            known = set(self.awareness.states)
            self.awareness.apply_awareness_update(
                read_message(data[1:]), "remote")
            if set(self.awareness.states) - known:
                # Someone new: tell them who we are straight away.
                self._send_awareness()
            self._refresh_peers()

    def _unwrap_hocuspocus(self, data: bytes) -> Optional[bytes]:
        """A Hocuspocus message as a y-websocket one, or None if handled."""
        try:
            document, kind, rest = hocuspocus.parse(data)
        except (IndexError, UnicodeDecodeError):
            return None
        if document != self.kherve_doc.document:
            return None
        if kind in (hocuspocus.SYNC, hocuspocus.SYNC_REPLY):
            return bytes([YMessageType.SYNC]) + rest
        if kind == hocuspocus.AWARENESS:
            return bytes([YMessageType.AWARENESS]) + rest
        if kind == hocuspocus.QUERY_AWARENESS:
            self._send_awareness()
        elif kind == hocuspocus.AUTH:
            granted, scope = hocuspocus.parse_auth(rest)
            if not granted:
                self.stop("KherveDOC refused access to this spreadsheet"
                          + (f" ({scope})" if scope else "") + ".")
            else:
                self.read_only = scope == "readonly"
        return None

    def _on_doc_transaction(self, event):
        if not self._remote and not self._stopped:
            self._dirty = True
            if not self.read_only:
                self._send(create_update_message(event.update))

    def _map_observer(self, name):
        # pycrdt passes as many arguments as the callback accepts, so the
        # callback must take exactly one.
        def on_event(event):
            if self._remote:
                self._pending[name].update(event.keys)
        return on_event

    # ── First synchronisation ────────────────────────────────────────
    def _after_first_sync(self):
        if self.publish_local or not len(self.ysheets):
            if not self.publish_local:
                self.status_changed.emit("The shared workbook was empty — "
                                         "sharing yours instead")
            for name in self._pending:
                self._pending[name].clear()
            self._flush_local()
        else:
            self._load_from_doc()
        self.window._undo_stack.indexChanged.connect(self._schedule_flush)
        self._poll_timer.start()
        if self.kherve_doc:
            self._save_timer.start()
            if self.publish_local:
                self.save()   # a new spreadsheet: on the server at once
        self.status_changed.emit("Live (view only)" if self.read_only
                                 else "Live")

    def _load_from_doc(self):
        """Replace the (fresh) local workbook's sheets with the shared ones."""
        wb = self._wb
        placeholders = list(wb.all_sheets())
        # Move the fresh workbook's own sheets out of the way first, so a
        # shared "Sheet1" is not mistaken for the empty local one.
        for i, sheet in enumerate(placeholders):
            wb.tabs.setTabText(wb.tabs.indexOf(sheet), f"__local_{i}__")
        for name, ymap in ((model.SHEETS, self.ysheets),
                           (model.CELLS, self.ycells),
                           (model.FORMATS, self.yformats),
                           (model.WIDTHS, self.ywidths)):
            self._pending[name] = set(ymap.keys())
        # The placeholder sheets are about to go: do not publish them.
        self._apply_remote(flush_first=False)
        for sheet in placeholders:
            idx = wb.tabs.indexOf(sheet)
            if idx >= 0 and len(wb.all_sheets()) > 1:
                wb.tabs.removeTab(idx)
                sheet.deleteLater()
        # Cross-sheet formulas read the shared sheets now.
        wb.refresh_cross_sheet()
        wb.tabs.setCurrentIndex(0)
        self.window._wire_undo_to_sheets()

    # ── Local → shared ───────────────────────────────────────────────
    def _schedule_flush(self, *_):
        if not self._stopped:
            self._flush_timer.start()

    def _tick(self):
        if self._wb is not self.window._workbook:
            self.stop("Stopped sharing: another workbook was opened")
            return
        self._flush_local()
        self._update_presence()
        self._refresh_peers()

    def _flush_local(self):
        if self._busy or self._stopped or not self._synced or self.read_only:
            return
        if self._wb is not self.window._workbook:
            return
        wb = self._wb
        sheets = wb.all_sheets()
        with self.doc.transaction():
            seen = set()
            for order, sheet in enumerate(sheets):
                sheet_id = getattr(sheet, "_collab_id", None)
                if sheet_id is None:
                    sheet_id = sheet._collab_id = model.new_sheet_id()
                self._sheets[sheet_id] = sheet
                seen.add(sheet_id)
                meta = model.encode_json({
                    "name": wb.tabs.tabText(wb.tabs.indexOf(sheet)),
                    "order": order,
                    "rows": sheet.table.rowCount(),
                    "cols": sheet.table.columnCount(),
                })
                if self._last_meta.get(sheet_id) != meta:
                    self.ysheets[sheet_id] = meta
                    self._last_meta[sheet_id] = meta
                self._push_sheet(sheet_id, sheet)
            for sheet_id in list(self._last_meta):
                if sheet_id not in seen:
                    self._forget_sheet(sheet_id, shared=True)

    def _push_sheet(self, sheet_id, sheet):
        cells = model.cell_sources(sheet)
        old = self._last_cells.get(sheet_id, {})
        changed, removed = model.diff(old, cells)
        for (row, col), source in changed.items():
            self.ycells[model.cell_key(sheet_id, row, col)] = source
        for row, col in removed:
            self.ycells.pop(model.cell_key(sheet_id, row, col), None)
        self._last_cells[sheet_id] = cells

        formats = model.cell_formats(sheet)
        old = self._last_formats.get(sheet_id, {})
        changed, removed = model.diff(old, formats)
        for (row, col), value in changed.items():
            self.yformats[model.cell_key(sheet_id, row, col)] = value
        for row, col in removed:
            self.yformats.pop(model.cell_key(sheet_id, row, col), None)
        self._last_formats[sheet_id] = formats

        widths = model.column_widths(sheet)
        old = self._last_widths.get(sheet_id, {})
        changed, removed = model.diff(old, widths)
        for col, width in changed.items():
            self.ywidths[model.width_key(sheet_id, col)] = width
        for col in removed:
            self.ywidths.pop(model.width_key(sheet_id, col), None)
        self._last_widths[sheet_id] = widths

    def _forget_sheet(self, sheet_id, shared: bool):
        if shared:
            self.ysheets.pop(sheet_id, None)
            for ymap in (self.ycells, self.yformats, self.ywidths):
                for key in model.keys_for_sheet(list(ymap.keys()), sheet_id):
                    ymap.pop(key, None)
        for store in (self._last_meta, self._last_cells,
                      self._last_formats, self._last_widths, self._sheets):
            store.pop(sheet_id, None)

    # ── Shared → local ───────────────────────────────────────────────
    def _apply_remote(self, flush_first=True):
        if self._stopped or not self._synced:
            return
        if self._busy:
            self._apply_timer.start(100)
            return
        # Local edits not yet sent go first, so they are merged, not lost.
        if flush_first:
            self._flush_local()
        pending = {name: keys for name, keys in self._pending.items()}
        self._pending = {name: set() for name in pending}
        if not any(pending.values()):
            return
        if not self._confirm_python(pending[model.CELLS]):
            self._python_trusted = False
        new_sheets = bool(pending[model.SHEETS])
        self._busy = True
        try:
            self._apply_sheets(pending[model.SHEETS])
            self._apply_cells(pending[model.CELLS])
            self._apply_formats(pending[model.FORMATS])
            self._apply_widths(pending[model.WIDTHS])
        finally:
            self._busy = False
        self._refresh_peers()
        if new_sheets:
            self.peers_changed.emit(self._peers)   # cursors for new sheets

    def _confirm_python(self, cell_keys) -> bool:
        if self._python_trusted is not None:
            return self._python_trusted
        if not any(is_python_source(self.ycells.get(key) or "")
                   for key in cell_keys):
            return True
        self._busy = True
        try:
            self._python_trusted = self.window._confirm_python_trust(
                f"live:{self.room}")
        finally:
            self._busy = False
        return self._python_trusted

    def _apply_sheets(self, sheet_ids):
        wb = self._wb
        for sheet_id in sorted(sheet_ids, key=self._sheet_order):
            raw = self.ysheets.get(sheet_id)
            sheet = self._sheets.get(sheet_id)
            if raw is None:
                if sheet is not None and len(wb.all_sheets()) > 1:
                    wb.tabs.removeTab(wb.tabs.indexOf(sheet))
                    sheet.deleteLater()
                self._forget_sheet(sheet_id, shared=False)
                continue
            meta = json.loads(raw)
            if sheet is None:
                sheet = wb.add_sheet(meta.get("name") or None)
                sheet._collab_id = sheet_id
                sheet._undo_stack = self.window._undo_stack
                self._sheets[sheet_id] = sheet
            idx = wb.tabs.indexOf(sheet)
            if meta.get("name") and wb.tabs.tabText(idx) != meta["name"]:
                wb.tabs.setTabText(idx, meta["name"])
            self._ensure_size(sheet, meta.get("rows", 0) - 1,
                              meta.get("cols", 0) - 1)
            self._last_meta[sheet_id] = raw

    def _sheet_order(self, sheet_id):
        raw = self.ysheets.get(sheet_id)
        return json.loads(raw).get("order", 0) if raw else -1

    @staticmethod
    def _ensure_size(sheet, row, col):
        table = sheet.table
        if row >= table.rowCount():
            table.setRowCount(row + 1)
        if col >= table.columnCount():
            table.setColumnCount(col + 1)
            if hasattr(sheet, "_refresh_headers"):
                sheet._refresh_headers()

    def _apply_cells(self, keys):
        # Plain values first, then formulas, so formulas see their inputs.
        items = []
        for key in keys:
            sheet_id, row, col = model.parse_cell_key(key)
            sheet = self._sheets.get(sheet_id)
            if sheet is not None:
                items.append((sheet_id, sheet, row, col,
                              self.ycells.get(key) or ""))
        items.sort(key=lambda item: item[4].startswith("="))
        for sheet_id, sheet, row, col, source in items:
            self._apply_cell(sheet, row, col, source)
            actual = model.cell_source(sheet, row, col)
            last = self._last_cells.setdefault(sheet_id, {})
            if actual:
                last[(row, col)] = actual
            else:
                last.pop((row, col), None)

    def _apply_cell(self, sheet, row, col, source):
        self._ensure_size(sheet, row, col)
        table = sheet.table
        sheet._collab_applying = True
        try:
            table.blockSignals(True)
            try:
                item = table.item(row, col)
                if item is None:
                    item = QTableWidgetItem("")
                    table.setItem(row, col, item)
                if is_python_source(source) and not self._python_trusted:
                    sheet._cell_formulas[(row, col)] = source
                    item.setText(NOT_RUN)
                    sheet._shadow[(row, col)] = NOT_RUN
                    return
                if not source:
                    sheet._cell_formulas.pop((row, col), None)
                item.setText(source)
            finally:
                table.blockSignals(False)
            sheet._on_cell_changed(row, col)
        finally:
            sheet._collab_applying = False

    def _apply_formats(self, keys):
        from ..cellformat import CellFormat
        touched = set()
        for key in keys:
            sheet_id, row, col = model.parse_cell_key(key)
            sheet = self._sheets.get(sheet_id)
            if sheet is None:
                continue
            raw = self.yformats.get(key)
            self._ensure_size(sheet, row, col)
            table = sheet.table
            table.blockSignals(True)
            try:
                item = table.item(row, col)
                if item is None:
                    item = QTableWidgetItem("")
                    table.setItem(row, col, item)
                item.setFont(QFont(table.font()))
                if raw is None:
                    sheet._cell_formats.pop((row, col), None)
                    sheet._apply_format_to_item(item, CellFormat())
                    self._last_formats.get(sheet_id, {}).pop(
                        (row, col), None)
                else:
                    fmt = CellFormat.from_dict(json.loads(raw))
                    sheet._cell_formats[(row, col)] = fmt
                    sheet._apply_format_to_item(item, fmt)
                    # Remember it as this side writes it, so it is not
                    # sent back merely because the JSON is laid out
                    # differently (KherveCELL writes unsorted keys).
                    self._last_formats.setdefault(sheet_id, {})[
                        (row, col)] = model.encode_json(fmt.to_dict())
            finally:
                table.blockSignals(False)
            touched.add(sheet)
        for sheet in touched:
            sheet.table.viewport().update()

    def _apply_widths(self, keys):
        for key in keys:
            sheet_id, col = model.parse_width_key(key)
            sheet = self._sheets.get(sheet_id)
            if sheet is None:
                continue
            header = sheet.table.horizontalHeader()
            width = self.ywidths.get(key)
            if width is None:
                width = header.defaultSectionSize()
                self._last_widths.get(sheet_id, {}).pop(col, None)
            else:
                width = int(width)
                self._last_widths.setdefault(sheet_id, {})[col] = width
            self._ensure_size(sheet, 0, col)
            sheet._resizing_sections = True
            try:
                sheet.table.setColumnWidth(col, width)
            finally:
                sheet._resizing_sections = False

    # ── Presence ─────────────────────────────────────────────────────
    def _update_presence(self, force=False):
        sheet = self._wb.current_sheet() if self._wb else None
        state = {"user": self.user, "color": self.color}
        if sheet is not None:
            index = sheet.table.currentIndex()
            state["sheet"] = getattr(sheet, "_collab_id", None)
            if index.isValid():
                state["cell"] = [index.row(), index.column()]
                # The same, in the form KherveCELL (the web grid) reads.
                state["kherveCell"] = {
                    "sheetId": state["sheet"], "row": index.row(),
                    "col": index.column(), "name": self.user,
                    "color": self.color,
                }
        now = time.monotonic()
        if (force or state != self.awareness.get_local_state()
                or now - self._last_heartbeat > HEARTBEAT_S):
            self.awareness.set_local_state(state)
            self._last_heartbeat = now
            self._send_awareness()

    def _refresh_peers(self):
        now_ms = time.time() * 1000
        peers = []
        for client_id, state in self.awareness.states.items():
            if client_id == self.awareness.client_id or not state:
                continue
            seen = self.awareness.meta.get(client_id, {}).get(
                "lastUpdated", now_ms)
            if now_ms - seen > PEER_TIMEOUT_S * 1000:
                continue
            peer = dict(state)
            web = state.get("kherveCell")
            if isinstance(web, dict):
                # A KherveCELL (browser) user.
                peer.setdefault("user", web.get("name") or "Someone")
                peer.setdefault("color", web.get("color") or "#1971c2")
                peer.setdefault("sheet", web.get("sheetId"))
                if "row" in web and "col" in web:
                    peer.setdefault("cell", [web["row"], web["col"]])
            if "user" not in peer:
                continue   # e.g. a text editor's cursor, not a sheet user
            peers.append(peer)
        peers.sort(key=lambda peer: peer.get("user", ""))
        if peers != self._peers:
            self._peers = peers
            self.peers_changed.emit(peers)

    def peer_location(self, peer) -> str:
        """``Sheet1!B3`` for a collaborator's current cell."""
        from ..sheet import col_index_to_letter
        sheet = self._sheets.get(peer.get("sheet"))
        cell = peer.get("cell")
        if sheet is None or not cell:
            return ""
        name = self._wb.tabs.tabText(self._wb.tabs.indexOf(sheet))
        return f"{name}!{col_index_to_letter(cell[1])}{cell[0] + 1}"
