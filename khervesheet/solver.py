"""Solver — Excel-style optimisation dialog.

Minimise / maximise / target a cell value by changing variable cells,
subject to linear and nonlinear constraints.  Uses scipy.optimize
under the hood.

The dialog is non-modal so the user can click cells in the sheet and
have their references inserted into the active input field.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re
from typing import List, Optional, Tuple

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QRadioButton, QCheckBox, QComboBox,
    QListWidget, QListWidgetItem, QPushButton, QGroupBox, QMessageBox,
    QButtonGroup, QWidget, QSizePolicy, QToolButton, QApplication,
)

from .sheet import SheetWidget, col_index_to_letter, letter_to_col_index

# ── Cell reference helpers ──────────────────────────────────────────

_CELL_RE = re.compile(
    r'\$?([A-Za-z]{1,3})\$?(\d{1,7})', re.ASCII)


def _parse_ref(ref: str) -> Optional[Tuple[int, int]]:
    """Parse a cell reference like '$D$5' or 'A1' → (row, col) 0-based."""
    ref = ref.strip()
    m = _CELL_RE.fullmatch(ref)
    if not m:
        return None
    col = letter_to_col_index(m.group(1))
    row = int(m.group(2)) - 1
    return (row, col)


def _parse_range(text: str) -> List[Tuple[int, int]]:
    """Parse one or more comma-separated cell references / ranges into a
    flat list of (row, col). Handles 'A1', 'A1:A5', and
    'A1:A5,C1:D3' (multiple non-contiguous blocks)."""
    cells: List[Tuple[int, int]] = []
    for part in text.split(','):
        part = part.strip()
        if not part:
            continue
        if ':' in part:
            ends = part.split(':')
            if len(ends) != 2:
                continue
            start = _parse_ref(ends[0])
            end = _parse_ref(ends[1])
            if start is None or end is None:
                continue
            r1, c1 = start
            r2, c2 = end
            for r in range(min(r1, r2), max(r1, r2) + 1):
                for c in range(min(c1, c2), max(c1, c2) + 1):
                    cells.append((r, c))
        else:
            rc = _parse_ref(part)
            if rc:
                cells.append(rc)
    return cells


def _ref_str(row: int, col: int) -> str:
    """(row, col) 0-based → '$A$1' string."""
    return f"${col_index_to_letter(col)}${row + 1}"


def _range_ref_str(rng) -> str:
    """One QTableWidgetSelectionRange → '$A$1' or '$A$1:$B$3'."""
    tl = _ref_str(rng.topRow(), rng.leftColumn())
    if rng.rowCount() == 1 and rng.columnCount() == 1:
        return tl
    br = _ref_str(rng.bottomRow(), rng.rightColumn())
    return f"{tl}:{br}"


def _selection_ref_str(sheet: SheetWidget) -> str:
    """Build a ref string from the sheet's current selection. Multiple
    non-contiguous ranges (Ctrl-selected) are joined with commas, so the
    variable-cell field can collect several blocks Excel-style."""
    sel = sheet.table.selectedRanges()
    if not sel:
        r = sheet.table.currentRow()
        c = sheet.table.currentColumn()
        if r >= 0 and c >= 0:
            return _ref_str(r, c)
        return ""
    return ",".join(_range_ref_str(rng) for rng in sel)


# ── Pickable line-edit (highlights when listening) ──────────────────

_PICK_STYLE = "QLineEdit { border: 2px solid #3a78b4; background: #eef4fb; }"
_NORMAL_STYLE = ""


class _PickLineEdit(QLineEdit):
    """QLineEdit that visually highlights when it is the active
    cell-pick target and notifies its parent dialog."""

    def __init__(self, parent_dlg, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parent_dlg = parent_dlg

    def focusInEvent(self, ev):
        super().focusInEvent(ev)
        self._parent_dlg._set_active_pick(self)


# ── Constraint operators ────────────────────────────────────────────

OPERATORS = ["<=", ">=", "="]


class Constraint:
    """One solver constraint: cell_ref  op  rhs."""

    def __init__(self, cell_ref: str, op: str, rhs: str):
        self.cell_ref = cell_ref  # e.g. "$A$1"
        self.op = op              # "<=", ">=", "="
        self.rhs = rhs            # e.g. "100" or "$B$2"

    def __str__(self):
        return f"{self.cell_ref} {self.op} {self.rhs}"


# ── Add / Change Constraint dialog ─────────────────────────────────

class _ConstraintDialog(QDialog):
    """Small dialog for adding or editing a single constraint.

    Also non-modal with cell-pick support.
    """

    def __init__(self, sheet: SheetWidget, parent=None,
                 constraint: Optional[Constraint] = None,
                 callback=None):
        super().__init__(parent)
        self.setWindowTitle("Add Constraint" if constraint is None
                           else "Change Constraint")
        self.setWindowModality(Qt.NonModal)
        self.resize(420, 130)
        self._sheet = sheet
        self._active_edit: Optional[_PickLineEdit] = None
        self._callback = callback

        layout = QVBoxLayout(self)
        form = QHBoxLayout()

        self._ref_edit = _PickLineEdit(self)
        self._ref_edit.setPlaceholderText("Cell Reference (e.g. $A$1)")
        form.addWidget(self._ref_edit, 3)

        self._op_combo = QComboBox()
        self._op_combo.addItems(OPERATORS)
        form.addWidget(self._op_combo, 1)

        self._rhs_edit = _PickLineEdit(self)
        self._rhs_edit.setPlaceholderText("Constraint (value or cell)")
        form.addWidget(self._rhs_edit, 3)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self._ok_btn = QPushButton("OK")
        self._cancel_btn = QPushButton("Cancel")
        btn_row.addStretch()
        btn_row.addWidget(self._ok_btn)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

        self._ok_btn.clicked.connect(self._on_ok)
        self._cancel_btn.clicked.connect(self.reject)

        if constraint:
            self._ref_edit.setText(constraint.cell_ref)
            idx = (OPERATORS.index(constraint.op)
                   if constraint.op in OPERATORS else 0)
            self._op_combo.setCurrentIndex(idx)
            self._rhs_edit.setText(constraint.rhs)

        # Connect to sheet selection
        self._sheet.table.itemSelectionChanged.connect(
            self._on_sheet_selection)
        self._set_active_pick(self._ref_edit)

    def _set_active_pick(self, edit: _PickLineEdit):
        if self._active_edit and self._active_edit is not edit:
            self._active_edit.setStyleSheet(_NORMAL_STYLE)
        self._active_edit = edit
        edit.setStyleSheet(_PICK_STYLE)

    def _on_sheet_selection(self):
        if self._active_edit is None or not self.isVisible():
            return
        ref = _selection_ref_str(self._sheet)
        if ref:
            self._active_edit.setText(ref)
            self.activateWindow()

    def _on_ok(self):
        c = self.get_constraint()
        if c and self._callback:
            self._callback(c)
        self.accept()

    def get_constraint(self) -> Optional[Constraint]:
        ref = self._ref_edit.text().strip()
        rhs = self._rhs_edit.text().strip()
        if not ref or not rhs:
            return None
        return Constraint(ref, self._op_combo.currentText(), rhs)

    def closeEvent(self, ev):
        try:
            self._sheet.table.itemSelectionChanged.disconnect(
                self._on_sheet_selection)
        except (TypeError, RuntimeError):
            pass
        super().closeEvent(ev)

    def reject(self):
        try:
            self._sheet.table.itemSelectionChanged.disconnect(
                self._on_sheet_selection)
        except (TypeError, RuntimeError):
            pass
        super().reject()


# ── Main Solver Parameters dialog ──────────────────────────────────

class SolverDialog(QDialog):
    """Excel-style Solver Parameters dialog (non-modal).

    Click on a cell-reference input field, then click a cell or drag a
    range in the sheet — the reference is inserted automatically.
    """

    METHODS = ["GRG Nonlinear", "LP Simplex", "Evolutionary"]

    def __init__(self, sheet: SheetWidget, parent=None,
                 headless: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Solver Parameters")
        self.setWindowModality(Qt.NonModal)
        self.setMinimumWidth(560)
        self._sheet = sheet
        self._constraints: List[Constraint] = []
        self._active_edit: Optional[_PickLineEdit] = None

        self._cancelled = False
        self._solving = False
        # Headless runs (scripted, or driven over MCP) must never block
        # on a modal box: outcomes land in _report_log instead and any
        # question takes its default answer.
        self._headless = headless
        self._report_log: List[dict] = []

        self._build_ui()

        # Restore saved state if available, otherwise pre-fill from
        # the current selection.
        saved = getattr(sheet, '_solver_config', {})
        if saved:
            self._load_state(saved)
        else:
            self._pre_fill()

        # Listen to sheet selection changes
        self._sheet.table.itemSelectionChanged.connect(
            self._on_sheet_selection)

    # ── Reporting ───────────────────────────────────────────────────

    def _report(self, level: str, title: str, text: str,
                question: bool = False, default: bool = True) -> bool:
        """Tell the user how the solve went, and return their answer.

        Every outcome is recorded in *_report_log* whether or not a box
        is shown, so a headless caller can report the same thing the
        dialog would have said.
        """
        self._report_log.append({"level": level, "text": text})
        if self._headless:
            return default
        if question:
            reply = QMessageBox.warning(
                self, title, text,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            return reply == QMessageBox.Yes
        {"critical": QMessageBox.critical,
         "warning": QMessageBox.warning,
         "info": QMessageBox.information}[level](self, title, text)
        return default

    # ── Cell-pick machinery ─────────────────────────────────────────

    def _set_active_pick(self, edit: _PickLineEdit):
        """Highlight *edit* as the current cell-pick target."""
        if self._active_edit and self._active_edit is not edit:
            self._active_edit.setStyleSheet(_NORMAL_STYLE)
        self._active_edit = edit
        edit.setStyleSheet(_PICK_STYLE)

    def _on_sheet_selection(self):
        """Called when the user clicks / drags in the sheet."""
        if self._active_edit is None or not self.isVisible():
            return
        ref = _selection_ref_str(self._sheet)
        if not ref:
            return
        # Variable-cells field accumulates comma-separated ranges;
        # all other fields (objective, constraint refs) replace.
        if self._active_edit is self._var_edit:
            cur = self._active_edit.text().strip()
            if cur and ref not in cur.split(","):
                self._active_edit.setText(f"{cur},{ref}")
            else:
                self._active_edit.setText(ref)
        else:
            self._active_edit.setText(ref)
        # Re-activate the dialog so the user can keep working
        self.activateWindow()

    # ── UI construction ─────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # --- Objective ---
        obj_row = QHBoxLayout()
        obj_row.addWidget(QLabel("Set Objective:"))
        self._obj_edit = _PickLineEdit(self)
        self._obj_edit.setPlaceholderText("Click a cell, e.g. $D$5")
        obj_row.addWidget(self._obj_edit, 1)
        layout.addLayout(obj_row)

        # --- To: Max / Min / Value Of ---
        to_row = QHBoxLayout()
        to_row.addWidget(QLabel("To:"))
        self._radio_max = QRadioButton("Max")
        self._radio_min = QRadioButton("Min")
        self._radio_val = QRadioButton("Value Of:")
        self._btn_group = QButtonGroup(self)
        self._btn_group.addButton(self._radio_max, 0)
        self._btn_group.addButton(self._radio_min, 1)
        self._btn_group.addButton(self._radio_val, 2)
        self._radio_min.setChecked(True)
        to_row.addWidget(self._radio_max)
        to_row.addWidget(self._radio_min)
        to_row.addWidget(self._radio_val)
        self._target_edit = QLineEdit()
        self._target_edit.setFixedWidth(80)
        self._target_edit.setEnabled(False)
        to_row.addWidget(self._target_edit)
        to_row.addStretch()
        layout.addLayout(to_row)

        self._radio_val.toggled.connect(self._target_edit.setEnabled)

        # --- Variable cells ---
        var_row = QHBoxLayout()
        var_row.addWidget(QLabel("By Changing Variable Cells:"))
        self._var_edit = _PickLineEdit(self)
        self._var_edit.setPlaceholderText(
            "Click a cell or drag a range, e.g. $A$1:$A$5")
        var_row.addWidget(self._var_edit, 1)
        self._var_clear_btn = QToolButton()
        self._var_clear_btn.setText("\u00d7")  # ×
        self._var_clear_btn.setToolTip("Clear variable cells")
        self._var_clear_btn.setFixedSize(24, 24)
        self._var_clear_btn.clicked.connect(self._var_edit.clear)
        var_row.addWidget(self._var_clear_btn)
        layout.addLayout(var_row)

        # --- Constraints ---
        layout.addWidget(QLabel("Subject to the Constraints:"))
        constr_row = QHBoxLayout()

        self._constr_list = QListWidget()
        self._constr_list.setMinimumHeight(120)
        constr_row.addWidget(self._constr_list, 1)

        btn_col = QVBoxLayout()
        self._add_btn = QPushButton("Add")
        self._change_btn = QPushButton("Change")
        self._delete_btn = QPushButton("Delete")
        self._reset_btn = QPushButton("Reset All")
        for b in (self._add_btn, self._change_btn,
                  self._delete_btn, self._reset_btn):
            b.setFixedWidth(90)
            btn_col.addWidget(b)
        btn_col.addStretch()
        constr_row.addLayout(btn_col)
        layout.addLayout(constr_row)

        self._add_btn.clicked.connect(self._add_constraint)
        self._change_btn.clicked.connect(self._change_constraint)
        self._delete_btn.clicked.connect(self._delete_constraint)
        self._reset_btn.clicked.connect(self._reset_constraints)

        # --- Non-negative ---
        self._nonneg_chk = QCheckBox(
            "Make Unconstrained Variables Non-Negative")
        self._nonneg_chk.setChecked(True)
        layout.addWidget(self._nonneg_chk)

        # --- Keep searching ---
        self._keep_chk = QCheckBox(
            "Keep searching with random restarts until I press Stop")
        self._keep_chk.setToolTip(
            "Useful when the model has a narrow feature far from the data: "
            "a single pass can converge immediately on a flat region. This "
            "keeps trying new starting points, keeping the best result, "
            "until you click Stop.")
        layout.addWidget(self._keep_chk)

        # --- Method ---
        method_row = QHBoxLayout()
        method_row.addWidget(QLabel("Select a Solving Method:"))
        self._method_combo = QComboBox()
        self._method_combo.addItems(self.METHODS)
        method_row.addWidget(self._method_combo, 1)
        layout.addLayout(method_row)

        # --- Description box ---
        self._desc_label = QLabel()
        self._desc_label.setWordWrap(True)
        self._desc_label.setStyleSheet(
            "QLabel { background: #f0f0f0; padding: 8px; "
            "border: 1px solid #ccc; }")
        layout.addWidget(self._desc_label)
        self._method_combo.currentIndexChanged.connect(
            self._update_method_desc)
        self._update_method_desc()

        # --- Bottom buttons ---
        bottom = QHBoxLayout()
        self._solve_btn = QPushButton("Solve")
        self._solve_btn.setDefault(True)
        self._close_btn = QPushButton("Close")
        bottom.addStretch()
        bottom.addWidget(self._solve_btn)
        bottom.addWidget(self._close_btn)
        layout.addLayout(bottom)

        self._solve_btn.clicked.connect(self._on_solve_btn)
        self._close_btn.clicked.connect(self.reject)

        # Default: objective field is active for picking
        self._set_active_pick(self._obj_edit)

    # ── Pre-fill from current selection ─────────────────────────────

    def _pre_fill(self):
        """Pre-fill objective/variable cells from the current selection."""
        sel = self._sheet.table.selectedRanges()
        if sel:
            rng = sel[0]
            top_left = _ref_str(rng.topRow(), rng.leftColumn())
            if rng.rowCount() == 1 and rng.columnCount() == 1:
                self._obj_edit.setText(top_left)
            else:
                bottom_right = _ref_str(rng.bottomRow(),
                                        rng.rightColumn())
                self._var_edit.setText(f"{top_left}:{bottom_right}")

    # ── Method description ──────────────────────────────────────────

    _METHOD_DESCS = {
        "GRG Nonlinear": (
            "Select the GRG Nonlinear engine for Solver Problems that "
            "are smooth nonlinear. Uses scipy.optimize.minimize with "
            "the SLSQP method."),
        "LP Simplex": (
            "Select the LP Simplex engine for linear Solver Problems. "
            "Uses scipy.optimize.linprog with the HiGHS simplex method."),
        "Evolutionary": (
            "Select the Evolutionary engine for Solver Problems that "
            "are non-smooth. Uses scipy.optimize.differential_evolution."),
    }

    def _update_method_desc(self):
        method = self._method_combo.currentText()
        self._desc_label.setText(
            f"<b>Solving Method</b><br>{self._METHOD_DESCS.get(method, '')}")

    # ── Constraint management ───────────────────────────────────────

    def _add_constraint(self):
        dlg = _ConstraintDialog(self._sheet, self,
                                callback=self._on_constraint_added)
        dlg.show()

    def _on_constraint_added(self, c: Constraint):
        self._constraints.append(c)
        self._constr_list.addItem(str(c))

    def _change_constraint(self):
        row = self._constr_list.currentRow()
        if row < 0:
            return
        idx = row  # capture for closure

        def _on_changed(c: Constraint):
            self._constraints[idx] = c
            self._constr_list.item(idx).setText(str(c))

        dlg = _ConstraintDialog(self._sheet, self,
                                self._constraints[row],
                                callback=_on_changed)
        dlg.show()

    def _delete_constraint(self):
        row = self._constr_list.currentRow()
        if row < 0:
            return
        self._constraints.pop(row)
        self._constr_list.takeItem(row)

    def _reset_constraints(self):
        self._constraints.clear()
        self._constr_list.clear()

    # ── Resolve a value that may be a cell ref or a number ──────────

    def _resolve_value(self, text: str) -> Optional[float]:
        """Return float from a number literal or cell reference."""
        text = text.strip()
        rc = _parse_ref(text)
        if rc is not None:
            r, c = rc
            try:
                return float(self._sheet.cell_text(r, c))
            except (ValueError, TypeError):
                return None
        try:
            return float(text)
        except (ValueError, TypeError):
            return None

    # ── State persistence ─────────────────────────────────────────

    def _get_state(self) -> dict:
        """Return all dialog fields as a JSON-serialisable dict."""
        return {
            "objective": self._obj_edit.text(),
            "to_mode": self._btn_group.checkedId(),  # 0=max,1=min,2=val
            "target_value": self._target_edit.text(),
            "var_cells": self._var_edit.text(),
            "constraints": [
                {"ref": c.cell_ref, "op": c.op, "rhs": c.rhs}
                for c in self._constraints
            ],
            "nonneg": self._nonneg_chk.isChecked(),
            "method": self._method_combo.currentIndex(),
            "keep_searching": self._keep_chk.isChecked(),
        }

    def _load_state(self, state: dict):
        """Populate dialog fields from a previously saved state dict."""
        self._obj_edit.setText(state.get("objective", ""))
        to_mode = state.get("to_mode", 1)
        btn = self._btn_group.button(to_mode)
        if btn:
            btn.setChecked(True)
        self._target_edit.setText(state.get("target_value", ""))
        self._var_edit.setText(state.get("var_cells", ""))
        self._constraints.clear()
        self._constr_list.clear()
        for cd in state.get("constraints", []):
            c = Constraint(cd["ref"], cd["op"], cd["rhs"])
            self._constraints.append(c)
            self._constr_list.addItem(str(c))
        self._nonneg_chk.setChecked(state.get("nonneg", True))
        self._method_combo.setCurrentIndex(state.get("method", 0))
        self._keep_chk.setChecked(state.get("keep_searching", False))

    def _save_to_sheet(self):
        """Persist current dialog state onto the sheet object."""
        self._sheet._solver_config = self._get_state()

    # ── Cleanup ─────────────────────────────────────────────────────

    def _disconnect_sheet(self):
        try:
            self._sheet.table.itemSelectionChanged.disconnect(
                self._on_sheet_selection)
        except (TypeError, RuntimeError):
            pass

    def closeEvent(self, ev):
        self._save_to_sheet()
        self._disconnect_sheet()
        super().closeEvent(ev)

    def reject(self):
        self._save_to_sheet()
        self._disconnect_sheet()
        super().reject()

    # ── Solve ───────────────────────────────────────────────────────

    def _on_solve_btn(self):
        """Toggle between Solve and Stop."""
        if self._solving:
            self._cancelled = True
        else:
            self._solve()

    def keyPressEvent(self, ev):
        """Allow Esc to cancel a running solve without closing."""
        if ev.key() == Qt.Key_Escape and self._solving:
            self._cancelled = True
            return
        super().keyPressEvent(ev)

    def _solve(self):
        try:
            from scipy import optimize as opt
        except ImportError:
            self._report(
                "critical", "Missing Dependency",
                "scipy is required for the Solver.\n"
                "Install it with:  pip install scipy")
            return

        # Parse objective cell
        obj_rc = _parse_ref(self._obj_edit.text())
        if obj_rc is None:
            self._report("warning", "Solver", "Invalid objective cell.")
            return

        # Parse variable cells (may span several comma-separated ranges).
        # Deduplicate while preserving order so overlapping ranges don't
        # create duplicate optimiser variables.
        parsed = _parse_range(self._var_edit.text())
        var_cells = list(dict.fromkeys(parsed))
        if not var_cells:
            self._report("warning", "Solver",
                         "Invalid variable cell range.")
            return

        # Save original values for undo
        original = {}
        for r, c in var_cells:
            original[(r, c)] = self._sheet.cell_text(r, c)

        # Read initial guess
        x0 = []
        for r, c in var_cells:
            try:
                x0.append(float(self._sheet.cell_text(r, c)))
            except (ValueError, TypeError):
                x0.append(0.0)

        # Determine sense
        if self._radio_max.isChecked():
            sense = "max"
        elif self._radio_min.isChecked():
            sense = "min"
        else:
            sense = "value"
            target = self._resolve_value(self._target_edit.text())
            if target is None:
                self._report("warning", "Solver",
                             "Invalid target value.")
                return

        # Bounds (unchanged from the original engine: the only box bounds
        # come from the "non-negative" option).  Constraints are passed to
        # the optimiser as real constraints so the search path is exactly
        # what it always was; we additionally remember the lower/upper
        # limits that act on a variable cell so the *final* result can be
        # clipped into range — that is what makes the constraints bind
        # without changing how the solver explores.
        if self._nonneg_chk.isChecked():
            bounds = [(0, None)] * len(var_cells)
        else:
            bounds = [(None, None)] * len(var_cells)

        var_index = {rc: i for i, rc in enumerate(var_cells)}
        clip_lo = [None] * len(var_cells)
        clip_hi = [None] * len(var_cells)

        # Build objective function
        _SOLVE_DEC = 15  # full precision during optimisation

        def _fmt_display(v, dec):
            """Format a float for cell display (matches sheet style)."""
            v = float(v)
            if v == int(v) and abs(v) < 1e15:
                return str(int(v))
            s = f"{round(v, dec):.{dec}f}"
            return s.rstrip("0").rstrip(".")

        def _set_vars(x, full_prec=True):
            """Write trial values into the sheet (silently)."""
            for i, (r, c) in enumerate(var_cells):
                if full_prec:
                    self._sheet._set_cell_quiet(r, c, repr(float(x[i])))
                else:
                    # Format for display using cell's own precision.
                    dec = self._sheet._cell_decimals(r, c)
                    self._sheet._set_cell_quiet(
                        r, c, _fmt_display(x[i], dec))
            # Recalculate formulas that depend on variable cells.
            # Use high precision so the optimizer sees smooth gradients.
            # Seed from all variable cells at once so the shared
            # downstream graph is evaluated only once per trial.
            dec = _SOLVE_DEC if full_prec else None
            self._sheet._recalc_from_seeds(var_cells, decimals=dec)

        def _obj(x):
            _set_vars(x)
            # Read objective — evaluate formula at full precision
            # to avoid rounding that flattens the gradient.
            formula = self._sheet._cell_formulas.get(obj_rc)
            if formula:
                try:
                    val = float(self._sheet._evaluate_formula(
                        formula, obj_rc[0], obj_rc[1], _SOLVE_DEC))
                except (ValueError, TypeError):
                    return 1e30
            else:
                try:
                    val = float(self._sheet.cell_text(*obj_rc))
                except (ValueError, TypeError):
                    return 1e30
            if sense == "max":
                return -val
            elif sense == "value":
                return (val - target) ** 2
            return val

        # Build constraint dicts for scipy
        scipy_constraints = []
        for con in self._constraints:
            con_rc = _parse_ref(con.cell_ref)
            if con_rc is None:
                self._report(
                    "warning", "Solver",
                    f"Invalid constraint reference: {con.cell_ref}")
                # Restore originals
                for (r, c), txt in original.items():
                    self._sheet._set_cell_quiet(r, c, txt)
                return

            rhs_val = self._resolve_value(con.rhs)
            if rhs_val is None:
                self._report(
                    "warning", "Solver",
                    f"Invalid constraint value: {con.rhs}")
                for (r, c), txt in original.items():
                    self._sheet._set_cell_quiet(r, c, txt)
                return

            # If the constraint acts on a variable cell, remember its
            # limit so the final solution can be clipped into range.  The
            # constraint is STILL added below as a real optimiser
            # constraint — clipping is only a guarantee, not a substitute,
            # so the search behaves exactly as it always did.
            idx = var_index.get(con_rc)
            if idx is not None:
                if con.op == "<=":
                    clip_hi[idx] = (rhs_val if clip_hi[idx] is None
                                    else min(clip_hi[idx], rhs_val))
                elif con.op == ">=":
                    clip_lo[idx] = (rhs_val if clip_lo[idx] is None
                                    else max(clip_lo[idx], rhs_val))
                else:  # "="
                    clip_lo[idx] = clip_hi[idx] = rhs_val

            def _read_cell_full(rc):
                """Read a cell value at full precision."""
                f = self._sheet._cell_formulas.get(rc)
                if f:
                    try:
                        return float(self._sheet._evaluate_formula(
                            f, rc[0], rc[1], _SOLVE_DEC))
                    except (ValueError, TypeError):
                        pass
                try:
                    return float(self._sheet.cell_text(*rc))
                except (ValueError, TypeError):
                    return None

            if con.op == "<=":
                def _cfn(x, _rc=con_rc, _rhs=rhs_val):
                    _set_vars(x)
                    v = _read_cell_full(_rc)
                    if v is None:
                        return -1e30
                    return _rhs - v  # >= 0 means cell <= rhs
                scipy_constraints.append({"type": "ineq", "fun": _cfn})
            elif con.op == ">=":
                def _cfn(x, _rc=con_rc, _rhs=rhs_val):
                    _set_vars(x)
                    v = _read_cell_full(_rc)
                    if v is None:
                        return -1e30
                    return v - _rhs  # >= 0 means cell >= rhs
                scipy_constraints.append({"type": "ineq", "fun": _cfn})
            elif con.op == "=":
                def _cfn(x, _rc=con_rc, _rhs=rhs_val):
                    _set_vars(x)
                    v = _read_cell_full(_rc)
                    if v is None:
                        return -1e30
                    return v - _rhs  # == 0
                scipy_constraints.append({"type": "eq", "fun": _cfn})

        # Keep the GUI responsive: scipy runs synchronously on the GUI
        # thread, so pump the event loop on every iteration.  We also
        # refresh embedded charts here so the plot tracks the solve live.
        # If the user clicks Stop or presses Esc, raise to abort.
        class _SolverCancelled(Exception):
            pass

        def _pump(*_args, **_kwargs):
            QApplication.processEvents()
            for chart in getattr(self._sheet, "_charts", []):
                try:
                    chart._refresh_data()
                except Exception:
                    pass
            if self._cancelled:
                raise _SolverCancelled

        import numpy as np

        # Powell bounds want finite/±inf entries, not None.
        powell_bounds = [(-np.inf if lo is None else lo,
                          np.inf if hi is None else hi)
                         for (lo, hi) in bounds]

        def _solve_nonlinear(start):
            # Spreadsheet models are routinely badly scaled — a peak
            # amplitude of ~500 sitting next to a background coefficient
            # of ~0.1 whose term is multiplied by a large x².  Gradient
            # methods (SLSQP) take a finite-difference Jacobian and
            # diverge on such conditioning.  Powell is a derivative-free
            # direction-set method that is immune to this and reliably
            # matches Excel's GRG on these problems, so prefer it when
            # there are no constraints.  Fall back to SLSQP only when
            # constraints are present (Powell can't honour them).  The
            # final result is clipped to the variable-cell limits below
            # so the constraints are respected even if SLSQP drifts.
            if scipy_constraints:
                return opt.minimize(
                    _obj, start, method='SLSQP', bounds=bounds,
                    constraints=scipy_constraints, callback=_pump,
                    options={'maxiter': 1000, 'ftol': 1e-9})
            return opt.minimize(
                _obj, start, method='Powell', bounds=powell_bounds,
                callback=_pump,
                options={'maxiter': 20000, 'xtol': 1e-8, 'ftol': 1e-8})

        # Evolutionary needs finite bounds and a penalty for constraints.
        de_bounds = []
        for i, (lo, hi) in enumerate(bounds):
            lo2 = lo if lo is not None else x0[i] - 1000
            hi2 = hi if hi is not None else x0[i] + 1000
            if lo2 >= hi2:
                hi2 = lo2 + 1000
            de_bounds.append((lo2, hi2))

        def _penalised(x):
            v = _obj(x)
            for cd in scipy_constraints:
                cv = cd["fun"](x)
                if cd["type"] == "ineq" and cv < 0:
                    v += 1e6 * cv ** 2
                elif cd["type"] == "eq":
                    v += 1e6 * cv ** 2
            return v

        method_name = self._method_combo.currentText()

        def _run_once(start):
            if method_name == "Evolutionary":
                return opt.differential_evolution(
                    _penalised, de_bounds, maxiter=1000, tol=1e-12,
                    callback=_pump)
            return _solve_nonlinear(start)

        # Random-restart point for multistart mode: sample bounded
        # (constrained) variables uniformly across their range, jitter the
        # rest around the current best.
        rng = np.random.default_rng()

        def _restart(base):
            nx = list(base)
            for i in range(len(var_cells)):
                lo, hi = clip_lo[i], clip_hi[i]
                if lo is not None and hi is not None:
                    nx[i] = float(rng.uniform(lo, hi))
                elif lo is not None:
                    nx[i] = lo + abs(rng.normal(
                        0.0, max(1.0, abs(base[i]))))
                elif hi is not None:
                    nx[i] = hi - abs(rng.normal(
                        0.0, max(1.0, abs(base[i]))))
                else:
                    nx[i] = base[i] + rng.normal(
                        0.0, max(1.0, abs(base[i])))
            return nx

        # Run solver, looping with random restarts when "keep searching"
        # is on, keeping the best result, until the user presses Stop.
        keep_searching = self._keep_chk.isChecked()
        self._sheet._suppress_recalc_signals = True
        self._cancelled = False
        self._solving = True
        self._solve_btn.setText("Stop")
        self._close_btn.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        cancelled = False
        best = None
        start = list(x0)
        try:
            while True:
                try:
                    res = _run_once(start)
                except _SolverCancelled:
                    cancelled = True
                    break
                if (getattr(res, "x", None) is not None
                        and np.isfinite(res.fun)
                        and (best is None or res.fun < best.fun)):
                    best = res
                    _set_vars(best.x)  # reflect the best so far live
                if not keep_searching:
                    break
                if self._cancelled:
                    cancelled = True
                    break
                start = _restart(best.x if best is not None else x0)
        except Exception as exc:
            for (r, c), txt in original.items():
                self._sheet._set_cell_quiet(r, c, txt)
            self._report("critical", "Solver Error",
                         f"Solver failed:\n{exc}")
            return
        finally:
            self._sheet._suppress_recalc_signals = False
            self._solving = False
            self._cancelled = False
            self._solve_btn.setText("Solve")
            self._close_btn.setEnabled(True)
            QApplication.restoreOverrideCursor()

        if best is None:
            # Cancelled before any run produced a usable result.
            for (r, c), txt in original.items():
                self._sheet._set_cell_quiet(r, c, txt)
            for r, c in var_cells:
                self._sheet._recalc_dependents(r, c)
            self._report(
                "info", "Solver",
                "Solver stopped before finding a solution."
                if cancelled else "Solver could not find a solution.")
            return

        result = best

        # Make the constraints bind: clip every variable that carries a
        # <= / >= / = limit into range.  The search itself was free, so
        # quality matches the old engine; this just guarantees the final
        # values respect the limits the user set.
        if getattr(result, "x", None) is not None:
            for i in range(len(var_cells)):
                lo, hi = clip_lo[i], clip_hi[i]
                if lo is not None and result.x[i] < lo:
                    result.x[i] = lo
                if hi is not None and result.x[i] > hi:
                    result.x[i] = hi

        if cancelled:
            # User stopped a (multistart) search — keep the best found.
            _set_vars(result.x, full_prec=False)
        elif not result.success:
            # Still write the best result found, but warn user.
            # Use normal precision for final display formatting.
            _set_vars(result.x, full_prec=False)
            keep = self._report(
                "warning", "Solver",
                f"Solver could not find a solution.\n"
                f"Reason: {result.message}\n\n"
                f"Keep the best values found, or restore originals?",
                question=True, default=True)
            if not keep:
                for (r, c), txt in original.items():
                    self._sheet._set_cell_quiet(r, c, txt)
                for r, c in var_cells:
                    self._sheet._recalc_dependents(r, c)
                return
        else:
            # Final write at normal display precision.
            _set_vars(result.x, full_prec=False)

        # Push undo command for all changed cells
        if self._sheet._undo_stack is not None:
            from .sheet import BulkCellEditCmd
            changes = []
            for (r, c), old_txt in original.items():
                new_txt = self._sheet.cell_text(r, c)
                if old_txt != new_txt:
                    changes.append((r, c, old_txt, new_txt))
            if changes:
                self._sheet._undo_stack.push(
                    BulkCellEditCmd(self._sheet, changes, "Solver"))

        obj_val = self._sheet.cell_text(*obj_rc)
        # Show a clean number in the message.
        try:
            obj_display = f"{float(obj_val):g}"
        except (ValueError, TypeError):
            obj_display = obj_val
        self._report(
            "info", "Solver",
            (f"Search stopped — keeping the best result found.\n"
             if cancelled else "Solver found a solution.\n")
            + f"Objective cell value: {obj_display}")


# ── Headless entry point ────────────────────────────────────────────

def solve_headless(sheet: SheetWidget, spec: dict) -> dict:
    """Run a solve from a plain dict, with no dialog on screen.

    Used by the AI / MCP tool layer.  The dialog is still what does the
    work — it is built but never shown — so a scripted solve and a
    hand-driven one take exactly the same numerical path, and there is
    no second optimiser to keep in step with this one.
    """
    dlg = SolverDialog(sheet, headless=True)
    try:
        dlg._obj_edit.setText(str(spec.get("objective_cell", "")))
        dlg._var_edit.setText(str(spec.get("variable_cells", "")))

        goal = str(spec.get("goal", "min")).lower()
        dlg._radio_max.setChecked(goal == "max")
        dlg._radio_min.setChecked(goal == "min")
        dlg._radio_val.setChecked(goal in ("value", "target"))
        if spec.get("target_value") is not None:
            dlg._target_edit.setText(str(spec["target_value"]))

        dlg._nonneg_chk.setChecked(bool(spec.get("non_negative", False)))
        # Multistart never terminates on its own — it runs until the
        # user presses Stop, and there is nobody to press it here.
        dlg._keep_chk.setChecked(False)

        method = spec.get("method")
        if method:
            if method not in SolverDialog.METHODS:
                return {"error": f"Unknown method {method!r}. "
                                 f"Choose from {SolverDialog.METHODS}."}
            dlg._method_combo.setCurrentText(method)

        dlg._constraints = []
        for con in spec.get("constraints") or []:
            op = str(con.get("op", "<="))
            if op not in ("<=", ">=", "="):
                return {"error": f"Unknown constraint operator {op!r}. "
                                 "Use '<=', '>=' or '='."}
            dlg._constraints.append(
                Constraint(str(con.get("cell", "")), op,
                           str(con.get("value", ""))))

        var_cells = list(dict.fromkeys(_parse_range(dlg._var_edit.text())))
        before = {rc: sheet.cell_text(*rc) for rc in var_cells}

        dlg._solve()

        obj_rc = _parse_ref(dlg._obj_edit.text())
        after = {_ref_str(*rc): sheet.cell_text(*rc) for rc in var_cells}
        changed = any(sheet.cell_text(*rc) != before[rc]
                      for rc in var_cells)
        messages = [m["text"] for m in dlg._report_log]
        failed = any(m["level"] in ("warning", "critical")
                     for m in dlg._report_log)
        result = {
            "solved": bool(changed and not failed),
            "method": dlg._method_combo.currentText(),
            "goal": goal,
            "variables": after,
            "messages": messages,
        }
        if obj_rc is not None:
            result["objective_cell"] = _ref_str(*obj_rc)
            result["objective_value"] = sheet.cell_text(*obj_rc)
        if failed and not changed:
            result["error"] = "; ".join(messages) or "Solve failed."
        return result
    finally:
        dlg._disconnect_sheet()
        dlg.deleteLater()
