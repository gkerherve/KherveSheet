"""Rich Excel (.xlsx) export — formatting, merged cells, charts, images.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
import re
from typing import TYPE_CHECKING

from PyQt5.QtCore import Qt

if TYPE_CHECKING:
    from .sheet import SheetWidget


# ── Pixel ↔ Excel unit conversions ───────────────────────────────────
# Excel column width ≈ (pixels - 5) / 7  (at 96 dpi, Calibri 11).
# Excel row height is in points (1 pt = 1.333 px at 96 dpi).
_PX_PER_COL_UNIT = 7.0
_COL_PADDING = 5
_PX_PER_PT = 96.0 / 72.0  # 1.333…


def _px_to_col_width(px: int) -> float:
    """Convert pixel width to Excel column-width units."""
    return max(0.0, (px - _COL_PADDING) / _PX_PER_COL_UNIT)


def _px_to_row_height(px: int) -> float:
    """Convert pixel height to Excel row-height points."""
    return max(0.0, px / _PX_PER_PT)


# ── Qt → openpyxl style helpers ──────────────────────────────────────

def _hex_to_argb(hex_color: str) -> str:
    """Convert '#RRGGBB' or '#AARRGGBB' to 8-char ARGB for openpyxl."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        return "FF" + h.upper()
    if len(h) == 8:
        return h.upper()
    return "FF000000"


def _qt_border_style(qt_style: int) -> str:
    """Map Qt pen style to openpyxl border style name."""
    mapping = {
        Qt.SolidLine: "thin",
        Qt.DashLine: "dashed",
        Qt.DotLine: "dotted",
        Qt.DashDotLine: "dashDot",
        Qt.DashDotDotLine: "dashDotDot",
    }
    return mapping.get(qt_style, "thin")


def _make_side(border_spec):
    """Convert a BorderSpec to an openpyxl Side."""
    from openpyxl.styles import Side
    from openpyxl.styles.colors import Color
    if border_spec is None:
        return Side()
    style = _qt_border_style(border_spec.style)
    if border_spec.width >= 2.5:
        style = "thick" if style == "thin" else style
    elif border_spec.width >= 1.5:
        style = "medium" if style == "thin" else style
    return Side(style=style,
                color=Color(rgb=_hex_to_argb(border_spec.color)))


def _qt_alignment_to_xl(qt_align: int):
    """Convert Qt alignment flags to openpyxl horizontal/vertical strings."""
    horiz = "general"
    if qt_align & Qt.AlignLeft:
        horiz = "left"
    elif qt_align & Qt.AlignHCenter:
        horiz = "center"
    elif qt_align & Qt.AlignRight:
        horiz = "right"

    vert = "bottom"
    if qt_align & Qt.AlignTop:
        vert = "top"
    elif qt_align & Qt.AlignVCenter:
        vert = "center"

    return horiz, vert


def _convert_number_format(fmt: str) -> str:
    """Convert KherveSheet number format string to Excel number format."""
    if not fmt or fmt == "General":
        return "General"
    if fmt == "Text":
        return "@"
    # Fixed decimal: "0", "0.0", "0.00", …
    if fmt.startswith("0"):
        return fmt
    # Scientific
    if fmt == "Scientific" or fmt.startswith("Sci:"):
        dec = 2
        if fmt.startswith("Sci:"):
            try:
                dec = int(fmt.split(":")[1])
            except (IndexError, ValueError):
                pass
        return "0." + "0" * dec + "E+00"
    # Percentage
    if fmt == "Percentage":
        return "0.00%"
    # Currency
    if fmt.startswith("Currency"):
        sym = "$"
        if ":" in fmt:
            sym = fmt.split(":", 1)[1]
        return f'{sym}#,##0.00'
    # Date
    if fmt.startswith("Date"):
        # Convert strftime patterns to Excel date format codes
        pattern = "yyyy-mm-dd"
        if ":" in fmt:
            py_pat = fmt.split(":", 1)[1]
            pattern = (py_pat
                       .replace("%Y", "yyyy")
                       .replace("%y", "yy")
                       .replace("%m", "mm")
                       .replace("%d", "dd")
                       .replace("%B", "mmmm")
                       .replace("%b", "mmm"))
        return pattern
    # Time
    if fmt.startswith("Time"):
        pattern = "hh:mm:ss"
        if ":" in fmt:
            py_pat = fmt.split(":", 1)[1]
            pattern = (py_pat
                       .replace("%H", "hh")
                       .replace("%M", "mm")
                       .replace("%S", "ss")
                       .replace("%I", "hh")
                       .replace("%p", "AM/PM"))
        return pattern
    return "General"


