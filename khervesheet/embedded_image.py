"""Embedded image — movable/resizable picture overlaid on grid.

Images float as child widgets of the sheet's table viewport, just like
embedded charts.  They can be dragged to reposition and resized via
edge handles.  Supports crop and colour-filter adjustments.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import base64

from PyQt5.QtCore import Qt, QRect, QRectF, QPoint, QBuffer, QIODevice
from PyQt5.QtGui import (
    QPixmap, QPainter, QPen, QColor, QCursor, QImage,
    QBrush, QPainterPath,
)
from PyQt5.QtWidgets import (
    QWidget, QMenu, QFileDialog, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QDialogButtonBox, QGroupBox, QFormLayout,
    QRubberBand, QPushButton, QSpinBox,
)

# Resize handle size in pixels.
_HANDLE = 6


class EmbeddedImage(QWidget):
    """A picture that lives as a child of the grid viewport."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._original_pixmap = pixmap   # unmodified source
        self._pixmap = pixmap            # displayed (after filters)
        self._selected = False
        self._cropping = False

        # Crop state: normalized rect (0..1) relative to original.
        self._crop_rect = QRectF(0, 0, 1, 1)

        # Colour filter state (all in degrees / percent offsets).
        self._hue_shift = 0        # -180..180
        self._saturation = 0       # -100..100
        self._brightness = 0       # -100..100

        # Dragging / resizing state.
        self._drag_origin = None
        self._drag_widget_pos = None
        self._resizing = False
        self._resize_edge = None

        # Aspect ratio lock (default: keep proportions).
        self._keep_aspect_ratio = True
        self._aspect_ratio = pixmap.width() / max(pixmap.height(), 1)

        # Crop rubber-band state.
        self._crop_origin = None
        self._rubber_band = None

        # Size to pixmap, capped to reasonable dimensions.
        pw = min(pixmap.width(), 600)
        ph = min(pixmap.height(), 600)
        if pixmap.width() > 600 or pixmap.height() > 600:
            scaled = pixmap.scaled(600, 600, Qt.KeepAspectRatio,
                                   Qt.SmoothTransformation)
            pw, ph = scaled.width(), scaled.height()
        self.setMinimumSize(40, 40)
        self.resize(pw + 4, ph + 4)
        self.show()

    # ── Painting ──────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        target = self.rect().adjusted(2, 2, -2, -2)
        p.drawPixmap(target, self._pixmap)
        # Selection border.
        if self._selected:
            pen = QPen(QColor("#3078c6"), 2, Qt.DashLine)
            p.setPen(pen)
            p.drawRect(self.rect().adjusted(0, 0, -1, -1))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#3078c6"))
            for hx, hy in self._handle_positions():
                p.drawRect(hx - _HANDLE // 2, hy - _HANDLE // 2,
                           _HANDLE, _HANDLE)
        p.end()

    def _handle_positions(self):
        r = self.rect()
        mx = r.width() // 2
        my = r.height() // 2
        return [
            (0, 0), (mx, 0), (r.width(), 0),
            (0, my), (r.width(), my),
            (0, r.height()), (mx, r.height()),
            (r.width(), r.height()),
        ]

    # ── Mouse interaction ─────────────────────────────────────────────

    def _edge_at(self, pos):
        r = self.rect()
        edge = ""
        if pos.y() <= _HANDLE:
            edge += "t"
        elif pos.y() >= r.height() - _HANDLE:
            edge += "b"
        if pos.x() <= _HANDLE:
            edge += "l"
        elif pos.x() >= r.width() - _HANDLE:
            edge += "r"
        return edge

    def _cursor_for_edge(self, edge):
        m = {
            "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
            "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor,
            "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
            "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
        }
        return m.get(edge, Qt.ArrowCursor)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            if self._cropping:
                self._crop_origin = ev.pos()
                if not self._rubber_band:
                    self._rubber_band = QRubberBand(
                        QRubberBand.Rectangle, self)
                self._rubber_band.setGeometry(
                    QRect(self._crop_origin, self._crop_origin))
                self._rubber_band.show()
                return
            self._selected = True
            self.update()
            edge = self._edge_at(ev.pos()) if self._selected else ""
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._drag_origin = ev.globalPos()
                self._drag_widget_pos = self.geometry()
            else:
                self._drag_origin = ev.globalPos()
                self._drag_widget_pos = self.pos()
            self.raise_()

    def mouseMoveEvent(self, ev):
        if self._cropping and self._crop_origin:
            rect = QRect(self._crop_origin, ev.pos()).normalized()
            self._rubber_band.setGeometry(rect)
            return
        if self._resizing and self._drag_origin:
            delta = ev.globalPos() - self._drag_origin
            geo = QRect(self._drag_widget_pos)
            e = self._resize_edge
            if "l" in e:
                geo.setLeft(geo.left() + delta.x())
            if "r" in e:
                geo.setRight(geo.right() + delta.x())
            if "t" in e:
                geo.setTop(geo.top() + delta.y())
            if "b" in e:
                geo.setBottom(geo.bottom() + delta.y())
            # Enforce aspect ratio if locked.
            if self._keep_aspect_ratio and self._aspect_ratio > 0:
                ar = self._aspect_ratio
                if "r" in e or "l" in e:
                    new_h = int(geo.width() / ar)
                    if "t" in e:
                        geo.setTop(geo.bottom() - new_h)
                    else:
                        geo.setBottom(geo.top() + new_h)
                elif "t" in e or "b" in e:
                    new_w = int(geo.height() * ar)
                    if "l" in e:
                        geo.setLeft(geo.right() - new_w)
                    else:
                        geo.setRight(geo.left() + new_w)
            if geo.width() >= self.minimumWidth() and \
               geo.height() >= self.minimumHeight():
                self.setGeometry(geo)
        elif self._drag_origin:
            delta = ev.globalPos() - self._drag_origin
            self.move(self._drag_widget_pos + delta)
        else:
            if self._cropping:
                self.setCursor(Qt.CrossCursor)
            else:
                edge = self._edge_at(ev.pos()) if self._selected else ""
                if edge:
                    self.setCursor(self._cursor_for_edge(edge))
                else:
                    self.setCursor(Qt.SizeAllCursor)

    def mouseReleaseEvent(self, ev):
        if self._cropping and self._crop_origin:
            rect = QRect(self._crop_origin, ev.pos()).normalized()
            self._crop_origin = None
            if self._rubber_band:
                self._rubber_band.hide()
            # Apply crop if region is meaningful.
            w = self.width() - 4
            h = self.height() - 4
            if rect.width() > 10 and rect.height() > 10 and w > 0 and h > 0:
                # Convert widget coords to normalized crop within
                # current displayed image.
                x1 = max(0.0, (rect.left() - 2) / w)
                y1 = max(0.0, (rect.top() - 2) / h)
                x2 = min(1.0, (rect.right() - 2) / w)
                y2 = min(1.0, (rect.bottom() - 2) / h)
                # Compose with existing crop.
                cr = self._crop_rect
                new_x1 = cr.x() + x1 * cr.width()
                new_y1 = cr.y() + y1 * cr.height()
                new_w = (x2 - x1) * cr.width()
                new_h = (y2 - y1) * cr.height()
                self._crop_rect = QRectF(new_x1, new_y1, new_w, new_h)
                self._apply_filters()
            self._cropping = False
            self.setCursor(Qt.SizeAllCursor)
            return
        self._drag_origin = None
        self._drag_widget_pos = None
        self._resizing = False
        self._resize_edge = None

    def mouseDoubleClickEvent(self, ev):
        """Double-click opens the image adjustments dialog."""
        self._open_adjustments()

    def contextMenuEvent(self, ev):
        menu = QMenu(self)
        menu.addAction("Resize…", self._resize_dialog)
        ar_act = menu.addAction("Lock Aspect Ratio")
        ar_act.setCheckable(True)
        ar_act.setChecked(self._keep_aspect_ratio)
        ar_act.toggled.connect(self._toggle_aspect_ratio)
        menu.addSeparator()
        menu.addAction("Crop", self._start_crop)
        menu.addAction("Reset Crop", self._reset_crop)
        menu.addSeparator()
        menu.addAction("Adjustments…", self._open_adjustments)
        menu.addSeparator()
        menu.addAction("Replace Image…", self._replace_image)
        menu.addSeparator()
        menu.addAction("Delete", self._delete)
        menu.exec_(ev.globalPos())

    # ── Crop ──────────────────────────────────────────────────────────

    def _start_crop(self):
        """Enter crop mode — next drag selects crop region."""
        self._cropping = True
        self.setCursor(Qt.CrossCursor)

    def _reset_crop(self):
        """Remove any cropping."""
        self._crop_rect = QRectF(0, 0, 1, 1)
        self._apply_filters()

    # ── Colour adjustments ────────────────────────────────────────────

    def _open_adjustments(self):
        dlg = ImageAdjustDialog(
            self._hue_shift, self._saturation, self._brightness,
            parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self._hue_shift = dlg.hue_shift
            self._saturation = dlg.saturation
            self._brightness = dlg.brightness
            self._apply_filters()

    def _apply_filters(self):
        """Rebuild _pixmap from _original_pixmap applying crop + colour."""
        src = self._original_pixmap.toImage()
        # Apply crop.
        cr = self._crop_rect
        sx = int(cr.x() * src.width())
        sy = int(cr.y() * src.height())
        sw = int(cr.width() * src.width())
        sh = int(cr.height() * src.height())
        if sw < 1:
            sw = 1
        if sh < 1:
            sh = 1
        cropped = src.copy(sx, sy, sw, sh)

        # Apply colour adjustments if any are non-zero.
        if self._hue_shift != 0 or self._saturation != 0 \
                or self._brightness != 0:
            cropped = self._adjust_colors(cropped)

        self._pixmap = QPixmap.fromImage(cropped)
        self.update()

    def _adjust_colors(self, img: QImage) -> QImage:
        """Apply hue shift, saturation, and brightness to image."""
        # Work on a copy in ARGB32 format for pixel access.
        result = img.convertToFormat(QImage.Format_ARGB32)
        w, h = result.width(), result.height()
        for y in range(h):
            for x in range(w):
                c = QColor(result.pixel(x, y))
                hue, sat, val, alpha = c.getHsv()
                if hue < 0:
                    hue = 0
                # Shift hue.
                hue = (hue + self._hue_shift) % 360
                # Adjust saturation.
                sat = max(0, min(255, sat + int(
                    self._saturation * 2.55)))
                # Adjust brightness (value).
                val = max(0, min(255, val + int(
                    self._brightness * 2.55)))
                c.setHsv(hue, sat, val, alpha)
                result.setPixel(x, y, c.rgba())
        return result

    # ── Size / aspect ratio ──────────────────────────────────────────

    def _toggle_aspect_ratio(self, checked):
        self._keep_aspect_ratio = checked
        if checked:
            # Update ratio from current size.
            self._aspect_ratio = self.width() / max(self.height(), 1)

    def _resize_dialog(self):
        """Open a dialog to set exact width and height."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Resize Image")
        layout = QVBoxLayout(dlg)
        form = QFormLayout()
        w_spin = QSpinBox()
        w_spin.setRange(40, 4000)
        w_spin.setValue(self.width())
        h_spin = QSpinBox()
        h_spin.setRange(40, 4000)
        h_spin.setValue(self.height())

        def _w_changed(val):
            if self._keep_aspect_ratio and self._aspect_ratio > 0:
                h_spin.blockSignals(True)
                h_spin.setValue(int(val / self._aspect_ratio))
                h_spin.blockSignals(False)

        def _h_changed(val):
            if self._keep_aspect_ratio and self._aspect_ratio > 0:
                w_spin.blockSignals(True)
                w_spin.setValue(int(val * self._aspect_ratio))
                w_spin.blockSignals(False)

        w_spin.valueChanged.connect(_w_changed)
        h_spin.valueChanged.connect(_h_changed)
        form.addRow("Width:", w_spin)
        form.addRow("Height:", h_spin)
        layout.addLayout(form)
        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        layout.addWidget(bb)
        if dlg.exec_() == QDialog.Accepted:
            self.resize(w_spin.value(), h_spin.value())
            self._aspect_ratio = self.width() / max(self.height(), 1)

    # ── Other actions ─────────────────────────────────────────────────

    def _replace_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Replace Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.svg);;All Files (*)")
        if path:
            pm = QPixmap(path)
            if not pm.isNull():
                self._original_pixmap = pm
                self._crop_rect = QRectF(0, 0, 1, 1)
                self._hue_shift = 0
                self._saturation = 0
                self._brightness = 0
                self._pixmap = pm
                self.update()

    def _delete(self):
        """Remove this image from the sheet."""
        sheet = self.parent()
        if sheet and hasattr(sheet, 'parent'):
            sw = sheet.parent()
            while sw and not hasattr(sw, '_images'):
                sw = sw.parent()
            if sw and hasattr(sw, '_images'):
                if self in sw._images:
                    sw._images.remove(self)
        self.deleteLater()

    # ── Serialisation ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialise image to a dict for persistence."""
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        self._original_pixmap.save(buf, "PNG")
        data = base64.b64encode(bytes(buf.data())).decode("ascii")
        buf.close()
        d = {
            "pos_x": self.pos().x(),
            "pos_y": self.pos().y(),
            "width": self.width(),
            "height": self.height(),
            "data": data,
        }
        # Persist crop and colour adjustments.
        cr = self._crop_rect
        if cr != QRectF(0, 0, 1, 1):
            d["crop"] = [cr.x(), cr.y(), cr.width(), cr.height()]
        if self._hue_shift != 0:
            d["hue_shift"] = self._hue_shift
        if self._saturation != 0:
            d["saturation"] = self._saturation
        if self._brightness != 0:
            d["brightness"] = self._brightness
        if not self._keep_aspect_ratio:
            d["keep_aspect_ratio"] = False
        return d

    @classmethod
    def from_dict(cls, d: dict, parent=None) -> EmbeddedImage:
        """Restore an image from a serialised dict."""
        raw = base64.b64decode(d["data"])
        pm = QPixmap()
        pm.loadFromData(raw, "PNG")
        img = cls(pm, parent)
        img.move(d["pos_x"], d["pos_y"])
        img.resize(d["width"], d["height"])
        # Restore crop.
        if "crop" in d:
            cx, cy, cw, ch = d["crop"]
            img._crop_rect = QRectF(cx, cy, cw, ch)
        # Restore colour adjustments.
        img._hue_shift = d.get("hue_shift", 0)
        img._saturation = d.get("saturation", 0)
        img._brightness = d.get("brightness", 0)
        img._keep_aspect_ratio = d.get("keep_aspect_ratio", True)
        img._aspect_ratio = img.width() / max(img.height(), 1)
        # Re-apply if anything changed.
        if img._crop_rect != QRectF(0, 0, 1, 1) or \
                img._hue_shift or img._saturation or img._brightness:
            img._apply_filters()
        return img


# ── Image Adjustments Dialog ──────────────────────────────────────────

class ImageAdjustDialog(QDialog):
    """Slider dialog for hue, saturation, and brightness."""

    def __init__(self, hue=0, saturation=0, brightness=0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Adjustments")
        self.resize(320, 200)

        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Hue slider (-180..180).
        self._hue_slider = QSlider(Qt.Horizontal)
        self._hue_slider.setRange(-180, 180)
        self._hue_slider.setValue(hue)
        self._hue_label = QLabel(str(hue))
        self._hue_slider.valueChanged.connect(
            lambda v: self._hue_label.setText(str(v)))
        row = QHBoxLayout()
        row.addWidget(self._hue_slider)
        row.addWidget(self._hue_label)
        form.addRow("Hue:", row)

        # Saturation slider (-100..100).
        self._sat_slider = QSlider(Qt.Horizontal)
        self._sat_slider.setRange(-100, 100)
        self._sat_slider.setValue(saturation)
        self._sat_label = QLabel(str(saturation))
        self._sat_slider.valueChanged.connect(
            lambda v: self._sat_label.setText(str(v)))
        row2 = QHBoxLayout()
        row2.addWidget(self._sat_slider)
        row2.addWidget(self._sat_label)
        form.addRow("Saturation:", row2)

        # Brightness slider (-100..100).
        self._bri_slider = QSlider(Qt.Horizontal)
        self._bri_slider.setRange(-100, 100)
        self._bri_slider.setValue(brightness)
        self._bri_label = QLabel(str(brightness))
        self._bri_slider.valueChanged.connect(
            lambda v: self._bri_label.setText(str(v)))
        row3 = QHBoxLayout()
        row3.addWidget(self._bri_slider)
        row3.addWidget(self._bri_label)
        form.addRow("Brightness:", row3)

        layout.addLayout(form)

        # Reset button.
        reset_btn = QPushButton("Reset All")
        reset_btn.clicked.connect(self._reset)
        layout.addWidget(reset_btn)

        # Buttons.
        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _reset(self):
        self._hue_slider.setValue(0)
        self._sat_slider.setValue(0)
        self._bri_slider.setValue(0)

    @property
    def hue_shift(self):
        return self._hue_slider.value()

    @property
    def saturation(self):
        return self._sat_slider.value()

    @property
    def brightness(self):
        return self._bri_slider.value()
