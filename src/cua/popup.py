"""Spotlight-style question popup summoned by the global shortcut, plus the shared answer worker and renderer."""
import ctypes
from dataclasses import replace
import html
import threading
from urllib.parse import urlsplit
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QProgressBar, QPushButton, QTextBrowser, QVBoxLayout, QWidget)
from .config import UserError
from .models import Cancelled
from .rag import detect_app
from . import profiles

POPUP_SANS = ("Segoe UI Variable Text", "Segoe UI", "Arial")
SUGGESTIONS = ["Make text bigger", "Read this page aloud", "Turn on dark mode", "Open reader mode", "Turn on captions", "Find a word"]


class AnswerWorker(QThread):
    """Finds a guide and optionally rewrites it with the local text model. Never touches the desktop."""
    status = Signal(str, str)
    answered = Signal(object)

    def __init__(self, settings, question, factory=None):
        super().__init__()
        self.settings, self.question = settings, question
        self.stop_event = threading.Event()
        self.factory = factory

    def run(self):
        try:
            from .assistant import build_assistant
            helper = self.factory() if self.factory else build_assistant(self.settings)
            self.status.emit("processing", "Finding the guide and writing your answer" if self.settings.text_model else "Finding the guide")
            answer = helper.answer(self.question, self.stop_event)
            if self.stop_event.is_set():
                raise Cancelled()
            self.answered.emit(answer)
            self.status.emit("success" if answer.grounded else "error",
                             "Here is how to do it." if answer.grounded else "I don't have a guide for that yet.")
        except Cancelled:
            self.status.emit("inactive", "Question stopped")
        except UserError as exc:
            self.status.emit("error", str(exc))
        except Exception:
            self.status.emit("error", "I could not look up that guide. Please try again.")


def answer_html(answer, profile, step=0, show_title=True):
    """Answer as rich text. One step at a time for profiles that ask for it."""
    c, line = profile.colors, f"line-height:{profile.line_height}%;"
    parts = []
    if show_title:
        parts.append(f'<p style="font-size:large; font-weight:bold; margin-bottom:2px;">{html.escape(answer.title)}</p>')
    if answer.apps:
        parts.append(f'<p style="color:{c["muted"]}; margin-top:0;">For {html.escape(", ".join(a.title() for a in answer.apps))}</p>')
    one_step = profile.one_step and answer.grounded and len(answer.steps) > 1
    if one_step:
        parts.append(f'<p style="{line} color:{c["accent"]}; font-weight:bold;">Step {step + 1} of {len(answer.steps)}</p>'
                     f'<p style="{line}">{html.escape(answer.steps[step])}</p>')
    elif answer.steps:
        rows = "".join(f'<tr><td valign="top" style="color:{c["accent"]}; font-weight:bold; padding-right:10px;">{i}</td>'
                       f'<td style="{line} padding-bottom:8px;">{html.escape(s)}</td></tr>' for i, s in enumerate(answer.steps, 1))
        parts.append(f'<table cellspacing="0" cellpadding="2">{rows}</table>')
    if answer.note:
        parts.append(f'<p style="{line} color:{c["muted"]};"><i>{html.escape(answer.note)}</i></p>')
    links = " · ".join(f'<a style="color:{c["accent"]};" href="{html.escape(s)}">{html.escape(urlsplit(s).hostname or s)}</a>'
                       for s in answer.sources if s.startswith("https://"))
    if answer.grounded:
        origin = "Written by your local answer model from the guide" if answer.generated else "From Klicky's checked guide"
        parts.append(f'<p style="color:{c["muted"]};">{origin}{" · " + links if links else ""}</p>')
    return "".join(parts), one_step