def _apply_cell_format(ws_cell, cf):
    """Apply a CellFormat to an openpyxl cell."""
    from openpyxl.styles import Font, PatternFill, Border, Alignment

    # Font
    font_kw = {}
    if cf.bold is not None:
        font_kw["bold"] = cf.bold
    if cf.italic is not None:
        font_kw["italic"] = cf.italic
    if cf.underline is not None:
        font_kw["underline"] = "single" if cf.underline else None
    if cf.font_family is not None:
        font_kw["name"] = cf.font_family
    if cf.font_size is not None:
        font_kw["size"] = cf.font_size
    if cf.font_color is not None:
        from openpyxl.styles.colors import Color
        font_kw["color"] = Color(rgb=_hex_to_argb(cf.font_color))
    if font_kw:
        ws_cell.font = Font(**font_kw)

    # Fill
    if cf.bg_color:
        ws_cell.fill = PatternFill(
            start_color=_hex_to_argb(cf.bg_color),
            end_color=_hex_to_argb(cf.bg_color),
            fill_type="solid")

    # Borders
    border_kw = {}
    if cf.border_top is not None:
        border_kw["top"] = _make_side(cf.border_top)
    if cf.border_bottom is not None:
        border_kw["bottom"] = _make_side(cf.border_bottom)
    if cf.border_left is not None:
        border_kw["left"] = _make_side(cf.border_left)
    if cf.border_right is not None:
        border_kw["right"] = _make_side(cf.border_right)
    if border_kw:
        ws_cell.border = Border(**border_kw)

    # Alignment
    align_kw = {}
    if cf.alignment is not None:
        h, v = _qt_alignment_to_xl(cf.alignment)
        align_kw["horizontal"] = h
        align_kw["vertical"] = v
    if cf.wrap_text is not None:
        align_kw["wrap_text"] = cf.wrap_text
    if align_kw:
        ws_cell.alignment = Alignment(**align_kw)

    # Number format
    if cf.number_format:
        ws_cell.number_format = _convert_number_format(cf.number_format)


# ── Overlay → image helpers ──────────────────────────────────────────

def _chart_to_png_bytes(chart) -> bytes:
    """Render an EmbeddedChart's matplotlib figure to PNG bytes."""
    buf = io.BytesIO()
    fig = chart._figure
    fig.savefig(buf, format="png", dpi=150,
                bbox_inches="tight", pad_inches=0.05,
                facecolor=fig.get_facecolor(), edgecolor="none")
    return buf.getvalue()


def _pixmap_to_png_bytes(pixmap) -> bytes:
    """Convert a QPixmap to PNG bytes."""
    from PyQt5.QtCore import QBuffer, QIODevice
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    pixmap.save(buf, "PNG")
    return bytes(buf.data())


def _widget_grab_png(widget) -> bytes:
    """Grab a QWidget rendering as PNG bytes."""
    pixmap = widget.grab()
    return _pixmap_to_png_bytes(pixmap)


def _pixel_to_cell_anchor(sheet: "SheetWidget", px_x: int, px_y: int):
    """Convert pixel position to (col, row) in 0-based grid coords.

    Returns the cell that contains the pixel position, clamped to grid
    bounds.  Used for positioning overlay images in Excel.
    """
    # Find column
    col = 0
    accum = 0
    for c in range(sheet.column_count()):
        w = sheet.table.columnWidth(c)
        if accum + w > px_x:
            col = c
            break
        accum += w
        col = c + 1

    # Find row
    row = 0
    accum = 0
    for r in range(sheet.row_count()):
        h = sheet.table.rowHeight(r)
        if accum + h > px_y:
            row = r
            break
        accum += h
        row = r + 1

    return col, row


