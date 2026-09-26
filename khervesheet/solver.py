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

from typing import List, Optional, Tuple

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QRadioButton, QCheckBox, QComboBox,
    QListWidget, QListWidgetItem, QPushButton, QGroupBox, QMessageBox,
    QButtonGroup, QWidget, QSizePolicy, QToolButton, QApplication,
)

from .core import solver as core_solver
from .sheet import SheetWidget

# ── Cell reference helpers ──────────────────────────────────────────

_parse_ref = core_solver.parse_ref
_parse_range = core_solver.parse_range
_ref_str = core_solver.ref_str


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

    METHODS = core_solver.METHODS

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
            import scipy  # noqa: F401
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

        # Variable cells (several comma-separated ranges; duplicates go).
        var_cells = list(dict.fromkeys(_parse_range(self._var_edit.text())))
        if not var_cells:
            self._report("warning", "Solver",
                         "Invalid variable cell range.")
            return

        # Save original values for undo
        original = {rc: self._sheet.cell_text(*rc) for rc in var_cells}

        if self._radio_max.isChecked():
            goal, target = "max", 0.0
        elif self._radio_min.isChecked():
            goal, target = "min", 0.0
        else:
            goal = "value"
            target = self._resolve_value(self._target_edit.text())
            if target is None:
                self._report("warning", "Solver",
                             "Invalid target value.")
                return

        constraints = []
        for con in self._constraints:
            con_rc = _parse_ref(con.cell_ref)
            if con_rc is None:
                self._report(
                    "warning", "Solver",
                    f"Invalid constraint reference: {con.cell_ref}")
                return
            rhs_val = self._resolve_value(con.rhs)
            if rhs_val is None:
                self._report(
                    "warning", "Solver",
                    f"Invalid constraint value: {con.rhs}")
                return
            constraints.append(core_solver.Constraint(con_rc, con.op,
                                                      rhs_val))

        problem = core_solver.Problem(
            objective=obj_rc, variables=var_cells, goal=goal,
            target=target, constraints=constraints,
            non_negative=self._nonneg_chk.isChecked(),
            method=self._method_combo.currentText(),
            keep_searching=self._keep_chk.isChecked())
        host = _SheetHost(self._sheet)

        # scipy runs on the GUI thread: keep the window alive and the
        # charts following the search; Stop / Esc cancels.
        def _pump():
            QApplication.processEvents()
            for chart in getattr(self._sheet, "_charts", []):
                try:
                    chart._refresh_data()
                except Exception:
                    pass
            if self._cancelled:
                raise core_solver.Cancelled

        def _restore():
            for (r, c), txt in original.items():
                self._sheet._set_cell_quiet(r, c, txt)
            for r, c in var_cells:
                self._sheet._recalc_dependents(r, c)

        self._sheet._suppress_recalc_signals = True
        self._cancelled = False
        self._solving = True
        self._solve_btn.setText("Stop")
        self._close_btn.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            outcome = core_solver.solve(host, problem, _pump)
        except Exception as exc:
            _restore()
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

        if outcome.x is None:
            _restore()
            self._report("info", "Solver", outcome.message)
            return

        # Final write at each cell's display precision.
        host.write_final(var_cells, outcome.x)
        if not outcome.success:
            keep = self._report(
                "warning", "Solver",
                f"Solver could not find a solution.\n"
                f"Reason: {outcome.message}\n\n"
                f"Keep the best values found, or restore originals?",
                question=True, default=True)
            if not keep:
                _restore()
                return

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
        try:
            obj_display = f"{float(obj_val):g}"
        except (ValueError, TypeError):
            obj_display = obj_val
        self._report(
            "info", "Solver",
            ("Search stopped — keeping the best result found.\n"
             if outcome.cancelled else "Solver found a solution.\n")
            + f"Objective cell value: {obj_display}")


_SOLVE_DEC = 15  # full precision during optimisation


class _SheetHost(core_solver.SolverHost):
    """The desktop sheet, for core.solver."""

    def __init__(self, sheet: SheetWidget):
        self.sheet = sheet

    def value(self, cell):
        formula = self.sheet._cell_formulas.get(cell)
        try:
            if formula:
                return float(self.sheet._evaluate_formula(
                    formula, cell[0], cell[1], _SOLVE_DEC))
            return float(self.sheet.cell_text(*cell))
        except (ValueError, TypeError):
            return None

    def try_values(self, cells, values):
        for (r, c), v in zip(cells, values):
            self.sheet._set_cell_quiet(r, c, repr(float(v)))
        # One recalculation seeded from every variable cell.
        self.sheet._recalc_from_seeds(list(cells), decimals=_SOLVE_DEC)

    def write_final(self, cells, values):
        for (r, c), v in zip(cells, values):
            self.sheet._set_cell_quiet(r, c, core_solver.display_number(
                v, self.sheet._cell_decimals(r, c)))
        self.sheet._recalc_from_seeds(list(cells))


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
