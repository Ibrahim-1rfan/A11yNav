"""Study recorder: logs the mouse during each LMS task, so effort can be measured from behaviour (no forms).

The member running the session presses Ctrl+S when a task starts and Ctrl+E when it ends (F8 also works, as a
toggle), then clicks whether the student did it. While the recorder is open it owns Ctrl+S and Ctrl+E, so the
browser never sees them (no "Save page" dialog, no jump to the address bar). Between start and end the recorder
notes, 50 times a second, where the pointer is, every click, and which page is open (the window title). It never
records keys, screen pixels or sound.

Each student gets one file pair in study/recordings/: <code>.csv (every event) and <code>.json (one line per task:
which round, with or without Klicky, done or not, and when Klicky was busy listening, thinking or speaking, read
from Klicky's own log on this PC). Usage: python study/recorder.py (or study/run_recorder.bat).
"""
from dataclasses import dataclass, field
from datetime import datetime
import csv
import os
import json
from pathlib import Path
import re
import time

HERE = Path(__file__).resolve().parent
RECORDINGS = HERE / "recordings"
SAMPLE_MS = 20          # 50 samples a second
VK_F8, VK_LBUTTON, VK_RBUTTON = 0x77, 0x01, 0x02
MOD_CONTROL, MOD_NOREPEAT, WM_HOTKEY = 0x0002, 0x4000, 0x0312
SHORTCUTS = {0x5301: ("start", 0x53), 0x4501: ("end", 0x45)}  # hotkey id: (what it does, key): Ctrl+S, Ctrl+E
# The four tasks, the same for every student and always in this order (owner's choice, 8 Nov 2026).
STEPS = (
    ("without", "outline", "Open the Course Outline of Computer Security."),
    ("without", "assignment", "In Human Computer Interaction, find which assignment is due next, and its due date."),
    ("with", "outline", "Open the Course Outline of Computer Security."),
    ("with", "assignment", "In Human Computer Interaction, find which assignment is due next, and its due date."),
)
FIELDS = ("code", "step", "round", "klicky", "task", "t", "type", "x", "y", "button", "title")
CODE = re.compile(r"^P\d{1,3}$")
# Klicky is busy (the student asks, waits or listens) in these dock states; "waiting" is the student's own turn.
BUSY = {"idle", "listening", "typing", "thinking", "speaking", "acting"}
STATE_LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}) dock (\w+) -> (\w+)$")


def klicky_log():
    folder = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Klicky"
    return [folder / "klicky.log.1", folder / "klicky.log"]   # the older rotated file first


def busy_spans(lines, start, end):
    """When Klicky was busy between two wall-clock times: [[from, to], ...] in seconds after start."""
    state, since, spans = "closed", None, []
    for line in lines:
        match = STATE_LINE.match(line.strip())
        if not match:
            continue
        when = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S,%f").timestamp()
        if when > end:
            break
        if state in BUSY and since is not None:
            spans.append((since, when))
        state, since = match.group(3), when
    if state in BUSY and since is not None:
        spans.append((since, end))
    return [[round(max(a, start) - start, 2), round(min(b, end) - start, 2)] for a, b in spans if b > start and a < end]


def read_log_lines(paths=None):
    lines = []
    for path in paths or klicky_log():
        try:
            lines += path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            pass
    return lines


def plan(code):
    """The four steps, identical for every student: both tasks without Klicky, then both again with Klicky."""
    return [{"step": i + 1, "round": 1 if klicky == "without" else 2, "klicky": klicky, "task": task, "text": text}
            for i, (klicky, task, text) in enumerate(STEPS)]


