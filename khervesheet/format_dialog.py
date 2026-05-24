"""Format Cells dialog — Excel-style multi-tab cell formatting.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal
from PyQt5.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush, QFontMetrics, QIcon, QPixmap,
)
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QFormLayout, QGroupBox, QLabel,
    QListWidget, QListWidgetItem, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QPushButton, QFontComboBox, QColorDialog, QSizePolicy,
    QFrame, QAbstractItemView,
)

from .cellformat import CellFormat, BorderSpec


# ── Number format categories ────────────────────────────────────────

_NUM_CATEGORIES = [
    ("General",    "General format cells have no specific number format."),
    ("Number",     "Number format displays values with a fixed number of\n"
                   "decimal places.  Select precision below."),
    ("Currency",   "Currency format is used for general monetary values.\n"
                   "Displays a dollar sign and two decimal places."),
    ("Percentage", "Percentage format multiplies the cell value by 100\n"
                   "and displays the result with a percent sign."),
    ("Scientific", "Scientific format displays numbers in exponential\n"
                   "notation (e.g. 1.23e+04)."),
    ("Date",       "Date format displays cell values as dates."),
    ("Time",       "Time format displays cell values as times."),
    ("Text",       "Text format cells are treated as text even when a\n"
                   "number is in the cell."),
]

# Map category name -> format string(s) for _format_value.
_CAT_TO_FMT = {
    "General": "General",
    "Number": "0.00",       # default; precision spin adjusts
    "Currency": "Currency",
    "Percentage": "Percentage",
    "Scientific": "Scientific",
    "Date": "Date",
    "Time": "Time",
    "Text": "Text",
}

_NUMBER_PRECISIONS = {
    0: "0", 1: "0.0", 2: "0.00", 3: "0.000", 4: "0.0000",
}


# ── Helpers ─────────────────────────────────────────────────────────

def _format_preview(raw: str, fmt: str) -> str:
    """Format a raw value for preview in the Number tab."""
    if not raw or fmt in ("General", "Text"):
        return raw or "0"
    try:
        val = float(raw)
    except (ValueError, TypeError):
        return raw or "0"
    if fmt == "0":
        return f"{val:.0f}"
    elif fmt == "0.0":
        return f"{val:.1f}"
    elif fmt == "0.00":
        return f"{val:.2f}"
    elif fmt == "0.000":
        return f"{val:.3f}"
    elif fmt == "0.0000":
        return f"{val:.4f}"
    elif fmt == "Scientific":
        return f"{val:.4e}"
    elif fmt == "Percentage":
        return f"{val * 100:.2f}%"
    elif fmt == "Currency":
        return f"${val:,.2f}"
    return raw or "0"


# ── Line style helpers ──────────────────────────────────────────────

_LINE_STYLES = [
    # (display name, Qt pen style, line width)
    ("Hair",              Qt.SolidLine,      0.5),
    ("Thin",              Qt.SolidLine,      1.0),
    ("Medium",            Qt.SolidLine,      2.0),
    ("Thick",             Qt.SolidLine,      3.0),
    ("Dashed",            Qt.DashLine,       1.0),
    ("Dashed Medium",     Qt.DashLine,       2.0),
    ("Dashed Thick",      Qt.DashLine,       3.0),
    ("Dotted",            Qt.DotLine,        1.0),
    ("Dotted Medium",     Qt.DotLine,        2.0),
    ("Dash-Dot",          Qt.DashDotLine,    1.0),
    ("Dash-Dot Medium",   Qt.DashDotLine,    2.0),
    ("Dash-Dot-Dot",      Qt.DashDotDotLine, 1.0),
    ("Dash-Dot-Dot Medium", Qt.DashDotDotLine, 2.0),
    ("Double",            Qt.SolidLine,      1.0),  # drawn as two lines
]


def _line_style_icon(style: int, width: float = 1.0,
                     size: int = 80, double: bool = False) -> QIcon:
    """Create a small icon showing the given line style and width."""
    pix = QPixmap(size, 20)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#000000"), width, Qt.PenStyle(style))
    p.setPen(pen)
    if double:
        p.drawLine(4, 7, size - 4, 7)
        p.drawLine(4, 13, size - 4, 13)
    else:
        p.drawLine(4, 10, size - 4, 10)
    p.end()
    return QIcon(pix)


# ── Border preview widget ──────────────────────────────────────────

class _BorderPreviewWidget(QWidget):
    """Interactive preview showing which borders are active.

    Click near an edge to toggle that border on/off.
    """

    border_changed = pyqtSignal()

    _EDGE_TOLERANCE = 12  # px from edge to detect click

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Each value: BorderSpec or None.
        self.borders: Dict[str, Optional[BorderSpec]] = {
            "top": None, "bottom": None, "left": None, "right": None,
        }
        self._line_style = Qt.SolidLine
        self._line_color = "#000000"
        self._line_width = 1.0

    def set_line_style(self, style: int):
        self._line_style = style

    def set_line_color(self, color: str):
        self._line_color = color

    def set_line_width(self, width: float):
        self._line_width = width

    def _cell_rect(self) -> QRect:
        """The inner rectangle representing the cell."""
        m = 24
        return self.rect().adjusted(m, m, -m, -m)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Background.
        p.fillRect(self.rect(), QColor("#ffffff"))

        cr = self._cell_rect()

        # Faint guide lines.
        guide = QPen(QColor("#d0d0d0"), 1.0, Qt.DotLine)
        p.setPen(guide)
        p.drawRect(cr)

        # "Text" label inside.
        p.setPen(QPen(QColor("#999999")))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(cr, Qt.AlignCenter, "Text")

        # Active borders.
        for side, spec in self.borders.items():
            if spec is None:
                continue
            pen = QPen(QColor(spec.color), spec.width,
                       Qt.PenStyle(spec.style))
            p.setPen(pen)
            if side == "top":
                p.drawLine(cr.topLeft(), cr.topRight())
            elif side == "bottom":
                p.drawLine(cr.bottomLeft(), cr.bottomRight())
            elif side == "left":
                p.drawLine(cr.topLeft(), cr.bottomLeft())
            elif side == "right":
                p.drawLine(cr.topRight(), cr.bottomRight())
        p.end()

    def mousePressEvent(self, event):
        pos = event.pos()
        cr = self._cell_rect()
        tol = self._EDGE_TOLERANCE

        toggled = None
        # Check proximity to each edge.
        if abs(pos.y() - cr.top()) < tol and cr.left() - tol < pos.x() < cr.right() + tol:
            toggled = "top"
        elif abs(pos.y() - cr.bottom()) < tol and cr.left() - tol < pos.x() < cr.right() + tol:
            toggled = "bottom"
        elif abs(pos.x() - cr.left()) < tol and cr.top() - tol < pos.y() < cr.bottom() + tol:
            toggled = "left"
        elif abs(pos.x() - cr.right()) < tol and cr.top() - tol < pos.y() < cr.bottom() + tol:
            toggled = "right"

        if toggled is not None:
            if self.borders[toggled] is not None:
                self.borders[toggled] = None
            else:
                self.borders[toggled] = BorderSpec(
                    style=self._line_style,
                    color=self._line_color,
                    width=self._line_width,
                )
            self.update()
            self.border_changed.emit()


# ── Color button ────────────────────────────────────────────────────

class _ColorButton(QPushButton):
    """Small button showing a colour swatch."""

    color_changed = pyqtSignal(str)

    def __init__(self, color: str = "#000000", palette=None, parent=None):
        super().__init__(parent)
        self._color = color
        self._palette = palette or []
        self.setFixedSize(28, 28)
        self._update_icon()
        self.clicked.connect(self._pick)

    def color(self) -> str:
        return self._color

    def set_color(self, c: str):
        self._color = c
        self._update_icon()

    def _update_icon(self):
        self.setStyleSheet(
            f"background:{self._color}; border:1px solid #888;")

    def _pick(self):
        dlg = QColorDialog(QColor(self._color), self)
        dlg.setStyleSheet("")
        if dlg.exec_() == QColorDialog.Accepted:
            c = dlg.selectedColor().name()
            self._color = c
            self._update_icon()
            self.color_changed.emit(c)


# ── Main dialog ─────────────────────────────────────────────────────

class FormatCellsDialog(QDialog):
    """Excel-style Format Cells dialog with Number, Alignment, Font,
    Border, and Fill tabs."""

    def __init__(self, cell_format: CellFormat, sample_value: str,
                 palette: List[str], current_number_fmt: str = "General",
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Format Cells")
        self.setMinimumSize(520, 440)
        self.resize(560, 470)

        self._cf = cell_format
        self._sample = sample_value or "0"
        self._palette = palette
        self._current_num_fmt = current_number_fmt

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._tabs.addTab(self._build_number_tab(), "Number")
        self._tabs.addTab(self._build_alignment_tab(), "Alignment")
        self._tabs.addTab(self._build_font_tab(), "Font")
        self._tabs.addTab(self._build_border_tab(), "Border")
        self._tabs.addTab(self._build_fill_tab(), "Fill")

        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    # ── Number tab ──────────────────────────────────────────────────

    def _build_number_tab(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)

        # Category list.
        left = QVBoxLayout()
        left.addWidget(QLabel("Category:"))
        self._num_list = QListWidget()
        self._num_list.setMaximumWidth(140)
        for name, _desc in _NUM_CATEGORIES:
            self._num_list.addItem(name)
        left.addWidget(self._num_list)
        h.addLayout(left)

        # Right side: sample + description + precision.
        right = QVBoxLayout()
        right.addSpacing(8)

        # Sample area.
        sample_box = QGroupBox("Sample")
        sb_lay = QVBoxLayout(sample_box)
        self._num_sample = QLabel(self._sample)
        self._num_sample.setStyleSheet(
            "font-size:13px; padding:6px; background:#fafafa; "
            "border:1px solid #ccc;")
        self._num_sample.setMinimumHeight(32)
        sb_lay.addWidget(self._num_sample)
        right.addWidget(sample_box)

        # Description.
        self._num_desc = QLabel()
        self._num_desc.setWordWrap(True)
        self._num_desc.setStyleSheet("color:#555; margin-top:8px;")
        right.addWidget(self._num_desc)

        # Precision spinner (only visible for "Number" category).
        prec_row = QHBoxLayout()
        self._prec_label = QLabel("Decimal places:")
        self._prec_spin = QSpinBox()
        self._prec_spin.setRange(0, 4)
        self._prec_spin.setValue(2)
        prec_row.addWidget(self._prec_label)
        prec_row.addWidget(self._prec_spin)
        prec_row.addStretch()
        right.addLayout(prec_row)

        right.addStretch()
        h.addLayout(right, stretch=1)

        # Connections.
        self._num_list.currentRowChanged.connect(self._on_num_category)
        self._prec_spin.valueChanged.connect(self._on_num_precision)

        # Pre-select current format.
        self._pre_select_number()

        return w

    def _pre_select_number(self):
        """Select the list item matching the current number format."""
        fmt = self._current_num_fmt
        # Map format strings back to category names.
        if fmt in ("0", "0.0", "0.00", "0.000", "0.0000"):
            cat = "Number"
            prec = {"0": 0, "0.0": 1, "0.00": 2, "0.000": 3,
                     "0.0000": 4}.get(fmt, 2)
            self._prec_spin.setValue(prec)
        elif fmt in _CAT_TO_FMT:
            cat = fmt
        else:
            cat = "General"

        for i in range(self._num_list.count()):
            if self._num_list.item(i).text() == cat:
                self._num_list.setCurrentRow(i)
                return
        self._num_list.setCurrentRow(0)

    def _on_num_category(self, row: int):
        if row < 0 or row >= len(_NUM_CATEGORIES):
            return
        name, desc = _NUM_CATEGORIES[row]
        self._num_desc.setText(desc)
        show_prec = (name == "Number")
        self._prec_label.setVisible(show_prec)
        self._prec_spin.setVisible(show_prec)
        self._update_num_sample()

    def _on_num_precision(self, _val):
        self._update_num_sample()

    def _update_num_sample(self):
        cat = self._selected_num_category()
        fmt = self._num_fmt_string()
        self._num_sample.setText(_format_preview(self._sample, fmt))

    def _selected_num_category(self) -> str:
        item = self._num_list.currentItem()
        return item.text() if item else "General"

    def _num_fmt_string(self) -> str:
        cat = self._selected_num_category()
        if cat == "Number":
            prec = self._prec_spin.value()
            return _NUMBER_PRECISIONS.get(prec, "0.00")
        return _CAT_TO_FMT.get(cat, "General")

    # ── Alignment tab ───────────────────────────────────────────────

    def _build_alignment_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        # Text alignment group.
        align_grp = QGroupBox("Text alignment")
        form = QFormLayout(align_grp)

        self._h_align = QComboBox()
        self._h_align.addItems(["General", "Left", "Center", "Right"])
        form.addRow("Horizontal:", self._h_align)

        self._v_align = QComboBox()
        self._v_align.addItems(["Bottom", "Center", "Top"])
        form.addRow("Vertical:", self._v_align)

        lay.addWidget(align_grp)

        # Text control group.
        ctrl_grp = QGroupBox("Text control")
        ctrl_lay = QVBoxLayout(ctrl_grp)
        self._wrap_text = QCheckBox("Wrap text")
        ctrl_lay.addWidget(self._wrap_text)
        lay.addWidget(ctrl_grp)

        lay.addStretch()

        # Pre-populate.
        self._pre_select_alignment()

        return w

    def _pre_select_alignment(self):
        a = self._cf.alignment
        if a is not None:
            # Horizontal.
            if a & Qt.AlignRight:
                self._h_align.setCurrentText("Right")
            elif a & Qt.AlignHCenter:
                self._h_align.setCurrentText("Center")
            elif a & Qt.AlignLeft:
                self._h_align.setCurrentText("Left")
            # Vertical.
            if a & Qt.AlignTop:
                self._v_align.setCurrentText("Top")
            elif a & Qt.AlignVCenter:
                self._v_align.setCurrentText("Center")
            else:
                self._v_align.setCurrentText("Bottom")
        if self._cf.wrap_text:
            self._wrap_text.setChecked(True)

    def _alignment_flags(self) -> Optional[int]:
        h_map = {
            "General": None,
            "Left": Qt.AlignLeft,
            "Center": Qt.AlignHCenter,
            "Right": Qt.AlignRight,
        }
        v_map = {
            "Bottom": Qt.AlignBottom,
            "Center": Qt.AlignVCenter,
            "Top": Qt.AlignTop,
        }
        h = h_map.get(self._h_align.currentText())
        v = v_map.get(self._v_align.currentText(), Qt.AlignBottom)
        if h is None:
            return None
        return int(h | v)

    # ── Font tab ────────────────────────────────────────────────────

    def _build_font_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        # Font family + style + size row.
        top = QHBoxLayout()

        # Family.
        fam_col = QVBoxLayout()
        fam_col.addWidget(QLabel("Font:"))
        self._font_combo = QFontComboBox()
        fam_col.addWidget(self._font_combo)
        top.addLayout(fam_col, stretch=2)

        # Style.
        sty_col = QVBoxLayout()
        sty_col.addWidget(QLabel("Font style:"))
        self._font_style = QComboBox()
        self._font_style.addItems(["Regular", "Bold", "Italic",
                                    "Bold Italic"])
        sty_col.addWidget(self._font_style)
        top.addLayout(sty_col, stretch=1)

        # Size.
        sz_col = QVBoxLayout()
        sz_col.addWidget(QLabel("Size:"))
        self._font_size = QComboBox()
        self._font_size.setEditable(True)
        self._font_size.setMaximumWidth(70)
        for s in ("8", "9", "10", "11", "12", "14", "16",
                  "18", "20", "22", "24", "26", "28", "36",
                  "48", "72"):
            self._font_size.addItem(s)
        self._font_size.setCurrentText("9")
        sz_col.addWidget(self._font_size)
        top.addLayout(sz_col)

        lay.addLayout(top)

        # Underline + color row.
        mid = QHBoxLayout()
        self._font_underline = QCheckBox("Underline")
        mid.addWidget(self._font_underline)
        mid.addSpacing(20)
        mid.addWidget(QLabel("Color:"))
        self._font_color_btn = _ColorButton(
            self._cf.font_color or "#000000", self._palette)
        mid.addWidget(self._font_color_btn)
        mid.addStretch()
        lay.addLayout(mid)

        # Preview.
        prev_grp = QGroupBox("Preview")
        prev_lay = QVBoxLayout(prev_grp)
        self._font_preview = QLabel("AaBbCcYyZz")
        self._font_preview.setAlignment(Qt.AlignCenter)
        self._font_preview.setMinimumHeight(50)
        self._font_preview.setStyleSheet(
            "background:#ffffff; border:1px solid #ccc; padding:8px;")
        prev_lay.addWidget(self._font_preview)
        lay.addWidget(prev_grp)

        lay.addStretch()

        # Pre-populate.
        self._pre_select_font()

        # Live preview connections.
        self._font_combo.currentFontChanged.connect(
            lambda: self._update_font_preview())
        self._font_style.currentTextChanged.connect(
            lambda: self._update_font_preview())
        self._font_size.currentTextChanged.connect(
            lambda: self._update_font_preview())
        self._font_underline.toggled.connect(
            lambda: self._update_font_preview())
        self._font_color_btn.color_changed.connect(
            lambda: self._update_font_preview())

        self._update_font_preview()
        return w

    def _pre_select_font(self):
        cf = self._cf
        if cf.font_family:
            self._font_combo.setCurrentFont(QFont(cf.font_family))
        if cf.font_size:
            self._font_size.setCurrentText(
                str(int(cf.font_size)) if cf.font_size == int(cf.font_size)
                else str(cf.font_size))
        # Style from bold/italic.
        bold = cf.bold or False
        italic = cf.italic or False
        if bold and italic:
            self._font_style.setCurrentText("Bold Italic")
        elif bold:
            self._font_style.setCurrentText("Bold")
        elif italic:
            self._font_style.setCurrentText("Italic")
        else:
            self._font_style.setCurrentText("Regular")
        if cf.underline:
            self._font_underline.setChecked(True)
        if cf.font_color:
            self._font_color_btn.set_color(cf.font_color)

    def _update_font_preview(self):
        f = self._font_combo.currentFont()
        try:
            sz = float(self._font_size.currentText())
        except ValueError:
            sz = 9.0
        f.setPointSizeF(max(1, sz))
        style = self._font_style.currentText()
        f.setBold(style in ("Bold", "Bold Italic"))
        f.setItalic(style in ("Italic", "Bold Italic"))
        f.setUnderline(self._font_underline.isChecked())
        self._font_preview.setFont(f)
        c = self._font_color_btn.color()
        self._font_preview.setStyleSheet(
            f"color:{c}; background:#ffffff; border:1px solid #ccc; "
            f"padding:8px;")

    # ── Border tab ──────────────────────────────────────────────────

    def _build_border_tab(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)

        # Left column: presets, line style, color.
        left = QVBoxLayout()

        # Presets.
        preset_grp = QGroupBox("Presets")
        preset_lay = QHBoxLayout(preset_grp)
        self._brd_none_btn = QPushButton("None")
        self._brd_none_btn.setFixedWidth(70)
        self._brd_outline_btn = QPushButton("Outline")
        self._brd_outline_btn.setFixedWidth(70)
        self._brd_inside_btn = QPushButton("Inside")
        self._brd_inside_btn.setFixedWidth(70)
        preset_lay.addWidget(self._brd_none_btn)
        preset_lay.addWidget(self._brd_outline_btn)
        preset_lay.addWidget(self._brd_inside_btn)
        left.addWidget(preset_grp)

        # Line style.
        style_grp = QGroupBox("Line style")
        style_lay = QVBoxLayout(style_grp)
        self._line_style_list = QListWidget()
        self._line_style_list.setMaximumHeight(180)
        for name, style, width in _LINE_STYLES:
            item = QListWidgetItem()
            item.setText(name)
            is_double = (name == "Double")
            item.setIcon(_line_style_icon(style, width,
                                          double=is_double))
            item.setData(Qt.UserRole, (style, width))
            self._line_style_list.addItem(item)
        self._line_style_list.setCurrentRow(0)
        style_lay.addWidget(self._line_style_list)
        left.addWidget(style_grp)

        # Line color.
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Color:"))
        self._brd_color_btn = _ColorButton("#000000", self._palette)
        color_row.addWidget(self._brd_color_btn)
        color_row.addStretch()
        left.addLayout(color_row)

        left.addStretch()
        lay.addLayout(left)

        # Right column: border preview.
        right = QVBoxLayout()
        right.addWidget(QLabel("Border:"))
        self._border_preview = _BorderPreviewWidget()
        right.addWidget(self._border_preview, stretch=1)

        # Individual toggle buttons.
        btn_row = QHBoxLayout()
        self._brd_top_btn = QPushButton("Top")
        self._brd_bottom_btn = QPushButton("Bottom")
        self._brd_left_btn = QPushButton("Left")
        self._brd_right_btn = QPushButton("Right")
        for b in (self._brd_top_btn, self._brd_bottom_btn,
                  self._brd_left_btn, self._brd_right_btn):
            b.setFixedWidth(55)
            btn_row.addWidget(b)
        right.addLayout(btn_row)

        lay.addLayout(right, stretch=1)

        # Pre-populate.
        self._pre_select_borders()

        # Connections.
        self._brd_none_btn.clicked.connect(self._brd_preset_none)
        self._brd_outline_btn.clicked.connect(self._brd_preset_outline)
        self._brd_inside_btn.clicked.connect(self._brd_preset_inside)
        self._brd_top_btn.clicked.connect(lambda: self._brd_toggle("top"))
        self._brd_bottom_btn.clicked.connect(
            lambda: self._brd_toggle("bottom"))
        self._brd_left_btn.clicked.connect(lambda: self._brd_toggle("left"))
        self._brd_right_btn.clicked.connect(
            lambda: self._brd_toggle("right"))
        self._line_style_list.currentRowChanged.connect(
            self._on_line_style_changed)
        self._brd_color_btn.color_changed.connect(
            self._on_border_color_changed)

        return w

    def _pre_select_borders(self):
        cf = self._cf
        for side in ("top", "bottom", "left", "right"):
            spec = getattr(cf, f"border_{side}", None)
            if spec is not None:
                self._border_preview.borders[side] = BorderSpec(
                    style=spec.style, color=spec.color, width=spec.width)
        self._border_preview.update()

    def _current_border_spec(self) -> BorderSpec:
        """Build a BorderSpec from current line style/color selections."""
        item = self._line_style_list.currentItem()
        if item:
            data = item.data(Qt.UserRole)
            if isinstance(data, tuple):
                style, width = data
            else:
                style, width = data, 1.0
        else:
            style, width = Qt.SolidLine, 1.0
        color = self._brd_color_btn.color()
        return BorderSpec(style=style, color=color, width=width)

    def _brd_preset_none(self):
        for side in self._border_preview.borders:
            self._border_preview.borders[side] = None
        self._border_preview.update()

    def _brd_preset_outline(self):
        spec = self._current_border_spec()
        for side in ("top", "bottom", "left", "right"):
            self._border_preview.borders[side] = BorderSpec(
                style=spec.style, color=spec.color, width=spec.width)
        self._border_preview.update()

    def _brd_preset_inside(self):
        # "Inside" clears outside and is a no-op for single cell.
        # For the preview, we show no borders (single cell has no inside).
        self._brd_preset_none()

    def _brd_toggle(self, side: str):
        if self._border_preview.borders[side] is not None:
            self._border_preview.borders[side] = None
        else:
            self._border_preview.borders[side] = self._current_border_spec()
        self._border_preview.update()

    def _on_line_style_changed(self, row):
        if row >= 0:
            data = self._line_style_list.item(row).data(Qt.UserRole)
            if isinstance(data, tuple):
                style, width = data
            else:
                style, width = data, 1.0
        else:
            style, width = Qt.SolidLine, 1.0
        self._border_preview.set_line_style(style)
        self._border_preview.set_line_width(width)

    def _on_border_color_changed(self, color):
        self._border_preview.set_line_color(color)

    # ── Fill tab ────────────────────────────────────────────────────

    def _build_fill_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        lay.addWidget(QLabel("Background color:"))

        # Color palette grid.
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setSpacing(2)
        grid.setContentsMargins(4, 4, 4, 4)
        cols = 10
        self._fill_buttons: List[QPushButton] = []
        for i, color in enumerate(self._palette):
            btn = QPushButton()
            btn.setFixedSize(20, 20)
            btn.setStyleSheet(
                f"background:{color}; border:1px solid #888; "
                f"border-radius:0px;")
            btn.setToolTip(color)
            btn.clicked.connect(lambda _, c=color: self._select_fill(c))
            grid.addWidget(btn, i // cols, i % cols)
            self._fill_buttons.append(btn)
        lay.addWidget(grid_w)

        # Buttons row.
        btn_row = QHBoxLayout()
        no_fill = QPushButton("No Fill")
        no_fill.clicked.connect(lambda: self._select_fill(None))
        btn_row.addWidget(no_fill)
        more = QPushButton("More Colors\u2026")
        more.clicked.connect(self._pick_fill_custom)
        btn_row.addWidget(more)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        # Preview swatch.
        prev_grp = QGroupBox("Preview")
        prev_lay = QVBoxLayout(prev_grp)
        self._fill_preview = QLabel()
        self._fill_preview.setMinimumHeight(40)
        self._fill_preview.setAlignment(Qt.AlignCenter)
        prev_lay.addWidget(self._fill_preview)
        lay.addWidget(prev_grp)

        lay.addStretch()

        # Pre-populate.
        self._fill_color: Optional[str] = self._cf.bg_color
        self._update_fill_preview()

        return w

    def _select_fill(self, color: Optional[str]):
        self._fill_color = color
        self._update_fill_preview()

    def _pick_fill_custom(self):
        initial = QColor(self._fill_color) if self._fill_color else QColor("#ffffff")
        dlg = QColorDialog(initial, self)
        dlg.setStyleSheet("")
        if dlg.exec_() == QColorDialog.Accepted:
            self._select_fill(dlg.selectedColor().name())

    def _update_fill_preview(self):
        if self._fill_color:
            self._fill_preview.setStyleSheet(
                f"background:{self._fill_color}; border:1px solid #888;")
            self._fill_preview.setText(self._fill_color)
        else:
            self._fill_preview.setStyleSheet(
                "background:#ffffff; border:1px solid #ccc;")
            self._fill_preview.setText("No Fill")

    # ── Result extraction ───────────────────────────────────────────

    def get_result(self) -> dict:
        """Return a dict of all formatting settings from the dialog."""
        result = {}

        # Number format.
        result["number_format"] = self._num_fmt_string()

        # Alignment.
        result["alignment"] = self._alignment_flags()
        result["wrap_text"] = self._wrap_text.isChecked()

        # Font.
        style = self._font_style.currentText()
        result["bold"] = style in ("Bold", "Bold Italic")
        result["italic"] = style in ("Italic", "Bold Italic")
        result["underline"] = self._font_underline.isChecked()
        result["font_family"] = self._font_combo.currentFont().family()
        try:
            result["font_size"] = float(self._font_size.currentText())
        except ValueError:
            result["font_size"] = None
        result["font_color"] = self._font_color_btn.color()

        # Fill.
        result["bg_color"] = self._fill_color

        # Borders.
        for side in ("top", "bottom", "left", "right"):
            result[f"border_{side}"] = self._border_preview.borders[side]

        return result
