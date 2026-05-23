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

from PyQt5.QtCore import Qt, QRectF, QModelIndex
from PyQt5.QtGui import QPen, QColor, QPainter
from PyQt5.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem


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
    """Per-cell visual formatting (fill colour + borders)."""
    bg_color: Optional[str] = None
    border_top: Optional[BorderSpec] = None
    border_bottom: Optional[BorderSpec] = None
    border_left: Optional[BorderSpec] = None
    border_right: Optional[BorderSpec] = None

    def is_empty(self) -> bool:
        return (self.bg_color is None
                and self.border_top is None
                and self.border_bottom is None
                and self.border_left is None
                and self.border_right is None)

    def to_dict(self) -> dict:
        d: dict = {}
        if self.bg_color:
            d["bg"] = self.bg_color
        for side in ("top", "bottom", "left", "right"):
            b = getattr(self, f"border_{side}")
            if b is not None:
                d[f"b_{side}"] = b.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> CellFormat:
        cf = cls()
        cf.bg_color = d.get("bg")
        for side in ("top", "bottom", "left", "right"):
            bd = d.get(f"b_{side}")
            if bd:
                setattr(cf, f"border_{side}", BorderSpec.from_dict(bd))
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

    def __init__(self, formats: Dict[Tuple[int, int], CellFormat],
                 parent=None):
        super().__init__(parent)
        self._formats = formats

    def paint(self, painter: QPainter,
              option: QStyleOptionViewItem,
              index: QModelIndex):
        super().paint(painter, option, index)
        cf = self._formats.get((index.row(), index.column()))
        if cf is None:
            return
        rect = option.rect
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
