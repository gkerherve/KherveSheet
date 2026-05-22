"""Embedded chart — movable/resizable matplotlib plot.

Charts float as independent windows (QDialog) that can be moved and
resized. Double-click opens a properties dialog. Single-layer only.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import numpy as np

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QFormLayout, QDialogButtonBox,
    QWidget, QCheckBox, QDoubleSpinBox,
)

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure


# ── Plot defaults (matching KhervePlot) ──────────────────────────────
_DEFAULT_LINEWIDTH = 1.0
_DEFAULT_MARKERSIZE = 3.0


class EmbeddedChartDialog(QDialog):
    """A floating chart window with matplotlib canvas."""

    def __init__(self, x, y, label, plot_type, source_sheet=None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Chart — {label}")
        self.setMinimumSize(400, 300)
        self.resize(600, 400)
        self.setWindowFlags(
            Qt.Window | Qt.WindowMinMaxButtonsHint
            | Qt.WindowCloseButtonHint)

        self._source_sheet = source_sheet
        self._series = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # Matplotlib figure
        self._figure = Figure(figsize=(6, 4), dpi=100)
        self._canvas = FigureCanvas(self._figure)
        self._ax = self._figure.add_subplot(111)

        # Compact toolbar
        self._toolbar = NavigationToolbar(self._canvas, self)
        self._toolbar.setIconSize(QSize(18, 18))
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas, stretch=1)

        # Add the initial series
        self.add_series(x, y, label, plot_type)

        # Tight layout
        try:
            self._figure.set_layout_engine("tight")
        except Exception:
            try:
                self._figure.tight_layout()
            except Exception:
                pass

    def add_series(self, x, y, label, plot_type="Line"):
        """Plot a data series on the chart."""
        ax = self._ax
        artist = None

        if plot_type == "Line":
            lines = ax.plot(x, y, label=label,
                            linewidth=_DEFAULT_LINEWIDTH)
            artist = lines[0] if lines else None
        elif plot_type == "Scatter":
            artist = ax.scatter(x, y, label=label,
                                s=_DEFAULT_MARKERSIZE ** 2)
        elif plot_type == "Line+Symbol":
            lines = ax.plot(x, y, 'o-', label=label,
                            linewidth=_DEFAULT_LINEWIDTH,
                            markersize=_DEFAULT_MARKERSIZE)
            artist = lines[0] if lines else None
        elif plot_type == "Bar":
            bars = ax.bar(x, y, label=label)
            artist = bars

        self._series.append({
            "x": x, "y": y, "label": label,
            "plot_type": plot_type, "artist": artist,
        })

        ax.legend(loc="best", framealpha=0.8, fontsize=8)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        self._canvas.draw_idle()

    def mouseDoubleClickEvent(self, event):
        """Open chart properties on double-click."""
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
