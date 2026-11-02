"""Voice-first dock: a small orb docked bottom-centre, live captions, and an answer card that is read aloud.

Laid out as [answer card] -> [caption] -> [orb] in a frameless window with no backdrop, so the browser stays
visible and usable. Every behaviour goes through the DockState machine in dockstate.py.
"""
import ctypes
import os
from dataclasses import replace
from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QFont, QFontMetrics, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget
from .answer_card import AnswerCard
from .config import UserError
from .dockstate import (CAPTIONS, CLOSED, DONE, ERROR, IDLE, LISTENING, ORB_LABELS, SPEAKING, THINKING, TYPING,
                        DockState)
from .highlighter import Highlighter
from .orb import Orb
from .popup import AnswerWorker
from .rag import detect_app
from .tts import ReadAloud, intro, spoken

LIGHT = {"surface": "#FFFFFF", "border": "#D5DDDA", "text": "#14231E", "muted": "#46564F", "accent_text": "#0F6E56",
         "active_bg": "#E1F5EE", "active_text": "#085041", "kbd_bg": "#EEF2F1", "kbd_text": "#14231E",
         "focus": "#085041", "button_bg": "#F4F7F6"}
DARK = {"surface": "#1B2321", "border": "#3A4744", "text": "#F1F5F4", "muted": "#B9C7C2", "accent_text": "#5DCAA5",
        "active_bg": "#E1F5EE", "active_text": "#085041", "kbd_bg": "#2C3835", "kbd_text": "#F1F5F4",
        "focus": "#9FE1CB", "button_bg": "#253230"}


def palette(profile_key):
    """System light or dark; the low-vision profile always uses the dark, high-contrast set."""
    dark = profile_key == "low_vision"
    try:
        dark = dark or QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        pass
    return DARK if dark else LIGHT


def screen_reader_running():
    if os.name != "nt":
        return False
    running = ctypes.c_bool(False)
    try:
        ctypes.windll.user32.SystemParametersInfoW(0x0046, 0, ctypes.byref(running), 0)  # SPI_GETSCREENREADER
    except (AttributeError, OSError):
        return False
    return running.value


def announce(widget, text):
    """Polite live-region announcement for screen readers (Qt 6.8+); harmless when unsupported."""
    if not text:
        return
    try:
        from PySide6.QtGui import QAccessible, QAccessibleAnnouncementEvent
        QAccessible.updateAccessibility(QAccessibleAnnouncementEvent(widget, text))
    except Exception:
        pass


def last_two_lines(text, font, width):
    """Keep the newest words that fit in two lines, dropping older words from the left."""
    metrics, words = QFontMetrics(font), text.split()
    for start in range(len(words)):
        candidate = ("… " if start else "") + " ".join(words[start:])
        rect = metrics.boundingRect(QRect(0, 0, width, 10000), int(Qt.TextFlag.TextWordWrap), candidate)
        if rect.height() <= metrics.lineSpacing() * 2 + 2:
            return candidate
    return words[-1] if words else ""


