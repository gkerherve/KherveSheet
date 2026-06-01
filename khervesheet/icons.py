"""Icon helpers — qtawesome wrapper, app icon, fallback to Qt standard icons.

Same icon system as KhervePlot / SimplePlot: themed MDI glyphs via
qtawesome, filled+outline stacking, and custom QPainter plot-type icons.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from typing import Optional

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QFont, QIcon, QPainter, QPen,
                         QPixmap, QPolygonF)
from PyQt5.QtWidgets import QApplication, QStyle


try:
    import qtawesome as qta
    HAVE_QTA = True
except ImportError:
    qta = None
    HAVE_QTA = False

try:
    from scipy import optimize as _sp_optimize  # noqa: F401
    from scipy import signal as _sp_signal  # noqa: F401
    from scipy import integrate as _sp_integrate  # noqa: F401
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False


APP_ICON: Optional[QIcon] = None

# Icon colour styles — name → hex colour used by themed_icon().
ICON_STYLES = {
    # --- Darks / neutrals ---
    "Dark Blue":     "#404060",
    "Black":         "#1a1a1a",
    "Charcoal":      "#3c3c3c",
    "Graphite":      "#2e2e38",
    "Dim Grey":      "#555555",
    # --- Blues ---
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
    # --- Greens / teals ---
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
    # --- Reds / pinks ---
    "Burgundy":      "#6b2c3e",
    "Crimson":       "#9b1b30",
    "Rust":          "#a0522d",
    "Rose":          "#b5485d",
    "Fuchsia":       "#9b3072",
    "Magenta":       "#8e2a6e",
    "Hot Pink":      "#c44080",
    "Blush":         "#b0506a",
    "Raspberry":     "#8b1a4a",
    "Coral":         "#c05050",
    # --- Purples ---
    "Plum":          "#5b3a6e",
    "Indigo":        "#3f3d99",
    "Violet":        "#7c3aad",
    "Mauve":         "#8b6a8f",
    # --- Warm tones ---
    "Warm Grey":     "#6b5e50",
    "Espresso":      "#4a3728",
    "Terracotta":    "#a0583c",
    "Amber":         "#b8860b",
    "Sienna":        "#8b5a2b",
    # --- Light / bright (for dark window themes) ---
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


def themed_icon(qta_name: str, std_fallback=None,
                color: str = "", scale_factor: float = 1.0) -> QIcon:
    if not color:
        color = active_icon_color()
    if HAVE_QTA:
        try:
            return qta.icon(qta_name, color=color,
                            scale_factor=scale_factor)
        except Exception:  # noqa: BLE001
            pass
    if std_fallback is not None:
        try:
            return QApplication.style().standardIcon(std_fallback)
        except Exception:  # noqa: BLE001
            pass
    return QIcon()


def make_app_icon() -> QIcon:
    pm = QPixmap(32, 32)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setBrush(QColor(34, 139, 34))
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


def kind_icon(kind: str) -> QIcon:
    """Return a window icon for an MDI subwindow kind so the title-bar
    glyph reads as Workbook / Graph / Matrix instead of every window
    showing the same app icon. Falls back to the app icon if
    qtawesome isn't available or the lookup fails."""
    spec = {
        "Workbook":   ("mdi.table-large", QStyle.SP_FileIcon),
        "Graph":      ("mdi.chart-line",  QStyle.SP_FileDialogDetailedView),
        "MatrixBook": ("mdi.grid",        QStyle.SP_DirIcon),
        "Matrix":     ("mdi.grid",        QStyle.SP_DirIcon),
    }.get(kind)
    if spec is not None:
        ic = themed_icon(spec[0], spec[1], color="#000000")
        if not ic.isNull():
            return ic
    return APP_ICON or QIcon()


def axis_arrow_icon(axis: str, side: str, expand: bool,
                    size: int = 28) -> QIcon:
    """Draw an axis-edge nudge icon.

    A horizontal or vertical bar represents the axis edge.  A straight
    arrow extends from the bar's centre — pointing *away* from the bar
    when *expand* is True (push edge outward) and *toward* the bar when
    False (pull edge inward).

    *axis*: ``"x"`` or ``"y"``.
    *side*: ``"hi"`` (top / right) or ``"lo"`` (bottom / left).
    """
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    color = QColor(active_icon_color())
    bar_color = QColor(ICON_ACCENT)
    s = float(size)
    pad = 2.0
    # Bar stroke is heavier than the arrow shaft so the red edge
    # reads as the dominant element of the icon.
    bar_pw = s * 0.11
    pw = 2.0                # pen width — arrow shaft
    aw = s * 0.22           # arrowhead half-width
    ah = s * 0.20           # arrowhead length
    bar_half = s * 0.38     # half-length of the edge bar
    gap = bar_pw / 2 + s * 0.06  # clearance between bar centre and arrow start

    if axis == "y":
        cx = s / 2
        if side == "hi":
            # Bar at top — horizontal.
            bar_y = pad
            _draw_bar(p, bar_color, bar_pw, cx - bar_half, bar_y,
                      cx + bar_half, bar_y)
            if expand:
                _draw_arrow(p, color, pw, aw, ah,
                            cx, s - pad, cx, bar_y + gap)
            else:
                _draw_arrow(p, color, pw, aw, ah,
                            cx, bar_y + gap, cx, s - pad)
        else:
            # Bar at bottom — horizontal.
            bar_y = s - pad
            _draw_bar(p, bar_color, bar_pw, cx - bar_half, bar_y,
                      cx + bar_half, bar_y)
            if expand:
                _draw_arrow(p, color, pw, aw, ah,
                            cx, pad, cx, bar_y - gap)
            else:
                _draw_arrow(p, color, pw, aw, ah,
                            cx, bar_y - gap, cx, pad)
    else:
        cy = s / 2
        if side == "lo":
            # Bar on left — vertical.
            bar_x = pad
            _draw_bar(p, bar_color, bar_pw, bar_x, cy - bar_half,
                      bar_x, cy + bar_half)
            if expand:
                _draw_arrow(p, color, pw, aw, ah,
                            s - pad, cy, bar_x + gap, cy)
            else:
                _draw_arrow(p, color, pw, aw, ah,
                            bar_x + gap, cy, s - pad, cy)
        else:
            # Bar on right — vertical.
            bar_x = s - pad
            _draw_bar(p, bar_color, bar_pw, bar_x, cy - bar_half,
                      bar_x, cy + bar_half)
            if expand:
                _draw_arrow(p, color, pw, aw, ah,
                            pad, cy, bar_x - gap, cy)
            else:
                _draw_arrow(p, color, pw, aw, ah,
                            bar_x - gap, cy, pad, cy)
    p.end()
    return QIcon(pm)


