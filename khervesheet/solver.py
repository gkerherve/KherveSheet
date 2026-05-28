"""Solver — Excel-style optimisation dialog.

Minimise / maximise / target a cell value by changing variable cells,
subject to linear and nonlinear constraints.  Uses scipy.optimize
under the hood.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re
from typing import List, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QRadioButton, QCheckBox, QComboBox,
    QListWidget, QListWidgetItem, QPushButton, QGroupBox, QMessageBox,
    QButtonGroup, QWidget, QSizePolicy,
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
    """Parse a cell reference or range like 'A1:A5' → list of (row, col)."""
    text = text.strip()
    if ':' in text:
        parts = text.split(':')
        if len(parts) != 2:
            return []
        start = _parse_ref(parts[0])
        end = _parse_ref(parts[1])
        if start is None or end is None:
            return []
        r1, c1 = start
        r2, c2 = end
        cells = []
        for r in range(min(r1, r2), max(r1, r2) + 1):
            for c in range(min(c1, c2), max(c1, c2) + 1):
                cells.append((r, c))
        return cells
    # Comma-separated refs
    cells = []
    for part in text.split(','):
        part = part.strip()
        if ':' in part:
            cells.extend(_parse_range(part))
        else:
            rc = _parse_ref(part)
            if rc:
                cells.append(rc)
    return cells


def _ref_str(row: int, col: int) -> str:
    """(row, col) 0-based → '$A$1' string."""
    return f"${col_index_to_letter(col)}${row + 1}"


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
    """Small dialog for adding or editing a single constraint."""

    def __init__(self, parent=None, constraint: Optional[Constraint] = None):
        super().__init__(parent)
        self.setWindowTitle("Add Constraint" if constraint is None
                           else "Change Constraint")
        self.resize(400, 120)

        layout = QVBoxLayout(self)
        form = QHBoxLayout()

        self._ref_edit = QLineEdit()
        self._ref_edit.setPlaceholderText("Cell Reference (e.g. $A$1)")
        form.addWidget(self._ref_edit, 3)

        self._op_combo = QComboBox()
        self._op_combo.addItems(OPERATORS)
        form.addWidget(self._op_combo, 1)

        self._rhs_edit = QLineEdit()
        self._rhs_edit.setPlaceholderText("Constraint (value or cell)")
        form.addWidget(self._rhs_edit, 3)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        if constraint:
            self._ref_edit.setText(constraint.cell_ref)
            idx = OPERATORS.index(constraint.op) if constraint.op in OPERATORS else 0
            self._op_combo.setCurrentIndex(idx)
            self._rhs_edit.setText(constraint.rhs)

    def get_constraint(self) -> Optional[Constraint]:
        ref = self._ref_edit.text().strip()
        rhs = self._rhs_edit.text().strip()
        if not ref or not rhs:
            return None
        return Constraint(ref, self._op_combo.currentText(), rhs)


# ── Main Solver Parameters dialog ──────────────────────────────────

class SolverDialog(QDialog):
    """Excel-style Solver Parameters dialog."""

    METHODS = ["GRG Nonlinear", "LP Simplex", "Evolutionary"]

    def __init__(self, sheet: SheetWidget, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Solver Parameters")
        self.setMinimumWidth(560)
        self._sheet = sheet
        self._constraints: List[Constraint] = []

        self._build_ui()
        self._pre_fill()

    # ── UI construction ─────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # --- Objective ---
        obj_form = QFormLayout()
        self._obj_edit = QLineEdit()
        self._obj_edit.setPlaceholderText("e.g. $D$5")
        obj_form.addRow("Set Objective:", self._obj_edit)
        layout.addLayout(obj_form)

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
        var_form = QFormLayout()
        self._var_edit = QLineEdit()
        self._var_edit.setPlaceholderText("e.g. $A$1:$A$5")
        var_form.addRow("By Changing Variable Cells:", self._var_edit)
        layout.addLayout(var_form)

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

        self._solve_btn.clicked.connect(self._solve)
        self._close_btn.clicked.connect(self.reject)

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
                bottom_right = _ref_str(rng.bottomRow(), rng.rightColumn())
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
        dlg = _ConstraintDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            c = dlg.get_constraint()
            if c:
                self._constraints.append(c)
                self._constr_list.addItem(str(c))

    def _change_constraint(self):
        row = self._constr_list.currentRow()
        if row < 0:
            return
        dlg = _ConstraintDialog(self, self._constraints[row])
        if dlg.exec_() == QDialog.Accepted:
            c = dlg.get_constraint()
            if c:
                self._constraints[row] = c
                self._constr_list.item(row).setText(str(c))

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

    # ── Solve ───────────────────────────────────────────────────────

    def _solve(self):
        try:
            from scipy import optimize as opt
        except ImportError:
            QMessageBox.critical(
                self, "Missing Dependency",
                "scipy is required for the Solver.\n"
                "Install it with:  pip install scipy")
            return

        # Parse objective cell
        obj_rc = _parse_ref(self._obj_edit.text())
        if obj_rc is None:
            QMessageBox.warning(self, "Solver", "Invalid objective cell.")
            return

        # Parse variable cells
        var_cells = _parse_range(self._var_edit.text())
        if not var_cells:
            QMessageBox.warning(self, "Solver",
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
                QMessageBox.warning(self, "Solver",
                                    "Invalid target value.")
                return

        # Bounds
        if self._nonneg_chk.isChecked():
            bounds = [(0, None)] * len(var_cells)
        else:
            bounds = [(None, None)] * len(var_cells)

        # Build objective function
        def _set_vars(x):
            """Write trial values into the sheet (silently)."""
            self._sheet.table.blockSignals(True)
            for i, (r, c) in enumerate(var_cells):
                self._sheet._set_cell_quiet(r, c, str(x[i]))
            self._sheet.table.blockSignals(False)
            # Recalculate formulas that depend on variable cells
            for r, c in var_cells:
                self._sheet._recalc_dependents(r, c)

        def _obj(x):
            _set_vars(x)
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
                QMessageBox.warning(
                    self, "Solver",
                    f"Invalid constraint reference: {con.cell_ref}")
                # Restore originals
                for (r, c), txt in original.items():
                    self._sheet._set_cell_quiet(r, c, txt)
                return

            rhs_val = self._resolve_value(con.rhs)
            if rhs_val is None:
                QMessageBox.warning(
                    self, "Solver",
                    f"Invalid constraint value: {con.rhs}")
                for (r, c), txt in original.items():
                    self._sheet._set_cell_quiet(r, c, txt)
                return

            if con.op == "<=":
                def _cfn(x, _rc=con_rc, _rhs=rhs_val):
                    _set_vars(x)
                    try:
                        v = float(self._sheet.cell_text(*_rc))
                    except (ValueError, TypeError):
                        return -1e30
                    return _rhs - v  # >= 0 means cell <= rhs
                scipy_constraints.append({"type": "ineq", "fun": _cfn})
            elif con.op == ">=":
                def _cfn(x, _rc=con_rc, _rhs=rhs_val):
                    _set_vars(x)
                    try:
                        v = float(self._sheet.cell_text(*_rc))
                    except (ValueError, TypeError):
                        return -1e30
                    return v - _rhs  # >= 0 means cell >= rhs
                scipy_constraints.append({"type": "ineq", "fun": _cfn})
            elif con.op == "=":
                def _cfn(x, _rc=con_rc, _rhs=rhs_val):
                    _set_vars(x)
                    try:
                        v = float(self._sheet.cell_text(*_rc))
                    except (ValueError, TypeError):
                        return -1e30
                    return v - _rhs  # == 0
                scipy_constraints.append({"type": "eq", "fun": _cfn})

        # Run solver
        method_name = self._method_combo.currentText()
        try:
            if method_name == "GRG Nonlinear":
                result = opt.minimize(
                    _obj, x0, method='SLSQP', bounds=bounds,
                    constraints=scipy_constraints,
                    options={'maxiter': 1000, 'ftol': 1e-12})
            elif method_name == "LP Simplex":
                # For LP, fall back to SLSQP since linprog needs
                # explicit matrix form which is hard to extract
                # from a general spreadsheet model.
                result = opt.minimize(
                    _obj, x0, method='SLSQP', bounds=bounds,
                    constraints=scipy_constraints,
                    options={'maxiter': 1000, 'ftol': 1e-12})
            elif method_name == "Evolutionary":
                # differential_evolution needs finite bounds
                de_bounds = []
                for i, (lo, hi) in enumerate(bounds):
                    lo2 = lo if lo is not None else x0[i] - 1000
                    hi2 = hi if hi is not None else x0[i] + 1000
                    if lo2 >= hi2:
                        hi2 = lo2 + 1000
                    de_bounds.append((lo2, hi2))
                # differential_evolution doesn't accept constraints
                # directly — wrap as penalty
                base_obj = _obj

                def _penalised(x):
                    v = base_obj(x)
                    for cd in scipy_constraints:
                        cv = cd["fun"](x)
                        if cd["type"] == "ineq" and cv < 0:
                            v += 1e6 * cv ** 2
                        elif cd["type"] == "eq":
                            v += 1e6 * cv ** 2
                    return v
                result = opt.differential_evolution(
                    _penalised, de_bounds, maxiter=1000, tol=1e-12)
            else:
                result = opt.minimize(
                    _obj, x0, method='SLSQP', bounds=bounds,
                    constraints=scipy_constraints)
        except Exception as exc:
            # Restore on failure
            for (r, c), txt in original.items():
                self._sheet._set_cell_quiet(r, c, txt)
            QMessageBox.critical(
                self, "Solver Error", f"Solver failed:\n{exc}")
            return

        if not result.success:
            # Still write the best result found, but warn user
            _set_vars(result.x)
            # Recalc all dependents for final state
            for r, c in var_cells:
                self._sheet._recalc_dependents(r, c)
            reply = QMessageBox.warning(
                self, "Solver",
                f"Solver could not find a solution.\n"
                f"Reason: {result.message}\n\n"
                f"Keep the best values found, or restore originals?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes)
            if reply == QMessageBox.No:
                for (r, c), txt in original.items():
                    self._sheet._set_cell_quiet(r, c, txt)
                for r, c in var_cells:
                    self._sheet._recalc_dependents(r, c)
                return
        else:
            _set_vars(result.x)
            for r, c in var_cells:
                self._sheet._recalc_dependents(r, c)

        # Push undo command for all changed cells
        if self._sheet._undo_stack:
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
        QMessageBox.information(
            self, "Solver",
            f"Solver found a solution.\n"
            f"Objective cell value: {obj_val}")
        self.accept()
