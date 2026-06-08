"""Heatmap and 3-D Surface options tabs for the Series Properties dialog.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox, QComboBox,
    QDoubleSpinBox, QCheckBox, QLabel, QHBoxLayout,
)

import matplotlib.pyplot as plt


# ── Colour-map registry ──────────────────────────────────────────────
# Ordered by category for a user-friendly dropdown.

_SEQUENTIAL = [
    "viridis", "plasma", "inferno", "magma", "cividis",
    "Greys", "Purples", "Blues", "Greens", "Oranges", "Reds",
    "YlOrBr", "YlOrRd", "OrRd", "PuRd", "RdPu", "BuPu",
    "GnBu", "PuBu", "YlGnBu", "PuBuGn", "BuGn", "YlGn",
]
_DIVERGING = [
    "PiYG", "PRGn", "BrBG", "PuOr", "RdGy", "RdBu",
    "RdYlBu", "RdYlGn", "Spectral", "coolwarm", "bwr", "seismic",
]
_QUALITATIVE = [
    "Pastel1", "Pastel2", "Paired", "Accent",
    "Dark2", "Set1", "Set2", "Set3", "tab10", "tab20",
]
_MISC = [
    "flag", "prism", "ocean", "gist_earth", "terrain",
    "gist_stern", "gnuplot", "gnuplot2", "CMRmap",
    "cubehelix", "brg", "gist_rainbow", "rainbow", "jet",
    "turbo", "nipy_spectral", "gist_ncar",
    "hot", "afmhot", "gist_heat", "copper",
    "bone", "gray", "binary", "pink", "spring", "summer",
    "autumn", "winter", "cool", "Wistia",
]

ALL_CMAPS = _SEQUENTIAL + _DIVERGING + _QUALITATIVE + _MISC

# Interpolation methods available in matplotlib imshow.
_INTERP_METHODS = [
    "none", "nearest", "bilinear", "bicubic",
    "spline16", "spline36", "hanning", "hamming",
    "hermite", "kaiser", "quadric", "catrom",
    "gaussian", "bessel", "mitchell", "sinc", "lanczos",
]


# ── Default configs ──────────────────────────────────────────────────

DEFAULT_HEATMAP_CONFIG = {
    "cmap": "viridis",
    "interpolation": "nearest",
    "origin": "lower",
    "aspect": "auto",
    "alpha": 1.0,
    "vmin_auto": True,
    "vmin": 0.0,
    "vmax_auto": True,
    "vmax": 1.0,
    "colorbar": True,
    "annotate": False,
    "annot_fmt": ".2g",
}

DEFAULT_SURFACE3D_CONFIG = {
    "cmap": "viridis",
    "alpha": 0.9,
    "edgecolor": "none",
    "linewidth": 0.0,
    "rstride": 1,
    "cstride": 1,
    "antialiased": True,
    "colorbar": True,
}


# ── Heatmap options tab ─────────────────────────────────────────────

class HeatmapOptionsTab(QWidget):
    """The 'Heatmap' tab for PlotDetailsDialog."""

    def __init__(self, chart, parent=None):
        super().__init__(parent)
        self._chart = chart
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── Colour map ─────────────────────────────────────────────
        grp = QGroupBox("Colour Map")
        gf = QFormLayout(grp)

        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(ALL_CMAPS)
        self.cmap_combo.setCurrentText("viridis")
        gf.addRow("Colormap:", self.cmap_combo)

        self.cmap_reverse = QCheckBox("Reverse")
        gf.addRow("", self.cmap_reverse)

        layout.addWidget(grp)

        # ── Rendering ──────────────────────────────────────────────
        grp2 = QGroupBox("Rendering")
        rf = QFormLayout(grp2)

        self.interp_combo = QComboBox()
        self.interp_combo.addItems(_INTERP_METHODS)
        self.interp_combo.setCurrentText("nearest")
        rf.addRow("Interpolation:", self.interp_combo)

        self.origin_combo = QComboBox()
        self.origin_combo.addItems(["lower", "upper"])
        self.origin_combo.setCurrentText("lower")
        rf.addRow("Origin:", self.origin_combo)

        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(["auto", "equal"])
        self.aspect_combo.setCurrentText("auto")
        rf.addRow("Aspect:", self.aspect_combo)

        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setRange(0.0, 1.0)
        self.alpha_spin.setSingleStep(0.05)
        self.alpha_spin.setValue(1.0)
        rf.addRow("Opacity:", self.alpha_spin)

        layout.addWidget(grp2)

        # ── Value range ────────────────────────────────────────────
        grp3 = QGroupBox("Value Range")
        vf = QFormLayout(grp3)

        self.vmin_auto = QCheckBox("Auto min")
        self.vmin_auto.setChecked(True)
        self.vmin_spin = QDoubleSpinBox()
        self.vmin_spin.setRange(-1e12, 1e12)
        self.vmin_spin.setDecimals(4)
        self.vmin_spin.setEnabled(False)
        self.vmin_auto.toggled.connect(
            lambda on: self.vmin_spin.setEnabled(not on))
        row_min = QHBoxLayout()
        row_min.addWidget(self.vmin_auto)
        row_min.addWidget(self.vmin_spin)
        vf.addRow("Min:", row_min)

        self.vmax_auto = QCheckBox("Auto max")
        self.vmax_auto.setChecked(True)
        self.vmax_spin = QDoubleSpinBox()
        self.vmax_spin.setRange(-1e12, 1e12)
        self.vmax_spin.setDecimals(4)
        self.vmax_spin.setEnabled(False)
        self.vmax_auto.toggled.connect(
            lambda on: self.vmax_spin.setEnabled(not on))
        row_max = QHBoxLayout()
        row_max.addWidget(self.vmax_auto)
        row_max.addWidget(self.vmax_spin)
        vf.addRow("Max:", row_max)

        layout.addWidget(grp3)

        # ── Extras ─────────────────────────────────────────────────
        grp4 = QGroupBox("Extras")
        ef = QFormLayout(grp4)

        self.colorbar_check = QCheckBox("Show colour bar")
        self.colorbar_check.setChecked(True)
        ef.addRow(self.colorbar_check)

        self.annotate_check = QCheckBox("Annotate cells with values")
        self.annotate_check.setChecked(False)
        ef.addRow(self.annotate_check)

        self.annot_fmt_edit = QComboBox()
        self.annot_fmt_edit.setEditable(True)
        self.annot_fmt_edit.addItems([".2g", ".1f", ".2f", ".3f",
                                      ".0f", ".2e", "d"])
        self.annot_fmt_edit.setCurrentText(".2g")
        ef.addRow("Annotation fmt:", self.annot_fmt_edit)

        layout.addWidget(grp4)
        layout.addStretch()

    # ── Data binding ─────────────────────────────────────────────────

    def read_from_config(self, cfg: dict):
        """Populate widgets from a heatmap config dict."""
        if not cfg:
            cfg = DEFAULT_HEATMAP_CONFIG
        cmap = cfg.get("cmap", "viridis")
        rev = cmap.endswith("_r")
        base = cmap[:-2] if rev else cmap
        self.cmap_combo.setCurrentText(base)
        self.cmap_reverse.setChecked(rev)
        self.interp_combo.setCurrentText(
            cfg.get("interpolation", "nearest"))
        self.origin_combo.setCurrentText(cfg.get("origin", "lower"))
        self.aspect_combo.setCurrentText(cfg.get("aspect", "auto"))
        self.alpha_spin.setValue(cfg.get("alpha", 1.0))
        self.vmin_auto.setChecked(cfg.get("vmin_auto", True))
        self.vmin_spin.setValue(cfg.get("vmin", 0.0))
        self.vmax_auto.setChecked(cfg.get("vmax_auto", True))
        self.vmax_spin.setValue(cfg.get("vmax", 1.0))
        self.colorbar_check.setChecked(cfg.get("colorbar", True))
        self.annotate_check.setChecked(cfg.get("annotate", False))
        self.annot_fmt_edit.setCurrentText(cfg.get("annot_fmt", ".2g"))

    def write_to_config(self) -> dict:
        """Return config dict from current widget state."""
        cmap = self.cmap_combo.currentText()
        if self.cmap_reverse.isChecked():
            cmap += "_r"
        return {
            "cmap": cmap,
            "interpolation": self.interp_combo.currentText(),
            "origin": self.origin_combo.currentText(),
            "aspect": self.aspect_combo.currentText(),
            "alpha": self.alpha_spin.value(),
            "vmin_auto": self.vmin_auto.isChecked(),
            "vmin": self.vmin_spin.value(),
            "vmax_auto": self.vmax_auto.isChecked(),
            "vmax": self.vmax_spin.value(),
            "colorbar": self.colorbar_check.isChecked(),
            "annotate": self.annotate_check.isChecked(),
            "annot_fmt": self.annot_fmt_edit.currentText(),
        }


# ── 3-D Surface options tab ─────────────────────────────────────────

class Surface3DOptionsTab(QWidget):
    """The '3D Surface' tab for PlotDetailsDialog."""

    def __init__(self, chart, parent=None):
        super().__init__(parent)
        self._chart = chart
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── Colour map ─────────────────────────────────────────────
        grp = QGroupBox("Colour Map")
        gf = QFormLayout(grp)

        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(ALL_CMAPS)
        self.cmap_combo.setCurrentText("viridis")
        gf.addRow("Colormap:", self.cmap_combo)

        self.cmap_reverse = QCheckBox("Reverse")
        gf.addRow("", self.cmap_reverse)

        layout.addWidget(grp)

        # ── Surface rendering ──────────────────────────────────────
        grp2 = QGroupBox("Rendering")
        rf = QFormLayout(grp2)

        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setRange(0.0, 1.0)
        self.alpha_spin.setSingleStep(0.05)
        self.alpha_spin.setValue(0.9)
        rf.addRow("Opacity:", self.alpha_spin)

        self.edge_combo = QComboBox()
        self.edge_combo.addItems(["none", "black", "grey", "white"])
        self.edge_combo.setEditable(True)
        self.edge_combo.setCurrentText("none")
        rf.addRow("Edge colour:", self.edge_combo)

        self.linewidth_spin = QDoubleSpinBox()
        self.linewidth_spin.setRange(0.0, 5.0)
        self.linewidth_spin.setSingleStep(0.1)
        self.linewidth_spin.setValue(0.0)
        rf.addRow("Edge width:", self.linewidth_spin)

        self.rstride_spin = QDoubleSpinBox()
        self.rstride_spin.setRange(1, 50)
        self.rstride_spin.setDecimals(0)
        self.rstride_spin.setValue(1)
        rf.addRow("Row stride:", self.rstride_spin)

        self.cstride_spin = QDoubleSpinBox()
        self.cstride_spin.setRange(1, 50)
        self.cstride_spin.setDecimals(0)
        self.cstride_spin.setValue(1)
        rf.addRow("Col stride:", self.cstride_spin)

        self.antialias_check = QCheckBox("Antialiased")
        self.antialias_check.setChecked(True)
        rf.addRow(self.antialias_check)

        layout.addWidget(grp2)

        # ── Extras ─────────────────────────────────────────────────
        grp3 = QGroupBox("Extras")
        ef = QFormLayout(grp3)

        self.colorbar_check = QCheckBox("Show colour bar")
        self.colorbar_check.setChecked(True)
        ef.addRow(self.colorbar_check)

        layout.addWidget(grp3)
        layout.addStretch()

    # ── Data binding ─────────────────────────────────────────────────

    def read_from_config(self, cfg: dict):
        """Populate widgets from a surface config dict."""
        if not cfg:
            cfg = DEFAULT_SURFACE3D_CONFIG
        cmap = cfg.get("cmap", "viridis")
        rev = cmap.endswith("_r")
        base = cmap[:-2] if rev else cmap
        self.cmap_combo.setCurrentText(base)
        self.cmap_reverse.setChecked(rev)
        self.alpha_spin.setValue(cfg.get("alpha", 0.9))
        self.edge_combo.setCurrentText(cfg.get("edgecolor", "none"))
        self.linewidth_spin.setValue(cfg.get("linewidth", 0.0))
        self.rstride_spin.setValue(cfg.get("rstride", 1))
        self.cstride_spin.setValue(cfg.get("cstride", 1))
        self.antialias_check.setChecked(cfg.get("antialiased", True))
        self.colorbar_check.setChecked(cfg.get("colorbar", True))

    def write_to_config(self) -> dict:
        """Return config dict from current widget state."""
        cmap = self.cmap_combo.currentText()
        if self.cmap_reverse.isChecked():
            cmap += "_r"
        return {
            "cmap": cmap,
            "alpha": self.alpha_spin.value(),
            "edgecolor": self.edge_combo.currentText(),
            "linewidth": self.linewidth_spin.value(),
            "rstride": int(self.rstride_spin.value()),
            "cstride": int(self.cstride_spin.value()),
            "antialiased": self.antialias_check.isChecked(),
            "colorbar": self.colorbar_check.isChecked(),
        }


# ── Redraw helpers ───────────────────────────────────────────────────

def redraw_heatmap(chart, cfg: dict):
    """Clear and re-render a heatmap with the given config."""
    import numpy as np
    ax = chart._ax
    s = chart._series[0]
    data = np.atleast_2d(np.asarray(s["y"]))

    # Remove old artist
    old = s.get("artist")
    if old is not None:
        try:
            old.remove()
        except Exception:
            pass

    # Remove old colorbar if any
    _remove_colorbar(chart)
    # Remove old annotations
    _remove_annotations(chart)

    cmap = cfg.get("cmap", "viridis")
    kw = {
        "aspect": cfg.get("aspect", "auto"),
        "origin": cfg.get("origin", "lower"),
        "cmap": cmap,
        "interpolation": cfg.get("interpolation", "nearest"),
        "alpha": cfg.get("alpha", 1.0),
    }
    if not cfg.get("vmin_auto", True):
        kw["vmin"] = cfg.get("vmin", None)
    if not cfg.get("vmax_auto", True):
        kw["vmax"] = cfg.get("vmax", None)

    im = ax.imshow(data, **kw)
    s["artist"] = im

    # Colorbar
    if cfg.get("colorbar", True):
        chart._heatmap_cbar = chart._figure.colorbar(im, ax=ax)

    try:
        chart._figure.tight_layout()
    except Exception:
        pass

    # Annotations
    if cfg.get("annotate", False):
        fmt = cfg.get("annot_fmt", ".2g")
        rows, cols = data.shape
        texts = []
        for i in range(rows):
            for j in range(cols):
                txt = ax.text(j, i, format(data[i, j], fmt),
                              ha="center", va="center",
                              fontsize=7, color="white")
                texts.append(txt)
        chart._heatmap_annot_texts = texts

    chart._canvas.draw_idle()


def redraw_surface(chart, cfg: dict):
    """Clear and re-render a 3-D surface with the given config."""
    import numpy as np
    ax = chart._ax
    s = chart._series[0]
    data = np.atleast_2d(np.asarray(s["y"]))
    rows, cols = data.shape
    X = np.arange(cols)
    Y = np.arange(rows)
    X, Y = np.meshgrid(X, Y)

    # Remove old artist
    old = s.get("artist")
    if old is not None:
        try:
            old.remove()
        except Exception:
            pass

    # Remove old colorbar
    _remove_colorbar(chart)

    cmap = cfg.get("cmap", "viridis")
    surf = ax.plot_surface(
        X, Y, data,
        cmap=cmap,
        alpha=cfg.get("alpha", 0.9),
        edgecolor=cfg.get("edgecolor", "none"),
        linewidth=cfg.get("linewidth", 0.0),
        rstride=cfg.get("rstride", 1),
        cstride=cfg.get("cstride", 1),
        antialiased=cfg.get("antialiased", True),
    )
    s["artist"] = surf

    if cfg.get("colorbar", True):
        chart._heatmap_cbar = chart._figure.colorbar(surf, ax=ax,
                                                       shrink=0.6)

    try:
        chart._figure.tight_layout()
    except Exception:
        pass

    chart._canvas.draw_idle()


def _remove_colorbar(chart):
    """Remove existing colorbar if present."""
    cbar = getattr(chart, '_heatmap_cbar', None)
    if cbar is not None:
        try:
            cbar.remove()
        except Exception:
            pass
        chart._heatmap_cbar = None


def _remove_annotations(chart):
    """Remove heatmap cell annotations."""
    texts = getattr(chart, '_heatmap_annot_texts', None)
    if texts:
        for t in texts:
            try:
                t.remove()
            except Exception:
                pass
        chart._heatmap_annot_texts = None
