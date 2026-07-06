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

# Each glyph is built in a unit box (x, y in 0..1, y downward). Caps fill
# the box height; lowercase glyphs sit on the baseline (y=1) at *xh* of it.


def _glyph_K():
    w = 0.82
    p = QPainterPath()
    p.moveTo(0.0, 0.0); p.lineTo(0.0, 1.0)
    p.moveTo(0.0, 0.52); p.lineTo(w, 0.0)
    p.moveTo(0.0, 0.52); p.lineTo(w, 1.0)
    return p, w


def _glyph_S():
    w = 0.64
    p = QPainterPath()
    p.moveTo(0.60, 0.20)
    p.cubicTo(0.54, 0.00, 0.08, 0.00, 0.06, 0.26)
    p.cubicTo(0.04, 0.46, 0.60, 0.46, 0.58, 0.70)
    p.cubicTo(0.56, 1.00, 0.10, 1.00, 0.04, 0.78)
    return p, w


def _glyph_h(xh):
    w = 0.64
    top = 1.0 - xh
    p = QPainterPath()
    p.moveTo(0.0, 0.0); p.lineTo(0.0, 1.0)               # full-height stem
    p.moveTo(0.0, top + 0.12)                            # shoulder + right leg
    p.cubicTo(0.0, top, w, top, w, top + 0.12)
    p.lineTo(w, 1.0)
    return p, w


def _glyph_e(xh):
    w = 0.66
    top = 1.0 - xh
    a, b = 0.03, w - 0.03
    mid = top + xh * 0.42
    p = QPainterPath()
    p.moveTo(b - 0.02, mid)                              # bowl, open lower-right
    p.cubicTo(b + 0.03, top - 0.03, a - 0.03, top - 0.03, a, mid)
    p.cubicTo(a - 0.03, 1.0, b + 0.03, 1.0, b, 1.0 - xh * 0.20)
    p.moveTo(a + 0.02, mid); p.lineTo(b - 0.02, mid)     # crossbar
    return p, w


def _glyph_t(xh):
    w = 0.42
    top = 1.0 - xh
    p = QPainterPath()
    p.moveTo(w * 0.40, top - 0.16); p.lineTo(w * 0.40, 0.96)   # stem
    p.moveTo(0.0, top); p.lineTo(w, top)                       # crossbar
    return p, w


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


def _wordmark(p, rect):
    xh = 0.66
    items = [_glyph_K(), _glyph_S(), _glyph_h(xh), _glyph_e(xh),
             _glyph_e(xh), _glyph_t(xh)]
    gap = 0.10
    total = sum(w for _p, w in items) + gap * (len(items) - 1)
    pad_x, pad_y = rect.width() * 0.11, rect.height() * 0.22
    ch = min(rect.height() - 2 * pad_y, (rect.width() - 2 * pad_x) / total)
    x = rect.x() + (rect.width() - total * ch) / 2.0
    top = rect.y() + (rect.height() - ch) / 2.0
    for path, gw in items:
        _stroke(p, path, _INK, QRectF(x, top, gw * ch, ch), 0.15)
        x += (gw + gap) * ch


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
    _wordmark(p, QRectF(x, y + h * 0.05, w, h * 0.44))
    gw, gh = w * 0.46, h * 0.38
    _grid(p, QRectF(x + (w - gw) / 2.0, y + h * 0.54, gw, gh))
    p.end()
    return pm
