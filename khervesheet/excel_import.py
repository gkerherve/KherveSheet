"""Excel import extras — reconstruct embedded charts, pictures and
floating text boxes from an .xlsx workbook (cell comments are handled
inline by the main loader).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import posixpath
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
from PyQt5.QtCore import Qt

from .cellformat import BorderSpec, CellFormat
from .sheet import col_index_to_letter
from .core.xlsx import (  # noqa: F401 (shared with KherveCELL)
    _DEFAULT_THEME, _TYPE_MAP, _apply_tint, _argb_to_hex, _color_hex,
    _parse_ref, _series_ref, _series_title, build_theme_palette,
)


# ── Cell formatting (fill, font, borders, alignment) ───────────────────

_BORDER_MAP = {
    "thin": (Qt.SolidLine, 1.0),
    "medium": (Qt.SolidLine, 2.0),
    "thick": (Qt.SolidLine, 3.0),
    "dashed": (Qt.DashLine, 1.0),
    "mediumDashed": (Qt.DashLine, 2.0),
    "dotted": (Qt.DotLine, 1.0),
    "double": (Qt.SolidLine, 2.5),
    "hair": (Qt.SolidLine, 0.5),
    "dashDot": (Qt.DashDotLine, 1.0),
    "dashDotDot": (Qt.DashDotDotLine, 1.0),
}

_ALIGN_MAP = {
    "left": Qt.AlignLeft,
    "center": Qt.AlignHCenter,
    "centerContinuous": Qt.AlignHCenter,
    "right": Qt.AlignRight,
    "justify": Qt.AlignJustify,
}


def _border_spec(side, palette):
    style = getattr(side, "style", None) if side is not None else None
    if not style:
        return None
    qstyle, width = _BORDER_MAP.get(style, (Qt.SolidLine, 1.0))
    col = _color_hex(getattr(side, "color", None), palette) or "#000000"
    return BorderSpec(style=int(qstyle), color=col, width=width)


def cell_format_from_xl(cell, palette):
    """Build a CellFormat from an openpyxl cell's style, or None when
    the cell carries no non-default visual formatting."""
    cf = CellFormat()
    used = False

    f = getattr(cell, "font", None)
    if f is not None:
        if f.bold:
            cf.bold = True
            used = True
        if f.italic:
            cf.italic = True
            used = True
        if f.underline:
            cf.underline = True
            used = True
        fc = _color_hex(f.color, palette)
        if fc and fc != "#000000":
            cf.font_color = fc
            used = True

    fill = getattr(cell, "fill", None)
    if fill is not None and getattr(fill, "patternType", None) == "solid":
        bg = _color_hex(fill.fgColor, palette)
        if bg:
            cf.bg_color = bg
            used = True

    al = getattr(cell, "alignment", None)
    if al is not None:
        if al.horizontal in _ALIGN_MAP:
            cf.alignment = int(_ALIGN_MAP[al.horizontal] | Qt.AlignVCenter)
            used = True
        if al.wrap_text:
            cf.wrap_text = True
            used = True

    b = getattr(cell, "border", None)
    if b is not None:
        for side, attr in (("top", "border_top"),
                           ("bottom", "border_bottom"),
                           ("left", "border_left"),
                           ("right", "border_right")):
            spec = _border_spec(getattr(b, side, None), palette)
            if spec is not None:
                setattr(cf, attr, spec)
                used = True

    return cf if used else None


# ── Chart import (via openpyxl chart objects) ──────────────────────────

def _place_chart(chart, sheet, ch):
    table = sheet.table
    anc = getattr(ch, "anchor", None)
    frm = getattr(anc, "_from", None)
    if frm is not None and hasattr(frm, "col"):
        col = int(frm.col)
        row = int(frm.row)
        x_px = sum(table.columnWidth(c) for c in range(col))
        y_px = sum(table.rowHeight(r) for r in range(row))
        chart.move(x_px, y_px)
        to = getattr(anc, "to", None)
        if to is not None and hasattr(to, "col"):
            w = sum(table.columnWidth(c) for c in range(col, int(to.col)))
            h = sum(table.rowHeight(r) for r in range(row, int(to.row)))
            if w > 60 and h > 60:
                chart.resize(max(240, w), max(180, h))
    else:
        off = len(sheet._charts) * 30
        chart.move(40 + off, 40 + off)


def import_charts(sheet, ws_f, sheet_by_title):
    """Reconstruct EmbeddedCharts on *sheet* from a worksheet's native
    Excel charts.  Styling is best-effort (type, series, titles)."""
    charts = list(getattr(ws_f, "_charts", []) or [])
    if not charts:
        return
    from .graph import EmbeddedChart
    if not hasattr(sheet, "_charts"):
        sheet._charts = []

    for ch in charts:
        plot_type = _TYPE_MAP.get(getattr(ch, "tagname", ""), "Line")
        first = None
        for ser in (getattr(ch, "series", []) or []):
            # Line/bar series carry y in .val; scatter in .yVal.
            yp = _parse_ref(_series_ref(getattr(ser, "val", None))
                            or _series_ref(getattr(ser, "yVal", None)))
            if not yp:
                continue
            ytitle, ycol, yr0, yr1 = yp
            data_sheet = sheet_by_title.get(ytitle) or sheet

            xref = (_series_ref(getattr(ser, "xVal", None))
                    or _series_ref(getattr(ser, "cat", None)))
            xp = _parse_ref(xref)
            if xp:
                xcol = xp[1]
                x = data_sheet.numeric_column(xcol)[yr0:yr1 + 1]
            else:
                xcol = None
                x = np.arange(yr1 - yr0 + 1, dtype=float)
            y = data_sheet.numeric_column(ycol)[yr0:yr1 + 1]

            n = min(len(x), len(y))
            x, y = x[:n], y[:n]
            mask = ~(np.isnan(x) | np.isnan(y))
            x, y = x[mask], y[mask]
            if len(x) == 0:
                continue
            label = _series_title(ser) or col_index_to_letter(ycol)

            if first is None:
                chart = EmbeddedChart(
                    x, y, label, plot_type, data_sheet,
                    sheet.table.viewport(),
                    x_col=xcol, y_col=ycol, row_start=yr0, row_end=yr1)
                _place_chart(chart, sheet, ch)
                sheet._charts.append(chart)
                data_sheet.data_changed.connect(chart._on_data_changed)
                first = chart
            else:
                first.add_series(x, y, label, plot_type, x_col=xcol,
                                 y_col=ycol, row_start=yr0, row_end=yr1)


# ── Drawing import: text boxes + pictures (raw drawing XML —
#    openpyxl can't read shapes, and drops pictures without Pillow) ──────

_NS = {
    "or": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
_R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_R_EMBED = ("{http://schemas.openxmlformats.org/officeDocument"
            "/2006/relationships}embed")

# OpenXML drawing offsets are in EMU; 9525 EMU per screen pixel (96 dpi).
_EMU_PER_PX = 9525


def _resolve(base, target):
    # Absolute targets ('/xl/media/image1.png', as written by openpyxl)
    # are package-root relative; zip entry names carry no leading slash.
    if target.startswith("/"):
        return posixpath.normpath(target).lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(base), target))


def _read_rels(zf, names, rels_path):
    """Return {rId: resolved_target} for a .rels part."""
    out = {}
    if rels_path not in names:
        return out
    root = ET.fromstring(zf.read(rels_path))
    for rel in root.findall("pr:Relationship", _NS):
        out[rel.get("Id")] = _resolve(rels_path.replace("_rels/", ""),
                                      rel.get("Target"))
    return out


def _sp_text(sp):
    paras = []
    for p in sp.findall(".//a:p", _NS):
        runs = [t.text or "" for t in p.findall(".//a:t", _NS)]
        paras.append("".join(runs))
    return "\n".join(paras).strip()


def _sp_fill(sp):
    """Return the shape's solid fill colour as #RRGGBB, or None."""
    sppr = sp.find("xdr:spPr", _NS)
    if sppr is None:
        return None
    fill = sppr.find("a:solidFill", _NS)
    if fill is None:
        return None
    srgb = fill.find("a:srgbClr", _NS)
    if srgb is not None and srgb.get("val"):
        return "#" + srgb.get("val").upper()
    return None


