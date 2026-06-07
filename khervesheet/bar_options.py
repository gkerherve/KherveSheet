"""Bar chart options — grouping, stacking, per-series styling, and UI tab.

Provides the drawing logic for grouped / stacked / 100 %-stacked bar charts
and the "Bar" tab that plugs into PlotDetailsDialog.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import numpy as np

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox, QComboBox,
    QDoubleSpinBox, QCheckBox, QLineEdit, QLabel, QHBoxLayout,
    QPushButton, QColorDialog,
)

# ── Defaults ────────────────────────────────────────────────────────

DEFAULT_BAR_CONFIG = {
    "mode": "grouped",          # grouped | stacked | percent_stacked
    "orientation": "vertical",  # vertical | horizontal
    "gap_width": 0.2,           # spacing between groups (fraction)
}

DEFAULT_BAR_SERIES = {
    "width": 0.8,
    "edge_color": "#000000",
    "edge_width": 0.0,
    "hatch": "",
    "opacity": 1.0,
    "color_by_point": False,
    "data_labels": "none",       # none | outside | inside | center
    "data_label_fmt": "{:.1f}",
    "error_bars": None,          # None or dict
}

_HATCH_PATTERNS = [
    ("None", ""), ("/", "/"), ("\\", "\\"), ("|", "|"),
    ("-", "-"), ("+", "+"), ("x", "x"), ("o", "o"), (".", "."),
]

_LABEL_POSITIONS = ["None", "Outside", "Inside", "Center"]
_ERROR_MODES = ["None", "Constant", "From Column"]

# Default matplotlib colour cycle.
_DEFAULT_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]


def _series_bar_props(series_dict):
    """Return the bar property dict for a series, filling defaults."""
    bp = dict(DEFAULT_BAR_SERIES)
    bp.update(series_dict.get("bar", {}))
    return bp


# ── Drawing ─────────────────────────────────────────────────────────

def plot_bars(ax, series_list, bar_config, *, _colors=None):
    """(Re)draw all bar-type series on *ax*.

    Parameters
    ----------
    ax : matplotlib Axes
    series_list : list[dict]
        Full ``chart._series``; only entries with ``plot_type == "Bar"``
        are drawn.
    bar_config : dict
        Chart-level bar config (mode, orientation, gap_width).
    _colors : list[str] | None
        Explicit per-series colours (length ≥ bar count); when *None*
        the default colour cycle is used.

    Returns
    -------
    list[(int, BarContainer)]
        ``(series_index, artist)`` for every bar series drawn.
    """
    from matplotlib.container import BarContainer

    mode = bar_config.get("mode", "grouped")
    orientation = bar_config.get("orientation", "vertical")
    gap = bar_config.get("gap_width", 0.2)
    horiz = orientation == "horizontal"

    # Collect bar-type series (keep original index).
    bar_indices = [i for i, s in enumerate(series_list)
                   if s.get("plot_type") == "Bar"
                   and not s.get("is_trendline")]
    n_bars = len(bar_indices)
    if n_bars == 0:
        return []

    # Remove existing bar artists from axes.
    for idx in bar_indices:
        old = series_list[idx].get("artist")
        if old is not None:
            try:
                old.remove()
            except Exception:
                if hasattr(old, '__iter__'):
                    for child in old:
                        try:
                            child.remove()
                        except Exception:
                            pass
        # Also remove any lingering data-label texts.
        for txt in series_list[idx].get("_bar_labels", []):
            try:
                txt.remove()
            except Exception:
                pass
        series_list[idx]["_bar_labels"] = []

    # Resolve per-series colours.
    colors = _colors or []
    while len(colors) < n_bars:
        colors.append(_DEFAULT_COLORS[len(colors) % len(_DEFAULT_COLORS)])

    # Gather X/Y arrays.
    xs = [np.asarray(series_list[i]["x"]) for i in bar_indices]
    ys = [np.asarray(series_list[i]["y"]) for i in bar_indices]
    bar_props = [_series_bar_props(series_list[i]) for i in bar_indices]
    labels = [series_list[i]["label"] for i in bar_indices]

    results = []

    if mode == "grouped":
        results = _draw_grouped(ax, xs, ys, labels, bar_props, colors,
                                n_bars, gap, horiz)
    elif mode == "stacked":
        results = _draw_stacked(ax, xs, ys, labels, bar_props, colors,
                                n_bars, gap, horiz, percent=False)
    elif mode == "percent_stacked":
        results = _draw_stacked(ax, xs, ys, labels, bar_props, colors,
                                n_bars, gap, horiz, percent=True)
    else:
        results = _draw_grouped(ax, xs, ys, labels, bar_props, colors,
                                n_bars, gap, horiz)

    # Map artists back and apply per-series visuals.
    out = []
    for k, (container, bp) in enumerate(zip(
            [r for r in results], bar_props)):
        idx = bar_indices[k]
        series_list[idx]["artist"] = container
        _apply_visuals(ax, container, bp, series_list[idx], horiz)
        out.append((idx, container))

    return out


def _draw_grouped(ax, xs, ys, labels, bar_props, colors,
                  n_bars, gap, horiz):
    """Draw bars side-by-side (grouped)."""
    containers = []
    for k in range(n_bars):
        x, y = xs[k], ys[k]
        bp = bar_props[k]
        w = bp["width"] / n_bars
        # Offset: centre the group around x
        offset = (k - (n_bars - 1) / 2) * (w + gap / n_bars)
        kw = dict(width=w, label=labels[k], color=colors[k])
        if horiz:
            c = ax.barh(x + offset, y, height=w, label=labels[k],
                        color=colors[k])
        else:
            c = ax.bar(x + offset, y, **kw)
        containers.append(c)
    return containers


def _draw_stacked(ax, xs, ys, labels, bar_props, colors,
                  n_bars, gap, horiz, percent=False):
    """Draw bars stacked on top of each other."""
    # Use the longest x as the reference positions.
    ref_x = xs[0]
    for x in xs[1:]:
        if len(x) > len(ref_x):
            ref_x = x

    n_pts = len(ref_x)
    # Pad shorter series with zeros.
    padded = []
    for y in ys:
        if len(y) < n_pts:
            p = np.zeros(n_pts)
            p[:len(y)] = y
            padded.append(p)
        else:
            padded.append(y[:n_pts])

    if percent:
        totals = np.zeros(n_pts)
        for y in padded:
            totals += np.abs(y)
        totals[totals == 0] = 1.0
        padded = [(y / totals) * 100.0 for y in padded]

    w = bar_props[0]["width"] if bar_props else 0.8
    bottoms = np.zeros(n_pts)
    containers = []
    for k in range(n_bars):
        y = padded[k]
        if horiz:
            c = ax.barh(ref_x[:n_pts], y, left=bottoms, height=w,
                        label=labels[k], color=colors[k])
        else:
            c = ax.bar(ref_x[:n_pts], y, bottom=bottoms, width=w,
                       label=labels[k], color=colors[k])
        containers.append(c)
        bottoms = bottoms + y

    return containers


def _apply_visuals(ax, container, bp, series_dict, horiz):
    """Apply edge, hatch, opacity, data labels to a BarContainer."""
    edge_color = bp.get("edge_color", "#000000")
    edge_width = bp.get("edge_width", 0.0)
    hatch = bp.get("hatch", "")
    alpha = bp.get("opacity", 1.0)
    color_by_point = bp.get("color_by_point", False)

    for i, patch in enumerate(container.patches):
        if edge_width > 0:
            patch.set_edgecolor(edge_color)
            patch.set_linewidth(edge_width)
        else:
            patch.set_edgecolor("none")
            patch.set_linewidth(0)
        if hatch:
            patch.set_hatch(hatch)
        patch.set_alpha(alpha)
        if color_by_point:
            patch.set_facecolor(
                _DEFAULT_COLORS[i % len(_DEFAULT_COLORS)])

    # Data labels.
    dl = bp.get("data_labels", "none")
    fmt = bp.get("data_label_fmt", "{:.1f}")
    texts = []
    if dl != "none":
        for patch in container.patches:
            if horiz:
                val = patch.get_width()
                cx = patch.get_x()
                cy = patch.get_y() + patch.get_height() / 2
                if dl == "outside":
                    tx, ty = cx + val, cy
                    ha, va = "left", "center"
                elif dl == "inside":
                    tx, ty = cx + val * 0.5, cy
                    ha, va = "center", "center"
                else:  # center
                    tx, ty = cx + val * 0.5, cy
                    ha, va = "center", "center"
            else:
                val = patch.get_height()
                cx = patch.get_x() + patch.get_width() / 2
                cy = patch.get_y()
                if dl == "outside":
                    tx, ty = cx, cy + val
                    ha, va = "center", "bottom"
                elif dl == "inside":
                    tx, ty = cx, cy + val * 0.5
                    ha, va = "center", "center"
                else:  # center
                    tx, ty = cx, cy + val * 0.5
                    ha, va = "center", "center"
            try:
                label_text = fmt.format(val)
            except (ValueError, KeyError):
                label_text = str(val)
            txt = ax.text(tx, ty, label_text, ha=ha, va=va, fontsize=7,
                          clip_on=True)
            texts.append(txt)
    series_dict["_bar_labels"] = texts

    # Error bars.
    eb = bp.get("error_bars")
    if eb and eb.get("type") == "constant":
        val = eb.get("value", 0)
        if val > 0:
            x_vals = [p.get_x() + p.get_width() / 2
                      for p in container.patches]
            y_vals = [p.get_height() + p.get_y()
                      for p in container.patches]
            if horiz:
                ax.errorbar(
                    [p.get_width() + p.get_x() for p in container.patches],
                    x_vals, xerr=val, fmt="none", ecolor=eb.get("color", "black"),
                    capsize=3)
            else:
                ax.errorbar(x_vals, y_vals, yerr=val, fmt="none",
                            ecolor=eb.get("color", "black"), capsize=3)


# ── UI Tab ──────────────────────────────────────────────────────────

class BarOptionsTab(QWidget):
    """The 'Bar' tab for PlotDetailsDialog.

    Exposes chart-level bar config (mode, orientation, gap) and
    per-series properties (width, edge, hatch, opacity, labels, etc.).
    """

    def __init__(self, chart, parent=None):
        super().__init__(parent)
        self._chart = chart
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── Chart-level ─────────────────────────────────────────────
        grp = QGroupBox("Chart-level")
        gf = QFormLayout(grp)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Grouped", "Stacked", "100% Stacked"])
        cfg = getattr(chart, "_bar_config", DEFAULT_BAR_CONFIG)
        mode_map = {"grouped": 0, "stacked": 1, "percent_stacked": 2}
        self.mode_combo.setCurrentIndex(mode_map.get(cfg.get("mode"), 0))
        gf.addRow("Grouping:", self.mode_combo)

        self.orient_combo = QComboBox()
        self.orient_combo.addItems(["Vertical", "Horizontal"])
        self.orient_combo.setCurrentIndex(
            0 if cfg.get("orientation", "vertical") == "vertical" else 1)
        gf.addRow("Orientation:", self.orient_combo)

        self.gap_spin = QDoubleSpinBox()
        self.gap_spin.setRange(0.0, 2.0)
        self.gap_spin.setSingleStep(0.05)
        self.gap_spin.setValue(cfg.get("gap_width", 0.2))
        gf.addRow("Gap Width:", self.gap_spin)

        layout.addWidget(grp)

        # ── Per-series ──────────────────────────────────────────────
        grp2 = QGroupBox("Series")
        sf = QFormLayout(grp2)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.1, 1.0)
        self.width_spin.setSingleStep(0.05)
        self.width_spin.setValue(0.8)
        sf.addRow("Bar Width:", self.width_spin)

        self.fill_color_btn = _BarColorButton("#1f77b4")
        sf.addRow("Fill Color:", self.fill_color_btn)

        self.edge_color_btn = _BarColorButton("#000000")
        sf.addRow("Edge Color:", self.edge_color_btn)

        self.edge_width_spin = QDoubleSpinBox()
        self.edge_width_spin.setRange(0.0, 5.0)
        self.edge_width_spin.setSingleStep(0.5)
        self.edge_width_spin.setValue(0.0)
        sf.addRow("Edge Width:", self.edge_width_spin)

        self.hatch_combo = QComboBox()
        for name, _ in _HATCH_PATTERNS:
            self.hatch_combo.addItem(name)
        sf.addRow("Hatch:", self.hatch_combo)

        self.opacity_spin = QDoubleSpinBox()
        self.opacity_spin.setRange(0.0, 1.0)
        self.opacity_spin.setSingleStep(0.05)
        self.opacity_spin.setValue(1.0)
        sf.addRow("Opacity:", self.opacity_spin)

        self.cbp_check = QCheckBox("Color each bar differently")
        sf.addRow(self.cbp_check)

        self.label_combo = QComboBox()
        self.label_combo.addItems(_LABEL_POSITIONS)
        sf.addRow("Data Labels:", self.label_combo)

        self.label_fmt = QLineEdit("{:.1f}")
        self.label_fmt.setPlaceholderText("{:.1f}")
        sf.addRow("Label Format:", self.label_fmt)

        # Error bars row.
        self.error_combo = QComboBox()
        self.error_combo.addItems(_ERROR_MODES)
        sf.addRow("Error Bars:", self.error_combo)

        err_row = QHBoxLayout()
        self.error_value = QDoubleSpinBox()
        self.error_value.setRange(0.0, 1e9)
        self.error_value.setSingleStep(0.1)
        self.error_value.setValue(0.0)
        err_row.addWidget(QLabel("Value:"))
        err_row.addWidget(self.error_value)
        self.error_color_btn = _BarColorButton("#000000")
        err_row.addWidget(QLabel("Color:"))
        err_row.addWidget(self.error_color_btn)
        sf.addRow("", err_row)

        self.error_combo.currentIndexChanged.connect(
            lambda i: self.error_value.setEnabled(i == 1))
        self.error_value.setEnabled(False)

        layout.addWidget(grp2)
        layout.addStretch()

    # ── Read / write helpers ────────────────────────────────────────

    def read_from_series(self, series_dict):
        """Populate per-series widgets from series data."""
        bp = _series_bar_props(series_dict)
        self.width_spin.setValue(bp["width"])
        self.edge_width_spin.setValue(bp["edge_width"])
        self.opacity_spin.setValue(bp["opacity"])
        self.cbp_check.setChecked(bp["color_by_point"])

        self.edge_color_btn.set_color(bp["edge_color"])

        # Fill colour — read from bar props or from the artist.
        fc = bp.get("fill_color")
        if not fc:
            artist = series_dict.get("artist")
            if artist is not None:
                from matplotlib.container import BarContainer
                if isinstance(artist, BarContainer) and artist.patches:
                    from matplotlib.colors import to_hex
                    try:
                        fc = to_hex(artist.patches[0].get_facecolor())
                    except Exception:
                        pass
        if fc:
            self.fill_color_btn.set_color(fc)

        # Hatch.
        h = bp["hatch"]
        for i, (_, code) in enumerate(_HATCH_PATTERNS):
            if code == h:
                self.hatch_combo.setCurrentIndex(i)
                break

        # Data labels.
        dl = bp["data_labels"]
        lbl_map = {"none": 0, "outside": 1, "inside": 2, "center": 3}
        self.label_combo.setCurrentIndex(lbl_map.get(dl, 0))
        self.label_fmt.setText(bp["data_label_fmt"])

        # Error bars.
        eb = bp.get("error_bars")
        if eb and eb.get("type") == "constant":
            self.error_combo.setCurrentIndex(1)
            self.error_value.setValue(eb.get("value", 0))
            self.error_value.setEnabled(True)
            if eb.get("color"):
                self.error_color_btn.set_color(eb["color"])
        else:
            self.error_combo.setCurrentIndex(0)
            self.error_value.setEnabled(False)

    def write_to_series(self, series_dict):
        """Save per-series widget state into the series dict."""
        bp = series_dict.setdefault("bar", {})
        bp["width"] = self.width_spin.value()
        bp["fill_color"] = self.fill_color_btn.color()
        bp["edge_color"] = self.edge_color_btn.color()
        bp["edge_width"] = self.edge_width_spin.value()
        bp["hatch"] = _HATCH_PATTERNS[self.hatch_combo.currentIndex()][1]
        bp["opacity"] = self.opacity_spin.value()
        bp["color_by_point"] = self.cbp_check.isChecked()

        dl_idx = self.label_combo.currentIndex()
        bp["data_labels"] = ["none", "outside", "inside", "center"][dl_idx]
        bp["data_label_fmt"] = self.label_fmt.text() or "{:.1f}"

        ei = self.error_combo.currentIndex()
        if ei == 1:
            bp["error_bars"] = {
                "type": "constant",
                "value": self.error_value.value(),
                "color": self.error_color_btn.color(),
            }
        else:
            bp["error_bars"] = None

    def write_chart_config(self):
        """Return the chart-level bar config from the widgets."""
        mode_map = {0: "grouped", 1: "stacked", 2: "percent_stacked"}
        return {
            "mode": mode_map.get(self.mode_combo.currentIndex(), "grouped"),
            "orientation": ("vertical" if self.orient_combo.currentIndex() == 0
                            else "horizontal"),
            "gap_width": self.gap_spin.value(),
        }


# ── Tiny colour button (self-contained, no graph.py import) ────────

class _BarColorButton(QPushButton):
    """Small colour swatch button for the bar tab."""

    def __init__(self, color="#1f77b4", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(28, 22)
        self._update()
        self.clicked.connect(self._pick)

    def color(self):
        return self._color

    def set_color(self, c):
        self._color = c
        self._update()

    def _update(self):
        self.setStyleSheet(
            f"background: {self._color}; border: 1px solid #888;")

    def _pick(self):
        from PyQt5.QtGui import QColor
        c = QColorDialog.getColor(QColor(self._color), self)
        if c.isValid():
            self._color = c.name()
            self._update()
