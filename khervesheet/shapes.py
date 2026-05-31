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

from PyQt5.QtCore import Qt, QRect, QRectF, QPoint, QPointF, QTimer
from PyQt5.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont, QPalette,
    QTextDocument, QTextOption, QTextCursor, QTextCharFormat,
    QTextBlockFormat, QAbstractTextDocumentLayout,
)
from PyQt5.QtWidgets import (
    QWidget, QMenu, QDialog, QHBoxLayout, QFormLayout,
    QPushButton, QSpinBox, QDialogButtonBox, QColorDialog,
    QCheckBox, QTextEdit, QUndoCommand,
)

from . import shape_defs
from . import overlay

_HANDLE = 6
_PAD = 3        # inset so outline + handles stay inside the widget
_ROT_OFFSET = 18  # distance of rotation handle above the top edge
_ROT_R = 5      # rotation-handle radius


def _is_closed(shape_type) -> bool:
    """True for shapes that enclose a region (and so can carry a fill)."""
    return not shape_defs.is_line(shape_type)


# Cross-sheet clipboard for copy/paste of a shape (a to_dict() payload).
_shape_clipboard = None


# Backward-compatible export: the full gallery now lives in shape_defs.
SHAPE_LABELS = [(k, v["label"]) for k, v in shape_defs.SHAPES.items()]


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
        self._fill_color = "#FFFFCC" if _is_closed(shape_type) else None
        self._outline_color = "#000000"
        self._outline_width = 1.0
        self._text = ""        # plain-text fallback / for empty checks
        self._html = ""        # rich text (per-run bold/italic/align)
        self._text_color = "#000000"
        self._font_size = 9
        self._bold = False
        self._italic = False
        self._underline = False
        self._text_align = int(Qt.AlignLeft)   # default horizontal flag
        self._rotation = 0.0
        self._selected = False
        self._group_id = None
        self._group_drag = None
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
            "html": self._html,
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
        self._html = d.get("html", self._html)
        self._text_color = d.get("text_color", self._text_color)
        self._font_size = d.get("font_size", self._font_size)
        self._bold = bool(d.get("bold", self._bold))
        self._italic = bool(d.get("italic", self._italic))
        self._underline = bool(d.get("underline", self._underline))
        self._text_align = int(d.get("text_align", self._text_align))
        self._rotation = float(d.get("rotation", self._rotation))
        self.update()

    # ── Painting ──────────────────────────────────────────────────────

    def _content_rect(self):
        """Rect the shape is drawn into.  When rotated, it is shrunk so
        the rotated shape's bounding box still fits inside the widget and
        nothing (e.g. an arrowhead) gets clipped at the edges."""
        inner = QRectF(self.rect().adjusted(_PAD, _PAD, -_PAD, -_PAD))
        if not self._rotation:
            return inner
        import math
        th = math.radians(self._rotation)
        cs, sn = abs(math.cos(th)), abs(math.sin(th))
        w, h = inner.width(), inner.height()
        bw = w * cs + h * sn
        bh = w * sn + h * cs
        f = min(w / bw if bw else 1.0, h / bh if bh else 1.0)
        if f >= 1.0:
            return inner
        nw, nh = w * f, h * f
        c = inner.center()
        return QRectF(c.x() - nw / 2, c.y() - nh / 2, nw, nh)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        inner = self._content_rect()

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
        st = self._shape_type
        closed = _is_closed(st)
        if self._fill_color and closed:
            p.setBrush(QBrush(QColor(self._fill_color)))
        else:
            p.setBrush(Qt.NoBrush)

        shape_defs.draw_shape(p, inner, st)

        # Text (all shapes), hidden while the inline editor is open.
        if (self._html or self._text) and self._inline_editor is None:
            self._draw_text(p, inner.adjusted(4, 4, -4, -4), closed)
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

    def _build_document(self, width):
        """A QTextDocument holding the shape's (rich) text, used for both
        painting and as the model the inline editor edits."""
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setDefaultFont(self._text_font())
        opt = QTextOption(Qt.Alignment(
            int(self._text_align) & int(Qt.AlignHorizontal_Mask)))
        opt.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        doc.setDefaultTextOption(opt)
        if width > 0:
            doc.setTextWidth(width)
        if self._html:
            doc.setHtml(self._html)
        else:
            doc.setPlainText(self._text)
        return doc

    def _draw_text(self, p, rect, closed):
        doc = self._build_document(rect.width())
        # Vertical placement: closed shapes anchor text at the top,
        # open shapes (lines/arrows) centre it.
        th = doc.size().height()
        ty = rect.top() if closed else rect.center().y() - th / 2
        p.save()
        p.translate(rect.left(), ty)
        ctx = QAbstractTextDocumentLayout.PaintContext()
        ctx.palette.setColor(QPalette.Text, QColor(self._text_color))
        ctx.clip = QRectF(0, 0, rect.width(), max(rect.height(), th))
        doc.documentLayout().draw(p, ctx)
        p.restore()

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
        overlay.handle_select_on_press(
            self, bool(ev.modifiers() & Qt.ControlModifier))
        self.update()
        if self._on_rot_handle(ev.pos()):
            self._rotating = True
            self._rot_before = self._style_dict()
            self._rot_start_angle = self._angle_to(ev.pos())
            self._rot_start_value = self._rotation
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
            self._group_drag = overlay.begin_group_drag(self)

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
            if self._group_drag and len(self._group_drag) > 1:
                overlay.drag_group(self._group_drag, delta)
            else:
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
        self._group_drag = None
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
        overlay.add_arrange_actions(menu, self)
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
        ed.setAcceptRichText(True)
        ed.setStyleSheet(
            "QTextEdit { background: rgba(255,255,255,210);"
            " border: 1px solid #3078c6; }")
        ed.setFont(self._text_font())
        if self._html:
            ed.setHtml(self._html)
        else:
            ed.setPlainText(self._text)
            ed.setTextColor(QColor(self._text_color))
            ed.setAlignment(Qt.Alignment(
                int(self._text_align) & int(Qt.AlignHorizontal_Mask)))
        m = _PAD + 2
        ed.setGeometry(m, m, max(20, self.width() - 2 * m),
                       max(16, self.height() - 2 * m))
        self._inline_editor = ed
        self.update()
        ed.show()
        ed.setFocus()

    @staticmethod
    def _char_format(bold, italic, underline):
        fmt = QTextCharFormat()
        if bold is not None:
            fmt.setFontWeight(QFont.Bold if bold else QFont.Normal)
        if italic is not None:
            fmt.setFontItalic(bool(italic))
        if underline is not None:
            fmt.setFontUnderline(bool(underline))
        return fmt

    def set_text_format(self, *, bold=None, italic=None, underline=None,
                        align=None, label="Format Shape"):
        """Apply text formatting from the toolbar — undoable.

        While the inline editor is open the change applies to the current
        selection (or to subsequent typing), so different runs of text can
        be bold/italic/underlined and different paragraphs aligned
        independently.  When not editing it applies to the whole shape."""
        before = self._style_dict()
        ed = self._inline_editor
        if ed is not None:
            if bold is not None or italic is not None or underline is not None:
                fmt = self._char_format(bold, italic, underline)
                cur = ed.textCursor()
                if cur.hasSelection():
                    cur.mergeCharFormat(fmt)
                ed.mergeCurrentCharFormat(fmt)
            if align is not None:
                ed.setAlignment(Qt.Alignment(
                    int(align) & int(Qt.AlignHorizontal_Mask)))
            ed.setFocus()
            self._html = ed.toHtml()
            self.update()
            self._push_change(before, label)
            return

        # Not editing — apply to the whole shape.
        if bold is not None:
            self._bold = bool(bold)
        if italic is not None:
            self._italic = bool(italic)
        if underline is not None:
            self._underline = bool(underline)
        if align is not None:
            self._text_align = int(align) & int(Qt.AlignHorizontal_Mask)
        if self._html:
            doc = self._build_document(0)
            cur = QTextCursor(doc)
            cur.select(QTextCursor.Document)
            if bold is not None or italic is not None or underline is not None:
                cur.mergeCharFormat(
                    self._char_format(bold, italic, underline))
            if align is not None:
                bf = QTextBlockFormat()
                bf.setAlignment(Qt.Alignment(self._text_align))
                cur.mergeBlockFormat(bf)
            self._html = doc.toHtml()
        self.update()
        self._push_change(before, label)

    def _end_inline_edit(self, editor, text, commit):
        """Tear down the inline editor (called deferred, never mid-event)."""
        if self._inline_editor is editor:
            self._inline_editor = None
        if commit:
            plain = editor.toPlainText()
            self._text = plain
            self._html = editor.toHtml() if plain.strip() else ""
        editor.hide()
        editor.setParent(None)
        editor.deleteLater()
        if commit:
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
            "group_id": self._group_id,
        })
        return d

    @classmethod
    def from_dict(cls, d, parent=None):
        sh = cls(d.get("shape_type", "rectangle"), parent)
        sh._apply_style(d)
        sh.move(int(d.get("pos_x", 40)), int(d.get("pos_y", 40)))
        sh.resize(int(d.get("width", 160)), int(d.get("height", 90)))
        sh._group_id = d.get("group_id")
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
        closed = _is_closed(shape._shape_type)
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
