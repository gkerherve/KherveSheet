"""Fill the Excel-style ribbon from MainWindow's menus and toolbars.

Commands are the window's own menu actions (found by menu path), so
checkable state — Gridlines, Normal / Page Layout, Wrap Text — stays
shared between the menus and the ribbon. Widgets that only lived on the
classic toolbars (font combo, colour buttons, chart button) get ribbon
twins that take over the window's attribute names.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""
from __future__ import annotations

import sys

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAction, QComboBox, QFontComboBox, QMenu, QToolBar, QToolButton,
)

from . import icons
from .ribbon import Ribbon, accent_color, short

ACCENT = object()      # "colour this icon with the theme accent"
_accented: list = []   # (action, mdi name) recoloured on theme change

_ICO = 32


def _ic(name: str, color=""):
    if color is ACCENT:
        icon = icons.themed_icon(name, color=accent_color())
        icon._accent_name = name
        return icon
    return icons.themed_icon(name, color=color)


def retheme(rb: Ribbon) -> None:
    """Follow a theme change: ribbon colours and accent icons."""
    accent = accent_color()
    rb.apply_accent(accent)
    for act, name in _accented:
        act.setIcon(icons.themed_icon(name, color=accent))
    # A new theme changes button padding; size the buttons again so the
    # labels are not elided ("For…as Table").
    from PyQt5.QtCore import QTimer

    def refit():
        for btn in rb.findChildren(QToolButton):
            btn.ensurePolished()
            btn.setMinimumWidth(0)
            btn.setMinimumWidth(btn.sizeHint().width())
    QTimer.singleShot(0, refit)


class _Builder:
    def __init__(self, win):
        self.w = win
        self._menus = {short(a.text()): a.menu()
                       for a in win.menuBar().actions() if a.menu()}

    # ── lookup ──────────────────────────────────────────────────────
    def menu(self, *path: str) -> QMenu | None:
        m = self._menus.get(path[0])
        for name in path[1:]:
            if m is None:
                return None
            m = next((a.menu() for a in m.actions()
                      if a.menu() and short(a.text()) == name), None)
        return m

    def find(self, *path: str, icon=None, text: str | None = None):
        """The existing menu action at path, given a ribbon icon."""
        m = self.menu(*path[:-1])
        if m is None:
            return None
        for a in m.actions():
            if short(a.text()) == path[-1]:
                if icon is not None:
                    a.setIcon(icon)
                if text:
                    a.setIconText(text)
                return a
        return None

    def act(self, text: str, icon, slot=None, *, menu: QMenu | None = None,
            menu_only: bool = False, checkable: bool = False,
            tip: str = "") -> QAction:
        a = QAction(icon, text, self.w)
        if getattr(icon, "_accent_name", None):
            _accented.append((a, icon._accent_name))
        if slot is not None:
            a.triggered.connect(lambda _=False, s=slot: s())
        a.setCheckable(checkable)
        if tip:
            a.setToolTip(tip)
        if menu is not None:
            a.setProperty("ribbon_menu", menu)
            a.setProperty("ribbon_menu_only", menu_only)
        return a

    def menu_act(self, text: str, icon, menu: QMenu | None) -> QAction:
        """A button that only opens a menu (Excel's Sort & Filter ▾)."""
        if menu is None:
            menu = QMenu(self.w)
        return self.act(text, icon, menu=menu, menu_only=True)


def build_ribbon(win) -> Ribbon:
    """Build the ribbon, hide the classic toolbars, return the ribbon."""
    b = _Builder(win)
    rb = Ribbon()
    w = win

    # File button → the File menu; Excel has no menu bar, so on Windows
    # and Linux the bar goes (macOS keeps its global one).
    rb.set_file_menu(b.menu("File"))

    undo = b.find("Edit", "Undo", icon=icons.undo_icon(_ICO))
    redo = b.find("Edit", "Redo", icon=icons.redo_icon(_ICO))
    save = b.find("File", "Save", icon=icons.save_file_icon(_ICO))
    collapse = b.act("Collapse the Ribbon", _ic("mdi.chevron-up"),
                     lambda: rb.set_collapsed(not rb.is_collapsed()),
                     tip="Collapse the Ribbon (double-click a tab)")
    rb.collapsedChanged.connect(lambda c: collapse.setIcon(
        _ic("mdi.chevron-down" if c else "mdi.chevron-up")))
    rb.set_quick_access([a for a in (save, undo, redo) if a] +
                        [None, w._ai_chat_act, collapse])

    fmt_cells = w._open_format_cells_dialog

    # ── Home ────────────────────────────────────────────────────────
    home = rb.add_tab("Home")
    paste_menu = QMenu(w)
    paste_menu.addAction(_ic("mdi.content-paste"), "Paste", w._paste)
    paste_menu.addAction(_ic("mdi.numeric"), "Paste Values Only",
                         w._paste_values)
    paste_menu.addAction(_ic("mdi.swap-horizontal"), "Transpose",
                         w._transpose_selection)
    paste = b.act("Paste", _ic("mdi.content-paste", ACCENT), w._paste,
                  menu=paste_menu, tip="Paste (Ctrl+V)")
    home.add_group("Clipboard", large=[paste], rows=[
        [b.act("Cut", _ic("mdi.content-cut"), w._cut, tip="Cut (Ctrl+X)")],
        [b.act("Copy", _ic("mdi.content-copy"), w._copy,
               tip="Copy (Ctrl+C)")],
        [b.act("Paste Values", _ic("mdi.numeric"), w._paste_values,
               tip="Paste Values Only (Ctrl+Shift+V)")]])

    font_combo = QFontComboBox()
    font_combo.setCurrentFont(w._font_combo.currentFont())
    font_combo.setFixedWidth(150)
    font_combo.currentFontChanged.connect(w._apply_font_family)
    size_combo = QComboBox()
    size_combo.setEditable(True)
    size_combo.setFixedWidth(52)
    for i in range(w._font_size.count()):
        size_combo.addItem(w._font_size.itemText(i))
    size_combo.setCurrentText(w._font_size.currentText())
    size_combo.currentTextChanged.connect(w._apply_font_size)
    for cb in (font_combo, size_combo):
        cb.setFocusPolicy(Qt.ClickFocus)
    w._font_combo, w._font_size = font_combo, size_combo
    font_combo.setProperty("tip_key", "font")
    size_combo.setProperty("tip_key", "size")

    def twin(old: QToolButton, label: str) -> QToolButton:
        """A small ribbon copy of a classic-toolbar menu button."""
        t = QToolButton()
        t.setIcon(old.icon())
        t.setToolTip(old.toolTip())
        t.setMenu(old.menu())
        t.setPopupMode(old.popupMode())
        t.setAutoRaise(True)
        t.setFocusPolicy(Qt.NoFocus)
        t.setIconSize(QSize(16, 16))
        for slot in (getattr(w, label, None),):
            if slot is not None:
                t.clicked.connect(slot)
        return t

    borders = twin(w._border_btn, "")
    fill = twin(w._fill_btn, "_apply_last_fill_color")
    fcolor = twin(w._font_color_btn, "_apply_last_font_color")
    # The colour handlers repaint these by name with the window's size.
    w._fill_btn, w._font_color_btn = fill, fcolor
    for t, key in ((borders, "borders"), (fill, "fill"), (fcolor, "fcolor")):
        t.setProperty("tip_key", key)
    w._ico = 16
    home.add_group("Font", rows=[
        [font_combo, size_combo],
        [w._bold_act, w._italic_act, w._underline_act, borders, fill,
         fcolor]], text=False, launcher=fmt_cells)

    wrap = b.find("Format", "Wrap Text")
    merge = b.act("Merge & Center", icons.merge_cells_icon(_ICO),
                  w._toggle_merge, menu=_merge_menu(w))
    home.add_group("Alignment", rows=[
        [w._align_left_act, w._align_center_act, w._align_right_act],
        [(wrap, "Wrap Text")] if wrap else [],
        [merge]], launcher=fmt_cells)

    from .sheet import NUMBER_FORMATS
    num = QComboBox()
    num.addItems(NUMBER_FORMATS)
    num.setFixedWidth(118)
    num.setFocusPolicy(Qt.NoFocus)
    num.textActivated.connect(w._set_number_format)
    num.setProperty("tip_key", "number")
    pct = next((f for f in NUMBER_FORMATS if "%" in f), None)
    sci = next((f for f in NUMBER_FORMATS if "Sci" in f or "E+" in f), None)
    quick = []
    if pct:
        quick.append(b.act("Percent Style", _ic("mdi.percent"),
                           lambda: w._set_number_format(pct)))
    if sci:
        quick.append(b.act("Scientific", _ic("mdi.alpha-e-box-outline"),
                           lambda: w._set_number_format(sci)))
    quick += [
        b.act("Increase Decimal", _ic("mdi.decimal-increase"),
              lambda: _step_decimals(w, +1)),
        b.act("Decrease Decimal", _ic("mdi.decimal-decrease"),
              lambda: _step_decimals(w, -1))]
    home.add_group("Number", rows=[[num], quick], text=False,
                   launcher=fmt_cells)

    home.add_group("Styles", large=[
        b.menu_act("Format as\nTable", icons.table_design_icon(_ICO),
                   w._table_design_menu),
        b.act("Cell\nStyles", _ic("mdi.format-paint", ACCENT), fmt_cells)])

    ins_cells = QMenu(w)
    ins_cells.addAction("Insert Sheet Rows Above", w._insert_row_above)
    ins_cells.addAction("Insert Sheet Rows Below", w._insert_row_below)
    ins_cells.addAction("Insert Sheet Columns", w._insert_column)
    ins_cells.addAction("Insert Sheet", lambda: w._workbook.add_sheet())
    fmt_menu = QMenu(w)
    fmt_menu.addAction("Row Height…", w._format_row_height)
    fmt_menu.addAction("Column Width…", w._format_col_width)
    fmt_menu.addSeparator()
    fmt_menu.addAction("Format Cells…", fmt_cells)
    home.add_group("Cells", large=[
        b.act("Insert", _ic("mdi.table-row-plus-after"),
              w._insert_row_below, menu=ins_cells),
        b.menu_act("Format", _ic("mdi.table-cog"), fmt_menu)])

    sort_menu = QMenu(w)
    sort_menu.addAction(_ic("mdi.sort-alphabetical-ascending"),
                        "Sort A to Z", w._sort_asc)
    sort_menu.addAction(_ic("mdi.sort-alphabetical-descending"),
                        "Sort Z to A", w._sort_desc)
    home.add_group("Editing", rows=[
        [b.act("AutoSum", _ic("mdi.sigma", ACCENT),
               lambda: w._insert_function("SUM"),
               menu=_autosum_menu(w))],
        [b.act("Clear", _ic("mdi.eraser"), w._clear, tip="Clear (Del)")],
        [b.menu_act("Sort & Filter", _ic("mdi.sort"), sort_menu)]])

    home.add_group("Analysis", large=[
        b.act("Solver", icons.solver_icon(_ICO), w._open_solver),
        b.act("Curve\nFitting", icons.fitting_icon(_ICO), w._open_fitting)])

    # ── Insert ──────────────────────────────────────────────────────
    ins = rb.add_tab("Insert")
    ins.add_group("Tables", large=[
        b.menu_act("Table", icons.table_design_icon(_ICO),
                   w._table_design_menu),
        b.act("Pivot /\nTranspose", _ic("mdi.table-pivot"),
              w._transpose_selection)])
    ins.add_group("Illustrations", large=[
        b.act("Pictures", icons.image_icon(_ICO), w._insert_image),
        b.menu_act("Shapes", icons.shapes_button_icon(_ICO),
                   w._shapes_btn.menu())])
    fns = w._plot_icon_fns

    def chart(kind: str, label: str = "") -> QAction:
        return b.act(label or kind, fns[kind](_ICO),
                     lambda: w._plot_from_menu(kind),
                     tip=f"Insert {kind} Chart")
    others = QMenu(w)
    for kind in ("Step", "Stem", "Heatmap", "3D Surface", "Doughnut",
                 "3D Pie"):
        if kind in fns:
            others.addAction(fns[kind](20), kind,
                             lambda k=kind: w._plot_from_menu(k))
    others.addSeparator()
    others.addAction("From Template…", w._insert_chart_from_template)
    rec = b.act("Recommended\nCharts", fns["Line"](_ICO),
                lambda: w._plot_from_menu(w._last_plot_type),
                menu=w._plot_btn.menu())
    ins.add_group("Charts", large=[rec], rows=[
        [chart("Line"), chart("Bar"), chart("Pie")],
        [chart("Scatter"), chart("Line+Symbol"), chart("Histogram")],
        [chart("Box"), b.menu_act("More", _ic("mdi.chart-box-plus-outline"),
                                  others)]], text=False)
    spark = w._sparkline_btn.menu()
    ins.add_group("Sparklines", large=[
        (b.act("Sparkline", icons.sparkline_icon(_ICO),
               w._insert_sparklines_bulk, menu=spark), "Line")])
    ins.add_group("Controls", rows=[
        [b.act("Checkbox", icons.checkbox_icon(20), w._insert_checkbox)],
        [b.act("Button", icons.checkbox_icon(20), w._insert_button)],
        [b.act("Dropdown", icons.dropdown_icon(20), w._insert_dropdown)]])
    ins.add_group("Links", large=[
        b.act("Link", icons.link_icon(_ICO), w._insert_link,
              tip="Insert Link (Ctrl+K)")])
    ins.add_group("Comments", large=[
        b.act("Comment", icons.comment_icon(_ICO), w._insert_comment),
        b.act("Note", icons.note_icon(_ICO), w._insert_note)])
    ins.add_group("Symbols", large=[
        b.menu_act("Equation", icons.equation_icon(_ICO),
                   w._equation_btn.menu()),
        b.menu_act("Symbol", icons.omega_icon(_ICO), w._symbol_btn.menu()),
        b.menu_act("Emoji", icons.emoji_icon(_ICO), b.menu("Insert",
                                                          "Emoji"))])

    # ── Page Layout ─────────────────────────────────────────────────
    pl = rb.add_tab("Page Layout")
    pl.add_group("Themes", large=[
        b.menu_act("Themes", _ic("mdi.palette", ACCENT),
                   b.menu("View", "Theme"))])
    pl.add_group("Page Setup", large=[
        b.act("Print\nSetup", icons.print_icon(_ICO), w._open_print_dialog)])
    grid = b.find("View", "Gridlines", icon=_ic("mdi.grid"))
    heads = b.find("View", "Headings", icon=_ic("mdi.format-header-pound"))
    pl.add_group("Sheet Options", rows=[[grid], [heads]])
    pl.add_group("Arrange", rows=[
        [b.act("Bring Forward", _ic("mdi.arrange-bring-forward"),
               w._bring_forward)],
        [b.act("Send Backward", _ic("mdi.arrange-send-backward"),
               w._send_backward)]])

    # ── Formulas ────────────────────────────────────────────────────
    fo = rb.add_tab("Formulas")
    fo.add_group("Function Library", large=[
        b.act("Insert\nFunction", _ic("mdi.function-variant", ACCENT),
              w._open_insert_function_dialog,
              tip="Insert Function (Shift+F3)"),
        b.act("AutoSum", _ic("mdi.sigma"),
              lambda: w._insert_function("SUM"), menu=_autosum_menu(w))],
        rows=_category_rows(b))
    fo.add_group("Python", large=[
        b.act("Python\nCell", _ic("mdi.language-python", ACCENT),
              w._insert_python_cell)])

    # ── Data ────────────────────────────────────────────────────────
    da = rb.add_tab("Data")
    imp = b.menu("File", "Import")
    da.add_group("Get & Transform Data", large=[
        b.menu_act("Get\nData", _ic("mdi.database-import", ACCENT), imp)],
        rows=[[b.act("From Text/CSV", _ic("mdi.file-delimited-outline"),
                     w._import_text)],
              [b.act("From Excel", _ic("mdi.microsoft-excel"),
                     w._import_excel)]])
    da.add_group("Sort & Filter", rows=[
        [b.act("Sort A to Z", _ic("mdi.sort-alphabetical-ascending"),
               w._sort_asc)],
        [b.act("Sort Z to A", _ic("mdi.sort-alphabetical-descending"),
               w._sort_desc)]])
    da.add_group("Data Tools", large=[
        b.menu_act("Set Column\nAs X / Y", _ic("mdi.axis-arrow"),
                   b.menu("Data", "Set Column As"))])
    da.add_group("Analyze", large=[
        b.act("Solver", icons.solver_icon(_ICO), w._open_solver),
        b.act("Curve\nFitting", icons.fitting_icon(_ICO), w._open_fitting),
        b.act("Statistics", _ic("mdi.chart-bell-curve"),
              w._show_statistics),
        b.menu_act("Science\nTools", icons.science_icon(_ICO),
                   w._science_btn.menu())])

    # ── Review ──────────────────────────────────────────────────────
    rv = rb.add_tab("Review")
    rv.add_group("Proofing", large=[
        b.act("Spelling", _ic("mdi.spellcheck", ACCENT), w._spell_check,
              tip="Spelling (F7)")],
        rows=[[(w._spell_live_act, "Check as You Type")]])
    rv.add_group("Comments", large=[
        b.act("New\nComment", icons.comment_icon(_ICO), w._insert_comment),
        b.act("New\nNote", icons.note_icon(_ICO), w._insert_note)])
    rv.add_group("Version History", large=[
        b.act("History", _ic("mdi.history"), w._open_history)],
        rows=[[b.act("Push", _ic("mdi.cloud-upload-outline"), w._vc_push)],
              [b.act("Pull", _ic("mdi.cloud-download-outline"),
                     w._vc_pull)]])
    share = b.menu("File", "Live Sharing")
    if share is not None:
        rv.add_group("Share", large=[
            b.menu_act("Share", _ic("mdi.account-multiple-plus", ACCENT),
                       share)])

    # ── View ────────────────────────────────────────────────────────
    vw = rb.add_tab("View")
    normal = b.find("View", "Normal", icon=_ic("mdi.grid-large"))
    page = b.find("View", "Page Layout", icon=_ic("mdi.file-document"))
    vw.add_group("Workbook Views", large=[a for a in (normal, page) if a])
    vw.add_group("Show", rows=[[grid], [heads]])
    vw.add_group("Zoom", large=[
        b.act("Zoom In", icons.zoom_in_icon(_ICO), w._zoom_in),
        b.act("Zoom Out", icons.zoom_out_icon(_ICO), w._zoom_out),
        b.act("100%", _ic("mdi.magnify-scan"), w._zoom_reset)])
    vw.add_group("Window", large=[
        b.act("New\nWindow", _ic("mdi.dock-window"), w._new_window)])

    # ── Automate / AI / Help ────────────────────────────────────────
    ai = rb.add_tab("AI")
    ai.add_group("Claude", large=[
        b.act("Connect to\nClaude", _ic("mdi.lan-connect", ACCENT),
              w._open_mcp_dialog),
        (w._ai_chat_act, "Chat\nBox")])
    hp = rb.add_tab("Help")
    hp.add_group("Help", large=[
        b.act("User\nGuide", _ic("mdi.book-open-variant", ACCENT),
              w._open_user_guide),
        b.act("Python\nHelp", _ic("mdi.language-python"),
              w._show_python_help)])
    hp.add_group("Learn", large=[
        b.menu_act("Examples", _ic("mdi.school"), b.menu("Examples"))])
    hp.add_group("About", large=[
        b.act("Check for\nUpdates", _ic("mdi.update"),
              w._check_for_updates),
        b.act("About", _ic("mdi.information-outline"), w._show_about)])

    # Swap the classic toolbars for one bar holding the ribbon.
    for bar in w.findChildren(QToolBar):
        if bar.parent() is w:
            w.removeToolBar(bar)
            bar.hide()
    bar = QToolBar("Ribbon", w)
    bar.setObjectName("RibbonBar")
    bar.setMovable(False)
    bar.setFloatable(False)
    bar.setStyleSheet("QToolBar#RibbonBar { padding: 0; margin: 0; "
                      "border: none; spacing: 0; }")
    bar.addWidget(rb)
    w.addToolBar(Qt.TopToolBarArea, bar)
    if sys.platform != "darwin":
        _keep_shortcuts(w)
        w.menuBar().hide()
    rb.setCurrentIndex(0)
    from . import tooltips
    tooltips.apply(rb)
    return rb


def _merge_menu(w) -> QMenu:
    m = QMenu(w)
    m.addAction(icons.merge_cells_icon(20), "Merge & Center", w._merge_cells)
    m.addAction(icons.unmerge_cells_icon(20), "Unmerge Cells",
                w._unmerge_cells)
    return m


def _autosum_menu(w) -> QMenu:
    m = QMenu(w)
    for fn, label in (("SUM", "Sum"), ("AVERAGE", "Average"),
                      ("COUNT", "Count Numbers"), ("MAX", "Max"),
                      ("MIN", "Min")):
        m.addAction(label, lambda f=fn: w._insert_function(f))
    m.addSeparator()
    m.addAction("More Functions…", w._open_insert_function_dialog)
    return m


def _category_rows(b: _Builder):
    """Excel's category buttons (Financial ▾, Logical ▾, …) taken from
    the Formulas menu, three to a row."""
    fm = b.menu("Formulas")
    if fm is None:
        return []
    glyph = {"Math": "mdi.calculator-variant", "Stat": "mdi.chart-bar",
             "Logic": "mdi.help-rhombus-outline", "Text": "mdi.format-text",
             "Date": "mdi.calendar-clock", "Look": "mdi.magnify",
             "Financ": "mdi.cash", "Eng": "mdi.cog-outline",
             "Info": "mdi.information-outline", "Trig": "mdi.math-sin"}
    btns = []
    for a in fm.actions():
        if not a.menu():
            continue
        name = short(a.text())
        icon = next((v for k, v in glyph.items() if name.startswith(k)),
                    "mdi.function")
        btn = b.menu_act(name, _ic(icon), a.menu())
        btn.setProperty("tip_category", True)
        btns.append(btn)
    rows = [[], [], []]
    for i, btn in enumerate(btns):
        rows[i % 3].append(btn)
    return rows


def _step_decimals(w, step: int) -> None:
    """Increase / Decrease Decimal over the 0, 0.0 … 0.0000 formats."""
    s = w._active_sheet()
    if s is None:
        return
    cur = getattr(s, "_col_formats", {}).get(s.table.currentColumn())
    cur = cur or "0.00"
    places = len(cur.split(".")[1]) if cur.startswith("0.") else 0
    places = max(0, min(4, places + step))
    w._set_number_format("0" if places == 0 else "0." + "0" * places)


def _keep_shortcuts(w) -> None:
    """With the menu bar hidden its actions' shortcuts stop firing;
    adding them to the window keeps Ctrl+S, Ctrl+Z, … alive."""
    def walk(menu: QMenu):
        for a in menu.actions():
            if a.menu():
                walk(a.menu())
            elif not a.shortcut().isEmpty():
                w.addAction(a)
    for a in w.menuBar().actions():
        if a.menu():
            walk(a.menu())
