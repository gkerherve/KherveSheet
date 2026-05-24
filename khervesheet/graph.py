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
    QSplitter, QTabWidget, QListWidget, QDoubleSpinBox,
    QColorDialog,
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
                 parent=None, x_col=None, y_col=None):
        # Parent must be the table viewport so we paint over the grid.
        super().__init__(parent)
        self.setMouseTracking(True)
        self._source_sheet = source_sheet
        self._series = []
        self._fill_artists = []  # fill_between patches
        self._axis_props = {}    # persisted axis dialog state
        # Source column indices for live data updates.
        self._x_col = x_col      # None means row-index X
        self._y_cols = []         # populated by add_series

        # Dragging / resizing state.
        self._drag_origin = None      # mouse pos at drag start
        self._drag_widget_pos = None  # widget pos at drag start
        self._resizing = False
        self._resize_edge = None      # which edges: combination of t/b/l/r
        self._legend_dragging = False

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

        # Intercept mouse events on canvas for drag/resize while
        # letting matplotlib handle clicks inside the axes area.
        self._canvas.installEventFilter(self)

        # Double-click on labels/spines opens edit dialogs.
        self._canvas.mpl_connect("button_press_event", self._on_canvas_click)

        # Add the initial series.
        self.add_series(x, y, label, plot_type, y_col=y_col)

        try:
            self._figure.set_layout_engine("tight")
        except Exception:
            try:
                self._figure.tight_layout()
            except Exception:
                pass

        # Style the frame — no border by default; paintEvent draws
        # selection border only when chart is selected.
        self.setStyleSheet(
            "EmbeddedChart { background: white; }")
        self.setAutoFillBackground(True)

        self.show()
        self.raise_()

    # ── Series management ───────────────────────────────────────────
    def add_series(self, x, y, label, plot_type="Line", y_col=None):
        ax = self._ax
        artist = self._plot_one(ax, x, y, label, plot_type)

        self._series.append({
            "x": x, "y": y, "label": label,
            "plot_type": plot_type, "artist": artist,
        })
        if y_col is not None:
            self._y_cols.append(y_col)

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

    def change_series_type(self, series_idx, new_plot_type):
        """Remove the old artist and replot a series with a new type."""
        if series_idx < 0 or series_idx >= len(self._series):
            return
        s = self._series[series_idx]
        if s["plot_type"] == new_plot_type:
            return
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
        # Replot with new type.
        x, y = np.asarray(s["x"]), np.asarray(s["y"])
        new_artist = self._plot_one(
            self._ax, x, y, s["label"], new_plot_type)
        s["artist"] = new_artist
        s["plot_type"] = new_plot_type
        # Refresh legend.
        leg = self._ax.legend(loc="best", framealpha=0.8, fontsize=8)
        if leg:
            leg.set_draggable(True)
        self._canvas.draw_idle()

    # ── Serialisation ────────────────────────────────────────────────
    def to_dict(self):
        """Return a JSON-safe dict capturing chart state."""
        ax = self._ax
        series = []
        for s in self._series:
            sd = {
                "x": list(s["x"]),
                "y": list(s["y"]),
                "label": s["label"],
                "plot_type": s["plot_type"],
            }
            # Line / marker visual properties.
            artist = s.get("artist")
            if artist is not None:
                if hasattr(artist, 'get_linestyle'):
                    sd["linestyle"] = artist.get_linestyle()
                if hasattr(artist, 'get_linewidth'):
                    sd["linewidth"] = artist.get_linewidth()
                if hasattr(artist, 'get_color'):
                    c = artist.get_color()
                    if isinstance(c, str):
                        sd["color"] = c
                    elif hasattr(c, '__len__') and len(c) >= 3:
                        from matplotlib.colors import to_hex
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
                        from matplotlib.colors import to_hex
                        sd["markerfacecolor"] = to_hex(c)
                if hasattr(artist, 'get_markeredgecolor'):
                    c = artist.get_markeredgecolor()
                    if isinstance(c, str):
                        sd["markeredgecolor"] = c
                    elif hasattr(c, '__len__') and len(c) >= 3:
                        from matplotlib.colors import to_hex
                        sd["markeredgecolor"] = to_hex(c)
                # Visibility.
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
            # Row range info for data tab persistence.
            for rk in ("x_row_start", "x_row_end",
                        "y_row_start", "y_row_end"):
                if rk in s:
                    sd[rk] = int(s[rk])
            series.append(sd)
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
            "grid": (ax.xaxis.get_gridlines()[0].get_visible()
                     if ax.xaxis.get_gridlines() else False),
            "top_label": getattr(self, '_top_label_text', ''),
            "right_label": getattr(self, '_right_label_text', ''),
        }
        if self._axis_props:
            d["axis_props"] = self._axis_props
        if self._x_col is not None:
            d["x_col"] = self._x_col
        if self._y_cols:
            d["y_cols"] = self._y_cols
        return d

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
        # Restore source column mapping for live updates.
        chart._x_col = d.get("x_col")
        chart._y_cols = d.get("y_cols", [])
        if chart._source_sheet and chart._y_cols:
            chart._source_sheet.data_changed.connect(
                chart._on_data_changed)
        # Restore visual properties, fill, and visibility per series.
        for i, sd in enumerate(series):
            if i >= len(chart._series):
                break
            artist = chart._series[i].get("artist")
            if artist is not None:
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
                if sd.get("visible") is False:
                    if hasattr(artist, 'set_visible'):
                        artist.set_visible(False)
            # Restore row range info.
            for rk in ("x_row_start", "x_row_end",
                        "y_row_start", "y_row_end"):
                if rk in sd:
                    chart._series[i][rk] = int(sd[rk])
            fm = sd.get("fill_mode", "none")
            if fm != "none":
                chart.apply_fill(
                    i, fm, sd.get("fill_target", 0),
                    sd.get("fill_color", "#1f77b4"),
                    sd.get("fill_alpha", 0.3))
        chart._canvas.draw_idle()
        return chart

    # ── Close ───────────────────────────────────────────────────────
    def _close_chart(self):
        if self._source_sheet:
            try:
                self._source_sheet.data_changed.disconnect(
                    self._on_data_changed)
            except (TypeError, RuntimeError):
                pass
            if hasattr(self._source_sheet, '_charts'):
                try:
                    self._source_sheet._charts.remove(self)
                except ValueError:
                    pass
            if getattr(self._source_sheet, '_selected_chart', None) is self:
                self._source_sheet._selected_chart = None
        self.deleteLater()

    # ── Live data update ─────────────────────────────────────────────
    def _on_data_changed(self, col: int):
        """Re-read source data and refresh the chart when a plotted
        column changes on the sheet."""
        if not self._source_sheet:
            return
        # Check if this column is one we care about.
        relevant = (col == self._x_col) or (col in self._y_cols)
        if not relevant:
            return
        sheet = self._source_sheet
        # Re-read X data (full column, sliced per-series below).
        if self._x_col is not None:
            x_full = sheet.numeric_column(self._x_col)
        else:
            x_full = np.arange(sheet.row_count(), dtype=float)
        # Update each series respecting row ranges.
        for i, (s, yc) in enumerate(
                zip(self._series, self._y_cols)):
            y_full = sheet.numeric_column(yc)
            # Apply row range bounds if set.
            x_r0 = s.get("x_row_start", 0)
            x_r1 = s.get("x_row_end", len(x_full) - 1)
            y_r0 = s.get("y_row_start", 0)
            y_r1 = s.get("y_row_end", len(y_full) - 1)
            x_data = x_full[x_r0:x_r1 + 1]
            y_data = y_full[y_r0:y_r1 + 1]
            # Align lengths.
            n = min(len(x_data), len(y_data))
            x_data = x_data[:n]
            y_data = y_data[:n]
            mask = ~(np.isnan(x_data) | np.isnan(y_data))
            x = x_data[mask]
            y = y_data[mask]
            s["x"], s["y"] = x, y
            artist = s.get("artist")
            if artist is None:
                continue
            if hasattr(artist, 'set_data'):
                artist.set_data(x, y)
            elif hasattr(artist, 'set_offsets'):
                artist.set_offsets(np.column_stack([x, y]))
        self._ax.relim()
        self._ax.autoscale_view()
        self._canvas.draw_idle()

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
        """Handle double-click: label edit or axis properties."""
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

    # ── Axis properties dialog ─────────────────────────────────────
    SWITCH_TO_PLOT_DETAILS = 3

    def _open_axis_dialog(self, side):
        from .axis_dialog import AxisPropertiesDialog
        dlg = AxisPropertiesDialog(self, side)
        result = dlg.exec_()
        if result == QDialog.Accepted:
            dlg.apply_to_chart(self)
        elif result == self.SWITCH_TO_PLOT_DETAILS:
            self._open_plot_details()

    # ── Context menu ────────────────────────────────────────────────
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("Plot Details\u2026", self._open_plot_details)
        menu.addAction("Properties\u2026", self._open_properties)
        menu.addAction("Edit Legend\u2026", self._open_legend_editor)
        menu.addSeparator()

        # X Axis submenu
        xm = menu.addMenu("X Axis")
        xm.addAction("Linear", lambda: self._set_scale("x", "linear"))
        xm.addAction("Log\u2081\u2080",
                      lambda: self._set_scale("x", "log"))
        xm.addSeparator()
        x_inv = xm.addAction("Invert Axis")
        x_inv.setCheckable(True)
        x_inv.setChecked(self._ax.get_xlim()[0] > self._ax.get_xlim()[1])
        x_inv.toggled.connect(lambda c: self._invert_axis("x", c))
        xm.addSeparator()
        xm.addAction("Axis Properties\u2026",
                      lambda: self._open_axis_dialog("Bottom"))

        # Y Axis submenu
        ym = menu.addMenu("Y Axis")
        ym.addAction("Linear", lambda: self._set_scale("y", "linear"))
        ym.addAction("Log\u2081\u2080",
                      lambda: self._set_scale("y", "log"))
        ym.addSeparator()
        y_inv = ym.addAction("Invert Axis")
        y_inv.setCheckable(True)
        y_inv.setChecked(self._ax.get_ylim()[0] > self._ax.get_ylim()[1])
        y_inv.toggled.connect(lambda c: self._invert_axis("y", c))
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
        result = dlg.exec_()
        if result == QDialog.Accepted:
            dlg.apply_to_chart(self)
        elif result == PlotDetailsDialog.SWITCH_TO_AXIS:
            self._open_axis_dialog("Bottom")

    # ── Properties dialog ───────────────────────────────────────────
    def mouseDoubleClickEvent(self, event):
        self._open_axis_dialog("Bottom")

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
                         QEvent.MouseButtonRelease):
            return False

        # Map event pos to canvas-local and chart-widget coords.
        if obj is self._canvas:
            canvas_pos = event.pos()
        else:
            canvas_pos = self._canvas.mapFromGlobal(
                obj.mapToGlobal(event.pos()))
        wpos = self._canvas.mapToParent(canvas_pos)

        if etype == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                self._select()
                edge = self._hit_edge(wpos)
                if edge:
                    self._resizing = True
                    self._resize_edge = edge
                    self._drag_origin = event.globalPos()
                    self._drag_widget_pos = self.geometry()
                    return True   # consumed — resize only
                # Inside axes area → let matplotlib handle it
                # (legend drag, zoom, pan, data interaction).
                if self._in_axes_area(canvas_pos):
                    if self._hit_legend(canvas_pos):
                        self._legend_dragging = True
                    return False
                # Outside axes (margins) → start chart drag.
                self._drag_origin = event.globalPos()
                self._drag_widget_pos = self.pos()
            return False  # let matplotlib see the press

        if etype == QEvent.MouseMove:
            # While legend is being dragged, let matplotlib handle.
            if self._legend_dragging:
                return False
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
                self.unsetCursor()
                return False  # let matplotlib handle hover
            self.setCursor(Qt.SizeAllCursor)
            return False

        if etype == QEvent.MouseButtonRelease:
            if self._legend_dragging:
                self._legend_dragging = False
                return False  # let mpl finalize
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
        if selected:
            p = QPainter(self)
            p.setPen(QPen(QColor("#3078c6"), 2))
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

        self._build_graph_tab()
        self._build_data_tab()
        self._build_line_tab()
        self._build_symbol_tab()
        self._build_fill_tab()

        # Per-series range edits: {row: (x_range_str, y_range_str)}
        self._range_edits = {}
        self._series_list.currentRowChanged.connect(self._on_series)
        if self._series_list.count():
            self._series_list.setCurrentRow(0)

        # ── Footer ──────────────────────────────────────────────────
        footer = QHBoxLayout()
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

    def _build_data_tab(self):
        """Data range tab — shows and allows editing the plotted range."""
        w = QWidget()
        form = QFormLayout(w)

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

    # Custom result code for dialog switching.
    SWITCH_TO_AXIS = 2

    def _open_axis_props(self):
        """Close Plot Details and signal to open Axis Properties."""
        self.apply_to_chart(self._chart)
        self.done(self.SWITCH_TO_AXIS)

    def _add_series(self):
        """Add a new series from a column range entered by the user."""
        chart = self._chart
        sheet = chart._source_sheet
        if not sheet:
            return
        rng, ok = QInputDialog.getText(
            self, "Add Series", "Y data range (e.g. C1:C50):")
        if not ok or not rng.strip():
            return
        parsed = self._parse_range(rng)
        if parsed is None:
            return
        col, r1, r2 = parsed
        label = self._col_letter(col)
        y_all = sheet.numeric_column(col)
        # X data: use chart's existing X column or row index.
        if chart._x_col is not None:
            x_all = sheet.numeric_column(chart._x_col)
        else:
            x_all = np.arange(sheet.row_count(), dtype=float)
        x_slice = x_all[r1:r2 + 1]
        y_slice = y_all[r1:r2 + 1]
        mask = ~(np.isnan(x_slice) | np.isnan(y_slice))
        x, y = x_slice[mask], y_slice[mask]
        if len(x) == 0:
            return
        chart.add_series(x, y, label, "Line", y_col=col)
        # Update the series list in the dialog.
        from PyQt5.QtWidgets import QListWidgetItem
        item = QListWidgetItem(label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        self._series_list.addItem(item)
        # Update fill target combo.
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
        leg = chart._ax.legend(loc="best", framealpha=0.8, fontsize=8)
        if leg:
            leg.set_draggable(True)
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
        "Histogram",
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
            x_col = chart._x_col
            y_cols = chart._y_cols
            # Use stored row range if available, otherwise full range.
            x_r1 = s.get("x_row_start", 0)
            x_r2 = s.get("x_row_end", n_pts - 1) if n_pts else 0
            if x_col is not None:
                letter = self._col_letter(x_col)
                self.x_range_edit.setText(
                    f"{letter}{x_r1 + 1}:{letter}{x_r2 + 1}")
            else:
                self.x_range_edit.setText(f"1:{n_pts}  (row index)")
            if row < len(y_cols):
                y_r1 = s.get("y_row_start", 0)
                y_r2 = s.get("y_row_end", n_pts - 1) if n_pts else 0
                letter = self._col_letter(y_cols[row])
                self.y_range_edit.setText(
                    f"{letter}{y_r1 + 1}:{letter}{y_r2 + 1}")
            else:
                self.y_range_edit.setText("")

        n_pts = len(s.get("x", []))
        self.data_info.setText(str(n_pts))

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
        elif hasattr(artist, 'get_color'):
            c = artist.get_color()
            if isinstance(c, str):
                self.fill_color.set_color(c)
        fa = s.get("fill_alpha")
        if fa is not None:
            self.fill_alpha.setValue(fa)

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
                chart.change_series_type(row, new_pt)

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

            # Refresh legend (only include visible series).
            if self.legend_check.isChecked():
                leg = ax.legend(loc="best", framealpha=0.8, fontsize=8)
                if leg:
                    leg.set_draggable(True)

        chart._canvas.draw_idle()

    def _apply_range_edit_for(self, chart, row, sheet,
                              x_range_str, y_range_str):
        """Re-read data for a single series from range strings."""
        x_parsed = self._parse_range(x_range_str)
        y_parsed = self._parse_range(y_range_str)

        if x_parsed is not None:
            x_col, xr1, xr2 = x_parsed
            chart._x_col = x_col
        else:
            x_col = chart._x_col
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
        artist = s.get("artist")
        if artist is not None:
            if hasattr(artist, 'set_data'):
                artist.set_data(x, y)
            elif hasattr(artist, 'set_offsets'):
                artist.set_offsets(np.column_stack([x, y]))
        chart._ax.relim()
        chart._ax.autoscale_view()


# ── Legend Editor Dialog ──────────────────────────────────────────

class LegendEditorDialog(QDialog):
    """Dialog to edit legend entry names."""

    def __init__(self, chart, parent=None):
        super().__init__(parent or chart)
        self.setWindowTitle("Edit Legend")
        self._chart = chart
        self.resize(320, 200)

        layout = QVBoxLayout(self)

        # One QLineEdit per series.
        self._edits = []
        form = QFormLayout()
        for i, s in enumerate(chart._series):
            edit = QLineEdit(s.get("label", ""))
            self._edits.append(edit)
            form.addRow(f"Series {i + 1}:", edit)
        layout.addLayout(form)

        # Show/hide legend checkbox.
        leg = chart._ax.get_legend()
        self._show_legend = QCheckBox("Show Legend")
        self._show_legend.setChecked(leg is not None and leg.get_visible())
        layout.addWidget(self._show_legend)

        # OK / Cancel.
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply_to_chart(self, chart):
        """Apply edited labels to chart series and refresh legend."""
        ax = chart._ax
        for i, edit in enumerate(self._edits):
            if i >= len(chart._series):
                break
            new_label = edit.text()
            chart._series[i]["label"] = new_label
            artist = chart._series[i].get("artist")
            if artist is not None and hasattr(artist, 'set_label'):
                artist.set_label(new_label)

        if self._show_legend.isChecked():
            leg = ax.legend(loc="best", framealpha=0.8, fontsize=8)
            if leg:
                leg.set_draggable(True)
        else:
            leg = ax.get_legend()
            if leg:
                leg.remove()

        chart._canvas.draw_idle()
