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
    # First match wins: "the plus sign ... The cursor appears in the address bar" is about the plus sign.
    "newtab": (r"\bplus sign\b|\bplus button\b|\bNew tab, the plus\b", "Button", r"^(New tab|New Tab|Open a new tab.*|New tab \(Ctrl\+T\))$",
               "New tab is up here", "left"),
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
        label = QFontMetrics(self.font).horizontalAdvance(text) + 24 if text else 0
        width = max(rect.width() + 16, label)
        left = min(rect.x() - 8, rect.right() + 8 - width) if label > rect.width() + 16 else rect.x() - 8
        self.setGeometry(left, rect.y() - 8, width, rect.height() + 16 + (40 if text else 0))
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
            if not self.text:
                return
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
    """Shows at most one pointer at a time and removes it when asked.

    on_located(rect) receives the control's logical rect (or None) so the companion can fly to it.
    """
    def __init__(self, on_located=lambda rect: None):
        super().__init__()
        self.on_located = on_located
        self.label_rings = True  # the companion pointing makes the ring's text label unnecessary
        self.overlay = Overlay()
        self.cache, self.pending = {}, set()
        self.wanted = None     # the (hwnd, target) the step being read points at
        self.locators = set()  # running lookups stay referenced until they finish

    @staticmethod
    def target(step, hwnd):
        # Nothing to point at in a minimized browser (Windows parks it near -32000, -32000).
        return target_for(step) if hwnd and not ctypes.windll.user32.IsIconic(wintypes.HWND(hwnd)) else None

    def prefetch(self, steps, hwnd):
        """Look up every control an answer mentions as soon as it arrives, so pointing is instant when read."""
        for step in steps:
            target = self.target(step, hwnd)
            if target:
                self.locate(hwnd, target)

    def point(self, step, hwnd):
        target = self.target(step, hwnd)
        if not target:
            self.clear()
            return
        key = (hwnd, target)
        self.wanted = key
        if key in self.cache:
            self.show(target, self.cache[key], hwnd)
        else:
            self.locate(hwnd, target)

    def locate(self, hwnd, target):
        key = (hwnd, target)
        if key in self.cache or key in self.pending:
            return
        self.pending.add(key)
        locator = ControlLocator(hwnd, target)
        self.locators.add(locator)
        locator.found.connect(lambda t, rect, key=key: self.located(key, rect))
        locator.finished.connect(lambda locator=locator: self.locators.discard(locator))
        locator.start()

    def located(self, key, rect):
        self.pending.discard(key)
        self.cache[key] = rect
        if self.wanted == key:
            self.show(key[1], rect, key[0])

    def show(self, target, rect, hwnd):
        text, side = TARGETS[target][3], TARGETS[target][4]
        if rect:
            logical = to_logical(rect)
            self.overlay.show_ring(logical, text.replace(" is up here", " is here") if self.label_rings else "")
            self.on_located(logical)
        else:
            self.on_located(None)
            try:
                self.overlay.show_callout(to_logical(window_rect(hwnd)), side, text)
            except (AttributeError, OSError):
                self.overlay.hide()

    def clear(self):
        self.wanted = None
        self.overlay.hide()
        self.on_located(None)
