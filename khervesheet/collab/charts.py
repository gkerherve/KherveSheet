"""Charts in a shared workbook: KherveSheet's chart windows ↔ the chart
specs KherveCELL keeps in the shared document's ``charts`` map (see
khervesheet/core/charts.py for the spec).

A spec names ranges ("B2:B20") and anchors the chart to a cell; a desktop
chart reads grid columns and sits at a pixel position. Only what both can
express travels; the rest of a spec (a forecast, …) is kept as it was.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

import numpy as np

from ..core.charts import CHART_TYPES, DEFAULT_COLORS, series_xy
from ..core.refs import col_index_to_letter, letter_to_col_index

_COLUMN_RANGE = re.compile(
    r"^\$?([A-Za-z]{1,3})\$?(\d{1,7})(?::\$?([A-Za-z]{1,3})\$?(\d{1,7}))?$")


def column_range(ref: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """"B2:B20" → (col, first row, last row), 0-based; None for anything a
    desktop chart cannot read (another sheet, several columns…)."""
    if not ref or "!" in ref:
        return None
    m = _COLUMN_RANGE.match(ref.strip())
    if not m:
        return None
    c1 = letter_to_col_index(m.group(1))
    r1 = int(m.group(2)) - 1
    c2 = letter_to_col_index(m.group(3)) if m.group(3) else c1
    r2 = int(m.group(4)) - 1 if m.group(4) else r1
    if c1 != c2:
        return None
    return c1, min(r1, r2), max(r1, r2)


def _range_ref(col: int, r1: int, r2: int) -> str:
    letter = col_index_to_letter(col)
    return f"{letter}{r1 + 1}:{letter}{r2 + 1}"


def _values(sheet, col, r1, r2):
    """The cells' values, as the engine reads them (None when empty)."""
    out = []
    for r in range(r1, r2 + 1):
        text = sheet.cell_text(r, col)
        if not text:
            out.append(None)
            continue
        try:
            out.append(float(text.replace(",", "")))
        except ValueError:
            out.append(text)
    return out


# ── Desktop → spec ───────────────────────────────────────────────────
def spec_from_chart(chart, sheet_id: str) -> Optional[dict]:
    """The spec of a desktop chart, or None if it does not come from grid
    columns (nothing to share)."""
    sheet = chart._source_sheet
    if sheet is None:
        return None
    d = chart.to_dict()
    series, x_ref = [], None
    real = [s for s in chart._series if not s.get("is_trendline")]
    for i, (s, sd) in enumerate(zip(real, d["series"])):
        y_col = chart._y_cols[i] if i < len(chart._y_cols) else None
        r1, r2 = s.get("y_row_start"), s.get("y_row_end")
        if y_col is None or r1 is None or r2 is None:
            return None
        series.append({"ref": _range_ref(y_col, int(r1), int(r2)),
                       "name": s.get("label") or None,
                       "color": sd.get("color")})
        x_col = s.get("x_col", chart._x_col)
        if x_ref is None and x_col is not None:
            x1 = s.get("x_row_start", r1)
            x2 = s.get("x_row_end", r2)
            x_ref = _range_ref(x_col, int(x1), int(x2))
    if not series:
        return None
    table = sheet.table
    col = table.columnAt(max(0, chart.x()))
    row = table.rowAt(max(0, chart.y()))
    col = col if col >= 0 else max(0, table.columnCount() - 1)
    row = row if row >= 0 else max(0, table.rowCount() - 1)
    kind = real[0].get("plot_type") or "Line"
    spec = {
        "sheetId": sheet_id,
        "row": row,
        "col": col,
        "dx": max(0, chart.x() - table.columnViewportPosition(col)),
        "dy": max(0, chart.y() - table.rowViewportPosition(row)),
        "width": chart.width(),
        "height": chart.height(),
        "type": kind if kind in CHART_TYPES else "Line",
        "title": d.get("title") or "",
        "xLabel": d.get("xlabel") or "",
        "yLabel": d.get("ylabel") or "",
        "x": x_ref,
        "series": series,
        "legend": bool(d.get("legend_visible")),
        "grid": bool(d.get("grid")),
        "logX": d.get("xscale") == "log",
        "logY": d.get("yscale") == "log",
    }
    trendlines = [{
        "series": info.series_idx,
        "model": info.model_name,
        "polyOrder": info.poly_order,
        "maPeriod": info.ma_period,
        "color": info.color,
        "showEquation": info.show_equation,
        "showR2": info.show_r_squared,
    } for info in getattr(chart, "_trendlines", [])]
    spec["trendlines"] = trendlines
    return spec


def merge_spec(shared: dict, desktop: dict) -> dict:
    """The desktop's view of a chart over the shared spec: what the desktop
    cannot express (a trendline's forecast…) is kept."""
    merged = {**shared, **desktop}
    old = shared.get("trendlines") or []
    merged["trendlines"] = [
        {**(old[i] if i < len(old) else {}), **t}
        for i, t in enumerate(desktop.get("trendlines") or [])]
    return merged


