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
from PyQt5.QtGui import QIcon, QKeySequence, QFont
from PyQt5.QtWidgets import QStyle
from PyQt5.QtWidgets import (
    QMainWindow, QStatusBar, QLabel, QAction, QMenu, QMenuBar,
    QToolBar, QToolButton, QFileDialog, QMessageBox, QProgressBar,
    QSlider, QHBoxLayout, QWidget, QUndoStack, QComboBox,
    QInputDialog, QApplication, QFontComboBox,
)

from . import APP_NAME, __version__
from .workbook import WorkbookWidget
from .sheet import SheetWidget, col_index_to_letter
from . import icons


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
        format_menu.addAction("Column Width…", self._format_col_width)
        format_menu.addAction("Row Height…", self._format_row_height)

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
        self.statusBar().showMessage("New workbook created", 3000)

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

            self.statusBar().showMessage(
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
            self.statusBar().showMessage(f"Saved to {path}", 5000)
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

            self.statusBar().showMessage(
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
            self.statusBar().showMessage(f"Exported to {path}", 5000)
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
                    for r in range(n_rows):
                        self._progress.setValue(
                            int(100 * (si * n_rows + r)
                                / max(1, wb.tabs.count() * n_rows)))
                        QApplication.processEvents()
                        for c in range(n_cols):
                            it = sheet.table.item(r, c)
                            data.append(it.text() if it else "")
                    dt = h5py.string_dtype()
                    sg.create_dataset("cells", data=data, dtype=dt)

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
                        for ki, s in enumerate(d['series']):
                            srg = cg.create_group(f"series_{ki}")
                            srg.create_dataset("x", data=s['x'])
                            srg.create_dataset("y", data=s['y'])
                            srg.attrs['label'] = s['label']
                            srg.attrs['plot_type'] = s['plot_type']

            self.statusBar().showMessage(f"Saved to {path}", 5000)
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
                    sg = f[f"sheet_{si}"]
                    name = sg.attrs['name']
                    n_rows = int(sg.attrs['rows'])
                    n_cols = int(sg.attrs['cols'])

                    sheet = wb.add_sheet(name)
                    sheet.table.blockSignals(True)
                    sheet.table.setRowCount(n_rows)
                    sheet.table.setColumnCount(n_cols)
                    sheet._refresh_headers()

                    # Restore cells.
                    cells = sg["cells"][:]
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
                                sheet.table.setItem(
                                    r, c, QTableWidgetItem(val))
                                sheet._shadow[(r, c)] = val
                            idx += 1
                    sheet.table.blockSignals(False)

                    # Column designations.
                    desig_json = sg.attrs.get('col_designations', '')
                    if desig_json:
                        d = json.loads(desig_json)
                        sheet._col_designations = {
                            int(k): v for k, v in d.items()}

                    # Column widths.
                    if "col_widths" in sg:
                        widths = sg["col_widths"][:]
                        for c, w in enumerate(widths):
                            sheet.table.setColumnWidth(c, int(w))

                    # Charts.
                    chart_count = int(sg.attrs.get('chart_count', 0))
                    if chart_count:
                        from .graph import EmbeddedChart
                        if not hasattr(sheet, '_charts'):
                            sheet._charts = []
                        viewport = sheet.table.viewport()
                        for ci in range(chart_count):
                            cg = sg[f"chart_{ci}"]
                            series_count = int(
                                cg.attrs['series_count'])
                            series = []
                            for ki in range(series_count):
                                srg = cg[f"series_{ki}"]
                                series.append({
                                    "x": list(srg["x"][:]),
                                    "y": list(srg["y"][:]),
                                    "label": srg.attrs['label'],
                                    "plot_type": srg.attrs[
                                        'plot_type'],
                                })
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
                            }
                            chart = EmbeddedChart.from_dict(
                                cd, sheet, viewport)
                            sheet._charts.append(chart)

                wb.tabs.setCurrentIndex(0)
                self.setCentralWidget(wb)
                self._workbook = wb
                self._wire_undo_to_sheets()
                self._workbook.tabs.currentChanged.connect(
                    lambda: self._wire_undo_to_sheets())
                self._undo_stack.clear()

            self.statusBar().showMessage(
                f"Loaded {path}", 5000)
        except Exception as e:
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
            self.statusBar().showMessage("Chart copied", 2000)
        else:
            s._copy_selection()

    def _paste(self):
        s = self._active_sheet()
        if not s:
            return
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
            self.statusBar().showMessage("Chart pasted", 2000)
        else:
            s._paste_clipboard()

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

    def _apply_font_family(self, font):
        for it in self._selected_items():
            f = it.font()
            f.setFamily(font.family())
            it.setFont(f)

    def _apply_font_size(self, size_text):
        try:
            size = float(size_text)
        except ValueError:
            return
        if size < 1:
            return
        for it in self._selected_items():
            f = it.font()
            f.setPointSizeF(size)
            it.setFont(f)

    def _toggle_bold(self):
        checked = self._bold_act.isChecked()
        for it in self._selected_items():
            f = it.font()
            f.setBold(checked)
            it.setFont(f)

    def _toggle_italic(self):
        checked = self._italic_act.isChecked()
        for it in self._selected_items():
            f = it.font()
            f.setItalic(checked)
            it.setFont(f)

    def _toggle_underline(self):
        checked = self._underline_act.isChecked()
        for it in self._selected_items():
            f = it.font()
            f.setUnderline(checked)
            it.setFont(f)

    def _apply_alignment(self, alignment):
        # Update toggle state — only one alignment active at a time.
        self._align_left_act.setChecked(
            alignment & Qt.AlignLeft and not alignment & Qt.AlignHCenter)
        self._align_center_act.setChecked(bool(alignment & Qt.AlignHCenter))
        self._align_right_act.setChecked(bool(alignment & Qt.AlignRight))
        for it in self._selected_items():
            it.setTextAlignment(int(alignment))

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
                    x, y, label, plot_type, sheet, viewport)
                # Position at a visible spot, offset by existing charts.
                offset = len(sheet._charts) * 30
                chart.move(40 + offset, 40 + offset)
                sheet._charts.append(chart)
                first_chart = chart
            else:
                first_chart.add_series(x, y, label, plot_type)

        self.statusBar().showMessage(
            f"Created {plot_type} chart", 3000)

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
        self.statusBar().showMessage(
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