class AskPopup(QWidget):
    """Floats above the browser: type a question, read the answer, Escape returns to the browser."""
    def __init__(self, owner):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.owner = owner
        self.setObjectName("popupRoot")
        self.setWindowTitle("Ask Klicky")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.context_app, self.return_hwnd = None, None
        self.worker, self.answer, self.step = None, None, 0
        self.max_answer = 600
        self.listener, self.asked_by_voice = None, False
        self.voice_factory = None  # tests inject a fake listener here
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 20, 28, 36)  # room for the shadow
        self.card = QFrame()
        self.card.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(22, 18, 22, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self.badge = QLabel("K")
        self.badge.setObjectName("badge")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel("Ask Klicky")
        self.title.setObjectName("title")
        self.chip = QLabel()
        self.chip.setObjectName("chip")
        self.hint = QLabel("Esc to close")
        self.hint.setObjectName("hint")
        header.addWidget(self.badge)
        header.addWidget(self.title)
        header.addWidget(self.chip)
        header.addStretch()
        header.addWidget(self.hint)
        layout.addLayout(header)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setObjectName("ask")
        self.input.setAccessibleName("Ask Klicky")
        self.input.returnPressed.connect(self.submit)
        self.input.textEdited.connect(lambda _: self.stop_listening())  # typing takes over from the microphone
        self.mic = QPushButton("Speak")
        self.mic.setObjectName("mic")
        self.mic.setAccessibleName("Speak your question")
        self.mic.clicked.connect(self.toggle_listening)
        self.go = QPushButton("Ask")
        self.go.setObjectName("go")
        self.go.setAccessibleName("Ask the question")
        self.go.clicked.connect(self.submit)
        row.addWidget(self.input, 1)
        row.addWidget(self.mic)
        row.addWidget(self.go)
        layout.addLayout(row)
        self.level = QProgressBar()
        self.level.setObjectName("level")
        self.level.setAccessibleName("Microphone level")
        self.level.setRange(0, 100)
        self.level.setTextVisible(False)
        self.level.setFixedHeight(6)
        self.level.hide()
        layout.addWidget(self.level)

        self.chips_box = QWidget()
        self.chips = QGridLayout(self.chips_box)
        self.chips.setContentsMargins(0, 0, 0, 0)
        self.chips.setSpacing(8)
        self.chip_buttons = []
        for text in SUGGESTIONS:
            button = QPushButton(text)
            button.setObjectName("suggestion")
            button.setAccessibleName(f"Ask: how do I {text.lower()}")
            button.clicked.connect(lambda _=False, t=text: self.ask_suggestion(t))
            self.chip_buttons.append(button)

        # Status sits right under the input, where the eyes already are; suggestions follow.
        self.status = QLabel()
        self.status.setObjectName("status")
        self.status.setAccessibleName("Klicky status")
        self.status.setWordWrap(True)
        self.status.hide()
        layout.addWidget(self.status)
        layout.addWidget(self.chips_box)

        self.view = QTextBrowser()
        self.view.setObjectName("answer")
        self.view.setAccessibleName("Answer")
        self.view.setOpenExternalLinks(True)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.hide()
        layout.addWidget(self.view)

        nav = QHBoxLayout()
        self.back, self.next = QPushButton("Back"), QPushButton("Next step")
        self.back.setAccessibleName("Previous step")
        self.back.clicked.connect(lambda: self.show_step(self.step - 1))
        self.next.clicked.connect(lambda: self.show_step(self.step + 1))
        nav.addWidget(self.back)
        nav.addWidget(self.next)
        self.nav = QWidget()
        self.nav.setLayout(nav)
        self.nav.hide()
        layout.addWidget(self.nav)

        QShortcut(QKeySequence("Escape"), self, activated=self.escape)

    @property
    def profile(self):
        return self.owner.profile

    def restyle(self):
        p, px = self.profile, self.owner.settings.font_px
        c = p.colors
        from .ui import selected_font
        # The popup reads as a modern overlay: profiles that use the monospace look get Segoe UI here.
        family = selected_font(replace(p, fonts=POPUP_SANS) if p.fonts == profiles.MONO else p)
        self.view.document().setDocumentMargin(14)
        self.setStyleSheet(
            f'* {{ background:transparent; color:{c["text"]}; font-family:"{family}"; font-size:{px}px; }}'
            f' #card {{ background:{c["background"]}; border:{max(1, p.focus_px - 2)}px solid {c["border"]}; border-radius:18px; }}'
            f' #badge {{ background:{c["accent"]}; color:{c["on_accent"]}; font-weight:bold; border-radius:{(px + 16) // 2}px;'
            f' min-width:{px + 16}px; max-width:{px + 16}px; min-height:{px + 16}px; max-height:{px + 16}px; }}'
            f' #title {{ font-weight:bold; font-size:{px + 2}px; }}'
            f' #chip {{ background:{c["surface"]}; color:{c["accent"]}; border:1px solid {c["accent"]}; border-radius:10px; padding:2px 10px; font-size:{max(14, px - 4)}px; }}'
            f' #hint, #status {{ color:{c["muted"]}; font-size:{max(14, px - 3)}px; }}'
            f' QLineEdit#ask {{ background:{c["surface"]}; border:2px solid {c["border"]}; border-radius:12px; padding:6px 14px;'
            f' font-size:{max(p.input_px, px + 4)}px; min-height:{int(max(p.input_px, px + 4) * 1.7)}px; }}'
            f' QLineEdit#ask:focus {{ border:{p.focus_px}px solid {c["focus"]}; }}'
            f' QPushButton {{ background:{c["surface"]}; border:1px solid {c["border"]}; border-radius:10px; padding:8px 14px; min-height:{max(28, p.button_px - 28)}px; }}'
            f' QPushButton:focus {{ border:{p.focus_px}px solid {c["focus"]}; }}'
            f' QPushButton:disabled {{ color:{c["muted"]}; background:{c["disabled"]}; }}'
            f' QPushButton#go {{ background:{c["accent"]}; color:{c["on_accent"]}; font-weight:bold; padding:12px 22px; }}'
            f' QPushButton#suggestion {{ font-size:{max(14, px - 3)}px; }}'
            f' QPushButton#mic[listening="true"] {{ background:{c["accent"]}; color:{c["on_accent"]}; font-weight:bold; }}'
            f' QProgressBar#level {{ background:{c["surface"]}; border:none; border-radius:3px; }}'
            f' QProgressBar#level::chunk {{ background:{c["accent"]}; border-radius:3px; }}'
            f' QTextBrowser#answer {{ background:{c["surface"]}; border-radius:12px; }}'
            f' QScrollBar:vertical {{ background:transparent; width:{max(10, p.focus_px * 2)}px; margin:6px 2px; }}'
            f' QScrollBar::handle:vertical {{ background:{c["border"]}; border-radius:{max(5, p.focus_px)}px; min-height:40px; }}'
            f' QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background:none; height:0; }}')
        columns = 3 if px <= 20 else 2
        for i, button in enumerate(self.chip_buttons):
            self.chips.addWidget(button, i // columns, i % columns)
        place = self.context_app.title() if self.context_app else "your browser"
        self.input.setPlaceholderText(f"How do I … in {place}?")
        self.chip.setText(self.context_app.title() if self.context_app else "")
        self.chip.setVisible(bool(self.context_app))
        if self.answer:
            self.render()

    def open_for(self, app, hwnd, listen=True):
        self.context_app, self.return_hwnd = app, hwnd
        self.restyle()
        self.place()
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()
        self.input.selectAll()
        self.status.hide()
        if listen and self.voice_ready():
            self.start_listening()  # the beep is the spoken cue; a greeting would be picked up by the microphone
        elif not listen:
            where = f"about {app.title()}" if app else "about your browser"
            self.owner.speaker.say(f"Ask Klicky {where}.")

    def voice_ready(self):
        settings = self.owner.settings
        if not settings.voice:
            return False
        if self.voice_factory:
            return True
        from .voice import model_installed
        if model_installed(settings.voice_model):
            return True
        self.set_status("inactive", "Type your question. For voice, run scripts\\get_speech_model.bat once.")
        return False

    @property
    def listening(self):
        return bool(self.listener and self.listener.isRunning())

    def toggle_listening(self):
        if self.listening:
            self.stop_listening()
        elif self.voice_ready():
            self.start_listening()

    def start_listening(self):
        if self.listening or (self.worker and self.worker.isRunning()):
            return
        self.owner.speaker.stop()  # never listen to Klicky's own voice
        from .voice import VoiceWorker
        self.listener = self.voice_factory() if self.voice_factory else VoiceWorker(self.owner.settings.voice_model)
        self.listener.level.connect(lambda value: self.level.setValue(int(value * 100)))
        self.listener.stage.connect(self.voice_stage)
        self.listener.heard.connect(self.on_heard)
        self.listener.failed.connect(lambda message: self.set_status("error", message))
        self.listener.finished.connect(lambda: self.show_listening(False))
        self.show_listening(True)
        self.listener.start()

    def stop_listening(self):
        if self.listening:
            self.listener.stop_event.set()

    def show_listening(self, on):
        self.mic.setText("Stop" if on else "Speak")
        self.mic.setAccessibleName("Stop listening" if on else "Speak your question")
        self.mic.setProperty("listening", "true" if on else "false")
        self.mic.style().unpolish(self.mic)
        self.mic.style().polish(self.mic)
        self.level.setValue(0)
        self.level.setVisible(on)
        QTimer.singleShot(0, self.adjustSize)

    def voice_stage(self, stage):
        if stage == "listening":
            self.set_status("processing", "Listening... ask your question, or just start typing.")
        elif stage == "transcribing":
            self.level.hide()
            self.set_status("processing", "Got it. Working out what you said...")
        elif stage == "stopped":
            self.set_status("inactive", "Stopped listening. Type your question or press Speak.")

    def on_heard(self, text):
        from .planning import parse_task
        self.input.setText(text)
        self.asked_by_voice = True
        try:
            parse_task(text, self.owner.settings.engine)
            is_search = True
        except UserError:
            is_search = False
        if is_search:
            self.hide()
            self.owner.run_search(text)
            return
        # Spoken questions are free-form; let retrieval decide whether a guide matches.
        self.ask(" ".join(text.split())[:500])

    def place(self):
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        width = min(area.width() - 40, max(720, self.owner.settings.font_px * 34))
        self.setFixedWidth(width)
        self.max_answer = int(area.height() * .55)
        self.adjustSize()
        self.move(area.x() + (area.width() - width) // 2, area.y() + int(area.height() * .12))

    def set_status(self, state, message):
        self.status.setText(message)
        self.status.setStyleSheet(f"color:{self.profile.states[state]};")
        self.status.setVisible(bool(message))
        if state == "error":
            self.owner.speaker.say(message, force=self.asked_by_voice)
        QTimer.singleShot(0, self.adjustSize)

    def ask_suggestion(self, text):
        self.input.setText(f"How do I {text[0].lower() + text[1:]}?")
        self.submit()

    def submit(self):
        if self.worker and self.worker.isRunning():
            return
        self.stop_listening()
        self.asked_by_voice = False
        from .planning import route, HelpQuestion
        text = self.input.text()
        try:
            routed = route(text, self.owner.settings.engine)
        except UserError as exc:
            self.set_status("error", str(exc))
            return
        if not isinstance(routed, HelpQuestion):
            self.hide()
            self.owner.run_search(text)
            return
        self.ask(routed.question)

    def ask(self, question, factory=None):
        settings = self.owner.settings
        # A browser named in the question wins; otherwise answer for the browser the shortcut was pressed in.
        if self.context_app and settings.rag_app == "auto" and detect_app(question) is None:
            settings = replace(settings, rag_app=self.context_app)
        self.answer = None
        self.view.hide()
        self.nav.hide()
        self.chips_box.hide()
        self.set_running(True)
        self.worker = AnswerWorker(settings, question, factory)
        self.worker.status.connect(self.set_status)
        self.worker.answered.connect(self.show_answer)
        self.worker.finished.connect(lambda: self.set_running(False))
        self.worker.start()

    def set_running(self, running):
        self.input.setEnabled(not running)
        self.go.setEnabled(not running)
        if not running:
            self.input.setFocus()

    def show_answer(self, answer):
        self.answer, self.step = answer, 0
        self.render()
        p = self.profile
        self.owner.speaker.say(answer.spoken() if not (p.one_step and answer.grounded) else f"{answer.title}. Step 1. {answer.steps[0]}",
                               force=self.asked_by_voice)

    def show_step(self, index):
        if self.answer and self.answer.steps:
            self.step = max(0, min(index, len(self.answer.steps) - 1))
            self.render()
            self.owner.speaker.say(f"Step {self.step + 1}. {self.answer.steps[self.step]}", force=self.asked_by_voice)

    def render(self):
        text, one_step = answer_html(self.answer, self.profile, self.step)
        self.view.setHtml(text)
        self.view.show()
        self.nav.setVisible(one_step)
        if one_step:
            self.back.setEnabled(self.step > 0)
            self.next.setEnabled(self.step < len(self.answer.steps) - 1)
        # Fit once the layout has given the view its real width, then again in case wrapping changed.
        QTimer.singleShot(0, self.fit)
        QTimer.singleShot(60, self.fit)

    def fit(self):
        """Grow the answer to its content, up to 55% of the screen; longer answers scroll."""
        if not self.view.isVisible():
            return
        document = self.view.document()
        # Measure at full width; a scrollbar only appears when the answer is taller than the cap.
        document.setTextWidth(self.view.width() - 2 * self.view.frameWidth())
        # Qt under-measures paragraphs with extra line-height, so allow most of one more line.
        height = int(document.size().height() + self.view.fontMetrics().lineSpacing() * self.profile.line_height / 100 * .8) + 6
        fits = height <= self.max_answer
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff if fits else Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setFixedHeight(height if fits else self.max_answer)
        self.adjustSize()

    def escape(self):
        if self.listening:
            self.stop_listening()
            return
        if self.worker and self.worker.isRunning():
            self.worker.stop_event.set()
            return
        self.close_popup()

    def close_popup(self):
        hwnd, self.return_hwnd = self.return_hwnd, None
        self.stop_listening()
        self.owner.speaker.stop()  # closing the popup also silences an answer being read out
        self.hide()
        if hwnd:
            try:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except (AttributeError, OSError):
                pass
