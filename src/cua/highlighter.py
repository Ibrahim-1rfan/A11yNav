"""Point at the browser control a step talks about: a teal ring on the real control, or an edge callout.

Klicky is a desktop app, so it cannot see inside web pages, but Windows UI Automation exposes the browser's own
toolbar. The overlay is click-through and never takes focus.
"""
import ctypes
from ctypes import wintypes
import re

from PySide6.QtCore import QObject, QPointF, QRect, QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

TEAL = "#1D9E75"
TARGETS = {
    "menu": (r"\bthree dots\b|\bSettings and more\b|\bmenu \(three lines|\bMore \(|\bselect More\b|\bopen the menu\b", "Button",
             r"^(Chrome|Google Chrome|Customize and control.*|Settings and more.*|Open application menu|Application menu)$",
             "The menu is up here", "right"),
    "address": (r"\baddress bar\b", "Edit", r"^(Address and search bar|Address bar|Search or enter address|Search with .* or enter address)$",
                "The address bar is up here", "left"),
    "bookmark": (r"\bBookmark star\b|\bstar\b", "Button", r"^(Bookmark this tab|Bookmark this page|Add this page to favou?rites.*|Edit bookmark.*)$",
                 "The star is up here", "right"),
    "reader": (r"\bReading mode in the address bar\b|\bReader View icon\b|\bReading mode button\b", "Button",
               r"^(Reading mode|Enter Reading mode.*|Immersive Reader.*|Toggle reader view.*|Reader view.*)$",
               "Reading mode is up here", "left"),
}


def target_for(step):
    """Which browser control a step refers to, if any."""
    return next((key for key, (pattern, *_rest) in TARGETS.items() if re.search(pattern, step, re.I)), None)


def to_logical(rect):
    """Physical screen pixels (UI Automation, Win32) to Qt's logical coordinates on the right monitor."""
    left, top, right, bottom = rect
    for screen in QGuiApplication.screens():
        g, ratio = screen.geometry(), screen.devicePixelRatio()
        # Qt keeps each screen's top-left in native pixels and scales sizes by the screen's ratio.
        if g.x() <= left < g.x() + g.width() * ratio and g.y() <= top < g.y() + g.height() * ratio:
            return QRect(int(g.x() + (left - g.x()) / ratio), int(g.y() + (top - g.y()) / ratio),
                         int((right - left) / ratio), int((bottom - top) / ratio))
    return QRect(left, top, right - left, bottom - top)


def window_rect(hwnd):
    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


class ControlLocator(QThread):
    """Finds a toolbar control in the browser window through UI Automation, off the UI thread."""
    found = Signal(str, object)

    def __init__(self, hwnd, target):
        super().__init__()
        self.hwnd, self.target = hwnd, target

    def run(self):
        import sys
        import pythoncom
        sys.coinit_flags = 2  # this thread is single-threaded COM; tell pywinauto before it is imported
        pythoncom.CoInitialize()
        try:
            self.found.emit(self.target, self.locate())
        except Exception:
            self.found.emit(self.target, None)
        finally:
            pythoncom.CoUninitialize()

    def locate(self):
        from pywinauto import Desktop
        _pattern, control_type, name_pattern, *_rest = TARGETS[self.target]
        window = Desktop(backend="uia").window(handle=self.hwnd).wrapper_object()
        names = re.compile(name_pattern, re.I)
        top = window_rect(self.hwnd)[1]
        for control in window.descendants(control_type=control_type, depth=14):
            info = control.element_info
            if names.match(info.name or "") or (self.target == "address" and (info.automation_id or "") == "urlbar-input"):
                r = info.rectangle
                # Browser chrome sits in the top band of the window; skip look-alikes inside the page.
                if r.width() > 0 and r.top - top < 220 and control.is_visible():
                    return r.left, r.top, r.right, r.bottom
        return None


class Overlay(QWidget):
    """Click-through teal ring around a control, or an arrow callout at the window edge."""
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.text, self.ring, self.side = "", None, "right"
        self.font = QFont("Segoe UI")
        self.font.setPixelSize(16)
        self.font.setBold(True)

    def show_ring(self, rect, text):
        """rect: logical QRect of the control."""
        self.text, self.ring = text, True
        label = QFontMetrics(self.font).horizontalAdvance(text) + 24
        width = max(rect.width() + 16, label)
        left = min(rect.x() - 8, rect.right() + 8 - width) if label > rect.width() + 16 else rect.x() - 8
        self.setGeometry(left, rect.y() - 8, width, rect.height() + 16 + 40)
        self.ring_rect = QRectF(rect.x() - 8 - left + 1.5, 1.5, rect.width() + 13, rect.height() + 13)
        self.show()
        self.raise_()
        self.update()

    def show_callout(self, window, side, text):
        """window: logical QRect of the browser; an arrow points to its top corner."""
        self.text, self.ring, self.side = text, False, side
        width = QFontMetrics(self.font).horizontalAdvance(text) + 76
        x = window.right() - width - 12 if side == "right" else window.x() + 140
        self.setGeometry(x, window.y() + 70, width, 60)
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self.font)
        teal = QColor(TEAL)
        if self.ring:
            p.setPen(QPen(teal, 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(self.ring_rect, 8, 8)
            box = QRectF(0, self.ring_rect.bottom() + 6, self.width(), 32)
        else:
            box = QRectF(0, 22, self.width() - 2, 36)
            arrow = QPainterPath()
            tip_x = self.width() - 24 if self.side == "right" else 24
            arrow.moveTo(QPointF(tip_x, 2))
            arrow.lineTo(QPointF(tip_x - 10, 22))
            arrow.lineTo(QPointF(tip_x + 10, 22))
            arrow.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(teal)
            p.drawPath(arrow)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(teal)
        p.drawRoundedRect(box, 8, 8)
        p.setPen(QColor("white"))
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, self.text)


class Highlighter(QObject):
    """Shows at most one pointer at a time and removes it when asked."""
    def __init__(self):
        super().__init__()
        self.overlay = Overlay()
        self.locator, self.request = None, 0
        self.cache = {}

    def point(self, step, hwnd):
        # Nothing to point at in a minimized browser (Windows parks it near -32000, -32000).
        target = target_for(step) if hwnd and not ctypes.windll.user32.IsIconic(wintypes.HWND(hwnd)) else None
        if not target:
            self.clear()
            return
        self.request += 1
        request = self.request
        if (hwnd, target) in self.cache:
            self.show(target, self.cache[(hwnd, target)], hwnd)
            return
        locator = ControlLocator(hwnd, target)
        locator.found.connect(lambda t, rect: self.located(request, hwnd, t, rect))
        self.locator = locator
        locator.start()

    def located(self, request, hwnd, target, rect):
        self.cache[(hwnd, target)] = rect
        if request == self.request:
            self.show(target, rect, hwnd)

    def show(self, target, rect, hwnd):
        text, side = TARGETS[target][3], TARGETS[target][4]
        if rect:
            self.overlay.show_ring(to_logical(rect), text.replace(" is up here", " is here"))
        else:
            try:
                self.overlay.show_callout(to_logical(window_rect(hwnd)), side, text)
            except (AttributeError, OSError):
                self.overlay.hide()

    def clear(self):
        self.request += 1
        self.overlay.hide()
