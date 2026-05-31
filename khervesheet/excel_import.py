"""Excel import extras — reconstruct embedded charts and floating
text boxes from an .xlsx workbook (cell comments are handled inline by
the main loader).

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


# ── Cell formatting (fill, font, borders, alignment) ───────────────────

# Default Office theme palette, ordered by the *style* theme index
# (0=background1/lt1, 1=text1/dk1, 2=lt2, 3=dk2, 4..9=accent1..6,
# 10=hlink, 11=folHlink).  Used as a fallback when the workbook theme
# can't be parsed.
_DEFAULT_THEME = [
    "#FFFFFF", "#000000", "#E7E6E6", "#44546A",
    "#4472C4", "#ED7D31", "#A5A5A5", "#FFC000",
    "#5B9BD5", "#70AD47", "#0563C1", "#954F72",
]

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


def _argb_to_hex(s):
    """'00FFFF99'/'FFFF0000'/'000000' -> '#RRGGBB' (alpha dropped)."""
    if not isinstance(s, str):
        return None
    if len(s) == 8:
        s = s[2:]
    if len(s) == 6:
        return "#" + s.upper()
    return None


def _apply_tint(hex_color, tint):
    """Lighten/darken a #RRGGBB color by an OpenXML tint factor."""
    if not tint:
        return hex_color
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
    except (ValueError, IndexError):
        return hex_color

    def adj(c):
        c = c * (1 + tint) if tint < 0 else c * (1 - tint) + 255 * tint
        return max(0, min(255, int(round(c))))

    return f"#{adj(r):02X}{adj(g):02X}{adj(b):02X}"


def build_theme_palette(wb):
    """Parse the workbook's theme colour scheme into the indexed list
    used by style theme references.  Falls back to the Office default."""
    raw = getattr(wb, "loaded_theme", None)
    if not raw:
        return list(_DEFAULT_THEME)
    try:
        ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        root = ET.fromstring(raw)
        scheme = root.find(".//a:clrScheme", ns)
        by_name = {}
        for child in scheme:
            name = child.tag.split("}")[-1]
            srgb = child.find("a:srgbClr", ns)
            sysc = child.find("a:sysClr", ns)
            if srgb is not None:
                by_name[name] = "#" + srgb.get("val").upper()
            elif sysc is not None:
                by_name[name] = "#" + (
                    sysc.get("lastClr") or "000000").upper()
        order = ["lt1", "dk1", "lt2", "dk2", "accent1", "accent2",
                 "accent3", "accent4", "accent5", "accent6",
                 "hlink", "folHlink"]
        pal = [by_name.get(n) or _DEFAULT_THEME[i]
               for i, n in enumerate(order)]
        return pal
    except Exception:
        return list(_DEFAULT_THEME)


def _color_hex(color, palette):
    """Resolve an openpyxl Color (rgb/theme/indexed) to '#RRGGBB'."""
    if color is None:
        return None
    ctype = getattr(color, "type", None)
    if ctype == "rgb":
        return _argb_to_hex(getattr(color, "rgb", None))
    if ctype == "theme":
        try:
            idx = int(color.theme)
        except (TypeError, ValueError):
            return None
        if 0 <= idx < len(palette):
            return _apply_tint(palette[idx], float(getattr(color, "tint", 0)
                                                  or 0))
        return None
    if ctype == "indexed":
        from openpyxl.styles.colors import COLOR_INDEX
        try:
            idx = int(color.indexed)
        except (TypeError, ValueError):
            return None
        if 0 <= idx < len(COLOR_INDEX):
            return _argb_to_hex(COLOR_INDEX[idx])
    return None


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

_TYPE_MAP = {
    "lineChart": "Line", "line3DChart": "Line",
    "scatterChart": "Scatter",
    "barChart": "Bar", "bar3DChart": "Bar",
    "areaChart": "Line", "area3DChart": "Line",
}


def _parse_ref(ref):
    """Parse an Excel range ref ('Sheet1!$L$2:$L$252' or 'L2:L252')
    into (sheet_title|None, col0, row_start0, row_end0).  0-based."""
    if not ref:
        return None
    from openpyxl.utils import range_boundaries
    title = None
    rng = ref
    if "!" in ref:
        title, rng = ref.rsplit("!", 1)
        title = title.strip().strip("'").replace("''", "'")
    rng = rng.replace("$", "")
    try:
        min_col, min_row, max_col, max_row = range_boundaries(rng)
    except Exception:
        return None
    return title, min_col - 1, min_row - 1, max_row - 1


def _series_ref(src):
    """Return the .f range string from a num/str data source, or None."""
    if src is None:
        return None
    for attr in ("numRef", "strRef", "multiLvlStrRef"):
        ref = getattr(src, attr, None)
        if ref is not None and getattr(ref, "f", None):
            return ref.f
    return None


def _series_title(ser):
    tx = getattr(ser, "tx", None)
    if tx is None:
        return None
    v = getattr(tx, "v", None)
    if v:
        return str(v)
    sref = getattr(tx, "strRef", None)
    if sref is not None:
        cache = getattr(sref, "strCache", None)
        pts = getattr(cache, "pt", None) if cache is not None else None
        if pts:
            return str(pts[0].v)
        return sref.f
    return None


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


# ── Text-box import (raw drawing XML — openpyxl can't read shapes) ──────

_NS = {
    "or": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
_R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _resolve(base, target):
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


def import_textboxes(path, sheet_by_title):
    """Parse drawing XML for floating text boxes and recreate them as
    real EmbeddedShape rectangles (with fill, outline and editable text)
    positioned/sized from their cell anchors."""
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

                d_root = ET.fromstring(zf.read(draw_path))
                for anc in list(d_root):
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
