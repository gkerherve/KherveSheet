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

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import (
    QColor, QFont, QSyntaxHighlighter, QTextCharFormat,
)
from PyQt5.QtWidgets import QPlainTextEdit, QDialog, QWidget

# Marker that flags a cell as Python source.  Stored as the first line of
# the cell text so Python cells round-trip through the existing formula
# persistence (``_cell_formulas``) unchanged.
PY_MARKER = "=PY"

# Matches ks("A1"), cell('A1:B10'), ks("Sheet1!A1") inside source so the
# referenced cells can be registered as dependencies.  (xl is kept as an
# alias for users coming from Excel.)
_XL_CALL = re.compile(r"\b(?:ks|xl|cell)\s*\(\s*([\"'])(.+?)\1")


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
    IMAGE = "image"
    NONE = "none"

    def __init__(self, value=None, kind=NONE, figure=None, error=None,
                 stdout=""):
        self.value = value
        self.kind = kind
        self.figure = figure
        self.error = error      # traceback string, or None
        self.stdout = stdout    # captured print() output

    @property
    def ok(self):
        return self.error is None


def to_pixmap(value):
    """Convert an image-like value to a QPixmap, or return None.

    Accepts a QPixmap, QImage, PIL.Image, raw PNG/JPEG bytes, or a NumPy
    H×W×3/4 uint8 array."""
    from PyQt5.QtGui import QPixmap, QImage
    if isinstance(value, QPixmap):
        return value if not value.isNull() else None
    if isinstance(value, QImage):
        return QPixmap.fromImage(value) if not value.isNull() else None
    if isinstance(value, (bytes, bytearray)):
        pm = QPixmap()
        pm.loadFromData(bytes(value))
        return pm if not pm.isNull() else None
    # PIL image?
    try:
        from PIL import Image
        if isinstance(value, Image.Image):
            import io
            buf = io.BytesIO()
            value.convert("RGBA").save(buf, format="PNG")
            pm = QPixmap()
            pm.loadFromData(buf.getvalue())
            return pm if not pm.isNull() else None
    except Exception:
        pass
    # NumPy H×W×3/4 uint8 image array?
    try:
        import numpy as np
        if (isinstance(value, np.ndarray) and value.ndim == 3
                and value.shape[2] in (3, 4)):
            a = np.ascontiguousarray(value.astype(np.uint8))
            h, w, ch = a.shape
            fmt = QImage.Format_RGBA8888 if ch == 4 else QImage.Format_RGB888
            img = QImage(a.data, w, h, ch * w, fmt).copy()
            return QPixmap.fromImage(img)
    except Exception:
        pass
    return None


