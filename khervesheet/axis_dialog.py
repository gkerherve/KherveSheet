"""Axis properties dialog — comprehensive per-axis configuration.

Two main tabs: Bottom (X) and Left (Y).  Each contains property sub-tabs
for scale, title, tick labels, line & ticks, grids, plus a secondary-side
tab (Top / Right) exposing only the properties that matplotlib allows to
be controlled independently on the opposite side of the same axis.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox,
    QSpinBox, QDoubleSpinBox, QTabWidget, QWidget, QGroupBox,
    QDialogButtonBox, QColorDialog, QSlider,
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
        dlg = QColorDialog(QColor(self._color), self)
        dlg.setStyleSheet("")        # prevent app theme bleeding in
        if dlg.exec_() == QColorDialog.Accepted:
            self._color = dlg.currentColor().name()
            self._update_style()


# ── Styled side notebook ────────────────────────────────────────────

_SIDE_TAB_STYLE = """
QTabBar::tab {
    min-width: 100px;
    padding: 6px 16px;
    font-weight: bold;
    color: #555;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #f4f4f4, stop:1 #e0e0e0);
    border: 1px solid #b0b0b0;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    color: #1a1a1a;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:1 #f0f4fa);
    border-bottom: 2px solid #3078c6;
}
QTabBar::tab:hover:!selected {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #fafafa, stop:1 #eaeef4);
    color: #333;
}
"""


# ── Main dialog ─────────────────────────────────────────────────────

_TICK_FORMATS = [
    ("Auto", "auto"),
    ("Decimal", "decimal"),
    ("Scientific (1.23e+05)", "scientific"),
    ("Scientific (\u00d710\u207f)", "std_scientific"),
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
    """Two-tab axis dialog: Bottom (X) and Left (Y).

    Each main tab contains property sub-tabs for scale, title,
    tick labels, line & ticks, grids — plus a secondary-side tab
    (Top Axis / Right Axis) with the subset of properties that
    matplotlib allows to be controlled independently.
    """

    def __init__(self, chart, side, parent=None):
        super().__init__(parent or chart)
        self._chart = chart
        self._ax = chart._ax

        self.setWindowTitle("Axis Properties")
        self.resize(480, 560)

        outer = QVBoxLayout(self)

        # ── Side notebook: Bottom (X) | Left (Y) | Front (Z) ────
        self._side_tabs = QTabWidget()
        self._side_tabs.setStyleSheet(_SIDE_TAB_STYLE)
        for label in ("Bottom (X)", "Left (Y)", "Front (Z)"):
            placeholder = QWidget()
            placeholder.setMaximumHeight(0)
            self._side_tabs.addTab(placeholder, label)
        self._side_tabs.setMaximumHeight(
            self._side_tabs.tabBar().sizeHint().height() + 4)
        self._side_tabs.currentChanged.connect(self._on_side_tab)
        outer.addWidget(self._side_tabs)
        # Z tab is only enabled for 3D plots (Heatmap colour-bar axis,
        # 3D Surface z-axis).
        is_3d = any(s.get("plot_type") in ("Heatmap", "3D Surface")
                     for s in chart._series)
        self._side_tabs.setTabEnabled(2, is_3d)

        # ── Property sub-tabs ─────────────────────────────────────
        self._tabs = QTabWidget()
        outer.addWidget(self._tabs, stretch=1)

        self._build_scale_tab()
        self._build_title_tab()
        self._build_tick_labels_tab()
        self._build_line_ticks_tab()
        self._build_grids_tab()
        self._build_secondary_tab()

        # ── Footer ────────────────────────────────────────────────
        footer = QHBoxLayout()
        gen_btn = QPushButton("General Properties\u2026")
        gen_btn.clicked.connect(self._switch_to_general)
        footer.addWidget(gen_btn)
        pd_btn = QPushButton("Series Properties\u2026")
        pd_btn.clicked.connect(self._switch_to_plot_details)
        footer.addWidget(pd_btn)
        footer.addStretch()
        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply
            | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.Apply).clicked.connect(
            self._apply_current)
        footer.addWidget(bb)
        outer.addLayout(footer)

        # ── Per-direction state cache ─────────────────────────────
        # Pre-load from chart's saved axis properties so that manual
        # limits and other settings persist across dialog sessions.
        self._dir_states = dict(getattr(chart, '_axis_props', {}) or {})
        self._current_dir = None

        # ── Initial selection ─────────────────────────────────────
        open_secondary = side in ("Top", "Right")
        if side in ("Bottom", "Top"):
            self._side_tabs.setCurrentIndex(0)
            self._switch_dir("x")
        else:
            self._side_tabs.setCurrentIndex(1)
            self._switch_dir("y")
        if open_secondary:
            self._tabs.setCurrentIndex(5)   # secondary tab

    # ── Tab builders ────────────────────────────────────────────────

    # Slider resolution: number of discrete steps.
    _SLIDER_STEPS = 1000

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

        # ── Min: slider + spin box ─────────────────────────────────
        self.limit_min = QDoubleSpinBox()
        self.limit_min.setRange(-1e15, 1e15)
        self.limit_min.setDecimals(4)
        self._min_slider = QSlider(Qt.Horizontal)
        self._min_slider.setRange(0, self._SLIDER_STEPS)
        min_row = QHBoxLayout()
        min_row.addWidget(self._min_slider, stretch=1)
        min_row.addWidget(self.limit_min)
        form.addRow("Min:", min_row)

        # ── Max: slider + spin box ─────────────────────────────────
        self.limit_max = QDoubleSpinBox()
        self.limit_max.setRange(-1e15, 1e15)
        self.limit_max.setDecimals(4)
        self._max_slider = QSlider(Qt.Horizontal)
        self._max_slider.setRange(0, self._SLIDER_STEPS)
        max_row = QHBoxLayout()
        max_row.addWidget(self._max_slider, stretch=1)
        max_row.addWidget(self.limit_max)
        form.addRow("Max:", max_row)

        # Slider ↔ spin box sync + live preview.
        self._min_slider.valueChanged.connect(self._on_min_slider)
        self._max_slider.valueChanged.connect(self._on_max_slider)
        self.limit_min.valueChanged.connect(self._on_min_spin)
        self.limit_max.valueChanged.connect(self._on_max_spin)

        # Slider range bookkeeping (set in _refresh_from_axes).
        self._slider_lo = 0.0
        self._slider_hi = 1.0

        self.invert_check = QCheckBox("Invert axis")
        form.addRow(self.invert_check)

        self._tabs.addTab(w, "Scale")

    # ── Slider helpers ─────────────────────────────────────────────

    def _setup_slider_range(self, lo, hi):
        """Configure the slider mapping from [lo, hi]."""
        # Always use ascending order for slider range, even if axis
        # is inverted (where get_xlim returns high, low).
        lo, hi = min(lo, hi), max(lo, hi)
        margin = max(abs(hi - lo) * 0.5, 1e-6)
        self._slider_lo = lo - margin
        self._slider_hi = hi + margin

    def _val_to_slider(self, val):
        span = self._slider_hi - self._slider_lo
        if span == 0:
            return 0
        frac = (val - self._slider_lo) / span
        return int(max(0, min(self._SLIDER_STEPS,
                              frac * self._SLIDER_STEPS)))

    def _slider_to_val(self, pos):
        frac = pos / self._SLIDER_STEPS
        return self._slider_lo + frac * (self._slider_hi - self._slider_lo)

    def _on_min_slider(self, pos):
        val = self._slider_to_val(pos)
        self.limit_min.blockSignals(True)
        self.limit_min.setValue(val)
        self.limit_min.blockSignals(False)
        self._live_update_limits()

    def _on_max_slider(self, pos):
        val = self._slider_to_val(pos)
        self.limit_max.blockSignals(True)
        self.limit_max.setValue(val)
        self.limit_max.blockSignals(False)
        self._live_update_limits()

    def _on_min_spin(self, val):
        self._min_slider.blockSignals(True)
        self._min_slider.setValue(self._val_to_slider(val))
        self._min_slider.blockSignals(False)
        self._live_update_limits()

    def _on_max_spin(self, val):
        self._max_slider.blockSignals(True)
        self._max_slider.setValue(self._val_to_slider(val))
        self._max_slider.blockSignals(False)
        self._live_update_limits()

    def _live_update_limits(self):
        """Apply min/max to the chart in real time."""
        if self.limit_auto.isChecked():
            return
        ax = self._ax
        is_x = (self._current_dir == "x")
        lo = self.limit_min.value()
        hi = self.limit_max.value()
        if is_x:
            ax.set_xlim(lo, hi)
        else:
            ax.set_ylim(lo, hi)
        self._chart._canvas.draw_idle()

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
        self.spine_width.setValue(1.0)
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
        self.major_width.setValue(1.0)
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
        self.minor_width.setValue(1.0)
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

    # ── Secondary axis tab (Top / Right) ───────────────────────────

    def _build_secondary_tab(self):
        """Properties independently controllable on the opposite side.

        matplotlib shares scale, limits, locators, formatters, tick
        styling (direction / width / color / length), and grids between
        both sides of an axis.  Only the spine, per-side tick & label
        visibility, and a secondary title can be set independently.
        """
        w = QWidget()
        layout = QVBoxLayout(w)

        # ── Spine ──────────────────────────────────────────────────
        spine_grp = QGroupBox("Spine")
        sf = QFormLayout(spine_grp)

        self.sec_spine_show = QCheckBox("Show")
        sf.addRow(self.sec_spine_show)

        self.sec_spine_color = _ColorButton("#000000")
        sf.addRow("Color:", self.sec_spine_color)

        self.sec_spine_width = QDoubleSpinBox()
        self.sec_spine_width.setRange(0.0, 20.0)
        self.sec_spine_width.setSingleStep(0.5)
        self.sec_spine_width.setValue(1.0)
        sf.addRow("Width:", self.sec_spine_width)

        self.sec_spine_style = QComboBox()
        for name, _ in _LINE_STYLES:
            self.sec_spine_style.addItem(name)
        sf.addRow("Style:", self.sec_spine_style)

        layout.addWidget(spine_grp)

        # ── Ticks & labels visibility ──────────────────────────────
        vis_grp = QGroupBox("Ticks && Labels")
        vf = QFormLayout(vis_grp)

        self.sec_tick_show = QCheckBox("Show ticks")
        vf.addRow(self.sec_tick_show)

        self.sec_label_show = QCheckBox("Show tick labels")
        vf.addRow(self.sec_label_show)

        layout.addWidget(vis_grp)

        # ── Title ──────────────────────────────────────────────────
        title_grp = QGroupBox("Title")
        tf = QFormLayout(title_grp)

        self.sec_title_show = QCheckBox("Show title")
        tf.addRow(self.sec_title_show)

        self.sec_title_text = QLineEdit()
        tf.addRow("Text:", self.sec_title_text)

        self.sec_title_color = _ColorButton("#000000")
        tf.addRow("Color:", self.sec_title_color)

        self.sec_title_font = QComboBox()
        self.sec_title_font.addItems(_FONTS)
        tf.addRow("Font:", self.sec_title_font)

        self.sec_title_size = QSpinBox()
        self.sec_title_size.setRange(4, 96)
        self.sec_title_size.setValue(10)
        tf.addRow("Size:", self.sec_title_size)

        self.sec_title_bold = QCheckBox("Bold")
        self.sec_title_italic = QCheckBox("Italic")
        style_row = QHBoxLayout()
        style_row.addWidget(self.sec_title_bold)
        style_row.addWidget(self.sec_title_italic)
        style_row.addStretch()
        tf.addRow("Style:", style_row)

        self.sec_title_rotation = QComboBox()
        self.sec_title_rotation.addItems(["0", "90", "180", "270"])
        self.sec_title_rotation.setEditable(True)
        tf.addRow("Rotation:", self.sec_title_rotation)

        self.sec_title_offset = QDoubleSpinBox()
        self.sec_title_offset.setRange(0.0, 0.50)
        self.sec_title_offset.setSingleStep(0.02)
        self.sec_title_offset.setDecimals(2)
        self.sec_title_offset.setValue(0.08)
        self.sec_title_offset.setToolTip(
            "Distance from the axes edge in axes-fraction units.\n"
            "Increase to push the title further from the plot.")
        tf.addRow("Offset:", self.sec_title_offset)

        layout.addWidget(title_grp)
        layout.addStretch()

        # Tab label updated dynamically in _switch_dir.
        self._tabs.addTab(w, "Top Axis")

    # ── Auto limits toggle ─────────────────────────────────────────
    def _on_auto_limits(self, auto):
        self.limit_min.setEnabled(not auto)
        self.limit_max.setEnabled(not auto)
        self._min_slider.setEnabled(not auto)
        self._max_slider.setEnabled(not auto)

    # ── Side switching ─────────────────────────────────────────────

    def _on_side_tab(self, index):
        """Called when the top-level side tab changes."""
        direction = ("x", "y", "z")[min(index, 2)]
        self._switch_dir(direction)

    def _switch_dir(self, direction):
        """Save current direction state, load new direction state."""
        if self._current_dir:
            self._dir_states[self._current_dir] = \
                self._capture_widgets()
        self._current_dir = direction

        # Update secondary tab label.
        if direction == "x":
            sec_label = "Top Axis"
        elif direction == "y":
            sec_label = "Right Axis"
        else:
            sec_label = "Back Axis"
        self._tabs.setTabText(5, sec_label)

        if direction in self._dir_states:
            self._restore_widgets(self._dir_states[direction])
        else:
            self._refresh_from_axes(direction)

    def _capture_widgets(self):
        """Snapshot all widget values into a dict."""
        return {
            # Scale
            "scale": self.scale_combo.currentText(),
            "limit_auto": self.limit_auto.isChecked(),
            "limit_min": self.limit_min.value(),
            "limit_max": self.limit_max.value(),
            "invert": self.invert_check.isChecked(),
            # Title (primary: Bottom / Left)
            "title_show": self.title_show.isChecked(),
            "title_text": self.title_text.text(),
            "title_color": self.title_color.color(),
            "title_font": self.title_font.currentText(),
            "title_size": self.title_size.value(),
            "title_bold": self.title_bold.isChecked(),
            "title_italic": self.title_italic.isChecked(),
            "title_rotation": self.title_rotation.currentText(),
            # Tick labels (shared styling, primary-side visibility)
            "tl_show": self.tl_show.isChecked(),
            "tl_format": self.tl_format.currentIndex(),
            "tl_decimals": self.tl_decimals.value(),
            "tl_prefix": self.tl_prefix.text(),
            "tl_suffix": self.tl_suffix.text(),
            "tl_color": self.tl_color.color(),
            "tl_size": self.tl_size.value(),
            "tl_rotation": self.tl_rotation.value(),
            # Spine (primary)
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
            # Secondary side (Top / Right)
            "sec_spine_show": self.sec_spine_show.isChecked(),
            "sec_spine_color": self.sec_spine_color.color(),
            "sec_spine_width": self.sec_spine_width.value(),
            "sec_spine_style": self.sec_spine_style.currentIndex(),
            "sec_tick_show": self.sec_tick_show.isChecked(),
            "sec_label_show": self.sec_label_show.isChecked(),
            "sec_title_show": self.sec_title_show.isChecked(),
            "sec_title_text": self.sec_title_text.text(),
            "sec_title_color": self.sec_title_color.color(),
            "sec_title_font": self.sec_title_font.currentText(),
            "sec_title_size": self.sec_title_size.value(),
            "sec_title_bold": self.sec_title_bold.isChecked(),
            "sec_title_italic": self.sec_title_italic.isChecked(),
            "sec_title_rotation":
                self.sec_title_rotation.currentText(),
            "sec_title_offset": self.sec_title_offset.value(),
        }

    def _restore_widgets(self, st):
        """Restore widget values from a captured dict."""
        self.scale_combo.setCurrentText(st["scale"])
        self._setup_slider_range(st["limit_min"], st["limit_max"])
        self.limit_auto.setChecked(st["limit_auto"])
        self.limit_min.blockSignals(True)
        self.limit_max.blockSignals(True)
        self.limit_min.setValue(st["limit_min"])
        self.limit_max.setValue(st["limit_max"])
        self._min_slider.blockSignals(True)
        self._max_slider.blockSignals(True)
        self._min_slider.setValue(self._val_to_slider(st["limit_min"]))
        self._max_slider.setValue(self._val_to_slider(st["limit_max"]))
        self._min_slider.blockSignals(False)
        self._max_slider.blockSignals(False)
        self.limit_min.blockSignals(False)
        self.limit_max.blockSignals(False)
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

        # Secondary side.
        self.sec_spine_show.setChecked(st["sec_spine_show"])
        self.sec_spine_color.set_color(st["sec_spine_color"])
        self.sec_spine_width.setValue(st["sec_spine_width"])
        self.sec_spine_style.setCurrentIndex(st["sec_spine_style"])
        self.sec_tick_show.setChecked(st["sec_tick_show"])
        self.sec_label_show.setChecked(st["sec_label_show"])
        self.sec_title_show.setChecked(st["sec_title_show"])
        self.sec_title_text.setText(st["sec_title_text"])
        self.sec_title_color.set_color(st["sec_title_color"])
        self.sec_title_font.setCurrentText(st["sec_title_font"])
        self.sec_title_size.setValue(st["sec_title_size"])
        self.sec_title_bold.setChecked(st["sec_title_bold"])
        self.sec_title_italic.setChecked(st["sec_title_italic"])
        self.sec_title_rotation.setCurrentText(
            st["sec_title_rotation"])
        self.sec_title_offset.setValue(st.get("sec_title_offset", 0.08))

    # ── Read current axes state ────────────────────────────────────

    def _refresh_from_axes(self, direction):
        """Read matplotlib axes and populate widgets for *direction*.

        direction is "x" (Bottom + Top), "y" (Left + Right), or "z"
        (Front / Back on 3-D axes).
        """
        ax = self._ax
        is_x = (direction == "x")
        is_z = (direction == "z")
        if is_z:
            # 3-D z-axis — fall back to sensible defaults if not 3D.
            has_z = hasattr(ax, 'get_zlim')
            pri_key = "left"
            sec_key = "right"
            mpl_axis = getattr(ax, 'zaxis', ax.yaxis)
            if has_z:
                cur_scale = ax.get_zscale() if hasattr(
                    ax, 'get_zscale') else "linear"
                lims = ax.get_zlim()
                inverted = False
            else:
                cur_scale = "linear"
                lims = (0, 1)
                inverted = False
        else:
            pri_key = "bottom" if is_x else "left"
            sec_key = "top" if is_x else "right"
            mpl_axis = ax.xaxis if is_x else ax.yaxis
            cur_scale = ax.get_xscale() if is_x else ax.get_yscale()
            lims = ax.get_xlim() if is_x else ax.get_ylim()
            inverted = (ax.xaxis_inverted() if is_x
                        else ax.yaxis_inverted())

        # ── Scale ──────────────────────────────────────────────────
        self.scale_combo.setCurrentText(cur_scale)
        self._setup_slider_range(lims[0], lims[1])
        self.limit_auto.setChecked(True)
        self.limit_min.blockSignals(True)
        self.limit_max.blockSignals(True)
        self.limit_min.setValue(lims[0])
        self.limit_max.setValue(lims[1])
        self._min_slider.blockSignals(True)
        self._max_slider.blockSignals(True)
        self._min_slider.setValue(self._val_to_slider(lims[0]))
        self._max_slider.setValue(self._val_to_slider(lims[1]))
        self._min_slider.blockSignals(False)
        self._max_slider.blockSignals(False)
        self.limit_min.blockSignals(False)
        self.limit_max.blockSignals(False)
        self._on_auto_limits(True)
        self.invert_check.setChecked(bool(inverted))

        # ── Primary title (Bottom / Left) ──────────────────────────
        if is_x:
            label_text = ax.get_xlabel()
        else:
            label_text = ax.get_ylabel()
        self.title_show.setChecked(bool(label_text))
        self.title_text.setText(label_text)

        label_art = mpl_axis.label
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
        fam = fp.get_name()
        idx = self.title_font.findText(fam)
        self.title_font.setCurrentIndex(max(0, idx))

        # ── Tick labels (primary side visibility) ──────────────────
        tl_vis = True
        major_ticks = mpl_axis.get_major_ticks()
        if major_ticks:
            tl_vis = major_ticks[0].label1.get_visible()
        self.tl_show.setChecked(tl_vis)
        self.tl_format.setCurrentIndex(0)
        self.tl_decimals.setValue(2)
        self.tl_prefix.setText("")
        self.tl_suffix.setText("")
        try:
            from matplotlib.colors import to_hex
            if major_ticks:
                lbl = major_ticks[0].label1
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

        # ── Primary spine ──────────────────────────────────────────
        spine = ax.spines[pri_key]
        self.spine_show.setChecked(spine.get_visible())
        self.spine_color.set_color("#000000")
        self.spine_width.setValue(1.0)

        # ── Major ticks ────────────────────────────────────────────
        self.major_show.setChecked(True)
        if major_ticks:
            tk = major_ticks[0]
            vis = (tk.tick1line.get_visible()
                   if hasattr(tk, 'tick1line') else True)
            self.major_show.setChecked(vis)
        self.major_direction.setCurrentIndex(0)
        try:
            tp = mpl_axis.get_tick_params()
        except Exception:
            tp = {}
        direction_str = tp.get('tickdir', 'out')
        for i, (_, code) in enumerate(_TICK_DIRECTIONS):
            if code == direction_str:
                self.major_direction.setCurrentIndex(i)
                break
        self.major_length.setValue(
            float(tp.get('major_tick_length',
                         tp.get('length', 3.5))))
        self.major_width.setValue(1.0)
        self.major_color.set_color("#000000")
        n_major = len(mpl_axis.get_majorticklocs())
        self.major_count.setValue(max(2, n_major))

        # ── Minor ticks ────────────────────────────────────────────
        loc = mpl_axis.get_minor_locator()
        minor_on = not isinstance(loc, mticker.NullLocator)
        self.minor_show.setChecked(minor_on)
        self.minor_direction.setCurrentIndex(
            self.major_direction.currentIndex())
        self.minor_length.setValue(2.0)
        self.minor_width.setValue(1.0)
        self.minor_color.set_color("#000000")
        self.minor_count.setValue(5)

        # ── Grids ──────────────────────────────────────────────────
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

        # ── Secondary side (Top / Right) ───────────────────────────
        sec_spine = ax.spines[sec_key]
        self.sec_spine_show.setChecked(sec_spine.get_visible())
        self.sec_spine_color.set_color("#000000")
        self.sec_spine_width.setValue(1.0)
        self.sec_spine_style.setCurrentIndex(0)

        # Secondary tick / label visibility.
        sec_tick_vis = False
        sec_label_vis = False
        if major_ticks:
            tk = major_ticks[0]
            sec_tick_vis = (tk.tick2line.get_visible()
                           if hasattr(tk, 'tick2line') else False)
            sec_label_vis = tk.label2.get_visible()
        self.sec_tick_show.setChecked(sec_tick_vis)
        self.sec_label_show.setChecked(sec_label_vis)

        # Secondary title.
        if is_x:
            sec_text = getattr(self._chart, '_top_label_text', '')
        else:
            sec_text = getattr(self._chart, '_right_label_text', '')
        self.sec_title_show.setChecked(bool(sec_text))
        self.sec_title_text.setText(sec_text)
        self.sec_title_color.set_color("#000000")
        self.sec_title_font.setCurrentIndex(0)
        self.sec_title_size.setValue(10)
        self.sec_title_bold.setChecked(False)
        self.sec_title_italic.setChecked(False)
        self.sec_title_rotation.setCurrentText("0")
        attr = '_top_label_offset' if is_x else '_right_label_offset'
        self.sec_title_offset.setValue(
            getattr(self._chart, attr, 0.08))

    # ── Apply ──────────────────────────────────────────────────────

    # Custom result codes for dialog switching.
    SWITCH_TO_PLOT_DETAILS = 3
    SWITCH_TO_GENERAL = 4

    def _switch_to_plot_details(self):
        """Apply settings, close, and signal to open Series Properties."""
        self.apply_to_chart(self._chart)
        self.done(self.SWITCH_TO_PLOT_DETAILS)

    def _switch_to_general(self):
        """Apply settings, close, and signal to open General Properties."""
        self.apply_to_chart(self._chart)
        self.done(self.SWITCH_TO_GENERAL)

    def _apply_current(self):
        """Apply current direction to the chart without closing."""
        self._dir_states[self._current_dir] = \
            self._capture_widgets()
        self._apply_dir(self._current_dir)
        self._chart._axis_props = dict(self._dir_states)

    def apply_to_chart(self, chart):
        """Apply all modified directions to the chart (called on OK)."""
        self._dir_states[self._current_dir] = \
            self._capture_widgets()
        for d, st in self._dir_states.items():
            self._apply_dir(d, st)
        # Persist axis properties on chart for save/load.
        chart._axis_props = dict(self._dir_states)

    def _apply_dir(self, direction, st=None):
        """Apply one direction's state (primary + secondary) to axes."""
        if st is None:
            st = self._dir_states.get(direction)
        if st is None:
            return
        ax = self._ax
        is_x = (direction == "x")
        is_z = (direction == "z")

        if is_z:
            # 3-D z-axis — only apply if axes supports it.
            self._apply_dir_z(ax, st)
            return

        pri_key = "bottom" if is_x else "left"
        sec_key = "top" if is_x else "right"
        mpl_axis = ax.xaxis if is_x else ax.yaxis
        ax_str = 'x' if is_x else 'y'

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

        currently_inverted = (ax.xaxis_inverted() if is_x
                              else ax.yaxis_inverted())
        if st["invert"] != currently_inverted:
            if is_x:
                ax.invert_xaxis()
            else:
                ax.invert_yaxis()

        # ── Primary title ──────────────────────────────────────────
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

        if is_x:
            ax.set_xlabel(text, **title_kw)
        else:
            ax.set_ylabel(text, **title_kw)

        # ── Primary spine ──────────────────────────────────────────
        spine = ax.spines[pri_key]
        spine.set_visible(st["spine_show"])
        spine.set_edgecolor(st["spine_color"])
        spine.set_linewidth(st["spine_width"])

        # ── Tick labels (primary side) ─────────────────────────────
        ax.tick_params(
            axis=ax_str, which='both',
            **{pri_key: st["tl_show"],
               f"label{pri_key}": st["tl_show"]})

        if st["tl_show"]:
            ax.tick_params(
                axis=ax_str, which='major',
                labelcolor=st["tl_color"],
                labelsize=st["tl_size"],
                labelrotation=st["tl_rotation"],
            )
            fmt_idx = st["tl_format"]
            if fmt_idx >= len(_TICK_FORMATS):
                fmt_idx = 0
            fmt_code = _TICK_FORMATS[fmt_idx][1]
            self._apply_tick_format(
                mpl_axis, fmt_code, st["tl_decimals"],
                st["tl_prefix"], st["tl_suffix"])

        # ── Major ticks ────────────────────────────────────────────
        tick_dir = _TICK_DIRECTIONS[st["major_dir"]][1]
        if st["major_show"]:
            mpl_axis.set_major_locator(
                mticker.MaxNLocator(nbins=st["major_count"]))
            ax.tick_params(
                axis=ax_str, which='major',
                direction=tick_dir,
                length=st["major_length"],
                width=st["major_width"],
                color=st["major_color"],
                **{pri_key: True},
            )
        else:
            ax.tick_params(
                axis=ax_str, which='major',
                **{pri_key: False},
            )

        # ── Minor ticks ────────────────────────────────────────────
        minor_dir = _TICK_DIRECTIONS[st["minor_dir"]][1]
        if st["minor_show"]:
            mpl_axis.set_minor_locator(
                mticker.AutoMinorLocator(st["minor_count"]))
            ax.tick_params(
                axis=ax_str, which='minor',
                direction=minor_dir,
                length=st["minor_length"],
                width=st["minor_width"],
                color=st["minor_color"],
                **{pri_key: True},
            )
        else:
            ax.tick_params(
                axis=ax_str, which='minor',
                **{pri_key: False},
            )

        # ── Grids ──────────────────────────────────────────────────
        for gl in mpl_axis.get_gridlines():
            gl.set_visible(st["grid_major_show"])
        if st["grid_major_show"]:
            major_ls = _LINE_STYLES[st["grid_major_style"]][1]
            ax.grid(True, axis=ax_str, which='major',
                    color=st["grid_major_color"],
                    alpha=st["grid_major_alpha"],
                    linestyle=major_ls,
                    linewidth=st["grid_major_width"])
        else:
            ax.grid(False, axis=ax_str, which='major')

        if st["minor_show"] and st["grid_minor_show"]:
            minor_ls = _LINE_STYLES[st["grid_minor_style"]][1]
            ax.grid(True, axis=ax_str, which='minor',
                    color=st["grid_minor_color"],
                    alpha=st["grid_minor_alpha"],
                    linestyle=minor_ls,
                    linewidth=st["grid_minor_width"])
        else:
            ax.grid(False, axis=ax_str, which='minor')

        # ── Secondary spine ────────────────────────────────────────
        sec_spine = ax.spines[sec_key]
        sec_spine.set_visible(st["sec_spine_show"])
        sec_spine.set_edgecolor(st["sec_spine_color"])
        sec_spine.set_linewidth(st["sec_spine_width"])
        sec_ls = _LINE_STYLES[st["sec_spine_style"]][1]
        sec_spine.set_linestyle(sec_ls)

        # ── Secondary ticks & labels ──────────────────────────────
        ax.tick_params(
            axis=ax_str, which='both',
            **{sec_key: st["sec_tick_show"],
               f"label{sec_key}": st["sec_label_show"]})

        # ── Secondary title ────────────────────────────────────────
        sec_text = (st["sec_title_text"]
                    if st["sec_title_show"] else "")
        sec_weight = "bold" if st["sec_title_bold"] else "normal"
        sec_style = "italic" if st["sec_title_italic"] else "normal"
        sec_font = st["sec_title_font"]
        if sec_font == "Default":
            sec_font = "sans-serif"
        try:
            sec_rot = int(st["sec_title_rotation"])
        except (ValueError, TypeError):
            sec_rot = 0

        sec_offset = st.get("sec_title_offset", 0.08)
        sec_title_kw = dict(
            fontsize=st["sec_title_size"],
            color=st["sec_title_color"],
            fontweight=sec_weight,
            fontstyle=sec_style,
            fontfamily=sec_font,
            rotation=sec_rot,
        )
        loc = "top" if is_x else "right"
        if is_x:
            self._chart._top_label_text = sec_text
            self._chart._top_label_offset = sec_offset
        else:
            self._chart._right_label_text = sec_text
            self._chart._right_label_offset = sec_offset
        self._set_secondary_label(
            self._chart, loc, sec_text, sec_title_kw, sec_offset)

        self._chart._canvas.draw_idle()

    def _apply_dir_z(self, ax, st):
        """Apply Z-axis state on a 3-D axes."""
        if not hasattr(ax, 'set_zlabel'):
            return  # not a 3-D axes

        # Scale (matplotlib 3D only supports linear)
        try:
            if hasattr(ax, 'set_zscale'):
                ax.set_zscale(st.get("scale", "linear"))
        except Exception:
            pass

        # Limits
        if not st.get("limit_auto", True):
            ax.set_zlim(st["limit_min"], st["limit_max"])

        # Title
        text = st.get("title_text", "") if st.get(
            "title_show", True) else ""
        weight = "bold" if st.get("title_bold") else "normal"
        style = "italic" if st.get("title_italic") else "normal"
        font_family = st.get("title_font", "Default")
        if font_family == "Default":
            font_family = "sans-serif"
        try:
            rotation = int(st.get("title_rotation", 0))
        except (ValueError, TypeError):
            rotation = 0
        ax.set_zlabel(text,
                      fontsize=st.get("title_size", 10),
                      color=st.get("title_color", "black"),
                      fontweight=weight, fontstyle=style,
                      fontfamily=font_family, rotation=rotation)

        # Tick labels
        if hasattr(ax, 'zaxis'):
            ax.zaxis.set_tick_params(
                labelsize=st.get("tl_size", 10),
                labelcolor=st.get("tl_color", "black"),
                labelrotation=st.get("tl_rotation", 0))
            if not st.get("tl_show", True):
                ax.zaxis.set_ticklabels([])

        # Grid
        if hasattr(ax, 'zaxis'):
            ax.zaxis.grid(st.get("grid_major_show", True))

        self._chart._canvas.draw_idle()

    # ── Static re-apply (for restoring saved state) ───────────────

    @classmethod
    def _apply_dir_static(cls, chart, direction, st):
        """Apply saved axis state *st* to *chart* without a dialog."""
        if direction == "z":
            # 3-D z-axis — limited static apply.
            ax = chart._ax
            if hasattr(ax, 'set_zlabel'):
                text = st.get("title_text", "") if st.get(
                    "title_show", True) else ""
                ax.set_zlabel(text,
                              fontsize=st.get("title_size", 10))
                if not st.get("limit_auto", True):
                    ax.set_zlim(st["limit_min"], st["limit_max"])
            return
        ax = chart._ax
        is_x = (direction == "x")
        pri_key = "bottom" if is_x else "left"
        sec_key = "top" if is_x else "right"
        mpl_axis = ax.xaxis if is_x else ax.yaxis
        ax_str = 'x' if is_x else 'y'

        # Scale.
        try:
            if is_x:
                ax.set_xscale(st["scale"])
            else:
                ax.set_yscale(st["scale"])
        except ValueError:
            pass

        if not st.get("limit_auto", True):
            if is_x:
                ax.set_xlim(st["limit_min"], st["limit_max"])
            else:
                ax.set_ylim(st["limit_min"], st["limit_max"])

        currently_inverted = (ax.xaxis_inverted() if is_x
                              else ax.yaxis_inverted())
        if st.get("invert", False) != currently_inverted:
            if is_x:
                ax.invert_xaxis()
            else:
                ax.invert_yaxis()

        # Primary title.
        text = st.get("title_text", "") if st.get("title_show", True) else ""
        weight = "bold" if st.get("title_bold") else "normal"
        style = "italic" if st.get("title_italic") else "normal"
        font_family = st.get("title_font", "Default")
        if font_family == "Default":
            font_family = "sans-serif"
        try:
            rotation = int(st.get("title_rotation", 0))
        except (ValueError, TypeError):
            rotation = 0

        title_kw = dict(
            fontsize=st.get("title_size", 10),
            color=st.get("title_color", "#000000"),
            fontweight=weight, fontstyle=style,
            fontfamily=font_family, rotation=rotation,
        )
        if is_x:
            ax.set_xlabel(text, **title_kw)
        else:
            ax.set_ylabel(text, **title_kw)

        # Primary spine.
        spine = ax.spines[pri_key]
        spine.set_visible(st.get("spine_show", True))
        spine.set_edgecolor(st.get("spine_color", "#000000"))
        spine.set_linewidth(st.get("spine_width", 1.0))

        # Tick labels.
        ax.tick_params(
            axis=ax_str, which='both',
            **{pri_key: st.get("tl_show", True),
               f"label{pri_key}": st.get("tl_show", True)})
        if st.get("tl_show", True):
            ax.tick_params(
                axis=ax_str, which='major',
                labelcolor=st.get("tl_color", "#000000"),
                labelsize=st.get("tl_size", 10),
                labelrotation=st.get("tl_rotation", 0),
            )
            fmt_idx = st.get("tl_format", 0)
            if fmt_idx >= len(_TICK_FORMATS):
                fmt_idx = 0
            fmt_code = _TICK_FORMATS[fmt_idx][1]
            cls._apply_tick_format(
                mpl_axis, fmt_code, st.get("tl_decimals", 2),
                st.get("tl_prefix", ""), st.get("tl_suffix", ""))

        # Major ticks.
        tick_dir = _TICK_DIRECTIONS[st.get("major_dir", 0)][1]
        if st.get("major_show", True):
            mpl_axis.set_major_locator(
                mticker.MaxNLocator(nbins=st.get("major_count", 6)))
            ax.tick_params(
                axis=ax_str, which='major',
                direction=tick_dir,
                length=st.get("major_length", 3.5),
                width=st.get("major_width", 1.0),
                color=st.get("major_color", "#000000"),
                **{pri_key: True},
            )
        else:
            ax.tick_params(
                axis=ax_str, which='major', **{pri_key: False})

        # Minor ticks.
        minor_dir = _TICK_DIRECTIONS[st.get("minor_dir", 0)][1]
        if st.get("minor_show", False):
            mpl_axis.set_minor_locator(
                mticker.AutoMinorLocator(st.get("minor_count", 5)))
            ax.tick_params(
                axis=ax_str, which='minor',
                direction=minor_dir,
                length=st.get("minor_length", 2.0),
                width=st.get("minor_width", 1.0),
                color=st.get("minor_color", "#000000"),
                **{pri_key: True},
            )
        else:
            ax.tick_params(
                axis=ax_str, which='minor', **{pri_key: False})

        # Grids.
        for gl in mpl_axis.get_gridlines():
            gl.set_visible(st.get("grid_major_show", False))
        if st.get("grid_major_show", False):
            major_ls = _LINE_STYLES[st.get("grid_major_style", 0)][1]
            ax.grid(True, axis=ax_str, which='major',
                    color=st.get("grid_major_color", "#cccccc"),
                    alpha=st.get("grid_major_alpha", 0.7),
                    linestyle=major_ls,
                    linewidth=st.get("grid_major_width", 0.8))
        else:
            ax.grid(False, axis=ax_str, which='major')

        if st.get("minor_show", False) and st.get("grid_minor_show", False):
            minor_ls = _LINE_STYLES[st.get("grid_minor_style", 2)][1]
            ax.grid(True, axis=ax_str, which='minor',
                    color=st.get("grid_minor_color", "#e0e0e0"),
                    alpha=st.get("grid_minor_alpha", 0.4),
                    linestyle=minor_ls,
                    linewidth=st.get("grid_minor_width", 0.5))
        else:
            ax.grid(False, axis=ax_str, which='minor')

        # Secondary spine.
        sec_spine = ax.spines[sec_key]
        sec_spine.set_visible(st.get("sec_spine_show", False))
        sec_spine.set_edgecolor(st.get("sec_spine_color", "#000000"))
        sec_spine.set_linewidth(st.get("sec_spine_width", 1.0))
        sec_ls = _LINE_STYLES[st.get("sec_spine_style", 0)][1]
        sec_spine.set_linestyle(sec_ls)

        # Secondary ticks & labels.
        ax.tick_params(
            axis=ax_str, which='both',
            **{sec_key: st.get("sec_tick_show", False),
               f"label{sec_key}": st.get("sec_label_show", False)})

        # Secondary title.
        sec_text = (st.get("sec_title_text", "")
                    if st.get("sec_title_show", False) else "")
        sec_weight = "bold" if st.get("sec_title_bold") else "normal"
        sec_style = "italic" if st.get("sec_title_italic") else "normal"
        sec_font = st.get("sec_title_font", "Default")
        if sec_font == "Default":
            sec_font = "sans-serif"
        try:
            sec_rot = int(st.get("sec_title_rotation", "0"))
        except (ValueError, TypeError):
            sec_rot = 0

        sec_title_kw = dict(
            fontsize=st.get("sec_title_size", 10),
            color=st.get("sec_title_color", "#000000"),
            fontweight=sec_weight, fontstyle=sec_style,
            fontfamily=sec_font, rotation=sec_rot,
        )
        sec_offset = st.get("sec_title_offset", 0.08)
        loc = "top" if is_x else "right"
        if is_x:
            chart._top_label_text = sec_text
            chart._top_label_offset = sec_offset
        else:
            chart._right_label_text = sec_text
            chart._right_label_offset = sec_offset
        cls._set_secondary_label(chart, loc, sec_text, sec_title_kw,
                                 sec_offset)

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _apply_tick_format(mpl_axis, fmt_code, decimals,
                           prefix, suffix):
        """Apply a tick label formatter to *mpl_axis*."""
        if fmt_code == "auto":
            mpl_axis.set_major_formatter(
                mticker.ScalarFormatter())
        elif fmt_code == "decimal":
            mpl_axis.set_major_formatter(
                mticker.FuncFormatter(
                    lambda v, _: f"{prefix}{v:,.{decimals}f}"
                    f"{suffix}"))
        elif fmt_code == "scientific":
            mpl_axis.set_major_formatter(
                mticker.FuncFormatter(
                    lambda v, _: f"{prefix}{v:.{decimals}e}"
                    f"{suffix}"))
        elif fmt_code == "std_scientific":
            fmt = mticker.ScalarFormatter(useMathText=True)
            fmt.set_powerlimits((0, 0))
            mpl_axis.set_major_formatter(fmt)
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
    def _set_secondary_label(chart, location, text, title_kw,
                             offset=0.08):
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
                0.5, 1.0 + offset, text, transform=ax.transAxes,
                ha='center', va='bottom', clip_on=False, **title_kw)
        else:  # right
            art = ax.text(
                1.0 + offset, 0.5, text, transform=ax.transAxes,
                ha='left', va='center', clip_on=False,
                rotation=270 if title_kw.get('rotation', 0) == 0
                else title_kw['rotation'],
                fontsize=title_kw.get('fontsize', 10),
                color=title_kw.get('color', '#000000'),
                fontweight=title_kw.get('fontweight', 'normal'),
                fontstyle=title_kw.get('fontstyle', 'normal'),
                fontfamily=title_kw.get('fontfamily', 'sans-serif'),
            )
        setattr(chart, attr, art)