def axis_toggle_icon(side: str, size: int = 28) -> QIcon:
    """Draw a thin plot-frame rectangle with one edge highlighted in
    the red accent colour. All edges share the same stroke width — the
    highlight is colour, not thickness.

    *side*: ``"top"``, ``"bottom"``, ``"left"``, or ``"right"``.
    """
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    color = QColor(active_icon_color())
    accent = QColor(ICON_ACCENT)
    s = float(size)
    pad = 2.0
    pw = 1.2          # neutral edges
    accent_pw = s * 0.10  # heavier red accent edge
    x0, y0, x1, y1 = pad, pad, s - pad, s - pad
    edges = {
        "top":    ((x0, y0, x1, y0), (x0, y1, x1, y1),
                   (x0, y0, x0, y1), (x1, y0, x1, y1)),
        "bottom": ((x0, y1, x1, y1), (x0, y0, x1, y0),
                   (x0, y0, x0, y1), (x1, y0, x1, y1)),
        "left":   ((x0, y0, x0, y1), (x1, y0, x1, y1),
                   (x0, y0, x1, y0), (x0, y1, x1, y1)),
        "right":  ((x1, y0, x1, y1), (x0, y0, x0, y1),
                   (x0, y0, x1, y0), (x0, y1, x1, y1)),
    }
    accent_edge, *other_edges = edges[side]
    p.setPen(QPen(color, pw, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
    for ex0, ey0, ex1, ey1 in other_edges:
        p.drawLine(QPointF(ex0, ey0), QPointF(ex1, ey1))
    p.setPen(QPen(accent, accent_pw, Qt.SolidLine,
                  Qt.SquareCap, Qt.MiterJoin))
    p.drawLine(QPointF(accent_edge[0], accent_edge[1]),
               QPointF(accent_edge[2], accent_edge[3]))
    p.end()
    return QIcon(pm)


ICON_ACCENT = "#e60000"
TWIN_AXIS_ACCENT = ICON_ACCENT
# Default amber tone for the Line plot icon glyph.
LINE_PLOT_ACCENT = "#d49b1f"
# Per-series palette for multicolor Scatter / Bar icons. Borrowed from
# matplotlib's default cycle so the icons read as "many series".
SERIES_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c",
                  "#d62728", "#9467bd", "#8c564b"]


def math_symbol_icon(text: str, color: str, size: int = 28,
                     italic: bool = True,
                     scale: float = 0.75) -> QIcon:
    """Render *text* as a math glyph (italic serif by default) on a
    transparent square. Used for the Integrate (∫) and Differentiate
    (dx) toolbar buttons where MDI doesn't carry a clean icon for
    the operation."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    f = QFont("Cambria Math")
    if not f.exactMatch():
        # Cambria Math ships on Windows; fall back to common serifs.
        f = QFont("Times New Roman")
    f.setItalic(italic)
    f.setPixelSize(int(size * scale))
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, text)
    p.end()
    return QIcon(pm)


def with_plus_badge(base_icon: QIcon, size: int = 28) -> QIcon:
    """Overlay a themed mdi.plus-circle in the bottom-right corner of
    *base_icon* — matches the badge new_sheet_icon / new_workbook_icon
    apply via qta stacking, so custom-painted icons (New Graph, New
    Matrix Book) can carry the same "+" affordance.

    A small white halo is painted behind the badge so it stays
    legible on busy / coloured base icons (e.g. the yellow matrix
    grid) that would otherwise blend with the themed badge stroke."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    p.setRenderHint(QPainter.Antialiasing, True)
    base_icon.paint(p, 0, 0, size, size)
    if HAVE_QTA:
        try:
            bs = int(size * 0.55)
            x0 = size - bs
            y0 = size - bs
            # White halo slightly inset from the badge's outer edge.
            halo_pad = bs * 0.08
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QRectF(x0 + halo_pad, y0 + halo_pad,
                                 bs - 2 * halo_pad,
                                 bs - 2 * halo_pad))
            badge = qta.icon("mdi.plus-circle", color=active_icon_color())
            badge.paint(p, x0, y0, bs, bs)
        except Exception:  # noqa: BLE001
            pass
    p.end()
    return QIcon(pm)


def _draw_plot_axes(p: QPainter, color: QColor, x0: float, y0: float,
                    x1: float, y1: float, pw: float = 1.2):
    """Shared L-shaped axes used by the multicolor plot-type icons.
    Bottom + left edges only — matches matplotlib's default frame
    look closely enough at icon scale."""
    p.setPen(QPen(color, pw, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
    p.drawLine(QPointF(x0, y0), QPointF(x0, y1))
    p.drawLine(QPointF(x0, y1), QPointF(x1, y1))


def plot_icon_line(size: int = 22,
                   line_color: str = LINE_PLOT_ACCENT) -> QIcon:
    """Line-plot icon: themed L-axes + an amber polyline."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = float(size)
    pad = 2.5
    x0, y0, x1, y1 = pad, pad, s - pad, s - pad
    _draw_plot_axes(p, QColor(active_icon_color()), x0, y0, x1, y1)
    # Polyline within the axes area.
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
    """Scatter icon: themed L-axes + five dots in distinct colours."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = float(size)
    pad = 2.5
    x0, y0, x1, y1 = pad, pad, s - pad, s - pad
    _draw_plot_axes(p, QColor(active_icon_color()), x0, y0, x1, y1)
    # Five dots scattered inside the plot area.
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


MATRIX_BOOK_FILL = "#f4c027"  # warm yellow for the New Matrix Book icon
NEW_SHEET_GREEN = "#2ca02c"   # matplotlib-cycle green for New Sheet
NEW_WORKBOOK_BROWN = "#c08552"  # light tan brown for New Workbook
OPEN_FOLDER_YELLOW = "#ffc83d"  # warm folder yellow for Open
SAVE_GREEN = "#2ca02c"          # green for Save / Save CSV
DELETE_RED = ICON_ACCENT        # delete = accent red
COPY_BLUE = "#1f77b4"           # mpl-cycle blue for Copy
PASTE_ORANGE = "#ff7f0e"        # mpl-cycle orange for Paste


def plot_icon_3d_scatter(size: int = 22) -> QIcon:
    """3D Scatter icon — themed cube-scan glyph in mpl purple."""
    return themed_icon("mdi.cube-scan", color="#9467bd")


def plot_icon_3d_surface(size: int = 22) -> QIcon:
    """3D Surface icon — filled blue cube with a dark outline."""
    if HAVE_QTA:
        try:
            return qta.icon(
                "mdi.cube", "mdi.cube-outline",
                options=[
                    {"color": "#1f77b4", "scale_factor": 1.0},
                    {"color": active_icon_color(), "scale_factor": 1.0},
                ])
        except Exception:  # noqa: BLE001
            pass
    return themed_icon("mdi.cube-outline", color="#1f77b4")


# --- "fill inside the outline" pattern ---------------------------------
#
# Stack a filled qta glyph in an action colour under the themed outline
# variant so the fill is shaped to the icon's silhouette and the
# contour stays in the user's icon theme.

# Saturated single-glyph tints for icons without an MDI outline pair
# (Σ, ∫, Δ, eraser, etc.). Pastels wash out at small sizes when the
# contour isn't separately stroked, so these are full-strength.
TINT_BLUE = "#1f77b4"
TINT_ORANGE = "#ff7f0e"
TINT_GREEN = "#2ca02c"
TINT_RED = "#e60000"
TINT_PURPLE = "#9467bd"
TINT_BROWN = "#8b5a2b"
TINT_GREY = "#6a6a6a"

ADD_FILL = "#cce6cc"      # pale green for add / create actions
REMOVE_FILL = "#f5b8b8"   # pale red for remove / clear actions
COG_FILL = "#dcdcdc"      # neutral grey for settings / config
LAYOUT_FILL = "#d4e3f4"   # pale blue for layout / view-grid actions
PIN_FILL = "#f5b8b8"      # pale red for pin / drop-marker
PRINT_FILL = "#dcdcdc"    # neutral grey for print
IMAGE_FILL = "#cce6cc"    # pale green for save-image
COPY_FILL = "#c8dcef"     # pale blue
PASTE_FILL = "#fadcb8"    # pale orange
DELETE_FILL = "#f5b8b8"   # pale red
SAVE_FILL = "#cce6cc"     # pale green
EYE_OFF_FILL = "#dcdcdc"  # neutral grey

# Column-designation tints.
X_FILL = "#cfe2f3"     # pale blue
Y_FILL = "#fce5b6"     # pale yellow
YERR_FILL = "#d4ead0"  # pale green
XERR_FILL = "#f8d2c4"  # pale peach


def filled_outline_icon(filled_name: str, outline_name: str,
                        fill_color: str,
                        std_fallback=None,
                        scale: float = 1.0) -> QIcon:
    """Stack a filled qta glyph in *fill_color* under the matching
    outline glyph in the themed icon colour. Falls back to a tinted
    outline-only glyph when qtawesome isn't available.

    *scale* enlarges both glyphs within the icon viewport. Useful for
    pictographic glyphs (cut, paste, delete) that have more inherent
    padding than letter-in-box glyphs (alpha-x-box, alpha-y-box) and
    so look smaller when sat next to them on the same toolbar."""
    if HAVE_QTA:
        try:
            return qta.icon(
                filled_name, outline_name,
                options=[
                    {"color": fill_color, "scale_factor": scale},
                    {"color": active_icon_color(), "scale_factor": scale},
                ])
        except Exception:  # noqa: BLE001
            pass
    return themed_icon(outline_name, std_fallback, color=fill_color)


def err_designation_icon(axis: str, bg_color: str,
                         size: int = 28) -> QIcon:
    """yErr / xErr designation icon — same alpha-letter-box plate as
    column_designation_icon (so X/Y/yE/xE share one visual style),
    with "yE" / "xE" text painted over the placeholder letter.

    *axis*: ``"y"`` or ``"x"``."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = float(size)
    # Use the very same filled_outline_icon pattern as X / Y, with
    # the placeholder letter matching *axis* — keeps the rounded-corner
    # radius, border thickness and inset identical to the other
    # designation buttons.
    box = filled_outline_icon(f"mdi.alpha-{axis}-box",
                              f"mdi.alpha-{axis}-box-outline",
                              bg_color)
    box.paint(p, 0, 0, size, size)
    # Knock out the placeholder letter with a fill-matching rect so
    # the underlying y / x glyph doesn't bleed through behind the
    # "yE" / "xE" text. Keep it inside the box outline.
    knock_pad = s * 0.18
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(bg_color))
    p.drawRect(QRectF(knock_pad, knock_pad,
                      s - 2 * knock_pad,
                      s - 2 * knock_pad))
    # Two-letter label centred on the plate.
    text = f"{axis}E"
    f = QFont()
    f.setBold(True)
    f.setPixelSize(int(s * 0.42))
    p.setFont(f)
    p.setPen(QColor(active_icon_color()))
    p.drawText(QRectF(0, 0, s, s), Qt.AlignCenter, text)
    p.end()
    return QIcon(pm)


def column_designation_icon(letter: str, fill_color: str,
                            size: int = 20) -> QIcon:
    """X / Y / E column-designation icons — filled alpha-letter-box in
    *fill_color* under the themed outline glyph."""
    return filled_outline_icon(f"mdi.alpha-{letter}-box",
                               f"mdi.alpha-{letter}-box-outline",
                               fill_color)


def open_folder_icon(size: int = 20) -> QIcon:
    """Open-file icon — yellow folder body with a dark outline."""
    if HAVE_QTA:
        try:
            return qta.icon(
                "mdi.folder-open", "mdi.folder-open-outline",
                options=[
                    {"color": OPEN_FOLDER_YELLOW, "scale_factor": 1.0},
                    {"color": active_icon_color(), "scale_factor": 1.0},
                ])
        except Exception:  # noqa: BLE001
            pass
    return themed_icon("mdi.folder-open-outline", color=OPEN_FOLDER_YELLOW)


def new_workbook_icon(size: int = 20) -> QIcon:
    """Stacked icon for the New Workbook button — light-brown filled
    book with a black outline so the cover shape stays legible
    against the toolbar background, plus a themed +circle badge."""
    if HAVE_QTA:
        try:
            return qta.icon(
                "mdi.book", "mdi.book-outline", "mdi.plus-circle",
                options=[
                    {"color": NEW_WORKBOOK_BROWN, "scale_factor": 1.0},
                    {"color": active_icon_color(), "scale_factor": 1.0},
                    {"color": active_icon_color(), "scale_factor": 0.55,
                     "offset": (0.25, 0.25)},
                ])
        except Exception:  # noqa: BLE001
            pass
    return themed_icon("mdi.book-plus", color=NEW_WORKBOOK_BROWN)


def new_sheet_icon(size: int = 20) -> QIcon:
    """Stacked icon for the New Sheet button — green table glyph
    with a themed plus badge in the bottom-right corner."""
    if HAVE_QTA:
        try:
            return qta.icon(
                "mdi.table", "mdi.plus-circle",
                options=[
                    {"color": NEW_SHEET_GREEN, "scale_factor": 1.0},
                    {"color": active_icon_color(), "scale_factor": 0.55,
                     "offset": (0.25, 0.25)},
                ])
        except Exception:  # noqa: BLE001
            pass
    return themed_icon("mdi.table-plus", color=NEW_SHEET_GREEN)

_HEATMAP_PALETTE = ("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728")


def matrix_book_icon(size: int = 20,
                     fill: str = MATRIX_BOOK_FILL) -> QIcon:
    """Grid icon for New Matrix Book — yellow cells with themed grid
    lines."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, False)
    s = float(size)
    pad = 2.0
    x0, y0, x1, y1 = pad, pad, s - pad, s - pad
    n = 4
    cw = (x1 - x0) / n
    ch = (y1 - y0) / n
    # Cells.
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(fill))
    for i in range(n):
        for j in range(n):
            p.drawRect(QRectF(x0 + j * cw, y0 + i * ch, cw, ch))
    # Themed grid lines.
    p.setPen(QPen(QColor(active_icon_color()), 1.0, Qt.SolidLine,
                  Qt.SquareCap, Qt.MiterJoin))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(x0, y0, x1 - x0, y1 - y0))
    for k in range(1, n):
        p.drawLine(QPointF(x0 + k * cw, y0), QPointF(x0 + k * cw, y1))
        p.drawLine(QPointF(x0, y0 + k * ch), QPointF(x1, y0 + k * ch))
    p.end()
    return QIcon(pm)


