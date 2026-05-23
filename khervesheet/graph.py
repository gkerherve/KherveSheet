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
from PyQt5.QtGui import QFont, QCursor, QPainter, QPen, QColor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QFormLayout, QDialogButtonBox,
    QWidget, QCheckBox, QMenu, QInputDialog,
)

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure


# ── Plot defaults ───────────────────────────────────────────────────
_DEFAULT_LINEWIDTH = 1.0
_DEFAULT_MARKERSIZE = 3.0

# Resize handle size in pixels.
_HANDLE = 6

# Module-level clipboard for chart cut/copy/paste.
_chart_clipboard = None


class EmbeddedChart(QWidget):
    """A matplotlib chart that lives as a child of the grid viewport."""

    def __init__(self, x, y, label, plot_type, source_sheet=None,
                 parent=None):
        # Parent must be the table viewport so we paint over the grid.
        super().__init__(parent)
        self.setMouseTracking(True)
        self._source_sheet = source_sheet
        self._series = []
        self._fill_artists = []  # fill_between patches

        # Dragging / resizing state.
        self._drag_origin = None      # mouse pos at drag start
        self._drag_widget_pos = None  # widget pos at drag start
        self._resizing = False
        self._resize_edge = None      # which edges: combination of t/b/l/r

        self.setMinimumSize(240, 180)
        self.resize(480, 320)

        # ── Layout ──────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        # Matplotlib figure — no title bar, just the plot.
        self._figure = Figure(figsize=(5, 3), dpi=100)
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setMouseTracking(True)
        self._ax = self._figure.add_subplot(111)
        layout.addWidget(self._canvas, stretch=1)

        # No toolbar — right-click menu provides all actions.

        # Interactive label/axis editing — hover highlight + double-click.
        self._hover_highlight_artist = None
        self._hover_spine = None          # (spine_obj, orig_color, orig_lw)
        self._canvas.mpl_connect("motion_notify_event", self._on_label_hover)
        self._canvas.mpl_connect("button_press_event", self._on_canvas_click)

        # Add the initial series.
        self.add_series(x, y, label, plot_type)

        try:
            self._figure.set_layout_engine("tight")
        except Exception:
            try:
                self._figure.tight_layout()
            except Exception:
                pass

        # Style the frame.
        self.setStyleSheet(
            "EmbeddedChart { "
            "  border: 1px solid #90a4b8; "
            "  background: white; "
            "}")
        self.setAutoFillBackground(True)

        self.show()
        self.raise_()

    # ── Series management ───────────────────────────────────────────
    def add_series(self, x, y, label, plot_type="Line"):
        ax = self._ax
        artist = self._plot_one(ax, x, y, label, plot_type)

        self._series.append({
            "x": x, "y": y, "label": label,
            "plot_type": plot_type, "artist": artist,
        })

        leg = ax.legend(loc="best", framealpha=0.8, fontsize=8)
        if leg:
            leg.set_draggable(True)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        self._canvas.draw_idle()

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
        else:
            lines = ax.plot(x, y, label=label)
            return lines[0] if lines else None

    # ── Serialisation ────────────────────────────────────────────────
    def to_dict(self):
        """Return a JSON-safe dict capturing chart state."""
        ax = self._ax
        series = []
        for s in self._series:
            series.append({
                "x": list(s["x"]),
                "y": list(s["y"]),
                "label": s["label"],
                "plot_type": s["plot_type"],
            })
        return {
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
            "grid": (ax.xaxis.get_gridlines()[0].get_visible()
                     if ax.xaxis.get_gridlines() else False),
            "top_label": getattr(self, '_top_label_text', ''),
            "right_label": getattr(self, '_right_label_text', ''),
        }

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
        chart.resize(d.get("width", 480), d.get("height", 320))
        ax = chart._ax
        ax.set_title(d.get("title", ""))
        ax.set_xlabel(d.get("xlabel", "X"))
        ax.set_ylabel(d.get("ylabel", "Y"))
        # Secondary labels (top / right).
        top_lbl = d.get("top_label", "")
        right_lbl = d.get("right_label", "")
        if top_lbl:
            chart._top_label_text = top_lbl
            from .axis_dialog import AxisPropertiesDialog
            AxisPropertiesDialog._set_secondary_label(
                chart, "top", top_lbl, {"fontsize": 10})
        if right_lbl:
            chart._right_label_text = right_lbl
            from .axis_dialog import AxisPropertiesDialog
            AxisPropertiesDialog._set_secondary_label(
                chart, "right", right_lbl, {"fontsize": 10})
        try:
            ax.set_xscale(d.get("xscale", "linear"))
            ax.set_yscale(d.get("yscale", "linear"))
        except ValueError:
            pass
        ax.grid(d.get("grid", False))
        chart._canvas.draw_idle()
        return chart

    # ── Close ───────────────────────────────────────────────────────
    def _close_chart(self):
        if self._source_sheet:
            if hasattr(self._source_sheet, '_charts'):
                try:
                    self._source_sheet._charts.remove(self)
                except ValueError:
                    pass
            if getattr(self._source_sheet, '_selected_chart', None) is self:
                self._source_sheet._selected_chart = None
        self.deleteLater()

    # ── Interactive label / axis editing ───────────────────────────
    _SPINE_MAP = {"Bottom": "bottom", "Top": "top",
                  "Left": "left", "Right": "right"}

    def _on_label_hover(self, event):
        """Highlight xlabel, ylabel, or title on hover; highlight axis
        spine when cursor is near an edge."""
        ax = self._ax
        hit_artist = None
        for artist in (ax.xaxis.label, ax.yaxis.label, ax.title):
            try:
                inside, _ = artist.contains(event)
            except Exception:
                inside = False
            if inside and artist.get_text():
                hit_artist = artist
                break

        prev = self._hover_highlight_artist
        changed = False
        if hit_artist is not prev:
            if prev is not None:
                prev.set_bbox(None)
                self._hover_highlight_artist = None
                changed = True
            if hit_artist is not None:
                hit_artist.set_bbox(dict(
                    boxstyle="round,pad=0.15", facecolor="#d0e8ff",
                    edgecolor="#4a90d9", alpha=0.6, linewidth=1.0))
                self._hover_highlight_artist = hit_artist
                changed = True

        # Spine highlight.
        side = self._hit_axis_spine(event)
        new_spine = None
        if side is not None and hit_artist is None:
            key = self._SPINE_MAP.get(side)
            if key:
                new_spine = ax.spines[key]
        prev_sp = self._hover_spine
        prev_spine_obj = prev_sp[0] if prev_sp else None
        if new_spine is not prev_spine_obj:
            if prev_sp is not None:
                sp, orig_c, orig_lw = prev_sp
                try:
                    sp.set_edgecolor(orig_c)
                    sp.set_linewidth(orig_lw)
                except Exception:
                    pass
                self._hover_spine = None
                changed = True
            if new_spine is not None:
                try:
                    orig_c = new_spine.get_edgecolor()
                    orig_lw = new_spine.get_linewidth()
                    self._hover_spine = (new_spine, orig_c, orig_lw)
                    new_spine.set_edgecolor("#4a90d9")
                    new_spine.set_linewidth(2.5)
                except Exception:
                    self._hover_spine = None
                changed = True

        if changed:
            self._canvas.draw_idle()

    def _on_canvas_click(self, event):
        """Handle double-click on labels or axis spines."""
        if event.dblclick:
            if self._try_edit_axis_label(event):
                return
            side = self._hit_axis_spine(event)
            if side is not None:
                self._open_axis_dialog(side)

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

    # ── Axis properties dialog ─────────────────────────────────────
    def _open_axis_dialog(self, side):
        from .axis_dialog import AxisPropertiesDialog
        dlg = AxisPropertiesDialog(self, side)
        if dlg.exec_() == QDialog.Accepted:
            dlg.apply_to_chart(self)

    # ── Context menu ────────────────────────────────────────────────
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("Plot Details\u2026", self._open_plot_details)
        menu.addAction("Properties\u2026", self._open_properties)
        menu.addSeparator()

        # X Axis submenu
        xm = menu.addMenu("X Axis")
        xm.addAction("Linear", lambda: self._set_scale("x", "linear"))
        xm.addAction("Log\u2081\u2080",
                      lambda: self._set_scale("x", "log"))
        xm.addSeparator()
        xm.addAction("Axis Properties\u2026",
                      lambda: self._open_axis_dialog("Bottom"))

        # Y Axis submenu
        ym = menu.addMenu("Y Axis")
        ym.addAction("Linear", lambda: self._set_scale("y", "linear"))
        ym.addAction("Log\u2081\u2080",
                      lambda: self._set_scale("y", "log"))
        ym.addSeparator()
        ym.addAction("Axis Properties\u2026",
                      lambda: self._open_axis_dialog("Left"))

        menu.addSeparator()
        menu.addAction("Pop Out to Window", self._pop_out)
        menu.addSeparator()
        menu.addAction("Close Chart", self._close_chart)
        menu.exec_(event.globalPos())

    def _pop_out(self):
        """Detach from grid and show as an independent window."""
        dlg = _ChartWindow(self._figure, self._series, self.window())
        self._close_chart()
        dlg.show()

    # ── Plot Details dialog ─────────────────────────────────────────
    def _open_plot_details(self):
        dlg = PlotDetailsDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            dlg.apply_to_chart(self)

    # ── Properties dialog ───────────────────────────────────────────
    def mouseDoubleClickEvent(self, event):
        self._open_plot_details()

    def _open_properties(self):
        dlg = ChartPropertiesDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self._apply_properties(dlg)

    def _apply_properties(self, dlg):
        ax = self._ax
        ax.set_title(dlg.title_edit.text())
        ax.set_xlabel(dlg.xlabel_edit.text())
        ax.set_ylabel(dlg.ylabel_edit.text())
        ax.grid(dlg.grid_check.isChecked())
        self._canvas.draw_idle()

    # ── Fill between curves ─────────────────────────────────────────
    def apply_fill(self, series_idx, fill_mode, fill_target_idx,
                   fill_color, fill_alpha):
        """Add or update fill for a series.

        fill_mode: 'none', 'zero', 'series'
        fill_target_idx: index into self._series (for 'series' mode)
        """
        # Remove existing fill for this series.
        self._remove_fill(series_idx)

        if fill_mode == "none":
            return

        s = self._series[series_idx]
        x, y = s["x"], s["y"]

        if fill_mode == "zero":
            fc = self._ax.fill_between(
                x, y, 0, alpha=fill_alpha, color=fill_color,
                label="_nolegend_")
        elif fill_mode == "series" and 0 <= fill_target_idx < len(self._series):
            t = self._series[fill_target_idx]
            # Interpolate target to match x
            y2 = np.interp(x, t["x"], t["y"])
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

    # ── Drag to move ────────────────────────────────────────────────
    def _in_axes_area(self, pos):
        """True if *pos* (widget coords) falls inside the matplotlib
        axes rectangle — the actual plot area, not the margins."""
        try:
            bbox = self._ax.get_window_extent()
            # Canvas coords: origin bottom-left; widget coords: top-left.
            canvas_geom = self._canvas.geometry()
            # Map widget pos to canvas-local coords.
            cx = pos.x() - canvas_geom.x()
            cy = pos.y() - canvas_geom.y()
            # Flip y for matplotlib convention.
            cy_mpl = canvas_geom.height() - cy
            return (bbox.x0 <= cx <= bbox.x1 and
                    bbox.y0 <= cy_mpl <= bbox.y1)
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
            # Drag from anywhere outside the axes area (margins/border).
            if not self._in_axes_area(event.pos()):
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

        # Update cursor: resize edges → resize cursors,
        # outside axes → move cursor, inside axes → default.
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
        elif not self._in_axes_area(event.pos()):
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.unsetCursor()
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

    def _set_selected(self, selected):
        """Visual feedback for selection — thicker blue border."""
        self.update()  # trigger paintEvent to redraw border

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

    # ── Paint border ────────────────────────────────────────────────
    def paintEvent(self, event):
        super().paintEvent(event)
        selected = (self._source_sheet and
                    getattr(self._source_sheet, '_selected_chart',
                            None) is self)
        p = QPainter(self)
        if selected:
            p.setPen(QPen(QColor("#3078c6"), 2))
        else:
            p.setPen(QPen(QColor("#90a4b8"), 1))
        p.drawRect(0, 0, self.width() - 1, self.height() - 1)
        p.end()


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


