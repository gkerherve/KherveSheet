"""Printing, print preview, page setup, and PDF export.

Renders spreadsheet grids to QPrinter so that the printed / exported
output matches what is shown on screen (WYSIWYG): the same cell fonts,
colours, fills, borders, alignment, gridline and heading visibility.

A single :class:`PrintDialog` consolidates every print-related action —
orientation, paper size, margins, scaling, print-what (sheet / selection
/ defined area), live preview, direct printing and PDF export.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from PyQt5.QtCore import Qt, QRectF, QRect
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QGroupBox, QHBoxLayout, QVBoxLayout, QLabel, QComboBox,
    QCheckBox, QRadioButton, QSpinBox, QMessageBox,
    QFileDialog, QUndoCommand, QPushButton, QWidget,
)

if TYPE_CHECKING:
    from PyQt5.QtPrintSupport import QPrinter

# ── Constants ────────────────────────────────────────────────────────

_SCREEN_DPI = 96.0

# Standard paper sizes: name → (width_mm, height_mm)
PAPER_SIZES = {
    "A4":     (210, 297),
    "A3":     (297, 420),
    "Letter": (215.9, 279.4),
    "Legal":  (215.9, 355.6),
    "B5":     (176, 250),
}

DEFAULT_MARGINS_MM = {
    "top": 25.4, "bottom": 25.4,
    "left": 19.05, "right": 19.05,
}


# ── Column letter helper (duplicated to avoid circular import) ───────

def _col_letter(idx: int) -> str:
    """0 -> A, 1 -> B, ... 25 -> Z, 26 -> AA ..."""
    result = ""
    while True:
        result = chr(ord('A') + idx % 26) + result
        idx = idx // 26 - 1
        if idx < 0:
            break
    return result


# ── Undo command for print area ──────────────────────────────────────

class SetPrintAreaCmd(QUndoCommand):
    """Undoable set / clear of a sheet's print area."""

    def __init__(self, sheet, new_area, description="Set Print Area"):
        super().__init__(description)
        self._sheet = sheet
        self._old = getattr(sheet, '_print_area', None)
        self._new = new_area

    def redo(self):
        self._sheet._print_area = self._new

    def undo(self):
        self._sheet._print_area = self._old


# ── Cell border drawing (mirrors CellFormatDelegate._draw_borders) ───

def _draw_cell_borders(painter: QPainter, rect: QRectF, cf) -> None:
    """Draw a cell's per-edge borders exactly as the screen delegate does.

    *cf* is a ``CellFormat``; its edges are ``border_top`` / ``border_bottom``
    / ``border_left`` / ``border_right``, each an optional ``BorderSpec`` with
    integer ``style`` (a ``Qt.PenStyle`` value), ``color`` and ``width``.
    """
    edges = (
        ("top", cf.border_top, rect.topLeft(), rect.topRight()),
        ("bottom", cf.border_bottom, rect.bottomLeft(), rect.bottomRight()),
        ("left", cf.border_left, rect.topLeft(), rect.bottomLeft()),
        ("right", cf.border_right, rect.topRight(), rect.bottomRight()),
    )
    for _side, spec, p1, p2 in edges:
        if not spec:
            continue
        pen = QPen(QColor(spec.color), float(spec.width),
                   Qt.PenStyle(int(spec.style)))
        pen.setCapStyle(Qt.FlatCap)
        painter.setPen(pen)
        painter.drawLine(p1, p2)


# ── Sheet renderer ───────────────────────────────────────────────────

