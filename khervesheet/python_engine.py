"""Python-in-cell engine for KherveSheet.

Provides an Excel-style ``=PY`` cell: a cell holds real Python source
(including multi-line ``def``s).  All Python cells in a workbook share a
single namespace, so a function or variable defined in one cell is visible
to later cells.  A cell's value is the value of its trailing expression
(Excel semantics); arrays spill, other objects are held live in the cell
(referenced from other cells via ``xl()``), and matplotlib figures are
captured for embedding.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import ast
import re

from PyQt5.QtGui import (
    QColor, QFont, QSyntaxHighlighter, QTextCharFormat,
)

# Marker that flags a cell as Python source.  Stored as the first line of
# the cell text so Python cells round-trip through the existing formula
# persistence (``_cell_formulas``) unchanged.
PY_MARKER = "=PY"

# Matches xl("A1"), cell('A1:B10'), xl("Sheet1!A1") inside source so the
# referenced cells can be registered as dependencies.
_XL_CALL = re.compile(r"\b(?:xl|cell)\s*\(\s*([\"'])(.+?)\1")


def is_python_source(text) -> bool:
    """True if *text* is a Python cell (starts with the =PY marker)."""
    return isinstance(text, str) and text.lstrip().upper().startswith(PY_MARKER)


def strip_marker(text: str) -> str:
    """Return the raw Python code with the leading =PY marker removed."""
    s = text.lstrip()
    body = s[len(PY_MARKER):]
    # Drop a single leading newline or space that separates marker & code.
    if body[:1] in ("\n", " "):
        body = body[1:]
    return body


def extract_refs(code: str):
    """Yield the A1-style ref strings used in xl()/cell() calls in *code*."""
    return [m.group(2) for m in _XL_CALL.finditer(code or "")]


class PyResult:
    """Outcome of running one Python cell."""

    SCALAR = "scalar"
    ARRAY1D = "array1d"
    ARRAY2D = "array2d"
    OBJECT = "object"
    FIGURE = "figure"
    NONE = "none"

    def __init__(self, value=None, kind=NONE, figure=None, error=None):
        self.value = value
        self.kind = kind
        self.figure = figure
        self.error = error      # traceback string, or None

    @property
    def ok(self):
        return self.error is None


def _classify(value):
    """Map a Python value to a (kind, normalised_value) pair."""
    if value is None:
        return PyResult.NONE, None

    # Matplotlib figure?
    try:
        from matplotlib.figure import Figure
        if isinstance(value, Figure):
            return PyResult.FIGURE, value
    except Exception:
        pass

    # Scalars (treat numpy 0-d scalars and bools/str as scalar).
    if isinstance(value, (bool, int, float, complex, str)):
        return PyResult.SCALAR, value
    try:
        import numpy as np
        if isinstance(value, np.generic):
            return PyResult.SCALAR, value.item()
    except Exception:
        pass

    # Plain lists/tuples spill into the grid; nested sequences are 2-D.
    # numpy arrays, DataFrames, dicts, etc. are kept live in the cell as
    # objects (referenced from other cells via xl()) — to spill an array,
    # call .tolist() on it.
    if isinstance(value, (list, tuple)):
        seq = list(value)
        if seq and all(isinstance(r, (list, tuple)) for r in seq):
            return PyResult.ARRAY2D, [list(r) for r in seq]
        if all(not isinstance(r, (list, tuple, dict)) for r in seq):
            return PyResult.ARRAY1D, seq
        return PyResult.OBJECT, value

    return PyResult.OBJECT, value


def badge_for(value) -> str:
    """Short type badge shown in the grid for an object-valued cell."""
    try:
        import numpy as np
        if isinstance(value, np.ndarray):
            shape = ", ".join(str(d) for d in value.shape)
            if value.ndim == 1:
                shape += ","
            return f"▮ ndarray({shape})"
    except Exception:
        pass
    try:
        import pandas as pd
        if isinstance(value, pd.DataFrame):
            return f"▮ DataFrame[{value.shape[0]}×{value.shape[1]}]"
        if isinstance(value, pd.Series):
            return f"▮ Series[{len(value)}]"
    except Exception:
        pass
    if isinstance(value, dict):
        return f"▮ dict[{len(value)}]"
    return f"▮ {type(value).__name__}"


class PythonRuntime:
    """Owns the shared namespace for every ``=PY`` cell in a workbook."""

    def __init__(self):
        self._globals = None
        self._sheet = None      # sheet bound to the current run (for xl())

    # ── namespace ────────────────────────────────────────────────────
    def _ensure_globals(self):
        if self._globals is not None:
            return self._globals
        g = {"__builtins__": __builtins__}
        import math
        g["math"] = math
        try:
            import numpy as np
            g["np"] = np
            g["numpy"] = np
        except Exception:
            pass
        try:
            import matplotlib
            matplotlib.use("Agg", force=False)
            import matplotlib.pyplot as plt
            g["plt"] = plt
        except Exception:
            pass
        try:
            import pandas as pd
            g["pd"] = pd
            g["pandas"] = pd
        except Exception:
            pass
        try:
            import scipy
            g["scipy"] = scipy
        except Exception:
            pass
        # Range/cell access helpers — late-bound to the running sheet.
        g["xl"] = self._xl
        g["cell"] = self._xl
        self._globals = g
        return g

    def reset(self):
        """Forget all definitions (e.g. when a workbook is closed)."""
        self._globals = None

    # ── xl() / cell() ────────────────────────────────────────────────
    def _xl(self, ref):
        """Resolve an A1-style ref against the sheet bound for this run."""
        sheet = self._sheet
        if sheet is None:
            raise RuntimeError("xl() is only available inside a =PY cell")
        return resolve_ref(sheet, str(ref))

    # ── execution ────────────────────────────────────────────────────
    def run(self, code, sheet, row, col) -> PyResult:
        """Execute *code* in the shared namespace and classify its value."""
        import traceback
        g = self._ensure_globals()
        self._sheet = sheet
        plt = g.get("plt")
        before = set(plt.get_fignums()) if plt is not None else set()
        try:
            value = self._exec_with_value(code, g)
        except Exception:
            return PyResult(error=traceback.format_exc())
        finally:
            self._sheet = None

        kind, norm = _classify(value)

        # If the cell did not itself yield a figure but created one, grab it.
        if kind != PyResult.FIGURE and plt is not None:
            new = [n for n in plt.get_fignums() if n not in before]
            if new:
                fig = plt.figure(new[-1])
                return PyResult(value=fig, kind=PyResult.FIGURE, figure=fig)

        if kind == PyResult.FIGURE:
            return PyResult(value=norm, kind=kind, figure=norm)
        return PyResult(value=norm, kind=kind)

    @staticmethod
    def _exec_with_value(code, g):
        """Exec all but a trailing expression, eval the trailing expr."""
        tree = ast.parse(code, "<py-cell>", "exec")
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last = ast.Expression(tree.body[-1].value)
            head = ast.Module(body=tree.body[:-1], type_ignores=[])
            exec(compile(head, "<py-cell>", "exec"), g)        # noqa: S102
            return eval(compile(last, "<py-cell>", "eval"), g)  # noqa: S307
        exec(compile(tree, "<py-cell>", "exec"), g)            # noqa: S102
        return None


# ── ref resolution ──────────────────────────────────────────────────

_REF_RE = re.compile(r"^\$?([A-Za-z]{1,3})\$?(\d{1,7})$")
_RANGE_RE = re.compile(
    r"^\$?([A-Za-z]{1,3})\$?(\d{1,7})\s*:\s*\$?([A-Za-z]{1,3})\$?(\d{1,7})$")


def _read_one(sheet, r, c):
    """Live object if the cell holds one, else its parsed scalar value."""
    objs = getattr(sheet, "_cell_objects", None)
    if objs and (r, c) in objs:
        return objs[(r, c)]
    it = sheet.table.item(r, c)
    if it is None or not it.text():
        return None
    txt = it.text()
    try:
        f = float(txt)
        return int(f) if f.is_integer() else f
    except ValueError:
        return txt


def resolve_ref(sheet, ref):
    """Resolve "A1", "A1:B10" or "Sheet1!A1" to a value/array.

    A single cell → its value (object or scalar).  A 1-D range → a numpy
    array (or list).  A 2-D block → a 2-D numpy array (or list of lists).
    """
    from .sheet import letter_to_col_index

    ref = ref.strip()

    # Cross-sheet: Sheet1!A1 or 'My Sheet'!A1:B2
    if "!" in ref:
        name, _, rest = ref.partition("!")
        name = name.strip().strip("'")
        wb = sheet._workbook() if hasattr(sheet, "_workbook") else None
        target = wb.sheet_by_name(name) if wb is not None else None
        if target is None:
            raise ValueError(f"unknown sheet: {name!r}")
        return resolve_ref(target, rest.strip())

    m = _REF_RE.match(ref)
    if m:
        c = letter_to_col_index(m.group(1))
        r = int(m.group(2)) - 1
        return _read_one(sheet, r, c)

    m = _RANGE_RE.match(ref)
    if not m:
        raise ValueError(f"bad cell reference: {ref!r}")
    c1 = letter_to_col_index(m.group(1))
    r1 = int(m.group(2)) - 1
    c2 = letter_to_col_index(m.group(3))
    r2 = int(m.group(4)) - 1
    if c1 > c2:
        c1, c2 = c2, c1
    if r1 > r2:
        r1, r2 = r2, r1

    rows = [[_read_one(sheet, r, c) for c in range(c1, c2 + 1)]
            for r in range(r1, r2 + 1)]

    # A single row or column collapses to a 1-D vector.
    flat = None
    if len(rows) == 1:
        flat = rows[0]
    elif all(len(r) == 1 for r in rows):
        flat = [r[0] for r in rows]

    try:
        import numpy as np
        if flat is not None:
            try:
                return np.array(flat, dtype=float)
            except (TypeError, ValueError):
                return flat
        try:
            return np.array(rows, dtype=float)
        except (TypeError, ValueError):
            return rows
    except Exception:
        return flat if flat is not None else rows


# ── editor widgets ──────────────────────────────────────────────────

class PythonHighlighter(QSyntaxHighlighter):
    """Minimal Python syntax highlighting for the in-cell code editor."""

    _KEYWORDS = (
        "def class return if elif else for while in is and or not import "
        "from as with try except finally raise lambda yield global nonlocal "
        "pass break continue None True False assert del").split()

    def __init__(self, document):
        super().__init__(document)
        self._rules = []

        kw = QTextCharFormat()
        kw.setForeground(QColor("#0000C0"))
        kw.setFontWeight(QFont.Bold)
        for word in self._KEYWORDS:
            self._rules.append((re.compile(rf"\b{word}\b"), kw))

        num = QTextCharFormat()
        num.setForeground(QColor("#098658"))
        self._rules.append((re.compile(r"\b\d+(\.\d+)?\b"), num))

        self._str_fmt = QTextCharFormat()
        self._str_fmt.setForeground(QColor("#A31515"))
        self._rules.append(
            (re.compile(r"'[^']*'|\"[^\"]*\""), self._str_fmt))

        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setForeground(QColor("#808080"))
        self._comment_fmt.setFontItalic(True)
        self._rules.append((re.compile(r"#.*$"), self._comment_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)