def _add_image_to_ws(ws, png_bytes: bytes, col: int, row: int,
                     width_px: int, height_px: int):
    """Add a PNG image to an Excel worksheet at the given cell anchor."""
    from openpyxl.drawing.image import Image as XlImage
    from openpyxl.utils import get_column_letter
    img = XlImage(io.BytesIO(png_bytes))
    img.width = width_px
    img.height = height_px
    anchor = f"{get_column_letter(col + 1)}{row + 1}"
    ws.add_image(img, anchor)


# ── Formula export ───────────────────────────────────────────────────

# Functions that exist in Excel with the same name and semantics.
_EXCEL_FUNCTIONS = {
    "ABS", "ACOS", "ACOSH", "AND", "ASIN", "ASINH", "ATAN", "ATAN2",
    "ATANH", "AVERAGE", "CEILING", "CHAR", "CHOOSE", "CLEAN", "CODE",
    "COLUMN", "COLUMNS", "COMBIN", "CONCAT", "CONCATENATE", "COS",
    "COSH", "COUNT", "COUNTA", "COUNTBLANK", "COUNTIF", "COUNTIFS",
    "DATE", "DAY", "DAYS", "DEGREES", "EVEN", "EXACT", "EXP", "FACT",
    "FALSE", "FIND", "FLOOR", "FV", "GCD", "HLOOKUP", "HOUR", "IF",
    "IFERROR", "IFNA", "IFS", "INDEX", "INT", "IPMT", "IRR", "ISBLANK",
    "ISERR", "ISERROR", "ISLOGICAL", "ISNA", "ISNONTEXT", "ISNUMBER",
    "ISTEXT", "LARGE", "LCM", "LEFT", "LEN", "LN", "LOG", "LOG10",
    "LOWER", "MATCH", "MAX", "MEDIAN", "MID", "MIN", "MINUTE", "MOD",
    "MONTH", "NOT", "NOW", "NPER", "NPV", "ODD", "OR", "PERCENTILE",
    "PI", "PMT", "POWER", "PPMT", "PRODUCT", "PROPER", "PV", "QUOTIENT",
    "RADIANS", "RAND", "RANDBETWEEN", "RANK", "RATE", "REPLACE", "REPT",
    "RIGHT", "ROUND", "ROUNDDOWN", "ROUNDUP", "ROW", "ROWS", "SEARCH",
    "SECOND", "SIGN", "SIN", "SINH", "SMALL", "SORT", "SQRT", "STDEV",
    "SUBSTITUTE", "SUM", "SUMIF", "SUMIFS", "SUMPRODUCT", "SUMSQ",
    "SWITCH", "TAN", "TANH", "TEXT", "TIME", "TODAY", "TRIM", "TRUE",
    "TRUNC", "TYPE", "UPPER", "VALUE", "VLOOKUP", "WEEKDAY", "XOR",
    "YEAR",
}