class ChartPropertiesDialog(QDialog):
    """Simple chart properties editor."""

    def __init__(self, chart, parent=None):
        super().__init__(parent or chart)
        self.setWindowTitle("Chart Properties")
        self.resize(350, 200)

        form = QFormLayout(self)

        ax = chart._ax
        self.title_edit = QLineEdit(ax.get_title())
        self.xlabel_edit = QLineEdit(ax.get_xlabel())
        self.ylabel_edit = QLineEdit(ax.get_ylabel())
        self.grid_check = QCheckBox("Show Grid")
        self.grid_check.setChecked(ax.xaxis.get_gridlines()[0].get_visible()
                                    if ax.xaxis.get_gridlines() else False)

        form.addRow("Title:", self.title_edit)
        form.addRow("X Label:", self.xlabel_edit)
        form.addRow("Y Label:", self.ylabel_edit)
        form.addRow(self.grid_check)

        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)


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
        c = QColorDialog.getColor(QColor(self._color), self)
        if c.isValid():
            self._color = c.name()
            self._update_style()


class PlotDetailsDialog(QDialog):
    """Simplified Plot Details — series list + property tabs."""

    def __init__(self, chart, parent=None):
        super().__init__(parent or chart)
        self.setWindowTitle("Plot Details")
        self.resize(640, 480)
        self._chart = chart

        outer = QVBoxLayout(self)

        sp = QSplitter(Qt.Horizontal)
        outer.addWidget(sp, stretch=1)

        # ── Series list ─────────────────────────────────────────────
        self._series_list = QListWidget()
        self._series_list.setMinimumWidth(140)
        for s in chart._series:
            self._series_list.addItem(s["label"])
        sp.addWidget(self._series_list)

        # ── Tabs ────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        sp.addWidget(self._tabs)
        sp.setSizes([160, 480])

        self._build_graph_tab()
        self._build_line_tab()
        self._build_symbol_tab()
        self._build_fill_tab()

        self._series_list.currentRowChanged.connect(self._on_series)
        if self._series_list.count():
            self._series_list.setCurrentRow(0)

        # ── Footer ──────────────────────────────────────────────────
        footer = QHBoxLayout()
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

    def _build_graph_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        ax = self._chart._ax
        self.title_edit = QLineEdit(ax.get_title())
        self.xlabel_edit = QLineEdit(ax.get_xlabel())
        self.ylabel_edit = QLineEdit(ax.get_ylabel())
        self.grid_check = QCheckBox("Show Grid")
        self.grid_check.setChecked(
            ax.xaxis.get_gridlines()[0].get_visible()
            if ax.xaxis.get_gridlines() else False)
        self.legend_check = QCheckBox("Show Legend")
        self.legend_check.setChecked(ax.get_legend() is not None)
        self.xscale_combo = QComboBox()
        self.xscale_combo.addItems(["linear", "log"])
        self.xscale_combo.setCurrentText(ax.get_xscale())
        self.yscale_combo = QComboBox()
        self.yscale_combo.addItems(["linear", "log"])
        self.yscale_combo.setCurrentText(ax.get_yscale())

        form.addRow("Title:", self.title_edit)
        form.addRow("X Label:", self.xlabel_edit)
        form.addRow("Y Label:", self.ylabel_edit)
        form.addRow(self.grid_check)
        form.addRow(self.legend_check)
        form.addRow("X Scale:", self.xscale_combo)
        form.addRow("Y Scale:", self.yscale_combo)
        self._tabs.addTab(w, "Graph")

    def _build_line_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        self.line_style = QComboBox()
        for name, _ in _LINE_STYLES:
            self.line_style.addItem(name)
        self.line_width = QDoubleSpinBox()
        self.line_width.setRange(0.0, 20.0)
        self.line_width.setSingleStep(0.5)
        self.line_width.setValue(_DEFAULT_LINEWIDTH)
        self.line_color = _ColorButton()
        self.label_edit = QLineEdit()

        form.addRow("Label:", self.label_edit)
        form.addRow("Style:", self.line_style)
        form.addRow("Width:", self.line_width)
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

    def _on_series(self, row):
        """Populate widgets from the selected series."""
        if row < 0 or row >= len(self._chart._series):
            return
        s = self._chart._series[row]
        artist = s.get("artist")
        self.label_edit.setText(s["label"])

        # Try to read line properties from the artist.
        if hasattr(artist, 'get_linestyle'):
            ls = artist.get_linestyle()
            for i, (_, code) in enumerate(_LINE_STYLES):
                if code == ls:
                    self.line_style.setCurrentIndex(i)
                    break
        if hasattr(artist, 'get_linewidth'):
            self.line_width.setValue(artist.get_linewidth())
        if hasattr(artist, 'get_color'):
            c = artist.get_color()
            if isinstance(c, str):
                self.line_color.set_color(c)
            elif hasattr(c, '__len__') and len(c) >= 3:
                from matplotlib.colors import to_hex
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
                from matplotlib.colors import to_hex
                self.marker_fill.set_color(to_hex(c))

        # Fill — check if this series already has a fill.
        fill_found = False
        for idx, _ in self._chart._fill_artists:
            if idx == row:
                fill_found = True
                break
        if not fill_found:
            self.fill_mode.setCurrentIndex(0)

        # Set fill color from line color.
        if hasattr(artist, 'get_color'):
            c = artist.get_color()
            if isinstance(c, str):
                self.fill_color.set_color(c)

    def apply_to_chart(self, chart):
        """Apply all settings to the chart."""
        ax = chart._ax

        # Graph settings
        ax.set_title(self.title_edit.text())
        ax.set_xlabel(self.xlabel_edit.text())
        ax.set_ylabel(self.ylabel_edit.text())
        ax.grid(self.grid_check.isChecked())
        ax.set_xscale(self.xscale_combo.currentText())
        ax.set_yscale(self.yscale_combo.currentText())
        if self.legend_check.isChecked():
            leg = ax.legend(loc="best", framealpha=0.8, fontsize=8)
            if leg:
                leg.set_draggable(True)
        else:
            leg = ax.get_legend()
            if leg:
                leg.remove()

        # Series settings for currently selected series
        row = self._series_list.currentRow()
        if 0 <= row < len(chart._series):
            s = chart._series[row]
            artist = s.get("artist")
            s["label"] = self.label_edit.text()

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

            # Refresh legend
            if self.legend_check.isChecked():
                leg = ax.legend(loc="best", framealpha=0.8, fontsize=8)
                if leg:
                    leg.set_draggable(True)

        chart._canvas.draw_idle()
