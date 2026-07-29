"""Embedded chart — movable/resizable matplotlib plot overlaid on grid.

Charts float as child widgets of the sheet's table viewport, just like
Excel's embedded charts. They can be dragged to reposition and resized
via edge handles. Double-click opens a properties dialog.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import numpy as np

from PyQt5.QtCore import Qt, QSize, QPoint, QRect, QEvent
from PyQt5.QtGui import QBrush, QFont, QCursor, QPainter, QPen, QColor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QFormLayout, QDialogButtonBox,
    QWidget, QCheckBox, QMenu, QInputDialog, QGroupBox, QSpinBox,
    QSplitter, QTabWidget, QListWidget, QDoubleSpinBox,
    QColorDialog, QToolButton, QApplication, QMessageBox,
)

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure


class _OpaqueCanvas(FigureCanvas):
    """FigureCanvas that paints a solid white background first so that
    the grid cells underneath never bleed through."""

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.white)
        p.end()
        super().paintEvent(event)


# ── Plot defaults ───────────────────────────────────────────────────
_DEFAULT_LINEWIDTH = 1.0
_DEFAULT_MARKERSIZE = 3.0

# Resize handle size in pixels.
_HANDLE = 12  # matches layout margin for handle hit-testing

# Module-level clipboard for chart cut/copy/paste.
_chart_clipboard = None


# ── Arrow-style name lookup ────────────────────────────────────────
def _arrowstyle_name(arrow_patch):
    """Return the string name (e.g. '->') for an arrow patch's style."""
    from matplotlib.patches import ArrowStyle
    style_obj = arrow_patch.get_arrowstyle()
    # Walk the ArrowStyle registry to match by class.
    for name, cls in ArrowStyle._style_list.items():
        if isinstance(style_obj, cls):
            return name
    return "->"


# ── Time string parsing ────────────────────────────────────────────
import re as _re

