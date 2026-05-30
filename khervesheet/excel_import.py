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

from .sheet import col_index_to_letter


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


def import_textboxes(path, sheet_by_title):
    """Parse drawing XML for floating text boxes and surface their text
    as yellow notes anchored at each box's top-left cell."""
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

                d_root = ET.fromstring(zf.read(draw_path))
                for anc in list(d_root):
                    sp = anc.find("xdr:sp", _NS)
                    if sp is None:
                        continue
                    text = _sp_text(sp)
                    if not text:
                        continue
                    frm = anc.find("xdr:from", _NS)
                    row = col = 0
                    if frm is not None:
                        rc = frm.find("xdr:row", _NS)
                        cc = frm.find("xdr:col", _NS)
                        if rc is not None and rc.text:
                            row = int(rc.text)
                        if cc is not None and cc.text:
                            col = int(cc.text)
                    if (row, col) in sheet._cell_notes:
                        continue
                    sheet._cell_notes[(row, col)] = {
                        "text": text, "kind": "note"}
                    _ensure_item(sheet, row, col)
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
