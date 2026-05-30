"""General (figure-level) chart properties dialog.

Exposes whole-plot settings that are not tied to a single data series or
a single axis: titles, plot/figure background colour and opacity, grid
appearance, frame spines, and a hand-drawn "cartoon" sketch effect.

The chosen state is stored on the chart as ``_general_props`` so it can
round-trip through the .ksheet format, mirroring how axis properties are
persisted via ``_axis_props``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from matplotlib.colors import to_hex

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QCheckBox, QComboBox, QDoubleSpinBox, QPushButton,
    QDialogButtonBox, QWidget,
)


_GRID_STYLES = [
    ("Solid", "-"), ("Dashed", "--"), ("Dotted", ":"),
    ("Dash-dot", "-."),
]

# Sketch parameters used when "cartoon" mode is enabled:
# (scale, length, randomness) — see Artist.set_sketch_params.
_SKETCH_PARAMS = (2.0, 120.0, 16.0)


def _hexify(color):
    """Coerce any matplotlib colour spec to a #rrggbb hex string."""
    try:
        return to_hex(color)
    except Exception:
        return "#ffffff"


def apply_sketch(chart, enabled):
    """Enable/disable the wobbly hand-drawn sketch effect on every
    artist, spine and tick of the chart's axes."""
    ax = chart._ax
    if enabled:
        scale, length, randomness = _SKETCH_PARAMS
    else:
        scale = length = randomness = None
    targets = list(ax.get_lines())
    targets += list(ax.collections)
    targets += list(ax.patches)
    targets += list(ax.spines.values())
    targets += list(ax.xaxis.get_ticklines())
    targets += list(ax.yaxis.get_ticklines())
    for t in targets:
        try:
            t.set_sketch_params(scale, length, randomness)
        except Exception:
            pass


def default_general_state(chart):
    """Read the chart's current general properties into a state dict."""
    ax = chart._ax
    fig = chart._figure
    grid_on = bool(ax.xaxis.get_gridlines()[0].get_visible()
                   if ax.xaxis.get_gridlines() else False)
    return {
        "title": ax.get_title(),
        "xlabel": ax.get_xlabel(),
        "ylabel": ax.get_ylabel(),
        "axes_facecolor": _hexify(ax.get_facecolor()),
        "axes_alpha": float(ax.patch.get_alpha() or 1.0),
        "fig_facecolor": _hexify(fig.get_facecolor()),
        "fig_alpha": float(fig.patch.get_alpha() or 1.0),
        "grid": grid_on,
        "grid_color": "#b0b0b0",
        "grid_alpha": 1.0,
        "grid_style": "-",
        "spine_top": ax.spines["top"].get_visible(),
        "spine_right": ax.spines["right"].get_visible(),
        "sketch": bool(getattr(chart, "_sketch_on", False)),
    }


def apply_general_state(chart, state):
    """Apply a general-properties state dict to the chart's axes/figure."""
    ax = chart._ax
    fig = chart._figure

    ax.set_title(state.get("title", ""))
    ax.set_xlabel(state.get("xlabel", "X"))
    ax.set_ylabel(state.get("ylabel", "Y"))

    ax.set_facecolor(state.get("axes_facecolor", "#ffffff"))
    ax.patch.set_alpha(float(state.get("axes_alpha", 1.0)))
    fig.patch.set_facecolor(state.get("fig_facecolor", "#ffffff"))
    fig.patch.set_alpha(float(state.get("fig_alpha", 1.0)))

    if state.get("grid", False):
        ax.grid(True,
                color=state.get("grid_color", "#b0b0b0"),
                alpha=float(state.get("grid_alpha", 1.0)),
                linestyle=state.get("grid_style", "-"))
    else:
        ax.grid(False)

    ax.spines["top"].set_visible(bool(state.get("spine_top", True)))
    ax.spines["right"].set_visible(bool(state.get("spine_right", True)))

    sketch_on = bool(state.get("sketch", False))
    chart._sketch_on = sketch_on
    apply_sketch(chart, sketch_on)

    chart._general_props = dict(state)
    chart._canvas.draw_idle()


