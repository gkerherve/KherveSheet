"""ksheet_author — a small, Qt-free library for authoring rich .ksheet
example files.

A ``.ksheet`` file is an HDF5 container.  Its loader
(``MainWindow._load_ksheet``) is pure ``h5py`` + JSON and re-evaluates
formulas itself on open, so a complete, richly-formatted workbook can be
written here without launching the GUI or rendering anything.

Typical use::

    from ksheet_author import Workbook, Series

    wb = Workbook()
    s = wb.add_sheet("Data")
    s.title_block("Projectile Motion", "A worked physics example")
    s.table(3, 0,
            headers=["t (s)", "height (m)"],
            rows=[[t, f"=100*A{r}-4.9*A{r}*A{r}"] for r, t in ...])
    s.note(0, 4, "Edit the launch speed in B1 — the chart updates.")
    s.chart([Series(x, y, "height", "Line", color="#4472c4")],
            at=(520, 40), title="Trajectory", xlabel="t", ylabel="h")
    s.equation(r"h(t) = v_0 t - \\tfrac12 g t^2", at=(520, 360))
    wb.save("examples/Projectile Motion.ksheet")

This module only depends on ``h5py``, ``numpy`` and the project's
``khervesheet.cellformat`` (imported for guaranteed-correct format
serialisation; that import pulls in ``PyQt5.QtCore`` but never needs a
``QApplication``).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import h5py

# Make the project importable when this script is run from anywhere.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from PyQt5.QtCore import Qt  # noqa: E402 — only QtCore constants, no app
from khervesheet.cellformat import (  # noqa: E402
    CellFormat, BorderSpec, formats_to_json,
)

# ── Constants the agent can use by name ──────────────────────────────

#: Friendly alignment names → Qt alignment bitmask (vertically centred).
ALIGN = {
    "left": int(Qt.AlignLeft | Qt.AlignVCenter),
    "center": int(Qt.AlignHCenter | Qt.AlignVCenter),
    "right": int(Qt.AlignRight | Qt.AlignVCenter),
}

#: Border line styles.
BORDER_STYLE = {
    "solid": int(Qt.SolidLine),
    "dash": int(Qt.DashLine),
    "dot": int(Qt.DotLine),
}

#: A pleasant, Excel-like palette for fills / accents.
PALETTE = {
    "header": "#4472c4",      # blue header fill
    "header_text": "#ffffff",
    "band": "#d9e1f2",        # light blue banding
    "band_alt": "#eef3fb",
    "good": "#c6efce",        # green
    "warn": "#ffeb9c",        # amber
    "bad": "#ffc7ce",         # red
    "note": "#fff2a8",        # yellow sticky note
    "accent": "#ed7d31",
    "grid": "#bfbfbf",
}

#: Valid chart plot types (see graph.py).
PLOT_TYPES = ("Line", "Scatter", "Line+Symbol", "Bar", "Step", "Stem",
              "Histogram", "Box")


# ── Chart series ─────────────────────────────────────────────────────

@dataclass
class Series:
    """One data series for a chart.

    *x* / *y* are numeric sequences.  Extra keyword style attributes
    (``color``, ``linewidth``, ``linestyle``, ``marker``, ``markersize``,
    ``markerfacecolor``, ``markeredgecolor``) are written to the series
    ``props`` so they survive a round-trip and style the plot.
    """

    x: Sequence[float]
    y: Sequence[float]
    label: str = "series"
    plot_type: str = "Line"
    color: Optional[str] = None
    linewidth: Optional[float] = None
    linestyle: Optional[str] = None
    marker: Optional[str] = None
    markersize: Optional[float] = None
    markerfacecolor: Optional[str] = None
    markeredgecolor: Optional[str] = None

    def _props(self) -> dict:
        keys = ("color", "linewidth", "linestyle", "marker", "markersize",
                "markerfacecolor", "markeredgecolor")
        return {k: getattr(self, k) for k in keys
                if getattr(self, k) is not None}


# ── Sheet ────────────────────────────────────────────────────────────

class Sheet:
    """A single grid tab being authored."""

    def __init__(self, name: str):
        self.name = name
        self._cells: Dict[Tuple[int, int], str] = {}
        self._formats: Dict[Tuple[int, int], CellFormat] = {}
        self._merges: List[Tuple[int, int, int, int]] = []
        self._col_widths: Dict[int, int] = {}
        self._designations: Dict[int, str] = {}
        self._notes: Dict[str, dict] = {}
        self._links: Dict[str, str] = {}
        self._dropdowns: Dict[str, List[str]] = {}
        self._charts: List[dict] = []
        self._equations: List[dict] = []
        self._max_row = 0
        self._max_col = 0

    # ── Cell content ─────────────────────────────────────────────────

    def set(self, row: int, col: int, value) -> "Sheet":
        """Write a literal value (string/number) to a cell."""
        self._cells[(row, col)] = "" if value is None else str(value)
        self._grow(row, col)
        return self

    def formula(self, row: int, col: int, expr: str) -> "Sheet":
        """Write a formula.  ``expr`` should start with ``=``."""
        if not expr.startswith("="):
            expr = "=" + expr
        self._cells[(row, col)] = expr
        self._grow(row, col)
        return self

    def _grow(self, row: int, col: int):
        self._max_row = max(self._max_row, row)
        self._max_col = max(self._max_col, col)

    # ── Formatting ───────────────────────────────────────────────────

    def fmt(self, row: int, col: int, *, bold=None, italic=None,
            underline=None, bg=None, font_color=None, font_family=None,
            font_size=None, align=None, number_format=None,
            wrap=None) -> "Sheet":
        """Apply visual formatting to one cell.

        *align* accepts ``"left"`` / ``"center"`` / ``"right"``.
        *bg* / *font_color* are hex strings like ``"#4472c4"``.
        """
        cf = self._formats.setdefault((row, col), CellFormat())
        if bold is not None:
            cf.bold = bold
        if italic is not None:
            cf.italic = italic
        if underline is not None:
            cf.underline = underline
        if bg is not None:
            cf.bg_color = bg
        if font_color is not None:
            cf.font_color = font_color
        if font_family is not None:
            cf.font_family = font_family
        if font_size is not None:
            cf.font_size = float(font_size)
        if align is not None:
            cf.alignment = ALIGN.get(align, align)
        if number_format is not None:
            cf.number_format = number_format
        if wrap is not None:
            cf.wrap_text = wrap
        self._grow(row, col)
        return self

    def fmt_range(self, r1, c1, r2, c2, **kw) -> "Sheet":
        """Apply :meth:`fmt` to every cell in a rectangular block."""
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                self.fmt(r, c, **kw)
        return self

    def box(self, r1, c1, r2, c2, *, color="#000000", width=1.0,
            style="solid", inner=False) -> "Sheet":
        """Draw borders around (and optionally inside) a block."""
        st = BORDER_STYLE.get(style, int(Qt.SolidLine))

        def edge(r, c, side):
            cf = self._formats.setdefault((r, c), CellFormat())
            setattr(cf, f"border_{side}",
                    BorderSpec(style=st, color=color, width=width))
            self._grow(r, c)

        for c in range(c1, c2 + 1):
            edge(r1, c, "top")
            edge(r2, c, "bottom")
        for r in range(r1, r2 + 1):
            edge(r, c1, "left")
            edge(r, c2, "right")
        if inner:
            for r in range(r1, r2 + 1):
                for c in range(c1, c2 + 1):
                    edge(r, c, "top")
                    edge(r, c, "bottom")
                    edge(r, c, "left")
                    edge(r, c, "right")
        return self

    def merge(self, row, col, row_span, col_span) -> "Sheet":
        """Merge a block of cells (anchor at top-left)."""
        self._merges.append((row, col, row_span, col_span))
        self._grow(row + row_span - 1, col + col_span - 1)
        return self

    def col_width(self, col: int, px: int) -> "Sheet":
        self._col_widths[col] = int(px)
        self._grow(0, col)
        return self

    def designate(self, col: int, role: str) -> "Sheet":
        """Mark a column as ``"X"`` or ``"Y"`` (for chart axis hints)."""
        self._designations[col] = role
        self._grow(0, col)
        return self

    # ── High-level helpers ───────────────────────────────────────────

    def title_block(self, title: str, subtitle: str = "",
                    row: int = 0, col: int = 0, span: int = 6) -> "Sheet":
        """Big bold title with an optional subtitle line underneath."""
        self.set(row, col, title)
        self.fmt(row, col, bold=True, font_size=18,
                 font_color=PALETTE["header"])
        self.merge(row, col, 1, span)
        if subtitle:
            self.set(row + 1, col, subtitle)
            self.fmt(row + 1, col, italic=True, font_color="#555555")
            self.merge(row + 1, col, 1, span)
        return self

    def table(self, start_row: int, start_col: int, *,
              headers: Sequence[str],
              rows: Sequence[Sequence],
              number_format: Optional[str] = None,
              banded: bool = True,
              align_data: str = "right") -> "Sheet":
        """Write a styled table: filled bold header, banded rows, border.

        ``rows`` cells beginning with ``=`` are treated as formulas.
        Returns self; the block spans ``len(rows)+1`` rows.
        """
        ncol = len(headers)
        # Header.
        for j, h in enumerate(headers):
            c = start_col + j
            self.set(start_row, c, h)
            self.fmt(start_row, c, bold=True, bg=PALETTE["header"],
                     font_color=PALETTE["header_text"], align="center")
        # Body.
        for i, row in enumerate(rows):
            r = start_row + 1 + i
            band = (PALETTE["band_alt"] if (banded and i % 2) else None)
            for j in range(ncol):
                c = start_col + j
                val = row[j] if j < len(row) else ""
                if isinstance(val, str) and val.startswith("="):
                    self.formula(r, c, val)
                else:
                    self.set(r, c, val)
                kw = dict(align=align_data)
                if band:
                    kw["bg"] = band
                if number_format and j > 0:
                    kw["number_format"] = number_format
                self.fmt(r, c, **kw)
        # First column left-aligned (labels).
        for i in range(len(rows)):
            self.fmt(start_row + 1 + i, start_col, align="left")
        # Outer border.
        self.box(start_row, start_col,
                 start_row + len(rows), start_col + ncol - 1,
                 color=PALETTE["header"], width=1.0)
        return self

    # ── Annotations ──────────────────────────────────────────────────

    def note(self, row: int, col: int, text: str,
             kind: str = "note") -> "Sheet":
        """Attach a sticky note (``kind="note"`` = yellow rectangle) or a
        ``kind="comment"`` to a cell."""
        self._notes[f"{row},{col}"] = {"text": text, "kind": kind}
        self._grow(row, col)
        return self

    def link(self, row: int, col: int, url: str) -> "Sheet":
        self._links[f"{row},{col}"] = url
        self._grow(row, col)
        return self

    def dropdown(self, row: int, col: int,
                 options: Sequence[str]) -> "Sheet":
        self._dropdowns[f"{row},{col}"] = list(options)
        self._grow(row, col)
        return self

    # ── Embedded objects ─────────────────────────────────────────────

    def chart(self, series: Sequence[Series], *, at=(480, 40),
              size=(420, 300), title="", xlabel="X", ylabel="Y",
              grid=True, legend=True, xscale="linear",
              yscale="linear") -> "Sheet":
        """Add a matplotlib chart overlay built from *series*."""
        ser_dicts = []
        for s in series:
            d = {
                "x": np.asarray(s.x, dtype=float),
                "y": np.asarray(s.y, dtype=float),
                "label": s.label,
                "plot_type": s.plot_type,
                "props": s._props(),
            }
            ser_dicts.append(d)
        self._charts.append({
            "series": ser_dicts,
            "pos_x": int(at[0]), "pos_y": int(at[1]),
            "width": int(size[0]), "height": int(size[1]),
            "title": title, "xlabel": xlabel, "ylabel": ylabel,
            "xscale": xscale, "yscale": yscale, "grid": bool(grid),
            "legend_visible": bool(legend),
        })
        return self

    def equation(self, latex: str, *, at=(480, 360), fontsize=20,
                 color="#000000", bg_color=None, border_color=None,
                 border_width=1.0, size=None) -> "Sheet":
        """Embed a LaTeX equation (rendered with matplotlib mathtext)."""
        d = {
            "latex": latex, "fontsize": int(fontsize), "color": color,
            "bg_color": bg_color, "border_color": border_color,
            "border_width": float(border_width),
            "pos_x": int(at[0]), "pos_y": int(at[1]), "group_id": None,
        }
        if size is not None:
            d["width"], d["height"] = int(size[0]), int(size[1])
        self._equations.append(d)
        return self

    # ── HDF5 emission ────────────────────────────────────────────────

    def _dims(self, min_rows: int, min_cols: int) -> Tuple[int, int]:
        return (max(self._max_row + 1, min_rows),
                max(self._max_col + 1, min_cols))

    def _write(self, f: h5py.File, index: int,
               min_rows: int, min_cols: int):
        n_rows, n_cols = self._dims(min_rows, min_cols)
        sg = f.create_group(f"sheet_{index}")
        sg.attrs["name"] = self.name
        sg.attrs["rows"] = n_rows
        sg.attrs["cols"] = n_cols

        # Cells (row-major flat string array; formulas stored verbatim).
        data = [self._cells.get((r, c), "")
                for r in range(n_rows) for c in range(n_cols)]
        sg.create_dataset("cells", data=data, dtype=h5py.string_dtype())

        # Formats.
        fmt_json = formats_to_json(self._formats)
        if fmt_json:
            sg.attrs["cell_formats"] = fmt_json

        # Merges.
        if self._merges:
            sg.attrs["merged_ranges"] = json.dumps(
                [list(m) for m in self._merges])

        # Designations.
        if self._designations:
            sg.attrs["col_designations"] = json.dumps(
                {str(k): v for k, v in self._designations.items()})

        # Insert-ops (notes / links / dropdowns).
        iops = {}
        if self._notes:
            iops["notes"] = self._notes
        if self._links:
            iops["links"] = self._links
        if self._dropdowns:
            iops["dropdowns"] = self._dropdowns
        if iops:
            sg.attrs["insert_ops"] = json.dumps(iops)

        # Column widths (one per column; default 90 px).
        widths = [self._col_widths.get(c, 90) for c in range(n_cols)]
        sg.create_dataset("col_widths", data=widths)

        # Charts.
        sg.attrs["chart_count"] = len(self._charts)
        for ci, ch in enumerate(self._charts):
            cg = sg.create_group(f"chart_{ci}")
            cg.attrs["pos_x"] = ch["pos_x"]
            cg.attrs["pos_y"] = ch["pos_y"]
            cg.attrs["width"] = ch["width"]
            cg.attrs["height"] = ch["height"]
            cg.attrs["title"] = ch["title"]
            cg.attrs["xlabel"] = ch["xlabel"]
            cg.attrs["ylabel"] = ch["ylabel"]
            cg.attrs["xscale"] = ch["xscale"]
            cg.attrs["yscale"] = ch["yscale"]
            cg.attrs["grid"] = ch["grid"]
            cg.attrs["legend_visible"] = ch["legend_visible"]
            cg.attrs["legend_size"] = 8
            cg.attrs["series_count"] = len(ch["series"])
            for ki, s in enumerate(ch["series"]):
                srg = cg.create_group(f"series_{ki}")
                srg.create_dataset("x", data=s["x"])
                srg.create_dataset("y", data=s["y"])
                srg.attrs["label"] = s["label"]
                srg.attrs["plot_type"] = s["plot_type"]
                if s["props"]:
                    srg.attrs["props"] = json.dumps(s["props"])

        # Images / shapes: none from this authoring API.
        sg.attrs["image_count"] = 0
        sg.attrs["shape_count"] = 0

        # Equations.
        sg.attrs["equation_count"] = len(self._equations)
        for ei, eq in enumerate(self._equations):
            eqg = sg.create_group(f"equation_{ei}")
            eqg.attrs["data"] = json.dumps(eq)


# ── Workbook ─────────────────────────────────────────────────────────

class Workbook:
    """A collection of sheets that serialises to a ``.ksheet`` file."""

    def __init__(self, min_rows: int = 40, min_cols: int = 14):
        self.sheets: List[Sheet] = []
        self.min_rows = min_rows
        self.min_cols = min_cols

    def add_sheet(self, name: str) -> Sheet:
        s = Sheet(name)
        self.sheets.append(s)
        return s

    def save(self, path: str):
        """Write the workbook to *path* (creates parent dirs)."""
        if not self.sheets:
            raise ValueError("Workbook has no sheets.")
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with h5py.File(path, "w") as f:
            f.attrs["format"] = "ksheet"
            f.attrs["version"] = 1
            f.attrs["sheet_count"] = len(self.sheets)
            for i, sheet in enumerate(self.sheets):
                sheet._write(f, i, self.min_rows, self.min_cols)
        return path
