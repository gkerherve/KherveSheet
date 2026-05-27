"""Text Import Wizard — configurable delimiter-based file import.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import csv
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QComboBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QPushButton, QDialogButtonBox, QHeaderView, QCheckBox,
    QLineEdit, QGroupBox, QSizePolicy, QApplication,
)


# Common encodings users might need
_ENCODINGS = [
    ("UTF-8", "utf-8"),
    ("UTF-8 with BOM", "utf-8-sig"),
    ("Latin-1 (ISO 8859-1)", "latin-1"),
    ("1252: Western European (Windows)", "cp1252"),
    ("1250: Central European (Windows)", "cp1250"),
    ("1251: Cyrillic (Windows)", "cp1251"),
    ("1253: Greek (Windows)", "cp1253"),
    ("1254: Turkish (Windows)", "cp1254"),
    ("1256: Arabic (Windows)", "cp1256"),
    ("Shift-JIS (Japanese)", "shift_jis"),
    ("GB2312 (Chinese Simplified)", "gb2312"),
    ("EUC-KR (Korean)", "euc_kr"),
    ("ASCII", "ascii"),
]

# Delimiter presets
_DELIMITERS = [
    ("Comma", ","),
    ("Tab", "\t"),
    ("Semicolon", ";"),
    ("Space", " "),
    ("Pipe", "|"),
    ("Custom…", None),
]

_DATA_TYPE_OPTIONS = [
    "Automatic",
    "All as text",
]

# Max rows shown in preview
_PREVIEW_ROWS = 100


class TextImportDialog(QDialog):
    """Excel-style text import wizard with delimiter/encoding/skip options."""

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path
        self._raw_lines: list[str] = []
        self._parsed_rows: list[list[str]] = []

        self.setWindowTitle("Import Text File")
        self.resize(900, 620)
        self.setMinimumSize(640, 400)

        self._build_ui()
        self._read_raw()
        self._refresh_preview()

    # ── result accessors ────────────────────────────────────────────
    def parsed_rows(self) -> list[list[str]]:
        """Return parsed rows after dialog accepted."""
        return self._parsed_rows

    def start_row(self) -> int:
        return self._start_spin.value()

    def treat_as_text(self) -> bool:
        return self._dtype_combo.currentText() == "All as text"

    def first_row_header(self) -> bool:
        return self._header_chk.isChecked()

    # ── UI construction ─────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)

        # ── File name label ─────────────────────────────────────────
        name_lbl = QLabel(os.path.basename(self._path))
        name_lbl.setStyleSheet("font-size: 14px; font-weight: bold; "
                               "color: #217346;")
        root.addWidget(name_lbl)
        root.addSpacing(6)

        # ── Options row ─────────────────────────────────────────────
        opts = QGridLayout()
        opts.setHorizontalSpacing(18)

        # Encoding
        opts.addWidget(QLabel("File Origin"), 0, 0)
        self._enc_combo = QComboBox()
        for label, _ in _ENCODINGS:
            self._enc_combo.addItem(label)
        self._enc_combo.setCurrentIndex(0)
        self._enc_combo.currentIndexChanged.connect(self._on_settings_changed)
        opts.addWidget(self._enc_combo, 1, 0)

        # Delimiter
        opts.addWidget(QLabel("Delimiter"), 0, 1)
        delim_box = QHBoxLayout()
        self._delim_combo = QComboBox()
        for label, _ in _DELIMITERS:
            self._delim_combo.addItem(label)
        self._delim_combo.currentIndexChanged.connect(
            self._on_delimiter_changed)
        delim_box.addWidget(self._delim_combo)

        self._custom_delim = QLineEdit()
        self._custom_delim.setMaximumWidth(40)
        self._custom_delim.setPlaceholderText(",")
        self._custom_delim.setVisible(False)
        self._custom_delim.textChanged.connect(self._on_settings_changed)
        delim_box.addWidget(self._custom_delim)
        opts.addLayout(delim_box, 1, 1)

        # Data type detection
        opts.addWidget(QLabel("Data Type Detection"), 0, 2)
        self._dtype_combo = QComboBox()
        for t in _DATA_TYPE_OPTIONS:
            self._dtype_combo.addItem(t)
        opts.addWidget(self._dtype_combo, 1, 2)

        root.addLayout(opts)
        root.addSpacing(4)

        # ── Second options row ──────────────────────────────────────
        row2 = QHBoxLayout()

        row2.addWidget(QLabel("Start import at row:"))
        self._start_spin = QSpinBox()
        self._start_spin.setMinimum(1)
        self._start_spin.setMaximum(999999)
        self._start_spin.setValue(1)
        self._start_spin.valueChanged.connect(self._on_settings_changed)
        row2.addWidget(self._start_spin)

        row2.addSpacing(24)
        self._header_chk = QCheckBox("First row is header")
        self._header_chk.setChecked(True)
        self._header_chk.stateChanged.connect(self._refresh_preview)
        row2.addWidget(self._header_chk)

        row2.addStretch()

        self._row_count_lbl = QLabel()
        row2.addWidget(self._row_count_lbl)

        root.addLayout(row2)
        root.addSpacing(4)

        # ── Preview table ───────────────────────────────────────────
        self._preview = QTableWidget()
        self._preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self._preview.setSelectionMode(QTableWidget.NoSelection)
        self._preview.horizontalHeader().setDefaultSectionSize(110)
        self._preview.horizontalHeader().setStretchLastSection(True)
        self._preview.verticalHeader().setDefaultSectionSize(22)
        self._preview.setAlternatingRowColors(True)
        root.addWidget(self._preview, 1)

        # ── Buttons ─────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        load_btn = QPushButton("Load")
        load_btn.setDefault(True)
        load_btn.clicked.connect(self._on_load)
        btn_row.addWidget(load_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        root.addLayout(btn_row)

    # ── data reading ────────────────────────────────────────────────
    def _read_raw(self):
        """Read the file with the selected encoding."""
        enc = _ENCODINGS[self._enc_combo.currentIndex()][1]
        try:
            with open(self._path, newline='', encoding=enc,
                      errors='replace') as f:
                self._raw_lines = f.readlines()
        except Exception:
            self._raw_lines = []

    def _current_delimiter(self) -> str:
        idx = self._delim_combo.currentIndex()
        if _DELIMITERS[idx][1] is None:
            return self._custom_delim.text() or ","
        return _DELIMITERS[idx][1]

    def _auto_detect_delimiter(self) -> int:
        """Try to guess the best delimiter from the first few lines.
        Returns the index into _DELIMITERS."""
        if not self._raw_lines:
            return 0  # default to comma

        # Sample first 20 non-empty lines
        sample = []
        for line in self._raw_lines[:20]:
            stripped = line.strip()
            if stripped:
                sample.append(stripped)
        if not sample:
            return 0

        # Count occurrences of each candidate delimiter
        best_idx = 0
        best_score = 0
        for i, (_, delim) in enumerate(_DELIMITERS):
            if delim is None:
                continue
            # Score = min count across sample lines (consistent delimiter
            # appears on every line)
            counts = [line.count(delim) for line in sample]
            if all(c > 0 for c in counts):
                score = min(counts)
                if score > best_score:
                    best_score = score
                    best_idx = i

        return best_idx

    # ── parsing + preview ───────────────────────────────────────────
    def _parse_rows(self) -> list[list[str]]:
        delim = self._current_delimiter()
        start = self._start_spin.value() - 1  # 0-based
        lines = self._raw_lines[start:]
        if not lines:
            return []

        text = ''.join(lines)
        try:
            reader = csv.reader(text.splitlines(), delimiter=delim)
            return list(reader)
        except Exception:
            # Fallback: simple split
            return [line.rstrip('\n\r').split(delim) for line in lines]

    def _refresh_preview(self, *_args):
        rows = self._parse_rows()
        self._parsed_rows = rows

        if not rows:
            self._preview.setRowCount(0)
            self._preview.setColumnCount(0)
            self._row_count_lbl.setText("0 rows")
            return

        n_cols = max(len(r) for r in rows)
        header_row = None
        data_start = 0

        if self._header_chk.isChecked() and len(rows) > 0:
            header_row = rows[0]
            data_start = 1

        data_rows = rows[data_start:]
        show_rows = data_rows[:_PREVIEW_ROWS]

        self._preview.setColumnCount(n_cols)
        self._preview.setRowCount(len(show_rows))

        # Column headers
        if header_row:
            headers = list(header_row)
            while len(headers) < n_cols:
                headers.append(f"Column {len(headers) + 1}")
            self._preview.setHorizontalHeaderLabels(headers)
        else:
            self._preview.setHorizontalHeaderLabels(
                [f"Column {i + 1}" for i in range(n_cols)])

        # Row numbers (1-based, offset by start row + header)
        base = self._start_spin.value() + data_start
        self._preview.setVerticalHeaderLabels(
            [str(base + i) for i in range(len(show_rows))])

        # Fill cells
        for i, row in enumerate(show_rows):
            for j, val in enumerate(row):
                item = QTableWidgetItem(val)
                self._preview.setItem(i, j, item)

        total = len(data_rows)
        suffix = f" (showing first {_PREVIEW_ROWS})" if total > _PREVIEW_ROWS else ""
        self._row_count_lbl.setText(f"{total} data rows{suffix}")

    # ── slots ───────────────────────────────────────────────────────
    def _on_delimiter_changed(self, idx):
        is_custom = (_DELIMITERS[idx][1] is None)
        self._custom_delim.setVisible(is_custom)
        if not is_custom:
            self._refresh_preview()

    def _on_settings_changed(self, *_args):
        # Re-read if encoding changed
        self._read_raw()
        self._refresh_preview()

    def _on_load(self):
        # Final parse with current settings
        self._parsed_rows = self._parse_rows()
        self.accept()

    # ── public convenience ──────────────────────────────────────────
    @staticmethod
    def get_import_data(path: str, parent=None):
        """Show dialog, return (rows, first_row_is_header, as_text, accepted).

        rows includes the header row if first_row_is_header is True.
        """
        dlg = TextImportDialog(path, parent)

        # Auto-detect delimiter before showing
        dlg._read_raw()
        best = dlg._auto_detect_delimiter()
        dlg._delim_combo.setCurrentIndex(best)
        # _on_delimiter_changed already triggers preview refresh

        ok = dlg.exec_() == QDialog.Accepted
        return (dlg.parsed_rows(), dlg.first_row_header(),
                dlg.treat_as_text(), ok)