class Dock(QWidget):
    def __init__(self, owner):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Klicky")
        self.setObjectName("dock")
        self.owner = owner
        self.machine = DockState(self.on_state)
        self.context_app = self.return_hwnd = None
        self.listener = self.monitor = self.worker = None
        self.answer, self.slower, self.colors, self.answered = None, False, LIGHT, False
        self.voice_factory = self.monitor_factory = self.answer_factory = None  # tests inject fakes here
        self.tts = ReadAloud()
        self.highlighter = Highlighter()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(10)
        self.card = AnswerCard()
        self.card.hide()
        self.card.replay.connect(self.replay)
        self.card.slower.connect(self.set_slower)
        self.card.more.connect(lambda _: QTimer.singleShot(0, self.reposition))
        self.caption = QLabel()
        self.caption.setObjectName("caption")
        self.caption.setWordWrap(True)
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption.setAccessibleName("Klicky says")
        self.input = QLineEdit()
        self.input.setObjectName("typed")
        self.input.setAccessibleName("Type your question")
        self.input.setPlaceholderText("Type your question and press Enter")
        self.input.returnPressed.connect(self.submit_typed)
        self.input.hide()
        self.orb = Orb()
        self.orb.clicked.connect(self.orb_clicked)
        layout.addWidget(self.card)
        layout.addWidget(self.caption)
        layout.addWidget(self.input)
        layout.addWidget(self.orb, 0, Qt.AlignmentFlag.AlignHCenter)
        QShortcut(QKeySequence("Escape"), self, activated=self.escape)

    @property
    def state(self):
        return self.machine.state

    @property
    def settings(self):
        return self.owner.settings

    # ---- state changes -------------------------------------------------------------------------------------
    def on_state(self, old, new, event):
        if new == CLOSED:
            self.finish_close()
            return
        self.orb.set_mode(new, ORB_LABELS[new])
        self.input.setVisible(new == TYPING)
        self.set_caption(CAPTIONS.get(new, ""))
        if new == LISTENING:
            self.card.hide()
            self.highlighter.clear()
        if new in (SPEAKING, DONE) and old != new:
            announce(self, "Reading the answer" if new == SPEAKING else "Answer ready")
        QTimer.singleShot(0, self.reposition)

    def set_caption(self, text):
        text = last_two_lines(text, self.caption.font(), self.caption_width()) if text else ""
        self.caption.setText(text)
        self.caption.setVisible(bool(text))
        if text:
            announce(self, text)

    # ---- opening, layout, styling ---------------------------------------------------------------------------
    def open_for(self, app, hwnd, listen=True):
        if self.state == CLOSED:
            self.context_app, self.return_hwnd = app, hwnd
            self.highlighter.cache.clear()
            self.answer = None
            self.card.hide()
            self.restyle()
            self.machine.fire("open")
            self.show()
            self.orb.start()
        elif hwnd:
            self.context_app, self.return_hwnd = app, hwnd
        self.raise_()
        self.activateWindow()
        self.orb.setFocus()
        self.reposition()
        if listen:
            self.listen_now()

    def restyle(self):
        p = self.owner.profile
        px = max(16, self.settings.font_px)
        cap = max(18, px + 2)
        self.colors = c = palette(p.key)
        self.orb.set_diameter(72 if p.key == "low_vision" else 56)
        self.orb.focus_color = c["focus"]
        self.card.reduced = self.orb.reduced
        font = QFont("Segoe UI")
        font.setPixelSize(cap)
        self.caption.setFont(font)
        self.setFixedWidth(self.dock_width() + 16)
        self.setStyleSheet(
            f'* {{ background:transparent; color:{c["text"]}; font-family:"Segoe UI"; font-size:{px}px; }}'
            f' #card {{ background:{c["surface"]}; border:1px solid {c["border"]}; border-radius:12px; }}'
            f' #cardTitle {{ font-weight:500; font-size:{px + 2}px; }}'
            f' QLabel#step {{ padding:6px 8px; border-radius:8px; }}'
            f' QLabel#step[active="true"] {{ background:{c["active_bg"]}; color:{c["active_text"]}; }}'
            f' #note {{ color:{c["muted"]}; font-size:{max(16, px - 2)}px; }}'
            f' QLabel#caption {{ background:{c["surface"]}; border:1px solid {c["border"]}; border-radius:10px; padding:6px 14px; font-size:{cap}px; }}'
            f' QLineEdit#typed {{ background:{c["surface"]}; border:2px solid {c["border"]}; border-radius:10px; padding:8px 12px; font-size:{cap}px; }}'
            f' QLineEdit#typed:focus {{ border:3px solid {c["focus"]}; }}'
            f' QPushButton#cardButton {{ background:{c["button_bg"]}; border:1px solid {c["border"]}; border-radius:8px; padding:6px 14px; min-height:28px; }}'
            f' QPushButton#cardButton:focus {{ border:3px solid {c["focus"]}; }}'
            f' QPushButton#cardButton:checked {{ background:{c["active_bg"]}; color:{c["active_text"]}; }}')
        if self.answer:
            self.card.colors = c
            self.card.render()

    def dock_width(self):
        return max(420, self.settings.font_px * 22)

    def caption_width(self):
        return self.dock_width() - 30

    def reposition(self):
        if not self.isVisible():
            return
        # Wrapped captions and steps need height-for-width; adjustSize alone under-measures them and clips the orb.
        layout = self.layout()
        layout.activate()
        height = layout.totalHeightForWidth(self.width()) if layout.hasHeightForWidth() else layout.totalSizeHint().height()
        self.setFixedHeight(max(height, layout.totalMinimumSize().height()))
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(area.x() + (area.width() - self.width()) // 2, area.bottom() - 24 - self.height())

    # ---- listening -----------------------------------------------------------------------------------------
    def voice_ready(self):
        if not self.settings.voice:
            return False
        if self.voice_factory:
            return True
        from .voice import model_installed
        return model_installed(self.settings.voice_model)

    def listen_now(self):
        """Hotkey while open: listen, or barge in over an answer being read."""
        if self.state == SPEAKING:
            self.barge_in()
        elif self.state in (IDLE, DONE, ERROR, TYPING):
            self.start_listening()

    def start_listening(self):
        if not self.voice_ready():
            self.start_typing("")
            if self.settings.voice:
                self.set_caption("Type your question. For voice, run scripts\\get_speech_model.bat once.")
            return
        self.quiet()
        if self.machine.fire("start"):
            self.listen()

    def listen(self, cue=True):
        from .voice import VoiceWorker
        self.listener = self.voice_factory() if self.voice_factory else VoiceWorker(self.settings.voice_model, cue=cue)
        self.listener.level.connect(self.orb.set_level)
        self.listener.partial.connect(self.show_partial)
        self.listener.stage.connect(self.on_stage)
        self.listener.heard.connect(self.on_heard)
        self.listener.failed.connect(self.on_fail)
        self.listener.start()

    def stop_listener(self):
        if self.listener and self.listener.isRunning():
            self.listener.stop_event.set()

    def show_partial(self, text):
        if self.state == LISTENING:
            self.set_caption(text)

    def on_stage(self, stage):
        if stage == "transcribing":
            self.machine.fire("heard")  # end of speech: no Ask button
        elif stage == "stopped" and self.state == LISTENING:
            self.machine.fire("stop_listening")

    def on_heard(self, text):
        if self.state != THINKING:
            return
        self.set_caption(f"“{text}”  Finding the answer...")
        self.route(text, spoken_question=True)

    # ---- typing fallback -----------------------------------------------------------------------------------
    def keyPressEvent(self, event):
        text = event.text()
        if (text and text.isprintable() and not text.isspace() and not event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
                and self.state in (LISTENING, IDLE, DONE, ERROR)):
            self.start_typing(text)
            return
        super().keyPressEvent(event)

    def start_typing(self, text):
        self.stop_listener()
        self.quiet()
        if self.state != TYPING:
            self.machine.fire("type")
        self.input.setText(text)
        self.input.show()
        self.input.setFocus()
        self.input.end(False)
        QTimer.singleShot(0, self.reposition)

    def submit_typed(self):
        text = self.input.text().strip()
        if not text or self.state != TYPING:
            return
        try:
            from .planning import route
            route(text, self.settings.engine)
        except UserError as exc:
            self.set_caption(str(exc))
            return
        self.machine.fire("submit")
        self.route(text, spoken_question=False)

    # ---- answering -----------------------------------------------------------------------------------------
    def route(self, text, spoken_question):
        from .planning import parse_task
        try:
            parse_task(text, self.settings.engine)
            is_search = True
        except UserError:
            is_search = False
        if is_search:
            self.machine.fire("cancel")  # closes the dock and returns focus to the browser
            self.owner.run_search(text)
            return
        self.ask(" ".join(text.split())[:500])

    def ask(self, question):
        settings = self.settings
        # A browser named in the question wins; otherwise answer for the browser the hotkey was pressed in.
        if self.context_app and settings.rag_app == "auto" and detect_app(question) is None:
            settings = replace(settings, rag_app=self.context_app)
        self.answered = False
        self.worker = AnswerWorker(settings, question, self.answer_factory)
        self.worker.answered.connect(self.on_answer)
        self.worker.status.connect(lambda state, message: self.on_fail(message) if state == "error" and not self.answered else None)
        self.worker.start()

    def on_answer(self, answer):
        if self.state != THINKING:
            return
        self.answered = True
        self.answer = answer
        self.card.show_answer(answer, self.colors, self.slower)
        self.card.show()
        announce(self, answer.spoken() if answer.grounded else answer.note)
        read = self.settings.read_aloud and not (self.settings.screen_reader_quiet and screen_reader_running())
        if read and self.machine.fire("answer_read"):
            self.read_answer()
        else:
            self.machine.fire("answer_quiet")
            self.point_at_first_step()
        self.card.replay_button.setFocus() if self.card.replay_button.isVisible() else self.orb.setFocus()

    def lines(self):
        if not self.answer.grounded:
            return [self.answer.note]
        return [intro(self.answer)] + [spoken(step) for step in self.card.visible_steps]

    def read_answer(self):
        self.tts.voice_name = self.settings.tts_voice
        rate = self.settings.speech_rate * (.8 if self.slower else 1.0)
        self.tts.speak(self.lines(), rate, on_line_start=self.on_line, on_end=self.on_read_end)
        self.start_monitor()

    def on_line(self, index):
        step = index - 1  # line 0 is the spoken intro
        self.card.set_active(step)
        steps = self.card.visible_steps
        if 0 <= step < len(steps):
            self.highlighter.point(steps[step], self.return_hwnd)

    def on_read_end(self):
        self.stop_monitor()
        self.card.set_active(-1)
        self.machine.fire("finished")

    def point_at_first_step(self):
        for step in self.card.visible_steps:
            from .highlighter import target_for
            if target_for(step):
                self.highlighter.point(step, self.return_hwnd)
                return

    def stop_reading(self):
        self.quiet()
        self.machine.fire("stop")

    def replay(self):
        if self.state not in (SPEAKING, DONE) or not self.answer:
            return
        self.quiet()
        if self.state == DONE:
            self.machine.fire("replay")
        self.read_answer()

    def set_slower(self, on):
        self.slower = on
        if self.state == SPEAKING:
            self.replay()

    # ---- barge-in ------------------------------------------------------------------------------------------
    def start_monitor(self):
        if not (self.settings.barge_in and self.voice_ready()):
            return
        from .voice import BargeInMonitor
        self.monitor = self.monitor_factory() if self.monitor_factory else BargeInMonitor()
        self.monitor.barged.connect(self.barge_in)
        self.monitor.start()

    def stop_monitor(self):
        if self.monitor and self.monitor.isRunning():
            self.monitor.stop_event.set()

    def barge_in(self):
        if self.state != SPEAKING:
            return
        self.quiet()
        if self.machine.fire("barge_in"):
            self.listen(cue=False)  # the person is already talking; no beep over their words

    def quiet(self):
        """Stop reading, stop listening for barge-in, and clear highlights."""
        self.tts.stop()
        self.stop_monitor()
        self.card.set_active(-1)
        self.highlighter.clear()

    # ---- orb, Escape, problems, closing ---------------------------------------------------------------------
    def orb_clicked(self):
        if self.state in (IDLE, DONE, ERROR, TYPING):
            self.start_listening()
        elif self.state == LISTENING:
            self.stop_listener()
        elif self.state == SPEAKING:
            self.stop_reading()

    def escape(self):
        if self.state in (LISTENING, THINKING):
            self.stop_listener()
            if self.worker and self.worker.isRunning():
                self.worker.stop_event.set()
            self.machine.fire("cancel")
        elif self.state == SPEAKING:
            self.stop_reading()
        else:
            self.machine.fire("close")

    def on_fail(self, message):
        self.stop_listener()
        self.quiet()
        from .voice import NO_MIC
        if message == NO_MIC:
            # Never a dead end: without a microphone, typing takes over.
            self.machine.fire("fail")
            self.start_typing("")
            self.set_caption("I can't use the microphone. Type your question instead.")
            return
        if self.machine.fire("fail") == ERROR:
            self.set_caption(message if "orb" in message or "type" in message.lower() else f"{message} Tap the orb to try again.")

    def close_dock(self):
        if self.state in (LISTENING, THINKING):
            self.machine.fire("cancel")
        elif self.state != CLOSED:
            self.machine.fire("close")

    def finish_close(self):
        self.stop_listener()
        if self.worker and self.worker.isRunning():
            self.worker.stop_event.set()
        self.quiet()
        self.orb.stop()  # stops the animation loop; the microphone closes when the listener thread ends
        self.card.hide()
        self.hide()
        hwnd, self.return_hwnd = self.return_hwnd, None
        if hwnd:
            try:
                ctypes.windll.user32.SetForegroundWindow(hwnd)  # focus goes back where it was
            except (AttributeError, OSError):
                pass
