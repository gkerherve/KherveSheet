"""Annotation selection, property dialogs, and interaction helpers for
embedded charts — text labels, arrows, and line segments.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QComboBox, QDoubleSpinBox, QCheckBox, QPushButton,
    QDialogButtonBox, QGroupBox, QColorDialog, QSpinBox, QTabWidget,
    QWidget, QListWidget, QSplitter, QScrollArea,
)

import matplotlib.patches as mpatches
import numpy as np

# ── Constants ─────────────────────────────────────────────────────────

_LINE_STYLES = [
    ("Solid", "-"),
    ("Dashed", "--"),
    ("Dash-dot", "-."),
    ("Dotted", ":"),
]

_ARROW_STYLES = [
    ("Arrow  ->", "->"),
    ("Filled arrow  -|>", "-|>"),
    ("Double arrow  <->", "<->"),
    ("Fancy", "fancy"),
    ("Simple", "simple"),
    ("Wedge", "wedge"),
]

_BOX_STYLES = [
    ("Round", "round,pad=0.3"),
    ("Round tight", "round,pad=0.15"),
    ("Square", "square,pad=0.3"),
    ("Round tooth", "roundtooth,pad=0.3"),
    ("Saw tooth", "sawtooth,pad=0.3"),
    ("None", ""),
]

_SELECT_COLOR = "#1a73e8"       # blue highlight
_HANDLE_RADIUS_PX = 7           # endpoint circle radius in pixels


# ── Selection visuals ─────────────────────────────────────────────────

def draw_text_selection(ann, ax, canvas):
    """Draw a dashed blue rectangle around a text annotation.

    The rectangle is drawn in **display (pixel) coordinates** so it
    matches the text tightly regardless of axis scale ratios.

    Returns a list of matplotlib artists to remove on deselect.
    """
    renderer = canvas.get_renderer()
    try:
        bbox = ann.get_window_extent(renderer)
    except Exception:
        return []
    pad = 4  # pixels
    rect = mpatches.FancyBboxPatch(
        (bbox.x0 - pad, bbox.y0 - pad),
        bbox.width + 2 * pad, bbox.height + 2 * pad,
        boxstyle="round,pad=2",
        linewidth=1.5, edgecolor=_SELECT_COLOR,
        facecolor="none", linestyle="--",
        zorder=999,
        transform=None,          # None = raw display coords
        clip_on=False)
    ax.add_patch(rect)
    return [rect]


def draw_endpoint_handles(ann, ax, canvas):
    """Draw filled circles at the two endpoints of a line/arrow annotation.

    Circles are drawn via a **pixel-offset transform** anchored to each
    data-coordinate point, so they always appear round on screen.

    Returns (artists, handle_data) where handle_data is a list of
    dicts with ``artist`` and ``role`` ('xy' or 'xytext') for
    hit-testing and dragging.
    """
    artists = []
    handles = []
    r = _HANDLE_RADIUS_PX           # radius in display pixels

    for role in ("xy", "xytext"):
        pt = tuple(ann.xy if role == "xy" else ann.get_position())
        # Draw in display (pixel) coords so circles are always round.
        disp = ax.transData.transform(pt)
        circ = mpatches.Circle(
            disp, radius=r, linewidth=2,
            edgecolor=_SELECT_COLOR, facecolor=_SELECT_COLOR,
            alpha=0.65, zorder=999,
            transform=None,       # raw display coords
            clip_on=False)
        ax.add_patch(circ)
        artists.append(circ)
        handles.append({"artist": circ, "role": role})
    return artists, handles


def clear_selection_artists(artists, canvas):
    """Remove selection-visual artists from the axes and redraw."""
    for a in artists:
        try:
            a.remove()
        except Exception:
            pass


# ── Hit-testing helpers ───────────────────────────────────────────────

_HIT_TOL_PX = 8   # pixel tolerance for clicking near a line / point


def _point_to_px(pt, ax):
    """Convert a data-coordinate (x, y) tuple to display pixels."""
    return ax.transData.transform(pt)


def _dist_point_to_segment_px(px, py, ax, pt_a, pt_b):
    """Pixel distance from (px, py) to segment pt_a→pt_b (data coords)."""
    a = _point_to_px(pt_a, ax)
    b = _point_to_px(pt_b, ax)
    ab = b - a
    ap = np.array([px, py]) - a
    t = np.dot(ap, ab) / max(np.dot(ab, ab), 1e-12)
    t = np.clip(t, 0, 1)
    closest = a + t * ab
    return np.linalg.norm(np.array([px, py]) - closest)


def _dist_point_px(px, py, ax, pt):
    """Pixel distance from (px, py) to a data-coordinate point."""
    s = _point_to_px(pt, ax)
    return np.hypot(px - s[0], py - s[1])


def _hit_text(event, artist, ax, canvas):
    """Check if *event* hits a text annotation's bounding box."""
    try:
        renderer = canvas.get_renderer()
        bbox = artist.get_window_extent(renderer)
        return bbox.contains(event.x, event.y)
    except Exception:
        return False