def plot_icon_heatmap(size: int = 22) -> QIcon:
    """Heatmap icon: themed L-axes + a grid of randomly-coloured cells
    drawn from a 4-colour palette. The random seed is fixed so the
    layout is deterministic across renders."""
    import random
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, False)
    s = float(size)
    pad = 2.5
    x0, y0, x1, y1 = pad, pad, s - pad, s - pad
    _draw_plot_axes(p, QColor(active_icon_color()), x0, y0, x1, y1)
    n = 4
    inset = 1.0  # leave a hair of space between axes and grid
    gx0 = x0 + inset
    gy0 = y0
    gx1 = x1
    gy1 = y1 - inset
    cw = (gx1 - gx0) / n
    ch = (gy1 - gy0) / n
    rng = random.Random(0xBEEF)  # fixed seed → deterministic layout
    p.setPen(Qt.NoPen)
    for i in range(n):
        for j in range(n):
            col = QColor(rng.choice(_HEATMAP_PALETTE))
            p.setBrush(col)
            p.drawRect(QRectF(gx0 + j * cw, gy0 + i * ch, cw, ch))
    p.end()
    return QIcon(pm)


def zoom_icon(plus: bool, size: int = 28,
              accent: str = "") -> QIcon:
    """Magnifying-glass icon with the +/- symbol in the red accent.

    Stacks an outline-only lens (``mdi.magnify``) in the themed icon
    colour and a smaller plus or minus glyph in red, offset to sit
    inside the lens. Falls back to the themed combined glyph if
    qtawesome isn't available.
    """
    accent_color = accent or ICON_ACCENT
    if HAVE_QTA:
        try:
            sym = "mdi.plus" if plus else "mdi.minus"
            base_color = active_icon_color()
            return qta.icon(
                "mdi.magnify", sym,
                options=[
                    {"color": base_color, "scale_factor": 1.0},
                    # Shift the +/- so it sits inside the lens (lens
                    # centre is biased toward the top-left on the MDI
                    # canvas because of the handle on the bottom-right).
                    {"color": "#00e640" if plus else accent_color,
                     "scale_factor": 0.55,
                     "offset": (-0.10, -0.10)},
                ])
        except Exception:  # noqa: BLE001
            pass
    fallback = "mdi.magnify-plus-outline" if plus else "mdi.magnify-minus-outline"
    return themed_icon(fallback, color=accent_color)


def plot_icon_line_symbol(size: int = 22,
                          line_color: str = LINE_PLOT_ACCENT) -> QIcon:
    """Line+Symbol icon: amber polyline with per-vertex coloured dots."""
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