class SheetRenderer:
    """Render a SheetWidget's grid onto a QPrinter / QPdfWriter.

    Works in *screen pixels* (the same units the grid uses on screen) and
    applies a single scale that maps those pixels onto the printer device,
    so printed cells keep the on-screen proportions, fonts and formatting.
    Handles pagination, row/column headers, gridlines, cell formatting,
    word wrap, overlays (charts / images / shapes / equations), and the
    print-area / selection-only modes.
    """

    # Row-number column width and column-letter row height (screen px).
    ROW_HDR_WIDTH = 46
    HEADER_HEIGHT = 22
    # Reserved band at the bottom of every page for the page-number line.
    FOOTER_HEIGHT = 18

    def __init__(self, sheet, *,
                 margins_mm=None,
                 orientation="portrait",
                 paper_mm=None,
                 scale_percent=100,
                 fit_to_page=False,
                 selection_only=False,
                 use_print_area=True,
                 sheet_name="Sheet1",
                 show_gridlines=None,
                 show_headings=None):
        self._sheet = sheet
        self._margins = margins_mm or dict(DEFAULT_MARGINS_MM)
        self._orientation = orientation
        self._paper = paper_mm or (210, 297)
        self._scale_pct = scale_percent
        self._fit_to_page = fit_to_page
        self._selection_only = selection_only
        self._use_print_area = use_print_area
        self._sheet_name = sheet_name
        # None means "follow the on-screen state".
        self._show_gridlines = show_gridlines
        self._show_headings = show_headings

    # ── Public entry point ───────────────────────────────────────────

    def render(self, printer: "QPrinter"):
        """Paint the grid onto *printer* (may span multiple pages)."""
        table = self._sheet.table
        cell_formats = getattr(self._sheet, '_cell_formats', {})

        # Determine the cell range to print.
        r0, r1, c0, c1 = self._cell_range(table)
        if r1 < r0 or c1 < c0:
            return  # nothing to print

        cols = list(range(c0, c1 + 1))
        rows = list(range(r0, r1 + 1))
        col_ws = [max(table.columnWidth(c), 1) for c in cols]
        row_hs = [max(table.rowHeight(r), 1) for r in rows]

        show_grid = (table.showGrid() if self._show_gridlines is None
                     else bool(self._show_gridlines))
        show_head = (table.horizontalHeader().isVisible()
                     if self._show_headings is None
                     else bool(self._show_headings))

        rh_w = self.ROW_HDR_WIDTH if show_head else 0.0
        ch_h = self.HEADER_HEIGHT if show_head else 0.0

        # Device page geometry (device pixels, inside the printer margins).
        page_rect = printer.pageRect()
        dpi = printer.resolution() or _SCREEN_DPI

        # screen-px → device-px scale at 100 % ("actual size").
        base = dpi / _SCREEN_DPI

        total_w = sum(col_ws) + rh_w
        footer_dev = self.FOOTER_HEIGHT * base
        avail_dev_w = float(page_rect.width())
        avail_dev_h = float(page_rect.height()) - footer_dev

        if self._fit_to_page and total_w > 0:
            scale = min(avail_dev_w / total_w, base)
        else:
            scale = base * (self._scale_pct / 100.0)
        if scale <= 0:
            scale = base

        # Available drawing area expressed back in screen-px (content) units.
        avail_w = avail_dev_w / scale
        avail_h = avail_dev_h / scale
        data_w = max(avail_w - rh_w, 1.0)
        data_h = max(avail_h - ch_h, 1.0)

        col_pages = self._paginate(col_ws, data_w, start=c0)
        row_pages = self._paginate(row_hs, data_h, start=r0)
        if not col_pages or not row_pages:
            return

        # Starting screen-px offset of each page within the printed range.
        col_page_off = self._page_offsets(col_pages)
        row_page_off = self._page_offsets(row_pages)

        total_pages = len(col_pages) * len(row_pages)
        page_num = 0
        default_font = table.font()

        painter = QPainter(printer)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setRenderHint(QPainter.Antialiasing)

        hdr_font = QFont("Segoe UI")
        hdr_font.setPixelSize(11)
        hdr_font.setBold(True)
        grid_pen = QPen(QColor(208, 208, 208))
        grid_pen.setWidthF(0.6)
        hdr_pen = QPen(QColor(150, 150, 150), 0.6)
        hdr_bg = QColor(240, 240, 240)

        for cp_idx, col_page in enumerate(col_pages):
            page_w = sum(w for _, w in col_page)
            for rp_idx, row_page in enumerate(row_pages):
                page_h = sum(h for _, h in row_page)
                if page_num > 0:
                    printer.newPage()
                page_num += 1

                painter.save()
                painter.translate(page_rect.left(), page_rect.top())
                painter.scale(scale, scale)

                # ── Column headers (letters) ─────────────────────────
                if show_head:
                    painter.setFont(hdr_font)
                    x = rh_w
                    for gc, cw in col_page:
                        rect = QRectF(x, 0, cw, ch_h)
                        painter.fillRect(rect, hdr_bg)
                        painter.setPen(hdr_pen)
                        painter.drawRect(rect)
                        painter.setPen(QColor(60, 60, 60))
                        painter.drawText(rect, Qt.AlignCenter,
                                         _col_letter(gc))
                        x += cw

                # ── Row headers + cells ──────────────────────────────
                y = ch_h
                for gr, rh in row_page:
                    if show_head:
                        rh_rect = QRectF(0, y, rh_w, rh)
                        painter.fillRect(rh_rect, hdr_bg)
                        painter.setPen(hdr_pen)
                        painter.drawRect(rh_rect)
                        painter.setFont(hdr_font)
                        painter.setPen(QColor(60, 60, 60))
                        painter.drawText(rh_rect, Qt.AlignCenter,
                                         str(gr + 1))

                    x = rh_w
                    for gc, cw in col_page:
                        self._draw_cell(painter, table, cell_formats,
                                        gr, gc, QRectF(x, y, cw, rh),
                                        default_font, show_grid, grid_pen)
                        x += cw
                    y += rh

                # ── Overlays that fall on this page ──────────────────
                painter.setClipRect(QRectF(rh_w, ch_h, page_w, page_h))
                self._draw_overlays(painter, table, c0, r0,
                                    col_page_off[cp_idx],
                                    row_page_off[rp_idx],
                                    page_w, page_h, rh_w, ch_h)
                painter.setClipping(False)

                painter.restore()

                # ── Footer (page chrome, drawn in device space) ──────
                self._draw_footer(
                    painter, page_rect, base,
                    f"{self._sheet_name}   ·   "
                    f"Page {page_num} of {total_pages}")

        painter.end()

    # ── Cell drawing ─────────────────────────────────────────────────

    def _draw_cell(self, painter, table, cell_formats, gr, gc, rect,
                   default_font, show_grid, grid_pen):
        """Draw a single cell (fill, gridline, borders, text)."""
        fmt = cell_formats.get((gr, gc))
        item = table.item(gr, gc)

        # Background fill — prefer the item brush (what the screen uses),
        # then fall back to the format's bg_color.
        bg = None
        if item is not None:
            br = item.background()
            if br.style() != Qt.NoBrush and br.color().isValid():
                bg = br.color()
        if bg is None and fmt is not None and getattr(fmt, 'bg_color', None):
            bg = QColor(fmt.bg_color)
        if bg is not None:
            painter.fillRect(rect, bg)

        # Gridline (matches the on-screen grid toggle).
        if show_grid:
            painter.setPen(grid_pen)
            painter.drawRect(rect)

        # Per-edge cell borders.
        if fmt is not None:
            _draw_cell_borders(painter, rect, fmt)

        # Cell text.
        if item is None or not item.text():
            return
        font = self._pixel_font(item.font(), default_font)
        painter.setFont(font)
        fg_brush = item.foreground()
        if fg_brush.style() != Qt.NoBrush:
            painter.setPen(fg_brush.color())
        elif fmt is not None and getattr(fmt, 'font_color', None):
            painter.setPen(QColor(fmt.font_color))
        else:
            painter.setPen(QColor(0, 0, 0))

        align = item.textAlignment() or int(Qt.AlignLeft | Qt.AlignVCenter)
        if fmt is not None and getattr(fmt, 'wrap_text', None):
            align |= int(Qt.TextWordWrap)
        txt_rect = rect.adjusted(3, 1, -3, -1)
        painter.drawText(txt_rect, align, item.text())

    @staticmethod
    def _pixel_font(src: QFont, default_font: QFont) -> QFont:
        """Return a copy of *src* sized in screen pixels.

        Point sizes are converted to pixels at the screen DPI so that, once
        the painter's screen→device scale is applied, glyphs print at the
        same visual size they have on screen.
        """
        font = QFont(src if src.family() else default_font)
        pt = src.pointSizeF()
        if pt <= 0:
            pt = default_font.pointSizeF()
        if pt > 0:
            font.setPixelSize(max(int(round(pt * _SCREEN_DPI / 72.0)), 1))
        return font

    def _draw_footer(self, painter, page_rect, base, text):
        painter.save()
        f = QFont("Segoe UI")
        f.setPixelSize(max(int(round(9 * base)), 8))
        painter.setFont(f)
        painter.setPen(QColor(120, 120, 120))
        fh = self.FOOTER_HEIGHT * base
        rect = QRectF(page_rect.left(), page_rect.bottom() - fh,
                      page_rect.width(), fh)
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.restore()

    # ── Overlay rendering ─────────────────────────────────────────────

    def _draw_overlays(self, painter, table, c0, r0,
                       col_off, row_off, page_w, page_h, rh_w, ch_h):
        """Draw charts / images / shapes / equations onto the current page.

        Each overlay is a QWidget over the table viewport.  Its position is
        mapped into the printed range's screen-px coordinates, shifted by the
        current page's offset, and clipped to the page content rect — so an
        overlay lands on whichever page(s) actually contain it.
        """
        overlays = []
        for attr in ('_charts', '_images', '_shapes', '_equations'):
            overlays.extend(getattr(self._sheet, attr, []))
        if not overlays:
            return

        # Viewport pixel position of the printed range's top-left cell.
        vp_x0 = table.columnViewportPosition(c0)
        vp_y0 = table.rowViewportPosition(r0)

        for widget in overlays:
            if not widget.isVisible():
                continue
            geom = widget.geometry()
            # Position relative to the printed range origin (screen px).
            ox = (geom.x() - vp_x0) - col_off
            oy = (geom.y() - vp_y0) - row_off
            # Map onto the page content area.
            px = rh_w + ox
            py = ch_h + oy
            target = QRectF(px, py, geom.width(), geom.height())
            page_rect = QRectF(rh_w, ch_h, page_w, page_h)
            if not target.intersects(page_rect):
                continue
            pixmap = widget.grab()
            painter.drawPixmap(target.toRect(), pixmap)

    # ── Helpers ──────────────────────────────────────────────────────

    def _cell_range(self, table):
        """Return (r0, r1, c0, c1) for the region to print.

        Print area takes priority (unless disabled), then selection-only,
        then the used range (scan for non-empty cells)."""
        pa = getattr(self._sheet, '_print_area', None)
        if self._use_print_area and pa is not None:
            return pa  # (r1, r2, c1, c2)

        if self._selection_only:
            sel = table.selectedRanges()
            if sel:
                r1 = min(s.topRow() for s in sel)
                r2 = max(s.bottomRow() for s in sel)
                c1 = min(s.leftColumn() for s in sel)
                c2 = max(s.rightColumn() for s in sel)
                return (r1, r2, c1, c2)

        max_row = max_col = -1
        for r in range(table.rowCount()):
            for c in range(table.columnCount()):
                it = table.item(r, c)
                if it and it.text():
                    max_row = max(max_row, r)
                    max_col = max(max_col, c)
        if max_row < 0:
            return (0, -1, 0, -1)  # empty sheet
        return (0, max_row, 0, max_col)

    @staticmethod
    def _paginate(sizes, available, start=0):
        """Split column widths / row heights into pages.

        Returns a list of pages, each a list of ``(global_index, size)``
        tuples.  *start* is the global index of ``sizes[0]`` so the returned
        indices address the real rows / columns.
        """
        pages: list = []
        current: list = []
        used = 0.0
        for i, sz in enumerate(sizes):
            if current and used + sz > available:
                pages.append(current)
                current = []
                used = 0.0
            current.append((start + i, sz))
            used += sz
        if current:
            pages.append(current)
        return pages

    @staticmethod
    def _page_offsets(pages):
        """Cumulative screen-px offset of each page within the range."""
        offsets = []
        acc = 0.0
        for pg in pages:
            offsets.append(acc)
            acc += sum(sz for _, sz in pg)
        return offsets


