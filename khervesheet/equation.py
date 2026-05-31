"""Embedded equation — LaTeX maths rendered onto the grid.

Equations float as child widgets of the sheet's table viewport, just
like embedded charts, images and shapes.  The maths is rendered with
matplotlib's built-in *mathtext* engine, so no external LaTeX install is
required.  An editor dialog provides a live preview plus LaTeX-to-maths
and maths-to-LaTeX round-tripping, and a gallery offers ready-made
equations (quadratic formula, Pythagoras, Fourier series, ...).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import io

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.font_manager import FontProperties

from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor
from PyQt5.QtWidgets import (
    QWidget, QMenu, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QSpinBox, QPushButton, QDialogButtonBox,
    QColorDialog, QFormLayout, QApplication, QUndoCommand, QScrollArea,
    QToolButton, QWidgetAction, QSizePolicy,
)

from . import overlay

# Resize handle size in pixels.
_HANDLE = 6
# Supersampling DPI for crisp rendering.
_RENDER_DPI = 200

# Module-level clipboard for copy / cut / paste of equations.
_equation_clipboard = None


# ── Common equation presets (label → LaTeX body, no $ delimiters) ─────

EQUATION_PRESETS = [
    ("Area of Circle", r"A = \pi r^2"),
    ("Binomial Theorem",
     r"(x+a)^n = \sum_{k=0}^{n} \binom{n}{k} x^k a^{n-k}"),
    ("Expansion of a Sum",
     r"(1+x)^n = 1 + \frac{nx}{1!} + \frac{n(n-1)x^2}{2!} + \cdots"),
    ("Fourier Series",
     r"f(x) = a_0 + \sum_{n=1}^{\infty}\left(a_n\cos\frac{n\pi x}{L}"
     r" + b_n\sin\frac{n\pi x}{L}\right)"),
    ("Pythagorean Theorem", r"a^2 + b^2 = c^2"),
    ("Quadratic Formula", r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}"),
    ("Taylor Expansion",
     r"e^x = 1 + \frac{x}{1!} + \frac{x^2}{2!} + \frac{x^3}{3!}"
     r" + \cdots, \quad -\infty < x < \infty"),
    ("Trig Identity 1",
     r"\sin\alpha \pm \sin\beta = 2\sin\frac{1}{2}(\alpha\pm\beta)"
     r"\cos\frac{1}{2}(\alpha\mp\beta)"),
    ("Trig Identity 2",
     r"\cos\alpha + \cos\beta = 2\cos\frac{1}{2}(\alpha+\beta)"
     r"\cos\frac{1}{2}(\alpha-\beta)"),
]


# ── Rendering helpers ─────────────────────────────────────────────────

def render_latex(latex: str, fontsize: int = 20,
                 color: str = "#000000") -> QPixmap:
    """Render a LaTeX maths string to a transparent QPixmap.

    Uses matplotlib mathtext (no external LaTeX).  The string is wrapped
    in ``$...$`` automatically.  On a parse error a small red error
    pixmap is produced instead, so the caller always gets a valid pixmap.
    """
    body = (latex or "").strip()
    if not body:
        body = r"\ "
    expr = body if body.startswith("$") else "$" + body + "$"
    prop = FontProperties(size=fontsize)
    try:
        # Draw the expression onto a figure and let matplotlib crop to
        # the real ink extent with bbox_inches="tight".  This avoids the
        # edge clipping that happens when the mathtext-reported width
        # underestimates italic overhang or large delimiters.
        fig = Figure(figsize=(0.05, 0.05))
        FigureCanvasAgg(fig)
        fig.patch.set_alpha(0.0)
        fig.text(0.0, 0.0, expr, fontproperties=prop, color=color)
        buf = io.BytesIO()
        fig.savefig(buf, dpi=_RENDER_DPI, format="png", transparent=True,
                    bbox_inches="tight", pad_inches=0.05)
        pm = QPixmap()
        pm.loadFromData(buf.getvalue(), "PNG")
        return pm
    except Exception as exc:  # invalid LaTeX → visible error glyph
        return _error_pixmap(str(exc), fontsize)


def _error_pixmap(msg: str, fontsize: int) -> QPixmap:
    """Render an error placeholder pixmap."""
    from PyQt5.QtGui import QFont, QFontMetrics
    text = "  ⚠ invalid equation  "
    font = QFont()
    font.setPointSize(max(8, fontsize // 2))
    fm = QFontMetrics(font)
    w = fm.horizontalAdvance(text) + 8
    h = fm.height() + 8
    pm = QPixmap(w, h)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setFont(font)
    p.setPen(QColor("#c0392b"))
    p.drawText(pm.rect(), Qt.AlignCenter, text)
    p.end()
    return pm


# ── Undo commands ─────────────────────────────────────────────────────

def _find_sheet_widget(viewport_widget):
    """Walk up from viewport to the SheetWidget owning _equations."""
    sw = viewport_widget
    while sw and not hasattr(sw, "_equations"):
        p = sw.parent()
        if p is sw:
            break
        sw = p
    return sw if sw and hasattr(sw, "_equations") else None


def _find_undo_stack(viewport_widget):
    sw = _find_sheet_widget(viewport_widget)
    if sw:
        return getattr(sw, "_undo_stack", None)
    return None


class InsertEquationCmd(QUndoCommand):
    """Undoable insert / paste of an equation."""

    def __init__(self, sheet, equation, label="Insert Equation"):
        super().__init__(label)
        self._sheet = sheet
        self._eq = equation

    def undo(self):
        if self._eq in self._sheet._equations:
            self._sheet._equations.remove(self._eq)
        self._eq.hide()

    def redo(self):
        if not getattr(self, "_first", False):
            self._first = True
            return
        if self._eq not in self._sheet._equations:
            self._sheet._equations.append(self._eq)
        self._eq.setParent(self._sheet.table.viewport())
        self._eq.show()


class DeleteEquationCmd(QUndoCommand):
    """Undoable deletion of an equation."""

    def __init__(self, sheet, equation):
        super().__init__("Delete Equation")
        self._sheet = sheet
        self._eq = equation
        self._pos = equation.pos()
        self._size = equation.size()

    def undo(self):
        self._eq.setParent(self._sheet.table.viewport())
        self._eq.move(self._pos)
        self._eq.resize(self._size)
        if self._eq not in self._sheet._equations:
            self._sheet._equations.append(self._eq)
        self._eq.show()

    def redo(self):
        if not getattr(self, "_first", False):
            self._first = True
            return
        if self._eq in self._sheet._equations:
            self._sheet._equations.remove(self._eq)
        self._eq.hide()


class EditEquationCmd(QUndoCommand):
    """Undoable change of equation content / style."""

    def __init__(self, equation, old, new):
        super().__init__("Edit Equation")
        self._eq = equation
        self._old = old   # (latex, fontsize, color)
        self._new = new

    def undo(self):
        self._eq._apply_state(*self._old)

    def redo(self):
        if not getattr(self, "_first", False):
            self._first = True
            return
        self._eq._apply_state(*self._new)


# ── Embedded equation widget ──────────────────────────────────────────

class EmbeddedEquation(QWidget):
    """A LaTeX equation living as a child of the grid viewport."""

    def __init__(self, latex="E = mc^2", fontsize=20,
                 color="#000000", parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._latex = latex
        self._fontsize = fontsize
        self._color = color
        self._selected = False
        self._group_id = None
        self._group_drag = None
        self._pixmap = QPixmap()

        self._drag_origin = None
        self._drag_widget_pos = None
        self._resizing = False
        self._resize_edge = None

        self._render()
        self.setMinimumSize(24, 16)
        self.show()

    # ── Rendering ─────────────────────────────────────────────────────

    def _render(self):
        """Re-render the pixmap and size the widget to fit it."""
        self._pixmap = render_latex(self._latex, self._fontsize,
                                    self._color)
        pw = max(self._pixmap.width() // 2, 24)
        ph = max(self._pixmap.height() // 2, 16)
        self._aspect = pw / max(ph, 1)
        self.resize(pw + 8, ph + 8)
        self.update()

    def _apply_state(self, latex, fontsize, color):
        """Set content/style and re-render (used by undo)."""
        self._latex = latex
        self._fontsize = fontsize
        self._color = color
        self._pixmap = render_latex(latex, fontsize, color)
        self._aspect = max(self._pixmap.width(), 1) / \
            max(self._pixmap.height(), 1)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        target = self.rect().adjusted(4, 4, -4, -4)
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                target.size(), Qt.KeepAspectRatio,
                Qt.SmoothTransformation)
            x = target.x() + (target.width() - scaled.width()) // 2
            y = target.y() + (target.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
        if self._selected:
            pen = QPen(QColor("#3078c6"), 2, Qt.DashLine)
            p.setPen(pen)
            p.drawRect(self.rect().adjusted(0, 0, -1, -1))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#3078c6"))
            for hx, hy in self._handle_positions():
                p.drawRect(hx - _HANDLE // 2, hy - _HANDLE // 2,
                           _HANDLE, _HANDLE)
        p.end()

    def _handle_positions(self):
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
            overlay.handle_select_on_press(
                self, bool(ev.modifiers() & Qt.ControlModifier))
            self.update()
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
            # Keep aspect ratio (equations should not distort).
            ar = getattr(self, "_aspect", 0)
            if ar > 0:
                if "r" in e or "l" in e:
                    new_h = int(geo.width() / ar)
                    if "t" in e:
                        geo.setTop(geo.bottom() - new_h)
                    else:
                        geo.setBottom(geo.top() + new_h)
                elif "t" in e or "b" in e:
                    new_w = int(geo.height() * ar)
                    if "l" in e:
                        geo.setLeft(geo.right() - new_w)
                    else:
                        geo.setRight(geo.left() + new_w)
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
            edge = self._edge_at(ev.pos()) if self._selected else ""
            if edge:
                self.setCursor(self._cursor_for_edge(edge))
            else:
                self.setCursor(Qt.SizeAllCursor)

    def mouseReleaseEvent(self, ev):
        self._drag_origin = None
        self._drag_widget_pos = None
        self._group_drag = None
        self._resizing = False
        self._resize_edge = None

    def mouseDoubleClickEvent(self, ev):
        self._open_editor()

    def contextMenuEvent(self, ev):
        menu = QMenu(self)
        menu.addAction("Edit Equation…", self._open_editor)
        menu.addAction("Copy LaTeX", self._copy_latex)
        menu.addSeparator()
        overlay.add_arrange_actions(menu, self)
        menu.addSeparator()
        menu.addAction("Delete", self._delete)
        menu.exec_(ev.globalPos())

    # ── Editing ───────────────────────────────────────────────────────

    def _open_editor(self):
        old = (self._latex, self._fontsize, self._color)
        dlg = EquationDialog(self._latex, self._fontsize,
                             self._color, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            new = (dlg.latex, dlg.fontsize, dlg.color)
            if new == old:
                return
            self._apply_state(*new)
            self._render_keep_pos()
            stack = _find_undo_stack(self.parent())
            if stack is not None:
                stack.push(EditEquationCmd(self, old, new))

    def _render_keep_pos(self):
        """Re-render but keep current top-left position."""
        pos = self.pos()
        self._render()
        self.move(pos)

    def _copy_latex(self):
        QApplication.clipboard().setText(self._latex)

    def _delete(self):
        """Remove this equation from the sheet (undoable)."""
        sw = _find_sheet_widget(self.parent())
        if sw:
            stack = getattr(sw, "_undo_stack", None)
            if stack is not None:
                if self in sw._equations:
                    sw._equations.remove(self)
                self.hide()
                stack.push(DeleteEquationCmd(sw, self))
                return
            if self in sw._equations:
                sw._equations.remove(self)
        self.deleteLater()

    # ── Serialisation ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "latex": self._latex,
            "fontsize": self._fontsize,
            "color": self._color,
            "pos_x": self.pos().x(),
            "pos_y": self.pos().y(),
            "width": self.width(),
            "height": self.height(),
            "group_id": self._group_id,
        }

    @classmethod
    def from_dict(cls, d: dict, parent=None) -> "EmbeddedEquation":
        eq = cls(d.get("latex", ""), d.get("fontsize", 20),
                 d.get("color", "#000000"), parent)
        eq.move(d.get("pos_x", 0), d.get("pos_y", 0))
        eq.resize(d.get("width", eq.width()),
                  d.get("height", eq.height()))
        eq._group_id = d.get("group_id")
        return eq


# ── Equation editor dialog ────────────────────────────────────────────

class EquationDialog(QDialog):
    """Editor with live preview and LaTeX <-> maths round-tripping.

    The input box holds the LaTeX source.  As you type, the preview
    renders the corresponding maths (LaTeX → Math).  The same source is
    the LaTeX representation (Math → LaTeX) and can be copied out.
    """

    def __init__(self, latex="E = mc^2", fontsize=20,
                 color="#000000", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Equation Editor")
        self.resize(560, 360)
        self._color = color

        layout = QVBoxLayout(self)

        # Live preview area.
        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setMinimumHeight(120)
        self._preview.setStyleSheet(
            "background:#ffffff; border:1px solid #c0c0c0;")
        layout.addWidget(self._preview, 1)

        # Symbol / structure quick-insert palette.
        layout.addWidget(self._build_palette())

        # LaTeX source input.
        form = QFormLayout()
        self._input = QLineEdit(latex)
        self._input.setPlaceholderText(r"e.g.  x = \frac{-b}{2a}")
        self._input.textChanged.connect(self._update_preview)
        form.addRow("LaTeX:", self._input)

        # Font size.
        self._size_spin = QSpinBox()
        self._size_spin.setRange(8, 96)
        self._size_spin.setValue(fontsize)
        self._size_spin.valueChanged.connect(self._update_preview)
        form.addRow("Font size:", self._size_spin)

        # Colour.
        row = QHBoxLayout()
        self._color_btn = QPushButton("Colour…")
        self._color_btn.clicked.connect(self._pick_color)
        self._color_swatch = QLabel()
        self._color_swatch.setFixedSize(40, 20)
        self._update_swatch()
        row.addWidget(self._color_btn)
        row.addWidget(self._color_swatch)
        row.addStretch(1)
        form.addRow("Colour:", row)
        layout.addLayout(form)

        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

        self._update_preview()

    def _build_palette(self):
        """Common symbols and structures for quick insertion."""
        wrap = QWidget()
        grid = QGridLayout(wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)
        # (button label, snippet to insert).
        items = [
            ("x/y", r"\frac{}{}"), ("√", r"\sqrt{}"),
            ("xⁿ", r"^{}"), ("xₙ", r"_{}"),
            ("∑", r"\sum_{}^{}"), ("∫", r"\int_{}^{}"),
            ("∏", r"\prod_{}^{}"), ("π", r"\pi"),
            ("α", r"\alpha"), ("β", r"\beta"),
            ("θ", r"\theta"), ("∞", r"\infty"),
            ("≤", r"\leq"), ("≥", r"\geq"),
            ("±", r"\pm"), ("×", r"\times"),
            ("→", r"\rightarrow"), ("∂", r"\partial"),
        ]
        cols = 9
        for i, (lab, snip) in enumerate(items):
            b = QToolButton()
            b.setText(lab)
            b.setAutoRaise(True)
            b.setFocusPolicy(Qt.NoFocus)
            b.setFixedSize(30, 26)
            b.clicked.connect(lambda _=False, s=snip: self._insert(s))
            grid.addWidget(b, i // cols, i % cols)
        return wrap

    def _insert(self, snippet):
        """Insert a snippet at the cursor and place caret inside {}."""
        cur = self._input.cursorPosition()
        text = self._input.text()
        new = text[:cur] + snippet + text[cur:]
        self._input.setText(new)
        # Place caret in the first empty brace, if any.
        idx = snippet.find("{}")
        if idx >= 0:
            self._input.setCursorPosition(cur + idx + 1)
        else:
            self._input.setCursorPosition(cur + len(snippet))
        self._input.setFocus()

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color), self,
                                  "Equation Colour")
        if c.isValid():
            self._color = c.name()
            self._update_swatch()
            self._update_preview()

    def _update_swatch(self):
        self._color_swatch.setStyleSheet(
            f"background:{self._color}; border:1px solid #808080;")

    def _update_preview(self):
        pm = render_latex(self._input.text(), self._size_spin.value(),
                          self._color)
        self._preview.setPixmap(pm)

    # ── Result accessors ──────────────────────────────────────────────

    @property
    def latex(self):
        return self._input.text()

    @property
    def fontsize(self):
        return self._size_spin.value()

    @property
    def color(self):
        return self._color


# ── Equation gallery popup ────────────────────────────────────────────

class EquationGalleryMenu(QMenu):
    """Drop-down listing preset equations plus 'Insert New Equation'."""

    def __init__(self, on_pick, parent=None):
        super().__init__(parent)
        self._on_pick = on_pick

        container = QWidget(self)
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(6, 6, 6, 6)
        vbox.setSpacing(3)

        for label, body in EQUATION_PRESETS:
            btn = QToolButton(container)
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setText("  " + label)
            btn.setIcon(self._preview_icon(body))
            btn.setIconSize(QSize(120, 28))
            btn.setAutoRaise(True)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setStyleSheet("text-align:left;")
            btn.clicked.connect(
                lambda _=False, b=body: self._pick(b))
            vbox.addWidget(btn)

        sep = QLabel("─" * 30, container)
        sep.setStyleSheet("color:#c0c0c0;")
        vbox.addWidget(sep)

        new_btn = QToolButton(container)
        new_btn.setText("  Insert New Equation…")
        new_btn.setAutoRaise(True)
        new_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        new_btn.setStyleSheet("text-align:left;")
        new_btn.clicked.connect(lambda: self._pick(None))
        vbox.addWidget(new_btn)

        container.adjustSize()
        hint = container.sizeHint()
        scroll = QScrollArea(self)
        scroll.setWidget(container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedWidth(hint.width() + 24)
        scroll.setMaximumHeight(420)
        scroll.setMinimumHeight(min(420, hint.height() + 4))

        action = QWidgetAction(self)
        action.setDefaultWidget(scroll)
        self.addAction(action)

    def _preview_icon(self, body):
        from PyQt5.QtGui import QIcon
        pm = render_latex(body, 16, "#000000")
        if pm.width() > 120 or pm.height() > 28:
            pm = pm.scaled(120, 28, Qt.KeepAspectRatio,
                           Qt.SmoothTransformation)
        return QIcon(pm)

    def _pick(self, body):
        self.hide()
        self._on_pick(body)