def ks_image(src, timeout=8):
    """Load an image from a URL, file path, bytes, or image object and
    return a QPixmap (for a =PY cell to display).  Use as the last line of
    a cell, e.g. ks_image("https://example.com/photo.jpg")."""
    if isinstance(src, str):
        if src.startswith(("http://", "https://")):
            import urllib.request
            req = urllib.request.Request(
                src, headers={"User-Agent": "KherveSheet"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                from PyQt5.QtGui import QPixmap
                pm = QPixmap()
                pm.loadFromData(r.read())
                if pm.isNull():
                    raise ValueError("ks_image: could not decode the image")
                return pm
        from PyQt5.QtGui import QPixmap
        pm = QPixmap(src)               # local file path
        if pm.isNull():
            raise ValueError(f"ks_image: could not load {src!r}")
        return pm
    pm = to_pixmap(src)
    if pm is None:
        raise ValueError("ks_image: unsupported image source")
    return pm


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

    # An image (QPixmap/QImage/PIL/bytes/HxWx3 array) -> embed as a picture.
    pm = to_pixmap(value)
    if pm is not None:
        return PyResult.IMAGE, pm

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
        self._cur_cell = None   # (row, col) of the running cell (for ks_set)
        self._written = None    # cells written via ks_set during a run
        self._last_writes = set()  # cells written by the most recent run
        #: Max seconds a single =PY cell may run before it is aborted.
        #: Guards against infinite loops freezing the app.  Set to 0/None
        #: to disable.
        self.timeout = 30.0

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
        # ks() is the KherveSheet accessor; xl()/cell() are aliases.
        g["ks"] = self._xl
        g["xl"] = self._xl
        g["cell"] = self._xl
        # Write-back helpers: push values/arrays into the grid.
        g["ks_set"] = self._ks_set
        g["write"] = self._ks_set
        # Image helper: load a picture (URL / path / bytes) to embed.
        g["ks_image"] = ks_image
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
            raise RuntimeError("ks() is only available inside a =PY cell")
        return resolve_ref(sheet, str(ref))

    def _ks_set(self, ref, value):
        """Write *value* into the grid at *ref* (a cell or range).

        A scalar fills the whole range; a 1-D list/array writes down a
        column (or across a single-row range); a 2-D array writes a block.
        The cell currently running is never overwritten.
        """
        sheet = self._sheet
        if sheet is None:
            raise RuntimeError("ks_set() is only available inside a =PY cell")
        if "!" in str(ref):
            raise ValueError("ks_set() cannot write to another sheet")
        coords = parse_ref_coords(str(ref))
        sheet._py_write(coords, value, self._cur_cell, self._written)
        return value

    # ── execution ────────────────────────────────────────────────────
    def run(self, code, sheet, row, col) -> PyResult:
        """Execute *code* in the shared namespace and classify its value."""
        import contextlib
        import io
        import traceback
        g = self._ensure_globals()
        # Re-entrancy safe: a ks_set()-triggered recalc may run another
        # =PY cell while this one is mid-flight, so save/restore context.
        prev_sheet, prev_cell, prev_written = (
            self._sheet, self._cur_cell, self._written)
        self._sheet = sheet
        self._cur_cell = (row, col)
        self._written = set()
        plt = g.get("plt")
        before = set(plt.get_fignums()) if plt is not None else set()
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                value = self._call_with_timeout(
                    lambda: self._exec_with_value(code, g))
        except TimeoutError:
            return PyResult(
                error=("TimeoutError: execution exceeded "
                       f"{self.timeout:g} s — possible infinite loop. "
                       "Increase the limit or fix the code."),
                stdout=buf.getvalue())
        except Exception:
            return PyResult(error=traceback.format_exc(),
                            stdout=buf.getvalue())
        finally:
            self._last_writes = self._written or set()
            self._sheet, self._cur_cell, self._written = (
                prev_sheet, prev_cell, prev_written)
        out = buf.getvalue()

        kind, norm = _classify(value)

        # If the cell did not itself yield a figure/image but created a
        # matplotlib figure, grab it.
        if kind not in (PyResult.FIGURE, PyResult.IMAGE) and plt is not None:
            new = [n for n in plt.get_fignums() if n not in before]
            if new:
                fig = plt.figure(new[-1])
                return PyResult(value=fig, kind=PyResult.FIGURE,
                                figure=fig, stdout=out)

        if kind == PyResult.FIGURE:
            return PyResult(value=norm, kind=kind, figure=norm, stdout=out)
        return PyResult(value=norm, kind=kind, stdout=out)

    def _call_with_timeout(self, fn):
        """Run *fn* on the calling thread with a timeout guard.

        A watchdog thread sets a flag after ``self.timeout`` seconds, and
        a ``sys.settrace`` hook checks that flag at every Python line,
        raising ``TimeoutError`` cleanly from pure-Python context.

        This is safe because:
        - The code runs on the calling (main) thread, so Qt widget
          access via ``ks()``/``ks_set()`` is legal.
        - The exception is raised from the trace hook at a Python line
          boundary, never inside C code — no stack corruption.
        - Unlike ``PyThreadState_SetAsyncExc``, this cannot cause
          STATUS_STACK_BUFFER_OVERRUN (0xC0000409) crashes.

        The only downside is that a single long-running C call (e.g. a
        huge numpy operation) will not be interrupted until it returns
        to Python, but that is acceptable.
        """
        timeout = self.timeout
        if not timeout or timeout <= 0:
            return fn()
        import sys
        import threading
        import time

        deadline = time.monotonic() + timeout
        expired = False

        def _watchdog():
            nonlocal expired
            remaining = deadline - time.monotonic()
            if remaining > 0:
                threading.Event().wait(remaining)
            expired = True

        def _trace(frame, event, arg):
            if expired:
                raise TimeoutError(
                    f"execution exceeded {timeout:g} s — possible "
                    "infinite loop.  Increase the limit or fix the code.")
            return _trace

        wd = threading.Thread(target=_watchdog, daemon=True)
        wd.start()
        old_trace = sys.gettrace()
        sys.settrace(_trace)
        try:
            return fn()
        finally:
            sys.settrace(old_trace)
            expired = True  # stop watchdog early

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


def parse_ref_coords(ref):
    """Parse "A1" or "A1:B10" → (r1, c1, r2, c2), 0-indexed, normalised."""
    from .sheet import letter_to_col_index
    ref = ref.strip()
    m = _REF_RE.match(ref)
    if m:
        c = letter_to_col_index(m.group(1))
        r = int(m.group(2)) - 1
        return r, c, r, c
    m = _RANGE_RE.match(ref)
    if not m:
        raise ValueError(f"bad cell reference: {ref!r}")
    c1 = letter_to_col_index(m.group(1))
    r1 = int(m.group(2)) - 1
    c2 = letter_to_col_index(m.group(3))
    r2 = int(m.group(4)) - 1
    return min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2)


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


# ── "PY" badge (Python brand colours) ────────────────────────────────

PY_BLUE = "#3776ab"      # Python logo blue
PY_YELLOW = "#ffd43b"    # Python logo yellow
#: Very faint Python-blue tint for the body of a =PY cell / formula bar.
PY_TINT = QColor(55, 118, 171, 12)


def fmt_loop_period(secs):
    """Compact label for a loop interval, e.g. 5 -> '5s', 90 -> '2m'."""
    secs = float(secs)
    if secs < 1:
        return f"{secs:g}s"
    secs = int(round(secs))
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    return f"{secs // 3600}h"


def _draw_refresh(painter, cx, cy, rad, color):
    """Draw a small circular-arrow (refresh) glyph centred at (cx, cy)."""
    import math
    from PyQt5.QtCore import QRectF, QPointF
    from PyQt5.QtGui import QPen, QPolygonF
    painter.save()
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(color, max(1.0, rad * 0.35), Qt.SolidLine,
                        Qt.RoundCap))
    rr = QRectF(cx - rad, cy - rad, 2 * rad, 2 * rad)
    painter.drawArc(rr, int(105 * 16), int(-300 * 16))     # ~300° arc
    # Arrowhead at the open (start) end, ~105°.
    a = math.radians(105)
    ex, ey = cx + rad * math.cos(a), cy - rad * math.sin(a)
    h = rad * 0.7
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawPolygon(QPolygonF([
        QPointF(ex + h, ey - h * 0.2),
        QPointF(ex - h * 0.2, ey - h),
        QPointF(ex - h * 0.3, ey + h * 0.3),
    ]))
    painter.restore()


