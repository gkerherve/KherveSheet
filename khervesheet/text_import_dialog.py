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


# Full encoding list matching Excel's File Origin dropdown.
# Format: (display_label, python_codec).  Sorted alphabetically by
# language/region, with Unicode variants at the end.
_ENCODINGS = [
    ("--None--", None),
    # ── Arabic ──────────────────────────────────────────────────────
    ("864: Arabic (864)", "cp864"),
    ("708: Arabic (ASMO 708)", "iso8859_6"),
    ("720: Arabic (DOS)", "cp720"),
    ("28596: Arabic (ISO)", "iso8859_6"),
    ("10004: Arabic (Mac)", "mac_arabic"),
    ("1256: Arabic (Windows)", "cp1256"),
    # ── Baltic ──────────────────────────────────────────────────────
    ("775: Baltic (DOS)", "cp775"),
    ("28594: Baltic (ISO)", "iso8859_4"),
    ("1257: Baltic (Windows)", "cp1257"),
    # ── Central European ────────────────────────────────────────────
    ("852: Central European (DOS)", "cp852"),
    ("28592: Central European (ISO)", "iso8859_2"),
    ("10029: Central European (Mac)", "mac_latin2"),
    ("1250: Central European (Windows)", "cp1250"),
    # ── Chinese Simplified ──────────────────────────────────────────
    ("51936: Chinese Simplified (EUC)", "euc_jp"),      # placeholder
    ("54936: Chinese Simplified (GB18030)", "gb18030"),
    ("936: Chinese Simplified (GB2312)", "gb2312"),
    ("20936: Chinese Simplified (GB2312-80)", "gb2312"),
    ("52936: Chinese Simplified (HZ)", "hz"),
    ("50227: Chinese Simplified (ISO-2022)", "iso2022_jp"),
    # ── Chinese Traditional ─────────────────────────────────────────
    ("950: Chinese Traditional (Big5)", "big5"),
    ("51950: Chinese Traditional (EUC)", "euc_jp"),     # placeholder
    # ── Cyrillic ────────────────────────────────────────────────────
    ("855: OEM Cyrillic", "cp855"),
    ("866: Cyrillic (DOS)", "cp866"),
    ("28595: Cyrillic (ISO)", "iso8859_5"),
    ("20866: Cyrillic (KOI8-R)", "koi8_r"),
    ("21866: Cyrillic (KOI8-U)", "koi8_u"),
    ("10007: Cyrillic (Mac)", "mac_cyrillic"),
    ("1251: Cyrillic (Windows)", "cp1251"),
    # ── Greek ───────────────────────────────────────────────────────
    ("737: Greek (DOS)", "cp737"),
    ("28597: Greek (ISO)", "iso8859_7"),
    ("10006: Greek (Mac)", "mac_greek"),
    ("1253: Greek (Windows)", "cp1253"),
    # ── Hebrew ──────────────────────────────────────────────────────
    ("862: Hebrew (DOS)", "cp862"),
    ("28598: Hebrew (ISO-Logical)", "iso8859_8"),
    ("38598: Hebrew (ISO-Visual)", "iso8859_8"),
    ("10005: Hebrew (Mac)", "mac_arabic"),              # closest
    ("1255: Hebrew (Windows)", "cp1255"),
    # ── Japanese ────────────────────────────────────────────────────
    ("51932: Japanese (EUC)", "euc_jp"),
    ("20932: Japanese (JIS 0208-1990 and 0212-1990)", "euc_jp"),
    ("50220: Japanese (JIS)", "iso2022_jp"),
    ("50222: Japanese (JIS-Allow 1 byte Kana - SO/SI)", "iso2022_jp"),
    ("50221: Japanese (JIS-Allow 1 byte Kana)", "iso2022_jp"),
    ("10001: Japanese (Mac)", "shift_jis"),
    ("932: Japanese (Shift-JIS)", "shift_jis"),
    # ── Korean ──────────────────────────────────────────────────────
    ("949: Korean", "euc_kr"),
    ("51949: Korean (EUC)", "euc_kr"),
    ("50225: Korean (ISO)", "iso2022_kr"),
    ("1361: Korean (Johab)", "johab"),
    ("10003: Korean (Mac)", "euc_kr"),
    ("20949: Korean Wansung", "euc_kr"),
    # ── Latin ───────────────────────────────────────────────────────
    ("28593: Latin 3 (ISO)", "iso8859_3"),
    ("28605: Latin 9 (ISO)", "iso8859_15"),
    # ── Nordic / Icelandic ──────────────────────────────────────────
    ("865: Nordic (DOS)", "cp865"),
    ("861: Icelandic (DOS)", "cp861"),
    ("10079: Icelandic (Mac)", "mac_iceland"),
    # ── Norwegian ───────────────────────────────────────────────────
    ("20108: Norwegian (IA5)", "ascii"),
    # ── ISO / Misc ──────────────────────────────────────────────────
    ("20269: ISO-6937", "ascii"),                       # no direct codec
    # ── ISCII (India) ───────────────────────────────────────────────
    ("57002: ISCII Devanagari", "utf-8"),               # fallback
    ("57003: ISCII Bengali", "utf-8"),
    ("57004: ISCII Tamil", "utf-8"),
    ("57005: ISCII Telugu", "utf-8"),
    ("57010: ISCII Punjabi", "utf-8"),
    # ── Thai ────────────────────────────────────────────────────────
    ("874: Thai (Windows)", "cp874"),
    # ── Turkish ─────────────────────────────────────────────────────
    ("857: Turkish (DOS)", "cp857"),
    ("28599: Turkish (ISO)", "iso8859_9"),
    ("10081: Turkish (Mac)", "mac_turkish"),
    ("1254: Turkish (Windows)", "cp1254"),
    # ── Ukrainian ───────────────────────────────────────────────────
    ("10017: Ukrainian (Mac)", "mac_cyrillic"),
    # ── Vietnamese ──────────────────────────────────────────────────
    ("1258: Vietnamese (Windows)", "cp1258"),
    # ── Western European ────────────────────────────────────────────
    ("850: Western European (DOS)", "cp850"),
    ("20105: Western European (IA5)", "ascii"),
    ("28591: Western European (ISO)", "iso8859_1"),
    ("10000: Western European (Mac)", "mac_roman"),
    ("1252: Western European (Windows)", "cp1252"),
    # ── Unicode ─────────────────────────────────────────────────────
    ("1200: Unicode", "utf-16-le"),
    ("1201: Unicode (Big-Endian)", "utf-16-be"),
    ("12001: Unicode (UTF-32 Big-Endian)", "utf-32-be"),
    ("12000: Unicode (UTF-32)", "utf-32-le"),
    ("65000: Unicode (UTF-7)", "utf-7"),
    ("65001: Unicode (UTF-8)", "utf-8"),
    # ── US-ASCII ────────────────────────────────────────────────────
    ("20127: US-ASCII", "ascii"),
    # ── Wang Taiwan ─────────────────────────────────────────────────
    ("20005: Wang Taiwan", "big5"),                     # closest
]

# Index of the default encoding (UTF-8) in the list above
_DEFAULT_ENC_IDX = next(
    i for i, (lbl, _) in enumerate(_ENCODINGS) if lbl == "65001: Unicode (UTF-8)"
)

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
    "Based on first 200 rows",
    "Based on entire dataset",
    "Do not detect data types",
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
        return self._dtype_combo.currentText() == "Do not detect data types"

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
        self._enc_combo.setCurrentIndex(_DEFAULT_ENC_IDX)
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
        if enc is None:
            # "--None--" means try utf-8-sig first, fall back to latin-1
            for try_enc in ("utf-8-sig", "latin-1"):
                try:
                    with open(self._path, newline='',
                              encoding=try_enc) as f:
                        self._raw_lines = f.readlines()
                    return
                except (UnicodeDecodeError, Exception):
                    continue
            self._raw_lines = []
            return
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
