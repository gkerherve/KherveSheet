"""Cell formatting — background colour, borders, and delegate.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from PyQt5.QtCore import Qt, QPoint, QRect, QRectF, QModelIndex
from PyQt5.QtGui import (QPen, QColor, QPainter, QFont, QFontMetrics,
                         QPolygon, QPalette, QBrush)
from PyQt5.QtWidgets import (
    QStyledItemDelegate, QStyleOptionViewItem, QTableWidget,
    QStyle,
)


# ── Data classes ────────────────────────────────────────────────────

@dataclass
class BorderSpec:
    """Specification for a single cell edge border."""
    style: int = Qt.SolidLine   # Qt.SolidLine, Qt.DashLine, etc.
    color: str = "#000000"
    width: float = 1.0

    def to_dict(self) -> dict:
        return {"style": self.style, "color": self.color,
                "width": self.width}

    @classmethod
    def from_dict(cls, d: dict) -> BorderSpec:
        return cls(style=int(d.get("style", Qt.SolidLine)),
                   color=d.get("color", "#000000"),
                   width=float(d.get("width", 1.0)))


@dataclass
class CellFormat:
    """Per-cell visual formatting (fill, borders, font, alignment)."""
    bg_color: Optional[str] = None
    border_top: Optional[BorderSpec] = None
    border_bottom: Optional[BorderSpec] = None
    border_left: Optional[BorderSpec] = None
    border_right: Optional[BorderSpec] = None
    # Font properties.
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    underline: Optional[bool] = None
    font_family: Optional[str] = None
    font_size: Optional[float] = None
    font_color: Optional[str] = None
    alignment: Optional[int] = None
    number_format: Optional[str] = None
    wrap_text: Optional[bool] = None

    def is_empty(self) -> bool:
        return (self.bg_color is None
                and self.border_top is None
                and self.border_bottom is None
                and self.border_left is None
                and self.border_right is None
                and self.bold is None
                and self.italic is None
                and self.underline is None
                and self.font_family is None
                and self.font_size is None
                and self.font_color is None
                and self.alignment is None
                and self.number_format is None
                and self.wrap_text is None)

    def to_dict(self) -> dict:
        d: dict = {}
        if self.bg_color:
            d["bg"] = self.bg_color
        for side in ("top", "bottom", "left", "right"):
            b = getattr(self, f"border_{side}")
            if b is not None:
                d[f"b_{side}"] = b.to_dict()
        if self.bold is not None:
            d["bold"] = self.bold
        if self.italic is not None:
            d["italic"] = self.italic
        if self.underline is not None:
            d["underline"] = self.underline
        if self.font_family is not None:
            d["font_family"] = self.font_family
        if self.font_size is not None:
            d["font_size"] = self.font_size
        if self.font_color is not None:
            d["font_color"] = self.font_color
        if self.alignment is not None:
            d["alignment"] = int(self.alignment)
        if self.number_format is not None:
            d["number_format"] = self.number_format
        if self.wrap_text is not None:
            d["wrap_text"] = self.wrap_text
        return d

    @classmethod
    def from_dict(cls, d: dict) -> CellFormat:
        cf = cls()
        cf.bg_color = d.get("bg")
        for side in ("top", "bottom", "left", "right"):
            bd = d.get(f"b_{side}")
            if bd:
                setattr(cf, f"border_{side}", BorderSpec.from_dict(bd))
        cf.bold = d.get("bold")
        cf.italic = d.get("italic")
        cf.underline = d.get("underline")
        cf.font_family = d.get("font_family")
        cf.font_size = d.get("font_size")
        if cf.font_size is not None:
            cf.font_size = float(cf.font_size)
        cf.font_color = d.get("font_color")
        cf.alignment = d.get("alignment")
        if cf.alignment is not None:
            cf.alignment = int(cf.alignment)
        cf.number_format = d.get("number_format")
        cf.wrap_text = d.get("wrap_text")
        return cf


# ── Serialisation helpers ───────────────────────────────────────────

def formats_to_json(formats: Dict[Tuple[int, int], CellFormat]) -> str:
    """Serialise cell formats dict to JSON string."""
    out = {}
    for (r, c), cf in formats.items():
        if not cf.is_empty():
            out[f"{r},{c}"] = cf.to_dict()
    return json.dumps(out) if out else ""


def formats_from_json(s: str) -> Dict[Tuple[int, int], CellFormat]:
    """Deserialise cell formats dict from JSON string."""
    if not s:
        return {}
    raw = json.loads(s)
    result: Dict[Tuple[int, int], CellFormat] = {}
    for key, val in raw.items():
        r, c = key.split(",")
        result[(int(r), int(c))] = CellFormat.from_dict(val)
    return result


# ── Delegate ────────────────────────────────────────────────────────

class CellFormatDelegate(QStyledItemDelegate):
    """Draws cell borders stored in a shared *formats* dict.

    Background colour is handled via QTableWidgetItem.setBackground()
    for performance; only borders need custom painting.
    """

    # Cycling colours for formula reference highlights (Excel-like).
    REF_COLORS = [
        "#4472c4",   # blue
        "#ed7d31",   # orange
        "#a5a5a5",   # grey
        "#ffc000",   # gold
        "#5b9bd5",   # light blue
        "#70ad47",   # green
        "#e74c3c",   # red
        "#9b59b6",   # purple
    ]

    def __init__(self, formats: Dict[Tuple[int, int], CellFormat],
                 parent=None):
        super().__init__(parent)
        self._formats = formats
        # Formula reference highlights: {(row, col): color_hex}
        self._ref_highlights: Dict[Tuple[int, int], str] = {}
        # Sparklines: {(row, col): {"col": int, "r1": int, "r2": int,
        #              "type": "line"|"bar"|"winloss", "color": str}}
        self._sparklines: Dict[Tuple[int, int], dict] = {}
        # Notes: {(row, col): str} — pointer set by SheetWidget
        self._notes: Dict[Tuple[int, int], str] = {}
        # Dropdowns: {(row, col): list[str]} — pointer set by SheetWidget
        self._dropdowns: Dict[Tuple[int, int], list] = {}
        # Cell formulas: {(row, col): "=..."} — pointer set by SheetWidget.
        # Used to give Python (=PY) cells a green tint and a "PY" badge.
        self._cell_formulas: Dict[Tuple[int, int], str] = {}
        # Live spell-check: when True, misspelled words get a red wavy
        # underline.  Toggled from the Tools menu.
        self._spell_enabled: bool = False

    def paint(self, painter: QPainter,
              option: QStyleOptionViewItem,
              index: QModelIndex):
        key = (index.row(), index.column())

        # Python (=PY) cells get a faint green tint + a "PY" badge.
        fm = self._cell_formulas.get(key)
        is_py = isinstance(fm, str) and fm.lstrip().upper().startswith("=PY")
        py_tint = QColor(46, 160, 67, 16) if is_py else None

        # Draw formula reference background tint before default paint.
        ref_color = self._ref_highlights.get(key)
        if ref_color:
            painter.save()
            bg = QColor(ref_color)
            bg.setAlpha(30)
            painter.fillRect(option.rect, bg)
            painter.restore()

        # Green tint for Python cells (under the text, like a fill).
        if py_tint is not None:
            painter.save()
            painter.fillRect(option.rect, py_tint)
            painter.restore()

        # Strip the built-in selection highlight completely: paint the
        # cell background ourselves, then let the base class draw only
        # the text/icon on top.  A 10 % translucent tint replaces the
        # opaque fill.  The selection border is drawn by a viewport
        # overlay (_SelectionOverlay).
        selected = bool(option.state & QStyle.State_Selected)
        if selected:
            # 1) Fill the cell rect with the normal (unselected) bg.
            painter.save()
            item_bg = index.data(Qt.BackgroundRole)
            if item_bg and QColor(item_bg).isValid():
                painter.fillRect(option.rect, QColor(item_bg))
            else:
                painter.fillRect(option.rect, option.palette.base())
            # 1b) Re-apply the Python green tint over the base fill.
            if py_tint is not None:
                painter.fillRect(option.rect, py_tint)
            # 2) Light selection tint (10 % opacity ≈ alpha 25).
            hl = option.palette.highlight().color()
            hl.setAlpha(25)
            painter.fillRect(option.rect, hl)
            painter.restore()
            # 3) Draw text/decoration without any selection styling.
            opt2 = QStyleOptionViewItem(option)
            opt2.state &= ~(QStyle.State_Selected | QStyle.State_HasFocus)
            pal = QPalette(opt2.palette)
            pal.setBrush(QPalette.Highlight, QColor(0, 0, 0, 0))
            pal.setBrush(QPalette.HighlightedText, pal.text())
            opt2.palette = pal
            opt2.backgroundBrush = QBrush(Qt.NoBrush)
            super().paint(painter, opt2, index)
        else:
            super().paint(painter, option, index)

        # ── Text overflow into empty right-hand neighbours ────────
        self._paint_overflow(painter, option, index)

        # ── Live spell-check underlines ───────────────────────────
        if self._spell_enabled:
            self._paint_spell(painter, option, index)

        # Draw cell format borders.
        cf = self._formats.get(key)
        if cf is not None:
            self._draw_borders(painter, option.rect, cf)

        # Draw sparkline if present.
        spark = self._sparklines.get(key)
        if spark:
            self._paint_sparkline(painter, option.rect, spark)

        # Draw note indicator (red triangle, top-right corner).
        if key in self._notes:
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#ff0000"))
            r = option.rect
            tri_size = 6
            triangle = QPolygon([
                QPoint(r.right() - tri_size, r.top()),
                QPoint(r.right(), r.top()),
                QPoint(r.right(), r.top() + tri_size),
            ])
            painter.drawPolygon(triangle)
            painter.restore()

        # Draw dropdown arrow indicator (small ▼, right edge).
        if key in self._dropdowns:
            painter.save()
            r = option.rect
            arrow_w = 12
            arrow_rect = QRect(r.right() - arrow_w, r.top(),
                               arrow_w, r.height())
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#666666"))
            cx = arrow_rect.center().x()
            cy = arrow_rect.center().y()
            triangle = QPolygon([
                QPoint(cx - 3, cy - 2),
                QPoint(cx + 3, cy - 2),
                QPoint(cx, cy + 2),
            ])
            painter.drawPolygon(triangle)
            painter.restore()

        # Draw the "PY" strip down the full height of the RIGHT edge.
        if is_py:
            painter.save()
            r = option.rect
            bw = 18
            badge = QRect(r.right() - bw, r.top(), bw, r.height())
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#2e7d32"))      # Excel-like green
            painter.drawRect(badge)
            f = QFont(painter.font())
            f.setPointSize(7)
            f.setBold(True)
            painter.setFont(f)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(badge, Qt.AlignCenter, "PY")
            painter.restore()

        # Draw formula reference border on top.
        if ref_color:
            painter.save()
            pen = QPen(QColor(ref_color), 2.0)
            painter.setPen(pen)
            painter.drawRect(option.rect.adjusted(1, 1, -1, -1))
            painter.restore()

    def _paint_sparkline(self, painter: QPainter, rect, spark: dict):
        """Render a tiny chart inside the cell rect."""
        table = self.parent()
        if not isinstance(table, QTableWidget):
            return
        col = spark.get("col")
        r1 = spark.get("r1", 0)
        r2 = spark.get("r2", table.rowCount() - 1)
        if col is None:
            return

        # Collect numeric values from the source range.
        vals = []
        for r in range(r1, r2 + 1):
            it = table.item(r, col)
            if it and it.text():
                try:
                    vals.append(float(it.text()))
                except (ValueError, TypeError):
                    vals.append(0.0)
            else:
                vals.append(0.0)
        if not vals:
            return

        color = QColor(spark.get("color", "#4472c4"))
        neg_color = QColor(spark.get("neg_color", "#e74c3c"))
        spark_type = spark.get("type", "line")
        pad = 2
        area = rect.adjusted(pad, pad, -pad, -pad)
        if area.width() < 4 or area.height() < 4:
            return

        painter.save()
        painter.setClipRect(rect)
        painter.setRenderHint(QPainter.Antialiasing, True)

        vmin = min(vals)
        vmax = max(vals)
        if vmax == vmin:
            vmax = vmin + 1  # avoid division by zero

        n = len(vals)
        h = area.height()
        w = area.width()

        if spark_type == "bar":
            bar_w = max(1, w / n)
            zero_y = area.bottom() - h * (0 - vmin) / (vmax - vmin)
            if vmin >= 0:
                zero_y = area.bottom()
            for i, v in enumerate(vals):
                x = area.left() + i * bar_w
                frac = (v - vmin) / (vmax - vmin)
                bar_h = frac * h
                if vmin < 0:
                    # Bars grow from zero line.
                    y_top = zero_y - (v / (vmax - vmin)) * h
                    bar_h_abs = abs(v / (vmax - vmin)) * h
                    c = neg_color if v < 0 else color
                    painter.fillRect(
                        int(x), int(min(y_top, zero_y)),
                        int(bar_w - 1) or 1, int(bar_h_abs) or 1, c)
                else:
                    y_top = area.bottom() - bar_h
                    painter.fillRect(
                        int(x), int(y_top),
                        int(bar_w - 1) or 1, int(bar_h) or 1, color)

        elif spark_type == "winloss":
            bar_w = max(1, w / n)
            mid_y = area.top() + h / 2
            for i, v in enumerate(vals):
                x = area.left() + i * bar_w
                c = color if v >= 0 else neg_color
                if v >= 0:
                    painter.fillRect(
                        int(x), int(area.top()),
                        int(bar_w - 1) or 1, int(h / 2), c)
                else:
                    painter.fillRect(
                        int(x), int(mid_y),
                        int(bar_w - 1) or 1, int(h / 2), c)

        else:  # line (default)
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            points = []
            for i, v in enumerate(vals):
                x = area.left() + (i / max(n - 1, 1)) * w
                frac = (v - vmin) / (vmax - vmin)
                y = area.bottom() - frac * h
                points.append((x, y))
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            # Mark min/max points.
            min_i = vals.index(min(vals))
            max_i = vals.index(max(vals))
            for idx, c in ((min_i, neg_color), (max_i, QColor("#70ad47"))):
                px, py = points[idx]
                painter.setBrush(c)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(int(px) - 2, int(py) - 2, 4, 4)

        painter.restore()

    def _paint_spell(self, painter, option, index):
        """Underline misspelled words in the cell with a red wavy line."""
        from . import spellcheck
        text = index.data(Qt.DisplayRole)
        if not spellcheck.should_check(text) or not spellcheck.available():
            return
        # Wrapped multi-line text isn't laid out single-line here; skip
        # so underlines never land in the wrong place.
        cf = self._formats.get((index.row(), index.column()))
        if cf and cf.wrap_text:
            return
        font = index.data(Qt.FontRole) or option.font
        fm = QFontMetrics(font)
        text_rect = option.rect.adjusted(3, 0, -3, 0)
        align = int(index.data(Qt.TextAlignmentRole) or
                    (Qt.AlignLeft | Qt.AlignVCenter))
        # Underline sits just below the text baseline, clamped in cell.
        y = min(text_rect.center().y() + fm.ascent() // 2 + 2,
                text_rect.bottom() - 1)
        painter.save()
        painter.setClipRect(option.rect)
        pen = QPen(QColor("#e53935"), 1.0)
        painter.setPen(pen)
        painter.setRenderHint(QPainter.Antialiasing, True)
        for _s, _e, word, x0, x1 in spellcheck.iter_word_spans(
                text, fm, text_rect.left(), text_rect.width(), align):
            if x1 <= text_rect.left() or x0 >= text_rect.right():
                continue
            if spellcheck.is_misspelled(word):
                self._draw_wavy(painter, x0, x1, y)
        painter.restore()

    @staticmethod
    def _draw_wavy(painter, x0, x1, y):
        """Draw a small red zig-zag between x0 and x1 at height y."""
        from PyQt5.QtCore import QPointF
        from PyQt5.QtGui import QPainterPath
        step = 2.0          # half-wavelength in px
        amp = 1.2           # amplitude
        path = QPainterPath()
        path.moveTo(x0, y)
        x = float(x0)
        up = True
        while x < x1:
            x_next = min(x + step, x1)
            path.lineTo(x_next, y - amp if up else y + amp)
            up = not up
            x = x_next
        painter.drawPath(path)

    def _paint_overflow(self, painter, option, index):
        """If this cell's text is wider than the column, paint the
        overflow portion across empty cells to the right."""
        table = self.parent()
        if not isinstance(table, QTableWidget):
            return
        row, col = index.row(), index.column()

        # Check if wrap-text is enabled — overflow doesn't apply.
        cf = self._formats.get((row, col))
        if cf and cf.wrap_text:
            return

        text = index.data(Qt.DisplayRole)
        if not text:
            return

        # Measure text width.
        font = index.data(Qt.FontRole) or option.font
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(text)
        cell_w = option.rect.width() - 6  # 3px padding each side

        if text_w <= cell_w:
            return

        # Count how many empty columns to the right we can spill into.
        total_w = option.rect.width()
        max_col = table.columnCount()
        for nc in range(col + 1, max_col):
            item = table.item(row, nc)
            if item and item.text():
                break
            total_w += table.columnWidth(nc)
            if total_w >= text_w + 6:
                break

        if total_w <= option.rect.width():
            return

        # Paint overflow text with an extended rect.
        painter.save()
        overflow_rect = QRect(option.rect)
        overflow_rect.setWidth(total_w)
        painter.setClipRect(overflow_rect)
        # Fill background (use cell bg or white).
        bg = index.data(Qt.BackgroundRole)
        if bg:
            painter.fillRect(overflow_rect, bg)
        else:
            painter.fillRect(overflow_rect, QColor("#ffffff"))
        # Draw text.
        fg = index.data(Qt.ForegroundRole)
        if fg:
            painter.setPen(QPen(fg.color()))
        else:
            painter.setPen(QPen(QColor("#000000")))
        painter.setFont(font)
        align = int(index.data(Qt.TextAlignmentRole) or
                    (Qt.AlignLeft | Qt.AlignVCenter))
        text_rect = overflow_rect.adjusted(3, 0, -3, 0)
        painter.drawText(text_rect, align, text)
        painter.restore()

    def _draw_borders(self, painter, rect, cf):
        """Draw cell format borders."""
        painter.save()
        # Expand clip rect so thick borders aren't clipped at cell edges
        max_w = max(
            (cf.border_top.width if cf.border_top else 0),
            (cf.border_bottom.width if cf.border_bottom else 0),
            (cf.border_left.width if cf.border_left else 0),
            (cf.border_right.width if cf.border_right else 0),
        )
        margin = int(max_w / 2) + 1
        painter.setClipRect(rect.adjusted(-margin, -margin, margin, margin))
        if cf.border_top:
            pen = QPen(QColor(cf.border_top.color),
                       cf.border_top.width,
                       Qt.PenStyle(cf.border_top.style))
            pen.setCapStyle(Qt.FlatCap)
            painter.setPen(pen)
            y = rect.top()
            painter.drawLine(rect.left(), y, rect.right(), y)
        if cf.border_bottom:
            pen = QPen(QColor(cf.border_bottom.color),
                       cf.border_bottom.width,
                       Qt.PenStyle(cf.border_bottom.style))
            pen.setCapStyle(Qt.FlatCap)
            painter.setPen(pen)
            y = rect.bottom()
            painter.drawLine(rect.left(), y, rect.right(), y)
        if cf.border_left:
            pen = QPen(QColor(cf.border_left.color),
                       cf.border_left.width,
                       Qt.PenStyle(cf.border_left.style))
            pen.setCapStyle(Qt.FlatCap)
            painter.setPen(pen)
            x = rect.left()
            painter.drawLine(x, rect.top(), x, rect.bottom())
        if cf.border_right:
            pen = QPen(QColor(cf.border_right.color),
                       cf.border_right.width,
                       Qt.PenStyle(cf.border_right.style))
            pen.setCapStyle(Qt.FlatCap)
            painter.setPen(pen)
            x = rect.right()
            painter.drawLine(x, rect.top(), x, rect.bottom())
        painter.restore()
