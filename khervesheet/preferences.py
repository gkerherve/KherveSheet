# KherveSheet — Preferences dialog
# Copyright (C) 2024-2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later

"""Preferences dialog for application-wide settings."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget,
    QWidget, QSpinBox, QComboBox, QCheckBox, QDialogButtonBox,
    QFontComboBox, QLabel, QGroupBox,
)
from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QFont


class PreferencesDialog(QDialog):
    """Application preferences with General, Appearance, and Advanced tabs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(440)
        self._settings = QSettings("KherveSheet", "KherveSheet")
        self._build_ui()
        self._load()

    # ── UI ───────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_appearance_tab(), "Appearance")
        tabs.addTab(self._build_advanced_tab(), "Advanced")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── General tab ──────────────────────────────────────────────────

    def _build_general_tab(self):
        w = QWidget()
        form = QFormLayout(w)

        self._decimal_spin = QSpinBox()
        self._decimal_spin.setRange(0, 10)
        form.addRow("Default decimal places:", self._decimal_spin)

        self._new_sheets_spin = QSpinBox()
        self._new_sheets_spin.setRange(1, 10)
        form.addRow("Sheets in new workbook:", self._new_sheets_spin)

        self._autosave_check = QCheckBox("Enable autosave")
        form.addRow(self._autosave_check)

        self._autosave_interval = QSpinBox()
        self._autosave_interval.setRange(1, 60)
        self._autosave_interval.setSuffix(" min")
        form.addRow("Autosave interval:", self._autosave_interval)

        self._update_check = QCheckBox(
            "Automatically check for updates")
        self._update_check.setToolTip(
            "Checks once a day in the background and downloads the new "
            "version quietly. You are asked before anything is installed.")
        form.addRow(self._update_check)

        return w

    # ── Appearance tab ───────────────────────────────────────────────

    def _build_appearance_tab(self):
        w = QWidget()
        form = QFormLayout(w)

        self._font_combo = QFontComboBox()
        form.addRow("Default font:", self._font_combo)

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(6, 36)
        form.addRow("Default font size:", self._font_size_spin)

        self._theme_combo = QComboBox()
        from .app import THEMES
        self._theme_combo.addItems(list(THEMES.keys()))
        form.addRow("Theme:", self._theme_combo)

        self._gridline_check = QCheckBox("Show gridlines")
        form.addRow(self._gridline_check)

        return w

    # ── Advanced tab ─────────────────────────────────────────────────

    def _build_advanced_tab(self):
        w = QWidget()
        form = QFormLayout(w)

        self._calc_combo = QComboBox()
        self._calc_combo.addItems(["Automatic", "Manual"])
        form.addRow("Calculation mode:", self._calc_combo)

        self._max_recent_spin = QSpinBox()
        self._max_recent_spin.setRange(1, 30)
        form.addRow("Max recent files:", self._max_recent_spin)

        return w

    # ── Load / Save ──────────────────────────────────────────────────

    def _load(self):
        s = self._settings
        self._decimal_spin.setValue(
            int(s.value("prefs/decimal_places", 2)))
        self._new_sheets_spin.setValue(
            int(s.value("prefs/new_sheets", 3)))
        self._autosave_check.setChecked(
            s.value("prefs/autosave", False, type=bool))
        self._autosave_interval.setValue(
            int(s.value("prefs/autosave_interval", 5)))
        self._update_check.setChecked(
            s.value("update/auto_check", True, type=bool))

        font_family = s.value("prefs/font_family", "")
        if font_family:
            self._font_combo.setCurrentFont(QFont(font_family))
        self._font_size_spin.setValue(
            int(s.value("prefs/font_size", 11)))

        theme = s.value("theme", "Light")
        idx = self._theme_combo.findText(theme)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)

        self._gridline_check.setChecked(
            s.value("prefs/gridlines", True, type=bool))
        self._calc_combo.setCurrentIndex(
            int(s.value("prefs/calc_mode", 0)))
        self._max_recent_spin.setValue(
            int(s.value("prefs/max_recent", 10)))

    def _save_and_accept(self):
        s = self._settings
        s.setValue("prefs/decimal_places", self._decimal_spin.value())
        s.setValue("prefs/new_sheets", self._new_sheets_spin.value())
        s.setValue("prefs/autosave", self._autosave_check.isChecked())
        s.setValue("prefs/autosave_interval",
                   self._autosave_interval.value())

        # Re-enabling the check should take effect now, not after the
        # daily throttle from the last check happens to expire.
        auto_update = self._update_check.isChecked()
        if auto_update and not s.value("update/auto_check", True, type=bool):
            s.remove("update/last_check")
        s.setValue("update/auto_check", auto_update)
        s.setValue("prefs/font_family",
                   self._font_combo.currentFont().family())
        s.setValue("prefs/font_size", self._font_size_spin.value())
        s.setValue("prefs/gridlines", self._gridline_check.isChecked())
        s.setValue("prefs/calc_mode", self._calc_combo.currentIndex())
        s.setValue("prefs/max_recent", self._max_recent_spin.value())

        # Theme change is applied immediately.
        new_theme = self._theme_combo.currentText()
        old_theme = s.value("theme", "Light")
        if new_theme != old_theme:
            parent = self.parent()
            if parent and hasattr(parent, '_apply_theme'):
                parent._apply_theme(new_theme)

        self.accept()
