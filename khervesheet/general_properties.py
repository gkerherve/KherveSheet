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
    QLineEdit, QCheckBox, QComboBox, QDoubleSpinBox, QSpinBox,
    QPushButton, QDialogButtonBox, QWidget,
)


_GRID_STYLES = [
    ("Solid", "-"), ("Dashed", "--"), ("Dotted", ":"),
    ("Dash-dot", "-."),
]

# Default sketch parameters — see Artist.set_sketch_params.
_SKETCH_DEFAULTS = {"scale": 2.0, "length": 120.0, "randomness": 16.0}


def _hexify(color):
    """Coerce any matplotlib colour spec to a #rrggbb hex string."""
    try:
        return to_hex(color)
    except Exception:
        return "#ffffff"


def apply_sketch(chart, enabled, scale=None, length=None, randomness=None):
    """Enable/disable the wobbly hand-drawn sketch effect on every
    artist, spine and tick of the chart's axes."""
    ax = chart._ax
    if enabled:
        scale = scale if scale is not None else _SKETCH_DEFAULTS["scale"]
        length = length if length is not None else _SKETCH_DEFAULTS["length"]
        randomness = (randomness if randomness is not None
                      else _SKETCH_DEFAULTS["randomness"])
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
    sp = fig.subplotpars
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
        "sketch": bool(getattr(chart, "_sketch_on", False)),
        "sketch_scale": float(getattr(chart, "_sketch_scale",
                                       _SKETCH_DEFAULTS["scale"])),
        "sketch_length": float(getattr(chart, "_sketch_length",
                                        _SKETCH_DEFAULTS["length"])),
        "sketch_randomness": float(getattr(chart, "_sketch_randomness",
                                            _SKETCH_DEFAULTS["randomness"])),
        "tight_layout": bool(getattr(chart, "_tight_layout", False)),
        "keep_ratio": bool(getattr(chart, "_keep_ratio", False)),
        "margin_left": sp.left,
        "margin_right": sp.right,
        "margin_top": sp.top,
        "margin_bottom": sp.bottom,
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

    sketch_on = bool(state.get("sketch", False))
    chart._sketch_on = sketch_on
    sk_scale = float(state.get("sketch_scale", _SKETCH_DEFAULTS["scale"]))
    sk_length = float(state.get("sketch_length", _SKETCH_DEFAULTS["length"]))
    sk_rand = float(state.get("sketch_randomness",
                               _SKETCH_DEFAULTS["randomness"]))
    chart._sketch_scale = sk_scale
    chart._sketch_length = sk_length
    chart._sketch_randomness = sk_rand
    apply_sketch(chart, sketch_on, sk_scale, sk_length, sk_rand)

    # ── Layout controls ─────────────────────────────────────────────
    tight = bool(state.get("tight_layout", False))
    chart._tight_layout = tight
    if tight:
        try:
            fig.set_layout_engine("tight")
        except Exception:
            try:
                fig.tight_layout()
            except Exception:
                pass
    else:
        try:
            fig.set_layout_engine("none")
        except Exception:
            pass
        fig.subplots_adjust(
            left=float(state.get("margin_left", 0.15)),
            right=float(state.get("margin_right", 0.95)),
            top=float(state.get("margin_top", 0.92)),
            bottom=float(state.get("margin_bottom", 0.15)),
        )

    # ── Figure size ──────────────────────────────────────────────────
    fig_w = state.get("fig_width")
    fig_h = state.get("fig_height")
    if fig_w is not None and fig_h is not None:
        w, h = int(fig_w), int(fig_h)
        chart.resize(w, h)
        chart._aspect_ratio = w / max(h, 1)

    keep = bool(state.get("keep_ratio", False))
    chart._keep_ratio = keep
    if keep:
        chart._aspect_ratio = chart.width() / max(chart.height(), 1)

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
        self.resize(680, 520)
        self._chart = chart

        from .graph import _ColorButton  # lazy: graph imports us lazily

        state = dict(getattr(chart, "_general_props", None)
                     or default_general_state(chart))

        outer = QVBoxLayout(self)

        # Two-column body: left = existing groups, right = layout controls
        columns = QHBoxLayout()
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()

        # ── Titles ──────────────────────────────────────────────────
        title_box = QGroupBox("Titles")
        tform = QFormLayout(title_box)
        self.title_edit = QLineEdit(state.get("title", ""))
        self.xlabel_edit = QLineEdit(state.get("xlabel", ""))
        self.ylabel_edit = QLineEdit(state.get("ylabel", ""))
        tform.addRow("Title:", self.title_edit)
        tform.addRow("X Label:", self.xlabel_edit)
        tform.addRow("Y Label:", self.ylabel_edit)
        left_col.addWidget(title_box)

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
        left_col.addWidget(bg_box)

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
        left_col.addWidget(grid_box)

        left_col.addStretch()

        # ── RIGHT COLUMN: Figure Size ──────────────────────────────
        size_box = QGroupBox("Figure Size")
        sform = QFormLayout(size_box)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(100, 4000)
        self.width_spin.setSingleStep(10)
        self.width_spin.setSuffix(" px")
        self.width_spin.setValue(
            int(state.get("fig_width", chart.width())))
        sform.addRow("Width:", self.width_spin)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(100, 4000)
        self.height_spin.setSingleStep(10)
        self.height_spin.setSuffix(" px")
        self.height_spin.setValue(
            int(state.get("fig_height", chart.height())))
        sform.addRow("Height:", self.height_spin)
        # Preset buttons
        preset_row = QHBoxLayout()
        for label, pw, ph in (
            ("Square", 400, 400),
            ("Small", 320, 240),
            ("Medium", 480, 320),
            ("Large", 640, 480),
        ):
            btn = QPushButton(label)
            btn.setFixedHeight(24)
            btn.clicked.connect(
                lambda _=False, w=pw, h=ph: (
                    self.width_spin.setValue(w),
                    self.height_spin.setValue(h)))
            preset_row.addWidget(btn)
        sform.addRow(preset_row)
        right_col.addWidget(size_box)

        # ── Layout ──────────────────────────────────────────────────
        layout_box = QGroupBox("Layout")
        lform = QFormLayout(layout_box)
        self.tight_check = QCheckBox("Tight layout")
        self.tight_check.setChecked(bool(state.get("tight_layout", False)))
        lform.addRow(self.tight_check)
        self.ratio_check = QCheckBox("Keep proportions")
        self.ratio_check.setChecked(bool(state.get("keep_ratio", False)))
        lform.addRow(self.ratio_check)
        right_col.addWidget(layout_box)

        # ── Margins ─────────────────────────────────────────────────
        margin_box = QGroupBox("Margins")
        mform = QFormLayout(margin_box)
        sp = chart._figure.subplotpars
        self._margin_spins = {}
        for name, val in (
            ("left", state.get("margin_left", sp.left)),
            ("right", state.get("margin_right", sp.right)),
            ("top", state.get("margin_top", sp.top)),
            ("bottom", state.get("margin_bottom", sp.bottom)),
        ):
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1.0)
            spin.setSingleStep(0.01)
            spin.setDecimals(3)
            spin.setValue(float(val))
            mform.addRow(name.capitalize() + ":", spin)
            self._margin_spins[name] = spin
        right_col.addWidget(margin_box)

        # Disable margin spinboxes when tight layout is on.
        self.tight_check.toggled.connect(
            lambda on: margin_box.setEnabled(not on))
        margin_box.setEnabled(not self.tight_check.isChecked())

        # ── Effects ─────────────────────────────────────────────────
        fx_box = QGroupBox("Effects")
        fxform = QFormLayout(fx_box)
        self.sketch_check = QCheckBox("Cartoon (wobbly lines)")
        self.sketch_check.setChecked(bool(state.get("sketch", False)))
        fxform.addRow(self.sketch_check)

        self.sketch_scale = QDoubleSpinBox()
        self.sketch_scale.setRange(0.1, 20.0)
        self.sketch_scale.setSingleStep(0.5)
        self.sketch_scale.setDecimals(1)
        self.sketch_scale.setValue(
            float(state.get("sketch_scale", _SKETCH_DEFAULTS["scale"])))
        self.sketch_scale.setToolTip(
            "Amplitude of the wiggle perpendicular to the line")
        fxform.addRow("Scale:", self.sketch_scale)

        self.sketch_length = QDoubleSpinBox()
        self.sketch_length.setRange(1.0, 500.0)
        self.sketch_length.setSingleStep(10.0)
        self.sketch_length.setDecimals(1)
        self.sketch_length.setValue(
            float(state.get("sketch_length", _SKETCH_DEFAULTS["length"])))
        self.sketch_length.setToolTip(
            "Length of the wiggle along the line (in pixels)")
        fxform.addRow("Length:", self.sketch_length)

        self.sketch_randomness = QDoubleSpinBox()
        self.sketch_randomness.setRange(0.0, 100.0)
        self.sketch_randomness.setSingleStep(1.0)
        self.sketch_randomness.setDecimals(1)
        self.sketch_randomness.setValue(
            float(state.get("sketch_randomness",
                            _SKETCH_DEFAULTS["randomness"])))
        self.sketch_randomness.setToolTip(
            "Scale factor for the random offset of each wiggle")
        fxform.addRow("Randomness:", self.sketch_randomness)

        # Enable/disable sketch params when checkbox toggled.
        def _toggle_sketch_params(on):
            self.sketch_scale.setEnabled(on)
            self.sketch_length.setEnabled(on)
            self.sketch_randomness.setEnabled(on)
        self.sketch_check.toggled.connect(_toggle_sketch_params)
        _toggle_sketch_params(self.sketch_check.isChecked())

        right_col.addWidget(fx_box)

        right_col.addStretch()

        columns.addLayout(left_col, stretch=1)
        columns.addLayout(right_col, stretch=1)
        outer.addLayout(columns)

        # ── Footer ──────────────────────────────────────────────────
        footer = QHBoxLayout()
        series_btn = QPushButton("Series Properties\u2026")
        series_btn.clicked.connect(self._switch_to_series)
        footer.addWidget(series_btn)
        axis_btn = QPushButton("Axis Properties\u2026")
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
        state = {
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
            "sketch": self.sketch_check.isChecked(),
            "sketch_scale": self.sketch_scale.value(),
            "sketch_length": self.sketch_length.value(),
            "sketch_randomness": self.sketch_randomness.value(),
            "tight_layout": self.tight_check.isChecked(),
            "keep_ratio": self.ratio_check.isChecked(),
            "fig_width": self.width_spin.value(),
            "fig_height": self.height_spin.value(),
        }
        for k, spin in self._margin_spins.items():
            state[f"margin_{k}"] = spin.value()
        return state

    def apply_to_chart(self, chart):
        apply_general_state(chart, self._capture_state())

    # ── Cross-navigation ────────────────────────────────────────────
    def _switch_to_series(self):
        self.apply_to_chart(self._chart)
        self.done(self.SWITCH_TO_SERIES)

    def _switch_to_axis(self):
        self.apply_to_chart(self._chart)
        self.done(self.SWITCH_TO_AXIS)
