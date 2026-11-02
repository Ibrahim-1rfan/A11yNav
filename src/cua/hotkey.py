"""System-wide shortcut that summons Klicky from any application (Windows RegisterHotKey).

The hotkey only shows Klicky's question box. It never starts a search or sends input elsewhere.
"""
import ctypes
from ctypes import wintypes
import os
from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from .config import parse_hotkey

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
HOTKEY_ID = 0x4B4C  # "KL"


class GlobalHotkey(QObject, QAbstractNativeEventFilter):
    triggered = Signal()

    def __init__(self):
        QObject.__init__(self)
        QAbstractNativeEventFilter.__init__(self)
        self.registered = False
        self.installed = False

    def register(self, text):
        """Register (or re-register) the shortcut. Returns False when another app already owns it."""
        self.unregister()
        if os.name != "nt" or not text:
            return not text
        from PySide6.QtCore import QCoreApplication
        if not self.installed:
            QCoreApplication.instance().installNativeEventFilter(self)
            self.installed = True
        modifiers, key = parse_hotkey(text)
        # hWnd NULL posts WM_HOTKEY to this (GUI) thread's queue, which Qt passes to native filters.
        self.registered = bool(ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID, modifiers | MOD_NOREPEAT, key))
        return self.registered

    def unregister(self):
        if self.registered:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            self.registered = False

    def nativeEventFilter(self, event_type, message):
        if self.registered and event_type in (b"windows_generic_MSG", "windows_generic_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.triggered.emit()
                return True, 0
        return False, 0
