"""Publication layout tab — aggregate every chart in the workbook.

``CombinedLayoutTab`` is always pinned to the right of the sheet tabs.
It lays every (visible) chart out as a subplot of a single matplotlib
figure, giving real ``wspace``/``hspace`` control and one chosen figure
size, so the whole layout exports as one clean vector file — the natural
choice for a publication panel figure.

It reproduces the source charts exactly by replaying the same serialized
dict (``EmbeddedChart.to_dict``) through :func:`render_chart`, which reuses
the very static helpers the live charts use, so properties round-trip
identically.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import numpy as np

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.collections import PathCollection

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QListWidget, QListWidgetItem, QPushButton, QSpinBox, QDoubleSpinBox,
    QComboBox, QScrollArea, QFileDialog, QSplitter,
)


# Publication figure-size presets: (label, width_mm, height_mm).
# "Custom…" must stay last — it is the sentinel with zero size.
_SIZE_PRESETS = [
    ("Nature single (89×66 mm)", 89, 66),
    ("Nature double (183×137 mm)", 183, 137),
    ("ACS single (83×63 mm)", 83, 63),
    ("ACS double (178×102 mm)", 178, 102),
    ("PNAS double (178×120 mm)", 178, 120),
    ("2-column wide (190×120 mm)", 190, 120),
    ("A4 landscape (250×170 mm)", 250, 170),
    ("A4 portrait (170×250 mm)", 170, 250),
    ("Full page (190×230 mm)", 190, 230),
    ("Letter landscape (240×180 mm)", 240, 180),
    ("Square (120×120 mm)", 120, 120),
    ("Large square (180×180 mm)", 180, 180),
    ("Custom…", 0, 0),
]

# How subplots are filled into the grid.
_FILL_ORDERS = [("By row", "row"), ("By column", "col")]

# Per-tile style override. Applied on top of a chart's own appearance
# only when an entry exists for that tile in ``_tile_styles``.
_DEFAULT_TILE_STYLE = {
    "face": "#ffffff", "alpha": 1.0,
    "border_on": True, "edge": "#000000", "edge_w": 1.0,
}

_MM_PER_IN = 25.4


def _is_3d(d):
    return any(s.get("plot_type") == "3D Surface"
              for s in d.get("series", []))


def collect_charts(workbook):
    """Return ``[(title, dict), ...]`` for every chart across all sheets.

    Titles fall back to ``"<sheet> · plot N"`` when a chart has no
    title set, so list entries stay distinguishable.
    """
    from .sheet import SheetWidget
    out = []
    for i in range(workbook.tabs.count()):
        w = workbook.tabs.widget(i)
        if not isinstance(w, SheetWidget):
            continue
        sheet_name = workbook.tabs.tabText(i)
        for ci, chart in enumerate(getattr(w, "_charts", [])):
            try:
                d = chart.to_dict()
            except Exception:
                continue
            title = d.get("title") or f"{sheet_name} · plot {ci + 1}"
            out.append((title, d))
    return out


class _ShimChart:
    """Duck-typed stand-in for ``EmbeddedChart``.

    The static render helpers in ``graph``/``axis_dialog``/``trendline``/
    ``general_properties`` only ever touch a handful of attributes
    (``_ax``, ``_figure``, ``_canvas``, ``_series`` …).  Pointing those at
    an arbitrary figure+axes lets us replay a chart without building a
    live, draggable widget."""

    def __init__(self, fig, ax, canvas):
        self._figure = fig
        self._ax = ax
        self._canvas = canvas
        self._series = []
        self._fill_artists = []
        self._trendlines = []
        self._axis_props = {}
        self._general_props = None
        self._sketch_on = False
        self._source_sheet = None
        self._x_col = None
        self._y_cols = []

    def _remove_fill(self, series_idx):
        keep = []
        for idx, artist in self._fill_artists:
            if idx == series_idx:
                try:
                    artist.remove()
                except Exception:
                    pass
            else:
                keep.append((idx, artist))
        self._fill_artists = keep


def _apply_series_visuals(shim, series):
    """Restore per-series line/marker colours, sizes, visibility and
    fills — mirrors ``EmbeddedChart.from_dict``'s artist-styling block."""
    from .graph import EmbeddedChart
    for i, sd in enumerate(series):
        if i >= len(shim._series):
            break
        artist = shim._series[i].get("artist")
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
                    shim._series[i]["marker"] = mk
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
                if "markersize" in sd and hasattr(artist, 'set_markersize'):
                    artist.set_markersize(sd["markersize"])
                if "markerfacecolor" in sd and hasattr(
                        artist, 'set_markerfacecolor'):
                    artist.set_markerfacecolor(sd["markerfacecolor"])
                if "markeredgecolor" in sd and hasattr(
                        artist, 'set_markeredgecolor'):
                    artist.set_markeredgecolor(sd["markeredgecolor"])
            if sd.get("visible") is False and hasattr(artist, 'set_visible'):
                artist.set_visible(False)
        fm = sd.get("fill_mode", "none")
        if fm != "none":
            try:
                EmbeddedChart.apply_fill(
                    shim, i, fm, sd.get("fill_target", 0),
                    sd.get("fill_color", "#1f77b4"),
                    sd.get("fill_alpha", 0.3))
            except Exception:
                pass


