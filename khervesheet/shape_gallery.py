"""Excel-style shape gallery popup.

A single drop-down that lays the whole shape registry out as a grid of
icon buttons grouped under category headers (Lines, Rectangles, Basic
Shapes, ...), instead of one very tall single-column list.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import (
    QMenu, QWidget, QWidgetAction, QScrollArea, QGridLayout,
    QLabel, QToolButton,
)

from . import shape_defs
from . import icons

_COLS = 7
_BTN = 30
_ICON = 22


class ShapeGalleryMenu(QMenu):
    """Drop-down showing every shape as a multi-column icon grid."""

    def __init__(self, on_pick, parent=None):
        super().__init__(parent)
        self._on_pick = on_pick

        container = QWidget(self)
        grid = QGridLayout(container)
        grid.setSpacing(2)
        grid.setContentsMargins(6, 4, 6, 6)

        row = 0
        for cat in shape_defs.CATEGORY_ORDER:
            entries = shape_defs.shapes_in_category(cat)
            if not entries:
                continue
            header = QLabel(cat, container)
            hf = header.font()
            hf.setBold(True)
            hf.setPointSizeF(max(7.5, hf.pointSizeF() - 0.5))
            header.setFont(hf)
            header.setStyleSheet("color:#666; margin-top:5px;")
            grid.addWidget(header, row, 0, 1, _COLS)
            row += 1
            col = 0
            for stype, slabel in entries:
                btn = QToolButton(container)
                btn.setIcon(icons.shape_icon(stype, _ICON))
                btn.setIconSize(QSize(_ICON, _ICON))
                btn.setFixedSize(_BTN, _BTN)
                btn.setAutoRaise(True)
                btn.setToolTip(slabel)
                btn.clicked.connect(
                    lambda _=False, t=stype: self._pick(t))
                grid.addWidget(btn, row, col)
                col += 1
                if col >= _COLS:
                    col = 0
                    row += 1
            if col != 0:
                row += 1

        container.adjustSize()
        hint = container.sizeHint()
        scroll = QScrollArea(self)
        scroll.setWidget(container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedWidth(hint.width() + 24)
        scroll.setMaximumHeight(560)
        scroll.setMinimumHeight(min(560, hint.height() + 4))

        action = QWidgetAction(self)
        action.setDefaultWidget(scroll)
        self.addAction(action)

    def _pick(self, shape_type):
        self.hide()
        self._on_pick(shape_type)
