"""Chart tools for the AI chat and for MCP clients.

Split out of ``ai_backend`` / ``ai_tools`` so both stay near the
project's 1500-line ceiling, and so the *schemas* and the *code* for a
chart sit next to each other.

The schemas here are the only briefing an external MCP client's model
gets — an MCP host writes its own system prompt — so anything needed to
produce a presentable plot has to be stated in the descriptions.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from .sheet import col_index_to_letter


#: Plot types EmbeddedChart knows how to draw.
CHART_TYPES = [
    "Line", "Scatter", "Line+Symbol", "Bar", "Step",
    "Stem", "Histogram", "Box", "Heatmap", "3D Surface",
]

#: Named looks ``style_chart`` can apply in one call.  Each is a small
#: recipe applied to the live axes — no rcParams, so it never leaks
#: into other charts.
PRESETS = ("clean", "minimal", "publication", "dark", "default")


# ── Schemas ────────────────────────────────────────────────────────

_SERIES_STYLE = {
    "type": "object",
    "properties": {
        "index": {"type": "integer",
                  "description": "0-based series index (see list_charts)."},
        "label": {"type": "string",
                  "description": "Legend text for this series."},
        "color": {"type": "string",
                  "description": "Line/marker colour as hex, e.g. '#d62728'."},
        "linestyle": {"type": "string",
                      "description": "'-', '--', '-.', ':' or 'None'."},
        "linewidth": {"type": "number"},
        "marker": {"type": "string",
                   "description": ("Marker glyph: 'o', 's', '^', 'v', 'D', "
                                   "'x', '+', '*' or 'None' for no marker.")},
        "markersize": {"type": "number"},
        "markerfacecolor": {"type": "string"},
        "markeredgecolor": {"type": "string"},
        "plot_type": {"type": "string", "enum": CHART_TYPES,
                      "description": "Redraw this series as another type."},
        "visible": {"type": "boolean"},
        "fill_mode": {
            "type": "string", "enum": ["none", "zero", "series"],
            "description": ("Shade the area under the curve ('zero') or "
                            "between it and another series ('series', "
                            "which needs fill_target)."),
        },
        "fill_target": {"type": "integer",
                        "description": "Series index to fill against, "
                                       "when fill_mode is 'series'."},
        "fill_color": {"type": "string", "description": "Hex."},
        "fill_alpha": {"type": "number",
                       "description": "0-1. Default 0.3."},
    },
    "required": ["index"],
}

_LEGEND = {
    "type": "object",
    "description": "Legend appearance. Omit to leave it as it is.",
    "properties": {
        "visible": {"type": "boolean",
                    "description": "False removes the legend entirely."},
        "loc": {"type": "string",
                "description": ("Placement: 'best', 'upper right', "
                                "'upper left', 'lower left', 'lower right', "
                                "'center left', 'center right'.")},
        "ncol": {"type": "integer"},
        "fontsize": {"type": "number"},
        "frame": {"type": "boolean",
                  "description": "Draw the box around the legend."},
        "title": {"type": "string"},
    },
}

CHART_TOOLS = [
    {
        "name": "insert_chart",
        "description": (
            "Create an embedded chart from data already in the sheet and "
            "return its chart_index. Give it a title and axis labels in "
            "this same call — an unlabelled plot is rarely what the user "
            "wants. Series labels default to the text in the header cell "
            "directly above each Y column, so a chart over a properly "
            "headed table names itself; pass series_labels to override. "
            "Use style_chart afterwards for colours, markers and presets. "
            "For a plot that is not a chart over grid columns — an image, "
            "a map, several subplots, anything matplotlib can draw — "
            "write a =PY cell that returns a figure instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string",
                               "description": "Sheet containing the data."},
                "chart_type": {"type": "string", "enum": CHART_TYPES},
                "x_range": {
                    "type": "string",
                    "description": (
                        "A1-notation range for X, e.g. 'A2:A20'. Text "
                        "values become category labels; times are parsed "
                        "as a time axis."),
                },
                "y_range": {
                    "type": "string",
                    "description": (
                        "A1-notation range for Y. A multi-column range "
                        "like 'D5:H14' plots one series per column, or "
                        "give comma-separated ranges: 'D5:D14,F5:F14'."),
                },
                "title": {"type": "string",
                          "description": "Chart title."},
                "x_label": {"type": "string",
                            "description": (
                                "X axis label. Defaults to the header cell "
                                "above the X range when it holds text.")},
                "y_label": {"type": "string",
                            "description": "Y axis label."},
                "series_labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Legend name per Y series, in order. Defaults to "
                        "each column's header cell, then to its column "
                        "letter."),
                },
                "colors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Hex colour per series, in order. Omit to use the "
                        "default palette."),
                },
                "legend": _LEGEND,
                "grid": {"type": "boolean",
                         "description": "Draw gridlines. Default false."},
                "x_scale": {"type": "string",
                            "enum": ["linear", "log", "symlog", "logit"]},
                "y_scale": {"type": "string",
                            "enum": ["linear", "log", "symlog", "logit"]},
                "preset": {
                    "type": "string", "enum": list(PRESETS),
                    "description": (
                        "Overall look — see style_chart. 'clean' is a good "
                        "default for a presentable plot."),
                },
                "width": {"type": "integer",
                          "description": "Chart width in pixels (default 480)."},
                "height": {"type": "integer",
                           "description": "Chart height in pixels (default 320)."},
                "position": {
                    "type": "string",
                    "description": (
                        "Top-left cell the chart floats over, e.g. 'H2'. "
                        "Charts overlay the grid rather than occupying "
                        "cells, so place them clear of the data. Omit to "
                        "cascade from the top-left corner."),
                },
            },
            "required": ["sheet_name", "chart_type", "x_range", "y_range"],
        },
    },
    {
        "name": "modify_chart",
        "description": (
            "Edit an existing chart's axes, labels and size in place: "
            "invert (reverse) an axis, switch to a log scale, set the "
            "title or axis labels, pin the axis limits, toggle gridlines, "
            "resize or move it. Use style_chart for the series themselves "
            "(colours, markers, line styles) and for the legend."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string"},
                "chart_index": {"type": "integer",
                                "description": "0-based (see list_charts)."},
                "invert_x": {"type": "boolean",
                             "description": "True reverses the X axis."},
                "invert_y": {"type": "boolean",
                             "description": "True reverses the Y axis."},
                "x_scale": {"type": "string",
                            "enum": ["linear", "log", "symlog", "logit"]},
                "y_scale": {"type": "string",
                            "enum": ["linear", "log", "symlog", "logit"]},
                "title": {"type": "string"},
                "x_label": {"type": "string"},
                "y_label": {"type": "string"},
                "grid": {"type": "boolean"},
                "x_min": {"type": "number"},
                "x_max": {"type": "number"},
                "y_min": {"type": "number"},
                "y_max": {"type": "number"},
                "width": {"type": "integer",
                          "description": "Chart width in pixels."},
                "height": {"type": "integer",
                           "description": "Chart height in pixels."},
                "position": {"type": "string",
                             "description": ("Top-left cell to move the "
                                             "chart over, e.g. 'H2'.")},
                "tight_layout": {
                    "type": "boolean",
                    "description": ("Let matplotlib fit the labels to "
                                    "the canvas. Turn it off to control "
                                    "the margins yourself."),
                },
                "margins": {
                    "type": "object",
                    "description": ("Plot-area edges as fractions of the "
                                    "canvas, when tight_layout is off."),
                    "properties": {
                        "left": {"type": "number"},
                        "right": {"type": "number"},
                        "top": {"type": "number"},
                        "bottom": {"type": "number"},
                    },
                },
            },
            "required": ["sheet_name", "chart_index"],
        },
    },
    {
        "name": "style_chart",
        "description": (
            "Restyle an existing chart's series and legend: per-series "
            "colour, line style and width, marker glyph and size, legend "
            "text, visibility, or plot type; legend placement; font "
            "sizes; and a named preset for the overall look. Call "
            "get_chart_details first to see the current series order and "
            "styling. Everything is optional — only what you pass is "
            "changed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string"},
                "chart_index": {"type": "integer",
                                "description": "0-based (see list_charts)."},
                "preset": {
                    "type": "string", "enum": list(PRESETS),
                    "description": (
                        "'clean' — no top/right spines, faint horizontal "
                        "grid, tight layout. 'minimal' — clean with no "
                        "grid and small ticks. 'publication' — black "
                        "spines, inward ticks, serif labels, no grid. "
                        "'dark' — dark figure and axes with light text. "
                        "'default' — plain matplotlib. A preset is applied "
                        "before the other options, so they win over it."),
                },
                "series": {
                    "type": "array",
                    "description": (
                        "Style changes, one entry per series you want to "
                        "touch. Series you omit keep their style."),
                    "items": _SERIES_STYLE,
                },
                "legend": _LEGEND,
                "title_size": {"type": "number"},
                "label_size": {"type": "number",
                               "description": "Axis label font size."},
                "tick_size": {"type": "number"},
                "grid": {"type": "boolean"},
                "grid_axis": {"type": "string",
                              "enum": ["both", "x", "y"],
                              "description": "Which gridlines to draw."},
                "face_color": {"type": "string",
                               "description": "Plot area background, hex."},
                "figure_color": {"type": "string",
                                 "description": "Chart background, hex."},
            },
            "required": ["sheet_name", "chart_index"],
        },
    },
]


# ── Helpers ────────────────────────────────────────────────────────

def _chart(ex, inp: dict):
    """Resolve (sheet, chart) from a tool payload, raising on miss."""
    sheet = ex._sheet(inp["sheet_name"])
    charts = getattr(sheet, "_charts", []) or []
    idx = int(inp.get("chart_index", 0))
    if idx < 0 or idx >= len(charts):
        raise ValueError(f"Chart index {idx} out of range "
                         f"(sheet has {len(charts)} chart(s)).")
    return sheet, charts[idx]


def _header_text(sheet, row: int, col: int) -> str:
    """Text one row above a data range, when it reads like a header."""
    if row <= 0:
        return ""
    text = (sheet.cell_text(row - 1, col) or "").strip()
    if not text:
        return ""
    try:
        float(text)
    except (ValueError, TypeError):
        return text
    return ""          # a number above the data is data, not a header


def _move_to_cell(sheet, chart, ref: str):
    """Float *chart* over the cell named by *ref* (A1 notation)."""
    from .ai_tools import parse_a1
    row, col = parse_a1(ref)
    table = sheet.table
    x = table.columnViewportPosition(col)
    y = table.rowViewportPosition(row)
    # A ref scrolled out of view reports a negative position; clamp so
    # the chart never lands off the visible grid.
    chart.move(max(x, 0), max(y, 0))


def _apply_legend(chart, spec: dict):
    """Apply a legend sub-dict; returns what was applied."""
    ax = chart._ax
    if spec.get("visible") is False:
        leg = ax.get_legend()
        if leg is not None:
            leg.remove()
        return {"visible": False}
    kw = {"loc": spec.get("loc", "best")}
    if "ncol" in spec:
        kw["ncol"] = int(spec["ncol"])
    if "fontsize" in spec:
        kw["fontsize"] = float(spec["fontsize"])
    if "frame" in spec:
        kw["frameon"] = bool(spec["frame"])
    if spec.get("title"):
        kw["title"] = spec["title"]
    leg = chart._install_legend(ax, **kw)
    if leg is not None:
        _match_legend_to_axes(ax, leg)
    return {k: v for k, v in spec.items()}


def _match_legend_to_axes(ax, leg):
    """Keep the legend readable over a dark plot area."""
    from matplotlib.colors import to_rgb
    r, g, b = to_rgb(ax.get_facecolor())
    if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.5:
        return                              # light background, leave it
    frame = leg.get_frame()
    if frame is not None:
        frame.set_facecolor(ax.get_facecolor())
        frame.set_edgecolor("#888888")
    for text in leg.get_texts():
        text.set_color("#eeeeee")
    title = leg.get_title()
    if title is not None:
        title.set_color("#eeeeee")


def _apply_preset(chart, name: str):
    """Apply a named look to the live axes."""
    fig, ax = chart._figure, chart._ax
    # Start from a plain state so presets don't accumulate.
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(True)
        ax.spines[side].set_color("black")
    ax.grid(False)
    ax.tick_params(direction="out", labelsize=None)
    if name == "default":
        fig.set_facecolor("white")
        ax.set_facecolor("white")
        return
    if name in ("clean", "minimal"):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#666666")
        ax.spines["bottom"].set_color("#666666")
        fig.set_facecolor("white")
        ax.set_facecolor("white")
        if name == "clean":
            ax.grid(True, axis="y", color="#dddddd", linewidth=0.7)
            ax.set_axisbelow(True)
        else:
            ax.tick_params(length=2, labelsize=8)
    elif name == "publication":
        ax.tick_params(direction="in", top=True, right=True, labelsize=9)
        for side in ("top", "right", "bottom", "left"):
            ax.spines[side].set_linewidth(1.0)
        for lbl in (ax.title, ax.xaxis.label, ax.yaxis.label,
                    *ax.get_xticklabels(), *ax.get_yticklabels()):
            lbl.set_fontfamily("serif")
        fig.set_facecolor("white")
        ax.set_facecolor("white")
    elif name == "dark":
        fig.set_facecolor("#1e1e1e")
        ax.set_facecolor("#2b2b2b")
        for side in ("top", "right", "bottom", "left"):
            ax.spines[side].set_color("#888888")
        ax.tick_params(colors="#dddddd")
        for lbl in (ax.title, ax.xaxis.label, ax.yaxis.label):
            lbl.set_color("#eeeeee")
        ax.grid(True, color="#3d3d3d", linewidth=0.7)
        ax.set_axisbelow(True)


def _style_one_series(chart, idx: int, spec: dict) -> dict:
    """Apply one entry of the *series* array; returns what stuck."""
    from matplotlib.collections import PathCollection
    from matplotlib.container import BarContainer
    from matplotlib.markers import MarkerStyle

    if idx < 0 or idx >= len(chart._series):
        raise ValueError(f"Series index {idx} out of range "
                         f"(chart has {len(chart._series)} series).")
    applied = {"index": idx}

    # Plot type first: it replaces the artist.
    new_type = spec.get("plot_type")
    if new_type:
        if new_type not in CHART_TYPES:
            raise ValueError(f"Unknown plot_type {new_type!r}. "
                             f"Valid: {CHART_TYPES}")
        if not chart.change_series_type(idx, new_type):
            raise ValueError(
                f"Series {idx} cannot become a {new_type} — 2-D matrix "
                "data only supports Heatmap and 3D Surface.")
        applied["plot_type"] = new_type

    s = chart._series[idx]
    artist = s.get("artist")
    if "label" in spec:
        s["label"] = spec["label"]
        if artist is not None and hasattr(artist, "set_label"):
            artist.set_label(spec["label"])
        applied["label"] = spec["label"]
    if artist is None:
        return applied

    if "visible" in spec and hasattr(artist, "set_visible"):
        artist.set_visible(bool(spec["visible"]))
        applied["visible"] = bool(spec["visible"])

    if isinstance(artist, BarContainer):
        if "color" in spec:
            for patch in artist.patches:
                patch.set_facecolor(spec["color"])
            applied["color"] = spec["color"]
        _apply_fill(chart, idx, spec, applied)
        return applied

    if isinstance(artist, PathCollection):     # Scatter
        face = spec.get("markerfacecolor", spec.get("color"))
        if face is not None:
            artist.set_facecolors(face)
            applied["color"] = face
        if "markeredgecolor" in spec:
            artist.set_edgecolors(spec["markeredgecolor"])
            applied["markeredgecolor"] = spec["markeredgecolor"]
        if "markersize" in spec:
            artist.set_sizes([float(spec["markersize"]) ** 2])
            applied["markersize"] = spec["markersize"]
        if "marker" in spec and spec["marker"] != "None":
            mk = MarkerStyle(spec["marker"])
            artist.set_paths(
                [mk.get_path().transformed(mk.get_transform())])
            s["marker"] = spec["marker"]
            applied["marker"] = spec["marker"]
        _apply_fill(chart, idx, spec, applied)
        return applied

    # Line2D and friends.
    pairs = (
        ("color", "set_color"),
        ("linestyle", "set_linestyle"),
        ("linewidth", "set_linewidth"),
        ("markersize", "set_markersize"),
        ("markerfacecolor", "set_markerfacecolor"),
        ("markeredgecolor", "set_markeredgecolor"),
    )
    for key, setter in pairs:
        if key in spec and hasattr(artist, setter):
            getattr(artist, setter)(spec[key])
            applied[key] = spec[key]
    if "marker" in spec and hasattr(artist, "set_marker"):
        mk = spec["marker"]
        artist.set_marker("" if mk == "None" else mk)
        applied["marker"] = mk
    _apply_fill(chart, idx, spec, applied)
    return applied


def _apply_fill(chart, idx: int, spec: dict, applied: dict):
    """Shade under a curve, or between it and another series."""
    if "fill_mode" not in spec:
        return
    mode = spec["fill_mode"]
    if mode not in ("none", "zero", "series"):
        raise ValueError(f"fill_mode must be 'none', 'zero' or "
                         f"'series', not {mode!r}.")
    target = int(spec.get("fill_target", 0))
    if mode == "series" and not (0 <= target < len(chart._series)):
        raise ValueError(f"fill_target {target} is not a series index "
                         f"(chart has {len(chart._series)}).")
    default = "#1f77b4"
    artist = chart._series[idx].get("artist")
    if artist is not None and hasattr(artist, "get_color"):
        try:
            default = artist.get_color()
        except Exception:
            pass
    chart.apply_fill(idx, mode, target,
                     spec.get("fill_color", default),
                     float(spec.get("fill_alpha", 0.3)))
    applied["fill_mode"] = mode


# ── Tools ──────────────────────────────────────────────────────────

def tool_insert_chart(ex, inp: dict) -> dict:
    """Build a chart over grid columns, labelled and styled up front."""
    import numpy as np
    from .ai_tools import parse_range
    from .graph import EmbeddedChart, parse_time_column

    sheet = ex._sheet(inp["sheet_name"])
    # Callers (LLMs especially) write "scatter" as often as "Scatter".
    chart_type = next((t for t in CHART_TYPES
                       if t.lower() == str(inp["chart_type"]).lower()),
                      inp["chart_type"])
    if chart_type not in CHART_TYPES:
        return {"error": f"Invalid chart_type {chart_type!r}. "
                f"Valid: {CHART_TYPES}"}

    # ── X data: numeric, time, or categorical labels.
    xr1, xc1, xr2, _ = parse_range(inp["x_range"])
    x_labels = [sheet.cell_text(r, xc1) for r in range(xr1, xr2 + 1)]
    x_vals = []
    for t in x_labels:
        try:
            x_vals.append(float(t))
        except (ValueError, TypeError):
            x_vals.append(float("nan"))
    x = np.array(x_vals)
    if len(x) == 0:
        return {"error": "No X data found."}
    cat_labels = None
    is_time = False
    if int(np.isnan(x).sum()) > len(x) / 2:
        t_hours, _ = parse_time_column(x_labels)
        if t_hours is not None:
            x, is_time = t_hours, True
        else:
            cat_labels = x_labels
            x = np.arange(len(x_labels), dtype=float)

    # ── Y columns: "D5:H14" spans columns, commas join ranges.
    y_columns = []
    for part in inp["y_range"].split(","):
        part = part.strip()
        if not part:
            continue
        yr1, yc1, yr2, yc2 = parse_range(part)
        for c in range(yc1, yc2 + 1):
            y_columns.append((yr1, c, yr2))
    if not y_columns:
        return {"error": "No Y range specified."}

    labels = list(inp.get("series_labels") or [])
    chart = None
    used_labels = []
    for i, (yr1, yc, yr2) in enumerate(y_columns):
        y_vals = []
        for r in range(yr1, yr2 + 1):
            try:
                y_vals.append(float(sheet.cell_text(r, yc)))
            except (ValueError, TypeError):
                y_vals.append(float("nan"))
        y = np.array(y_vals)
        if len(y) == 0:
            continue
        if i < len(labels) and labels[i]:
            label = labels[i]
        else:
            label = _header_text(sheet, yr1, yc) or col_index_to_letter(yc)
        used_labels.append(label)
        if chart is None:
            chart = EmbeddedChart(x, y, label, chart_type, sheet,
                                  sheet.table.viewport(),
                                  x_col=xc1, y_col=yc,
                                  row_start=yr1, row_end=yr2)
        else:
            chart.add_series(x, y, label, chart_type,
                             x_col=xc1, y_col=yc,
                             row_start=yr1, row_end=yr2)
    if chart is None:
        return {"error": "No numeric Y data found in the given ranges."}

    if is_time:
        chart._apply_time_x()
    elif cat_labels is not None:
        chart._apply_categorical_x(cat_labels)

    # ── Labels: explicit, else the header cell above each range.
    ax = chart._ax
    ax.set_xlabel(inp.get("x_label")
                  or _header_text(sheet, xr1, xc1) or "X")
    y_label = inp.get("y_label")
    if not y_label and len(used_labels) == 1:
        y_label = used_labels[0]
    ax.set_ylabel(y_label or "Y")
    if inp.get("title"):
        ax.set_title(inp["title"])

    if inp.get("preset"):
        _apply_preset(chart, inp["preset"])
    for key, setter in (("x_scale", ax.set_xscale),
                        ("y_scale", ax.set_yscale)):
        if inp.get(key):
            setter(inp[key])
    if "grid" in inp:
        ax.grid(bool(inp["grid"]))

    for i, color in enumerate(inp.get("colors") or []):
        if i < len(chart._series) and color:
            try:
                _style_one_series(chart, i, {"color": color})
            except ValueError:
                pass
    # Re-install after label/colour edits so swatches match.
    if chart_type not in ("Heatmap", "3D Surface"):
        _apply_legend(chart, inp.get("legend") or {})

    w = int(inp.get("width") or 480)
    h = int(inp.get("height") or 320)
    chart.resize(w, h)
    if inp.get("position"):
        _move_to_cell(sheet, chart, inp["position"])
    else:
        offset = len(sheet._charts) * 30
        chart.move(40 + offset, 40 + offset)
    sheet._charts.append(chart)
    sheet.data_changed.connect(chart._on_data_changed)
    chart._canvas.draw_idle()
    # The project's undo promise covers charts too: the command no-ops
    # on its first redo, since the chart is already on the sheet.
    from .undo_commands import InsertChartCmd
    ex._undo.push(InsertChartCmd(sheet, chart))
    return {"chart_created": True, "chart_type": chart_type,
            "chart_index": len(sheet._charts) - 1,
            "series_count": len(chart._series),
            "series_labels": used_labels}


def tool_modify_chart(ex, inp: dict) -> dict:
    """Axes, labels, limits, size and position of an existing chart."""
    sheet, chart = _chart(ex, inp)
    kwargs = {}
    for key in ("invert_x", "invert_y", "grid"):
        if key in inp:
            kwargs[key] = bool(inp[key])
    for key in ("x_scale", "y_scale", "title", "x_label", "y_label"):
        if key in inp:
            kwargs[key] = inp[key]
    applied = {}
    if kwargs:
        try:
            applied.update(chart.set_axis_options(**kwargs))
        except ValueError as exc:
            return {"error": f"Invalid value: {exc}"}

    ax = chart._ax
    for lo, hi, setter, getter in (
            ("x_min", "x_max", ax.set_xlim, ax.get_xlim),
            ("y_min", "y_max", ax.set_ylim, ax.get_ylim)):
        if lo in inp or hi in inp:
            cur = getter()
            setter(float(inp.get(lo, cur[0])), float(inp.get(hi, cur[1])))
            applied[lo] = inp.get(lo, cur[0])
            applied[hi] = inp.get(hi, cur[1])

    if "width" in inp or "height" in inp:
        w = int(inp.get("width", chart.width()))
        h = int(inp.get("height", chart.height()))
        chart.resize(w, h)
        applied["width"], applied["height"] = w, h
    if inp.get("position"):
        _move_to_cell(sheet, chart, inp["position"])
        applied["position"] = inp["position"]

    if "tight_layout" in inp:
        chart._tight_layout = bool(inp["tight_layout"])
        if not chart._tight_layout:
            try:
                chart._figure.set_layout_engine("none")
            except Exception:
                pass
        applied["tight_layout"] = chart._tight_layout
    if inp.get("margins"):
        allowed = ("left", "right", "top", "bottom")
        margins = {k: float(v) for k, v in inp["margins"].items()
                   if k in allowed}
        if margins:
            try:
                chart._figure.set_layout_engine("none")
            except Exception:
                pass
            chart._tight_layout = False
            chart._figure.subplots_adjust(**margins)
            applied["margins"] = margins

    if not applied:
        return {"error": "No changes specified. Provide at least one of: "
                "invert_x, invert_y, x_scale, y_scale, title, x_label, "
                "y_label, grid, x_min, x_max, y_min, y_max, width, "
                "height, position, tight_layout, margins."}
    chart._canvas.draw_idle()
    return {"modified": True, "index": int(inp.get("chart_index", 0)),
            "applied": applied}


def tool_style_chart(ex, inp: dict) -> dict:
    """Series styling, legend, fonts and overall look."""
    _sheet, chart = _chart(ex, inp)
    ax = chart._ax
    applied = {}

    if inp.get("preset"):
        if inp["preset"] not in PRESETS:
            return {"error": f"Unknown preset {inp['preset']!r}. "
                    f"Valid: {list(PRESETS)}"}
        _apply_preset(chart, inp["preset"])
        applied["preset"] = inp["preset"]

    styled = []
    for spec in inp.get("series") or []:
        try:
            styled.append(_style_one_series(chart, int(spec["index"]), spec))
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}
    if styled:
        applied["series"] = styled

    if "grid" in inp or "grid_axis" in inp:
        on = bool(inp.get("grid", True))
        ax.grid(on, axis=inp.get("grid_axis", "both"))
        ax.set_axisbelow(True)
        applied["grid"] = on
    if "title_size" in inp:
        ax.title.set_fontsize(float(inp["title_size"]))
        applied["title_size"] = inp["title_size"]
    if "label_size" in inp:
        ax.xaxis.label.set_fontsize(float(inp["label_size"]))
        ax.yaxis.label.set_fontsize(float(inp["label_size"]))
        applied["label_size"] = inp["label_size"]
    if "tick_size" in inp:
        ax.tick_params(labelsize=float(inp["tick_size"]))
        applied["tick_size"] = inp["tick_size"]
    if inp.get("face_color"):
        ax.set_facecolor(inp["face_color"])
        applied["face_color"] = inp["face_color"]
    if inp.get("figure_color"):
        chart._figure.set_facecolor(inp["figure_color"])
        applied["figure_color"] = inp["figure_color"]

    # Legend last: it has to pick up new colours and labels.
    if inp.get("legend") is not None or styled:
        applied["legend"] = _apply_legend(chart, inp.get("legend") or {})

    if not applied:
        return {"error": "No changes specified. Provide at least one of: "
                "preset, series, legend, grid, grid_axis, title_size, "
                "label_size, tick_size, face_color, figure_color."}
    chart._canvas.draw_idle()
    return {"styled": True, "index": int(inp.get("chart_index", 0)),
            "applied": applied}


def build_dispatch(ex) -> dict:
    """Chart tool names → bound callables, for AiToolExecutor."""
    return {
        "insert_chart": lambda inp: tool_insert_chart(ex, inp),
        "modify_chart": lambda inp: tool_modify_chart(ex, inp),
        "style_chart": lambda inp: tool_style_chart(ex, inp),
    }
