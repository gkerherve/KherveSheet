"""The rest of the chart system, exposed to the AI chat and MCP.

``ai_charts`` covers creating a chart and styling what is already on
it.  This module reaches the parts that used to be dialog-only: adding
and removing series, trendlines, the full per-axis configuration,
annotations, and export.

Split from ``ai_charts`` purely for the project's 1500-line ceiling;
the two are registered together.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os

from .ai_charts import (CHART_TYPES, _chart, _header_text,
                        canonical_chart_type)
from .sheet import col_index_to_letter

#: Tick-label formats.  These are positional indices into
#: axis_dialog._TICK_FORMATS, so the order here must match it exactly.
TICK_FORMATS = ["auto", "decimal", "scientific", "std_scientific",
                "engineering", "percent", "plain"]

#: Tick directions, matching axis_dialog._TICK_DIRECTIONS order.
TICK_DIRECTIONS = ["out", "in", "inout"]

#: Line styles, matching axis_dialog._LINE_STYLES order.  The dialog
#: stores every one of these as an index into its combo box, so the
#: tool takes the matplotlib string and converts.
LINE_STYLES = ["-", "--", ":", "-."]

#: Annotation kinds annotate_chart understands.
ANNOTATION_TYPES = ("text", "arrow", "line")


# ── Schemas ────────────────────────────────────────────────────────

_CHART_REF = {
    "sheet_name": {"type": "string"},
    "chart_index": {"type": "integer",
                    "description": "0-based (see list_charts)."},
}

CHART_TOOLS_EXTRA = [
    {
        "name": "add_chart_series",
        "description": (
            "Add another Y column to an existing chart as a new series, "
            "reusing the chart's X unless you give a different x_range. "
            "Use this to grow a chart rather than deleting and "
            "rebuilding it — the existing series keep their styling. "
            "The new series is named after the header cell above its "
            "column unless you pass a label."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                **_CHART_REF,
                "y_range": {"type": "string",
                            "description": "Range for the new series, "
                                           "e.g. 'E2:E20'."},
                "x_range": {"type": "string",
                            "description": "Optional different X range; "
                                           "defaults to the chart's own."},
                "label": {"type": "string"},
                "plot_type": {"type": "string", "enum": CHART_TYPES,
                              "description": "Defaults to the chart's "
                                             "first series' type."},
                "color": {"type": "string", "description": "Hex colour."},
            },
            "required": ["sheet_name", "chart_index", "y_range"],
        },
    },
    {
        "name": "remove_chart_series",
        "description": (
            "Remove one series from a chart by index, along with its "
            "fill. A chart must keep at least one series — delete the "
            "whole chart with delete_charts instead. Indices shift down "
            "after a removal, so re-read with list_charts before "
            "removing another."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                **_CHART_REF,
                "series_index": {"type": "integer",
                                 "description": "0-based series index."},
            },
            "required": ["sheet_name", "chart_index", "series_index"],
        },
    },
    {
        "name": "add_trendline",
        "description": (
            "Fit a curve to one series of a chart and draw it on top, "
            "optionally labelled with the equation and R². This is the "
            "chart-side counterpart of fit_trendline: same 23 models "
            "(call list_fit_models for names), but the result becomes "
            "part of the plot instead of a column of numbers. The "
            "trendline is added as its own series, so style_chart and "
            "remove_chart_series can reach it afterwards."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                **_CHART_REF,
                "series_index": {"type": "integer",
                                 "description": "Series to fit. Default 0."},
                "model": {"type": "string",
                          "description": "Model name, e.g. 'Linear', "
                                         "'Exponential', 'Polynomial'. "
                                         "Default 'Linear'."},
                "poly_order": {"type": "integer",
                               "description": "Order for 'Polynomial'."},
                "ma_period": {"type": "integer",
                              "description": "Window for 'Moving Average'."},
                "show_equation": {"type": "boolean",
                                  "description": "Label the fit with its "
                                                 "equation. Default false."},
                "show_r_squared": {"type": "boolean",
                                   "description": "Label it with R². "
                                                  "Default false."},
                "color": {"type": "string",
                          "description": "Hex colour. Default '#ff0000'."},
                "linestyle": {"type": "string",
                              "description": "Default '--'."},
                "linewidth": {"type": "number", "description": "Default 1.5."},
                "clear_existing": {
                    "type": "boolean",
                    "description": ("Remove the chart's existing "
                                    "trendlines first. Default false."),
                },
            },
            "required": ["sheet_name", "chart_index"],
        },
    },
    {
        "name": "configure_axis",
        "description": (
            "Full control of one axis of a chart — everything the Axis "
            "Properties dialog offers. Scale and limits, the title with "
            "its font, colour and rotation, tick-label format "
            "(scientific, percent, currency, prefix/suffix, decimals), "
            "major and minor tick appearance, major and minor "
            "gridlines, the spine, and the secondary (top/right) axis "
            "label. Settings merge with what the axis already has, so "
            "pass only what you want to change. For a title or a simple "
            "log scale, modify_chart is shorter."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                **_CHART_REF,
                "axis": {"type": "string", "enum": ["x", "y", "z"],
                         "description": "Which axis. 'z' is the colour "
                                        "scale on a heatmap and the Z "
                                        "axis on a 3D surface."},
                "scale": {"type": "string",
                          "enum": ["linear", "log", "symlog", "logit"]},
                "invert": {"type": "boolean"},
                "limit_auto": {"type": "boolean",
                               "description": "False pins the limits below."},
                "limit_min": {"type": "number"},
                "limit_max": {"type": "number"},
                "title_text": {"type": "string"},
                "title_show": {"type": "boolean"},
                "title_size": {"type": "number"},
                "title_color": {"type": "string"},
                "title_bold": {"type": "boolean"},
                "title_italic": {"type": "boolean"},
                "title_rotation": {"type": "number"},
                "tl_show": {"type": "boolean",
                            "description": "Show tick labels."},
                "tl_size": {"type": "number"},
                "tl_color": {"type": "string"},
                "tl_rotation": {"type": "number"},
                "tl_format": {
                    "type": "string", "enum": TICK_FORMATS,
                    "description": (
                        "Tick-label number format. 'auto' is "
                        "matplotlib's own and ignores tl_decimals, "
                        "tl_prefix and tl_suffix — use 'decimal' or "
                        "'plain' for those to take effect ('decimal' "
                        "adds thousands separators, 'plain' does not)."),
                },
                "tl_decimals": {"type": "integer"},
                "tl_prefix": {"type": "string"},
                "tl_suffix": {"type": "string"},
                "major_show": {"type": "boolean"},
                "major_count": {"type": "integer",
                                "description": "Approximate tick count."},
                "major_length": {"type": "number"},
                "major_width": {"type": "number"},
                "major_color": {"type": "string"},
                "major_dir": {"type": "string", "enum": TICK_DIRECTIONS},
                "minor_show": {"type": "boolean"},
                "minor_count": {"type": "integer",
                                "description": "Minor ticks per major."},
                "minor_length": {"type": "number"},
                "minor_dir": {"type": "string", "enum": TICK_DIRECTIONS},
                "grid_major_show": {"type": "boolean"},
                "grid_major_color": {"type": "string"},
                "grid_major_style": {"type": "string", "enum": LINE_STYLES},
                "grid_major_width": {"type": "number"},
                "grid_major_alpha": {"type": "number"},
                "grid_minor_show": {"type": "boolean"},
                "grid_minor_color": {"type": "string"},
                "grid_minor_style": {"type": "string",
                                     "enum": LINE_STYLES},
                "grid_minor_alpha": {"type": "number"},
                "spine_show": {"type": "boolean"},
                "spine_color": {"type": "string"},
                "spine_width": {"type": "number"},
                "sec_title_text": {"type": "string",
                                   "description": "Label for the opposite "
                                                  "(top or right) side."},
                "sec_title_show": {"type": "boolean"},
                "sec_spine_show": {"type": "boolean"},
                "sec_tick_show": {"type": "boolean"},
                "sec_tick_dir": {
                    "type": "string", "enum": TICK_DIRECTIONS,
                    "description": (
                        "Direction of the ticks on the opposite (top or "
                        "right) edge when it differs from the main one, "
                        "e.g. 'out' at the bottom and 'in' at the top. "
                        "Needs sec_tick_show.")},
            },
            "required": ["sheet_name", "chart_index", "axis"],
        },
    },
    {
        "name": "annotate_chart",
        "description": (
            "Put text, arrows or line segments on a chart at data "
            "coordinates — for calling out a peak, marking a threshold, "
            "or labelling a region. Annotations are draggable in the "
            "app and are saved with the workbook."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                **_CHART_REF,
                "replace": {"type": "boolean",
                            "description": ("Remove the chart's existing "
                                            "annotations first. Pass with "
                                            "an empty list to clear them "
                                            "all. Default false.")},
                "annotations": {
                    "type": "array",
                    "description": "Annotations to add.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string",
                                     "enum": list(ANNOTATION_TYPES),
                                     "description": (
                                         "'text' is a label at x/y; "
                                         "'arrow' points from x2/y2 to "
                                         "x/y; 'line' is a plain segment "
                                         "between them.")},
                            "text": {"type": "string"},
                            "x": {"type": "number",
                                  "description": "Data X of the label, or "
                                                 "of an arrow's head."},
                            "y": {"type": "number"},
                            "x2": {"type": "number",
                                   "description": "Tail end, for arrow "
                                                  "and line."},
                            "y2": {"type": "number"},
                            "color": {"type": "string"},
                            "fontsize": {"type": "number"},
                            "linewidth": {"type": "number"},
                            "linestyle": {
                                "type": "string",
                                "enum": ["-", "--", ":", "-."],
                                "description": "Arrow/line dash style; "
                                               "':' for dotted guides."},
                            "box": {
                                "type": "boolean",
                                "description": "Draw a box behind the "
                                               "text. Default true; false "
                                               "for plain journal-style "
                                               "labels."},
                        },
                        "required": ["type", "x", "y"],
                    },
                },
            },
            "required": ["sheet_name", "chart_index"],
        },
    },
    {
        "name": "export_chart",
        "description": (
            "Save a chart to an image file. Format follows the "
            "extension: .png, .svg, .pdf. Use this when the user wants "
            "the plot as a file for a document or a slide — the chart "
            "stays in the workbook either way."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                **_CHART_REF,
                "path": {"type": "string",
                         "description": "Full output path ending in .png, "
                                        ".svg or .pdf."},
                "dpi": {"type": "integer",
                        "description": "Raster resolution. Default 200."},
                "transparent": {"type": "boolean",
                                "description": "Transparent background."},
            },
            "required": ["sheet_name", "chart_index", "path"],
        },
    },
]


# ── Series ─────────────────────────────────────────────────────────

def _column_values(sheet, r1, col, r2):
    """Numeric column slice, non-numeric cells becoming NaN."""
    import numpy as np
    out = []
    for r in range(r1, r2 + 1):
        try:
            out.append(float(sheet.cell_text(r, col)))
        except (ValueError, TypeError):
            out.append(float("nan"))
    return np.array(out)


def tool_add_chart_series(ex, inp: dict) -> dict:
    from .ai_charts import _style_one_series
    from .ai_tools import parse_range

    sheet, chart = _chart(ex, inp)
    yr1, yc1, yr2, yc2 = parse_range(inp["y_range"])
    if yc1 != yc2:
        return {"error": "y_range must be a single column. Call this "
                         "once per series."}
    y = _column_values(sheet, yr1, yc1, yr2)

    if inp.get("x_range"):
        xr1, xc1, xr2, _ = parse_range(inp["x_range"])
        x = _column_values(sheet, xr1, xc1, xr2)
        x_col = xc1
    else:
        import numpy as np
        base = chart._series[0]
        x = np.asarray(base["x"], dtype=float)
        x_col = chart._x_col
        xr1 = base.get("x_row_start", yr1)
    if len(x) != len(y):
        return {"error": f"X has {len(x)} points but the new Y column "
                         f"has {len(y)}. They must match."}

    label = (inp.get("label") or _header_text(sheet, yr1, yc1)
             or col_index_to_letter(yc1))
    plot_type = canonical_chart_type(
        inp.get("plot_type") or chart._series[0]["plot_type"])
    if plot_type not in CHART_TYPES:
        return {"error": f"Invalid plot_type {plot_type!r}. "
                f"Valid: {CHART_TYPES}"}
    chart.add_series(x, y, label, plot_type, x_col=x_col, y_col=yc1,
                     row_start=yr1, row_end=yr2)
    idx = len(chart._series) - 1
    if inp.get("color"):
        _style_one_series(chart, idx, {"color": inp["color"]})
    chart._install_legend()
    chart._canvas.draw_idle()
    return {"added": True, "series_index": idx, "label": label,
            "series_count": len(chart._series)}


def tool_remove_chart_series(ex, inp: dict) -> dict:
    _sheet, chart = _chart(ex, inp)
    idx = int(inp["series_index"])
    if idx < 0 or idx >= len(chart._series):
        return {"error": f"Series index {idx} out of range "
                f"(chart has {len(chart._series)} series)."}
    if len(chart._series) <= 1:
        return {"error": "A chart must keep at least one series. Use "
                         "delete_charts to remove the whole chart."}
    artist = chart._series[idx].get("artist")
    if artist is not None:
        try:
            artist.remove()
        except Exception:
            for child in (artist if hasattr(artist, "__iter__") else ()):
                try:
                    child.remove()
                except Exception:
                    pass
    chart._remove_fill(idx)
    # Fills are keyed by series index, so close the gap left behind.
    chart._fill_artists = [(i if i < idx else i - 1, a)
                           for i, a in chart._fill_artists]
    label = chart._series.pop(idx)["label"]
    if idx < len(chart._y_cols):
        chart._y_cols.pop(idx)
    chart._install_legend()
    chart._canvas.draw_idle()
    return {"removed": True, "label": label,
            "series_count": len(chart._series)}


# ── Trendlines ─────────────────────────────────────────────────────

def _clear_trendlines(chart):
    """Drop every trendline series and its equation/R² labels."""
    infos = list(getattr(chart, "_trendlines", []) or [])
    for info in infos:
        for attr in ("eq_artist", "r2_artist"):
            art = getattr(info, attr, None)
            if art is not None:
                try:
                    art.remove()
                except Exception:
                    pass
    # Rebuild the series list without the flagged ones.
    keep = []
    for s in chart._series:
        if s.get("is_trendline"):
            art = s.get("artist")
            if art is not None:
                try:
                    art.remove()
                except Exception:
                    pass
        else:
            keep.append(s)
    removed = len(chart._series) - len(keep)
    chart._series[:] = keep
    chart._trendlines = []
    return removed


def tool_add_trendline(ex, inp: dict) -> dict:
    import numpy as np
    from .trendline import TrendlineInfo, fit_series, restore_trendline

    _sheet, chart = _chart(ex, inp)
    if inp.get("clear_existing"):
        _clear_trendlines(chart)
    idx = int(inp.get("series_index", 0))
    if idx < 0 or idx >= len(chart._series):
        return {"error": f"Series index {idx} out of range "
                f"(chart has {len(chart._series)} series)."}
    s = chart._series[idx]
    model = inp.get("model", "Linear")
    res = fit_series(np.asarray(s["x"], dtype=float),
                     np.asarray(s["y"], dtype=float), model,
                     poly_order=int(inp.get("poly_order", 4)),
                     ma_period=int(inp.get("ma_period", 2)))
    if res.get("error"):
        return {"error": f"Fit failed: {res['error']}"}

    info = TrendlineInfo()
    info.series_idx = idx
    info.model_name = model
    info.poly_order = int(inp.get("poly_order", 4))
    info.ma_period = int(inp.get("ma_period", 2))
    info.params = res.get("params", {})
    info.equation = res.get("equation", "")
    info.gof = res.get("gof", {})
    info.show_equation = bool(inp.get("show_equation", False))
    info.show_r_squared = bool(inp.get("show_r_squared", False))
    info.color = inp.get("color", "#ff0000")
    info.linestyle = inp.get("linestyle", "--")
    info.linewidth = float(inp.get("linewidth", 1.5))
    restore_trendline(chart, info)
    if not hasattr(chart, "_trendlines") or chart._trendlines is None:
        chart._trendlines = []
    chart._trendlines.append(info)
    chart._install_legend()
    chart._canvas.draw_idle()
    gof = {k: (None if v is None or not np.isfinite(v) else round(v, 6))
           for k, v in (res.get("gof") or {}).items()}
    return {"added": True, "model": model, "fitted_series": s["label"],
            "trendline_series_index": info.fit_series_idx,
            "equation": info.equation, "parameters": info.params,
            "goodness_of_fit": gof}


# ── Axes ───────────────────────────────────────────────────────────

#: Tool key → the enum list its index is looked up in.  The axis
#: dialog stores these as integer indices; the schema takes names.
_ENUM_KEYS = {
    "tl_format": TICK_FORMATS,
    "major_dir": TICK_DIRECTIONS,
    "minor_dir": TICK_DIRECTIONS,
    "sec_tick_dir": TICK_DIRECTIONS,
    "grid_major_style": LINE_STYLES,
    "grid_minor_style": LINE_STYLES,
    "sec_spine_style": LINE_STYLES,
}


def _seed_axis_state(chart, axis: str) -> dict:
    """Baseline state for an axis the dialog has never touched.

    ``_apply_dir_static`` fills unset keys with its own defaults, which
    would silently wipe a title or a scale set through modify_chart.  So
    read those back off the live axes first.
    """
    ax = chart._ax
    if axis == "z":
        return {"limit_auto": True}
    is_x = axis == "x"
    return {
        "scale": ax.get_xscale() if is_x else ax.get_yscale(),
        "invert": (ax.xaxis_inverted() if is_x else ax.yaxis_inverted()),
        "limit_auto": True,
        "title_text": (ax.get_xlabel() if is_x else ax.get_ylabel()),
        "title_show": True,
        # The applier's own default is 0, which would lay a Y label on
        # its side the first time this tool touches the axis.
        "title_rotation": 0 if is_x else 90,
    }


def tool_configure_axis(ex, inp: dict) -> dict:
    from .axis_dialog import AxisPropertiesDialog

    _sheet, chart = _chart(ex, inp)
    axis = inp["axis"]
    if axis not in ("x", "y", "z"):
        return {"error": "axis must be 'x', 'y' or 'z'."}

    props = dict(getattr(chart, "_axis_props", None) or {})
    state = dict(props.get(axis) or _seed_axis_state(chart, axis))

    skip = {"sheet_name", "chart_index", "axis"}
    applied = {}
    for key, value in inp.items():
        if key in skip:
            continue
        if key in _ENUM_KEYS:
            choices = _ENUM_KEYS[key]
            if value not in choices:
                return {"error": f"{key} must be one of {choices}."}
            state[key] = choices.index(value)
        else:
            state[key] = value
        applied[key] = value
    if not applied:
        return {"error": "No axis settings given. Pass at least one, "
                         "e.g. scale, title_text, minor_show, "
                         "grid_major_show."}
    # Pinning a limit is only honoured with limit_auto off; asking for
    # one and getting nothing back is the more surprising outcome.
    if ("limit_min" in applied or "limit_max" in applied) \
            and "limit_auto" not in applied:
        state["limit_auto"] = False
        applied["limit_auto"] = False

    try:
        AxisPropertiesDialog._apply_dir_static(chart, axis, state)
    except Exception as exc:
        return {"error": f"Could not apply axis settings: {exc}"}
    props[axis] = state
    chart._axis_props = props
    chart._canvas.draw_idle()
    return {"configured": True, "axis": axis, "applied": applied}


# ── Annotations ────────────────────────────────────────────────────

def _add_annotation(chart, spec: dict) -> dict:
    """Place one annotation in data coordinates."""
    ax = chart._ax
    kind = spec.get("type")
    if kind not in ANNOTATION_TYPES:
        raise ValueError(f"Unknown annotation type {kind!r}. "
                         f"Valid: {list(ANNOTATION_TYPES)}")
    x, y = float(spec["x"]), float(spec["y"])
    text = spec.get("text", "") or ""
    color = spec.get("color", "black")
    lw = float(spec.get("linewidth", 1.5))
    size = float(spec.get("fontsize", 10 if kind == "text" else 9))
    box = bool(spec.get("box", True))
    ls = spec.get("linestyle", "-") or "-"

    if kind == "text":
        art = ax.annotate(
            text, xy=(x, y), xytext=(x, y), fontsize=size,
            color=color, ha="center", va="center",
            bbox=(dict(boxstyle="round,pad=0.3", fc="wheat", alpha=0.8)
                  if box else None))
        entry = {"type": "text", "artist": art, "text": text,
                 "xy": (x, y)}
    else:
        # Tail defaults to a short offset so the arrow is visible even
        # when the caller gives only a head position.
        xl, xr = ax.get_xlim()
        yb, yt = ax.get_ylim()
        x2 = float(spec.get("x2", x + (xr - xl) * 0.15))
        y2 = float(spec.get("y2", y + (yt - yb) * 0.15))
        style = "->" if kind == "arrow" else "-"
        art = ax.annotate(
            text, xy=(x, y), xytext=(x2, y2), fontsize=size,
            color=color,
            arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                            linestyle=ls),
            bbox=(dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7)
                  if text.strip() and box else None))
        entry = {"type": kind, "artist": art, "text": text,
                 "xy": (x, y), "xytext": (x2, y2)}
    art.draggable(True)
    chart._annotations.append(entry)
    return entry


def tool_annotate_chart(ex, inp: dict) -> dict:
    from .undo_commands import AddAnnotationCmd

    _sheet, chart = _chart(ex, inp)
    cleared = 0
    if inp.get("replace"):
        for entry in chart._annotations:
            art = entry.get("artist")
            if art is not None:
                try:
                    art.remove()
                except Exception:
                    pass
        cleared = len(chart._annotations)
        chart._annotations = []
    added = []
    for spec in inp.get("annotations") or []:
        try:
            entry = _add_annotation(chart, spec)
        except (ValueError, KeyError, TypeError) as exc:
            return {"error": str(exc)}
        ex._undo.push(AddAnnotationCmd(chart, entry))
        added.append({"type": entry["type"], "text": entry["text"],
                      "xy": list(entry["xy"])})
    if not added and not cleared:
        return {"error": "Nothing to do — pass annotations, or replace "
                         "with an empty list to clear them."}
    chart._canvas.draw_idle()
    return {"annotated": True, "added": added, "cleared": cleared,
            "total": len(chart._annotations)}


# ── Export ─────────────────────────────────────────────────────────

_EXPORT_FORMATS = (".png", ".svg", ".pdf")


def tool_export_chart(ex, inp: dict) -> dict:
    _sheet, chart = _chart(ex, inp)
    path = os.path.expanduser(str(inp["path"]))
    ext = os.path.splitext(path)[1].lower()
    if ext not in _EXPORT_FORMATS:
        return {"error": f"Unsupported format {ext or '(none)'}. "
                f"Use one of {list(_EXPORT_FORMATS)}."}
    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        return {"error": f"Directory does not exist: {parent}"}
    fig = chart._figure
    try:
        fig.savefig(path, dpi=int(inp.get("dpi", 200)),
                    transparent=bool(inp.get("transparent", False)),
                    facecolor=(None if inp.get("transparent")
                               else fig.get_facecolor()),
                    bbox_inches="tight")
    except Exception as exc:
        return {"error": f"Could not write {path}: {exc}"}
    return {"exported": True, "path": path,
            "bytes": os.path.getsize(path)}


def build_dispatch(ex) -> dict:
    """Extra chart tool names → bound callables."""
    return {
        "add_chart_series": lambda inp: tool_add_chart_series(ex, inp),
        "remove_chart_series": lambda inp: tool_remove_chart_series(ex, inp),
        "add_trendline": lambda inp: tool_add_trendline(ex, inp),
        "configure_axis": lambda inp: tool_configure_axis(ex, inp),
        "annotate_chart": lambda inp: tool_annotate_chart(ex, inp),
        "export_chart": lambda inp: tool_export_chart(ex, inp),
    }
