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

from PyQt5.QtCore import Qt, QRect, QRectF, QModelIndex
from PyQt5.QtGui import QPen, QColor, QPainter, QFontMetrics
from PyQt5.QtWidgets import (
    QStyledItemDelegate, QStyleOptionViewItem, QTableWidget,
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
            d["alignment"] = self.alignment
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

    def paint(self, painter: QPainter,
              option: QStyleOptionViewItem,
              index: QModelIndex):
        key = (index.row(), index.column())

        # Draw formula reference background tint before default paint.
        ref_color = self._ref_highlights.get(key)
        if ref_color:
            painter.save()
            bg = QColor(ref_color)
            bg.setAlpha(30)
            painter.fillRect(option.rect, bg)
            painter.restore()

        super().paint(painter, option, index)

        # ── Text overflow into empty right-hand neighbours ────────
        self._paint_overflow(painter, option, index)

        # Draw cell format borders.
        cf = self._formats.get(key)
        if cf is not None:
            self._draw_borders(painter, option.rect, cf)

        # Draw formula reference border on top.
        if ref_color:
            painter.save()
            pen = QPen(QColor(ref_color), 2.0)
            painter.setPen(pen)
            painter.drawRect(option.rect.adjusted(1, 1, -1, -1))
            painter.restore()

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
        painter.setClipRect(rect)
        if cf.border_top:
            painter.setPen(QPen(QColor(cf.border_top.color),
                                cf.border_top.width,
                                Qt.PenStyle(cf.border_top.style)))
            painter.drawLine(rect.topLeft(), rect.topRight())
        if cf.border_bottom:
            painter.setPen(QPen(QColor(cf.border_bottom.color),
                                cf.border_bottom.width,
                                Qt.PenStyle(cf.border_bottom.style)))
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if cf.border_left:
            painter.setPen(QPen(QColor(cf.border_left.color),
                                cf.border_left.width,
                                Qt.PenStyle(cf.border_left.style)))
            painter.drawLine(rect.topLeft(), rect.bottomLeft())
        if cf.border_right:
            painter.setPen(QPen(QColor(cf.border_right.color),
                                cf.border_right.width,
                                Qt.PenStyle(cf.border_right.style)))
            painter.drawLine(rect.topRight(), rect.bottomRight())
        painter.restore()