# ── Spec → desktop ───────────────────────────────────────────────────
def chart_from_spec(sheet, spec: dict):
    """A desktop chart for *spec* on *sheet*, or None if none of its
    series can be read there."""
    from ..graph import EmbeddedChart

    kind = spec.get("type") or "Line"
    x_range = column_range(spec.get("x"))
    x_values = _values(sheet, *x_range) if x_range else None
    chart, labels, colors, time_axis = None, None, [], False
    for i, s in enumerate(spec.get("series") or []):
        y_range = column_range(s.get("ref"))
        if y_range is None:
            continue
        y_col, r1, r2 = y_range
        x, y, lab = series_xy(x_values, _values(sheet, y_col, r1, r2))
        if lab == "TIME":
            time_axis = True
        elif lab is not None:
            labels = labels or lab
        name = s.get("name") or s.get("ref")
        x_col = x_range[0] if x_range else None
        if chart is None:
            chart = EmbeddedChart(x, y, name, kind, sheet,
                                  sheet.table.viewport(), x_col=x_col,
                                  y_col=y_col, row_start=r1, row_end=r2)
        else:
            chart.add_series(x, y, name, kind, x_col=x_col, y_col=y_col,
                             row_start=r1, row_end=r2)
        if x_range:
            chart._series[-1]["x_row_start"] = x_range[1]
            chart._series[-1]["x_row_end"] = x_range[2]
        colors.append(s.get("color") or DEFAULT_COLORS[i % 10])
    if chart is None:
        return None

    if labels:
        chart._apply_categorical_x(labels)
    elif time_axis:
        chart._apply_time_x()
    ax = chart._ax
    ax.set_title(spec.get("title") or "")
    ax.set_xlabel(spec.get("xLabel") or "")
    ax.set_ylabel(spec.get("yLabel") or "")
    for key, setter in (("logX", ax.set_xscale), ("logY", ax.set_yscale)):
        if spec.get(key):
            try:
                setter("log")
            except ValueError:
                pass
    ax.grid(bool(spec.get("grid")))
    from ..ai_charts import _apply_legend, _style_one_series
    for i, color in enumerate(colors):
        try:
            _style_one_series(chart, i, {"color": color})
        except (ValueError, IndexError):
            pass
    if spec.get("legend", len(colors) > 1) and kind not in (
            "Heatmap", "3D Surface"):
        _apply_legend(chart, {})
    elif ax.get_legend() is not None:
        ax.get_legend().remove()
    _add_trendlines(chart, spec)

    table = sheet.table
    row = min(int(spec.get("row") or 0), table.rowCount() - 1)
    col = min(int(spec.get("col") or 0), table.columnCount() - 1)
    chart.resize(int(spec.get("width") or 480), int(spec.get("height") or 300))
    chart.move(table.columnViewportPosition(col) + int(spec.get("dx") or 0),
               table.rowViewportPosition(row) + int(spec.get("dy") or 0))
    sheet._charts.append(chart)
    sheet.data_changed.connect(chart._on_data_changed)
    chart.show()
    chart._canvas.draw_idle()
    return chart


def _add_trendlines(chart, spec: dict):
    """Fit and draw the spec's trendlines, as the Trendline dialog does."""
    from ..core.fitting import fit_series
    from ..trendline import TrendlineInfo, restore_trendline

    real = [s for s in chart._series if not s.get("is_trendline")]
    for t in spec.get("trendlines") or []:
        index = int(t.get("series", 0) or 0)
        if index >= len(real):
            continue
        x = np.asarray(real[index]["x"], dtype=float)
        y = np.asarray(real[index]["y"], dtype=float)
        fit = fit_series(x, y, t.get("model") or "Linear",
                         poly_order=int(t.get("polyOrder") or 2),
                         ma_period=int(t.get("maPeriod") or 2))
        if "error" in fit:
            continue
        info = TrendlineInfo()
        info.series_idx = index
        info.model_name = t.get("model") or "Linear"
        info.poly_order = int(t.get("polyOrder") or 2)
        info.ma_period = int(t.get("maPeriod") or 2)
        info.params = fit["params"]
        info.equation = fit.get("equation", "")
        info.gof = fit.get("gof", {})
        info.show_equation = bool(t.get("showEquation"))
        info.show_r_squared = bool(t.get("showR2"))
        info.color = t.get("color") or "#d62728"
        restore_trendline(chart, info)
        chart._trendlines.append(info)


def remove_chart(chart):
    """Take a chart off its sheet without an undo step (a collaborator
    removed or replaced it)."""
    sheet = chart._source_sheet
    if sheet is not None:
        try:
            sheet.data_changed.disconnect(chart._on_data_changed)
        except (TypeError, RuntimeError):
            pass
        if chart in getattr(sheet, "_charts", []):
            sheet._charts.remove(chart)
        if getattr(sheet, "_selected_chart", None) is chart:
            sheet._selected_chart = None
    chart.hide()
    chart.deleteLater()
