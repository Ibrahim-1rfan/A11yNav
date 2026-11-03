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
# (words in a step, UI Automation control type, name pattern or "class:" pattern, callout text, side of the window)
# Names and classes were read from real Chrome and Edge windows; the profile button is named after the profile,
# so it is matched by class, and every tab has its own close button, so the selected tab's one is chosen.
TARGETS = {
    # Inside the browser's open main menu (its own popup window). Chromium browsers name the zoom buttons
    # "Zoom in"/"Zoom out" or, in other versions, "Make text larger"/"Make text smaller".
    "zoom": (r"\bNext to Zoom, select Zoom in\b", "Button", r"^(Zoom in|Make text larger|Zoom out|Make text smaller)\b",
             "Zoom is in the menu", "right"),
    "menusettings": (r"\bSelect Settings near the bottom of the menu\b", "MenuItem", r"^Settings\b", "Settings is in the menu", "right"),
    # First match wins: "the plus sign ... The cursor appears in the address bar" is about the plus sign.
    "newtab": (r"\bplus sign\b|\bplus button\b|\bNew tab, the plus\b", "Button", r"^(New tab|New Tab|Open a new tab.*|New tab \(Ctrl\+T\))$",
               "New tab is up here", "left"),
    "back": (r"\bselect Back\b", "Button", r"^Back$", "Back is up here", "left"),
    "refresh": (r"\bselect (Reload|Refresh)\b", "Button", r"^(Reload|Refresh)$", "Refresh is up here", "left"),
    "closetab": (r"\bthe X on the tab\b", "Button", r"class:^(Edge)?TabCloseButton$", "Your tab's X is up here", "left"),
    "extensions": (r"\bExtensions, to the right of the address bar\b", "Button", r"^Extensions$", "Extensions are up here", "right"),
    "profile": (r"\bselect Profile\b|\bthe Profile icon\b", "Button", r"class:^(Edge)?AvatarToolbarButton$", "Your profile is up here", "right"),
    "menu": (r"\bthree dots\b|\bSettings and more\b|\bmenu \(three lines|\bMore \(|\bselect More\b|\bopen the menu\b", "Button",
             r"^(Chrome|Google Chrome|Customize and control.*|Settings and more.*|Open application menu|Application menu)$",
             "The menu is up here", "right"),
    "bookmark": (r"\bBookmark star\b|\bstar\b", "Button", r"^(Bookmark this tab|Bookmark this page|Add this page to favou?rites.*|Edit bookmark.*|Edit favou?rite.*)$",
                 "The star is up here", "right"),
    "reader": (r"\bReading mode in the address bar\b|\bReader View icon\b|\bReading mode button\b", "Button",
               r"^(Reading mode|Enter Reading mode.*|Immersive Reader.*|Toggle reader view.*|Reader view.*)$",
               "Reading mode is up here", "left"),
    # Last: many steps mention the address bar only to say where something else is.
    "address": (r"\baddress bar\b", "Edit", r"^(Address and search bar|Address bar|Search or enter address|Search with .* or enter address)$",
                "The address bar is up here", "left"),
}


POPUP_TARGETS = {"zoom", "menusettings"}   # only exist while the menu is open; never cached


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


def process_windows(hwnd):
    """Visible top-level windows of the same process, the main window first (menus are separate windows)."""
    user32 = ctypes.windll.user32
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    found = []
    def visit(h, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(owner))
        if owner.value == pid.value and user32.IsWindowVisible(h) and not user32.IsIconic(h) and h != hwnd:
            found.append(h)
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(visit), 0)
    return [hwnd] + found


def browser_chrome(root, max_depth=14):
    """The browser's own controls: walk the UI Automation tree but never enter the web page (Document).
    A busy page has hundreds of elements; skipping it took lookups from about 3 s to a fraction of that."""
    stack = [(root, 0)]
    while stack:
        info, depth = stack.pop()
        if depth >= max_depth:
            continue
        try:
            children = info.children()
        except Exception:
            continue
        kept = [child for child in children if child.control_type != "Document"]
        yield from kept  # in screen order, so the first match is the first such control
        stack.extend((child, depth + 1) for child in reversed(kept))


