"""Main window shell — menus, toolbars, status bar.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import csv
import os

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QIcon, QKeySequence, QFont
from PyQt5.QtWidgets import QStyle
from PyQt5.QtWidgets import (
    QMainWindow, QStatusBar, QLabel, QAction, QMenu, QMenuBar,
    QToolBar, QToolButton, QFileDialog, QMessageBox, QProgressBar,
    QSlider, QHBoxLayout, QWidget, QUndoStack, QComboBox,
    QInputDialog, QApplication, QFontComboBox, QPushButton,
    QWidgetAction, QGridLayout, QDialog, QShortcut,
)

from . import APP_NAME, __version__
from .workbook import WorkbookWidget
from .sheet import SheetWidget, col_index_to_letter
from . import icons
from .formulas import build_formulas_menu


# References to extra windows opened via "New Window" so they are not
# garbage-collected while still on screen.
_OPEN_WINDOWS = []


class MainWindow(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = None
        self._settings = __import__(
            'PyQt5.QtCore', fromlist=['QSettings']).QSettings(
            "KherveSheet", "KherveSheet")
        self._recent_files: list = (
            self._settings.value("recent_files", []) or [])
        self._undo_stack = QUndoStack(self)
        # Page setup defaults (used by Print).
        self._page_orientation = "portrait"
        self._page_size = ("A4", 210, 297)
        self._page_margins_mm = {"top": 25.4, "bottom": 25.4,
                                 "left": 19.05, "right": 19.05}
        self._init_ui()
        # Open files dropped onto the window (grid included).
        self.setAcceptDrops(True)

    # ── UI setup ─────────────────────────────────────────────────────
    def _init_ui(self):
        self.resize(1280, 800)
        # Centre the window on screen.
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self.move((sg.width() - 1280) // 2,
                      (sg.height() - 800) // 2)

        # Central widget: workbook with sheet tabs
        self._workbook = WorkbookWidget()
        self.setCentralWidget(self._workbook)

        # Wire undo stack to all sheets
        self._wire_undo_to_sheets()
        self._workbook.tabs.currentChanged.connect(
            lambda: self._wire_undo_to_sheets())

        # Build UI
        self._build_menu_bar()
        self._build_toolbars()
        self._build_status_bar()
        self._update_title()
        # Apply the default live spell-check state now menus + sheets exist.
        if hasattr(self, "_spell_live_act"):
            self._toggle_live_spell(self._spell_live_act.isChecked())

    def _wire_undo_to_sheets(self):
        for s in self._workbook.all_sheets():
            s._undo_stack = self._undo_stack
            self._apply_live_spell_to(s)
            # Connect cell selection to format toolbar sync (guard
            # against duplicate connections with a flag).
            if not getattr(s, '_fmt_connected', False):
                s.table.currentCellChanged.connect(
                    lambda *_: self._update_format_toolbar())
                s.table.itemSelectionChanged.connect(
                    self._update_selection_summary)
                s._fmt_connected = True

    # ── Title bar ────────────────────────────────────────────────────
    def _update_title(self):
        name = self._current_file or "Untitled"
        if self._current_file:
            name = os.path.basename(self._current_file)
        self.setWindowTitle(f"{APP_NAME} v{__version__} \u2014 {name}")

    # ── Menu bar ─────────────────────────────────────────────────────
    def _build_menu_bar(self):
        mb = self.menuBar()

        # ── File ─────────────────────────────────────────────────────
        file_menu = mb.addMenu("&File")
        file_menu.addAction("&New", self._new_workbook, "Ctrl+N")
        file_menu.addAction("New &Window", self._new_window,
                            "Ctrl+Shift+N")
        file_menu.addAction("&Open…", self._open_file, "Ctrl+O")
        file_menu.addSeparator()

        imp = file_menu.addMenu("Import")
        imp.addAction("Text/CSV…", self._import_text)
        imp.addAction("Excel…", self._import_excel)

        file_menu.addSeparator()
        file_menu.addAction("&Save", self._save_file, "Ctrl+S")
        file_menu.addAction("Save &As…", self._save_file_as, "Ctrl+Shift+S")
        file_menu.addSeparator()

        exp = file_menu.addMenu("Export")
        exp.addAction("CSV…", self._export_csv)
        exp.addAction("Excel…", self._export_excel)

        file_menu.addSeparator()
        self._recent_menu = file_menu.addMenu("Recent Files")
        self._rebuild_recent_menu()

        file_menu.addSeparator()
        vc_menu = file_menu.addMenu("Version Control")
        vc_menu.setIcon(icons.themed_icon("mdi.source-branch"))
        vc_menu.addAction("Version History…", self._open_history)
        vc_menu.addSeparator()
        vc_menu.addAction("Push", self._vc_push)
        vc_menu.addAction("Pull", self._vc_pull)
        vc_menu.addSeparator()
        vc_menu.addAction("Configure Remote…", self._vc_configure_remote)

        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close, "Ctrl+Q")

        # ── Edit ─────────────────────────────────────────────────────
        edit_menu = mb.addMenu("&Edit")
        self._undo_act = edit_menu.addAction(
            "&Undo", self._undo_stack.undo, "Ctrl+Z")
        self._redo_act = edit_menu.addAction(
            "&Redo", self._undo_stack.redo, "Ctrl+Y")
        edit_menu.addSeparator()
        edit_menu.addAction("Cu&t", self._cut, "Ctrl+X")
        edit_menu.addAction("&Copy", self._copy, "Ctrl+C")
        edit_menu.addAction("&Paste", self._paste, "Ctrl+V")
        edit_menu.addAction("Paste &Values Only",
                            self._paste_values, "Ctrl+Shift+V")
        edit_menu.addAction("Cl&ear", self._clear, "Del")

        self._undo_stack.canUndoChanged.connect(self._undo_act.setEnabled)
        self._undo_stack.canRedoChanged.connect(self._redo_act.setEnabled)
        self._undo_act.setEnabled(False)
        self._redo_act.setEnabled(False)

        # ── View ─────────────────────────────────────────────────────
        view_menu = mb.addMenu("&View")

        # View modes.
        self._view_normal_act = view_menu.addAction(
            "Normal", lambda: self._set_view_mode("normal"))
        self._view_normal_act.setCheckable(True)
        self._view_normal_act.setChecked(True)
        self._view_pagelayout_act = view_menu.addAction(
            "Page Layout", lambda: self._set_view_mode("page_layout"))
        self._view_pagelayout_act.setCheckable(True)
        view_menu.addSeparator()

        # Gridlines / Headings toggles.
        self._gridlines_act = view_menu.addAction(
            "Gridlines", self._toggle_gridlines)
        self._gridlines_act.setCheckable(True)
        self._gridlines_act.setChecked(True)
        self._headings_act = view_menu.addAction(
            "Headings", self._toggle_headings)
        self._headings_act.setCheckable(True)
        self._headings_act.setChecked(True)
        view_menu.addSeparator()

        view_menu.addAction("Zoom In", self._zoom_in, "Ctrl+=")
        view_menu.addAction("Zoom Out", self._zoom_out, "Ctrl+-")
        view_menu.addAction("Reset Zoom", self._zoom_reset, "Ctrl+0")
        view_menu.addSeparator()
        bf_act = view_menu.addAction("Bring Forward", self._bring_forward)
        bf_act.setIcon(icons.themed_icon("mdi.arrange-bring-forward"))
        sb_act = view_menu.addAction("Send Backward", self._send_backward)
        sb_act.setIcon(icons.themed_icon("mdi.arrange-send-backward"))
        view_menu.addSeparator()
        theme_menu = view_menu.addMenu("Theme")
        from .app import THEMES
        for name in THEMES:
            act = theme_menu.addAction(name)
            act.triggered.connect(
                lambda _, n=name: self._apply_theme(n))

        # ── Page Layout ─────────────────────────────────────────────
        page_menu = mb.addMenu("Page &Layout")

        page_menu.addAction("Margins\u2026", self._page_margins)
        orient_menu = page_menu.addMenu("Orientation")
        self._orient_portrait = orient_menu.addAction(
            "Portrait", lambda: self._set_orientation("portrait"))
        self._orient_portrait.setCheckable(True)
        self._orient_portrait.setChecked(True)
        self._orient_landscape = orient_menu.addAction(
            "Landscape", lambda: self._set_orientation("landscape"))
        self._orient_landscape.setCheckable(True)

        size_menu = page_menu.addMenu("Size")
        for name, w, h in [("Letter", 215.9, 279.4),
                            ("A4", 210, 297),
                            ("A3", 297, 420),
                            ("Legal", 215.9, 355.6)]:
            size_menu.addAction(
                f"{name} ({w:.0f} \u00d7 {h:.0f} mm)",
                lambda n=name, ww=w, hh=h: self._set_page_size(
                    n, ww, hh))
        page_menu.addSeparator()
        page_menu.addAction("Print\u2026", self._print_sheet, "Ctrl+P")

        # ── Insert ───────────────────────────────────────────────────
        insert_menu = mb.addMenu("&Insert")

        # Chart submenu.
        chart_menu = insert_menu.addMenu("Chart")
        from .sheet import SheetWidget
        for pt in SheetWidget.PLOT_TYPES:
            act = chart_menu.addAction(pt)
            act.triggered.connect(
                lambda _, t=pt: self._insert_chart(t))

        # Pivot / Transpose.
        insert_menu.addAction("Pivot / Transpose",
                              self._transpose_selection)
        insert_menu.addSeparator()

        # Image.
        insert_menu.addAction("Image\u2026", self._insert_image)

        # Shapes submenu (full gallery, grouped by category).
        shapes_menu = self._make_shape_gallery()
        shapes_menu.setTitle("Shapes")
        shapes_menu.setIcon(icons.shapes_button_icon(24))
        insert_menu.addMenu(shapes_menu)

        # Equation submenu (presets + new equation editor).
        equation_menu = self._make_equation_gallery()
        equation_menu.setTitle("Equation")
        equation_menu.setIcon(icons.equation_icon(24))
        insert_menu.addMenu(equation_menu)

        # Sparkline.
        insert_menu.addAction("Sparkline\u2026", self._insert_sparkline)
        insert_menu.addSeparator()

        # Function submenu (mirrors Formulas menu).
        func_sub = insert_menu.addMenu("Function")
        from .formulas import FUNCTION_CATEGORIES, CATEGORY_ORDER
        for cat in CATEGORY_ORDER:
            funcs = FUNCTION_CATEGORIES.get(cat, [])
            cat_sub = func_sub.addMenu(cat)
            for fn in funcs:
                cat_sub.addAction(
                    fn, lambda f=fn: self._insert_function(f))

        # Link.
        insert_menu.addAction(
            icons.link_icon(20), "Link\tCtrl+K", self._insert_link)
        QShortcut(QKeySequence("Ctrl+K"), self, self._insert_link)
        insert_menu.addSeparator()

        # Checkbox, Dropdown, Emoji.
        insert_menu.addAction(
            icons.checkbox_icon(20), "Checkbox", self._insert_checkbox)
        insert_menu.addAction(
            icons.dropdown_icon(20), "Dropdown\u2026", self._insert_dropdown)

        # Emoji submenu.
        emoji_menu = insert_menu.addMenu(icons.emoji_icon(20), "Emoji")
        from . import insert_ops
        emoji_wa = QWidgetAction(emoji_menu)
        emoji_wa.setDefaultWidget(
            insert_ops.build_emoji_grid(
                emoji_menu,
                lambda e: self._insert_emoji(e, emoji_menu)))
        emoji_menu.addAction(emoji_wa)
        insert_menu.addSeparator()

        # Comment / Note.
        insert_menu.addAction(
            icons.comment_icon(20), "Comment\tCtrl+Alt+M",
            self._insert_comment)
        insert_menu.addAction(
            icons.note_icon(20), "Note\tShift+F2", self._insert_note)
        QShortcut(QKeySequence("Shift+F2"), self, self._insert_note)
        insert_menu.addSeparator()

        # Row / Column / Sheet.
        insert_menu.addAction("Row Above",
                              self._insert_row_above)
        insert_menu.addAction("Row Below",
                              self._insert_row_below)
        insert_menu.addAction("Column",
                              self._insert_column)
        insert_menu.addSeparator()
        insert_menu.addAction("Sheet",
                              lambda: self._workbook.add_sheet())

        # ── Format ───────────────────────────────────────────────────
        format_menu = mb.addMenu("F&ormat")
        fmt_menu = format_menu.addMenu("Number Format")
        from .sheet import NUMBER_FORMATS
        for fmt in NUMBER_FORMATS:
            act = fmt_menu.addAction(fmt)
            act.triggered.connect(
                lambda _, f=fmt: self._set_number_format(f))

        format_menu.addSeparator()
        format_menu.addAction("Fill Color\u2026", self._pick_fill_color)
        format_menu.addAction("Font Color\u2026", self._pick_font_color)
        border_sub = self._build_border_menu(format_menu)
        border_sub.setTitle("Borders")
        format_menu.addMenu(border_sub)
        format_menu.addSeparator()
        format_menu.addAction("Column Width…", self._format_col_width)
        format_menu.addAction("Row Height…", self._format_row_height)
        format_menu.addSeparator()
        merge_act = format_menu.addAction("Merge Cells", self._merge_cells)
        merge_act.setIcon(icons.themed_icon("mdi.table-merge-cells"))
        unmerge_act = format_menu.addAction(
            "Unmerge Cells", self._unmerge_cells)
        unmerge_act.setIcon(icons.themed_icon("mdi.table-split-cell"))
        self._wrap_act = format_menu.addAction(
            "Wrap Text", self._toggle_wrap_text)
        self._wrap_act.setIcon(icons.themed_icon("mdi.wrap"))
        self._wrap_act.setCheckable(True)
        format_menu.addSeparator()
        self._table_design_menu = format_menu.addMenu("Table Design")
        self._table_design_menu.setIcon(
            icons.themed_icon("mdi.table-large"))
        self._table_design_menu.aboutToShow.connect(
            self._build_table_design_menu)
        format_menu.addSeparator()
        fc_act = format_menu.addAction(
            "Format Cells\u2026\tCtrl+1", self._open_format_cells_dialog)
        # QShortcut, QKeySequence already imported at module level
        QShortcut(QKeySequence("Ctrl+1"), self,
                  self._open_format_cells_dialog)

        # ── Formulas ─────────────────────────────────────────────────
        fmenu = build_formulas_menu(mb, self._insert_function)
        fmenu.addSeparator()
        fx_act = fmenu.addAction(
            "Insert Function\u2026",
            self._open_insert_function_dialog, "Shift+F3")

        # ── Data ─────────────────────────────────────────────────────
        data_menu = mb.addMenu("&Data")
        desig_menu = data_menu.addMenu("Set Column As")
        for d in ("X", "Y"):
            act = desig_menu.addAction(d)
            act.triggered.connect(
                lambda _, d=d: self._set_designation(d))

        data_menu.addSeparator()
        data_menu.addAction("Sort A → Z", self._sort_asc)
        data_menu.addAction("Sort Z → A", self._sort_desc)

        # ── Tools ────────────────────────────────────────────────────
        tools_menu = mb.addMenu("&Tools")
        tools_menu.addAction("Spelling\u2026\tF7", self._spell_check)
        QShortcut(QKeySequence("F7"), self, self._spell_check)
        from . import spellcheck
        self._spell_live_act = tools_menu.addAction(
            "Check Spelling as You Type")
        self._spell_live_act.setCheckable(True)
        self._spell_live_act.setChecked(spellcheck.available())
        self._spell_live_act.setEnabled(spellcheck.available())
        self._spell_live_act.toggled.connect(self._toggle_live_spell)
        tools_menu.addSeparator()
        tools_menu.addAction("Statistics on Selection",
                             self._show_statistics)
        tools_menu.addSeparator()
        tools_menu.addAction("Curve Fitting…", self._open_fitting)

        # ── Help ─────────────────────────────────────────────────────
        help_menu = mb.addMenu("&Help")
        # Examples submenu — organized by category.
        from .examples import EXAMPLES
        examples_menu = help_menu.addMenu("Examples")
        cats: dict = {}
        for name, cat, builder in EXAMPLES:
            cats.setdefault(cat, []).append((name, builder))
        for cat in cats:
            cm = examples_menu.addMenu(cat)
            for name, builder in cats[cat]:
                cm.addAction(name,
                             lambda b=builder: self._load_example(b))
        help_menu.addSeparator()
        help_menu.addAction("&About", self._show_about)
        help_menu.addAction("GitHub Repository", self._open_github)

    # ── Toolbars ─────────────────────────────────────────────────────
    def _build_toolbars(self):
        icon_size = QSize(28, 28)

        # Standard toolbar
        std = self.addToolBar("Standard")
        std.setIconSize(icon_size)
        std.setToolButtonStyle(Qt.ToolButtonIconOnly)
        std.setMovable(False)

        std.addAction(
            icons.new_file_icon(28), "New", self._new_workbook)
        std.addAction(
            icons.open_file_icon(28), "Open", self._open_file)
        std.addAction(
            icons.save_file_icon(28), "Save", self._save_file)
        std.addSeparator()

        self._undo_act = std.addAction(
            icons.undo_icon(28), "Undo", self._undo_stack.undo)
        self._undo_act.setToolTip("Undo (Ctrl+Z)")
        self._redo_act = std.addAction(
            icons.redo_icon(28), "Redo", self._undo_stack.redo)
        self._redo_act.setToolTip("Redo (Ctrl+Y)")
        std.addSeparator()

        # ── Solver button ───────────────────────────────────────────
        self._solver_btn = QToolButton()
        self._solver_btn.setIcon(icons.solver_icon(28))
        self._solver_btn.setToolTip("Solver")
        self._solver_btn.clicked.connect(self._open_solver)
        std.addWidget(self._solver_btn)

        self._fitting_btn = QToolButton()
        self._fitting_btn.setIcon(icons.fitting_icon(28))
        self._fitting_btn.setToolTip("Curve Fitting")
        self._fitting_btn.clicked.connect(self._open_fitting)
        std.addWidget(self._fitting_btn)

        fx_btn = QToolButton()
        fx_btn.setText("f(x)")
        fx_btn.setStyleSheet(
            "QToolButton { font-style:italic; font-weight:bold; }")
        fx_btn.setToolTip("Insert Function (Shift+F3)")
        fx_btn.clicked.connect(self._open_insert_function_dialog)
        std.addWidget(fx_btn)

        # Font toolbar
        fmt = self.addToolBar("Font")
        fmt.setIconSize(icon_size)
        fmt.setToolButtonStyle(Qt.ToolButtonIconOnly)
        fmt.setMovable(False)

        self._font_combo = QFontComboBox()
        self._font_combo.setCurrentFont(QFont("Segoe UI"))
        self._font_combo.setMaximumWidth(160)
        self._font_combo.currentFontChanged.connect(self._apply_font_family)
        fmt.addWidget(self._font_combo)

        self._font_size = QComboBox()
        self._font_size.setEditable(True)
        self._font_size.setMaximumWidth(50)
        for s in ("8", "9", "10", "11", "12", "14", "16", "18",
                  "20", "24", "28", "36", "48", "72"):
            self._font_size.addItem(s)
        self._font_size.setCurrentText("9")
        self._font_size.currentTextChanged.connect(self._apply_font_size)
        fmt.addWidget(self._font_size)

        fmt.addSeparator()

        self._bold_act = fmt.addAction(
            icons.bold_icon(28), "Bold", self._toggle_bold)
        self._bold_act.setToolTip("Bold (Ctrl+B)")
        self._bold_act.setCheckable(True)
        self._bold_act.setShortcut("Ctrl+B")

        self._italic_act = fmt.addAction(
            icons.italic_icon(28), "Italic", self._toggle_italic)
        self._italic_act.setToolTip("Italic (Ctrl+I)")
        self._italic_act.setCheckable(True)
        self._italic_act.setShortcut("Ctrl+I")

        self._underline_act = fmt.addAction(
            icons.underline_icon(28), "Underline",
            self._toggle_underline)
        self._underline_act.setToolTip("Underline (Ctrl+U)")
        self._underline_act.setCheckable(True)
        self._underline_act.setShortcut("Ctrl+U")

        fmt.addSeparator()

        self._align_left_act = fmt.addAction(
            icons.align_left_icon(28), "Align Left",
            lambda: self._apply_alignment(Qt.AlignLeft | Qt.AlignVCenter))
        self._align_left_act.setToolTip("Align Left")
        self._align_left_act.setCheckable(True)

        self._align_center_act = fmt.addAction(
            icons.align_center_icon(28), "Align Center",
            lambda: self._apply_alignment(Qt.AlignHCenter | Qt.AlignVCenter))
        self._align_center_act.setToolTip("Align Center")
        self._align_center_act.setCheckable(True)

        self._align_right_act = fmt.addAction(
            icons.align_right_icon(28), "Align Right",
            lambda: self._apply_alignment(Qt.AlignRight | Qt.AlignVCenter))
        self._align_right_act.setToolTip("Align Right")
        self._align_right_act.setCheckable(True)

        # Keep these buttons from stealing keyboard focus, so clicking
        # them while editing a shape's text formats the current selection
        # instead of closing the in-place editor.
        for _a in (self._bold_act, self._italic_act, self._underline_act,
                   self._align_left_act, self._align_center_act,
                   self._align_right_act):
            _w = fmt.widgetForAction(_a)
            if _w is not None:
                _w.setFocusPolicy(Qt.NoFocus)

        fmt.addSeparator()

        # ── Fill colour button with dropdown ──────────────────────
        self._last_fill_color = "#ffff00"
        self._fill_btn = QToolButton()
        self._fill_btn.setIcon(
            icons.fill_color_icon(28, self._last_fill_color))
        self._fill_btn.setToolTip("Fill Color")
        self._fill_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self._fill_btn.clicked.connect(self._apply_last_fill_color)
        self._fill_menu = QMenu(self._fill_btn)
        self._fill_menu_built = False
        self._fill_menu.aboutToShow.connect(self._ensure_fill_palette)
        self._fill_btn.setMenu(self._fill_menu)
        fmt.addWidget(self._fill_btn)

        # ── Font colour button with dropdown ──────────────────────
        self._last_font_color = "#ff0000"
        self._font_color_btn = QToolButton()
        self._font_color_btn.setIcon(
            icons.font_color_icon(28, self._last_font_color))
        self._font_color_btn.setToolTip("Font Color")
        self._font_color_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self._font_color_btn.clicked.connect(
            self._apply_last_font_color)
        self._fc_menu = QMenu(self._font_color_btn)
        self._fc_menu_built = False
        self._fc_menu.aboutToShow.connect(self._ensure_font_palette)
        self._font_color_btn.setMenu(self._fc_menu)
        fmt.addWidget(self._font_color_btn)

        # ── Border button with dropdown ───────────────────────────
        self._border_btn = QToolButton()
        self._border_btn.setIcon(icons.border_icon(28))
        self._border_btn.setToolTip("Borders")
        self._border_btn.setPopupMode(QToolButton.InstantPopup)
        brd_menu = self._build_border_menu(self._border_btn)
        self._border_btn.setMenu(brd_menu)
        fmt.addWidget(self._border_btn)

        # Plot toolbar — single dropdown button with all plot types
        from .sheet import SheetWidget
        plot_bar = self.addToolBar("Plot")
        plot_bar.setIconSize(icon_size)
        plot_bar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        plot_bar.setMovable(False)
        _plot_icon_fns = {
            "Line":        icons.plot_icon_line,
            "Scatter":     icons.plot_icon_scatter,
            "Line+Symbol": icons.plot_icon_line_symbol,
            "Bar":         icons.plot_icon_bar,
            "Step":        icons.plot_icon_step,
            "Stem":        icons.plot_icon_stem,
            "Histogram":   icons.plot_icon_histogram,
            "Box":         icons.plot_icon_box,
            "Heatmap":     icons.plot_icon_heatmap,
            "3D Surface":  icons.plot_icon_3d_surface,
        }
        self._plot_btn = QToolButton()
        self._plot_btn.setToolTip("Insert Chart")
        self._plot_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self._last_plot_type = "Line"
        self._plot_btn.setIcon(icons.plot_icon_line(28))
        self._plot_btn.clicked.connect(
            lambda: self._insert_chart(self._last_plot_type))
        plot_menu = QMenu(self._plot_btn)
        for pt in SheetWidget.PLOT_TYPES:
            fn = _plot_icon_fns.get(pt)
            ic = fn(28) if fn else icons.themed_icon("mdi.chart-line")
            act = plot_menu.addAction(ic, pt,
                                      lambda t=pt: self._plot_from_menu(t))
        self._plot_btn.setMenu(plot_menu)
        self._plot_icon_fns = _plot_icon_fns
        plot_bar.addWidget(self._plot_btn)

        # ── Table Design button ──────────────────────────────────
        self._table_design_btn = QToolButton()
        self._table_design_btn.setIcon(icons.table_design_icon(28))
        self._table_design_btn.setToolTip("Table Design")
        self._table_design_btn.setPopupMode(QToolButton.InstantPopup)
        self._table_design_btn.setMenu(self._table_design_menu)
        plot_bar.addWidget(self._table_design_btn)

        # ── Image button ────────────────────────────────────────
        img_btn = QToolButton()
        img_btn.setIcon(icons.image_icon(28))
        img_btn.setToolTip("Insert Image")
        img_btn.clicked.connect(self._insert_image)
        plot_bar.addWidget(img_btn)

        # ── Shapes button ───────────────────────────────────────
        self._shapes_btn = QToolButton()
        self._shapes_btn.setIcon(icons.shapes_button_icon(28))
        self._shapes_btn.setToolTip("Insert Shape")
        self._shapes_btn.setPopupMode(QToolButton.InstantPopup)
        self._shapes_btn.setMenu(self._make_shape_gallery())
        plot_bar.addWidget(self._shapes_btn)

        # ── Equation button ──────────────────────────────────────
        self._equation_btn = QToolButton()
        self._equation_btn.setIcon(icons.equation_icon(28))
        self._equation_btn.setToolTip("Insert Equation")
        self._equation_btn.setPopupMode(QToolButton.InstantPopup)
        self._equation_btn.setMenu(self._make_equation_gallery())
        plot_bar.addWidget(self._equation_btn)

        # ── Symbol insertion button ──────────────────────────────
        self._symbol_btn = QToolButton()
        self._symbol_btn.setIcon(icons.omega_icon(28))
        self._symbol_btn.setToolTip("Insert Symbol")
        self._symbol_btn.setPopupMode(QToolButton.InstantPopup)
        sym_menu = QMenu(self._symbol_btn)
        sym_action = QWidgetAction(sym_menu)
        sym_action.setDefaultWidget(self._build_symbol_grid(sym_menu))
        sym_menu.addAction(sym_action)
        self._symbol_btn.setMenu(sym_menu)
        plot_bar.addWidget(self._symbol_btn)


        # ── Insert button with dropdown ────────────────────────────
        self._insert_btn = QToolButton()
        self._insert_btn.setIcon(icons.symbol_icon(28))
        self._insert_btn.setToolTip("Insert")
        self._insert_btn.setPopupMode(QToolButton.InstantPopup)
        ins_menu = QMenu(self._insert_btn)
        ins_menu.addAction(
            icons.checkbox_icon(20), "Checkbox", self._insert_checkbox)
        ins_menu.addAction(
            icons.dropdown_icon(20), "Dropdown\u2026", self._insert_dropdown)
        # Emoji submenu
        emoji_sub2 = ins_menu.addMenu(icons.emoji_icon(20), "Emoji")
        from .insert_ops import build_emoji_grid
        def _tb_emoji_cb(ch):
            s = self._active_sheet()
            if not s:
                return
            r, c = s.table.currentRow(), s.table.currentColumn()
            if r < 0 or c < 0:
                return
            it = s.table.item(r, c)
            if it is None:
                from PyQt5.QtWidgets import QTableWidgetItem
                it = QTableWidgetItem(ch)
                s.table.setItem(r, c, it)
            else:
                it.setText(it.text() + ch)
            s._shadow[(r, c)] = it.text()
        _tb_ewa = QWidgetAction(emoji_sub2)
        _tb_ewa.setDefaultWidget(build_emoji_grid(emoji_sub2, _tb_emoji_cb))
        emoji_sub2.addAction(_tb_ewa)
        ins_menu.addSeparator()
        ins_menu.addAction(
            icons.comment_icon(20), "Comment\tCtrl+Alt+M",
            self._insert_comment)
        ins_menu.addAction(
            icons.note_icon(20), "Note\tShift+F2", self._insert_note)
        self._insert_btn.setMenu(ins_menu)
        # Lives on the Standard toolbar, just after Undo/Redo and f(x).
        plot_bar.addWidget(self._insert_btn)

        # ── Merge/Unmerge button (in formatting toolbar) ─────────
        self._merge_btn = QToolButton()
        self._merge_btn.setIcon(icons.merge_cells_icon(28))
        self._merge_btn.setToolTip("Merge / Unmerge Cells")
        self._merge_btn.clicked.connect(self._toggle_merge)
        fmt.addWidget(self._merge_btn)

    # ── Status bar ───────────────────────────────────────────────────
    def _status_msg(self, text: str, timeout: int = 0):
        """Show a message in the status label. *timeout* in ms;
        0 = permanent.  Never use statusBar().showMessage() as it
        hides the stretch label and shifts permanent widgets left."""
        self._status_label.setText(text)
        if timeout > 0:
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(
                timeout, lambda: self._status_label.setText("Ready"))

    def _update_selection_summary(self):
        """Update status bar with Average, Count, Sum of selection."""
        s = self._active_sheet()
        if not s:
            self._sum_label.setText("")
            return
        sel = s.table.selectedRanges()
        if not sel:
            self._sum_label.setText("")
            return
        values = []
        for rng in sel:
            for r in range(rng.topRow(), rng.bottomRow() + 1):
                for c in range(rng.leftColumn(), rng.rightColumn() + 1):
                    it = s.table.item(r, c)
                    if it and it.text():
                        try:
                            values.append(float(it.text()))
                        except ValueError:
                            pass
        if not values:
            self._sum_label.setText("")
            return
        import numpy as np
        avg = np.mean(values)
        total = np.sum(values)
        count = len(values)
        # Format compactly.
        def _fmt(v):
            if abs(v) < 1e-10:
                return "0"
            if abs(v) >= 1e6 or (abs(v) < 0.01 and v != 0):
                return f"{v:.4g}"
            return f"{v:,.4f}".rstrip("0").rstrip(".")
        self._sum_label.setText(
            f"Average: {_fmt(avg)}   Count: {count}   Sum: {_fmt(total)}")

    def _build_status_bar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._status_label = QLabel("Ready")
        sb.addWidget(self._status_label, stretch=1)

        self._progress = QProgressBar()
        self._progress.setFixedWidth(200)
        self._progress.setMaximumHeight(16)
        self._progress.hide()
        sb.addPermanentWidget(self._progress)

        # Spacer pushes summary + zoom to far right
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy())
        from PyQt5.QtWidgets import QSizePolicy
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sb.addPermanentWidget(spacer)

        # Selection summary: Average | Count | Sum (right-aligned)
        self._sum_label = QLabel("")
        self._sum_label.setMinimumWidth(300)
        self._sum_label.setStyleSheet("padding: 0 8px;")
        self._sum_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sb.addPermanentWidget(self._sum_label)

        # Zoom slider (far right)
        zoom_w = QWidget()
        zh = QHBoxLayout(zoom_w)
        zh.setContentsMargins(4, 0, 4, 0)
        zh.setSpacing(4)
        zm = QLabel("\u2212")
        zm.setCursor(Qt.PointingHandCursor)
        zm.mousePressEvent = lambda _: self._zoom_out()
        self._zoom_slider = QSlider(Qt.Horizontal)
        self._zoom_slider.setRange(1, 200)
        self._zoom_slider.setValue(100)
        self._zoom_slider.setMaximumWidth(120)
        self._zoom_slider.valueChanged.connect(self._apply_zoom)
        self._zoom_label = QLabel("100%")
        self._zoom_label.setMinimumWidth(36)
        zp = QLabel("+")
        zp.setCursor(Qt.PointingHandCursor)
        zp.mousePressEvent = lambda _: self._zoom_in()
        zh.addWidget(zm)
        zh.addWidget(self._zoom_slider)
        zh.addWidget(self._zoom_label)
        zh.addWidget(zp)
        sb.addPermanentWidget(zoom_w)

    # ── Active sheet helper ──────────────────────────────────────────
    def _active_sheet(self) -> SheetWidget:
        return self._workbook.current_sheet()

    # ── File operations ──────────────────────────────────────────────
    def _maybe_save_changes(self) -> bool:
        """If there are unsaved changes, ask the user to save/discard.

        Returns True if the caller may proceed (saved or discarded),
        False if the user cancelled.
        """
        if self._undo_stack.isClean():
            return True
        reply = QMessageBox.question(
            self, "Save Changes?",
            "You have unsaved changes.\n"
            "Do you want to save them first?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save)
        if reply == QMessageBox.Save:
            return self._save_file()
        if reply == QMessageBox.Discard:
            return True
        return False

    def _new_workbook(self):
        if not self._maybe_save_changes():
            return
        self._current_file = None
        # Reset workbook
        wb = WorkbookWidget()
        self.setCentralWidget(wb)
        self._workbook = wb
        self._wire_undo_to_sheets()
        self._workbook.tabs.currentChanged.connect(
            lambda: self._wire_undo_to_sheets())
        self._undo_stack.clear()
        self._update_title()
        self._status_msg("New workbook created", 3000)

    def _new_window(self):
        """Open a brand-new independent MainWindow (a fresh front end).

        The new window shares this process but has its own workbook,
        undo stack and document, like a second instance of the app.
        A module-level registry keeps a reference so the window is not
        garbage-collected when this method returns.
        """
        win = MainWindow()
        win.resize(self.size())
        pos = self.pos()
        win.move(pos.x() + 36, pos.y() + 36)
        _OPEN_WINDOWS.append(win)
        # Drop the reference once the window is closed.
        win.destroyed.connect(
            lambda _=None, w=win: _OPEN_WINDOWS.remove(w)
            if w in _OPEN_WINDOWS else None)
        win.show()
        win.raise_()
        win.activateWindow()
        return win

    def _load_example(self, builder):
        """Create a new workbook from an example builder function."""
        from PyQt5.QtWidgets import QTableWidgetItem
        sheets = builder()
        self._new_workbook()
        wb = self._workbook
        # Remove default sheets.
        while wb.tabs.count() > 0:
            wb.tabs.removeTab(0)
        for sheet_name, headers, rows in sheets:
            s = wb.add_sheet(sheet_name)
            n_cols = max(len(headers), max(
                (len(r) for r in rows), default=0)) if rows else len(headers)
            if n_cols > s.table.columnCount():
                s.table.setColumnCount(n_cols)
            s.table.blockSignals(True)
            # Write header row.
            for c, h in enumerate(headers):
                it = QTableWidgetItem(h)
                font = it.font()
                font.setBold(True)
                it.setFont(font)
                s.table.setItem(0, c, it)
                s._shadow[(0, c)] = h
            # Write data rows.
            for ri, row in enumerate(rows):
                r = ri + 1
                for c, val in enumerate(row):
                    it = QTableWidgetItem(val)
                    s.table.setItem(r, c, it)
                    s._shadow[(r, c)] = val
            s.table.blockSignals(False)
            # Evaluate formulas.
            for ri, row in enumerate(rows):
                r = ri + 1
                for c, val in enumerate(row):
                    if val.startswith("="):
                        s._on_cell_changed(r, c)
        wb._combined_tab = None
        wb.ensure_layout_tabs()
        wb.tabs.setCurrentIndex(0)
        self._status_msg("Example loaded", 3000)

    # Extensions accepted by the open dialog and drag-and-drop.
    _OPENABLE_EXTS = (".ksheet", ".csv", ".xlsx", ".xlsm")

    def _open_path(self, path: str, add_recent: bool = True) -> bool:
        """Load a file by its extension (.ksheet / .csv / .xlsx / .xlsm).
        Returns True if the extension was recognised and loaded."""
        low = path.lower()
        if low.endswith(".ksheet"):
            self._load_ksheet(path)
        elif low.endswith(".csv"):
            self._load_csv(path)
        elif low.endswith((".xlsx", ".xlsm")):
            self._load_excel(path)
        else:
            return False
        self._current_file = path
        if add_recent:
            self._add_recent(path)
        self._update_title()
        return True

    def _open_file(self):
        if not self._maybe_save_changes():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "",
            "KherveSheet (*.ksheet);;"
            "CSV Files (*.csv);;Excel Files (*.xlsx *.xlsm);;"
            "All Files (*)")
        if not path:
            return
        self._open_path(path)

    def _save_file(self) -> bool:
        if self._current_file:
            if self._current_file.endswith(".ksheet"):
                self._save_to_ksheet(self._current_file)
            else:
                self._save_to_csv(self._current_file)
            self._undo_stack.setClean()
            return True
        return self._save_file_as()

    def _save_file_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save As", "",
            "KherveSheet (*.ksheet);;"
            "CSV Files (*.csv);;All Files (*)")
        if not path:
            return False
        if path.endswith(".ksheet"):
            self._save_to_ksheet(path)
        else:
            self._save_to_csv(path)
        self._current_file = path
        self._add_recent(path)
        self._update_title()
        self._undo_stack.setClean()
        return True

    def closeEvent(self, event):
        """Prompt to save unsaved changes before closing."""
        event.accept() if self._maybe_save_changes() else event.ignore()

    # ── Drag-and-drop file opening ───────────────────────────────────
    def _dropped_openable_paths(self, mime):
        """Local file paths in a drop whose extension we can open."""
        if not mime.hasUrls():
            return []
        paths = []
        for url in mime.urls():
            p = url.toLocalFile()
            if p and p.lower().endswith(self._OPENABLE_EXTS):
                paths.append(p)
        return paths

    def dragEnterEvent(self, event):
        if self._dropped_openable_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._dropped_openable_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = self._dropped_openable_paths(event.mimeData())
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        # Open the first dropped file in this window (after the usual
        # unsaved-changes prompt); open any extras in new windows so
        # nothing is silently discarded.
        if not self._maybe_save_changes():
            return
        self._open_path(paths[0])
        for extra in paths[1:]:
            try:
                win = MainWindow()
                win.show()
                win._open_path(extra)
            except Exception:
                pass

    def _import_text(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Text / CSV", "",
            "Text Files (*.csv *.tsv *.txt *.dat *.ascii *.asc);;"
            "All Files (*)")
        if not path:
            return
        from .text_import_dialog import TextImportDialog
        rows, has_header, as_text, ok = TextImportDialog.get_import_data(
            path, self)
        if not ok or not rows:
            return
        self._load_parsed_rows(rows, has_header, as_text)
        self._add_recent(path)
        self._status_msg(
            f"Imported {len(rows)} rows from {os.path.basename(path)}", 5000)

    def _load_parsed_rows(self, rows, has_header, as_text):
        """Load pre-parsed rows into the active sheet."""
        sheet = self._active_sheet()
        if not sheet:
            return
        sheet.clear_all_data()
        from PyQt5.QtWidgets import QTableWidgetItem

        data_start = 1 if has_header else 0
        data = rows[data_start:]
        if not data and not has_header:
            return
        n_cols = max(26, max(len(r) for r in rows))
        n_rows = len(data)

        sheet.table.blockSignals(True)
        sheet.table.setColumnCount(n_cols)
        sheet.table.setRowCount(n_rows)
        sheet._refresh_headers()

        self._show_progress(True)
        for i, row in enumerate(data):
            self._progress.setValue(int(100 * i / max(1, n_rows)))
            QApplication.processEvents()
            for j, val in enumerate(row):
                if not as_text:
                    # Try to preserve numeric types for the cell
                    try:
                        float(val)
                    except (ValueError, TypeError):
                        pass
                sheet.table.setItem(i, j, QTableWidgetItem(val))
                sheet._shadow[(i, j)] = val
        sheet.table.blockSignals(False)
        self._show_progress(False)

    def _import_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Excel", "", "Excel Files (*.xlsx *.xls)")
        if path:
            self._load_excel(path)
            self._add_recent(path)

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "", "CSV Files (*.csv)")
        if path:
            self._save_to_csv(path)

    def _export_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Excel", "", "Excel Files (*.xlsx)")
        if path:
            self._save_to_excel(path)

    # ── CSV I/O ──────────────────────────────────────────────────────
    def _load_csv(self, path: str):
        sheet = self._active_sheet()
        if not sheet:
            return
        sheet.clear_all_data()
        self._show_progress(True)
        try:
            with open(path, newline='', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                rows = list(reader)
            if not rows:
                return

            n_cols = max(len(r) for r in rows)
            n_rows = len(rows)

            sheet.table.blockSignals(True)
            sheet.table.setColumnCount(n_cols)
            sheet.table.setRowCount(n_rows)
            sheet._refresh_headers()

            from PyQt5.QtWidgets import QTableWidgetItem
            for i, row in enumerate(rows):
                self._progress.setValue(int(100 * i / n_rows))
                QApplication.processEvents()
                for j, val in enumerate(row):
                    sheet.table.setItem(i, j, QTableWidgetItem(val))
                    sheet._shadow[(i, j)] = val
            sheet.table.blockSignals(False)

            self._status_msg(
                f"Loaded {n_rows} rows × {n_cols} columns from {path}",
                5000)
        except Exception as e:
            QMessageBox.warning(self, "Import Error", str(e))
        finally:
            self._show_progress(False)

    def _save_to_csv(self, path: str):
        sheet = self._active_sheet()
        if not sheet:
            return
        self._show_progress(True, "Saving…")
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                for r in range(sheet.row_count()):
                    self._progress.setValue(
                        int(100 * r / max(1, sheet.row_count())))
                    row = []
                    for c in range(sheet.column_count()):
                        it = sheet.table.item(r, c)
                        row.append(it.text() if it else "")
                    writer.writerow(row)
            self._status_msg(f"Saved to {path}", 5000)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))
        finally:
            self._show_progress(False)

    # ── Excel I/O ────────────────────────────────────────────────────
    def _load_excel(self, path: str):
        try:
            import openpyxl
        except ImportError:
            QMessageBox.warning(
                self, "Missing Library",
                "openpyxl is required for Excel import.\n"
                "Install with: pip install openpyxl")
            return
        self._show_progress(True)
        try:
            # data_only=False keeps the formula text (=SUM(...)); a second
            # pass with data_only=True provides Excel's last-computed values
            # so cells display correctly the moment they load, before our
            # own engine recalculates them.
            wb_f = openpyxl.load_workbook(path, data_only=False)
            try:
                wb_v = openpyxl.load_workbook(path, data_only=True)
            except Exception:
                wb_v = None

            wb = self._workbook
            # Replace the existing sheet tabs with one tab per worksheet.
            for s in wb.all_sheets():
                idx = wb.tabs.indexOf(s)
                if idx >= 0:
                    wb.tabs.removeTab(idx)
                    s.deleteLater()

            from . import excel_import
            theme_palette = excel_import.build_theme_palette(wb_f)

            titles = wb_f.sheetnames
            total = sum((wb_f[t].max_row or 0) for t in titles) or 1
            done = 0
            first = None
            sheet_by_title = {}
            for title in titles:
                ws_f = wb_f[title]
                ws_v = wb_v[title] if wb_v is not None else None
                sheet = wb.add_sheet(title)
                sheet_by_title[title] = sheet
                if first is None:
                    first = sheet
                done = self._fill_sheet_from_excel(
                    sheet, ws_f, ws_v, done, total, theme_palette)

            wb.ensure_layout_tabs()
            self._wire_undo_to_sheets()
            if first is not None:
                wb.tabs.setCurrentWidget(first)

            # Reconstruct charts and floating text boxes now that the
            # sheet viewports exist as valid parent widgets.
            from . import excel_import
            for title in titles:
                try:
                    excel_import.import_charts(
                        sheet_by_title[title], wb_f[title], sheet_by_title)
                except Exception:
                    pass
            excel_import.import_textboxes(path, sheet_by_title)
            self._status_msg(
                f"Loaded {len(titles)} sheet(s) from {path}", 5000)
        except Exception as e:
            QMessageBox.warning(self, "Import Error", str(e))
        finally:
            self._show_progress(False)

    @staticmethod
    def _excel_value_str(v) -> str:
        """Format an openpyxl cell value for grid display."""
        if isinstance(v, bool):
            return "TRUE" if v else "FALSE"
        if isinstance(v, float) and v == int(v):
            return str(int(v))
        return str(v)

    def _fill_sheet_from_excel(self, sheet, ws_f, ws_v, done, total,
                               theme_palette=None):
        """Populate one SheetWidget from a worksheet, preserving
        formulas.  Returns the running progress counter."""
        from PyQt5.QtWidgets import QTableWidgetItem
        from . import excel_import
        n_rows = ws_f.max_row or 0
        n_cols = ws_f.max_column or 0
        sheet.table.blockSignals(True)
        sheet.table.setColumnCount(max(n_cols, 1))
        sheet.table.setRowCount(max(n_rows, 1))
        sheet._refresh_headers()
        uncached = []
        for r in range(n_rows):
            done += 1
            self._progress.setValue(int(100 * done / total))
            QApplication.processEvents()
            for c in range(n_cols):
                xl_cell = ws_f.cell(r + 1, c + 1)
                fv = xl_cell.value
                cmt = getattr(xl_cell, "comment", None)
                if cmt is not None and getattr(cmt, "text", None):
                    sheet._cell_notes[(r, c)] = {
                        "text": cmt.text, "kind": "comment"}
                formula = None
                if isinstance(fv, str) and fv.startswith("="):
                    formula = fv
                elif fv is not None:
                    # Array/data-table formulas carry their text here.
                    t = getattr(fv, "text", None)
                    if isinstance(t, str) and t.startswith("="):
                        formula = t
                if formula is not None:
                    sheet._cell_formulas[(r, c)] = formula
                    sheet._register_deps(r, c, formula)
                    cached = (ws_v.cell(r + 1, c + 1).value
                              if ws_v is not None else None)
                    if cached is not None:
                        display = self._excel_value_str(cached)
                    else:
                        display = str(sheet._evaluate_formula(
                            formula, r, c, sheet._cell_decimals(r, c)))
                        uncached.append((r, c))
                    sheet.table.setItem(r, c, QTableWidgetItem(display))
                    sheet._shadow[(r, c)] = display
                else:
                    val = self._excel_value_str(fv) if fv is not None else ""
                    sheet.table.setItem(r, c, QTableWidgetItem(val))
                    sheet._shadow[(r, c)] = val
                # Import visual formatting (fill, font, borders, align).
                cf = excel_import.cell_format_from_xl(xl_cell, theme_palette)
                if cf is not None:
                    sheet._cell_formats[(r, c)] = cf
                    it = sheet.table.item(r, c)
                    if it is not None:
                        sheet._apply_format_to_item(it, cf)
        # If Excel never cached values, our engine must compute them; a
        # second pass resolves simple forward references.
        for _ in range(2 if uncached else 0):
            for (r, c) in uncached:
                fm = sheet._cell_formulas.get((r, c))
                res = str(sheet._evaluate_formula(
                    fm, r, c, sheet._cell_decimals(r, c)))
                it = sheet.table.item(r, c)
                if it is not None:
                    it.setText(res)
                sheet._shadow[(r, c)] = res
        sheet.table.blockSignals(False)
        return done

    def _save_to_excel(self, path: str):
        try:
            import openpyxl
        except ImportError:
            QMessageBox.warning(
                self, "Missing Library",
                "openpyxl is required for Excel export.\n"
                "Install with: pip install openpyxl")
            return
        sheet = self._active_sheet()
        if not sheet:
            return
        self._show_progress(True, "Saving…")
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            for r in range(sheet.row_count()):
                self._progress.setValue(
                    int(100 * r / max(1, sheet.row_count())))
                for c in range(sheet.column_count()):
                    it = sheet.table.item(r, c)
                    val = it.text() if it else ""
                    # Try to write as number
                    try:
                        val = float(val)
                        if val == int(val):
                            val = int(val)
                    except (ValueError, TypeError):
                        pass
                    ws.cell(r + 1, c + 1, val)
            wb.save(path)
            self._status_msg(f"Exported to {path}", 5000)
        except Exception as e:
            QMessageBox.warning(self, "Export Error", str(e))
        finally:
            self._show_progress(False)

    # ── KherveSheet native HDF5 I/O ────────────────────────────────
    def _save_to_ksheet(self, path: str):
        try:
            import h5py
        except ImportError:
            QMessageBox.warning(
                self, "Missing Library",
                "h5py is required for .ksheet files.\n"
                "Install with: pip install h5py")
            return
        import json
        import numpy as np
        self._show_progress(True, "Saving…")
        try:
            wb = self._workbook
            with h5py.File(path, 'w') as f:
                from .sheet import SheetWidget
                sheet_tabs = [si for si in range(wb.tabs.count())
                              if isinstance(wb.tabs.widget(si), SheetWidget)]
                f.attrs['format'] = 'ksheet'
                f.attrs['version'] = 1
                f.attrs['sheet_count'] = len(sheet_tabs)

                ct = getattr(wb, '_combined_tab', None)
                if ct is not None:
                    try:
                        f.attrs['layout_settings'] = json.dumps(
                            ct.get_settings())
                    except Exception:
                        pass

                for out_i, si in enumerate(sheet_tabs):
                    sheet = wb.tabs.widget(si)
                    name = wb.tabs.tabText(si)
                    sg = f.create_group(f"sheet_{out_i}")
                    sg.attrs['name'] = name
                    sg.attrs['rows'] = sheet.row_count()
                    sg.attrs['cols'] = sheet.column_count()

                    # Grid data as a flat string array.
                    n_rows = sheet.row_count()
                    n_cols = sheet.column_count()
                    data = []
                    formulas = sheet._cell_formulas
                    for r in range(n_rows):
                        self._progress.setValue(
                            int(100 * (si * n_rows + r)
                                / max(1, wb.tabs.count() * n_rows)))
                        QApplication.processEvents()
                        for c in range(n_cols):
                            # Save formula text if cell has one,
                            # otherwise save display value.
                            fm = formulas.get((r, c))
                            if fm:
                                data.append(fm)
                            else:
                                it = sheet.table.item(r, c)
                                data.append(it.text() if it else "")
                    dt = h5py.string_dtype()
                    sg.create_dataset("cells", data=data, dtype=dt)

                    # Cell formats (fill + borders).
                    from .cellformat import formats_to_json
                    fmt_json = formats_to_json(sheet._cell_formats)
                    if fmt_json:
                        sg.attrs['cell_formats'] = fmt_json

                    # Merged cells.
                    if sheet._merged_ranges:
                        sg.attrs['merged_ranges'] = json.dumps(
                            sheet._merged_ranges)

                    # Column designations.
                    if sheet._col_designations:
                        sg.attrs['col_designations'] = json.dumps(
                            {str(k): v
                             for k, v in sheet._col_designations.items()})

                    # Insert-ops metadata (notes, links, dropdowns).
                    from .insert_ops import save_insert_data
                    iops_json = save_insert_data(sheet)
                    if iops_json:
                        sg.attrs['insert_ops'] = iops_json

                    # Column widths.
                    widths = [sheet.table.columnWidth(c)
                              for c in range(n_cols)]
                    sg.create_dataset("col_widths", data=widths)

                    # Charts.
                    charts = getattr(sheet, '_charts', [])
                    sg.attrs['chart_count'] = len(charts)
                    for ci, chart in enumerate(charts):
                        cg = sg.create_group(f"chart_{ci}")
                        d = chart.to_dict()
                        cg.attrs['pos_x'] = d['pos_x']
                        cg.attrs['pos_y'] = d['pos_y']
                        cg.attrs['width'] = d['width']
                        cg.attrs['height'] = d['height']
                        cg.attrs['title'] = d.get('title', '')
                        cg.attrs['xlabel'] = d.get('xlabel', 'X')
                        cg.attrs['ylabel'] = d.get('ylabel', 'Y')
                        cg.attrs['xscale'] = d.get('xscale', 'linear')
                        cg.attrs['yscale'] = d.get('yscale', 'linear')
                        cg.attrs['grid'] = d.get('grid', False)
                        cg.attrs['series_count'] = len(d['series'])
                        # Axis properties (full dialog state).
                        if d.get('axis_props'):
                            ap = d['axis_props']
                            for _dir, st in ap.items():
                                if isinstance(st, dict):
                                    for k, v in list(st.items()):
                                        if hasattr(v, 'item'):
                                            st[k] = v.item()
                            cg.attrs['axis_props'] = json.dumps(ap)
                        # General (figure-level) properties.
                        if d.get('general_props'):
                            cg.attrs['general_props'] = json.dumps(
                                d['general_props'])
                        # Secondary labels.
                        cg.attrs['top_label'] = d.get(
                            'top_label', '')
                        cg.attrs['right_label'] = d.get(
                            'right_label', '')
                        # Source column mapping.
                        if d.get('x_col') is not None:
                            cg.attrs['x_col'] = d['x_col']
                        if d.get('y_cols'):
                            cg.attrs['y_cols'] = json.dumps(
                                d['y_cols'])
                        # Legend properties.
                        cg.attrs['legend_visible'] = d.get(
                            'legend_visible', True)
                        if d.get('legend_font'):
                            cg.attrs['legend_font'] = d['legend_font']
                        cg.attrs['legend_size'] = d.get(
                            'legend_size', 8)
                        if d.get('legend_props'):
                            cg.attrs['legend_props'] = json.dumps(
                                d['legend_props'])
                        for ki, s in enumerate(d['series']):
                            srg = cg.create_group(f"series_{ki}")
                            srg.create_dataset("x", data=s['x'])
                            srg.create_dataset("y", data=s['y'])
                            srg.attrs['label'] = s['label']
                            srg.attrs['plot_type'] = s['plot_type']
                            # All extra visual / fill properties.
                            _skip = {'x', 'y', 'label', 'plot_type'}
                            props = {}
                            for k, v in s.items():
                                if k in _skip:
                                    continue
                                # Convert numpy scalars to Python.
                                if hasattr(v, 'item'):
                                    v = v.item()
                                if isinstance(v, (str, int, float,
                                                  bool, type(None))):
                                    props[k] = v
                            if props:
                                srg.attrs['props'] = json.dumps(
                                    props)

                    # Images.
                    images = getattr(sheet, '_images', [])
                    sg.attrs['image_count'] = len(images)
                    for ii, img in enumerate(images):
                        ig = sg.create_group(f"image_{ii}")
                        d = img.to_dict()
                        ig.attrs['pos_x'] = d['pos_x']
                        ig.attrs['pos_y'] = d['pos_y']
                        ig.attrs['width'] = d['width']
                        ig.attrs['height'] = d['height']
                        # Crop and colour filter metadata.
                        if 'crop' in d:
                            ig.attrs['crop'] = json.dumps(d['crop'])
                        if d.get('hue_shift', 0) != 0:
                            ig.attrs['hue_shift'] = d['hue_shift']
                        if d.get('saturation', 0) != 0:
                            ig.attrs['saturation'] = d['saturation']
                        if d.get('brightness', 0) != 0:
                            ig.attrs['brightness'] = d['brightness']
                        if not d.get('keep_aspect_ratio', True):
                            ig.attrs['keep_aspect_ratio'] = False
                        if d.get('group_id') is not None:
                            ig.attrs['group_id'] = int(d['group_id'])
                        # Store PNG data as raw bytes (uint8 array
                        # to avoid VLEN string null-byte issues).
                        import base64
                        raw = base64.b64decode(d['data'])
                        ig.create_dataset(
                            "png_data",
                            data=np.frombuffer(raw, dtype=np.uint8))

                    # Shapes.
                    shapes = getattr(sheet, '_shapes', [])
                    sg.attrs['shape_count'] = len(shapes)
                    for si2, shp in enumerate(shapes):
                        shg = sg.create_group(f"shape_{si2}")
                        shg.attrs['data'] = json.dumps(shp.to_dict())

                    # Equations.
                    equations = getattr(sheet, '_equations', [])
                    sg.attrs['equation_count'] = len(equations)
                    for ei2, eqn in enumerate(equations):
                        eqg = sg.create_group(f"equation_{ei2}")
                        eqg.attrs['data'] = json.dumps(eqn.to_dict())

                    # Solver configuration.
                    solver_cfg = getattr(sheet, '_solver_config', {})
                    if solver_cfg:
                        sg.attrs['solver_config'] = json.dumps(solver_cfg)

                    # Curve Fitting configuration (peaks, ranges, etc.).
                    fit_cfg = getattr(sheet, '_fit_config', {})
                    if fit_cfg:
                        sg.attrs['fit_config'] = json.dumps(fit_cfg)

            self._status_msg(f"Saved to {path}", 5000)
            # Auto-commit for version history.
            self._auto_commit(path)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))
        finally:
            self._show_progress(False)

    def _auto_commit(self, path: str):
        """Commit the saved file to its own isolated version repo."""
        from . import git_backend
        if not git_backend.is_available():
            return
        import shutil
        from pathlib import Path
        p = Path(path)
        repo_dir = p.parent / ".ksheet_versions" / p.stem
        repo_dir.mkdir(parents=True, exist_ok=True)
        # Copy the saved file into the version repo.
        shutil.copy2(str(p), str(repo_dir / p.name))
        git_backend.commit_all(repo_dir, file_stem=p.stem)

    def _load_ksheet(self, path: str):
        try:
            import h5py
        except ImportError:
            QMessageBox.warning(
                self, "Missing Library",
                "h5py is required for .ksheet files.\n"
                "Install with: pip install h5py")
            return
        import json
        import numpy as np
        self._show_progress(True)
        try:
            with h5py.File(path, 'r') as f:
                if f.attrs.get('format') != 'ksheet':
                    QMessageBox.warning(
                        self, "Format Error",
                        "Not a valid .ksheet file.")
                    return

                sheet_count = int(f.attrs['sheet_count'])
                layout_settings = None
                ls_raw = f.attrs.get('layout_settings')
                if ls_raw is not None:
                    if isinstance(ls_raw, bytes):
                        ls_raw = ls_raw.decode('utf-8')
                    try:
                        layout_settings = json.loads(ls_raw)
                    except Exception:
                        layout_settings = None

                # Create fresh workbook.
                wb = WorkbookWidget()
                # Remove default sheets.
                while wb.tabs.count():
                    w = wb.tabs.widget(0)
                    wb.tabs.removeTab(0)
                    w.deleteLater()

                from PyQt5.QtWidgets import QTableWidgetItem

                for si in range(sheet_count):
                    sheet_key = f"sheet_{si}"
                    if sheet_key not in f:
                        continue
                    sg = f[sheet_key]
                    name = sg.attrs['name']
                    n_rows = int(sg.attrs['rows'])
                    n_cols = int(sg.attrs['cols'])

                    sheet = wb.add_sheet(name)
                    sheet.table.blockSignals(True)
                    sheet.table.setRowCount(n_rows)
                    sheet.table.setColumnCount(n_cols)
                    sheet._refresh_headers()

                    # Restore cells — first pass: load values and
                    # record formulas for a second evaluation pass.
                    cells = sg["cells"][:]
                    pending_formulas = []
                    idx = 0
                    for r in range(n_rows):
                        self._progress.setValue(
                            int(100 * (si * n_rows + r)
                                / max(1, sheet_count * n_rows)))
                        QApplication.processEvents()
                        for c in range(n_cols):
                            val = cells[idx]
                            if isinstance(val, bytes):
                                val = val.decode('utf-8')
                            if val:
                                if val.startswith("="):
                                    # Store formula; set placeholder.
                                    sheet._cell_formulas[(r, c)] = val
                                    sheet.table.setItem(
                                        r, c, QTableWidgetItem(""))
                                    pending_formulas.append((r, c, val))
                                else:
                                    sheet.table.setItem(
                                        r, c, QTableWidgetItem(val))
                                    sheet._shadow[(r, c)] = val
                            idx += 1
                    # Second pass: evaluate formulas now that all
                    # plain values are in place, and register deps.
                    # Run twice so formulas referencing other formula
                    # cells (e.g. max(E) where E has formulas) pick
                    # up results from the first pass.
                    for _pass in range(2):
                        for r, c, formula in pending_formulas:
                            if _pass == 0:
                                sheet._register_deps(r, c, formula)
                            result = sheet._evaluate_formula(
                                formula, r, c)
                            it = sheet.table.item(r, c)
                            if it:
                                it.setText(str(result))
                            sheet._shadow[(r, c)] = str(result)
                    sheet.table.blockSignals(False)

                    # Column designations.
                    desig_json = sg.attrs.get('col_designations', '')
                    if desig_json:
                        d = json.loads(desig_json)
                        sheet._col_designations = {
                            int(k): v for k, v in d.items()}
                        sheet._refresh_headers()

                    # Insert-ops metadata (notes, links, dropdowns).
                    iops_json = sg.attrs.get('insert_ops', '')
                    if isinstance(iops_json, bytes):
                        iops_json = iops_json.decode('utf-8')
                    if iops_json:
                        from .insert_ops import load_insert_data
                        load_insert_data(sheet, iops_json)

                    # Cell formats (fill, borders, font).
                    fmt_json = sg.attrs.get('cell_formats', '')
                    if isinstance(fmt_json, bytes):
                        fmt_json = fmt_json.decode('utf-8')
                    if fmt_json:
                        from .cellformat import formats_from_json
                        sheet._cell_formats.update(
                            formats_from_json(fmt_json))
                        from PyQt5.QtWidgets import QTableWidgetItem
                        from PyQt5.QtGui import QFont, QBrush
                        for (fr, fc), cf in sheet._cell_formats.items():
                            it = sheet.table.item(fr, fc)
                            if it is None:
                                it = QTableWidgetItem("")
                                sheet.table.setItem(fr, fc, it)
                            if cf.bg_color:
                                it.setBackground(QColor(cf.bg_color))
                            if cf.font_color:
                                it.setForeground(QColor(cf.font_color))
                            if cf.alignment is not None:
                                it.setTextAlignment(cf.alignment)
                            # Font properties.
                            need_font = (cf.bold is not None
                                         or cf.italic is not None
                                         or cf.underline is not None
                                         or cf.font_family is not None
                                         or cf.font_size is not None)
                            if need_font:
                                ft = it.font()
                                if cf.bold is not None:
                                    ft.setBold(cf.bold)
                                if cf.italic is not None:
                                    ft.setItalic(cf.italic)
                                if cf.underline is not None:
                                    ft.setUnderline(cf.underline)
                                if cf.font_family is not None:
                                    ft.setFamily(cf.font_family)
                                if cf.font_size is not None:
                                    ft.setPointSizeF(cf.font_size)
                                it.setFont(ft)
                            if cf.wrap_text:
                                flags = it.flags()
                                flags |= Qt.TextWordWrap
                                it.setFlags(flags)
                                sheet.table.resizeRowToContents(fr)

                    # Column widths.
                    if "col_widths" in sg:
                        widths = sg["col_widths"][:]
                        for c, w in enumerate(widths):
                            sheet.table.setColumnWidth(c, int(w))

                    # Merged cells.
                    mr_json = sg.attrs.get('merged_ranges', '')
                    if mr_json:
                        spans = json.loads(mr_json)
                        sheet._merged_ranges = [
                            tuple(s) for s in spans]
                        for (mr, mc, rs, cs) in sheet._merged_ranges:
                            sheet.table.setSpan(mr, mc, rs, cs)

                    # Collect chart data (defer creation until after
                    # the workbook is installed as central widget so
                    # the viewport is part of a visible window —
                    # matplotlib crashes if the parent is off-screen).
                    chart_count = int(sg.attrs.get('chart_count', 0))
                    deferred_charts = []
                    for ci in range(chart_count):
                        cg = sg[f"chart_{ci}"]
                        series_count = int(
                            cg.attrs['series_count'])
                        series = []
                        for ki in range(series_count):
                            srg = cg[f"series_{ki}"]
                            sd = {
                                "x": list(srg["x"][:]),
                                "y": list(srg["y"][:]),
                                "label": srg.attrs['label'],
                                "plot_type": srg.attrs[
                                    'plot_type'],
                            }
                            # Restore visual / fill properties.
                            props_json = srg.attrs.get(
                                'props', '')
                            if props_json:
                                sd.update(json.loads(props_json))
                            series.append(sd)
                        cd = {
                            "series": series,
                            "pos_x": int(cg.attrs['pos_x']),
                            "pos_y": int(cg.attrs['pos_y']),
                            "width": int(cg.attrs['width']),
                            "height": int(cg.attrs['height']),
                            "title": cg.attrs.get('title', ''),
                            "xlabel": cg.attrs.get(
                                'xlabel', 'X'),
                            "ylabel": cg.attrs.get(
                                'ylabel', 'Y'),
                            "xscale": cg.attrs.get(
                                'xscale', 'linear'),
                            "yscale": cg.attrs.get(
                                'yscale', 'linear'),
                            "grid": bool(cg.attrs.get(
                                'grid', False)),
                            "top_label": cg.attrs.get(
                                'top_label', ''),
                            "right_label": cg.attrs.get(
                                'right_label', ''),
                        }
                        # Legend properties.
                        cd["legend_visible"] = bool(
                            cg.attrs.get('legend_visible', True))
                        lf = cg.attrs.get('legend_font', '')
                        if lf:
                            cd["legend_font"] = (lf.decode('utf-8')
                                                 if isinstance(lf, bytes)
                                                 else lf)
                        cd["legend_size"] = int(
                            cg.attrs.get('legend_size', 8))
                        lp_json = cg.attrs.get('legend_props', '')
                        if isinstance(lp_json, bytes):
                            lp_json = lp_json.decode('utf-8')
                        if lp_json:
                            cd["legend_props"] = json.loads(lp_json)
                        # Axis properties (full dialog state).
                        ap_json = cg.attrs.get('axis_props', '')
                        if ap_json:
                            cd["axis_props"] = json.loads(ap_json)
                        # General (figure-level) properties.
                        gp_json = cg.attrs.get('general_props', '')
                        if isinstance(gp_json, bytes):
                            gp_json = gp_json.decode('utf-8')
                        if gp_json:
                            cd["general_props"] = json.loads(gp_json)
                        # Source column mapping.
                        if 'x_col' in cg.attrs:
                            cd["x_col"] = int(cg.attrs['x_col'])
                        yc_json = cg.attrs.get('y_cols', '')
                        if yc_json:
                            cd["y_cols"] = json.loads(yc_json)
                        deferred_charts.append(cd)
                    if deferred_charts:
                        sheet._deferred_charts = deferred_charts

                    # Collect image data.
                    import base64 as _b64
                    img_count = int(sg.attrs.get('image_count', 0))
                    deferred_images = []
                    for ii in range(img_count):
                        ig_key = f"image_{ii}"
                        if ig_key not in sg:
                            continue
                        ig = sg[ig_key]
                        # Read PNG data — handle both old scalar
                        # datasets and new uint8 array datasets.
                        ds = ig["png_data"]
                        if ds.shape == ():
                            # Scalar dataset (old format).
                            raw_png = bytes(ds[()])
                        else:
                            raw_png = bytes(ds[:])
                        imd = {
                            "pos_x": int(ig.attrs['pos_x']),
                            "pos_y": int(ig.attrs['pos_y']),
                            "width": int(ig.attrs['width']),
                            "height": int(ig.attrs['height']),
                            "data": _b64.b64encode(
                                raw_png).decode("ascii"),
                        }
                        crop_json = ig.attrs.get('crop', '')
                        if crop_json:
                            imd["crop"] = json.loads(crop_json)
                        if 'hue_shift' in ig.attrs:
                            imd["hue_shift"] = int(ig.attrs['hue_shift'])
                        if 'saturation' in ig.attrs:
                            imd["saturation"] = int(
                                ig.attrs['saturation'])
                        if 'brightness' in ig.attrs:
                            imd["brightness"] = int(
                                ig.attrs['brightness'])
                        if 'keep_aspect_ratio' in ig.attrs:
                            imd["keep_aspect_ratio"] = bool(
                                ig.attrs['keep_aspect_ratio'])
                        if 'group_id' in ig.attrs:
                            imd["group_id"] = int(ig.attrs['group_id'])
                        deferred_images.append(imd)
                    if deferred_images:
                        sheet._deferred_images = deferred_images

                    # Collect shape data.
                    shp_count = int(sg.attrs.get('shape_count', 0))
                    deferred_shapes = []
                    for si2 in range(shp_count):
                        shg_key = f"shape_{si2}"
                        if shg_key not in sg:
                            continue
                        sdat = sg[shg_key].attrs.get('data', '')
                        if isinstance(sdat, bytes):
                            sdat = sdat.decode('utf-8')
                        if sdat:
                            deferred_shapes.append(json.loads(sdat))
                    if deferred_shapes:
                        sheet._deferred_shapes = deferred_shapes

                    # Collect equation data.
                    eq_count = int(sg.attrs.get('equation_count', 0))
                    deferred_equations = []
                    for ei2 in range(eq_count):
                        eqg_key = f"equation_{ei2}"
                        if eqg_key not in sg:
                            continue
                        edat = sg[eqg_key].attrs.get('data', '')
                        if isinstance(edat, bytes):
                            edat = edat.decode('utf-8')
                        if edat:
                            deferred_equations.append(json.loads(edat))
                    if deferred_equations:
                        sheet._deferred_equations = deferred_equations

                    # Solver configuration.
                    scfg = sg.attrs.get('solver_config', '')
                    if isinstance(scfg, bytes):
                        scfg = scfg.decode('utf-8')
                    if scfg:
                        sheet._solver_config = json.loads(scfg)

                    # Curve Fitting configuration.
                    fcfg = sg.attrs.get('fit_config', '')
                    if isinstance(fcfg, bytes):
                        fcfg = fcfg.decode('utf-8')
                    if fcfg:
                        cfg = json.loads(fcfg)
                        sheet._fit_config = cfg
                        # Restore custom functions so they're available
                        # the moment the dialog reopens.
                        if cfg.get("custom"):
                            sheet._fit_custom = dict(cfg["custom"])

                wb.tabs.setCurrentIndex(0)
                self.setCentralWidget(wb)
                self._workbook = wb
                self._wire_undo_to_sheets()
                self._workbook.tabs.currentChanged.connect(
                    lambda: self._wire_undo_to_sheets())
                self._undo_stack.clear()

            # Now create charts — workbook is visible and viewports
            # are valid parents for matplotlib canvases.
            from .graph import EmbeddedChart
            for si in range(wb.tabs.count()):
                sheet = wb.tabs.widget(si)
                chart_dicts = getattr(sheet, '_deferred_charts', [])
                if not chart_dicts:
                    continue
                if not hasattr(sheet, '_charts'):
                    sheet._charts = []
                viewport = sheet.table.viewport()
                for cd in chart_dicts:
                    chart = EmbeddedChart.from_dict(
                        cd, sheet, viewport)
                    sheet._charts.append(chart)
                del sheet._deferred_charts

            # Create images.
            from .embedded_image import EmbeddedImage
            for si in range(wb.tabs.count()):
                sheet = wb.tabs.widget(si)
                img_dicts = getattr(sheet, '_deferred_images', [])
                if not img_dicts:
                    continue
                if not hasattr(sheet, '_images'):
                    sheet._images = []
                viewport = sheet.table.viewport()
                for imd in img_dicts:
                    img = EmbeddedImage.from_dict(imd, viewport)
                    sheet._images.append(img)
                del sheet._deferred_images

            # Create shapes.
            from .shapes import EmbeddedShape
            for si in range(wb.tabs.count()):
                sheet = wb.tabs.widget(si)
                shp_dicts = getattr(sheet, '_deferred_shapes', [])
                if not shp_dicts:
                    continue
                if not hasattr(sheet, '_shapes'):
                    sheet._shapes = []
                viewport = sheet.table.viewport()
                for sd in shp_dicts:
                    shp = EmbeddedShape.from_dict(sd, viewport)
                    sheet._shapes.append(shp)
                del sheet._deferred_shapes

            # Create equations.
            from .equation import EmbeddedEquation
            for si in range(wb.tabs.count()):
                sheet = wb.tabs.widget(si)
                eq_dicts = getattr(sheet, '_deferred_equations', [])
                if not eq_dicts:
                    continue
                if not hasattr(sheet, '_equations'):
                    sheet._equations = []
                viewport = sheet.table.viewport()
                for ed in eq_dicts:
                    eqn = EmbeddedEquation.from_dict(ed, viewport)
                    sheet._equations.append(eqn)
                del sheet._deferred_equations

            wb._combined_tab = None
            wb.ensure_layout_tabs()
            if layout_settings:
                wb._combined_tab.apply_settings(layout_settings)

            self._status_msg(
                f"Loaded {path}", 5000)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Load Error", str(e))
        finally:
            self._show_progress(False)

    # ── Recent files ─────────────────────────────────────────────────
    def _add_recent(self, path: str):
        if path in self._recent_files:
            self._recent_files.remove(path)
        self._recent_files.insert(0, path)
        self._recent_files = self._recent_files[:12]
        self._settings.setValue("recent_files", self._recent_files)
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self):
        self._recent_menu.clear()
        for p in self._recent_files:
            act = self._recent_menu.addAction(os.path.basename(p))
            act.setToolTip(p)
            act.triggered.connect(
                lambda _, path=p: self._open_recent(path))
        if not self._recent_files:
            self._recent_menu.addAction("(none)").setEnabled(False)

    def _open_recent(self, path: str):
        if not os.path.exists(path):
            QMessageBox.warning(self, "File Not Found",
                                f"{path} no longer exists.")
            return
        self._open_path(path, add_recent=False)

    # ── Edit operations (proxy to active sheet) ──────────────────────
    def _cut(self):
        s = self._active_sheet()
        if not s:
            return
        from . import shapes as _sh
        from . import equation as _eq
        eqn = self._selected_equation()
        if eqn is not None:
            _eq._equation_clipboard = eqn.to_dict()
            eqn._delete()
            self._status_msg("Equation cut", 2000)
            return
        shp = self._selected_shape()
        if shp is not None:
            _sh._shape_clipboard = shp.to_dict()
            from . import graph as _g
            _g._chart_clipboard = None
            shp._delete()
            self._status_msg("Shape cut", 2000)
            return
        sel = getattr(s, '_selected_chart', None)
        if sel:
            from . import graph as _g
            _g._chart_clipboard = {
                "series": [
                    {"x": sr["x"].tolist(), "y": sr["y"].tolist(),
                     "label": sr["label"], "plot_type": sr["plot_type"]}
                    for sr in sel._series
                ],
            }
            sel._close_chart()
            s._selected_chart = None
        else:
            s._cut_selection()

    def _copy(self):
        s = self._active_sheet()
        if not s:
            return
        from . import shapes as _sh
        from . import equation as _eq
        eqn = self._selected_equation()
        if eqn is not None:
            _eq._equation_clipboard = eqn.to_dict()
            self._status_msg("Equation copied", 2000)
            return
        shp = self._selected_shape()
        if shp is not None:
            _sh._shape_clipboard = shp.to_dict()
            from . import graph as _g
            _g._chart_clipboard = None
            self._status_msg("Shape copied", 2000)
            return
        sel = getattr(s, '_selected_chart', None)
        if sel:
            from . import graph as _g
            _g._chart_clipboard = {
                "series": [
                    {"x": sr["x"].tolist(), "y": sr["y"].tolist(),
                     "label": sr["label"], "plot_type": sr["plot_type"]}
                    for sr in sel._series
                ],
            }
            _sh._shape_clipboard = None
            self._status_msg("Chart copied", 2000)
        else:
            _sh._shape_clipboard = None
            s._copy_selection()

    def _paste(self):
        s = self._active_sheet()
        if not s:
            return
        # Check for chart clipboard first.
        from . import graph as _g
        cb = getattr(_g, '_chart_clipboard', None)
        if cb:
            import numpy as np
            from .graph import EmbeddedChart
            if not hasattr(s, '_charts'):
                s._charts = []
            viewport = s.table.viewport()
            first_chart = None
            for sr in cb["series"]:
                x = np.array(sr["x"])
                y = np.array(sr["y"])
                if first_chart is None:
                    offset = len(s._charts) * 30
                    first_chart = EmbeddedChart(
                        x, y, sr["label"], sr["plot_type"], s, viewport)
                    first_chart.move(60 + offset, 60 + offset)
                    s._charts.append(first_chart)
                else:
                    first_chart.add_series(x, y, sr["label"], sr["plot_type"])
            _g._chart_clipboard = None
            self._status_msg("Chart pasted", 2000)
            return
        # Check for a copied shape.
        from . import shapes as _sh
        sc = getattr(_sh, '_shape_clipboard', None)
        if sc:
            from .shapes import EmbeddedShape, InsertShapeCmd
            if not hasattr(s, '_shapes'):
                s._shapes = []
            viewport = s.table.viewport()
            shape = EmbeddedShape.from_dict(sc, viewport)
            shape.move(int(sc.get("pos_x", 60)) + 20,
                       int(sc.get("pos_y", 60)) + 20)
            shape.show()
            shape.raise_()
            s._shapes.append(shape)
            if self._undo_stack is not None:
                self._undo_stack.push(
                    InsertShapeCmd(s, shape, "Paste Shape"))
            self._status_msg("Shape pasted", 2000)
            return
        # Check for a copied equation.
        from . import equation as _eq
        ec = getattr(_eq, '_equation_clipboard', None)
        if ec:
            from .equation import EmbeddedEquation, InsertEquationCmd
            if not hasattr(s, '_equations'):
                s._equations = []
            viewport = s.table.viewport()
            eqn = EmbeddedEquation.from_dict(ec, viewport)
            eqn.move(int(ec.get("pos_x", 60)) + 20,
                     int(ec.get("pos_y", 60)) + 20)
            eqn.show()
            eqn.raise_()
            s._equations.append(eqn)
            if self._undo_stack is not None:
                self._undo_stack.push(
                    InsertEquationCmd(s, eqn, "Paste Equation"))
            self._status_msg("Equation pasted", 2000)
            return
        # Check for image in system clipboard.
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime and mime.hasImage():
            from PyQt5.QtGui import QPixmap
            pm = QPixmap(clipboard.pixmap())
            if not pm.isNull():
                self._place_image(pm, "Paste Image")
                return
        # Fall back to text paste.
        s._paste_clipboard()

    def _paste_values(self):
        s = self._active_sheet()
        if s:
            s._paste_values_only()

    def _clear(self):
        s = self._active_sheet()
        if not s:
            return
        eqn = self._selected_equation()
        if eqn is not None:
            eqn._delete()
            return
        shp = self._selected_shape()
        if shp is not None:
            shp._delete()
            return
        sel = getattr(s, '_selected_chart', None)
        if sel:
            sel._close_chart()
            s._selected_chart = None
        else:
            s._clear_selection()

    # ── Font / alignment formatting ─────────────────────────────────
    def _selected_items(self):
        """Return all QTableWidgetItems in the current selection."""
        s = self._active_sheet()
        if not s:
            return []
        from PyQt5.QtWidgets import QTableWidgetItem
        items = []
        for rng in s.table.selectedRanges():
            for r in range(rng.topRow(), rng.bottomRow() + 1):
                for c in range(rng.leftColumn(), rng.rightColumn() + 1):
                    it = s.table.item(r, c)
                    if it is None:
                        it = QTableWidgetItem("")
                        s.table.setItem(r, c, it)
                    items.append(it)
        return items

    def _cell_fmt(self, sheet, row, col):
        """Get or create a CellFormat for a cell."""
        from .cellformat import CellFormat
        return sheet._cell_formats.setdefault((row, col), CellFormat())

    def _selected_cell_keys(self):
        """Return list of (row, col) for all selected cells."""
        s = self._active_sheet()
        if not s:
            return []
        keys = []
        for rng in s.table.selectedRanges():
            for r in range(rng.topRow(), rng.bottomRow() + 1):
                for c in range(rng.leftColumn(), rng.rightColumn() + 1):
                    keys.append((r, c))
        if not keys:
            r = s.table.currentRow()
            c = s.table.currentColumn()
            if r >= 0 and c >= 0:
                keys.append((r, c))
        return keys

    def _push_format_undo(self, sheet, keys, label="Format"):
        """Snapshot formats for *keys*, return old_fmts dict.

        Call this BEFORE making changes.  After changes, call
        ``_finish_format_undo`` with the returned old_fmts.
        """
        from .sheet import _snapshot_format
        old = {}
        for k in keys:
            old[k] = _snapshot_format(sheet._cell_formats.get(k))
        return old

    def _finish_format_undo(self, sheet, old_fmts, label="Format"):
        """Push undo command by comparing *old_fmts* to current state."""
        from .sheet import _snapshot_format, FormatCellsCmd
        new_fmts = {}
        for k in old_fmts:
            new_fmts[k] = _snapshot_format(sheet._cell_formats.get(k))
        if self._undo_stack is not None:
            self._undo_stack.push(
                FormatCellsCmd(sheet, old_fmts, new_fmts, label))

    def _apply_font_family(self, font):
        s = self._active_sheet()
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys) if s else None
        if s:
            s.table.blockSignals(True)
        for it in self._selected_items():
            f = it.font()
            f.setFamily(font.family())
            it.setFont(f)
            if s:
                r, c = it.row(), it.column()
                self._cell_fmt(s, r, c).font_family = font.family()
        if s:
            s.table.blockSignals(False)
        if s and old:
            self._finish_format_undo(s, old, "Font Family")

    def _apply_font_size(self, size_text):
        try:
            size = float(size_text)
        except ValueError:
            return
        if size < 1:
            return
        s = self._active_sheet()
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys) if s else None
        if s:
            s.table.blockSignals(True)
        for it in self._selected_items():
            f = it.font()
            f.setPointSizeF(size)
            it.setFont(f)
            if s:
                r, c = it.row(), it.column()
                self._cell_fmt(s, r, c).font_size = size
        if s:
            s.table.blockSignals(False)
        if s and old:
            self._finish_format_undo(s, old, "Font Size")

    def _toggle_bold(self):
        checked = self._bold_act.isChecked()
        ov = self._selected_overlay()
        if ov is not None and hasattr(ov, "set_text_format"):
            ov.set_text_format(bold=checked, label="Bold")
            return
        s = self._active_sheet()
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys) if s else None
        if s:
            s.table.blockSignals(True)
        for it in self._selected_items():
            f = it.font()
            f.setBold(checked)
            it.setFont(f)
            if s:
                r, c = it.row(), it.column()
                self._cell_fmt(s, r, c).bold = checked
        if s:
            s.table.blockSignals(False)
        if s and old:
            self._finish_format_undo(s, old, "Bold")

    def _toggle_italic(self):
        checked = self._italic_act.isChecked()
        ov = self._selected_overlay()
        if ov is not None and hasattr(ov, "set_text_format"):
            ov.set_text_format(italic=checked, label="Italic")
            return
        s = self._active_sheet()
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys) if s else None
        if s:
            s.table.blockSignals(True)
        for it in self._selected_items():
            f = it.font()
            f.setItalic(checked)
            it.setFont(f)
            if s:
                r, c = it.row(), it.column()
                self._cell_fmt(s, r, c).italic = checked
        if s:
            s.table.blockSignals(False)
        if s and old:
            self._finish_format_undo(s, old, "Italic")

    def _toggle_underline(self):
        checked = self._underline_act.isChecked()
        ov = self._selected_overlay()
        if ov is not None and hasattr(ov, "set_text_format"):
            ov.set_text_format(underline=checked, label="Underline")
            return
        s = self._active_sheet()
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys) if s else None
        if s:
            s.table.blockSignals(True)
        for it in self._selected_items():
            f = it.font()
            f.setUnderline(checked)
            it.setFont(f)
            if s:
                r, c = it.row(), it.column()
                self._cell_fmt(s, r, c).underline = checked
        if s:
            s.table.blockSignals(False)
        if s and old:
            self._finish_format_undo(s, old, "Underline")

    def _apply_alignment(self, alignment):
        # Update toggle state — only one alignment active at a time.
        self._align_left_act.setChecked(
            alignment & Qt.AlignLeft and not alignment & Qt.AlignHCenter)
        self._align_center_act.setChecked(bool(alignment & Qt.AlignHCenter))
        self._align_right_act.setChecked(bool(alignment & Qt.AlignRight))
        ov = self._selected_overlay()
        if ov is not None and hasattr(ov, "set_text_format"):
            ov.set_text_format(align=int(alignment), label="Alignment")
            return
        s = self._active_sheet()
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys) if s else None
        if s:
            s.table.blockSignals(True)
        for it in self._selected_items():
            it.setTextAlignment(int(alignment))
            if s:
                r, c = it.row(), it.column()
                self._cell_fmt(s, r, c).alignment = int(alignment)
        if s:
            s.table.blockSignals(False)
        if s and old:
            self._finish_format_undo(s, old, "Alignment")

    # ── Colour palette ────────────────────────────────────────────────
    _PALETTE = [
        # Row 1 — theme colours.
        "#000000", "#ffffff", "#e7e6e6", "#44546a",
        "#4472c4", "#ed7d31", "#a5a5a5", "#ffc000",
        "#5b9bd5", "#70ad47",
        # Row 2-6 — tints.
        "#808080", "#f2f2f2", "#d0cece", "#d6dce4",
        "#d9e2f3", "#fbe5d6", "#ededed", "#fff2cc",
        "#deebf7", "#e2efda",
        "#595959", "#d9d9d9", "#aeaaaa", "#adb9ca",
        "#b4c7e7", "#f8cbad", "#dbdbdb", "#ffe599",
        "#bdd7ee", "#c5e0b4",
        "#404040", "#bfbfbf", "#757171", "#8497b0",
        "#8faadc", "#f4b183", "#c9c9c9", "#ffd966",
        "#9dc3e6", "#a9d18e",
        "#262626", "#a6a6a6", "#3b3838", "#333f50",
        "#2f5597", "#c55a11", "#7b7b7b", "#bf9000",
        "#2e75b6", "#538135",
        "#0d0d0d", "#7f7f7f", "#171616", "#222b35",
        "#1f3864", "#843c0c", "#525252", "#7f6000",
        "#1f4e79", "#385723",
        # Row 7 — standard colours.
        "#c00000", "#ff0000", "#ffc000", "#ffff00",
        "#92d050", "#00b050", "#00b0f0", "#0070c0",
        "#002060", "#7030a0",
    ]

    def _build_color_palette(self, parent_menu, callback):
        """Return a QWidgetAction containing a grid of colour swatches."""
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(2)
        grid.setContentsMargins(4, 4, 4, 4)
        cols = 10
        for i, color in enumerate(self._PALETTE):
            btn = QPushButton()
            btn.setFixedSize(18, 18)
            btn.setStyleSheet(
                f"background:{color}; border:1px solid #888;"
                f"border-radius:0px;")
            btn.setToolTip(color)
            btn.clicked.connect(
                lambda _, c=color: callback(c))
            grid.addWidget(btn, i // cols, i % cols)
        wa = QWidgetAction(parent_menu)
        wa.setDefaultWidget(container)
        return wa

    def _ensure_fill_palette(self):
        if self._fill_menu_built:
            return
        self._fill_menu_built = True
        self._fill_menu.addAction(
            self._build_color_palette(self._fill_menu,
                                      self._on_fill_palette))
        self._fill_menu.addSeparator()
        self._fill_menu.addAction("No Fill", self._clear_fill_color)
        self._fill_menu.addAction("Choose Color\u2026",
                                  self._pick_fill_color)

    def _ensure_font_palette(self):
        if self._fc_menu_built:
            return
        self._fc_menu_built = True
        self._fc_menu.addAction(
            self._build_color_palette(self._fc_menu,
                                      self._on_font_palette))
        self._fc_menu.addSeparator()
        self._fc_menu.addAction("Choose Color\u2026",
                                self._pick_font_color)

    def _on_fill_palette(self, color):
        self._last_fill_color = color
        self._fill_btn.setIcon(icons.fill_color_icon(28, color))
        self._apply_fill_color(color)
        self._fill_btn.menu().close()

    def _on_font_palette(self, color):
        self._last_font_color = color
        self._font_color_btn.setIcon(icons.font_color_icon(28, color))
        self._apply_font_color(color)
        self._font_color_btn.menu().close()

    # ── Fill colour ─────────────────────────────────────────────────
    def _apply_last_fill_color(self):
        self._apply_fill_color(self._last_fill_color)

    def _pick_fill_color(self):
        from PyQt5.QtWidgets import QColorDialog
        dlg = QColorDialog(QColor(self._last_fill_color), self)
        dlg.setStyleSheet("")
        if dlg.exec_() == QColorDialog.Accepted:
            c = dlg.currentColor().name()
            self._last_fill_color = c
            self._fill_btn.setIcon(
                icons.fill_color_icon(28, c))
            self._apply_fill_color(c)

    def _apply_fill_color(self, color_hex):
        s = self._active_sheet()
        if not s:
            return
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys)
        for rng in s.table.selectedRanges():
            for r in range(rng.topRow(), rng.bottomRow() + 1):
                for c in range(rng.leftColumn(),
                               rng.rightColumn() + 1):
                    s.set_cell_bg(r, c, color_hex)
        self._finish_format_undo(s, old, "Fill Color")

    def _clear_fill_color(self):
        s = self._active_sheet()
        if not s:
            return
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys)
        for rng in s.table.selectedRanges():
            for r in range(rng.topRow(), rng.bottomRow() + 1):
                for c in range(rng.leftColumn(),
                               rng.rightColumn() + 1):
                    s.set_cell_bg(r, c, None)
        self._finish_format_undo(s, old, "Clear Fill")

    # ── Font colour ──────────────────────────────────────────────────
    def _apply_last_font_color(self):
        self._apply_font_color(self._last_font_color)

    def _pick_font_color(self):
        from PyQt5.QtWidgets import QColorDialog
        dlg = QColorDialog(QColor(self._last_font_color), self)
        dlg.setStyleSheet("")
        if dlg.exec_() == QColorDialog.Accepted:
            c = dlg.currentColor().name()
            self._last_font_color = c
            self._font_color_btn.setIcon(
                icons.font_color_icon(28, c))
            self._apply_font_color(c)

    def _apply_font_color(self, color_hex):
        s = self._active_sheet()
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys) if s else None
        for it in self._selected_items():
            it.setForeground(QColor(color_hex))
            if s:
                r, c = it.row(), it.column()
                self._cell_fmt(s, r, c).font_color = color_hex
        if s and old:
            self._finish_format_undo(s, old, "Font Color")

    # ── Borders ──────────────────────────────────────────────────────
    _BORDER_PRESETS = [
        ("Bottom Border",              "bottom"),
        ("Top Border",                 "top"),
        ("Left Border",                "left"),
        ("Right Border",               "right"),
        ("No Border",                  "none"),
        None,  # separator
        ("All Borders",                "all"),
        ("Outside Borders",            "outside"),
        ("Thick Outside Borders",      "thick_outside"),
        None,
        ("Bottom Double Border",       "bottom_double"),
        ("Thick Bottom Border",        "thick_bottom"),
        ("Top and Bottom Border",      "top_bottom"),
        ("Top and Thick Bottom Border", "top_thick_bottom"),
        ("Top and Double Bottom Border", "top_double_bottom"),
    ]

    def _build_border_menu(self, parent):
        """Build and return a QMenu with all border presets and icons."""
        menu = QMenu(parent)
        for item in self._BORDER_PRESETS:
            if item is None:
                menu.addSeparator()
            else:
                label, preset = item
                act = menu.addAction(
                    icons.border_preset_icon(preset, 20), label)
                act.triggered.connect(
                    lambda _, p=preset: self._apply_border_preset(p))
        return menu

    def _apply_border_preset(self, preset):
        """Apply a border preset to the current selection."""
        from .cellformat import BorderSpec
        s = self._active_sheet()
        if not s:
            return

        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys)

        thin = BorderSpec()              # solid black 1px
        thick = BorderSpec(width=2.0)     # solid black 2px
        double = BorderSpec(style=Qt.DashLine)  # approx double

        for rng in s.table.selectedRanges():
            top_r = rng.topRow()
            bot_r = rng.bottomRow()
            left_c = rng.leftColumn()
            right_c = rng.rightColumn()

            for r in range(top_r, bot_r + 1):
                for c in range(left_c, right_c + 1):
                    sides = {}

                    if preset == "all":
                        sides = {"top": thin, "bottom": thin,
                                 "left": thin, "right": thin}

                    elif preset == "outside":
                        if r == top_r:  sides["top"] = thin
                        if r == bot_r:  sides["bottom"] = thin
                        if c == left_c: sides["left"] = thin
                        if c == right_c: sides["right"] = thin

                    elif preset == "thick_outside":
                        if r == top_r:  sides["top"] = thick
                        if r == bot_r:  sides["bottom"] = thick
                        if c == left_c: sides["left"] = thick
                        if c == right_c: sides["right"] = thick

                    elif preset == "none":
                        sides = {"top": None, "bottom": None,
                                 "left": None, "right": None}

                    elif preset == "bottom_double":
                        if r == bot_r:
                            sides["bottom"] = double

                    elif preset == "thick_bottom":
                        if r == bot_r:
                            sides["bottom"] = thick

                    elif preset == "top_bottom":
                        if r == top_r:  sides["top"] = thin
                        if r == bot_r:  sides["bottom"] = thin

                    elif preset == "top_thick_bottom":
                        if r == top_r:  sides["top"] = thin
                        if r == bot_r:  sides["bottom"] = thick

                    elif preset == "top_double_bottom":
                        if r == top_r:  sides["top"] = thin
                        if r == bot_r:  sides["bottom"] = double

                    elif preset in ("top", "bottom", "left", "right"):
                        sides[preset] = thin

                    if sides:
                        s.set_cell_borders(r, c, sides)

        self._finish_format_undo(s, old, f"Border: {preset}")

    def _update_format_toolbar(self):
        """Sync toolbar widgets with the current cell's formatting."""
        s = self._active_sheet()
        if not s:
            return
        r = s.table.currentRow()
        c = s.table.currentColumn()
        if r < 0 or c < 0:
            return
        it = s.table.item(r, c)
        if it is None:
            return
        f = it.font()

        # Block signals to avoid re-triggering formatting.
        self._font_combo.blockSignals(True)
        self._font_combo.setCurrentFont(f)
        self._font_combo.blockSignals(False)

        self._font_size.blockSignals(True)
        self._font_size.setCurrentText(str(int(f.pointSize()))
                                       if f.pointSize() > 0 else "9")
        self._font_size.blockSignals(False)

        self._bold_act.setChecked(f.bold())
        self._italic_act.setChecked(f.italic())
        self._underline_act.setChecked(f.underline())

        align = it.textAlignment()
        self._align_left_act.setChecked(
            bool(align & Qt.AlignLeft) and not bool(align & Qt.AlignHCenter))
        self._align_center_act.setChecked(bool(align & Qt.AlignHCenter))
        self._align_right_act.setChecked(bool(align & Qt.AlignRight))

    # ── Theme ────────────────────────────────────────────────────────
    def _apply_theme(self, name):
        from .app import apply_theme
        apply_theme(QApplication.instance(), name)
        # Persist the choice so it's restored on next launch.
        from PyQt5.QtCore import QSettings
        QSettings("KherveSheet", "KherveSheet").setValue("theme", name)
        self._refresh_toolbar_icons()

    def _refresh_toolbar_icons(self):
        """Rebuild format toolbar icons so they match the current theme."""
        self._bold_act.setIcon(icons.bold_icon(28))
        self._italic_act.setIcon(icons.italic_icon(28))
        self._underline_act.setIcon(icons.underline_icon(28))
        self._align_left_act.setIcon(icons.align_left_icon(28))
        self._align_center_act.setIcon(icons.align_center_icon(28))
        self._align_right_act.setIcon(icons.align_right_icon(28))

    # ── Version control ─────────────────────────────────────────────
    def _vc_repo_dir(self):
        """Return the per-document version repo directory.

        Each .ksheet file gets its own isolated git repo at
        ``<file_dir>/.ksheet_versions/<stem>/`` so document history
        is never mixed with the application's source repo.
        """
        if self._current_file:
            from pathlib import Path
            p = Path(self._current_file)
            return p.parent / ".ksheet_versions" / p.stem
        return None

    def _open_history(self):
        from . import git_backend
        repo_dir = self._vc_repo_dir()
        if not repo_dir:
            QMessageBox.information(
                self, "No File",
                "Save the file first to enable version history.")
            return
        if not git_backend.is_available():
            QMessageBox.warning(
                self, "Missing Library",
                "pygit2 is required for version history.\n"
                "Install with: pip install pygit2")
            return
        from pathlib import Path
        from .history_dialog import HistoryDialog
        stem = Path(self._current_file).stem
        dlg = HistoryDialog(repo_dir, parent=self, file_stem=stem)
        dlg.exec_()

    def _vc_push(self):
        from . import git_backend
        repo_dir = self._vc_repo_dir()
        if not repo_dir:
            QMessageBox.information(self, "No File", "Save first.")
            return
        if not git_backend.is_available():
            QMessageBox.warning(self, "Missing Library",
                                "pygit2 is required.")
            return
        ok, msg = git_backend.push(repo_dir)
        if ok:
            self._status_msg(msg, 5000)
        else:
            QMessageBox.warning(self, "Push failed", msg)

    def _vc_pull(self):
        from . import git_backend
        repo_dir = self._vc_repo_dir()
        if not repo_dir:
            QMessageBox.information(self, "No File", "Save first.")
            return
        if not git_backend.is_available():
            QMessageBox.warning(self, "Missing Library",
                                "pygit2 is required.")
            return
        ok, msg = git_backend.pull(repo_dir)
        if ok:
            self._status_msg(msg, 5000)
            # Reload the file after pull.
            if self._current_file:
                self._load_ksheet(self._current_file)
        else:
            QMessageBox.warning(self, "Pull failed", msg)

    def _vc_configure_remote(self):
        from . import git_backend
        repo_dir = self._vc_repo_dir()
        if not repo_dir:
            QMessageBox.information(self, "No File", "Save first.")
            return
        if not git_backend.is_available():
            QMessageBox.warning(self, "Missing Library",
                                "pygit2 is required.")
            return
        remotes = git_backend.get_remotes(repo_dir)
        current_url = ""
        for name, url in remotes:
            if name == "origin":
                current_url = url
                break
        from PyQt5.QtWidgets import QInputDialog
        url, ok = QInputDialog.getText(
            self, "Configure Remote",
            "Remote URL (origin):", text=current_url)
        if ok and url.strip():
            git_backend.set_remote(repo_dir, "origin", url.strip())
            self._status_msg("Remote 'origin' configured.", 3000)

    def _reload_current(self):
        """Reload the current .ksheet file from disk (after restore).

        After a version restore, the file lives in the version repo dir;
        copy it back to the original location before reloading.
        """
        if not self._current_file or not self._current_file.endswith(
                ".ksheet"):
            return
        import shutil
        from pathlib import Path
        p = Path(self._current_file)
        repo_copy = p.parent / ".ksheet_versions" / p.stem / p.name
        if repo_copy.exists():
            shutil.copy2(str(repo_copy), str(p))
        self._load_ksheet(self._current_file)

    # ── Zoom ─────────────────────────────────────────────────────────
    def _zoom_in(self):
        v = min(200, self._zoom_slider.value() + 10)
        self._zoom_slider.setValue(v)

    def _zoom_out(self):
        v = max(1, self._zoom_slider.value() - 10)
        self._zoom_slider.setValue(v)

    def _zoom_reset(self):
        self._zoom_slider.setValue(100)

    def _apply_zoom(self, value):
        self._zoom_label.setText(f"{value}%")
        sheet = self._active_sheet()
        if not sheet:
            return
        factor = value / 100.0
        old_factor = getattr(sheet, '_zoom_factor', 1.0)

        # Scale row/column sizes proportionally.  Clamp to >=1px so
        # extreme zoom-out (down to 1%) never collapses rows/cols to
        # zero height and leaves the grid invisible.
        base_row = 20
        base_col = 80
        row_sz = max(1, int(round(base_row * factor)))
        col_sz = max(1, int(round(base_col * factor)))
        vh = sheet.table.verticalHeader()
        hh = sheet.table.horizontalHeader()
        # The minimum section size would otherwise clamp the default and
        # stop the grid shrinking below 16/40px; lower it when zoomed out
        # so 1% really zooms out, but keep the normal floor at 100%+.
        vh.setMinimumSectionSize(min(16, row_sz))
        hh.setMinimumSectionSize(min(40, col_sz))
        vh.setDefaultSectionSize(row_sz)
        hh.setDefaultSectionSize(col_sz)
        font = sheet.table.font()
        font.setPointSizeF(max(1.0, 9 * factor))
        sheet.table.setFont(font)

        # Scale charts and images proportionally.
        if old_factor != factor:
            ratio = factor / old_factor
            for chart in getattr(sheet, '_charts', []):
                pos = chart.pos()
                chart.move(int(pos.x() * ratio),
                           int(pos.y() * ratio))
                chart.resize(int(chart.width() * ratio),
                             int(chart.height() * ratio))
            for img in getattr(sheet, '_images', []):
                pos = img.pos()
                img.move(int(pos.x() * ratio),
                         int(pos.y() * ratio))
                img.resize(int(img.width() * ratio),
                           int(img.height() * ratio))
            for shp in getattr(sheet, '_shapes', []):
                pos = shp.pos()
                shp.move(int(pos.x() * ratio),
                         int(pos.y() * ratio))
                shp.resize(int(shp.width() * ratio),
                           int(shp.height() * ratio))

        sheet._zoom_factor = factor

        # Zooming out shrinks columns; top up so the grid stays filled.
        if hasattr(sheet, "_ensure_columns_fill_viewport"):
            sheet._ensure_columns_fill_viewport()

    # ── Bring forward / send backward ────────────────────────────────
    def _selected_shape(self):
        """Return the currently selected EmbeddedShape, if any."""
        s = self._active_sheet()
        if not s:
            return None
        for shp in getattr(s, '_shapes', []):
            if getattr(shp, '_selected', False):
                return shp
        return None

    def _selected_overlay(self):
        """Return the currently selected chart or image widget, if any."""
        s = self._active_sheet()
        if not s:
            return None
        for chart in getattr(s, '_charts', []):
            if getattr(chart, '_selected', False):
                return chart
        for img in getattr(s, '_images', []):
            if getattr(img, '_selected', False):
                return img
        for shp in getattr(s, '_shapes', []):
            if getattr(shp, '_selected', False):
                return shp
        for eq in getattr(s, '_equations', []):
            if getattr(eq, '_selected', False):
                return eq
        return None

    def _selected_equation(self):
        """Return the currently selected EmbeddedEquation, if any."""
        s = self._active_sheet()
        if not s:
            return None
        for eq in getattr(s, '_equations', []):
            if getattr(eq, '_selected', False):
                return eq
        return None

    def _bring_forward(self):
        w = self._selected_overlay()
        if w:
            w.raise_()

    def _send_backward(self):
        w = self._selected_overlay()
        if w:
            w.lower()

    # ── Insert operations ────────────────────────────────────────────
    def _insert_row_above(self):
        s = self._active_sheet()
        if s:
            s._insert_row_above()

    def _insert_row_below(self):
        s = self._active_sheet()
        if s:
            s._insert_row_below()

    def _insert_column(self):
        s = self._active_sheet()
        if s:
            col = s.table.currentColumn()
            if col < 0:
                col = s.column_count()
            s._insert_column(col)

    def _insert_chart(self, plot_type: str):
        self.plot_from_sheet(self._active_sheet(), plot_type)

    def _plot_from_menu(self, plot_type: str):
        """Insert chart and remember last-used type for the button."""
        self._last_plot_type = plot_type
        fn = self._plot_icon_fns.get(plot_type)
        if fn:
            self._plot_btn.setIcon(fn(28))
        self._insert_chart(plot_type)

    def _build_symbol_grid(self, parent_menu):
        """Build a grid widget with symbol buttons for insertion."""
        greek = list("αβγδεζηθικλμνξπρστυφχψω"
                     "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΠΡΣΤΥΦΧΨΩ")
        math_syms = list("±×÷√∞≠≤≥≈∑∏∫∂∇°′″")
        arrows = list("←→↑↓↔⇐⇒⇑⇓⇔")
        all_syms = greek + math_syms + arrows

        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(1)
        grid.setContentsMargins(4, 4, 4, 4)
        cols = 10
        for i, sym in enumerate(all_syms):
            btn = QPushButton(sym)
            btn.setFixedSize(28, 28)
            btn.setStyleSheet("font-size: 14px;")
            btn.clicked.connect(
                lambda checked, s=sym, m=parent_menu:
                    self._insert_symbol(s, m))
            grid.addWidget(btn, i // cols, i % cols)
        return container

    def _insert_symbol(self, symbol: str, menu):
        """Insert a symbol character into the current cell."""
        menu.close()
        sheet = self._active_sheet()
        if not sheet:
            return
        row = sheet.table.currentRow()
        col = sheet.table.currentColumn()
        if row < 0 or col < 0:
            return
        from PyQt5.QtWidgets import QTableWidgetItem
        it = sheet.table.item(row, col)
        old = it.text() if it else ""
        new_val = old + symbol
        if it is None:
            it = QTableWidgetItem(new_val)
            sheet.table.setItem(row, col, it)
        else:
            it.setText(new_val)
        sheet._shadow[(row, col)] = new_val
        if sheet._undo_stack is not None:
            from .sheet import CellEditCmd
            sheet._undo_stack.push(
                CellEditCmd(sheet, row, col, old, new_val))

    def _insert_emoji(self, emoji, menu):
        """Insert an emoji character into the current cell."""
        menu.close()
        self._insert_symbol(emoji, menu)

    def _insert_checkbox(self):
        s = self._active_sheet()
        if s:
            from . import insert_ops
            insert_ops.insert_checkbox(s)

    def _insert_dropdown(self):
        s = self._active_sheet()
        if s:
            from . import insert_ops
            insert_ops.insert_dropdown(s, self)

    def _insert_link(self):
        s = self._active_sheet()
        if s:
            from . import insert_ops
            insert_ops.insert_link(s, self)

    def _insert_comment(self):
        s = self._active_sheet()
        if s:
            from . import insert_ops
            insert_ops.insert_comment(s, self)

    def _insert_note(self):
        s = self._active_sheet()
        if s:
            from . import insert_ops
            insert_ops.insert_note(s, self)

    def _transpose_selection(self):
        s = self._active_sheet()
        if s:
            from . import insert_ops
            insert_ops.transpose_selection(s, self._undo_stack)

    def _spell_check(self):
        s = self._active_sheet()
        if not s:
            return
        from .insert_ops import SpellCheckDialog
        dlg = SpellCheckDialog(s, self)
        dlg.exec_()

    def _toggle_live_spell(self, enabled):
        """Enable/disable live red-underline spell-checking on all sheets."""
        for s in self._workbook.all_sheets():
            d = getattr(s, "_fmt_delegate", None)
            if d is not None:
                d._spell_enabled = enabled
                s.table.viewport().update()

    def _apply_live_spell_to(self, sheet):
        """Push the current live-spell setting onto one sheet."""
        d = getattr(sheet, "_fmt_delegate", None)
        if d is not None and hasattr(self, "_spell_live_act"):
            d._spell_enabled = self._spell_live_act.isChecked()

    def _toggle_merge(self):
        """Toggle merge/unmerge on the active sheet selection."""
        sheet = self._active_sheet()
        if not sheet:
            return
        sel = sheet.table.selectedRanges()
        if not sel:
            return
        rng = sel[0]
        # Check if already merged at this position
        r, c = rng.topRow(), rng.leftColumn()
        is_merged = False
        for (mr, mc, rs, cs) in sheet._merged_ranges:
            if mr == r and mc == c:
                is_merged = True
                break
        if is_merged:
            sheet.unmerge_selection()
        else:
            sheet.merge_selection()

    # ── Plot from sheet ──────────────────────────────────────────────
    def plot_from_sheet(self, sheet: SheetWidget, plot_type: str):
        """Create an embedded chart from selected columns."""
        if not sheet:
            return
        sel = sheet.table.selectedRanges()
        if not sel:
            QMessageBox.information(
                self, "No Selection",
                "Select columns to plot first.")
            return
        s = sel[0]
        cols = list(range(s.leftColumn(), s.rightColumn() + 1))
        if len(cols) < 1:
            return

        import numpy as np
        from .graph import EmbeddedChart
        if not hasattr(sheet, '_charts'):
            sheet._charts = []

        # ── Heatmap / 3D Surface: read selection as 2D matrix ────
        if plot_type in ("Heatmap", "3D Surface"):
            rows = list(range(s.topRow(), s.bottomRow() + 1))
            matrix = np.full((len(rows), len(cols)), np.nan)
            for ri, r in enumerate(rows):
                for ci, c in enumerate(cols):
                    it = sheet.table.item(r, c)
                    if it:
                        try:
                            matrix[ri, ci] = float(it.text())
                        except (ValueError, TypeError):
                            pass
            # Remove all-nan rows/cols
            mask_r = ~np.all(np.isnan(matrix), axis=1)
            mask_c = ~np.all(np.isnan(matrix), axis=0)
            matrix = matrix[np.ix_(mask_r, mask_c)]
            if matrix.size == 0:
                QMessageBox.information(
                    self, "No Data",
                    "Selected range contains no numeric data.")
                return
            # Replace remaining NaN with 0 for plotting
            matrix = np.nan_to_num(matrix, nan=0.0)
            # x is dummy (unused for these types); y is the matrix
            x_dummy = np.arange(matrix.shape[1], dtype=float)
            viewport = sheet.table.viewport()
            chart = EmbeddedChart(
                x_dummy, matrix, "Data", plot_type, sheet, viewport)
            offset = len(sheet._charts) * 30
            chart.move(40 + offset, 40 + offset)
            sheet._charts.append(chart)
            sheet.data_changed.connect(chart._on_data_changed)
            self._status_msg(f"Created {plot_type} chart", 3000)
            return

        # ── Standard 1D plot types ───────────────────────────────
        # Separate selected columns into Y columns (to plot) and
        # determine each Y column's X source: the nearest X-designated
        # column to its left (scanning all sheet columns, not just the
        # selection).
        y_cols = []
        for c in cols:
            if sheet.get_designation(c) != "X":
                y_cols.append(c)

        # If no Y columns found (all selected are X), treat all but
        # the first as Y.
        if not y_cols and len(cols) >= 2:
            y_cols = cols[1:]

        # Single column with no X to its left: plot against row index.
        def _find_x_for(y_col):
            """Return the nearest X-designated column to the left of
            *y_col*, or None if there is none."""
            for c in range(y_col - 1, -1, -1):
                if sheet.get_designation(c) == "X":
                    return c
            return None

        # Build one chart with all Y columns as series
        first_chart = None
        row_start = s.topRow()
        row_end = s.bottomRow()
        for yc in y_cols:
            x_col = _find_x_for(yc)
            if x_col is not None:
                x_data = sheet.numeric_column(x_col)[row_start:row_end + 1]
            else:
                x_data = np.arange(row_end - row_start + 1, dtype=float)

            y_data = sheet.numeric_column(yc)[row_start:row_end + 1]
            label = col_index_to_letter(yc)

            mask = ~(np.isnan(x_data) | np.isnan(y_data))
            x = x_data[mask]
            y = y_data[mask]
            if len(x) == 0:
                continue

            if first_chart is None:
                # Place chart on the table viewport so it overlays
                # the grid cells, just like Excel.
                viewport = sheet.table.viewport()
                chart = EmbeddedChart(
                    x, y, label, plot_type, sheet, viewport,
                    x_col=x_col, y_col=yc,
                    row_start=s.topRow(), row_end=s.bottomRow())
                # Position at a visible spot, offset by existing charts.
                offset = len(sheet._charts) * 30
                chart.move(40 + offset, 40 + offset)
                sheet._charts.append(chart)
                # Connect data change signal for live updates.
                sheet.data_changed.connect(chart._on_data_changed)
                first_chart = chart
            else:
                first_chart.add_series(x, y, label, plot_type,
                                       x_col=x_col, y_col=yc,
                                       row_start=s.topRow(),
                                       row_end=s.bottomRow())

        self._status_msg(
            f"Created {plot_type} chart", 3000)

    # ── Insert image ─────────────────────────────────────────────────

    def _insert_sparkline(self):
        sheet = self._active_sheet()
        if not sheet:
            return
        from .insert_ops import insert_sparkline
        insert_sparkline(sheet)

    def _remove_sparkline(self):
        sheet = self._active_sheet()
        if not sheet:
            return
        from .insert_ops import remove_sparklines
        remove_sparklines(sheet)

    def _insert_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Insert Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.svg);;All Files (*)")
        if not path:
            return
        from PyQt5.QtGui import QPixmap
        pm = QPixmap(path)
        if pm.isNull():
            QMessageBox.warning(self, "Image Error",
                                f"Could not load image:\n{path}")
            return
        self._place_image(pm, "Insert Image")

    def _place_image(self, pm, label="Insert Image"):
        """Create an EmbeddedImage on the active sheet (undoable)."""
        sheet = self._active_sheet()
        if not sheet:
            return
        from .embedded_image import EmbeddedImage, InsertImageCmd
        viewport = sheet.table.viewport()
        img = EmbeddedImage(pm, viewport)
        offset = len(getattr(sheet, '_images', [])) * 30
        img.move(40 + offset, 40 + offset)
        if not hasattr(sheet, '_images'):
            sheet._images = []
        sheet._images.append(img)
        if self._undo_stack is not None:
            self._undo_stack.push(InsertImageCmd(sheet, img, label))
        self._status_msg(label, 3000)

    def _make_shape_gallery(self):
        """A drop-down gallery of every shape, grouped by category in a
        multi-column icon grid (Excel-style)."""
        from .shape_gallery import ShapeGalleryMenu
        return ShapeGalleryMenu(self._insert_shape, self)

    def _insert_shape(self, shape_type="rectangle"):
        """Create an EmbeddedShape on the active sheet (undoable)."""
        sheet = self._active_sheet()
        if not sheet:
            return
        from .shapes import EmbeddedShape, InsertShapeCmd
        viewport = sheet.table.viewport()
        shape = EmbeddedShape(shape_type, viewport)
        if not hasattr(sheet, '_shapes'):
            sheet._shapes = []
        offset = len(sheet._shapes) * 24
        shape.move(60 + offset, 60 + offset)
        sheet._shapes.append(shape)
        if self._undo_stack is not None:
            self._undo_stack.push(
                InsertShapeCmd(sheet, shape, "Insert Shape"))
        self._status_msg("Insert Shape", 3000)

    def _make_equation_gallery(self):
        """A drop-down gallery of preset equations plus a 'new' entry."""
        from .equation import EquationGalleryMenu
        return EquationGalleryMenu(self._insert_equation, self)

    def _insert_equation(self, latex=None):
        """Create an EmbeddedEquation on the active sheet (undoable).

        ``latex`` None opens the editor for a fresh equation; a string
        inserts that preset directly.
        """
        sheet = self._active_sheet()
        if not sheet:
            return
        from .equation import (
            EmbeddedEquation, EquationDialog, InsertEquationCmd)
        if latex is None:
            dlg = EquationDialog(parent=self)
            if dlg.exec_() != QDialog.Accepted or not dlg.latex.strip():
                return
            eq = EmbeddedEquation(dlg.latex, dlg.fontsize, dlg.color,
                                  sheet.table.viewport())
        else:
            eq = EmbeddedEquation(latex, 20, "#000000",
                                  sheet.table.viewport())
        if not hasattr(sheet, '_equations'):
            sheet._equations = []
        offset = len(sheet._equations) * 24
        eq.move(60 + offset, 60 + offset)
        sheet._equations.append(eq)
        if self._undo_stack is not None:
            self._undo_stack.push(
                InsertEquationCmd(sheet, eq, "Insert Equation"))
        self._status_msg("Insert Equation", 3000)

    # ── Format operations ────────────────────────────────────────────
    def _set_number_format(self, fmt: str):
        s = self._active_sheet()
        if not s:
            return
        sel = s.table.selectedRanges()
        if not sel:
            return
        from .sheet import SetNumberFormatCmd
        changes = []
        for rng in sel:
            for c in range(rng.leftColumn(), rng.rightColumn() + 1):
                old_fmt = s._col_formats.get(c)
                s._col_formats[c] = fmt
                changes.append((c, old_fmt, fmt))
        if changes and self._undo_stack is not None:
            self._undo_stack.push(
                SetNumberFormatCmd(s, changes, "Number Format"))

    def _format_col_width(self):
        s = self._active_sheet()
        if not s:
            return
        col = s.table.currentColumn()
        if col >= 0:
            s._set_column_width(col)

    def _format_row_height(self):
        s = self._active_sheet()
        if not s:
            return
        cur = s.table.verticalHeader().defaultSectionSize()
        h, ok = QInputDialog.getInt(
            self, "Row Height", "Height (pixels):", cur, 10, 100)
        if ok:
            s.table.verticalHeader().setDefaultSectionSize(h)

    # ── Table Design (inline menu gallery) ──────────────────────────
    def _build_table_design_menu(self):
        """Populate the Table Design submenu with style thumbnails."""
        from .table_styles import BUILTIN_STYLES, _render_thumbnail
        from PyQt5.QtWidgets import (
            QWidgetAction, QWidget, QVBoxLayout, QGridLayout,
            QHBoxLayout, QCheckBox, QLabel, QPushButton, QGroupBox,
        )
        from PyQt5.QtGui import QIcon
        menu = self._table_design_menu
        menu.clear()

        # Options row (header / banding checkboxes).
        opts_widget = QWidget()
        opts_layout = QHBoxLayout(opts_widget)
        opts_layout.setContentsMargins(8, 4, 8, 4)
        self._td_header_check = QCheckBox("Header Row")
        self._td_header_check.setChecked(True)
        self._td_banded_check = QCheckBox("Banded Rows")
        self._td_banded_check.setChecked(True)
        opts_layout.addWidget(self._td_header_check)
        opts_layout.addWidget(self._td_banded_check)
        opts_layout.addStretch()
        opts_action = QWidgetAction(menu)
        opts_action.setDefaultWidget(opts_widget)
        menu.addAction(opts_action)
        menu.addSeparator()

        # Gallery per category.
        for category in ("Plain", "Grid", "List"):
            cat_styles = [s for s in BUILTIN_STYLES
                          if s.category == category]
            # Category label.
            lbl_widget = QWidget()
            lbl_layout = QHBoxLayout(lbl_widget)
            lbl_layout.setContentsMargins(8, 4, 8, 2)
            lbl = QLabel(f"<b>{category} Tables</b>")
            lbl_layout.addWidget(lbl)
            lbl_action = QWidgetAction(menu)
            lbl_action.setDefaultWidget(lbl_widget)
            menu.addAction(lbl_action)

            # Grid of thumbnails.
            grid_widget = QWidget()
            grid_layout = QGridLayout(grid_widget)
            grid_layout.setContentsMargins(8, 2, 8, 6)
            grid_layout.setSpacing(4)
            cols_per_row = 7
            for i, style in enumerate(cat_styles):
                btn = QPushButton()
                pm = _render_thumbnail(style)
                btn.setIcon(QIcon(pm))
                btn.setIconSize(pm.size())
                btn.setFixedSize(pm.width() + 6, pm.height() + 6)
                btn.setToolTip(style.name)
                btn.setFlat(True)
                btn.setStyleSheet(
                    "QPushButton:hover { border: 2px solid #3078c6; }")
                btn.clicked.connect(
                    lambda _, s=style: self._apply_table_style(s))
                grid_layout.addWidget(btn, i // cols_per_row,
                                      i % cols_per_row)
            grid_action = QWidgetAction(menu)
            grid_action.setDefaultWidget(grid_widget)
            menu.addAction(grid_action)

    def _apply_table_style(self, style):
        """Apply a table style to the current selection."""
        from .cellformat import BorderSpec
        self._table_design_menu.close()
        s = self._active_sheet()
        if not s:
            return
        sel = s.table.selectedRanges()
        if not sel:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "No Selection",
                "Select the cell range to format first.")
            return
        rng = sel[0]
        r0, r1 = rng.topRow(), rng.bottomRow()
        c0, c1 = rng.leftColumn(), rng.rightColumn()
        use_header = self._td_header_check.isChecked()
        use_banding = self._td_banded_check.isChecked()

        keys = []
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                keys.append((r, c))
        old = self._push_format_undo(s, keys)

        from PyQt5.QtWidgets import QTableWidgetItem
        s.table.blockSignals(True)
        try:
            for r in range(r0, r1 + 1):
                is_header = (r == r0 and use_header)
                data_row = r - r0 - (1 if use_header else 0)
                for c in range(c0, c1 + 1):
                    cf = self._cell_fmt(s, r, c)
                    it = s.table.item(r, c)
                    if it is None:
                        it = QTableWidgetItem("")
                        s.table.setItem(r, c, it)

                    # Background.
                    if is_header:
                        bg = style.header_bg
                    elif use_banding and data_row % 2 == 1:
                        bg = style.odd_bg
                    else:
                        bg = style.even_bg
                    cf.bg_color = bg
                    it.setBackground(QColor(bg))

                    # Text colour & font.
                    fg = style.header_fg if is_header else style.text_fg
                    cf.font_color = fg
                    it.setForeground(QColor(fg))
                    if is_header and style.header_bold:
                        cf.bold = True
                        ft = it.font()
                        ft.setBold(True)
                        it.setFont(ft)

                    # Borders.
                    bc = style.border_color
                    if bc:
                        if style.border_outer:
                            if r == r0:
                                cf.border_top = BorderSpec(color=bc)
                            if r == r1:
                                cf.border_bottom = BorderSpec(color=bc)
                            if c == c0:
                                cf.border_left = BorderSpec(color=bc)
                            if c == c1:
                                cf.border_right = BorderSpec(color=bc)
                        if style.border_inner:
                            if c < c1:
                                cf.border_right = BorderSpec(color=bc)
                            if r < r1:
                                cf.border_bottom = BorderSpec(color=bc)
                        if is_header and style.border_header_bottom:
                            cf.border_bottom = BorderSpec(
                                color=bc, width=2.0)
                        elif (not is_header and r == r0
                              and style.border_header_bottom):
                            cf.border_top = BorderSpec(
                                color=bc, width=2.0)
        finally:
            s.table.blockSignals(False)

        self._finish_format_undo(s, old, "Table Style")
        s.table.viewport().update()

    # ── Merge / Wrap ──────────────────────────────────────────────────
    def _merge_cells(self):
        s = self._active_sheet()
        if s:
            s.merge_selection()

    def _unmerge_cells(self):
        s = self._active_sheet()
        if s:
            s.unmerge_selection()

    def _toggle_wrap_text(self):
        s = self._active_sheet()
        if not s:
            return
        checked = self._wrap_act.isChecked()
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys) if s else None
        for r, c in keys:
            cf = self._cell_fmt(s, r, c)
            cf.wrap_text = checked
            it = s.table.item(r, c)
            if it is None:
                from PyQt5.QtWidgets import QTableWidgetItem
                it = QTableWidgetItem("")
                s.table.setItem(r, c, it)
            flags = it.flags()
            if checked:
                flags |= Qt.TextWordWrap
            else:
                flags &= ~Qt.TextWordWrap
            it.setFlags(flags)
            s.table.resizeRowToContents(r)
        self._finish_format_undo(s, old, "Wrap Text")

    # ── Format Cells dialog ────────────────────────────────────────
    def _open_format_cells_dialog(self):
        """Open the Format Cells dialog for the current selection."""
        from .format_dialog import FormatCellsDialog
        from .cellformat import CellFormat

        s = self._active_sheet()
        if not s:
            return

        ranges = s.table.selectedRanges()
        if not ranges:
            r = s.table.currentRow()
            c = s.table.currentColumn()
            if r < 0 or c < 0:
                return
            from PyQt5.QtWidgets import QTableWidgetSelectionRange
            ranges = [QTableWidgetSelectionRange(r, c, r, c)]

        first_r = ranges[0].topRow()
        first_c = ranges[0].leftColumn()
        cf = s._cell_formats.get((first_r, first_c), CellFormat())

        # Sample value for number format preview.
        sample = s._shadow.get((first_r, first_c), "")
        if not sample:
            it = s.table.item(first_r, first_c)
            sample = it.text() if it else ""

        # Current number format (cell overrides column).
        num_fmt = cf.number_format or s._col_formats.get(first_c, "General")

        dlg = FormatCellsDialog(cf, sample, self._PALETTE, num_fmt, self)
        if dlg.exec_() != QDialog.Accepted:
            return

        result = dlg.get_result()
        self._apply_format_cells_result(s, ranges, result)

    def _apply_format_cells_result(self, sheet, ranges, result):
        """Apply formatting result dict to all cells in *ranges*."""
        # Collect keys and snapshot old formats for undo.
        keys = []
        for rng in ranges:
            for r in range(rng.topRow(), rng.bottomRow() + 1):
                for c in range(rng.leftColumn(), rng.rightColumn() + 1):
                    keys.append((r, c))
        old_fmts = self._push_format_undo(sheet, keys)

        # Apply new formatting.
        for rng in ranges:
            for r in range(rng.topRow(), rng.bottomRow() + 1):
                for c in range(rng.leftColumn(), rng.rightColumn() + 1):
                    cf = self._cell_fmt(sheet, r, c)
                    it = sheet.table.item(r, c)
                    if it is None:
                        from PyQt5.QtWidgets import QTableWidgetItem
                        it = QTableWidgetItem("")
                        sheet.table.setItem(r, c, it)

                    # Number format.
                    if result.get("number_format") is not None:
                        nf = result["number_format"]
                        cf.number_format = nf if nf != "General" else None

                    # Font properties.
                    f = it.font()
                    if result.get("bold") is not None:
                        cf.bold = result["bold"]
                        f.setBold(result["bold"])
                    if result.get("italic") is not None:
                        cf.italic = result["italic"]
                        f.setItalic(result["italic"])
                    if result.get("underline") is not None:
                        cf.underline = result["underline"]
                        f.setUnderline(result["underline"])
                    if result.get("font_family") is not None:
                        cf.font_family = result["font_family"]
                        f.setFamily(result["font_family"])
                    if result.get("font_size") is not None:
                        cf.font_size = result["font_size"]
                        f.setPointSizeF(result["font_size"])
                    it.setFont(f)

                    # Font color.
                    if result.get("font_color") is not None:
                        cf.font_color = result["font_color"]
                        it.setForeground(QColor(result["font_color"]))

                    # Alignment.
                    if result.get("alignment") is not None:
                        cf.alignment = result["alignment"]
                        it.setTextAlignment(result["alignment"])

                    # Wrap text.
                    if result.get("wrap_text") is not None:
                        cf.wrap_text = result["wrap_text"]
                        flags = it.flags()
                        if result["wrap_text"]:
                            flags |= Qt.TextWordWrap
                        else:
                            flags &= ~Qt.TextWordWrap
                        it.setFlags(flags)
                        sheet.table.resizeRowToContents(r)

                    # Fill.
                    if "bg_color" in result:
                        sheet.set_cell_bg(r, c, result["bg_color"])

                    # Borders.
                    for side in ("top", "bottom", "left", "right"):
                        key = f"border_{side}"
                        if key in result:
                            setattr(cf, key, result[key])

                    # Clean up empty formats.
                    if cf.is_empty():
                        sheet._cell_formats.pop((r, c), None)

        self._finish_format_undo(sheet, old_fmts, "Format Cells")
        sheet.table.viewport().update()

    # ── Formulas ─────────────────────────────────────────────────────
    def _insert_function(self, func_name: str):
        """Insert ``=FUNC()`` into the active sheet's formula bar."""
        s = self._active_sheet()
        if not s:
            return
        bar = s._formula_bar
        bar.setText(f"={func_name}()")
        bar.setFocus()
        # Place cursor between the parentheses.
        bar.setCursorPosition(len(bar.text()) - 1)

    def _open_insert_function_dialog(self):
        """Open the Insert Function dialog (Shift+F3)."""
        s = self._active_sheet()
        if s:
            s._open_insert_function()

    def _open_solver(self):
        """Open the Solver Parameters dialog (non-modal)."""
        s = self._active_sheet()
        if s is None:
            return
        from .solver import SolverDialog
        dlg = SolverDialog(s, self)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        dlg.show()

    def _open_fitting(self):
        """Open the Curve Fitting dialog (lmfit-based, non-modal)."""
        s = self._active_sheet()
        if s is None:
            return
        from .fitting import FittingDialog
        dlg = FittingDialog(s, self)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        dlg.show()

    # ── View modes ───────────────────────────────────────────────────
    def _set_view_mode(self, mode: str):
        """Switch between Normal and Page Layout view."""
        is_normal = mode == "normal"
        self._view_normal_act.setChecked(is_normal)
        self._view_pagelayout_act.setChecked(not is_normal)
        s = self._active_sheet()
        if not s:
            return
        if is_normal:
            s.table.setAlternatingRowColors(False)
            self._status_msg("Normal view", 2000)
        else:
            # Page Layout: show alternating row colors as a visual cue.
            s.table.setAlternatingRowColors(True)
            self._status_msg("Page Layout view", 2000)

    def _toggle_gridlines(self):
        """Show or hide grid lines on the active sheet."""
        show = self._gridlines_act.isChecked()
        for s in self._workbook.all_sheets():
            s.table.setShowGrid(show)

    def _toggle_headings(self):
        """Show or hide row/column headers on the active sheet."""
        show = self._headings_act.isChecked()
        for s in self._workbook.all_sheets():
            s.table.horizontalHeader().setVisible(show)
            s.table.verticalHeader().setVisible(show)

    # ── Page Layout operations ───────────────────────────────────────
    def _page_margins(self):
        """Open a dialog to set page margins for printing."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Page Margins")
        from PyQt5.QtWidgets import (QFormLayout, QDoubleSpinBox,
                                     QDialogButtonBox)
        layout = QFormLayout(dlg)
        margins = getattr(self, '_page_margins_mm',
                          {"top": 25.4, "bottom": 25.4,
                           "left": 19.05, "right": 19.05})
        spins = {}
        for side in ("top", "bottom", "left", "right"):
            sp = QDoubleSpinBox()
            sp.setRange(0, 100)
            sp.setDecimals(1)
            sp.setSuffix(" mm")
            sp.setValue(margins[side])
            layout.addRow(side.capitalize() + ":", sp)
            spins[side] = sp
        bbox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        layout.addRow(bbox)
        if dlg.exec_() == QDialog.Accepted:
            self._page_margins_mm = {
                s: spins[s].value() for s in spins}
            self._status_msg("Margins updated", 2000)

    def _set_orientation(self, orient: str):
        """Set page orientation for printing."""
        is_portrait = orient == "portrait"
        self._orient_portrait.setChecked(is_portrait)
        self._orient_landscape.setChecked(not is_portrait)
        self._page_orientation = orient
        self._status_msg(
            f"Orientation: {orient.capitalize()}", 2000)

    def _set_page_size(self, name: str, w: float, h: float):
        """Set page size for printing."""
        self._page_size = (name, w, h)
        self._status_msg(f"Page size: {name} ({w:.0f} × {h:.0f} mm)",
                         2000)

    def _print_sheet(self):
        """Print the active sheet via QPrintPreviewDialog."""
        s = self._active_sheet()
        if not s:
            return
        try:
            from PyQt5.QtPrintSupport import (QPrinter,
                                              QPrintPreviewDialog)
        except ImportError:
            QMessageBox.warning(
                self, "Print",
                "Printing requires PyQt5 print support module.")
            return
        printer = QPrinter(QPrinter.HighResolution)
        # Apply stored orientation.
        orient = getattr(self, '_page_orientation', 'portrait')
        if orient == 'landscape':
            printer.setOrientation(QPrinter.Landscape)
        else:
            printer.setOrientation(QPrinter.Portrait)
        preview = QPrintPreviewDialog(printer, self)
        preview.paintRequested.connect(
            lambda p: self._render_sheet_to_printer(p, s))
        preview.exec_()

    def _render_sheet_to_printer(self, printer, sheet):
        """Render sheet grid to the given QPrinter."""
        from PyQt5.QtGui import QPainter as _P
        painter = _P(printer)
        table = sheet.table
        # Render visible cells onto the printer page.
        total_w = sum(table.columnWidth(c)
                      for c in range(table.columnCount()))
        total_h = sum(table.rowHeight(r)
                      for r in range(table.rowCount())
                      if table.item(r, 0) is not None or r < 50)
        page = printer.pageRect()
        sx = page.width() / max(total_w, 1)
        sy = page.height() / max(total_h, 1)
        scale = min(sx, sy, 1.0)
        painter.scale(scale, scale)
        table.render(painter)
        painter.end()

    # ── Data operations ──────────────────────────────────────────────
    def _set_designation(self, desig: str):
        s = self._active_sheet()
        if not s:
            return
        sel = s.table.selectedRanges()
        if not sel:
            return
        for rng in sel:
            for c in range(rng.leftColumn(), rng.rightColumn() + 1):
                s.set_designation(c, desig)
        self._status_msg(
            f"Set column(s) as {desig}", 2000)

    def _sort_asc(self):
        s = self._active_sheet()
        if s:
            col = s.table.currentColumn()
            if col >= 0:
                s._sort_column(col, Qt.AscendingOrder)

    def _sort_desc(self):
        s = self._active_sheet()
        if s:
            col = s.table.currentColumn()
            if col >= 0:
                s._sort_column(col, Qt.DescendingOrder)

    # ── Statistics ───────────────────────────────────────────────────
    def _show_statistics(self):
        s = self._active_sheet()
        if not s:
            return
        import numpy as np
        sel = s.table.selectedRanges()
        if not sel:
            QMessageBox.information(self, "Statistics",
                                    "Select cells first.")
            return
        vals = []
        for rng in sel:
            for r in range(rng.topRow(), rng.bottomRow() + 1):
                for c in range(rng.leftColumn(), rng.rightColumn() + 1):
                    it = s.table.item(r, c)
                    if it:
                        try:
                            vals.append(float(it.text()))
                        except ValueError:
                            pass
        if not vals:
            QMessageBox.information(self, "Statistics",
                                    "No numeric data selected.")
            return
        arr = np.array(vals)
        msg = (f"Count: {len(arr)}\n"
               f"Sum: {np.nansum(arr):.6g}\n"
               f"Mean: {np.nanmean(arr):.6g}\n"
               f"Std Dev: {np.nanstd(arr):.6g}\n"
               f"Min: {np.nanmin(arr):.6g}\n"
               f"Max: {np.nanmax(arr):.6g}\n"
               f"Median: {np.nanmedian(arr):.6g}")
        QMessageBox.information(self, "Statistics", msg)

    # ── Progress bar ─────────────────────────────────────────────────
    def _show_progress(self, show: bool, message: str = "Loading…"):
        if show:
            self._progress.setValue(0)
            self._progress.show()
            self._status_label.setText(message)
            # Force an immediate paint so the bar is visible during the
            # slow file-parse phase that runs before the per-row loop.
            self._progress.repaint()
            self._status_label.repaint()
            QApplication.processEvents()
        else:
            self._progress.hide()
            self._status_label.setText("Ready")

    # ── Help ─────────────────────────────────────────────────────────
    def _show_about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h2>{APP_NAME}</h2>"
            f"<p>Version {__version__}</p>"
            f"<p>An Excel-inspired spreadsheet workbench built with "
            f"PyQt5 + matplotlib.</p>"
            f"<p>Copyright (C) 2026 Gwilherm Kerherve</p>"
            f"<p>Licensed under GPL-3.0</p>")

    def _open_github(self):
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl
        QDesktopServices.openUrl(
            QUrl("https://github.com/gkerherve/KherveSheet"))