# Pattern for function names in a formula (word before open-paren).
_FUNC_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_.]*)\s*\(')


def _is_excel_compatible(formula: str) -> bool:
    """Check whether a KherveSheet formula can be written to Excel as-is.

    Returns True for formulas that only use Excel-compatible functions,
    standard cell refs, ranges, and arithmetic operators.
    Returns False for =PY(...) cells and KherveSheet-specific functions.
    """
    if not formula or not formula.startswith("="):
        return False
    body = formula[1:].strip()
    # Python cells are never compatible
    if body.upper().startswith("PY(") or body.upper().startswith("PY "):
        return False
    # Check every function call in the formula
    for m in _FUNC_RE.finditer(body):
        name = m.group(1).upper().replace(".", "_")
        if name not in _EXCEL_FUNCTIONS:
            return False
    return True


def _formula_for_excel(formula: str) -> str:
    """Prepare a KherveSheet formula for Excel.

    Replaces ^ (power) with Excel-compatible syntax and normalises
    function names.  The leading '=' is preserved.
    """
    # KherveSheet uses ^ for power like Excel, but the internal compiler
    # converts it to **.  The raw stored formula still has ^, so it's
    # already Excel-compatible.  Just return it as-is.
    return formula


# ── Native Excel chart builder ───────────────────────────────────────

def _build_excel_chart(ws, chart, sheet):
    """Create a native openpyxl chart from an EmbeddedChart.

    Writes series data into hidden helper columns if no cell references
    are available, then builds a chart object referencing those cells.
    """
    from openpyxl.chart import (
        ScatterChart, LineChart, BarChart, Reference,
    )
    from openpyxl.chart.series import DataPoint
    from openpyxl.utils import get_column_letter

    d = chart.to_dict()
    series_list = d.get("series", [])
    if not series_list:
        return

    plot_type = series_list[0].get("plot_type", "Line")

    # Choose chart class
    if plot_type in ("Scatter", "Line+Symbol"):
        xl_chart = ScatterChart()
        xl_chart.style = 13
    elif plot_type == "Bar":
        xl_chart = BarChart()
        xl_chart.style = 10
    elif plot_type == "Histogram":
        xl_chart = BarChart()
        xl_chart.style = 10
    else:
        # Line, Step, Stem → line chart
        xl_chart = LineChart()
        xl_chart.style = 10

    # Chart title and axis labels
    xl_chart.title = d.get("title", "")
    xl_chart.x_axis.title = d.get("xlabel", "")
    xl_chart.y_axis.title = d.get("ylabel", "")

    # Grid
    if not d.get("grid", False):
        xl_chart.y_axis.majorGridlines = None

    # Log scale
    if d.get("xscale") == "log":
        xl_chart.x_axis.scaling.logBase = 10
    if d.get("yscale") == "log":
        xl_chart.y_axis.scaling.logBase = 10

    # Determine if we can reference existing cells or need helper columns
    for si, s in enumerate(series_list):
        x_data = s.get("x", [])
        y_data = s.get("y", [])
        label = s.get("label", f"Series {si + 1}")
        n = len(y_data)
        if n == 0:
            continue

        # Try to use source cell references if available
        y_row_start = s.get("y_row_start")
        y_row_end = s.get("y_row_end")
        y_col = s.get("y_col")
        x_col = s.get("x_col", d.get("x_col"))
        x_row_start = s.get("x_row_start", y_row_start)
        x_row_end = s.get("x_row_end", y_row_end)

        has_cell_refs = (y_col is not None and y_row_start is not None
                         and y_row_end is not None)

        if has_cell_refs:
            # Reference existing data cells (1-based for openpyxl)
            y_ref = Reference(ws,
                              min_col=y_col + 1,
                              min_row=y_row_start + 1,
                              max_row=y_row_end + 1)
            if x_col is not None and x_row_start is not None:
                x_ref = Reference(ws,
                                  min_col=x_col + 1,
                                  min_row=x_row_start + 1,
                                  max_row=x_row_end + 1)
            else:
                x_ref = None
        else:
            # Write data to helper columns beyond the used range
            # Find first empty column
            helper_col = ws.max_column + 2 + si * 2
            for i, (xv, yv) in enumerate(zip(x_data, y_data)):
                ws.cell(row=i + 1, column=helper_col, value=xv)
                ws.cell(row=i + 1, column=helper_col + 1, value=yv)
            x_ref = Reference(ws,
                              min_col=helper_col,
                              min_row=1, max_row=n)
            y_ref = Reference(ws,
                              min_col=helper_col + 1,
                              min_row=1, max_row=n)

        if isinstance(xl_chart, ScatterChart):
            series_obj = xl_chart.series
            from openpyxl.chart import Series as XlSeries
            sr = XlSeries(y_ref, xvalues=x_ref, title=label)
            # Line+Symbol: show lines; pure Scatter: markers only
            s_type = s.get("plot_type", plot_type)
            if s_type == "Scatter":
                sr.graphicalProperties.line.noFill = True
            xl_chart.series.append(sr)
        elif isinstance(xl_chart, BarChart):
            xl_chart.append(y_ref)
            xl_chart.series[-1].title = label
            if x_ref:
                xl_chart.set_categories(x_ref)
        else:
            # LineChart
            xl_chart.append(y_ref)
            xl_chart.series[-1].title = label
            if x_ref:
                xl_chart.set_categories(x_ref)

        # Apply series color
        color = s.get("color")
        if color and xl_chart.series:
            hex_c = color.lstrip("#")
            if len(hex_c) == 6:
                sr_obj = xl_chart.series[-1]
                sr_obj.graphicalProperties.line.solidFill = hex_c
                if isinstance(xl_chart, (ScatterChart,)):
                    # Also set marker fill
                    try:
                        sr_obj.marker = sr_obj.marker or \
                            type(sr_obj.marker)()
                        sr_obj.marker.graphicalProperties.solidFill = hex_c
                    except Exception:
                        pass

    # Position the chart at the same cell anchor
    col, row = _pixel_to_cell_anchor(sheet, chart.x(), chart.y())
    anchor = f"{get_column_letter(col + 1)}{row + 1}"
    # openpyxl chart size is in cm; 96 px per inch at standard DPI
    xl_chart.width = chart.width() / 96 * 2.54
    xl_chart.height = chart.height() / 96 * 2.54
    ws.add_chart(xl_chart, anchor)


# ── Main export entry point ──────────────────────────────────────────

def export_workbook(workbook_widget, path: str,
                    progress_cb=None, process_events=None):
    """Export the full workbook to an Excel .xlsx file.

    Parameters
    ----------
    workbook_widget : WorkbookWidget
        The workbook containing all sheet tabs.
    path : str
        Destination .xlsx file path.
    progress_cb : callable, optional
        Called with (percent: int) for progress updates.
    process_events : callable, optional
        Called periodically to keep the UI responsive.
    """
    import openpyxl
    from openpyxl.utils import get_column_letter
    from .sheet import SheetWidget

    wb = openpyxl.Workbook()
    # Remove default sheet — we create our own
    if wb.sheetnames:
        wb.remove(wb.active)

    tabs = workbook_widget.tabs
    sheet_indices = [i for i in range(tabs.count())
                     if isinstance(tabs.widget(i), SheetWidget)]

    total_sheets = len(sheet_indices)

    for out_i, si in enumerate(sheet_indices):
        sheet = tabs.widget(si)
        name = tabs.tabText(si)
        # Excel sheet names: max 31 chars, no special chars
        safe_name = name[:31].replace("/", "-").replace("\\", "-")
        safe_name = safe_name.replace("?", "").replace("*", "")
        safe_name = safe_name.replace("[", "(").replace("]", ")")
        safe_name = safe_name.replace(":", "-")
        if not safe_name:
            safe_name = f"Sheet{out_i + 1}"
        ws = wb.create_sheet(title=safe_name)

        n_rows = sheet.row_count()
        n_cols = sheet.column_count()
        formulas = getattr(sheet, '_cell_formulas', {})
        cell_formats = getattr(sheet, '_cell_formats', {})

        # ── Determine used range (skip trailing empty rows/cols) ─────
        max_row = 0
        max_col = 0
        for r in range(n_rows):
            for c in range(n_cols):
                it = sheet.table.item(r, c)
                has_content = (it and it.text()) or (r, c) in formulas
                has_format = (r, c) in cell_formats
                if has_content or has_format:
                    max_row = max(max_row, r)
                    max_col = max(max_col, c)
        # Also account for merged ranges
        for mr in getattr(sheet, '_merged_ranges', []):
            max_row = max(max_row, mr[0] + mr[2] - 1)
            max_col = max(max_col, mr[1] + mr[3] - 1)

        used_rows = max_row + 1
        used_cols = max_col + 1

        # ── Write cell values and formatting ─────────────────────────
        for r in range(used_rows):
            if progress_cb:
                pct = int(100 * (out_i * n_rows + r)
                          / max(1, total_sheets * n_rows))
                progress_cb(pct)
            if process_events:
                process_events()

            for c in range(used_cols):
                it = sheet.table.item(r, c)
                raw = it.text() if it else ""

                # Check for formula first
                fm = formulas.get((r, c), "")
                if fm and _is_excel_compatible(fm):
                    val = _formula_for_excel(fm)
                else:
                    # Write display value; try to write as number
                    val = raw
                    if raw:
                        try:
                            val = float(raw)
                            if val == int(val) and "." not in raw:
                                val = int(val)
                        except (ValueError, TypeError):
                            val = raw

                cell = ws.cell(row=r + 1, column=c + 1, value=val)

                # Apply formatting
                cf = cell_formats.get((r, c))
                if cf and not cf.is_empty():
                    _apply_cell_format(cell, cf)

        # ── Column widths ────────────────────────────────────────────
        for c in range(used_cols):
            px = sheet.table.columnWidth(c)
            xl_w = _px_to_col_width(px)
            if xl_w > 0:
                letter = get_column_letter(c + 1)
                ws.column_dimensions[letter].width = xl_w

        # ── Row heights ──────────────────────────────────────────────
        default_h = sheet.table.verticalHeader().defaultSectionSize()
        for r in range(used_rows):
            h = sheet.table.rowHeight(r)
            if h != default_h:
                ws.row_dimensions[r + 1].height = _px_to_row_height(h)

        # ── Merged cells ─────────────────────────────────────────────
        for mr in getattr(sheet, '_merged_ranges', []):
            r0, c0, rspan, cspan = mr
            if rspan > 1 or cspan > 1:
                ws.merge_cells(
                    start_row=r0 + 1, start_column=c0 + 1,
                    end_row=r0 + rspan, end_column=c0 + cspan)

        # ── Embedded charts ──────────────────────────────────────────
        for chart in getattr(sheet, '_charts', []):
            # Always embed the matplotlib render as a high-fidelity image
            try:
                png = _chart_to_png_bytes(chart)
                col, row = _pixel_to_cell_anchor(
                    sheet, chart.x(), chart.y())
                _add_image_to_ws(ws, png, col, row,
                                 chart.width(), chart.height())
            except Exception:
                pass
            # Also create a native Excel chart (interactive) for
            # supported plot types
            try:
                d = chart.to_dict()
                pt = d.get("series", [{}])[0].get("plot_type", "")
                if pt in ("Line", "Scatter", "Line+Symbol", "Bar",
                          "Step", "Histogram"):
                    _build_excel_chart(ws, chart, sheet)
            except Exception:
                pass

        # ── Embedded images ──────────────────────────────────────────
        for img in getattr(sheet, '_images', []):
            try:
                png = _pixmap_to_png_bytes(img._pixmap)
                col, row = _pixel_to_cell_anchor(
                    sheet, img.x(), img.y())
                _add_image_to_ws(ws, png, col, row,
                                 img.width(), img.height())
            except Exception:
                pass

        # ── Embedded equations (rendered to image) ───────────────────
        for eqn in getattr(sheet, '_equations', []):
            try:
                png = _widget_grab_png(eqn)
                col, row = _pixel_to_cell_anchor(
                    sheet, eqn.x(), eqn.y())
                _add_image_to_ws(ws, png, col, row,
                                 eqn.width(), eqn.height())
            except Exception:
                pass

        # ── Embedded shapes (rendered to image) ──────────────────────
        for shp in getattr(sheet, '_shapes', []):
            try:
                png = _widget_grab_png(shp)
                col, row = _pixel_to_cell_anchor(
                    sheet, shp.x(), shp.y())
                _add_image_to_ws(ws, png, col, row,
                                 shp.width(), shp.height())
            except Exception:
                pass

    wb.save(path)
