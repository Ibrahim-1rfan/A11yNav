"""Windows browser discovery, foreground guarding and address-bar interaction.

Uses UI Automation for address values, never the clipboard or arbitrary model keys.
Only process-identified browser windows are trusted; title text alone is insufficient.
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import time
import webbrowser
from .config import UserError
from .models import Cancelled

EXECUTABLES = {"edge": "msedge.exe", "chrome": "chrome.exe", "firefox": "firefox.exe"}


def enable_dpi_awareness():
    if os.name == "nt":
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            ctypes.windll.shcore.SetProcessDpiAwareness(2)


def executable_for(preference):
    if preference == "default":
        return None
    name = EXECUTABLES[preference]
    import winreg
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for flags in (winreg.KEY_READ | winreg.KEY_WOW64_64KEY, winreg.KEY_READ | winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(root, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}", 0, flags) as key:
                    path = Path(winreg.QueryValue(key, None).strip('"'))
                    if path.is_file():
                        return path
            except OSError:
                pass
    suffix = {"edge": "Microsoft/Edge/Application/msedge.exe", "chrome": "Google/Chrome/Application/chrome.exe", "firefox": "Mozilla Firefox/firefox.exe"}[preference]
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        path = Path(os.environ.get(env, "")) / suffix
        if path.is_file():
            return path
    return None


class WindowsBrowser:
    def __init__(self, preference="default"):
        if os.name != "nt":
            raise UserError("Desktop control currently requires Windows 10 or 11.")
        self.preference = preference
        self.hwnd = None
        self.user32 = ctypes.windll.user32
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.kernel = ctypes.windll.kernel32
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]

    def process_name(self, hwnd):
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = self.kernel.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return ""
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            if self.kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return Path(buffer.value).name.lower()
            return ""
        finally:
            self.kernel.CloseHandle(handle)

    def windows(self):
        found = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def visit(hwnd, _):
            if self.user32.IsWindowVisible(hwnd) and self.process_name(hwnd) in EXECUTABLES.values():
                found.append(hwnd)
            return True
        callback = callback_type(visit)
        self.user32.EnumWindows(callback, 0)
        return found

    def guard(self):
        if not self.hwnd or self.user32.GetForegroundWindow() != self.hwnd or self.process_name(self.hwnd) not in EXECUTABLES.values():
            raise UserError("The browser lost focus. I stopped to avoid typing in another application. Keep the browser in front and start again.")

    def open(self, home, stop):
        # OS bootstrap is trusted application code, not an inferred model action.
        windows = self.windows()
        preferred = [h for h in windows if self.preference == "default" or self.process_name(h) == EXECUTABLES[self.preference]]
        if preferred:
            foreground = self.user32.GetForegroundWindow()
            self.hwnd = foreground if foreground in preferred else preferred[0]
            self.user32.ShowWindow(self.hwnd, 9)
            self.user32.SetForegroundWindow(self.hwnd)
            if self.user32.GetForegroundWindow() != self.hwnd:
                from pywinauto import Desktop
                Desktop(backend="win32").window(handle=self.hwnd).set_focus()
            if stop.wait(.4):
                raise Cancelled()
            self.guard()
            # New tab preserves whatever the user was doing in their old tab.
            import pyautogui
            pyautogui.hotkey("ctrl", "t")
            if stop.wait(.4):
                raise Cancelled()
            self.focus_address(stop)
            self.set_address(home, stop)
            self.submit(home, stop)
        else:
            executable = executable_for(self.preference)
            if stop.is_set():
                raise Cancelled()
            if executable:
                subprocess.Popen([str(executable), home], shell=False)
            elif not webbrowser.open(home, new=2):
                raise UserError("No browser could be opened. Install or select Edge, Chrome or Firefox, then try again.")
            deadline = time.monotonic()+12
            while time.monotonic() < deadline:
                if stop.wait(.2):
                    raise Cancelled()
                foreground = self.user32.GetForegroundWindow()
                if self.process_name(foreground) in EXECUTABLES.values():
                    self.hwnd = foreground
                    break
            if not self.hwnd:
                raise UserError("I could not verify a supported browser window. Bring Edge, Chrome or Firefox to the front and try again.")
        self.guard()

    def bounds(self):
        self.guard()
        rect = wintypes.RECT()
        self.user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        # Crop to the virtual desktop; maximized windows can have negative borders.
        left = self.user32.GetSystemMetrics(76)
        top = self.user32.GetSystemMetrics(77)
        right = left+self.user32.GetSystemMetrics(78)
        bottom = top+self.user32.GetSystemMetrics(79)
        return max(left,rect.left), max(top,rect.top), min(right,rect.right), min(bottom,rect.bottom)

    def address(self):
        from pywinauto import Desktop
        from pywinauto import timings
        from pywinauto.uia_defines import IUIA
        import comtypes.client
        import comtypes.gen.UIAutomationClient as uia
        # The older CUIAutomation object lacks configurable call timeouts.
        # CUIAutomation8 is available on supported Windows 10/11 machines.
        if not getattr(self, "_uia_configured", False):
            client = comtypes.client.CreateObject(uia.CUIAutomation8, interface=uia.IUIAutomation2)
            client.ConnectionTimeout = 2000
            client.TransactionTimeout = 2000
            IUIA().iuia = client
            self._uia_configured = True
        timings.Timings.window_find_timeout = 2
        timings.Timings.exists_timeout = 2
        window = Desktop(backend="uia").window(handle=self.hwnd)
        # Known browser chrome identifiers/names. Do not select page search fields.
        for edit in window.descendants(control_type="Edit", depth=8):
            info = edit.element_info
            aid = (info.automation_id or "").lower()
            name = (info.name or "").lower()
            if aid in {"urlbar-input", "address and search bar", "omnibox"} or name in {"address and search bar", "address bar", "search or enter address", "search with google or enter address", "search with bing or enter address"}:
                ancestor = edit.parent()
                inside_page = False
                reached_window = False
                for _ in range(12):
                    if ancestor.element_info.control_type == "Document":
                        inside_page = True
                        break
                    if ancestor.handle == self.hwnd:
                        reached_window = True
                        break
                    ancestor = ancestor.parent()
                    if ancestor is None:
                        inside_page = True
                        break
                if reached_window and not inside_page and edit.is_visible():
                    return edit
        raise UserError("I cannot identify this browser's address bar. Try an English-language Edge, Chrome or Firefox window.")

    def address_value(self):
        self.guard()
        try:
            return self.address().get_value()
        except UserError:
            raise
        except Exception as exc:
            raise UserError("I could not read the browser address. Please restart the browser and try again.") from exc

    def address_focused(self):
        self.guard()
        return bool(self.address().has_keyboard_focus())

    def focus_address(self, stop):
        self.guard()
        if stop.is_set():
            raise Cancelled()
        import pyautogui
        pyautogui.hotkey("ctrl", "l")
        if stop.wait(.2):
            raise Cancelled()
        if not self.address_focused():
            self.guard()
            if stop.is_set():
                raise Cancelled()
            self.address().set_focus()
            if stop.wait(.2):
                raise Cancelled()
        if not self.address_focused():
            raise UserError("I could not focus the address bar. No text was entered.")

    def set_address(self, text, stop):
        self.guard()
        control = self.address()
        if not control.has_keyboard_focus():
            raise UserError("The address bar lost focus. No text was entered.")
        if stop.is_set():
            raise Cancelled()
        # UIA ValuePattern changes only this verified chrome control, even if
        # another application takes focus during the call. No clipboard mutation.
        control.iface_value.SetValue(text)
        if self.address_value() != text:
            raise UserError("The search address was not entered correctly. I stopped before submitting it.")

    def submit(self, expected, stop):
        self.guard()
        if not self.address_focused() or self.address_value() != expected:
            raise UserError("The address changed unexpectedly. I stopped before submitting it.")
        if stop.is_set():
            raise Cancelled()
        import pyautogui
        self.guard()
        pyautogui.press("enter")
