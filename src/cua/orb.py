"""The voice orb: a real button with two rings that follow the voice, breathe while thinking and pulse gently
while speaking. Only scale changes; nothing moves on screen when reduced motion is on.
"""
import ctypes
import math
import os
import time
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPushButton

TEAL, TEAL_DARK, RING = "#1D9E75", "#0F6E56", "#9FE1CB"
ICONS = {"idle": "mic", "listening": "mic", "typing": "mic", "done": "mic", "error": "mic", "thinking": "sparkle", "speaking": "speaker"}


def reduced_motion():
    """Windows 'Show animations in Windows' switched off counts as prefers-reduced-motion."""
    if os.name != "nt":
        return False
    enabled = ctypes.c_bool(True)
    try:
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0)  # SPI_GETCLIENTAREAANIMATION
    except (AttributeError, OSError):
        return False
    return not enabled.value


class Orb(QPushButton):
    def __init__(self, diameter=56, focus_color="#085041"):
        super().__init__()
        self.focus_color = focus_color
        self.set_diameter(diameter)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode = "idle"
        self.level, self.target = 0.0, 0.0
        self.scales = (1.0, 1.0, 1.0)
        self.started = time.monotonic()
        self.reduced = reduced_motion()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)

    def set_diameter(self, diameter):
        self.diameter = diameter
        side = int(diameter * 2.1)  # room for the outer ring at full scale
        # Own size rules: an app-wide QPushButton min-height would otherwise squash the orb and clip its rings.
        self.setStyleSheet(f"QPushButton {{ min-width:{side}px; max-width:{side}px; min-height:{side}px; max-height:{side}px;"
                           " padding:0; margin:0; border:none; background:transparent; }")
        self.setFixedSize(side, side)

    def set_mode(self, mode, label):
        self.mode = mode
        self.setAccessibleName(label)
        self.setToolTip(label)
        if mode != "listening":
            self.target = 0.0
        self.started = time.monotonic()
        self.update()

    def set_level(self, rms):
        """Microphone loudness (RMS). Normalised as in the motion spec: x6, clamped to 0..1."""
        self.target = max(0.0, min(1.0, rms * 6))

    def start(self):
        if not self.reduced:
            self.timer.start()

    def stop(self):
        self.timer.stop()
        self.level, self.target, self.scales = 0.0, 0.0, (1.0, 1.0, 1.0)
        self.update()

    def tick(self):
        t = time.monotonic() - self.started
        if self.mode == "listening":
            self.level += (self.target - self.level) * .25
            l = self.level
            self.scales = (1 + l * .12, 1 + l * .45, 1 + l * .85)
        elif self.mode == "thinking":
            p = (1 - math.cos(2 * math.pi * t / 2.8)) / 2  # slow, steady breathing; not voice-driven
            self.scales = (1 + p * .05, 1 + p * .18, 1 + p * .3)
        elif self.mode == "speaking":
            s = .5 + .25 * math.sin(2 * math.pi * t * 1.7) + .25 * math.sin(2 * math.pi * t * 2.9 + 1)
            self.scales = (1 + s * .04, 1 + s * .15, 1 + s * .25)  # smaller than listening, so the two look different
        else:
            self.level *= .8
            self.scales = tuple(1 + (scale - 1) * .8 for scale in self.scales)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = self.diameter / 2
        orb, inner, outer = (1.0, 1.0, 1.0) if self.reduced else self.scales
        painter.setPen(Qt.PenStyle.NoPen)
        for scale, alpha in ((outer, .20), (inner, .35)):
            ring = QColor(RING)
            ring.setAlphaF(alpha)
            painter.setBrush(ring)
            painter.drawEllipse(center, radius * scale, radius * scale)
        painter.setBrush(QColor(TEAL_DARK if self.mode == "thinking" else TEAL))
        painter.drawEllipse(center, radius * orb, radius * orb)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(self.focus_color), 3))
            painter.drawEllipse(center, radius * orb + 5, radius * orb + 5)
        painter.setPen(QPen(QColor("white"), max(2.0, radius * .09), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        {"mic": self.draw_mic, "sparkle": self.draw_sparkle, "speaker": self.draw_speaker}[ICONS.get(self.mode, "mic")](painter, center, radius * .42)

    def draw_mic(self, p, c, s):
        p.setBrush(QColor("white"))
        p.drawRoundedRect(QRectF(c.x() - s * .35, c.y() - s * .9, s * .7, s * 1.15), s * .35, s * .35)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(c.x() - s * .65, c.y() - s * .55, s * 1.3, s * 1.1), 200 * 16, 140 * 16)
        p.drawLine(QPointF(c.x(), c.y() + s * .55), QPointF(c.x(), c.y() + s * .9))

    def draw_sparkle(self, p, c, s):
        path = QPainterPath(QPointF(c.x(), c.y() - s))
        for dx, dy in ((.22, -.22), (1, 0), (.22, .22), (0, 1), (-.22, .22), (-1, 0), (-.22, -.22), (0, -1)):
            path.lineTo(QPointF(c.x() + dx * s, c.y() + dy * s))
        p.setBrush(QColor("white"))
        p.drawPath(path)

    def draw_speaker(self, p, c, s):
        path = QPainterPath(QPointF(c.x() - s * .8, c.y() - s * .3))
        for x, y in ((-.4, -.3), (.05, -.75), (.05, .75), (-.4, .3), (-.8, .3)):
            path.lineTo(QPointF(c.x() + x * s, c.y() + y * s))
        path.closeSubpath()
        p.setBrush(QColor("white"))
        p.drawPath(path)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for r in (.45, .8):
            p.drawArc(QRectF(c.x() + .05 * s - r * s, c.y() - r * s, 2 * r * s, 2 * r * s), -45 * 16, 90 * 16)