class ControlLocator(QThread):
    """Finds a toolbar control in the browser window through UI Automation, off the UI thread."""
    found = Signal(str, object)

    def __init__(self, hwnd, target):
        super().__init__()
        self.hwnd, self.target = hwnd, target
        self.kind = "control"  # or "row": only the menu row was found, not the exact buttons
        self.info = None       # the matched UI Automation element, so an action can press it

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
        from pywinauto.controls.uiawrapper import UIAWrapper
        _pattern, control_type, name_pattern, *_rest = TARGETS[self.target]
        by_class = name_pattern.startswith("class:")
        matcher = re.compile(name_pattern[6:] if by_class else name_pattern, re.I)
        popup = self.target in POPUP_TARGETS
        top = window_rect(self.hwnd)[1]
        matches, rows = [], []
        # Menus open in their own window owned by the browser process, so search all of its windows for those.
        for hwnd in (process_windows(self.hwnd) if popup else [self.hwnd]):
            window = Desktop(backend="uia").window(handle=hwnd).wrapper_object()
            for info in browser_chrome(window.element_info):
                if self.target == "zoom" and info.control_type != control_type and re.match(r"^Zoom\b", info.name or "", re.I):
                    r = info.rectangle
                    if r.width() > 0 and info.visible:
                        rows.append((r.left, r.top, r.right, r.bottom))  # the whole "Zoom" row, if the buttons are unnamed
                    continue
                if info.control_type != control_type:
                    continue
                text = info.class_name if by_class else info.name
                if matcher.match(text or "") or (self.target == "address" and (info.automation_id or "") == "urlbar-input"):
                    r = info.rectangle
                    # Toolbar controls sit in the top band of the window; menu items can be anywhere in the menu.
                    if r.width() > 0 and (popup or r.top - top < 220) and info.visible and self.on_current_tab(UIAWrapper(info)):
                        if self.target != "zoom":
                            self.info = info
                            return r.left, r.top, r.right, r.bottom
                        matches.append((r.left, r.top, r.right, r.bottom))
        if matches:  # the zoom row: one ring around both the minus and the plus
            return min(m[0] for m in matches), min(m[1] for m in matches), max(m[2] for m in matches), max(m[3] for m in matches)
        if rows:
            self.kind = "row"
            return rows[0]
        return None

    def on_current_tab(self, control):
        """Every tab has a close button; only the selected tab's one is the page the user is on."""
        if self.target != "closetab":
            return True
        try:
            return bool(control.parent().iface_selection_item.CurrentIsSelected)
        except Exception:
            return False


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
        self.cache, self.pending, self.kinds = {}, set(), {}
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
            if target and target not in POPUP_TARGETS:
                self.locate(hwnd, target)

    def point(self, step, hwnd):
        target = self.target(step, hwnd)
        if not target:
            self.clear()
            return
        key = (hwnd, target)
        self.wanted = key
        if key in self.cache and target not in POPUP_TARGETS:
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
        locator.found.connect(lambda t, rect, key=key, locator=locator: self.located(key, rect, getattr(locator, "kind", "control")))
        locator.finished.connect(lambda locator=locator: self.locators.discard(locator))
        locator.start()

    def located(self, key, rect, kind="control"):
        self.kinds[key] = kind
        self.pending.discard(key)
        if key[1] not in POPUP_TARGETS:
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

    @property
    def current_target(self):
        return self.wanted[1] if self.wanted else None

    @property
    def current_kind(self):
        return self.kinds.get(self.wanted, "control") if self.wanted else "control"

    def clear(self):
        self.wanted = None
        self.overlay.hide()
        self.on_located(None)