def paint_py_badge(painter, rect, loop_secs=None):
    """Paint a rounded, two-tone (Python blue over yellow), raised "PY"
    badge into *rect*.  When *loop_secs* is set, the badge shows a refresh
    glyph and the period (e.g. "5s") instead of the logo eyes."""
    from PyQt5.QtCore import QRectF, QPointF
    from PyQt5.QtGui import QPainter, QPainterPath, QPen
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    r = QRectF(rect).adjusted(1.5, 1.5, -1.5, -1.5)
    if r.width() <= 1 or r.height() <= 1:
        painter.restore()
        return
    radius = min(6.0, r.width() * 0.40)
    clip = QPainterPath()
    clip.addRoundedRect(r, radius, radius)
    painter.setClipPath(clip)
    half = r.height() / 2.0
    painter.fillRect(QRectF(r.left(), r.top(), r.width(), half),
                     QColor(PY_BLUE))                       # top = blue
    painter.fillRect(QRectF(r.left(), r.top() + half, r.width(),
                            r.height() - half),
                     QColor(PY_YELLOW))                     # bottom = yellow
    if loop_secs is None:
        # Two tiny white "eyes" echoing the Python logo (blue top-left,
        # yellow bottom-right), diagonally arranged.
        dot = max(1.0, r.width() * 0.12)
        dx = r.width() * 0.17
        dy = r.height() * 0.17
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QPointF(r.center().x()-dx, r.top()+dy), dot, dot)
        painter.drawEllipse(QPointF(r.center().x()+dx, r.bottom()-dy),
                            dot, dot)
    painter.setClipping(False)
    # Raised bevel: light highlight inset, darker outer edge.
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QColor(255, 255, 255, 150), 1.2))
    painter.drawRoundedRect(r.adjusted(0.6, 0.6, -0.6, -0.6), radius, radius)
    painter.setPen(QPen(QColor(0, 0, 0, 80), 1.0))
    painter.drawRoundedRect(r, radius, radius)

    f = QFont(painter.font())
    f.setBold(True)
    if loop_secs is None:
        f.setPointSizeF(max(6.5, min(9.5, r.width() * 0.42)))
        painter.setFont(f)
        painter.setPen(QColor(0, 0, 0, 110))
        painter.drawText(QRectF(r).translated(0.6, 0.9), Qt.AlignCenter, "PY")
        painter.setPen(QColor("#ffffff"))
        painter.drawText(r, Qt.AlignCenter, "PY")
    else:
        # Looping: "PY" (upper) + refresh glyph + period (lower).
        top = QRectF(r.left(), r.top(), r.width(), r.height() * 0.52)
        bot = QRectF(r.left(), r.top() + r.height() * 0.50,
                     r.width(), r.height() * 0.50)
        f.setPointSizeF(max(6.0, min(8.5, r.width() * 0.38)))
        painter.setFont(f)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(top, Qt.AlignCenter, "PY")
        _draw_refresh(painter, bot.center().x() - r.width() * 0.22,
                      bot.center().y(), max(2.0, r.width() * 0.14),
                      QColor("#ffffff"))
        fp = QFont(f)
        fp.setPointSizeF(max(5.5, min(7.5, r.width() * 0.30)))
        painter.setFont(fp)
        painter.setPen(QColor(0, 0, 0, 160))
        painter.drawText(bot.translated(r.width()*0.10, 0),
                         Qt.AlignCenter, fmt_loop_period(loop_secs))
    painter.restore()


class PyBadge(QWidget):
    """Widget that paints the Python "PY" badge (used on the formula bar).

    Set ``loop_secs`` (then call update) to show the loop indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop_secs = None

    def set_loop(self, secs):
        if secs != self.loop_secs:
            self.loop_secs = secs
            self.update()

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter
        p = QPainter(self)
        paint_py_badge(p, self.rect(), self.loop_secs)
        p.end()


# ── Help ─────────────────────────────────────────────────────────────

PYTHON_HELP_HTML = """
<h2>Python in KherveSheet</h2>
<p>A cell can run real Python instead of an Excel formula. Type
<code>=PY</code> in a cell (or use <b>Insert &rarr; Python Cell</b>) and the
formula bar turns into a multi-line code editor. Press
<b>Ctrl+Enter</b> to run (plain Enter adds a new line).</p>

