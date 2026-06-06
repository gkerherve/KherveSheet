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
from PyQt5.QtWidgets import QPlainTextEdit, QDialog

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
        # ks() is the KherveSheet accessor; xl()/cell() are aliases.
        g["ks"] = self._xl
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
            raise RuntimeError("ks() is only available inside a =PY cell")
        return resolve_ref(sheet, str(ref))

    # ── execution ────────────────────────────────────────────────────
    def run(self, code, sheet, row, col) -> PyResult:
        """Execute *code* in the shared namespace and classify its value."""
        import contextlib
        import io
        import traceback
        g = self._ensure_globals()
        self._sheet = sheet
        plt = g.get("plt")
        before = set(plt.get_fignums()) if plt is not None else set()
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                value = self._exec_with_value(code, g)
        except Exception:
            return PyResult(error=traceback.format_exc(),
                            stdout=buf.getvalue())
        finally:
            self._sheet = None
        out = buf.getvalue()

        kind, norm = _classify(value)

        # If the cell did not itself yield a figure but created one, grab it.
        if kind != PyResult.FIGURE and plt is not None:
            new = [n for n in plt.get_fignums() if n not in before]
            if new:
                fig = plt.figure(new[-1])
                return PyResult(value=fig, kind=PyResult.FIGURE,
                                figure=fig, stdout=out)

        if kind == PyResult.FIGURE:
            return PyResult(value=norm, kind=kind, figure=norm, stdout=out)
        return PyResult(value=norm, kind=kind, stdout=out)

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
</ul>

<h3>Shared namespace</h3>
<p>All Python cells in a workbook share one namespace, so a function defined
in one cell is callable from any other:</p>
<pre>=PY
def celsius_to_f(c):
    return c * 9 / 5 + 32</pre>
<pre>=PY
celsius_to_f(ks("A1"))</pre>

<h3>Examples &mdash; calculations</h3>
<pre>=PY
import numpy as np
np.mean(ks("A1:A10"))            # average of a column</pre>
<pre>=PY
[x ** 2 for x in range(1, 6)]    # spills 1, 4, 9, 16, 25</pre>
<pre>=PY
import numpy as np
np.linspace(0, 1, 100)           # stored as an object in the cell</pre>

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
<li>Errors show <code>#PYERR</code> &mdash; hover the cell for the message.</li>
<li>Code is saved in the <code>.ksheet</code> file. Reopening a file with
Python cells asks for permission before running it.</li>
<li>Ready to use: <code>math</code>, <code>numpy as np</code>,
<code>matplotlib.pyplot as plt</code>, and <code>pandas as pd</code> /
<code>scipy</code> if installed. You can <code>import</code> anything else
you have.</li>
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


class _DialogCodeEditor(QPlainTextEdit):
    """Code editor for the pop-out dialog.

    Tab indents (selection-aware), Shift+Tab dedents, Ctrl+/ toggles line
    comments, and Ctrl+Enter / Ctrl+Return emits *runRequested*.
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

    def keyPressEvent(self, event):
        mod = event.modifiers()
        if (event.key() in (Qt.Key_Return, Qt.Key_Enter)
                and (mod & Qt.ControlModifier)):
            self.runRequested.emit()
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
}


class PythonCellDialog(QDialog):
    """Non-modal pop-out editor for a single =PY cell.

    Running (toolbar Run or Ctrl+Enter) applies the code to the cell and
    shows the result / printed output / errors in the output pane — the
    window stays open so you can iterate.  *run_cb(code)* must apply the
    code and return a dict with keys: result, error, stdout, has_plot.
    """

    def __init__(self, parent, code, cell_ref, run_cb, help_cb=None):
        super().__init__(parent)
        from PyQt5.QtWidgets import (
            QVBoxLayout, QLabel, QPushButton, QToolBar, QToolButton,
            QMenu, QSplitter, QWidget, QHBoxLayout,
        )
        from PyQt5.QtWidgets import QAction
        self._run_cb = run_cb
        self._help_cb = help_cb
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
        out = self._run_cb(self.editor.toPlainText()) or {}
        parts = []
        err = out.get("error")
        if out.get("stdout"):
            parts.append(out["stdout"].rstrip())
        if err:
            parts.append(err.rstrip())
            self.output.setStyleSheet("color:#b00020;")
        else:
            self.output.setStyleSheet("")
            if out.get("has_plot"):
                parts.append("→ plot embedded in the grid")
            res = out.get("result", "")
            if res not in ("", None):
                parts.append("Result: " + str(res))
        self.output.setPlainText(
            "\n".join(p for p in parts if p) or "(ran — no output)")

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
