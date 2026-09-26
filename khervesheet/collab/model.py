"""Shared-document layout for live co-editing, and workbook snapshots.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

The Yjs document holds four flat maps, so every edit is one key:

- ``sheets``  — sheet id → JSON ``{"name", "order", "rows", "cols"}``
- ``cells``   — ``"<sheet id>|<row>,<col>"`` → cell source (the formula
  if the cell has one, else its text)
- ``formats`` — same keys → JSON of ``CellFormat.to_dict()``
- ``widths``  — ``"<sheet id>|<col>"`` → column width in pixels

Cells store *sources*, never computed values: each window recalculates
formulas itself, exactly as when a file is opened.
"""

from __future__ import annotations

import json
import uuid
from typing import Dict, Iterable, Tuple

SHEETS = "sheets"
CELLS = "cells"
FORMATS = "formats"
WIDTHS = "widths"

Cell = Tuple[int, int]


def new_sheet_id() -> str:
    return uuid.uuid4().hex[:12]


def cell_key(sheet_id: str, row: int, col: int) -> str:
    return f"{sheet_id}|{row},{col}"


def parse_cell_key(key: str) -> Tuple[str, int, int]:
    sheet_id, _, rc = key.partition("|")
    row, _, col = rc.partition(",")
    return sheet_id, int(row), int(col)


def width_key(sheet_id: str, col: int) -> str:
    return f"{sheet_id}|{col}"


def parse_width_key(key: str) -> Tuple[str, int]:
    sheet_id, _, col = key.partition("|")
    return sheet_id, int(col)


def sheet_id_of(key: str) -> str:
    return key.partition("|")[0]


def encode_json(value) -> str:
    """Stable JSON, so equal values compare equal as strings."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


# ── Snapshots of a SheetWidget (duck-typed, so tests can use fakes) ──

def _number_source(value: float) -> str:
    """A number as typed: 10 not 10.0, full precision."""
    if value.is_integer() and abs(value) < 1e15:
        return str(int(value))
    return repr(value)


def cell_source(sheet, row: int, col: int) -> str:
    """One cell's source: its formula, else its value ("" when empty).

    A number is shared at full precision (the sheet remembers the exact
    value behind its rounded text), not as the 2-decimal text on screen."""
    source = sheet._cell_formulas.get((row, col))
    if source:
        return source
    item = sheet.table.item(row, col)
    text = item.text() if item is not None else ""
    known = getattr(sheet, "_precise", {}).get((row, col))
    if text and known is not None and known[0] == text:
        return _number_source(known[1])
    return text


def cell_sources(sheet) -> Dict[Cell, str]:
    """Every non-empty cell's source (see cell_source)."""
    table = sheet.table
    out: Dict[Cell, str] = {}
    for row in range(table.rowCount()):
        for col in range(table.columnCount()):
            source = cell_source(sheet, row, col)
            if source:
                out[(row, col)] = source
    return out


def cell_formats(sheet) -> Dict[Cell, str]:
    out: Dict[Cell, str] = {}
    for cell, fmt in sheet._cell_formats.items():
        data = fmt.to_dict()
        if data:
            out[cell] = encode_json(data)
    return out


def column_widths(sheet) -> Dict[int, int]:
    """Widths of the columns that differ from the default."""
    header = sheet.table.horizontalHeader()
    default = header.defaultSectionSize()
    return {col: header.sectionSize(col)
            for col in range(sheet.table.columnCount())
            if header.sectionSize(col) != default}


def diff(old: Dict, new: Dict) -> Tuple[Dict, set]:
    """What changed from ``old`` to ``new``: (set or changed, removed)."""
    changed = {key: value for key, value in new.items()
               if old.get(key) != value}
    removed = set(old) - set(new)
    return changed, removed


def keys_for_sheet(keys: Iterable[str], sheet_id: str):
    prefix = f"{sheet_id}|"
    return [key for key in keys if key.startswith(prefix)]