def _hit_line_or_arrow(event, artist, ax):
    """Check if *event* is within tolerance of a line/arrow segment."""
    try:
        xy = np.asarray(artist.xy, dtype=float)
        xytext = np.asarray(artist.get_position(), dtype=float)
        return _dist_point_to_segment_px(
            event.x, event.y, ax, xy, xytext) <= _HIT_TOL_PX
    except Exception:
        return False


def hit_test_annotations(event, annotations, ax, canvas):
    """Return the index of the annotation under *event*, or -1.

    *event* is a matplotlib ``MouseEvent`` (real or fake with .x, .y,
    .xdata, .ydata, .inaxes).
    """
    if event.inaxes is not ax:
        return -1
    # Walk backwards so the topmost annotation wins.
    for i in range(len(annotations) - 1, -1, -1):
        a = annotations[i]
        artist = a["artist"]
        atype = a["type"]
        if atype == "text":
            if _hit_text(event, artist, ax, canvas):
                return i
        elif atype in ("arrow", "line"):
            # Check text label first (arrows can have labels).
            if artist.get_text().strip():
                if _hit_text(event, artist, ax, canvas):
                    return i
            # Check the line/arrow segment itself.
            if _hit_line_or_arrow(event, artist, ax):
                return i
        else:
            # Legacy axhline/axvline — try matplotlib contains().
            try:
                hit, _ = artist.contains(event)
                if hit:
                    return i
            except Exception:
                pass
    return -1


def hit_test_handle(event, handles, ax):
    """Return the handle dict under *event*, or None."""
    if event.inaxes is not ax:
        return None
    for h in handles:
        try:
            # Handle circles are in display coords already.
            cx, cy = h["artist"].center
            d = np.hypot(event.x - cx, event.y - cy)
            if d <= _HANDLE_RADIUS_PX + 4:
                return h
        except Exception:
            pass
    return None


# ── Text Annotation Properties Dialog ─────────────────────────────────