def plot_icon_step(size: int = 22,
                   line_color: str = LINE_PLOT_ACCENT) -> QIcon:
    """Step icon: themed axes + an amber step (staircase) polyline."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = float(size)
    pad = 2.5
    x0, y0, x1, y1 = pad, pad, s - pad, s - pad
    _draw_plot_axes(p, QColor(active_icon_color()), x0, y0, x1, y1)
    # Four steps — alternating up / down.
    xs = [0.05, 0.30, 0.55, 0.80, 1.00]
    ys = [0.30, 0.55, 0.40, 0.75, 0.75]
    pts = []
    for i, (xf, yf) in enumerate(zip(xs, ys)):
        x = x0 + (x1 - x0) * xf
        y = y1 - (y1 - y0) * yf
        if i > 0:
            prev = pts[-1]
            pts.append(QPointF(x, prev.y()))
        pts.append(QPointF(x, y))
    p.setPen(QPen(QColor(line_color), 2.0, Qt.SolidLine,
                  Qt.SquareCap, Qt.MiterJoin))
    for a, b in zip(pts, pts[1:]):
        p.drawLine(a, b)
    p.end()
    return QIcon(pm)


def plot_icon_stem(size: int = 22) -> QIcon:
    """Stem icon: themed axes + vertical stems with coloured dot tops."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = float(size)
    pad = 2.5
    x0, y0, x1, y1 = pad, pad, s - pad, s - pad
    _draw_plot_axes(p, QColor(active_icon_color()), x0, y0, x1, y1)
    heights = [0.40, 0.70, 0.50, 0.85, 0.60]
    n = len(heights)
    axis_pw = 1.2
    r = s * 0.09
    stem_color = QColor(active_icon_color())
    for i, h in enumerate(heights):
        fx = (i + 1) / (n + 1)
        x = x0 + (x1 - x0) * fx
        y_top = y1 - (y1 - y0) * h
        y_base = y1 - axis_pw / 2
        p.setPen(QPen(stem_color, 1.3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x, y_base), QPointF(x, y_top))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(SERIES_PALETTE[i % len(SERIES_PALETTE)]))
        p.drawEllipse(QPointF(x, y_top), r, r)
    p.end()
    return QIcon(pm)


def plot_icon_histogram(size: int = 22) -> QIcon:
    """Histogram icon: themed axes + adjacent bars in distinct colours."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = float(size)
    pad = 2.5
    x0, y0, x1, y1 = pad, pad, s - pad, s - pad
    _draw_plot_axes(p, QColor(active_icon_color()), x0, y0, x1, y1)
    # Bell-shaped histogram: 6 adjacent bars, no gaps.
    heights = [0.30, 0.55, 0.80, 0.75, 0.45, 0.25]
    n = len(heights)
    bw = (x1 - x0) / n
    axis_pw = 1.2
    p.setPen(Qt.NoPen)
    for i, h in enumerate(heights):
        p.setBrush(QColor(SERIES_PALETTE[i % len(SERIES_PALETTE)]))
        bx = x0 + i * bw
        bh = (y1 - y0) * h
        by = y1 - axis_pw / 2 - bh
        p.drawRect(QRectF(bx, by, bw, bh))
    p.end()
    return QIcon(pm)


def plot_icon_box(size: int = 22) -> QIcon:
    """Box-plot icon: themed axes + three coloured box-and-whisker glyphs."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = float(size)
    pad = 2.5
    x0, y0, x1, y1 = pad, pad, s - pad, s - pad
    _draw_plot_axes(p, QColor(active_icon_color()), x0, y0, x1, y1)
    # Three boxes side by side. Each: (q1, median, q3, lo_whisker, hi_whisker)
    # given as fractions of the plot height (1.0 = top of icon).
    boxes = [
        (0.30, 0.45, 0.65, 0.15, 0.80),
        (0.40, 0.55, 0.75, 0.20, 0.90),
        (0.25, 0.40, 0.55, 0.10, 0.70),
    ]
    n = len(boxes)
    plot_w = x1 - x0
    plot_h = y1 - y0
    bw = plot_w * 0.16
    centres = [x0 + plot_w * ((i + 1) / (n + 1)) for i in range(n)]
    for cx, (q1, med, q3, lo, hi), col in zip(centres, boxes, SERIES_PALETTE):
        y_q1 = y1 - plot_h * q1
        y_q3 = y1 - plot_h * q3
        y_med = y1 - plot_h * med
        y_lo = y1 - plot_h * lo
        y_hi = y1 - plot_h * hi
        line = QPen(QColor(col), 1.2, Qt.SolidLine,
                    Qt.SquareCap, Qt.MiterJoin)
        # Whiskers.
        p.setPen(line)
        p.drawLine(QPointF(cx, y_lo), QPointF(cx, y_q1))
        p.drawLine(QPointF(cx, y_q3), QPointF(cx, y_hi))
        # Whisker caps.
        cap = bw * 0.45
        p.drawLine(QPointF(cx - cap, y_lo), QPointF(cx + cap, y_lo))
        p.drawLine(QPointF(cx - cap, y_hi), QPointF(cx + cap, y_hi))
        # Box body.
        fill = QColor(col)
        fill.setAlpha(140)
        p.setBrush(fill)
        p.setPen(line)
        p.drawRect(QRectF(cx - bw / 2, y_q3, bw, y_q1 - y_q3))
        # Median line.
        p.setPen(QPen(QColor(col), 1.6, Qt.SolidLine,
                      Qt.SquareCap, Qt.MiterJoin))
        p.drawLine(QPointF(cx - bw / 2, y_med), QPointF(cx + bw / 2, y_med))
    p.end()
    return QIcon(pm)


def plot_icon_bar(size: int = 22) -> QIcon:
    """Bar-plot icon: themed L-axes + four bars in distinct colours."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = float(size)
    pad = 2.5
    x0, y0, x1, y1 = pad, pad, s - pad, s - pad
    _draw_plot_axes(p, QColor(active_icon_color()), x0, y0, x1, y1)
    # Four bars, ascending then descending, each its own colour.
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
        # Sit bars on top of the bottom axis stroke.
        by = y1 - axis_pw / 2 - bh
        p.drawRect(QRectF(bx, by, bw, bh))
    p.end()
    return QIcon(pm)


def twin_axis_icon(side: str, size: int = 28,
                   accent: str = "") -> QIcon:
    """Icon for the Twin X / Twin Y toolbar buttons.

    Draws a plot-frame rectangle with four short tick marks sticking
    *outward* from the named edge — the new axis being added. The
    three non-axis frame edges are drawn in the active themed icon
    colour; the axis edge and its ticks are drawn in *accent* (a
    red highlight by default) so the eye is drawn to the new axis.

    *side*: ``"top"`` (Twin X, top X axis) or ``"right"`` (Twin Y,
    right Y axis).
    """
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    color = QColor(active_icon_color())
    accent_qc = QColor(accent or TWIN_AXIS_ACCENT)
    s = float(size)
    pad = 2.0
    tick_len = s * 0.11
    frame_pw = 1.0
    axis_pw = 2.4
    tick_pw = 1.4
    n_ticks = 4

    if side == "top":
        x0, y0, x1, y1 = pad, pad + tick_len, s - pad, s - pad
    elif side == "right":
        x0, y0, x1, y1 = pad, pad, s - pad - tick_len, s - pad
    else:
        x0, y0, x1, y1 = pad, pad, s - pad, s - pad

    # Three thin frame edges (everything except the axis edge).
    thin_pen = QPen(color, frame_pw, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin)
    p.setPen(thin_pen)
    p.setBrush(Qt.NoBrush)
    if side == "top":
        p.drawLine(QPointF(x0, y1), QPointF(x1, y1))   # bottom
        p.drawLine(QPointF(x0, y0), QPointF(x0, y1))   # left
        p.drawLine(QPointF(x1, y0), QPointF(x1, y1))   # right
    elif side == "right":
        p.drawLine(QPointF(x0, y0), QPointF(x1, y0))   # top
        p.drawLine(QPointF(x0, y1), QPointF(x1, y1))   # bottom
        p.drawLine(QPointF(x0, y0), QPointF(x0, y1))   # left

    # Thick axis edge with evenly-spaced outward ticks. Edge divided
    # into (n_ticks + 1) intervals so the corner gap equals the inter-
    # tick gap.
    axis_pen = QPen(accent_qc, axis_pw, Qt.SolidLine, Qt.SquareCap,
                    Qt.MiterJoin)
    tick_pen = QPen(accent_qc, tick_pw, Qt.SolidLine, Qt.RoundCap)
    if side == "top":
        p.setPen(axis_pen)
        p.drawLine(QPointF(x0, y0), QPointF(x1, y0))
        p.setPen(tick_pen)
        L = x1 - x0
        for i in range(1, n_ticks + 1):
            t = x0 + L * i / (n_ticks + 1)
            p.drawLine(QPointF(t, y0), QPointF(t, y0 - tick_len))
    elif side == "right":
        p.setPen(axis_pen)
        p.drawLine(QPointF(x1, y0), QPointF(x1, y1))
        p.setPen(tick_pen)
        L = y1 - y0
        for i in range(1, n_ticks + 1):
            t = y0 + L * i / (n_ticks + 1)
            p.drawLine(QPointF(x1, t), QPointF(x1 + tick_len, t))
    p.end()
    return QIcon(pm)


def _draw_bar(p: QPainter, color: QColor, pw: float,
              x1: float, y1: float, x2: float, y2: float):
    """Draw the axis-edge bar with uniform pen width *pw*."""
    p.setPen(QPen(color, pw, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _draw_arrow(p: QPainter, color: QColor, pw: float,
                aw: float, ah: float,
                x1: float, y1: float, x2: float, y2: float):
    """Draw a straight arrow from (x1,y1) to (x2,y2) with a filled head."""
    import math
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1:
        return
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux

    base_x = x2 - ux * ah
    base_y = y2 - uy * ah
    p.setPen(QPen(color, pw, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(x1, y1), QPointF(base_x, base_y))

    p.setPen(Qt.NoPen)
    p.setBrush(color)
    tri = QPolygonF([
        QPointF(x2, y2),
        QPointF(base_x + nx * aw, base_y + ny * aw),
        QPointF(base_x - nx * aw, base_y - ny * aw)])
    p.drawPolygon(tri)


# ── Plot-toolbar icons (QPainter — no qtawesome dependency) ──────

def home_icon(size: int = 22) -> QIcon:
    """Simple house glyph for 'reset view'."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    color = QColor(active_icon_color())
    s = float(size)
    pad = s * 0.10
    # Roof: triangle.
    peak = QPointF(s / 2, pad)
    left = QPointF(pad, s * 0.48)
    right = QPointF(s - pad, s * 0.48)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPolygon(QPolygonF([peak, left, right]))
    # Body: rectangle with a door gap.
    bx0, bx1 = s * 0.22, s * 0.78
    by0, by1 = s * 0.44, s - pad
    p.drawRect(QRectF(bx0, by0, bx1 - bx0, by1 - by0))
    # Door cutout (transparent).
    p.setCompositionMode(QPainter.CompositionMode_Clear)
    dw = s * 0.18
    p.drawRect(QRectF(s / 2 - dw / 2, s * 0.58, dw, by1 - s * 0.58))
    p.end()
    return QIcon(pm)


