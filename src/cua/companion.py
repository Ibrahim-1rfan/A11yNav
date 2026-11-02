"""Klicky companion: a small teal pointer that trails the mouse over Chrome, Edge and Firefox.

A desktop app gets no mouse events for other applications, so the companion reads the pointer each frame at the
monitor's refresh rate while it is moving, and drops to a light 20 Hz check once it has settled. It never hooks
system input: clicks and typing are seen by polling key state, so no click anywhere can ever be delayed by Klicky.
The window is click-through, never takes focus and is hidden from Alt+Tab.
"""
import ctypes
from ctypes import wintypes
import os
import time
from PySide6.QtCore import QByteArray, QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget
from .companion_asset import SIZE, SVG, TIP
from .orb import reduced_motion

OFFSET = (16, 14)                 # companion top-left sits down-right of the pointer, never over its target
SPEEDS = {"gentle": .12, "normal": .18, "snappy": .28}
IDLE_DIM_S, IDLE_OPACITY = 4.0, .35
TYPING_HIDE_S = 1.5
FADE_IN_S, FADE_OUT_S = .2, .25
SQUISH_S, SQUISH_TO = .14, .75
MORPH_S = .2
SETTLED_MS = 50                   # light polling once settled
AWAY_MS = 250                     # no browser in front
PAD = 3                           # transparent margin around the 22 px pointer
MODIFIERS = {0x10, 0x11, 0x12, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x14, 0x90, 0x91}


def follow_step(position, target, speed, dt):
    """Frame-rate independent ease: 'speed' of the remaining distance per 60 fps frame."""
    k = 1 - (1 - speed) ** (dt * 60)
    return position + (target - position) * k


def companion_opacity(enabled, suppressed, typing, in_browser, fullscreen, idle_seconds):
    if not enabled or suppressed or typing or not in_browser or fullscreen:
        return 0.0
    return IDLE_OPACITY if idle_seconds >= IDLE_DIM_S else 1.0


def ease_out(u):
    return 1 - (1 - u) ** 2


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


class Desktop:
    """Cheap Win32 reads: pointer, buttons, keys, last input time, and the browser in front."""
    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.MonitorFromWindow.restype = wintypes.HANDLE
        self.names = {}
        self.browser = None

    def cursor(self):
        point = wintypes.POINT()
        self.user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    def buttons(self):
        return any(self.user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x01, 0x02, 0x04))

    def key_down(self):
        return any(self.user32.GetAsyncKeyState(vk) & 0x8000 for vk in range(0x08, 0xE0) if vk not in MODIFIERS)

    def last_input(self):
        info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
        self.user32.GetLastInputInfo(ctypes.byref(info))
        return info.dwTime

    def browser_window(self):
        """(window rect, fullscreen) when Chrome, Edge or Firefox is in front, else None. Physical pixels."""
        from .browser import EXECUTABLES, WindowsBrowser
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            return None
        key = int(hwnd)
        if key not in self.names:
            self.browser = self.browser or WindowsBrowser()
            self.names = {k: v for k, v in list(self.names.items())[-50:]}
            self.names[key] = self.browser.process_name(hwnd)
        if self.names[key] not in EXECUTABLES.values():
            return None
        rect = wintypes.RECT()
        self.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        info = MONITORINFO(ctypes.sizeof(MONITORINFO))
        self.user32.GetMonitorInfoW(self.user32.MonitorFromWindow(hwnd, 2), ctypes.byref(info))
        m = info.rcMonitor
        # Fullscreen video or F11: the window covers its whole monitor (a maximized window stops at the taskbar).
        fullscreen = rect.left <= m.left and rect.top <= m.top and rect.right >= m.right and rect.bottom >= m.bottom
        return (rect.left, rect.top, rect.right, rect.bottom), fullscreen