# ── Printer factory ──────────────────────────────────────────────────

def _make_printer(orientation="portrait", paper_key="A4",
                  margins_mm=None):
    """Create and configure a QPrinter."""
    from PyQt5.QtPrintSupport import QPrinter
    printer = QPrinter(QPrinter.HighResolution)
    if orientation == "landscape":
        printer.setOrientation(QPrinter.Landscape)
    else:
        printer.setOrientation(QPrinter.Portrait)

    size_map = {
        "A4": QPrinter.A4,
        "A3": QPrinter.A3,
        "Letter": QPrinter.Letter,
        "Legal": QPrinter.Legal,
        "B5": QPrinter.B5,
    }
    printer.setPaperSize(size_map.get(paper_key, QPrinter.A4))

    m = margins_mm or DEFAULT_MARGINS_MM
    try:
        printer.setPageMargins(
            m["left"], m["top"], m["right"], m["bottom"],
            QPrinter.Millimeter)
    except Exception:
        pass
    return printer


# ── Unified Print dialog ─────────────────────────────────────────────

class PrintDialog(QDialog):
    """One dialog for everything print-related.

    Provides orientation, paper size, margins, scaling, print-what
    (active sheet / selection / defined print area), gridline and heading
    toggles, a live preview, and Print / Export-PDF / Set-Print-Area
    actions.  Settings are returned via :meth:`state` so the caller can
    persist them between invocations.
    """

    def __init__(self, parent=None, sheet=None, *,
                 state=None, sheet_name="Sheet1", undo_stack=None):
        super().__init__(parent)
        self.setWindowTitle("Print")
        self.setMinimumSize(900, 600)
        self._sheet = sheet
        self._sheet_name = sheet_name
        self._undo_stack = undo_stack

        st = dict(state or {})
        self._margins = dict(st.get("margins") or DEFAULT_MARGINS_MM)
        self._preview = None
        self._build_ui(st)
        self._refresh_preview()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self, st):
        from PyQt5.QtPrintSupport import QPrintPreviewWidget

        root = QHBoxLayout(self)

        # ── Left: controls ───────────────────────────────────────────
        side = QVBoxLayout()
        side.setSpacing(8)

        # Print what.
        wg = QGroupBox("Print what")
        wf = QVBoxLayout()
        self._what_combo = QComboBox()
        self._what_combo.addItem("Active sheet", "active")
        self._what_combo.addItem("Selection", "selection")
        self._what_combo.addItem("Defined print area", "area")
        has_area = getattr(self._sheet, '_print_area', None) is not None
        self._what_combo.setCurrentIndex(2 if has_area else 0)
        self._what_combo.currentIndexChanged.connect(self._refresh_preview)
        wf.addWidget(self._what_combo)
        area_row = QHBoxLayout()
        set_area_btn = QPushButton("Set from selection")
        set_area_btn.clicked.connect(self._set_print_area)
        clr_area_btn = QPushButton("Clear")
        clr_area_btn.clicked.connect(self._clear_print_area)
        area_row.addWidget(set_area_btn)
        area_row.addWidget(clr_area_btn)
        wf.addLayout(area_row)
        wg.setLayout(wf)
        side.addWidget(wg)

        # Orientation.
        og = QGroupBox("Orientation")
        oh = QHBoxLayout()
        self._portrait_rb = QRadioButton("Portrait")
        self._landscape_rb = QRadioButton("Landscape")
        if st.get("orientation") == "landscape":
            self._landscape_rb.setChecked(True)
        else:
            self._portrait_rb.setChecked(True)
        self._portrait_rb.toggled.connect(self._refresh_preview)
        oh.addWidget(self._portrait_rb)
        oh.addWidget(self._landscape_rb)
        og.setLayout(oh)
        side.addWidget(og)

        # Paper size.
        pg = QGroupBox("Paper size")
        pf = QFormLayout()
        self._size_combo = QComboBox()
        for name, (w, h) in PAPER_SIZES.items():
            self._size_combo.addItem(f"{name} ({w:.0f} × {h:.0f} mm)",
                                     name)
        pk = st.get("paper_key", "A4")
        keys = list(PAPER_SIZES.keys())
        self._size_combo.setCurrentIndex(keys.index(pk) if pk in keys else 0)
        self._size_combo.currentIndexChanged.connect(self._refresh_preview)
        pf.addRow("Size:", self._size_combo)
        pg.setLayout(pf)
        side.addWidget(pg)

        # Margins.
        mg = QGroupBox("Margins (mm)")
        mf = QFormLayout()
        self._margin_spins = {}
        for s in ("top", "bottom", "left", "right"):
            sp = QDoubleSpinBox()
            sp.setRange(0, 100)
            sp.setDecimals(1)
            sp.setValue(self._margins.get(s, 25.4))
            sp.valueChanged.connect(self._refresh_preview)
            mf.addRow(s.capitalize() + ":", sp)
            self._margin_spins[s] = sp
        mg.setLayout(mf)
        side.addWidget(mg)

        # Scaling.
        sg = QGroupBox("Scaling")
        sv = QVBoxLayout()
        sh = QHBoxLayout()
        sh.addWidget(QLabel("Scale:"))
        self._scale_spin = QSpinBox()
        self._scale_spin.setRange(10, 400)
        self._scale_spin.setSuffix(" %")
        self._scale_spin.setValue(int(st.get("scale_percent", 100)))
        self._scale_spin.valueChanged.connect(self._refresh_preview)
        sh.addWidget(self._scale_spin)
        sv.addLayout(sh)
        self._fit_cb = QCheckBox("Fit all columns on one page")
        self._fit_cb.setChecked(bool(st.get("fit_to_page", False)))
        self._fit_cb.toggled.connect(self._on_fit_toggled)
        self._scale_spin.setEnabled(not self._fit_cb.isChecked())
        sv.addWidget(self._fit_cb)
        sg.setLayout(sv)
        side.addWidget(sg)

        # Show options.
        vg = QGroupBox("Show")
        vv = QVBoxLayout()
        self._grid_cb = QCheckBox("Gridlines")
        self._head_cb = QCheckBox("Row / column headings")
        # Default to whatever the sheet currently shows.
        scr_grid = True
        scr_head = True
        if self._sheet is not None:
            scr_grid = self._sheet.table.showGrid()
            scr_head = self._sheet.table.horizontalHeader().isVisible()
        self._grid_cb.setChecked(st.get("show_gridlines", scr_grid))
        self._head_cb.setChecked(st.get("show_headings", scr_head))
        self._grid_cb.toggled.connect(self._refresh_preview)
        self._head_cb.toggled.connect(self._refresh_preview)
        vv.addWidget(self._grid_cb)
        vv.addWidget(self._head_cb)
        vg.setLayout(vv)
        side.addWidget(vg)

        side.addStretch(1)

        # Action buttons.
        btn_row = QHBoxLayout()
        print_btn = QPushButton("Print…")
        print_btn.setDefault(True)
        print_btn.clicked.connect(self._do_print)
        pdf_btn = QPushButton("Export PDF…")
        pdf_btn.clicked.connect(self._do_pdf)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(print_btn)
        btn_row.addWidget(pdf_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        side.addLayout(btn_row)

        side_w = QWidget()
        side_w.setLayout(side)
        side_w.setMaximumWidth(300)
        root.addWidget(side_w)

        # ── Right: live preview ──────────────────────────────────────
        self._printer = _make_printer(
            self._orientation(), self._paper_key(), self._margins)
        self._preview = QPrintPreviewWidget(self._printer, self)
        self._preview.paintRequested.connect(self._render_to)
        root.addWidget(self._preview, 1)

    # ── Control readouts ─────────────────────────────────────────────

    def _orientation(self):
        return ("landscape" if getattr(self, '_landscape_rb', None)
                and self._landscape_rb.isChecked() else "portrait")

    def _paper_key(self):
        return self._size_combo.currentData()

    def _read_margins(self):
        return {s: self._margin_spins[s].value()
                for s in self._margin_spins}

    def _on_fit_toggled(self, on):
        self._scale_spin.setEnabled(not on)
        self._refresh_preview()

    # ── Rendering ────────────────────────────────────────────────────

    def _make_renderer(self):
        what = self._what_combo.currentData()
        return SheetRenderer(
            self._sheet,
            margins_mm=self._read_margins(),
            orientation=self._orientation(),
            paper_mm=PAPER_SIZES.get(self._paper_key(), (210, 297)),
            scale_percent=self._scale_spin.value(),
            fit_to_page=self._fit_cb.isChecked(),
            selection_only=(what == "selection"),
            use_print_area=(what == "area"),
            sheet_name=self._sheet_name,
            show_gridlines=self._grid_cb.isChecked(),
            show_headings=self._head_cb.isChecked(),
        )

    def _render_to(self, printer):
        if self._sheet is None:
            return
        self._make_renderer().render(printer)

    def _refresh_preview(self):
        if self._preview is None:
            return
        self._margins = self._read_margins()
        self._printer.setOrientation(
            self._printer.Landscape if self._orientation() == "landscape"
            else self._printer.Portrait)
        size_map = {
            "A4": self._printer.A4, "A3": self._printer.A3,
            "Letter": self._printer.Letter, "Legal": self._printer.Legal,
            "B5": self._printer.B5,
        }
        self._printer.setPaperSize(
            size_map.get(self._paper_key(), self._printer.A4))
        try:
            m = self._margins
            self._printer.setPageMargins(
                m["left"], m["top"], m["right"], m["bottom"],
                self._printer.Millimeter)
        except Exception:
            pass
        self._preview.updatePreview()

    # ── Actions ──────────────────────────────────────────────────────

    def _do_print(self):
        from PyQt5.QtPrintSupport import QPrintDialog
        printer = _make_printer(
            self._orientation(), self._paper_key(), self._read_margins())
        dlg = QPrintDialog(printer, self)
        if dlg.exec_() == QDialog.Accepted:
            self._make_renderer().render(printer)
            self.accept()

    def _do_pdf(self):
        from PyQt5.QtPrintSupport import QPrinter
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        if not path.lower().endswith('.pdf'):
            path += '.pdf'
        printer = _make_printer(
            self._orientation(), self._paper_key(), self._read_margins())
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        self._make_renderer().render(printer)
        self._exported_path = path
        QMessageBox.information(self, "Export PDF",
                               f"Exported to:\n{path}")

    def _set_print_area(self):
        if self._sheet is None:
            return
        set_print_area(self._sheet, self._undo_stack)
        self._what_combo.setCurrentIndex(2)  # "area"
        self._refresh_preview()

    def _clear_print_area(self):
        if self._sheet is None:
            return
        clear_print_area(self._sheet, self._undo_stack)
        if self._what_combo.currentData() == "area":
            self._what_combo.setCurrentIndex(0)  # "active"
        self._refresh_preview()

    # ── Persisted state ──────────────────────────────────────────────

    def state(self) -> dict:
        return {
            "orientation": self._orientation(),
            "paper_key": self._paper_key(),
            "paper_mm": PAPER_SIZES.get(self._paper_key(), (210, 297)),
            "margins": self._read_margins(),
            "scale_percent": self._scale_spin.value(),
            "fit_to_page": self._fit_cb.isChecked(),
            "show_gridlines": self._grid_cb.isChecked(),
            "show_headings": self._head_cb.isChecked(),
        }


# ── Public API (called from MainWindow) ──────────────────────────────

def open_print_dialog(parent, sheet, *, state=None,
                      sheet_name="Sheet1", undo_stack=None):
    """Open the unified print dialog; return the (possibly updated) state."""
    dlg = PrintDialog(parent, sheet, state=state,
                      sheet_name=sheet_name, undo_stack=undo_stack)
    dlg.exec_()
    return dlg.state()


def set_print_area(sheet, undo_stack=None):
    """Set the print area to the current selection on *sheet*."""
    sel = sheet.table.selectedRanges()
    if not sel:
        return
    r1 = min(s.topRow() for s in sel)
    r2 = max(s.bottomRow() for s in sel)
    c1 = min(s.leftColumn() for s in sel)
    c2 = max(s.rightColumn() for s in sel)
    area = (r1, r2, c1, c2)
    cmd = SetPrintAreaCmd(sheet, area, "Set Print Area")
    if undo_stack:
        undo_stack.push(cmd)
    else:
        cmd.redo()


def clear_print_area(sheet, undo_stack=None):
    """Clear the print area on *sheet*."""
    cmd = SetPrintAreaCmd(sheet, None, "Clear Print Area")
    if undo_stack:
        undo_stack.push(cmd)
    else:
        cmd.redo()
