"""Axis properties dialog — comprehensive per-axis configuration.

Provides full control over each axis side (Bottom, Top, Left, Right):
scale, title, tick labels, line & ticks, and grids.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox,
    QSpinBox, QDoubleSpinBox, QTabWidget, QWidget, QGroupBox,
    QDialogButtonBox, QColorDialog, QSizePolicy,
)

import matplotlib.ticker as mticker


# ── Colour button ───────────────────────────────────────────────────

class _ColorButton(QPushButton):
    """Small button that shows and edits a colour."""

    def __init__(self, color="#000000", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(28, 22)
        self._update_style()
        self.clicked.connect(self._pick)

    def color(self):
        return self._color

    def set_color(self, c):
        if isinstance(c, (list, tuple)):
            from matplotlib.colors import to_hex
            c = to_hex(c)
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


# ── Side rail ───────────────────────────────────────────────────────

class _SideRail(QWidget):
    """Four auto-exclusive buttons to pick Bottom/Top/Left/Right."""

    def __init__(self, callback, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(2)
        self._buttons = {}
        self._callback = callback
        for side in ("Bottom", "Top", "Left", "Right"):
            b = QPushButton(side)
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setMinimumWidth(60)
            b.clicked.connect(lambda _, s=side: self._on_click(s))
            h.addWidget(b)
            self._buttons[side] = b

    def set_side(self, side):
        self._buttons[side].setChecked(True)

    def _on_click(self, side):
        self._callback(side)


# ── Main dialog ─────────────────────────────────────────────────────

_TICK_FORMATS = [
    ("Auto", "auto"),
    ("Decimal", "decimal"),
    ("Scientific", "scientific"),
    ("Engineering", "engineering"),
    ("Percentage", "percent"),
    ("Plain", "plain"),
]

_TICK_DIRECTIONS = [("Out", "out"), ("In", "in"), ("In & Out", "inout")]

_LINE_STYLES = [
    ("Solid", "-"), ("Dashed", "--"), ("Dotted", ":"),
    ("Dash-dot", "-."),
]

_FONTS = ["Default", "Arial", "Times New Roman", "Courier New",
          "Helvetica"]


class AxisPropertiesDialog(QDialog):
    """Comprehensive per-axis dialog: scale, title, tick labels,
    line & ticks, grids — for Bottom, Top, Left, or Right."""

    _AXIS_LABEL = {
        "Bottom": "Axis Properties — Bottom (X)",
        "Top": "Axis Properties — Top (X)",
        "Left": "Axis Properties — Left (Y)",
        "Right": "Axis Properties — Right (Y)",
    }

    def __init__(self, chart, side, parent=None):
        super().__init__(parent or chart)
        self._chart = chart
        self._side = side
        self._ax = chart._ax

        self.setWindowTitle(self._AXIS_LABEL.get(side, side))
        self.resize(460, 520)

        outer = QVBoxLayout(self)

        # Side rail.
        self._rail = _SideRail(self._switch_side)
        outer.addWidget(self._rail)

        # Tabs.
        self._tabs = QTabWidget()
        outer.addWidget(self._tabs, stretch=1)

        self._build_scale_tab()
        self._build_title_tab()
        self._build_tick_labels_tab()
        self._build_line_ticks_tab()
        self._build_grids_tab()

        # Footer.
        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply
            | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.Apply).clicked.connect(
            self._apply_current)
        outer.addWidget(bb)

        # Per-side state cache.
        self._side_states = {}
        self._current_side = None

        # Populate from current side.
        self._rail.set_side(side)
        self._switch_side(side)

    # ── Tab builders ────────────────────────────────────────────────

    def _build_scale_tab(self):
        w = QWidget()
        form = QFormLayout(w)

        self.scale_combo = QComboBox()
        self.scale_combo.addItems(
            ["linear", "log", "symlog", "logit"])
        form.addRow("Scale:", self.scale_combo)

        self.limit_auto = QCheckBox("Auto limits")
        self.limit_auto.setChecked(True)
        self.limit_auto.toggled.connect(self._on_auto_limits)
        form.addRow(self.limit_auto)

        self.limit_min = QDoubleSpinBox()
        self.limit_min.setRange(-1e15, 1e15)
        self.limit_min.setDecimals(6)
        form.addRow("Min:", self.limit_min)

        self.limit_max = QDoubleSpinBox()
        self.limit_max.setRange(-1e15, 1e15)
        self.limit_max.setDecimals(6)
        form.addRow("Max:", self.limit_max)

        self.invert_check = QCheckBox("Invert axis")
        form.addRow(self.invert_check)

        self._tabs.addTab(w, "Scale")

    def _build_title_tab(self):
        w = QWidget()
        form = QFormLayout(w)

        self.title_show = QCheckBox("Show title")
        self.title_show.setChecked(True)
        form.addRow(self.title_show)

        self.title_text = QLineEdit()
        form.addRow("Text:", self.title_text)

        self.title_color = _ColorButton("#000000")
        form.addRow("Color:", self.title_color)

        self.title_font = QComboBox()
        self.title_font.addItems(_FONTS)
        form.addRow("Font:", self.title_font)

        self.title_size = QSpinBox()
        self.title_size.setRange(4, 96)
        self.title_size.setValue(10)
        form.addRow("Size:", self.title_size)

        self.title_bold = QCheckBox("Bold")
        self.title_italic = QCheckBox("Italic")
        style_row = QHBoxLayout()
        style_row.addWidget(self.title_bold)
        style_row.addWidget(self.title_italic)
        style_row.addStretch()
        form.addRow("Style:", style_row)

        self.title_rotation = QComboBox()
        self.title_rotation.addItems(["0", "90", "180", "270"])
        self.title_rotation.setEditable(True)
        form.addRow("Rotation:", self.title_rotation)

        self._tabs.addTab(w, "Title")

    def _build_tick_labels_tab(self):
        w = QWidget()
        form = QFormLayout(w)

        self.tl_show = QCheckBox("Show tick labels")
        self.tl_show.setChecked(True)
        form.addRow(self.tl_show)

        form.addRow(QLabel(""))

        self.tl_format = QComboBox()
        for name, _ in _TICK_FORMATS:
            self.tl_format.addItem(name)
        form.addRow("Format:", self.tl_format)

        self.tl_decimals = QSpinBox()
        self.tl_decimals.setRange(0, 12)
        self.tl_decimals.setValue(2)
        form.addRow("Decimal places:", self.tl_decimals)

        self.tl_prefix = QLineEdit()
        form.addRow("Prefix:", self.tl_prefix)

        self.tl_suffix = QLineEdit()
        form.addRow("Suffix:", self.tl_suffix)

        form.addRow(QLabel(""))

        self.tl_color = _ColorButton("#000000")
        form.addRow("Color:", self.tl_color)

        self.tl_size = QSpinBox()
        self.tl_size.setRange(4, 96)
        self.tl_size.setValue(10)
        form.addRow("Font size:", self.tl_size)

        self.tl_rotation = QSpinBox()
        self.tl_rotation.setRange(-360, 360)
        self.tl_rotation.setValue(0)
        form.addRow("Rotation:", self.tl_rotation)

        self._tabs.addTab(w, "Tick Labels")

    def _build_line_ticks_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        # ── Spine ──────────────────────────────────────────────────
        spine_grp = QGroupBox("Axis Line (Spine)")
        sf = QFormLayout(spine_grp)

        self.spine_show = QCheckBox("Show")
        self.spine_show.setChecked(True)
        sf.addRow(self.spine_show)

        self.spine_color = _ColorButton("#000000")
        sf.addRow("Color:", self.spine_color)

        self.spine_width = QDoubleSpinBox()
        self.spine_width.setRange(0.0, 20.0)
        self.spine_width.setSingleStep(0.5)
        self.spine_width.setValue(0.8)
        sf.addRow("Width:", self.spine_width)

        layout.addWidget(spine_grp)

        # ── Major ticks ────────────────────────────────────────────
        major_grp = QGroupBox("Major Ticks")
        mf = QFormLayout(major_grp)

        self.major_show = QCheckBox("Show")
        self.major_show.setChecked(True)
        mf.addRow(self.major_show)

        self.major_direction = QComboBox()
        for name, _ in _TICK_DIRECTIONS:
            self.major_direction.addItem(name)
        mf.addRow("Direction:", self.major_direction)

        self.major_length = QDoubleSpinBox()
        self.major_length.setRange(0.0, 30.0)
        self.major_length.setSingleStep(1.0)
        self.major_length.setValue(3.5)
        mf.addRow("Length:", self.major_length)

        self.major_width = QDoubleSpinBox()
        self.major_width.setRange(0.0, 10.0)
        self.major_width.setSingleStep(0.5)
        self.major_width.setValue(0.8)
        mf.addRow("Width:", self.major_width)

        self.major_color = _ColorButton("#000000")
        mf.addRow("Color:", self.major_color)

        self.major_count = QSpinBox()
        self.major_count.setRange(2, 50)
        self.major_count.setValue(6)
        self.major_count.setToolTip("Approximate number of major ticks")
        mf.addRow("Count:", self.major_count)

        layout.addWidget(major_grp)

        # ── Minor ticks ────────────────────────────────────────────
        minor_grp = QGroupBox("Minor Ticks")
        nf = QFormLayout(minor_grp)

        self.minor_show = QCheckBox("Show")
        nf.addRow(self.minor_show)

        self.minor_direction = QComboBox()
        for name, _ in _TICK_DIRECTIONS:
            self.minor_direction.addItem(name)
        nf.addRow("Direction:", self.minor_direction)

        self.minor_length = QDoubleSpinBox()
        self.minor_length.setRange(0.0, 30.0)
        self.minor_length.setSingleStep(1.0)
        self.minor_length.setValue(2.0)
        nf.addRow("Length:", self.minor_length)

        self.minor_width = QDoubleSpinBox()
        self.minor_width.setRange(0.0, 10.0)
        self.minor_width.setSingleStep(0.5)
        self.minor_width.setValue(0.6)
        nf.addRow("Width:", self.minor_width)

        self.minor_color = _ColorButton("#000000")
        nf.addRow("Color:", self.minor_color)

        self.minor_count = QSpinBox()
        self.minor_count.setRange(1, 20)
        self.minor_count.setValue(5)
        self.minor_count.setToolTip("Subdivisions per major interval")
        nf.addRow("Subdivisions:", self.minor_count)

        layout.addWidget(minor_grp)
        layout.addStretch()

        self._tabs.addTab(w, "Line && Ticks")

    def _build_grids_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        # ── Major grid ─────────────────────────────────────────────
        mg = QGroupBox("Major Grid")
        mf = QFormLayout(mg)

        self.grid_major_show = QCheckBox("Show")
        mf.addRow(self.grid_major_show)

        self.grid_major_color = _ColorButton("#cccccc")
        mf.addRow("Color:", self.grid_major_color)

        self.grid_major_alpha = QDoubleSpinBox()
        self.grid_major_alpha.setRange(0.0, 1.0)
        self.grid_major_alpha.setSingleStep(0.05)
        self.grid_major_alpha.setValue(0.7)
        mf.addRow("Opacity:", self.grid_major_alpha)

        self.grid_major_style = QComboBox()
        for name, _ in _LINE_STYLES:
            self.grid_major_style.addItem(name)
        mf.addRow("Style:", self.grid_major_style)

        self.grid_major_width = QDoubleSpinBox()
        self.grid_major_width.setRange(0.0, 10.0)
        self.grid_major_width.setSingleStep(0.5)
        self.grid_major_width.setValue(0.8)
        mf.addRow("Width:", self.grid_major_width)

        layout.addWidget(mg)

        # ── Minor grid ─────────────────────────────────────────────
        ng = QGroupBox("Minor Grid")
        nf = QFormLayout(ng)

        self.grid_minor_show = QCheckBox("Show")
        nf.addRow(self.grid_minor_show)

        self.grid_minor_color = _ColorButton("#e0e0e0")
        nf.addRow("Color:", self.grid_minor_color)

        self.grid_minor_alpha = QDoubleSpinBox()
        self.grid_minor_alpha.setRange(0.0, 1.0)
        self.grid_minor_alpha.setSingleStep(0.05)
        self.grid_minor_alpha.setValue(0.4)
        nf.addRow("Opacity:", self.grid_minor_alpha)

        self.grid_minor_style = QComboBox()
        for name, _ in _LINE_STYLES:
            self.grid_minor_style.addItem(name)
        self.grid_minor_style.setCurrentIndex(2)  # dotted
        nf.addRow("Style:", self.grid_minor_style)

        self.grid_minor_width = QDoubleSpinBox()
        self.grid_minor_width.setRange(0.0, 10.0)
        self.grid_minor_width.setSingleStep(0.5)
        self.grid_minor_width.setValue(0.5)
        nf.addRow("Width:", self.grid_minor_width)

        layout.addWidget(ng)
        layout.addStretch()

        self._tabs.addTab(w, "Grids")

    # ── Auto limits toggle ─────────────────────────────────────────
    def _on_auto_limits(self, auto):
        self.limit_min.setEnabled(not auto)
        self.limit_max.setEnabled(not auto)

    # ── Side switching ─────────────────────────────────────────────

    def _switch_side(self, side):
        """Save current side state, load new side state."""
        if self._current_side:
            self._side_states[self._current_side] = \
                self._capture_widgets()
        self._current_side = side
        self._side = side
        self.setWindowTitle(self._AXIS_LABEL.get(side, side))

        if side in self._side_states:
            self._restore_widgets(self._side_states[side])
        else:
            self._refresh_from_axes(side)

    def _capture_widgets(self):
        """Snapshot all widget values into a dict."""
        return {
            # Scale
            "scale": self.scale_combo.currentText(),
            "limit_auto": self.limit_auto.isChecked(),
            "limit_min": self.limit_min.value(),
            "limit_max": self.limit_max.value(),
            "invert": self.invert_check.isChecked(),
            # Title
            "title_show": self.title_show.isChecked(),
            "title_text": self.title_text.text(),
            "title_color": self.title_color.color(),
            "title_font": self.title_font.currentText(),
            "title_size": self.title_size.value(),
            "title_bold": self.title_bold.isChecked(),
            "title_italic": self.title_italic.isChecked(),
            "title_rotation": self.title_rotation.currentText(),
            # Tick labels
            "tl_show": self.tl_show.isChecked(),
            "tl_format": self.tl_format.currentIndex(),
            "tl_decimals": self.tl_decimals.value(),
            "tl_prefix": self.tl_prefix.text(),
            "tl_suffix": self.tl_suffix.text(),
            "tl_color": self.tl_color.color(),
            "tl_size": self.tl_size.value(),
            "tl_rotation": self.tl_rotation.value(),
            # Spine
            "spine_show": self.spine_show.isChecked(),
            "spine_color": self.spine_color.color(),
            "spine_width": self.spine_width.value(),
            # Major ticks
            "major_show": self.major_show.isChecked(),
            "major_dir": self.major_direction.currentIndex(),
            "major_length": self.major_length.value(),
            "major_width": self.major_width.value(),
            "major_color": self.major_color.color(),
            "major_count": self.major_count.value(),
            # Minor ticks
            "minor_show": self.minor_show.isChecked(),
            "minor_dir": self.minor_direction.currentIndex(),
            "minor_length": self.minor_length.value(),
            "minor_width": self.minor_width.value(),
            "minor_color": self.minor_color.color(),
            "minor_count": self.minor_count.value(),
            # Grids
            "grid_major_show": self.grid_major_show.isChecked(),
            "grid_major_color": self.grid_major_color.color(),
            "grid_major_alpha": self.grid_major_alpha.value(),
            "grid_major_style": self.grid_major_style.currentIndex(),
            "grid_major_width": self.grid_major_width.value(),
            "grid_minor_show": self.grid_minor_show.isChecked(),
            "grid_minor_color": self.grid_minor_color.color(),
            "grid_minor_alpha": self.grid_minor_alpha.value(),
            "grid_minor_style": self.grid_minor_style.currentIndex(),
            "grid_minor_width": self.grid_minor_width.value(),
        }

    def _restore_widgets(self, st):
        """Restore widget values from a captured dict."""
        self.scale_combo.setCurrentText(st["scale"])
        self.limit_auto.setChecked(st["limit_auto"])
        self.limit_min.setValue(st["limit_min"])
        self.limit_max.setValue(st["limit_max"])
        self._on_auto_limits(st["limit_auto"])
        self.invert_check.setChecked(st["invert"])

        self.title_show.setChecked(st["title_show"])
        self.title_text.setText(st["title_text"])
        self.title_color.set_color(st["title_color"])
        self.title_font.setCurrentText(st["title_font"])
        self.title_size.setValue(st["title_size"])
        self.title_bold.setChecked(st["title_bold"])
        self.title_italic.setChecked(st["title_italic"])
        self.title_rotation.setCurrentText(st["title_rotation"])

        self.tl_show.setChecked(st["tl_show"])
        self.tl_format.setCurrentIndex(st["tl_format"])
        self.tl_decimals.setValue(st["tl_decimals"])
        self.tl_prefix.setText(st["tl_prefix"])
        self.tl_suffix.setText(st["tl_suffix"])
        self.tl_color.set_color(st["tl_color"])
        self.tl_size.setValue(st["tl_size"])
        self.tl_rotation.setValue(st["tl_rotation"])

        self.spine_show.setChecked(st["spine_show"])
        self.spine_color.set_color(st["spine_color"])
        self.spine_width.setValue(st["spine_width"])

        self.major_show.setChecked(st["major_show"])
        self.major_direction.setCurrentIndex(st["major_dir"])
        self.major_length.setValue(st["major_length"])
        self.major_width.setValue(st["major_width"])
        self.major_color.set_color(st["major_color"])
        self.major_count.setValue(st["major_count"])

        self.minor_show.setChecked(st["minor_show"])
        self.minor_direction.setCurrentIndex(st["minor_dir"])
        self.minor_length.setValue(st["minor_length"])
        self.minor_width.setValue(st["minor_width"])
        self.minor_color.set_color(st["minor_color"])
        self.minor_count.setValue(st["minor_count"])

        self.grid_major_show.setChecked(st["grid_major_show"])
        self.grid_major_color.set_color(st["grid_major_color"])
        self.grid_major_alpha.setValue(st["grid_major_alpha"])
        self.grid_major_style.setCurrentIndex(st["grid_major_style"])
        self.grid_major_width.setValue(st["grid_major_width"])
        self.grid_minor_show.setChecked(st["grid_minor_show"])
        self.grid_minor_color.set_color(st["grid_minor_color"])
        self.grid_minor_alpha.setValue(st["grid_minor_alpha"])
        self.grid_minor_style.setCurrentIndex(st["grid_minor_style"])
        self.grid_minor_width.setValue(st["grid_minor_width"])

    # ── Read current axes state ────────────────────────────────────

    def _refresh_from_axes(self, side):
        """Read the matplotlib axes and populate widgets for *side*."""
        ax = self._ax
        is_x = side in ("Bottom", "Top")
        spine_key = {"Bottom": "bottom", "Top": "top",
                     "Left": "left", "Right": "right"}[side]
        mpl_axis = ax.xaxis if is_x else ax.yaxis

        # Scale.
        cur_scale = ax.get_xscale() if is_x else ax.get_yscale()
        self.scale_combo.setCurrentText(cur_scale)
        lims = ax.get_xlim() if is_x else ax.get_ylim()
        self.limit_auto.setChecked(True)
        self.limit_min.setValue(lims[0])
        self.limit_max.setValue(lims[1])
        self._on_auto_limits(True)
        inverted = (ax.xaxis_inverted() if is_x
                    else ax.yaxis_inverted())
        self.invert_check.setChecked(bool(inverted))

        # Title — for Bottom/Left use native label; for Top/Right
        # check for stored secondary labels on the chart.
        if side == "Bottom":
            label_text = ax.get_xlabel()
        elif side == "Left":
            label_text = ax.get_ylabel()
        elif side == "Top":
            label_text = getattr(
                self._chart, '_top_label_text', '')
        else:  # Right
            label_text = getattr(
                self._chart, '_right_label_text', '')

        self.title_show.setChecked(bool(label_text))
        self.title_text.setText(label_text)

        # Read label font properties from the native label artist.
        if side in ("Bottom", "Top"):
            label_art = ax.xaxis.label
        else:
            label_art = ax.yaxis.label
        try:
            from matplotlib.colors import to_hex
            self.title_color.set_color(to_hex(label_art.get_color()))
        except Exception:
            self.title_color.set_color("#000000")
        self.title_size.setValue(int(label_art.get_fontsize()))
        fp = label_art.get_fontproperties()
        self.title_bold.setChecked(
            str(fp.get_weight()) in ("bold", "heavy", "extra bold",
                                     "700", "800", "900"))
        self.title_italic.setChecked(
            fp.get_style() in ("italic", "oblique"))
        self.title_rotation.setCurrentText(
            str(int(label_art.get_rotation())))

        # Font family.
        fam = fp.get_name()
        idx = self.title_font.findText(fam)
        self.title_font.setCurrentIndex(max(0, idx))

        # Tick labels — read visibility from tick params.
        _side_show = {
            "Bottom": "labelbottom", "Top": "labeltop",
            "Left": "labelleft", "Right": "labelright",
        }
        # Default visibility: Bottom/Left on, Top/Right off.
        tl_vis = side in ("Bottom", "Left")
        major_ticks = mpl_axis.get_major_ticks()
        if major_ticks:
            tk = major_ticks[0]
            if side in ("Bottom", "Left"):
                tl_vis = tk.label1.get_visible()
            else:
                tl_vis = tk.label2.get_visible()
        self.tl_show.setChecked(tl_vis)
        self.tl_format.setCurrentIndex(0)  # Auto
        self.tl_decimals.setValue(2)
        self.tl_prefix.setText("")
        self.tl_suffix.setText("")
        try:
            from matplotlib.colors import to_hex
            if major_ticks:
                lbl = (major_ticks[0].label1 if side in
                       ("Bottom", "Left") else major_ticks[0].label2)
                self.tl_color.set_color(to_hex(lbl.get_color()))
                self.tl_size.setValue(int(lbl.get_fontsize()))
                self.tl_rotation.setValue(int(lbl.get_rotation()))
            else:
                self.tl_color.set_color("#000000")
                self.tl_size.setValue(10)
                self.tl_rotation.setValue(0)
        except Exception:
            self.tl_color.set_color("#000000")
            self.tl_size.setValue(10)
            self.tl_rotation.setValue(0)

        # Spine.
        spine = ax.spines[spine_key]
        self.spine_show.setChecked(spine.get_visible())
        try:
            from matplotlib.colors import to_hex
            self.spine_color.set_color(to_hex(spine.get_edgecolor()))
        except Exception:
            self.spine_color.set_color("#000000")
        self.spine_width.setValue(spine.get_linewidth())

        # Major ticks.
        self.major_show.setChecked(True)
        if major_ticks:
            tk = major_ticks[0]
            vis = (tk.tick1line.get_visible()
                   if hasattr(tk, 'tick1line') else True)
            self.major_show.setChecked(vis)
        self.major_direction.setCurrentIndex(0)  # out
        try:
            tp = ax.yaxis.get_tick_params() if not is_x \
                else ax.xaxis.get_tick_params()
        except Exception:
            tp = {}
        direction = tp.get('tickdir', 'out')
        for i, (_, code) in enumerate(_TICK_DIRECTIONS):
            if code == direction:
                self.major_direction.setCurrentIndex(i)
                break
        self.major_length.setValue(
            float(tp.get('major_tick_length',
                         tp.get('length', 3.5))))
        self.major_width.setValue(
            float(tp.get('major_tick_width',
                         tp.get('width', 0.8))))
        try:
            from matplotlib.colors import to_hex
            mc = tp.get('color', '#000000')
            if not isinstance(mc, str):
                mc = to_hex(mc)
            self.major_color.set_color(mc)
        except Exception:
            self.major_color.set_color("#000000")
        n_major = len(mpl_axis.get_majorticklocs())
        self.major_count.setValue(max(2, n_major))

        # Minor ticks.
        loc = mpl_axis.get_minor_locator()
        minor_on = not isinstance(loc, mticker.NullLocator)
        self.minor_show.setChecked(minor_on)
        self.minor_direction.setCurrentIndex(
            self.major_direction.currentIndex())
        self.minor_length.setValue(2.0)
        self.minor_width.setValue(0.6)
        self.minor_color.set_color(self.major_color.color())
        self.minor_count.setValue(5)

        # Grids.
        major_grid = any(gl.get_visible()
                         for gl in mpl_axis.get_gridlines())
        self.grid_major_show.setChecked(major_grid)
        if mpl_axis.get_gridlines():
            gl = mpl_axis.get_gridlines()[0]
            try:
                from matplotlib.colors import to_hex
                self.grid_major_color.set_color(
                    to_hex(gl.get_color()))
            except Exception:
                pass
            self.grid_major_alpha.setValue(gl.get_alpha() or 0.7)
            ls = gl.get_linestyle()
            for i, (_, code) in enumerate(_LINE_STYLES):
                if code == ls:
                    self.grid_major_style.setCurrentIndex(i)
                    break
            self.grid_major_width.setValue(gl.get_linewidth())
        self.grid_minor_show.setChecked(False)

    # ── Apply ──────────────────────────────────────────────────────

    def _apply_current(self):
        """Apply current side to the chart without closing."""
        self._side_states[self._current_side] = \
            self._capture_widgets()
        self._apply_side(self._current_side)

    def apply_to_chart(self, chart):
        """Apply all modified sides to the chart (called on OK)."""
        self._side_states[self._current_side] = \
            self._capture_widgets()
        for side, st in self._side_states.items():
            self._apply_side(side, st)

    def _apply_side(self, side, st=None):
        """Apply one side's state to the chart axes."""
        if st is None:
            st = self._side_states.get(side)
        if st is None:
            return
        ax = self._ax
        is_x = side in ("Bottom", "Top")
        spine_key = {"Bottom": "bottom", "Top": "top",
                     "Left": "left", "Right": "right"}[side]
        mpl_axis = ax.xaxis if is_x else ax.yaxis
        _side_param = {"Bottom": "bottom", "Top": "top",
                       "Left": "left", "Right": "right"}[side]

        # ── Scale ──────────────────────────────────────────────────
        try:
            if is_x:
                ax.set_xscale(st["scale"])
            else:
                ax.set_yscale(st["scale"])
        except ValueError:
            pass

        if not st["limit_auto"]:
            if is_x:
                ax.set_xlim(st["limit_min"], st["limit_max"])
            else:
                ax.set_ylim(st["limit_min"], st["limit_max"])

        # Invert.
        currently_inverted = (ax.xaxis_inverted() if is_x
                              else ax.yaxis_inverted())
        if st["invert"] != currently_inverted:
            if is_x:
                ax.invert_xaxis()
            else:
                ax.invert_yaxis()

        # ── Title ──────────────────────────────────────────────────
        text = st["title_text"] if st["title_show"] else ""
        weight = "bold" if st["title_bold"] else "normal"
        style = "italic" if st["title_italic"] else "normal"
        font_family = st["title_font"]
        if font_family == "Default":
            font_family = "sans-serif"
        try:
            rotation = int(st["title_rotation"])
        except (ValueError, TypeError):
            rotation = 0

        title_kw = dict(
            fontsize=st["title_size"],
            color=st["title_color"],
            fontweight=weight,
            fontstyle=style,
            fontfamily=font_family,
            rotation=rotation,
        )

        if side == "Bottom":
            ax.set_xlabel(text, **title_kw)
        elif side == "Left":
            ax.set_ylabel(text, **title_kw)
        elif side == "Top":
            self._chart._top_label_text = text
            self._set_secondary_label(
                self._chart, "top", text, title_kw)
        else:  # Right
            self._chart._right_label_text = text
            self._set_secondary_label(
                self._chart, "right", text, title_kw)

        # ── Spine ──────────────────────────────────────────────────
        spine = ax.spines[spine_key]
        spine.set_visible(st["spine_show"])
        spine.set_edgecolor(st["spine_color"])
        spine.set_linewidth(st["spine_width"])

        # ── Tick labels ────────────────────────────────────────────
        label_kw = {
            _side_param: st["tl_show"],
            f"label{_side_param}": st["tl_show"],
        }
        mpl_axis.set_tick_params(which='both', **label_kw)

        if st["tl_show"]:
            tl_props = dict(
                color=st["tl_color"],
                fontsize=st["tl_size"],
                rotation=st["tl_rotation"],
            )
            ax.tick_params(
                axis='x' if is_x else 'y',
                which='major',
                labelcolor=st["tl_color"],
                labelsize=st["tl_size"],
                labelrotation=st["tl_rotation"],
            )

            # Tick format.
            fmt_idx = st["tl_format"]
            fmt_code = _TICK_FORMATS[fmt_idx][1]
            decimals = st["tl_decimals"]
            prefix = st["tl_prefix"]
            suffix = st["tl_suffix"]
            self._apply_tick_format(
                mpl_axis, fmt_code, decimals, prefix, suffix)

        # ── Major ticks ────────────────────────────────────────────
        tick_dir = _TICK_DIRECTIONS[st["major_dir"]][1]
        if st["major_show"]:
            mpl_axis.set_major_locator(
                mticker.MaxNLocator(nbins=st["major_count"]))
            ax.tick_params(
                axis='x' if is_x else 'y',
                which='major',
                direction=tick_dir,
                length=st["major_length"],
                width=st["major_width"],
                color=st["major_color"],
                **{_side_param: True},
            )
        else:
            mpl_axis.set_major_locator(mticker.NullLocator())

        # ── Minor ticks ────────────────────────────────────────────
        minor_dir = _TICK_DIRECTIONS[st["minor_dir"]][1]
        if st["minor_show"]:
            mpl_axis.set_minor_locator(
                mticker.AutoMinorLocator(st["minor_count"]))
            ax.tick_params(
                axis='x' if is_x else 'y',
                which='minor',
                direction=minor_dir,
                length=st["minor_length"],
                width=st["minor_width"],
                color=st["minor_color"],
                **{_side_param: True},
            )
        else:
            mpl_axis.set_minor_locator(mticker.NullLocator())

        # ── Grids ──────────────────────────────────────────────────
        major_ls = _LINE_STYLES[st["grid_major_style"]][1]
        minor_ls = _LINE_STYLES[st["grid_minor_style"]][1]

        ax.grid(
            st["grid_major_show"],
            axis='x' if is_x else 'y',
            which='major',
            color=st["grid_major_color"],
            alpha=st["grid_major_alpha"],
            linestyle=major_ls,
            linewidth=st["grid_major_width"],
        )
        if st["minor_show"]:
            ax.grid(
                st["grid_minor_show"],
                axis='x' if is_x else 'y',
                which='minor',
                color=st["grid_minor_color"],
                alpha=st["grid_minor_alpha"],
                linestyle=minor_ls,
                linewidth=st["grid_minor_width"],
            )

        self._chart._canvas.draw_idle()

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _apply_tick_format(mpl_axis, fmt_code, decimals,
                           prefix, suffix):
        """Apply a tick label formatter to *mpl_axis*."""
        if fmt_code == "auto":
            mpl_axis.set_major_formatter(
                mticker.ScalarFormatter())
        elif fmt_code == "decimal":
            fmt_str = f"{{:{prefix},.{decimals}f}}{suffix}"
            mpl_axis.set_major_formatter(
                mticker.FuncFormatter(
                    lambda v, _: f"{prefix}{v:,.{decimals}f}"
                    f"{suffix}"))
        elif fmt_code == "scientific":
            mpl_axis.set_major_formatter(
                mticker.FuncFormatter(
                    lambda v, _: f"{prefix}{v:.{decimals}e}"
                    f"{suffix}"))
        elif fmt_code == "engineering":
            mpl_axis.set_major_formatter(
                mticker.EngFormatter(places=decimals,
                                     sep="\N{THIN SPACE}"))
        elif fmt_code == "percent":
            mpl_axis.set_major_formatter(
                mticker.PercentFormatter())
        elif fmt_code == "plain":
            mpl_axis.set_major_formatter(
                mticker.FuncFormatter(
                    lambda v, _: f"{prefix}{v:.{decimals}f}"
                    f"{suffix}"))

    @staticmethod
    def _set_secondary_label(chart, location, text, title_kw):
        """Place or update a secondary axis label (top or right)
        using an axes Text annotation stored on the chart."""
        attr = f"_{location}_label_artist"
        old = getattr(chart, attr, None)
        if old is not None:
            try:
                old.remove()
            except Exception:
                pass
            setattr(chart, attr, None)

        if not text:
            return

        ax = chart._ax
        if location == "top":
            art = ax.text(
                0.5, 1.02, text, transform=ax.transAxes,
                ha='center', va='bottom', **title_kw)
        else:  # right
            art = ax.text(
                1.02, 0.5, text, transform=ax.transAxes,
                ha='left', va='center',
                rotation=270 if title_kw.get('rotation', 0) == 0
                else title_kw['rotation'],
                fontsize=title_kw.get('fontsize', 10),
                color=title_kw.get('color', '#000000'),
                fontweight=title_kw.get('fontweight', 'normal'),
                fontstyle=title_kw.get('fontstyle', 'normal'),
                fontfamily=title_kw.get('fontfamily', 'sans-serif'),
            )
        setattr(chart, attr, art)
