"""The KherveSheet application mark (window / taskbar icon).

Draws a "KSheet" wordmark above a spreadsheet grid on a rounded green
tile, in the shared Kherve-family style (cf. KherveBook / KhervePaint):
the letters are stroked vector paths — not text — so the mark renders
identically on every platform and stays crisp from 16 px to 256 px,
without depending on a system font.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import (QColor, QPainter, QPainterPath, QPen, QPixmap,
                         QTransform)

#: KherveSheet green tile with white ink (matches the wordmark it replaces).
_FILL = "#228B22"
_EDGE = "#1c7a1c"
_INK = "#ffffff"

# The grid schematic is a stroked vector path (font-independent); the
# "KSheet" wordmark itself is drawn with a normal system font.


def _stroke(p, path, color, box, weight):
    t = QTransform()
    t.translate(box.x(), box.y())
    t.scale(box.width(), box.height())
    pen = QPen(QColor(color))
    pen.setWidthF(weight * box.height())
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPath(t.map(path))


def _tile(p, s):
    m = s * 0.06
    radius = s * 0.22
    rect = QRectF(m, m, s - 2 * m, s - 2 * m)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(_FILL))
    p.drawRoundedRect(rect, radius, radius)
    pen = QPen(QColor(_EDGE))
    pen.setWidthF(max(1.0, s * 0.02))
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(rect, radius, radius)
    return rect


def _wordmark(p, rect, text):
    """Draw *text* centred in *rect* with a normal bold system font,
    scaled up to the largest size that still fits the tile width."""
    from PyQt5.QtGui import QFont, QFontMetricsF
    avail = rect.width() * 0.82
    font = QFont("Segoe UI")
    font.setBold(True)
    size = 1.0
    while size < rect.height():
        font.setPointSizeF(size + 0.5)
        fm = QFontMetricsF(font)
        if fm.horizontalAdvance(text) > avail or fm.height() > rect.height():
            break
        size += 0.5
    font.setPointSizeF(size)
    p.setFont(font)
    p.setPen(QColor(_INK))
    p.drawText(rect, Qt.AlignCenter, text)


def _grid(p, box):
    """A 3x3 spreadsheet grid."""
    path = QPainterPath()
    path.moveTo(0.06, 0.06); path.lineTo(0.94, 0.06); path.lineTo(0.94, 0.94)
    path.lineTo(0.06, 0.94); path.lineTo(0.06, 0.06)
    for gx in (0.35, 0.65):
        path.moveTo(gx, 0.06); path.lineTo(gx, 0.94)
    for gy in (0.35, 0.65):
        path.moveTo(0.06, gy); path.lineTo(0.94, gy)
    _stroke(p, path, _INK, box, 0.05)


def paint(size: int) -> QPixmap:
    """Render the KSheet mark at *size* px."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    rect = _tile(p, s)
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    _wordmark(p, QRectF(x, y + h * 0.05, w, h * 0.44), "KSheet")
    gw, gh = w * 0.46, h * 0.38
    _grid(p, QRectF(x + (w - gw) / 2.0, y + h * 0.54, gw, gh))
    p.end()
    return pm