def _sp_outline(sp):
    """Return (colour #RRGGBB or None, width_pts float) for the line."""
    sppr = sp.find("xdr:spPr", _NS)
    if sppr is None:
        return None, 1.0
    ln = sppr.find("a:ln", _NS)
    if ln is None:
        return "#000000", 1.0
    col = None
    sf = ln.find("a:solidFill", _NS)
    if sf is not None:
        srgb = sf.find("a:srgbClr", _NS)
        if srgb is not None and srgb.get("val"):
            col = "#" + srgb.get("val").upper()
    w = ln.get("w")
    width = (int(w) / 12700.0) if w else 1.0   # EMU → points
    return col, max(0.5, width)


def _anchor_cell(node):
    """Return (col, row) ints from an xdr:from / xdr:to node."""
    if node is None:
        return None
    cc = node.find("xdr:col", _NS)
    rc = node.find("xdr:row", _NS)
    col = int(cc.text) if cc is not None and cc.text else 0
    row = int(rc.text) if rc is not None and rc.text else 0
    return col, row


def _col_x(table, col):
    """Pixel x of a column edge; columns beyond the table's current
    extent count at the default section width."""
    n = table.columnCount()
    x = sum(table.columnWidth(c) for c in range(min(col, n)))
    if col > n:
        x += (col - n) * max(
            table.horizontalHeader().defaultSectionSize(), 1)
    return x