class Companion(QWidget):
    def __init__(self, settings, desktop=None):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus
                         | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("")
        self.setAccessibleName("")  # decorative: the orb is Klicky's accessible control
        self.setFixedSize(SIZE + 2 * PAD, SIZE + 2 * PAD)
        self.settings = settings
        self.desktop = desktop or (Desktop() if os.name == "nt" else None)
        self.renderer = QSvgRenderer(QByteArray(SVG.encode()))
        self.reduced = reduced_motion()
        self.x = self.y = 0.0
        self.opacity, self.scale = 0.0, 1.0
        self.suppressed = False
        self.morph_started = None
        self.squish_started = None
        self.clock = 0.0  # animation time, advanced by each frame's dt
        now = time.monotonic()
        self.last_tick = self.last_move = now
        self.typing_until = 0.0
        self.prev_cursor, self.prev_buttons, self.prev_input = None, False, 0
        self.context, self.context_at = None, 0.0
        self.timer = QTimer(self)
        # Coarse timer: a precise one forces 1 ms system timer resolution (CPU and battery); dt-based easing absorbs jitter.
        self.timer.setTimerType(Qt.TimerType.CoarseTimer)
        self.timer.timeout.connect(self.tick)

    # ---- public --------------------------------------------------------------------------------------------
    def start(self):
        if self.desktop:
            self.timer.start(SETTLED_MS)

    def stop(self):
        self.timer.stop()
        self.hide()

    def position(self):
        """Top-left of the visible pointer, for the orb to pop in at."""
        return QPoint(round(self.x), round(self.y))

    def is_showing(self):
        return self.isVisible() and self.opacity > 0.05

    def morph_out(self):
        """Hotkey: shrink to nothing and fade over 200 ms; stays hidden while the orb is open."""
        self.suppressed = True
        if self.reduced or not self.is_showing():
            self.opacity, self.scale = 0.0, 1.0
            self.hide()
            return
        self.morph_started = self.clock
        self.timer.setInterval(self.frame_ms())

    def reappear(self):
        """Orb closed: come back at the current pointer (snap, then fade in), never flying back from the orb."""
        self.suppressed = False
        self.morph_started = None
        self.opacity, self.scale = 0.0, 1.0
        self.timer.setInterval(self.frame_ms())

    # ---- loop ----------------------------------------------------------------------------------------------
    def frame_ms(self):
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        rate = screen.refreshRate() if screen and screen.refreshRate() > 1 else 60
        return max(4, int(1000 / rate))

    def browser_context(self, now):
        if now - self.context_at > .2 or self.timer.interval() >= AWAY_MS:
            try:
                self.context = self.desktop.browser_window()
            except Exception:
                self.context = None
            self.context_at = now
        return self.context

    def tick(self):
        now = time.monotonic()
        dt = min(.1, max(.001, now - self.last_tick))
        self.last_tick = now
        self.clock += dt
        s = self.settings()
        pos = QCursor.pos()
        cursor = (pos.x(), pos.y())
        moved = cursor != self.prev_cursor
        buttons = self.desktop.buttons()
        if moved:
            self.last_move = now
        last_input = self.desktop.last_input()
        if last_input != self.prev_input and not moved and buttons == self.prev_buttons and self.desktop.key_down():
            self.typing_until = now + TYPING_HIDE_S  # a keystroke, not the mouse
        context = self.browser_context(now)
        physical = self.desktop.cursor()
        in_browser = bool(context) and context[0][0] <= physical[0] < context[0][2] and context[0][1] <= physical[1] < context[0][3]
        target = companion_opacity(s.companion, self.suppressed, now < self.typing_until, in_browser,
                                   bool(context) and context[1], now - self.last_move)
        if buttons and not self.prev_buttons and target > 0:
            self.clicked(pos, s)
        self.prev_cursor, self.prev_buttons, self.prev_input = cursor, buttons, last_input

        tx, ty = pos.x() + OFFSET[0], pos.y() + OFFSET[1]
        if self.morph_started is not None:
            u = min(1.0, (self.clock - self.morph_started) / MORPH_S)
            self.scale, self.opacity = 1 - u, 1 - u
            if u >= 1:
                self.morph_started, self.scale = None, 1.0
            target = self.opacity
        elif self.opacity <= 0 and target > 0:
            self.x, self.y = tx, ty  # first appearance: snap, never fly in from elsewhere
        if self.morph_started is None:
            speed = 1.0 if self.reduced else SPEEDS.get(s.companion_speed, SPEEDS["normal"])
            self.x, self.y = follow_step(self.x, tx, speed, dt), follow_step(self.y, ty, speed, dt)
            rate = dt / (FADE_IN_S if target > self.opacity else FADE_OUT_S)
            self.opacity = min(target, self.opacity + rate) if target > self.opacity else max(target, self.opacity - rate)
            self.scale = self.squish_scale(self.clock)
        self.apply()
        settled = (abs(tx - self.x) < .1 and abs(ty - self.y) < .1 and not moved and self.opacity == target
                   and self.morph_started is None and self.squish_started is None)
        if not context and self.opacity == 0 and self.morph_started is None:
            interval = AWAY_MS  # no browser in front: just watch for one to come forward
        else:
            interval = SETTLED_MS if settled or self.opacity == 0 and target == 0 else self.frame_ms()
        if self.timer.interval() != interval:
            self.timer.setInterval(interval)

    def squish_scale(self, now):
        if self.squish_started is None:
            return 1.0
        t = now - self.squish_started
        if t < SQUISH_S:
            return 1 - (1 - SQUISH_TO) * ease_out(t / SQUISH_S)
        if t < 2 * SQUISH_S:
            return SQUISH_TO + (1 - SQUISH_TO) * ease_out((t - SQUISH_S) / SQUISH_S)
        self.squish_started = None
        return 1.0

    def clicked(self, pos, s):
        if self.reduced:
            return
        self.squish_started = self.clock
        if s.click_ripple:
            from .ripple import Ripple
            Ripple(pos)
        self.timer.setInterval(self.frame_ms())

    def apply(self):
        if self.opacity <= 0:
            if self.isVisible():
                self.hide()
            return
        self.move(round(self.x) - PAD, round(self.y) - PAD)
        self.setWindowOpacity(self.opacity)
        if not self.isVisible():
            self.show()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Squish and morph shrink toward the pointer's tip, like transform-origin at the tip.
        tip = QPointF(PAD + TIP[0], PAD + TIP[1])
        painter.translate(tip)
        painter.scale(self.scale, self.scale)
        painter.translate(-tip)
        self.renderer.render(painter, QRectF(PAD, PAD, SIZE, SIZE))
