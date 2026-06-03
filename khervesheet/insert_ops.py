"""Insert operations — checkbox, dropdown, link, comment, note, emoji,
pivot/transpose, and spell-check.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import re

from PyQt5.QtCore import Qt, QTimer, QEvent, QObject
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGridLayout, QWidget, QTableWidgetItem,
    QComboBox, QTextEdit, QDialogButtonBox, QFormLayout,
    QInputDialog, QMessageBox, QApplication, QWidgetAction,
    QScrollArea, QToolTip,
)


# ── Checkbox ────────────────────────────────────────────────────────
def insert_checkbox(sheet):
    """Insert a toggleable checkbox (TRUE/FALSE) in the current cell."""
    row = sheet.table.currentRow()
    col = sheet.table.currentColumn()
    if row < 0 or col < 0:
        return
    it = sheet.table.item(row, col)
    old = it.text() if it else ""
    new_val = ""
    if it is None:
        it = QTableWidgetItem(new_val)
        sheet.table.setItem(row, col, it)
    else:
        it.setText(new_val)
    it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
    it.setCheckState(Qt.Unchecked)
    sheet._shadow[(row, col)] = new_val
    if sheet._undo_stack is not None:
        from .sheet import CellEditCmd
        sheet._undo_stack.push(
            CellEditCmd(sheet, row, col, old, new_val))


def toggle_checkbox(sheet, row, col):
    """Toggle a checkbox cell between checked and unchecked."""
    it = sheet.table.item(row, col)
    if it is None:
        return
    if it.checkState() == Qt.Checked:
        it.setCheckState(Qt.Unchecked)
    else:
        it.setCheckState(Qt.Checked)


# ── Dropdown (data validation) ──────────────────────────────────────
class DropdownDialog(QDialog):
    """Dialog to configure a dropdown list for selected cells."""

    def __init__(self, parent=None, current_items=""):
        super().__init__(parent)
        self.setWindowTitle("Configure Dropdown")
        self.resize(350, 200)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Enter comma-separated values for the dropdown list:"))
        self._edit = QTextEdit()
        self._edit.setPlainText(current_items)
        self._edit.setPlaceholderText("Option1, Option2, Option3")
        layout.addWidget(self._edit)
        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def items(self):
        raw = self._edit.toPlainText()
        return [s.strip() for s in raw.split(",") if s.strip()]


def insert_dropdown(sheet, parent=None):
    """Configure a dropdown validation list on the selected cells."""
    row = sheet.table.currentRow()
    col = sheet.table.currentColumn()
    if row < 0 or col < 0:
        return
    # Check existing dropdown items.
    existing = ""
    dd = getattr(sheet, '_cell_dropdowns', {})
    if (row, col) in dd:
        existing = ", ".join(dd[(row, col)])
    dlg = DropdownDialog(parent, existing)
    if dlg.exec_() != QDialog.Accepted:
        return
    items = dlg.items()
    if not items:
        return
    if not hasattr(sheet, '_cell_dropdowns'):
        sheet._cell_dropdowns = {}
    # Apply to all selected cells.
    for rng in sheet.table.selectedRanges():
        for r in range(rng.topRow(), rng.bottomRow() + 1):
            for c in range(rng.leftColumn(), rng.rightColumn() + 1):
                sheet._cell_dropdowns[(r, c)] = items
                # Set first item as default if cell is empty.
                it = sheet.table.item(r, c)
                if it is None or not it.text():
                    if it is None:
                        it = QTableWidgetItem(items[0])
                        sheet.table.setItem(r, c, it)
                    else:
                        it.setText(items[0])
                    sheet._shadow[(r, c)] = items[0]
                mark_dropdown_cell(sheet, r, c)


def mark_dropdown_cell(sheet, row, col):
    """Make a validated cell non-editable so its value can only be
    changed through the dropdown list (no free-text typing)."""
    it = sheet.table.item(row, col)
    if it is None:
        it = QTableWidgetItem("")
        sheet.table.setItem(row, col, it)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)


class _DropdownCloseFilter(QObject):
    """Deletes the dropdown combo when it loses focus."""
    def __init__(self, combo, sheet):
        super().__init__(combo)
        self._combo = combo
        self._sheet = sheet
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Hide:
            QTimer.singleShot(200, self._combo.deleteLater)
        return False


def show_dropdown_for_cell(sheet, row, col):
    """Show a QComboBox popup for a dropdown-validated cell."""
    dd = getattr(sheet, '_cell_dropdowns', {})
    items = dd.get((row, col))
    if not items:
        return False
    combo = QComboBox(sheet.table.viewport())
    combo.addItems(items)
    it = sheet.table.item(row, col)
    if it and it.text() in items:
        combo.setCurrentText(it.text())
    # Overlay the combo exactly on the cell so its popup drops down from
    # the cell itself (previously it was offset one row below).
    x = sheet.table.columnViewportPosition(col)
    y = sheet.table.rowViewportPosition(row)
    w = max(sheet.table.columnWidth(col), 60)
    h = sheet.table.rowHeight(row)
    combo.setGeometry(x, y, w, h)
    combo.show()
    combo.showPopup()

    def _apply(idx):
        text = combo.itemText(idx)
        it = sheet.table.item(row, col)
        old = it.text() if it else ""
        if it is None:
            from PyQt5.QtWidgets import QTableWidgetItem
            it = QTableWidgetItem(text)
            sheet.table.setItem(row, col, it)
        else:
            it.setText(text)
        sheet._shadow[(row, col)] = text
        QTimer.singleShot(0, combo.deleteLater)

    combo.activated[int].connect(_apply)
    # Delete combo when popup is closed without selecting
    combo.installEventFilter(_DropdownCloseFilter(combo, sheet))
    return True


# ── Hyperlink ───────────────────────────────────────────────────────
class LinkDialog(QDialog):
    """Insert / edit a hyperlink."""

    def __init__(self, parent=None, text="", url=""):
        super().__init__(parent)
        self.setWindowTitle("Insert Link")
        self.resize(400, 140)
        layout = QFormLayout(self)
        self._text_edit = QLineEdit(text)
        self._url_edit = QLineEdit(url)
        self._url_edit.setPlaceholderText("https://example.com")
        layout.addRow("Display text:", self._text_edit)
        layout.addRow("URL:", self._url_edit)
        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addRow(bb)

    def result_data(self):
        return self._text_edit.text(), self._url_edit.text()


def insert_link(sheet, parent=None):
    """Insert a hyperlink into the current cell."""
    row = sheet.table.currentRow()
    col = sheet.table.currentColumn()
    if row < 0 or col < 0:
        return
    it = sheet.table.item(row, col)
    text = it.text() if it else ""
    # Check existing link.
    links = getattr(sheet, '_cell_links', {})
    url = links.get((row, col), "")
    dlg = LinkDialog(parent, text, url)
    if dlg.exec_() != QDialog.Accepted:
        return
    display, url = dlg.result_data()
    if not url:
        return
    if not hasattr(sheet, '_cell_links'):
        sheet._cell_links = {}
    sheet._cell_links[(row, col)] = url
    sheet.table.blockSignals(True)
    if it is None:
        it = QTableWidgetItem(display or url)
        sheet.table.setItem(row, col, it)
    else:
        it.setText(display or url)
    # Style as hyperlink.
    f = it.font()
    f.setUnderline(True)
    it.setFont(f)
    it.setForeground(QColor("#0563C1"))
    sheet.table.blockSignals(False)
    sheet._shadow[(row, col)] = display or url


def open_link(sheet, row, col):
    """Open a hyperlink if the cell has one."""
    links = getattr(sheet, '_cell_links', {})
    url = links.get((row, col))
    if url:
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))
        return True
    return False


# ── Comment / Note ──────────────────────────────────────────────────
def insert_comment(sheet, parent=None):
    """Add or edit a white comment on the current cell."""
    row = sheet.table.currentRow()
    col = sheet.table.currentColumn()
    if row < 0 or col < 0:
        return
    existing = sheet._cell_notes.get((row, col), {})
    old_text = existing.get("text", "") if isinstance(existing, dict) else str(existing)
    text, ok = QInputDialog.getMultiLineText(
        parent or sheet, "Edit Comment",
        f"Comment for {_cell_ref(row, col)}:",
        old_text)
    if not ok:
        return
    if text.strip():
        sheet._cell_notes[(row, col)] = {"text": text, "kind": "comment"}
        it = sheet.table.item(row, col)
        if it is None:
            it = QTableWidgetItem("")
            sheet.table.setItem(row, col, it)
        it.setToolTip("")  # We handle hover ourselves
    else:
        sheet._cell_notes.pop((row, col), None)
    sheet.table.viewport().update()


def insert_note(sheet, parent=None):
    """Add or edit a yellow sticky note on the current cell."""
    row = sheet.table.currentRow()
    col = sheet.table.currentColumn()
    if row < 0 or col < 0:
        return
    existing = sheet._cell_notes.get((row, col), {})
    old_text = existing.get("text", "") if isinstance(existing, dict) else str(existing)
    text, ok = QInputDialog.getMultiLineText(
        parent or sheet, "Edit Note",
        f"Note for {_cell_ref(row, col)}:",
        old_text)
    if not ok:
        return
    if text.strip():
        sheet._cell_notes[(row, col)] = {"text": text, "kind": "note"}
        it = sheet.table.item(row, col)
        if it is None:
            it = QTableWidgetItem("")
            sheet.table.setItem(row, col, it)
        it.setToolTip("")  # We handle hover ourselves
    else:
        sheet._cell_notes.pop((row, col), None)
    sheet.table.viewport().update()


def _cell_ref(row, col):
    from .sheet import col_index_to_letter
    return f"{col_index_to_letter(col)}{row + 1}"


# ── Emoji picker ────────────────────────────────────────────────────
# Common emoji groups — a curated selection.
_EMOJI_GROUPS = {
    "Smileys": list("😀😃😄😁😆😅🤣😂🙂😉😊😇"
                     "🥰😍🤩😘😗😋😛😜🤪😝🤑🤗"),
    "Gestures": list("👍👎👏🙌🤝🤲👐✌🤞🤟🤘🤙"
                      "👈👉👆👇☝✋🤚🖐🖖👋🤏"),
    "Objects": list("⭐🌟💡🔥❤💎🏆🎯📌📎✏📝"
                     "💰📊📈📉🔬🔭🧪🧮💻📱"),
    "Symbols": list("✅❌⚠️ℹ❓❗✔➕➖➗💲"
                     "©®™🔴🟢🔵⚫⚪🟡🟠🟣"),
}


def build_emoji_grid(parent_menu, insert_callback):
    """Build an emoji picker widget for embedding in a menu."""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(4)
    for group_name, emojis in _EMOJI_GROUPS.items():
        lbl = QLabel(f"<b>{group_name}</b>")
        lbl.setStyleSheet("color: #555; font-size: 10px;")
        layout.addWidget(lbl)
        grid = QGridLayout()
        grid.setSpacing(1)
        cols = 12
        for i, em in enumerate(emojis):
            btn = QPushButton(em)
            btn.setFixedSize(28, 28)
            btn.setStyleSheet("font-size: 16px; border: none;")
            btn.setToolTip(em)
            btn.clicked.connect(
                lambda _, e=em: insert_callback(e))
            grid.addWidget(btn, i // cols, i % cols)
        layout.addLayout(grid)
    return container


# ── Pivot / Transpose ───────────────────────────────────────────────
def transpose_selection(sheet, undo_stack=None):
    """Transpose the selected range (swap rows and columns)."""
    sel = sheet.table.selectedRanges()
    if not sel:
        QMessageBox.information(
            sheet, "No Selection",
            "Select a range of cells to transpose.")
        return
    rng = sel[0]
    r0, r1 = rng.topRow(), rng.bottomRow()
    c0, c1 = rng.leftColumn(), rng.rightColumn()
    n_rows = r1 - r0 + 1
    n_cols = c1 - c0 + 1

    # Read the source data.
    data = []
    for r in range(r0, r1 + 1):
        row_data = []
        for c in range(c0, c1 + 1):
            it = sheet.table.item(r, c)
            row_data.append(it.text() if it else "")
        data.append(row_data)

    # Check destination fits.
    dest_rows = n_cols
    dest_cols = n_rows
    if r0 + dest_rows > sheet.row_count():
        QMessageBox.warning(
            sheet, "Transpose",
            "Not enough rows for the transposed data.")
        return
    if c0 + dest_cols > sheet.column_count():
        QMessageBox.warning(
            sheet, "Transpose",
            "Not enough columns for the transposed data.")
        return

    # Collect changes for undo.
    changes = []
    sheet.table.blockSignals(True)
    try:
        # Clear original range.
        for r in range(r0, r0 + max(n_rows, dest_rows)):
            for c in range(c0, c0 + max(n_cols, dest_cols)):
                if r >= sheet.row_count() or c >= sheet.column_count():
                    continue
                it = sheet.table.item(r, c)
                old = it.text() if it else ""
                # Determine new value.
                tr = c - c0  # transposed row index
                tc = r - r0  # transposed col index
                if tr < n_rows and tc < n_cols:
                    new_val = data[tr][tc]
                else:
                    new_val = ""
                if it is None:
                    it = QTableWidgetItem(new_val)
                    sheet.table.setItem(r, c, it)
                else:
                    it.setText(new_val)
                sheet._shadow[(r, c)] = new_val
                if old != new_val:
                    changes.append((r, c, old, new_val))
    finally:
        sheet.table.blockSignals(False)

    if changes and undo_stack:
        from .sheet import BulkCellEditCmd
        undo_stack.push(BulkCellEditCmd(sheet, changes, "Transpose"))

    # Select the transposed area.
    from PyQt5.QtWidgets import QTableWidgetSelectionRange
    sheet.table.setRangeSelected(
        QTableWidgetSelectionRange(
            r0, c0, r0 + dest_rows - 1, c0 + dest_cols - 1),
        True)


# ── Spell-check ─────────────────────────────────────────────────────
# Uses a simple built-in word list approach. For a richer experience
# install pyspellchecker: pip install pyspellchecker

def _get_checker():
    """Return a spell-checker object, or None if unavailable."""
    try:
        from spellchecker import SpellChecker
        return SpellChecker()
    except ImportError:
        return None


class SpellCheckDialog(QDialog):
    """Walk through misspelled words in the sheet."""

    def __init__(self, sheet, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spelling")
        self.resize(420, 260)
        self._sheet = sheet
        self._checker = _get_checker()
        self._misspelled = []  # [(row, col, word, suggestions), ...]
        self._idx = -1

        layout = QVBoxLayout(self)
        if self._checker is None:
            layout.addWidget(QLabel(
                "<b>Spell-checker not available.</b><br><br>"
                "Install it with:<br>"
                "<code>pip install pyspellchecker</code>"))
            bb = QDialogButtonBox(QDialogButtonBox.Close)
            bb.rejected.connect(self.reject)
            layout.addWidget(bb)
            return

        self._scan_sheet()

        # Word display.
        self._word_label = QLabel("")
        self._word_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: red;")
        layout.addWidget(self._word_label)

        self._cell_label = QLabel("")
        self._cell_label.setStyleSheet("color: #666;")
        layout.addWidget(self._cell_label)

        # Replacement.
        row_h = QHBoxLayout()
        row_h.addWidget(QLabel("Replace with:"))
        self._replace_edit = QLineEdit()
        row_h.addWidget(self._replace_edit)
        layout.addLayout(row_h)

        # Suggestions.
        self._suggestions_label = QLabel("Suggestions:")
        layout.addWidget(self._suggestions_label)
        self._sug_combo = QComboBox()
        self._sug_combo.currentTextChanged.connect(
            self._replace_edit.setText)
        layout.addWidget(self._sug_combo)

        # Buttons.
        btn_row = QHBoxLayout()
        self._change_btn = QPushButton("Change")
        self._change_btn.clicked.connect(self._change)
        self._ignore_btn = QPushButton("Ignore")
        self._ignore_btn.clicked.connect(self._next_word)
        self._ignore_all_btn = QPushButton("Ignore All")
        self._ignore_all_btn.clicked.connect(self._ignore_all)
        btn_row.addWidget(self._change_btn)
        btn_row.addWidget(self._ignore_btn)
        btn_row.addWidget(self._ignore_all_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._ignored = set()
        self._next_word()

    def _scan_sheet(self):
        """Scan all cells for misspelled words."""
        sheet = self._sheet
        checker = self._checker
        word_re = re.compile(r"[A-Za-z']+")
        for r in range(sheet.row_count()):
            for c in range(sheet.column_count()):
                it = sheet.table.item(r, c)
                if not it:
                    continue
                text = it.text()
                if not text or text.startswith("="):
                    continue
                # Skip numeric values.
                try:
                    float(text)
                    continue
                except ValueError:
                    pass
                words = word_re.findall(text)
                for w in words:
                    if len(w) < 2:
                        continue
                    misspelled = checker.unknown([w])
                    if misspelled:
                        sugs = list(checker.candidates(w) or [])
                        self._misspelled.append((r, c, w, sugs))

    def _next_word(self):
        self._idx += 1
        while (self._idx < len(self._misspelled)
               and self._misspelled[self._idx][2].lower()
               in self._ignored):
            self._idx += 1
        if self._idx >= len(self._misspelled):
            self._word_label.setText("Spell check complete.")
            self._cell_label.setText("")
            self._replace_edit.clear()
            self._sug_combo.clear()
            self._change_btn.setEnabled(False)
            self._ignore_btn.setEnabled(False)
            self._ignore_all_btn.setEnabled(False)
            return
        r, c, word, sugs = self._misspelled[self._idx]
        self._word_label.setText(f'"{word}"')
        self._cell_label.setText(f"Cell: {_cell_ref(r, c)}")
        self._sug_combo.clear()
        self._sug_combo.addItems(sugs[:10])
        self._replace_edit.setText(sugs[0] if sugs else word)
        # Navigate to the cell.
        self._sheet.table.setCurrentCell(r, c)

    def _change(self):
        if self._idx >= len(self._misspelled):
            return
        r, c, old_word, _ = self._misspelled[self._idx]
        new_word = self._replace_edit.text()
        if not new_word:
            return
        it = self._sheet.table.item(r, c)
        if it:
            old_text = it.text()
            new_text = old_text.replace(old_word, new_word, 1)
            it.setText(new_text)
            self._sheet._shadow[(r, c)] = new_text
        self._next_word()

    def _ignore_all(self):
        if self._idx >= len(self._misspelled):
            return
        word = self._misspelled[self._idx][2]
        self._ignored.add(word.lower())
        self._next_word()


# ── Sparklines ──────────────────────────────────────────────────────

_PICK_STYLE = "QLineEdit { border: 2px solid #3a78b4; background: #eef4fb; }"
_NORMAL_STYLE = ""


class _SparkPickLineEdit(QLineEdit):
    """QLineEdit that highlights when it is the active cell-pick target."""

    def __init__(self, parent_dlg, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parent_dlg = parent_dlg

    def focusInEvent(self, ev):
        super().focusInEvent(ev)
        self._parent_dlg._set_active_pick(self)


class SparklineDialog(QDialog):
    """Non-modal dialog to configure a sparkline for the current cell.

    Stays above the main window so the user can click cells to pick the
    data range interactively.
    """

    def __init__(self, default_range, sheet, target_row, target_col,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insert Sparkline")
        self.setWindowModality(Qt.NonModal)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.resize(340, 200)

        self._sheet = sheet
        self._target_row = target_row
        self._target_col = target_col
        self._active_edit = None

        layout = QFormLayout(self)

        self.range_edit = _SparkPickLineEdit(self, default_range)
        self.range_edit.setPlaceholderText("e.g. B1:B20 or click cells")
        layout.addRow("Data Range:", self.range_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Line", "Bar", "Win/Loss"])
        layout.addRow("Type:", self.type_combo)

        self.color_edit = QLineEdit("#4472c4")
        layout.addRow("Color:", self.color_edit)

        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        layout.addRow(bb)

        # Connect sheet selection to cell-pick
        self._sheet.table.itemSelectionChanged.connect(
            self._on_sheet_selection)
        self._set_active_pick(self.range_edit)

    @property
    def spark_type(self):
        t = self.type_combo.currentText()
        return {"Line": "line", "Bar": "bar",
                "Win/Loss": "winloss"}.get(t, "line")

    def _set_active_pick(self, edit):
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
        rng = self.range_edit.text().strip()
        parsed = _parse_range(rng)
        if parsed is None:
            QMessageBox.warning(self, "Invalid Range",
                                "Enter a single-column range like B1:B20.")
            return
        src_col, r1, r2 = parsed
        spark = {
            "col": src_col, "r1": r1, "r2": r2,
            "type": self.spark_type,
            "color": self.color_edit.text().strip() or "#4472c4",
        }
        row, col = self._target_row, self._target_col
        self._sheet._fmt_delegate._sparklines[(row, col)] = spark
        if not hasattr(self._sheet, '_cell_sparklines'):
            self._sheet._cell_sparklines = {}
        self._sheet._cell_sparklines[(row, col)] = spark
        idx = self._sheet.table.model().index(row, col)
        self._sheet.table.update(idx)
        self.accept()

    def _disconnect(self):
        try:
            self._sheet.table.itemSelectionChanged.disconnect(
                self._on_sheet_selection)
        except (TypeError, RuntimeError):
            pass

    def closeEvent(self, ev):
        self._disconnect()
        super().closeEvent(ev)

    def reject(self):
        self._disconnect()
        super().reject()


def _selection_ref_str(sheet):
    """Build a ref string from the sheet's current selection."""
    from .sheet import col_index_to_letter
    sel = sheet.table.selectedRanges()
    if not sel:
        r = sheet.table.currentRow()
        c = sheet.table.currentColumn()
        if r >= 0 and c >= 0:
            return f"{col_index_to_letter(c)}{r + 1}"
        return ""
    rng = sel[0]
    tl = f"{col_index_to_letter(rng.leftColumn())}{rng.topRow() + 1}"
    if rng.rowCount() == 1 and rng.columnCount() == 1:
        return tl
    br = f"{col_index_to_letter(rng.rightColumn())}{rng.bottomRow() + 1}"
    return f"{tl}:{br}"


