"""Embedded image — movable/resizable picture overlaid on grid.

Images float as child widgets of the sheet's table viewport, just like
embedded charts.  They can be dragged to reposition and resized via
edge handles.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import base64

from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QCursor, QImage
from PyQt5.QtWidgets import QWidget, QMenu, QFileDialog

# Resize handle size in pixels.
_HANDLE = 6


class EmbeddedImage(QWidget):
    """A picture that lives as a child of the grid viewport."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._pixmap = pixmap
        self._selected = False

        # Dragging / resizing state.
        self._drag_origin = None
        self._drag_widget_pos = None
        self._resizing = False
        self._resize_edge = None

        # Size to pixmap, capped to reasonable dimensions.
        pw = min(pixmap.width(), 600)
        ph = min(pixmap.height(), 600)
        if pixmap.width() > 600 or pixmap.height() > 600:
            scaled = pixmap.scaled(600, 600, Qt.KeepAspectRatio,
                                   Qt.SmoothTransformation)
            pw, ph = scaled.width(), scaled.height()
        self.setMinimumSize(40, 40)
        self.resize(pw + 4, ph + 4)  # small border margin
        self.show()

    # ── Painting ──────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        # Draw scaled pixmap inside widget bounds (with 2px margin).
        target = self.rect().adjusted(2, 2, -2, -2)
        p.drawPixmap(target, self._pixmap)
        # Selection border.
        if self._selected:
            pen = QPen(QColor("#3078c6"), 2, Qt.DashLine)
            p.setPen(pen)
            p.drawRect(self.rect().adjusted(0, 0, -1, -1))
            # Draw resize handles at corners and midpoints.
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#3078c6"))
            for hx, hy in self._handle_positions():
                p.drawRect(hx - _HANDLE // 2, hy - _HANDLE // 2,
                           _HANDLE, _HANDLE)
        p.end()

    def _handle_positions(self):
        """Yield (x, y) of the 8 resize handles."""
        r = self.rect()
        mx = r.width() // 2
        my = r.height() // 2
        return [
            (0, 0), (mx, 0), (r.width(), 0),
            (0, my), (r.width(), my),
            (0, r.height()), (mx, r.height()),
            (r.width(), r.height()),
        ]

    # ── Mouse interaction ─────────────────────────────────────────────

    def _edge_at(self, pos):
        """Return resize-edge string (combination of t/b/l/r) or ''."""
        r = self.rect()
        edge = ""
        if pos.y() <= _HANDLE:
            edge += "t"
        elif pos.y() >= r.height() - _HANDLE:
            edge += "b"
        if pos.x() <= _HANDLE:
            edge += "l"
        elif pos.x() >= r.width() - _HANDLE:
            edge += "r"
        return edge

    def _cursor_for_edge(self, edge):
        m = {
            "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
            "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor,
            "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
            "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
        }
        return m.get(edge, Qt.ArrowCursor)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._selected = True
            self.update()
            edge = self._edge_at(ev.pos()) if self._selected else ""
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._drag_origin = ev.globalPos()
                self._drag_widget_pos = self.geometry()
            else:
                self._drag_origin = ev.globalPos()
                self._drag_widget_pos = self.pos()
            self.raise_()

    def mouseMoveEvent(self, ev):
        if self._resizing and self._drag_origin:
            delta = ev.globalPos() - self._drag_origin
            geo = QRect(self._drag_widget_pos)
            e = self._resize_edge
            if "l" in e:
                geo.setLeft(geo.left() + delta.x())
            if "r" in e:
                geo.setRight(geo.right() + delta.x())
            if "t" in e:
                geo.setTop(geo.top() + delta.y())
            if "b" in e:
                geo.setBottom(geo.bottom() + delta.y())
            if geo.width() >= self.minimumWidth() and \
               geo.height() >= self.minimumHeight():
                self.setGeometry(geo)
        elif self._drag_origin:
            delta = ev.globalPos() - self._drag_origin
            self.move(self._drag_widget_pos + delta)
        else:
            edge = self._edge_at(ev.pos()) if self._selected else ""
            if edge:
                self.setCursor(self._cursor_for_edge(edge))
            else:
                self.setCursor(Qt.SizeAllCursor)

    def mouseReleaseEvent(self, ev):
        self._drag_origin = None
        self._drag_widget_pos = None
        self._resizing = False
        self._resize_edge = None

    def contextMenuEvent(self, ev):
        menu = QMenu(self)
        menu.addAction("Replace Image…", self._replace_image)
        menu.addSeparator()
        menu.addAction("Delete", self._delete)
        menu.exec_(ev.globalPos())

    def _replace_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Replace Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.svg);;All Files (*)")
        if path:
            pm = QPixmap(path)
            if not pm.isNull():
                self._pixmap = pm
                self.update()

    def _delete(self):
        """Remove this image from the sheet."""
        sheet = self.parent()
        if sheet and hasattr(sheet, 'parent'):
            # Walk up to find the SheetWidget that owns _images.
            sw = sheet.parent()
            while sw and not hasattr(sw, '_images'):
                sw = sw.parent()
            if sw and hasattr(sw, '_images'):
                if self in sw._images:
                    sw._images.remove(self)
        self.deleteLater()

    # ── Serialisation ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialise image to a dict for persistence."""
        # Encode pixmap as PNG base64.
        from PyQt5.QtCore import QBuffer, QIODevice
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        self._pixmap.save(buf, "PNG")
        data = base64.b64encode(bytes(buf.data())).decode("ascii")
        buf.close()
        return {
            "pos_x": self.pos().x(),
            "pos_y": self.pos().y(),
            "width": self.width(),
            "height": self.height(),
            "data": data,
        }

    @classmethod
    def from_dict(cls, d: dict, parent=None) -> EmbeddedImage:
        """Restore an image from a serialised dict."""
        raw = base64.b64decode(d["data"])
        pm = QPixmap()
        pm.loadFromData(raw, "PNG")
        img = cls(pm, parent)
        img.move(d["pos_x"], d["pos_y"])
        img.resize(d["width"], d["height"])
        return img
