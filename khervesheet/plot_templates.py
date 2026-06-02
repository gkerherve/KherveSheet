"""Plot template persistence — save / load reusable chart configurations.

Templates capture a chart's visual styling, axis properties, column
mapping, and series layout without the raw data.  They are stored as
JSON files in the user's application-data directory.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import re

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QListWidget, QListWidgetItem,
    QMessageBox, QGroupBox, QSizePolicy,
)


# ── Directory helpers ──────────────────────────────────────────────────

def templates_dir() -> str:
    """Return (and create) the user plot-templates directory."""
    from PyQt5.QtCore import QStandardPaths
    base = QStandardPaths.writableLocation(
        QStandardPaths.AppDataLocation)
    d = os.path.join(base, "KherveSheet", "plot_templates")
    os.makedirs(d, exist_ok=True)
    return d


def _sanitise(name: str) -> str:
    """Turn a template name into a safe file-name stem."""
    return re.sub(r'[^\w\s\-]', '', name).strip().replace(' ', '_') or "template"


# ── I/O ────────────────────────────────────────────────────────────────

def save_template(name: str, tpl: dict) -> str:
    """Write *tpl* to ``<templates_dir>/<name>.json``. Returns path."""
    tpl["template_name"] = name
    path = os.path.join(templates_dir(), _sanitise(name) + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tpl, f, indent=2, ensure_ascii=False)
    return path


def load_template(name: str) -> dict:
    """Read a template by stem name and return the dict."""
    path = os.path.join(templates_dir(), _sanitise(name) + ".json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_templates() -> list:
    """Return ``[(display_name, filename_stem), ...]`` sorted by name."""
    d = templates_dir()
    result = []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        stem = fn[:-5]
        try:
            with open(os.path.join(d, fn), "r", encoding="utf-8") as f:
                data = json.load(f)
            display = data.get("template_name", stem)
        except Exception:
            display = stem
        result.append((display, stem))
    return result


def delete_template(name: str):
    """Remove a template file by stem name."""
    path = os.path.join(templates_dir(), _sanitise(name) + ".json")
    if os.path.isfile(path):
        os.remove(path)


# ── Save dialog ────────────────────────────────────────────────────────

class SaveTemplateDialog(QDialog):
    """Small dialog to name a plot template before saving."""

    def __init__(self, parent=None, default_name=""):
        super().__init__(parent)
        self.setWindowTitle("Save Plot Template")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Template name:"))
        self._name_edit = QLineEdit(default_name)
        layout.addWidget(self._name_edit)

        layout.addWidget(QLabel("Description (optional):"))
        self._desc_edit = QTextEdit()
        self._desc_edit.setMaximumHeight(80)
        layout.addWidget(self._desc_edit)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        self.template_name = ""
        self.description = ""

    def _on_save(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required",
                                "Please enter a template name.")
            return
        # Check for overwrite.
        stem = _sanitise(name)
        path = os.path.join(templates_dir(), stem + ".json")
        if os.path.isfile(path):
            r = QMessageBox.question(
                self, "Overwrite?",
                f"A template named \"{name}\" already exists.\n"
                f"Do you want to replace it?",
                QMessageBox.Yes | QMessageBox.No)
            if r != QMessageBox.Yes:
                return
        self.template_name = name
        self.description = self._desc_edit.toPlainText().strip()
        self.accept()


# ── Load / manage dialog ──────────────────────────────────────────────

class LoadTemplateDialog(QDialog):
    """Lists saved templates with a preview pane; returns the chosen one."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Plot Templates")
        self.setMinimumSize(520, 400)

        layout = QHBoxLayout(self)

        # Left: template list.
        left = QVBoxLayout()
        left.addWidget(QLabel("Saved templates:"))
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_select)
        self._list.itemDoubleClicked.connect(self._on_load)
        left.addWidget(self._list)
        layout.addLayout(left, stretch=1)

        # Right: preview + buttons.
        right = QVBoxLayout()
        self._preview = QGroupBox("Details")
        pv = QVBoxLayout(self._preview)
        self._info_label = QLabel("Select a template to see details.")
        self._info_label.setWordWrap(True)
        self._info_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._info_label.setSizePolicy(QSizePolicy.Preferred,
                                       QSizePolicy.Expanding)
        pv.addWidget(self._info_label)
        right.addWidget(self._preview, stretch=1)

        btn_col = QHBoxLayout()
        self._load_btn = QPushButton("Load")
        self._load_btn.setDefault(True)
        self._load_btn.setEnabled(False)
        self._load_btn.clicked.connect(self._on_load)
        self._del_btn = QPushButton("Delete")
        self._del_btn.setEnabled(False)
        self._del_btn.clicked.connect(self._on_delete)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_col.addWidget(self._load_btn)
        btn_col.addWidget(self._del_btn)
        btn_col.addStretch()
        btn_col.addWidget(cancel_btn)
        right.addLayout(btn_col)
        layout.addLayout(right, stretch=1)

        self.selected_template = None  # dict on accept
        self._templates = {}  # stem -> dict (lazy loaded)
        self._refresh()

    def _refresh(self):
        self._list.clear()
        self._templates.clear()
        for display, stem in list_templates():
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, stem)
            self._list.addItem(item)

    def _on_select(self, current, _previous=None):
        enabled = current is not None
        self._load_btn.setEnabled(enabled)
        self._del_btn.setEnabled(enabled)
        if not current:
            self._info_label.setText("Select a template to see details.")
            return
        stem = current.data(Qt.UserRole)
        tpl = self._load_cached(stem)
        if tpl is None:
            self._info_label.setText("Error reading template.")
            return
        self._info_label.setText(self._format_preview(tpl))

    def _load_cached(self, stem: str):
        if stem in self._templates:
            return self._templates[stem]
        try:
            path = os.path.join(templates_dir(), stem + ".json")
            with open(path, "r", encoding="utf-8") as f:
                tpl = json.load(f)
            self._templates[stem] = tpl
            return tpl
        except Exception:
            return None

    @staticmethod
    def _col_letter(idx):
        """Convert 0-based column index to Excel-style letter(s)."""
        if idx is None:
            return "?"
        s = ""
        n = idx
        while True:
            s = chr(65 + n % 26) + s
            n = n // 26 - 1
            if n < 0:
                break
        return s

    def _format_preview(self, tpl: dict) -> str:
        lines = []
        desc = tpl.get("description", "")
        if desc:
            lines.append(f"<i>{desc}</i>")
            lines.append("")

        series = tpl.get("series", [])
        lines.append(f"<b>Series:</b> {len(series)}")
        for i, s in enumerate(series):
            pt = s.get("plot_type", "?")
            label = s.get("label", f"Series {i+1}")
            x_col = self._col_letter(s.get("x_col", tpl.get("x_col")))
            y_col = self._col_letter(s.get("y_col"))
            lines.append(f"  {i+1}. {label} ({pt}) — X={x_col}, Y={y_col}")

        if tpl.get("title"):
            lines.append(f"<b>Title:</b> {tpl['title']}")
        if tpl.get("xlabel"):
            lines.append(f"<b>X label:</b> {tpl['xlabel']}")
        if tpl.get("ylabel"):
            lines.append(f"<b>Y label:</b> {tpl['ylabel']}")

        w = tpl.get("width", "?")
        h = tpl.get("height", "?")
        lines.append(f"<b>Size:</b> {w} x {h}")

        tl = tpl.get("trendlines", [])
        if tl:
            models = [t.get("model_name", "?") for t in tl]
            lines.append(f"<b>Trendlines:</b> {', '.join(models)}")

        return "<br>".join(lines)

    def _on_load(self, _=None):
        item = self._list.currentItem()
        if not item:
            return
        stem = item.data(Qt.UserRole)
        tpl = self._load_cached(stem)
        if tpl is None:
            QMessageBox.warning(self, "Error", "Could not read template.")
            return
        self.selected_template = tpl
        self.accept()

    def _on_delete(self):
        item = self._list.currentItem()
        if not item:
            return
        name = item.text()
        stem = item.data(Qt.UserRole)
        r = QMessageBox.question(
            self, "Delete template?",
            f"Permanently delete \"{name}\"?",
            QMessageBox.Yes | QMessageBox.No)
        if r != QMessageBox.Yes:
            return
        try:
            path = os.path.join(templates_dir(), stem + ".json")
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass
        self._templates.pop(stem, None)
        self._refresh()