def _parse_range(range_str):
    """Parse 'A1:A20' or '$A$1:$A$20' → (col, r1, r2) or None."""
    # Strip $ signs for absolute ref compatibility
    cleaned = range_str.strip().replace("$", "")
    m = re.match(r'^([A-Za-z]+)(\d+):([A-Za-z]+)(\d+)$', cleaned)
    if not m:
        return None
    c1 = _col_to_idx(m.group(1))
    c2 = _col_to_idx(m.group(3))
    if c1 != c2:
        return None  # sparklines use a single column
    return c1, int(m.group(2)) - 1, int(m.group(4)) - 1


def _col_to_idx(letters):
    """Convert column letters to 0-based index (A=0, Z=25, AA=26)."""
    result = 0
    for ch in letters.upper():
        result = result * 26 + (ord(ch) - ord('A') + 1)
    return result - 1


def insert_sparkline(sheet):
    """Show non-modal dialog to insert a sparkline in the current cell."""
    row = sheet.table.currentRow()
    col = sheet.table.currentColumn()
    if row < 0 or col < 0:
        return

    # Default range: same column, row 1 to current row.
    from .sheet import col_index_to_letter
    letter = col_index_to_letter(col)
    default = f"{letter}1:{letter}{row}" if row > 0 else ""

    dlg = SparklineDialog(default, sheet, row, col, parent=sheet)
    dlg.show()


