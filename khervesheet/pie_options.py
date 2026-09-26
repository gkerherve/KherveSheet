"""Pie / Doughnut chart options — drawing, config, and UI tab.

Provides the drawing logic for Pie, Doughnut, and 3-D Pie charts,
plus the "Pie" tab that plugs into PlotDetailsDialog.

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
    QDoubleSpinBox, QSpinBox, QCheckBox, QPushButton, QColorDialog,
)

# ── Defaults ────────────────────────────────────────────────────────

from .core.charts import (  # noqa: F401
    DEFAULT_COLORS as _DEFAULT_COLORS, DEFAULT_PIE_CONFIG, PIE_TYPES, plot_pie,
)

_LABEL_MODES = ["Percent", "Value", "Label", "Label + Percent", "None"]
_LABEL_MODE_KEYS = ["percent", "value", "label", "label+percent", "none"]


# ── Drawing ─────────────────────────────────────────────────────────

def redraw_pie(chart):
    """Redraw the pie chart on *chart* using its stored config."""
    if not chart._series:
        return
    s = chart._series[0]
    pt = s.get("plot_type", "Pie")
    if pt not in PIE_TYPES:
        return
    cfg = getattr(chart, "_pie_config", {})
    vals = np.asarray(s["y"])
    labels = cfg.get("labels")
    # Collect saved slice colours.
    colors = cfg.get("colors")
    result = plot_pie(chart._ax, vals, labels, cfg, pt, colors)
    if result is not None:
        wedges = result[0]
        s["artist"] = wedges  # store list of Wedge patches
        # Save back the actual colours used.
        cfg["colors"] = [w.get_facecolor() for w in wedges]
    chart._canvas.draw_idle()


# ── UI Tab ──────────────────────────────────────────────────────────

class PieOptionsTab(QWidget):
    """The 'Pie' tab for PlotDetailsDialog."""

    def __init__(self, chart, parent=None):
        super().__init__(parent)
        self._chart = chart
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        grp = QGroupBox("Pie Options")
        form = QFormLayout(grp)

        self.start_angle = QDoubleSpinBox()
        self.start_angle.setRange(0, 360)
        self.start_angle.setSingleStep(5)
        self.start_angle.setValue(90)
        form.addRow("Start Angle:", self.start_angle)

        self.direction = QComboBox()
        self.direction.addItems(["Counter-clockwise", "Clockwise"])
        form.addRow("Direction:", self.direction)

        self.explode = QDoubleSpinBox()
        self.explode.setRange(0.0, 0.3)
        self.explode.setSingleStep(0.02)
        self.explode.setValue(0.0)
        form.addRow("Explode:", self.explode)

        self.label_mode = QComboBox()
        self.label_mode.addItems(_LABEL_MODES)
        form.addRow("Labels:", self.label_mode)

        self.decimals = QSpinBox()
        self.decimals.setRange(0, 4)
        self.decimals.setValue(1)
        form.addRow("Decimal Places:", self.decimals)

        self.shadow_check = QCheckBox("Shadow")
        form.addRow(self.shadow_check)

        layout.addWidget(grp)

        # Doughnut-specific.
        grp2 = QGroupBox("Doughnut")
        df = QFormLayout(grp2)
        self.doughnut_width = QDoubleSpinBox()
        self.doughnut_width.setRange(0.1, 0.9)
        self.doughnut_width.setSingleStep(0.05)
        self.doughnut_width.setValue(0.4)
        df.addRow("Ring Width:", self.doughnut_width)
        layout.addWidget(grp2)

        layout.addStretch()

    def read_from_config(self, pie_config):
        """Populate widgets from pie config dict."""
        cfg = dict(DEFAULT_PIE_CONFIG)
        cfg.update(pie_config or {})
        self.start_angle.setValue(cfg["start_angle"])
        self.direction.setCurrentIndex(
            0 if cfg["direction"] == "counter-clockwise" else 1)
        self.explode.setValue(cfg["explode_pct"])
        idx = _LABEL_MODE_KEYS.index(cfg["label_mode"]) \
            if cfg["label_mode"] in _LABEL_MODE_KEYS else 0
        self.label_mode.setCurrentIndex(idx)
        self.decimals.setValue(cfg["decimal_places"])
        self.shadow_check.setChecked(cfg["shadow"])
        self.doughnut_width.setValue(cfg.get("doughnut_width", 0.4))

    def write_to_config(self):
        """Return a pie config dict from widget state."""
        return {
            "start_angle": self.start_angle.value(),
            "direction": ("counter-clockwise"
                          if self.direction.currentIndex() == 0
                          else "clockwise"),
            "explode_pct": self.explode.value(),
            "label_mode": _LABEL_MODE_KEYS[
                self.label_mode.currentIndex()],
            "decimal_places": self.decimals.value(),
            "shadow": self.shadow_check.isChecked(),
            "doughnut_width": self.doughnut_width.value(),
        }