def _row_y(table, row):
    """Pixel y of a row edge; rows beyond the table's current extent
    count at the default section height."""
    n = table.rowCount()
    y = sum(table.rowHeight(r) for r in range(min(row, n)))
    if row > n:
        y += (row - n) * max(
            table.verticalHeader().defaultSectionSize(), 1)
    return y


def _anchor_px(node, table):
    """Resolve an xdr:from / xdr:to node to viewport pixel coordinates,
    including the sub-cell EMU offsets.  Returns (x, y) or None."""
    if node is None:
        return None

    def _num(tag):
        el = node.find(tag, _NS)
        try:
            return int(el.text) if el is not None and el.text else 0
        except ValueError:
            return 0

    return (_col_x(table, _num("xdr:col"))
            + _num("xdr:colOff") // _EMU_PER_PX,
            _row_y(table, _num("xdr:row"))
            + _num("xdr:rowOff") // _EMU_PER_PX)


def _import_picture(zf, names, anc, pic, draw_rels, sheet):
    """Recreate one <xdr:pic> as an EmbeddedImage on *sheet*.  Returns
    True when an image was placed."""
    from PyQt5.QtGui import QPixmap
    from .embedded_image import EmbeddedImage

    blip = pic.find("xdr:blipFill/a:blip", _NS)
    if blip is None:
        return False
    target = draw_rels.get(blip.get(_R_EMBED))
    if not target or target not in names:
        return False
    pm = QPixmap()
    if not pm.loadFromData(zf.read(target)) or pm.isNull():
        return False   # unsupported format (e.g. EMF/WMF)

    table = sheet.table
    frm = _anchor_px(anc.find("xdr:from", _NS), table)
    if frm is None:
        # absoluteAnchor positions in raw EMU instead of cell anchors.
        pos = anc.find("xdr:pos", _NS)
        if pos is None:
            return False
        frm = (int(pos.get("x") or 0) // _EMU_PER_PX,
               int(pos.get("y") or 0) // _EMU_PER_PX)
    x_px, y_px = frm

    # Size: twoCellAnchor carries xdr:to; one/absoluteAnchor carry xdr:ext.
    w_px = h_px = 0
    to = _anchor_px(anc.find("xdr:to", _NS), table)
    if to is not None:
        w_px, h_px = to[0] - x_px, to[1] - y_px
    else:
        ext = anc.find("xdr:ext", _NS)
        if ext is not None:
            w_px = int(ext.get("cx") or 0) // _EMU_PER_PX
            h_px = int(ext.get("cy") or 0) // _EMU_PER_PX

    img = EmbeddedImage(pm, table.viewport())
    img.move(max(0, x_px), max(0, y_px))
    if w_px > 10 and h_px > 10:
        img.resize(w_px, h_px)
        img._aspect_ratio = w_px / max(h_px, 1)
    if not hasattr(sheet, "_images"):
        sheet._images = []
    sheet._images.append(img)
    img.show()
    return True


def import_drawings(path, sheet_by_title):
    """Parse drawing XML for floating text boxes and pictures, and
    recreate them as EmbeddedShape rectangles / EmbeddedImages
    positioned and sized from their cell anchors."""
    from .shapes import EmbeddedShape
    touched = set()
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            if "xl/workbook.xml" not in names:
                return
            wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
            wb_rels = _read_rels(zf, names, "xl/_rels/workbook.xml.rels")

            for sh in wb_root.iter(
                    "{http://schemas.openxmlformats.org/"
                    "spreadsheetml/2006/main}sheet"):
                name = sh.get("name")
                sheet = sheet_by_title.get(name)
                if sheet is None:
                    continue
                ws_path = wb_rels.get(sh.get(_R_ID))
                if not ws_path or ws_path not in names:
                    continue
                ws_rels_path = (posixpath.dirname(ws_path) + "/_rels/"
                                + posixpath.basename(ws_path) + ".rels")
                ws_rels = _read_rels(zf, names, ws_rels_path)
                draw_path = next(
                    (t for t in ws_rels.values()
                     if "drawings/" in t and t.endswith(".xml")), None)
                if not draw_path or draw_path not in names:
                    continue

                if not hasattr(sheet, "_shapes"):
                    sheet._shapes = []
                table = sheet.table
                viewport = table.viewport()
                draw_rels = _read_rels(
                    zf, names,
                    posixpath.dirname(draw_path) + "/_rels/"
                    + posixpath.basename(draw_path) + ".rels")

                d_root = ET.fromstring(zf.read(draw_path))
                for anc in list(d_root):
                    # Pictures (including those nested in group shapes).
                    for pic in anc.findall(".//xdr:pic", _NS):
                        try:
                            if _import_picture(zf, names, anc, pic,
                                               draw_rels, sheet):
                                touched.add(sheet)
                        except Exception:
                            pass
                    sp = anc.find("xdr:sp", _NS)
                    if sp is None:
                        continue
                    text = _sp_text(sp)
                    if not text:
                        continue
                    frm = _anchor_cell(anc.find("xdr:from", _NS))
                    if frm is None:
                        continue
                    col, row = frm
                    x_px = sum(table.columnWidth(c) for c in range(col))
                    y_px = sum(table.rowHeight(r) for r in range(row))
                    to = _anchor_cell(anc.find("xdr:to", _NS))
                    w_px, h_px = 160, 90
                    if to is not None:
                        tc, tr = to
                        if tc > col:
                            w_px = sum(table.columnWidth(c)
                                       for c in range(col, tc))
                        if tr > row:
                            h_px = sum(table.rowHeight(r)
                                       for r in range(row, tr))

                    shape = EmbeddedShape("rectangle", viewport)
                    fill = _sp_fill(sp) or "#FFFFCC"
                    ocol, owidth = _sp_outline(sp)
                    shape._fill_color = fill
                    shape._outline_color = ocol or "#000000"
                    shape._outline_width = owidth
                    shape._text = text
                    shape.move(x_px, y_px)
                    shape.resize(max(60, w_px), max(30, h_px))
                    shape.show()
                    sheet._shapes.append(shape)
                    touched.add(sheet)
    except Exception:
        return
    for sheet in touched:
        sheet.table.viewport().update()


def _ensure_item(sheet, row, col):
    from PyQt5.QtWidgets import QTableWidgetItem
    if row >= sheet.table.rowCount():
        sheet.table.setRowCount(row + 1)
    if col >= sheet.table.columnCount():
        sheet.table.setColumnCount(col + 1)
    if sheet.table.item(row, col) is None:
        sheet.table.setItem(row, col, QTableWidgetItem(""))