def remove_sparklines(sheet):
    """Remove sparklines from all selected cells."""
    sel = sheet.table.selectedRanges()
    if not sel:
        row = sheet.table.currentRow()
        col = sheet.table.currentColumn()
        if row < 0 or col < 0:
            return
        cells = [(row, col)]
    else:
        cells = []
        for rng in sel:
            for r in range(rng.topRow(), rng.bottomRow() + 1):
                for c in range(rng.leftColumn(), rng.rightColumn() + 1):
                    cells.append((r, c))

    removed = False
    sparklines = getattr(sheet, '_cell_sparklines', {})
    delegate_sp = sheet._fmt_delegate._sparklines
    for r, c in cells:
        if (r, c) in sparklines:
            del sparklines[(r, c)]
            removed = True
        if (r, c) in delegate_sp:
            del delegate_sp[(r, c)]
            removed = True
        idx = sheet.table.model().index(r, c)
        sheet.table.update(idx)

    if not removed:
        QMessageBox.information(sheet, "Remove Sparkline",
                                "No sparklines in the selected cells.")


# ── Persistence helpers ─────────────────────────────────────────────
def save_insert_data(sheet):
    """Return a JSON-serialisable dict of insert-ops metadata."""
    d = {}
    notes = getattr(sheet, '_cell_notes', {})
    if notes:
        d['notes'] = {f"{r},{c}": v for (r, c), v in notes.items()}
    links = getattr(sheet, '_cell_links', {})
    if links:
        d['links'] = {f"{r},{c}": v for (r, c), v in links.items()}
    dd = getattr(sheet, '_cell_dropdowns', {})
    if dd:
        d['dropdowns'] = {f"{r},{c}": v for (r, c), v in dd.items()}
    sp = getattr(sheet, '_cell_sparklines', {})
    if sp:
        d['sparklines'] = {f"{r},{c}": v for (r, c), v in sp.items()}
    return json.dumps(d) if d else ""