def _apply_legend(ax, d, shim):
    """Restore the legend exactly as ``from_dict`` does."""
    leg_font = d.get("legend_font")
    leg_size = d.get("legend_size", 8)
    leg_visible = d.get("legend_visible", True)
    lp = d.get("legend_props", {})
    if not leg_visible:
        leg = ax.get_legend()
        if leg:
            leg.remove()
        return
    prop = {"family": leg_font or "sans-serif", "size": leg_size}
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
    leg = ax.legend(**kw)
    if leg:
        lc = lp.get("label_color", "#000000")
        for t in leg.get_texts():
            t.set_color(lc)
        fp = leg.get_frame()
        if fp:
            fp.set_edgecolor(lp.get("edge_color", "#cccccc"))
            fp.set_facecolor(lp.get("face_color", "#ffffff"))
    if lp:
        shim._legend_props = dict(lp)


def render_chart(fig, ax, d):
    """Replay a serialized chart dict onto ``fig``/``ax`` so the result is
    visually identical to the source ``EmbeddedChart``."""
    from .graph import EmbeddedChart
    from .axis_dialog import AxisPropertiesDialog

    shim = _ShimChart(fig, ax, fig.canvas)
    series = d.get("series", [])

    for s in series:
        x = np.array(s["x"])
        y = np.array(s["y"])
        artist = EmbeddedChart._plot_one(
            ax, x, y, s["label"], s["plot_type"])
        shim._series.append({
            "x": x, "y": y, "label": s["label"],
            "plot_type": s["plot_type"], "artist": artist,
        })

    ax.set_title(d.get("title", ""))
    ax.set_xlabel(d.get("xlabel", "X"))
    ax.set_ylabel(d.get("ylabel", "Y"))

    top_lbl = d.get("top_label", "")
    right_lbl = d.get("right_label", "")
    if top_lbl:
        shim._top_label_text = top_lbl
        AxisPropertiesDialog._set_secondary_label(
            shim, "top", top_lbl, {"fontsize": 10})
    if right_lbl:
        shim._right_label_text = right_lbl
        AxisPropertiesDialog._set_secondary_label(
            shim, "right", right_lbl, {"fontsize": 10})

    axis_props = d.get("axis_props")
    if axis_props:
        shim._axis_props = axis_props
        for direction, st in axis_props.items():
            try:
                AxisPropertiesDialog._apply_dir_static(shim, direction, st)
            except Exception:
                pass
    else:
        try:
            ax.set_xscale(d.get("xscale", "linear"))
            ax.set_yscale(d.get("yscale", "linear"))
        except ValueError:
            pass
        ax.grid(d.get("grid", False))

    _apply_series_visuals(shim, series)
    _apply_legend(ax, d, shim)

    tl_list = d.get("trendlines", [])
    if tl_list:
        from .trendline import TrendlineInfo, restore_trendline
        for td in tl_list:
            try:
                info = TrendlineInfo.from_dict(td)
                restore_trendline(shim, info)
                shim._trendlines.append(info)
            except Exception:
                pass

    gp = d.get("general_props")
    if gp:
        from .general_properties import apply_general_state
        try:
            apply_general_state(shim, gp)
        except Exception:
            pass

    return shim