class GeneralPropertiesDialog(QDialog):
    """Whole-plot ("general") properties editor with cross-navigation
    buttons to the Series and Axis property dialogs."""

    # Custom result codes for dialog switching.
    SWITCH_TO_SERIES = 2
    SWITCH_TO_AXIS = 3

    def __init__(self, chart, parent=None):
        super().__init__(parent or chart)
        self.setWindowTitle("General Properties")
        self.resize(420, 480)
        self._chart = chart

        from .graph import _ColorButton  # lazy: graph imports us lazily

        state = dict(getattr(chart, "_general_props", None)
                     or default_general_state(chart))

        outer = QVBoxLayout(self)

        # ── Titles ──────────────────────────────────────────────────
        title_box = QGroupBox("Titles")
        tform = QFormLayout(title_box)
        self.title_edit = QLineEdit(state.get("title", ""))
        self.xlabel_edit = QLineEdit(state.get("xlabel", ""))
        self.ylabel_edit = QLineEdit(state.get("ylabel", ""))
        tform.addRow("Title:", self.title_edit)
        tform.addRow("X Label:", self.xlabel_edit)
        tform.addRow("Y Label:", self.ylabel_edit)
        outer.addWidget(title_box)

        # ── Background ──────────────────────────────────────────────
        bg_box = QGroupBox("Background")
        bform = QFormLayout(bg_box)
        self.axes_color = _ColorButton(state.get("axes_facecolor", "#ffffff"))
        bform.addRow("Plot area color:", self.axes_color)
        self.axes_alpha = self._make_alpha(state.get("axes_alpha", 1.0))
        bform.addRow("Plot area opacity:", self.axes_alpha)
        self.fig_color = _ColorButton(state.get("fig_facecolor", "#ffffff"))
        bform.addRow("Figure color:", self.fig_color)
        self.fig_alpha = self._make_alpha(state.get("fig_alpha", 1.0))
        bform.addRow("Figure opacity:", self.fig_alpha)
        outer.addWidget(bg_box)

        # ── Grid ────────────────────────────────────────────────────
        grid_box = QGroupBox("Grid")
        gform = QFormLayout(grid_box)
        self.grid_check = QCheckBox("Show grid")
        self.grid_check.setChecked(bool(state.get("grid", False)))
        gform.addRow(self.grid_check)
        self.grid_color = _ColorButton(state.get("grid_color", "#b0b0b0"))
        gform.addRow("Grid color:", self.grid_color)
        self.grid_alpha = self._make_alpha(state.get("grid_alpha", 1.0))
        gform.addRow("Grid opacity:", self.grid_alpha)
        self.grid_style = QComboBox()
        for name, val in _GRID_STYLES:
            self.grid_style.addItem(name, val)
        cur_style = state.get("grid_style", "-")
        si = self.grid_style.findData(cur_style)
        if si >= 0:
            self.grid_style.setCurrentIndex(si)
        gform.addRow("Grid style:", self.grid_style)
        outer.addWidget(grid_box)

        # ── Frame & effects ─────────────────────────────────────────
        fx_box = QGroupBox("Frame && Effects")
        fxform = QFormLayout(fx_box)
        self.spine_top = QCheckBox("Show top border")
        self.spine_top.setChecked(bool(state.get("spine_top", True)))
        fxform.addRow(self.spine_top)
        self.spine_right = QCheckBox("Show right border")
        self.spine_right.setChecked(bool(state.get("spine_right", True)))
        fxform.addRow(self.spine_right)
        self.sketch_check = QCheckBox("Cartoon (wobbly lines)")
        self.sketch_check.setChecked(bool(state.get("sketch", False)))
        fxform.addRow(self.sketch_check)
        outer.addWidget(fx_box)

        outer.addStretch()

        # ── Footer ──────────────────────────────────────────────────
        footer = QHBoxLayout()
        series_btn = QPushButton("Series Properties…")
        series_btn.clicked.connect(self._switch_to_series)
        footer.addWidget(series_btn)
        axis_btn = QPushButton("Axis Properties…")
        axis_btn.clicked.connect(self._switch_to_axis)
        footer.addWidget(axis_btn)
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

    @staticmethod
    def _make_alpha(value):
        sb = QDoubleSpinBox()
        sb.setRange(0.0, 1.0)
        sb.setSingleStep(0.05)
        sb.setDecimals(2)
        sb.setValue(float(value))
        return sb

    # ── State capture / apply ──────────────────────────────────────
    def _capture_state(self):
        return {
            "title": self.title_edit.text(),
            "xlabel": self.xlabel_edit.text(),
            "ylabel": self.ylabel_edit.text(),
            "axes_facecolor": self.axes_color.color(),
            "axes_alpha": self.axes_alpha.value(),
            "fig_facecolor": self.fig_color.color(),
            "fig_alpha": self.fig_alpha.value(),
            "grid": self.grid_check.isChecked(),
            "grid_color": self.grid_color.color(),
            "grid_alpha": self.grid_alpha.value(),
            "grid_style": self.grid_style.currentData(),
            "spine_top": self.spine_top.isChecked(),
            "spine_right": self.spine_right.isChecked(),
            "sketch": self.sketch_check.isChecked(),
        }

    def apply_to_chart(self, chart):
        apply_general_state(chart, self._capture_state())

    # ── Cross-navigation ────────────────────────────────────────────
    def _switch_to_series(self):
        self.apply_to_chart(self._chart)
        self.done(self.SWITCH_TO_SERIES)

    def _switch_to_axis(self):
        self.apply_to_chart(self._chart)
        self.done(self.SWITCH_TO_AXIS)