class _ColorButton(QPushButton):
    """Small button that shows and lets the user pick a colour."""

    def __init__(self, color="#000000", parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(28, 22)
        self._update_swatch()
        self.clicked.connect(self._pick)

    def color(self):
        return self._color

    def setColor(self, c):
        self._color = QColor(c)
        self._update_swatch()

    def _update_swatch(self):
        self.setStyleSheet(
            f"background-color: {self._color.name()}; border: 1px solid #888;")

    def _pick(self):
        c = QColorDialog.getColor(self._color, self, "Pick colour")
        if c.isValid():
            self._color = c
            self._update_swatch()


class TextAnnotationEditor(QWidget):
    """Embeddable property controls for a text annotation."""

    def __init__(self, ann_dict, parent=None):
        super().__init__(parent)
        self._ann = ann_dict
        artist = ann_dict["artist"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()

        # Text
        self._text_edit = QLineEdit(artist.get_text())
        form.addRow("Text:", self._text_edit)

        # Font size
        self._size_spin = QSpinBox()
        self._size_spin.setRange(4, 72)
        self._size_spin.setValue(int(artist.get_fontsize()))
        form.addRow("Font size:", self._size_spin)

        # Bold
        self._bold_cb = QCheckBox()
        fw = artist.get_fontweight()
        self._bold_cb.setChecked(fw in ("bold", "heavy", "extra bold",
                                        "ultrabold", 700, 800, 900))
        form.addRow("Bold:", self._bold_cb)

        # Italic
        self._italic_cb = QCheckBox()
        fs = artist.get_fontstyle()
        self._italic_cb.setChecked(fs in ("italic", "oblique"))
        form.addRow("Italic:", self._italic_cb)

        # Text colour
        tc = artist.get_color()
        self._text_color = _ColorButton(tc)
        form.addRow("Text colour:", self._text_color)

        # Rotation
        self._rotation_spin = QDoubleSpinBox()
        self._rotation_spin.setRange(-360, 360)
        self._rotation_spin.setDecimals(1)
        self._rotation_spin.setValue(float(artist.get_rotation()))
        form.addRow("Rotation (°):", self._rotation_spin)

        layout.addLayout(form)

        # Background box
        box_group = QGroupBox("Background Box")
        bf = QFormLayout(box_group)

        self._box_style_combo = QComboBox()
        for label, _ in _BOX_STYLES:
            self._box_style_combo.addItem(label)
        # Detect current box style.
        cur_bbox = artist.get_bbox_patch()
        cur_bs_idx = 0
        if cur_bbox is None:
            cur_bs_idx = len(_BOX_STYLES) - 1  # "None"
        else:
            raw = cur_bbox.get_boxstyle()
            raw_str = str(raw).split("(")[0].lower() if raw else ""
            for j, (_, val) in enumerate(_BOX_STYLES):
                if val and val.split(",")[0] == raw_str:
                    cur_bs_idx = j
                    break
        self._box_style_combo.setCurrentIndex(cur_bs_idx)
        bf.addRow("Style:", self._box_style_combo)

        # Background colour
        bg = "#f5deb3"  # wheat default
        bg_alpha = 0.8
        if cur_bbox is not None:
            try:
                fc = cur_bbox.get_facecolor()
                from matplotlib.colors import to_hex
                bg = to_hex(fc[:3])
                bg_alpha = fc[3] if len(fc) > 3 else 1.0
            except Exception:
                pass
        self._bg_color = _ColorButton(bg)
        bf.addRow("Fill colour:", self._bg_color)

        self._bg_alpha = QDoubleSpinBox()
        self._bg_alpha.setRange(0.0, 1.0)
        self._bg_alpha.setSingleStep(0.1)
        self._bg_alpha.setDecimals(2)
        self._bg_alpha.setValue(bg_alpha)
        bf.addRow("Opacity:", self._bg_alpha)

        layout.addWidget(box_group)

        # Position
        pos_group = QGroupBox("Position")
        pf = QFormLayout(pos_group)
        xy = artist.xy
        self._pos_x = QDoubleSpinBox()
        self._pos_x.setRange(-1e12, 1e12)
        self._pos_x.setDecimals(6)
        self._pos_x.setValue(xy[0])
        pf.addRow("X:", self._pos_x)
        self._pos_y = QDoubleSpinBox()
        self._pos_y.setRange(-1e12, 1e12)
        self._pos_y.setDecimals(6)
        self._pos_y.setValue(xy[1])
        pf.addRow("Y:", self._pos_y)
        layout.addWidget(pos_group)
        layout.addStretch(1)

    def apply(self):
        """Apply properties to the annotation artist."""
        artist = self._ann["artist"]
        artist.set_text(self._text_edit.text())
        artist.set_fontsize(self._size_spin.value())
        artist.set_fontweight("bold" if self._bold_cb.isChecked() else "normal")
        artist.set_fontstyle("italic" if self._italic_cb.isChecked() else "normal")
        artist.set_color(self._text_color.color().name())
        artist.set_rotation(self._rotation_spin.value())

        # Position
        x = self._pos_x.value()
        y = self._pos_y.value()
        artist.xy = (x, y)
        artist.set_position((x, y))

        # Background box
        idx = self._box_style_combo.currentIndex()
        _, bs_val = _BOX_STYLES[idx]
        if not bs_val:
            artist.set_bbox(None)
        else:
            c = self._bg_color.color()
            alpha = self._bg_alpha.value()
            artist.set_bbox(dict(
                boxstyle=bs_val,
                facecolor=c.name(), alpha=alpha))


# ── Line / Arrow Properties Dialog ────────────────────────────────────

class LineArrowEditor(QWidget):
    """Embeddable property controls for a line segment or arrow."""

    def __init__(self, ann_dict, parent=None):
        super().__init__(parent)
        atype = ann_dict["type"]
        self._ann = ann_dict
        artist = ann_dict["artist"]
        ap = artist.arrowprops if hasattr(artist, "arrowprops") else {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Label (arrow only) ────────────────────────────────────────
        if atype == "arrow":
            form0 = QFormLayout()
            self._label_edit = QLineEdit(artist.get_text())
            form0.addRow("Label:", self._label_edit)
            layout.addLayout(form0)
        else:
            self._label_edit = None

        # ── Line style ────────────────────────────────────────────────
        line_group = QGroupBox("Line")
        lf = QFormLayout(line_group)

        self._color_btn = _ColorButton("#000000")
        # Read current colour from arrow patch.
        arrow_patch = getattr(artist, "arrow_patch", None)
        if arrow_patch is not None:
            try:
                from matplotlib.colors import to_hex
                ec = arrow_patch.get_edgecolor()
                self._color_btn.setColor(to_hex(ec[:3]))
            except Exception:
                pass
        lf.addRow("Colour:", self._color_btn)

        self._lw_spin = QDoubleSpinBox()
        self._lw_spin.setRange(0.1, 20.0)
        self._lw_spin.setSingleStep(0.5)
        self._lw_spin.setDecimals(1)
        cur_lw = 1.5
        if arrow_patch is not None:
            try:
                cur_lw = arrow_patch.get_linewidth()
            except Exception:
                pass
        self._lw_spin.setValue(cur_lw)
        lf.addRow("Width:", self._lw_spin)

        self._ls_combo = QComboBox()
        for label, _ in _LINE_STYLES:
            self._ls_combo.addItem(label)
        cur_ls = "-"
        if arrow_patch is not None:
            try:
                cur_ls = arrow_patch.get_linestyle()
            except Exception:
                pass
        for j, (_, val) in enumerate(_LINE_STYLES):
            if val == cur_ls:
                self._ls_combo.setCurrentIndex(j)
                break
        lf.addRow("Style:", self._ls_combo)

        # Arrow style (arrows only)
        if atype == "arrow":
            self._arrow_combo = QComboBox()
            for label, _ in _ARROW_STYLES:
                self._arrow_combo.addItem(label)
            cur_as = ap.get("arrowstyle", "->") if ap else "->"
            for j, (_, val) in enumerate(_ARROW_STYLES):
                if val == cur_as:
                    self._arrow_combo.setCurrentIndex(j)
                    break
            lf.addRow("Arrow style:", self._arrow_combo)
        else:
            self._arrow_combo = None

        layout.addWidget(line_group)

        # ── Endpoints ─────────────────────────────────────────────────
        ep_group = QGroupBox("Endpoints")
        ef = QFormLayout(ep_group)

        xy = artist.xy
        xytext = artist.get_position()

        self._start_x = QDoubleSpinBox()
        self._start_x.setRange(-1e12, 1e12)
        self._start_x.setDecimals(6)
        self._start_x.setValue(xytext[0])
        ef.addRow("Start X:", self._start_x)

        self._start_y = QDoubleSpinBox()
        self._start_y.setRange(-1e12, 1e12)
        self._start_y.setDecimals(6)
        self._start_y.setValue(xytext[1])
        ef.addRow("Start Y:", self._start_y)

        self._end_x = QDoubleSpinBox()
        self._end_x.setRange(-1e12, 1e12)
        self._end_x.setDecimals(6)
        self._end_x.setValue(xy[0])
        ef.addRow("End X:", self._end_x)

        self._end_y = QDoubleSpinBox()
        self._end_y.setRange(-1e12, 1e12)
        self._end_y.setDecimals(6)
        self._end_y.setValue(xy[1])
        ef.addRow("End Y:", self._end_y)

        layout.addWidget(ep_group)
        layout.addStretch(1)

    def apply(self):
        """Apply properties to the annotation artist."""
        artist = self._ann["artist"]
        atype = self._ann["type"]

        # Endpoints
        artist.xy = (self._end_x.value(), self._end_y.value())
        artist.set_position((self._start_x.value(), self._start_y.value()))

        # Label (arrow only)
        if self._label_edit is not None:
            artist.set_text(self._label_edit.text())
            txt = self._label_edit.text().strip()
            if txt:
                artist.set_bbox(dict(boxstyle="round,pad=0.2",
                                     fc="white", alpha=0.7))
            else:
                artist.set_bbox(None)

        # Arrow props — rebuild dict and re-set.
        color = self._color_btn.color().name()
        lw = self._lw_spin.value()
        _, ls = _LINE_STYLES[self._ls_combo.currentIndex()]

        if atype == "arrow" and self._arrow_combo is not None:
            _, astyle = _ARROW_STYLES[self._arrow_combo.currentIndex()]
        else:
            astyle = "-"  # plain line, no arrowheads

        new_props = dict(arrowstyle=astyle, color=color, lw=lw,
                         linestyle=ls)
        # Update via the arrow patch directly if it exists.
        ap = getattr(artist, "arrow_patch", None)
        if ap is not None:
            try:
                ap.set_arrowstyle(astyle)
                ap.set_edgecolor(color)
                ap.set_facecolor(color)
                ap.set_linewidth(lw)
                ap.set_linestyle(ls)
            except Exception:
                pass
        # Also store on the annotation so future redraws keep them.
        artist.arrowprops = new_props


# ── Stand-alone property dialogs (thin wrappers) ──────────────────────

class TextAnnotationDialog(QDialog):
    """Modal wrapper around :class:`TextAnnotationEditor`."""

    def __init__(self, ann_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Text Annotation Properties")
        self.setMinimumWidth(340)
        self._editor = TextAnnotationEditor(ann_dict, self)
        lay = QVBoxLayout(self)
        lay.addWidget(self._editor)
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def apply(self):
        self._editor.apply()


class LineArrowPropertiesDialog(QDialog):
    """Modal wrapper around :class:`LineArrowEditor`."""

    def __init__(self, ann_dict, parent=None):
        super().__init__(parent)
        atype = ann_dict["type"]
        self.setWindowTitle(
            "Arrow Properties" if atype == "arrow" else "Line Properties")
        self.setMinimumWidth(360)
        self._editor = LineArrowEditor(ann_dict, self)
        lay = QVBoxLayout(self)
        lay.addWidget(self._editor)
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def apply(self):
        self._editor.apply()


# ── Annotations Manager ───────────────────────────────────────────────

class AnnotationsManagerDialog(QDialog):
    """Manage every annotation on a chart from a single place.

    Left: a list of all text / arrow / line annotations.  Right: the
    property editor for the selected one.  A Delete button removes the
    selection.  This is the way to reach annotations that are hard to
    click directly, and it replaces the individual property dialogs.
    """

    def __init__(self, chart, parent=None, preselect_idx=None):
        super().__init__(parent)
        self.setWindowTitle("Annotations Manager")
        self.resize(640, 460)
        self._chart = chart
        self._editor = None
        self._current_idx = -1

        outer = QVBoxLayout(self)
        split = QSplitter(Qt.Horizontal)
        outer.addWidget(split, 1)

        # ── Left: list + delete ──────────────────────────────────────
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self._list = QListWidget()
        self._list.setMinimumWidth(190)
        lv.addWidget(self._list, 1)
        self._del_btn = QPushButton("Delete")
        self._del_btn.setToolTip("Remove the selected annotation")
        self._del_btn.clicked.connect(self._delete_current)
        lv.addWidget(self._del_btn)
        split.addWidget(left)

        # ── Right: editor host (scrollable) ──────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._right_host = QWidget()
        self._right_layout = QVBoxLayout(self._right_host)
        self._placeholder = QLabel(
            "No annotation selected.\n\nAdd text, arrows or lines from the "
            "chart's right-click menu, then edit them here.")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._right_layout.addWidget(self._placeholder)
        self._right_layout.addStretch(1)
        self._scroll.setWidget(self._right_host)
        split.addWidget(self._scroll)
        split.setSizes([210, 430])

        # ── Footer ───────────────────────────────────────────────────
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        apply_btn = QPushButton("Apply")
        apply_btn.setToolTip("Apply the current edits to the chart")
        apply_btn.clicked.connect(self._apply_current)
        bb.addButton(apply_btn, QDialogButtonBox.ApplyRole)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

        self._list.currentRowChanged.connect(self._on_row_changed)
        self._reload_list()
        n = self._list.count()
        if n:
            if isinstance(preselect_idx, int) and 0 <= preselect_idx < n:
                self._list.setCurrentRow(preselect_idx)
            else:
                self._list.setCurrentRow(0)
        else:
            self._del_btn.setEnabled(False)

    # ── list helpers ──────────────────────────────────────────────────
    @staticmethod
    def _ann_label(i, a):
        atype = a.get("type", "?")
        artist = a.get("artist")
        try:
            text = artist.get_text()
        except Exception:
            text = a.get("text", "")
        text = (text or "").strip()
        if len(text) > 24:
            text = text[:23] + "…"
        if atype == "text":
            body = f"“{text}”" if text else "(empty)"
            return f"{i + 1}.  Text — {body}"
        if atype == "arrow":
            body = f" — “{text}”" if text else ""
            return f"{i + 1}.  Arrow{body}"
        if atype == "line":
            return f"{i + 1}.  Line"
        return f"{i + 1}.  {atype.title()}"

    def _reload_list(self):
        self._list.blockSignals(True)
        self._list.clear()
        for i, a in enumerate(self._chart._annotations):
            self._list.addItem(self._ann_label(i, a))
        self._list.blockSignals(False)

    def _clear_editor(self):
        if self._editor is not None:
            self._right_layout.removeWidget(self._editor)
            self._editor.setParent(None)
            self._editor.deleteLater()
            self._editor = None

    # ── selection / editing ──────────────────────────────────────────
    def _on_row_changed(self, row):
        # Commit edits to the previously shown annotation first.
        self._commit_current()
        self._clear_editor()
        self._current_idx = row
        anns = self._chart._annotations
        if row < 0 or row >= len(anns):
            self._placeholder.show()
            return
        a = anns[row]
        self._placeholder.hide()
        if a["type"] == "text":
            self._editor = TextAnnotationEditor(a, self._right_host)
        else:
            self._editor = LineArrowEditor(a, self._right_host)
        self._right_layout.insertWidget(0, self._editor)
        # Highlight it on the chart so the user sees which one it is.
        try:
            self._chart._select_annotation(row)
        except Exception:
            pass

    def _commit_current(self):
        """Apply pending editor edits to the current annotation."""
        if self._editor is None:
            return
        idx = self._current_idx
        anns = self._chart._annotations
        if idx < 0 or idx >= len(anns):
            return
        a = anns[idx]
        from .undo_commands import (_snapshot_annotation,
                                     ModifyAnnotationCmd)
        old_snap = _snapshot_annotation(a)
        self._editor.apply()
        new_snap = _snapshot_annotation(a)
        if new_snap != old_snap:
            undo = self._chart._get_undo_stack()
            if undo is not None:
                undo.push(ModifyAnnotationCmd(
                    self._chart, a, old_snap, new_snap))
            self._chart._canvas.draw_idle()
        # Keep the list label in sync (text may have changed).
        if 0 <= idx < self._list.count():
            it = self._list.item(idx)
            if it is not None:
                it.setText(self._ann_label(idx, a))

    def _apply_current(self):
        self._commit_current()
        idx = self._current_idx
        # Refresh selection visuals to match the new geometry.
        if 0 <= idx < len(self._chart._annotations):
            try:
                self._chart._select_annotation(idx)
            except Exception:
                pass

    def _delete_current(self):
        idx = self._current_idx
        anns = self._chart._annotations
        if idx < 0 or idx >= len(anns):
            return
        # Drop the editor first so the row change that follows does not
        # try to commit edits to an annotation we are removing.
        self._clear_editor()
        self._current_idx = -1
        try:
            self._chart._select_annotation(idx)
            self._chart._delete_selected_annotation()
        except Exception:
            pass
        self._reload_list()
        n = self._list.count()
        if n:
            self._list.setCurrentRow(min(idx, n - 1))
        else:
            self._del_btn.setEnabled(False)
            self._placeholder.show()

    def reject(self):
        # Commit any pending edits before closing (covers Close and [X]).
        self._commit_current()
        super().reject()