<p>The cell's value is the value of the <b>last line</b>, if that line is an
expression &mdash; just like Excel's Python. Assignments, <code>import</code>s
and <code>def</code>s produce no output on their own.</p>

<h3>Reading the grid with <code>ks()</code></h3>
<p>Use <code>ks("...")</code> to pull cell values into your code
(<code>xl()</code> and <code>cell()</code> are aliases):</p>
<table border="1" cellpadding="4" cellspacing="0">
<tr><th align="left"><code>ks("A1")</code></th><td>the value in A1</td></tr>
<tr><th align="left"><code>ks("A1:A10")</code></th>
    <td>a 1-D NumPy array</td></tr>
<tr><th align="left"><code>ks("A1:C5")</code></th>
    <td>a 2-D NumPy array</td></tr>
<tr><th align="left"><code>ks("Sheet2!B2")</code></th>
    <td>a value from another sheet</td></tr>
</table>

<h3>Writing back with <code>ks_set()</code></h3>
<p>Push values from Python into any cell or range
(<code>write()</code> is an alias):</p>
<table border="1" cellpadding="4" cellspacing="0">
<tr><th align="left"><code>ks_set("C1", 42)</code></th>
    <td>write a scalar into C1</td></tr>
<tr><th align="left"><code>ks_set("D1:D50", arr)</code></th>
    <td>write a 1-D array down a column</td></tr>
<tr><th align="left"><code>ks_set("A1:C3", matrix)</code></th>
    <td>write a 2-D array into a block</td></tr>
</table>
<p>The cell running the code is never overwritten.
A scalar fills the whole range; a list/array fills row-by-row.</p>

<h3>Embedding images with <code>ks_image()</code></h3>
<p>Return an image to embed it next to the cell, just like a plot:</p>
<pre>=PY
ks_image("https://example.com/photo.jpg")</pre>
<p>Accepts a URL, local file path, raw bytes, a PIL image, or a
NumPy H&times;W&times;3 uint8 array.</p>