class _BaseLayoutTab(QWidget):
    """Shared scaffolding for the two layout tabs: a left control panel
    (plot list + reorder + grid/spacing/size controls) and a right
    content area that each subclass fills in."""

    _size_group_label = "Figure size"

    def __init__(self, workbook):
        super().__init__()
        self._workbook = workbook
        self._items = []          # [{title, dict, visible}]
        self._tile_styles = {}    # title -> per-tile style override dict
        self._suspend = False     # block re-render while repopulating

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._build_controls())
        content = self._build_content()
        splitter.addWidget(content)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 720])

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(splitter)

    # ── Controls ────────────────────────────────────────────────────
    def _build_controls(self):
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(8, 8, 8, 8)

        list_box = QGroupBox("Plots")
        lv = QVBoxLayout(list_box)
        self._list = QListWidget()
        self._list.itemChanged.connect(self._on_item_changed)
        lv.addWidget(self._list)
        row = QHBoxLayout()
        up = QPushButton("↑")
        up.setToolTip("Move selected plot up")
        up.clicked.connect(lambda: self._move_selected(-1))
        down = QPushButton("↓")
        down.setToolTip("Move selected plot down")
        down.clicked.connect(lambda: self._move_selected(1))
        refresh = QPushButton("Refresh")
        refresh.setToolTip("Re-collect plots from all sheets")
        refresh.clicked.connect(self.rebuild_from_workbook)
        row.addWidget(up)
        row.addWidget(down)
        row.addStretch()
        row.addWidget(refresh)
        lv.addLayout(row)
        v.addWidget(list_box, stretch=1)

        grid_box = QGroupBox("Arrangement")
        gform = QFormLayout(grid_box)
        self._cols = QSpinBox()
        self._cols.setRange(1, 8)
        self._cols.setValue(2)
        self._cols.valueChanged.connect(self._render)
        gform.addRow("Columns per row:", self._cols)
        self._fill_order = QComboBox()
        for label, _val in _FILL_ORDERS:
            self._fill_order.addItem(label)
        self._fill_order.currentIndexChanged.connect(self._render)
        gform.addRow("Fill order:", self._fill_order)
        self._wspace = QDoubleSpinBox()
        self._wspace.setRange(0.0, 2.0)
        self._wspace.setSingleStep(0.05)
        self._wspace.setValue(0.3)
        self._wspace.valueChanged.connect(self._render)
        gform.addRow("Horizontal gap:", self._wspace)
        self._hspace = QDoubleSpinBox()
        self._hspace.setRange(0.0, 2.0)
        self._hspace.setSingleStep(0.05)
        self._hspace.setValue(0.3)
        self._hspace.valueChanged.connect(self._render)
        gform.addRow("Vertical gap:", self._hspace)
        v.addWidget(grid_box)

        margin_box = QGroupBox("Outer margins")
        mform = QFormLayout(margin_box)
        self._m_left = self._margin_spin(0.10)
        mform.addRow("Left:", self._m_left)
        self._m_right = self._margin_spin(0.97)
        mform.addRow("Right:", self._m_right)
        self._m_top = self._margin_spin(0.94)
        mform.addRow("Top:", self._m_top)
        self._m_bottom = self._margin_spin(0.10)
        mform.addRow("Bottom:", self._m_bottom)
        v.addWidget(margin_box)

        size_box = QGroupBox(self._size_group_label)
        sform = QFormLayout(size_box)
        self._size_preset = QComboBox()
        for label, _w, _h in _SIZE_PRESETS:
            self._size_preset.addItem(label)
        self._size_preset.currentIndexChanged.connect(self._on_preset)
        sform.addRow("Preset:", self._size_preset)
        self._width_mm = QDoubleSpinBox()
        self._width_mm.setRange(20, 600)
        self._width_mm.setValue(183)
        self._width_mm.setSuffix(" mm")
        self._width_mm.valueChanged.connect(self._render)
        sform.addRow("Width:", self._width_mm)
        self._height_mm = QDoubleSpinBox()
        self._height_mm.setRange(20, 600)
        self._height_mm.setValue(137)
        self._height_mm.setSuffix(" mm")
        self._height_mm.valueChanged.connect(self._render)
        sform.addRow("Height:", self._height_mm)
        self._dpi = QSpinBox()
        self._dpi.setRange(72, 1200)
        self._dpi.setValue(300)
        self._dpi.valueChanged.connect(self._render)
        sform.addRow("DPI:", self._dpi)
        v.addWidget(size_box)

        v.addWidget(self._build_tile_box())

        export = QPushButton("Export…")
        export.clicked.connect(self._export)
        v.addWidget(export)

        return panel

    def _build_tile_box(self):
        """Per-tile background / transparency / border controls that act
        on the plot currently selected in the list."""
        from .graph import _ColorButton
        from PyQt5.QtWidgets import QCheckBox

        box = QGroupBox("Selected tile")
        form = QFormLayout(box)
        self._tile_face = _ColorButton(_DEFAULT_TILE_STYLE["face"])
        self._tile_face.clicked.connect(self._on_tile_style_changed)
        form.addRow("Background:", self._tile_face)
        self._tile_alpha = QDoubleSpinBox()
        self._tile_alpha.setRange(0.0, 1.0)
        self._tile_alpha.setSingleStep(0.05)
        self._tile_alpha.setDecimals(2)
        self._tile_alpha.setValue(1.0)
        self._tile_alpha.valueChanged.connect(self._on_tile_style_changed)
        form.addRow("Opacity:", self._tile_alpha)
        self._tile_border = QCheckBox("Show border")
        self._tile_border.setChecked(True)
        self._tile_border.toggled.connect(self._on_tile_style_changed)
        form.addRow(self._tile_border)
        self._tile_edge = _ColorButton(_DEFAULT_TILE_STYLE["edge"])
        self._tile_edge.clicked.connect(self._on_tile_style_changed)
        form.addRow("Border color:", self._tile_edge)
        self._tile_edge_w = QDoubleSpinBox()
        self._tile_edge_w.setRange(0.0, 6.0)
        self._tile_edge_w.setSingleStep(0.5)
        self._tile_edge_w.setValue(1.0)
        self._tile_edge_w.valueChanged.connect(self._on_tile_style_changed)
        form.addRow("Border width:", self._tile_edge_w)
        clear = QPushButton("Reset tile")
        clear.clicked.connect(self._clear_tile_style)
        form.addRow(clear)
        self._tile_box = box
        self._list.currentRowChanged.connect(self._on_tile_selected)
        box.setEnabled(False)
        return box

    def _margin_spin(self, value):
        sb = QDoubleSpinBox()
        sb.setRange(0.0, 1.0)
        sb.setSingleStep(0.01)
        sb.setDecimals(2)
        sb.setValue(value)
        sb.valueChanged.connect(self._render)
        return sb

    def _on_preset(self, idx):
        if idx < 0 or idx >= len(_SIZE_PRESETS):
            return
        _label, w, h = _SIZE_PRESETS[idx]
        if w and h:
            prev = self._suspend
            self._suspend = True
            self._width_mm.setValue(w)
            self._height_mm.setValue(h)
            self._suspend = prev
            if not prev:
                self._render()

    # ── Settings (persisted in the .ksheet file) ─────────────────────
    def get_settings(self):
        return {
            "cols": self._cols.value(),
            "fill_order": self._fill_order.currentIndex(),
            "wspace": self._wspace.value(),
            "hspace": self._hspace.value(),
            "margins": {
                "left": self._m_left.value(),
                "right": self._m_right.value(),
                "top": self._m_top.value(),
                "bottom": self._m_bottom.value(),
            },
            "size_preset": self._size_preset.currentIndex(),
            "width_mm": self._width_mm.value(),
            "height_mm": self._height_mm.value(),
            "dpi": self._dpi.value(),
            "tiles": dict(self._tile_styles),
        }

    def apply_settings(self, st):
        if not st:
            return
        self._suspend = True
        try:
            self._cols.setValue(int(st.get("cols", self._cols.value())))
            self._fill_order.setCurrentIndex(int(st.get("fill_order", 0)))
            self._wspace.setValue(
                float(st.get("wspace", self._wspace.value())))
            self._hspace.setValue(
                float(st.get("hspace", self._hspace.value())))
            m = st.get("margins", {})
            self._m_left.setValue(float(m.get("left", self._m_left.value())))
            self._m_right.setValue(
                float(m.get("right", self._m_right.value())))
            self._m_top.setValue(float(m.get("top", self._m_top.value())))
            self._m_bottom.setValue(
                float(m.get("bottom", self._m_bottom.value())))
            self._size_preset.setCurrentIndex(
                int(st.get("size_preset", self._size_preset.currentIndex())))
            self._width_mm.setValue(
                float(st.get("width_mm", self._width_mm.value())))
            self._height_mm.setValue(
                float(st.get("height_mm", self._height_mm.value())))
            self._dpi.setValue(int(st.get("dpi", self._dpi.value())))
            self._tile_styles = dict(st.get("tiles", {}))
        finally:
            self._suspend = False
        self._render()

    # ── Plot list model ─────────────────────────────────────────────
    def rebuild_from_workbook(self):
        from collections import defaultdict
        collected = collect_charts(self._workbook)
        buckets = defaultdict(list)
        for t, d in collected:
            buckets[t].append(d)
        consumed = defaultdict(int)
        new_items = []
        # Preserve the user's existing order / visibility where titles match.
        for it in self._items:
            t = it["title"]
            lst = buckets.get(t, [])
            if consumed[t] < len(lst):
                new_items.append({"title": t, "dict": lst[consumed[t]],
                                  "visible": it["visible"]})
                consumed[t] += 1
        # Append any newly-created charts.
        for t, lst in buckets.items():
            while consumed[t] < len(lst):
                new_items.append({"title": t, "dict": lst[consumed[t]],
                                  "visible": True})
                consumed[t] += 1
        self._items = new_items
        self._repopulate_list()
        self._render()

    def _repopulate_list(self):
        self._suspend = True
        self._list.clear()
        for it in self._items:
            li = QListWidgetItem(it["title"])
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Checked if it["visible"] else Qt.Unchecked)
            self._list.addItem(li)
        self._suspend = False

    def _on_item_changed(self, item):
        if self._suspend:
            return
        row = self._list.row(item)
        if 0 <= row < len(self._items):
            self._items[row]["visible"] = (
                item.checkState() == Qt.Checked)
            self._render()

    def _move_selected(self, delta):
        row = self._list.currentRow()
        new = row + delta
        if row < 0 or new < 0 or new >= len(self._items):
            return
        self._items[row], self._items[new] = (
            self._items[new], self._items[row])
        self._repopulate_list()
        self._list.setCurrentRow(new)
        self._render()

    def _visible_items(self):
        return [it for it in self._items if it["visible"]]

    # ── Per-tile style ──────────────────────────────────────────────
    def _current_title(self):
        row = self._list.currentRow()
        if 0 <= row < len(self._items):
            return self._items[row]["title"]
        return None

    def _on_tile_selected(self, row):
        title = self._current_title()
        self._tile_box.setEnabled(title is not None)
        if title is None:
            return
        st = self._tile_styles.get(title, _DEFAULT_TILE_STYLE)
        self._suspend = True
        self._tile_face.set_color(st.get("face", "#ffffff"))
        self._tile_alpha.setValue(float(st.get("alpha", 1.0)))
        self._tile_border.setChecked(bool(st.get("border_on", True)))
        self._tile_edge.set_color(st.get("edge", "#000000"))
        self._tile_edge_w.setValue(float(st.get("edge_w", 1.0)))
        self._suspend = False

    def _on_tile_style_changed(self, *args):
        if self._suspend:
            return
        title = self._current_title()
        if title is None:
            return
        self._tile_styles[title] = {
            "face": self._tile_face.color(),
            "alpha": self._tile_alpha.value(),
            "border_on": self._tile_border.isChecked(),
            "edge": self._tile_edge.color(),
            "edge_w": self._tile_edge_w.value(),
        }
        self._render()

    def _clear_tile_style(self):
        title = self._current_title()
        if title is None:
            return
        self._tile_styles.pop(title, None)
        self._on_tile_selected(self._list.currentRow())
        self._render()

    @staticmethod
    def _apply_tile_style(ax, st):
        ax.patch.set_facecolor(st.get("face", "#ffffff"))
        ax.patch.set_alpha(float(st.get("alpha", 1.0)))
        on = bool(st.get("border_on", True))
        for sp in ax.spines.values():
            sp.set_visible(on)
            if on:
                sp.set_edgecolor(st.get("edge", "#000000"))
                sp.set_linewidth(float(st.get("edge_w", 1.0)))

    def _figsize_in(self):
        return (self._width_mm.value() / _MM_PER_IN,
                self._height_mm.value() / _MM_PER_IN)

    # ── To be implemented by subclasses ─────────────────────────────
    def _build_content(self):
        raise NotImplementedError

    def _render(self):
        raise NotImplementedError

    def _export(self):
        raise NotImplementedError