@dataclass
class Session:
    """What happened in one student's session. Pure logic: the Windows polling feeds it samples."""
    code: str
    folder: Path = RECORDINGS
    steps: list = field(default_factory=list)
    index: int = 0          # the step the next F8 starts
    active: dict | None = None
    waiting: dict | None = None   # ended, waiting for "did they do it?"
    rows: list = field(default_factory=list)
    results: list = field(default_factory=list)
    last: tuple | None = None
    buttons: tuple = (False, False)
    title: str = ""

    def __post_init__(self):
        if not CODE.match(self.code):
            raise ValueError("Use a student code like P01.")
        self.steps = self.steps or plan(self.code)

    @property
    def done(self):
        return self.index >= len(self.steps) and not self.active and not self.waiting

    @property
    def current(self):
        return self.active or self.waiting or (self.steps[self.index] if self.index < len(self.steps) else None)

    def row(self, now, kind, x, y, button="", title=""):
        step = self.active
        self.rows.append({"code": self.code, "step": step["step"], "round": step["round"], "klicky": step["klicky"],
                          "task": step["task"], "t": round(now - step["started"], 3), "type": kind, "x": x, "y": y,
                          "button": button, "title": title})

    def start(self, now, x, y, title, wall=None):
        """Ctrl+S: start the next task. Ignored while one is running or waiting for done / not done."""
        if self.active or self.waiting or self.done:
            return None
        self.active = {**self.steps[self.index], "started": now, "wall": time.time() if wall is None else wall}
        self.last, self.title = (x, y), title
        self.row(now, "start", x, y, title=title)
        return "started"

    def end(self, now, x, y, title):
        """Ctrl+E: end the running task. Ignored when none is running."""
        if not self.active:
            return None
        self.row(now, "end", x, y, title=title)
        seconds = round(now - self.active["started"], 2)
        wall = self.active["wall"]
        self.waiting = {**self.active, "seconds": seconds,
                        "klicky_busy": busy_spans(self.log_lines(), wall, wall + seconds)}
        self.active = None
        return "ended"

    def log_lines(self):
        return read_log_lines()

    def f8(self, now, x, y, title):
        """F8, the backup key: start the next task, or end the running one."""
        return self.end(now, x, y, title) if self.active else self.start(now, x, y, title)

    def sample(self, now, x, y, left, right, title):
        """One reading of the pointer, the buttons and the window title."""
        if self.active is not None:
            if (x, y) != self.last:
                self.row(now, "move", x, y)
            for name, down, was in (("left", left, self.buttons[0]), ("right", right, self.buttons[1])):
                if down and not was:
                    self.row(now, "click", x, y, button=name, title=title)
            if title != self.title:
                self.row(now, "page", x, y, title=title)
        self.last, self.buttons, self.title = (x, y), (left, right), title

    def mark(self, success):
        """The member says whether the student did the task; the step is saved and the next one comes up."""
        if not self.waiting:
            return
        step = self.waiting
        self.results.append({k: step[k] for k in ("step", "round", "klicky", "task", "text", "seconds", "klicky_busy")}
                            | {"started_at": datetime.fromtimestamp(step["wall"]).isoformat(timespec="milliseconds"),
                               "success": bool(success)})
        self.waiting = None
        self.index += 1
        self.save()

    def save(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        with (self.folder / f"{self.code}.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(self.rows)
        (self.folder / f"{self.code}.json").write_text(json.dumps(
            {"code": self.code, "saved": time.strftime("%Y-%m-%d %H:%M:%S"), "tasks": self.results}, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- Windows polling and the small window

def read_windows():
    """Pointer position, button states, F8 state and the foreground window's title."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    down = lambda key: bool(user32.GetAsyncKeyState(key) & 0x8000)
    hwnd = user32.GetForegroundWindow()
    buffer = ctypes.create_unicode_buffer(300)
    user32.GetWindowTextW(hwnd, buffer, 300)
    return point.x, point.y, down(VK_LBUTTON), down(VK_RBUTTON), down(VK_F8), buffer.value


def claim_shortcuts(app, on_key):
    """Own Ctrl+S and Ctrl+E system-wide while the recorder is open. Returns False if another app has them."""
    import ctypes
    from ctypes import wintypes
    from PySide6.QtCore import QAbstractNativeEventFilter

    class Filter(QAbstractNativeEventFilter):
        def nativeEventFilter(self, event_type, message):
            if event_type in (b"windows_generic_MSG", "windows_generic_MSG"):
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam in SHORTCUTS:
                    on_key(SHORTCUTS[msg.wParam][0])
                    return True, 0
            return False, 0

    app._shortcut_filter = Filter()  # kept alive with the app
    app.installNativeEventFilter(app._shortcut_filter)
    ok = [bool(ctypes.windll.user32.RegisterHotKey(None, hotkey, MOD_CONTROL | MOD_NOREPEAT, key))
          for hotkey, (_name, key) in SHORTCUTS.items()]
    app.aboutToQuit.connect(lambda: [ctypes.windll.user32.UnregisterHotKey(None, hotkey) for hotkey in SHORTCUTS])
    return all(ok)


def main():
    import sys
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
                                   QVBoxLayout, QWidget)
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Klicky study recorder")
    window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    layout = QVBoxLayout(window)
    code_row = QHBoxLayout()
    code = QLineEdit(placeholderText="Student code, e.g. P01")
    begin = QPushButton("Start this student")
    code_row.addWidget(code)
    code_row.addWidget(begin)
    layout.addLayout(code_row)
    status = QLabel("Type the student's code and press Start this student.")
    status.setWordWrap(True)
    status.setMinimumWidth(420)
    status.setStyleSheet("font-size: 15px;")
    layout.addWidget(status)
    answer_row = QHBoxLayout()
    yes, no = QPushButton("Yes, they did it"), QPushButton("No / gave up")
    answer_row.addWidget(yes)
    answer_row.addWidget(no)
    layout.addLayout(answer_row)
    state = {"session": None, "f8": False}

    def show():
        s = state["session"]
        yes.setEnabled(bool(s and s.waiting))
        no.setEnabled(bool(s and s.waiting))
        if s is None:
            return
        if s.done:
            status.setText(f"{s.code} is finished. Files saved in study\\recordings\\. Stop the screen recording, then "
                           "type the next student's code.")
            code.setEnabled(True); begin.setEnabled(True)
            return
        step = s.current
        klicky = "WITH Klicky" if step["klicky"] == "with" else "WITHOUT Klicky (keep Klicky closed)"
        head = f"<b>{s.code}: task {step['step']} of {len(s.steps)}, {klicky}</b><br>Read aloud: <i>{step['text']}</i><br><br>"
        if s.active:
            status.setText(head + "<span style='color:#b42318'><b>Recording.</b></span> Press <b>Ctrl+E</b> when the student finishes or gives up.")
        elif s.waiting:
            status.setText(head + f"Ended after {s.waiting['seconds']:.0f} s. <b>Did the student do it?</b>")
        else:
            status.setText(head + "Press <b>Ctrl+S</b> when the student starts.")

    def start_student():
        text = code.text().strip().upper()
        if not CODE.match(text):
            QMessageBox.warning(window, "Student code", "Use a code like P01, P02...")
            return
        if (RECORDINGS / f"{text}.csv").exists() and QMessageBox.question(
                window, "Student code", f"{text} already has a recording. Replace it?") != QMessageBox.StandardButton.Yes:
            return
        state["session"] = Session(text)
        code.setEnabled(False); begin.setEnabled(False)
        show()

    def answer(success):
        state["session"].mark(success)
        show()

    def tick():
        s = state["session"]
        x, y, left, right, f8, title = read_windows()
        if s is None:
            return
        now = time.perf_counter()
        if f8 and not state["f8"]:
            s.f8(now, x, y, title)
            show()
        state["f8"] = f8
        s.sample(now, x, y, left, right, title)

    def shortcut(which):
        s = state["session"]
        if s is None:
            return
        x, y, _left, _right, _f8, title = read_windows()
        (s.start if which == "start" else s.end)(time.perf_counter(), x, y, title)
        show()

    if not claim_shortcuts(app, shortcut):
        QMessageBox.warning(window, "Shortcuts", "Another app is using Ctrl+S or Ctrl+E. Use F8 instead: "
                            "press it once to start a task and again to end it.")
    begin.clicked.connect(start_student)
    code.returnPressed.connect(start_student)
    yes.clicked.connect(lambda: answer(True))
    no.clicked.connect(lambda: answer(False))
    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(SAMPLE_MS)
    show()
    window.show()
    screen = app.primaryScreen().availableGeometry()
    window.move(screen.left() + 16, screen.bottom() - window.height() - 16)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
