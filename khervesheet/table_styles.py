"""Table Design — predefined table styles for quick formatting.

Provides a gallery dialog of Excel-like table styles (Plain, Grid,
List) that apply header, banded-row, and border formatting to a
selected cell range.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QPainter, QPen, QFont, QPixmap, QIcon
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialogButtonBox, QScrollArea, QWidget, QGridLayout,
    QCheckBox, QGroupBox,
)


# ── Style definition ───────────────────────────────────────────────

@dataclass
class TableStyle:
    """A table style definition."""
    name: str
    category: str          # "Plain", "Grid", "List"
    header_bg: str         # header row background
    header_fg: str = "#ffffff"   # header text colour
    header_bold: bool = True
    even_bg: str = "#ffffff"     # even data rows
    odd_bg: str = "#f2f2f2"     # odd data rows (banding)
    text_fg: str = "#000000"    # data text colour
    border_color: Optional[str] = None   # border colour (None = no borders)
    border_header_bottom: bool = True    # thick header bottom
    border_outer: bool = False
    border_inner: bool = False


# ── Built-in styles ────────────────────────────────────────────────

_ACCENT_COLORS = [
    ("#404040", "Black"),
    ("#4472c4", "Blue"),
    ("#ed7d31", "Orange"),
    ("#a5a5a5", "Grey"),
    ("#ffc000", "Gold"),
    ("#5b9bd5", "Light Blue"),
    ("#70ad47", "Green"),
    ("#e74c3c", "Red"),
    ("#9b59b6", "Purple"),
    ("#ff69b4", "Pink"),
    ("#2ecc71", "Bright Green"),
]


def _lighten(hex_color: str, factor: float = 0.75) -> str:
    """Lighten a hex colour toward white by *factor* (0=unchanged,
    1=white)."""
    c = QColor(hex_color)
    r = int(c.red() + (255 - c.red()) * factor)
    g = int(c.green() + (255 - c.green()) * factor)
    b = int(c.blue() + (255 - c.blue()) * factor)
    return QColor(r, g, b).name()


def _darken(hex_color: str, factor: float = 0.3) -> str:
    """Darken a hex colour toward black by *factor* (0=unchanged,
    1=black)."""
    c = QColor(hex_color)
    r = int(c.red() * (1 - factor))
    g = int(c.green() * (1 - factor))
    b = int(c.blue() * (1 - factor))
    return QColor(r, g, b).name()


def _build_styles() -> list:
    """Generate all built-in table styles."""
    styles = []

    # ── Plain Tables ──────────────────────────────────────────────
    # Variant 1 — Light: white background, coloured header underline,
    #   very light banded rows.
    for accent, aname in _ACCENT_COLORS:
        light = _lighten(accent, 0.85)
        styles.append(TableStyle(
            name=f"Plain Light {aname}",
            category="Plain",
            header_bg="#ffffff",
            header_fg=accent,
            header_bold=True,
            even_bg="#ffffff",
            odd_bg=light,
            text_fg="#000000",
            border_color=accent,
            border_header_bottom=True,
            border_outer=False,
            border_inner=False,
        ))
    # Variant 2 — Medium: coloured header with white text, light rows,
    #   top-and-bottom border.
    for accent, aname in _ACCENT_COLORS:
        light = _lighten(accent, 0.85)
        styles.append(TableStyle(
            name=f"Plain Medium {aname}",
            category="Plain",
            header_bg=accent,
            header_fg="#ffffff",
            header_bold=True,
            even_bg="#ffffff",
            odd_bg=light,
            text_fg="#000000",
            border_color=accent,
            border_header_bottom=True,
            border_outer=True,
            border_inner=False,
        ))

    # ── Grid Tables ───────────────────────────────────────────────
    # Variant 1 — Light: coloured header, white/light rows, all borders.
    for accent, aname in _ACCENT_COLORS:
        light = _lighten(accent, 0.7)
        styles.append(TableStyle(
            name=f"Grid Light {aname}",
            category="Grid",
            header_bg=accent,
            header_fg="#ffffff",
            even_bg="#ffffff",
            odd_bg=light,
            text_fg="#000000",
            border_color=accent,
            border_header_bottom=True,
            border_outer=True,
            border_inner=True,
        ))
    # Variant 2 — Medium: coloured header, banded medium rows,
    #   outer border only.
    for accent, aname in _ACCENT_COLORS:
        light = _lighten(accent, 0.75)
        med = _lighten(accent, 0.55)
        styles.append(TableStyle(
            name=f"Grid Medium {aname}",
            category="Grid",
            header_bg=accent,
            header_fg="#ffffff",
            even_bg=light,
            odd_bg=med,
            text_fg="#000000",
            border_color=accent,
            border_header_bottom=True,
            border_outer=True,
            border_inner=False,
        ))
    # Variant 3 — Dark: coloured header, medium/dark rows, all borders.
    for accent, aname in _ACCENT_COLORS:
        light = _lighten(accent, 0.7)
        med = _lighten(accent, 0.4)
        styles.append(TableStyle(
            name=f"Grid Dark {aname}",
            category="Grid",
            header_bg=accent,
            header_fg="#ffffff",
            even_bg=light,
            odd_bg=med,
            text_fg="#000000",
            border_color=accent,
            border_header_bottom=True,
            border_outer=True,
            border_inner=True,
        ))
    # Variant 4 — Accent: deeply coloured, dark header, strong banding,
    #   all borders.
    for accent, aname in _ACCENT_COLORS:
        dark = _darken(accent, 0.25)
        med = _lighten(accent, 0.2)
        light = _lighten(accent, 0.45)
        styles.append(TableStyle(
            name=f"Grid Accent {aname}",
            category="Grid",
            header_bg=dark,
            header_fg="#ffffff",
            even_bg=med,
            odd_bg=light,
            text_fg="#ffffff",
            border_color=dark,
            border_header_bottom=True,
            border_outer=True,
            border_inner=True,
        ))

    # ── List Tables ───────────────────────────────────────────────
    # Variant 1 — Light: no borders, coloured header text, light banding.
    for accent, aname in _ACCENT_COLORS:
        light = _lighten(accent, 0.85)
        styles.append(TableStyle(
            name=f"List Light {aname}",
            category="List",
            header_bg="#ffffff",
            header_fg=accent,
            header_bold=True,
            even_bg="#ffffff",
            odd_bg=light,
            text_fg="#000000",
            border_color=accent,
            border_header_bottom=True,
            border_outer=False,
            border_inner=False,
        ))
    # Variant 2 — Medium: coloured header fill, white text, medium banding,
    #   bottom border on header.
    for accent, aname in _ACCENT_COLORS:
        light = _lighten(accent, 0.75)
        styles.append(TableStyle(
            name=f"List Medium {aname}",
            category="List",
            header_bg=accent,
            header_fg="#ffffff",
            header_bold=True,
            even_bg="#ffffff",
            odd_bg=light,
            text_fg="#000000",
            border_color=None,
            border_header_bottom=True,
            border_outer=False,
            border_inner=False,
        ))
    # Variant 3 — Dark: dark header, strong coloured banding, no borders.
    for accent, aname in _ACCENT_COLORS:
        dark = _darken(accent, 0.2)
        med = _lighten(accent, 0.55)
        light = _lighten(accent, 0.75)
        styles.append(TableStyle(
            name=f"List Dark {aname}",
            category="List",
            header_bg=dark,
            header_fg="#ffffff",
            header_bold=True,
            even_bg=light,
            odd_bg=med,
            text_fg="#000000",
            border_color=None,
            border_header_bottom=False,
            border_outer=False,
            border_inner=False,
        ))

    return styles


BUILTIN_STYLES = _build_styles()


# ── Thumbnail rendering ───────────────────────────────────────────

def _render_thumbnail(style: TableStyle, size: QSize = QSize(72, 52)
                      ) -> QPixmap:
    """Paint a small preview of the table style."""
    pm = QPixmap(size)
    pm.fill(Qt.white)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, False)

    cols, rows = 4, 5
    cw = size.width() // cols
    rh = size.height() // rows

    for row in range(rows):
        for col in range(cols):
            x = col * cw
            y = row * rh
            if row == 0:
                bg = QColor(style.header_bg)
            elif row % 2 == 0:
                bg = QColor(style.even_bg)
            else:
                bg = QColor(style.odd_bg)
            p.fillRect(x, y, cw, rh, bg)

    # Draw borders.
    bc = style.border_color or style.header_bg
    if style.border_color:
        pen = QPen(QColor(bc), 1)
        p.setPen(pen)
        if style.border_outer:
            p.drawRect(0, 0, size.width() - 1, size.height() - 1)
        if style.border_inner:
            for col in range(1, cols):
                p.drawLine(col * cw, 0, col * cw, size.height())
            for row in range(1, rows):
                p.drawLine(0, row * rh, size.width(), row * rh)
    if style.border_header_bottom:
        pen = QPen(QColor(bc), 2)
        p.setPen(pen)
        p.drawLine(0, rh, size.width(), rh)

    # Draw text lines.
    p.setPen(QPen(QColor(style.header_fg if True else "#000"), 1))
    for col in range(cols):
        x = col * cw + 3
        y = 0 + rh // 2 + 2
        p.drawLine(x, y - 1, x + cw - 6, y - 1)

    p.setPen(QPen(QColor("#888"), 1))
    for row in range(1, rows):
        for col in range(cols):
            x = col * cw + 4
            y = row * rh + rh // 2 + 1
            p.drawLine(x, y, x + cw - 8, y)

    p.end()
    return pm


# ── Gallery dialog ─────────────────────────────────────────────────

class TableDesignDialog(QDialog):
    """Gallery of table styles for quick formatting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Table Design")
        self.resize(680, 560)
        self._selected_style = None

        outer = QVBoxLayout(self)

        # Options.
        opts = QHBoxLayout()
        self.header_check = QCheckBox("Header Row")
        self.header_check.setChecked(True)
        self.banded_check = QCheckBox("Banded Rows")
        self.banded_check.setChecked(True)
        opts.addWidget(self.header_check)
        opts.addWidget(self.banded_check)
        opts.addStretch()
        outer.addLayout(opts)

        # Scrollable gallery.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        gallery = QWidget()
        gallery_layout = QVBoxLayout(gallery)

        # Group by category.
        for category in ("Plain", "Grid", "List"):
            grp = QGroupBox(f"{category} Tables")
            grid = QGridLayout(grp)
            grid.setSpacing(6)
            cat_styles = [s for s in BUILTIN_STYLES
                          if s.category == category]
            cols_per_row = 7
            for i, style in enumerate(cat_styles):
                btn = QPushButton()
                pm = _render_thumbnail(style)
                btn.setIcon(QIcon(pm))
                btn.setIconSize(pm.size())
                btn.setFixedSize(pm.width() + 8, pm.height() + 8)
                btn.setToolTip(style.name)
                btn.setFlat(True)
                btn.setStyleSheet(
                    "QPushButton:hover { border: 2px solid #3078c6; }")
                btn.clicked.connect(
                    lambda _, s=style: self._pick(s))
                grid.addWidget(btn, i // cols_per_row,
                               i % cols_per_row)
            gallery_layout.addWidget(grp)

        gallery_layout.addStretch()
        scroll.setWidget(gallery)
        outer.addWidget(scroll, stretch=1)

        # Footer.
        bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

    def _pick(self, style):
        self._selected_style = style
        self._use_header = self.header_check.isChecked()
        self._use_banding = self.banded_check.isChecked()
        self.accept()

    @property
    def selected_style(self):
        return self._selected_style

    @property
    def use_header(self):
        return getattr(self, '_use_header', True)

    @property
    def use_banding(self):
        return getattr(self, '_use_banding', True)
