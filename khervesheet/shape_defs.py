"""Shape geometry registry for embedded shapes.

Every shape is defined once as a small function that paints itself into
a normalised ``QRectF`` using the painter's current pen and brush.  Both
the on-canvas ``EmbeddedShape`` and the toolbar icon factory render
through this registry, so a shape looks identical everywhere and new
shapes only need a single entry here.

Shapes are grouped into the same categories Excel uses (Lines,
Rectangles, Basic Shapes, Block Arrows, Equation Shapes, Flowchart,
Stars and Banners, Callouts).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QPainterPath, QPolygonF

# key -> {"label": str, "cat": str, "line": bool, "fn": callable}
SHAPES: dict = {}

CATEGORY_ORDER = [
    "Lines",
    "Rectangles",
    "Basic Shapes",
    "Block Arrows",
    "Equation Shapes",
    "Flowchart",
    "Stars and Banners",
    "Callouts",
]


def _reg(key, label, cat, fn, line=False):
    SHAPES[key] = {"label": label, "cat": cat, "fn": fn, "line": line}


# ── Generic geometry helpers ────────────────────────────────────────

def _poly(points) -> QPainterPath:
    path = QPainterPath()
    path.addPolygon(QPolygonF([QPointF(x, y) for x, y in points]))
    path.closeSubpath()
    return path


def _regular(rect: QRectF, n: int, rot_deg: float = -90.0) -> QPainterPath:
    cx, cy = rect.center().x(), rect.center().y()
    rx, ry = rect.width() / 2, rect.height() / 2
    pts = []
    for i in range(n):
        a = math.radians(rot_deg) + 2 * math.pi * i / n
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return _poly(pts)


def _star_path(rect: QRectF, n: int, inner: float = 0.4,
               rot_deg: float = -90.0) -> QPainterPath:
    cx, cy = rect.center().x(), rect.center().y()
    rx, ry = rect.width() / 2, rect.height() / 2
    pts = []
    for i in range(2 * n):
        rr = 1.0 if i % 2 == 0 else inner
        a = math.radians(rot_deg) + math.pi * i / n
        pts.append((cx + rx * rr * math.cos(a), cy + ry * rr * math.sin(a)))
    return _poly(pts)


def _draw_arrowhead(p, a: QPointF, b: QPointF, size: float):
    """Filled triangular head at *b* pointing along a→b."""
    ang = math.atan2(b.y() - a.y(), b.x() - a.x())
    left = QPointF(b.x() - size * math.cos(ang - math.pi / 7),
                   b.y() - size * math.sin(ang - math.pi / 7))
    right = QPointF(b.x() - size * math.cos(ang + math.pi / 7),
                    b.y() - size * math.sin(ang + math.pi / 7))
    br = p.brush()
    p.save()
    p.setBrush(p.pen().color())
    p.drawPolygon(QPolygonF([b, left, right]))
    p.setBrush(br)
    p.restore()


def _path(build):
    """Wrap a rect->QPainterPath builder into a painter draw fn."""
    def fn(p, r):
        p.drawPath(build(r))
    return fn


# ── Lines & connectors ──────────────────────────────────────────────

def _line(p, r):
    yc = r.center().y()
    p.drawLine(QPointF(r.left(), yc), QPointF(r.right(), yc))


def _arrow(p, r):
    yc = r.center().y()
    a, b = QPointF(r.left(), yc), QPointF(r.right(), yc)
    p.drawLine(a, b)
    _draw_arrowhead(p, a, b, 10 + p.pen().widthF() * 2)


def _double_arrow(p, r):
    yc = r.center().y()
    a, b = QPointF(r.left(), yc), QPointF(r.right(), yc)
    p.drawLine(a, b)
    size = 10 + p.pen().widthF() * 2
    _draw_arrowhead(p, a, b, size)
    _draw_arrowhead(p, b, a, size)


def _elbow(p, r):
    mx = r.center().x()
    p.drawLine(QPointF(r.left(), r.top()), QPointF(mx, r.top()))
    p.drawLine(QPointF(mx, r.top()), QPointF(mx, r.bottom()))
    p.drawLine(QPointF(mx, r.bottom()), QPointF(r.right(), r.bottom()))


def _elbow_arrow(p, r):
    _elbow(p, r)
    _draw_arrowhead(p, QPointF(r.center().x(), r.bottom()),
                    QPointF(r.right(), r.bottom()),
                    10 + p.pen().widthF() * 2)


def _curved(p, r):
    path = QPainterPath()
    path.moveTo(r.left(), r.bottom())
    path.cubicTo(r.left(), r.top(), r.right(), r.bottom(),
                 r.right(), r.top())
    p.drawPath(path)


def _curved_arrow(p, r):
    _curved(p, r)
    _draw_arrowhead(p, QPointF(r.right(), r.center().y()),
                    QPointF(r.right(), r.top()),
                    10 + p.pen().widthF() * 2)


_reg("line", "Line", "Lines", _line, line=True)
_reg("arrow", "Arrow", "Lines", _arrow, line=True)
_reg("double_arrow", "Double Arrow", "Lines", _double_arrow, line=True)
_reg("elbow", "Elbow Connector", "Lines", _elbow, line=True)
_reg("elbow_arrow", "Elbow Arrow", "Lines", _elbow_arrow, line=True)
_reg("curve", "Curve", "Lines", _curved, line=True)
_reg("curve_arrow", "Curved Arrow", "Lines", _curved_arrow, line=True)


# ── Rectangles ──────────────────────────────────────────────────────

def _round_radius(r):
    return min(r.width(), r.height()) * 0.18


def _rect_path(r):
    path = QPainterPath()
    path.addRect(r)
    return path


def _rounded_path(r):
    path = QPainterPath()
    rad = _round_radius(r)
    path.addRoundedRect(r, rad, rad)
    return path


def _snip_corner(r):
    s = min(r.width(), r.height()) * 0.22
    return _poly([(r.left(), r.top()), (r.right() - s, r.top()),
                  (r.right(), r.top() + s), (r.right(), r.bottom()),
                  (r.left(), r.bottom())])


def _snip_diagonal(r):
    s = min(r.width(), r.height()) * 0.22
    return _poly([(r.left() + s, r.top()), (r.right(), r.top()),
                  (r.right(), r.bottom() - s), (r.right() - s, r.bottom()),
                  (r.left(), r.bottom()), (r.left(), r.top() + s)])


def _round_one(r):
    path = QPainterPath()
    s = min(r.width(), r.height()) * 0.3
    path.moveTo(r.left(), r.top())
    path.lineTo(r.right() - s, r.top())
    path.quadTo(r.right(), r.top(), r.right(), r.top() + s)
    path.lineTo(r.right(), r.bottom())
    path.lineTo(r.left(), r.bottom())
    path.closeSubpath()
    return path


def _plaque(r):
    path = QPainterPath()
    s = min(r.width(), r.height()) * 0.22
    path.moveTo(r.left() + s, r.top())
    path.lineTo(r.right() - s, r.top())
    path.quadTo(r.right(), r.top(), r.right(), r.top() + s)
    path.lineTo(r.right(), r.bottom() - s)
    path.quadTo(r.right(), r.bottom(), r.right() - s, r.bottom())
    path.lineTo(r.left() + s, r.bottom())
    path.quadTo(r.left(), r.bottom(), r.left(), r.bottom() - s)
    path.lineTo(r.left(), r.top() + s)
    path.quadTo(r.left(), r.top(), r.left() + s, r.top())
    return path


_reg("rectangle", "Rectangle", "Rectangles", _path(_rect_path))
_reg("rounded_rect", "Rounded Rectangle", "Rectangles", _path(_rounded_path))
_reg("snip_corner_rect", "Snip Corner", "Rectangles", _path(_snip_corner))
_reg("snip_diagonal_rect", "Snip Diagonal", "Rectangles",
     _path(_snip_diagonal))
_reg("round_corner_rect", "Round Single Corner", "Rectangles",
     _path(_round_one))
_reg("plaque", "Plaque", "Rectangles", _path(_plaque))


# ── Basic shapes ────────────────────────────────────────────────────

def _oval_path(r):
    path = QPainterPath()
    path.addEllipse(r)
    return path


def _triangle(r):
    return _poly([(r.center().x(), r.top()),
                  (r.left(), r.bottom()), (r.right(), r.bottom())])


def _right_triangle(r):
    return _poly([(r.left(), r.top()),
                  (r.left(), r.bottom()), (r.right(), r.bottom())])


def _parallelogram(r):
    o = r.width() * 0.25
    return _poly([(r.left() + o, r.top()), (r.right(), r.top()),
                  (r.right() - o, r.bottom()), (r.left(), r.bottom())])


def _trapezoid(r):
    o = r.width() * 0.22
    return _poly([(r.left() + o, r.top()), (r.right() - o, r.top()),
                  (r.right(), r.bottom()), (r.left(), r.bottom())])


def _diamond(r):
    return _poly([(r.center().x(), r.top()), (r.right(), r.center().y()),
                  (r.center().x(), r.bottom()), (r.left(), r.center().y())])


def _cross(r, th=0.34):
    w, h = r.width(), r.height()
    ax, ay = w * th, h * th
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    cx0, cx1 = l + (w - ax) / 2, r.right() - (w - ax) / 2
    cy0, cy1 = t + (h - ay) / 2, b - (h - ay) / 2
    return _poly([(cx0, t), (cx1, t), (cx1, cy0), (rt, cy0), (rt, cy1),
                  (cx1, cy1), (cx1, b), (cx0, b), (cx0, cy1), (l, cy1),
                  (l, cy0), (cx0, cy0)])


def _heart(r):
    w, h = r.width(), r.height()
    l, t = r.left(), r.top()
    path = QPainterPath()
    path.moveTo(l + w / 2, t + h * 0.95)
    path.cubicTo(l - w * 0.1, t + h * 0.4, l + w * 0.2, t - h * 0.05,
                 l + w / 2, t + h * 0.28)
    path.cubicTo(l + w * 0.8, t - h * 0.05, l + w * 1.1, t + h * 0.4,
                 l + w / 2, t + h * 0.95)
    return path


def _lightning(r):
    w, h = r.width(), r.height()
    l, t = r.left(), r.top()
    return _poly([(l + w * 0.42, t), (l + w * 0.0 + w * 0.62, t),
                  (l + w * 0.40, t + h * 0.42), (l + w * 0.66, t + h * 0.42),
                  (l + w * 0.30, t + h), (l + w * 0.50, t + h * 0.52),
                  (l + w * 0.24, t + h * 0.52)])


def _donut(r):
    path = QPainterPath()
    path.setFillRule(Qt.OddEvenFill)
    path.addEllipse(r)
    d = min(r.width(), r.height()) * 0.25
    path.addEllipse(r.adjusted(d, d, -d, -d))
    return path


def _frame(r):
    path = QPainterPath()
    path.setFillRule(Qt.OddEvenFill)
    path.addRect(r)
    d = min(r.width(), r.height()) * 0.16
    path.addRect(r.adjusted(d, d, -d, -d))
    return path


def _pie(r):
    path = QPainterPath()
    path.moveTo(r.center())
    path.arcTo(r, 0, 300)
    path.closeSubpath()
    return path


def _chord(r):
    path = QPainterPath()
    path.arcMoveTo(r, 30)
    path.arcTo(r, 30, 300)
    path.closeSubpath()
    return path


def _teardrop(r):
    path = QPainterPath()
    path.moveTo(r.right(), r.top())
    path.arcTo(r, 90, 270)
    path.lineTo(r.right(), r.top())
    path.closeSubpath()
    return path


def _can(p, r):
    eh = r.height() * 0.18
    body = QRectF(r.left(), r.top() + eh / 2,
                  r.width(), r.height() - eh)
    top = QRectF(r.left(), r.top(), r.width(), eh)
    path = QPainterPath()
    path.moveTo(r.left(), r.top() + eh / 2)
    path.lineTo(r.left(), r.bottom() - eh / 2)
    path.arcTo(QRectF(r.left(), r.bottom() - eh, r.width(), eh), 180, 180)
    path.lineTo(r.right(), r.top() + eh / 2)
    p.drawPath(path)
    p.drawEllipse(top)


def _cube(p, r):
    d = min(r.width(), r.height()) * 0.25
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    front = _poly([(l, t + d), (rt - d, t + d), (rt - d, b), (l, b)])
    p.drawPath(front)
    top = _poly([(l, t + d), (l + d, t), (rt, t), (rt - d, t + d)])
    p.drawPath(top)
    side = _poly([(rt - d, t + d), (rt, t), (rt, b - d), (rt - d, b)])
    p.drawPath(side)


def _sun(p, r):
    cx, cy = r.center().x(), r.center().y()
    rad = min(r.width(), r.height()) * 0.28
    outer = min(r.width(), r.height()) * 0.48
    for i in range(12):
        a = 2 * math.pi * i / 12
        p.drawLine(QPointF(cx + rad * math.cos(a), cy + rad * math.sin(a)),
                   QPointF(cx + outer * math.cos(a),
                           cy + outer * math.sin(a)))
    p.drawEllipse(QPointF(cx, cy), rad, rad)


def _moon(r):
    path = QPainterPath()
    path.moveTo(r.right(), r.top())
    path.arcTo(r, 90, -180)
    path.arcTo(r.adjusted(r.width() * 0.35, 0, 0, 0), -90, 180)
    path.closeSubpath()
    return path


def _cloud(p, r):
    w, h = r.width(), r.height()
    l, t = r.left(), r.top()
    bumps = [(0.22, 0.62, 0.22), (0.18, 0.32, 0.20), (0.45, 0.25, 0.24),
             (0.72, 0.34, 0.20), (0.78, 0.62, 0.20), (0.5, 0.72, 0.26)]
    path = QPainterPath()
    for fx, fy, fr in bumps:
        cx, cy = l + w * fx, t + h * fy
        rr = min(w, h) * fr
        path.addEllipse(QPointF(cx, cy), rr, rr)
    path.setFillRule(Qt.WindingFill)
    p.drawPath(path.simplified())


def _smiley(p, r):
    p.drawEllipse(r)
    w, h = r.width(), r.height()
    l, t = r.left(), r.top()
    er = min(w, h) * 0.06
    p.drawEllipse(QPointF(l + w * 0.36, t + h * 0.4), er, er)
    p.drawEllipse(QPointF(l + w * 0.64, t + h * 0.4), er, er)
    mouth = QRectF(l + w * 0.28, t + h * 0.4, w * 0.44, h * 0.35)
    p.drawArc(mouth, 200 * 16, 140 * 16)


_reg("oval", "Oval", "Basic Shapes", _path(_oval_path))
_reg("triangle", "Triangle", "Basic Shapes", _path(_triangle))
_reg("right_triangle", "Right Triangle", "Basic Shapes",
     _path(_right_triangle))
_reg("parallelogram", "Parallelogram", "Basic Shapes",
     _path(_parallelogram))
_reg("trapezoid", "Trapezoid", "Basic Shapes", _path(_trapezoid))
_reg("diamond", "Diamond", "Basic Shapes", _path(_diamond))
_reg("pentagon", "Pentagon", "Basic Shapes", _path(lambda r: _regular(r, 5)))
_reg("hexagon", "Hexagon", "Basic Shapes",
     _path(lambda r: _regular(r, 6, 0)))
_reg("heptagon", "Heptagon", "Basic Shapes", _path(lambda r: _regular(r, 7)))
_reg("octagon", "Octagon", "Basic Shapes",
     _path(lambda r: _regular(r, 8, 22.5)))
_reg("decagon", "Decagon", "Basic Shapes", _path(lambda r: _regular(r, 10)))
_reg("dodecagon", "Dodecagon", "Basic Shapes",
     _path(lambda r: _regular(r, 12)))
_reg("cross", "Cross", "Basic Shapes", _path(_cross))
_reg("heart", "Heart", "Basic Shapes", _path(_heart))
_reg("lightning", "Lightning Bolt", "Basic Shapes", _path(_lightning))
_reg("donut", "Donut", "Basic Shapes", _path(_donut))
_reg("frame", "Frame", "Basic Shapes", _path(_frame))
_reg("pie", "Pie", "Basic Shapes", _path(_pie))
_reg("chord", "Chord", "Basic Shapes", _path(_chord))
_reg("teardrop", "Teardrop", "Basic Shapes", _path(_teardrop))
_reg("can", "Cylinder", "Basic Shapes", _can)
_reg("cube", "Cube", "Basic Shapes", _cube)
_reg("sun", "Sun", "Basic Shapes", _sun)
_reg("moon", "Moon", "Basic Shapes", _path(_moon))
_reg("cloud", "Cloud", "Basic Shapes", _cloud)
_reg("smiley", "Smiley Face", "Basic Shapes", _smiley)


# ── Block arrows ────────────────────────────────────────────────────

def _r_arrow(r):
    w, h = r.width(), r.height()
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    cy = r.center().y()
    hw = w * 0.4
    sh = h * 0.28
    return _poly([(l, cy - sh), (rt - hw, cy - sh), (rt - hw, t),
                  (rt, cy), (rt - hw, b), (rt - hw, cy + sh), (l, cy + sh)])


def _l_arrow(r):
    w, h = r.width(), r.height()
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    cy = r.center().y()
    hw = w * 0.4
    sh = h * 0.28
    return _poly([(rt, cy - sh), (l + hw, cy - sh), (l + hw, t),
                  (l, cy), (l + hw, b), (l + hw, cy + sh), (rt, cy + sh)])


def _u_arrow(r):
    w, h = r.width(), r.height()
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    cx = r.center().x()
    hh = h * 0.4
    sw = w * 0.28
    return _poly([(cx - sw, b), (cx - sw, t + hh), (l, t + hh),
                  (cx, t), (rt, t + hh), (cx + sw, t + hh), (cx + sw, b)])


def _d_arrow(r):
    w, h = r.width(), r.height()
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    cx = r.center().x()
    hh = h * 0.4
    sw = w * 0.28
    return _poly([(cx - sw, t), (cx - sw, b - hh), (l, b - hh),
                  (cx, b), (rt, b - hh), (cx + sw, b - hh), (cx + sw, t)])


def _lr_arrow(r):
    w, h = r.width(), r.height()
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    cy = r.center().y()
    hw = w * 0.25
    sh = h * 0.28
    return _poly([(l, cy), (l + hw, t), (l + hw, cy - sh),
                  (rt - hw, cy - sh), (rt - hw, t), (rt, cy),
                  (rt - hw, b), (rt - hw, cy + sh), (l + hw, cy + sh),
                  (l + hw, b)])


def _chevron(r):
    w = r.width()
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    cy = r.center().y()
    n = w * 0.3
    return _poly([(l, t), (rt - n, t), (rt, cy), (rt - n, b),
                  (l, b), (l + n, cy)])


def _pentagon_arrow(r):
    w = r.width()
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    cy = r.center().y()
    pt = w * 0.3
    return _poly([(l, t), (rt - pt, t), (rt, cy), (rt - pt, b), (l, b)])


def _notched_arrow(r):
    w, h = r.width(), r.height()
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    cy = r.center().y()
    hw = w * 0.4
    sh = h * 0.28
    nt = w * 0.12
    return _poly([(l, cy - sh), (rt - hw, cy - sh), (rt - hw, t),
                  (rt, cy), (rt - hw, b), (rt - hw, cy + sh),
                  (l, cy + sh), (l + nt, cy)])


def _quad_arrow(r):
    cx, cy = r.center().x(), r.center().y()
    w, h = r.width(), r.height()
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    aw = w * 0.13
    hw = w * 0.22
    return _poly([
        (cx, t), (cx + hw, t + h * 0.22), (cx + aw, t + h * 0.22),
        (cx + aw, cy - aw), (rt - w * 0.22, cy - aw),
        (rt - w * 0.22, cy - hw), (rt, cy), (rt - w * 0.22, cy + hw),
        (rt - w * 0.22, cy + aw), (cx + aw, cy + aw),
        (cx + aw, b - h * 0.22), (cx + hw, b - h * 0.22), (cx, b),
        (cx - hw, b - h * 0.22), (cx - aw, b - h * 0.22),
        (cx - aw, cy + aw), (l + w * 0.22, cy + aw),
        (l + w * 0.22, cy + hw), (l, cy), (l + w * 0.22, cy - hw),
        (l + w * 0.22, cy - aw), (cx - aw, cy - aw),
        (cx - aw, t + h * 0.22), (cx - hw, t + h * 0.22)])


_reg("right_arrow", "Right Arrow", "Block Arrows", _path(_r_arrow))
_reg("left_arrow", "Left Arrow", "Block Arrows", _path(_l_arrow))
_reg("up_arrow", "Up Arrow", "Block Arrows", _path(_u_arrow))
_reg("down_arrow", "Down Arrow", "Block Arrows", _path(_d_arrow))
_reg("left_right_arrow", "Left-Right Arrow", "Block Arrows",
     _path(_lr_arrow))
_reg("chevron", "Chevron", "Block Arrows", _path(_chevron))
_reg("pentagon_arrow", "Pentagon Arrow", "Block Arrows",
     _path(_pentagon_arrow))
_reg("notched_arrow", "Notched Arrow", "Block Arrows", _path(_notched_arrow))
_reg("quad_arrow", "Quad Arrow", "Block Arrows", _path(_quad_arrow))


# ── Equation shapes ─────────────────────────────────────────────────

def _eq_plus(r):
    return _cross(r, th=0.3)


def _eq_minus(r):
    h = r.height()
    th = h * 0.22
    cy = r.center().y()
    return _poly([(r.left(), cy - th / 2), (r.right(), cy - th / 2),
                  (r.right(), cy + th / 2), (r.left(), cy + th / 2)])


def _eq_multiply(p, r):
    th = min(r.width(), r.height()) * 0.16
    p.save()
    p.translate(r.center())
    p.rotate(45)
    half = min(r.width(), r.height()) * 0.5
    bar_h = QRectF(-half, -th / 2, 2 * half, th)
    bar_v = QRectF(-th / 2, -half, th, 2 * half)
    path = QPainterPath()
    path.addRect(bar_h)
    path.addRect(bar_v)
    p.drawPath(path.simplified())
    p.restore()


def _eq_equal(r):
    h = r.height()
    th = h * 0.16
    cy = r.center().y()
    gap = h * 0.18
    path = QPainterPath()
    path.addRect(QRectF(r.left(), cy - gap - th, r.width(), th))
    path.addRect(QRectF(r.left(), cy + gap, r.width(), th))
    return path


def _eq_divide(p, r):
    cx, cy = r.center().x(), r.center().y()
    w, h = r.width(), r.height()
    th = h * 0.12
    p.drawRect(QRectF(r.left() + w * 0.1, cy - th / 2,
                      w * 0.8, th))
    dr = min(w, h) * 0.08
    p.drawEllipse(QPointF(cx, cy - h * 0.26), dr, dr)
    p.drawEllipse(QPointF(cx, cy + h * 0.26), dr, dr)


def _eq_not_equal(p, r):
    _path(_eq_equal)(p, r)
    p.save()
    p.translate(r.center())
    p.rotate(20)
    half = min(r.width(), r.height()) * 0.55
    th = r.height() * 0.1
    p.drawRect(QRectF(-th / 2, -half, th, 2 * half))
    p.restore()


_reg("eq_plus", "Plus", "Equation Shapes", _path(_eq_plus))
_reg("eq_minus", "Minus", "Equation Shapes", _path(_eq_minus))
_reg("eq_multiply", "Multiply", "Equation Shapes", _eq_multiply)
_reg("eq_divide", "Division", "Equation Shapes", _eq_divide)
_reg("eq_equal", "Equal", "Equation Shapes", _path(_eq_equal))
_reg("eq_not_equal", "Not Equal", "Equation Shapes", _eq_not_equal)


# ── Flowchart ───────────────────────────────────────────────────────

def _fc_terminator(r):
    path = QPainterPath()
    rad = r.height() / 2
    path.addRoundedRect(r, rad, rad)
    return path


def _fc_document(r):
    w, h = r.width(), r.height()
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    wave = h * 0.12
    path = QPainterPath()
    path.moveTo(l, t)
    path.lineTo(rt, t)
    path.lineTo(rt, b - wave)
    path.cubicTo(rt - w * 0.25, b - wave * 3, l + w * 0.25, b + wave,
                 l, b - wave)
    path.closeSubpath()
    return path


def _fc_predefined(p, r):
    p.drawRect(r)
    d = r.width() * 0.12
    p.drawLine(QPointF(r.left() + d, r.top()),
               QPointF(r.left() + d, r.bottom()))
    p.drawLine(QPointF(r.right() - d, r.top()),
               QPointF(r.right() - d, r.bottom()))


def _fc_internal(p, r):
    p.drawRect(r)
    d = min(r.width(), r.height()) * 0.22
    p.drawLine(QPointF(r.left() + d, r.top()),
               QPointF(r.left() + d, r.bottom()))
    p.drawLine(QPointF(r.left(), r.top() + d),
               QPointF(r.right(), r.top() + d))


def _fc_manual_input(r):
    return _poly([(r.left(), r.top() + r.height() * 0.25),
                  (r.right(), r.top()), (r.right(), r.bottom()),
                  (r.left(), r.bottom())])


def _fc_manual_op(r):
    o = r.width() * 0.18
    return _poly([(r.left(), r.top()), (r.right(), r.top()),
                  (r.right() - o, r.bottom()), (r.left() + o, r.bottom())])


def _fc_delay(r):
    path = QPainterPath()
    rad = r.height() / 2
    path.moveTo(r.left(), r.top())
    path.lineTo(r.right() - rad, r.top())
    path.arcTo(QRectF(r.right() - 2 * rad, r.top(), 2 * rad, r.height()),
               90, -180)
    path.lineTo(r.left(), r.bottom())
    path.closeSubpath()
    return path


def _fc_display(r):
    w = r.width()
    path = QPainterPath()
    path.moveTo(r.left() + w * 0.12, r.top())
    path.lineTo(r.right() - w * 0.16, r.top())
    path.quadTo(r.right(), r.center().y(), r.right() - w * 0.16, r.bottom())
    path.lineTo(r.left() + w * 0.12, r.bottom())
    path.quadTo(r.left(), r.center().y(), r.left() + w * 0.12, r.top())
    path.closeSubpath()
    return path


def _fc_card(r):
    s = min(r.width(), r.height()) * 0.25
    return _poly([(r.left() + s, r.top()), (r.right(), r.top()),
                  (r.right(), r.bottom()), (r.left(), r.bottom()),
                  (r.left(), r.top() + s)])


def _fc_merge(r):
    return _poly([(r.left(), r.top()), (r.right(), r.top()),
                  (r.center().x(), r.bottom())])


def _fc_extract(r):
    return _poly([(r.center().x(), r.top()),
                  (r.right(), r.bottom()), (r.left(), r.bottom())])


def _fc_or(p, r):
    p.drawEllipse(r)
    p.drawLine(QPointF(r.center().x(), r.top()),
               QPointF(r.center().x(), r.bottom()))
    p.drawLine(QPointF(r.left(), r.center().y()),
               QPointF(r.right(), r.center().y()))


def _fc_summing(p, r):
    p.drawEllipse(r)
    d = (1 - 0.7071) / 2
    rr = r.adjusted(r.width() * d, r.height() * d,
                    -r.width() * d, -r.height() * d)
    p.drawLine(rr.topLeft(), rr.bottomRight())
    p.drawLine(rr.topRight(), rr.bottomLeft())


def _fc_database(p, r):
    _can(p, r)


_reg("fc_process", "Process", "Flowchart", _path(_rect_path))
_reg("fc_alt_process", "Alternate Process", "Flowchart",
     _path(_rounded_path))
_reg("fc_decision", "Decision", "Flowchart", _path(_diamond))
_reg("fc_terminator", "Terminator", "Flowchart", _path(_fc_terminator))
_reg("fc_data", "Data", "Flowchart", _path(_parallelogram))
_reg("fc_predefined", "Predefined Process", "Flowchart", _fc_predefined)
_reg("fc_internal", "Internal Storage", "Flowchart", _fc_internal)
_reg("fc_document", "Document", "Flowchart", _path(_fc_document))
_reg("fc_manual_input", "Manual Input", "Flowchart", _path(_fc_manual_input))
_reg("fc_manual_op", "Manual Operation", "Flowchart", _path(_fc_manual_op))
_reg("fc_preparation", "Preparation", "Flowchart",
     _path(lambda r: _regular(QRectF(r), 6, 0)))
_reg("fc_connector", "Connector", "Flowchart", _path(_oval_path))
_reg("fc_delay", "Delay", "Flowchart", _path(_fc_delay))
_reg("fc_display", "Display", "Flowchart", _path(_fc_display))
_reg("fc_card", "Card", "Flowchart", _path(_fc_card))
_reg("fc_merge", "Merge", "Flowchart", _path(_fc_merge))
_reg("fc_extract", "Extract", "Flowchart", _path(_fc_extract))
_reg("fc_or", "Or", "Flowchart", _fc_or)
_reg("fc_summing", "Summing Junction", "Flowchart", _fc_summing)
_reg("fc_database", "Database", "Flowchart", _fc_database)


# ── Stars and banners ───────────────────────────────────────────────

def _explosion(r):
    cx, cy = r.center().x(), r.center().y()
    rx, ry = r.width() / 2, r.height() / 2
    pts = []
    n = 12
    for i in range(2 * n):
        rr = 1.0 if i % 2 == 0 else 0.55
        jitter = 0.9 if (i % 4) else 1.0
        a = math.pi * i / n
        pts.append((cx + rx * rr * jitter * math.cos(a),
                    cy + ry * rr * jitter * math.sin(a)))
    return _poly(pts)


def _wave(r):
    w, h = r.width(), r.height()
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    amp = h * 0.12
    path = QPainterPath()
    path.moveTo(l, t + amp)
    path.cubicTo(l + w * 0.25, t - amp, l + w * 0.75, t + amp * 3,
                 rt, t + amp)
    path.lineTo(rt, b - amp)
    path.cubicTo(l + w * 0.75, b + amp, l + w * 0.25, b - amp * 3,
                 l, b - amp)
    path.closeSubpath()
    return path


def _ribbon(r):
    w, h = r.width(), r.height()
    l, t, rt, b = r.left(), r.top(), r.right(), r.bottom()
    tail = w * 0.16
    notch = w * 0.07
    yt = t + h * 0.18
    yb = b - h * 0.18
    return _poly([(l, t + h * 0.05), (l + tail, t + h * 0.05),
                  (l + tail, yt), (rt - tail, yt), (rt - tail, t + h * 0.05),
                  (rt, t + h * 0.05), (rt - notch, b * 0 + (yt + yb) / 2),
                  (rt, b - h * 0.05), (rt - tail, b - h * 0.05),
                  (rt - tail, yb), (l + tail, yb), (l + tail, b - h * 0.05),
                  (l, b - h * 0.05), (l + notch, (yt + yb) / 2)])


def _vscroll(p, r):
    w = r.width()
    curl = w * 0.18
    body = QRectF(r.left() + curl, r.top(), r.width() - curl, r.height())
    p.drawRect(body)
    p.drawEllipse(QRectF(r.left(), r.top(), curl * 2, curl * 2 * 0.7))


def _hscroll(p, r):
    h = r.height()
    curl = h * 0.18
    body = QRectF(r.left(), r.top() + curl, r.width(), r.height() - curl)
    p.drawRect(body)
    p.drawEllipse(QRectF(r.left(), r.top(), curl * 2 * 0.7, curl * 2))


for _n in (4, 5, 6, 7, 8, 10, 12, 16, 24, 32):
    _inner = 0.5 if _n <= 6 else (0.62 if _n <= 12 else 0.78)
    _reg(f"star{_n}", f"{_n}-Point Star", "Stars and Banners",
         _path(lambda r, n=_n, ir=_inner: _star_path(r, n, ir)))
_reg("explosion", "Explosion", "Stars and Banners", _path(_explosion))
_reg("wave", "Wave", "Stars and Banners", _path(_wave))
_reg("ribbon", "Ribbon", "Stars and Banners", _path(_ribbon))
_reg("vscroll", "Vertical Scroll", "Stars and Banners", _vscroll)
_reg("hscroll", "Horizontal Scroll", "Stars and Banners", _hscroll)


# ── Callouts ────────────────────────────────────────────────────────

def _callout_rect(p, r):
    body = QRectF(r.left(), r.top(), r.width(), r.height() * 0.72)
    p.drawRect(body)
    tail = _poly([(r.left() + r.width() * 0.2, body.bottom()),
                  (r.left() + r.width() * 0.4, body.bottom()),
                  (r.left() + r.width() * 0.15, r.bottom())])
    p.drawPath(tail)


def _callout_rounded(p, r):
    body = QRectF(r.left(), r.top(), r.width(), r.height() * 0.72)
    rad = min(body.width(), body.height()) * 0.18
    path = QPainterPath()
    path.addRoundedRect(body, rad, rad)
    p.drawPath(path)
    tail = _poly([(r.left() + r.width() * 0.2, body.bottom() - 1),
                  (r.left() + r.width() * 0.4, body.bottom() - 1),
                  (r.left() + r.width() * 0.15, r.bottom())])
    p.drawPath(tail)


def _callout_oval(p, r):
    body = QRectF(r.left(), r.top(), r.width(), r.height() * 0.72)
    p.drawEllipse(body)
    cx = r.left() + r.width() * 0.3
    tail = _poly([(cx, body.center().y() + body.height() * 0.3),
                  (cx + r.width() * 0.18, body.bottom()),
                  (r.left() + r.width() * 0.18, r.bottom())])
    p.drawPath(tail)


def _callout_cloud(p, r):
    body = QRectF(r.left(), r.top(), r.width(), r.height() * 0.72)
    _cloud(p, body)
    rr = min(r.width(), r.height()) * 0.05
    p.drawEllipse(QPointF(r.left() + r.width() * 0.28, r.bottom() - rr * 4),
                  rr, rr)
    p.drawEllipse(QPointF(r.left() + r.width() * 0.2, r.bottom() - rr),
                  rr * 0.6, rr * 0.6)


_reg("callout_rect", "Rectangular Callout", "Callouts", _callout_rect)
_reg("callout_rounded", "Rounded Callout", "Callouts", _callout_rounded)
_reg("callout_oval", "Oval Callout", "Callouts", _callout_oval)
_reg("callout_cloud", "Cloud Callout", "Callouts", _callout_cloud)


# ── Public API ──────────────────────────────────────────────────────

def draw_shape(painter, rect: QRectF, key: str):
    """Render *key* into *rect* using the painter's pen/brush."""
    spec = SHAPES.get(key) or SHAPES["rectangle"]
    spec["fn"](painter, rect)


def is_line(key: str) -> bool:
    return bool(SHAPES.get(key, {}).get("line", False))


def label_for(key: str) -> str:
    return SHAPES.get(key, {}).get("label", key)


def shapes_in_category(cat: str):
    return [(k, v["label"]) for k, v in SHAPES.items() if v["cat"] == cat]


def all_keys():
    return list(SHAPES.keys())
