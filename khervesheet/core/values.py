"""Reading cell values for formulas, for any grid that can give a cell's text.

``CellValues`` is mixed into the desktop sheet (cells in a Qt table) and
into the Qt-free engine (cells in a dict).  A host provides:

- ``_cell_text(r, c)``  → the cell's displayed text ("" when empty)
- ``row_count()``        → number of rows, for whole-column functions
- ``_workbook()``        → an object with ``sheet_by_name(name)``, or None

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""


class CellValues:
    """The runtime helpers compiled formulas call: _C, _RANGE, _COL, _XC…"""

    #: Boolean cell text → its numeric value, as Excel coerces them.
    _BOOL_VALUES = {"TRUE": 1.0, "FALSE": 0.0}

    def _cell_text(self, r, c):  # pragma: no cover - provided by hosts
        raise NotImplementedError

    def row_count(self):  # pragma: no cover - provided by hosts
        raise NotImplementedError

    def _workbook(self):
        return None

    def _cell_val(self, r, c):
        t = self._cell_text(r, c)
        if t:
            try:
                return float(t)
            except ValueError:
                # TRUE/FALSE are values, not stray text: a checkbox
                # cell holds one, and =IF(A1,…) over it has to work.
                return self._BOOL_VALUES.get(t.strip().upper(), 0.0)
        return 0.0

    def _cell_raw(self, r, c):
        """Return the raw cell value: number if numeric, else string."""
        t = self._cell_text(r, c)
        if not t:
            return ""
        try:
            return float(t)
        except ValueError:
            return t

    def _apply_agg(self, func, vals):
        if func == "sum":
            return sum(vals) if vals else 0
        if func == "sumsq":
            return sum(v * v for v in vals) if vals else 0
        if func in ("average", "avg", "mean"):
            return sum(vals) / len(vals) if vals else 0
        if func == "min":
            return min(vals) if vals else 0
        if func == "max":
            return max(vals) if vals else 0
        if func in ("count", "counta"):
            return len(vals)
        if func == "stdev":
            if len(vals) < 2:
                return 0
            mn = sum(vals) / len(vals)
            return (sum((v - mn) ** 2 for v in vals)
                    / (len(vals) - 1)) ** 0.5
        return 0

    def _range_values(self, c1, r1, c2, r2):
        """Return the list of numeric values within a cell range."""
        vals = []
        text = self._cell_text
        for c in range(c1, c2 + 1):
            for r in range(r1, r2 + 1):
                t = text(r, c)
                if t:
                    try:
                        vals.append(float(t))
                    except ValueError:
                        # A boolean is a value here too, so SUM over a
                        # column of checkboxes counts the ticked ones.
                        b = self._BOOL_VALUES.get(t.strip().upper())
                        if b is not None:
                            vals.append(b)
        return vals

    def _range_values_2d(self, c1, r1, c2, r2):
        """Return a 2-D list (rows × cols) of cell values in a range."""
        text = self._cell_text
        rows = []
        for r in range(r1, r2 + 1):
            row = []
            for c in range(c1, c2 + 1):
                txt = text(r, c)
                if txt:
                    try:
                        row.append(float(txt))
                    except ValueError:
                        row.append(txt)
                else:
                    row.append(None)
            rows.append(row)
        return rows

    def _agg_range(self, func, c1, r1, c2, r2):
        vals = []
        text = self._cell_text
        for c in range(c1, c2 + 1):
            for r in range(r1, r2 + 1):
                t = text(r, c)
                if t:
                    try:
                        vals.append(float(t))
                    except ValueError:
                        pass
        return self._apply_agg(func, vals)

    def _agg_col(self, func, c):
        vals = []
        text = self._cell_text
        for r in range(self.row_count()):
            t = text(r, c)
            if t:
                try:
                    vals.append(float(t))
                except ValueError:
                    pass
        return self._apply_agg(func, vals)

    def _XC(self, name, r, c):
        """Read a single cell value from another sheet (Sheet!A1)."""
        wb = self._workbook()
        s = wb.sheet_by_name(name) if wb else None
        return s._cell_val(r, c) if s is not None else 0.0

    def _XRANGE(self, name, c1, r1, c2, r2):
        """Read a range of values from another sheet (Sheet!A1:B10)."""
        wb = self._workbook()
        s = wb.sheet_by_name(name) if wb else None
        return s._range_values(c1, r1, c2, r2) if s is not None else []
