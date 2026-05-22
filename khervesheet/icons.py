"""Icon helpers — qtawesome wrapper with fallback to Qt standard icons.

Mirrors the KhervePlot / SimplePlot icon system: themed MDI glyphs via
qtawesome, filled+outline stacking, and custom QPainter plot-type icons.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from typing import Optional

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QColor, QFont, QIcon, QPainter, QPen, QPixmap,
                         QPolygonF)
from PyQt5.QtWidgets import QApplication, QStyle


try:
    import qtawesome as qta
    HAVE_QTA = True
except ImportError:
    qta = None
    HAVE_QTA = False


APP_ICON: Optional[QIcon] = None

# ── Icon colour styles ──────────────────────────────────────────────
ICON_STYLES = {
    "Dark Blue":     "#404060",
    "Black":         "#1a1a1a",
    "Charcoal":      "#3c3c3c",
    "Graphite":      "#2e2e38",
    "Dim Grey":      "#555555",
    "Navy":          "#1b2a4a",
    "Slate":         "#4a5568",
    "Steel Blue":    "#3a6ea5",
    "Cobalt":        "#0047ab",
    "Royal Blue":    "#2856a6",
    "Cornflower":    "#5b82c4",
    "Sky":           "#4a90d9",
    "Ocean":         "#1e5fa8",
    "Azure":         "#2a7ab5",
    "Cerulean":      "#1a6e8e",
    "Powder Blue":   "#5b8cb8",
    "Denim":         "#335b8e",
    "Teal":          "#1a7a6d",
    "Forest":        "#2d6a4f",
    "Emerald":       "#1b8a5a",
    "Olive":         "#5a6632",
    "Sage":          "#6b8f71",
    "Jade":          "#2a8a6a",
    "Pine":          "#1e5945",
    "Fern":          "#4a7a52",
    "Moss":          "#3a6b3a",
    "Spring Green":  "#2d8e5e",
    "Sea Green":     "#2e7d6e",
    "Burgundy":      "#6b2c3e",
    "Crimson":       "#9b1b30",
    "Rust":          "#a0522d",
    "Rose":          "#b5485d",
    "Fuchsia":       "#9b3072",
    "Magenta":       "#8e2a6e",
    "Plum":          "#5b3a6e",
    "Indigo":        "#3f3d99",
    "Violet":        "#7c3aad",
    "Mauve":         "#8b6a8f",
    "Warm Grey":     "#6b5e50",
    "Espresso":      "#4a3728",
    "Terracotta":    "#a0583c",
    "Amber":         "#b8860b",
    "Sienna":        "#8b5a2b",
    "Snow":          "#e8e8f0",
    "Silver":        "#a8a8b8",
    "Ice Blue":      "#88b8e0",
    "Mint":          "#78c8a0",
    "Peach":         "#e8a888",
    "Lavender":      "#b0a0d8",
}

_active_icon_style: str = "Dark Blue"


def active_icon_style() -> str:
    return _active_icon_style


def set_active_icon_style(name: str) -> None:
    global _active_icon_style
    if name in ICON_STYLES:
        _active_icon_style = name


def active_icon_color() -> str:
    return ICON_STYLES.get(_active_icon_style, "#404060")


# ── Core themed icon ────────────────────────────────────────────────
def themed_icon(qta_name: str, std_fallback=None,
                color: str = "", scale_factor: float = 1.0) -> QIcon:
    if not color:
        color = active_icon_color()
    if HAVE_QTA:
        try:
            return qta.icon(qta_name, color=color,
                            scale_factor=scale_factor)
        except Exception:
            pass
    if std_fallback is not None:
        try:
            return QApplication.style().standardIcon(std_fallback)
        except Exception:
            pass
    return QIcon()


# ── Filled + outline stacking ──────────────────────────────────────
def filled_outline_icon(filled_name: str, outline_name: str,
                        fill_color: str,
                        std_fallback=None,
                        scale: float = 1.0) -> QIcon:
    if HAVE_QTA:
        try:
            return qta.icon(
                filled_name, outline_name,
                options=[
                    {"color": fill_color, "scale_factor": scale},
                    {"color": active_icon_color(), "scale_factor": scale},
                ])
        except Exception:
            pass
    return themed_icon(outline_name, std_fallback, color=fill_color)


# ── Accent / fill colours ──────────────────────────────────────────
ICON_ACCENT = "#e60000"
LINE_PLOT_ACCENT = "#d49b1f"
SERIES_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c",
                  "#d62728", "#9467bd", "#8c564b"]

OPEN_FOLDER_YELLOW = "#ffc83d"
SAVE_GREEN = "#2ca02c"
DELETE_RED = ICON_ACCENT
COPY_BLUE = "#1f77b4"
PASTE_ORANGE = "#ff7f0e"

ADD_FILL = "#cce6cc"
REMOVE_FILL = "#f5b8b8"
COPY_FILL = "#c8dcef"
PASTE_FILL = "#fadcb8"
DELETE_FILL = "#f5b8b8"
SAVE_FILL = "#cce6cc"


# ── App icon ────────────────────────────────────────────────────────
def make_app_icon() -> QIcon:
    pm = QPixmap(32, 32)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setBrush(QColor(60, 90, 160))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, 32, 32, 6, 6)
    p.setPen(Qt.white)
    p.setFont(QFont("Segoe UI", 13, QFont.Bold))
    p.drawText(pm.rect(), Qt.AlignCenter, "KS")
    p.end()
    return QIcon(pm)


def init_app_icon() -> QIcon:
    global APP_ICON
    if APP_ICON is None:
        APP_ICON = make_app_icon()
    return APP_ICON


# ── File / action icons ────────────────────────────────────────────
def new_icon() -> QIcon:
    return filled_outline_icon("mdi.file", "mdi.file-outline",
                               ADD_FILL, QStyle.SP_FileIcon)


def open_folder_icon() -> QIcon:
    if HAVE_QTA:
        try:
            return qta.icon(
                "mdi.folder-open", "mdi.folder-open-outline",
                options=[
                    {"color": OPEN_FOLDER_YELLOW, "scale_factor": 1.0},
                    {"color": active_icon_color(), "scale_factor": 1.0},
                ])
        except Exception:
            pass
    return themed_icon("mdi.folder-open-outline",
                       QStyle.SP_DirOpenIcon,
                       color=OPEN_FOLDER_YELLOW)


def save_icon() -> QIcon:
    return filled_outline_icon("mdi.content-save", "mdi.content-save-outline",
                               SAVE_FILL, QStyle.SP_DialogSaveButton)


def undo_icon() -> QIcon:
    return themed_icon("mdi.undo", QStyle.SP_ArrowBack)


def redo_icon() -> QIcon:
    return themed_icon("mdi.redo", QStyle.SP_ArrowForward)


def cut_icon() -> QIcon:
    return filled_outline_icon("mdi.content-cut", "mdi.content-cut",
                               DELETE_FILL, scale=1.1)


def copy_icon() -> QIcon:
    return filled_outline_icon("mdi.content-copy", "mdi.content-copy",
                               COPY_FILL, scale=1.1)


def paste_icon() -> QIcon:
    return filled_outline_icon("mdi.content-paste", "mdi.content-paste",
                               PASTE_FILL, scale=1.1)


# ── Plot-type icons (custom QPainter) ──────────────────────────────
def _draw_plot_axes(p: QPainter, color: QColor, x0: float, y0: float,
                    x1: float, y1: float, pw: float = 1.2):
    p.setPen(QPen(color, pw, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
    p.drawLine(QPointF(x0, y0), QPointF(x0, y1))
    p.drawLine(QPointF(x0, y1), QPointF(x1, y1))


def plot_icon_line(size: int = 22,
                   line_color: str = LINE_PLOT_ACCENT) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = float(size)
    pad = 2.5
    x0, y0, x1, y1 = pad, pad, s - pad, s - pad
    _draw_plot_axes(p, QColor(active_icon_color()), x0, y0, x1, y1)
    p.setPen(QPen(QColor(line_color), 2.0, Qt.SolidLine,
                  Qt.RoundCap, Qt.RoundJoin))
    inner = [
        QPointF(x0 + (x1 - x0) * 0.10, y1 - (y1 - y0) * 0.25),
        QPointF(x0 + (x1 - x0) * 0.32, y1 - (y1 - y0) * 0.55),
        QPointF(x0 + (x1 - x0) * 0.55, y1 - (y1 - y0) * 0.35),
        QPointF(x0 + (x1 - x0) * 0.78, y1 - (y1 - y0) * 0.80),
    ]
    for a, b in zip(inner, inner[1:]):
        p.drawLine(a, b)
    p.end()
    return QIcon(pm)


def plot_icon_scatter(size: int = 22) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = float(size)
    pad = 2.5
    x0, y0, x1, y1 = pad, pad, s - pad, s - pad
    _draw_plot_axes(p, QColor(active_icon_color()), x0, y0, x1, y1)
    positions = [(0.18, 0.70), (0.36, 0.40), (0.52, 0.62),
                 (0.70, 0.30), (0.85, 0.55)]
    r = s * 0.10
    p.setPen(Qt.NoPen)
    for (fx, fy), col in zip(positions, SERIES_PALETTE):
        p.setBrush(QColor(col))
        cx = x0 + (x1 - x0) * fx
        cy = y0 + (y1 - y0) * fy
        p.drawEllipse(QPointF(cx, cy), r, r)
    p.end()
    return QIcon(pm)


def plot_icon_line_symbol(size: int = 22,
                          line_color: str = LINE_PLOT_ACCENT) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = float(size)
    pad = 2.5
    x0, y0, x1, y1 = pad, pad, s - pad, s - pad
    _draw_plot_axes(p, QColor(active_icon_color()), x0, y0, x1, y1)
    pts = [
        QPointF(x0 + (x1 - x0) * 0.12, y1 - (y1 - y0) * 0.22),
        QPointF(x0 + (x1 - x0) * 0.36, y1 - (y1 - y0) * 0.55),
        QPointF(x0 + (x1 - x0) * 0.60, y1 - (y1 - y0) * 0.38),
        QPointF(x0 + (x1 - x0) * 0.82, y1 - (y1 - y0) * 0.78),
    ]
    p.setPen(QPen(QColor(line_color), 1.8, Qt.SolidLine,
                  Qt.RoundCap, Qt.RoundJoin))
    for a, b in zip(pts, pts[1:]):
        p.drawLine(a, b)
    r = s * 0.11
    p.setPen(Qt.NoPen)
    for pt, col in zip(pts, SERIES_PALETTE):
        p.setBrush(QColor(col))
        p.drawEllipse(pt, r, r)
    p.end()
    return QIcon(pm)


def plot_icon_bar(size: int = 22) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = float(size)
    pad = 2.5
    x0, y0, x1, y1 = pad, pad, s - pad, s - pad
    _draw_plot_axes(p, QColor(active_icon_color()), x0, y0, x1, y1)
    heights = [0.45, 0.75, 0.55, 0.85]
    n = len(heights)
    gap = (x1 - x0) * 0.08
    bw = ((x1 - x0) - gap * (n + 1)) / n
    axis_pw = 1.2
    p.setPen(Qt.NoPen)
    for i, h in enumerate(heights):
        col = SERIES_PALETTE[i % len(SERIES_PALETTE)]
        p.setBrush(QColor(col))
        bx = x0 + gap + i * (bw + gap)
        bh = (y1 - y0) * h
        by = y1 - axis_pw / 2 - bh
        p.drawRect(QRectF(bx, by, bw, bh))
    p.end()
    return QIcon(pm)


# ── Zoom icons ──────────────────────────────────────────────────────
def zoom_in_icon() -> QIcon:
    if HAVE_QTA:
        try:
            return qta.icon(
                "mdi.magnify", "mdi.plus",
                options=[
                    {"color": active_icon_color(), "scale_factor": 1.0},
                    {"color": "#00e640", "scale_factor": 0.55,
                     "offset": (-0.10, -0.10)},
                ])
        except Exception:
            pass
    return themed_icon("mdi.magnify-plus-outline")


def zoom_out_icon() -> QIcon:
    if HAVE_QTA:
        try:
            return qta.icon(
                "mdi.magnify", "mdi.minus",
                options=[
                    {"color": active_icon_color(), "scale_factor": 1.0},
                    {"color": ICON_ACCENT, "scale_factor": 0.55,
                     "offset": (-0.10, -0.10)},
                ])
        except Exception:
            pass
    return themed_icon("mdi.magnify-minus-outline")
