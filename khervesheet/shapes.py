"""Embedded shapes — movable/resizable vector shapes overlaid on grid.

Shapes (rectangle, rounded rectangle, oval, triangle, line, arrow) float
as child widgets of the sheet's table viewport, like embedded charts and
images.  They can be dragged, resized, given a fill/outline via a
properties dialog, and (for closed shapes) carry editable text.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, QRect, QPoint, QPointF, QTimer
from PyQt5.QtGui import (
    QPainter, QPen, QColor, QBrush, QPolygonF, QFont,
)
from PyQt5.QtWidgets import (
    QWidget, QMenu, QDialog, QHBoxLayout, QFormLayout,
    QPushButton, QSpinBox, QDialogButtonBox, QColorDialog,
    QCheckBox, QTextEdit, QUndoCommand,
)

_HANDLE = 6
_PAD = 3        # inset so outline + handles stay inside the widget
_ROT_OFFSET = 18  # distance of rotation handle above the top edge
_ROT_R = 5      # rotation-handle radius

# Shape types that are closed regions (can have a fill).
_CLOSED = {"rectangle", "rounded_rect", "oval", "triangle"}

SHAPE_LABELS = [
    ("rectangle", "Rectangle"),
    ("rounded_rect", "Rounded Rectangle"),
    ("oval", "Oval / Ellipse"),
    ("triangle", "Triangle"),
    ("line", "Line"),
    ("arrow", "Arrow"),
]


# ── Helpers to reach the owning sheet / undo stack ─────────────────────

def _find_sheet_widget(viewport_widget):
    sw = viewport_widget
    while sw and not hasattr(sw, "_shapes"):
        p = sw.parent()
        if p is sw:
            break
        sw = p
    return sw if sw and hasattr(sw, "_shapes") else None


def _find_undo_stack(viewport_widget):
    sw = _find_sheet_widget(viewport_widget)
    return getattr(sw, "_undo_stack", None) if sw else None


# ── Undo commands ──────────────────────────────────────────────────────

class InsertShapeCmd(QUndoCommand):
    def __init__(self, sheet, shape, label="Insert Shape"):
        super().__init__(label)
        self._sheet = sheet
        self._shape = shape

    def undo(self):
        if self._shape in self._sheet._shapes:
            self._sheet._shapes.remove(self._shape)
        self._shape.hide()

    def redo(self):
        if not getattr(self, "_first", False):
            self._first = True
            return
        if self._shape not in self._sheet._shapes:
            self._sheet._shapes.append(self._shape)
        self._shape.setParent(self._sheet.table.viewport())
        self._shape.show()


class DeleteShapeCmd(QUndoCommand):
    def __init__(self, sheet, shape):
        super().__init__("Delete Shape")
        self._sheet = sheet
        self._shape = shape
        self._pos = shape.pos()
        self._size = shape.size()

    def undo(self):
        self._shape.setParent(self._sheet.table.viewport())
        self._shape.move(self._pos)
        self._shape.resize(self._size)
        if self._shape not in self._sheet._shapes:
            self._sheet._shapes.append(self._shape)
        self._shape.show()

    def redo(self):
        if not getattr(self, "_first", False):
            self._first = True
            return
        if self._shape in self._sheet._shapes:
            self._sheet._shapes.remove(self._shape)
        self._shape.hide()


class ShapeChangeCmd(QUndoCommand):
    """Undoable style/text change captured as before/after dicts."""

    def __init__(self, shape, before, after, label="Edit Shape"):
        super().__init__(label)
        self._shape = shape
        self._before = before
        self._after = after

    def undo(self):
        self._shape._apply_style(self._before)

    def redo(self):
        if not getattr(self, "_first", False):
            self._first = True
            return
        self._shape._apply_style(self._after)


# ── Inline text editor ─────────────────────────────────────────────────

class _InlineTextEdit(QTextEdit):
    """In-place editor shown over a shape.  Commits on focus-out or
    Enter, cancels on Esc.  Teardown is always deferred via a timer so
    the editor is never deleted while Qt is mid event-dispatch (which
    can crash)."""

    def __init__(self, shape):
        super().__init__(shape)
        self._shape = shape
        self._done = False

    def focusOutEvent(self, ev):
        super().focusOutEvent(ev)
        self._finish(commit=True)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self._finish(commit=False)
            return
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter) and not (
                ev.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier)):
            self._finish(commit=True)
            return
        super().keyPressEvent(ev)

    def _finish(self, commit):
        if self._done:
            return
        self._done = True
        shape = self._shape
        text = self.toPlainText()
        self.clearFocus()
        QTimer.singleShot(
            0, lambda: shape._end_inline_edit(self, text, commit))


# ── The shape widget ───────────────────────────────────────────────────

class EmbeddedShape(QWidget):
    """A vector shape that lives as a child of the grid viewport."""

    def __init__(self, shape_type="rectangle", parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._shape_type = shape_type
        self._fill_color = "#FFFFCC" if shape_type in _CLOSED else None
        self._outline_color = "#000000"
        self._outline_width = 1.0
        self._text = ""
        self._text_color = "#000000"
        self._font_size = 9
        self._bold = False
        self._italic = False
        self._underline = False
        self._text_align = int(Qt.AlignLeft)   # horizontal flag
        self._rotation = 0.0
        self._selected = False
        self._inline_editor = None

        # Dragging / resizing / rotating state.
        self._drag_origin = None
        self._drag_widget_pos = None
        self._resizing = False
        self._resize_edge = None
        self._rotating = False
        self._rot_start_angle = 0.0
        self._rot_start_value = 0.0

        self.setMinimumSize(24, 16)
        self.resize(160, 90)
        self.show()

    # ── Style snapshot (for undo + persistence) ───────────────────────

    def _style_dict(self):
        return {
            "shape_type": self._shape_type,
            "fill_color": self._fill_color,
            "outline_color": self._outline_color,
            "outline_width": self._outline_width,
            "text": self._text,
            "text_color": self._text_color,
            "font_size": self._font_size,
            "bold": self._bold,
            "italic": self._italic,
            "underline": self._underline,
            "text_align": self._text_align,
            "rotation": self._rotation,
        }

    def _apply_style(self, d):
        self._shape_type = d.get("shape_type", self._shape_type)
        self._fill_color = d.get("fill_color", self._fill_color)
        self._outline_color = d.get("outline_color", self._outline_color)
        self._outline_width = d.get("outline_width", self._outline_width)
        self._text = d.get("text", self._text)
        self._text_color = d.get("text_color", self._text_color)
        self._font_size = d.get("font_size", self._font_size)
        self._bold = bool(d.get("bold", self._bold))
        self._italic = bool(d.get("italic", self._italic))
        self._underline = bool(d.get("underline", self._underline))
        self._text_align = int(d.get("text_align", self._text_align))
        self._rotation = float(d.get("rotation", self._rotation))
        self.update()

    # ── Painting ──────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        inner = self.rect().adjusted(_PAD, _PAD, -_PAD, -_PAD)

        # Apply rotation around the widget centre for the shape content.
        p.save()
        if self._rotation:
            c = self.rect().center()
            p.translate(c)
            p.rotate(self._rotation)
            p.translate(-c)

        pen = QPen(QColor(self._outline_color),
                   max(0.0, float(self._outline_width)))
        pen.setJoinStyle(Qt.MiterJoin)
        p.setPen(pen if self._outline_width > 0 else Qt.NoPen)
        if self._fill_color and self._shape_type in _CLOSED:
            p.setBrush(QBrush(QColor(self._fill_color)))
        else:
            p.setBrush(Qt.NoBrush)

        st = self._shape_type
        if st == "rectangle":
            p.drawRect(inner)
        elif st == "rounded_rect":
            p.drawRoundedRect(inner, 12, 12)
        elif st == "oval":
            p.drawEllipse(inner)
        elif st == "triangle":
            poly = QPolygonF([
                QPointF(inner.center().x(), inner.top()),
                QPointF(inner.left(), inner.bottom()),
                QPointF(inner.right(), inner.bottom()),
            ])
            p.drawPolygon(poly)
        elif st in ("line", "arrow"):
            p.setBrush(Qt.NoBrush)
            # Horizontal through the vertical centre (rotation gives angle).
            yc = inner.center().y()
            a = QPointF(inner.left(), yc)
            b = QPointF(inner.right(), yc)
            p.drawLine(a, b)
            if st == "arrow":
                self._draw_arrowhead(p, a, b)

        # Text (all shapes), hidden while the inline editor is open.
        if self._text and self._inline_editor is None:
            p.setPen(QPen(QColor(self._text_color)))
            p.setFont(self._text_font())
            valign = Qt.AlignTop if st in _CLOSED else Qt.AlignVCenter
            align = (int(self._text_align) & int(Qt.AlignHorizontal_Mask)) \
                | int(valign)
            flags = int(Qt.TextWordWrap) | align
            p.drawText(inner.adjusted(4, 4, -4, -4), flags, self._text)
        p.restore()

        # Selection border + handles (axis-aligned, never rotated).
        if self._selected:
            sp = QPen(QColor("#3078c6"), 1, Qt.DashLine)
            p.setPen(sp)
            p.setBrush(Qt.NoBrush)
            p.drawRect(self.rect().adjusted(0, 0, -1, -1))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#3078c6"))
            for hx, hy in self._handle_positions():
                p.drawRect(hx - _HANDLE // 2, hy - _HANDLE // 2,
                           _HANDLE, _HANDLE)
            # Rotation handle: green circle just inside the top-centre.
            rx, ry = self._rot_handle_pos()
            p.setPen(QPen(QColor("#ffffff"), 1))
            p.setBrush(QColor("#2d8a4e"))
            p.drawEllipse(QPoint(rx, ry), _ROT_R, _ROT_R)
        p.end()

    def _rot_handle_pos(self):
        return self.rect().width() // 2, _PAD + _ROT_R

    def _text_font(self):
        f = QFont()
        f.setPointSize(int(self._font_size))
        f.setBold(self._bold)
        f.setItalic(self._italic)
        f.setUnderline(self._underline)
        return f

    def _draw_arrowhead(self, p, a, b):
        import math
        ang = math.atan2(b.y() - a.y(), b.x() - a.x())
        size = 10 + self._outline_width * 2
        left = QPointF(b.x() - size * math.cos(ang - math.pi / 7),
                       b.y() - size * math.sin(ang - math.pi / 7))
        right = QPointF(b.x() - size * math.cos(ang + math.pi / 7),
                        b.y() - size * math.sin(ang + math.pi / 7))
        p.setBrush(QColor(self._outline_color))
        p.drawPolygon(QPolygonF([b, left, right]))

    def _handle_positions(self):
        r = self.rect()
        mx, my = r.width() // 2, r.height() // 2
        return [(0, 0), (mx, 0), (r.width(), 0),
                (0, my), (r.width(), my),
                (0, r.height()), (mx, r.height()),
                (r.width(), r.height())]

    # ── Mouse interaction ─────────────────────────────────────────────

    def _edge_at(self, pos):
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
        return {
            "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
            "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor,
            "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
            "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
        }.get(edge, Qt.ArrowCursor)

    def _on_rot_handle(self, pos):
        rx, ry = self._rot_handle_pos()
        return (pos.x() - rx) ** 2 + (pos.y() - ry) ** 2 \
            <= (_ROT_R + 3) ** 2

    def _angle_to(self, pos):
        import math
        c = self.rect().center()
        return math.degrees(math.atan2(pos.y() - c.y(),
                                       pos.x() - c.x()))

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        self._deselect_siblings()
        self._selected = True
        self.update()
        if self._on_rot_handle(ev.pos()):
            self._rotating = True
            self._rot_before = self._style_dict()
            self._rot_start_angle = self._angle_to(ev.pos())
            self._rot_start_value = self._rotation
            self.raise_()
            return
        edge = self._edge_at(ev.pos())
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
        if self._rotating:
            ang = self._angle_to(ev.pos())
            new = self._rot_start_value + (ang - self._rot_start_angle)
            if ev.modifiers() & Qt.ShiftModifier:
                new = round(new / 15.0) * 15.0
            self._rotation = new % 360.0
            self.update()
        elif self._resizing and self._drag_origin:
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
            if self._selected and self._on_rot_handle(ev.pos()):
                self.setCursor(Qt.CrossCursor)
            else:
                edge = self._edge_at(ev.pos()) if self._selected else ""
                self.setCursor(self._cursor_for_edge(edge) if edge
                               else Qt.SizeAllCursor)

    def mouseReleaseEvent(self, ev):
        if self._rotating:
            self._rotating = False
            self._push_change(getattr(self, "_rot_before",
                                      self._style_dict()), "Rotate Shape")
        self._drag_origin = None
        self._drag_widget_pos = None
        self._resizing = False
        self._resize_edge = None

    def mouseDoubleClickEvent(self, ev):
        self._begin_inline_edit()

    def _deselect_siblings(self):
        sw = _find_sheet_widget(self.parent())
        if not sw:
            return
        for s in getattr(sw, "_shapes", []):
            if s is not self and getattr(s, "_selected", False):
                s._selected = False
                s.update()

    def contextMenuEvent(self, ev):
        menu = QMenu(self)
        menu.addAction("Properties…", self._open_properties)
        menu.addAction("Edit Text", self._begin_inline_edit)
        menu.addSeparator()
        menu.addAction("Bring to Front", self.raise_)
        menu.addAction("Send to Back", self.lower)
        menu.addSeparator()
        menu.addAction("Delete", self._delete)
        menu.exec_(ev.globalPos())

    # ── Editing ───────────────────────────────────────────────────────

    def _begin_inline_edit(self):
        """Edit the label directly inside the shape (no dialog)."""
        if self._inline_editor is not None:
            self._inline_editor.setFocus()
            return
        self._edit_before = self._style_dict()
        ed = _InlineTextEdit(self)
        ed.setPlainText(self._text)
        ed.setStyleSheet(
            "QTextEdit { background: rgba(255,255,255,210);"
            " border: 1px solid #3078c6; }")
        ed.setFont(self._text_font())
        ed.setTextColor(QColor(self._text_color))
        ed.setAlignment(Qt.Alignment(
            (int(self._text_align) & int(Qt.AlignHorizontal_Mask))
            | int(Qt.AlignTop)))
        m = _PAD + 2
        ed.setGeometry(m, m, max(20, self.width() - 2 * m),
                       max(16, self.height() - 2 * m))
        self._inline_editor = ed
        self.update()
        ed.show()
        ed.setFocus()

    def set_text_format(self, *, bold=None, italic=None, underline=None,
                        align=None, label="Format Shape"):
        """Apply text formatting (used by the toolbar) — undoable."""
        before = self._style_dict()
        if bold is not None:
            self._bold = bool(bold)
        if italic is not None:
            self._italic = bool(italic)
        if underline is not None:
            self._underline = bool(underline)
        if align is not None:
            self._text_align = int(align) & int(Qt.AlignHorizontal_Mask)
        # Live-update an open editor so the change is visible immediately.
        ed = self._inline_editor
        if ed is not None:
            cur = ed.textCursor()
            ed.selectAll()
            ed.setFont(self._text_font())
            if align is not None:
                ed.setAlignment(Qt.Alignment(
                    (int(self._text_align) & int(Qt.AlignHorizontal_Mask))
                    | int(Qt.AlignTop)))
            ed.setTextCursor(cur)
        self.update()
        self._push_change(before, label)

    def _end_inline_edit(self, editor, text, commit):
        """Tear down the inline editor (called deferred, never mid-event)."""
        if self._inline_editor is editor:
            self._inline_editor = None
        editor.hide()
        editor.setParent(None)
        editor.deleteLater()
        if commit:
            self._text = text
            self.update()
            self._push_change(getattr(self, "_edit_before",
                                      self._style_dict()), "Edit Text")
        else:
            self.update()

    def _open_properties(self):
        before = self._style_dict()
        dlg = ShapePropertiesDialog(self, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            dlg.apply_to(self)
            self.update()
            self._push_change(before, "Shape Properties")

    def _push_change(self, before, label):
        after = self._style_dict()
        if before == after:
            return
        stack = _find_undo_stack(self.parent())
        if stack is not None:
            stack.push(ShapeChangeCmd(self, before, after, label))

    def _delete(self):
        sw = _find_sheet_widget(self.parent())
        if sw:
            stack = getattr(sw, "_undo_stack", None)
            if stack is not None:
                if self in sw._shapes:
                    sw._shapes.remove(self)
                self.hide()
                stack.push(DeleteShapeCmd(sw, self))
                return
            if self in sw._shapes:
                sw._shapes.remove(self)
        self.deleteLater()

    # ── Serialisation ─────────────────────────────────────────────────

    def to_dict(self):
        d = self._style_dict()
        d.update({
            "pos_x": self.pos().x(), "pos_y": self.pos().y(),
            "width": self.width(), "height": self.height(),
        })
        return d

    @classmethod
    def from_dict(cls, d, parent=None):
        sh = cls(d.get("shape_type", "rectangle"), parent)
        sh._apply_style(d)
        sh.move(int(d.get("pos_x", 40)), int(d.get("pos_y", 40)))
        sh.resize(int(d.get("width", 160)), int(d.get("height", 90)))
        return sh


# ── Properties dialog ──────────────────────────────────────────────────

class _ColorButton(QPushButton):
    """A button showing a colour swatch; click opens a colour picker.
    A 'no colour' state is supported (shown as a diagonal red line)."""

    def __init__(self, color, allow_none=False, parent=None):
        super().__init__(parent)
        self._color = color
        self._allow_none = allow_none
        self.setFixedSize(60, 24)
        self.clicked.connect(self._pick)
        self._refresh()

    def _refresh(self):
        if self._color:
            self.setStyleSheet(
                f"background:{self._color}; border:1px solid #888;")
            self.setText("")
        else:
            self.setStyleSheet("border:1px solid #888;")
            self.setText("None")

    def _pick(self):
        initial = QColor(self._color) if self._color else QColor("#FFFFFF")
        col = QColorDialog.getColor(initial, self, "Select Colour")
        if col.isValid():
            self._color = col.name().upper()
            self._refresh()

    def color(self):
        return self._color

    def set_none(self):
        self._color = None
        self._refresh()


class ShapePropertiesDialog(QDialog):
    """Fill colour, outline colour/width, and text colour/size."""

    def __init__(self, shape, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Shape Properties")
        closed = shape._shape_type in _CLOSED
        form = QFormLayout(self)

        # Fill (closed shapes only).
        self._fill_btn = None
        self._no_fill = None
        if closed:
            row = QHBoxLayout()
            self._fill_btn = _ColorButton(shape._fill_color, parent=self)
            self._no_fill = QCheckBox("No fill")
            self._no_fill.setChecked(shape._fill_color is None)
            self._no_fill.toggled.connect(
                lambda on: self._fill_btn.setDisabled(on))
            self._fill_btn.setDisabled(shape._fill_color is None)
            row.addWidget(self._fill_btn)
            row.addWidget(self._no_fill)
            row.addStretch(1)
            form.addRow("Fill:", row)

        # Outline / line colour and width.
        self._outline_btn = _ColorButton(shape._outline_color, parent=self)
        form.addRow("Line colour:", self._outline_btn)
        self._width = QSpinBox()
        self._width.setRange(0, 20)
        self._width.setValue(int(shape._outline_width))
        form.addRow("Line width:", self._width)

        # Rotation (all shapes).
        self._rotation = QSpinBox()
        self._rotation.setRange(0, 359)
        self._rotation.setSuffix("°")
        self._rotation.setValue(int(shape._rotation) % 360)
        form.addRow("Rotation:", self._rotation)

        # Text (all shapes).
        self._text_btn = _ColorButton(shape._text_color, parent=self)
        form.addRow("Text colour:", self._text_btn)
        self._font_size = QSpinBox()
        self._font_size.setRange(6, 96)
        self._font_size.setValue(int(shape._font_size))
        form.addRow("Text size:", self._font_size)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def apply_to(self, shape):
        if self._fill_btn is not None:
            shape._fill_color = (None if self._no_fill.isChecked()
                                 else self._fill_btn.color())
        shape._outline_color = self._outline_btn.color() or "#000000"
        shape._outline_width = float(self._width.value())
        shape._rotation = float(self._rotation.value())
        shape._text_color = self._text_btn.color() or "#000000"
        shape._font_size = int(self._font_size.value())
