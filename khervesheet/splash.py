"""Startup splash screen.

The picture is painted with QPainter at runtime rather than shipped as
a PNG: it stays crisp on any DPI, carries the live version string, and
needs no extra file in the PyInstaller bundle.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QColor, QFont, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPixmap)
from PyQt5.QtWidgets import QApplication, QSplashScreen

from . import APP_NAME, __version__
from . import appmark

WIDTH, HEIGHT = 640, 380
_TOP = QColor("#1f7a3a")
_BOTTOM = QColor("#0f3d24")
_INK = QColor("#ffffff")


def _grid(p, rect):
    """Faint spreadsheet grid on the right half, fading to the left."""
    step = 28.0
    x = rect.left()
    while x <= rect.right():
        alpha = int(10 + 40 * (x - rect.left()) / rect.width())
        p.setPen(QPen(QColor(255, 255, 255, alpha), 1))
        p.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        x += step * 2.4
    y = rect.top()
    while y <= rect.bottom():
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        y += step


def _curve(p, rect):
    """A fitted peak over scattered points — the app's two jobs at once."""
    def f(t):
        return (0.75 * math.exp(-((t - 0.42) / 0.11) ** 2)
                + 0.35 * math.exp(-((t - 0.68) / 0.08) ** 2) + 0.08)

    def pt(t, v):
        return QPointF(rect.left() + t * rect.width(),
                       rect.bottom() - v * rect.height())

    path = QPainterPath(pt(0.0, f(0.0)))
    for i in range(1, 121):
        t = i / 120.0
        path.lineTo(pt(t, f(t)))
    fill = QPainterPath(path)
    fill.lineTo(pt(1.0, 0.0))
    fill.lineTo(pt(0.0, 0.0))
    fill.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 28))
    p.drawPath(fill)
    pen = QPen(QColor("#b8f5c8"), 2.4)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 190))
    for i in range(24):
        t = (i + 0.5) / 24.0
        wobble = 0.035 * math.sin(i * 2.7)
        p.drawEllipse(pt(t, f(t) + wobble), 2.6, 2.6)


def splash_pixmap(dpr: float = 1.0) -> QPixmap:
    """Render the startup picture at *dpr* device pixels per point."""
    pm = QPixmap(int(WIDTH * dpr), int(HEIGHT * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    frame = QRectF(0, 0, WIDTH, HEIGHT)
    bg = QLinearGradient(frame.topLeft(), frame.bottomRight())
    bg.setColorAt(0.0, _TOP)
    bg.setColorAt(1.0, _BOTTOM)
    clip = QPainterPath()
    clip.addRoundedRect(frame, 14, 14)
    p.setClipPath(clip)
    p.fillRect(frame, bg)

    _grid(p, QRectF(250, 0, WIDTH - 250, HEIGHT))
    _curve(p, QRectF(300, 120, 310, 170))

    mark = appmark.paint(int(112 * dpr))
    mark.setDevicePixelRatio(dpr)
    p.drawPixmap(QPointF(40, 52), mark)

    p.setPen(_INK)
    title = QFont()
    title.setPointSizeF(34)
    title.setBold(True)
    p.setFont(title)
    p.drawText(QRectF(40, 180, 400, 54), Qt.AlignLeft | Qt.AlignVCenter,
               APP_NAME)
    sub = QFont()
    sub.setPointSizeF(12.5)
    p.setFont(sub)
    p.setPen(QColor(255, 255, 255, 215))
    p.drawText(QRectF(42, 232, 400, 24), Qt.AlignLeft | Qt.AlignVCenter,
               "Spreadsheets, charts and curve fitting for science")
    small = QFont()
    small.setPointSizeF(9.5)
    p.setFont(small)
    p.setPen(QColor(255, 255, 255, 150))
    p.drawText(QRectF(42, HEIGHT - 34, 300, 20),
               Qt.AlignLeft | Qt.AlignVCenter,
               f"Version {__version__}")
    p.drawText(QRectF(WIDTH - 322, HEIGHT - 34, 300, 20),
               Qt.AlignRight | Qt.AlignVCenter,
               "© 2026 Gwilherm Kerherve · GPL-3.0")
    p.end()
    return pm


#: The steps main() reports, in order; the bar advances through them.
STEPS = ("Loading the formula engine", "Building the window",
         "Opening the workbook", "Ready")


class Splash(QSplashScreen):
    """The start-up picture plus a status line and a progress bar."""

    def __init__(self):
        screen = QApplication.primaryScreen()
        ratio = screen.devicePixelRatio() if screen is not None else 1.0
        super().__init__(splash_pixmap(max(1.0, ratio)),
                         Qt.WindowStaysOnTopHint)
        # Lets the rounded corners show the desktop, not a black square.
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.step_text = STEPS[0]
        self.fraction = 0.0

    def step(self, text: str):
        """Show *text* and advance the bar to its place in STEPS; the
        event loop gets a turn so it paints."""
        self.step_text = text
        if text in STEPS:
            self.fraction = STEPS.index(text) / (len(STEPS) - 1)
        self.repaint()
        QApplication.processEvents()

    def drawContents(self, p: QPainter):
        p.setRenderHint(QPainter.Antialiasing)
        bar = QRectF(42, HEIGHT - 62, WIDTH - 84, 5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 35))
        p.drawRoundedRect(bar, 2.5, 2.5)
        if self.fraction > 0:
            p.setBrush(QColor("#b8f5c8"))
            p.drawRoundedRect(QRectF(bar.x(), bar.y(),
                                     bar.width() * self.fraction,
                                     bar.height()), 2.5, 2.5)
        p.setPen(QColor(255, 255, 255, 200))
        small = QFont()
        small.setPointSizeF(10.5)
        p.setFont(small)
        dots = "" if self.step_text == STEPS[-1] else "\u2026"
        p.drawText(QRectF(42, HEIGHT - 86, 400, 20),
                   Qt.AlignLeft | Qt.AlignVCenter, self.step_text + dots)
