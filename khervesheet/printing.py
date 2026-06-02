"""Printing, print preview, page setup, and PDF export.

Renders spreadsheet grids to QPrinter with cell formatting, column/row
headers, pagination, and header/footer lines.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from PyQt5.QtCore import Qt, QRectF, QRect
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QGroupBox, QHBoxLayout, QVBoxLayout, QLabel, QComboBox,
    QCheckBox, QRadioButton, QSpinBox, QMessageBox,
    QFileDialog, QUndoCommand,
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


# ── Page Setup Dialog ────────────────────────────────────────────────

class PageSetupDialog(QDialog):
    """Dialog for margins, orientation, paper size, and scaling."""

    def __init__(self, parent=None, *,
                 margins=None, orientation="portrait",
                 paper_size="A4", scale_percent=100,
                 fit_to_page=False):
        super().__init__(parent)
        self.setWindowTitle("Page Setup")
        self.setMinimumWidth(380)

        self._margins = dict(margins or DEFAULT_MARGINS_MM)
        self._orientation = orientation
        self._paper_size = paper_size
        self._scale_percent = scale_percent
        self._fit_to_page = fit_to_page

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Margins ──────────────────────────────────────────────────
        mg = QGroupBox("Margins")
        mf = QFormLayout()
        self._margin_spins = {}
        for side in ("top", "bottom", "left", "right"):
            sp = QDoubleSpinBox()
            sp.setRange(0, 100)
            sp.setDecimals(1)
            sp.setSuffix(" mm")
            sp.setValue(self._margins.get(side, 25.4))
            mf.addRow(side.capitalize() + ":", sp)
            self._margin_spins[side] = sp
        mg.setLayout(mf)
        layout.addWidget(mg)

        # ── Orientation ──────────────────────────────────────────────
        og = QGroupBox("Orientation")
        oh = QHBoxLayout()
        self._portrait_rb = QRadioButton("Portrait")
        self._landscape_rb = QRadioButton("Landscape")
        if self._orientation == "landscape":
            self._landscape_rb.setChecked(True)
        else:
            self._portrait_rb.setChecked(True)
        oh.addWidget(self._portrait_rb)
        oh.addWidget(self._landscape_rb)
        og.setLayout(oh)
        layout.addWidget(og)

        # ── Paper Size ───────────────────────────────────────────────
        pg = QGroupBox("Paper Size")
        pf = QFormLayout()
        self._size_combo = QComboBox()
        for name in PAPER_SIZES:
            w, h = PAPER_SIZES[name]
            self._size_combo.addItem(f"{name} ({w:.0f} x {h:.0f} mm)", name)
        idx = list(PAPER_SIZES.keys()).index(self._paper_size) \
            if self._paper_size in PAPER_SIZES else 0
        self._size_combo.setCurrentIndex(idx)
        pf.addRow("Size:", self._size_combo)
        pg.setLayout(pf)
        layout.addWidget(pg)

        # ── Scaling ──────────────────────────────────────────────────
        sg = QGroupBox("Scaling")
        sv = QVBoxLayout()

        self._scale_pct_rb = QRadioButton("Scale to percentage:")
        self._fit_rb = QRadioButton("Fit all columns on one page")

        sh = QHBoxLayout()
        self._scale_spin = QSpinBox()
        self._scale_spin.setRange(10, 400)
        self._scale_spin.setSuffix(" %")
        self._scale_spin.setValue(self._scale_percent)
        sh.addWidget(self._scale_pct_rb)
        sh.addWidget(self._scale_spin)
        sv.addLayout(sh)
        sv.addWidget(self._fit_rb)

        if self._fit_to_page:
            self._fit_rb.setChecked(True)
        else:
            self._scale_pct_rb.setChecked(True)

        sg.setLayout(sv)
        layout.addWidget(sg)

        # ── Buttons ──────────────────────────────────────────────────
        bbox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    # ── Result accessors ─────────────────────────────────────────────

    def margins(self) -> dict:
        return {s: self._margin_spins[s].value()
                for s in self._margin_spins}

    def orientation(self) -> str:
        return "landscape" if self._landscape_rb.isChecked() else "portrait"

    def paper_size_key(self) -> str:
        return self._size_combo.currentData()

    def paper_size_mm(self) -> Tuple[float, float]:
        return PAPER_SIZES[self.paper_size_key()]

    def scale_percent(self) -> int:
        return self._scale_spin.value()

    def fit_to_page(self) -> bool:
        return self._fit_rb.isChecked()


# ── Sheet renderer ───────────────────────────────────────────────────

class SheetRenderer:
    """Render a SheetWidget's grid onto a QPrinter / QPdfWriter.

    Handles pagination, headers/footers, column letters, row numbers,
    cell formatting (font, colours, borders), and optional selection-only
    or print-area modes.
    """

    # Minimum row/col header widths (screen pixels, before scaling).
    ROW_HDR_WIDTH = 40
    HEADER_HEIGHT = 22

    def __init__(self, sheet, *,
                 margins_mm=None,
                 orientation="portrait",
                 paper_mm=None,
                 scale_percent=100,
                 fit_to_page=False,
                 selection_only=False,
                 sheet_name="Sheet1"):
        self._sheet = sheet
        self._margins = margins_mm or dict(DEFAULT_MARGINS_MM)
        self._orientation = orientation
        self._paper = paper_mm or (210, 297)
        self._scale_pct = scale_percent
        self._fit_to_page = fit_to_page
        self._selection_only = selection_only
        self._sheet_name = sheet_name

    # ── Public entry point ───────────────────────────────────────────

    # Logical page size — we work in these units and let Qt map to
    # the high-resolution device via setWindow / setViewport.
    _LOGICAL_W = 800
    _LOGICAL_H = 1130  # ~A4 aspect ratio

    def render(self, printer: "QPrinter"):
        """Paint the grid onto *printer* (may span multiple pages)."""
        table = self._sheet.table
        cell_formats = getattr(self._sheet, '_cell_formats', {})

        # Determine the cell range to print.
        r_start, r_end, c_start, c_end = self._cell_range(table)
        if r_end < r_start or c_end < c_start:
            return  # nothing to print

        # Collect column widths and row heights from the table widget.
        col_ws = [table.columnWidth(c) for c in range(c_start, c_end + 1)]
        row_hs = [table.rowHeight(r) for r in range(r_start, r_end + 1)]

        # ── Logical page geometry ────────────────────────────────────
        # Work entirely in logical units; setWindow maps them to device.
        page_w = self._LOGICAL_W
        page_h = self._LOGICAL_H
        if self._orientation == "landscape":
            page_w, page_h = page_h, page_w

        # Reserve space for header (sheet name) and footer (page number).
        hdr_footer_h = 20
        body_h = page_h - 2 * hdr_footer_h
        body_w = page_w

        # Account for row header column + column header row.
        data_w = body_w - self.ROW_HDR_WIDTH
        data_h = body_h - self.HEADER_HEIGHT

        # ── Compute scale ────────────────────────────────────────────
        total_col_w = sum(col_ws)
        if self._fit_to_page and total_col_w > 0:
            scale = min(data_w / total_col_w, 1.0)
        else:
            scale = self._scale_pct / 100.0

        # ── Paginate columns ─────────────────────────────────────────
        col_pages = self._paginate(col_ws, data_w / scale)
        row_pages = self._paginate(row_hs, data_h / scale)

        # Row header width and col header height in scaled coords.
        rh_w = self.ROW_HDR_WIDTH / scale
        ch_h = self.HEADER_HEIGHT / scale

        total_pages = len(col_pages) * len(row_pages)
        page_num = 0

        # Device page rect for viewport mapping.
        dev_rect = printer.pageRect()

        painter = QPainter(printer)
        painter.setRenderHint(QPainter.TextAntialiasing)

        for cp_idx, col_page in enumerate(col_pages):
            for rp_idx, row_page in enumerate(row_pages):
                if page_num > 0:
                    printer.newPage()
                page_num += 1

                painter.save()

                # Map logical coordinates to device pixels.  This lets
                # us draw in small logical units while Qt scales
                # geometry to the printer's native resolution.
                painter.setWindow(0, 0, page_w, page_h)
                painter.setViewport(dev_rect)

                # Fonts must use pixel sizes (in window units) because
                # point sizes would be interpreted at the printer's DPI
                # and then scaled again by the window/viewport mapping.
                hdr_font = QFont("Segoe UI")
                hdr_font.setPixelSize(11)
                hdr_font_s = QFont("Segoe UI", -1, QFont.Bold)
                hdr_font_s.setPixelSize(10)
                default_font = QFont("Segoe UI")
                default_font.setPixelSize(12)

                # Header line (sheet name — left, page info — right).
                painter.setFont(hdr_font)
                painter.setPen(QColor(80, 80, 80))
                hdr_rect = QRectF(0, 0, page_w, hdr_footer_h)
                painter.drawText(hdr_rect,
                                 Qt.AlignLeft | Qt.AlignVCenter,
                                 f"  {self._sheet_name}")
                painter.drawText(hdr_rect,
                                 Qt.AlignRight | Qt.AlignVCenter,
                                 f"Page {page_num} of {total_pages}  ")

                # Footer line.
                footer_y = page_h - hdr_footer_h
                ftr_rect = QRectF(0, footer_y, page_w, hdr_footer_h)
                painter.drawText(ftr_rect,
                                 Qt.AlignCenter | Qt.AlignVCenter,
                                 f"{self._sheet_name} - Page {page_num}")

                # Move origin below header, then scale for cell content.
                painter.translate(0, hdr_footer_h)
                painter.scale(scale, scale)

                # ── Column headers ───────────────────────────────────
                hdr_pen = QPen(QColor(100, 100, 100), 0.5)
                hdr_bg = QColor(230, 230, 230)
                painter.setFont(hdr_font_s)

                x = rh_w
                for local_c, (global_c, cw) in enumerate(col_page):
                    rect = QRectF(x, 0, cw, ch_h)
                    painter.fillRect(rect, hdr_bg)
                    painter.setPen(hdr_pen)
                    painter.drawRect(rect)
                    painter.setPen(QColor(60, 60, 60))
                    painter.drawText(rect, Qt.AlignCenter,
                                     _col_letter(global_c))
                    x += cw

                # ── Row headers + cells ──────────────────────────────
                y = ch_h
                grid_pen = QPen(QColor(180, 180, 180), 0.5)

                for local_r, (global_r, rh) in enumerate(row_page):
                    # Row number header.
                    rh_rect = QRectF(0, y, rh_w, rh)
                    painter.fillRect(rh_rect, hdr_bg)
                    painter.setPen(hdr_pen)
                    painter.drawRect(rh_rect)
                    painter.setFont(hdr_font_s)
                    painter.setPen(QColor(60, 60, 60))
                    painter.drawText(rh_rect, Qt.AlignCenter,
                                     str(global_r + 1))

                    x = rh_w
                    for local_c, (global_c, cw) in enumerate(col_page):
                        cell_rect = QRectF(x, y, cw, rh)

                        # Background fill.
                        fmt = cell_formats.get((global_r, global_c))
                        if fmt and getattr(fmt, 'bg_color', None):
                            painter.fillRect(
                                cell_rect, QColor(fmt.bg_color))

                        # Grid lines.
                        painter.setPen(grid_pen)
                        painter.drawRect(cell_rect)

                        # Cell borders (if formatting has them).
                        if fmt:
                            self._draw_borders(painter, cell_rect, fmt)

                        # Cell text.
                        it = table.item(global_r, global_c)
                        if it and it.text():
                            # Convert cell font to pixel-sized copy.
                            src = it.font()
                            if src.family():
                                font = QFont(src)
                            else:
                                font = QFont(default_font)
                            ps = src.pointSize()
                            font.setPixelSize(
                                max(int(ps * 1.33), 10) if ps > 0
                                else default_font.pixelSize())
                            painter.setFont(font)
                            fg = (it.foreground().color()
                                  if it.foreground().style()
                                  else QColor(0, 0, 0))
                            painter.setPen(fg)
                            align = (it.textAlignment()
                                     if it.textAlignment()
                                     else int(Qt.AlignLeft
                                              | Qt.AlignVCenter))
                            txt_rect = cell_rect.adjusted(3, 1, -3, -1)
                            painter.drawText(txt_rect, align, it.text())

                        x += cw
                    y += rh

                # ── Overlays (charts, images, shapes, equations) ─────
                # Only render on the first column/row page to avoid
                # duplicating overlays across paginated pages.
                if cp_idx == 0 and rp_idx == 0:
                    self._draw_overlays(painter, table, r_start,
                                        c_start, col_ws, row_hs,
                                        rh_w, ch_h)

                painter.restore()

        painter.end()

    # ── Overlay rendering ─────────────────────────────────────────────

    def _draw_overlays(self, painter, table, r_start, c_start,
                       col_ws, row_hs, rh_w, ch_h):
        """Grab and draw charts, images, shapes, equations onto the page.

        Each overlay is a QWidget parented to the table viewport.  We
        convert its viewport-pixel position to our print coordinate
        system using cumulative column widths and row heights.
        """
        overlays = []
        for attr in ('_charts', '_images', '_shapes', '_equations'):
            overlays.extend(getattr(self._sheet, attr, []))
        if not overlays:
            return

        # Build cumulative pixel offset → print offset maps.
        # Viewport pixel position of each column/row boundary.
        cum_col_px = [0]  # pixel x for column c_start
        for c in range(c_start, c_start + len(col_ws)):
            cum_col_px.append(cum_col_px[-1] + table.columnWidth(c))

        cum_row_px = [0]  # pixel y for row r_start
        for r in range(r_start, r_start + len(row_hs)):
            cum_row_px.append(cum_row_px[-1] + table.rowHeight(r))

        # Print-coordinate offsets for each column/row boundary.
        cum_col_pr = [0]
        for w in col_ws:
            cum_col_pr.append(cum_col_pr[-1] + w)

        cum_row_pr = [0]
        for h in row_hs:
            cum_row_pr.append(cum_row_pr[-1] + h)

        # Pixel offset of the top-left printed cell in the viewport.
        vp_x0 = table.columnViewportPosition(c_start)
        vp_y0 = table.rowViewportPosition(r_start)

        for widget in overlays:
            if not widget.isVisible():
                continue
            geom = widget.geometry()  # relative to table viewport

            # Widget position relative to the printed cell region.
            wx = geom.x() - vp_x0
            wy = geom.y() - vp_y0

            # Map viewport pixel position to print coordinates via
            # interpolation in the cumulative offset arrays.
            px = self._px_to_print(wx, cum_col_px, cum_col_pr) + rh_w
            py = self._px_to_print(wy, cum_row_px, cum_row_pr) + ch_h

            # Map widget size similarly.
            pw = self._px_to_print(wx + geom.width(), cum_col_px,
                                   cum_col_pr) + rh_w - px
            ph = self._px_to_print(wy + geom.height(), cum_row_px,
                                   cum_row_pr) + ch_h - py

            # Grab the widget as a pixmap.
            pixmap = widget.grab()
            target = QRectF(px, py, pw, ph)
            painter.drawPixmap(target.toRect(), pixmap)

    @staticmethod
    def _px_to_print(px_pos, cum_px, cum_pr):
        """Map a viewport pixel position to print coordinates.

        Uses the cumulative offset arrays to interpolate.
        """
        # Clamp to the range.
        if px_pos <= 0:
            return 0.0
        total_px = cum_px[-1] if cum_px else 1
        total_pr = cum_pr[-1] if cum_pr else 1
        if px_pos >= total_px:
            return float(total_pr)

        # Find which segment we're in.
        for i in range(1, len(cum_px)):
            if px_pos <= cum_px[i]:
                frac = ((px_pos - cum_px[i - 1])
                        / max(cum_px[i] - cum_px[i - 1], 1))
                return (cum_pr[i - 1]
                        + frac * (cum_pr[i] - cum_pr[i - 1]))
        return float(total_pr)

    # ── Helpers ──────────────────────────────────────────────────────

    def _cell_range(self, table):
        """Return (r_start, r_end, c_start, c_end) for the region to
        print.  Considers print area, selection, or used range."""
        # Print area takes priority.
        pa = getattr(self._sheet, '_print_area', None)
        if pa is not None:
            return pa  # (r1, r2, c1, c2)

        # Selection-only mode.
        if self._selection_only:
            sel = table.selectedRanges()
            if sel:
                r1 = min(s.topRow() for s in sel)
                r2 = max(s.bottomRow() for s in sel)
                c1 = min(s.leftColumn() for s in sel)
                c2 = max(s.rightColumn() for s in sel)
                return (r1, r2, c1, c2)

        # Fallback: used range (scan for non-empty cells).
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
    def _paginate(sizes, available):
        """Split a list of column widths or row heights into pages.

        Returns a list of pages, each page being a list of
        (global_index, size) tuples.
        """
        pages: list = []
        current_page: list = []
        used = 0.0
        for i, sz in enumerate(sizes):
            if current_page and used + sz > available:
                pages.append(current_page)
                current_page = []
                used = 0.0
            current_page.append((i, sz))
            used += sz
        if current_page:
            pages.append(current_page)
        # Adjust global indices: paginate receives sizes for a sub-range
        # starting at index 0 within the col_ws / row_hs list.  The
        # caller already sliced, so we need to offset by the range start.
        return pages if pages else [[(0, 0)]]

    @staticmethod
    def _draw_borders(painter, rect, fmt):
        """Draw cell borders from a CellFormat, if present."""
        borders = getattr(fmt, 'borders', None)
        if not borders:
            return
        for side in ('top', 'bottom', 'left', 'right'):
            spec = getattr(borders, side, None) if borders else None
            if not spec:
                continue
            color = QColor(getattr(spec, 'color', '#000000'))
            width = getattr(spec, 'width', 1)
            pen = QPen(color, width)
            style_map = {
                'dash': Qt.DashLine,
                'dot': Qt.DotLine,
                'dashdot': Qt.DashDotLine,
            }
            pen.setStyle(style_map.get(
                getattr(spec, 'style', 'solid'), Qt.SolidLine))
            painter.setPen(pen)
            if side == 'top':
                painter.drawLine(rect.topLeft(), rect.topRight())
            elif side == 'bottom':
                painter.drawLine(rect.bottomLeft(), rect.bottomRight())
            elif side == 'left':
                painter.drawLine(rect.topLeft(), rect.bottomLeft())
            elif side == 'right':
                painter.drawLine(rect.topRight(), rect.bottomRight())


# ── Public API (called from MainWindow) ──────────────────────────────

def _make_printer(orientation="portrait", paper_key="A4",
                  margins_mm=None):
    """Create and configure a QPrinter."""
    from PyQt5.QtPrintSupport import QPrinter
    printer = QPrinter(QPrinter.HighResolution)
    if orientation == "landscape":
        printer.setOrientation(QPrinter.Landscape)
    else:
        printer.setOrientation(QPrinter.Portrait)

    # Paper size.
    size_map = {
        "A4": QPrinter.A4,
        "A3": QPrinter.A3,
        "Letter": QPrinter.Letter,
        "Legal": QPrinter.Legal,
        "B5": QPrinter.B5,
    }
    printer.setPaperSize(size_map.get(paper_key, QPrinter.A4))

    # Margins.
    m = margins_mm or DEFAULT_MARGINS_MM
    try:
        printer.setPageMargins(
            m["left"], m["top"], m["right"], m["bottom"],
            QPrinter.Millimeter)
    except Exception:
        pass
    return printer


def print_preview(parent, sheet, *,
                  orientation="portrait", paper_key="A4",
                  margins_mm=None, scale_percent=100,
                  fit_to_page=False, sheet_name="Sheet1"):
    """Show a QPrintPreviewDialog for *sheet*."""
    from PyQt5.QtPrintSupport import QPrintPreviewDialog
    printer = _make_printer(orientation, paper_key, margins_mm)
    renderer = SheetRenderer(
        sheet,
        margins_mm=margins_mm,
        orientation=orientation,
        paper_mm=PAPER_SIZES.get(paper_key, (210, 297)),
        scale_percent=scale_percent,
        fit_to_page=fit_to_page,
        sheet_name=sheet_name,
    )
    preview = QPrintPreviewDialog(printer, parent)
    preview.paintRequested.connect(renderer.render)
    preview.exec_()


def print_direct(parent, sheet, **kwargs):
    """Open a QPrintDialog then print *sheet*."""
    from PyQt5.QtPrintSupport import QPrintDialog
    printer = _make_printer(
        kwargs.get("orientation", "portrait"),
        kwargs.get("paper_key", "A4"),
        kwargs.get("margins_mm"),
    )
    dlg = QPrintDialog(printer, parent)
    if dlg.exec_() == QDialog.Accepted:
        renderer = SheetRenderer(sheet, **_renderer_kwargs(kwargs))
        renderer.render(printer)


def print_selection(parent, sheet, **kwargs):
    """Print only the currently selected cells."""
    from PyQt5.QtPrintSupport import QPrintDialog
    printer = _make_printer(
        kwargs.get("orientation", "portrait"),
        kwargs.get("paper_key", "A4"),
        kwargs.get("margins_mm"),
    )
    dlg = QPrintDialog(printer, parent)
    if dlg.exec_() == QDialog.Accepted:
        kw = _renderer_kwargs(kwargs)
        kw["selection_only"] = True
        renderer = SheetRenderer(sheet, **kw)
        renderer.render(printer)


def export_pdf(parent, sheet, **kwargs):
    """Export *sheet* to a PDF file chosen by the user."""
    path, _ = QFileDialog.getSaveFileName(
        parent, "Export to PDF", "", "PDF Files (*.pdf)")
    if not path:
        return
    if not path.lower().endswith('.pdf'):
        path += '.pdf'

    from PyQt5.QtPrintSupport import QPrinter
    printer = _make_printer(
        kwargs.get("orientation", "portrait"),
        kwargs.get("paper_key", "A4"),
        kwargs.get("margins_mm"),
    )
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(path)

    renderer = SheetRenderer(sheet, **_renderer_kwargs(kwargs))
    renderer.render(printer)
    return path


def page_setup(parent, *, margins=None, orientation="portrait",
               paper_key="A4", scale_percent=100, fit_to_page=False):
    """Open PageSetupDialog and return the result dict, or None."""
    dlg = PageSetupDialog(
        parent,
        margins=margins,
        orientation=orientation,
        paper_size=paper_key,
        scale_percent=scale_percent,
        fit_to_page=fit_to_page,
    )
    if dlg.exec_() == QDialog.Accepted:
        return {
            "margins": dlg.margins(),
            "orientation": dlg.orientation(),
            "paper_key": dlg.paper_size_key(),
            "paper_mm": dlg.paper_size_mm(),
            "scale_percent": dlg.scale_percent(),
            "fit_to_page": dlg.fit_to_page(),
        }
    return None


def set_print_area(sheet, undo_stack=None):
    """Set the print area to the current selection on *sheet*.

    Pushes an undoable command if *undo_stack* is provided.
    """
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


# ── Internal helpers ─────────────────────────────────────────────────

def _renderer_kwargs(kw: dict) -> dict:
    """Extract SheetRenderer keyword arguments from a flat dict."""
    return {
        "margins_mm": kw.get("margins_mm"),
        "orientation": kw.get("orientation", "portrait"),
        "paper_mm": kw.get("paper_mm") or PAPER_SIZES.get(
            kw.get("paper_key", "A4"), (210, 297)),
        "scale_percent": kw.get("scale_percent", 100),
        "fit_to_page": kw.get("fit_to_page", False),
        "sheet_name": kw.get("sheet_name", "Sheet1"),
    }