class CombinedLayoutTab(_BaseLayoutTab):
    """All charts as subplots of one figure — a single exportable panel."""

    _size_group_label = "Figure size (whole panel)"

    def _build_content(self):
        self._figure = Figure(figsize=(7.2, 5.4), dpi=100)
        self._canvas = FigureCanvas(self._figure)
        scroll = QScrollArea()
        # Keep the panel at its chosen size; don't stretch with the window.
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignCenter)
        scroll.setWidget(self._canvas)
        self._scroll = scroll
        return scroll

    def _render(self):
        if self._suspend:
            return
        fig = self._figure
        fig.clear()
        items = self._visible_items()
        w_in, h_in = self._figsize_in()
        fig.set_size_inches(w_in, h_in)
        # Show on screen at a viewable scale; export uses full DPI.
        # Fixed (not minimum) so the panel keeps its size when the window
        # is resized rather than stretching to fill the viewport.
        self._canvas.setFixedSize(int(w_in * 96), int(h_in * 96))
        if not items:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "No plots yet — create charts in the sheets,\n"
                    "then press Refresh.", ha="center", va="center",
                    transform=ax.transAxes, color="#888888")
            ax.axis("off")
            self._canvas.draw_idle()
            return
        n = len(items)
        cols = min(self._cols.value(), n)
        rows = (n + cols - 1) // cols
        order = _FILL_ORDERS[self._fill_order.currentIndex()][1]
        for i, it in enumerate(items):
            d = it["dict"]
            if order == "col":
                pos = (i % rows) * cols + (i // rows) + 1
            else:
                pos = i + 1
            kw = {"projection": "3d"} if _is_3d(d) else {}
            ax = fig.add_subplot(rows, cols, pos, **kw)
            try:
                render_chart(fig, ax, d)
            except Exception:
                ax.text(0.5, 0.5, "render error", ha="center",
                        va="center", transform=ax.transAxes)
            style = self._tile_styles.get(it["title"])
            if style:
                self._apply_tile_style(ax, style)
        fig.subplots_adjust(
            left=self._m_left.value(), right=self._m_right.value(),
            top=self._m_top.value(), bottom=self._m_bottom.value(),
            wspace=self._wspace.value(), hspace=self._hspace.value())
        self._canvas.draw_idle()

    def _export(self):
        if not self._visible_items():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Layout", "",
            "SVG (*.svg);;PDF (*.pdf);;PNG (*.png)")
        if not path:
            return
        fmt = path.rsplit(".", 1)[-1].lower()
        try:
            self._figure.savefig(path, format=fmt, dpi=self._dpi.value())
        except Exception:
            self._figure.savefig(path, dpi=self._dpi.value())


def is_layout_tab(widget):
    return isinstance(widget, _BaseLayoutTab)
