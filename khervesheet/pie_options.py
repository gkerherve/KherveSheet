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

DEFAULT_PIE_CONFIG = {
    "start_angle": 90,
    "direction": "counter-clockwise",
    "explode_pct": 0.0,
    "label_mode": "label+percent",  # percent | value | label | label+percent | none
    "decimal_places": 1,
    "shadow": False,
    "doughnut_width": 0.4,       # only used for Doughnut type
    "labels": None,              # list[str] | None — slice labels
}

PIE_TYPES = {"Pie", "Doughnut", "3D Pie"}

_LABEL_MODES = ["Percent", "Value", "Label", "Label + Percent", "None"]
_LABEL_MODE_KEYS = ["percent", "value", "label", "label+percent", "none"]

_DEFAULT_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
]


# ── Drawing ─────────────────────────────────────────────────────────

def plot_pie(ax, values, labels, pie_config, plot_type="Pie",
             colors=None):
    """Draw a pie / doughnut / 3-D pie on *ax*.

    Parameters
    ----------
    ax : matplotlib Axes
    values : array-like  — slice sizes (will be abs'd, zeros removed)
    labels : list[str] | None — per-slice labels
    pie_config : dict
    plot_type : str — "Pie", "Doughnut", or "3D Pie"
    colors : list[str] | None

    Returns
    -------
    (wedges, texts, autotexts) — the three lists returned by ax.pie
    """
    ax.clear()

    vals = np.asarray(values, dtype=float)
    # Remove zero / nan slices.
    mask = (vals > 0) & ~np.isnan(vals)
    vals = vals[mask]
    n = len(vals)
    if n == 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                transform=ax.transAxes, fontsize=10)
        return None

    if labels is not None:
        labels = [labels[i] for i, m in enumerate(mask) if m]
    else:
        labels = [f"Slice {i+1}" for i in range(n)]
    # Truncate / pad labels to match values.
    while len(labels) < n:
        labels.append(f"Slice {len(labels)+1}")
    labels = labels[:n]

    if colors is None:
        colors = [_DEFAULT_COLORS[i % len(_DEFAULT_COLORS)]
                  for i in range(n)]
    else:
        while len(colors) < n:
            colors.append(_DEFAULT_COLORS[len(colors) % len(_DEFAULT_COLORS)])
        colors = colors[:n]

    cfg = dict(DEFAULT_PIE_CONFIG)
    cfg.update(pie_config or {})

    start = cfg["start_angle"]
    ccw = cfg["direction"] == "counter-clockwise"
    shadow = cfg["shadow"]
    explode_pct = cfg["explode_pct"]

    explode = [explode_pct] * n if explode_pct > 0 else None

    # Build autopct string.
    lm = cfg["label_mode"]
    dp = cfg["decimal_places"]
    fmt = f"%.{dp}f%%"

    show_labels = lm in ("label", "label+percent")
    show_pct = lm in ("percent", "label+percent")
    show_val = lm == "value"

    if show_pct:
        autopct = fmt
    elif show_val:
        # autopct receives the percentage; convert back to value.
        total = vals.sum()
        def autopct(pct, _t=total, _dp=dp):
            v = pct * _t / 100.0
            return f"{v:.{_dp}f}"
    else:
        autopct = None

    pie_labels = labels if show_labels else None

    kw = dict(
        labels=pie_labels,
        autopct=autopct,
        startangle=start,
        colors=colors,
        counterclock=ccw,
        shadow=shadow,
        explode=explode,
    )

    # Doughnut: ring shape.
    if plot_type == "Doughnut":
        w = cfg.get("doughnut_width", 0.4)
        kw["wedgeprops"] = dict(width=w, edgecolor="white", linewidth=1.5)
    else:
        kw["wedgeprops"] = dict(edgecolor="white", linewidth=1.0)

    # 3D Pie: fake depth via shadow + slight explode + squash.
    if plot_type == "3D Pie":
        kw["shadow"] = True
        if explode is None:
            kw["explode"] = [0.02] * n
        ax.set_aspect(0.7)  # squash vertically for 3-D illusion
    else:
        ax.set_aspect("equal")

    result = ax.pie(vals, **kw)

    # Hide axes frame.
    ax.set_frame_on(False)
    ax.set_xticks([])
    ax.set_yticks([])

    return result


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