def load_insert_data(sheet, json_str):
    """Restore insert-ops metadata from JSON."""
    if not json_str:
        return
    d = json.loads(json_str)
    if 'notes' in d:
        sheet._cell_notes.clear()
        for k, v in d['notes'].items():
            r, c = map(int, k.split(","))
            # v may be a dict {"text": ..., "kind": ...} or a plain string
            if isinstance(v, str):
                sheet._cell_notes[(r, c)] = {"text": v, "kind": "note"}
            else:
                sheet._cell_notes[(r, c)] = v
    if 'links' in d:
        sheet._cell_links.clear()
        for k, v in d['links'].items():
            r, c = map(int, k.split(","))
            sheet._cell_links[(r, c)] = v
            it = sheet.table.item(r, c)
            if it:
                f = it.font()
                f.setUnderline(True)
                it.setFont(f)
                it.setForeground(QColor("#0563C1"))
    if 'dropdowns' in d:
        sheet._cell_dropdowns.clear()
        for k, v in d['dropdowns'].items():
            r, c = map(int, k.split(","))
            sheet._cell_dropdowns[(r, c)] = v
    if 'sparklines' in d:
        sheet._cell_sparklines.clear()
        sheet._fmt_delegate._sparklines.clear()
        for k, v in d['sparklines'].items():
            r, c = map(int, k.split(","))
            sheet._cell_sparklines[(r, c)] = v
            sheet._fmt_delegate._sparklines[(r, c)] = v
