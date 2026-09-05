# KherveSheet — clickable cell buttons
# Copyright (C) 2024-2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later

"""Buttons that live in a cell and do something when clicked.

A checkbox says what a setting *is*; a button says *do this now*.  It
writes a value into a target cell, re-runs a ``=PY`` cell, or both — so
a sheet can carry its own control panel: "Refit", "Reset", "Fetch
data".

The button is a cell, not a floating widget: it saves, copies, sorts
and undoes like everything else in the grid, and a formula can read the
cell it writes to.  ``CellFormatDelegate`` paints the chrome behind the
label, which is the cell's own text.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QTableWidgetItem, QVBoxLayout,
)

#: What a click does to the button's target cell.
MODES = ("toggle", "set", "pulse")

#: Default face colour.
DEFAULT_COLOR = "#4472c4"

#: Values a toggle flips between; also what a formula reads as 1/0.
TRUE_TEXT = "TRUE"
FALSE_TEXT = "FALSE"


def default_spec(label: str = "Button") -> dict:
    return {"label": label, "mode": "toggle", "target": "",
            "value": TRUE_TEXT, "reset": FALSE_TEXT, "run": "",
            "color": DEFAULT_COLOR}


def normalise(spec: dict) -> dict:
    """Fill in a partial spec and reject a nonsensical one."""
    out = default_spec()
    out.update({k: v for k, v in (spec or {}).items() if v is not None})
    if out["mode"] not in MODES:
        raise ValueError(
            f"mode must be one of {list(MODES)}, not {out['mode']!r}")
    if out["mode"] in ("toggle", "set", "pulse") and not out["target"] \
            and not out["run"]:
        raise ValueError(
            "a button needs a target cell to write, a =PY cell to run, "
            "or both — otherwise clicking it would do nothing")
    out["label"] = str(out["label"])
    return out


# ── Creation ───────────────────────────────────────────────────────

def insert_button(sheet, row, col, spec: dict):
    """Turn (row, col) into a button.  Returns the stored spec."""
    spec = normalise(spec)
    if not hasattr(sheet, "_cell_buttons"):
        sheet._cell_buttons = {}
    it = sheet.table.item(row, col)
    old = it.text() if it else ""
    if it is None:
        it = QTableWidgetItem(spec["label"])
        sheet.table.setItem(row, col, it)
    else:
        it.setText(spec["label"])
    # Typing into a button would replace its label with data.
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    it.setTextAlignment(Qt.AlignCenter)
    sheet._cell_buttons[(row, col)] = spec
    sheet._shadow[(row, col)] = spec["label"]
    stack = getattr(sheet, "_undo_stack", None)
    if stack is not None:
        from .undo_commands import InsertButtonCmd
        stack.push(InsertButtonCmd(sheet, row, col, old, spec))
    sheet.table.viewport().update()
    return spec


def remove_button(sheet, row, col):
    """Turn a button cell back into an ordinary one."""
    buttons = getattr(sheet, "_cell_buttons", {})
    spec = buttons.pop((row, col), None)
    it = sheet.table.item(row, col)
    if it is not None:
        it.setFlags(it.flags() | Qt.ItemIsEditable)
    sheet.table.viewport().update()
    return spec


# ── Clicking ───────────────────────────────────────────────────────

def _write(sheet, ref: str, text: str):
    """Write *text* into *ref*, letting the normal edit path run."""
    from .python_engine import parse_ref_coords
    (r1, c1, _r2, _c2) = parse_ref_coords(ref)
    it = sheet.table.item(r1, c1)
    if it is None:
        it = QTableWidgetItem("")
        sheet.table.setItem(r1, c1, it)
    # setText fires cellChanged, which recalculates dependants and
    # pushes the edit onto the undo stack.
    it.setText(text)
    return (r1, c1)


def _read(sheet, ref: str) -> str:
    from .python_engine import parse_ref_coords
    (r1, c1, _r2, _c2) = parse_ref_coords(ref)
    it = sheet.table.item(r1, c1)
    return it.text() if it else ""


def click_button(sheet, row, col) -> dict:
    """Run the button at (row, col).  Returns what it did."""
    spec = getattr(sheet, "_cell_buttons", {}).get((row, col))
    if not spec:
        return {}
    done = {"label": spec["label"], "mode": spec["mode"]}
    target = spec.get("target") or ""
    mode = spec["mode"]

    if target:
        if mode == "toggle":
            now = _read(sheet, target).strip().upper()
            new = FALSE_TEXT if now == TRUE_TEXT else TRUE_TEXT
            _write(sheet, target, new)
            done["wrote"] = {target: new}
        elif mode in ("set", "pulse"):
            _write(sheet, target, str(spec.get("value", TRUE_TEXT)))
            done["wrote"] = {target: spec.get("value", TRUE_TEXT)}

    run_ref = (spec.get("run") or "").strip()
    if run_ref:
        done["ran"] = _run_target(sheet, run_ref)

    # A pulse is momentary: the target goes back down once the work
    # driven by it has run, so the next click is a fresh trigger.
    if target and mode == "pulse":
        _write(sheet, target, str(spec.get("reset", FALSE_TEXT)))
        done.setdefault("wrote", {})[target] = spec.get("reset", FALSE_TEXT)
    return done


def _run_target(sheet, ref: str):
    """Re-run one =PY cell, or every one on the sheet for 'all'."""
    from .python_engine import is_python_source
    from .python_engine import parse_ref_coords

    if ref.strip().lower() == "all":
        cells = [(r, c) for (r, c), src
                 in sheet._cell_formulas.items()
                 if is_python_source(src)]
    else:
        (r1, c1, _r2, _c2) = parse_ref_coords(ref)
        cells = [(r1, c1)]
    ran = []
    for (r, c) in cells:
        if not is_python_source(sheet._cell_formulas.get((r, c))):
            continue
        try:
            sheet._reeval_formula_cell(r, c)
            sheet._recalc_dependents(r, c)
            ran.append(f"{r + 1},{c + 1}")
        except Exception:
            pass
    return ran


# ── Painting ───────────────────────────────────────────────────────

def paint_button(painter: QPainter, rect, spec: dict, pressed=False):
    """Draw the button chrome.  The label is the cell's own text, drawn
    by the base delegate afterwards, so only the face is painted here."""
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    r = QRectF(rect).adjusted(2.5, 2.5, -2.5, -2.5)
    base = QColor(spec.get("color") or DEFAULT_COLOR)
    if not base.isValid():
        base = QColor(DEFAULT_COLOR)
    top, bottom = base.lighter(118), base.darker(108)
    if pressed:
        top, bottom = bottom, top
    grad = QLinearGradient(r.topLeft(), r.bottomLeft())
    grad.setColorAt(0.0, top)
    grad.setColorAt(1.0, bottom)
    painter.setBrush(grad)
    painter.setPen(QPen(base.darker(135), 1.0))
    painter.drawRoundedRect(r, 4, 4)
    painter.restore()


def label_color(spec: dict) -> QColor:
    """Readable text colour for this button's face."""
    base = QColor(spec.get("color") or DEFAULT_COLOR)
    if not base.isValid():
        base = QColor(DEFAULT_COLOR)
    luma = (0.2126 * base.redF() + 0.7152 * base.greenF()
            + 0.0722 * base.blueF())
    return QColor("#202020") if luma > 0.6 else QColor("#ffffff")