_TIME_HM = _re.compile(
    r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$')           # 8:00  20:00  13:45:30
_TIME_AMPM = _re.compile(
    r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$', _re.I)   # 8am  8:30pm


def _parse_time_str(text: str):
    """Try to parse *text* as a time-of-day string.

    Returns fractional hours (float) on success, or ``None``.
    """
    text = text.strip()
    m = _TIME_HM.match(text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        s = int(m.group(3)) if m.group(3) else 0
        if 0 <= h <= 23 and 0 <= mi <= 59 and 0 <= s <= 59:
            return h + mi / 60.0 + s / 3600.0
    m = _TIME_AMPM.match(text)
    if m:
        h = int(m.group(1))
        mi = int(m.group(2)) if m.group(2) else 0
        pm = m.group(3).lower() == 'pm'
        if 1 <= h <= 12 and 0 <= mi <= 59:
            if h == 12:
                h = 0
            if pm:
                h += 12
            return h + mi / 60.0
    return None


def parse_time_column(strings, start=0, count=None):
    """Parse a list of strings as time values.

    Returns ``(hours, labels)`` where *hours* is a float ndarray of
    fractional hours (with day-wrap adjustment so the sequence is
    monotonically non-decreasing when it crosses midnight) and *labels*
    is a list of the original strings.  Returns ``(None, None)`` if
    fewer than half the values parse as valid times.
    """
    if count is None:
        count = len(strings) - start
    sub = strings[start:start + count]
    hours = []
    for s in sub:
        h = _parse_time_str(s)
        hours.append(h)

    valid = sum(1 for h in hours if h is not None)
    if valid < len(hours) / 2 or valid == 0:
        return None, None

    # Replace None entries with NaN, then adjust day wraps.
    result = np.empty(len(hours))
    day_offset = 0.0
    prev = None
    for i, h in enumerate(hours):
        if h is None:
            result[i] = np.nan
            continue
        val = h + day_offset
        if prev is not None and val < prev - 1.0:
            # Clock wrapped past midnight — add 24h.
            day_offset += 24.0
            val += 24.0
        result[i] = val
        prev = val
    return result, sub


class _RangeOverlay(QWidget):
    """Transparent overlay that draws a coloured dashed border around
    a cell range, like Excel's data-highlight rectangles.

    The overlay is interactive: corner handles allow resizing the range
    and dragging inside the overlay moves it to a different cell region.
    When the interaction finishes the owning chart re-reads data from the
    new range.
    """

    _HP = 4   # half-size of corner handle squares

    def __init__(self, parent, color_hex):
        super().__init__(parent)
        self._color = QColor(color_hex)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self.setCursor(Qt.ArrowCursor)

        # Cell range this overlay represents (set by the chart).
        self._r0 = self._c0 = self._r1 = self._c1 = 0

        # Back-references set by _apply_show_data after creation.
        self._chart = None        # EmbeddedChart
        self._axis = None         # "x" or "y"
        self._series_idx = None   # index into chart._series (for Y)

        # Drag / resize state.
        self._drag_mode = None    # "move", "tl", "tr", "bl", "br"
        self._drag_origin = None  # QPoint (global)
        self._orig_range = None   # (r0, c0, r1, c1) at press

    # ── painting ────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        hp = self._HP
        w, h = self.width(), self.height()
        # The widget is padded by hp on top, bottom, and right so
        # handles are fully visible.  Border rect sits at (0, hp).
        bx, by = 0, hp
        bw, bh = w - hp - 1, h - 2 * hp - 1
        # Semi-transparent fill inside the border rect
        fill = QColor(self._color)
        fill.setAlpha(25)
        p.fillRect(bx, by, bw + 1, bh + 1, fill)
        # Solid border
        pen = QPen(self._color, 2, Qt.SolidLine)
        p.setPen(pen)
        p.drawRect(bx, by, bw, bh)
        # Handle squares — top-right and bottom-right, fully visible
        hs = hp * 2  # full side length of handle square
        p.setPen(Qt.NoPen)
        p.setBrush(self._color)
        # Top-right: centred on (right edge, top edge) of border
        p.drawRect(bx + bw - hp, by - hp, hs, hs)
        # Bottom-right: centred on (right edge, bottom edge) of border
        p.drawRect(bx + bw - hp, by + bh - hp, hs, hs)
        p.end()

    # ── hit-testing ─────────────────────────────────────────────────
    def _handle_at(self, pos):
        """Return 'tr'|'br' if *pos* is on a handle, else None."""
        x, y = pos.x(), pos.y()
        hp = self._HP
        w, h = self.width(), self.height()
        # Border right edge x = w - hp - 1; top y = hp; bottom y = h - hp - 1
        rx = w - hp - 1
        margin = hp + 3
        if abs(x - rx) > margin:
            return None
        if abs(y - hp) <= margin:
            return "tr"
        if abs(y - (h - hp - 1)) <= margin:
            return "br"
        return None

    # ── mouse interaction ───────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            event.ignore()
            return
        handle = self._handle_at(event.pos())
        if handle:
            self._drag_mode = handle
        else:
            self._drag_mode = "move"
        self._drag_origin = event.globalPos()
        self._orig_range = (self._r0, self._c0, self._r1, self._c1)
        event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_mode is None:
            # Update cursor on hover.
            handle = self._handle_at(event.pos())
            if handle:
                self.setCursor(Qt.CrossCursor)
            else:
                self.setCursor(Qt.SizeAllCursor)
            return
        self._apply_drag(event.globalPos())
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_mode is None:
            event.ignore()
            return
        self._apply_drag(event.globalPos())
        self._commit_range()
        self._drag_mode = None
        self._drag_origin = None
        self._orig_range = None
        event.accept()

    # ── core drag logic ─────────────────────────────────────────────
    def _apply_drag(self, global_pos):
        """Translate pixel drag into cell-range changes and reposition."""
        table = self.parentWidget()  # QTableWidget viewport's parent
        if table is None or self._chart is None:
            return
        # Find the actual QTableWidget (parent of the viewport).
        while table is not None and not hasattr(table, 'rowAt'):
            table = table.parentWidget()
        if table is None:
            return

        vp = table.viewport()
        local = vp.mapFromGlobal(global_pos)
        row = table.rowAt(local.y())
        col = table.columnAt(local.x())
        if row < 0 or col < 0:
            return

        r0, c0, r1, c1 = self._orig_range
        mode = self._drag_mode

        if mode == "move":
            # Translate both rows and columns.
            origin_local = vp.mapFromGlobal(self._drag_origin)
            orig_row = table.rowAt(origin_local.y())
            orig_col = table.columnAt(origin_local.x())
            if orig_row < 0 or orig_col < 0:
                return
            dr = row - orig_row
            dc = col - orig_col
            nr0 = max(0, r0 + dr)
            nc0 = max(0, c0 + dc)
            nr1 = nr0 + (r1 - r0)
            nc1 = nc0 + (c1 - c0)
            if nr1 >= table.rowCount():
                nr1 = table.rowCount() - 1
                nr0 = nr1 - (r1 - r0)
            if nc1 >= table.columnCount():
                nc1 = table.columnCount() - 1
                nc0 = nc1 - (c1 - c0)
            self._r0, self._c0 = nr0, nc0
            self._r1, self._c1 = nr1, nc1
        elif mode == "tr":
            # Resize top edge — rows only, column locked.
            self._r0 = min(row, self._r1)
        elif mode == "br":
            # Resize bottom edge — rows only, column locked.
            self._r1 = max(row, self._r0)

        self._reposition(table)

    def _reposition(self, table):
        """Move/resize the overlay widget to match the current cell range."""
        top = table.visualRect(table.model().index(self._r0, self._c0))
        bot = table.visualRect(table.model().index(self._r1, self._c1))
        if top.isNull() or bot.isNull():
            return
        hp = self._HP
        x = top.left() - 1
        y = top.top() - 1 - hp        # padding top
        w = bot.right() - x + 2 + hp  # padding right
        h = bot.bottom() - (top.top() - 1) + 2 + 2 * hp  # padding top+bottom
        self.setGeometry(x, y, w, h)
        self.update()

    # ── commit the new range back to the chart ──────────────────────
    def _commit_range(self):
        """Push the new cell range into the chart's series and re-plot."""
        chart = self._chart
        if chart is None or chart._source_sheet is None:
            return
        sheet = chart._source_sheet

        if self._axis == "x":
            # Update X range for every series that shares this X column.
            for s in chart._series:
                xc = s.get("x_col", chart._x_col)
                if xc == self._c0 or xc == self._orig_range[1]:
                    s["x_col"] = self._c0
                    s["x_row_start"] = self._r0
                    s["x_row_end"] = self._r1
            if chart._x_col is not None:
                chart._x_col = self._c0
        elif self._axis == "y" and self._series_idx is not None:
            idx = self._series_idx
            if idx < len(chart._series):
                s = chart._series[idx]
                s["y_row_start"] = self._r0
                s["y_row_end"] = self._r1
                # X row range always follows Y so both axes cover
                # the same rows (whether X is a column or row-index).
                s["x_row_start"] = self._r0
                s["x_row_end"] = self._r1
            if idx < len(chart._y_cols):
                chart._y_cols[idx] = self._c0

        # Re-read data and refresh the chart.
        chart._replot_from_source()
        # Refresh all overlays to match new positions.
        chart._apply_show_data()


class _HandleOverlay(QWidget):
    """Transparent overlay drawn ABOVE the canvas to show selection
    handles and border.  Lives as a sibling of the canvas inside
    EmbeddedChart, raised above it so the circles are never clipped."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.hide()

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        hr = 5   # handle circle radius
        m = 12   # margin matching layout contents margins

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # Black border around the canvas area
        p.setPen(QPen(QColor("#000000"), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(m - 1, m - 1, w - m * 2 + 1, h - m * 2 + 1)

        # 8 circular handles centred on the border
        cx0, cy0 = m - 1, m - 1
        cx1, cy1 = w - m, h - m
        cxm, cym = w // 2, h // 2
        handle_pts = [
            (cx0, cy0), (cxm, cy0), (cx1, cy0),
            (cx0, cym),              (cx1, cym),
            (cx0, cy1), (cxm, cy1), (cx1, cy1),
        ]
        p.setPen(QPen(QColor("#000000"), 1.2))
        p.setBrush(QBrush(QColor("#ffffff")))
        for hx, hy in handle_pts:
            p.drawEllipse(hx - hr, hy - hr, hr * 2, hr * 2)
        p.end()


class _DraggableLine:
    """Make an axhline / axvline draggable by mouse drag on the canvas."""

    def __init__(self, line, direction, canvas):
        self._line = line
        self._dir = direction     # "horizontal" or "vertical"
        self._canvas = canvas
        self._press = None
        self._cids = [
            canvas.mpl_connect('button_press_event', self._on_press),
            canvas.mpl_connect('motion_notify_event', self._on_motion),
            canvas.mpl_connect('button_release_event', self._on_release),
        ]

    def _on_press(self, event):
        if event.inaxes is None:
            return
        if self._dir == "horizontal":
            ydata = self._line.get_ydata()[0]
            ax = self._line.axes
            ypix = ax.transData.transform((0, ydata))[1]
            epix = ax.transData.transform((0, event.ydata))[1]
            if abs(ypix - epix) > 8:
                return
            self._press = event.ydata
        else:
            xdata = self._line.get_xdata()[0]
            ax = self._line.axes
            xpix = ax.transData.transform((xdata, 0))[0]
            epix = ax.transData.transform((event.xdata, 0))[0]
            if abs(xpix - epix) > 8:
                return
            self._press = event.xdata

    def _on_motion(self, event):
        if self._press is None or event.inaxes is None:
            return
        if self._dir == "horizontal":
            self._line.set_ydata([event.ydata, event.ydata])
        else:
            self._line.set_xdata([event.xdata, event.xdata])
        self._canvas.draw_idle()

    def _on_release(self, event):
        self._press = None

    def disconnect(self):
        for cid in self._cids:
            self._canvas.mpl_disconnect(cid)


class EmbeddedChart(QWidget):
    """A matplotlib chart that lives as a child of the grid viewport."""

    def __init__(self, x, y, label, plot_type, source_sheet=None,
                 parent=None, x_col=None, y_col=None,
                 row_start=None, row_end=None):
        # Parent must be the table viewport so we paint over the grid.
        super().__init__(parent)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(pal.Window, Qt.white)
        self.setPalette(pal)
        self.setMouseTracking(True)
        self._source_sheet = source_sheet
        self._series = []
        self._fill_artists = []  # fill_between patches
        self._trendlines = []    # TrendlineInfo objects
        self._axis_props = {}    # persisted axis dialog state
        self._header_row = False  # series labels come from column headers
        self._cat_labels = None   # categorical X-axis tick labels
        self._time_x = False      # True when X axis shows time-of-day
        # Bar chart config (grouping mode, orientation, gap).
        from .bar_options import DEFAULT_BAR_CONFIG
        self._bar_config = dict(DEFAULT_BAR_CONFIG)
        # Pie chart config (angles, labels, explode, etc.).
        self._pie_config = {}
        # Source column indices for live data updates.
        self._x_col = x_col      # None means row-index X
        self._y_cols = []         # populated by add_series

        # Dragging / resizing state.
        self._drag_origin = None      # mouse pos at drag start
        self._drag_widget_pos = None  # widget pos at drag start
        self._resizing = False
        self._resize_edge = None      # which edges: combination of t/b/l/r
        self._legend_dragging = False
        self._panning = False         # axes pan mode (inside plot area)
        self._pan_enabled = False     # user must enable via right-click
        self._keep_ratio = False      # fixed aspect-ratio resize
        self._aspect_ratio = 480 / 320  # w/h ratio at creation
        self._tight_layout = True       # tight layout on by default
        self._annotations = []            # user text/arrow/line annotations
        self._selected_ann_idx = -1       # index of selected annotation
        self._ann_select_artists = []     # visual selection markers
        self._ann_handles = []            # endpoint handle dicts
        self._ann_dragging_handle = None  # handle being dragged
        self._ann_body_drag = None        # body-drag origin for arrows/lines

        self.setMinimumSize(240, 180)
        self.resize(480, 320)
        self.setFocusPolicy(Qt.StrongFocus)

        # ── Layout ──────────────────────────────────────────────────
        _m = 12  # margin for selection handles
        layout = QVBoxLayout(self)
        layout.setContentsMargins(_m, _m, _m, _m)
        layout.setSpacing(0)

        # Matplotlib figure — no title bar, just the plot.
        self._figure = Figure(figsize=(5, 3), dpi=100,
                              facecolor='white')
        self._figure.patch.set_alpha(1.0)
        self._canvas = _OpaqueCanvas(self._figure)
        self._canvas.setMouseTracking(True)
        if plot_type == "3D Surface":
            from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
            self._ax = self._figure.add_subplot(111, projection='3d')
        else:
            self._ax = self._figure.add_subplot(111)
        self._ax.set_facecolor('white')
        self._ax.patch.set_alpha(1.0)
        layout.addWidget(self._canvas, stretch=1)

        # Selection-handle overlay — sits above canvas in z-order.
        self._handle_overlay = _HandleOverlay(self)

        # No toolbar — right-click menu provides all actions.

        # Intercept mouse events on canvas for drag/resize while
        # letting matplotlib handle clicks inside the axes area.
        self._canvas.installEventFilter(self)

        # Double-click on labels/spines opens edit dialogs.
        self._canvas.mpl_connect("button_press_event", self._on_canvas_click)
        # Annotation endpoint dragging.
        self._canvas.mpl_connect("motion_notify_event",
                                  self._on_ann_motion)
        self._canvas.mpl_connect("button_release_event",
                                  self._on_ann_release)

        # Add the initial series.
        self.add_series(x, y, label, plot_type, x_col=x_col, y_col=y_col,
                        row_start=row_start, row_end=row_end)

        if self._tight_layout:
            try:
                self._figure.set_layout_engine("tight")
            except Exception:
                try:
                    self._figure.tight_layout()
                except Exception:
                    pass
        else:
            self._figure.subplots_adjust(
                left=0.15, right=0.95, top=0.92, bottom=0.15)

        # Style the frame — no border by default; paintEvent draws
        # selection border only when chart is selected.
        self.setStyleSheet(
            "EmbeddedChart { background: white; }")
        self.setAutoFillBackground(True)

        self.show()
        self.raise_()

    # ── Series management ───────────────────────────────────────────
    def add_series(self, x, y, label, plot_type="Line",
                   x_col=None, y_col=None,
                   row_start=None, row_end=None):
        ax = self._ax
        artist = self._plot_one(ax, x, y, label, plot_type)

        s = {
            "x": x, "y": y, "label": label,
            "plot_type": plot_type, "artist": artist,
            "x_col": x_col,
        }
        if row_start is not None:
            s["x_row_start"] = row_start
            s["y_row_start"] = row_start
        if row_end is not None:
            s["x_row_end"] = row_end
            s["y_row_end"] = row_end
        self._series.append(s)
        if y_col is not None:
            self._y_cols.append(y_col)

        # Bar series need coordinated redraw for grouped offsets.
        if plot_type == "Bar":
            self._redraw_bars()

        if plot_type not in ("Heatmap", "3D Surface"):
            self._install_legend(ax)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        self._canvas.draw_idle()

    def _update_artist(self, s, x, y):
        """Update the artist for series *s* with new data.

        Line2D uses set_data.  Scatter PathCollection uses set_offsets
        with a manual data-limit update so relim() sees the new extent.
        Everything else (bar, stem, …) is removed and re-created with
        visual properties preserved.
        """
        from matplotlib.lines import Line2D
        from matplotlib.collections import PathCollection
        artist = s.get("artist")
        if artist is None:
            return
        if isinstance(artist, Line2D):
            artist.set_data(x, y)
        elif isinstance(artist, PathCollection):
            artist.set_offsets(np.column_stack([x, y]))
            # Manually update axes data limits so relim() works.
            if len(x) and len(y):
                ax = self._ax
                ax.update_datalim(
                    np.column_stack([x, y]))
        else:
            from matplotlib.container import BarContainer
            if isinstance(artist, BarContainer):
                # Bar series — update data in the dict and let
                # _redraw_bars handle the coordinated redraw.
                s["x"], s["y"] = x, y
                self._redraw_bars()
                return
            # Stem, etc. — snapshot face colour, remove, re-plot.
            old_color = None
            try:
                if hasattr(artist, 'get_facecolor'):
                    fc = artist.get_facecolor()
                    if hasattr(fc, '__len__') and len(fc) > 0:
                        old_color = fc[0]
            except Exception:
                pass
            try:
                artist.remove()
            except Exception:
                pass
            new = self._plot_one(self._ax, x, y, s["label"],
                                 s["plot_type"])
            if old_color is not None and new is not None:
                try:
                    if hasattr(new, 'set_facecolor'):
                        new.set_facecolor(old_color)
                except Exception:
                    pass
            s["artist"] = new

    def _redraw_bars(self):
        """Recalculate and redraw all bar-type series.

        Bar charts need coordinated layout (grouped offsets or stacked
        bottoms), so whenever a bar series is added, removed, or
        modified all bars must be redrawn together.
        """
        from .bar_options import plot_bars
        has_bars = any(s.get("plot_type") == "Bar"
                       and not s.get("is_trendline")
                       for s in self._series)
        if not has_bars:
            return
        # Collect current face colours so the redraw preserves them.
        from matplotlib.container import BarContainer
        from matplotlib.colors import to_hex
        colors = []
        for s in self._series:
            if s.get("plot_type") != "Bar" or s.get("is_trendline"):
                continue
            a = s.get("artist")
            c = None
            # Prefer explicitly saved fill_color in bar props.
            bp = s.get("bar", {})
            if bp.get("fill_color"):
                c = bp["fill_color"]
            elif isinstance(a, BarContainer) and a.patches:
                try:
                    c = to_hex(a.patches[0].get_facecolor())
                except Exception:
                    pass
            colors.append(c)
        # Fill None entries from the default cycle.
        from .bar_options import _DEFAULT_COLORS
        for i, c in enumerate(colors):
            if c is None:
                colors[i] = _DEFAULT_COLORS[i % len(_DEFAULT_COLORS)]
        plot_bars(self._ax, self._series, self._bar_config,
                  _colors=colors)
        # Refresh legend.
        if self._ax.get_legend() is not None:
            self._install_legend()
        self._canvas.draw_idle()

    def _redraw_pie(self):
        """Redraw the pie/doughnut chart from stored config."""
        from .pie_options import redraw_pie, PIE_TYPES
        if not self._series:
            return
        if self._series[0].get("plot_type") not in PIE_TYPES:
            return
        redraw_pie(self)

    @staticmethod
    def _plot_one(ax, x, y, label, plot_type):
        """Plot a single series and return the artist."""
        if plot_type == "Line":
            lines = ax.plot(x, y, label=label,
                            linewidth=_DEFAULT_LINEWIDTH)
            return lines[0] if lines else None
        elif plot_type == "Scatter":
            return ax.scatter(x, y, label=label,
                              s=_DEFAULT_MARKERSIZE ** 2)
        elif plot_type == "Line+Symbol":
            lines = ax.plot(x, y, 'o-', label=label,
                            linewidth=_DEFAULT_LINEWIDTH,
                            markersize=_DEFAULT_MARKERSIZE)
            return lines[0] if lines else None
        elif plot_type == "Bar":
            return ax.bar(x, y, label=label)
        elif plot_type == "Step":
            lines = ax.step(x, y, label=label, where='mid',
                            linewidth=_DEFAULT_LINEWIDTH)
            return lines[0] if lines else None
        elif plot_type == "Stem":
            container = ax.stem(x, y, label=label)
            return container
        elif plot_type == "Histogram":
            _, _, patches = ax.hist(y, bins='auto', label=label,
                                    alpha=0.7)
            return patches
        elif plot_type == "Box":
            bp = ax.boxplot([y], labels=[label], patch_artist=True)
            return bp
        elif plot_type == "Heatmap":
            # For heatmap, y is expected to be a 2D array; if 1D,
            # reshape into a single-row matrix.
            data = np.atleast_2d(np.asarray(y))
            im = ax.imshow(data, aspect='auto', origin='lower',
                           cmap='viridis')
            return im
        elif plot_type in ("Pie", "Doughnut", "3D Pie"):
            # Pie charts are drawn by pie_options.plot_pie;
            # _plot_one just returns a placeholder — the real draw
            # happens in _redraw_pie or from_dict.
            from .pie_options import plot_pie
            result = plot_pie(ax, y, None, {}, plot_type)
            if result is not None:
                return result[0]  # list of Wedge patches
            return None
        elif plot_type == "3D Surface":
            # 3D surface expects y to be a 2D array (Z matrix).
            # x is ignored here; X/Y are generated from shape.
            data = np.atleast_2d(np.asarray(y))
            rows, cols = data.shape
            X = np.arange(cols)
            Y = np.arange(rows)
            X, Y = np.meshgrid(X, Y)
            surf = ax.plot_surface(X, Y, data, cmap='viridis',
                                   edgecolor='none', alpha=0.9)
            return surf
        else:
            lines = ax.plot(x, y, label=label)
            return lines[0] if lines else None

    def _rebuild_axes(self, want_3d):
        """Swap the axes between 2-D and 3-D projections.

        Returns True when a new axes was created — every artist on
        the old axes (including annotations) is discarded and the
        caller must re-plot all series.  Returns False when the
        current projection already matches.
        """
        is_3d = hasattr(self._ax, 'get_zlim')
        if is_3d == bool(want_3d):
            return False
        from .heatmap_options import _remove_colorbar, _remove_annotations
        _remove_colorbar(self)
        _remove_annotations(self)
        self._heatmap_orig_pos = None
        # Annotation artists live on the old axes and die with it.
        self._annotations = []
        self._selected_ann_idx = -1
        self._ann_select_artists = []
        self._ann_handles = []
        self._figure.clf()
        if want_3d:
            from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
            self._ax = self._figure.add_subplot(111, projection='3d')
        else:
            self._ax = self._figure.add_subplot(111)
        self._ax.set_facecolor('white')
        self._ax.patch.set_alpha(1.0)
        if self._tight_layout:
            try:
                self._figure.set_layout_engine("tight")
            except Exception:
                pass
        return True

    def change_series_type(self, series_idx, new_plot_type):
        """Remove the old artist and replot a series with a new type.

        Returns True on success, False when the change is impossible
        (a 2-D matrix series can only be Heatmap or 3D Surface).
        """
        if series_idx < 0 or series_idx >= len(self._series):
            return False
        s = self._series[series_idx]
        if s["plot_type"] == new_plot_type:
            return True
        matrix_types = ("Heatmap", "3D Surface")
        if (np.asarray(s["y"]).ndim > 1
                and new_plot_type not in matrix_types):
            return False
        old_type = s["plot_type"]

        # Moving to or from 3D Surface changes the axes projection.
        if self._rebuild_axes(new_plot_type == "3D Surface"):
            s["plot_type"] = new_plot_type
            # The old axes is gone — re-plot every series fresh.
            for t in self._series:
                try:
                    t["artist"] = self._plot_one(
                        self._ax, np.asarray(t["x"]),
                        np.asarray(t["y"]), t["label"],
                        t["plot_type"])
                except Exception:
                    t["artist"] = None
        else:
            old_artist = s.get("artist")
            # Remove old artist from axes.
            if old_artist is not None:
                try:
                    old_artist.remove()
                except Exception:
                    # Some artist types (stem, bar containers) need
                    # per-child removal.
                    if hasattr(old_artist, '__iter__'):
                        for child in old_artist:
                            try:
                                child.remove()
                            except Exception:
                                pass
            # Leaving Heatmap: drop its colorbar and annotations.
            if old_type == "Heatmap":
                from .heatmap_options import (_remove_colorbar,
                                              _remove_annotations)
                _remove_colorbar(self)
                _remove_annotations(self)
            # Replot with new type.
            x, y = np.asarray(s["x"]), np.asarray(s["y"])
            new_artist = self._plot_one(
                self._ax, x, y, s["label"], new_plot_type)
            s["artist"] = new_artist
            s["plot_type"] = new_plot_type
        # If changing to or from Bar, recalculate bar layout.
        if new_plot_type == "Bar" or old_type == "Bar":
            self._redraw_bars()
        # Carry stored options (colormap, colorbar, …) over so the
        # chart keeps its configuration across type switches.
        if series_idx == 0 and new_plot_type == "Heatmap":
            from .heatmap_options import (redraw_heatmap,
                                          DEFAULT_HEATMAP_CONFIG)
            cfg = (getattr(self, '_heatmap_config', None)
                   or dict(DEFAULT_HEATMAP_CONFIG))
            self._heatmap_config = cfg
            redraw_heatmap(self, cfg)
        elif series_idx == 0 and new_plot_type == "3D Surface":
            from .heatmap_options import (redraw_surface,
                                          DEFAULT_SURFACE3D_CONFIG)
            cfg = (getattr(self, '_surface3d_config', None)
                   or dict(DEFAULT_SURFACE3D_CONFIG))
            self._surface3d_config = cfg
            redraw_surface(self, cfg)
        # Refresh legend (skip for heatmap / 3-D surface).
        if new_plot_type not in matrix_types:
            self._install_legend()
        else:
            old_leg = self._ax.get_legend()
            if old_leg is not None:
                old_leg.remove()
        self._canvas.draw_idle()
        return True

    # ── Programmatic axis editing (used by the AI assistant) ──────────
    def set_axis_options(self, *, invert_x=None, invert_y=None,
                         x_scale=None, y_scale=None, title=None,
                         x_label=None, y_label=None, grid=None):
        """Apply axis/labels changes live and return the applied set.

        Every argument is optional; only the ones provided are changed.
        ``invert_x``/``invert_y`` set the *absolute* desired state.
        ``x_scale``/``y_scale`` accept matplotlib scale names
        ("linear", "log", "symlog", "logit").
        """
        ax = self._ax
        applied = {}
        if x_scale is not None:
            ax.set_xscale(x_scale)
            applied["x_scale"] = x_scale
        if y_scale is not None:
            ax.set_yscale(y_scale)
            applied["y_scale"] = y_scale
        if invert_x is not None:
            if bool(invert_x) != ax.xaxis_inverted():
                ax.invert_xaxis()
            applied["invert_x"] = bool(invert_x)
        if invert_y is not None:
            if bool(invert_y) != ax.yaxis_inverted():
                ax.invert_yaxis()
            applied["invert_y"] = bool(invert_y)
        if title is not None:
            ax.set_title(title)
            applied["title"] = title
        if x_label is not None:
            ax.set_xlabel(x_label)
            applied["x_label"] = x_label
        if y_label is not None:
            ax.set_ylabel(y_label)
            applied["y_label"] = y_label
        if grid is not None:
            ax.grid(bool(grid))
            applied["grid"] = bool(grid)
        # Keep any dialog-saved axis state in sync so a later open of the
        # Axis Properties dialog reflects these changes.
        ap = self._axis_props or {}
        if "x" in ap:
            ap["x"]["invert"] = ax.xaxis_inverted()
            ap["x"]["scale"] = ax.get_xscale()
        if "y" in ap:
            ap["y"]["invert"] = ax.yaxis_inverted()
            ap["y"]["scale"] = ax.get_yscale()
        self._canvas.draw_idle()
        return applied

    # ── Serialisation ────────────────────────────────────────────────
    def to_dict(self):
        """Return a JSON-safe dict capturing chart state."""
        ax = self._ax
        series = []
        real_idx = 0
        for s in self._series:
            # Trendline series are saved via the trendlines list
            if s.get("is_trendline"):
                continue
            sd = {
                "x": list(s["x"]),
                "y": list(s["y"]),
                "label": s["label"],
                "plot_type": s["plot_type"],
            }
            # Line / marker visual properties.
            artist = s.get("artist")
            if artist is not None:
                from matplotlib.colors import to_hex
                from matplotlib.collections import PathCollection
                from matplotlib.container import BarContainer
                if isinstance(artist, BarContainer):
                    # Bar — save face colour from first patch.
                    if artist.patches:
                        try:
                            sd["color"] = to_hex(
                                artist.patches[0].get_facecolor())
                        except Exception:
                            pass
                    if hasattr(artist, 'get_visible'):
                        if not artist.get_visible():
                            sd["visible"] = False
                elif isinstance(artist, PathCollection):
                    # Scatter — save face/edge colors and sizes.
                    try:
                        fc = artist.get_facecolors()
                        if len(fc) > 0:
                            sd["color"] = to_hex(fc[0])
                            sd["markerfacecolor"] = to_hex(fc[0])
                    except Exception:
                        pass
                    try:
                        ec = artist.get_edgecolors()
                        if len(ec) > 0:
                            sd["markeredgecolor"] = to_hex(ec[0])
                    except Exception:
                        pass
                    try:
                        sizes = artist.get_sizes()
                        if len(sizes) > 0:
                            sd["markersize"] = float(sizes[0] ** 0.5)
                    except Exception:
                        pass
                    # Scatter marker shape (stored in series dict).
                    if s.get("marker"):
                        sd["marker"] = s["marker"]
                else:
                    # Line2D artist.
                    if hasattr(artist, 'get_linestyle'):
                        sd["linestyle"] = artist.get_linestyle()
                    if hasattr(artist, 'get_linewidth'):
                        sd["linewidth"] = artist.get_linewidth()
                    if hasattr(artist, 'get_color'):
                        c = artist.get_color()
                        if isinstance(c, str):
                            sd["color"] = c
                        elif hasattr(c, '__len__') and len(c) >= 3:
                            sd["color"] = to_hex(c)
                    if hasattr(artist, 'get_marker'):
                        sd["marker"] = str(artist.get_marker())
                    if hasattr(artist, 'get_markersize'):
                        sd["markersize"] = artist.get_markersize()
                    if hasattr(artist, 'get_markerfacecolor'):
                        c = artist.get_markerfacecolor()
                        if isinstance(c, str):
                            sd["markerfacecolor"] = c
                        elif hasattr(c, '__len__') and len(c) >= 3:
                            sd["markerfacecolor"] = to_hex(c)
                    if hasattr(artist, 'get_markeredgecolor'):
                        c = artist.get_markeredgecolor()
                        if isinstance(c, str):
                            sd["markeredgecolor"] = c
                        elif hasattr(c, '__len__') and len(c) >= 3:
                            sd["markeredgecolor"] = to_hex(c)
                # Visibility (works for both types).
                if hasattr(artist, 'get_visible'):
                    if not artist.get_visible():
                        sd["visible"] = False
            # Fill properties.
            fm = s.get("fill_mode", "none")
            if fm != "none":
                sd["fill_mode"] = fm
                sd["fill_target"] = s.get("fill_target", 0)
                sd["fill_color"] = s.get("fill_color", "#1f77b4")
                sd["fill_alpha"] = s.get("fill_alpha", 0.3)
            # Bar-specific per-series properties.
            bar_p = s.get("bar")
            if bar_p:
                sd["bar"] = dict(bar_p)
            # Per-series X column (if different from chart default).
            if s.get("x_col") is not None:
                sd["x_col"] = s["x_col"]
            # Per-series Y column (for template round-trip).
            if real_idx < len(self._y_cols):
                sd["y_col"] = self._y_cols[real_idx]
            # Row range info for data tab persistence.
            for rk in ("x_row_start", "x_row_end",
                        "y_row_start", "y_row_end"):
                if rk in s:
                    sd[rk] = int(s[rk])
            series.append(sd)
            real_idx += 1
        d = {
            "series": series,
            "pos_x": self.x(),
            "pos_y": self.y(),
            "width": self.width(),
            "height": self.height(),
            "title": ax.get_title(),
            "xlabel": ax.get_xlabel(),
            "ylabel": ax.get_ylabel(),
            "xscale": ax.get_xscale(),
            "yscale": ax.get_yscale(),
            "x_inverted": bool(ax.xaxis_inverted()),
            "y_inverted": bool(ax.yaxis_inverted()),
            "grid": (ax.xaxis.get_gridlines()[0].get_visible()
                     if ax.xaxis.get_gridlines() else False),
            "top_label": getattr(self, '_top_label_text', ''),
            "top_label_offset": getattr(self, '_top_label_offset', 0.08),
            "right_label": getattr(self, '_right_label_text', ''),
            "right_label_offset": getattr(self, '_right_label_offset', 0.08),
        }
        if self._axis_props:
            d["axis_props"] = self._axis_props
        # Bar chart config.
        from .bar_options import DEFAULT_BAR_CONFIG
        if self._bar_config != DEFAULT_BAR_CONFIG:
            d["bar_config"] = dict(self._bar_config)
        # Pie chart config.
        if self._pie_config:
            # Filter out non-serialisable values (like RGBA tuples).
            pc = {}
            for k, v in self._pie_config.items():
                if k == "colors":
                    from matplotlib.colors import to_hex
                    try:
                        pc["colors"] = [
                            to_hex(c) if not isinstance(c, str) else c
                            for c in v]
                    except Exception:
                        pass
                elif isinstance(v, (str, int, float, bool, type(None),
                                    list)):
                    pc[k] = v
            if pc:
                d["pie_config"] = pc
        hmc = getattr(self, '_heatmap_config', None)
        if hmc:
            d["heatmap_config"] = hmc
        s3c = getattr(self, '_surface3d_config', None)
        if s3c:
            d["surface3d_config"] = s3c
        gp = getattr(self, '_general_props', None)
        if gp:
            # Keep figure size in sync with actual widget dimensions.
            gp["fig_width"] = self.width()
            gp["fig_height"] = self.height()
            d["general_props"] = gp
        if self._header_row:
            d["header_row"] = True
        if self._keep_ratio:
            d["keep_ratio"] = True
        d["tight_layout"] = self._tight_layout
        if not self._tight_layout:
            sp = self._figure.subplotpars
            d["subplot_margins"] = {
                "left": sp.left, "right": sp.right,
                "top": sp.top, "bottom": sp.bottom,
            }
        # Always read legend font from the actual matplotlib legend.
        leg = self._ax.get_legend()
        if leg and leg.get_visible():
            d["legend_visible"] = True
            try:
                texts = leg.get_texts()
                if texts:
                    d["legend_font"] = texts[0].get_fontfamily()[0]
                    d["legend_size"] = int(texts[0].get_fontsize())
            except Exception:
                pass
            # Save extended legend properties if available.
            lp = getattr(self, '_legend_props', None)
            if lp:
                d["legend_props"] = lp
        else:
            d["legend_visible"] = False
        if self._x_col is not None:
            d["x_col"] = self._x_col
        if self._y_cols:
            d["y_cols"] = self._y_cols
        if self._cat_labels:
            d["cat_labels"] = self._cat_labels
        if self._time_x:
            d["time_x"] = True
        # Trendlines
        if self._trendlines:
            d["trendlines"] = [t.to_dict() for t in self._trendlines]
        # Annotations
        if self._annotations:
            ann_list = []
            for a in self._annotations:
                ad = {"type": a["type"]}
                if a["type"] == "text":
                    artist = a["artist"]
                    ad["text"] = artist.get_text()
                    ad["xy"] = list(artist.xy)
                    ad["fontsize"] = float(artist.get_fontsize())
                    ad["fontweight"] = str(artist.get_fontweight())
                    ad["fontstyle"] = str(artist.get_fontstyle())
                    ad["color"] = artist.get_color()
                    ad["rotation"] = float(artist.get_rotation())
                    bp = artist.get_bbox_patch()
                    if bp is not None:
                        from matplotlib.colors import to_hex
                        fc = bp.get_facecolor()
                        ad["bbox_fc"] = to_hex(fc[:3])
                        ad["bbox_alpha"] = float(fc[3]) if len(fc) > 3 else 1.0
                        ad["bbox_style"] = type(bp.get_boxstyle()).__name__.lower()
                elif a["type"] == "arrow":
                    artist = a["artist"]
                    ad["text"] = artist.get_text()
                    ad["xy"] = list(artist.xy)
                    ad["xytext"] = list(artist.get_position())
                    ap = getattr(artist, "arrow_patch", None)
                    if ap is not None:
                        from matplotlib.colors import to_hex
                        ad["arrow_color"] = to_hex(ap.get_edgecolor()[:3])
                        ad["arrow_lw"] = float(ap.get_linewidth())
                        ad["arrow_ls"] = ap.get_linestyle()
                        ad["arrow_style"] = _arrowstyle_name(ap)
                elif a["type"] == "line":
                    artist = a["artist"]
                    # New-style: finite line segment (Annotation object).
                    if hasattr(artist, 'xy') and hasattr(artist, 'get_position'):
                        ad["xy"] = list(artist.xy)
                        ad["xytext"] = list(artist.get_position())
                        ap = getattr(artist, "arrow_patch", None)
                        if ap is not None:
                            from matplotlib.colors import to_hex
                            ad["arrow_color"] = to_hex(
                                ap.get_edgecolor()[:3])
                            ad["arrow_lw"] = float(ap.get_linewidth())
                            ad["arrow_ls"] = ap.get_linestyle()
                    else:
                        # Legacy axhline/axvline — save for compat.
                        ad["direction"] = a.get("direction", "horizontal")
                        if ad["direction"] == "horizontal":
                            ad["value"] = float(artist.get_ydata()[0])
                        else:
                            ad["value"] = float(artist.get_xdata()[0])
                ann_list.append(ad)
            d["annotations"] = ann_list
        return d

    # ── Plot template support ──────────────────────────────────────────

    def to_template(self) -> dict:
        """Export chart config as a reusable template (no raw data)."""
        d = self.to_dict()
        # Strip raw data arrays — keep column mapping and visual props.
        for s in d.get("series", []):
            s.pop("x", None)
            s.pop("y", None)
        # Strip fitted trendline parameters (model config is kept).
        for t in d.get("trendlines", []):
            t.pop("params", None)
            t.pop("equation", None)
            t.pop("gof", None)
        # Strip absolute position — templates shouldn't fix placement.
        d.pop("pos_x", None)
        d.pop("pos_y", None)
        return d

    @classmethod
    def from_template(cls, tpl: dict, source_sheet, parent,
                      selection=None):
        """Create a chart from a template, pulling live data from *sheet*.

        *selection* is an optional ``QTableWidgetSelectionRange``.  If
        provided the row range is taken from it; otherwise the template's
        stored row range is used.
        """
        import numpy as np
        series_defs = tpl.get("series", [])
        if not series_defs:
            return None

        chart_x_col = tpl.get("x_col")

        def _col_data(sheet, col, r0, r1):
            arr = sheet.numeric_column(col)
            return arr[r0:r1 + 1] if arr is not None else np.array([])

        chart = None
        for i, sd in enumerate(series_defs):
            x_col = sd.get("x_col", chart_x_col)
            y_col = sd.get("y_col")
            if y_col is None:
                continue

            if selection is not None:
                r0, r1 = selection.topRow(), selection.bottomRow()
            else:
                r0 = sd.get("x_row_start", sd.get("y_row_start", 0))
                r1 = sd.get("x_row_end", sd.get("y_row_end", 99))

            if x_col is not None:
                x = _col_data(source_sheet, x_col, r0, r1)
            else:
                x = np.arange(r1 - r0 + 1, dtype=float)
            y = _col_data(source_sheet, y_col, r0, r1)

            # Mask NaN.
            mask = ~(np.isnan(x) | np.isnan(y))
            x, y = x[mask], y[mask]
            if len(x) == 0:
                continue

            label = sd.get("label", f"Series {i + 1}")
            pt = sd.get("plot_type", "Line")

            if chart is None:
                chart = cls(x, y, label, pt, source_sheet, parent,
                            x_col=x_col, y_col=y_col,
                            row_start=r0, row_end=r1)
            else:
                chart.add_series(x, y, label, pt,
                                 x_col=x_col, y_col=y_col,
                                 row_start=r0, row_end=r1)

        if chart is None:
            return None

        # Apply size.
        w = tpl.get("width", 480)
        h = tpl.get("height", 320)
        chart.resize(w, h)
        if tpl.get("keep_ratio"):
            chart._keep_ratio = True
            chart._aspect_ratio = w / max(h, 1)

        # Tight layout / subplot margins.
        if tpl.get("tight_layout") is True:
            chart._tight_layout = True
        elif tpl.get("tight_layout") is False:
            chart._tight_layout = False
            try:
                chart._figure.set_layout_engine("none")
            except Exception:
                pass
            margins = tpl.get("subplot_margins")
            if margins:
                chart._figure.subplots_adjust(**margins)

        ax = chart._ax
        ax.set_title(tpl.get("title", ""))
        ax.set_xlabel(tpl.get("xlabel", "X"))
        ax.set_ylabel(tpl.get("ylabel", "Y"))

        # Secondary labels.
        for side, key in (("top", "top_label"), ("right", "right_label")):
            lbl = tpl.get(key, "")
            if lbl:
                setattr(chart, f'_{side}_label_text', lbl)
                from .axis_dialog import AxisPropertiesDialog
                AxisPropertiesDialog._set_secondary_label(
                    chart, side, lbl, {"fontsize": 10})

        # Axis properties.
        axis_props = tpl.get("axis_props")
        if axis_props:
            chart._axis_props = axis_props
            from .axis_dialog import AxisPropertiesDialog
            for direction, st in axis_props.items():
                AxisPropertiesDialog._apply_dir_static(chart, direction, st)
        else:
            try:
                ax.set_xscale(tpl.get("xscale", "linear"))
                ax.set_yscale(tpl.get("yscale", "linear"))
            except ValueError:
                pass
            ax.grid(tpl.get("grid", False))
        # Enforce saved axis inversion (idempotent).
        if ("x_inverted" in tpl
                and bool(tpl["x_inverted"]) != ax.xaxis_inverted()):
            ax.invert_xaxis()
        if ("y_inverted" in tpl
                and bool(tpl["y_inverted"]) != ax.yaxis_inverted()):
            ax.invert_yaxis()

        # Column mapping.
        chart._x_col = chart_x_col
        chart._y_cols = tpl.get("y_cols", [])
        if chart._source_sheet and chart._y_cols:
            chart._source_sheet.data_changed.connect(
                chart._on_data_changed)

        # Visual properties per series (reuse from_dict logic).
        from matplotlib.collections import PathCollection
        for idx, sd in enumerate(series_defs):
            if idx >= len(chart._series):
                break
            artist = chart._series[idx].get("artist")
            if artist is not None:
                is_scatter = isinstance(artist, PathCollection)
                if is_scatter:
                    if "color" in sd or "markerfacecolor" in sd:
                        c = sd.get("markerfacecolor", sd.get("color"))
                        try:
                            artist.set_facecolors(c)
                        except Exception:
                            pass
                    if "markeredgecolor" in sd:
                        try:
                            artist.set_edgecolors(sd["markeredgecolor"])
                        except Exception:
                            pass
                    if "markersize" in sd:
                        try:
                            artist.set_sizes([sd["markersize"] ** 2])
                        except Exception:
                            pass
                    if "marker" in sd:
                        mk = sd["marker"]
                        chart._series[idx]["marker"] = mk
                        if mk != "None":
                            from matplotlib.markers import MarkerStyle
                            marker = MarkerStyle(mk)
                            path = marker.get_path().transformed(
                                marker.get_transform())
                            artist.set_paths([path])
                else:
                    if "linestyle" in sd and hasattr(artist, 'set_linestyle'):
                        artist.set_linestyle(sd["linestyle"])
                    if "linewidth" in sd and hasattr(artist, 'set_linewidth'):
                        artist.set_linewidth(sd["linewidth"])
                    if "color" in sd and hasattr(artist, 'set_color'):
                        artist.set_color(sd["color"])
                    if "marker" in sd and hasattr(artist, 'set_marker'):
                        mk = sd["marker"]
                        artist.set_marker(mk if mk != "None" else "")
                    if "markersize" in sd and hasattr(
                            artist, 'set_markersize'):
                        artist.set_markersize(sd["markersize"])
                    if "markerfacecolor" in sd and hasattr(
                            artist, 'set_markerfacecolor'):
                        artist.set_markerfacecolor(sd["markerfacecolor"])
                    if "markeredgecolor" in sd and hasattr(
                            artist, 'set_markeredgecolor'):
                        artist.set_markeredgecolor(sd["markeredgecolor"])
                if sd.get("visible") is False:
                    if hasattr(artist, 'set_visible'):
                        artist.set_visible(False)
            # Fill properties.
            fm = sd.get("fill_mode", "none")
            if fm != "none":
                chart.apply_fill(
                    idx, fm, sd.get("fill_target", 0),
                    sd.get("fill_color", "#1f77b4"),
                    sd.get("fill_alpha", 0.3))

        # Header mode.
        chart._header_row = bool(tpl.get("header_row", False))
        if chart._header_row:
            chart._apply_header_labels(refresh_legend=False)

        # Legend.
        leg_font = tpl.get("legend_font")
        leg_size = tpl.get("legend_size", 8)
        leg_visible = tpl.get("legend_visible", True)
        lp = tpl.get("legend_props", {})
        if leg_visible:
            prop = {"family": leg_font or "sans-serif", "size": leg_size}
            if lp.get("bold"):
                prop["weight"] = "bold"
            if lp.get("italic"):
                prop["style"] = "italic"
            kw = {
                "loc": "best",
                "prop": prop,
                "frameon": lp.get("frame_on", True),
                "framealpha": lp.get("frame_alpha", 0.8),
                "shadow": lp.get("shadow", False),
                "fancybox": lp.get("fancybox", True),
                "ncol": lp.get("ncol", 1),
                "markerscale": lp.get("markerscale", 1.0),
                "labelspacing": lp.get("labelspacing", 0.5),
                "columnspacing": lp.get("columnspacing", 2.0),
                "handlelength": lp.get("handlelength", 2.0),
                "handletextpad": lp.get("handletextpad", 0.8),
                "borderpad": lp.get("borderpad", 0.4),
            }
            title = lp.get("title")
            if title:
                kw["title"] = title
            leg = chart._install_legend(ax, **kw)
            if leg:
                leg.set_draggable(True)
                lc = lp.get("label_color", "#000000")
                for t in leg.get_texts():
                    t.set_color(lc)
                fp = leg.get_frame()
                if fp:
                    fp.set_edgecolor(lp.get("edge_color", "#cccccc"))
                    fp.set_facecolor(lp.get("face_color", "#ffffff"))
            if lp:
                chart._legend_props = dict(lp)
        else:
            leg = ax.get_legend()
            if leg:
                leg.remove()

        # Trendlines — re-fit from data (template doesn't store params).
        tl_list = tpl.get("trendlines", [])
        if tl_list:
            from .trendline import TrendlineInfo, restore_trendline
            for td in tl_list:
                info = TrendlineInfo.from_dict(td)
                restore_trendline(chart, info)
                chart._trendlines.append(info)

        # General properties last (sketch effect needs all artists).
        gp = tpl.get("general_props")
        if gp:
            from .general_properties import apply_general_state
            apply_general_state(chart, gp)

        chart._canvas.draw_idle()
        return chart

    @classmethod
    def from_dict(cls, d, source_sheet, parent):
        """Recreate a chart from a dict produced by to_dict()."""
        series = d["series"]
        s0 = series[0]
        chart = cls(
            np.array(s0["x"]), np.array(s0["y"]),
            s0["label"], s0["plot_type"],
            source_sheet, parent)
        for s in series[1:]:
            chart.add_series(
                np.array(s["x"]), np.array(s["y"]),
                s["label"], s["plot_type"])
        chart.move(d.get("pos_x", 40), d.get("pos_y", 40))
        w, h = d.get("width", 480), d.get("height", 320)
        chart.resize(w, h)
        if d.get("keep_ratio"):
            chart._keep_ratio = True
            chart._aspect_ratio = w / max(h, 1)
        if d.get("tight_layout") is True:
            chart._tight_layout = True
        elif d.get("tight_layout") is False:
            # Legacy files stored tight_layout=False explicitly
            chart._tight_layout = False
            try:
                chart._figure.set_layout_engine("none")
            except Exception:
                pass
            margins = d.get("subplot_margins")
            if margins:
                chart._figure.subplots_adjust(**margins)
        ax = chart._ax
        ax.set_title(d.get("title", ""))
        ax.set_xlabel(d.get("xlabel", "X"))
        ax.set_ylabel(d.get("ylabel", "Y"))
        # Secondary labels (top / right).
        top_lbl = d.get("top_label", "")
        top_off = d.get("top_label_offset", 0.08)
        right_lbl = d.get("right_label", "")
        right_off = d.get("right_label_offset", 0.08)
        if top_lbl:
            chart._top_label_text = top_lbl
            chart._top_label_offset = top_off
            from .axis_dialog import AxisPropertiesDialog
            AxisPropertiesDialog._set_secondary_label(
                chart, "top", top_lbl, {"fontsize": 10}, top_off)
        if right_lbl:
            chart._right_label_text = right_lbl
            chart._right_label_offset = right_off
            from .axis_dialog import AxisPropertiesDialog
            AxisPropertiesDialog._set_secondary_label(
                chart, "right", right_lbl, {"fontsize": 10}, right_off)
        # Restore axis properties if saved.
        axis_props = d.get("axis_props")
        if axis_props:
            chart._axis_props = axis_props
            from .axis_dialog import AxisPropertiesDialog
            for direction, st in axis_props.items():
                AxisPropertiesDialog._apply_dir_static(chart, direction, st)
        else:
            try:
                ax.set_xscale(d.get("xscale", "linear"))
                ax.set_yscale(d.get("yscale", "linear"))
            except ValueError:
                pass
            ax.grid(d.get("grid", False))
        # Enforce saved axis inversion (idempotent; applied after
        # axis_props so the most recent state always wins).
        if "x_inverted" in d and bool(d["x_inverted"]) != ax.xaxis_inverted():
            ax.invert_xaxis()
        if "y_inverted" in d and bool(d["y_inverted"]) != ax.yaxis_inverted():
            ax.invert_yaxis()
        # Restore source column mapping for live updates.
        chart._x_col = d.get("x_col")
        chart._y_cols = d.get("y_cols", [])
        if chart._source_sheet and chart._y_cols:
            chart._source_sheet.data_changed.connect(
                chart._on_data_changed)
        # Restore categorical X-axis labels or time formatting.
        if d.get("time_x"):
            chart._apply_time_x()
        else:
            saved_cat = d.get("cat_labels")
            if saved_cat:
                chart._apply_categorical_x(saved_cat)
        # Restore bar chart config.
        bc = d.get("bar_config")
        if bc:
            chart._bar_config.update(bc)
        # Restore pie chart config.
        pc = d.get("pie_config")
        if pc:
            chart._pie_config.update(pc)
        # Restore heatmap / 3D surface config and redraw.
        hmc = d.get("heatmap_config")
        if hmc:
            chart._heatmap_config = hmc
            if series and series[0].get("plot_type") == "Heatmap":
                from .heatmap_options import redraw_heatmap
                try:
                    redraw_heatmap(chart, hmc)
                except Exception:
                    pass
        s3c = d.get("surface3d_config")
        if s3c:
            chart._surface3d_config = s3c
            if series and series[0].get("plot_type") == "3D Surface":
                from .heatmap_options import redraw_surface
                try:
                    redraw_surface(chart, s3c)
                except Exception:
                    pass
        # Restore visual properties, fill, and visibility per series.
        from matplotlib.collections import PathCollection
        for i, sd in enumerate(series):
            if i >= len(chart._series):
                break
            artist = chart._series[i].get("artist")
            if artist is not None:
                from matplotlib.container import BarContainer
                is_bar = isinstance(artist, BarContainer)
                is_scatter = isinstance(artist, PathCollection)
                if is_bar:
                    # Bar visuals are handled by _redraw_bars above;
                    # just restore face colour for the initial render.
                    if "color" in sd and artist.patches:
                        try:
                            for p in artist.patches:
                                p.set_facecolor(sd["color"])
                        except Exception:
                            pass
                elif is_scatter:
                    # Scatter: restore face/edge colors and sizes.
                    if "color" in sd or "markerfacecolor" in sd:
                        c = sd.get("markerfacecolor", sd.get("color"))
                        try:
                            artist.set_facecolors(c)
                        except Exception:
                            pass
                    if "markeredgecolor" in sd:
                        try:
                            artist.set_edgecolors(sd["markeredgecolor"])
                        except Exception:
                            pass
                    if "markersize" in sd:
                        try:
                            artist.set_sizes([sd["markersize"] ** 2])
                        except Exception:
                            pass
                    if "marker" in sd:
                        mk = sd["marker"]
                        chart._series[i]["marker"] = mk
                        if mk != "None":
                            from matplotlib.markers import MarkerStyle
                            marker = MarkerStyle(mk)
                            path = marker.get_path().transformed(
                                marker.get_transform())
                            artist.set_paths([path])
                else:
                    # Line2D.
                    if "linestyle" in sd and hasattr(artist, 'set_linestyle'):
                        artist.set_linestyle(sd["linestyle"])
                    if "linewidth" in sd and hasattr(artist, 'set_linewidth'):
                        artist.set_linewidth(sd["linewidth"])
                    if "color" in sd and hasattr(artist, 'set_color'):
                        artist.set_color(sd["color"])
                    if "marker" in sd and hasattr(artist, 'set_marker'):
                        mk = sd["marker"]
                        artist.set_marker(mk if mk != "None" else "")
                    if "markersize" in sd and hasattr(
                            artist, 'set_markersize'):
                        artist.set_markersize(sd["markersize"])
                    if "markerfacecolor" in sd and hasattr(
                            artist, 'set_markerfacecolor'):
                        artist.set_markerfacecolor(sd["markerfacecolor"])
                    if "markeredgecolor" in sd and hasattr(
                            artist, 'set_markeredgecolor'):
                        artist.set_markeredgecolor(sd["markeredgecolor"])
                if sd.get("visible") is False:
                    if hasattr(artist, 'set_visible'):
                        artist.set_visible(False)
            # Restore per-series X column and row range info.
            if "x_col" in sd:
                chart._series[i]["x_col"] = sd["x_col"]
            for rk in ("x_row_start", "x_row_end",
                        "y_row_start", "y_row_end"):
                if rk in sd:
                    chart._series[i][rk] = int(sd[rk])
            # Per-series bar properties.
            if "bar" in sd:
                chart._series[i]["bar"] = dict(sd["bar"])
            fm = sd.get("fill_mode", "none")
            if fm != "none":
                chart.apply_fill(
                    i, fm, sd.get("fill_target", 0),
                    sd.get("fill_color", "#1f77b4"),
                    sd.get("fill_alpha", 0.3))
        # Redraw bars with restored config (grouped/stacked offsets).
        chart._redraw_bars()
        # Redraw pie with restored config.
        chart._redraw_pie()
        # Header mode: resync labels from header cells before the legend
        # is built so it reflects the (possibly edited) column headers.
        chart._header_row = bool(d.get("header_row", False))
        if chart._header_row:
            chart._apply_header_labels(refresh_legend=False)
        # Restore legend visibility, font, and extended properties.
        leg_font = d.get("legend_font")
        leg_size = d.get("legend_size", 8)
        leg_visible = d.get("legend_visible", True)
        lp = d.get("legend_props", {})
        if leg_visible:
            prop = {"family": leg_font or "sans-serif", "size": leg_size}
            if lp.get("bold"):
                prop["weight"] = "bold"
            if lp.get("italic"):
                prop["style"] = "italic"
            kw = {
                "loc": "best",
                "prop": prop,
                "frameon": lp.get("frame_on", True),
                "framealpha": lp.get("frame_alpha", 0.8),
                "shadow": lp.get("shadow", False),
                "fancybox": lp.get("fancybox", True),
                "ncol": lp.get("ncol", 1),
                "markerscale": lp.get("markerscale", 1.0),
                "labelspacing": lp.get("labelspacing", 0.5),
                "columnspacing": lp.get("columnspacing", 2.0),
                "handlelength": lp.get("handlelength", 2.0),
                "handletextpad": lp.get("handletextpad", 0.8),
                "borderpad": lp.get("borderpad", 0.4),
            }
            title = lp.get("title")
            if title:
                kw["title"] = title
            leg = chart._install_legend(ax, **kw)
            if leg:
                leg.set_draggable(True)
                lc = lp.get("label_color", "#000000")
                for t in leg.get_texts():
                    t.set_color(lc)
                fp = leg.get_frame()
                if fp:
                    fp.set_edgecolor(lp.get("edge_color", "#cccccc"))
                    fp.set_facecolor(lp.get("face_color", "#ffffff"))
            if lp:
                chart._legend_props = dict(lp)
        else:
            leg = ax.get_legend()
            if leg:
                leg.remove()
        # Restore trendlines.
        tl_list = d.get("trendlines", [])
        if tl_list:
            from .trendline import TrendlineInfo, restore_trendline
            for td in tl_list:
                info = TrendlineInfo.from_dict(td)
                restore_trendline(chart, info)
                chart._trendlines.append(info)
        # Restore general (figure-level) properties last, after all
        # artists exist so the sketch effect applies to every series.
        gp = d.get("general_props")
        if gp:
            from .general_properties import apply_general_state
            apply_general_state(chart, gp)
        # Restore annotations.
        for ad in d.get("annotations", []):
            atype = ad.get("type")
            if atype == "text":
                fs = ad.get("fontsize", 10)
                fw = ad.get("fontweight", "normal")
                fst = ad.get("fontstyle", "normal")
                tc = ad.get("color", "black")
                rot = ad.get("rotation", 0)
                bs = ad.get("bbox_style", "round")
                # Sanitize corrupted bbox_style from older saves.
                if bs.startswith("<") or "object at" in bs:
                    bs = "round"
                bfc = ad.get("bbox_fc", "wheat")
                ba = ad.get("bbox_alpha", 0.8)
                bbox_d = dict(boxstyle=f'{bs},pad=0.3',
                              fc=bfc, alpha=ba)
                ann = ax.annotate(
                    ad["text"], xy=tuple(ad["xy"]),
                    xytext=tuple(ad["xy"]),
                    fontsize=fs, fontweight=fw, fontstyle=fst,
                    color=tc, rotation=rot,
                    ha='center', va='center', bbox=bbox_d)
                ann.draggable(True)
                chart._annotations.append(
                    {"type": "text", "artist": ann})
            elif atype == "arrow":
                ac = ad.get("arrow_color", "black")
                alw = ad.get("arrow_lw", 1.5)
                als = ad.get("arrow_ls", "-")
                astyle = ad.get("arrow_style", "->")
                # Sanitize corrupted arrow_style from older saves.
                if astyle.startswith("<"):
                    astyle = "->"
                ann = ax.annotate(
                    ad.get("text", ""), xy=tuple(ad["xy"]),
                    xytext=tuple(ad.get("xytext", ad["xy"])),
                    fontsize=9,
                    arrowprops=dict(arrowstyle=astyle,
                                    color=ac, lw=alw,
                                    linestyle=als),
                    bbox=dict(boxstyle='round,pad=0.2',
                              fc='white', alpha=0.7)
                    if ad.get("text", "").strip() else None)
                ann.draggable(True)
                chart._annotations.append(
                    {"type": "arrow", "artist": ann})
            elif atype == "line":
                if "xy" in ad and "xytext" in ad:
                    # New-style finite line segment.
                    ac = ad.get("arrow_color", "black")
                    alw = ad.get("arrow_lw", 1.5)
                    als = ad.get("arrow_ls", "-")
                    ann = ax.annotate(
                        "", xy=tuple(ad["xy"]),
                        xytext=tuple(ad["xytext"]),
                        arrowprops=dict(arrowstyle='-',
                                        color=ac, lw=alw,
                                        linestyle=als))
                    ann.draggable(True)
                    chart._annotations.append(
                        {"type": "line", "artist": ann})
                else:
                    # Legacy axhline/axvline format.
                    dirn = ad.get("direction", "horizontal")
                    val = ad.get("value", 0)
                    if dirn == "horizontal":
                        line = ax.axhline(
                            val, color='red', ls='--', lw=1.2)
                    else:
                        line = ax.axvline(
                            val, color='red', ls='--', lw=1.2)
                    dl = _DraggableLine(line, dirn, chart._canvas)
                    chart._annotations.append(
                        {"type": "line", "artist": line,
                         "direction": dirn, "dragger": dl})
        chart._canvas.draw_idle()
        return chart

    # ── Plot template actions ──────────────────────────────────────────

    def _save_as_template(self):
        from .plot_templates import SaveTemplateDialog, save_template
        title = self._ax.get_title() or "Untitled"
        dlg = SaveTemplateDialog(self, default_name=title)
        if dlg.exec_() != dlg.Accepted:
            return
        tpl = self.to_template()
        if dlg.description:
            tpl["description"] = dlg.description
        save_template(dlg.template_name, tpl)

    def _apply_template(self):
        """Re-style this chart from a saved template (keeps data)."""
        from .plot_templates import LoadTemplateDialog
        dlg = LoadTemplateDialog(self)
        if dlg.exec_() != dlg.Accepted or dlg.selected_template is None:
            return
        tpl = dlg.selected_template
        ax = self._ax

        # Apply axis labels and title.
        ax.set_title(tpl.get("title", ax.get_title()))
        ax.set_xlabel(tpl.get("xlabel", ax.get_xlabel()))
        ax.set_ylabel(tpl.get("ylabel", ax.get_ylabel()))

        # Axis properties.
        axis_props = tpl.get("axis_props")
        if axis_props:
            self._axis_props = axis_props
            from .axis_dialog import AxisPropertiesDialog
            for direction, st in axis_props.items():
                AxisPropertiesDialog._apply_dir_static(self, direction, st)

        # General properties.
        gp = tpl.get("general_props")
        if gp:
            from .general_properties import apply_general_state
            apply_general_state(self, gp)

        # Legend properties.
        lp = tpl.get("legend_props", {})
        leg_visible = tpl.get("legend_visible", True)
        if leg_visible and lp:
            leg_font = tpl.get("legend_font", "sans-serif")
            leg_size = tpl.get("legend_size", 8)
            prop = {"family": leg_font, "size": leg_size}
            if lp.get("bold"):
                prop["weight"] = "bold"
            if lp.get("italic"):
                prop["style"] = "italic"
            kw = {
                "loc": "best", "prop": prop,
                "frameon": lp.get("frame_on", True),
                "framealpha": lp.get("frame_alpha", 0.8),
                "shadow": lp.get("shadow", False),
                "fancybox": lp.get("fancybox", True),
                "ncol": lp.get("ncol", 1),
            }
            leg = self._install_legend(ax, **kw)
            if leg:
                leg.set_draggable(True)
            self._legend_props = dict(lp)

        # Apply visual properties to existing series.
        from matplotlib.collections import PathCollection
        tpl_series = tpl.get("series", [])
        for idx, sd in enumerate(tpl_series):
            if idx >= len(self._series):
                break
            artist = self._series[idx].get("artist")
            if artist is None:
                continue
            is_scatter = isinstance(artist, PathCollection)
            if is_scatter:
                if "color" in sd or "markerfacecolor" in sd:
                    c = sd.get("markerfacecolor", sd.get("color"))
                    try:
                        artist.set_facecolors(c)
                    except Exception:
                        pass
                if "markeredgecolor" in sd:
                    try:
                        artist.set_edgecolors(sd["markeredgecolor"])
                    except Exception:
                        pass
            else:
                if "linestyle" in sd and hasattr(artist, 'set_linestyle'):
                    artist.set_linestyle(sd["linestyle"])
                if "linewidth" in sd and hasattr(artist, 'set_linewidth'):
                    artist.set_linewidth(sd["linewidth"])
                if "color" in sd and hasattr(artist, 'set_color'):
                    artist.set_color(sd["color"])
                if "marker" in sd and hasattr(artist, 'set_marker'):
                    mk = sd["marker"]
                    artist.set_marker(mk if mk != "None" else "")
                if "markersize" in sd and hasattr(artist, 'set_markersize'):
                    artist.set_markersize(sd["markersize"])
                if "markerfacecolor" in sd and hasattr(
                        artist, 'set_markerfacecolor'):
                    artist.set_markerfacecolor(sd["markerfacecolor"])
                if "markeredgecolor" in sd and hasattr(
                        artist, 'set_markeredgecolor'):
                    artist.set_markeredgecolor(sd["markeredgecolor"])

        # Size.
        w = tpl.get("width")
        h = tpl.get("height")
        if w and h:
            self.resize(w, h)

        self._canvas.draw_idle()

    # ── Close ───────────────────────────────────────────────────────
    def _close_chart(self):
        self._clear_show_data()
        sheet = self._source_sheet
        if sheet:
            undo = getattr(sheet, '_undo_stack', None)
            if undo is not None:
                from .undo_commands import DeleteChartCmd
                undo.push(DeleteChartCmd(sheet, self))
                return
            # Fallback if no undo stack — hard delete.
            try:
                sheet.data_changed.disconnect(self._on_data_changed)
            except (TypeError, RuntimeError):
                pass
            if hasattr(sheet, '_charts'):
                try:
                    sheet._charts.remove(self)
                except ValueError:
                    pass
            if getattr(sheet, '_selected_chart', None) is self:
                sheet._selected_chart = None
        self.deleteLater()

    # ── Categorical X-axis support ──────────────────────────────────

    def _read_series_xy(self, sheet, s, yc):
        """Read X and Y data for one series, detecting categorical X.

        Returns ``(x, y, labels)`` where *labels* is a list of tick
        label strings when the X column is categorical, or ``None``
        when it is numeric.
        """
        xc = s.get("x_col", self._x_col)
        y_full = sheet.numeric_column(yc)
        y_r0 = s.get("y_row_start", 0)
        y_r1 = s.get("y_row_end", len(y_full) - 1)
        y_data = y_full[y_r0:y_r1 + 1]

        if xc is None:
            # No X column — use row indices.
            x_data = np.arange(len(y_data), dtype=float)
            mask = ~np.isnan(y_data[:len(x_data)])
            return x_data[mask], y_data[:len(x_data)][mask], None

        x_full_num = sheet.numeric_column(xc)
        x_r0 = s.get("x_row_start", 0)
        x_r1 = s.get("x_row_end", len(x_full_num) - 1)
        x_num = x_full_num[x_r0:x_r1 + 1]

        n = min(len(x_num), len(y_data))
        x_num, y_data = x_num[:n], y_data[:n]

        # Decide: if more than half the X values are NaN (text), try
        # time parsing first, then fall back to categorical.
        nan_count = int(np.isnan(x_num).sum())
        if nan_count > n / 2 and n > 0:
            x_str = sheet.string_column(xc)
            labels = x_str[x_r0:x_r0 + n]
            # Try parsing as time-of-day strings.
            t_hours, _ = parse_time_column(labels)
            if t_hours is not None:
                mask = ~(np.isnan(t_hours) | np.isnan(y_data))
                # Return numeric hours — caller applies time formatter.
                return t_hours[mask], y_data[mask], "TIME"
            # Categorical X — evenly spaced with text labels.
            x_pos = np.arange(n, dtype=float)
            mask = ~np.isnan(y_data)
            return x_pos[mask], y_data[mask], \
                [labels[i] for i, m in enumerate(mask) if m]

        # Numeric X — original behaviour.
        mask = ~(np.isnan(x_num) | np.isnan(y_data))
        return x_num[mask], y_data[mask], None

    def _apply_categorical_x(self, labels):
        """Set X-axis tick positions and labels for a categorical axis."""
        if not labels:
            return
        ax = self._ax
        ax.set_xticks(np.arange(len(labels)))
        # Rotate labels when there are many or when they're long.
        max_len = max((len(s) for s in labels), default=0)
        needs_rotation = len(labels) > 5 or max_len > 8
        ax.set_xticklabels(labels,
                           rotation=45 if needs_rotation else 0,
                           ha='right' if needs_rotation else 'center')
        # Store for persistence and refresh.
        self._cat_labels = labels
        # Increase bottom margin for rotated labels.
        if needs_rotation:
            try:
                self._figure.subplots_adjust(bottom=0.28)
            except Exception:
                pass

    def _apply_time_x(self):
        """Format X-axis ticks as HH:MM for time-valued data."""
        import matplotlib.ticker as ticker
        ax = self._ax

        def _fmt(val, _pos):
            h = val % 24
            m = round((h - int(h)) * 60)
            return f"{int(h):02d}:{m:02d}"

        ax.xaxis.set_major_formatter(ticker.FuncFormatter(_fmt))
        self._time_x = True

    # ── Live data update ─────────────────────────────────────────────
    def _on_data_changed(self, col: int):
        """Re-read source data and refresh the chart when a plotted
        column changes on the sheet."""
        if not self._source_sheet:
            return
        # Check if this column is relevant (any series' X or Y col).
        x_cols = set()
        for s in self._series:
            xc = s.get("x_col", self._x_col)
            if xc is not None:
                x_cols.add(xc)
        relevant = (col in x_cols) or (col in self._y_cols)
        if not relevant:
            return
        sheet = self._source_sheet
        cat_labels = None
        is_time = False
        # Update each series respecting per-series X column.
        for i, (s, yc) in enumerate(
                zip(self._series, self._y_cols)):
            x, y, labels = self._read_series_xy(sheet, s, yc)
            s["x"], s["y"] = x, y
            if labels == "TIME":
                is_time = True
            elif labels is not None:
                cat_labels = labels
            self._update_artist(s, x, y)
        self._ax.dataLim.set_points(np.array(
            [[np.inf, np.inf], [-np.inf, -np.inf]]))
        for s2 in self._series:
            sx, sy = s2.get("x", []), s2.get("y", [])
            if len(sx) and len(sy):
                self._ax.update_datalim(np.column_stack([sx, sy]))
        self._ax.autoscale_view()
        if is_time:
            self._apply_time_x()
        elif cat_labels is not None:
            self._apply_categorical_x(cat_labels)
        if self._header_row:
            self._apply_header_labels()
        self._canvas.draw()

    def shift_column_refs(self, at, delta):
        """Shift stored source-column indices when a column is inserted
        (delta=+1) or removed (delta=-1) at index *at*, so the chart keeps
        following its data like Excel. Returns True if anything changed."""
        def shift(idx):
            if idx is None:
                return None, False
            if delta > 0:
                return (idx + delta, True) if idx >= at else (idx, False)
            if idx > at:
                return idx + delta, True
            return idx, False

        changed = False
        new_x, ch = shift(self._x_col)
        self._x_col = new_x
        changed = changed or ch
        new_y = []
        for c in self._y_cols:
            nc, ch = shift(c)
            new_y.append(nc)
            changed = changed or ch
        self._y_cols = new_y
        for s in self._series:
            if s.get("x_col") is not None:
                nc, ch = shift(s["x_col"])
                s["x_col"] = nc
                changed = changed or ch
        return changed

    def _apply_header_labels(self, refresh_legend=True):
        """Set each series' label from the first row of its Y range (the
        column header). Used when 'first row is a header' is enabled, and
        re-run on cell edits so the legend tracks the header cells."""
        sheet = self._source_sheet
        if not sheet:
            return
        for i, s in enumerate(self._series):
            if i >= len(self._y_cols):
                continue
            yc = self._y_cols[i]
            hdr_row = int(s.get("y_row_start", 0))
            text = sheet.cell_text(hdr_row, yc).strip()
            if not text:
                continue
            s["label"] = text
            artist = s.get("artist")
            if artist is not None and hasattr(artist, "set_label"):
                artist.set_label(text)
        if refresh_legend and self._ax.get_legend() is not None:
            self._install_legend()
            self._canvas.draw_idle()

    def _refresh_data(self):
        """Re-read source columns and update all series, preserving
        visual properties but autoscaling to fit the (possibly new)
        data range."""
        if not self._source_sheet:
            return
        sheet = self._source_sheet
        ax = self._ax
        # Snapshot axis labels/scales/grid (not limits — those must
        # autoscale so a changed data range is always visible).
        title = ax.get_title()
        xlabel = ax.get_xlabel()
        ylabel = ax.get_ylabel()
        xscale = ax.get_xscale()
        yscale = ax.get_yscale()
        grid_on = bool(ax.xaxis.get_gridlines()[0].get_visible()
                       if ax.xaxis.get_gridlines() else False)

        cat_labels = None
        is_time = False
        for i, (s, yc) in enumerate(
                zip(self._series, self._y_cols)):
            x, y, labels = self._read_series_xy(sheet, s, yc)
            s["x"], s["y"] = x, y
            if labels == "TIME":
                is_time = True
            elif labels is not None:
                cat_labels = labels
            self._update_artist(s, x, y)

        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        try:
            ax.set_xscale(xscale)
            ax.set_yscale(yscale)
        except Exception:
            pass
        # Reset data limits from scratch for all artist types.
        # Skip for heatmap / 3D surface — imshow/plot_surface manage
        # their own extent and y is a 2D matrix, not a 1D series.
        skip_types = ("Heatmap", "3D Surface")
        if not any(s.get("plot_type") in skip_types for s in self._series):
            ax.dataLim.set_points(np.array(
                [[np.inf, np.inf], [-np.inf, -np.inf]]))
            for s in self._series:
                sx, sy = s.get("x", []), s.get("y", [])
                if len(sx) and len(sy):
                    ax.update_datalim(np.column_stack([sx, sy]))
            ax.autoscale_view(True, True, True)
        if is_time:
            self._apply_time_x()
        elif cat_labels is not None:
            self._apply_categorical_x(cat_labels)
        ax.grid(grid_on)
        self._canvas.draw()

    def _replot_from_source(self):
        """Re-read source data after a range overlay drag/resize and
        autoscale to fit the new data.  Works for all plot types."""
        if not self._source_sheet:
            return
        sheet = self._source_sheet
        ax = self._ax

        cat_labels = None
        is_time = False
        for i, (s, yc) in enumerate(
                zip(self._series, self._y_cols)):
            x, y, labels = self._read_series_xy(sheet, s, yc)
            s["x"], s["y"] = x, y
            if labels == "TIME":
                is_time = True
            elif labels is not None:
                cat_labels = labels
            self._update_artist(s, x, y)

        # Reset data limits from scratch so autoscale sees all artists.
        # Skip for heatmap / 3D surface — y is 2D, not a 1D series.
        skip_types = ("Heatmap", "3D Surface")
        if not any(s.get("plot_type") in skip_types for s in self._series):
            ax.dataLim.set_points(np.array(
                [[np.inf, np.inf], [-np.inf, -np.inf]]))
            for s in self._series:
                x, y = s.get("x", []), s.get("y", [])
                if len(x) and len(y):
                    ax.update_datalim(np.column_stack([x, y]))
            ax.autoscale_view(True, True, True)
        if is_time:
            self._apply_time_x()
        elif cat_labels is not None:
            self._apply_categorical_x(cat_labels)
        if self._header_row:
            self._apply_header_labels()
        self._canvas.draw()

    # ── Show Data highlight ────────────────────────────────────────────

    def _toggle_show_data(self, checked):
        """Toggle highlighting source cells on the sheet."""
        if checked:
            self._apply_show_data()
        else:
            self._clear_show_data()

    # Grey used for X-data column overlays (not plotted, just the domain).
    _X_RANGE_COLOR = "#808080"

    @staticmethod
    def _artist_color_hex(artist):
        """Return the colour of *artist* as a hex string, or None."""
        from matplotlib.colors import to_hex
        try:
            if hasattr(artist, 'get_color'):
                c = artist.get_color()
                if isinstance(c, str):
                    return c if c.startswith('#') else to_hex(c)
                if hasattr(c, '__len__') and len(c) >= 3:
                    return to_hex(c)
            if hasattr(artist, 'get_facecolor'):
                fc = artist.get_facecolor()
                if hasattr(fc, '__len__') and len(fc) > 0:
                    return to_hex(fc[0])
        except Exception:
            pass
        return None

    def _apply_show_data(self):
        """Highlight source data ranges with coloured border overlays."""
        self._clear_show_data()
        sheet = self._source_sheet
        if not sheet:
            return
        table = sheet.table
        overlays = []

        # Track X columns already overlaid so we don't double-draw.
        x_cols_done = set()

        for i, (s, yc) in enumerate(
                zip(self._series, self._y_cols)):
            r0 = s.get("y_row_start", 0)
            r1 = s.get("y_row_end", len(s.get("y", [])) - 1)

            # X column overlay — transparent grey
            xc = s.get("x_col", self._x_col)
            if xc is not None and xc not in x_cols_done:
                x_cols_done.add(xc)
                xr0 = s.get("x_row_start", 0)
                xr1 = s.get("x_row_end", r1)
                ov = self._create_range_overlay(
                    table, xr0, xc, xr1, xc, self._X_RANGE_COLOR)
                if ov:
                    ov._chart = self
                    ov._axis = "x"
                    ov._series_idx = i
                    overlays.append(ov)

            # Y column overlay — use actual line/artist colour
            line_color = self._artist_color_hex(s.get("artist"))
            if line_color is None:
                line_color = "#4472C4"  # fallback blue
            ov = self._create_range_overlay(
                table, r0, yc, r1, yc, line_color)
            if ov:
                ov._chart = self
                ov._axis = "y"
                ov._series_idx = i
                overlays.append(ov)

        self._show_data_active = True
        self._show_data_overlays = overlays
        # Keep every embedded object above the range overlays so the
        # column-colour highlights never bleed over a plot, picture, shape or
        # equation — not just the active chart.
        for chart in getattr(sheet, "_charts", []):
            if chart is not self:
                chart.raise_()
        for obj in (list(getattr(sheet, "_images", []))
                    + list(getattr(sheet, "_shapes", []))
                    + list(getattr(sheet, "_equations", []))):
            try:
                obj.raise_()
            except Exception:
                pass
        self.raise_()
        if self._handle_overlay.isVisible():
            self._handle_overlay.raise_()

    @staticmethod
    def _create_range_overlay(table, r0, c0, r1, c1, color_hex):
        """Create a transparent QWidget overlay with a coloured solid
        border around the cell range (r0,c0)–(r1,c1)."""
        top_rect = table.visualRect(table.model().index(r0, c0))
        bot_rect = table.visualRect(table.model().index(r1, c1))
        if top_rect.isNull() or bot_rect.isNull():
            return None
        hp = _RangeOverlay._HP
        x = top_rect.left() - 1
        y = top_rect.top() - 1 - hp        # padding top
        w = bot_rect.right() - x + 2 + hp  # padding right
        h = bot_rect.bottom() - (top_rect.top() - 1) + 2 + 2 * hp  # top+bottom

        overlay = _RangeOverlay(table.viewport(), color_hex)
        overlay._r0 = r0
        overlay._c0 = c0
        overlay._r1 = r1
        overlay._c1 = c1
        overlay.setGeometry(x, y, w, h)
        overlay.show()
        overlay.raise_()
        return overlay

    def _clear_show_data(self):
        """Remove source data overlay widgets."""
        overlays = getattr(self, '_show_data_overlays', None)
        if overlays:
            for ov in overlays:
                ov.setParent(None)
                ov.deleteLater()
        self._show_data_overlays = None
        self._show_data_active = False

    # ── Legend hit testing ─────────────────────────────────────────────
    def _hit_legend(self, event_pos):
        """Return True if *event_pos* (canvas-local QPoint) is over the
        legend artist."""
        leg = self._ax.get_legend()
        if leg is None or not leg.get_visible():
            return False
        try:
            # Transform canvas-local Qt coords → matplotlib display coords.
            # Account for device pixel ratio (HiDPI / Windows scaling).
            dpr = self._canvas.devicePixelRatio()
            cx = event_pos.x() * dpr
            cy = (self._canvas.height() - event_pos.y()) * dpr
            renderer = self._canvas.get_renderer()
            bbox = leg.get_window_extent(renderer)
            return bbox.contains(cx, cy)
        except Exception:
            return False

    # ── Interactive label / axis editing ───────────────────────────
    _SPINE_MAP = {"Bottom": "bottom", "Top": "top",
                  "Left": "left", "Right": "right"}

    def _on_label_hover(self, event):
        """No-op — kept for mpl_connect compatibility."""
        pass

    def _on_canvas_click(self, event):
        """Handle clicks: single-click selects annotations, double-click
        opens label edit or axis properties."""
        if event.button == 1 and not event.dblclick:
            self._handle_annotation_click(event)
        if event.dblclick:
            # Ignore double-click on legend (use right-click menu).
            if self._hit_legend_mpl(event):
                return
            if self._try_edit_axis_label(event):
                return
            side = self._hit_axis_spine(event)
            if side is not None:
                self._open_axis_dialog(side)
                return
            # Double-click elsewhere opens axis properties (Bottom X).
            self._open_axis_dialog("Bottom")

    def _hit_legend_mpl(self, event):
        """Return True if matplotlib *event* is over the legend."""
        leg = self._ax.get_legend()
        if leg is None or not leg.get_visible():
            return False
        try:
            renderer = self._canvas.get_renderer()
            bbox = leg.get_window_extent(renderer)
            return bbox.contains(event.x, event.y)
        except Exception:
            return False

    def _open_legend_editor(self):
        """Open the legend editor dialog."""
        dlg = LegendEditorDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            dlg.apply_to_chart(self)

    def _open_trendline_dialog(self):
        """Open the trendline / curve fitting dialog."""
        from .trendline import TrendlineDialog
        dlg = TrendlineDialog(self, self)
        dlg.exec_()

    def _try_edit_axis_label(self, event):
        """If *event* hit xlabel, ylabel, or title, open QInputDialog
        to edit text inline. Returns True if handled."""
        ax = self._ax
        for artist, setter, dlg_title in (
            (ax.xaxis.label, ax.set_xlabel, "Edit X Axis Label"),
            (ax.yaxis.label, ax.set_ylabel, "Edit Y Axis Label"),
            (ax.title,       ax.set_title,  "Edit Plot Title"),
        ):
            try:
                hit, _ = artist.contains(event)
            except Exception:
                hit = False
            if not hit:
                continue
            old = artist.get_text()
            new, ok = QInputDialog.getText(
                self, dlg_title, "Label:", QLineEdit.Normal, old)
            if ok and new != old:
                setter(new)
                pass  # title updated on axes directly
                self._canvas.draw_idle()
            return True
        return False

    def _hit_axis_spine(self, event):
        """Return 'Bottom', 'Top', 'Left', or 'Right' if *event* is
        near an axis spine, else None."""
        if event.inaxes is not self._ax:
            return None
        ax = self._ax
        try:
            bbox = ax.get_window_extent()
        except Exception:
            return None
        margin = 12
        x, y = event.x, event.y
        if y <= bbox.y0 + margin:
            return "Bottom"
        if y >= bbox.y1 - margin:
            return "Top"
        if x <= bbox.x0 + margin:
            return "Left"
        if x >= bbox.x1 - margin:
            return "Right"
        return None

    def _set_scale(self, axis, scale):
        """Set *axis* ('x' or 'y') to *scale* ('linear' or 'log')."""
        ax = self._ax
        try:
            (ax.set_xscale if axis == "x" else ax.set_yscale)(scale)
            self._canvas.draw_idle()
        except ValueError:
            pass

    def _invert_axis(self, axis, inverted):
        """Invert or restore the given axis direction."""
        ax = self._ax
        if axis == "x":
            lo, hi = ax.get_xlim()
            if inverted and lo < hi:
                ax.set_xlim(hi, lo)
            elif not inverted and lo > hi:
                ax.set_xlim(hi, lo)
        else:
            lo, hi = ax.get_ylim()
            if inverted and lo < hi:
                ax.set_ylim(hi, lo)
            elif not inverted and lo > hi:
                ax.set_ylim(hi, lo)
        self._canvas.draw_idle()

    # ── Property dialog suite (General / Series / Axis) ─────────────
    # The three property dialogs cross-link via footer buttons. A single
    # dispatch loop keeps them open in sequence so the user can hop
    # between them without losing changes (each applies before switching).
    def _open_general_props(self):
        self._open_props_suite("general")

    def _open_plot_details(self):
        self._open_props_suite("series")

    def _open_axis_dialog(self, side="Bottom"):
        self._open_props_suite("axis", side)

    def _open_props_suite(self, start, axis_side="Bottom"):
        from .axis_dialog import AxisPropertiesDialog
        from .general_properties import (GeneralPropertiesDialog,
                                         default_general_state)
        nxt = start
        while nxt is not None:
            if nxt == "general":
                old_state = default_general_state(self)
                dlg = GeneralPropertiesDialog(self)
                res = dlg.exec_()
                if res == QDialog.Accepted:
                    new_state = dlg._capture_state()
                    dlg.apply_to_chart(self)
                    undo = self._get_undo_stack()
                    if undo is not None:
                        from .undo_commands import ChartPropertyCmd
                        undo.push(ChartPropertyCmd(
                            self, old_state, new_state))
                    nxt = None
                elif res == GeneralPropertiesDialog.SWITCH_TO_SERIES:
                    nxt = "series"
                elif res == GeneralPropertiesDialog.SWITCH_TO_AXIS:
                    nxt = "axis"
                else:
                    nxt = None
            elif nxt == "series":
                dlg = PlotDetailsDialog(self)
                res = dlg.run()
                if res == QDialog.Accepted:
                    dlg.apply_to_chart(self)
                    nxt = None
                elif res == PlotDetailsDialog.SWITCH_TO_AXIS:
                    nxt = "axis"
                elif res == PlotDetailsDialog.SWITCH_TO_GENERAL:
                    nxt = "general"
                else:
                    nxt = None
            elif nxt == "axis":
                dlg = AxisPropertiesDialog(self, axis_side)
                res = dlg.exec_()
                if res == QDialog.Accepted:
                    dlg.apply_to_chart(self)
                    nxt = None
                elif res == AxisPropertiesDialog.SWITCH_TO_PLOT_DETAILS:
                    nxt = "series"
                elif res == AxisPropertiesDialog.SWITCH_TO_GENERAL:
                    nxt = "general"
                else:
                    nxt = None
            else:
                nxt = None

    def paintEvent(self, event):
        """Fill the entire widget with white so grid cells don't bleed."""
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.white)
        p.end()
        super().paintEvent(event)

    # ── Context menu ────────────────────────────────────────────────
    def contextMenuEvent(self, event):
        # Try to select annotation under cursor before building menu.
        self._try_select_ann_at_pos(event)

        menu = QMenu(self)
        menu.addAction("Update Plot", self._refresh_data)

        menu.addSeparator()


        is_3d = hasattr(self._ax, 'get_zlim')

        # X Axis submenu
        xm = menu.addMenu("X Axis")
        xm.addAction("Linear", lambda: self._set_scale("x", "linear"))
        xm.addAction("Log\u2081\u2080",
                      lambda: self._set_scale("x", "log"))
        if not is_3d:
            xm.addSeparator()
            x_inv = xm.addAction("Invert Axis")
            x_inv.setCheckable(True)
            try:
                x_inv.setChecked(
                    self._ax.get_xlim()[0] > self._ax.get_xlim()[1])
            except Exception:
                pass
            x_inv.triggered.connect(
                lambda c: self._invert_axis("x", c))
        xm.addSeparator()
        xm.addAction("Axis Properties\u2026",
                      lambda: self._open_axis_dialog("Bottom"))

        # Y Axis submenu
        ym = menu.addMenu("Y Axis")
        ym.addAction("Linear", lambda: self._set_scale("y", "linear"))
        ym.addAction("Log\u2081\u2080",
                      lambda: self._set_scale("y", "log"))
        if not is_3d:
            ym.addSeparator()
            y_inv = ym.addAction("Invert Axis")
            y_inv.setCheckable(True)
            try:
                y_inv.setChecked(
                    self._ax.get_ylim()[0] > self._ax.get_ylim()[1])
            except Exception:
                pass
            y_inv.triggered.connect(
                lambda c: self._invert_axis("y", c))
        ym.addSeparator()
        ym.addAction("Axis Properties\u2026",
                      lambda: self._open_axis_dialog("Left"))

        menu.addSeparator()

        # Pan axes toggle
        pan_act = menu.addAction("Pan Axes")
        pan_act.setCheckable(True)
        pan_act.setChecked(self._pan_enabled)
        pan_act.triggered.connect(self._toggle_pan_mode)

        menu.addAction("Add Trendline\u2026", self._open_trendline_dialog)

        # Annotations
        ann_menu = menu.addMenu("Annotations")
        ann_menu.addAction("Add Text\u2026", self._add_text_annotation)
        ann_menu.addAction("Add Arrow\u2026", self._add_arrow_annotation)
        ann_menu.addAction("Add Line\u2026", self._add_line_annotation)
        if self._annotations:
            ann_menu.addSeparator()
            ann_menu.addAction("Manage Annotations\u2026",
                               lambda: self._open_annotations_manager())
        if self._selected_ann_idx >= 0:
            ann_menu.addSeparator()
            ann_menu.addAction("Properties\u2026",
                               self._open_annotation_properties)
            ann_menu.addAction("Delete",
                               self._delete_selected_annotation)

        # Resize presets — dimensions at 100 dpi (pixels = inches × 100)
        size_menu = menu.addMenu("Size")
        # General screen sizes
        for label, w, h in (
            ("Square (400\u00d7400)", 400, 400),
            ("Small (320\u00d7240)", 320, 240),
            ("Medium (480\u00d7320)", 480, 320),
            ("Large (640\u00d7480)", 640, 480),
            ("HD (960\u00d7540)", 960, 540),
        ):
            size_menu.addAction(
                label, lambda _=False, ww=w, hh=h: self._resize_to(ww, hh))
        size_menu.addSeparator()
        # Journal publication sizes
        for label, w, h in (
            ('Single column  (3.3\u2033\u00d72.5\u2033 / 84\u00d763 mm)',
             330, 250),
            ('1.5 column  (5.0\u2033\u00d73.75\u2033 / 127\u00d795 mm)',
             500, 375),
            ('Full width  (7.0\u2033\u00d75.25\u2033 / 178\u00d7133 mm)',
             700, 525),
            ('Full width short  (7.0\u2033\u00d74.0\u2033 / 178\u00d7102 mm)',
             700, 400),
            ('Nature single  (3.5\u2033\u00d72.6\u2033 / 89\u00d766 mm)',
             350, 260),
            ('Nature double  (7.2\u2033\u00d75.4\u2033 / 183\u00d7137 mm)',
             720, 540),
            ('ACS single  (3.25\u2033\u00d72.5\u2033 / 83\u00d763 mm)',
             325, 250),
            ('ACS double  (7.0\u2033\u00d74.0\u2033 / 178\u00d7102 mm)',
             700, 400),
            ('Square  (4.0\u2033\u00d74.0\u2033 / 102\u00d7102 mm)',
             400, 400),
        ):
            size_menu.addAction(
                label, lambda _=False, ww=w, hh=h: self._resize_to(ww, hh))

        # Export image
        export_menu = menu.addMenu("Export Image")
        export_menu.addAction("Save as PNG\u2026",
                              lambda: self._export_image("png"))
        export_menu.addAction("Save as PDF\u2026",
                              lambda: self._export_image("pdf"))
        export_menu.addAction("Save as SVG\u2026",
                              lambda: self._export_image("svg"))

        # Plot templates
        menu.addSeparator()
        menu.addAction("Save as Plot Template\u2026",
                        self._save_as_template)
        menu.addAction("Apply Plot Template\u2026",
                        self._apply_template)

        menu.addSeparator()

        menu.addAction("General Properties\u2026", self._open_general_props)
        menu.addAction("Series Properties\u2026", self._open_plot_details)
        menu.addAction("Axis Properties\u2026",
                      lambda: self._open_axis_dialog("Left"))
        menu.addAction("Edit Legend\u2026", self._open_legend_editor)

        menu.exec_(event.globalPos())

    def _toggle_pan_mode(self, checked):
        self._pan_enabled = checked

    def _toggle_keep_ratio(self, checked):
        self._keep_ratio = checked
        if checked:
            self._aspect_ratio = self.width() / max(self.height(), 1)

    def _toggle_tight_layout(self, checked):
        self._tight_layout = checked
        if checked:
            try:
                self._figure.set_layout_engine("tight")
            except Exception:
                try:
                    self._figure.tight_layout()
                except Exception:
                    pass
        else:
            # Disable auto-layout and reset to matplotlib defaults.
            try:
                self._figure.set_layout_engine("none")
            except Exception:
                pass
            self._figure.subplots_adjust(
                left=0.15, right=0.95, top=0.92, bottom=0.15,
                wspace=0.2, hspace=0.2)
        self._canvas.draw_idle()

    def _open_margins_dialog(self):
        """Open a dialog to manually adjust subplot margins."""
        sp = self._figure.subplotpars
        dlg = _SubplotMarginsDialog(
            sp.left, sp.right, sp.top, sp.bottom, self)
        if dlg.exec_() == QDialog.Accepted:
            vals = dlg.get_values()
            # Turn off tight layout so manual margins stick.
            self._tight_layout = False
            try:
                self._figure.set_layout_engine("none")
            except Exception:
                pass
            self._figure.subplots_adjust(**vals)
            self._canvas.draw_idle()

    def _resize_to(self, w, h):
        self.resize(w, h)
        self._aspect_ratio = w / max(h, 1)

    def _constrain_ratio(self, geo, edge):
        """Enforce fixed aspect ratio on *geo* QRect during resize."""
        if not self._keep_ratio:
            return geo
        r = self._aspect_ratio
        # Determine dominant axis from drag edge.
        if 'r' in edge or 'l' in edge:
            new_h = max(int(geo.width() / r), self.minimumHeight())
            geo.setHeight(new_h)
        else:
            new_w = max(int(geo.height() * r), self.minimumWidth())
            geo.setWidth(new_w)
        return geo

    def _export_image(self, fmt):
        from PyQt5.QtWidgets import QFileDialog
        ext = fmt.upper()
        path, _ = QFileDialog.getSaveFileName(
            self, f"Export Chart as {ext}", "",
            f"{ext} files (*.{fmt})")
        if path:
            self._figure.savefig(path, format=fmt, dpi=300,
                                 bbox_inches='tight')

    def _pop_out(self):
        """Detach from grid and show as an independent window."""
        dlg = _ChartWindow(self._figure, self._series, self.window())
        self._close_chart()
        dlg.show()

    # ── Annotations (text / arrow / line) ────────────────────────────

    def _get_undo_stack(self):
        """Return the shared undo stack (from the source sheet), or None."""
        sheet = self._source_sheet
        return getattr(sheet, '_undo_stack', None) if sheet else None

    def _add_text_annotation(self):
        """Add a draggable text label at the centre of the current view."""
        text, ok = QInputDialog.getText(self, "Add Text", "Text:")
        if not ok or not text.strip():
            return
        xl, xr = self._ax.get_xlim()
        yb, yt = self._ax.get_ylim()
        cx, cy = (xl + xr) / 2, (yb + yt) / 2
        ann = self._ax.annotate(
            text, xy=(cx, cy), xytext=(cx, cy),
            fontsize=10, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', fc='wheat', alpha=0.8))
        ann.draggable(True)
        entry = {"type": "text", "artist": ann,
                 "text": text, "xy": (cx, cy)}
        self._annotations.append(entry)
        undo = self._get_undo_stack()
        if undo is not None:
            from .undo_commands import AddAnnotationCmd
            undo.push(AddAnnotationCmd(self, entry))
        self._canvas.draw_idle()

    def _add_arrow_annotation(self):
        """Add a draggable arrow from one data point to another."""
        text, ok = QInputDialog.getText(
            self, "Add Arrow", "Label (blank for none):")
        if not ok:
            return
        xl, xr = self._ax.get_xlim()
        yb, yt = self._ax.get_ylim()
        dx, dy = (xr - xl) * 0.15, (yt - yb) * 0.15
        cx, cy = (xl + xr) / 2, (yb + yt) / 2
        ann = self._ax.annotate(
            text, xy=(cx, cy), xytext=(cx + dx, cy + dy),
            fontsize=9,
            arrowprops=dict(arrowstyle='->', color='black', lw=1.5),
            bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.7)
            if text.strip() else None)
        ann.draggable(True)
        entry = {"type": "arrow", "artist": ann,
                 "text": text,
                 "xy": (cx, cy),
                 "xytext": (cx + dx, cy + dy)}
        self._annotations.append(entry)
        undo = self._get_undo_stack()
        if undo is not None:
            from .undo_commands import AddAnnotationCmd
            undo.push(AddAnnotationCmd(self, entry))
        self._canvas.draw_idle()

    def _add_line_annotation(self):
        """Add a finite line segment (like an arrow without arrowheads)."""
        xl, xr = self._ax.get_xlim()
        yb, yt = self._ax.get_ylim()
        dx, dy = (xr - xl) * 0.15, (yt - yb) * 0.15
        cx, cy = (xl + xr) / 2, (yb + yt) / 2
        ann = self._ax.annotate(
            "", xy=(cx - dx, cy - dy), xytext=(cx + dx, cy + dy),
            arrowprops=dict(arrowstyle='-', color='black', lw=1.5))
        ann.draggable(True)
        entry = {"type": "line", "artist": ann,
                 "xy": (cx - dx, cy - dy),
                 "xytext": (cx + dx, cy + dy)}
        self._annotations.append(entry)
        undo = self._get_undo_stack()
        if undo is not None:
            from .undo_commands import AddAnnotationCmd
            undo.push(AddAnnotationCmd(self, entry))
        self._canvas.draw_idle()

    # ── Annotation selection / deletion / properties ──────────────────

    def _try_select_ann_at_pos(self, qevent):
        """Select annotation under a Qt *qevent* (e.g. right-click)."""
        from .annotation_tools import hit_test_annotations
        try:
            canvas_pos = self._canvas.mapFromGlobal(qevent.globalPos())
            dpr = self._canvas.devicePixelRatio()
            # matplotlib display coords: origin at bottom-left, in
            # physical pixels.
            mx = canvas_pos.x() * dpr
            my = (self._canvas.height() - canvas_pos.y()) * dpr
            inv = self._ax.transData.inverted()
            xdata, ydata = inv.transform((mx, my))

            class _FakeEvent:
                pass
            fe = _FakeEvent()
            fe.inaxes = self._ax
            fe.xdata = xdata
            fe.ydata = ydata
            fe.x = mx
            fe.y = my
            idx = hit_test_annotations(fe, self._annotations,
                                       self._ax, self._canvas)
            if idx >= 0:
                self._select_annotation(idx)
            # Don't deselect on right-click miss — user may want chart
            # menu while annotation stays selected.
        except Exception:
            pass

    def _handle_annotation_click(self, event):
        """Select or deselect an annotation on single left-click."""
        from .annotation_tools import (hit_test_annotations,
                                        hit_test_handle)
        # If an arrow/line is selected, check for endpoint handle drag.
        if self._ann_handles and self._selected_ann_idx >= 0:
            h = hit_test_handle(event, self._ann_handles, self._ax)
            if h is not None:
                self._ann_dragging_handle = h
                return  # start endpoint drag
        # Check if clicking on an annotation.
        idx = hit_test_annotations(event, self._annotations,
                                   self._ax, self._canvas)
        if idx >= 0:
            if idx == self._selected_ann_idx:
                # Already selected — start body drag.
                a = self._annotations[idx]
                artist = a["artist"]
                self._ann_body_drag = {
                    "x0": event.xdata, "y0": event.ydata,
                    "xy0": tuple(artist.xy),
                    "xytext0": tuple(artist.get_position()),
                }
                return
            self._select_annotation(idx)
        else:
            self._deselect_annotation()

    def _select_annotation(self, idx):
        """Mark annotation *idx* as selected and draw visual cues."""
        from .annotation_tools import (draw_text_selection,
                                        draw_endpoint_handles,
                                        clear_selection_artists)
        self._deselect_annotation()
        if idx < 0 or idx >= len(self._annotations):
            return
        self._selected_ann_idx = idx
        a = self._annotations[idx]
        atype = a["type"]
        # Disable matplotlib's built-in draggable — we handle all
        # dragging ourselves so selection visuals stay in sync.
        try:
            a["artist"].draggable(False)
        except Exception:
            pass
        if atype == "text":
            arts = draw_text_selection(a["artist"], self._ax, self._canvas)
            self._ann_select_artists = arts
        elif atype in ("arrow", "line"):
            arts, handles = draw_endpoint_handles(
                a["artist"], self._ax, self._canvas)
            self._ann_select_artists = arts
            self._ann_handles = handles
        self.setFocus()
        self._canvas.draw_idle()

    def _deselect_annotation(self):
        """Clear annotation selection visuals."""
        from .annotation_tools import clear_selection_artists
        if self._selected_ann_idx < 0:
            return
        clear_selection_artists(self._ann_select_artists, self._canvas)
        self._ann_select_artists = []
        self._ann_handles = []
        self._ann_dragging_handle = None
        self._ann_body_drag = None
        # Re-enable draggable.
        if self._selected_ann_idx < len(self._annotations):
            a = self._annotations[self._selected_ann_idx]
            try:
                a["artist"].draggable(True)
            except Exception:
                pass
        self._selected_ann_idx = -1
        self._canvas.draw_idle()

    def _delete_selected_annotation(self):
        """Remove the currently selected annotation."""
        if self._selected_ann_idx < 0:
            return
        idx = self._selected_ann_idx
        a = self._annotations[idx]
        undo = self._get_undo_stack()
        if undo is not None:
            from .undo_commands import DeleteAnnotationCmd
            undo.push(DeleteAnnotationCmd(self, a, idx))
            return
        # Fallback — no undo stack.
        from .annotation_tools import clear_selection_artists
        clear_selection_artists(self._ann_select_artists, self._canvas)
        self._ann_select_artists = []
        self._ann_handles = []
        self._ann_dragging_handle = None
        self._annotations.pop(idx)
        try:
            a["artist"].remove()
        except Exception:
            pass
        dragger = a.get("dragger")
        if dragger is not None:
            try:
                dragger.disconnect()
            except Exception:
                pass
        self._selected_ann_idx = -1
        self._canvas.draw_idle()

    def _open_annotation_properties(self):
        """Open the Annotations Manager on the selected annotation."""
        self._open_annotations_manager(self._selected_ann_idx)

    def _open_annotations_manager(self, preselect_idx=None):
        """Open the Annotations Manager (list + properties + delete)."""
        if not self._annotations:
            return
        if not isinstance(preselect_idx, int) or preselect_idx < 0:
            preselect_idx = (self._selected_ann_idx
                             if self._selected_ann_idx >= 0 else None)
        from .annotation_tools import AnnotationsManagerDialog
        dlg = AnnotationsManagerDialog(self, self, preselect_idx)
        dlg.exec_()
        self._canvas.draw_idle()

    def keyPressEvent(self, event):
        """Delete selected annotation on Delete/Backspace."""
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self._selected_ann_idx >= 0:
                self._delete_selected_annotation()
                return
        if event.key() == Qt.Key_Escape:
            self._deselect_annotation()
            return
        super().keyPressEvent(event)

    def _on_ann_motion(self, event):
        """Drag an annotation endpoint or body."""
        if event.inaxes is not self._ax or event.xdata is None:
            return
        idx = self._selected_ann_idx
        if idx < 0 or idx >= len(self._annotations):
            return
        artist = self._annotations[idx]["artist"]
        t = self._ax.transData      # data → display pixel transform

        # Endpoint drag.
        h = self._ann_dragging_handle
        if h is not None:
            pt = (event.xdata, event.ydata)
            if h["role"] == "xy":
                artist.xy = pt
            else:
                artist.set_position(pt)
            # Handle circles live in display coords.
            h["artist"].center = t.transform(pt)
            self._canvas.draw_idle()
            return

        # Body drag (move whole annotation).
        bd = self._ann_body_drag
        if bd is not None:
            dx = event.xdata - bd["x0"]
            dy = event.ydata - bd["y0"]
            new_xy = (bd["xy0"][0] + dx, bd["xy0"][1] + dy)
            new_xyt = (bd["xytext0"][0] + dx, bd["xytext0"][1] + dy)
            artist.xy = new_xy
            artist.set_position(new_xyt)
            # Move endpoint handle circles (arrows/lines).
            for hh in self._ann_handles:
                data_pt = new_xy if hh["role"] == "xy" else new_xyt
                hh["artist"].center = t.transform(data_pt)
            # Move text selection rectangle (display coords).
            atype = self._annotations[idx]["type"]
            if atype == "text" and self._ann_select_artists:
                disp_dx = t.transform(new_xy)[0] - t.transform(bd["xy0"])[0]
                disp_dy = t.transform(new_xy)[1] - t.transform(bd["xy0"])[1]
                rect = self._ann_select_artists[0]
                x0, y0 = rect.get_x(), rect.get_y()
                if "_rect_x0" not in bd:
                    bd["_rect_x0"] = x0
                    bd["_rect_y0"] = y0
                rect.set_x(bd["_rect_x0"] + disp_dx)
                rect.set_y(bd["_rect_y0"] + disp_dy)
            self._canvas.draw_idle()

    def _on_ann_release(self, event):
        """Finish endpoint or body drag."""
        self._ann_dragging_handle = None
        self._ann_body_drag = None

    # ── Double-click opens axis properties ─────────────────────────
    def mouseDoubleClickEvent(self, event):
        self._open_axis_dialog("Bottom")

    # ── Fill between curves ─────────────────────────────────────────
    def apply_fill(self, series_idx, fill_mode, fill_target_idx,
                   fill_color, fill_alpha):
        """Add or update fill for a series.

        fill_mode: 'none', 'zero', 'series'
        fill_target_idx: index into self._series (for 'series' mode)
        """
        # Remove existing fill for this series.
        self._remove_fill(series_idx)

        # Store fill parameters on the series dict for persistence.
        s = self._series[series_idx]
        s["fill_mode"] = fill_mode
        s["fill_target"] = fill_target_idx
        s["fill_color"] = fill_color
        s["fill_alpha"] = fill_alpha

        if fill_mode == "none":
            return

        x, y = np.asarray(s["x"]), np.asarray(s["y"])

        if fill_mode == "zero":
            fc = self._ax.fill_between(
                x, y, 0, alpha=fill_alpha, color=fill_color,
                label="_nolegend_")
        elif fill_mode == "series" and 0 <= fill_target_idx < len(self._series):
            t = self._series[fill_target_idx]
            tx, ty = np.asarray(t["x"]), np.asarray(t["y"])
            # Sort target by X so np.interp works correctly.
            order = np.argsort(tx)
            y2 = np.interp(x, tx[order], ty[order])
            fc = self._ax.fill_between(
                x, y, y2, alpha=fill_alpha, color=fill_color,
                label="_nolegend_")
        else:
            return

        self._fill_artists.append((series_idx, fc))
        self._canvas.draw_idle()

    def _remove_fill(self, series_idx):
        """Remove fill artist for the given series index."""
        keep = []
        for idx, artist in self._fill_artists:
            if idx == series_idx:
                artist.remove()
            else:
                keep.append((idx, artist))
        self._fill_artists = keep

    # ── Legend building ───────────────────────────────────────────────
    def _legend_handles_labels(self, ax):
        """Return (handles, labels), using a filled-rectangle swatch for
        any series that has an area fill so the legend reflects the fill
        instead of showing a plain line."""
        handles, labels = ax.get_legend_handles_labels()
        if not self._fill_artists or not handles:
            return handles, labels
        from matplotlib.patches import Patch
        fills = {idx: fc for idx, fc in self._fill_artists}
        art2idx = {id(s.get("artist")): i
                   for i, s in enumerate(self._series)
                   if s.get("artist") is not None}
        new_handles = []
        for h, lab in zip(handles, labels):
            fc = fills.get(art2idx.get(id(h)))
            if fc is None:
                new_handles.append(h)
                continue
            # Face = the fill colour (keeps its translucency); edge and
            # width = the line's, so the swatch reads as "filled line".
            try:
                face = fc.get_facecolor()
                if hasattr(face, "__len__") and len(face):
                    face = face[0]
            except Exception:
                face = None
            edge, lw = None, 1.0
            try:
                edge = h.get_color()
                lw = h.get_linewidth()
            except Exception:
                pass
            new_handles.append(Patch(
                facecolor=face if face is not None else edge,
                edgecolor=edge, linewidth=lw, label=lab))
        return new_handles, labels

    def _install_legend(self, ax=None, **kw):
        """(Re)build the legend on *ax* with fill-aware swatches."""
        ax = ax if ax is not None else self._ax
        handles, labels = self._legend_handles_labels(ax)
        if not handles:
            existing = ax.get_legend()
            if existing is not None:
                existing.remove()
            return None
        kw.setdefault("loc", "best")
        kw.setdefault("framealpha", 0.8)
        if "prop" not in kw:
            kw.setdefault("fontsize", 8)
        leg = ax.legend(handles, labels, **kw)
        if leg:
            leg.set_draggable(True)
        return leg

    # ── Event filter on canvas ─────────────────────────────────────
    def eventFilter(self, obj, event):
        """Intercept mouse events on the canvas for drag / resize.

        Click+drag moves the chart, except when on the legend
        (matplotlib's draggable legend handles that).
        """
        if obj is not self._canvas and not self._canvas.isAncestorOf(obj):
            return super().eventFilter(obj, event)

        from PyQt5.QtCore import QEvent
        etype = event.type()

        # Only handle mouse events — other events (paint, resize, etc.)
        # don't carry a pos() and must pass through untouched.
        if etype not in (QEvent.MouseButtonPress, QEvent.MouseMove,
                         QEvent.MouseButtonRelease, QEvent.ContextMenu):
            return False

        # Right-click context menu: handle ourselves, don't let
        # matplotlib's canvas process it (can crash with 3D axes).
        if etype == QEvent.ContextMenu:
            self.contextMenuEvent(event)
            return True

        # Map event pos to canvas-local and chart-widget coords.
        if obj is self._canvas:
            canvas_pos = event.pos()
        else:
            canvas_pos = self._canvas.mapFromGlobal(
                obj.mapToGlobal(event.pos()))
        wpos = self._canvas.mapToParent(canvas_pos)

        if etype == QEvent.MouseButtonPress:
            # Block right-click from reaching matplotlib (prevents
            # crashes in 3D axes and lets our contextMenuEvent fire).
            if event.button() == Qt.RightButton:
                self._select()
                return True
            if event.button() == Qt.LeftButton:
                self._select()
                edge = self._hit_edge(wpos)
                if edge:
                    self._resizing = True
                    self._resize_edge = edge
                    self._drag_origin = event.globalPos()
                    self._drag_widget_pos = self.geometry()
                    return True   # consumed — resize only
                # Inside axes area: legend drag or axes reposition.
                if self._in_axes_area(canvas_pos):
                    if self._hit_legend(canvas_pos):
                        self._legend_dragging = True
                        return False  # let mpl handle legend drag
                    if self._pan_enabled:
                        # Start axes reposition (move subplot).
                        self._panning = True
                        self._pan_origin = canvas_pos
                        try:
                            sp = self._figure.subplotpars
                            self._pan_margins = {
                                "left": sp.left, "right": sp.right,
                                "top": sp.top, "bottom": sp.bottom,
                            }
                            if self._tight_layout:
                                self._figure.set_layout_engine("none")
                                self._tight_layout = False
                        except Exception:
                            self._panning = False
                        return True
                    # Not panning — let matplotlib handle (legend drag etc.)
                    return False
                # Outside axes (margins) → start chart drag.
                self._drag_origin = event.globalPos()
                self._drag_widget_pos = self.pos()
            return False  # let matplotlib see the press

        if etype == QEvent.MouseMove:
            # While legend is being dragged, let matplotlib handle.
            if self._legend_dragging:
                return False
            # Axes reposition: shift subplot margins.
            if self._panning:
                try:
                    fw = self._canvas.width()
                    fh = self._canvas.height()
                    dx = (canvas_pos.x() - self._pan_origin.x()) / fw
                    dy = (canvas_pos.y() - self._pan_origin.y()) / fh
                    m = self._pan_margins
                    new_left = m["left"] + dx
                    new_right = m["right"] + dx
                    new_top = m["top"] - dy
                    new_bottom = m["bottom"] - dy
                    # Clamp so axes stay within figure.
                    if (0.02 <= new_left and new_right <= 0.99 and
                            0.02 <= new_bottom and new_top <= 0.99):
                        self._figure.subplots_adjust(
                            left=new_left, right=new_right,
                            top=new_top, bottom=new_bottom)
                        self._canvas.draw_idle()
                except Exception:
                    pass
                return True
            if self._resizing and self._drag_origin is not None:
                delta = event.globalPos() - self._drag_origin
                geo = QRect(self._drag_widget_pos)
                edge = self._resize_edge
                if 'r' in edge:
                    geo.setRight(geo.right() + delta.x())
                if 'b' in edge:
                    geo.setBottom(geo.bottom() + delta.y())
                if 'l' in edge:
                    geo.setLeft(geo.left() + delta.x())
                if 't' in edge:
                    geo.setTop(geo.top() + delta.y())
                geo = self._constrain_ratio(geo, edge)
                if (geo.width() >= self.minimumWidth() and
                        geo.height() >= self.minimumHeight()):
                    self.setGeometry(geo)
                return True
            if self._drag_origin is not None and not self._resizing:
                delta = event.globalPos() - self._drag_origin
                new_pos = self._drag_widget_pos + delta
                self.move(new_pos)
                return True
            # Cursor feedback.
            edge = self._hit_edge(wpos)
            if edge:
                cursors = {
                    'r': Qt.SizeHorCursor, 'l': Qt.SizeHorCursor,
                    'b': Qt.SizeVerCursor, 't': Qt.SizeVerCursor,
                    'rb': Qt.SizeFDiagCursor, 'br': Qt.SizeFDiagCursor,
                    'lb': Qt.SizeBDiagCursor, 'bl': Qt.SizeBDiagCursor,
                    'rt': Qt.SizeBDiagCursor, 'tr': Qt.SizeBDiagCursor,
                    'lt': Qt.SizeFDiagCursor, 'tl': Qt.SizeFDiagCursor,
                }
                self.setCursor(cursors.get(edge, Qt.ArrowCursor))
                return True
            if self._in_axes_area(canvas_pos):
                if self._pan_enabled:
                    self.setCursor(Qt.OpenHandCursor)
                else:
                    self.setCursor(Qt.ArrowCursor)
                return False  # let mpl handle (legend drag etc.)
            self.setCursor(Qt.SizeAllCursor)
            return False

        if etype == QEvent.MouseButtonRelease:
            if self._legend_dragging:
                self._legend_dragging = False
                return False  # let mpl finalize
            if self._panning:
                self._panning = False
                return True
            if self._drag_origin is not None or self._resizing:
                self._drag_origin = None
                self._drag_widget_pos = None
                self._resizing = False
                self._resize_edge = None
                self.unsetCursor()
                return True
            return False

        return False

    # ── Drag to move ────────────────────────────────────────────────
    def _in_axes_area(self, canvas_pos):
        """True if *canvas_pos* (canvas-local QPoint) is inside the
        matplotlib axes rectangle, accounting for HiDPI scaling."""
        try:
            dpr = self._canvas.devicePixelRatio()
            cx = canvas_pos.x() * dpr
            cy = (self._canvas.height() - canvas_pos.y()) * dpr
            renderer = self._canvas.get_renderer()
            bbox = self._ax.get_window_extent(renderer)
            return (bbox.x0 <= cx <= bbox.x1 and
                    bbox.y0 <= cy <= bbox.y1)
        except Exception:
            return True  # fallback: assume inside

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._select()
            edge = self._hit_edge(event.pos())
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._drag_origin = event.globalPos()
                self._drag_widget_pos = self.geometry()
                event.accept()
                return
            # Drag from anywhere on the border.
            self._drag_origin = event.globalPos()
            self._drag_widget_pos = self.pos()
            self.setCursor(Qt.SizeAllCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing and self._drag_origin is not None:
            delta = event.globalPos() - self._drag_origin
            geo = QRect(self._drag_widget_pos)
            edge = self._resize_edge
            if 'r' in edge:
                geo.setRight(geo.right() + delta.x())
            if 'b' in edge:
                geo.setBottom(geo.bottom() + delta.y())
            if 'l' in edge:
                geo.setLeft(geo.left() + delta.x())
            if 't' in edge:
                geo.setTop(geo.top() + delta.y())
            geo = self._constrain_ratio(geo, edge)
            if geo.width() >= self.minimumWidth() and \
               geo.height() >= self.minimumHeight():
                self.setGeometry(geo)
            event.accept()
            return

        if self._drag_origin is not None and not self._resizing:
            delta = event.globalPos() - self._drag_origin
            new_pos = self._drag_widget_pos + delta
            self.move(new_pos)
            event.accept()
            return

        # Cursor feedback: resize edges or move.
        edge = self._hit_edge(event.pos())
        if edge:
            cursors = {
                'r': Qt.SizeHorCursor, 'l': Qt.SizeHorCursor,
                'b': Qt.SizeVerCursor, 't': Qt.SizeVerCursor,
                'rb': Qt.SizeFDiagCursor, 'br': Qt.SizeFDiagCursor,
                'lb': Qt.SizeBDiagCursor, 'bl': Qt.SizeBDiagCursor,
                'rt': Qt.SizeBDiagCursor, 'tr': Qt.SizeBDiagCursor,
                'lt': Qt.SizeFDiagCursor, 'tl': Qt.SizeFDiagCursor,
            }
            self.setCursor(cursors.get(edge, Qt.ArrowCursor))
        else:
            self.setCursor(Qt.SizeAllCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_origin = None
        self._drag_widget_pos = None
        self._resizing = False
        self._resize_edge = None
        self.unsetCursor()
        super().mouseReleaseEvent(event)

    # ── Selection ───────────────────────────────────────────────────
    def _select(self):
        """Mark this chart as selected on the parent sheet."""
        if self._source_sheet:
            # Deselect previous
            prev = getattr(self._source_sheet, '_selected_chart', None)
            if prev and prev is not self:
                prev._set_selected(False)
            self._source_sheet._selected_chart = self
            self._set_selected(True)
            # Auto-highlight source data when selected
            if not getattr(self, '_show_data_active', False):
                self._show_data_active = True
                self._apply_show_data()

    def _set_selected(self, selected):
        """Visual feedback for selection — border + handles."""
        if not selected:
            # Clear data highlights when deselected
            if getattr(self, '_show_data_active', False):
                self._show_data_active = False
                self._clear_show_data()
        if selected:
            self._handle_overlay.setGeometry(0, 0, self.width(), self.height())
            self._handle_overlay.show()
            self._handle_overlay.raise_()
        else:
            self._handle_overlay.hide()
        self.update()

    def _hit_edge(self, pos):
        """Return a string like 'r', 'rb', 'l' etc. if pos is near
        a resize edge/corner, or '' if not."""
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()
        edge = ''
        if x >= w - _HANDLE:
            edge += 'r'
        elif x <= _HANDLE:
            edge += 'l'
        if y >= h - _HANDLE:
            edge += 'b'
        elif y <= _HANDLE:
            edge += 't'
        return edge

    # ── Keep handle overlay in sync with widget size ─────────────
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._handle_overlay.isVisible():
            self._handle_overlay.setGeometry(0, 0, self.width(), self.height())


class _ChartWindow(QDialog):
    """Fallback: pop-out a chart to its own window."""

    def __init__(self, figure, series, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chart (detached)")
        self.setMinimumSize(400, 300)
        self.resize(600, 400)
        self.setWindowFlags(
            Qt.Window | Qt.WindowMinMaxButtonsHint
            | Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        fig = Figure(figsize=(6, 4), dpi=100)
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)

        for s in series:
            EmbeddedChart._plot_one(
                ax, s["x"], s["y"], s["label"], s["plot_type"])
        leg = ax.legend(loc="best", framealpha=0.8, fontsize=8)
        if leg:
            leg.set_draggable(True)

        toolbar = NavigationToolbar(canvas, self)
        toolbar.setIconSize(QSize(18, 18))
        layout.addWidget(toolbar)
        layout.addWidget(canvas, stretch=1)

        try:
            fig.set_layout_engine("tight")
        except Exception:
            try:
                fig.tight_layout()
            except Exception:
                pass


# ── Plot Details Dialog ─────────────────────────────────────────────
# Simplified version of KhervePlot's PlotDetailsDialog — single layer,
# series list on the left, property tabs on the right.

_LINE_STYLES = [
    ("Solid", "-"), ("Dashed", "--"), ("Dotted", ":"),
    ("Dash-dot", "-."), ("None", "None"),
]

_MARKERS = [
    ("None", "None"), ("Circle", "o"), ("Square", "s"),
    ("Diamond", "D"), ("Triangle up", "^"), ("Triangle down", "v"),
    ("Plus", "+"), ("Cross", "x"), ("Star", "*"),
    ("Point", "."),
]


# Scoped stylesheet that restores the default grey look of the
# non-native QColorDialog. On Windows there is no native colour dialog,
# so QColorDialog is always Qt's own widget; under the app-wide
# stylesheet its internal custom widgets (gradient picker, swatch
# arrays, preview) otherwise render with black backgrounds.
_COLOR_DIALOG_QSS = (
    "QColorDialog { background:#f0f0f0; }"
    "QColorDialog QWidget { background:#f0f0f0; color:#000000; }"
    "QColorDialog QLabel { background:transparent; color:#000000; }"
    "QColorDialog QLineEdit, QColorDialog QSpinBox {"
    " background:#ffffff; color:#000000; border:1px solid #a0a0a0;"
    " border-radius:2px; padding:2px 4px; }"
    "QColorDialog QPushButton {"
    " background:#e1e1e1; color:#000000; border:1px solid #a0a0a0;"
    " border-radius:2px; padding:3px 10px; }"
    "QColorDialog QPushButton:hover {"
    " background:#e6efff; border-color:#3a78b4; }"
)


def _pick_color(initial, parent):
    """Open a colour picker with the default grey look and return the
    chosen colour as a hex string, or None if cancelled."""
    dlg = QColorDialog(QColor(initial), parent)
    dlg.setStyleSheet(_COLOR_DIALOG_QSS)
    if dlg.exec_() == QColorDialog.Accepted:
        c = dlg.selectedColor()
        if c.isValid():
            return c.name()
    return None


class _ColorButton(QPushButton):
    """Small button that shows and edits a colour."""

    def __init__(self, color="#1f77b4", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(28, 22)
        self._update_style()
        self.clicked.connect(self._pick)

    def color(self):
        return self._color

    def set_color(self, c):
        self._color = c
        self._update_style()

    def _update_style(self):
        self.setStyleSheet(
            f"background: {self._color}; border: 1px solid #888;")

    def _pick(self):
        c = _pick_color(self._color, self)
        if c is not None:
            self._color = c
            self._update_style()


class _HideSafeModalDialog(QDialog):
    """A modal dialog whose modal loop survives ``hide()`` / ``show()``.

    ``QDialog.exec_()`` returns the instant the dialog is hidden.  That
    breaks the Add-Series column picker, which hides the dialog (and its
    parent) so the user can click the sheet grid: exec_ returned
    ``Rejected`` immediately, so no series was ever added.

    ``run()`` spins its own ``QEventLoop`` instead.  Hiding then merely
    relinquishes the modal block (the grid becomes clickable) and
    re-showing restores it — without ending the loop.  Only accept /
    reject / done end it.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._run_loop = None
        self._run_result = QDialog.Rejected

    def run(self):
        """Show modally and block until accept/reject, surviving hide()."""
        from PyQt5.QtCore import QEventLoop
        self._run_result = QDialog.Rejected
        self.setModal(True)
        self.show()
        self.raise_()
        self.activateWindow()
        self._run_loop = QEventLoop()
        self._run_loop.exec_()
        self._run_loop = None
        return self._run_result

    def done(self, code):
        # If run() is driving us, quit our own loop; otherwise fall back
        # to the normal QDialog behaviour (in case exec_() is ever used).
        loop = self._run_loop
        if loop is not None:
            self._run_result = int(code)
            self.hide()
            if loop.isRunning():
                loop.quit()
        else:
            super().done(code)


class _AddSeriesDialog(_HideSafeModalDialog):
    """Dialog for adding a chart series with mouse-pick support.

    Provides Y-range (required) and X-range (optional) fields, each with
    a pick button.  When the user clicks a pick button the dialog hides,
    and the next column-header click in the sheet fills in the range.
    """

    def __init__(self, sheet, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Series")
        self._sheet = sheet

        layout = QVBoxLayout(self)

        # ── Y range row ──────────────────────────────────────────
        y_row = QHBoxLayout()
        y_row.addWidget(QLabel("Y data range:"))
        self.y_range = QLineEdit()
        self.y_range.setPlaceholderText("e.g. C1:C50")
        y_row.addWidget(self.y_range)
        y_pick = QToolButton()
        y_pick.setText("\u2316")            # crosshair
        y_pick.setToolTip("Pick Y column from the sheet")
        y_pick.clicked.connect(lambda: self._start_pick(self.y_range))
        y_row.addWidget(y_pick)
        layout.addLayout(y_row)

        # ── X range row (optional) ───────────────────────────────
        x_row = QHBoxLayout()
        x_row.addWidget(QLabel("X data range:"))
        self.x_range = QLineEdit()
        self.x_range.setPlaceholderText("optional — leave empty for row index")
        x_row.addWidget(self.x_range)
        x_pick = QToolButton()
        x_pick.setText("\u2316")
        x_pick.setToolTip("Pick X column from the sheet")
        x_pick.clicked.connect(lambda: self._start_pick(self.x_range))
        x_row.addWidget(x_pick)
        layout.addLayout(x_row)

        # ── Buttons ──────────────────────────────────────────────
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._pick_target = None
        self._parent_dlg = parent

    # ── Pick mode ────────────────────────────────────────────────
    def _status(self, text, timeout=0):
        """Route a status message to the main window, if reachable.

        The sheet is a ``SheetWidget`` and has no ``_status_msg`` of its
        own — that lives on the ``MainWindow``.  Calling it on the sheet
        raised an ``AttributeError`` inside the button slot, which aborts
        the whole process.  Reach the top-level window instead.
        """
        win = self._sheet.window()
        if hasattr(win, "_status_msg"):
            win._status_msg(text, timeout)

    def _start_pick(self, line_edit):
        """Collapse the dialog chain and wait for a sheet selection."""
        if self._pick_target is not None:
            return  # a pick is already in progress
        self._pick_target = line_edit
        # Hide this dialog *and* the modal parent, otherwise the parent
        # keeps blocking input to the grid and the pick can never land.
        self.hide()
        if self._parent_dlg is not None:
            self._parent_dlg.hide()
        table = self._sheet.table
        # Connect to column header click.
        hdr = table.horizontalHeader()
        hdr.sectionClicked.connect(self._on_header_click)
        # Also allow clicking any cell.
        table.cellPressed.connect(self._on_cell_click)
        self._status(
            "Click a column header or cell to select the range\u2026")

    def _finish_pick(self, col_idx):
        """Fill the target field with the full-column range and re-show."""
        table = self._sheet.table
        # Disconnect signals.
        try:
            table.horizontalHeader().sectionClicked.disconnect(
                self._on_header_click)
        except TypeError:
            pass
        try:
            table.cellPressed.disconnect(self._on_cell_click)
        except TypeError:
            pass
        # Build range string (e.g. "B1:B161").
        # Find last non-empty row in this column.
        last = 0
        for r in range(table.rowCount()):
            it = table.item(r, col_idx)
            if it and it.text():
                last = r
        col_letter = self._col_letter(col_idx)
        rng = f"{col_letter}1:{col_letter}{last + 1}"
        if self._pick_target is not None:
            self._pick_target.setText(rng)
            self._pick_target = None
        self._status("", 0)
        if self._parent_dlg is not None:
            self._parent_dlg.show()
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_header_click(self, logical_idx):
        self._finish_pick(logical_idx)

    def _on_cell_click(self, row, col):
        self._finish_pick(col)

    @staticmethod
    def _col_letter(idx):
        """Convert 0-based column index to Excel letter (A, B, … Z, AA)."""
        result = ""
        n = idx + 1
        while n > 0:
            n, rem = divmod(n - 1, 26)
            result = chr(65 + rem) + result
        return result


class PlotDetailsDialog(_HideSafeModalDialog):
    """Series Properties — per-series list + property tabs."""

    def __init__(self, chart, parent=None):
        super().__init__(parent or chart)
        self.setWindowTitle("Series Properties")
        self.resize(780, 480)
        self._chart = chart

        outer = QVBoxLayout(self)

        sp = QSplitter(Qt.Horizontal)
        outer.addWidget(sp, stretch=1)

        # ── Series list (checkable) ────────────────────────────────
        self._series_list = QListWidget()
        self._series_list.setMinimumWidth(140)
        from PyQt5.QtWidgets import QListWidgetItem
        for i, s in enumerate(chart._series):
            item = QListWidgetItem(s["label"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            visible = True
            artist = s.get("artist")
            if artist is not None and hasattr(artist, 'get_visible'):
                visible = artist.get_visible()
            item.setCheckState(Qt.Checked if visible else Qt.Unchecked)
            self._series_list.addItem(item)
        sp.addWidget(self._series_list)

        # ── Tabs ────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        sp.addWidget(self._tabs)
        sp.setSizes([160, 480])

        self._build_data_tab()
        self._build_line_tab()
        self._build_symbol_tab()
        self._build_fill_tab()
        self._build_bar_tab()
        self._build_pie_tab()
        self._build_heatmap_tab()
        self._build_surface3d_tab()

        # Per-series range edits: {row: (x_range_str, y_range_str)}
        self._range_edits = {}
        self._series_list.currentRowChanged.connect(self._on_series)
        if self._series_list.count():
            self._series_list.setCurrentRow(0)

        # ── Footer ──────────────────────────────────────────────────
        footer = QHBoxLayout()
        general_btn = QPushButton("General Properties\u2026")
        general_btn.clicked.connect(self._open_general_props)
        footer.addWidget(general_btn)
        axis_btn = QPushButton("Axis Properties\u2026")
        axis_btn.clicked.connect(self._open_axis_props)
        footer.addWidget(axis_btn)
        add_btn = QPushButton("Add Series")
        add_btn.clicked.connect(self._add_series)
        footer.addWidget(add_btn)
        remove_btn = QPushButton("Remove Series")
        remove_btn.clicked.connect(self._remove_series)
        footer.addWidget(remove_btn)
        footer.addStretch()
        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply
            | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.Apply).clicked.connect(
            lambda: self.apply_to_chart(self._chart))
        footer.addWidget(bb)
        outer.addLayout(footer)

    def _build_data_tab(self):
        """Data range tab — shows and allows editing the plotted range."""
        w = QWidget()
        form = QFormLayout(w)

        from PyQt5.QtWidgets import QCheckBox
        self.header_check = QCheckBox("First row is a header")
        self.header_check.setToolTip(
            "Name each series after the first row of its column "
            "(updates the legend, and tracks edits to that row).")
        self.header_check.setChecked(
            bool(getattr(self._chart, "_header_row", False)))
        form.addRow(self.header_check)

        self.x_range_edit = QLineEdit()
        self.x_range_edit.setPlaceholderText("e.g. A1:A20")
        form.addRow("X Range:", self.x_range_edit)

        self.y_range_edit = QLineEdit()
        self.y_range_edit.setPlaceholderText("e.g. B1:B20")
        form.addRow("Y Range:", self.y_range_edit)

        self.data_info = QLabel("")
        self.data_info.setWordWrap(True)
        form.addRow("Points:", self.data_info)

        self._tabs.addTab(w, "Data")

    # Custom result codes for dialog switching.
    SWITCH_TO_AXIS = 2
    SWITCH_TO_GENERAL = 4

    def _open_axis_props(self):
        """Close Series Properties and signal to open Axis Properties."""
        self.apply_to_chart(self._chart)
        self.done(self.SWITCH_TO_AXIS)

    def _open_general_props(self):
        """Close Series Properties and signal to open General Properties."""
        self.apply_to_chart(self._chart)
        self.done(self.SWITCH_TO_GENERAL)

    def _add_series(self):
        """Add a new series via a dialog with mouse-pick buttons."""
        chart = self._chart
        sheet = chart._source_sheet
        if not sheet:
            return
        dlg = _AddSeriesDialog(sheet, self)
        if dlg.run() != QDialog.Accepted:
            return
        y_rng = dlg.y_range.text().strip()
        x_rng = dlg.x_range.text().strip()
        parsed_y = self._parse_range(y_rng)
        if parsed_y is None:
            return
        y_col, r1, r2 = parsed_y
        label = self._col_letter(y_col)
        y_all = sheet.numeric_column(y_col)
        # X data: use picked X range, chart's X column, or row index.
        if x_rng:
            parsed_x = self._parse_range(x_rng)
            if parsed_x is not None:
                x_col, xr1, xr2 = parsed_x
                x_all = sheet.numeric_column(x_col)
                r1 = max(r1, xr1)
                r2 = min(r2, xr2)
            else:
                x_all = np.arange(sheet.row_count(), dtype=float)
        elif chart._x_col is not None:
            x_all = sheet.numeric_column(chart._x_col)
        else:
            x_all = np.arange(sheet.row_count(), dtype=float)
        x_slice = x_all[r1:r2 + 1]
        y_slice = y_all[r1:r2 + 1]
        mask = ~(np.isnan(x_slice) | np.isnan(y_slice))
        x, y = x_slice[mask], y_slice[mask]
        if len(x) == 0:
            QMessageBox.information(
                self, "Add Series",
                f"No numeric data found in {y_rng or 'the chosen range'}.\n\n"
                "Pick a column that contains numbers, or check that the "
                "range covers the data rows.")
            return
        chart.add_series(x, y, label, "Line", y_col=y_col,
                         row_start=r1, row_end=r2)
        from PyQt5.QtWidgets import QListWidgetItem
        item = QListWidgetItem(label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        self._series_list.addItem(item)
        self.fill_target.addItem(label)
        self._series_list.setCurrentRow(self._series_list.count() - 1)

    def _remove_series(self):
        """Remove the currently selected series."""
        chart = self._chart
        row = self._series_list.currentRow()
        if row < 0 or row >= len(chart._series):
            return
        if len(chart._series) <= 1:
            return  # keep at least one series
        # Remove artist from axes.
        s = chart._series[row]
        artist = s.get("artist")
        if artist is not None:
            try:
                artist.remove()
            except Exception:
                if hasattr(artist, '__iter__'):
                    for child in artist:
                        try:
                            child.remove()
                        except Exception:
                            pass
        # Remove fill artists for this series.
        chart._remove_fill(row)
        # Update fill indices for remaining series.
        chart._fill_artists = [
            (i if i < row else i - 1, a)
            for i, a in chart._fill_artists]
        # Remove from data structures.
        chart._series.pop(row)
        if row < len(chart._y_cols):
            chart._y_cols.pop(row)
        # Update dialog list.
        self._series_list.takeItem(row)
        # Refresh fill target combo.
        self.fill_target.clear()
        for s in chart._series:
            self.fill_target.addItem(s["label"])
        # Refresh legend.
        chart._install_legend()
        chart._canvas.draw_idle()
        if self._series_list.count():
            self._series_list.setCurrentRow(
                min(row, self._series_list.count() - 1))

    @staticmethod
    def _col_letter(col_idx):
        """Convert 0-based column index to letter (A, B, ... Z, AA...)."""
        result = ""
        n = col_idx
        while True:
            result = chr(ord('A') + n % 26) + result
            n = n // 26 - 1
            if n < 0:
                break
        return result

    def _range_string(self, col_idx, data_len):
        """Build a range string like 'A1:A20' from column index and
        data length."""
        letter = self._col_letter(col_idx)
        return f"{letter}1:{letter}{data_len}"

    _PLOT_TYPES = [
        "Line", "Scatter", "Line+Symbol", "Bar", "Step", "Stem",
        "Histogram", "Pie", "Doughnut", "3D Pie",
        "Heatmap", "3D Surface",
    ]

    def _build_line_tab(self):
        w = QWidget()
        form = QFormLayout(w)

        self.label_edit = QLineEdit()
        form.addRow("Label:", self.label_edit)

        self.plot_type_combo = QComboBox()
        self.plot_type_combo.addItems(self._PLOT_TYPES)
        form.addRow("Plot Type:", self.plot_type_combo)

        self.line_style = QComboBox()
        for name, _ in _LINE_STYLES:
            self.line_style.addItem(name)
        form.addRow("Style:", self.line_style)

        self.line_width = QDoubleSpinBox()
        self.line_width.setRange(0.0, 20.0)
        self.line_width.setSingleStep(0.5)
        self.line_width.setValue(_DEFAULT_LINEWIDTH)
        form.addRow("Width:", self.line_width)

        self.line_color = _ColorButton()
        form.addRow("Color:", self.line_color)

        self._tabs.addTab(w, "Line")

    def _build_symbol_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        self.marker_combo = QComboBox()
        for name, _ in _MARKERS:
            self.marker_combo.addItem(name)
        self.marker_size = QDoubleSpinBox()
        self.marker_size.setRange(0.0, 50.0)
        self.marker_size.setSingleStep(0.5)
        self.marker_size.setValue(_DEFAULT_MARKERSIZE)
        self.marker_fill = _ColorButton()
        self.marker_edge = _ColorButton("#000000")

        form.addRow("Marker:", self.marker_combo)
        form.addRow("Size:", self.marker_size)
        form.addRow("Fill Color:", self.marker_fill)
        form.addRow("Edge Color:", self.marker_edge)
        self._tabs.addTab(w, "Symbol")

    def _build_fill_tab(self):
        """Fill Under Curve tab — fill to zero or to another series."""
        w = QWidget()
        form = QFormLayout(w)

        self.fill_mode = QComboBox()
        self.fill_mode.addItems(["None", "Fill to Zero", "Fill to Series"])
        form.addRow("Fill Mode:", self.fill_mode)

        # Target series combo (for "Fill to Series")
        self.fill_target = QComboBox()
        for s in self._chart._series:
            self.fill_target.addItem(s["label"])
        form.addRow("Target Series:", self.fill_target)

        self.fill_color = _ColorButton("#1f77b4")
        form.addRow("Fill Color:", self.fill_color)

        self.fill_alpha = QDoubleSpinBox()
        self.fill_alpha.setRange(0.0, 1.0)
        self.fill_alpha.setSingleStep(0.05)
        self.fill_alpha.setValue(0.3)
        form.addRow("Opacity:", self.fill_alpha)

        # Enable/disable target based on mode.
        self.fill_mode.currentIndexChanged.connect(
            lambda i: self.fill_target.setEnabled(i == 2))
        self.fill_target.setEnabled(False)

        self._tabs.addTab(w, "Fill")

    def _build_bar_tab(self):
        """Bar options tab — delegates to bar_options.BarOptionsTab."""
        from .bar_options import BarOptionsTab
        self._bar_tab = BarOptionsTab(self._chart, self)
        self._bar_tab_idx = self._tabs.addTab(self._bar_tab, "Bar")

    def _build_pie_tab(self):
        """Pie options tab — delegates to pie_options.PieOptionsTab."""
        from .pie_options import PieOptionsTab
        self._pie_tab = PieOptionsTab(self._chart, self)
        self._pie_tab_idx = self._tabs.addTab(self._pie_tab, "Pie")

    def _build_heatmap_tab(self):
        """Heatmap options tab."""
        from .heatmap_options import HeatmapOptionsTab
        self._heatmap_tab = HeatmapOptionsTab(self._chart, self)
        self._heatmap_tab_idx = self._tabs.addTab(
            self._heatmap_tab, "Heatmap")

    def _build_surface3d_tab(self):
        """3D Surface options tab."""
        from .heatmap_options import Surface3DOptionsTab
        self._surface3d_tab = Surface3DOptionsTab(self._chart, self)
        self._surface3d_tab_idx = self._tabs.addTab(
            self._surface3d_tab, "3D Surface")

    def _save_current_range(self):
        """Save range edit values for the previously selected series."""
        prev = getattr(self, '_prev_series_row', -1)
        if prev >= 0:
            self._range_edits[prev] = (
                self.x_range_edit.text(),
                self.y_range_edit.text())

    def _on_series(self, row):
        """Populate widgets from the selected series."""
        # Save range edits from the previous series before switching.
        self._save_current_range()
        self._prev_series_row = row

        if row < 0 or row >= len(self._chart._series):
            return
        s = self._chart._series[row]
        artist = s.get("artist")
        self.label_edit.setText(s["label"])

        # Plot type combo.
        pt = s.get("plot_type", "Line")
        idx = self.plot_type_combo.findText(pt)
        if idx >= 0:
            self.plot_type_combo.setCurrentIndex(idx)

        # Data tab — restore saved range edits or build from data.
        if row in self._range_edits:
            x_rng, y_rng = self._range_edits[row]
            self.x_range_edit.setText(x_rng)
            self.y_range_edit.setText(y_rng)
        else:
            chart = self._chart
            n_pts = len(s.get("x", []))
            x_col = s.get("x_col", chart._x_col)
            y_cols = chart._y_cols
            # Use stored row range if available, otherwise full range.
            x_r1 = s.get("x_row_start", 0)
            x_r2 = s.get("x_row_end", n_pts - 1) if n_pts else 0
            if x_col is not None:
                letter = self._col_letter(x_col)
                self.x_range_edit.setText(
                    f"{letter}{x_r1 + 1}:{letter}{x_r2 + 1}")
            else:
                # No explicit X column — show the row range that
                # matches the Y range (1-based display).
                self.x_range_edit.setText(
                    f"{x_r1 + 1}:{x_r2 + 1}  (row index)")
            if row < len(y_cols):
                y_r1 = s.get("y_row_start", 0)
                y_r2 = s.get("y_row_end", n_pts - 1) if n_pts else 0
                letter = self._col_letter(y_cols[row])
                self.y_range_edit.setText(
                    f"{letter}{y_r1 + 1}:{letter}{y_r2 + 1}")
            else:
                self.y_range_edit.setText("")

        # Update data info — show matrix dims for heatmap/3D surface.
        import numpy as np
        y_data = s.get("y", [])
        pt = s.get("plot_type", "Line")
        if pt in ("Heatmap", "3D Surface"):
            arr = np.atleast_2d(np.asarray(y_data))
            rows, cols = arr.shape
            self.data_info.setText(f"{rows} \u00d7 {cols} matrix")
            # Show matrix dimensions as ranges if no saved edit.
            if row not in self._range_edits:
                self.x_range_edit.setText(f"1:{cols}  (columns)")
                self.y_range_edit.setText(f"1:{rows}  (rows)")
        else:
            n_pts = len(s.get("x", []))
            self.data_info.setText(str(n_pts))

        # Try to read line/scatter properties from the artist.
        from matplotlib.colors import to_hex
        from matplotlib.collections import PathCollection
        from matplotlib.container import BarContainer
        is_scatter = isinstance(artist, PathCollection)
        is_bar = isinstance(artist, BarContainer)

        if is_bar:
            # BarContainer — read face colour into Line tab colour.
            if artist.patches:
                try:
                    self.line_color.set_color(
                        to_hex(artist.patches[0].get_facecolor()))
                except Exception:
                    pass
        elif is_scatter:
            # Scatter: PathCollection has different APIs.
            try:
                fc = artist.get_facecolors()
                if len(fc) > 0:
                    self.line_color.set_color(to_hex(fc[0]))
                    self.marker_fill.set_color(to_hex(fc[0]))
            except Exception:
                pass
            try:
                ec = artist.get_edgecolors()
                if len(ec) > 0:
                    self.marker_edge.set_color(to_hex(ec[0]))
            except Exception:
                pass
            try:
                sizes = artist.get_sizes()
                if len(sizes) > 0:
                    self.marker_size.setValue(sizes[0] ** 0.5)
            except Exception:
                pass
            # Restore marker shape from series dict.
            saved_mk = s.get("marker", "o")
            for i, (_, code) in enumerate(_MARKERS):
                if code == str(saved_mk):
                    self.marker_combo.setCurrentIndex(i)
                    break
        elif artist is not None:
            # Line2D artist.
            if hasattr(artist, 'get_linestyle'):
                ls = artist.get_linestyle()
                for i, (_, code) in enumerate(_LINE_STYLES):
                    if code == ls:
                        self.line_style.setCurrentIndex(i)
                        break
            if hasattr(artist, 'get_linewidth'):
                lw = artist.get_linewidth()
                if hasattr(lw, '__len__'):
                    lw = float(lw[0]) if len(lw) else 1.0
                self.line_width.setValue(float(lw))
            if hasattr(artist, 'get_color'):
                c = artist.get_color()
                if isinstance(c, str):
                    self.line_color.set_color(c)
                elif hasattr(c, '__len__') and len(c) >= 3:
                    self.line_color.set_color(to_hex(c))
            # Marker
            if hasattr(artist, 'get_marker'):
                mk = artist.get_marker()
                for i, (_, code) in enumerate(_MARKERS):
                    if code == str(mk):
                        self.marker_combo.setCurrentIndex(i)
                        break
            if hasattr(artist, 'get_markersize'):
                self.marker_size.setValue(artist.get_markersize())
            if hasattr(artist, 'get_markerfacecolor'):
                c = artist.get_markerfacecolor()
                if isinstance(c, str) and c != 'none':
                    self.marker_fill.set_color(c)
                elif hasattr(c, '__len__') and len(c) >= 3:
                    self.marker_fill.set_color(to_hex(c))

        # Fill — restore from series dict.
        fm = s.get("fill_mode", "none")
        mode_map = {"none": 0, "zero": 1, "series": 2}
        self.fill_mode.setCurrentIndex(mode_map.get(fm, 0))
        self.fill_target.setEnabled(fm == "series")
        ft = s.get("fill_target", 0)
        if 0 <= ft < self.fill_target.count():
            self.fill_target.setCurrentIndex(ft)
        fc = s.get("fill_color")
        if fc:
            self.fill_color.set_color(fc)
        elif is_scatter:
            try:
                fcs = artist.get_facecolors()
                if len(fcs) > 0:
                    self.fill_color.set_color(to_hex(fcs[0]))
            except Exception:
                pass
        elif artist is not None and hasattr(artist, 'get_color'):
            c = artist.get_color()
            if isinstance(c, str):
                self.fill_color.set_color(c)
        fa = s.get("fill_alpha")
        if fa is not None:
            self.fill_alpha.setValue(fa)

        # Bar tab — populate from series data and enable/disable.
        pt = s.get("plot_type", "Line")
        if hasattr(self, '_bar_tab'):
            self._bar_tab.read_from_series(s)
            self._tabs.setTabEnabled(self._bar_tab_idx, pt == "Bar")

        # Pie tab — populate from chart config and enable/disable.
        from .pie_options import PIE_TYPES
        if hasattr(self, '_pie_tab'):
            is_pie = pt in PIE_TYPES
            self._tabs.setTabEnabled(self._pie_tab_idx, is_pie)
            if is_pie:
                self._pie_tab.read_from_config(
                    getattr(self._chart, '_pie_config', {}))

        # Heatmap tab — enable only for Heatmap.
        if hasattr(self, '_heatmap_tab'):
            self._tabs.setTabEnabled(
                self._heatmap_tab_idx, pt == "Heatmap")
            if pt == "Heatmap":
                self._heatmap_tab.read_from_config(
                    getattr(self._chart, '_heatmap_config', {}))

        # 3D Surface tab — enable only for 3D Surface.
        if hasattr(self, '_surface3d_tab'):
            self._tabs.setTabEnabled(
                self._surface3d_tab_idx, pt == "3D Surface")
            if pt == "3D Surface":
                self._surface3d_tab.read_from_config(
                    getattr(self._chart, '_surface3d_config', {}))

    @staticmethod
    def _parse_range(range_str):
        """Parse a range like 'A1:A20' into (col_idx, row_start, row_end).

        Returns None on failure.
        """
        import re
        m = re.match(r'^([A-Za-z]+)(\d+):([A-Za-z]+)(\d+)$',
                     range_str.strip())
        if not m:
            return None
        col_letter = m.group(1).upper()
        r1 = int(m.group(2)) - 1    # 0-based
        r2 = int(m.group(4)) - 1
        # Convert letter to index.
        col = 0
        for ch in col_letter:
            col = col * 26 + (ord(ch) - ord('A') + 1)
        col -= 1  # 0-based
        return col, min(r1, r2), max(r1, r2)

    def apply_to_chart(self, chart):
        """Apply all settings to the chart."""
        ax = chart._ax

        # ── Apply visibility from checkboxes ──────────────────────
        for i in range(self._series_list.count()):
            if i >= len(chart._series):
                break
            item = self._series_list.item(i)
            visible = (item.checkState() == Qt.Checked)
            artist = chart._series[i].get("artist")
            if artist is not None and hasattr(artist, 'set_visible'):
                artist.set_visible(visible)

        # ── Apply data range changes for ALL series ────────────────
        # Save the current series' range edits first.
        self._save_current_range()
        sheet = chart._source_sheet
        if sheet:
            for sr, (x_rng, y_rng) in self._range_edits.items():
                if 0 <= sr < len(chart._series):
                    self._apply_range_edit_for(
                        chart, sr, sheet, x_rng, y_rng)

        row = self._series_list.currentRow()
        # Series settings for currently selected series
        if 0 <= row < len(chart._series):
            s = chart._series[row]

            # Change plot type if different.
            new_pt = self.plot_type_combo.currentText()
            if new_pt != s.get("plot_type"):
                if not chart.change_series_type(row, new_pt):
                    QMessageBox.information(
                        self, "Plot Type",
                        "This series holds a 2-D matrix of data — "
                        "it can only be shown as a Heatmap or a "
                        "3D Surface.")
                    idx = self.plot_type_combo.findText(
                        s.get("plot_type", "Line"))
                    if idx >= 0:
                        self.plot_type_combo.setCurrentIndex(idx)

            artist = s.get("artist")
            s["label"] = self.label_edit.text()

            from matplotlib.collections import PathCollection
            from matplotlib.container import BarContainer
            is_scatter = isinstance(artist, PathCollection)
            is_bar = isinstance(artist, BarContainer)

            if is_bar:
                # BarContainer — colour is set via _redraw_bars; just
                # sync the fill_color into bar props from Line tab.
                bp = s.setdefault("bar", {})
                bp["fill_color"] = self.line_color.color()
                if hasattr(artist, 'set_label'):
                    for p in artist.patches:
                        pass  # label is on container
                    artist.set_label(self.label_edit.text())
            elif is_scatter:
                # PathCollection (scatter) — use collection APIs.
                try:
                    artist.set_facecolors(self.marker_fill.color())
                except Exception:
                    pass
                try:
                    artist.set_edgecolors(self.marker_edge.color())
                except Exception:
                    pass
                try:
                    sz = self.marker_size.value()
                    artist.set_sizes([sz ** 2])
                except Exception:
                    pass
                # Marker shape for scatter.
                idx = self.marker_combo.currentIndex()
                mk = _MARKERS[idx][1]
                if mk != "None":
                    from matplotlib.markers import MarkerStyle
                    marker = MarkerStyle(mk)
                    path = marker.get_path().transformed(
                        marker.get_transform())
                    artist.set_paths([path])
                s["marker"] = mk
                if hasattr(artist, 'set_label'):
                    artist.set_label(self.label_edit.text())
            elif artist is not None:
                # Line2D artist.
                if hasattr(artist, 'set_linestyle'):
                    idx = self.line_style.currentIndex()
                    artist.set_linestyle(_LINE_STYLES[idx][1])
                if hasattr(artist, 'set_linewidth'):
                    artist.set_linewidth(self.line_width.value())
                if hasattr(artist, 'set_color'):
                    artist.set_color(self.line_color.color())
                if hasattr(artist, 'set_label'):
                    artist.set_label(self.label_edit.text())
                if hasattr(artist, 'set_marker'):
                    idx = self.marker_combo.currentIndex()
                    mk = _MARKERS[idx][1]
                    artist.set_marker(mk if mk != "None" else "")
                if hasattr(artist, 'set_markersize'):
                    artist.set_markersize(self.marker_size.value())
                if hasattr(artist, 'set_markerfacecolor'):
                    artist.set_markerfacecolor(self.marker_fill.color())
                if hasattr(artist, 'set_markeredgecolor'):
                    artist.set_markeredgecolor(self.marker_edge.color())

            # Fill
            fm = self.fill_mode.currentIndex()
            mode = ["none", "zero", "series"][fm]
            chart.apply_fill(
                row, mode, self.fill_target.currentIndex(),
                self.fill_color.color(), self.fill_alpha.value())

            # Bar options — save per-series bar props and chart config,
            # then redraw all bars with the updated layout.
            if hasattr(self, '_bar_tab') and s.get("plot_type") == "Bar":
                self._bar_tab.write_to_series(s)
                chart._bar_config = self._bar_tab.write_chart_config()
                chart._redraw_bars()

            # Pie options — save config and redraw.
            from .pie_options import PIE_TYPES
            if (hasattr(self, '_pie_tab')
                    and s.get("plot_type") in PIE_TYPES):
                cfg = self._pie_tab.write_to_config()
                # Preserve labels from original config.
                cfg["labels"] = chart._pie_config.get("labels")
                cfg["colors"] = chart._pie_config.get("colors")
                chart._pie_config.update(cfg)
                chart._redraw_pie()

            # Heatmap options — save config and redraw.
            if (hasattr(self, '_heatmap_tab')
                    and s.get("plot_type") == "Heatmap"):
                from .heatmap_options import redraw_heatmap
                chart._heatmap_config = \
                    self._heatmap_tab.write_to_config()
                redraw_heatmap(chart, chart._heatmap_config)

            # 3D Surface options — save config and redraw.
            if (hasattr(self, '_surface3d_tab')
                    and s.get("plot_type") == "3D Surface"):
                from .heatmap_options import redraw_surface
                chart._surface3d_config = \
                    self._surface3d_tab.write_to_config()
                redraw_surface(chart, chart._surface3d_config)

            # Refresh legend if one exists (skip for heatmap / 3-D surface).
            pt = s.get("plot_type", "")
            if pt not in ("Heatmap", "3D Surface"):
                if ax.get_legend() is not None:
                    chart._install_legend(ax)
            else:
                old_leg = ax.get_legend()
                if old_leg is not None:
                    old_leg.remove()

        # ── Header-row labelling ──────────────────────────────────
        chart._header_row = self.header_check.isChecked()
        if chart._header_row:
            chart._apply_header_labels()
            # Reflect the derived names in the dialog's list + label box.
            for i in range(self._series_list.count()):
                if i < len(chart._series):
                    self._series_list.item(i).setText(
                        chart._series[i]["label"])
            cur = self._series_list.currentRow()
            if 0 <= cur < len(chart._series):
                self.label_edit.setText(chart._series[cur]["label"])

        chart._canvas.draw_idle()

    def _apply_range_edit_for(self, chart, row, sheet,
                              x_range_str, y_range_str):
        """Re-read data for a single series from range strings."""
        x_parsed = self._parse_range(x_range_str)
        y_parsed = self._parse_range(y_range_str)

        if x_parsed is not None:
            x_col, xr1, xr2 = x_parsed
            # Store per-series x_col so refresh/update uses it.
            # Don't set chart._x_col — each series owns its own X.
            chart._series[row]["x_col"] = x_col
        else:
            x_col = chart._series[row].get("x_col", chart._x_col)
            xr1, xr2 = 0, sheet.row_count() - 1

        if y_parsed is not None:
            y_col, yr1, yr2 = y_parsed
            # Extend y_cols list if needed.
            while len(chart._y_cols) <= row:
                chart._y_cols.append(y_col)
            chart._y_cols[row] = y_col
        elif row < len(chart._y_cols):
            y_col = chart._y_cols[row]
            yr1, yr2 = 0, sheet.row_count() - 1
        else:
            return

        # Use the intersection of X and Y row ranges.
        r1 = max(xr1, yr1)
        r2 = min(xr2, yr2)
        if r1 > r2:
            return

        # Read data for the specific row range.
        x_all = sheet.numeric_column(x_col) if x_col is not None \
            else np.arange(sheet.row_count(), dtype=float)
        y_all = sheet.numeric_column(y_col)
        x_slice = x_all[r1:r2 + 1]
        y_slice = y_all[r1:r2 + 1]
        mask = ~(np.isnan(x_slice) | np.isnan(y_slice))
        x = x_slice[mask]
        y = y_slice[mask]

        s = chart._series[row]
        s["x"], s["y"] = x, y
        # Store row ranges for persistence and re-display.
        s["x_row_start"] = xr1
        s["x_row_end"] = xr2
        s["y_row_start"] = yr1
        s["y_row_end"] = yr2
        chart._update_artist(s, x, y)
        chart._ax.relim()
        chart._ax.autoscale_view()
        chart._canvas.draw()


# ── Legend Editor Dialog ──────────────────────────────────────────

class LegendEditorDialog(QDialog):
    """Dialog to edit legend entry names and all visual properties."""

    def __init__(self, chart, parent=None):
        # Parent to the top-level window to avoid Qt crash when
        # parenting a dialog to a viewport-child widget on Windows.
        win = chart.window() if chart else None
        super().__init__(parent or win)
        self.setWindowTitle("Edit Legend")
        self._chart = chart
        self.resize(440, 560)

        root = QVBoxLayout(self)

        # Read all current values from the stored props dict first
        # (safe Python dict), only probe matplotlib as a fallback.
        lp = getattr(chart, '_legend_props', {}) or {}
        leg = chart._ax.get_legend()
        leg_visible = False
        if leg is not None:
            try:
                leg_visible = bool(leg.get_visible())
            except Exception:
                pass

        # ── Series labels ──────────────────────────────────────────
        self._edits = []
        form = QFormLayout()
        for i, s in enumerate(chart._series):
            edit = QLineEdit(s.get("label", ""))
            self._edits.append(edit)
            form.addRow(f"Series {i + 1}:", edit)
        root.addLayout(form)

        # ── Show / hide ────────────────────────────────────────────
        self._show_chk = QCheckBox("Show Legend")
        self._show_chk.setChecked(leg_visible)
        root.addWidget(self._show_chk)

        # ── Legend title ───────────────────────────────────────────
        title_lay = QHBoxLayout()
        title_lay.addWidget(QLabel("Title:"))
        self._title_edit = QLineEdit()
        cur_title = lp.get("title", "")
        if not cur_title and leg_visible:
            try:
                t = leg.get_title()
                if t:
                    cur_title = t.get_text() or ""
            except Exception:
                pass
        self._title_edit.setText(cur_title)
        title_lay.addWidget(self._title_edit, stretch=1)
        root.addLayout(title_lay)

        # ── Read font from props or live legend ────────────────────
        cur_family = lp.get("font_family",
                            getattr(chart, '_legend_font', None))
        cur_size = lp.get("font_size",
                          getattr(chart, '_legend_size', 8))
        cur_bold = lp.get("bold", False)
        cur_italic = lp.get("italic", False)
        cur_label_color = lp.get("label_color", "#000000")

        # Fallback: read from live legend text objects.
        if cur_family is None and leg_visible:
            try:
                texts = leg.get_texts()
                if texts:
                    cur_family = texts[0].get_fontfamily()[0]
                    cur_size = int(texts[0].get_fontsize())
            except Exception:
                pass
        if cur_family is None:
            cur_family = "Segoe UI"  # safe Windows default

        # Map generic CSS/mpl font names to real system fonts.
        _font_map = {
            "sans-serif": "Segoe UI",
            "serif": "Times New Roman",
            "monospace": "Consolas",
            "cursive": "Comic Sans MS",
            "fantasy": "Impact",
            "DejaVu Sans": "Segoe UI",
        }
        cur_family = _font_map.get(cur_family, cur_family)

        # ── Font controls ──────────────────────────────────────────
        font_group = QGroupBox("Font")
        font_grid = QGridLayout(font_group)

        # Use a plain QComboBox instead of QFontComboBox — the latter
        # crashes (0xC0000409) during font enumeration on some Windows
        # systems with certain font configurations.
        from PyQt5.QtGui import QFontDatabase
        self._font_combo = QComboBox()
        self._font_combo.setEditable(True)
        families = QFontDatabase().families()
        self._font_combo.addItems(families)
        # Select the current family.
        idx = self._font_combo.findText(cur_family, Qt.MatchFixedString)
        if idx >= 0:
            self._font_combo.setCurrentIndex(idx)
        else:
            self._font_combo.setCurrentText(cur_family)
        font_grid.addWidget(QLabel("Family:"), 0, 0)
        font_grid.addWidget(self._font_combo, 0, 1, 1, 3)

        font_grid.addWidget(QLabel("Size:"), 1, 0)
        self._size_spin = QSpinBox()
        self._size_spin.setRange(4, 48)
        self._size_spin.setValue(int(cur_size))
        self._size_spin.setSuffix(" pt")
        font_grid.addWidget(self._size_spin, 1, 1)

        self._bold_chk = QCheckBox("Bold")
        self._bold_chk.setChecked(bool(cur_bold))
        font_grid.addWidget(self._bold_chk, 1, 2)

        self._italic_chk = QCheckBox("Italic")
        self._italic_chk.setChecked(bool(cur_italic))
        font_grid.addWidget(self._italic_chk, 1, 3)

        # Label colour.
        font_grid.addWidget(QLabel("Color:"), 2, 0)
        self._label_color = str(cur_label_color)
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(60, 24)
        self._color_btn.setStyleSheet(
            f"background-color: {self._label_color}; border: 1px solid #888;")
        self._color_btn.clicked.connect(self._pick_label_color)
        font_grid.addWidget(self._color_btn, 2, 1)

        root.addWidget(font_group)

        # ── Frame / box (read from props, not live legend) ─────────
        frame_group = QGroupBox("Frame")
        frame_grid = QGridLayout(frame_group)

        cur_frame_on = lp.get("frame_on", True)
        cur_frame_alpha = lp.get("frame_alpha", 0.8)
        cur_fancybox = lp.get("fancybox", True)
        cur_shadow = lp.get("shadow", False)
        cur_edge_color = lp.get("edge_color", "#cccccc")
        cur_face_color = lp.get("face_color", "#ffffff")

        self._frame_chk = QCheckBox("Show frame")
        self._frame_chk.setChecked(bool(cur_frame_on))
        frame_grid.addWidget(self._frame_chk, 0, 0, 1, 2)

        self._shadow_chk = QCheckBox("Shadow")
        self._shadow_chk.setChecked(bool(cur_shadow))
        frame_grid.addWidget(self._shadow_chk, 0, 2)

        self._fancybox_chk = QCheckBox("Rounded corners")
        self._fancybox_chk.setChecked(bool(cur_fancybox))
        frame_grid.addWidget(self._fancybox_chk, 0, 3)

        frame_grid.addWidget(QLabel("Opacity:"), 1, 0)
        self._alpha_spin = QDoubleSpinBox()
        self._alpha_spin.setRange(0.0, 1.0)
        self._alpha_spin.setSingleStep(0.05)
        self._alpha_spin.setDecimals(2)
        self._alpha_spin.setValue(float(cur_frame_alpha))
        frame_grid.addWidget(self._alpha_spin, 1, 1)

        frame_grid.addWidget(QLabel("Edge:"), 1, 2)
        self._edge_color = str(cur_edge_color)
        self._edge_btn = QPushButton()
        self._edge_btn.setFixedSize(60, 24)
        self._edge_btn.setStyleSheet(
            f"background-color: {self._edge_color}; border: 1px solid #888;")
        self._edge_btn.clicked.connect(self._pick_edge_color)
        frame_grid.addWidget(self._edge_btn, 1, 3)

        frame_grid.addWidget(QLabel("Fill:"), 2, 0)
        self._face_color = str(cur_face_color)
        self._face_btn = QPushButton()
        self._face_btn.setFixedSize(60, 24)
        self._face_btn.setStyleSheet(
            f"background-color: {self._face_color}; border: 1px solid #888;")
        self._face_btn.clicked.connect(self._pick_face_color)
        frame_grid.addWidget(self._face_btn, 2, 1)

        root.addWidget(frame_group)

        # ── Layout / spacing (from props dict) ─────────────────────
        spacing_group = QGroupBox("Layout")
        sp_grid = QGridLayout(spacing_group)

        cur_ncol = int(lp.get("ncol", 1))
        cur_markerscale = float(lp.get("markerscale", 1.0))
        cur_labelspacing = float(lp.get("labelspacing", 0.5))
        cur_columnspacing = float(lp.get("columnspacing", 2.0))
        cur_handlelength = float(lp.get("handlelength", 2.0))
        cur_handlepadding = float(lp.get("handletextpad", 0.8))
        cur_borderpad = float(lp.get("borderpad", 0.4))

        sp_grid.addWidget(QLabel("Columns:"), 0, 0)
        self._ncol_spin = QSpinBox()
        self._ncol_spin.setRange(1, 10)
        self._ncol_spin.setValue(cur_ncol)
        sp_grid.addWidget(self._ncol_spin, 0, 1)

        sp_grid.addWidget(QLabel("Marker scale:"), 0, 2)
        self._markerscale_spin = QDoubleSpinBox()
        self._markerscale_spin.setRange(0.1, 5.0)
        self._markerscale_spin.setSingleStep(0.1)
        self._markerscale_spin.setDecimals(1)
        self._markerscale_spin.setValue(cur_markerscale)
        sp_grid.addWidget(self._markerscale_spin, 0, 3)

        sp_grid.addWidget(QLabel("Label spacing:"), 1, 0)
        self._labelsp_spin = QDoubleSpinBox()
        self._labelsp_spin.setRange(0.0, 5.0)
        self._labelsp_spin.setSingleStep(0.1)
        self._labelsp_spin.setDecimals(1)
        self._labelsp_spin.setValue(cur_labelspacing)
        sp_grid.addWidget(self._labelsp_spin, 1, 1)

        sp_grid.addWidget(QLabel("Column spacing:"), 1, 2)
        self._colsp_spin = QDoubleSpinBox()
        self._colsp_spin.setRange(0.0, 5.0)
        self._colsp_spin.setSingleStep(0.1)
        self._colsp_spin.setDecimals(1)
        self._colsp_spin.setValue(cur_columnspacing)
        sp_grid.addWidget(self._colsp_spin, 1, 3)

        sp_grid.addWidget(QLabel("Handle length:"), 2, 0)
        self._handlelen_spin = QDoubleSpinBox()
        self._handlelen_spin.setRange(0.0, 10.0)
        self._handlelen_spin.setSingleStep(0.1)
        self._handlelen_spin.setDecimals(1)
        self._handlelen_spin.setValue(cur_handlelength)
        sp_grid.addWidget(self._handlelen_spin, 2, 1)

        sp_grid.addWidget(QLabel("Handle padding:"), 2, 2)
        self._handlepad_spin = QDoubleSpinBox()
        self._handlepad_spin.setRange(0.0, 5.0)
        self._handlepad_spin.setSingleStep(0.1)
        self._handlepad_spin.setDecimals(1)
        self._handlepad_spin.setValue(cur_handlepadding)
        sp_grid.addWidget(self._handlepad_spin, 2, 3)

        sp_grid.addWidget(QLabel("Border padding:"), 3, 0)
        self._borderpad_spin = QDoubleSpinBox()
        self._borderpad_spin.setRange(0.0, 5.0)
        self._borderpad_spin.setSingleStep(0.1)
        self._borderpad_spin.setDecimals(1)
        self._borderpad_spin.setValue(cur_borderpad)
        sp_grid.addWidget(self._borderpad_spin, 3, 1)

        root.addWidget(spacing_group)

        # ── OK / Apply / Cancel ────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply
            | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(
            self._on_apply)
        root.addWidget(buttons)

    # ── Live apply ─────────────────────────────────────────────────
    def _on_apply(self):
        """Apply legend properties without closing the dialog."""
        self.apply_to_chart(self._chart)

    # ── Color pickers ──────────────────────────────────────────────
    def _pick_label_color(self):
        c = _pick_color(self._label_color, self)
        if c is not None:
            self._label_color = c
            self._color_btn.setStyleSheet(
                f"background-color: {c}; border: 1px solid #888;")

    def _pick_edge_color(self):
        c = _pick_color(self._edge_color, self)
        if c is not None:
            self._edge_color = c
            self._edge_btn.setStyleSheet(
                f"background-color: {c}; border: 1px solid #888;")

    def _pick_face_color(self):
        c = _pick_color(self._face_color, self)
        if c is not None:
            self._face_color = c
            self._face_btn.setStyleSheet(
                f"background-color: {c}; border: 1px solid #888;")

    # ── Apply ──────────────────────────────────────────────────────
    def apply_to_chart(self, chart):
        """Apply all legend properties to the chart."""
        ax = chart._ax
        # Update series labels.
        for i, edit in enumerate(self._edits):
            if i >= len(chart._series):
                break
            new_label = edit.text()
            chart._series[i]["label"] = new_label
            artist = chart._series[i].get("artist")
            if artist is not None and hasattr(artist, 'set_label'):
                artist.set_label(new_label)

        if not self._show_chk.isChecked():
            leg = ax.get_legend()
            if leg:
                leg.remove()
            chart._canvas.draw_idle()
            return

        font_family = self._font_combo.currentText()
        font_size = self._size_spin.value()
        font_weight = "bold" if self._bold_chk.isChecked() else "normal"
        font_style = "italic" if self._italic_chk.isChecked() else "normal"

        prop = {"family": font_family, "size": font_size,
                "weight": font_weight, "style": font_style}

        leg = chart._install_legend(
            ax,
            loc="best",
            prop=prop,
            frameon=self._frame_chk.isChecked(),
            framealpha=self._alpha_spin.value(),
            shadow=self._shadow_chk.isChecked(),
            fancybox=self._fancybox_chk.isChecked(),
            ncol=self._ncol_spin.value(),
            markerscale=self._markerscale_spin.value(),
            labelspacing=self._labelsp_spin.value(),
            columnspacing=self._colsp_spin.value(),
            handlelength=self._handlelen_spin.value(),
            handletextpad=self._handlepad_spin.value(),
            borderpad=self._borderpad_spin.value(),
            title=self._title_edit.text() or None,
        )
        if leg:
            leg.set_draggable(True)
            # Apply label colour.
            for t in leg.get_texts():
                t.set_color(self._label_color)
            # Apply frame colours.
            fp = leg.get_frame()
            if fp:
                fp.set_edgecolor(self._edge_color)
                fp.set_facecolor(self._face_color)

        # Store everything for persistence.
        chart._legend_font = font_family
        chart._legend_size = font_size
        chart._legend_props = {
            "font_family": font_family,
            "font_size": font_size,
            "bold": self._bold_chk.isChecked(),
            "italic": self._italic_chk.isChecked(),
            "label_color": self._label_color,
            "frame_on": self._frame_chk.isChecked(),
            "frame_alpha": self._alpha_spin.value(),
            "shadow": self._shadow_chk.isChecked(),
            "fancybox": self._fancybox_chk.isChecked(),
            "edge_color": self._edge_color,
            "face_color": self._face_color,
            "ncol": self._ncol_spin.value(),
            "markerscale": self._markerscale_spin.value(),
            "labelspacing": self._labelsp_spin.value(),
            "columnspacing": self._colsp_spin.value(),
            "handlelength": self._handlelen_spin.value(),
            "handletextpad": self._handlepad_spin.value(),
            "borderpad": self._borderpad_spin.value(),
            "title": self._title_edit.text(),
        }
        chart._canvas.draw_idle()


def _mpl_color_to_hex(c):
    """Convert a matplotlib colour (RGBA tuple or string) to #rrggbb."""
    try:
        from matplotlib.colors import to_hex
        return to_hex(c, keep_alpha=False)
    except Exception:
        return "#000000"


class _SubplotMarginsDialog(QDialog):
    """Adjust subplot margins (left, right, top, bottom) with sliders."""

    def __init__(self, left, right, top, bottom, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Subplot Margins")
        self.resize(340, 200)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._spins = {}
        for name, val in (("left", left), ("right", right),
                          ("top", top), ("bottom", bottom)):
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1.0)
            spin.setSingleStep(0.01)
            spin.setDecimals(3)
            spin.setValue(val)
            form.addRow(name.capitalize() + ":", spin)
            self._spins[name] = spin
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return {k: s.value() for k, s in self._spins.items()}
