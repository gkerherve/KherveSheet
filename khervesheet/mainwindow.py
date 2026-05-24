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
    QWidgetAction, QGridLayout, QDialog,
)

from . import APP_NAME, __version__
from .workbook import WorkbookWidget
from .sheet import SheetWidget, col_index_to_letter
from . import icons
from .formulas import build_formulas_menu


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
        self._init_ui()

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

    def _wire_undo_to_sheets(self):
        for s in self._workbook.all_sheets():
            s._undo_stack = self._undo_stack
            # Connect cell selection to format toolbar sync (guard
            # against duplicate connections with a flag).
            if not getattr(s, '_fmt_connected', False):
                s.table.currentCellChanged.connect(
                    lambda *_: self._update_format_toolbar())
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
        file_menu.addAction("&Open…", self._open_file, "Ctrl+O")
        file_menu.addSeparator()

        imp = file_menu.addMenu("Import")
        imp.addAction("CSV…", self._import_csv)
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
        view_menu.addAction("Zoom In", self._zoom_in, "Ctrl+=")
        view_menu.addAction("Zoom Out", self._zoom_out, "Ctrl+-")
        view_menu.addAction("Reset Zoom", self._zoom_reset, "Ctrl+0")
        view_menu.addSeparator()
        theme_menu = view_menu.addMenu("Theme")
        from .app import THEMES
        for name in THEMES:
            act = theme_menu.addAction(name)
            act.triggered.connect(
                lambda _, n=name: self._apply_theme(n))

        # ── Insert ───────────────────────────────────────────────────
        insert_menu = mb.addMenu("&Insert")
        insert_menu.addAction("Row Above",
                              self._insert_row_above)
        insert_menu.addAction("Row Below",
                              self._insert_row_below)
        insert_menu.addAction("Column",
                              self._insert_column)
        insert_menu.addSeparator()
        insert_menu.addAction("Sheet",
                              lambda: self._workbook.add_sheet())
        insert_menu.addSeparator()

        insert_menu.addAction("Image\u2026", self._insert_image)
        insert_menu.addSeparator()

        chart_menu = insert_menu.addMenu("Chart")
        from .sheet import SheetWidget
        for pt in SheetWidget.PLOT_TYPES:
            act = chart_menu.addAction(pt)
            act.triggered.connect(
                lambda _, t=pt: self._insert_chart(t))

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
        format_menu.addAction("Merge Cells", self._merge_cells)
        format_menu.addAction("Unmerge Cells", self._unmerge_cells)
        self._wrap_act = format_menu.addAction(
            "Wrap Text", self._toggle_wrap_text)
        self._wrap_act.setCheckable(True)
        format_menu.addSeparator()
        self._table_design_menu = format_menu.addMenu("Table Design")
        self._table_design_menu.aboutToShow.connect(
            self._build_table_design_menu)
        format_menu.addSeparator()
        fc_act = format_menu.addAction(
            "Format Cells\u2026\tCtrl+1", self._open_format_cells_dialog)
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui import QKeySequence
        QShortcut(QKeySequence("Ctrl+1"), self,
                  self._open_format_cells_dialog)

        # ── Formulas ─────────────────────────────────────────────────
        build_formulas_menu(mb, self._insert_function)

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
        tools_menu.addAction("Statistics on Selection",
                             self._show_statistics)

        # ── Help ─────────────────────────────────────────────────────
        help_menu = mb.addMenu("&Help")
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

        # Plot toolbar — all plot types with custom icons
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
        }
        for pt in SheetWidget.PLOT_TYPES:
            fn = _plot_icon_fns.get(pt)
            ic = fn(28) if fn else icons.themed_icon("mdi.chart-line")
            act = plot_bar.addAction(
                ic, "",
                lambda t=pt: self._insert_chart(t))
            act.setToolTip(pt)

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

        # Selection summary (left of zoom)
        self._sum_label = QLabel("")
        self._sum_label.setMinimumWidth(120)
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
        self._zoom_slider.setRange(50, 200)
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
    def _new_workbook(self):
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

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "",
            "KherveSheet (*.ksheet);;"
            "CSV Files (*.csv);;Excel Files (*.xlsx);;All Files (*)")
        if not path:
            return
        if path.endswith(".ksheet"):
            self._load_ksheet(path)
        elif path.endswith(".csv"):
            self._load_csv(path)
        elif path.endswith(".xlsx"):
            self._load_excel(path)
        self._current_file = path
        self._add_recent(path)
        self._update_title()

    def _save_file(self):
        if self._current_file:
            if self._current_file.endswith(".ksheet"):
                self._save_to_ksheet(self._current_file)
            else:
                self._save_to_csv(self._current_file)
        else:
            self._save_file_as()

    def _save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save As", "",
            "KherveSheet (*.ksheet);;"
            "CSV Files (*.csv);;All Files (*)")
        if not path:
            return
        if path.endswith(".ksheet"):
            self._save_to_ksheet(path)
        else:
            self._save_to_csv(path)
        self._current_file = path
        self._add_recent(path)
        self._update_title()

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "", "CSV Files (*.csv *.tsv *.txt)")
        if path:
            self._load_csv(path)
            self._add_recent(path)

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
        self._show_progress(True)
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
        sheet = self._active_sheet()
        if not sheet:
            return
        self._show_progress(True)
        try:
            wb = openpyxl.load_workbook(path, data_only=True)
            ws = wb.active
            n_rows = ws.max_row or 0
            n_cols = ws.max_column or 0

            sheet.table.blockSignals(True)
            sheet.table.setColumnCount(n_cols)
            sheet.table.setRowCount(n_rows)
            sheet._refresh_headers()

            from PyQt5.QtWidgets import QTableWidgetItem
            for r in range(n_rows):
                self._progress.setValue(int(100 * r / max(1, n_rows)))
                QApplication.processEvents()
                for c in range(n_cols):
                    cell = ws.cell(r + 1, c + 1)
                    val = str(cell.value) if cell.value is not None else ""
                    sheet.table.setItem(r, c, QTableWidgetItem(val))
                    sheet._shadow[(r, c)] = val
            sheet.table.blockSignals(False)

            self._status_msg(
                f"Loaded {n_rows} × {n_cols} from {path}", 5000)
        except Exception as e:
            QMessageBox.warning(self, "Import Error", str(e))
        finally:
            self._show_progress(False)

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
        self._show_progress(True)
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
        self._show_progress(True)
        try:
            wb = self._workbook
            with h5py.File(path, 'w') as f:
                f.attrs['format'] = 'ksheet'
                f.attrs['version'] = 1
                f.attrs['sheet_count'] = wb.tabs.count()

                for si in range(wb.tabs.count()):
                    sheet = wb.tabs.widget(si)
                    name = wb.tabs.tabText(si)
                    sg = f.create_group(f"sheet_{si}")
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
                        # Store PNG data as raw bytes (uint8 array
                        # to avoid VLEN string null-byte issues).
                        import base64
                        raw = base64.b64decode(d['data'])
                        ig.create_dataset(
                            "png_data",
                            data=np.frombuffer(raw, dtype=np.uint8))

            self._status_msg(f"Saved to {path}", 5000)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))
        finally:
            self._show_progress(False)

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
                        # Axis properties (full dialog state).
                        ap_json = cg.attrs.get('axis_props', '')
                        if ap_json:
                            cd["axis_props"] = json.loads(ap_json)
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
                        imd = {
                            "pos_x": int(ig.attrs['pos_x']),
                            "pos_y": int(ig.attrs['pos_y']),
                            "width": int(ig.attrs['width']),
                            "height": int(ig.attrs['height']),
                            "data": _b64.b64encode(
                                bytes(ig["png_data"][:])).decode("ascii"),
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
                        deferred_images.append(imd)
                    if deferred_images:
                        sheet._deferred_images = deferred_images

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
        if path.endswith(".ksheet"):
            self._load_ksheet(path)
        elif path.endswith(".csv"):
            self._load_csv(path)
        elif path.endswith(".xlsx"):
            self._load_excel(path)
        self._current_file = path
        self._update_title()

    # ── Edit operations (proxy to active sheet) ──────────────────────
    def _cut(self):
        s = self._active_sheet()
        if not s:
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
            self._status_msg("Chart copied", 2000)
        else:
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
        if self._undo_stack:
            self._undo_stack.push(
                FormatCellsCmd(sheet, old_fmts, new_fmts, label))

    def _apply_font_family(self, font):
        s = self._active_sheet()
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys) if s else None
        for it in self._selected_items():
            f = it.font()
            f.setFamily(font.family())
            it.setFont(f)
            if s:
                r, c = it.row(), it.column()
                self._cell_fmt(s, r, c).font_family = font.family()
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
        for it in self._selected_items():
            f = it.font()
            f.setPointSizeF(size)
            it.setFont(f)
            if s:
                r, c = it.row(), it.column()
                self._cell_fmt(s, r, c).font_size = size
        if s and old:
            self._finish_format_undo(s, old, "Font Size")

    def _toggle_bold(self):
        checked = self._bold_act.isChecked()
        s = self._active_sheet()
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys) if s else None
        for it in self._selected_items():
            f = it.font()
            f.setBold(checked)
            it.setFont(f)
            if s:
                r, c = it.row(), it.column()
                self._cell_fmt(s, r, c).bold = checked
        if s and old:
            self._finish_format_undo(s, old, "Bold")

    def _toggle_italic(self):
        checked = self._italic_act.isChecked()
        s = self._active_sheet()
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys) if s else None
        for it in self._selected_items():
            f = it.font()
            f.setItalic(checked)
            it.setFont(f)
            if s:
                r, c = it.row(), it.column()
                self._cell_fmt(s, r, c).italic = checked
        if s and old:
            self._finish_format_undo(s, old, "Italic")

    def _toggle_underline(self):
        checked = self._underline_act.isChecked()
        s = self._active_sheet()
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys) if s else None
        for it in self._selected_items():
            f = it.font()
            f.setUnderline(checked)
            it.setFont(f)
            if s:
                r, c = it.row(), it.column()
                self._cell_fmt(s, r, c).underline = checked
        if s and old:
            self._finish_format_undo(s, old, "Underline")

    def _apply_alignment(self, alignment):
        # Update toggle state — only one alignment active at a time.
        self._align_left_act.setChecked(
            alignment & Qt.AlignLeft and not alignment & Qt.AlignHCenter)
        self._align_center_act.setChecked(bool(alignment & Qt.AlignHCenter))
        self._align_right_act.setChecked(bool(alignment & Qt.AlignRight))
        s = self._active_sheet()
        keys = self._selected_cell_keys()
        old = self._push_format_undo(s, keys) if s else None
        for it in self._selected_items():
            it.setTextAlignment(int(alignment))
            if s:
                r, c = it.row(), it.column()
                self._cell_fmt(s, r, c).alignment = int(alignment)
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
        self._refresh_toolbar_icons()

    def _refresh_toolbar_icons(self):
        """Rebuild format toolbar icons so they match the current theme."""
        self._bold_act.setIcon(icons.bold_icon(28))
        self._italic_act.setIcon(icons.italic_icon(28))
        self._underline_act.setIcon(icons.underline_icon(28))
        self._align_left_act.setIcon(icons.align_left_icon(28))
        self._align_center_act.setIcon(icons.align_center_icon(28))
        self._align_right_act.setIcon(icons.align_right_icon(28))

    # ── Zoom ─────────────────────────────────────────────────────────
    def _zoom_in(self):
        v = min(200, self._zoom_slider.value() + 10)
        self._zoom_slider.setValue(v)

    def _zoom_out(self):
        v = max(50, self._zoom_slider.value() - 10)
        self._zoom_slider.setValue(v)

    def _zoom_reset(self):
        self._zoom_slider.setValue(100)

    def _apply_zoom(self, value):
        self._zoom_label.setText(f"{value}%")
        sheet = self._active_sheet()
        if not sheet:
            return
        # Scale row/column sizes proportionally
        base_row = 20
        base_col = 80
        factor = value / 100.0
        sheet.table.verticalHeader().setDefaultSectionSize(
            int(base_row * factor))
        sheet.table.horizontalHeader().setDefaultSectionSize(
            int(base_col * factor))
        font = sheet.table.font()
        font.setPointSizeF(9 * factor)
        sheet.table.setFont(font)

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

        # Find X and Y columns
        x_col = None
        y_cols = []
        for c in cols:
            if sheet.get_designation(c) == "X":
                x_col = c
            else:
                y_cols.append(c)

        # If no X designated, use first column as X
        if x_col is None and len(cols) >= 2:
            x_col = cols[0]
            y_cols = cols[1:]
        elif x_col is None:
            # Single column: plot against row index
            y_cols = cols

        # Collect data
        import numpy as np
        if x_col is not None:
            x_data = sheet.numeric_column(x_col)
        else:
            x_data = np.arange(sheet.row_count(), dtype=float)

        # Create embedded chart on the grid viewport
        from .graph import EmbeddedChart
        if not hasattr(sheet, '_charts'):
            sheet._charts = []

        # Build one chart with all Y columns as series
        first_chart = None
        for yc in y_cols:
            y_data = sheet.numeric_column(yc)
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
                    x_col=x_col, y_col=yc)
                # Position at a visible spot, offset by existing charts.
                offset = len(sheet._charts) * 30
                chart.move(40 + offset, 40 + offset)
                sheet._charts.append(chart)
                # Connect data change signal for live updates.
                sheet.data_changed.connect(chart._on_data_changed)
                first_chart = chart
            else:
                first_chart.add_series(x, y, label, plot_type,
                                       y_col=yc)

        self._status_msg(
            f"Created {plot_type} chart", 3000)

    # ── Insert image ─────────────────────────────────────────────────

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
        if self._undo_stack:
            self._undo_stack.push(InsertImageCmd(sheet, img, label))
        self._status_msg(label, 3000)

    # ── Format operations ────────────────────────────────────────────
    def _set_number_format(self, fmt: str):
        s = self._active_sheet()
        if not s:
            return
        sel = s.table.selectedRanges()
        if not sel:
            return
        for rng in sel:
            for c in range(rng.leftColumn(), rng.rightColumn() + 1):
                s._col_formats[c] = fmt

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
                    elif not is_header and r == r0 and style.border_header_bottom:
                        cf.border_top = BorderSpec(
                            color=bc, width=2.0)

        self._finish_format_undo(s, keys, old)
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
        self._finish_format_undo(s, keys, old)

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
    def _show_progress(self, show: bool):
        if show:
            self._progress.setValue(0)
            self._progress.show()
        else:
            self._progress.hide()

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