<h3>What a cell can output</h3>
<ul>
<li><b>A number or text</b> &mdash; shown directly in the cell.</li>
<li><b>A list</b> &mdash; spills into the cell and the cells below/right.</li>
<li><b>A NumPy array / DataFrame / any object</b> &mdash; kept <i>live in the
cell</i> (shown as a badge like <code>&#9646; ndarray(100,)</code>) and reused
elsewhere with <code>ks("C1")</code>. To spill an array instead, end with
<code>list(my_array)</code> or <code>my_array.tolist()</code>.</li>
<li><b>A matplotlib figure</b> &mdash; embedded as a picture next to the
cell.</li>
<li><b>An image</b> (via <code>ks_image()</code> or returning a QPixmap/PIL
image) &mdash; embedded as a picture next to the cell.</li>
</ul>

<h3>Shared namespace &amp; UDFs</h3>
<p>All Python cells in a workbook share one namespace, so a function defined
in one cell is callable from any other:</p>
<pre>=PY
def celsius_to_f(c):
    return c * 9 / 5 + 32</pre>
<pre>=PY
celsius_to_f(ks("A1"))</pre>
<p><b>User-defined functions (UDFs):</b> Any function you <code>def</code>
in a <code>=PY</code> cell can also be called from an ordinary formula.
For example, after defining <code>celsius_to_f</code> above, you can write
<code>=CELSIUS_TO_F(A1)</code> in any cell &mdash; case-insensitive,
and built-in functions are never overridden.</p>

<h3>Python loop (auto-refresh)</h3>
<p>Right-click a <code>=PY</code> cell &rarr; <b>Python loop</b> to re-run
it on an interval (0.1&nbsp;s, 1&nbsp;s, 5&nbsp;s, 30&nbsp;s, &hellip; up to
24&nbsp;hours, or a custom value). The PY badge shows a refresh icon and the
period. This is handy for live data, clocks, animations, or polling.</p>

<h3>Examples &mdash; calculations</h3>
<pre>=PY
import numpy as np
np.mean(ks("A1:A10"))            # average of a column</pre>
<pre>=PY
[x ** 2 for x in range(1, 6)]    # spills 1, 4, 9, 16, 25</pre>
<pre>=PY
import numpy as np
np.linspace(0, 1, 100)           # stored as an object in the cell</pre>

<h3>Examples &mdash; write back</h3>
<pre>=PY
import numpy as np
ks_set("D1:D50", np.cumsum(ks("A1:A50")))
"written"</pre>

<h3>Examples &mdash; matplotlib plots</h3>
<p>Build a figure and return it (or just create one &mdash; KherveSheet
captures the current figure automatically).</p>

<p><b>Simple line plot of a column</b></p>
<pre>=PY
import matplotlib.pyplot as plt
plt.plot(ks("A1:A20"))
plt.title("My data")
plt.gcf()</pre>

<p><b>X vs Y with labels and a grid</b></p>
<pre>=PY
import matplotlib.pyplot as plt
x = ks("A2:A50")
y = ks("B2:B50")
fig, ax = plt.subplots()
ax.plot(x, y, "o-", color="#4472C4")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Signal (V)")
ax.grid(True)
fig</pre>

<p><b>Histogram</b></p>
<pre>=PY
import matplotlib.pyplot as plt
plt.hist(ks("A1:A200"), bins=30, color="#E07B39")
plt.gcf()</pre>

<p><b>Curve from a formula</b></p>
<pre>=PY
import numpy as np, matplotlib.pyplot as plt
x = np.linspace(0, 2 * np.pi, 200)
plt.plot(x, np.sin(x), label="sin")
plt.plot(x, np.cos(x), label="cos")
plt.legend()
plt.gcf()</pre>

<p><b>Bar chart from two columns</b></p>
<pre>=PY
import matplotlib.pyplot as plt
labels = [str(v) for v in ks("A1:A6")]
plt.bar(labels, ks("B1:B6"))
plt.gcf()</pre>

<h3>Good to know</h3>
<ul>
<li>Editing a cell that <code>ks()</code> reads re-runs dependent Python
cells automatically.</li>
<li><code>print()</code> output is captured and shown in the cell tooltip
(hover the cell to see it).</li>
<li>Errors show <code>#PYERR</code> &mdash; hover the cell for the message.</li>
<li>Each cell has a <b>30-second timeout</b>. An infinite loop is
automatically stopped; you will see a <code>TimeoutError</code>.</li>
<li>Code is saved in the <code>.ksheet</code> file. Reopening a file with
Python cells asks for permission before running it.</li>
<li>Ready to use: <code>math</code>, <code>numpy as np</code>,
<code>matplotlib.pyplot as plt</code>, and <code>pandas as pd</code> /
<code>scipy</code> if installed. You can <code>import</code> anything else
you have.</li>
<li>Click the pop-out button next to the PY badge for a larger editor with
line numbers, autocomplete (Ctrl+Space), comment toggle (Ctrl+/), and a
<b>Pick cell</b> button to click-insert <code>ks("&hellip;")</code>
references.</li>
<li>The AI assistant can also write Python cells for you &mdash; just ask it
to "write a Python cell that&hellip;".</li>
</ul>
"""


def show_python_help(parent=None):
    """Open a dialog explaining how to use Python cells."""
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox,
    )
    dlg = QDialog(parent)
    dlg.setWindowTitle("Python in KherveSheet")
    dlg.resize(640, 640)
    layout = QVBoxLayout(dlg)
    browser = QTextBrowser()
    browser.setOpenExternalLinks(True)
    browser.setHtml(PYTHON_HELP_HTML)
    layout.addWidget(browser)
    bb = QDialogButtonBox(QDialogButtonBox.Close)
    bb.rejected.connect(dlg.reject)
    bb.accepted.connect(dlg.accept)
    layout.addWidget(bb)
    dlg.exec_()


class _LineNumberArea(QWidget):
    """Gutter widget that paints line numbers for _DialogCodeEditor."""

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        from PyQt5.QtCore import QSize
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.paint_line_numbers(event)


# Words always offered by autocomplete, beyond the live namespace.
_COMPLETE_KEYWORDS = (
    "import from as def class return if elif else for while in is and or "
    "not with try except finally raise lambda yield None True False print "
    "range len sum min max abs round int float str list dict tuple set "
    "enumerate zip sorted reversed").split()
_COMPLETE_HINTS = [
    "ks", "ks_set", "ks_image", "write", "np", "plt", "pd",
    "np.array", "np.linspace", "np.arange", "np.zeros", "np.ones",
    "np.mean", "np.sum", "np.std", "np.polyfit", "np.gradient",
    "plt.plot", "plt.scatter", "plt.bar", "plt.hist", "plt.gcf",
    "plt.xlabel", "plt.ylabel", "plt.title", "plt.legend",
]


class _DialogCodeEditor(QPlainTextEdit):
    """Code editor for the pop-out dialog.

    Line numbers + current-line highlight, Tab/Shift+Tab indent/dedent,
    Ctrl+/ comment toggle, Ctrl+Space (or typing) autocomplete, and
    Ctrl+Enter / Ctrl+Return emits *runRequested*.
    """

    runRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(11)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(
            4 * self.fontMetrics().horizontalAdvance(" "))
        self._highlighter = PythonHighlighter(self.document())
        self._error_line = None

        # Line-number gutter.
        self._lna = _LineNumberArea(self)
        self.blockCountChanged.connect(
            lambda _=0: self._update_lna_width())
        self.updateRequest.connect(self._update_lna)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_lna_width()
        self._highlight_current_line()

        # Autocomplete.
        from PyQt5.QtWidgets import QCompleter
        from PyQt5.QtCore import QStringListModel
        self._completer = QCompleter(self)
        self._completer.setModel(QStringListModel([], self._completer))
        self._completer.setWidget(self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.activated.connect(self._insert_completion)

    # ── line-number gutter ───────────────────────────────────────────
    def line_number_area_width(self):
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_lna_width(self):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_lna(self, rect, dy):
        if dy:
            self._lna.scroll(0, dy)
        else:
            self._lna.update(0, rect.y(), self._lna.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_lna_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._lna.setGeometry(
            cr.left(), cr.top(), self.line_number_area_width(), cr.height())

    def paint_line_numbers(self, event):
        from PyQt5.QtGui import QPainter, QColor
        painter = QPainter(self._lna)
        painter.fillRect(event.rect(), QColor("#f0f0f0"))
        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(
            self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        painter.setPen(QColor("#808080"))
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0, int(top), self._lna.width() - 4,
                    self.fontMetrics().height(),
                    Qt.AlignRight, str(num + 1))
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            num += 1

    # ── current-line + error-line highlight ──────────────────────────
    def _highlight_current_line(self):
        from PyQt5.QtWidgets import QTextEdit
        from PyQt5.QtGui import QColor, QTextFormat
        sels = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor("#eef5ff"))
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            sels.append(sel)
        if self._error_line is not None:
            from PyQt5.QtGui import QTextCursor
            blk = self.document().findBlockByNumber(self._error_line - 1)
            if blk.isValid():
                esel = QTextEdit.ExtraSelection()
                esel.format.setBackground(QColor("#ffe0e0"))
                esel.format.setProperty(QTextFormat.FullWidthSelection, True)
                esel.cursor = QTextCursor(blk)
                sels.append(esel)
        self.setExtraSelections(sels)

    def mark_error_line(self, line):
        """Highlight *line* (1-based) in red and scroll to it."""
        from PyQt5.QtGui import QTextCursor
        self._error_line = line
        blk = self.document().findBlockByNumber(line - 1)
        if blk.isValid():
            self.setTextCursor(QTextCursor(blk))
        self._highlight_current_line()

    def clear_error_line(self):
        self._error_line = None
        self._highlight_current_line()

    def keyPressEvent(self, event):
        comp = getattr(self, "_completer", None)
        if comp is not None and comp.popup().isVisible():
            if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab,
                               Qt.Key_Escape, Qt.Key_Up, Qt.Key_Down):
                event.ignore()
                return
        mod = event.modifiers()
        if (event.key() in (Qt.Key_Return, Qt.Key_Enter)
                and (mod & Qt.ControlModifier)):
            self.runRequested.emit()
            return
        if event.key() == Qt.Key_Space and (mod & Qt.ControlModifier):
            self._show_completions()
            return
        if event.key() == Qt.Key_Slash and (mod & Qt.ControlModifier):
            self.toggle_comment()
            return
        if event.key() == Qt.Key_Tab:
            if self._has_multiline_selection():
                self.indent_selection()
            else:
                self.insertPlainText("    ")
            return
        if event.key() == Qt.Key_Backtab:   # Shift+Tab
            self.dedent_selection()
            return
        super().keyPressEvent(event)
        # Auto-suggest while typing an identifier.
        if event.text() and (event.text().isalnum() or event.text() == "."):
            if len(self._completion_prefix()) >= 2:
                self._show_completions(auto=True)
            elif comp is not None:
                comp.popup().hide()

    # ── autocomplete ─────────────────────────────────────────────────
    def _completion_prefix(self):
        from PyQt5.QtGui import QTextCursor
        c = self.textCursor()
        c.select(QTextCursor.WordUnderCursor)
        return c.selectedText()

    def _candidate_words(self):
        words = set(_COMPLETE_KEYWORDS) | set(_COMPLETE_HINTS)
        # Names from the running workbook namespace, if available.
        win = self.window()
        rt = getattr(win, "_py_runtime_ref", None)
        g = getattr(rt, "_globals", None) if rt else None
        if g:
            words |= {k for k in g if not k.startswith("_")}
        # Identifiers already used in this buffer.
        words |= set(re.findall(r"[A-Za-z_]\w{2,}", self.toPlainText()))
        return sorted(words)

    def _show_completions(self, auto=False):
        from PyQt5.QtCore import QStringListModel
        prefix = self._completion_prefix()
        if auto and len(prefix) < 2:
            return
        self._completer.setModel(
            QStringListModel(self._candidate_words(), self._completer))
        self._completer.setCompletionPrefix(prefix)
        popup = self._completer.popup()
        if self._completer.completionCount() == 0:
            popup.hide()
            return
        popup.setCurrentIndex(self._completer.completionModel().index(0, 0))
        rect = self.cursorRect()
        rect.setWidth(self._completer.popup().sizeHintForColumn(0)
                      + self._completer.popup().verticalScrollBar()
                      .sizeHint().width())
        self._completer.complete(rect)

    def _insert_completion(self, text):
        from PyQt5.QtGui import QTextCursor
        c = self.textCursor()
        c.select(QTextCursor.WordUnderCursor)
        c.insertText(text)
        self.setTextCursor(c)

    # ── selection helpers ────────────────────────────────────────────
    def _has_multiline_selection(self):
        c = self.textCursor()
        return c.hasSelection() and "\n" in c.selectedText()

    def _selected_line_range(self):
        from PyQt5.QtGui import QTextCursor
        c = self.textCursor()
        start, end = c.selectionStart(), c.selectionEnd()
        c.setPosition(start)
        c.movePosition(QTextCursor.StartOfBlock)
        s = c.blockNumber()
        c.setPosition(end)
        e = c.blockNumber()
        return s, e

    def _apply_per_line(self, fn):
        from PyQt5.QtGui import QTextCursor
        doc = self.document()
        cur = self.textCursor()
        cur.beginEditBlock()
        if cur.hasSelection():
            s, e = self._selected_line_range()
        else:
            s = e = cur.blockNumber()
        for bn in range(s, e + 1):
            blk = doc.findBlockByNumber(bn)
            edit = QTextCursor(blk)
            edit.select(QTextCursor.LineUnderCursor)
            edit.insertText(fn(blk.text()))
        cur.endEditBlock()

    def indent_selection(self):
        self._apply_per_line(lambda ln: "    " + ln)

    def dedent_selection(self):
        def _ded(ln):
            for pre in ("    ", "\t", " ", "  ", "   "):
                if ln.startswith(pre):
                    return ln[len(pre):]
            return ln
        self._apply_per_line(_ded)

    def toggle_comment(self):
        from PyQt5.QtGui import QTextCursor
        doc = self.document()
        cur = self.textCursor()
        if cur.hasSelection():
            s, e = self._selected_line_range()
        else:
            s = e = cur.blockNumber()
        lines = [doc.findBlockByNumber(bn).text()
                 for bn in range(s, e + 1)]
        non_empty = [ln for ln in lines if ln.strip()]
        all_commented = non_empty and all(
            ln.lstrip().startswith("#") for ln in non_empty)
        if all_commented:
            self._apply_per_line(
                lambda ln: ln.replace("# ", "", 1) if "# " in ln
                else ln.replace("#", "", 1) if "#" in ln else ln)
        else:
            self._apply_per_line(
                lambda ln: ("# " + ln) if ln.strip() else ln)


# Ready-to-paste snippets offered by the dialog's Snippets menu.
PY_SNIPPETS = {
    "Imports (numpy, matplotlib)":
        "import numpy as np\nimport matplotlib.pyplot as plt\n",
    "Plot a column":
        "import matplotlib.pyplot as plt\n"
        "y = ks(\"A1:A50\")\n"
        "plt.plot(y)\n"
        "plt.gcf()",
    "X–Y plot":
        "import matplotlib.pyplot as plt\n"
        "x = ks(\"A2:A50\")\n"
        "y = ks(\"B2:B50\")\n"
        "plt.plot(x, y, \"o-\")\n"
        "plt.xlabel(\"x\"); plt.ylabel(\"y\"); plt.grid(True)\n"
        "plt.gcf()",
    "Histogram":
        "import matplotlib.pyplot as plt\n"
        "plt.hist(ks(\"A1:A200\"), bins=30)\n"
        "plt.gcf()",
    "Linear fit (slope, intercept)":
        "import numpy as np\n"
        "x = ks(\"A2:A50\"); y = ks(\"B2:B50\")\n"
        "m, b = np.polyfit(x, y, 1)\n"
        "[float(m), float(b)]",
    "Gaussian fit":
        "import numpy as np\n"
        "from scipy.optimize import curve_fit\n"
        "def g(x, A, mu, s): return A*np.exp(-(x-mu)**2/(2*s*s))\n"
        "x = ks(\"A2:A100\"); y = ks(\"B2:B100\")\n"
        "popt, _ = curve_fit(g, x, y, p0=[y.max(), x.mean(), 1])\n"
        "popt.tolist()",
    "FFT magnitude spectrum":
        "import numpy as np, matplotlib.pyplot as plt\n"
        "y = ks(\"B2:B514\")\n"
        "mag = np.abs(np.fft.rfft(y))\n"
        "plt.plot(mag); plt.xlabel(\"bin\"); plt.ylabel(\"|FFT|\")\n"
        "plt.gcf()",
    "Define a helper function":
        "def my_func(x):\n    return x * 2\n",
    "Write back to the grid (ks_set)":
        "import numpy as np\n"
        "ks_set(\"D1:D50\", np.cumsum(ks(\"A1:A50\")))\n"
        "\"written\"",
    "Embed an image (ks_image)":
        "ks_image(\"https://example.com/photo.jpg\")",
    "Live clock (use with Python loop)":
        "import datetime\n"
        "datetime.datetime.now().strftime(\"%H:%M:%S\")",
}


class PythonCellDialog(QDialog):
    """Non-modal pop-out editor for a single =PY cell.

    Running (toolbar Run or Ctrl+Enter) applies the code to the cell and
    shows the result / printed output / errors in the output pane — the
    window stays open so you can iterate.  *run_cb(code)* must apply the
    code and return a dict with keys: result, error, stdout, has_plot.
    """

    def __init__(self, parent, code, cell_ref, run_cb, help_cb=None,
                 pick_cb=None):
        super().__init__(parent)
        from PyQt5.QtWidgets import (
            QVBoxLayout, QLabel, QPushButton, QToolBar, QToolButton,
            QMenu, QSplitter, QWidget, QHBoxLayout,
        )
        from PyQt5.QtWidgets import QAction
        self._run_cb = run_cb
        self._help_cb = help_cb
        self._pick_cb = pick_cb
        self.setWindowTitle(f"Python — {cell_ref}" if cell_ref
                            else "Python cell")
        self.resize(760, 560)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Toolbar ──────────────────────────────────────────────────
        tb = QToolBar()
        tb.setStyleSheet("QToolBar{border:0;padding:3px;spacing:3px;}")
        run_act = QAction("▶ Run", self)
        run_act.setShortcut("Ctrl+Return")
        run_act.setToolTip("Run and apply to the cell (Ctrl+Enter)")
        run_act.triggered.connect(self._run)
        tb.addAction(run_act)
        tb.addSeparator()
        ks_act = QAction("Insert ks()", self)
        ks_act.setToolTip("Insert a cell reference: ks(\"A1\")")
        ks_act.triggered.connect(self._insert_ks)
        tb.addAction(ks_act)
        if pick_cb is not None:
            self._pick_act = QAction("Pick cell", self)
            self._pick_act.setCheckable(True)
            self._pick_act.setToolTip(
                "Click a grid cell to insert its ks(\"…\") reference")
            self._pick_act.toggled.connect(self._on_pick_toggled)
            tb.addAction(self._pick_act)
        # Snippets menu.
        snip_btn = QToolButton()
        snip_btn.setText("Snippets ▾")
        snip_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(snip_btn)
        for name, body in PY_SNIPPETS.items():
            act = menu.addAction(name)
            act.triggered.connect(
                lambda _=False, b=body: self._insert_snippet(b))
        snip_btn.setMenu(menu)
        tb.addWidget(snip_btn)
        cmt_act = QAction("Comment", self)
        cmt_act.setShortcut("Ctrl+/")
        cmt_act.setToolTip("Toggle line comments (Ctrl+/)")
        cmt_act.triggered.connect(lambda: self.editor.toggle_comment())
        tb.addAction(cmt_act)
        tb.addSeparator()
        if help_cb is not None:
            help_act = QAction("Help", self)
            help_act.setToolTip("Open the Python examples")
            help_act.triggered.connect(lambda: self._help_cb())
            tb.addAction(help_act)
        outer.addWidget(tb)

        # ── Hint + editor + output (split) ───────────────────────────
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(8, 4, 8, 8)
        hint = QLabel(
            "Read cells with ks(\"A1\") or ks(\"A1:B10\"). The last line's "
            "value is the cell result. Ctrl+Enter runs.")
        hint.setStyleSheet("color:#57606a;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        split = QSplitter(Qt.Vertical)
        self.editor = _DialogCodeEditor()
        self.editor.setPlainText(code or "")
        self.editor.runRequested.connect(self._run)
        split.addWidget(self.editor)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(150)
        self.output.setPlaceholderText("Output appears here after you Run.")
        of = QFont("Consolas")
        of.setStyleHint(QFont.Monospace)
        self.output.setFont(of)
        split.addWidget(self.output)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 1)
        layout.addWidget(split, stretch=1)

        # ── Bottom buttons ───────────────────────────────────────────
        row = QHBoxLayout()
        row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        row.addWidget(close_btn)
        layout.addLayout(row)
        outer.addWidget(body, stretch=1)

        self.editor.setFocus()

    # ── actions ──────────────────────────────────────────────────────
    def _run(self):
        self.editor.clear_error_line()
        out = self._run_cb(self.editor.toPlainText()) or {}
        parts = []
        err = out.get("error")
        if out.get("stdout"):
            parts.append(out["stdout"].rstrip())
        if err:
            parts.append(err.rstrip())
            self.output.setStyleSheet("color:#b00020;")
            ln = self._error_line_from(err)
            if ln:
                self.editor.mark_error_line(ln)
        else:
            self.output.setStyleSheet("")
            if out.get("has_plot"):
                parts.append("→ plot embedded in the grid")
            res = out.get("result", "")
            if res not in ("", None):
                parts.append("Result: " + str(res))
        self.output.setPlainText(
            "\n".join(p for p in parts if p) or "(ran — no output)")

    @staticmethod
    def _error_line_from(tb):
        """Pull the cell line number out of a traceback, if present."""
        ln = None
        for m in re.finditer(r'"<py-cell>", line (\d+)', tb or ""):
            ln = int(m.group(1))
        return ln

    def _on_pick_toggled(self, on):
        if self._pick_cb is not None:
            self._pick_cb(on)

    def insert_ref(self, ref):
        """Insert ks("<ref>") at the cursor (used by click-to-pick)."""
        self.editor.textCursor().insertText(f'ks("{ref}")')
        self.editor.setFocus()

    def end_pick(self):
        """Turn off cell-pick mode (called after a cell is picked)."""
        act = getattr(self, "_pick_act", None)
        if act is not None and act.isChecked():
            act.blockSignals(True)
            act.setChecked(False)
            act.blockSignals(False)

    def _insert_ks(self):
        from PyQt5.QtGui import QTextCursor
        cur = self.editor.textCursor()
        cur.insertText('ks("")')
        cur.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 2)
        self.editor.setTextCursor(cur)
        self.editor.setFocus()

    def _insert_snippet(self, body):
        self.editor.textCursor().insertText(body)
        self.editor.setFocus()
