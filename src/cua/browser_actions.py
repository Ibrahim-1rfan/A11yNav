"""A fixed set of simple browser actions Klicky can do for the person.

Each action presses the browser's real button through UI Automation (no synthetic mouse click, the person's pointer
never moves) and falls back to the browser's own keyboard shortcut. Nothing a model writes is ever executed; only the
entries below can run, and only in the browser window the person was using.
"""
import ctypes
import os
import threading
import time
from PySide6.QtCore import QThread, Signal

# action: target button (or None), keyboard fallback, internal page (opened in a new tab), what to say
SPECS = {
    "newtab": dict(target="newtab", keys=("ctrl", "t"), doing="Opening a new tab", done="Opened a new tab."),
    "refresh": dict(target="refresh", keys=("f5",), doing="Refreshing the page", done="Refreshed the page."),
    "back": dict(target="back", keys=("alt", "left"), doing="Going back", done="Went back a page."),
    "forward": dict(target=None, keys=("alt", "right"), doing="Going forward", done="Went forward a page."),
    "zoomin": dict(target=None, keys=("ctrl", "="), doing="Zooming in", done="Zoomed in. Ask again to zoom in more."),
    "zoomout": dict(target=None, keys=("ctrl", "-"), doing="Zooming out", done="Zoomed out."),
    "zoomreset": dict(target=None, keys=("ctrl", "0"), doing="Resetting the zoom", done="The page is back to normal size."),
    "closetab": dict(target="closetab", keys=("ctrl", "w"), doing="Closing this tab",
                     done="Closed the tab. Say reopen the tab if that was a mistake."),
    "reopen": dict(target=None, keys=("ctrl", "shift", "t"), doing="Bringing the tab back", done="Brought the last closed tab back."),
    "history": dict(target=None, keys=("ctrl", "h"), doing="Opening your history", done="Opened your history."),
    "bookmark": dict(target="bookmark", keys=("ctrl", "d"), doing="Saving this page",
                     done="Saved this page. Press Enter to finish, or type a new name first."),
    "settings": dict(target=None, keys=(), doing="Opening settings", done="Opened settings in a new tab.",
                     pages={"chrome": "chrome://settings", "edge": "edge://settings", "firefox": "about:preferences"}),
    "extensions": dict(target=None, keys=(), doing="Opening your extensions", done="Opened your extensions in a new tab.",
                       pages={"chrome": "chrome://extensions", "edge": "edge://extensions", "firefox": "about:addons"}),
}
FLY_S = .8     # let the companion fly to the button before it "clicks"
PRESS_S = .15  # the click animation, then the real press


class ActionWorker(QThread):
    located = Signal(object)   # physical rect of the button, or None when the keyboard is used
    pressing = Signal()
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, hwnd, action, app, locator_factory=None, keys=None, foreground=None):
        super().__init__()
        self.hwnd, self.action, self.app = hwnd, action, app or "chrome"
        self.spec = SPECS[action]
        self.stop_event = threading.Event()
        self.locator_factory = locator_factory
        self.send_keys = keys or self._send_keys
        self.bring_forward = foreground or self._bring_forward

    def run(self):
        import sys
        sys.coinit_flags = 2
        if os.name == "nt":
            import pythoncom
            pythoncom.CoInitialize()
        try:
            self.perform()
        except Exception:
            self.failed.emit("I couldn't do that in the browser. You can ask me how to do it instead.")
        finally:
            if os.name == "nt":
                import pythoncom
                pythoncom.CoUninitialize()

    def perform(self):
        target = self.spec["target"]
        if target and self.press_button(target):
            self.done.emit(self.spec["done"])
            return
        self.located.emit(None)
        if self.stop_event.is_set():
            return
        if not self.bring_forward():
            self.failed.emit("I couldn't reach the browser window. Click into it, then ask me again.")
            return
        if "pages" in self.spec:
            self.open_page(self.spec["pages"].get(self.app, self.spec["pages"]["chrome"]))
        else:
            self.send_keys(self.spec["keys"])
        self.done.emit(self.spec["done"])

    def press_button(self, target):
        """Find the real button, let the companion reach it, then press it. False means use the keyboard."""
        from .highlighter import ControlLocator
        locator = (self.locator_factory or ControlLocator)(self.hwnd, target)
        rect = locator.locate()
        if not rect or locator.info is None:
            return False
        self.located.emit(rect)
        if self.stop_event.wait(FLY_S):
            return True
        self.pressing.emit()
        time.sleep(PRESS_S)
        try:
            from pywinauto.controls.uiawrapper import UIAWrapper
            UIAWrapper(locator.info).invoke()
            return True
        except Exception:
            return False

    def open_page(self, page):
        """Open the browser's own settings or extensions page in a new tab, through the verified address bar."""
        from .browser import WindowsBrowser
        self.send_keys(("ctrl", "t"))
        time.sleep(.5)
        browser = WindowsBrowser()
        browser.hwnd = self.hwnd
        browser.focus_address(self.stop_event)
        browser.set_address(page, self.stop_event)
        browser.submit(page, self.stop_event)

    def _bring_forward(self):
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow(self.hwnd)
        for _ in range(10):
            if user32.GetForegroundWindow() == self.hwnd:
                return True
            time.sleep(.05)
        return False

    def _send_keys(self, keys):
        import pyautogui
        pyautogui.hotkey(*keys)
