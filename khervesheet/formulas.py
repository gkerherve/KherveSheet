"""Formulas menu — function library catalog and menu builder.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMenu, QAction, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QListWidget, QListWidgetItem,
    QDialogButtonBox, QSplitter, QWidget,
)

# The catalogue itself lives in core.catalog (no Qt), shared with the
# formula engine; the menu and dialog below are built from it.
from .core.catalog import (  # noqa: E402,F401
    CATEGORY_ORDER, FUNCTION_CATEGORIES, FUNCTION_HELP,
)


def build_formulas_menu(menu_bar, insert_callback):
    """Build the Formulas top-level menu on *menu_bar*.

    *insert_callback* is called with the function name (str) when a
    user selects a function from the library.  It should insert
    ``=FUNC()`` into the formula bar.
    """
    formulas_menu = menu_bar.addMenu("F&ormulas")

    # AutoSum shortcut
    formulas_menu.addAction(
        "AutoSum", lambda: insert_callback("SUM"), "Alt+Shift+=")
    formulas_menu.addSeparator()

    # Category submenus directly under Formulas
    for cat in CATEGORY_ORDER:
        funcs = FUNCTION_CATEGORIES.get(cat, [])
        sub = formulas_menu.addMenu(cat)
        sub.setToolTipsVisible(True)
        for fn in funcs:
            act = sub.addAction(fn)
            tip = FUNCTION_HELP.get(fn, "")
            if tip:
                act.setToolTip(tip)
                act.setStatusTip(tip.split("\n")[-1])
            act.triggered.connect(
                lambda _, f=fn: insert_callback(f))

    return formulas_menu


# ── Insert Function dialog ────────────────────────────────────────────

# Build a flat list of all functions for search.
_ALL_FUNCTIONS = sorted(
    {fn for funcs in FUNCTION_CATEGORIES.values() for fn in funcs})

# Map function → category for reverse lookup.
_FUNC_TO_CATEGORY: dict = {}
for _cat, _fns in FUNCTION_CATEGORIES.items():
    for _fn in _fns:
        _FUNC_TO_CATEGORY[_fn] = _cat


class InsertFunctionDialog(QDialog):
    """Excel-style Insert Function dialog with search, category filter,
    function list, and signature/description preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insert Function")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowContextHelpButtonHint)
        self.resize(480, 420)
        self._selected_function = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Search row ───────────────────────────────────────────────
        layout.addWidget(QLabel("Search for a function:"))
        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(
            "Type a brief description of what you want to do "
            "and then click Go")
        self._search_edit.returnPressed.connect(self._do_search)
        search_row.addWidget(self._search_edit, stretch=1)
        go_btn = QPushButton("Go")
        go_btn.clicked.connect(self._do_search)
        search_row.addWidget(go_btn)
        layout.addLayout(search_row)

        # ── Category combo ───────────────────────────────────────────
        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("Or select a category:"))
        self._cat_combo = QComboBox()
        self._cat_combo.addItem("All")
        self._cat_combo.addItem("Most Recently Used")
        for cat in CATEGORY_ORDER:
            self._cat_combo.addItem(cat)
        self._cat_combo.currentTextChanged.connect(self._filter_by_cat)
        cat_row.addWidget(self._cat_combo, stretch=1)
        layout.addLayout(cat_row)

        # ── Function list ────────────────────────────────────────────
        layout.addWidget(QLabel("Select a function:"))
        self._func_list = QListWidget()
        self._func_list.currentItemChanged.connect(
            self._on_selection_changed)
        self._func_list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._func_list, stretch=1)

        # ── Signature + description preview ──────────────────────────
        self._sig_label = QLabel("")
        self._sig_label.setStyleSheet("font-weight: bold;")
        self._sig_label.setWordWrap(True)
        layout.addWidget(self._sig_label)

        self._desc_label = QLabel("")
        self._desc_label.setWordWrap(True)
        self._desc_label.setMinimumHeight(36)
        layout.addWidget(self._desc_label)

        # ── Buttons ──────────────────────────────────────────────────
        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

        # Recently used functions (persisted per session).
        self._recent: list = []

        # Initial population — show "All".
        self._populate(_ALL_FUNCTIONS)
        if self._func_list.count():
            self._func_list.setCurrentRow(0)

    # ── Population helpers ────────────────────────────────────────────

    def _populate(self, func_names: list):
        """Fill the list widget with *func_names*."""
        self._func_list.clear()
        for fn in func_names:
            self._func_list.addItem(fn)
        if self._func_list.count():
            self._func_list.setCurrentRow(0)
        else:
            self._sig_label.setText("")
            self._desc_label.setText("")

    def _filter_by_cat(self, cat_text: str):
        """Repopulate the list when the category changes."""
        if cat_text == "All":
            self._populate(_ALL_FUNCTIONS)
        elif cat_text == "Most Recently Used":
            self._populate(self._recent if self._recent
                           else _ALL_FUNCTIONS[:15])
        else:
            funcs = FUNCTION_CATEGORIES.get(cat_text, [])
            self._populate(funcs)

    def _do_search(self):
        """Search functions by keyword in name or description."""
        query = self._search_edit.text().strip().upper()
        if not query:
            self._populate(_ALL_FUNCTIONS)
            return
        matches = []
        for fn in _ALL_FUNCTIONS:
            if query in fn:
                matches.append(fn)
                continue
            hlp = FUNCTION_HELP.get(fn, "")
            if query.lower() in hlp.lower():
                matches.append(fn)
        self._populate(matches if matches else _ALL_FUNCTIONS)
        # Switch combo to "All" so the user sees the search result.
        self._cat_combo.blockSignals(True)
        self._cat_combo.setCurrentText("All")
        self._cat_combo.blockSignals(False)

    # ── Selection ─────────────────────────────────────────────────────

    def _on_selection_changed(self, current, _prev):
        if not current:
            self._sig_label.setText("")
            self._desc_label.setText("")
            return
        fn = current.text()
        hlp = FUNCTION_HELP.get(fn, f"{fn}()")
        parts = hlp.split("\n", 1)
        self._sig_label.setText(parts[0])
        self._desc_label.setText(parts[1] if len(parts) > 1 else "")

    def _on_double_click(self, item):
        self._accept()

    def _accept(self):
        item = self._func_list.currentItem()
        if item:
            self._selected_function = item.text()
            # Track recently used.
            if self._selected_function in self._recent:
                self._recent.remove(self._selected_function)
            self._recent.insert(0, self._selected_function)
            self._recent = self._recent[:15]
            self.accept()

    @property
    def selected_function(self) -> str | None:
        return self._selected_function