def zoom_in_icon(size: int = 22) -> QIcon:
    """Magnifying-glass with a '+' sign — pure QPainter."""
    return _zoom_glass_icon(size, plus=True)


def zoom_out_icon(size: int = 22) -> QIcon:
    """Magnifying-glass with a '−' sign — pure QPainter."""
    return _zoom_glass_icon(size, plus=False)


def _zoom_glass_icon(size: int, plus: bool) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    color = QColor(active_icon_color())
    accent = QColor("#00b040") if plus else QColor(ICON_ACCENT)
    s = float(size)
    # Lens circle.
    cx, cy, r = s * 0.40, s * 0.40, s * 0.28
    pw = max(1.4, s * 0.07)
    p.setPen(QPen(color, pw))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(cx, cy), r, r)
    # Handle.
    import math
    hx = cx + r * math.cos(math.radians(45))
    hy = cy + r * math.sin(math.radians(45))
    p.setPen(QPen(color, pw * 1.3, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(hx, hy), QPointF(s * 0.88, s * 0.88))
    # +/− inside lens.
    sym_half = r * 0.50
    p.setPen(QPen(accent, pw * 0.9, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(cx - sym_half, cy), QPointF(cx + sym_half, cy))
    if plus:
        p.drawLine(QPointF(cx, cy - sym_half), QPointF(cx, cy + sym_half))
    p.end()
    return QIcon(pm)


def zoom_select_icon(size: int = 22) -> QIcon:
    """Magnifying glass with a dashed rectangle — zoom to selection."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    color = QColor(active_icon_color())
    s = float(size)
    # Lens circle.
    cx, cy, r = s * 0.40, s * 0.40, s * 0.28
    pw = max(1.4, s * 0.07)
    p.setPen(QPen(color, pw))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(cx, cy), r, r)
    # Handle.
    import math
    hx = cx + r * math.cos(math.radians(45))
    hy = cy + r * math.sin(math.radians(45))
    p.setPen(QPen(color, pw * 1.3, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(hx, hy), QPointF(s * 0.88, s * 0.88))
    # Dashed rectangle inside lens.
    rw = r * 0.55
    pen = QPen(QColor(ICON_ACCENT), max(1.0, pw * 0.7))
    pen.setDashPattern([2, 2])
    p.setPen(pen)
    p.drawRect(QRectF(cx - rw, cy - rw, rw * 2, rw * 2))
    p.end()
    return QIcon(pm)


def grid_icon(size: int = 22) -> QIcon:
    """Simple 3×3 grid glyph."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    color = QColor(active_icon_color())
    s = float(size)
    pad = s * 0.12
    pw = max(1.0, s * 0.06)
    p.setPen(QPen(color, pw, Qt.SolidLine, Qt.RoundCap))
    x0, x1 = pad, s - pad
    span = x1 - x0
    # Outer rectangle.
    p.drawRect(QRectF(x0, pad, span, span))
    # Two vertical and two horizontal inner lines.
    for i in (1, 2):
        t = x0 + span * i / 3
        p.drawLine(QPointF(t, pad), QPointF(t, x1))
        p.drawLine(QPointF(x0, pad + span * i / 3),
                   QPointF(x1, pad + span * i / 3))
    p.end()
    return QIcon(pm)


# ── Cell-formatting icons (QPainter) ──────────────────────────────
# These never depend on qtawesome — always painted manually.

def _toolbar_fg() -> QColor:
    """Return the current palette's ButtonText colour — adapts to theme."""
    app = QApplication.instance()
    if app:
        return app.palette().color(app.palette().ButtonText)
    return QColor("#333333")


def _fmt_icon(size: int, draw_fn) -> QIcon:
    """Create a *size*×*size* icon by calling *draw_fn(painter, size)*."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    draw_fn(p, size)
    p.end()
    return QIcon(pm)


def bold_icon(size: int = 28) -> QIcon:
    def _draw(p, s):
        f = QFont("Arial", int(s * 0.6))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(_toolbar_fg()))
        p.drawText(QRectF(0, 0, s, s), Qt.AlignCenter, "B")
    return _fmt_icon(size, _draw)


def italic_icon(size: int = 28) -> QIcon:
    def _draw(p, s):
        f = QFont("Arial", int(s * 0.6))
        f.setItalic(True)
        p.setFont(f)
        p.setPen(QPen(_toolbar_fg()))
        p.drawText(QRectF(0, 0, s, s), Qt.AlignCenter, "I")
    return _fmt_icon(size, _draw)


def underline_icon(size: int = 28) -> QIcon:
    def _draw(p, s):
        f = QFont("Arial", int(s * 0.6))
        f.setUnderline(True)
        p.setFont(f)
        p.setPen(QPen(_toolbar_fg()))
        p.drawText(QRectF(0, 0, s, s), Qt.AlignCenter, "U")
    return _fmt_icon(size, _draw)


def align_left_icon(size: int = 28) -> QIcon:
    def _draw(p, s):
        p.setPen(QPen(_toolbar_fg(), max(1.5, s / 14)))
        m = s * 0.2  # margin
        for i, w_frac in enumerate((1.0, 0.6, 0.8, 0.5)):
            y = m + i * (s - 2 * m) / 3
            p.drawLine(QPointF(m, y), QPointF(m + (s - 2 * m) * w_frac, y))
    return _fmt_icon(size, _draw)


def align_center_icon(size: int = 28) -> QIcon:
    def _draw(p, s):
        p.setPen(QPen(_toolbar_fg(), max(1.5, s / 14)))
        m = s * 0.2
        cx = s / 2
        for i, w_frac in enumerate((1.0, 0.6, 0.8, 0.5)):
            y = m + i * (s - 2 * m) / 3
            hw = (s - 2 * m) * w_frac / 2
            p.drawLine(QPointF(cx - hw, y), QPointF(cx + hw, y))
    return _fmt_icon(size, _draw)


def align_right_icon(size: int = 28) -> QIcon:
    def _draw(p, s):
        p.setPen(QPen(_toolbar_fg(), max(1.5, s / 14)))
        m = s * 0.2
        right = s - m
        for i, w_frac in enumerate((1.0, 0.6, 0.8, 0.5)):
            y = m + i * (s - 2 * m) / 3
            p.drawLine(QPointF(right - (s - 2 * m) * w_frac, y),
                       QPointF(right, y))
    return _fmt_icon(size, _draw)


def fill_color_icon(size: int = 28, color: str = "#ffff00") -> QIcon:
    """Paint-bucket icon with a coloured bar at the bottom."""
    def _draw(p, s):
        fg = _toolbar_fg()
        pw = max(1.2, s / 16)
        m = s * 0.18
        # "A" letter
        f = QFont("Arial", int(s * 0.45))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(fg))
        p.drawText(QRectF(0, 0, s, s * 0.72), Qt.AlignCenter, "A")
        # Coloured bar at bottom
        bar_y = s * 0.76
        bar_h = s * 0.18
        p.fillRect(QRectF(m, bar_y, s - 2 * m, bar_h), QColor(color))
        p.setPen(QPen(fg, max(1.0, s / 28)))
        p.drawRect(QRectF(m, bar_y, s - 2 * m, bar_h))
    return _fmt_icon(size, _draw)


def font_color_icon(size: int = 28, color: str = "#ff0000") -> QIcon:
    """Font colour icon — "A" with a coloured underline bar."""
    def _draw(p, s):
        fg = _toolbar_fg()
        m = s * 0.18
        f = QFont("Arial", int(s * 0.45))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(QColor(color)))
        p.drawText(QRectF(0, 0, s, s * 0.72), Qt.AlignCenter, "A")
        bar_y = s * 0.76
        bar_h = s * 0.18
        p.fillRect(QRectF(m, bar_y, s - 2 * m, bar_h), QColor(color))
    return _fmt_icon(size, _draw)


def border_icon(size: int = 28) -> QIcon:
    """Grid icon representing cell borders (All Borders)."""
    return border_preset_icon("all", size)


def border_preset_icon(preset: str, size: int = 28) -> QIcon:
    """Draw a border preset icon matching Excel's Borders menu.

    *preset*: "bottom", "top", "left", "right", "none",
              "all", "outside", "thick_outside",
              "bottom_double", "thick_bottom",
              "top_bottom", "top_thick_bottom",
              "top_double_bottom".
    """
    def _draw(p, s):
        fg = _toolbar_fg()
        light = QColor(fg)
        light.setAlpha(80)
        thin = max(1.0, s / 20)
        thick = max(2.0, s / 10)
        m = s * 0.15
        r = s - m          # right / bottom
        mid = s / 2

        # Draw faint 2×2 grid as background reference.
        p.setPen(QPen(light, 0.6))
        p.drawRect(QRectF(m, m, r - m, r - m))
        p.drawLine(QPointF(m, mid), QPointF(r, mid))
        p.drawLine(QPointF(mid, m), QPointF(mid, r))

        # Overlay the active border lines in full colour.
        solid = QPen(fg, thin)
        solid_thick = QPen(fg, thick)
        dbl_gap = thick * 0.8

        if preset == "bottom":
            p.setPen(solid)
            p.drawLine(QPointF(m, r), QPointF(r, r))

        elif preset == "top":
            p.setPen(solid)
            p.drawLine(QPointF(m, m), QPointF(r, m))

        elif preset == "left":
            p.setPen(solid)
            p.drawLine(QPointF(m, m), QPointF(m, r))

        elif preset == "right":
            p.setPen(solid)
            p.drawLine(QPointF(r, m), QPointF(r, r))

        elif preset == "none":
            pass  # only the faint grid

        elif preset == "all":
            p.setPen(solid)
            p.drawRect(QRectF(m, m, r - m, r - m))
            p.drawLine(QPointF(m, mid), QPointF(r, mid))
            p.drawLine(QPointF(mid, m), QPointF(mid, r))

        elif preset == "outside":
            p.setPen(solid)
            p.drawRect(QRectF(m, m, r - m, r - m))

        elif preset == "thick_outside":
            p.setPen(solid_thick)
            p.drawRect(QRectF(m, m, r - m, r - m))

        elif preset == "bottom_double":
            p.setPen(solid)
            p.drawLine(QPointF(m, r - dbl_gap), QPointF(r, r - dbl_gap))
            p.drawLine(QPointF(m, r), QPointF(r, r))

        elif preset == "thick_bottom":
            p.setPen(solid_thick)
            p.drawLine(QPointF(m, r), QPointF(r, r))

        elif preset == "top_bottom":
            p.setPen(solid)
            p.drawLine(QPointF(m, m), QPointF(r, m))
            p.drawLine(QPointF(m, r), QPointF(r, r))

        elif preset == "top_thick_bottom":
            p.setPen(solid)
            p.drawLine(QPointF(m, m), QPointF(r, m))
            p.setPen(solid_thick)
            p.drawLine(QPointF(m, r), QPointF(r, r))

        elif preset == "top_double_bottom":
            p.setPen(solid)
            p.drawLine(QPointF(m, m), QPointF(r, m))
            p.drawLine(QPointF(m, r - dbl_gap), QPointF(r, r - dbl_gap))
            p.drawLine(QPointF(m, r), QPointF(r, r))

    return _fmt_icon(size, _draw)


# ── Standard toolbar icons (QPainter) ─────────────────────────────

def new_file_icon(size: int = 28) -> QIcon:
    """Dog-eared page with accent + cross — matches KherveTeX style."""
    def _draw(p, s):
        fg = _toolbar_fg()
        accent = QColor("#3a78b4")
        page_bg = Qt.white
        pw = max(1.6, s / 15)
        # Page polygon with folded corner.
        p.setPen(QPen(fg, pw))
        p.setBrush(QBrush(page_bg))
        p.drawPolygon(QPolygonF([
            QPointF(s * 0.2, s * 0.1),
            QPointF(s * 0.6, s * 0.1),
            QPointF(s * 0.8, s * 0.3),
            QPointF(s * 0.8, s * 0.9),
            QPointF(s * 0.2, s * 0.9),
        ]))
        # Fold crease.
        p.drawPolyline(QPolygonF([
            QPointF(s * 0.6, s * 0.1),
            QPointF(s * 0.6, s * 0.3),
            QPointF(s * 0.8, s * 0.3),
        ]))
        # Accent + cross.
        p.setPen(QPen(accent, max(2.0, s / 12)))
        p.drawLine(QPointF(s * 0.5, s * 0.45),
                   QPointF(s * 0.5, s * 0.72))
        p.drawLine(QPointF(s * 0.36, s * 0.585),
                   QPointF(s * 0.64, s * 0.585))
    return _fmt_icon(size, _draw)


def open_file_icon(size: int = 28) -> QIcon:
    """Golden open-folder — matches KherveTeX style."""
    def _draw(p, s):
        fg = _toolbar_fg()
        pw = max(1.6, s / 15)
        p.setPen(QPen(fg, pw))
        p.setBrush(QBrush(QColor("#ffd073")))
        p.drawPolygon(QPolygonF([
            QPointF(s * 0.1, s * 0.3),
            QPointF(s * 0.35, s * 0.3),
            QPointF(s * 0.43, s * 0.2),
            QPointF(s * 0.85, s * 0.2),
            QPointF(s * 0.85, s * 0.82),
            QPointF(s * 0.1, s * 0.82),
        ]))
    return _fmt_icon(size, _draw)


def save_file_icon(size: int = 28) -> QIcon:
    """Floppy disk in accent blue — matches KherveTeX style."""
    def _draw(p, s):
        fg = _toolbar_fg()
        accent = QColor("#3a78b4")
        pw = max(1.6, s / 15)
        # Disk body.
        p.setPen(QPen(fg, pw))
        p.setBrush(QBrush(accent))
        p.drawPolygon(QPolygonF([
            QPointF(s * 0.14, s * 0.14),
            QPointF(s * 0.72, s * 0.14),
            QPointF(s * 0.86, s * 0.28),
            QPointF(s * 0.86, s * 0.86),
            QPointF(s * 0.14, s * 0.86),
        ]))
        # Label slot (top).
        p.setBrush(QBrush(Qt.white))
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(s * 0.28, s * 0.14, s * 0.34, s * 0.2))
        # Window cut-out (bottom).
        p.drawRect(QRectF(s * 0.28, s * 0.54, s * 0.44, s * 0.32))
    return _fmt_icon(size, _draw)


def undo_icon(size: int = 28) -> QIcon:
    """Curved left arrow — matches KherveTeX style."""
    def _draw(p, s):
        from PyQt5.QtGui import QPainterPath
        fg = _toolbar_fg()
        pw = max(2.2, s / 11)
        p.setPen(QPen(fg, pw, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(s * 0.2, s * 0.55)
        path.lineTo(s * 0.58, s * 0.55)
        path.cubicTo(s * 0.84, s * 0.55, s * 0.84, s * 0.2,
                     s * 0.58, s * 0.2)
        p.drawPath(path)
        # Arrowhead.
        p.setBrush(QBrush(fg))
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([
            QPointF(s * 0.08, s * 0.55),
            QPointF(s * 0.32, s * 0.38),
            QPointF(s * 0.32, s * 0.72),
        ]))
    return _fmt_icon(size, _draw)


def redo_icon(size: int = 28) -> QIcon:
    """Curved right arrow — matches KherveTeX style."""
    def _draw(p, s):
        from PyQt5.QtGui import QPainterPath
        fg = _toolbar_fg()
        pw = max(2.2, s / 11)
        p.setPen(QPen(fg, pw, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(s * 0.8, s * 0.55)
        path.lineTo(s * 0.42, s * 0.55)
        path.cubicTo(s * 0.16, s * 0.55, s * 0.16, s * 0.2,
                     s * 0.42, s * 0.2)
        p.drawPath(path)
        # Arrowhead.
        p.setBrush(QBrush(fg))
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([
            QPointF(s * 0.92, s * 0.55),
            QPointF(s * 0.68, s * 0.38),
            QPointF(s * 0.68, s * 0.72),
        ]))
    return _fmt_icon(size, _draw)


def table_design_icon(size: int = 28) -> QIcon:
    """Small coloured table grid for Table Design."""
    def _draw(p, s):
        m = s * 0.15
        r = s - m
        cols, rows = 3, 4
        cw = (r - m) / cols
        rh = (r - m) / rows
        # Header row
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#4472c4"))
        p.drawRect(QRectF(m, m, r - m, rh))
        # Banded rows
        for row in range(1, rows):
            bg = QColor("#d9e2f3") if row % 2 == 1 else QColor("#ffffff")
            p.setBrush(bg)
            p.drawRect(QRectF(m, m + row * rh, r - m, rh))
        # Grid lines
        p.setPen(QPen(QColor("#4472c4"), max(0.8, s / 28)))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(m, m, r - m, r - m))
        for col in range(1, cols):
            x = m + col * cw
            p.drawLine(QPointF(x, m), QPointF(x, r))
        for row in range(1, rows):
            y = m + row * rh
            p.drawLine(QPointF(m, y), QPointF(r, y))
    return _fmt_icon(size, _draw)


def symbol_icon(size: int = 28) -> QIcon:
    """Plus-in-grid glyph for the Insert toolbar button."""
    def _draw(p, s):
        fg = _toolbar_fg()
        pen = QPen(fg, max(1.2, s / 16))
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        # Grid square
        m = s * 0.12
        p.drawRect(QRectF(m, m, s - 2 * m, s - 2 * m))
        # Plus sign
        cx, cy = s / 2, s / 2
        arm = s * 0.22
        p.setPen(QPen(fg, max(1.6, s / 12)))
        p.drawLine(QPointF(cx - arm, cy), QPointF(cx + arm, cy))
        p.drawLine(QPointF(cx, cy - arm), QPointF(cx, cy + arm))
    return _fmt_icon(size, _draw)


def omega_icon(size: int = 28) -> QIcon:
    """Greek capital omega (Ω) glyph for the Insert Symbol button."""
    def _draw(p, s):
        fg = _toolbar_fg()
        f = QFont()
        f.setPointSizeF(max(8.0, s * 0.62))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(fg))
        p.drawText(QRectF(0, 0, s, s), int(Qt.AlignCenter), "Ω")
    return _fmt_icon(size, _draw)


def equation_icon(size: int = 28) -> QIcon:
    """Greek lowercase pi (π) glyph for the Insert Equation button."""
    def _draw(p, s):
        fg = _toolbar_fg()
        f = QFont("serif")
        f.setPointSizeF(max(8.0, s * 0.66))
        f.setItalic(True)
        p.setFont(f)
        p.setPen(QPen(fg))
        p.drawText(QRectF(0, 0, s, s), int(Qt.AlignCenter), "π")
    return _fmt_icon(size, _draw)


def merge_cells_icon(size: int = 28) -> QIcon:
    """Four cells merging into one with inward arrows."""
    def _draw(p, s):
        fg = _toolbar_fg()
        m = s * 0.15
        r = s - m
        mid = s / 2
        # 2x2 grid
        p.setPen(QPen(fg, max(1.0, s / 20)))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(m, m, r - m, r - m))
        p.setPen(QPen(fg, max(0.8, s / 24), Qt.DashLine))
        p.drawLine(QPointF(m, mid), QPointF(r, mid))
        p.drawLine(QPointF(mid, m), QPointF(mid, r))
        # Inward arrows
        p.setPen(Qt.NoPen)
        p.setBrush(fg)
        a = s * 0.08
        p.drawPolygon(QPolygonF([
            QPointF(m + a, mid), QPointF(m + a * 3, mid - a),
            QPointF(m + a * 3, mid + a)]))
        p.drawPolygon(QPolygonF([
            QPointF(r - a, mid), QPointF(r - a * 3, mid - a),
            QPointF(r - a * 3, mid + a)]))
        p.drawPolygon(QPolygonF([
            QPointF(mid, m + a), QPointF(mid - a, m + a * 3),
            QPointF(mid + a, m + a * 3)]))
        p.drawPolygon(QPolygonF([
            QPointF(mid, r - a), QPointF(mid - a, r - a * 3),
            QPointF(mid + a, r - a * 3)]))
    return _fmt_icon(size, _draw)


def image_icon(size: int = 28) -> QIcon:
    """Mountain-and-sun landscape icon for image insertion."""
    def _draw(p, s):
        fg = _toolbar_fg()
        m = s * 0.15
        r = s - m
        p.setPen(QPen(fg, max(1.0, s / 20)))
        p.setBrush(QColor("#f0f4f8"))
        p.drawRect(QRectF(m, m, r - m, r - m))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#f0c040"))
        sun_r = s * 0.08
        p.drawEllipse(QPointF(m + (r - m) * 0.7, m + (r - m) * 0.25),
                       sun_r, sun_r)
        p.setBrush(QColor("#5b9bd5"))
        p.drawPolygon(QPolygonF([
            QPointF(m, r),
            QPointF(m + (r - m) * 0.35, m + (r - m) * 0.4),
            QPointF(m + (r - m) * 0.65, r)]))
        p.setBrush(QColor("#70ad47"))
        p.drawPolygon(QPolygonF([
            QPointF(m + (r - m) * 0.3, r),
            QPointF(m + (r - m) * 0.6, m + (r - m) * 0.55),
            QPointF(r, r)]))
    return _fmt_icon(size, _draw)


def fx_icon(size: int = 28) -> QIcon:
    """f(x) icon for the function insertion toolbar button."""
    def _draw(p, s):
        f = QFont("Segoe UI", int(s * 0.38))
        f.setItalic(True)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(QColor("#3a78b4"), max(1.0, s / 18)))
        p.drawText(QRectF(0, 0, s, s), Qt.AlignCenter, "f(x)")
    return _fmt_icon(size, _draw)


def solver_icon(size: int = 28) -> QIcon:
    """Target / crosshair icon for the Solver toolbar button."""
    def _draw(p, s):
        fg = _toolbar_fg()
        mid = s / 2
        r = s * 0.35
        # Outer circle
        p.setPen(QPen(fg, max(1.2, s / 16)))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(mid, mid), r, r)
        # Inner circle
        p.drawEllipse(QPointF(mid, mid), r * 0.5, r * 0.5)
        # Crosshair lines
        m = s * 0.1
        p.drawLine(QPointF(m, mid), QPointF(s - m, mid))
        p.drawLine(QPointF(mid, m), QPointF(mid, s - m))
        # Centre dot
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#d04040"))
        p.drawEllipse(QPointF(mid, mid), s * 0.05, s * 0.05)
    return _fmt_icon(size, _draw)


def fitting_icon(size: int = 28) -> QIcon:
    """Curve-fitting icon: a fitted peak over scattered data points."""
    from PyQt5.QtGui import QPainterPath

    def _draw(p, s):
        fg = _toolbar_fg()
        # Scattered data points along a bell shape.
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#3a78b4"))
        pts = [(0.16, 0.78), (0.30, 0.62), (0.42, 0.40),
               (0.50, 0.26), (0.58, 0.40), (0.70, 0.63),
               (0.84, 0.78)]
        for fx, fy in pts:
            p.drawEllipse(QPointF(fx * s, fy * s), s * 0.045, s * 0.045)
        # Smooth fitted curve (Gaussian-like) through them.
        path = QPainterPath()
        path.moveTo(0.12 * s, 0.82 * s)
        path.cubicTo(0.34 * s, 0.80 * s, 0.40 * s, 0.20 * s,
                     0.50 * s, 0.20 * s)
        path.cubicTo(0.60 * s, 0.20 * s, 0.66 * s, 0.80 * s,
                     0.88 * s, 0.82 * s)
        p.setPen(QPen(QColor("#d04040"), max(1.4, s / 14)))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        # Baseline axis.
        p.setPen(QPen(fg, max(1.0, s / 20)))
        p.drawLine(QPointF(0.1 * s, 0.86 * s), QPointF(0.9 * s, 0.86 * s))
    return _fmt_icon(size, _draw)


def shape_icon(shape_type: str, size: int = 24) -> QIcon:
    """Glyph for an individual shape type, rendered via the shape
    registry so every gallery entry has a matching icon."""
    from . import shape_defs

    def _draw(p, s):
        fg = _toolbar_fg()
        m = s * 0.16
        rect = QRectF(m, m, s - 2 * m, s - 2 * m)
        p.setPen(QPen(fg, max(1.1, s / 16)))
        if shape_defs.is_line(shape_type):
            p.setBrush(Qt.NoBrush)
        else:
            p.setBrush(QColor("#dce8f5"))
        shape_defs.draw_shape(p, rect, shape_type)
    return _fmt_icon(size, _draw)


def shapes_button_icon(size: int = 28) -> QIcon:
    """Toolbar button glyph: overlapping rectangle + oval."""
    def _draw(p, s):
        fg = _toolbar_fg()
        p.setPen(QPen(fg, max(1.2, s / 16)))
        p.setBrush(QColor("#dce8f5"))
        p.drawRect(QRectF(s * 0.12, s * 0.34, s * 0.46, s * 0.42))
        p.setBrush(QColor("#f5e3c0"))
        p.drawEllipse(QRectF(s * 0.42, s * 0.16, s * 0.44, s * 0.44))
    return _fmt_icon(size, _draw)


def checkbox_icon(size: int = 20) -> QIcon:
    """Tick-box with a check mark."""
    def _draw(p, s):
        fg = _toolbar_fg()
        m = s * 0.15
        # Box
        p.setPen(QPen(fg, max(1.0, s / 16)))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(m, m, s - 2 * m, s - 2 * m))
        # Check mark
        p.setPen(QPen(QColor("#217346"), max(1.6, s / 10)))
        p.drawLine(QPointF(s * 0.28, s * 0.52),
                   QPointF(s * 0.44, s * 0.68))
        p.drawLine(QPointF(s * 0.44, s * 0.68),
                   QPointF(s * 0.74, s * 0.32))
    return _fmt_icon(size, _draw)


def dropdown_icon(size: int = 20) -> QIcon:
    """Rounded rect with a downward chevron (combo box)."""
    def _draw(p, s):
        fg = _toolbar_fg()
        m = s * 0.12
        # Box
        p.setPen(QPen(fg, max(1.0, s / 16)))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(m, s * 0.22, s - 2 * m, s * 0.56), 2, 2)
        # Down chevron
        p.setPen(QPen(fg, max(1.4, s / 12)))
        p.drawLine(QPointF(s * 0.55, s * 0.40),
                   QPointF(s * 0.70, s * 0.56))
        p.drawLine(QPointF(s * 0.70, s * 0.56),
                   QPointF(s * 0.85, s * 0.40))
    return _fmt_icon(size, _draw)


def emoji_icon(size: int = 20) -> QIcon:
    """Simple smiley face."""
    def _draw(p, s):
        fg = _toolbar_fg()
        m = s * 0.14
        # Circle
        p.setPen(QPen(fg, max(1.0, s / 16)))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(m, m, s - 2 * m, s - 2 * m))
        # Eyes
        dot = s * 0.06
        p.setPen(Qt.NoPen)
        p.setBrush(fg)
        p.drawEllipse(QPointF(s * 0.37, s * 0.40), dot, dot)
        p.drawEllipse(QPointF(s * 0.63, s * 0.40), dot, dot)
        # Smile arc
        from PyQt5.QtCore import QRect
        p.setPen(QPen(fg, max(1.0, s / 18)))
        p.setBrush(Qt.NoBrush)
        arc_rect = QRect(int(s * 0.28), int(s * 0.28),
                         int(s * 0.44), int(s * 0.44))
        p.drawArc(arc_rect, -30 * 16, -120 * 16)
    return _fmt_icon(size, _draw)


def comment_icon(size: int = 20) -> QIcon:
    """Speech bubble with lines."""
    def _draw(p, s):
        fg = _toolbar_fg()
        p.setPen(QPen(fg, max(1.0, s / 16)))
        p.setBrush(Qt.NoBrush)
        # Bubble body
        bx, by, bw, bh = s * 0.10, s * 0.12, s * 0.80, s * 0.54
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 3, 3)
        # Tail
        p.drawLine(QPointF(s * 0.24, by + bh),
                   QPointF(s * 0.18, s * 0.84))
        p.drawLine(QPointF(s * 0.18, s * 0.84),
                   QPointF(s * 0.40, by + bh))
        # Text lines
        p.setPen(QPen(fg, max(0.8, s / 22)))
        for yy in (0.30, 0.42, 0.52):
            p.drawLine(QPointF(s * 0.22, s * yy),
                       QPointF(s * 0.78, s * yy))
    return _fmt_icon(size, _draw)


def note_icon(size: int = 20) -> QIcon:
    """Sticky-note with folded corner."""
    def _draw(p, s):
        fg = _toolbar_fg()
        m = s * 0.12
        w = s - 2 * m
        fold = s * 0.20
        # Note body (rectangle minus folded corner)
        path = [QPointF(m, m), QPointF(m + w - fold, m),
                QPointF(m + w, m + fold), QPointF(m + w, m + w),
                QPointF(m, m + w)]
        p.setPen(QPen(fg, max(1.0, s / 16)))
        p.setBrush(QColor("#fff9c4"))
        p.drawPolygon(QPolygonF(path))
        # Fold line
        p.drawLine(QPointF(m + w - fold, m),
                   QPointF(m + w - fold, m + fold))
        p.drawLine(QPointF(m + w - fold, m + fold),
                   QPointF(m + w, m + fold))
        # Text lines
        p.setPen(QPen(fg, max(0.8, s / 22)))
        for yy in (0.38, 0.50, 0.62):
            p.drawLine(QPointF(s * 0.22, s * yy),
                       QPointF(s * 0.68, s * yy))
    return _fmt_icon(size, _draw)


def link_icon(size: int = 20) -> QIcon:
    """Two interlocking chain links."""
    def _draw(p, s):
        fg = _toolbar_fg()
        p.setPen(QPen(fg, max(1.2, s / 12)))
        p.setBrush(Qt.NoBrush)
        # Left link
        p.drawRoundedRect(QRectF(s * 0.10, s * 0.32, s * 0.42, s * 0.36),
                          s * 0.18, s * 0.18)
        # Right link
        p.drawRoundedRect(QRectF(s * 0.48, s * 0.32, s * 0.42, s * 0.36),
                          s * 0.18, s * 0.18)
    return _fmt_icon(size, _draw)