# ── Configuration dialog ───────────────────────────────────────────

class ButtonDialog(QDialog):
    """Insert ▸ Button: choose what the button does."""

    _MODE_LABELS = [
        ("toggle", "Toggle the target between TRUE and FALSE"),
        ("set", "Write a fixed value into the target"),
        ("pulse", "Write the value, run, then reset the target"),
    ]

    def __init__(self, parent=None, spec: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Button")
        self.resize(420, 240)
        spec = spec or default_spec()
        lay = QVBoxLayout(self)
        form = QFormLayout()
        lay.addLayout(form)

        self._label = QLineEdit(spec.get("label", "Button"))
        form.addRow("Label:", self._label)

        self._mode = QComboBox()
        for _key, text in self._MODE_LABELS:
            self._mode.addItem(text)
        keys = [k for k, _ in self._MODE_LABELS]
        self._mode.setCurrentIndex(
            keys.index(spec.get("mode", "toggle")))
        self._mode.currentIndexChanged.connect(self._sync)
        form.addRow("On click:", self._mode)

        self._target = QLineEdit(spec.get("target", ""))
        self._target.setPlaceholderText("e.g. B2 — leave blank to only run")
        form.addRow("Target cell:", self._target)

        self._value = QLineEdit(spec.get("value", TRUE_TEXT))
        form.addRow("Value:", self._value)

        self._reset = QLineEdit(spec.get("reset", FALSE_TEXT))
        form.addRow("Reset to:", self._reset)

        self._run = QLineEdit(spec.get("run", ""))
        self._run.setPlaceholderText(
            "=PY cell to re-run, e.g. E5, or 'all'")
        form.addRow("Then run:", self._run)

        self._color = QLineEdit(spec.get("color", DEFAULT_COLOR))
        form.addRow("Colour:", self._color)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._sync()

    def _sync(self):
        mode = self.spec()["mode"]
        self._value.setEnabled(mode in ("set", "pulse"))
        self._reset.setEnabled(mode == "pulse")

    def spec(self) -> dict:
        keys = [k for k, _ in self._MODE_LABELS]
        return {
            "label": self._label.text().strip() or "Button",
            "mode": keys[self._mode.currentIndex()],
            "target": self._target.text().strip(),
            "value": self._value.text(),
            "reset": self._reset.text(),
            "run": self._run.text().strip(),
            "color": self._color.text().strip() or DEFAULT_COLOR,
        }
